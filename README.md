# Asko Wiki

Code-only Repository fuer das interne ASKO Wiki / die Arbeitsanweisungen.

## Grundsatz

Dieses Repository enthaelt nur Programmcode und technische Vorlagen. Fachliche Inhalte bleiben lokal auf dem Server und werden nicht zu GitHub synchronisiert.

## In Git enthalten

- `app/` FastAPI Backend, Editor und Admin-Tool
- `scripts/` Deploy- und Betriebs-Skripte
- `tools/` Backup-/Hilfsskripte
- `shared/` gemeinsame MkDocs Assets und Overrides
- `portal/` technische Portal-Oberflaeche
- `sites/*/mkdocs.yml` technische Bereichskonfigurationen
- leere `sites/*/docs` und `sites/*/docs_draft` Platzhalter

## Nicht in Git

- Markdown-Inhalte unter `sites/**/docs/**/*.md`
- Entwuerfe unter `sites/**/docs_draft/**/*.md`
- Uploads unter `assets/images` und `assets/files`
- `review/`
- `versions/`
- `site/` Build-Ausgaben
- produktive `config.json`, `config.local.json`, `users.json`

## Shared Assets

`shared/` ist die technische Quelle fuer MkDocs CSS, JavaScript, Logos und Overrides. Beim Build/Deploy werden diese Dateien automatisch in die lokalen `sites/.../docs/assets`, `sites/.../docs_draft/assets` und `sites/.../overrides` synchronisiert.

## Deploy

Auf dem Server bleiben lokale Inhalte erhalten. Das Deploy aktualisiert Code, synchronisiert `shared` in die lokalen Sites und baut anschliessend MkDocs.

```bash
bash scripts/deploy.sh
```
