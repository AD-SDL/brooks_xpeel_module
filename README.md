# Brooks XPeel Module

Provides a python driver and MADSci-compatible REST interface for the Brooks XPeel peeler instrument.

## Current Features

* Peeler initialization
* Peeler information (version number, current status, tape remaining, etc.)
* Basic movements (move conveyor, spool, reset microplate, etc.)
* Execute peeling
* Change sensor threshold value
* Displays up to 3 error messages at at ime

## User Guide

### Python Installation

```
git clone https://github.com/ad-sdl/brooks_xpeel_module.git
cd brooks_xpeel_module
python -m venv .venv && src .venv/bin/activate
pip install -e .
```

To run the MADSci REST node, use the following command (updating arguments as needed)

```
python -m peeler_rest_node --port 2001 --device /dev/ttyUSB0
```

### Docker Installation

After installing and configuring docker, run

```
git clone https://github.com/ad-sdl/brooks_xpeel_module.git
cd brooks_xpeel_module
cp example.env .env
# Set appropriate values in the .env file before running the next commands
docker compose build
docker compose up
```

## Using the Driver

### Sending commands to XPeel:

* Connect XPeel Driver to device with a serial to usb cable.
* Find XPeel port ex: "/dev/ttyUSB0"

In Python:

```
	from brooks_xpeel_driver import BROOKS_PEELER_DRIVER
	peeler = BROOKS_PEELER_DRIVER("/dev/ttyUSB0")
```

* Send commands (provided below)

### Commands

1.     peeler.check_status()

Identifies up to 3 errors currently present.

2.     peeler.check_version()

Identifies the XPeel virmware version.

3.     peeler.reset()

This command causes the spool to advance a few inches to fresh tape, and the elevator and conveyor axes to return to the home and ready for plate pick up position. A good use for the reset command is to ensure that fresh tape is presented after a long period of inactivity.

4.     peeler.restart()

This command causes the XPeel to restart; the same as turning the power off and back on.

5.     peeler.peel(Set Number, Time)

This command has a number of parameters that can be selected to achieve better performance on difficult or unusual seal types. For most seals the default and fastest settings will give good
performance. In an automated environment it may be advisable to be more conservative, or to provide
for a retry at slower settings when the XPeel detects that a seal is not removed.

Parameter sets 1-8 are fixed; parameter set 9 can be set and saved manually by the user.

| Set Number | Begin Peel Location | Speed  |
|------------|---------------------|--------|
| 1          | Default -2 mm       | fast   |
| 2          | Default -2 mm       | slow   |
| 3          | Default             | fast   |
| 4          | Default             | slow   |
| 5          | Default +2 mm       | fast   |
| 6          | Default +2 mm       | slow   |
| 7          | Default +4 mm       | fast   |
| 8          | Default +4 mm       | slow   |
| 9          | custom              | custom |


The second parameter, refers to adhere time in seconds.

6.     peeler.seal_check()

The ‘sealcheck’ command causes the conveyor to place the plate under the reflective seal detection
sensor and the elevator to move down to the proper sensing elevation. The sensor status is then
recorded. The elevator and conveyor axes then return to the home and ready for plate pick up
position. Since this action only checks the plate at one location, a better indicator is the error code
that will be generated during a normal desealing operation where the plate is scanned over most of its
length. The ‘sealcheck’ command is useful, however, to verify that the sensor parameters are set
correctly to detect a particular seal type.

7.     peeler.tape_remaining()

The XPeel calculates the amount of tape remaining on the supply spool by comparing the travel of the
conveyor to the rotation of both the supply and take-up spools. After a completed ‘XPeel’ operation, a
‘tapeleft’ command can be issued to verify the amount of tape left as well as the space remaining on
the take-up spool. These calculations are not perfectly accurate but they will provide sufficient
warning to avoid running out of tape unexpectedly.

8.     peeler.plate_check(y or n?)

This command sets the plate check parameter to yes or no.

9.     peeler.sensor_threshold()

This command reports the threshold value of the seal detected sensor.

10.     peeler.sensor_threshold_higher(Threshold Value)

Setting the seal detected threshold value for the seal present if higher than threshold.

The Threshold Value refers to the 3 digit threshold value. This command sets the seal detected threshold so that during an XPeel, sensor readings higher than this value represents an un-removed seal and will
result in an error 04, “seal not removed”, message.

11.     peeler.sensor_threshold_lower(Threshold Value)

Setting the seal detected threshold value for the seal present if lower than threshold.

Where Threshold Value refers to the 3 digit threshold value. This command sets the seal detected threshold so that during an XPeel, sensor readings lower than this value represents an un-removed seal and will
result in an error 04, “seal not removed”, message.

12.     peeler.conveyor_out()

This command causes the conveyor to move out towards the user 7mm each time the command is called. When the conveyor reaches it’s fully extended home position no movement
occurs.

13.     peeler.conveyor_in()

This command causes the conveyor to move in to the default ‘begin peel’ position.

14.     peeler.elevator_down()

This command causes the elevator to move down until it is stopped by a plate or reaches its lower limit. The plate check option is disabled for this command.

15.     peeler.elevator_up()

This command causes the elevator to move up approximately 1.5mm each time the
command is called until the elevator reaches it full up home position.

16.     peeler.move_spool()

This command causes the spool to advance approximately 10mm of tape.
