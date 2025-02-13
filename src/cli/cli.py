import click
import json
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from src.fl_studio.parser.base import FLParser
from src.utils import generate_hash


@dataclass
class Commit:
    hash: str
    message: str
    timestamp: datetime
    changes: dict


class DawVC:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.daw_dir = root_dir / '.daw'
        self.state_file = self.daw_dir / 'state.json'
        self.commits_file = self.daw_dir / 'commits.json'
        self.staged_file = self.daw_dir / 'staged.json'

    def init(self):
        self.daw_dir.mkdir(exist_ok=True)
        self.state_file.touch()
        self.commits_file.touch()
        self.staged_file.touch()

        self.state_file.write_text(json.dumps({}))
        self.commits_file.write_text(json.dumps([]))
        self.staged_file.write_text(json.dumps([]))

    def add(self, project_path: Path):
        parser = FLParser(project_path)
        state = parser.get_state()
        state['metadata'] = state['metadata']
        staged = json.loads(self.staged_file.read_text())
        staged.append({
            'path': str(project_path),
            'state': state
        })
        self.staged_file.write_text(json.dumps(staged))

    def commit(self, message: str):
        staged = json.loads(self.staged_file.read_text())
        if not staged:
            raise click.ClickException("Nothing to commit")

        commits = json.loads(self.commits_file.read_text())
        commit = Commit(
            hash=generate_hash(),
            message=message,
            timestamp=datetime.now(),
            changes=staged
        )
        commits.append(commit.__dict__)

        self.commits_file.write_text(json.dumps(commits))
        self.staged_file.write_text(json.dumps([]))


@click.group()
def cli():
    """DAW Version Control CLI"""
    click.echo("Welcome to the DAW Version Control Tool!")


@cli.command()
def init():
    """
    Initialize a new FL Studio VC repository
    """
    vc = DawVC(Path.cwd())
    vc.init()


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def add(project):
    """
    Add FL Studio project to staging
    """
    vc = DawVC(Path.cwd())
    vc.add(Path(project))


@cli.command()
@click.argument('message')
def commit(message):
    """
    Commit staged changes
    """
    vc = DawVC(Path.cwd())
    vc.commit(message)


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def status(project):
    """
    Show project status
    """
    vc = DawVC(Path.cwd())
    # Show changes between current and last commit


@cli.command()
@click.argument('project', type=click.Path(exists=True))
def diff(project):
    """
    Show changes in project
    """
    vc = DawVC(Path.cwd())
    # Show detailed diff


@cli.command()
def log():
    """
    Show commit history
    """
    vc = DawVC(Path.cwd())
    commits = json.loads(vc.commits_file.read_text())
    for commit in commits:
        print(f"{commit['hash']}: {commit['message']}")


if __name__ == '__main__':
    cli()