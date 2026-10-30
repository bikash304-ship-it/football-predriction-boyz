"""Natural-English explanations built ONLY from the prediction payload.

The deterministic generator below is the source of truth. An optional LLM pass may
rephrase it for readability, but its output is rejected unless every number it
contains already appears in the grounded text (see `validate_llm_rewrite`).
Each sentence is tagged as `fact` (verified retrieved statistic) or `model`
(estimate produced by the statistical model) so the UI can label them.
"""
from __future__ import annotations

import json
import os
import re


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(x * 100)}%"


def _f(x: float | None, nd: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _s(kind: str, text: str) -> dict:
    return {"kind": kind, "text": text}


def build_explanation(pred: dict) -> dict:
    h, a = pred["home"], pred["away"]
    d = pred["display"]
    mk = pred["markets"]
    ctx = pred["context"]
    hp, ap = ctx["home_profile"], ctx["away_profile"]
    hh, aa = hp["home"], ap["away"]  # venue-specific splits
    r = pred["rates"]
    sections: dict[str, list[dict]] = {}

    # 1. Home case
    s = [_s("model", f"The model gives {h} a {d['1x2']['home']}% chance of winning, with expected goals of "
                     f"{_f(r['home'])} for {h} against {_f(r['away'])} for {a}.")]
    if hh["played"]:
        s.append(_s("fact", f"At home over their last {hh['played']} matches, {h} have won {hh['wins']}, drawn "
                            f"{hh['draws']} and lost {hh['losses']}, scoring {_f(hh['gf_per_match'])} and conceding "
                            f"{_f(hh['ga_per_match'])} per game."))
    if aa["played"] and aa["ga_per_match"] is not None and aa["ga_per_match"] >= 1.5:
        s.append(_s("fact", f"{a} have conceded {_f(aa['ga_per_match'])} goals per game on the road in their last {aa['played']} away matches."))
    sections["home_case"] = s

    # 2. Away case
    s = [_s("model", f"{a} are given a {d['1x2']['away']}% chance of winning.")]
    if aa["played"]:
        s.append(_s("fact", f"Away from home over their last {aa['played']} matches, {a} have won {aa['wins']}, drawn "
                            f"{aa['draws']} and lost {aa['losses']}."))
    if ap["last5"]["played"]:
        s.append(_s("fact", f"Recent form for {a} (most recent first): {ap['last5']['form'] or 'n/a'}."))
    rat = ctx["ratings"]
    if rat["away_attack"] is not None and rat["home_attack"] is not None and rat["away_attack"] > rat["home_attack"]:
        s.append(_s("model", f"The fitted ratings rate {a}'s attack above {h}'s, which keeps the away win a live outcome."))
    sections["away_case"] = s

    # 3. Draw
    s = [_s("model", f"The model puts the draw at {d['1x2']['draw']}%.")]
    top = mk["top_scores"]
    draws_in_top = [t["score"] for t in top if t["home"] == t["away"]]
    if draws_in_top:
        s.append(_s("model", f"{', '.join(draws_in_top)} is among the three most likely exact scores."))
    gap = abs(d['1x2']['home'] - d['1x2']['away'])
    if gap <= 10:
        s.append(_s("model", f"The two sides are closely matched (win probabilities within {gap} points), which supports a draw."))
    sections["draw"] = s

    # 4. BTTS
    s = [_s("model", f"Both teams to score: Yes {d['btts']['yes']}% / No {d['btts']['no']}%.")]
    for p in (hp, ap):
        l10 = p["last10"]
        if l10["played"]:
            s.append(_s("fact", f"{p['team']}: BTTS landed in {_pct(l10['btts_rate'])} of the last {l10['played']} matches; "
                                f"clean sheets {_pct(l10['clean_sheet_rate'])}, failed to score {_pct(l10['failed_to_score_rate'])}."))
    sections["btts"] = s

    # 5. Goals
    tot = r["home"] + r["away"]
    s = [_s("model", f"The model expects {_f(tot)} total goals. Over 2.5 is {d['ou']['2.5']['over']}% and "
                     f"Under 2.5 is {d['ou']['2.5']['under']}%; Over 1.5 is {d['ou']['1.5']['over']}%.")]
    for p in (hp, ap):
        l10 = p["last10"]
        if l10["played"]:
            s.append(_s("fact", f"{p['team']} matches went over 2.5 goals {_pct(l10['over25_rate'])} of the time over the last {l10['played']}."))
    sections["goals"] = s

    # 6. Key stats
    s = []
    for p in (hp, ap):
        if p["last10"]["xg_for_per_match"] is not None:
            s.append(_s("fact", f"{p['team']} xG last 10: {_f(p['last10']['xg_for_per_match'])} for, "
                                f"{_f(p['last10']['xg_against_per_match'])} against per match."))
    st = ctx.get("standings") or {}
    for side, team in (("home", h), ("away", a)):
        row = st.get(side)
        if row:
            s.append(_s("fact", f"{team} sit {row.get('rank')} in the table with {row.get('points')} points from {row.get('played')} games."))
    if ctx["h2h"]:
        res = ", ".join(f"{m['home']} {m['home_goals']}-{m['away_goals']} {m['away']}" for m in ctx["h2h"][:3])
        s.append(_s("fact", f"Recent head-to-heads: {res}. Head-to-head carries little weight in the model because samples are small and squads change."))
    ts = ", ".join(f"{t['score']} ({_pct(t['p'])})" for t in top)
    s.append(_s("model", f"Most likely scores: {ts}."))
    sections["key_stats"] = s

    # 7. Risks
    s = []
    for adj in pred["adjustments"]:
        s.append(_s("model", f"Adjustment applied: {adj['reason']} (x{adj['factor']:.2f} on expected goals)."))
    for m in pred["completeness"]["missing"]:
        s.append(_s("fact", m + "."))
    if ctx["injuries_status"] == "verified" and ctx["injuries"]:
        names = ", ".join(f"{i['player']} ({i['team']})" for i in ctx["injuries"][:6])
        s.append(_s("fact", f"Verified absences: {names}. These are shown for context and are not individually modelled."))
    u = pred["uncertainty"]
    s.append(_s("model", f"Accounting for rating uncertainty, the home-win probability plausibly ranges "
                         f"{_pct(u['home'][0])}–{_pct(u['home'][1])}. Confidence: {pred['confidence']}."))
    s.append(_s("model", "Probabilities are estimates, not guarantees. Red cards, late team news, weather and "
                         "tactical changes are not captured by a goals model."))
    sections["risks"] = s

    headline_key = max(("home", "draw", "away"), key=lambda k: d["1x2"][k])
    headline = {"home": f"{h} are the most probable winners", "draw": "A draw is the single most probable result",
                "away": f"{a} are the most probable winners"}[headline_key]
    return {"headline": headline, "sections": sections, "source": "deterministic", "model_version": pred["model_version"]}


def flatten(expl: dict) -> str:
    return "\n".join(x["text"] for sec in expl["sections"].values() for x in sec)


_NUM = re.compile(r"\d+(?:\.\d+)?")


def validate_llm_rewrite(grounded: str, rewrite: str) -> bool:
    """Reject any rewrite that introduces a number not present in the grounded text."""
    allowed = set(_NUM.findall(grounded))
    return all(n in allowed for n in _NUM.findall(rewrite))


def llm_polish(expl: dict, team_names: tuple[str, str]) -> dict:
    """Optional: ask Claude to make the text read more naturally. Falls back silently
    to the deterministic text when no key is set, the call fails, or validation fails."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return expl
    grounded = flatten(expl)
    try:
        import httpx  # imported lazily so the model package has no network dependency
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": os.getenv("EXPLAINER_MODEL", "claude-haiku-4-5"),
                "max_tokens": 700,
                "system": ("Rewrite football match analysis into 2-3 readable paragraphs. Use ONLY facts and numbers "
                           "in the input. Do not add statistics, players, injuries or predictions. Never say "
                           "'guaranteed', 'sure win' or 'safe bet'. Keep every probability exactly as given."),
                "messages": [{"role": "user", "content": json.dumps({"teams": team_names, "analysis": grounded})}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = "".join(b.get("text", "") for b in resp.json().get("content", []))
    except Exception:
        return expl
    banned = re.compile(r"guarantee|sure win|100% safe|lock of the day|risk[- ]free", re.I)
    if text and validate_llm_rewrite(grounded, text) and not banned.search(text):
        return {**expl, "summary": text, "source": "deterministic+llm"}
    return expl
