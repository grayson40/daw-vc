import click
import json
from pathlib import Path
from rich.console import Console
from src.vc.engine import DawVC
from src.fl_studio.diff.compare import compare

console = Console()


def _render_diff(diff: dict) -> None:
    """Render a structured diff dict to the terminal using rich."""
    if diff.get("metadata"):
        console.print("[bold yellow]Metadata changes:[/bold yellow]")
        for field, change in diff["metadata"].items():
            console.print(f"  {field}: [red]{change['old']}[/red] -> [green]{change['new']}[/green]")

    for section in ("channels", "patterns", "mixer", "plugins", "playlist"):
        section_diff = diff.get(section, {})
        if not isinstance(section_diff, dict):
            continue
        added = section_diff.get("added", [])
        removed = section_diff.get("removed", [])
        modified = section_diff.get("modified", [])
        if not (added or removed or modified):
            continue
        console.print(f"\n[bold cyan]{section.capitalize()}:[/bold cyan]")
        for item in added:
            name = item.get("name") or item.get("channel_name", "?")
            console.print(f"  [green]+ {name}[/green]")
        for item in removed:
            name = item.get("name") or item.get("channel_name", "?")
            console.print(f"  [red]- {name}[/red]")
        for item in modified:
            console.print(f"  [yellow]~ {item['name']}[/yellow]")
            for field, change in item["changes"].items():
                console.print(f"    {field}: [red]{change['old']}[/red] -> [green]{change['new']}[/green]")


@click.group()
def cli():
    """DAW Version Control CLI"""


@cli.command()
def init():
    """Initialize a new DAW VC repository."""
    vc = DawVC(Path.cwd())
    vc.init()
    console.print("[green]Initialized DAW repository in .daw/[/green]")


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def add(project):
    """Stage an FL Studio project file."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    vc.add(Path(project))
    console.print(f"[green]Staged {project}[/green]")


@cli.command()
@click.argument('message')
def commit(message):
    """Commit staged changes."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        commit_hash = vc.commit(message)
    except ValueError as e:
        raise click.ClickException(str(e))
    console.print(f"[green]Committed {commit_hash}: {message}[/green]")


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def status(project):
    """Show changes between working file and HEAD commit."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = json.loads(vc.commits_file.read_text())
    if not commits:
        console.print("No commits yet. Run 'daw add' and 'daw commit' first.")
        return

    last_commit = commits[-1]
    head_hash = last_commit["hash"]
    head_flp = vc.objects_dir / f"{head_hash}.flp"

    if not head_flp.exists():
        raise click.ClickException(f"HEAD snapshot not found: {head_flp}")

    from src.fl_studio.parser.base import FLParser
    old_state = FLParser(head_flp).get_state()
    new_state = FLParser(Path(project)).get_state()
    diff_result = compare(old_state, new_state)

    has_changes = (
        diff_result["metadata"]
        or any(diff_result[s].get("added") or diff_result[s].get("removed") or diff_result[s].get("modified")
               for s in ("channels", "patterns", "mixer", "plugins", "playlist"))
    )
    if not has_changes:
        console.print("Nothing changed since last commit.")
    else:
        _render_diff(diff_result)


@cli.command()
@click.argument('hash1', required=False)
@click.argument('hash2', required=False)
def diff(hash1, hash2):
    """Show diff between two commits (default: HEAD~1 vs HEAD)."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = json.loads(vc.commits_file.read_text())
    if len(commits) < 2:
        console.print("Need at least 2 commits to diff.")
        return

    if hash1 is None and hash2 is None:
        h1, h2 = commits[-2]["hash"], commits[-1]["hash"]
    elif hash2 is None:
        raise click.ClickException("Provide both hash1 and hash2, or neither.")
    else:
        h1, h2 = hash1, hash2

    flp1 = vc.objects_dir / f"{h1}.flp"
    flp2 = vc.objects_dir / f"{h2}.flp"

    for p in (flp1, flp2):
        if not p.exists():
            raise click.ClickException(f"Snapshot not found: {p}")

    from src.fl_studio.parser.base import FLParser
    old_state = FLParser(flp1).get_state()
    new_state = FLParser(flp2).get_state()
    diff_result = compare(old_state, new_state)
    _render_diff(diff_result)


@cli.command()
def log():
    """Show commit history."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")

    commits = vc.get_commits()
    if not commits:
        console.print("No commits yet.")
        return

    state = json.loads(vc.state_file.read_text())
    current_branch = state["branch"]

    for commit in reversed(commits):
        branch_tag = f" [bold green]({current_branch})[/bold green]" if commit["hash"] == state["head"] else ""
        console.print(f"[yellow]{commit['hash']}[/yellow]{branch_tag} {commit['message']}")
        console.print(f"  [dim]{commit['timestamp']} on {commit['branch']}[/dim]")


@cli.command()
@click.argument('name')
def branch(name):
    """Create a new branch at current HEAD."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        vc.create_branch(name)
        console.print(f"[green]Created branch '{name}'[/green]")
    except ValueError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument('ref')
def checkout(ref):
    """Switch to a branch or restore a commit snapshot."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        vc.checkout(ref)
        console.print(f"[green]Switched to '{ref}'[/green]")
    except ValueError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument('branch_name')
def merge(branch_name):
    """Merge a branch into the current branch."""
    vc = DawVC(Path.cwd())
    if not vc.daw_dir.exists():
        raise click.ClickException("Not a daw repository. Run 'daw init' first.")
    try:
        result = vc.merge(branch_name)
    except ValueError as e:
        raise click.ClickException(str(e))

    if result["status"] == "up-to-date":
        console.print("Already up to date.")
    elif result["status"] == "fast-forward":
        console.print(f"[green]Fast-forward merge from '{branch_name}'[/green]")
    elif result["status"] == "conflict":
        for c in result["conflicts"]:
            console.print(f"[red]CONFLICT: {c}[/red]")
        raise click.ClickException("Merge failed due to conflicts.")


if __name__ == '__main__':
    cli()
