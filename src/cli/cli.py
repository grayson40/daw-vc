import click
import json
import shutil
from pathlib import Path
from datetime import datetime
from src.utils import generate_hash
from rich.console import Console
from src.fl_studio.diff.compare import compare

console = Console()


class DawVC:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.daw_dir = root_dir / '.daw'
        self.state_file = self.daw_dir / 'state.json'
        self.commits_file = self.daw_dir / 'commits.json'
        self.staged_file = self.daw_dir / 'staged.json'
        self.objects_dir = self.daw_dir / 'objects'

    def init(self):
        self.daw_dir.mkdir(exist_ok=True)
        self.objects_dir.mkdir(exist_ok=True)
        self.state_file.write_text(json.dumps({"branch": "main", "head": None}))
        self.commits_file.write_text(json.dumps([]))
        self.staged_file.write_text(json.dumps([]))

    def add(self, project_path: Path):
        staged = json.loads(self.staged_file.read_text())
        staged.append({'path': str(project_path)})
        self.staged_file.write_text(json.dumps(staged))

    def commit(self, message: str):
        staged = json.loads(self.staged_file.read_text())
        if not staged:
            raise click.ClickException("Nothing to commit")

        self.objects_dir.mkdir(exist_ok=True)
        commits = json.loads(self.commits_file.read_text())
        commit_hash = generate_hash()

        for entry in staged:
            src_path = Path(entry["path"])
            if src_path.exists():
                shutil.copy2(src_path, self.objects_dir / f"{commit_hash}.flp")

        new_commit = {
            "hash": commit_hash,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "branch": "main",
            "parent_hash": commits[-1]["hash"] if commits else None,
            "changes": staged,
        }
        commits.append(new_commit)
        self.commits_file.write_text(json.dumps(commits, default=str))
        self.staged_file.write_text(json.dumps([]))
        return commit_hash


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
    commit_hash = vc.commit(message)
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
    commits = json.loads(vc.commits_file.read_text())
    if not commits:
        console.print("No commits yet.")
        return
    for c in reversed(commits):
        console.print(f"[yellow]{c['hash']}[/yellow] {c['message']} [dim]({c['timestamp']})[/dim]")


if __name__ == '__main__':
    cli()
