"""Datatypes for use with the Automated Peeler Interface."""

import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

ERROR_MAP = {
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


class ErrorCode(int, Enum):
    """Error codes returned by the peeler."""

    NO_ERROR = 0
    CONVEYOR_MOTOR_STALLED = 1
    ELEVATOR_MOTOR_STALLED = 2
    TAKE_UP_SPOOL_STALLED = 3
    SEAL_NOT_REMOVED = 4
    ILLEGAL_COMMAND = 5
    NO_PLATE_FOUND = 6
    OUT_OF_TAPE_OR_BROKE = 7
    PARAMETERS_NOT_SAVED = 8
    STOP_BUTTON_PRESSED_WHILE_RUNNING = 9
    SEAL_SENSOR_UNPLUGGED_OR_BROKE = 10
    LESS_THAN_30_SEALS_LEFT = 20
    LESS_THAN_30_SEALS_ROOM_ON_TAKEUP = 21
    EMERGENCY_STOP_POWER_RELAY = 51
    CIRCUITRY_FAULT_DETECTED = 52


class ReadyMessage(BaseModel):
    """
    Message indicating that the peeler is ready to accept a command.
    """

    error_codes: list[ErrorCode] = Field(
        default_factory=list,
        description="List of error codes indicating the status of the peeler.",
    )
    error_messages: list[str] = Field(
        default_factory=list,
        description="List of error messages corresponding to the error codes.",
    )
    message_received: Optional[float] = Field(
        default_factory=time.time, description="The time the message was received."
    )

    @classmethod
    def from_message(cls, message: str) -> "ReadyMessage":
        """
        Create a ReadyMessage from a message string.

        :param message: The message string received from the peeler.
        :return: A ReadyMessage object.
        """
        if not message.startswith("*ready:"):
            raise ValueError("Invalid message format. Expected '*ready:' prefix.")
        message = message[7:].strip()
        error_codes = [ErrorCode(int(code)) for code in message.split(",")]
        error_messages = [
            ERROR_MAP.get(str(int(code)).zfill(2), "Unknown error code")
            for code in error_codes
        ]
        return cls(error_codes=error_codes, error_messages=error_messages)
