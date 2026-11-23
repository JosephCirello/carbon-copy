"""Fail if any file in the project looks like it holds a private key, a seed or a provider token."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".hypothesis"}
PATTERNS = [
    (re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"), "a PEM private key"),
    (re.compile(r"CARBON_COPY_KEY\s*=\s*['\"]?[0-9a-fA-F]{64}"), "a Carbon Copy signing seed"),
    (re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"), "a model provider key"),
    (re.compile(r"\bxai-[A-Za-z0-9]{20,}"), "an xAI key"),
    (re.compile(r"\bA[0-9A-Za-z_-]{70,}\b"), "a PayPal client secret"),
]


def scan() -> list[str]:
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {".png", ".jpg", ".gif", ".mp3", ".wav", ".mp4", ".ico"} or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rx, what in PATTERNS:
            if rx.search(text):
                hits.append(f"{p.relative_to(ROOT)}: looks like {what}")
    return hits


if __name__ == "__main__":
    found = scan()
    for h in found:
        print(h)
    sys.exit(1 if found else 0)
