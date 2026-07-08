import platform
import subprocess
from pathlib import Path


def open_folder(path: Path) -> None:
    system = platform.system()
    if system == "Darwin":
        command = ["open", str(path)]
    elif system == "Windows":
        command = ["explorer", str(path)]
    elif system == "Linux":
        command = ["xdg-open", str(path)]
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    subprocess.Popen(command)
