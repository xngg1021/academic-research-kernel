"""Installed deterministic academic research kernel."""
try:
    from ._version import __version__
except ImportError:
    from pathlib import Path as _Path
    _ns: dict = {}
    exec((_Path(__file__).resolve().parents[2] / "scripts" / "_version.py").read_text(encoding="utf-8"), _ns)
    __version__ = _ns["__version__"]
