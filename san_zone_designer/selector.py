"""Interactive and batch selection of initiator-target pairs."""

from __future__ import annotations

from .models import HBA, Configuration, NameOrder, Target, Zone, ZoneMode


def batch_select(config: Configuration) -> list[Zone]:
    """Non-interactive all×all selection (like the original bash script).

    In 'single' mode: each initiator × each target = one zone.
    In 'many' mode: each initiator × each target group = one zone.
    """
    zones: list[Zone] = []

    if config.mode == ZoneMode.single:
        for init in config.initiators:
            for tgt in config.targets:
                zone_name = Zone.build_name(
                    init.alias, tgt.alias, config.order, config.separator
                )
                zones.append(Zone(name=zone_name, initiator=init, targets=[tgt]))
    else:
        # 'many' mode — group targets
        groups = _group_targets(config.targets)
        for init in config.initiators:
            for group_name, group_targets in groups.items():
                zone_name = Zone.build_name(
                    init.alias, group_name, config.order, config.separator
                )
                zones.append(Zone(name=zone_name, initiator=init, targets=group_targets))

    return zones


def _group_targets(targets: list[Target]) -> dict[str, list[Target]]:
    """Group targets by their group name, preserving order."""
    groups: dict[str, list[Target]] = {}
    for t in targets:
        group_key = t.group if t.group else "DEFAULT"
        groups.setdefault(group_key, []).append(t)
    return groups


def select_initiators(initiators: list[HBA]) -> list[HBA]:
    """Interactive multi-select for initiators using InquirerPy."""
    from InquirerPy import inquirer
    from InquirerPy.separator import Separator

    # Group by host
    hosts: dict[str, list[HBA]] = {}
    for hba in initiators:
        key = hba.host if hba.host else "All Initiators"
        hosts.setdefault(key, []).append(hba)

    choices: list = []
    for host, hbas in hosts.items():
        choices.append(Separator(f"── {host} ──"))
        for hba in hbas:
            choices.append({"name": f"{hba.alias}  ({hba.wwpn})", "value": hba, "enabled": False})

    result = inquirer.checkbox(
        message="Select initiators:",
        choices=choices,
        instruction="(Space to select, Enter to confirm)",
    ).execute()

    return result


def select_targets_for(initiator: HBA, targets: list[Target]) -> list[Target]:
    """Interactive multi-select of targets for a given initiator."""
    from InquirerPy import inquirer
    from InquirerPy.separator import Separator

    # Group by storage_array or group
    groups: dict[str, list[Target]] = {}
    for tgt in targets:
        key = tgt.storage_array or tgt.group or "All Targets"
        groups.setdefault(key, []).append(tgt)

    choices: list = []
    for group_name, tgts in groups.items():
        choices.append(Separator(f"── {group_name} ──"))
        for tgt in tgts:
            choices.append({"name": f"{tgt.alias}  ({tgt.wwpn})", "value": tgt, "enabled": False})

    result = inquirer.checkbox(
        message=f"Select targets for {initiator.alias}:",
        choices=choices,
        instruction="(Space to select, Enter to confirm)",
    ).execute()

    return result


def interactive_select(config: Configuration) -> list[Zone]:
    """Full interactive selection flow: pick initiators, then targets per initiator."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Step 1: select initiators
    console.print("\n[bold cyan]Step 1:[/bold cyan] Select initiators\n")
    selected_inits = select_initiators(config.initiators)
    if not selected_inits:
        console.print("[red]No initiators selected. Aborting.[/red]")
        return []

    console.print(f"\n[green]Selected {len(selected_inits)} initiator(s)[/green]\n")

    zones: list[Zone] = []

    if config.mode == ZoneMode.single:
        # Step 2: for each initiator, select targets
        console.print("[bold cyan]Step 2:[/bold cyan] Select targets for each initiator\n")
        for init in selected_inits:
            console.print(f"\n[bold]{init.alias}[/bold]")
            selected_tgts = select_targets_for(init, config.targets)
            for tgt in selected_tgts:
                zone_name = Zone.build_name(
                    init.alias, tgt.alias, config.order, config.separator
                )
                zones.append(Zone(name=zone_name, initiator=init, targets=[tgt]))
    else:
        # 'many' mode — select target groups
        groups = _group_targets(config.targets)
        console.print("[bold cyan]Step 2:[/bold cyan] Select target groups for each initiator\n")

        from InquirerPy import inquirer

        for init in selected_inits:
            console.print(f"\n[bold]{init.alias}[/bold]")
            group_choices = [
                {"name": f"{gname} ({len(gtgts)} targets)", "value": gname}
                for gname, gtgts in groups.items()
            ]
            selected_groups = inquirer.checkbox(
                message=f"Select target groups for {init.alias}:",
                choices=group_choices,
                instruction="(Space to select, Enter to confirm)",
            ).execute()

            for gname in selected_groups:
                zone_name = Zone.build_name(
                    init.alias, gname, config.order, config.separator
                )
                zones.append(Zone(name=zone_name, initiator=init, targets=groups[gname]))

    # Preview
    if zones:
        console.print(f"\n[bold cyan]Preview:[/bold cyan] {len(zones)} zone(s) will be created\n")
        table = Table(title="Zones")
        table.add_column("Zone Name", style="cyan")
        table.add_column("Initiator", style="green")
        table.add_column("Target(s)", style="yellow")
        for z in zones:
            tgt_str = ", ".join(t.alias for t in z.targets)
            table.add_row(z.name, z.initiator.alias, tgt_str)
        console.print(table)

        from InquirerPy import inquirer as inq

        confirm = inq.confirm(message="Proceed with these zones?", default=True).execute()
        if not confirm:
            console.print("[red]Cancelled.[/red]")
            return []

    return zones
