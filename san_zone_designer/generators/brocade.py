"""Brocade FOS config generator — mirrors zonedesigner.sh lines 601-708."""

from __future__ import annotations

from ..models import Configuration, ZoneMode
from .base import AbstractGenerator


class BrocadeGenerator(AbstractGenerator):
    """Generate Brocade FOS zoning configuration."""

    def __init__(self, config: Configuration) -> None:
        super().__init__(config)
        self._csv_data: list[str] = []

    def generate_aliases(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        self._emit("")
        self._emit("! --- KONFIGURACJA ALIASÓW ---")
        self._emit("")

        for init in cfg.initiators:
            self._emit(f'alicreate "{init.alias}","{init.wwpn}"')
            if cfg.rollback:
                self._rollback_cfg.append(f'alidelete "{init.alias}"')
                self._rollback_csv.append(f"device-alias;{init.alias};{vsan}")

        if cfg.mode == ZoneMode.single:
            for tgt in cfg.targets:
                self._emit(f'alicreate "{tgt.alias}","{tgt.wwpn}"')
                if cfg.rollback:
                    self._rollback_cfg.append(f'alidelete "{tgt.alias}"')
                    self._rollback_csv.append(f"device-alias;{tgt.alias};{vsan}")
        else:
            seen: set[str] = set()
            for zone in cfg.zones:
                for tgt in zone.targets:
                    if tgt.alias not in seen:
                        seen.add(tgt.alias)
                        self._emit(f'alicreate "{tgt.alias}","{tgt.wwpn}"')
                        if cfg.rollback:
                            self._rollback_cfg.append(f'alidelete "{tgt.alias}"')
                            self._rollback_csv.append(f"device-alias;{tgt.alias};{vsan}")

    def generate_zones(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        self._emit("")
        self._emit("! --- KONFIGURACJA ZON ---")
        self._emit("")

        if cfg.mode == ZoneMode.single:
            for zone in cfg.zones:
                tgt = zone.targets[0]
                members = f"{zone.initiator.alias};{tgt.alias}"
                self._emit(f'zonecreate "{zone.name}","{members}"')
                if cfg.rollback:
                    self._rollback_cfg.append(f'zonedelete "{zone.name}"')
                    self._rollback_csv.append(f"zone;{zone.name};{vsan}")
                self._csv_data.append(
                    f"{zone.name};{zone.initiator.alias};{zone.initiator.wwpn};{tgt.alias};{tgt.wwpn};{vsan}"
                )
        else:
            for zone in cfg.zones:
                members = zone.initiator.alias
                for tgt in zone.targets:
                    members += f";{tgt.alias}"
                self._emit(f'zonecreate "{zone.name}","{members}"')
                if cfg.rollback:
                    self._rollback_cfg.append(f'zonedelete "{zone.name}"')
                    self._rollback_csv.append(f"zone;{zone.name};{vsan}")
                for tgt in zone.targets:
                    self._csv_data.append(
                        f"{zone.name};{zone.initiator.alias};{zone.initiator.wwpn};{tgt.alias};{tgt.wwpn};{vsan}"
                    )

    def generate_zoneset(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        self._emit("")
        self._emit("! --- KONFIGURACJA CFG ---")
        self._emit("")
        zone_list = ";".join(z.name for z in cfg.zones)
        self._emit(f'cfgcreate "{cfg.zoneset_name}","{zone_list}"')
        self._emit(f'cfgadd "{cfg.zoneset_name}","{zone_list}"')

        if cfg.rollback:
            self._rollback_cfg.append(f'cfgdelete "{cfg.zoneset_name}"')
            self._rollback_csv.append(f"zoneset;{cfg.zoneset_name};{vsan}")

        self._emit("")
        self._emit("! --- AKTYWACJA I ZAPIS ---")
        self._emit("")
        self._emit(f"cfgenable {cfg.zoneset_name}")
        self._emit("cfgsave")
        self._emit("")

        if cfg.rollback:
            self._rollback_cfg.append(f"cfgdisable {cfg.zoneset_name}")
            self._rollback_cfg.append("cfgsave")

    def generate_rollback(self) -> None:
        pass

    @property
    def csv_lines(self) -> list[str]:
        return self._csv_data
