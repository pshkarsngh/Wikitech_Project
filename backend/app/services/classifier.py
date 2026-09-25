"""Guess whether a missing link points at a person, a place, or something else.

This is deliberately simple: Wikidata is asked for a one-line description of
the best matching item and the description is pattern matched. It is a hint for
the UI, not a named-entity-recognition pass.
"""

from __future__ import annotations

import asyncio
import re

from app.config import Settings
from app.services.mediawiki import MediaWikiClient

PERSON = "person"
PLACE = "place"
OTHER = "other"

_PERSON_PATTERN = re.compile(
    r"\b("
    r"actor|actress|architect|artist|astronaut|athlete|author|bishop|"
    r"businessman|businesswoman|chef|chess player|coach|composer|conductor|"
    r"diplomat|director|dramatist|economist|engineer|entrepreneur|explorer|"
    r"farmer|film producer|footballer|general|geologist|guitarist|"
    r"historian|human rights activist|illustrator|industrialist|inventor|"
    r"journalist|judge|king|knight|lawyer|linguist|lyricist|mathematician|"
    r"military officer|monarch|musician|naval officer|novelist|nurse|"
    r"painter|person|philosopher|physician|physicist|poet|politician|"
    r"presenter|priest|producer|professor|puppeteer|racing driver|revolutionary|"
    r"scientist|sculptor|singer|social worker|software engineer|soldier|"
    r"statesman|surfer|teacher|tennis player|translator|traveler|violinist|"
    r"volleyball player|writer|wrestler"
    r")\b",
    re.IGNORECASE,
)

_PLACE_PATTERN = re.compile(
    r"\b("
    r"airport|archipelago|area|basin|borough|campus|capital|city|cliff|"
    r"colony|commune|community|county|district|estate|fjord|forest|"
    r"glacier|hamlet|hill|hillock|island|islands|kingdom|lagoon|lake|"
    r"landform|locality|locale|massif|municipality|neighborhood|neighbourhood|"
    r"ocean|ordinance|parish|park|peninsula|place|plateau|port|province|"
    r"region|reservoir|river|sea|settlement|state|suburb|territory|"
    r"town|township|valley|village|waterfall|waterway"
    r")\b",
    re.IGNORECASE,
)

# Descriptions like "American politician" carry a nationality adjective in front
# of the role, which is why the patterns look for the role anywhere in the text.
_NATIONALITY_HINT = re.compile(
    r"^\s*(american|british|english|scottish|welsh|irish|french|german|italian|"
    r"spanish|dutch|belgian|swiss|austrian|australian|canadian|indian|japanese|"
    r"chinese|korean|brazilian|mexican|argentine|argentinian|polish|russian|"
    r"soviet|swedish|norwegian|danish|finnish|greek|turkish|egyptian|nigerian|"
    r"kenyan|portuguese|hungarian|czech|romanian|ukrainian|serbian|croatian)\b",
    re.IGNORECASE,
)


def classify_description(description: str | None) -> str:
    if not description:
        return OTHER
    if _PERSON_PATTERN.search(description):
        return PERSON
    if _PLACE_PATTERN.search(description):
        return PLACE
    return OTHER


def looks_like_person(description: str | None) -> bool:
    """Second pass used when the description has no explicit role word."""

    if not description:
        return False
    return bool(_NATIONALITY_HINT.search(description)) and _PERSON_PATTERN.search(description)


async def classify_titles(
    client: MediaWikiClient, titles: list[str], settings: Settings
) -> dict[str, str]:
    """Return ``{title: person|place|other}`` for at most ``classify_max_items``."""

    limited = titles[: max(0, settings.classify_max_items)]
    if not limited:
        return {}

    async def lookup(title: str) -> tuple[str, str]:
        try:
            description = await client.wikidata_descriptions(title)
        except Exception:  # noqa: BLE001 - classification is best effort
            return title, OTHER
        return title, classify_description(description)

    pairs = await asyncio.gather(*(lookup(title) for title in limited))
    result = dict(pairs)
    for title in titles[settings.classify_max_items :]:
        result.setdefault(title, OTHER)
    return result
