"""Cleanup command - delete all smithers-created vibekanban tasks."""

from typing import Annotated

import typer

from smithers.console import console, print_error, print_header, print_info, print_success
from smithers.services.vibekanban import VibekanbanService, get_vibekanban_url


def cleanup(
    project: str | None = typer.Argument(
        None,
        help="Project name to clean up (partial match supported)",
    ),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Delete all smithers-created vibekanban tasks.

    Finds and deletes all tasks with [impl] or [fix] prefixes across
    all statuses (todo, in_progress, completed, failed).

    Examples:
        smithers cleanup           # Clean up configured/auto-discovered project
        smithers cleanup megarepo  # Clean up the megarepo project
    """
    print_header("Vibekanban Cleanup")

    vibekanban_url = get_vibekanban_url()
    if vibekanban_url:
        console.print(f"URL: [cyan]{vibekanban_url}[/cyan]\n")

    service = VibekanbanService(enabled=True)

    # If a project name was provided, look it up
    if project:
        project_id = _resolve_project_by_name(project, service)
        if not project_id:
            raise typer.Exit(1)
        service.project_id = project_id
    # Otherwise, auto-discover project if not configured
    elif not service.project_id:
        from smithers.services.vibekanban import _auto_discover_project_id

        service.project_id = _auto_discover_project_id()

    if not service.is_configured():
        print_error("No vibekanban project configured.")
        console.print("\nRun [cyan]smithers projects[/cyan] to see available projects.")
        raise typer.Exit(1)

    # Find all smithers-created tasks
    console.print("[dim]Scanning for smithers-created tasks...[/dim]\n")
    tasks = service.list_all_smithers_tasks()

    if not tasks:
        print_info("No smithers-created tasks found.")
        return

    # Group tasks by status for display
    by_status: dict[str, list[dict[str, str]]] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(task)

    # Display what will be deleted
    console.print(f"[yellow]Found {len(tasks)} smithers-created task(s):[/yellow]\n")

    for status, status_tasks in sorted(by_status.items()):
        console.print(f"  [dim]{status}:[/dim]")
        for task in status_tasks:
            task_id = task.get("id", "unknown")
            title = task.get("title", "Untitled")
            console.print(f"    - [cyan]{title}[/cyan] [dim]({task_id})[/dim]")
        console.print()

    # Confirm before deleting (unless --force)
    if not force:
        confirm = typer.confirm(f"Delete all {len(tasks)} task(s)?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Delete each task
    console.print()
    deleted = 0
    failed = 0

    for task in tasks:
        task_id = task.get("id")
        title = task.get("title", "Untitled")

        if not task_id:
            continue

        if service.delete_task(task_id):
            console.print(f"  [red]x[/red] Deleted: [cyan]{title}[/cyan]")
            deleted += 1
        else:
            console.print(f"  [yellow]![/yellow] Failed to delete: [cyan]{title}[/cyan]")
            failed += 1

    console.print()
    if deleted > 0:
        print_success(f"Deleted {deleted} task(s).")
    if failed > 0:
        print_error(f"Failed to delete {failed} task(s).")


def _resolve_project_by_name(name: str, service: VibekanbanService) -> str | None:
    """Resolve a project name to its ID.

    Returns the project ID if found, None if not found or ambiguous.
    """
    project_list = service.list_projects()

    if not project_list:
        print_error("No projects found or vibekanban unavailable.")
        return None

    # Find matching projects (case-insensitive partial match)
    name_lower = name.lower()
    matches = [p for p in project_list if name_lower in p.get("name", "").lower()]

    if not matches:
        print_error(f"No project found matching '{name}'")
        console.print("\n[dim]Available projects:[/dim]")
        for p in project_list:
            console.print(f"  • {p.get('name', 'Unnamed')}")
        return None

    if len(matches) > 1:
        # Check for exact match first
        exact = [p for p in matches if p.get("name", "").lower() == name_lower]
        if len(exact) == 1:
            matches = exact
        else:
            console.print(f"[yellow]Multiple projects match '{name}':[/yellow]\n")
            for p in matches:
                console.print(f"  • {p.get('name', 'Unnamed')}")
            console.print("\n[dim]Please be more specific.[/dim]")
            return None

    project = matches[0]
    project_name = project.get("name", "Unnamed")
    console.print(f"Project: [cyan]{project_name}[/cyan]\n")
    return project.get("id")
