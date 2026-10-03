import unittest
from unittest.mock import patch

from podcast_transcriber.feed import fetch_feed


class FetchFeedTests(unittest.TestCase):
    @patch("podcast_transcriber.feed.urlopen")
    def test_reads_rss_episode_metadata_and_enclosure(self, urlopen):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self):
                return b"""<rss><channel><item>
                    <title>Test episode</title>
                    <pubDate>Sat, 03 Oct 2026 12:00:00 GMT</pubDate>
                    <enclosure url="https://example.com/audio.mp3" />
                </item></channel></rss>"""

        urlopen.return_value = Response()
        episodes = fetch_feed("https://example.com/feed.xml")
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].title, "Test episode")
        self.assertEqual(episodes[0].audio_url, "https://example.com/audio.mp3")
        self.assertEqual(episodes[0].published, "Sat, 03 Oct 2026 12:00:00 GMT")

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


if __name__ == "__main__":
    unittest.main()
