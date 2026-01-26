"""Projects command - list and set vibekanban projects."""

import typer

from smithers.console import console, print_header
from smithers.services.config_loader import (
    load_vibekanban_config,
    save_vibekanban_project_id,
)
from smithers.services.vibekanban import VibekanbanService, get_vibekanban_url


def projects(
    name: str | None = typer.Argument(
        None,
        help="Project name to set as active (partial match supported)",
    ),
) -> None:
    """List or set the active vibekanban project.

    Without arguments, lists all available projects.
    With a project name, sets that project as active.

    Examples:
        smithers kanban projects           # List all projects
        smithers kanban projects megarepo  # Set megarepo as active project
    """
    print_header("Vibekanban Projects")

    vibekanban_url = get_vibekanban_url()
    if vibekanban_url:
        console.print(f"URL: [cyan]{vibekanban_url}[/cyan]\n")

    service = VibekanbanService(enabled=True)
    project_list = service.list_projects()

    if not project_list:
        console.print("[yellow]No projects found or vibekanban unavailable.[/yellow]")
        console.print("\nMake sure vibekanban is installed:")
        console.print("  [cyan]npx vibe-kanban[/cyan]")
        return

    # If a name was provided, try to set that project
    if name:
        _set_project(name, project_list)
        return

    # Otherwise, list all projects
    _list_projects(project_list)


def _set_project(name: str, project_list: list[dict[str, str]]) -> None:
    """Set the active project by name."""
    # Find matching projects (case-insensitive partial match)
    name_lower = name.lower()
    matches = [p for p in project_list if name_lower in p.get("name", "").lower()]

    if not matches:
        console.print(f"[red]No project found matching '[/red]{name}[red]'[/red]\n")
        console.print("[dim]Available projects:[/dim]")
        for project in project_list:
            console.print(f"  • {project.get('name', 'Unnamed')}")
        raise typer.Exit(1)

    if len(matches) > 1:
        # Check for exact match first
        exact = [p for p in matches if p.get("name", "").lower() == name_lower]
        if len(exact) == 1:
            matches = exact
        else:
            console.print(f"[yellow]Multiple projects match '[/yellow]{name}[yellow]':[/yellow]\n")
            for project in matches:
                console.print(f"  • {project.get('name', 'Unnamed')}")
            console.print("\n[dim]Please be more specific.[/dim]")
            raise typer.Exit(1)

    # Set the project
    project = matches[0]
    project_id = project.get("id", "")
    project_name = project.get("name", "Unnamed")

    if save_vibekanban_project_id(project_id):
        console.print(f"[green]✓[/green] Set active project: [cyan]{project_name}[/cyan]")
        console.print(f"  [dim]id:[/dim] {project_id}")
    else:
        console.print("[red]Failed to save project configuration.[/red]")
        raise typer.Exit(1)


def _list_projects(project_list: list[dict[str, str]]) -> None:
    """List all available projects."""
    current_config = load_vibekanban_config()
    current_id = current_config.project_id

    for project in project_list:
        project_id = project.get("id", "unknown")
        project_name = project.get("name", "Unnamed")
        if project_id == current_id:
            console.print(f"  [green]•[/green] [cyan]{project_name}[/cyan] [green](active)[/green]")
        else:
            console.print(f"  • [cyan]{project_name}[/cyan]")

    console.print("\n[dim]Set a project with:[/dim]")
    console.print("  [cyan]smithers kanban projects <name>[/cyan]")
