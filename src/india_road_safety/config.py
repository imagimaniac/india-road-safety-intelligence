"""Project configuration and path resolution.

Settings are *inputs and guardrails*, never conclusions. The project root is
discovered by walking up from this file until ``config/settings.yaml`` is found,
so the package works from a source checkout without installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(RuntimeError):
    """Raised when configuration is missing or malformed."""


def project_root(start: Optional[Path] = None) -> Path:
    """Locate the project root (the directory containing ``config/settings.yaml``)."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "config" / "settings.yaml").is_file():
            return candidate
    raise ConfigError("could not locate project root (config/settings.yaml not found)")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"missing configuration file: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"expected a mapping at the top level of {path}")
    return data


@dataclass(frozen=True)
class Settings:
    """Resolved settings with absolute paths."""

    root: Path
    raw: dict[str, Any]

    # -- path helpers ------------------------------------------------------ #
    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    @property
    def app(self) -> dict[str, Any]:
        return self.raw.get("app", {})

    @property
    def study(self) -> dict[str, Any]:
        return self.raw.get("study", {})

    @property
    def http(self) -> dict[str, Any]:
        return self.raw.get("http", {})

    @property
    def analysis(self) -> dict[str, Any]:
        return self.raw.get("analysis", {})

    @property
    def report(self) -> dict[str, Any]:
        return self.raw.get("report", {})

    @property
    def evidence(self) -> dict[str, Any]:
        return self.raw.get("evidence", {})

    @property
    def data_dir(self) -> Path:
        return self.path(self.app.get("data_dir", "data"))

    @property
    def raw_dir(self) -> Path:
        return self.path(self.app.get("raw_dir", "data/raw"))

    @property
    def interim_dir(self) -> Path:
        return self.path(self.app.get("interim_dir", "data/interim"))

    @property
    def processed_dir(self) -> Path:
        return self.path(self.app.get("processed_dir", "data/processed"))

    @property
    def reports_dir(self) -> Path:
        return self.path(self.app.get("reports_dir", "reports"))

    @property
    def schemas_dir(self) -> Path:
        return self.path(self.app.get("schemas_dir", "schemas"))

    @property
    def db_path(self) -> Path:
        return self.path(self.app.get("db_path", "data/interim/irsi.db"))

    @property
    def sources_path(self) -> Path:
        return self.path("config", "sources.yaml")

    @property
    def vehicles_dir(self) -> Path:
        return self.path("config", "vehicles")

    @property
    def min_sample_size(self) -> int:
        return int(self.analysis.get("min_sample_size", 30))

    @property
    def allow_cross_protocol_comparison(self) -> bool:
        return bool(self.analysis.get("allow_cross_protocol_comparison", False))


def load_settings(path: Optional[Path] = None) -> Settings:
    """Load settings from ``path`` (or the discovered project root)."""
    if path is None:
        root = project_root()
        path = root / "config" / "settings.yaml"
    else:
        path = Path(path)
        root = path.parent.parent
    return Settings(root=root, raw=_load_yaml(path))
