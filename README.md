# Podcast Transcriber

A local-first command-line starter for finding podcast episodes in an RSS feed
and transcribing audio with Whisper. Audio and transcript files stay on this
computer. The first use of a model downloads that model from Hugging Face.
For a deeper explanation of capabilities, outputs, and internals, see the
[detailed guide](docs/guide.md).

## Requirements

- Python 3.10 or later
- Enough disk space for downloaded episodes and the selected speech model
- For NVIDIA GPU inference, a working NVIDIA driver and CUDA 12/cuDNN 9 runtime

This tool is confirmed to be working on WSL2 environment with an NVIDIA RTX 3050 Ti. This GPU's 4 GB of VRAM is a
good fit for the default `small` model with float16 inference. Larger models require higher VRAM.

## Install on Linux (WSL or bare metal)

Run these commands in the Linux workspace, not under `/mnt/c`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For NVIDIA GPU support, install the CUDA runtime libraries in the same
environment:

```bash
python -m pip install -e ".[cuda]"
```

Check the CLI:

```bash
podcast-tx --help
```

The CLI loads the pip-installed cuBLAS and cuDNN libraries automatically when
they are present. If they are absent, `--device auto` warns and falls back to
CPU; `--device cuda` reports the install command. If CUDA still fails after
installing the extra, verify GPU access with `nvidia-smi` and reinstall the
extra in the active virtual environment:

```bash
python -m pip install -e ".[cuda]"
```

`--device auto` selects CUDA when its runtime is usable, otherwise it clearly
warns and falls back to CPU. `--device cuda` requires a working CUDA runtime.
`--device cpu` forces CPU inference.

## Use

List recent episodes in an RSS feed:

```bash
podcast-tx episodes "https://example.com/podcast.rss" --limit 10
```

Each listed episode includes its corresponding `--episode` value.

Transcribe the last audio episode listed in a feed (usually the podcast's
oldest/first episode):

```bash
podcast-tx transcribe "https://example.com/podcast.rss" --episode 1 --language en
```

`--episode 2` selects the second-to-last audio episode. You can avoid depending
on feed order by selecting an exact RSS GUID or a unique, case-insensitive
title substring:

```bash
podcast-tx transcribe "https://example.com/podcast.rss" --guid "publisher-episode-guid"
podcast-tx transcribe "https://example.com/podcast.rss" --title "Episode title phrase"
```

If multiple episode titles match, the command reports an ambiguity instead of
silently choosing one. RSS-based outputs are placed in a directory under the
output directory named from the podcast and episode titles, for example
`transcripts/my-podcast/episode-title/`. Each slugged directory component is
limited to 120 characters. The `.txt` transcript starts with
podcast and episode metadata (including publication date and description when
provided by the feed).

You can also pass a direct audio URL or a local audio file:

```bash
podcast-tx transcribe "https://example.com/episode.mp3" --language en
podcast-tx transcribe "/path/to/episode.mp3" --model small --device auto
```

The first run downloads the model. Results go to `./transcripts/` by default:

- `.txt` — plain text for notes or LLM prompts
- `.srt` — timestamped subtitles
- `.json` — detected language and timestamped segments

Use `--output-dir`, `--model`, `--language`, and `--device` to adjust behavior.
Whisper can mishear names or overlapping speech; timestamps help locate and
review uncertain passages in the original audio.

## Tests

```bash
python -m unittest discover -s tests
```
