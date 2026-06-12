"""Regenerate backend/app/_frontend.py from public/index.html.
Run from the repo root after any frontend edit:  python scripts/embed_frontend.py
"""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "public" / "index.html").read_bytes()
b64 = base64.b64encode(html).decode()
lines = [b64[i:i+100] for i in range(0, len(b64), 100)]
body = "\n".join(f'    "{l}"' for l in lines)
src = (
    '"""\nEmbedded dashboard (auto-generated from public/index.html — regenerate with\n'
    'scripts/embed_frontend.py after editing the HTML).\n\n'
    "Why this exists: serverless bundlers (e.g. Vercel's FastAPI preset) trace\n"
    'Python imports and drop plain static files. Importing the dashboard as a\n'
    'module guarantees it ships everywhere the app does. Local/Render deployments\n'
    'still serve public/index.html directly; this is the fallback.\n"""\n'
    'import base64\n\n_B64 = (\n' + body + '\n)\n\nHTML = base64.b64decode(_B64).decode("utf-8")\n'
)
(ROOT / "backend" / "app" / "_frontend.py").write_text(src)
print(f"embedded {len(html)} bytes -> backend/app/_frontend.py")
