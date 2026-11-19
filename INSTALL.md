# Installation and developer setup (Windows)

## 1. Main application

Requires Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

## 2. FlatCAM headless worker (real CAM output)

SmartDrill Pro does **not** contain hardcoded G-code. It calls the real FlatCAM 2024.4 engine as an isolated subprocess.

1. Clone FlatCAM 2024.4 into `tools/flatcam` (the folder is gitignored):

   ```powershell
   git clone https://github.com/vika-sonne/FlatCAM tools/flatcam
   git -C tools/flatcam checkout <2024.4 tag or commit>
   ```

2. Create its Python 3.10 environment:

   ```powershell
   py -3.10 -m venv .venv-flatcam
   .\.venv-flatcam\Scripts\python -m pip install -r tools/flatcam/requirements_windows.txt
   ```

3. If `vispy` installation fails, install a working wheel separately, for example `.\.venv-flatcam\Scripts\python -m pip install vispy==0.12.2`, then rerun the remaining requirements. The adapter installs a small startup shim for FlatCAM's marker dictionary.

4. On first CAM run, `FlatcamAdapter.ensure_resources()` generates FlatCAM's Qt resource modules and applies documented headless compatibility patches. It never modifies the main application environment.

5. Optionally override paths in **Settings** using `FlatCAM Python` and `FlatCAM source`, or environment variables `SMARTDRILL_FLATCAM_PYTHON` and `SMARTDRILL_FLATCAM_ROOT`.

## 3. Tests

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pytest -q -m integration -s
```

Integration tests skip when the FlatCAM worker is unavailable. They never touch hardware.

## 4. Windows build

```powershell
.\.venv\Scripts\python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The script runs the full test suite before creating `dist/SmartDrillPro`. The FlatCAM worker and grblHAL firmware are **not** bundled; set them up separately as described above and in `docs/14_hardware_setup.md`.

## Safety

Simulation mode is enabled by default. Generated G-code is never executed automatically: create a `*.validated.nc` copy in G-code Preview, then explicitly confirm the toolpath in Machine Control. Physical machine behaviour remains UNVERIFIED without the operator's own tests.
