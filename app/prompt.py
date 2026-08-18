from pathlib import Path

SYSTEM_PROMPT = Path(__file__).resolve().parents[1].joinpath("PROMPT.md").read_text(encoding="utf-8")

