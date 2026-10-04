import ctypes
import json
import re
import tempfile
from importlib.util import find_spec
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from podcast_transcriber.feed import Episode

_CUDA_LIBRARY_HANDLES: list[ctypes.CDLL] = []


def transcribe(
    source: str,
    output_dir: Path,
    model_name: str,
    language: str | None,
    device: str,
    episode: Episode | None = None,
) -> tuple[Path, Path, Path]:
    audio_path, should_remove = _prepare_audio(source, output_dir)
    stem = _safe_stem(
        episode.title if episode else audio_path.stem if not should_remove else _source_stem(source)
    )
    try:
        from faster_whisper import WhisperModel

        resolved_device, compute_type = _resolve_device(device)
        try:
            model = WhisperModel(model_name, device=resolved_device, compute_type=compute_type)
        except (RuntimeError, ValueError) as exc:
            if resolved_device == "cuda":
                raise RuntimeError(
                    "Could not initialize the CUDA transcription model. Check that the "
                    "WSL NVIDIA driver is available and that CUDA 12/cuDNN 9 libraries "
                    "are installed; see README.md."
                ) from exc
            raise RuntimeError(f"Could not initialize the transcription model: {exc}") from exc

        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            vad_filter=True,
        )
        segment_data = [
            {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
            for segment in segments
        ]
    finally:
        if should_remove:
            audio_path.unlink(missing_ok=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / f"{stem}.txt"
    srt_path = output_dir / f"{stem}.srt"
    json_path = output_dir / f"{stem}.json"

    transcript = "\n".join(segment["text"] for segment in segment_data).strip()
    text_path.write_text(_text_output(transcript, episode), encoding="utf-8")
    srt_path.write_text(_to_srt(segment_data), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "source": source,
                "model": model_name,
                "language": info.language,
                "language_probability": info.language_probability,
                "podcast_title": episode.podcast_title if episode else None,
                "episode_title": episode.title if episode else None,
                "published": episode.published if episode else None,
                "guid": episode.guid if episode else None,
                "description": episode.description if episode else None,
                "segments": segment_data,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return text_path, srt_path, json_path


def _text_output(transcript: str, episode: Episode | None) -> str:
    if episode is None:
        return transcript + "\n"

    metadata = [
        ("Podcast", episode.podcast_title),
        ("Episode", episode.title),
        ("Published", episode.published),
        ("GUID", episode.guid),
        ("Description", episode.description),
    ]
    lines = [f"{label}: {value}" for label, value in metadata if value]
    lines.extend(("", "Transcript:", transcript))
    return "\n".join(lines) + "\n"


def _resolve_device(device: str) -> tuple[str, str]:
    if device == "cpu":
        return "cpu", "int8"

    try:
        _load_cuda_runtime_libraries()
    except RuntimeError as exc:
        if device == "cuda":
            raise RuntimeError(
                f"{exc} Install the CUDA runtime with "
                '`python -m pip install -e ".[cuda]"`, or use --device cpu.'
            ) from exc
        print(f"Warning: {exc} Falling back to CPU with int8.")
        return "cpu", "int8"

    import ctranslate2

    try:
        cuda_available = ctranslate2.get_cuda_device_count() > 0
    except RuntimeError as exc:
        if device == "cuda":
            raise RuntimeError(
                f"CUDA is not available to CTranslate2: {exc}. "
                "Check the WSL NVIDIA driver and CUDA runtime."
            ) from exc
        print(f"Warning: CUDA is unavailable ({exc}); falling back to CPU with int8.")
        return "cpu", "int8"

    if cuda_available:
        return "cuda", "float16"
    if device == "cuda":
        raise RuntimeError("CUDA was requested, but no CUDA device was found.")
    print("Warning: CUDA is unavailable; transcribing on CPU with int8.")
    return "cpu", "int8"


def _load_cuda_runtime_libraries() -> None:
    libraries = (
        ("nvidia.cublas.lib", "libcublas.so.12"),
        ("nvidia.cudnn.lib", "libcudnn.so.9"),
    )
    paths = []
    for package, library in libraries:
        try:
            spec = find_spec(package)
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        path = next(
            (
                Path(directory) / library
                for directory in (spec.submodule_search_locations or [])
                if (Path(directory) / library).is_file()
            ),
            None,
        ) if spec is not None else None
        if path is None:
            raise RuntimeError(
                f"CUDA runtime library {library} was not found in the Python environment."
            )
        paths.append(path)

    try:
        for path in paths:
            _CUDA_LIBRARY_HANDLES.append(ctypes.CDLL(str(path), mode=ctypes.RTLD_GLOBAL))
    except OSError as exc:
        raise RuntimeError(f"Could not load a packaged CUDA runtime library: {exc}") from exc


def _prepare_audio(source: str, output_dir: Path) -> tuple[Path, bool]:
    local_path = Path(source).expanduser()
    if local_path.is_file():
        return local_path.resolve(), False

    if not source.startswith(("https://", "http://")):
        raise ValueError(f"Audio file does not exist: {local_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    request = Request(source, headers={"User-Agent": "podcast-transcriber/0.1"})
    try:
        with urlopen(request, timeout=60) as response, tempfile.NamedTemporaryFile(
            dir=output_dir,
            suffix=".audio",
            delete=False,
        ) as audio:
            download_path = Path(audio.name)
            while chunk := response.read(1024 * 1024):
                audio.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if "download_path" in locals():
            download_path.unlink(missing_ok=True)
        raise ValueError(f"Could not download episode audio: {exc}") from exc
    return download_path, True


def _source_stem(source: str) -> str:
    if source.startswith(("https://", "http://")):
        from urllib.parse import urlparse

        return Path(urlparse(source).path).stem or "episode"
    return Path(source).stem


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip(".-")
    return stem[:100] or "episode"


def _to_srt(segments: list[dict[str, float | str]]) -> str:
    def timestamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        whole_seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"

    entries = []
    for index, segment in enumerate(segments, start=1):
        entries.append(
            f"{index}\n"
            f"{timestamp(float(segment['start']))} --> "
            f"{timestamp(float(segment['end']))}\n"
            f"{segment['text']}\n"
        )
    return "\n".join(entries)
