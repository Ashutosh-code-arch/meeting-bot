import click, subprocess
from .db import get_conn, list_meetings
from .config import REPORT_DIR


@click.group()
def cli():
    pass


@cli.command()
def ls():
    """List all meetings."""
    rows = list_meetings(get_conn())
    if not rows:
        click.echo("No meetings yet.")
        return
    click.echo(f"\n{'ID':>4}  {'TITLE':<30} {'DATE':<12} {'STATUS'}")
    for m in rows:
        click.echo(
            f"{m['id']:>4}  {(m['title'] or 'Untitled'):<30} "
            f"{(m['started_at'] or '')[:10]:<12} {m['status']}"
        )


@cli.command()
@click.argument("meeting_id", type=int)
def open_report(meeting_id: int):
    """Open HTML report for MEETING_ID."""
    reports = sorted(REPORT_DIR.glob(f"mtg{meeting_id:04d}_*.html"))
    if not reports:
        click.echo(f"No report for meeting {meeting_id}")
        return
    subprocess.run(["open", str(reports[-1])])


@cli.command()
def open_dir():
    """Open reports folder in Finder."""
    subprocess.run(["open", str(REPORT_DIR)])


if __name__ == "__main__":
    cli()
