"""Transport abstraction for real serial ports and the simulation controller.

The controller only talks through this interface, so every protocol test runs
against the simulated transport before any hardware is connected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
import time

from config.application_config import DEFAULT_BAUD_RATE, DEFAULT_SERIAL_TIMEOUT_S


class Transport(ABC):
    @abstractmethod
    def open(self) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def write_line(self, line: str) -> None:
        ...

    @abstractmethod
    def read_line(self, timeout_s: float = DEFAULT_SERIAL_TIMEOUT_S) -> str:
        ...

    @property
    @abstractmethod
    def is_open(self) -> bool:
        ...

    @property
    def description(self) -> str:
        return "transport"


class SerialTransport(Transport):
    """Thin wrapper around pyserial (real ESP32-S3 / grblHAL connection)."""

    def __init__(self, port: str, baud_rate: int = DEFAULT_BAUD_RATE) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self._serial = None

    def open(self) -> None:
        import serial  # imported lazily so unit tests never require a driver

        self._serial = serial.Serial(
            self.port, self.baud_rate, timeout=DEFAULT_SERIAL_TIMEOUT_S,
            write_timeout=DEFAULT_SERIAL_TIMEOUT_S,
        )
        time.sleep(0.2)  # grblHAL performs a short reset on port open

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def write_line(self, line: str) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port is not open.")
        self._serial.write((line.rstrip("\n") + "\n").encode("ascii", errors="replace"))

    def read_line(self, timeout_s: float = DEFAULT_SERIAL_TIMEOUT_S) -> str:
        if self._serial is None:
            raise RuntimeError("Serial port is not open.")
        self._serial.timeout = timeout_s
        raw = self._serial.readline()
        return raw.decode("utf-8", errors="replace").strip()

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def description(self) -> str:
        return f"{self.port} @ {self.baud_rate}"


class SimulatedTransport(Transport):
    """Deterministic in-memory grblHAL simulator for tests and dry runs."""

    def __init__(self) -> None:
        self._open = False
        self.responses: deque[str] = deque()
        self.position = [0.0, 0.0, 0.0]
        self.state = "Idle"
        self.absolute = True
        self.entered_lines: list[str] = []

    def open(self) -> None:
        self._open = True
        self.responses.append("GrblHAL 1.1 simulated (SmartDrill Pro)")
        self.responses.append("ok")

    def close(self) -> None:
        self._open = False
        self.responses.clear()

    def write_line(self, line: str) -> None:
        if not self._open:
            raise RuntimeError("Simulated controller is not open.")
        line = line.strip()
        self.entered_lines.append(line)
        upper = line.upper()

        if line == "?":
            self.responses.append(
                f"<{self.state}|MPos:{self.position[0]:.3f},{self.position[1]:.3f},"
                f"{self.position[2]:.3f}|FS:0,0>"
            )
            return
        if upper.startswith("$G"):
            self.responses.append("[G0 G17 G21 G90]")
            self.responses.append("ok")
            return
        if upper.startswith("$I"):
            self.responses.append("[VER:SmartDrill simulated grblHAL]")
            self.responses.append("ok")
            return
        if upper in {"$$", "$+"}:
            self.responses.append("$100=80.000")
            self.responses.append("$110=80.000")
            self.responses.append("$120=80.000")
            self.responses.append("ok")
            return
        if line == "!":
            self.state = "Hold"
            self.responses.append("ok")
            return
        if line == "~":
            self.state = "Idle" if self.state == "Hold" else self.state
            self.responses.append("ok")
            return
        if line == "\x18":
            self.state = "Idle"
            self.position = [0.0, 0.0, 0.0]
            self.responses.append("GrblHAL 1.1 simulated (reset)")
            self.responses.append("ok")
            return
        if upper.startswith("$H"):
            self.state = "Home"
            self.position = [0.0, 0.0, 0.0]
            self.responses.append("ok")
            return
        if upper.startswith("$J=") or upper.startswith("G0") or upper.startswith("G1"):
            self._apply_motion(upper)
        if upper in {"M2", "M30"}:
            self.state = "Idle"
        self.responses.append("ok")

    def _apply_motion(self, upper: str) -> None:
        import re

        if "G90" in upper:
            self.absolute = True
        if "G91" in upper:
            self.absolute = False
        for letter, index in (("X", 0), ("Y", 1), ("Z", 2)):
            match = re.search(rf"{letter}(-?\d+(?:\.\d+)?)", upper)
            if match:
                value = float(match.group(1))
                self.position[index] = value if self.absolute else self.position[index] + value
        self.state = "Run" if "G1" in upper or "$J=" in upper else self.state

    def read_line(self, timeout_s: float = DEFAULT_SERIAL_TIMEOUT_S) -> str:
        return self.responses.popleft() if self.responses else ""

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def description(self) -> str:
        return "SIMULATED grblHAL controller"
