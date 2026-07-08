import shutil
from pathlib import Path


def resolve_whisperkit_executable(
    executable_path: Path,
    cli_workdir: Path,
) -> Path | None:
    if executable_path and executable_path.name and executable_path.is_file():
        return executable_path.resolve()

    if cli_workdir and cli_workdir.name:
        release_binary = cli_workdir / ".build" / "release" / "argmax-cli"
        if release_binary.is_file():
            return release_binary.resolve()

    path_executable = shutil.which("argmax-cli")
    return Path(path_executable).resolve() if path_executable else None


def resolve_whisperkit_model_path(
    configured_path: Path,
    cli_workdir: Path,
    model: str,
) -> Path | None:
    if (
        configured_path
        and configured_path.name
        and configured_path.is_dir()
        and (configured_path / "config.json").is_file()
    ):
        return configured_path.resolve()

    if not cli_workdir or not cli_workdir.name:
        return None

    candidates = [
        cli_workdir / "Models" / "whisperkit-coreml" / f"openai_whisper-{model}",
        cli_workdir / "Models" / "whisperkit-coreml" / f"distil-whisper_{model}",
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "config.json").is_file():
            return candidate.resolve()
    return None
