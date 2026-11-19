# License compliance plan

Licenses were verified from upstream metadata and license files on 2026-11-19.

| Component | Version | License | How we use it | Obligation |
| --- | --- | --- | --- | --- |
| FlatCAM (`vika-sonne/FlatCAM`) | 2024.4 | **MIT** | Separate headless worker process for CAM | Preserve copyright + MIT notice in distributions; no source changes required |
| Gerbonara | 1.6.3 | **Apache-2.0** | Gerber/Excellon parsing and layer classification | Include LICENSE and NOTICE; state changes if modified |
| PyGerber | 2.4.3 | MIT | Evaluated, not currently vendored | None unless used |
| Universal Gcode Sender | 2.x | **GPL-3.0** | Read for protocol concepts only; no code copied | Do not copy source; cite documentation/protocol |
| grblHAL core + ESP32 driver | current | **GPL-3.0-or-later** | Flashed firmware on separate controller | Distribute firmware under GPL terms if we distribute binaries; keep controller separate from app |
| pcb2gcode | current | GPL-3.0 | Evaluated fallback, invoked as external CLI if ever used | Keep as separate process; no code copying |
| KiCad | 9/10 | GPL-3.0-or-later (+ exceptions) | External optional CLI only | Do not bundle or modify KiCad |
| PySide6 / Qt | current | **LGPL-3.0** (or commercial) | GUI framework | Dynamic linking, provide license/notice, allow relinking; review before commercial distribution |
| pyserial | current | BSD-3-Clause | Serial transport | Retain license notice |
| Shapely | current | MIT | Geometry | Retain notice |
| NumPy | current | BSD-3-Clause | Geometry/math | Retain notice |
| pytest | current | MIT | Tests only | None in distributed app |

## Rules for this repository

1. Never copy FlatCAM, UGS, grblHAL or KiCad source into `app/` without an explicit license review and a notice file.
2. When a dependency is vendored or bundled into a PyInstaller build, add its license text to `resources/third_party_licenses/`.
3. Keep a generated `THIRD_PARTY_NOTICES.md` in release artifacts.
4. FlatCAM's MIT notice must be shipped with the worker environment. Its copyright lines are:
   - Copyright (c) 2023 vika-sonne
   - Copyright (c) 2014-2019 Juan Pablo Caram
5. The GRBL protocol facts used in `app/machine/` come from public protocol documentation and UGS's published constants, not from copied source. Comments should reference the protocol, not UGS code.
6. A commercial distribution still needs a legal review for PySide6/Qt licensing and for the GPL firmware if firmware binaries are bundled with the installer.

## Practical packaging decision

The Windows installer will contain:

- SmartDrill Pro code and its own Python environment (LGPL/BSD/MIT/Apache components with notices).
- A separate FlatCAM worker folder containing FlatCAM 2024.4 and its MIT notice.
- **No** firmware binary and **no** KiCad/UGS binaries; users obtain those separately. This avoids GPL binary redistribution through our installer.
