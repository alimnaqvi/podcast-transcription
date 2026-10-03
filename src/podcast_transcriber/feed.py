from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


@dataclass(frozen=True)
class Episode:
    title: str
    audio_url: str
    published: str = ""


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

    episodes = []
    for item in root.findall(".//item"):
        title = _child_text(item, "title") or "Untitled episode"
        published = _child_text(item, "pubDate")
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url", "").strip() if enclosure is not None else ""
        if audio_url:
            episodes.append(Episode(title=title, audio_url=audio_url, published=published))

    if not episodes:
        raise ValueError("No RSS episodes with audio enclosures were found.")
    return episodes


def _child_text(element: ElementTree.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""
