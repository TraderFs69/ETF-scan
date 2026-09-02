from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)

COLUMNS = [
    "symbol", "name", "market", "category", "date", "score", "close", "rs_percentile",
    "rsi", "ema_rebound", "relative_volume", "average_dollar_volume", "atr", "stop",
    "target_2r", "target_3r", "risk_pct", "reasons",
]


def select_diversified(frame: pd.DataFrame, top_n: int, max_per_category: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    selected: list[int] = []
    category_counts: dict[str, int] = {}
    for index, row in frame.iterrows():
        category = str(row["category"])
        if category_counts.get(category, 0) >= max_per_category:
            continue
        selected.append(index)
        category_counts[category] = category_counts.get(category, 0) + 1
        if len(selected) >= top_n:
            break
    return frame.loc[selected].reset_index(drop=True)


def write_outputs(root: Path, signals: list[dict], universe: pd.DataFrame, diagnostics: dict, cfg: dict) -> pd.DataFrame:
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(signals, columns=COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(
            ["score", "rs_percentile", "relative_volume", "symbol"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)

    top = select_diversified(
        frame,
        top_n=int(cfg["top_n"]),
        max_per_category=int(cfg["maximum_per_category"]),
    )

    frame.to_csv(output / "tous_les_signaux_etf.csv", index=False)
    top.to_csv(output / "top_etf_diversifie.csv", index=False)
    universe.to_csv(output / "univers_etf_utilise.csv", index=False)
    (output / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    now = datetime.now(ZoneInfo("America/Toronto"))
    lines = [
        "# Scanner Swing ETF — Trading en Action",
        "",
        f"Généré le **{now:%Y-%m-%d à %H:%M} HE** avec une bougie quotidienne terminée.",
        f"Univers actif : **{len(universe)} ETF**. Données valides : **{diagnostics['download']['downloaded']}**. Signaux : **{len(frame)}**.",
        "",
    ]

    if top.empty:
        lines.append("Aucun ETF ne satisfait toutes les conditions aujourd'hui.")
    else:
        lines.extend([
            "| Rang | ETF | Marché | Catégorie | Score | Prix | Force rel. | RSI | Rebond | Stop | Cible 2R |",
            "|---:|---|---|---|---:|---:|---:|---:|---|---:|---:|",
        ])
        for rank, row in enumerate(top.itertuples(index=False), 1):
            currency = "$ CA" if row.market == "CA" else "$ US"
            lines.append(
                f"| {rank} | {row.symbol} | {row.market} | {row.category} | {row.score}/100 | "
                f"{row.close:.2f} {currency} | {row.rs_percentile:.0f}e | {row.rsi:.1f} | "
                f"{row.ema_rebound} | {row.stop:.2f} | {row.target_2r:.2f} |"
            )
        lines.extend(["", "## Confluences", ""])
        for row in top.itertuples(index=False):
            lines.append(f"- **{row.symbol} — {row.score}/100 :** {row.reasons}")

    lines.extend([
        "",
        "> Le score classe des configurations techniques. Il ne constitue ni une recommandation ni une garantie de rendement.",
    ])
    (output / "rapport_etf.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return top


def send_discord(top: pd.DataFrame, diagnostics: dict, cfg: dict) -> None:
    if not cfg.get("enabled", False):
        return
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        LOGGER.warning("DISCORD_WEBHOOK_URL absent : rapport créé sans publication Discord.")
        return

    if top.empty:
        description = "Aucun ETF ne satisfait toutes les confluences aujourd'hui."
    else:
        blocks = []
        for rank, row in enumerate(top.head(10).itertuples(index=False), 1):
            currency = "CA" if row.market == "CA" else "US"
            blocks.append(
                f"**{rank}. {row.symbol} — {row.score}/100** · {row.category}\n"
                f"Prix {row.close:.2f} $ {currency} | Force rel. {row.rs_percentile:.0f}e | RSI {row.rsi:.1f}\n"
                f"Rebond {row.ema_rebound} | Stop {row.stop:.2f} | Cible 2R {row.target_2r:.2f}"
            )
        description = "\n\n".join(blocks)

    payload = {
        "username": cfg.get("username", "Trading en Action"),
        "embeds": [{
            "title": "Scanner Swing ETF — Canada et États-Unis",
            "description": description[:4000],
            "color": 0xD4AF37,
            "footer": {
                "text": f"Couverture Yahoo {diagnostics['download']['coverage_pct']} % · Bougie quotidienne terminée"
            },
        }],
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(webhook, json=payload, timeout=20)
            response.raise_for_status()
            return
        except requests.RequestException as exc:
            LOGGER.warning("Discord, tentative %s/3 : %s", attempt, exc)
            if attempt < 3:
                time.sleep(2 * attempt)
    LOGGER.error("Impossible de publier le rapport sur Discord après trois tentatives.")
