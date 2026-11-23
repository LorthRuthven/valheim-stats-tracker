"""Pure helpers for V3.0 period filtering and honest session comparisons."""
from __future__ import annotations

import math


PERIODS = (("Tout", None), ("7 jours", 7*86400), ("30 jours", 30*86400),
           ("90 jours", 90*86400), ("1 an", 365*86400))


def filter_sessions(sessions, period=None, reference=None):
    """Filter by actual save timestamps, not guessed playing time."""
    if period is None or not sessions:
        return list(sessions)
    if not math.isfinite(float(period)) or period <= 0:
        raise ValueError("Période invalide")
    endpoint = float(reference) if reference is not None else max(s["end"] for s in sessions)
    return [s for s in sessions if endpoint - float(s["end"]) <= period]


def session_comparison(session, previous=None):
    """Delta between session gains; resets remain unavailable rather than zero."""
    previous_gains = previous.get("gains", {}) if previous else {}
    results = {}
    for name, value in session.get("gains", {}).items():
        if not math.isfinite(float(value)):
            continue
        baseline = previous_gains.get(name)
        results[name] = {
            "value": float(value),
            "previous": float(baseline) if baseline is not None else None,
            "change": float(value) - float(baseline) if baseline is not None else None,
        }
    return results


def session_summary(session, previous=None):
    """Descriptive session details without asserting actual play duration."""
    details = session_comparison(session, previous)
    labels = {"kills": "Créatures", "builds": "Constructions",
              "crafts": "Fabrications", "deaths": "Décès"}
    parts = [f"{labels.get(key,key)} : +{value['value']:g}"
             + (f" (écart : {value['change']:+g} vs session précédente)"
                if value["change"] is not None else "")
             for key,value in details.items()]
    resets = session.get("resets", ())
    if resets:
        parts.append("Compteurs réinitialisés, exclus : " + ", ".join(resets))
    return ("Relevés : " + str(session.get("samples", 0))
            + " • Intervalle observé : " + f"{session.get('span_minutes',0):.0f} min"
            + "\n" + ("\n".join(parts) if parts else "Aucun gain mesurable")
            + "\nL'intervalle entre relevés n'est pas du temps réellement joué.")
