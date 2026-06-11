#!/usr/bin/env python3
"""
Translate Markdown documentation while preserving MkDocs structure.

Designed for one-time country bootstraps, e.g. translating copied AT content in
sites/si/<area>/docs from German to Slovenian. The script only edits Markdown
files and leaves file names, folder names, .pages files, images, and attachments
unchanged.

Provider:
  - openai-compatible Chat Completions endpoint via stdlib urllib
  - requires OPENAI_API_KEY unless --dry-run is used

Examples:
  python tools/translation/translate_markdown.py --root sites/si --dry-run
  python tools/translation/translate_markdown.py --root sites/si --apply
  python tools/translation/translate_markdown.py --root sites/si/schaden/docs --apply --glossary glossary.si.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable

PLACEHOLDER_PREFIX = "ASKO_KEEP_"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")


@dataclasses.dataclass
class ProtectedMarkdown:
    text: str
    placeholders: dict[str, str]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="surrogateescape")


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", errors="surrogateescape")


def iter_markdown_files(root: Path) -> Iterable[Path]:
    ignored_parts = {"assets", "exports", ".git", "__pycache__"}
    for path in sorted(root.rglob("*.md")):
        if any(part in ignored_parts for part in path.parts):
            continue
        yield path


def load_glossary(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    data = json.loads(read_text(path))
    if not isinstance(data, dict):
        raise ValueError("Glossary must be a JSON object: {\"German term\": \"Slovenian term\"}")
    return {str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}


def protect_markdown(text: str) -> ProtectedMarkdown:
    placeholders: dict[str, str] = {}

    def keep(value: str) -> str:
        key = f"{PLACEHOLDER_PREFIX}{len(placeholders):05d}"
        placeholders[key] = value
        return key

    # YAML frontmatter at top of file.
    text = re.sub(r"\A---\s*\n.*?\n---\s*(?=\n)", lambda m: keep(m.group(0)), text, flags=re.S)

    # Fenced and indented code blocks.
    text = re.sub(r"(^```[\s\S]*?^```\s*$)", lambda m: keep(m.group(0)), text, flags=re.M)
    text = re.sub(r"(^~~~[\s\S]*?^~~~\s*$)", lambda m: keep(m.group(0)), text, flags=re.M)

    # HTML blocks and comments often contain widgets/scripts/styles.
    text = re.sub(r"<!--[\s\S]*?-->", lambda m: keep(m.group(0)), text)
    text = re.sub(r"<(script|style)\b[\s\S]*?</\1>", lambda m: keep(m.group(0)), text, flags=re.I)

    # Markdown links/images: keep the target URL/path stable, translate only surrounding text.
    text = re.sub(r"(!?\[[^\]]*\]\()([^\)]+)(\))", lambda m: m.group(1) + keep(m.group(2)) + m.group(3), text)

    # Inline code, raw URLs, mail addresses, anchors.
    text = re.sub(r"`[^`\n]+`", lambda m: keep(m.group(0)), text)
    text = re.sub(r"https?://[^\s)]+", lambda m: keep(m.group(0)), text)
    text = re.sub(r"mailto:[^\s)]+", lambda m: keep(m.group(0)), text)
    text = re.sub(r"#[A-Za-z0-9_\-./%]+", lambda m: keep(m.group(0)), text)

    return ProtectedMarkdown(text=text, placeholders=placeholders)


def restore_markdown(text: str, placeholders: dict[str, str]) -> str:
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def glossary_prompt(glossary: dict[str, str]) -> str:
    if not glossary:
        return "No project glossary has been provided yet."
    rows = [f"- {source} => {target}" for source, target in sorted(glossary.items(), key=lambda item: item[0].lower())]
    return "Project glossary. Use these translations exactly where applicable:\n" + "\n".join(rows)


def build_messages(markdown: str, glossary: dict[str, str], source_lang: str, target_lang: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You translate internal MkDocs Markdown documentation. "
                "Return only the translated Markdown, with no explanation. "
                "Preserve Markdown syntax, tables, headings, lists, placeholders, links, image paths, HTML snippets, and line breaks as much as possible. "
                f"Translate from {source_lang} to {target_lang}."
            ),
        },
        {
            "role": "user",
            "content": glossary_prompt(glossary) + "\n\nMarkdown to translate:\n\n" + markdown,
        },
    ]


def translate_openai(markdown: str, glossary: dict[str, str], args: argparse.Namespace) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Use --dry-run or set the key before --apply.")

    payload = {
        "model": args.model,
        "temperature": 0.1,
        "messages": build_messages(markdown, glossary, args.source_language, args.target_language),
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        args.api_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(1, args.retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            return str(data["choices"][0]["message"]["content"]).strip() + "\n"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= args.retries:
                break
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"Translation request failed after {args.retries} attempts: {last_error}")


def validate_placeholders(translated: str, placeholders: dict[str, str]) -> list[str]:
    missing = [key for key in placeholders if key not in translated]
    return missing


def translate_file(path: Path, glossary: dict[str, str], args: argparse.Namespace) -> tuple[bool, str]:
    original = read_text(path)
    if not original.strip():
        return False, "empty"

    protected = protect_markdown(original)
    if args.dry_run:
        return False, f"dry-run protected={len(protected.placeholders)} chars={len(original)}"

    translated_protected = translate_openai(protected.text, glossary, args)
    missing = validate_placeholders(translated_protected, protected.placeholders)
    if missing:
        raise RuntimeError(f"{path}: translation lost placeholders: {', '.join(missing[:10])}")

    translated = restore_markdown(translated_protected, protected.placeholders)
    if translated == original:
        return False, "unchanged"

    if args.apply:
        write_text(path, translated)
        return True, "translated"

    return False, "preview-only"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate MkDocs Markdown files while preserving structure.")
    parser.add_argument("--root", required=True, help="Root folder to scan, e.g. sites/si or sites/si/schaden/docs")
    parser.add_argument("--glossary", help="Optional JSON glossary: {\"Arbeitsanweisung\": \"delovno navodilo\"}")
    parser.add_argument("--source-language", default="German")
    parser.add_argument("--target-language", default="Slovenian")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of files to process, 0 = all")
    parser.add_argument("--dry-run", action="store_true", help="List files and protection counts without calling the API")
    parser.add_argument("--apply", action="store_true", help="Write translated Markdown files")
    args = parser.parse_args(argv)

    if args.dry_run and args.apply:
        parser.error("Use either --dry-run or --apply, not both.")
    if not args.dry_run and not args.apply:
        parser.error("Choose --dry-run first, then --apply when ready.")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: root not found: {root}", file=sys.stderr)
        return 2

    glossary_path = Path(args.glossary).resolve() if args.glossary else None
    glossary = load_glossary(glossary_path)

    files = list(iter_markdown_files(root))
    if args.limit > 0:
        files = files[: args.limit]

    print(f"Root: {root}")
    print(f"Files: {len(files)}")
    print(f"Glossary terms: {len(glossary)}")
    print(f"Mode: {'dry-run' if args.dry_run else 'apply'}")

    changed = 0
    for index, path in enumerate(files, start=1):
        try:
            did_change, status = translate_file(path, glossary, args)
            if did_change:
                changed += 1
            print(f"[{index}/{len(files)}] {path}: {status}")
        except Exception as exc:
            print(f"ERROR: {path}: {exc}", file=sys.stderr)
            return 1

    print(f"Done. Changed files: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
