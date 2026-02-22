"""Abstract base class for config generators."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Configuration


class AbstractGenerator(ABC):
    """Base class for SAN config generators."""

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self._lines: list[str] = []
        self._rollback_cfg: list[str] = []
        self._rollback_csv: list[str] = []

    def _emit(self, line: str = "") -> None:
        self._lines.append(line)

    @abstractmethod
    def generate_aliases(self) -> None:
        """Generate alias/device-alias configuration."""

    @abstractmethod
    def generate_zones(self) -> None:
        """Generate zone configuration."""

    @abstractmethod
    def generate_zoneset(self) -> None:
        """Generate zoneset/cfg configuration."""

    @abstractmethod
    def generate_rollback(self) -> None:
        """Generate rollback commands (called during generation if rollback enabled)."""

    def generate(self) -> str:
        """Run full generation pipeline and return config as string."""
        self._lines = []
        self._rollback_cfg = ["! Rollback config"]
        self._rollback_csv = ["Type;Name;VSAN"]
        self.generate_aliases()
        self.generate_zones()
        self.generate_zoneset()
        return "\n".join(self._lines)

    @property
    def rollback_cfg(self) -> str:
        return "\n".join(self._rollback_cfg)

    @property
    def rollback_csv(self) -> str:
        return "\n".join(self._rollback_csv)

    @property
    def csv_lines(self) -> list[str]:
        """Override in subclass to collect CSV data lines."""
        return []
