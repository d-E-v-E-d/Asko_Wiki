# Markdown Translation Tool

This tool prepares the one-time translation of copied MkDocs content, for example Austria to Slovenia.

It translates only Markdown files and keeps file names, folder names, `.pages`, images, and attachments unchanged.

## Typical workflow on the server

```bash
cd /srv/arbeitsanweisung/app
bash scripts/bootstrap_country_content.sh si
python tools/translation/translate_markdown.py --root sites/si --dry-run
python tools/translation/translate_markdown.py --root sites/si --apply
bash scripts/deploy.sh
```

## Glossary

The glossary is optional and can be added later as JSON:

```json
{
  "Arbeitsanweisung": "delovno navodilo",
  "Schaden": "skoda"
}
```

Use it with:

```bash
python tools/translation/translate_markdown.py --root sites/si --glossary tools/translation/glossary.si.json --apply
```

## Safety

- Run `--dry-run` first.
- The script requires `OPENAI_API_KEY` only for `--apply`.
- Markdown code blocks, links, image targets, frontmatter, and placeholders are protected before translation.
- Existing folder and file names are intentionally not translated.
