# ESP32-S3 / grblHAL hardware setup (UNVERIFIED)

> This guide was written without physical hardware. Treat every electrical and motion step as unverified. If you are unsure about wiring or safety, stop and ask a qualified person.

## 1. Firmware

- Use grblHAL **unchanged** from its upstream repository.
- Confirm the ESP32-S3 board map: `generic_s3_map.h` and `sdkconfig.defaults.esp32s3` were identified in Phase 1 research.
- Flash using the toolchain documented by grblHAL for your exact board. Record the firmware version reported by `$I`.
- Do not modify grblHAL source inside this repository.

## 2. First connection

1. In SmartDrill Pro open **Settings** and confirm **Simulation mode** is enabled until the machine is physically ready.
2. Connect the ESP32-S3 by USB. Install the driver your board requires.
3. Open **Machine Configuration** and note the UNVERIFIED warning.
4. When ready, disable Simulation mode, choose the serial port in **Machine Control**, and press **Connect**.
5. Press **Identify ($I / $$)**. Compare the returned values with the controller datasheet and your wiring.

## 3. Electrical and safety checks (operator must perform)

- Hardware emergency stop must be wired independently of this software.
- Verify limit switches with `$` diagnostics before enabling homing.
- Verify endstop directions by moving axes a few millimetres at a time with the spindle off.
- Confirm spindle enable direction, RPM range and anything connected to a relay or VFD.
- Confirm the machine's physical travel is smaller than the configured soft limits.

## 4. Calibration

1. Command a known move (for example 10 mm) with the spindle off and measure the real travel with a ruler or caliper.
2. New steps/mm = old steps/mm x commanded distance / measured distance.
3. Enter the new values in **Machine Configuration** and save.
4. Repeat for X, Y and Z; then set measured travel limits and conservative feeds/accelerations.
5. Tick **I have calibrated this profile on real hardware** only after completing these checks.

## 5. Dry run

- Remove the workpiece and tool or remove power from the spindle.
- Home the machine, set work zero, then run a small `*.validated.nc` file from **Machine Control** with the confirmation checkbox.
- Watch the toolpath from a safe position and keep a hand near the hardware emergency stop.
- Use **Feed hold** and **Soft reset** to practise stopping the job.

## 6. Progressive material tests

- Start with low spindle speed and shallow depth in a non-critical material.
- Increase depth/feed gradually after each successful supervised run.
- Review CAM parameters against the actual tool, material and machine before every job.

Known software limitation: continuous status polling and soft-limit enforcement during jogging are not implemented. The operator must supervise every move.
