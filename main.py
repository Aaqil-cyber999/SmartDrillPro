"""SmartDrill Pro application entry point."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.application import Application
from app.ui.main_window import MainWindow
from config.application_config import APP_NAME, APP_VERSION


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {APP_VERSION}")
    parser.add_argument(
        "--data-dir",
        help="Override the directory used for projects, output and logs.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Force simulation mode (no physical machine communication).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    core = Application(data_dir=args.data_dir, simulation=args.simulate)
    try:
        core.initialize()
    except Exception as exc:  # noqa: BLE001 - startup must show a friendly error
        QMessageBox.critical(None, APP_NAME, f"Could not start SmartDrill Pro:\n\n{exc}")
        return 1

    window = MainWindow(core)
    window.show()

    result = app.exec()
    core.shutdown()
    return result


if __name__ == "__main__":
    sys.exit(main())
