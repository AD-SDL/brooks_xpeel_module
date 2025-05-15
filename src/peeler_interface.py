"""Driver code to communicate with and control a Brooks Xpeel Peeler instrument."""

import re
import threading
import time
from typing import Any, Optional

import serial
from madsci.client.event_client import EventClient
from madsci.client.resource_client import ResourceClient
from madsci.common.types.resource_types import DiscreteConsumable, Slot

from peeler_datatypes import ErrorCode, ReadyMessage


class Peeler:
    """
    Description:
    Python interface that allows remote commands to be executed to the Peeler.
    """

    connection: Optional[serial.Serial] = None
    ready_message: Optional[ReadyMessage] = None
    acknowledged: bool = False

    def __init__(
        self,
        device_path: str = "/dev/ttyUSB0",
        baud_rate: int = 9600,
        resource_client: ResourceClient = None,
        plate_carrier: Optional[Slot] = None,
        tape_supply: Optional[DiscreteConsumable] = None,
        tape_takeup: Optional[DiscreteConsumable] = None,
        logger: EventClient = None,
    ) -> None:
        """
        This function initializes the data to be called and modified in other locations in the client.
        """

        self.device_path = device_path
        self.baud_rate = baud_rate
        self.resource_client = resource_client
        self.plate_carrier = plate_carrier
        self.tape_supply = tape_supply
        self.tape_takeup = tape_takeup
        self.logger = logger or EventClient()
        self.serial_lock = threading.Lock()
        self._device_lock = threading.Lock()

    def __del__(self) -> None:
        """
        Closes the connection to the device when the object is deleted.
        """
        self.disconnect()

    def connect(self) -> None:
        """
        Connect to serial port / If wrong port entered inform user
        """

        self.connection = serial.Serial(self.device_path, self.baud_rate)
        if not self.connection.is_open:
            raise serial.SerialException("Failed connecting to the device.")
        self.get_status()

    def disconnect(self) -> None:
        """
        Closes the serial connection to the device.
        """
        if self.connection and self.connection.is_open:
            self.connection.close()
        else:
            pass

    @staticmethod
    def construct_command(command: str, *args: Any) -> str:
        """
        Constructs a command string to be sent to the device.
        """
        return (
            f"*{command}\r\n"
            if not args
            else f"*{command}:{''.join(map(str, args))}\r\n"
        )

    def read_messages(self) -> list[str]:
        """
        Reads messages from the serial port and store results.
        """
        if not self.connection or not self.connection.is_open:
            self.connect_sealer()

        messages = []
        with self.serial_lock:
            try:
                while self.connection.in_waiting > 0:
                    message = self.connection.readline().decode("utf-8")
                    if message:
                        self.logger.log_info(f"Received message: {message}")
                        messages.append(self.process_message(message))
            except serial.SerialException as e:
                self.logger.error(f"Serial error: {e}")
            except Exception as e:
                self.logger.error(f"Error reading messages: {e}")
        return messages

    def process_message(self, message: str) -> None:
        """Process messages received from the serial port."""

        # *Remove everything in message before the first '*'
        star_index = message.find("*")
        message = message[star_index:].strip()

        if message.startswith("*ready:"):
            self.ready_message = ReadyMessage.from_message(message)
        if message.startswith("*ack"):
            self.acknowledged = True
        return message

    def send_command(self, command: str, timeout: float = 60) -> str:
        """
        Sends provided command to Peeler and stores data outputted by the peeler.
        Indicates when the confirmation that the Peeler received the command by displaying 'ACK TRUE.'
        """

        if self.connection is None or not self.connection.is_open:
            self.connect()

        ready_timer = time.time()

        with self.serial_lock:
            self.acknowledged = False
            self.connection.write(command.encode("utf-8"))

        # Waits till there is "ready" in the response_buffer indicating
        # the command is done executing.
        messages = []
        while time.time() - ready_timer < timeout:
            messages.extend(self.read_messages())
            if self.ready_message and self.ready_message.message_received > ready_timer:
                self.logger.log_debug(f"Received ready message: {self.ready_message}")
                break

        return messages

    def get_status(self) -> str:
        """
        Checks if there are currently any errors.
        """
        with self._device_lock:
            self.send_command(self.construct_command("stat"))
        return self.ready_message

    def check_version(self) -> str:
        """
        Checks firmware version number.
        """
        with self._device_lock:
            messages = self.send_command(self.construct_command("version"))
        for message in messages:
            if message.startswith("*") and not message.startswith("*ready:"):
                return message[1:]
        return "Unknown version"

    def reset(self) -> bool:
        """
        Returns elevator and conveyor to home location and gets fresh tape in place to use.
        """
        with self._device_lock:
            self.send_command(self.construct_command("reset"))
        return self.acknowledged

    def restart(self) -> bool:
        """
        Turns Peeler power off and on.
        """
        with self._device_lock:
            self.send_command(self.construct_command("restart"))
        return self.acknowledged

    def peel(self, param_set_num: int = 1, param_time: float = 2.5) -> None:
        """
        Removes seal based on the parameters given for the location to start peeling, the speed, and adhere time.
        """
        with self._device_lock:
            peel_dict = {
                1: ["default -2 mm", "fast"],
                2: ["default -2 mm", "slow"],
                3: ["default", "fast"],
                4: ["default", "slow"],
                5: ["default +2 mm", "fast"],
                6: ["default +2 mm", "slow"],
                7: ["default +4 mm", "fast"],
                8: ["default +4 mm", "slow"],
                9: ["custom", "custom"],
            }
            if param_set_num not in peel_dict:
                raise ValueError(
                    f"Invalid parameter set number: {param_set_num}. Must be between 1 and 9."
                )

            self.send_command(
                self.construct_command("xpeel", param_set_num, int(param_time / 2.5))
            )
        if not self.acknowledged or any(
            error != 0 for error in self.ready_message.error_codes
        ):
            raise Exception(
                f"Peel command failed with error codes: {self.ready_message.error_codes}"
            )
        try:
            if self.resource_client and self.plate_carrier:
                self.plate_carrier = self.resource_client.get_resource(
                    self.plate_carrier.resource_id
                )
                if self.plate_carrier.children:
                    plate_resource = self.plate_carrier.children[0]
                    plate_resource.attributes["sealed"] = False
                    self.resource_client.update_resource(plate_resource)
        except Exception as e:
            self.logger.log_error(
                f"Failed to update resource client with result of peel: {e}"
            )

    def seal_check(self) -> bool:
        """
        Checks if there is any seal on the plate.
        """
        with self._device_lock:
            self.send_command(self.construct_command("sealcheck"))
        if not self.acknowledged:
            raise Exception(
                f"Seal check command failed with error codes: {self.ready_message.error_codes}"
            )
        return self.ready_message.error_codes[0] == ErrorCode.SEAL_NOT_REMOVED

    def tape_remaining(self) -> tuple[int, int]:
        """
        Checks how much tape is left on the supply spool and take-up spool in deseals.
        """
        with self._device_lock:
            messages = self.send_command(self.construct_command("tapeleft"))

        tape_message = ""
        for message in messages:
            if message.startswith("*tape:"):
                tape_message = message
                break
        else:
            raise ValueError("No response from tape remaining command.")

        matches = re.search(r"\*tape:(\d+),(\d+)", tape_message)

        deseals_supply = int(matches[1]) * 10
        deseals_take = int(matches[2]) * 10
        try:
            if self.resource_client:
                if self.tape_supply:
                    self.resource_client.set_quantity(self.tape_supply, deseals_supply)
                if self.tape_takeup:
                    self.resource_client.set_quantity(self.tape_takeup, deseals_take)
        except Exception as e:
            self.logger.log_error(
                f"Failed to update resource client with tape remaining: {e}"
            )
        return deseals_supply, deseals_take

    def plate_check(self, enable: bool) -> None:
        """
        Set whether to check for a plate before peeling.
        If plate check set to yes, the XPeel process is prevented from taking place if there is no plate detected on the plate tray.
        """
        with self._device_lock:
            self.send_command(
                self.construct_command("platecheck", ("y" if enable else "n"))
            )
        if not self.acknowledged:
            raise Exception(
                f"Plate check command failed with error codes: {self.ready_message.error_codes}"
            )
        return self.acknowledged

    def get_sensor_threshold(self) -> str:
        """
        Displays sensor threshold value to ensure that the seal has been removed.
        """
        with self._device_lock:
            messages = self.send_command(self.construct_command("sealstat"))

        if not self.acknowledged:
            raise Exception(
                f"Sensor threshold command failed with error codes: {self.ready_message.error_codes}"
            )

        response = ""
        for message in messages:
            if message.startswith("*seal:"):
                response = message
                break
        else:
            raise ValueError("No response from seal status command.")

        return re.search(r"\*seal:(\d+)", response)[1]

    def sensor_threshold_higher(self, seal_higher_input: int) -> None:
        """
        Sets the seal detected threshold value for the seal present if higher than threshold.
        """
        with self._device_lock:
            messages = self.send_command(
                self.construct_command(
                    "sealhigher", str(int(seal_higher_input)).zfill(3)
                )
            )

        if not self.acknowledged:
            raise Exception(
                f"Sensor threshold higher command failed with error codes: {self.ready_message.error_codes}"
            )
        response = ""
        for message in messages:
            if message.startswith("*seal:"):
                response = message
                break
        else:
            raise ValueError("No response from seal status command.")
        return re.search(r"\*seal:(\d+)", response)[1]

    def sensor_threshold_lower(self, seal_lower_input: int) -> None:
        """
        Sets the seal detected threshold value for the seal present if lower than threshold.
        """
        with self._device_lock:
            messages = self.send_command(
                self.construct_command("seallower", str(int(seal_lower_input)).zfill(3))
            )
        if not self.acknowledged:
            raise Exception(
                f"Sensor threshold lower command failed with error codes: {self.ready_message.error_codes}"
            )
        response = ""
        for message in messages:
            if message.startswith("*seal:"):
                response = message
                break
        else:
            raise ValueError("No response from seal status command.")
        return re.search(r"\*seal:(\d+)", response)[1]

    def conveyor_out(self) -> None:
        """
        Moves the conveyor out 7mm at a time.
        """
        with self._device_lock:
            self.send_command(self.construct_command("moveout"))
        if not self.acknowledged:
            raise Exception(
                f"Conveyor out command failed with error codes: {self.ready_message.error_codes}"
            )

    def conveyor_in(self) -> None:
        """
        Moves conveyor in to the "begin peel" position.
        """
        with self._device_lock:
            self.send_command(self.construct_command("movein"))
        if not self.acknowledged:
            raise Exception(
                f"Conveyor in command failed with error codes: {self.ready_message.error_codes}"
            )

    def elevator_down(self) -> None:
        """
        Moves elevator down until it is stopped by a plate or the limit switch.
        """
        with self._device_lock:
            self.send_command(self.construct_command("movedown"))
        if not self.acknowledged:
            raise Exception(
                f"Elevator down command failed with error codes: {self.ready_message.error_codes}"
            )

    def elevator_up(self) -> None:
        """
        Moves elevator up 1.5 mm at a time until it reaches the top (home) position.
        """
        with self._device_lock:
            self.send_command(self.construct_command("moveup"))
        if not self.acknowledged:
            raise Exception(
                f"Elevator up command failed with error codes: {self.ready_message.error_codes}"
            )

    def move_spool(self) -> None:
        "Advances the spool 10 mm of tape"
        with self._device_lock:
            self.send_command(self.construct_command("movespool"))
        if not self.acknowledged:
            raise Exception(
                f"Move spool command failed with error codes: {self.ready_message.error_codes}"
            )


if __name__ == "__main__":
    """
    Runs get status function.
    """

    peeler = Peeler("/dev/ttyUSB1")
    peeler.get_status()
    peeler.seal_check()
