import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


@dataclass(frozen=True)
class Episode:
    title: str
    audio_url: str
    published: str = ""
    guid: str = ""
    description: str = ""
    podcast_title: str = ""


def fetch_feed(url: str) -> list[Episode]:
    request = Request(url, headers={"User-Agent": "podcast-transcriber/0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            document = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Could not fetch RSS feed: {exc}") from exc

    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise ValueError(f"RSS feed is not valid XML: {exc}") from exc

    channel = root.find(".//channel")
    podcast_title = _child_text(channel, "title") if channel is not None else ""
    episodes = []
    for item in root.findall(".//item"):
        title = _child_text(item, "title") or "Untitled episode"
        published = _child_text(item, "pubDate")
        guid = _child_text(item, "guid")
        description = _child_text(item, "description")
        if not description:
            description = _local_name_text(item, "encoded")
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url", "").strip() if enclosure is not None else ""
        if audio_url:
            episodes.append(
                Episode(
                    title=title,
                    audio_url=audio_url,
                    published=published,
                    guid=guid,
                    description=description,
                    podcast_title=podcast_title,
                )
            )

    if not episodes:
        raise ValueError("No RSS episodes with audio enclosures were found.")
    return episodes


def select_episode(
    episodes: list[Episode],
    *,
    episode_number: int | None = None,
    guid: str | None = None,
    title: str | None = None,
) -> Episode:
    selectors = sum(value is not None for value in (episode_number, guid, title))
    if selectors != 1:
        raise ValueError("Choose exactly one episode selector: --episode, --guid, or --title.")

    if episode_number is not None:
        if episode_number < 1:
            raise ValueError("--episode must be 1 or greater.")
        if episode_number > len(episodes):
            raise ValueError(
                f"--episode {episode_number} is out of range; "
                f"the feed has {len(episodes)} audio episodes."
            )
        return episodes[-episode_number]

    if guid is not None:
        if not guid.strip():
            raise ValueError("--guid cannot be empty.")
        matches = [episode for episode in episodes if episode.guid == guid.strip()]
        selector_name = "GUID"
    else:
        if title is None:
            raise ValueError("A title selector is required.")
        if not title.strip():
            raise ValueError("--title cannot be empty.")
        query = title.casefold().strip()
        matches = [episode for episode in episodes if query in episode.title.casefold()]
        selector_name = "title"

    if not matches:
        raise ValueError(f"No episode matched the requested {selector_name}.")
    if len(matches) > 1:
        raise ValueError(
            f"More than one episode matched the requested {selector_name}; "
            "refine the value to identify a single episode."
        )
    return matches[0]


def episode_output_dir(base_dir: Path, episode: Episode) -> Path:
    podcast = _slugify(episode.podcast_title) or "podcast"
    title = _slugify(episode.title) or "episode"
    max_length = 120
    separator = "--"
    podcast = podcast[:40].rstrip("-")
    title = title[: max_length - len(podcast) - len(separator)].rstrip("-")
    return base_dir / f"{podcast}{separator}{title}"


def _child_text(element: ElementTree.Element, tag: str) -> str:
    child = element.find(tag)
    return _plain_text(child) if child is not None else ""


def _local_name_text(element: ElementTree.Element, name: str) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] == name:
            return _plain_text(child)
    return ""


def _plain_text(element: ElementTree.Element) -> str:
    content = " ".join(element.itertext()).strip()
    content = re.sub(r"<[^>]+>", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", "-", value, flags=re.UNICODE)
    return value.strip("-")
