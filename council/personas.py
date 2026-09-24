"""Load persona worldview files from council/personas/*.md.

Each file is a short, neutral worldview. Name = the first "# " heading in
the file, falling back to the filename stem. Task 5 (prompts.py) is
responsible for stripping persona/provider names out of what the judge
sees; this module only loads and selects personas.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_PERSONAS_DIR = Path(__file__).resolve().parent / "personas"
DEFAULT_PAIR = ("bull", "bear")


class PersonaError(Exception):
    """Raised for a bad --pair argument or an unloadable persona file."""


class Persona:
    __slots__ = ("key", "name", "body")

    def __init__(self, key: str, name: str, body: str):
        self.key = key
        self.name = name
        self.body = body

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"Persona(key={self.key!r}, name={self.name!r})"


def _parse_persona_file(path: Path) -> Persona:
    text = path.read_text()
    name = path.stem
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip()
            break
    return Persona(key=path.stem.lower(), name=name, body=text.strip())


def load_all(directory: Optional[Path] = None) -> Dict[str, Persona]:
    """Load every *.md file in `directory` (default: council/personas/) keyed
    by lowercased filename stem."""
    directory = directory or DEFAULT_PERSONAS_DIR
    personas: Dict[str, Persona] = {}
    for path in sorted(directory.glob("*.md")):
        persona = _parse_persona_file(path)
        if persona.key in personas:
            raise PersonaError(f"duplicate persona key: {persona.key}")
        personas[persona.key] = persona
    return personas


def parse_pair(pair_arg: Optional[str], directory: Optional[Path] = None) -> List[Persona]:
    """Resolve a --pair "name,name" argument (or None for the default
    bull/bear pair) into a list of two Persona objects. Order is the order
    given (or DEFAULT_PAIR order when pair_arg is None)."""
    all_personas = load_all(directory)

    if pair_arg is None:
        keys = list(DEFAULT_PAIR)
    else:
        keys = [k.strip().lower() for k in pair_arg.split(",")]

    if len(keys) != 2:
        raise PersonaError(f"--pair needs exactly two names, got {len(keys)}: {pair_arg!r}")
    if keys[0] == keys[1]:
        raise PersonaError(f"--pair names must be different, got {pair_arg!r}")

    result = []
    for key in keys:
        if key not in all_personas:
            available = ", ".join(sorted(all_personas)) or "(none found)"
            raise PersonaError(f"unknown persona {key!r}; available: {available}")
        result.append(all_personas[key])
    return result
