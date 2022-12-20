import os
from pathlib import Path
import platform


def main():
    set_env_vars()


def set_env_vars() -> None:
    """Set needed environment variables.

    Raises:
        UnsupportedDebianOS: The Debian Operating System is not
            supported.
        UnsupportedOS: The Operating System is not supported.
    """
    # path starts at ffmpeg
    ffmpeg_directory = Path(get_script_cwd())
    ffmpeg_directory /= "ffmpeg"

    current_os = platform.system().lower()

    if current_os == "windows":
        ffmpeg_directory /= "windows"
    elif current_os == "linux":
        ffmpeg_directory /= "linux"

        current_machine = platform.machine().lower()

        if current_machine in ("x86_64", "amd64"):
            ffmpeg_directory /= "amd64"
        elif current_machine in ("i386", "i486", "i586", "i686"):
            ffmpeg_directory /= "i686"
        elif current_machine in ("arm64", "aarch64"):
            ffmpeg_directory /= "arm64"
        elif current_machine in ("armel", "armv5te", "armv4te"):
            ffmpeg_directory /= "armel"
        elif current_machine in ("armhf", "armv7"):
            ffmpeg_directory /= "armhf"
        else:
            raise UnsupportedDebianOS(
                f"Unsupported operating system: {current_os} with"
                f" {current_machine}."
            )

    elif current_os == "darwin":
        ffmpeg_directory /= "ffmpeg/mac"
    else:
        raise UnsupportedOS(
            f"Unsupported operating system: {current_os}.\nOnly Windows,"
            " Linux, and Darwin (mac) are supported."
        )

    os.environ["PATH"] += os.pathsep + str(ffmpeg_directory.resolve())

    os.environ.setdefault("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] += os.pathsep + str(
        Path("./torch/lib/").resolve()
    )


class UnsupportedOS(Exception):
    """The Operating System is not supported."""


class UnsupportedDebianOS(UnsupportedOS):
    """The Debian Operating System is not supported"""


def get_script_cwd() -> Path:
    """Get the file path for the directory containing the current
    script.

    Returns:
        Path: file path for the directory containing the current script.
    """
    return Path(__file__).parent


if __name__ == "__main__":
    main()
