# Third-party notices

SmartDrill Pro is built from mature open-source components. This summary must be shipped with release artifacts. Full license texts remain in the installed packages and in `resources/third_party_licenses/` when populated by a release build.

## Bundled with the main Windows application

| Component | License | Notice |
| --- | --- | --- |
| PySide6 / Qt | LGPL-3.0 or commercial | GUI framework. Dynamic linking; preserve notices and allow relinking. |
| Gerbonara 1.6.3 | Apache-2.0 | Gerber/Excellon parsing. Include its LICENSE and NOTICE files. |
| Shapely | MIT | Geometry conversion and bounds. |
| NumPy | BSD-3-Clause | Numeric support for geometry. |
| pyserial | BSD-3-Clause | Serial transport. |
| pytest | MIT | Development/testing only; not required at runtime. |

## Separate headless worker (not part of the main executable)

| Component | License | Notice |
| --- | --- | --- |
| FlatCAM 2024.4 (`vika-sonne/FlatCAM`) | MIT | Copyright (c) 2023 vika-sonne; Copyright (c) 2014-2019 Juan Pablo Caram. Used as an isolated process. SmartDrill applies small headless compatibility patches at runtime; these are documented in `app/cam/flatcam_adapter.py`. |

## Separate firmware / external tools (not bundled)

| Component | License | Notice |
| --- | --- | --- |
| grblHAL core + ESP32 driver | GPL-3.0-or-later | Flashed separately onto the ESP32-S3 controller. Firmware binaries are **not** included in our installer. |
| Universal Gcode Sender | GPL-3.0 | No UGS source code is used. Only documented GRBL protocol constants inform `app/machine/`. |
| KiCad | GPL-3.0-or-later (+ exceptions) | Optional external CLI; not bundled or modified. |

## Project code

SmartDrill Pro application code is licensed under the MIT License. See `LICENSE` for the full text.

A commercial release requires a legal review of PySide6/Qt licensing and of any decision to bundle GPL firmware binaries.
