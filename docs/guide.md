# Podcast Transcriber: detailed guide

This guide explains what the CLI supports, how to use it, what happens during
a transcription, and how to troubleshoot common issues.

## What the tool does

Podcast Transcriber is a local command-line client for transcribing spoken
audio with [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper), an
optimized implementation of OpenAI's Whisper models using CTranslate2.

It can:

- List episodes that have audio enclosures in an RSS feed.
- Transcribe an episode selected by its position in that feed.
- Transcribe a direct audio URL or an audio file already on disk.
- Use an NVIDIA CUDA GPU when available, or run on the CPU.
- Detect the spoken language or use a language code supplied by the user.
- Save plain text, timestamped SubRip subtitles, and timestamped JSON.

It does not currently provide a graphical interface, maintain a podcast
library or transcription database, identify speakers, separate overlapping
voices, summarize episodes, or fetch Apple Podcasts' proprietary transcript.
The RSS audio is transcribed locally instead.

## Installation

Use a Python 3.10+ virtual environment. In the project directory on Linux or
WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[cuda]"
```

The `cuda` extra installs NVIDIA cuBLAS 12 and cuDNN 9 runtime packages into
the Python environment. The CLI finds and loads these shared libraries before
starting CTranslate2. The NVIDIA driver itself is provided by the host; for
WSL2, install the NVIDIA driver on Windows and check that `nvidia-smi` works
inside WSL. Installing a full CUDA toolkit is usually unnecessary for this
prebuilt Python-package workflow.

For CPU-only use, install without the extra:

```bash
python -m pip install -e .
```

The first transcription downloads the selected Whisper model. The model is
cached by Hugging Face for subsequent runs. Audio passed as a URL is stored
temporarily while it is being processed and removed afterward.

## Commands

### Inspect a feed

```bash
podcast-tx episodes "https://example.com/podcast.rss"
podcast-tx episodes "https://example.com/podcast.rss" --limit 5
```

Episodes are displayed in the order they appear in the feed. Many publishers
put the newest item first, but ordering is controlled by the publisher.
Indexes are one-based and refer only to items with an audio enclosure.

### Transcribe a feed episode

```bash
podcast-tx transcribe "https://example.com/podcast.rss" --episode 1
```

The selected enclosure's audio is downloaded and transcribed. The tool prints
the episode title and uses the audio URL's filename to name the outputs.

### Transcribe an audio URL or local file

```bash
podcast-tx transcribe "https://example.com/episode.mp3"
podcast-tx transcribe "/path/to/episode.mp3"
```

The audio decoder is provided by PyAV, which supports common formats including
MP3, M4A/AAC, and WAV. The source file must be readable by PyAV.

### Choose model, language, device, and output directory

```bash
podcast-tx transcribe "/path/to/episode.mp3" \
  --model small \
  --language en \
  --device auto \
  --output-dir transcripts
```

- `--model` accepts a Faster-Whisper model name (for example `tiny`, `base`,
  `small`, `medium`, or `large-v3`) or a local model directory.
- `--language` is an optional Whisper language code such as `en`. If omitted,
  Whisper detects the language from the audio.
- `--device auto` uses CUDA if the GPU, CTranslate2, and CUDA runtime are
  usable, otherwise it warns and uses the CPU.
- `--device cuda` requires a usable CUDA setup and returns an error rather
  than silently switching devices.
- `--device cpu` forces CPU inference using the `int8` compute type.
- `--output-dir` chooses where transcript files are written; the default is
  `./transcripts`.

Smaller models generally use less memory and run faster, while larger models
can improve recognition at the cost of more memory and processing time. The
RTX 3050 Ti with 4 GB of VRAM is a reasonable target for `small`; larger
models may not fit depending on their configuration and GPU memory use.

## Output files

For each source, the CLI writes three UTF-8 files using a sanitized source
filename as their basename:

### Plain text (`.txt`)

Recognized segment text joined in chronological order, ready for searching,
notes, or an LLM prompt. Timestamps and speaker labels are not included.

### SubRip subtitles (`.srt`)

Numbered subtitle entries with start/end timestamps and text. SRT is supported
by many media players and subtitle editors.

### JSON (`.json`)

An object containing:

- `source`: the original local path or URL given to the command.
- `model`: the selected model name or path.
- `language`: the detected or specified language code.
- `language_probability`: Whisper's confidence in the language detection.
- `segments`: chronological objects with `start`, `end`, and `text`.

The JSON segments are useful for future search indexing, transcript viewers,
or links that jump to a time in the audio. The current CLI overwrites prior
output files with the same basename in the chosen output directory.

## What happens behind the scenes

1. **Resolve the audio source.** Local files are passed directly to the audio
   decoder. For a URL, the CLI downloads the response into a uniquely named
   temporary file in the output directory.
2. **Prepare the inference runtime.** The CLI checks the selected device. For
   CUDA, it loads the cuBLAS and cuDNN shared libraries installed by the
   optional Python extra, then asks CTranslate2 whether a CUDA device is
   available.
3. **Load the model.** Faster-Whisper loads the requested model from the local
   model cache or downloads it on first use.
4. **Decode and recognize.** PyAV decodes the input audio. Faster-Whisper
   performs voice activity detection, then sends speech through Whisper and
   returns text segments with timestamps. Beam search uses a beam size of 5.
5. **Write results.** The segment text and metadata are written as `.txt`,
   `.srt`, and `.json`. Downloaded temporary audio is removed even if
   transcription raises an error.

No audio is submitted to an online transcription API. Network access is used
to retrieve RSS/audio URLs and, on first use, to download model files.

## Accuracy and limitations

Whisper is an automatic speech recognition model, not a guaranteed verbatim
record. It can miss or alter names, technical terms, accents, quiet speech,
and overlapping dialogue. Language context and model size affect results.
Review important quotations against the original recording.

The current outputs have timestamps but not speaker diarization. Voice
activity detection helps skip non-speech sections; it does not identify who is
speaking. The tool preserves the model's recognized wording and does not
summarize, correct, or fact-check it.

Use audio you are allowed to download and transcribe, and respect the
publisher's terms and applicable copyright rules.

## Troubleshooting

### `Library libcublas.so.12 is not found or cannot be loaded`

Install the CUDA extra in the currently activated environment and rerun:

```bash
source .venv/bin/activate
python -m pip install -e ".[cuda]"
podcast-tx transcribe "/path/to/audio.mp3" --device cuda
```

The CLI preloads the pip-installed cuBLAS/cuDNN libraries before CTranslate2
starts. If the problem remains, check that `nvidia-smi` works in the same
Linux/WSL environment, confirm that the virtual environment is active, and
reinstall its packages. `--device auto` falls back to CPU when the optional
libraries are missing; `--device cpu` avoids CUDA entirely.

### CUDA runs out of memory

Choose a smaller model such as `small`, or run with `--device cpu`. Close
other GPU-intensive applications and inspect GPU memory with `nvidia-smi`.

### A feed cannot be read or has no episodes

The `episodes` command expects a reachable RSS or Atom-like XML feed with
`<item>` entries and `<enclosure url="...">` audio links. Some publishers
block automated requests, require authentication, or use nonstandard feed
formats. Check the feed URL in a browser and try the direct audio URL if one
is available.

### The output is empty or decoding fails

Check that the file is a complete, supported audio file and that it contains
speech. For an audio URL, verify that it is a direct audio resource rather
than an HTML episode page.

## Development and tests

Run the unit tests with:

```bash
python -m unittest discover -s tests -v
```

The CLI is split into a few small modules so it can grow incrementally:

- `feed.py` fetches and parses RSS episode metadata.
- `transcribe.py` handles audio retrieval, device selection, Whisper inference,
  and output serialization.
- `cli.py` validates command-line options and connects those operations.

Potential extensions include a persistent episode database, full-text
search, resumable downloads, a local web interface, and transcript editing.
