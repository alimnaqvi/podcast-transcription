import argparse
import sys
from pathlib import Path

from podcast_transcriber.feed import fetch_feed
from podcast_transcriber.transcribe import transcribe


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="podcast-tx",
        description="Transcribe podcast audio locally with Whisper.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    episodes = commands.add_parser("episodes", help="List episodes in an RSS feed.")
    episodes.add_argument("feed_url", help="Podcast RSS feed URL")
    episodes.add_argument("--limit", type=int, default=20, help="Maximum episodes to show")

    transcribe_command = commands.add_parser(
        "transcribe",
        help="Transcribe a local audio file, audio URL, or RSS feed episode.",
    )
    transcribe_command.add_argument(
        "source",
        help="Audio file or audio URL; use an RSS feed URL together with --episode",
    )
    transcribe_command.add_argument(
        "--episode",
        type=int,
        help="1-based position in the feed (RSS feeds usually list newest first)",
    )
    transcribe_command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("transcripts"),
        help="Where transcript files are saved (default: ./transcripts)",
    )
    transcribe_command.add_argument(
        "--model",
        default="small",
        help="Whisper model name or local model path (default: small)",
    )
    transcribe_command.add_argument(
        "--language",
        help="Language code, such as en; auto-detect if omitted",
    )
    transcribe_command.add_argument(
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Inference device (default: auto)",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.command == "episodes":
            if args.limit < 1:
                parser.error("--limit must be greater than zero")
            episodes = fetch_feed(args.feed_url)
            for index, episode in enumerate(episodes[: args.limit], start=1):
                published = f" ({episode.published})" if episode.published else ""
                print(f"{index:>3}. {episode.title}{published}\n     {episode.audio_url}")
            return 0

        source = args.source
        if args.episode is not None:
            if args.episode < 1:
                parser.error("--episode must be 1 or greater")
            episodes = fetch_feed(source)
            if args.episode > len(episodes):
                parser.error(
                    f"--episode {args.episode} is out of range; "
                    f"the feed has {len(episodes)} audio episodes."
                )
            episode = episodes[args.episode - 1]
            source = episode.audio_url
            print(f"Transcribing: {episode.title}")

        paths = transcribe(
            source=source,
            output_dir=args.output_dir,
            model_name=args.model,
            language=args.language,
            device=args.device,
        )
        print("Saved transcripts:")
        for path in paths:
            print(f"  {path}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
