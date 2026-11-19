# Phase 8 report - Hardware integration (UNVERIFIED)

## Status

**No physical ESP32-S3 board, grblHAL controller, spindle or CNC machine was connected during development.** Every statement about real hardware in this project is therefore **UNVERIFIED** and must be confirmed by the operator.

## Delivered

- `app/ui/pages/machine_config.py`: editable machine profile (profile name, steps/mm, travel, feed and acceleration per axis, homing/limits/spindle flags, calibration acknowledgement). The page always displays an UNVERIFIED warning and saves to `settings.json`.
- `app/ui/pages/settings_page.py`: simulation/real mode, baud rate, RX buffer size, status interval, conservative safety limits and FlatCAM paths.
- `config/machine_profiles.py`: `MachineProfile.validate()` rejects zero/negative calibration values.
- `config/default_settings.py` and `app/core/application.py`: active profile is persisted and restored across restarts.
- Machine Control's **Identify ($I / $$)** button reads controller identification/settings through the protocol layer and shows them in the UI.
- `docs/14_hardware_setup.md`: staged, beginner-friendly checklist for flashing grblHAL, wiring limits/homing/spindle, calibrating steps/mm, low-power dry runs and progressive cutting tests.

## Verification performed

- 35 automated tests pass, including machine profile validation and persistence.
- Offscreen UI smoke test constructs Machine Configuration and Settings pages.
- The simulator answers `$I` and `$$`; no real serial port was opened.

## Required physical verification (not performed)

1. Flash grblHAL unchanged for the specific ESP32-S3 board using the verified `generic_s3_map.h` and `sdkconfig.defaults.esp32s3` described in the research report.
2. Confirm `$I`/`$$` values over USB serial and enter measured steps/mm and travel limits in Machine Configuration.
3. Test limit switches, homing direction, emergency stop and spindle enable with the machine disabled/low power.
4. Dry-run a simple validated job with the spindle off and the workpiece removed.
5. Only then perform progressive material cuts while supervising the machine.

The software never auto-executes generated G-code; running a job always requires an explicit validated copy and operator confirmation.
