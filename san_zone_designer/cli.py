"""Typer CLI for SAN Zone Designer."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .colorizer import colorize_line
from .exporters.config_writer import write_config, write_rollback
from .exporters.csv_writer import write_csv, write_rollback_csv
from .generators import BrocadeGenerator, CiscoGenerator
from .models import Configuration, NameOrder, Vendor, ZoneMode
from .parser import load_initiators, load_targets
from .selector import batch_select, interactive_select

app = typer.Typer(
    name="san-zone-designer",
    help="SAN Zone Designer — Cisco/Brocade SAN Config Generator",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"SAN Zone Designer v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(None, "--version", "-V", callback=version_callback, is_eager=True),
) -> None:
    """SAN Zone Designer — Cisco/Brocade SAN Config Generator."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def _build_config(
    initiators: str,
    targets: str,
    vsan: int,
    vsan_name: str,
    iface_range: str,
    zoneset_name: str,
    vendor: str,
    mode: str,
    order: str,
    sep: str,
    dry: bool,
    rollback: bool,
    fabric: str = "",
) -> Configuration:
    """Build Configuration from CLI parameters."""
    vendor_enum = Vendor(vendor)
    mode_enum = ZoneMode(mode)
    order_enum = NameOrder(order)

    # Separator
    separator = "__"
    if sep == "one":
        separator = "_"
    elif sep == "two":
        separator = "__"

    # Defaults
    if vendor_enum == Vendor.cisco:
        effective_vsan_name = vsan_name or f"VSAN_{vsan}"
        zoneset_sep = "_vsan_"
        effective_zoneset = zoneset_name or f"zoneset{zoneset_sep}{vsan}"
    else:
        effective_vsan_name = ""
        effective_zoneset = zoneset_name or "cfg"

    # Load data
    inits = load_initiators(initiators)
    tgts = load_targets(targets, mode=mode)

    # Filter by fabric if specified
    if fabric:
        inits = [h for h in inits if h.fabric.lower() == fabric.lower()]
        tgts = [t for t in tgts if t.fabric.lower() == fabric.lower()]
        if not inits and not tgts:
            console.print(f"[red]Error: no initiators or targets found for fabric '{fabric}'.[/red]")
            raise typer.Exit(1)

    if not inits:
        console.print("[red]Error: no valid initiators found.[/red]")
        raise typer.Exit(1)
    if not tgts:
        console.print("[red]Error: no valid targets found.[/red]")
        raise typer.Exit(1)

    return Configuration(
        vendor=vendor_enum,
        mode=mode_enum,
        order=order_enum,
        separator=separator,
        vsan=vsan,
        vsan_name=effective_vsan_name,
        iface_range=iface_range,
        zoneset_name=effective_zoneset,
        initiators=inits,
        targets=tgts,
        dry_run=dry,
        rollback=rollback,
    )


def _generate_and_output(
    config: Configuration,
    output: str,
    csv_file: str,
    plain: bool = False,
) -> None:
    """Run generator and write outputs."""
    # Select generator
    if config.vendor == Vendor.cisco:
        gen = CiscoGenerator(config)
    else:
        gen = BrocadeGenerator(config)

    result = gen.generate()

    # Summary (appended to config output)
    summary_lines = [
        "! --- PODSUMOWANIE ---",
        f"! Vendor     : {config.vendor.value}",
        f"! Tryb       : {config.mode.value}",
        f"! Inicjatory : {len(config.initiators)}",
        f"! Targety    : {len(config.targets)}",
    ]
    if config.mode == ZoneMode.many:
        groups = set(t.group for t in config.targets if t.group)
        summary_lines.append(f"! Grupy      : {len(groups)}")
    summary_lines.extend([
        f"! Zony       : {len(config.zones)}",
        f"! Zoneset    : {config.zoneset_name}",
        "! --- KONIEC PODSUMOWANIA ---",
    ])
    result += "\n" + "\n".join(summary_lines)

    # Output
    if output:
        # File output — always plain text
        write_config(result, output)
        console.print(f"[green]Config written to {output}[/green]")
    else:
        # stdout output — colorize if TTY and not --plain
        use_color = not plain and console.is_terminal
        if use_color:
            vendor_str = config.vendor.value
            for line in result.splitlines():
                console.print(colorize_line(line, vendor_str), highlight=False)
        else:
            console.print(result, highlight=False)

    # CSV
    if csv_file:
        write_csv(gen.csv_lines, csv_file)
        console.print(f"[green]CSV written to {csv_file}[/green]")

    # Rollback
    if config.rollback:
        write_rollback(gen.rollback_cfg)
        write_rollback_csv([gen.rollback_csv] if isinstance(gen.rollback_csv, str) else gen.rollback_csv)
        # Actually rollback_csv is a string with newlines, write it directly
        Path("rollback.csv").write_text(gen.rollback_csv + "\n", encoding="utf-8")
        Path("rollback.cfg").write_text(gen.rollback_cfg + "\n", encoding="utf-8")
        console.print("[green]Rollback files written: rollback.cfg, rollback.csv[/green]")


def _show_dry_run(config: Configuration) -> None:
    """Show dry-run summary."""
    console.print("\n[bold]! --- PODSUMOWANIE (dry-run) ---[/bold]")
    console.print(f"! Tryb       : {config.mode.value}")
    console.print(f"! Inicjatory : {len(config.initiators)}")
    console.print(f"! Targety    : {len(config.targets)}")
    if config.mode == ZoneMode.many:
        groups = set(t.group for t in config.targets if t.group)
        console.print(f"! Grupy      : {len(groups)}")
    console.print(f"! Vendor     : {config.vendor.value}")
    console.print(f"! Zoneset    : {config.zoneset_name}")

    # Show zones preview in a table
    if config.zones:
        table = Table(title="Zones Preview")
        table.add_column("Zone Name", style="cyan")
        table.add_column("Initiator", style="green")
        table.add_column("Target(s)", style="yellow")
        for z in config.zones:
            tgt_str = ", ".join(t.alias for t in z.targets)
            table.add_row(z.name, z.initiator.alias, tgt_str)
        console.print(table)


# Common options as defaults
_i_opt = typer.Option(..., "-i", "--initiators", help="Initiators file (txt or yaml)")
_t_opt = typer.Option(..., "-t", "--targets", help="Targets file (txt or yaml)")
_vsan_opt = typer.Option(0, "--vsan", help="VSAN number (required for Cisco)")
_vsn_opt = typer.Option("", "--vsn", help="VSAN name (default: VSAN_<number>)")
_if_opt = typer.Option("1-32", "--if", "--iface", help="FC interface range")
_zs_opt = typer.Option("", "--zs", "--zoneset", help="Zoneset/CFG base name")
_o_opt = typer.Option("", "-o", "--output", help="Output config file")
_csv_opt = typer.Option("", "--csv", help="CSV export file")
_dry_opt = typer.Option(False, "--dry", help="Dry-run mode (summary only)")
_rollback_opt = typer.Option(False, "--rollback", help="Generate rollback files")
_vendor_opt = typer.Option("cisco", "--vendor", help="Switch vendor: cisco or brocade")
_mode_opt = typer.Option("single", "--mode", help="Zone mode: single or many")
_order_opt = typer.Option("ti", "--order", help="Name order: it or ti")
_sep_opt = typer.Option("two", "--sep", "--ul", help="Separator: one (_) or two (__)")
_plain_opt = typer.Option(False, "--plain", help="Disable colored output")
_fabric_opt = typer.Option("", "--fabric", help="Filter by fabric name (e.g. Fabric_A)")


@app.command()
def init(
    initiators: str = _i_opt,
    targets: str = _t_opt,
    vsan: int = _vsan_opt,
    vsan_name: str = _vsn_opt,
    iface_range: str = _if_opt,
    zoneset_name: str = _zs_opt,
    output: str = _o_opt,
    csv_file: str = _csv_opt,
    dry: bool = _dry_opt,
    rollback: bool = _rollback_opt,
    vendor: str = _vendor_opt,
    mode: str = _mode_opt,
    order: str = _order_opt,
    sep: str = _sep_opt,
    plain: bool = _plain_opt,
    fabric: str = _fabric_opt,
) -> None:
    """Generate SAN zoning config (all×all, non-interactive — backward compat with bash)."""
    if vendor == "cisco" and vsan == 0:
        console.print("[red]Error: --vsan is required for Cisco.[/red]")
        raise typer.Exit(1)

    config = _build_config(
        initiators, targets, vsan, vsan_name, iface_range,
        zoneset_name, vendor, mode, order, sep, dry, rollback, fabric,
    )

    # Batch select (all × all)
    config.zones = batch_select(config)

    if dry:
        _show_dry_run(config)
        raise typer.Exit()

    _generate_and_output(config, output, csv_file, plain=plain)


@app.command()
def expand(
    initiators: str = _i_opt,
    targets: str = _t_opt,
    vsan: int = _vsan_opt,
    vsan_name: str = _vsn_opt,
    iface_range: str = _if_opt,
    zoneset_name: str = _zs_opt,
    output: str = _o_opt,
    csv_file: str = _csv_opt,
    dry: bool = _dry_opt,
    rollback: bool = _rollback_opt,
    vendor: str = _vendor_opt,
    mode: str = _mode_opt,
    order: str = _order_opt,
    sep: str = _sep_opt,
    batch: bool = typer.Option(False, "--batch", help="Non-interactive batch mode (all×all)"),
    plain: bool = _plain_opt,
    fabric: str = _fabric_opt,
) -> None:
    """Interactive zone expansion with multi-select (NEW).

    Default: interactive multi-select of initiator-target pairs.
    Use --batch for non-interactive all×all mode (same as init).
    """
    if vendor == "cisco" and vsan == 0:
        console.print("[red]Error: --vsan is required for Cisco.[/red]")
        raise typer.Exit(1)

    config = _build_config(
        initiators, targets, vsan, vsan_name, iface_range,
        zoneset_name, vendor, mode, order, sep, dry, rollback, fabric,
    )

    if batch:
        config.zones = batch_select(config)
    else:
        config.zones = interactive_select(config)
        if not config.zones:
            raise typer.Exit()

    if dry:
        _show_dry_run(config)
        raise typer.Exit()

    _generate_and_output(config, output, csv_file, plain=plain)


@app.command()
def migrate(
    input_file: str = typer.Option(..., "-i", "--input", help="Input txt file"),
    output_file: str = typer.Option(..., "-o", "--output", help="Output yaml file"),
    file_type: str = typer.Option("auto", "--type", help="File type: initiators, targets, or auto"),
) -> None:
    """Migrate initiators/targets from txt to yaml format."""
    from .migrator import detect_type_from_filename, migrate_initiators, migrate_targets

    # Auto-detect type from filename if needed
    effective_type = file_type
    if effective_type == "auto":
        effective_type = detect_type_from_filename(input_file)
        if effective_type == "auto":
            console.print(
                "[red]Error: cannot auto-detect file type. "
                "Use --type initiators or --type targets.[/red]"
            )
            raise typer.Exit(1)
        console.print(f"[dim]Auto-detected type: {effective_type}[/dim]")

    if effective_type == "initiators":
        count = migrate_initiators(input_file, output_file)
    else:
        count = migrate_targets(input_file, output_file)

    console.print(f"[green]Migrated {count} entries to {output_file}[/green]")


@app.command()
def diff(
    initiators: str = _i_opt,
    targets: str = _t_opt,
    existing: str = typer.Option(..., "-e", "--existing", help="Existing zone config file (show zoneset output)"),
    vsan: int = _vsan_opt,
    vsan_name: str = _vsn_opt,
    iface_range: str = _if_opt,
    zoneset_name: str = _zs_opt,
    vendor: str = _vendor_opt,
    mode: str = _mode_opt,
    order: str = _order_opt,
    sep: str = _sep_opt,
    fabric: str = _fabric_opt,
) -> None:
    """Compare generated zones against existing zone config."""
    from .differ import compute_diff
    from .importer import import_zones

    config = _build_config(
        initiators, targets, vsan, vsan_name, iface_range,
        zoneset_name, vendor, mode, order, sep, dry=False, rollback=False, fabric=fabric,
    )

    # Generate new zones
    config.zones = batch_select(config)
    new_zones = config.zones

    # Import existing zones
    existing_zones = import_zones(existing, vendor)

    # Compute diff
    result = compute_diff(existing_zones, new_zones)

    # Display diff table
    table = Table(title="Zone Diff")
    table.add_column("Status", style="bold", width=10)
    table.add_column("Zone Name")
    table.add_column("Members")

    for z in result.added:
        members = f"{z.initiator.alias} → {', '.join(t.alias for t in z.targets)}"
        table.add_row("[green]+ ADD[/green]", z.name, members)

    for z in result.removed:
        members = f"{z.initiator.alias} → {', '.join(t.alias for t in z.targets)}"
        table.add_row("[red]- REMOVE[/red]", z.name, members)

    for z in result.unchanged:
        members = f"{z.initiator.alias} → {', '.join(t.alias for t in z.targets)}"
        table.add_row("[dim]= UNCHANGED[/dim]", z.name, members)

    for old_z, new_z in result.modified:
        old_members = f"{old_z.initiator.alias} → {', '.join(t.alias for t in old_z.targets)}"
        new_members = f"{new_z.initiator.alias} → {', '.join(t.alias for t in new_z.targets)}"
        table.add_row("[yellow]~ MODIFIED[/yellow]", new_z.name, f"OLD: {old_members}\nNEW: {new_members}")

    console.print(table)

    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Added     : [green]{len(result.added)}[/green]")
    console.print(f"  Removed   : [red]{len(result.removed)}[/red]")
    console.print(f"  Unchanged : [dim]{len(result.unchanged)}[/dim]")
    console.print(f"  Modified  : [yellow]{len(result.modified)}[/yellow]")


@app.command()
def license(
    key: str = typer.Argument(..., help="Klucz licencyjny (string)"),
) -> None:
    """Dodaj i zweryfikuj klucz licencyjny z poziomu CLI."""
    import yaml
    from rich.panel import Panel
    
    try:
        from .license_check import verify_and_decode, LicenseError
    except ImportError:
        console.print("[red]Błąd: Moduł weryfikacji licencji nie jest dostępny.[/red]")
        raise typer.Exit(1)

    database_dir = Path("database")
    config_file = database_dir / "configuration.yaml"
    public_key_file = Path("san_zone_designer/license_public.pem")

    database_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not public_key_file.exists():
            console.print("[red]Błąd konfiguracji: Brak klucza publicznego (license_public.pem).[/red]")
            raise typer.Exit(1)
            
        with open(public_key_file, "rb") as f:
            public_pem = f.read()

        info = verify_and_decode(key, public_pem)
    except LicenseError as e:
        console.print(f"[red]Nieprawidłowa licencja:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Błąd weryfikacji:[/red] {e}")
        raise typer.Exit(1)

    try:
        config: Dict[str, Any] = {}
        if config_file.exists():
            with open(config_file, "r") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config.update(loaded)
        
        config["license_key"] = key
        
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
            
        console.print("[green]✓ Klucz licencyjny został poprawnie zweryfikowany i zapisany.[/green]")
        
        details = (
            f"[bold]Odbiorca:[/bold] {info.get('company', 'Brak danych')}\n"
            f"[bold]Ważna do:[/bold] {info.get('expires', 'Brak danych')}\n"
            f"[bold]Liczba stanowisk:[/bold] {info.get('seats', 'n/a')}\n"
            f"[bold]Liczba switchy:[/bold] {info.get('switches', 'n/a')}"
        )
        console.print(Panel(details, title="Szczegóły Licencji", border_style="green", expand=False))
        
    except Exception as e:
        console.print(f"[red]Błąd podczas zapisywania licencji do pliku konfiguracyjnego:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def web(
    port: int = typer.Option(8000, help="Port serwera"),
    host: str = typer.Option("0.0.0.0", help="Host"),
    ssl_certfile: Optional[str] = typer.Option(None, "--ssl-cert", help="Sciezka do certyfikatu SSL (PEM)"),
    ssl_keyfile: Optional[str] = typer.Option(None, "--ssl-key", help="Sciezka do klucza prywatnego SSL (PEM)"),
    ssl_keyfile_password: Optional[str] = typer.Option(None, "--ssl-key-password", help="Haslo do klucza prywatnego SSL"),
    ssl_self_signed: bool = typer.Option(False, "--ssl-self-signed", help="Wygeneruj tymczasowy self-signed certyfikat"),
) -> None:
    """Uruchom interfejs webowy (HTTP lub HTTPS).

    Przyklady:

      # HTTP (domyslnie):
      san-zone-designer web

      # HTTPS z wlasnym certyfikatem:
      san-zone-designer web --ssl-cert cert.pem --ssl-key key.pem

      # HTTPS z automatycznym self-signed certyfikatem (dev/test):
      san-zone-designer web --ssl-self-signed

      # Zmiana portu i hosta:
      san-zone-designer web --port 8443 --host 127.0.0.1 --ssl-self-signed
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error: web dependencies not installed. Run: pip install san-zone-designer[web][/red]")
        raise typer.Exit(1)

    from .web.app import app as web_app

    ssl_kwargs: dict[str, Any] = {}

    if ssl_self_signed:
        if ssl_certfile or ssl_keyfile:
            console.print("[red]Error: --ssl-self-signed cannot be used with --ssl-cert / --ssl-key[/red]")
            raise typer.Exit(1)
        cert_path, key_path = _generate_self_signed_cert()
        ssl_kwargs["ssl_certfile"] = cert_path
        ssl_kwargs["ssl_keyfile"] = key_path
    elif ssl_certfile or ssl_keyfile:
        if not ssl_certfile or not ssl_keyfile:
            console.print("[red]Error: both --ssl-cert and --ssl-key are required for HTTPS[/red]")
            raise typer.Exit(1)
        if not Path(ssl_certfile).exists():
            console.print(f"[red]Error: certificate file not found: {ssl_certfile}[/red]")
            raise typer.Exit(1)
        if not Path(ssl_keyfile).exists():
            console.print(f"[red]Error: key file not found: {ssl_keyfile}[/red]")
            raise typer.Exit(1)
        ssl_kwargs["ssl_certfile"] = ssl_certfile
        ssl_kwargs["ssl_keyfile"] = ssl_keyfile
        if ssl_keyfile_password:
            ssl_kwargs["ssl_keyfile_password"] = ssl_keyfile_password

    scheme = "https" if ssl_kwargs else "http"
    console.print(f"[bold green]SAN Zone Designer Web[/bold green] — {scheme}://{host}:{port}")
    if ssl_kwargs:
        console.print(f"[dim]  SSL cert: {ssl_kwargs.get('ssl_certfile')}[/dim]")
        console.print(f"[dim]  SSL key:  {ssl_kwargs.get('ssl_keyfile')}[/dim]")

    uvicorn.run(web_app, host=host, port=port, **ssl_kwargs)


def _generate_self_signed_cert() -> tuple[str, str]:
    """Generate a temporary self-signed certificate for development use."""
    import datetime
    import tempfile

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        console.print("[red]Error: 'cryptography' package required for --ssl-self-signed.[/red]")
        console.print("[dim]Install with: pip install cryptography[/dim]")
        raise typer.Exit(1)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "SAN Zone Designer (self-signed)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAN Zone Designer"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                x509.IPAddress(ipaddress.ip_address("0.0.0.0")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    tmp_dir = tempfile.mkdtemp(prefix="szd_ssl_")
    cert_path = str(Path(tmp_dir) / "cert.pem")
    key_path = str(Path(tmp_dir) / "key.pem")

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    console.print(f"[yellow]Self-signed certificate generated (valid 365 days)[/yellow]")
    console.print(f"[yellow]Browsers will show a security warning — this is expected for dev/test.[/yellow]")

    return cert_path, key_path


def main() -> None:
    """Entry point."""
    app()
