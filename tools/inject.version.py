import json
from pathlib import Path


version_file = Path('version.json')
site_dir = Path('site')
footer_snippet = '"<div class=\"md-footer\"><div class=\"md-footer-meta\">{}</div></div>"'


if version_file.exists():
    data = json.loads(version_file.read_text(encoding='utf-8'))
    text = f"Version {data['current_version']} – {data['build_date']}"
    # Optional: Dateien anpassen oder in custom.css/Theme einblenden
    # Hier nur Platzhalter: tatsächliche Footer‑Manipulation hängt vom Theme ab.
    print(text)