"""Check that every local link and image in a static site points to a real file.

Usage: python3 check_links.py site
Exits with status 1 and lists broken links if any are found. Standard library only.
"""

import re
import sys
from pathlib import Path


def target(root, page, ref):
    # Root-relative links resolve against the site folder, the way a host serves them.
    path = root / ref.lstrip("/") if ref.startswith("/") else page.parent / ref
    return path / "index.html" if ref.endswith("/") or path.is_dir() else path


def broken_links(root):
    for page in sorted(root.rglob("*.html")):
        for ref in sorted(set(re.findall(r'(?:href|src)="([^"]+)"', page.read_text()))):
            ref = re.split(r"[?#]", ref)[0]
            if ref and ":" not in ref and not target(root, page, ref).exists():
                yield page.relative_to(root), ref


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    broken = list(broken_links(root))
    for page, ref in broken:
        print(f"{page}: broken link {ref}")
    print(f"{len(broken)} broken links in {root}/")
    sys.exit(1 if broken else 0)
