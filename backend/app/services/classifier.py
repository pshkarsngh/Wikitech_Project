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

# A role word only counts when it stands on its own. Without the trailing guard
# "general-purpose computer" reads as the military rank "general", and
# "lieutenant-commander" and "co-founder" read as "commander" and "founder":
# a hyphen continues the word, so the role is a modifier of something else
# rather than the description of the subject.
#
# "general" is deliberately absent even though the military rank is a real role:
# as a bare word it is far more often an ordinary adjective ("general
# relativity", "general assembly", "general election") than a description of a
# person, and every one of those would put a non-person in the people list.
_ROLE_END = r"(?<![\w-])(?:"
_ROLE_TAIL = r")(?![\w-])"

_PERSON_PATTERN = re.compile(
    _ROLE_END
    + r"actor|actress|architect|artist|astronaut|athlete|author|bishop|"
    r"businessman|businesswoman|chef|chess player|coach|composer|conductor|"
    r"diplomat|director|dramatist|economist|engineer|entrepreneur|explorer|"
    r"farmer|film producer|footballer|football player|geologist|"
    r"guitarist|historian|human rights activist|illustrator|industrialist|"
    r"inventor|journalist|judge|king|knight|lawyer|linguist|lyricist|"
    r"mathematician|military officer|monarch|musician|naval officer|novelist|"
    r"nurse|painter|person|philosopher|physician|physicist|poet|politician|"
    r"presenter|priest|producer|professor|puppeteer|racing driver|revolutionary|"
    r"scientist|sculptor|singer|social worker|software engineer|soldier|"
    r"statesman|surfer|teacher|tennis player|translator|traveler|violinist|"
    r"volleyball player|writer|wrestler"
    + _ROLE_TAIL,
    re.IGNORECASE,
)

_PLACE_PATTERN = re.compile(
    _ROLE_END
    + r"airport|archipelago|area|basin|borough|campus|capital|city|cliff|"
    r"colony|commune|community|county|district|estate|fjord|forest|"
    r"glacier|hamlet|hill|hillock|island|islands|kingdom|lagoon|lake|"
    r"landform|locality|locale|massif|municipality|neighborhood|neighbourhood|"
    r"ocean|ordinance|parish|park|peninsula|place|plateau|port|province|"
    r"region|reservoir|river|sea|settlement|state|suburb|territory|"
    r"town|township|valley|village|waterfall|waterway"
    + _ROLE_TAIL,
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
) -> tuple[dict[str, str], bool]:
    """Return ``({title: person|place|other}, truncated)`` for missing names.

    This is the expensive path: a name with no article has no description of its
    own, so Wikidata is asked for one, which costs a request per name. It is
    therefore capped at ``classify_max_items``, and ``truncated`` says whether
    names were left unclassified because of that cap.
    """

    limited = titles[: max(0, settings.classify_max_items)]
    if not limited:
        return {}, bool(titles)

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
    return result, len(titles) > len(limited)
