"""Player-name and team-code normalization shared by every source."""
import re
import unicodedata

# Real spelling differences between sources, by matching key -> canonical matching key.
# (Suffixes, accents, punctuation and status tags are already handled by `key`.)
ALIASES = {
    "herb jones": "herbert jones",
    "cam johnson": "cameron johnson",
    "nicolas claxton": "nic claxton",
    "alexandre sarr": "alex sarr",
    "jimmy butler iii": "jimmy butler",
    "moe wagner": "moritz wagner",
    "ronald holland": "ron holland",
}

TEAM_CODES = {
    "NYK": "NY", "GSW": "GS", "SAS": "SA", "UTH": "UTA", "UTAH": "UTA", "NOR": "NO", "NOP": "NO",
    "PHX": "PHO", "BRK": "BKN", "WSH": "WAS", "CHO": "CHA",
}

_STATUS = re.compile(r"\((?:OUT|DTD|GTD|O|Q|IR|INJ|SUSP)\)", re.I)
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv)\b")
_POS = re.compile(r"PG|SG|SF|PF|C")


def strip_status(name: str) -> str:
    return re.sub(r"\s+", " ", _STATUS.sub("", name or "")).strip()


def key(name: str) -> str:
    """Matching key: lowercase ASCII, no punctuation, no suffixes, aliases applied."""
    s = unicodedata.normalize("NFKD", strip_status(name)).encode("ascii", "ignore").decode()
    s = s.lower().replace("'", "").replace("’", "").replace(".", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", _SUFFIX.sub("", s)).strip()
    return ALIASES.get(s, s)


def slug(name: str) -> str:
    return key(name).replace(" ", "-")


def team(code: str) -> str:
    c = (code or "").strip().upper()
    return TEAM_CODES.get(c, c)


def positions(text: str) -> list[str]:
    """'PG,SG' / 'PG/SG' / 'PGSG' / 'SFPFC' -> ordered unique list of positions."""
    out = []
    for p in _POS.findall((text or "").upper()):
        if p not in out:
            out.append(p)
    return out
