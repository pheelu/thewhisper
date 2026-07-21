"""Servizi puri del dialogo: generazione degli alias misteriosi."""

import secrets

ALIAS_POOL = [
    "Ammiratore Segreto",
    "Ammiratrice Segreta",
    "Penna Misteriosa",
    "Ombra del Salotto",
    "Maschera d'Argento",
    "Cuore Nascosto",
    "Sussurro Notturno",
    "Sconosciuto Galante",
    "Dama Velata",
    "Cavaliere Senza Nome",
]


def random_alias() -> str:
    base = secrets.choice(ALIAS_POOL)
    return f"{base} n.{secrets.randbelow(90) + 10}"
