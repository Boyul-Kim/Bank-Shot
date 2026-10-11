"""CSV schemas shared by the seed files and user imports."""
import csv
import io

from ..core import names

SCHEMAS = {
    "hashtag_adp": {"required": ["rank", "player", "team", "pos", "adp"], "numeric": ["rank", "adp"], "min_rows": 100},
    "hashtag_auction": {"required": ["player", "hb_value", "yahoo_aav", "espn_aav"], "optional": ["team"],
                        "numeric": ["hb_value", "yahoo_aav", "espn_aav"], "min_rows": 10},
    "fantasypros_proj": {"required": ["player", "pts", "reb", "ast", "blk", "stl", "fgp", "ftp", "tpm", "gp", "min", "to"],
                         "optional": ["team", "pos"],
                         "numeric": ["pts", "reb", "ast", "blk", "stl", "fgp", "ftp", "tpm", "gp", "min", "to"], "min_rows": 100},
    "rotoworld_rank": {"required": ["rank", "player"], "optional": ["team"], "numeric": ["rank"], "min_rows": 100},
    "rotoworld_mock": {"required": ["player", "price"], "optional": ["team"], "numeric": ["price"], "min_rows": 100},
}


class InvalidData(ValueError):
    pass


def validate(source_id: str, rows: list[dict]) -> list[dict]:
    """Check columns, numbers and row count; return cleaned rows. Raises InvalidData with a readable message."""
    schema = SCHEMAS[source_id]
    if len(rows) < schema["min_rows"]:
        raise InvalidData(f"Only {len(rows)} rows found; expected at least {schema['min_rows']}.")
    cols = set(rows[0].keys())
    missing = [c for c in schema["required"] if c not in cols]
    if missing:
        raise InvalidData(f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(schema['required'])}.")
    clean, bad = [], []
    for i, r in enumerate(rows, 1):
        out = {k: (r.get(k) or "").strip() if isinstance(r.get(k), str) else r.get(k)
               for k in schema["required"] + schema.get("optional", [])}
        if not out["player"]:
            bad.append(i); continue
        out["player"] = names.strip_status(str(out["player"]))
        try:
            for k in schema["numeric"]:
                out[k] = float(str(out[k]).replace(",", "").replace("$", ""))
        except ValueError:
            bad.append(i); continue
        clean.append(out)
    if len(bad) > max(3, len(rows) // 20):
        raise InvalidData(f"{len(bad)} rows have unreadable numbers (first bad rows: {bad[:5]}).")
    return clean


def read_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return [{(k or "").strip().lower(): v for k, v in row.items()} for row in reader]


def write_csv(source_id: str, rows: list[dict]) -> str:
    schema = SCHEMAS[source_id]
    cols = schema["required"] + [c for c in schema.get("optional", []) if any(c in r for r in rows)]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
