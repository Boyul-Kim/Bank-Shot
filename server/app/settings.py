"""League and model settings, with defaults for your league and the reference (original page) settings."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

CATS = ["fg", "ft", "tpm", "pts", "reb", "ast", "stl", "blk", "to"]
CAT_LABEL = {"fg": "FG%", "ft": "FT%", "tpm": "3PM", "pts": "PTS", "reb": "REB",
             "ast": "AST", "stl": "STL", "blk": "BLK", "to": "TO"}
SLOT_TYPES = ["PG", "SG", "G", "SF", "PF", "F", "C", "UT"]
Punt = Optional[Literal["fg", "ft", "tpm", "pts", "reb", "ast", "stl", "blk", "to"]]


class League(BaseModel):
    teams: int = Field(12, ge=2, le=30)
    budget: int = Field(200, ge=10, le=10000)
    slots: list[str] = Field(default_factory=lambda: ["PG", "SG", "G", "SF", "PF", "F", "C", "C", "UT", "UT"])
    bench: int = Field(0, ge=0, le=15)
    categories: list[str] = Field(default_factory=lambda: list(CATS))
    board_size: int = Field(150, ge=20, le=400)

    @field_validator("slots")
    @classmethod
    def _slots(cls, v):
        v = [s.upper() for s in v]
        bad = [s for s in v if s not in SLOT_TYPES]
        if bad:
            raise ValueError(f"Unknown slot(s) {bad}. Use {SLOT_TYPES}.")
        if not v:
            raise ValueError("Add at least one roster slot.")
        return v

    @field_validator("categories")
    @classmethod
    def _cats(cls, v):
        bad = [c for c in v if c not in CATS]
        if bad:
            raise ValueError(f"Unknown categories {bad}. Use {CATS}.")
        if len(v) < 2:
            raise ValueError("Pick at least two categories.")
        return [c for c in CATS if c in v]

    @property
    def roster(self) -> int:
        return len(self.slots) + self.bench

    @model_validator(mode="after")
    def _fits(self):
        if self.budget < self.roster:
            raise ValueError(f"A ${self.budget} budget can't fill {self.roster} roster spots at $1 each.")
        return self


class Model(BaseModel):
    rescale_market: bool = True
    fta_per_pt: float = Field(0.25, gt=0, le=1)
    bargain_bid_up: float = Field(0.5, ge=0, le=1)
    bargain_threshold: float = Field(4, ge=0)
    max_bargains: int = Field(3, ge=0, le=20)
    star_price: int = Field(40, ge=1)
    max_stars: int = Field(2, ge=0, le=20)
    min_gp: int = Field(50, ge=0, le=82)
    sigma: float = Field(5.0, gt=0)
    opponent_baseline: Literal["drafted", "pool"] = "drafted"
    punt_options: list[Optional[str]] = Field(default_factory=lambda: [None, "ft", "fg", "to", "ast", "tpm", "blk", "pts"])
    anchor_punt_guard: float = 0.5
    reweight_iters: int = Field(6, ge=1, le=20)
    draft_reweight_iters: int = Field(3, ge=1, le=20)
    anchors: int = Field(12, ge=1, le=40)

    @field_validator("punt_options")
    @classmethod
    def _punts(cls, v):
        bad = [p for p in v if p is not None and p not in CATS]
        if bad:
            raise ValueError(f"Unknown punt options {bad}.")
        return v if None in v else [None] + v


class Sources(BaseModel):
    auto_fetch: bool = True
    fetch_max_age_hours: float = Field(12, ge=0)
    hashtag_adp_url: str = "https://hashtagbasketball.com/fantasy-basketball-adp"
    hashtag_auction_url: str = "https://hashtagbasketball.com/fantasy-basketball-auction-values"
    fantasypros_proj_url: str = "https://www.fantasypros.com/nba/projections/overall.php"
    rotoworld_rank_url: str = ("https://www.nbcsports.com/fantasy/basketball/news/"
                               "fantasy-basketball-2026-27-preseason-top-200-rankings-wemby-jokic-sga-headline-the-board")
    rotoworld_mock_url: str = ("https://www.nbcsports.com/fantasy/basketball/news/"
                               "2026-fantasy-basketball-salary-mock-draft-jokic-wemby-command-massive-bids")


class Settings(BaseModel):
    league: League = Field(default_factory=League)
    model: Model = Field(default_factory=Model)
    sources: Sources = Field(default_factory=Sources)


def defaults() -> Settings:
    return Settings()


def reference() -> Settings:
    """The settings behind the original single-page board: 13 spots (8 positional + 5 bench), no rescale."""
    return Settings(
        league=League(slots=["PG", "SG", "G", "SF", "PF", "F", "C", "C"], bench=5),
        model=Model(rescale_market=False, opponent_baseline="pool"),
    )
