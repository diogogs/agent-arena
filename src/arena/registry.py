"""Insert-only generation registry (ADR-002): one JSONL line per trained
generation, never edited, never deleted. The Arena later records which
generation traded which matchday against this registry."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .gym import Generation

REGISTRY = Path("data/registry/generations.jsonl")


def _git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def record(generation: Generation, note: str = "", extra: dict | None = None) -> dict:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    n_prior = sum(1 for e in load_all() if e.get("agent") == generation.agent)
    entry = {
        "generation_id": f"{generation.agent}-g{n_prior + 1:03d}",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "note": note,
        **(extra or {}),
        **asdict(generation),
    }
    with REGISTRY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load_all() -> list[dict]:
    if not REGISTRY.exists():
        return []
    return [json.loads(line) for line in REGISTRY.read_text("utf-8").splitlines() if line.strip()]
