"""Download frontend vendor assets for offline use."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "static" / "vendor"
CODEMIRROR_VERSION = "5.65.16"
CDN = f"https://cdnjs.cloudflare.com/ajax/libs/codemirror/{CODEMIRROR_VERSION}"

CODEMIRROR_FILES = [
    "codemirror.min.css",
    "codemirror.min.js",
    "theme/dracula.min.css",
    "mode/sql/sql.min.js",
    "addon/hint/show-hint.min.css",
    "addon/hint/show-hint.min.js",
    "addon/hint/sql-hint.min.js",
]

FONT_FILES = {
    "dm-sans-latin-400-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/dm-sans@5.2.5/files/dm-sans-latin-400-normal.woff2",
    "dm-sans-latin-500-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/dm-sans@5.2.5/files/dm-sans-latin-500-normal.woff2",
    "dm-sans-latin-600-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/dm-sans@5.2.5/files/dm-sans-latin-600-normal.woff2",
    "dm-sans-latin-700-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/dm-sans@5.2.5/files/dm-sans-latin-700-normal.woff2",
    "jetbrains-mono-latin-400-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.2.5/files/jetbrains-mono-latin-400-normal.woff2",
    "jetbrains-mono-latin-500-normal.woff2": "https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.2.5/files/jetbrains-mono-latin-500-normal.woff2",
}

FONTS_CSS = """/* Bundled for offline use */
@font-face {
  font-family: "DM Sans";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("./dm-sans-latin-400-normal.woff2") format("woff2");
}

@font-face {
  font-family: "DM Sans";
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url("./dm-sans-latin-500-normal.woff2") format("woff2");
}

@font-face {
  font-family: "DM Sans";
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url("./dm-sans-latin-600-normal.woff2") format("woff2");
}

@font-face {
  font-family: "DM Sans";
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url("./dm-sans-latin-700-normal.woff2") format("woff2");
}

@font-face {
  font-family: "JetBrains Mono";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("./jetbrains-mono-latin-400-normal.woff2") format("woff2");
}

@font-face {
  font-family: "JetBrains Mono";
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url("./jetbrains-mono-latin-500-normal.woff2") format("woff2");
}
"""


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {dest.relative_to(ROOT)}")
    urllib.request.urlretrieve(url, dest)


def main() -> None:
    for rel in CODEMIRROR_FILES:
        download(f"{CDN}/{rel}", VENDOR / "codemirror" / rel)

    fonts_dir = VENDOR / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in FONT_FILES.items():
        download(url, fonts_dir / filename)
    (fonts_dir / "fonts.css").write_text(FONTS_CSS, encoding="utf-8")

    print("Vendor assets downloaded.")


if __name__ == "__main__":
    main()
