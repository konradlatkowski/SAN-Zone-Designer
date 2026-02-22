"""Cisco MDS NX-OS config generator — mirrors zonedesigner.sh lines 471-599."""

from __future__ import annotations

from ..models import Configuration, ZoneMode
from .base import AbstractGenerator


class CiscoGenerator(AbstractGenerator):
    """Generate Cisco MDS NX-OS zoning configuration."""

    def __init__(self, config: Configuration) -> None:
        super().__init__(config)
        self._csv_data: list[str] = []

    def generate_aliases(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        # VSAN config
        self._emit("")
        self._emit("! --- KONFIGURACJA VSAN ---")
        self._emit("")
        self._emit("config t")
        self._emit("vsan database")
        self._emit(f"  vsan {vsan}")
        self._emit(f"  vsan {vsan} name {cfg.vsan_name}")
        self._emit(f"  vsan {vsan} interface fc1/{cfg.iface_range}")
        self._emit("exit")
        self._emit("")
        self._emit(f"interface fc1/{cfg.iface_range}")
        self._emit("  no shutdown")
        self._emit("exit")
        self._emit("")

        # Device-alias
        self._emit("")
        self._emit("! --- KONFIGURACJA DEVICE-ALIAS ---")
        self._emit("")
        self._emit("device-alias database")

        for init in cfg.initiators:
            self._emit(f"  device-alias name {init.alias} pwwn {init.wwpn}")
            if cfg.rollback:
                self._rollback_cfg.append(f"no device-alias name {init.alias}")
                self._rollback_csv.append(f"device-alias;{init.alias};{vsan}")

        if cfg.mode == ZoneMode.single:
            for tgt in cfg.targets:
                self._emit(f"  device-alias name {tgt.alias} pwwn {tgt.wwpn}")
                if cfg.rollback:
                    self._rollback_cfg.append(f"no device-alias name {tgt.alias}")
                    self._rollback_csv.append(f"device-alias;{tgt.alias};{vsan}")
        else:
            # 'many' mode — all targets from all groups
            seen: set[str] = set()
            for zone in cfg.zones:
                for tgt in zone.targets:
                    if tgt.alias not in seen:
                        seen.add(tgt.alias)
                        self._emit(f"  device-alias name {tgt.alias} pwwn {tgt.wwpn}")
                        if cfg.rollback:
                            self._rollback_cfg.append(f"  no device-alias name {tgt.alias}")
                            self._rollback_csv.append(f"device-alias;{tgt.alias};{vsan}")

        self._emit("exit")
        self._emit("device-alias commit")
        self._emit("")

    def generate_zones(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        self._emit("")
        self._emit("! --- KONFIGURACJA ZONING ---")
        self._emit("")

        if cfg.mode == ZoneMode.single:
            for zone in cfg.zones:
                tgt = zone.targets[0]
                self._emit(f"zone name {zone.name} vsan {vsan}")
                self._emit(f"  member device-alias {zone.initiator.alias}")
                self._emit(f"  member device-alias {tgt.alias}")
                self._emit("exit")
                self._emit("")
                if cfg.rollback:
                    self._rollback_cfg.append(f"no zone name {zone.name} vsan {vsan}")
                    self._rollback_csv.append(f"zone;{zone.name};{vsan}")
                self._csv_data.append(
                    f"{zone.name};{zone.initiator.alias};{zone.initiator.wwpn};{tgt.alias};{tgt.wwpn};{vsan}"
                )
        else:
            for zone in cfg.zones:
                self._emit(f"zone name {zone.name} vsan {vsan}")
                self._emit(f"  member device-alias {zone.initiator.alias}")
                for tgt in zone.targets:
                    self._emit(f"  member device-alias {tgt.alias}")
                    self._csv_data.append(
                        f"{zone.name};{zone.initiator.alias};{zone.initiator.wwpn};{tgt.alias};{tgt.wwpn};{vsan}"
                    )
                self._emit("exit")
                self._emit("")
                if cfg.rollback:
                    self._rollback_cfg.append(f"no zone name {zone.name} vsan {vsan}")
                    self._rollback_csv.append(f"zone;{zone.name};{vsan}")

    def generate_zoneset(self) -> None:
        cfg = self.config
        vsan = cfg.vsan

        self._emit("")
        self._emit("! --- KONFIGURACJA ZONESET ---")
        self._emit("")
        self._emit(f"zoneset name {cfg.zoneset_name} vsan {vsan}")
        for zone in cfg.zones:
            self._emit(f"  member {zone.name}")
        self._emit("exit")
        self._emit("")

        if cfg.rollback:
            self._rollback_cfg.append(f"no zoneset name {cfg.zoneset_name} vsan {vsan}")
            self._rollback_csv.append(f"zoneset;{cfg.zoneset_name};{vsan}")

        self._emit("")
        self._emit("! --- AKTYWACJA I ZAPIS ---")
        self._emit("")
        self._emit(f"zoneset activate name {cfg.zoneset_name} vsan {vsan}")
        self._emit("copy running-config startup-config")
        self._emit("")

    def generate_rollback(self) -> None:
        # Rollback is collected during alias/zone/zoneset generation
        pass

    @property
    def csv_lines(self) -> list[str]:
        return self._csv_data
