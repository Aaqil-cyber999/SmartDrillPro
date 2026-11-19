"""Headless FlatCAM worker adapter.

FlatCAM receives a Tcl shell script and writes real G-code files. SmartDrill
never generates fake G-code: if the worker fails or an output file is missing,
the job is reported as failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import subprocess
import time

from config.application_config import PROJECT_ROOT

DEFAULT_FLATCAM_ROOT = PROJECT_ROOT / "tools" / "flatcam"
DEFAULT_FLATCAM_PYTHON = PROJECT_ROOT / ".venv-flatcam" / "Scripts" / "python.exe"

# FlatCAM 2024.4 expects vispy 0.6.x. Current Windows wheels expose the same
# marker shaders through ``symbol_shaders`` instead of ``_marker_dict``. This
# tiny startup shim restores the old alias before FlatCAM's GUI patches load.
VISPY_COMPAT_SHIM = """\
try:
    from vispy.visuals import markers as _sd_markers
    if not hasattr(_sd_markers, "_marker_dict"):
        _sd_markers._marker_dict = getattr(_sd_markers, "symbol_shaders", {})
except Exception:
    pass
"""

# Headless FlatCAM 2024.4 fixes. Each patch is applied to the gitignored
# vendored source on first use, so a clean checkout behaves identically.
WRITER_IMPORT_OLD = "from tclCommands.TclCommand import TclCommandSignaled"
WRITER_IMPORT_NEW = "from tclCommands.TclCommand import TclCommand, TclCommandSignaled"
WRITER_CLASS_OLD = "class TclCommandWriteGCode(TclCommandSignaled):"
WRITER_CLASS_NEW = "class TclCommandWriteGCode(TclCommand):"
WRITER_BODY_OLD = """\t\ttry:
\t\t\tobj = self.app.collection.get_by_name(str(obj_name))
\t\texcept Exception:
\t\t\tif muted is False:
\t\t\t\treturn "Could not retrieve object: %s" % obj_name
\t\t\telse:
\t\t\t\treturn "fail"

\t\ttry:
\t\t\tobj.export_gcode(str(filename), str(preamble), str(postamble), from_tcl=True)
\t\texcept Exception as e:
\t\t\tif muted is False:
\t\t\t\treturn "Operation failed: %s" % str(e)
\t\t\telse:
\t\t\t\treturn
"""
WRITER_BODY_NEW = """\t\tfrom PyQt5 import QtCore

\t\tdef _sd_export_when_ready(_sd_attempt=0):
\t\t\t# _SD_OBJECT_WAIT: CNCJob objects are appended after this command
\t\t\t# returns. Retry from the Qt event loop until FlatCAM has them.
\t\t\ttarget = self.app.collection.get_by_name(str(obj_name))
\t\t\tif target is not None:
\t\t\t\ttry:
\t\t\t\t\ttarget.export_gcode(str(filename), str(preamble), str(postamble), from_tcl=True)
\t\t\t\texcept Exception as exc:
\t\t\t\t\tself.log.error("write_gcode(): %s", exc)
\t\t\t\treturn
\t\t\tif _sd_attempt < 300:
\t\t\t\tQtCore.QTimer.singleShot(100, lambda: _sd_export_when_ready(_sd_attempt + 1))
\t\t\telse:
\t\t\t\tself.log.error("write_gcode(): object not found: %s", obj_name)

\t\t_sd_export_when_ready()
"""

DRILL_PLOT_OLD = """\t\t\tjob_obj.gcode_parse()
\t\t\tjob_obj.create_geometry()
"""
DRILL_PLOT_NEW = """\t\t\tjob_obj.gcode_parse()
\t\t\t# _SD_SKIP_PLOT_GEOMETRY: not needed for headless G-code export.
"""

ZCUT_OLD = """\tdef check_zcut(self, zcut):
\t\tif zcut > 0:
"""
ZCUT_NEW = """\tdef check_zcut(self, zcut):
\t\t# _SD_ZCUT_FIX: upstream returns None for negative depths in Tcl mode.
\t\tif zcut is None:
\t\t\treturn 'fail'
\t\tif zcut > 0:
"""
ZCUT_END_OLD = """\t\telif zcut == 0:
\t\t\tself.app.inform.emit('[WARNING] %s.' % _("The Cut Z parameter is zero. There will be no cut, aborting"))
\t\t\treturn 'fail'

\t# used in Tool Drilling
"""
ZCUT_END_NEW = """\t\telif zcut == 0:
\t\t\tself.app.inform.emit('[WARNING] %s.' % _("The Cut Z parameter is zero. There will be no cut, aborting"))
\t\t\treturn 'fail'
\t\treturn zcut

\t# used in Tool Drilling
"""


@dataclass
class CamOperation:
    kind: str  # isolation, drilling, outline
    source_path: Path
    output_path: Path
    object_name: str


@dataclass
class FlatcamResult:
    success: bool
    script: str
    stdout: str = ""
    stderr: str = ""
    gcode_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def tcl_path(path: Path) -> str:
    """Return a Tcl-braced, forward-slash path (safe for spaces on Windows)."""
    return "{" + str(path).replace("\\", "/") + "}"


def _number(value: float) -> str:
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def expected_gcode_paths(script: str) -> list[Path]:
    """Paths that FlatCAM's write_gcode commands must actually create."""
    paths: list[Path] = []
    for line in script.splitlines():
        if not line.startswith("write_gcode"):
            continue
        match = re.search(r"write_gcode\s+\S+\s+(?:\{([^}]+)\}|(\S+))", line)
        if match:
            token = (match.group(1) or match.group(2) or "").replace("/", os.sep)
            if token:
                paths.append(Path(token))
    return paths


class FlatcamAdapter:
    def __init__(self, flatcam_python: str | Path | None = None, flatcam_root: str | Path | None = None) -> None:
        self.python_path = Path(flatcam_python) if flatcam_python else DEFAULT_FLATCAM_PYTHON
        self.source_root = Path(flatcam_root) if flatcam_root else DEFAULT_FLATCAM_ROOT
        env_python = os.environ.get("SMARTDRILL_FLATCAM_PYTHON")
        env_root = os.environ.get("SMARTDRILL_FLATCAM_ROOT")
        if env_python:
            self.python_path = Path(env_python)
        if env_root:
            self.source_root = Path(env_root)

    @property
    def available(self) -> tuple[bool, str]:
        if not self.python_path.is_file():
            return False, f"FlatCAM Python not found: {self.python_path}"
        if not (self.source_root / "__main__.py").is_file():
            return False, f"FlatCAM source not found: {self.source_root}"
        return True, "FlatCAM worker is available."

    def build_script(self, operations: list[CamOperation], settings) -> str:
        """Create a FlatCAM Tcl script. Every operation uses a real source file."""
        # Note: the Tcl `new` command calls a GUI-only slot in FlatCAM 2024.4,
        # so it must not be used in headless mode.
        lines = ["# Generated by SmartDrill Pro for the FlatCAM headless worker.",
                 "set_sys units MM"]
        for index, operation in enumerate(operations, start=1):
            name = f"sd_{operation.object_name}_{index}"
            source = tcl_path(operation.source_path)
            output = tcl_path(operation.output_path)
            if operation.kind == "isolation":
                geo = f"{name}_iso"
                job = f"{name}_job"
                lines += [
                    f"open_gerber {source} -outname {name}",
                    f"isolate {name} -dia {_number(settings.isolation_tool_mm)} "
                    f"-passes {settings.isolation_passes} -overlap {_number(settings.isolation_overlap)} "
                    f"-combine True -iso_type 2 -outname {geo}",
                    self._cncjob_line(geo, job, settings, settings.isolation_tool_mm, settings.cut_depth_mm),
                ]
            elif operation.kind == "drilling":
                job = f"{name}_job"
                lines += [
                    f"open_excellon {source} -outname {name}",
                    f"drillcncjob {name} -drillz {_number(settings.drill_depth_mm)} "
                    f"-travelz {_number(settings.travel_height_mm)} "
                    f"-feedrate_z {_number(settings.feed_z)} "
                    f"-feedrate_rapid {_number(settings.feed_rapid)} "
                    f"-spindlespeed {int(settings.spindle_rpm)} "
                    f"-endxy 0,0 -outname {job}",
                ]
            elif operation.kind == "outline":
                geo = f"{name}_follow"
                job = f"{name}_job"
                lines += [
                    f"open_gerber {source} -outname {name}",
                    f"follow {name} -outname {geo}",
                    self._cncjob_line(
                        geo, job, settings, settings.outline_tool_mm, settings.outline_depth_mm,
                        depth_per_pass=settings.outline_tool_mm,
                    ),
                ]
            else:
                raise ValueError(f"Unknown CAM operation: {operation.kind}")
            # Real FlatCAM output is wrapped with safe, explicit modal/end
            # codes. No quit_flatcam: CNCJob objects arrive asynchronously and
            # the worker is stopped once the output files actually exist.
            lines.append(
                f"write_gcode {job} {output} -preamble {{"
                f"\nG21\nG90\n"
                f"}} -postamble {{\nM30\n}}"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _cncjob_line(geo: str, job: str, settings, diameter: float, depth: float, depth_per_pass=None) -> str:
        dpp = depth_per_pass if depth_per_pass is not None else settings.depth_per_pass_mm
        return (
            f"cncjob {geo} -dia {_number(diameter)} -z_cut {_number(depth)} "
            f"-z_move {_number(settings.travel_height_mm)} -feedrate {_number(settings.feed_xy)} "
            f"-feedrate_z {_number(settings.feed_z)} -feedrate_rapid {_number(settings.feed_rapid)} "
            f"-dpp {_number(dpp)} -spindlespeed {int(settings.spindle_rpm)} "
            f"-endxy 0,0 -outname {job}"
        )

    def ensure_resources(self) -> tuple[bool, str]:
        """Generate FlatCAM's compiled Qt resources if they are missing.

        A fresh git checkout ships only ``.qrc`` files; FlatCAM imports the
        generated ``resources.py`` modules at startup.
        """
        resource_dir = self.source_root / "FlatCAM"
        for qrc in sorted(resource_dir.glob("resources*.qrc")):
            target = qrc.with_suffix(".py")
            if target.is_file():
                continue
            try:
                completed = subprocess.run(
                    [str(self.python_path), "-m", "PyQt5.pyrcc_main",
                     "-o", str(target), str(qrc)],
                    capture_output=True, text=True, timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return False, f"Could not compile FlatCAM resources: {exc}"
            if completed.returncode != 0:
                return False, f"Could not compile {qrc.name}: {completed.stderr[-500:]}"

        def patch(path: Path, marker: str, pairs: list[tuple[str, str]]) -> str | None:
            if not path.is_file():
                return f"Missing FlatCAM source file: {path.name}"
            text = path.read_text(encoding="utf-8", errors="replace")
            if marker in text:
                return None
            for old, new in pairs:
                if new in text:
                    continue
                if old not in text:
                    return f"Could not apply headless patch to {path.name}"
                text = text.replace(old, new, 1)
            path.write_text(text, encoding="utf-8")
            return None

        flatcam = self.source_root / "FlatCAM"
        patches = [
            (flatcam / "tclCommands" / "TclCommandWriteGCode.py", "_SD_OBJECT_WAIT", [
                (WRITER_IMPORT_OLD, WRITER_IMPORT_NEW),
                (WRITER_CLASS_OLD, WRITER_CLASS_NEW),
                (WRITER_BODY_OLD, WRITER_BODY_NEW),
            ]),
            (flatcam / "tclCommands" / "TclCommandDrillcncjob.py", "_SD_SKIP_PLOT_GEOMETRY", [
                (DRILL_PLOT_OLD, DRILL_PLOT_NEW),
            ]),
            (flatcam / "camlib.py", "_SD_ZCUT_FIX", [
                (ZCUT_OLD, ZCUT_NEW),
                (ZCUT_END_OLD, ZCUT_END_NEW),
            ]),
        ]
        for path, marker, pairs in patches:
            error = patch(path, marker, pairs)
            if error:
                return False, error
        return True, "FlatCAM resources are available."

    def run(self, script: str, workdir: Path, timeout_s: int = 300) -> FlatcamResult:
        available, reason = self.available
        if not available:
            return FlatcamResult(False, script, errors=[reason])
        ready, reason = self.ensure_resources()
        if not ready:
            return FlatcamResult(False, script, errors=[reason])

        workdir.mkdir(parents=True, exist_ok=True)
        script_path = workdir / "flatcam_job.tcl"
        script_path.write_text(script, encoding="utf-8")
        (workdir / "sitecustomize.py").write_text(VISPY_COMPAT_SHIM, encoding="utf-8")

        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(workdir), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(workdir)]
        )
        command = [
            str(self.python_path), str(self.source_root), "--headless",
            f"--shellfile={script_path}",
        ]
        expected = expected_gcode_paths(script)
        stdout_path = workdir / "flatcam_stdout.log"
        stderr_path = workdir / "flatcam_stderr.log"
        timed_out = False
        started = time.monotonic()
        try:
            # FlatCAM emits a lot of offscreen Qt warnings. Redirecting to
            # files prevents the OS pipe buffer from filling and stalling it.
            with stdout_path.open("w", encoding="utf-8") as stdout_file, \
                    stderr_path.open("w", encoding="utf-8") as stderr_file:
                try:
                    process = subprocess.Popen(
                        command,
                        cwd=str(workdir),
                        stdout=stdout_file,
                        stderr=stderr_file,
                        env=env,
                    )
                except OSError as exc:
                    return FlatcamResult(False, script, errors=[f"Could not start FlatCAM: {exc}"])

                try:
                    while True:
                        if expected and all(path.is_file() and path.stat().st_size > 0 for path in expected):
                            break
                        if process.poll() is not None:
                            break
                        if time.monotonic() - started > timeout_s:
                            timed_out = True
                            break
                        time.sleep(0.5)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
        finally:
            stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""

        files = [path for path in expected if path.is_file() and path.stat().st_size > 0]
        errors: list[str] = []
        if timed_out:
            errors.append(f"FlatCAM worker timed out after {timeout_s} seconds.")
        for path in expected:
            if path not in files:
                errors.append(f"FlatCAM did not write expected G-code: {path}")
        if not files:
            combined = stdout + "\n" + stderr
            for line in combined.splitlines():
                lowered = line.lower()
                if "traceback" in lowered or "error:" in lowered or "operation failed" in lowered:
                    errors.append(line.strip())
            errors.append(f"FlatCAM exited with code {process.returncode}.")

        return FlatcamResult(
            bool(files) and not errors, script, stdout, stderr, files, errors
        )
