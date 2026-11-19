# Technical decisions and risks

## Decision log

| ID | Decision | Reason | Status |
| --- | --- | --- | --- |
| ADR-001 | Use `vika-sonne/FlatCAM` 2024.4, not `flatcam/flatcam` | The latter has no code; the former is the real MIT-licensed source | Accepted |
| ADR-002 | Run FlatCAM as a headless subprocess | Avoid Qt5/Qt6 and Python 3.10/3.12 conflicts; reuse supported scripting mode | Accepted |
| ADR-003 | Use Gerbonara for in-process Gerber/Excellon parsing | Single maintained Apache-2.0 library covering both formats plus layer classification | Accepted |
| ADR-004 | Reimplement only the GRBL communication layer in Python | UGS is Java/GPL-3.0 with no Python API; protocol is documented and stable | Accepted |
| ADR-005 | Keep grblHAL firmware unmodified | ESP32-S3 support already exists; custom firmware is unnecessary risk | Accepted |
| ADR-006 | Default to simulation mode for development and tests | No hardware required; safer automation | Accepted |
| ADR-007 | Mark all machining presets as unverified | Values must be calibrated on the physical machine | Accepted |
| ADR-008 | Main app Python 3.12, worker Python 3.10 | Satisfies Gerbonara and FlatCAM pinning without dependency conflicts | Accepted |

## Top risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| FlatCAM headless command syntax differs between builds | CAM operations fail | Phase 5 compatibility probe with a known sample; pin worker version; adapter isolates syntax in one file |
| FlatCAM headless mode still initializes Qt and needs a display/platform plugin | Worker fails on Windows | Verify with `QT_QPA_PLATFORM=offscreen` equivalent; test early in Phase 5; document portable dependency pack |
| Gerbonara's layer classification guesses wrong for unusual filenames | Wrong layer used for machining | Confidence score, explicit layer assignment UI, mandatory user confirmation for outline/drill layers |
| GRBL status formats differ across grblHAL builds | Dashboard shows wrong state | Parse both legacy and v1 formats; treat unknown as unknown; capability discovery via `$I`/`$$` |
| RX buffer/ack handling sends too much data | Controller overruns, garbled job | Byte-budget streaming, one line at a time, ack timeout, periodic `Bf` status; configurable buffer size |
| Generated G-code exceeds machine limits | Crash or damage | Validator with machine profile and workpiece limits; block start on errors; explicit approval |
| Operator assumes software stop is an emergency stop | Injury/damage | UI wording, documentation warnings, require physical E-stop in hardware checklist |
| Python/PySide6 licensing for commercial distribution | Legal issue | LGPL review before release, dynamic linking, notices, no bundled GPL binaries |
| Sample files are synthetic rather than real manufacturing output | Parser bugs missed | Generate samples with KiCad CLI and include real-world files with varied formats/units |

## Missing decisions (do not guess)

1. **Physical machine dimensions and driver current/voltage** — needed before machine profile defaults can be finalized. Until then use small, clearly-marked example limits and require user configuration.
2. **Spindle type and control interface** — PWM, relay, or no spindle. G-code M3/M5 behavior must match the actual grblHAL build; default to "spindle control disabled" in the profile.
3. **FlatCAM worker distribution method** — bundled portable folder vs. user-installed. Affects installer size and license notices; decide before Phase 9.
4. **Actual grblHAL build options on the ESP32-S3 board** — must be read from `$I`/`$$` during Phase 8; validator's supported-command set depends on it.

These do not block Phases 2-4. They are explicit inputs for Phases 5 and 8.
