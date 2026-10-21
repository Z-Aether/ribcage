import tomllib
from pathlib import Path

STATIC = Path(__file__).parents[1] / "ribcage" / "static"
VENDOR = STATIC / "vendor"
MANIFEST = VENDOR / "vendored.toml"
FONT_SUFFIX = ".woff2"


def recorded_files():
    libraries = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    return {
        VENDOR / directory / name: entry["sha256"]
        for directory, library in libraries.items()
        for name, entry in library["files"].items()
    }


def vendored_assets():
    return [path.relative_to(STATIC).as_posix() for path in recorded_files() if path.name != "LICENSE"]


def vendored_files_pages_load():
    return [name for name in vendored_assets() if not name.endswith(FONT_SUFFIX)]


def vendored_fonts():
    return [name for name in vendored_assets() if name.endswith(FONT_SUFFIX)]
