"""Rich console singleton and helpers for terminal output."""

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

if TYPE_CHECKING:
    from smithers.models.todo import TodoFile

# Global console instance
console = Console()


def print_header(title: str) -> None:
    """Print a styled header."""
    console.print()
    console.print(Panel(title, style="bold blue"))
    console.print()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]{message}[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]Error: {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]Warning: {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]{message}[/blue]")


def create_progress() -> Progress:
    """Create a progress bar for tracking long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    )


def print_detach_message(session: str) -> None:
    """Print the detach/reconnect instructions when user presses Ctrl+C."""
    console.print()
    console.print(
        Panel.fit(
            f"[yellow]Detached from session.[/yellow]\n\n"
            f"The session [cyan]{session}[/cyan] is still running in the background.\n\n"
            f"Reconnect with: [bold cyan]smithers rejoin[/bold cyan]",
            title="[bold]Session Detached[/bold]",
            border_style="yellow",
        )
    )


def print_session_complete(exit_code: int) -> None:
    """Print session completion message with exit code."""
    if exit_code == 0:
        console.print()
        console.print(
            Panel.fit(
                "[green]Session completed successfully.[/green]",
                border_style="green",
            )
        )
    else:
        console.print()
        console.print(
            Panel.fit(
                f"[red]Session exited with code {exit_code}.[/red]",
                border_style="red",
            )
        )


def print_plan_summary(todo: TodoFile) -> None:
    """Print a formatted summary of the implementation plan.

    Args:
        todo: The parsed TodoFile containing the plan
    """
    console.print()
    console.print(Panel(f"[bold]{todo.title}[/bold]", style="cyan"))

    if todo.overview:
        console.print()
        console.print("[bold]Overview:[/bold]")
        # Truncate overview if too long
        overview = todo.overview[:500] + "..." if len(todo.overview) > 500 else todo.overview
        console.print(f"  {overview}")

    console.print()
    console.print(f"[bold]Stages:[/bold] {len(todo.stages)} total")
    console.print()

    # Create a table for stages
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="cyan")
    table.add_column("Branch", style="green")
    table.add_column("Files", justify="right")
    table.add_column("Depends On", style="dim")

    for stage in todo.stages:
        depends = stage.depends_on or "none"
        table.add_row(
            str(stage.number),
            stage.title,
            stage.branch,
            str(len(stage.files)),
            depends,
        )

    console.print(table)
    console.print()
