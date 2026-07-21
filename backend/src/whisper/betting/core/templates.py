"""Template delle Scommesse dell'Alta Società.

Reference statica in codice (snapshotted nel round alla creazione, come da
architettura: il round è immutabile rispetto al template). Le metriche sono
misurate DOPO la chiusura delle puntate (bet-before-outcome).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BetTemplate:
    code: str
    title: str
    prompt: str
    resolution_rule: str  # most_photographed | top_gossip | best_detective
    betting_seconds: int = 600  # finestra puntate (10 min)
    measurement_seconds: int = 1800  # finestra di misurazione dopo il lock (30 min)
    min_stake: int = 5
    max_stake: int = 100


BET_TEMPLATES: list[BetTemplate] = [
    BetTemplate(
        code="most_photographed",
        title="Il Soggetto più Desiderato",
        prompt="Chi sarà la persona più fotografata nella prossima mezz'ora?",
        resolution_rule="most_photographed",
    ),
    BetTemplate(
        code="top_gossip",
        title="Il Pettegolo più Instancabile",
        prompt="Chi scriverà più commenti nella prossima mezz'ora?",
        resolution_rule="top_gossip",
    ),
    BetTemplate(
        code="best_detective",
        title="Il Segugio dell'Alta Società",
        prompt="Chi indovinerà più Soggetti nella prossima mezz'ora?",
        resolution_rule="best_detective",
    ),
]


def template_by_index(index: int) -> BetTemplate:
    return BET_TEMPLATES[index % len(BET_TEMPLATES)]


def template_by_code(code: str) -> BetTemplate | None:
    return next((t for t in BET_TEMPLATES if t.code == code), None)
