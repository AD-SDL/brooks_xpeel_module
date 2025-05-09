"""Driver code to communicate with and control a Brooks Xpeel Peeler instrument."""

import re
import time

import serial


class Peeler:
    """
    Description:
    Python interface that allows remote commands to be executed to the Peeler.
    """

    def __init__(self, host_path, baud_rate=9600):
        """
        This function initializes the data to be called and modified in other locations in the client.
        """

        self.host_path = host_path
        self.baud_rate = baud_rate
        self.peeler_output = ""
        self.status_msg = ""
        # self.version = self.check_version()
        self.tape_remaining_var = 0
        self.sensor_threshold_var = 0
        self.error_msg = ""
        self.movement_state = "READY"
        self.connection = None
        self.connect_peeler()

    def connect_peeler(self):
        """
        Connect to serial port / If wrong port entered inform user
        """

        try:
            self.connection = serial.Serial(self.host_path, self.baud_rate)
        except Exception as e:
            raise Exception("Could not establish connection") from e

    def response_fun(self, time_wait):
        """
        Records the data outputted by the Peeler and sets it to equal "" if no data is outputted in the provided time.
        """

        response_timer = time.time()
        while time.time() - response_timer < time_wait:
            if self.connection.in_waiting != 0:
                response = self.connection.read_until(expected=b"\r")
                # print(response)
                response_string = response.decode("utf-8")
                break
            else:
                response_string = ""
        # print(response_string)
        return response_string

    def send_command(self, command, success_msg, err_msg, timeout=1):
        """
        Sends provided command to Peeler and stores data outputted by the peeler.
        Indicates when the confirmation that the Peeler received the command by displaying 'ACK TRUE.'
        """

        self.peeler_output = self.peeler_output + "Command: " + command + "\n"
        ready_timer = time.time()
        response_buffer = ""

        self.connection.write(command.encode("utf-8"))

        # Waits till there is "ready" in the response_buffer indicating
        # the command is done executing.
        while "ready" not in response_buffer:
            new_string = self.response_fun(timeout)

            if new_string != "":
                self.peeler_output = self.peeler_output + new_string + "\n"

            response_buffer = response_buffer + new_string

            # Indicates that command was received
            if "ack" in new_string:
                self.peeler_output = self.peeler_output + "ACK TRUE" + "\n"

            if time.time() - ready_timer > 20:
                break

        self.error(response_buffer)

        return response_buffer

    def error(self, response_buffer):
        """
        Decodes the error message outputted by the peeler.
        """

        error_dict = {
            "00": "",
            "01": "Error: Conveyor motor stalled",
            "02": "Error: Elevator motor stalled",
            "03": "Error: Take up spool staled",
            "04": "Error: Seal not removed",
            "05": "Error: Illegal Command",
            "06": "Error: No plate found",
            "07": "Error: Out of tape, or tape broke",
            "08": "Error: Parameters not saved",
            "09": "Error: Stop button pressed while running",
            "10": "Error: Seal Sensor unplugged or broke",
            "20": "Error: Less than 30 seals left on the supply roll",
            "21": "Error: Room for less than 30 seals on take up spool",
            "51": "Error: Emergency Stop: Power relay is not settable- i.e. cover open, or hardware problem",
            "52": "Error: Circuitry Fault Detected: Remove Power",
        }

        response_string = re.search(r"\*ready:(\d+,\d+,\d+)", response_buffer)
        error_code = response_string[1]

        first_error = error_code[0:2]
        second_error = error_code[3:5]
        third_error = error_code[6:8]
        if first_error == "00" and second_error == "00" and third_error == "00":
            error_code_msg = "No Errors"
        else:
            error_code_msg = (
                error_dict[first_error]
                + "\n"
                + error_dict[second_error]
                + "\n"
                + error_dict[third_error]
            )

        self.peeler_output = self.peeler_output + error_code_msg + "\n"

        # if "Error:" in error_code_msg:
        self.error_msg = error_code_msg

    def get_status(self):
        """
        Checks if there are currently any errors.
        """

        cmd_string = "*stat\r\n"
        success_msg = "Displaying status:"
        err_msg = "Displaying status:"

        status_response = self.send_command(cmd_string, success_msg, err_msg)
        msg_beginning = "*"
        msg_end = ":"
        self.status_msg = status_response[
            status_response.find(msg_beginning)
            + len(msg_beginning) : status_response.rfind(msg_end)
        ].upper()
        return status_response

    def check_version(self):
        """
        Checks firmware version number.
        """

        cmd_string = "*version\r\n"
        success_msg = "XPeel Firmware Version:"
        err_msg = "Failed to display XPeel firmware version"
        response = self.send_command(cmd_string, success_msg, err_msg)

        global matches_ver

        matches_ver = re.search(r"\*(\d+.\d+)", response)

        version = matches_ver[1]

        self.peeler_output = self.peeler_output + "Version = " + version + "\n"
        return version

    def reset(self):
        """
        Returns elevator and conveyor to home location and gets fresh tape in place to use.
        """
        self.movement_state = "BUSY"
        cmd_string = "*reset\r\n"
        success_msg = "Successful reset"
        err_msg = "Failed to reset"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def restart(self):
        """
        Turns Peeler power off and on.
        """
        self.movement_state = "BUSY"
        cmd_string = "*restart\r\n"
        success_msg = "Successful restart"
        err_msg = "Failed to restart"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def peel(self, param_set_num, param_time):
        """
        Removes seal based on the parameters given for the location to start peeling, the speed, and adhere time.
        """
        self.movement_state = "BUSY"

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
        cmd_string = "*xpeel:%s%s\r\n" % (param_set_num, int(param_time / 2.5))
        success_msg = "Successfully adjusted peel location to %s and speed to %s" % (
            peel_dict[param_set_num][0],
            peel_dict[param_set_num][1],
        )
        err_msg = "Failed to adjust peel location to %s and speed to %s" % (
            peel_dict[param_set_num][0],
            peel_dict[param_set_num][1],
        )
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def seal_check(self):
        """
        Checks if there is any seal on the plate.
        """
        self.movement_state = "BUSY"
        cmd_string = "*sealcheck\r\n"
        success_msg = "Successful seal check"
        err_msg = "Failed to conduct seal check"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def tape_remaining(self):
        """
        Checks how much tape is left on the supply spool and take-up spool in deseals.
        """
        self.movement_state = "BUSY"
        cmd_string = "*tapeleft\r\n"
        success_msg = (
            " deseals remaining on supply spool \n deseals remaining on take-up spool"
        )
        err_msg = "Failed to find amount of tape remaining"
        response = self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

        matches = re.search(r"\*tape:(\d+),(\d+)", response)

        deseals_supply = int(matches[1]) * 10
        deseals_take = int(matches[2]) * 10
        self.peeler_output = (
            self.peeler_output
            + "Deseals on supply spool: "
            + str(deseals_supply)
            + "\n"
        )
        self.peeler_output = (
            self.peeler_output + "Deseals on take-up spool: " + str(deseals_take) + "\n"
        )
        return deseals_supply, deseals_take

    def plate_check(self, pc_yn=""):
        """
        If plate check set to yes, the XPeel process is prevented from taking place if there is no plate detected on the plate tray.
        """
        self.movement_state = "BUSY"
        # pc_yn = y for yes n for no
        pc_yn = input("Set platecheck to yes (y) or no (n): ")
        cmd_string = "*platecheck:%s\r\n" % (pc_yn)
        if pc_yn == "y":
            pc_yn_string = "yes"
        if pc_yn == "n":
            pc_yn_string = "no"
        success_msg = "Platecheck set to %s" % (pc_yn_string)
        err_msg = "Failed to set plate check to %s" % (pc_yn_string)
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def sensor_threshold(self, threshold_value="Not Found"):
        """
        Displays sensor threshold value to ensure that the seal has been removed.
        """

        cmd_string = "*sealstat\r\n"
        success_msg = "Threshold value of %s for the seal detected sensor" % (
            threshold_value
        )
        err_msg = "Failed to get threshold value"
        response = self.send_command(cmd_string, success_msg, err_msg)

        matches = re.search(r"\*seal:(\d+)", response)

        threshold_value = matches[1]

        self.peeler_output = (
            self.peeler_output + "Threshold Value: " + threshold_value + "\n"
        )
        return threshold_value

    def sensor_threshold_higher(
        self, seal_higher_input="", threshold_value_high="Not Found"
    ):
        """
        Sets the seal detected threshold value for the seal present if higher than threshold.
        """

        seal_higher_input = input("3 digit threshold value: ")
        cmd_string = "*sealhigher:%s\r\n" % (seal_higher_input)
        success_msg = "Threshold value of %s for the seal detected sensor" % (
            threshold_value_high
        )
        err_msg = "Failed to get threshold value"
        response = self.send_command(cmd_string, success_msg, err_msg)

        matches = re.search(r"\*seal:(\d+)", response)

        threshold_value_high = matches[1]

        self.peeler_output = (
            self.peeler_output + "Threshold Value: " + threshold_value_high + "\n"
        )

    def sensor_threshold_lower(
        self, seal_lower_input="", threshold_value_low="Not Found"
    ):
        """
        Sets the seal detected threshold value for the seal present if lower than threshold.
        """

        seal_lower_input = input("3 digit threshold value: ")
        cmd_string = "*seallower:%s\r\n" % (seal_lower_input)
        success_msg = "Threshold value of %s for the seal detected sensor" % (
            threshold_value_low
        )
        err_msg = "Failed to get threshold value"
        response = self.send_command(cmd_string, success_msg, err_msg)

        matches = re.search(r"\*seal:(\d+)", response)

        threshold_value_low = matches[1]

        self.peeler_output = (
            self.peeler_output + "Threshold Value: " + threshold_value_low + "\n"
        )

    def conveyor_out(self):
        """
        Moves the conveyor out.
        """
        self.movement_state = "BUSY"
        cmd_string = "*moveout\r\n"
        success_msg = "Successfully moved conveyor out"
        err_msg = "Failed to move conveyor out"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def conveyor_in(self):
        """
        Moves conveyor in.
        """
        self.movement_state = "BUSY"
        cmd_string = "*movein\r\n"
        success_msg = "Successfully moved conveyor in"
        err_msg = "Failed to move conveyor in"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def elevator_down(self):
        """
        Moves elevator down.
        """
        self.movement_state = "BUSY"
        cmd_string = "*movedown\r\n"
        success_msg = "Successfully moved elevator down"
        err_msg = "Failed to move elevator down"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def elevator_up(self):
        """
        Moves elevator up.
        """
        self.movement_state = "BUSY"
        cmd_string = "*moveup\r\n"
        success_msg = "Successfully moved elevator up"
        err_msg = "Failed to move elevator up"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"

    def move_spool(self):
        "Advances the spool 10 mm of tape"
        self.movement_state = "BUSY"
        cmd_string = "*movespool\r\n"
        success_msg = "Successfully moved spool 10 mm"
        err_msg = "Failed to move spool 10 mm"
        self.send_command(cmd_string, success_msg, err_msg)
        self.movement_state = "READY"


if __name__ == "__main__":
    """
    Runs get status function.
    """

    peeler = Peeler("/dev/ttyUSB1")
    peeler.get_status()
    print(peeler.status_msg)
    peeler.seal_check()
