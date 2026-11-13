"""Write the static profile visuals (header, project banners, repo chips) to assets/ and the README's Projects.

Run from the repository root after changing anything under visuals/: uv run python -m visuals
The downloads card is separate and weekly: uv run python -m downloads
"""

from __future__ import annotations

from pathlib import Path

from visuals import THEMES
from visuals.header import VARIANTS as HEADER_VARIANTS
from visuals.header import render_header
from visuals.projects import GROUPS, render_banner, render_chip
from visuals.readme import update
from visuals.projects import VARIANTS as BANNER_VARIANTS

ROOT = Path(__file__).resolve().parent.parent


def main(root: Path = ROOT) -> None:
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    written = []
    for theme in THEMES:
        for suffix, width in HEADER_VARIANTS.items():
            written.append(assets / f"header{suffix}-{theme}.svg")
            written[-1].write_text(render_header(theme, width), encoding="utf-8")
        for group in GROUPS:
            for suffix, width in BANNER_VARIANTS.items():
                written.append(assets / f"project-{group.key}{suffix}-{theme}.svg")
                written[-1].write_text(render_banner(group, theme, width), encoding="utf-8")
            for repo in group.repos:
                written.append(assets / f"repo-{repo.key}-{theme}.svg")
                written[-1].write_text(render_chip(group, repo, theme), encoding="utf-8")
    update(root / "README.md")
    for path in written:
        print(f"{path.relative_to(root).as_posix():<44} {path.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
