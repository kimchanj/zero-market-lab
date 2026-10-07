"""Versioned news catalog and point-in-time filtering, independent of trading."""
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from zero_market_lab.simulator.models import Instrument


@dataclass(frozen=True)
class NewsItem:
    published_at: datetime
    headline: str
    source: str
    url: str
    summary: str
    keywords: tuple[str, ...]
    instrument: str | None = None
    relevance_score: float = 0
    event_type: str | None = None
    macro_category: str | None = None
    sentiment: str | None = None
    event_date: date | None = None
    retrospective: bool = False
    source_quality: int = 1
    verified_on: str | None = None

    def __post_init__(self):
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("News published_at must have a timezone")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("News needs an HTTPS source URL")

    def to_dict(self):
        value = asdict(self)
        value["published_at"] = self.published_at.isoformat()
        value["event_date"] = self.event_date.isoformat() if self.event_date else None
        return value


class NewsProvider(Protocol):
    def search_news(self, instrument: Instrument, start_date: date, end_date: date,
                    keywords: tuple[str, ...], *, mode: str, cutoff: datetime) -> list[NewsItem]: ...


class CatalogNewsProvider:
    """Search a bounded, manually source-verified catalog, not the live web."""
    def __init__(self, items: list[NewsItem]):
        self.items = tuple(items)

    @classmethod
    def from_file(cls, path: Path):
        records = json.loads(path.read_text(encoding="utf-8"))["items"]
        return cls([NewsItem(**{
            **item, "published_at": datetime.fromisoformat(item["published_at"]),
            "event_date": date.fromisoformat(item["event_date"]) if item.get("event_date") else None,
            "keywords": tuple(item["keywords"]),
        }) for item in records])

    def search_news(self, instrument, start_date, end_date, keywords=(), *, mode="REPLAY_MODE", cutoff=None):
        if mode not in {"REPLAY_MODE", "POST_ANALYSIS_MODE"}:
            raise ValueError("Unknown news mode")
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        zone = ZoneInfo(instrument.timezone)
        if cutoff is None:
            raise ValueError("Explicit timezone-aware news cutoff is required")
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("News cutoff must have a timezone")
        end_instant = datetime.combine(end_date, time.max, zone)
        replay_cutoff = min(cutoff, end_instant)
        terms = {term.casefold() for term in (
            instrument.symbol, instrument.display_name, *instrument.news_keywords,
            *instrument.related_indices, *instrument.related_sectors,
            *instrument.related_macro_topics, *keywords,
        ) if term}
        found = []
        seen = set()
        for item in self.items:
            publication_day = item.published_at.astimezone(zone).date()
            in_period = start_date <= publication_day <= end_date
            retrospective_match = (item.retrospective and item.event_date is not None
                                   and start_date <= item.event_date <= end_date)
            if mode == "REPLAY_MODE":
                if item.retrospective or not in_period or item.published_at > replay_cutoff:
                    continue
            elif not (in_period or retrospective_match) or item.published_at > cutoff:
                continue
            matches = terms.intersection(keyword.casefold() for keyword in item.keywords)
            direct = item.instrument == instrument.instrument_id
            if not matches and not direct:
                continue
            if item.url in seen:
                continue
            seen.add(item.url)
            found.append(replace(item, relevance_score=min(1, len(matches) / 5 + (0.5 if direct else 0))))
        return sorted(found, key=lambda item: (item.published_at, -item.relevance_score, -item.source_quality))
