"""Source registry.

The registry is the provenance root: **no metric may trace to a source that is
not registered here**, and collection is blocked unless a source's ``status`` is
``verified``. This keeps three distinct questions separate, per AGENTS.md:

* *identity* — what the source is;
* *collection authorisation* — may we fetch it, and how;
* *redistribution* — may we republish the material.

A source can be collectable without being redistributable (we then cite only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from .config import Settings, load_settings
from .models import Source, SourceStatus


class RegistryError(RuntimeError):
    """Raised when the registry is missing, malformed, or misused."""


class SourceNotVerified(RegistryError):
    """Raised when collection is attempted on a non-verified source."""


class Registry:
    """An immutable, validated view over ``config/sources.yaml``."""

    def __init__(self, sources: dict[str, Source], version: int = 1):
        self._sources = dict(sources)
        self.version = version

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Registry":
        if not isinstance(data, dict):
            raise RegistryError("registry must be a mapping")
        version = int(data.get("version", 1))
        raw_sources = data.get("sources")
        if not isinstance(raw_sources, list):
            raise RegistryError("registry 'sources' must be a list")
        sources: dict[str, Source] = {}
        for entry in raw_sources:
            if not isinstance(entry, dict):
                raise RegistryError("each source entry must be a mapping")
            normalised = dict(entry)
            if "slug" not in normalised and "id" in normalised:
                normalised["slug"] = normalised.pop("id")
            try:
                source = Source(**normalised)
            except ValidationError as exc:
                raise RegistryError(
                    f"invalid source entry {entry.get('id') or entry.get('slug')!r}: {exc}"
                ) from exc
            if source.slug in sources:
                raise RegistryError(f"duplicate source slug: {source.slug!r}")
            sources[source.slug] = source
        return cls(sources, version)

    @classmethod
    def from_yaml(cls, text: str) -> "Registry":
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise RegistryError(f"invalid registry YAML: {exc}") from exc
        return cls.from_mapping(data)

    @classmethod
    def load(cls, path: Optional[Path] = None, settings: Optional[Settings] = None) -> "Registry":
        if path is None:
            settings = settings or load_settings()
            path = settings.sources_path
        path = Path(path)
        if not path.is_file():
            raise RegistryError(f"registry file not found: {path}")
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    # -- access ------------------------------------------------------------ #
    def __contains__(self, slug: object) -> bool:
        return slug in self._sources

    def __len__(self) -> int:
        return len(self._sources)

    def get(self, slug: str) -> Source:
        try:
            return self._sources[slug]
        except KeyError as exc:
            raise RegistryError(f"unknown source: {slug!r}") from exc

    def all(self) -> list[Source]:
        return list(self._sources.values())

    def slugs(self) -> list[str]:
        return list(self._sources)

    def verified(self) -> list[Source]:
        return [s for s in self._sources.values() if s.status == SourceStatus.VERIFIED.value]

    def by_status(self, status: SourceStatus) -> list[Source]:
        return [s for s in self._sources.values() if s.status == status.value]

    def require_verified(self, slug: str) -> Source:
        """Return a source, or raise if it is not cleared for collection."""
        source = self.get(slug)
        if not source.is_usable:
            raise SourceNotVerified(
                f"source {slug!r} is {source.status!r}; collection is blocked until verified"
            )
        return source
