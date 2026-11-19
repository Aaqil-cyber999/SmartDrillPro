# Phase 7 report - CNC communication (simulation first)

## Delivered

- `app/machine/serial_transport.py`: real pyserial transport plus a deterministic in-memory grblHAL simulator used by all tests and dry runs.
- `app/machine/grbl_controller.py`: protocol layer written from documented GRBL/grblHAL constants only (no UGS code). Supports `?`, `!`, `~`, `$H`, `$I`, `$$`, `G10 L20`, `$J=` jogging, soft reset, 128-byte character-counted streaming, `ok`/`error` handling and status polling during jobs.
- `app/machine/machine_service.py`: connect/disconnect, jog/home/zero/hold/resume/reset/identify and job history. `run_file()` now requires an explicit `.validated.nc` copy, re-validates it against current safety limits and requires the operator confirmation checkbox; no implicit demo job exists.
- `app/ui/pages/machine_control.py`: mode banner, port selection, connection controls, jog grid, job list (validated copies only), confirmation checkbox, progress bar, logs and feed/restore controls.
- `app/ui/pages/job_history.py` and `app/ui/event_bridge.py`: persisted job records and thread-safe delivery of event-bus updates to Qt widgets.
- Simulation is the default. Real serial mode is only enabled by changing Settings.

## Verification

- 5 automated tests in `tests/test_machine.py`: simulator commands, `$$`/`$I` identification, RX character counting, oversized line rejection, validated-copy requirement and persisted job records.
- Full suite passes (35 tests). Offscreen `MainWindow` smoke test constructs every page including Machine Control and Job History.
- Simulated job run records `simulation: true`, re-validates the file and finishes with status `completed`.

## Known limitations

- No continuous background status polling thread; status is queried on demand and every five streamed lines.
- Feed hold does not itself stop the streaming loop; use Soft reset to cancel a job. A dedicated jog-cancel (`0x85`) path is not wired to the UI.
- Jog and zeroing are not checked against soft limits or homing state in the controller layer; the operator remains responsible for safe manual moves.
- The simulator does not model acceleration, limit switches, alarms, spindle RPM feedback or real timing.
- Real ESP32-S3/grblHAL hardware is **not** tested in this phase and is covered as UNVERIFIED in Phase 8 documentation.
