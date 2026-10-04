import unittest
from pathlib import Path
from unittest.mock import patch

from podcast_transcriber.feed import (
    Episode,
    episode_output_dir,
    fetch_feed,
    select_episode,
)


class FetchFeedTests(unittest.TestCase):
    @patch("podcast_transcriber.feed.urlopen")
    def test_reads_rss_episode_metadata_and_enclosure(self, urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return b"""<rss><channel><title>Test podcast</title><item>
                    <title>Test episode</title>
                    <pubDate>Sat, 03 Oct 2026 12:00:00 GMT</pubDate>
                    <guid>episode-guid</guid>
                    <description><![CDATA[<p>Episode summary.</p>]]></description>
                    <enclosure url="https://example.com/audio.mp3" />
                </item></channel></rss>"""

        urlopen.return_value = Response()
        episodes = fetch_feed("https://example.com/feed.xml")
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].title, "Test episode")
        self.assertEqual(episodes[0].audio_url, "https://example.com/audio.mp3")
        self.assertEqual(episodes[0].published, "Sat, 03 Oct 2026 12:00:00 GMT")
        self.assertEqual(episodes[0].guid, "episode-guid")
        self.assertEqual(episodes[0].description, "Episode summary.")
        self.assertEqual(episodes[0].podcast_title, "Test podcast")

    @patch("podcast_transcriber.feed.urlopen")
    def test_reports_feed_without_audio_enclosures(self, urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return b"<rss><channel><item><title>Missing audio</title></item></channel></rss>"

        urlopen.return_value = Response()
        with self.assertRaisesRegex(ValueError, "No RSS episodes"):
            fetch_feed("https://example.com/feed.xml")


class EpisodeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.episodes = [
            Episode("Part One", "https://example.com/one.mp3", guid="one"),
            Episode("Part Two", "https://example.com/two.mp3", guid="two"),
            Episode("Finale", "https://example.com/final.mp3", guid="final"),
        ]

    def test_episode_number_counts_backwards_from_last_feed_item(self):
        self.assertEqual(
            select_episode(self.episodes, episode_number=1).title,
            "Finale",
        )
        self.assertEqual(
            select_episode(self.episodes, episode_number=3).title,
            "Part One",
        )

    def test_guid_matches_exactly(self):
        self.assertEqual(select_episode(self.episodes, guid="two").title, "Part Two")

    def test_title_matches_case_insensitive_substring(self):
        self.assertEqual(select_episode(self.episodes, title="part t").title, "Part Two")

    def test_ambiguous_title_is_reported(self):
        with self.assertRaisesRegex(ValueError, "More than one episode"):
            select_episode(self.episodes, title="part")

    def test_missing_episode_is_reported(self):
        with self.assertRaisesRegex(ValueError, "No episode matched"):
            select_episode(self.episodes, guid="missing")

    def test_rss_output_directory_is_slugified_and_capped(self):
        episode = Episode(
            "An Episode Title",
            "https://example.com/audio.mp3",
            podcast_title="A Podcast Name!",
        )
        output_dir = episode_output_dir(Path("transcripts"), episode)
        self.assertEqual(
            output_dir,
            Path("transcripts/a-podcast-name/an-episode-title"),
        )

        long_episode = Episode("x" * 200, "https://example.com/audio.mp3", podcast_title="Show")
        long_output_dir = episode_output_dir(Path("out"), long_episode)
        self.assertLessEqual(len(long_output_dir.parent.name), 120)
        self.assertLessEqual(len(long_output_dir.name), 120)


if __name__ == "__main__":
    unittest.main()
