import unittest
from unittest.mock import patch

from podcast_transcriber.transcribe import (
    _load_cuda_runtime_libraries,
    _safe_stem,
    _to_srt,
    _text_output,
)
from podcast_transcriber.feed import Episode


class TranscriptFormattingTests(unittest.TestCase):
    def test_safe_stem_removes_unsafe_filename_characters(self):
        self.assertEqual(_safe_stem("Episode: part/one?"), "Episode-part-one")

    def test_srt_contains_one_based_indices_and_timestamps(self):
        result = _to_srt(
            [
                {"start": 1.25, "end": 2.5, "text": "Hello."},
                {"start": 3.0, "end": 4.0, "text": "World."},
            ]
        )
        self.assertEqual(
            result,
            "1\n00:00:01,250 --> 00:00:02,500\nHello.\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nWorld.\n",
        )

    @patch("podcast_transcriber.transcribe.find_spec", side_effect=ModuleNotFoundError)
    def test_missing_cuda_runtime_has_actionable_error(self, _find_spec):
        with self.assertRaisesRegex(RuntimeError, "libcublas.so.12"):
            _load_cuda_runtime_libraries()

    def test_rss_text_output_has_episode_metadata_before_transcript(self):
        episode = Episode(
            title="Episode title",
            audio_url="https://example.com/episode.mp3",
            published="Sat, 03 Oct 2026",
            guid="abc-123",
            description="A short summary.",
            podcast_title="Podcast title",
        )
        result = _text_output("Recognized words.", episode)
        self.assertTrue(result.startswith("Podcast: Podcast title\n"))
        self.assertIn("Episode: Episode title\n", result)
        self.assertIn("Published: Sat, 03 Oct 2026\n", result)
        self.assertIn("Description: A short summary.\n\nTranscript:\nRecognized words.", result)


if __name__ == "__main__":
    unittest.main()
