"""Kill command - terminate running smithers tmux sessions."""

from typing import Annotated

import typer

from smithers.console import console, print_error, print_header, print_info, print_warning
from smithers.services.git import GitService
from smithers.services.tmux import TmuxService


def kill(
    session: Annotated[
        str | None,
        typer.Argument(
            help="Session name to kill (defaults to the last smithers session)",
        ),
    ] = None,
    all_sessions: Annotated[
        bool,
        typer.Option("--all", "-a", help="Kill all running smithers sessions"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
    cleanup_worktrees: Annotated[
        bool,
        typer.Option("--cleanup-worktrees", "-w", help="Also remove associated git worktrees"),
    ] = False,
) -> None:
    """Kill a running smithers tmux session.

    If no session name is provided, kills the most recent smithers session.
    Use --all to kill all running smithers sessions.

    This will:
    - Terminate the tmux session (stops Claude Code and other processes)
    - Clean up session output files

    Use --cleanup-worktrees to also remove git worktrees created by the session.
    """
    tmux_service = TmuxService()

    if all_sessions:
        _kill_all_sessions(tmux_service, force, cleanup_worktrees)
        return

    # Determine which session to kill
    target_session: str | None = session

    if target_session is None:
        # Try to get the last session from hint file
        last_session = tmux_service.get_last_session()
        if last_session:
            target_session = last_session.session_name
        else:
            # Fall back to listing available sessions
            sessions = tmux_service.list_smithers_sessions()
            if not sessions:
                print_error("No smithers sessions found to kill.")
                raise typer.Exit(1)

            if len(sessions) == 1:
                target_session = sessions[0].name
            else:
                console.print("\n[yellow]Multiple sessions found. Please specify one:[/yellow]\n")
                _list_sessions(tmux_service)
                console.print("\n[dim]Or use --all to kill all sessions[/dim]")
                raise typer.Exit(1)

    # Verify the session exists
    if not tmux_service.session_exists(target_session):
        print_error(f"Session '{target_session}' does not exist.")

        # Show available sessions if any
        sessions = tmux_service.list_smithers_sessions()
        if sessions:
            console.print("\nAvailable sessions:")
            for s in sessions:
                console.print(f"  • {s.name}")
        raise typer.Exit(1)

    # Check for tracked worktrees before confirming
    tracked_worktrees = tmux_service.get_session_worktrees(target_session)

    # Confirm before killing (unless --force)
    if not force:
        if tracked_worktrees and not cleanup_worktrees:
            wt_count = len(tracked_worktrees)
            console.print(f"\n[yellow]Session has {wt_count} tracked worktree(s):[/yellow]")
            for wt in tracked_worktrees:
                console.print(f"  • {wt}")
            console.print("\n[dim]Use --cleanup-worktrees to also remove them[/dim]")

        confirm = typer.confirm(f"\nKill session '{target_session}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Kill the session (this also cleans up session files)
    _kill_session_with_cleanup(tmux_service, target_session, cleanup_worktrees, tracked_worktrees)
    print_info(f"Session '{target_session}' has been killed.")


def _kill_session_with_cleanup(
    tmux_service: TmuxService,
    session_name: str,
    cleanup_worktrees: bool,
    tracked_worktrees: list[str],
) -> None:
    """Kill a session and optionally clean up worktrees.

    Args:
        tmux_service: The tmux service instance
        session_name: Name of the session to kill
        cleanup_worktrees: Whether to also remove worktrees
        tracked_worktrees: List of worktree branches to clean up
    """
    # Kill the tmux session (stops Claude Code)
    tmux_service.kill_session(session_name)

    # Clean up worktrees if requested
    if cleanup_worktrees and tracked_worktrees:
        git_service = GitService()
        console.print("\n[dim]Cleaning up worktrees...[/dim]")
        for branch in tracked_worktrees:
            try:
                git_service.cleanup_worktree(branch)
                console.print(f"  [red]✗[/red] Removed worktree: {branch}")
            except Exception as e:
                print_warning(f"Failed to remove worktree {branch}: {e}")
    elif tracked_worktrees and not cleanup_worktrees:
        console.print(
            f"\n[dim]Note: {len(tracked_worktrees)} worktree(s) not removed. "
            "Use --cleanup-worktrees to remove them.[/dim]"
        )


def _kill_all_sessions(tmux_service: TmuxService, force: bool, cleanup_worktrees: bool) -> None:
    """Kill all running smithers sessions."""
    sessions = tmux_service.list_smithers_sessions()

    if not sessions:
        console.print("[yellow]No smithers sessions found to kill.[/yellow]")
        return

    print_header("Sessions to Kill")
    all_worktrees: dict[str, list[str]] = {}
    for session in sessions:
        attached = " [green](attached)[/green]" if session.attached else ""
        worktrees = tmux_service.get_session_worktrees(session.name)
        all_worktrees[session.name] = worktrees
        wt_info = f" ({len(worktrees)} worktree(s))" if worktrees else ""
        console.print(f"  • [cyan]{session.name}[/cyan]{attached}{wt_info}")

    # Confirm before killing (unless --force)
    if not force:
        if any(all_worktrees.values()) and not cleanup_worktrees:
            msg = "[dim]Use --cleanup-worktrees to also remove associated worktrees[/dim]"
            console.print(f"\n{msg}")
        confirm = typer.confirm(f"\nKill all {len(sessions)} session(s)?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # Kill each session
    for session in sessions:
        _kill_session_with_cleanup(
            tmux_service,
            session.name,
            cleanup_worktrees,
            all_worktrees.get(session.name, []),
        )
        console.print(f"  [red]✗[/red] Killed [cyan]{session.name}[/cyan]")

    print_info(f"Killed {len(sessions)} session(s).")


def _list_sessions(tmux_service: TmuxService) -> None:
    """List all running smithers tmux sessions."""
    sessions = tmux_service.list_smithers_sessions()

    print_header("Running Smithers Sessions")

    for session in sessions:
        attached = " [green](attached)[/green]" if session.attached else ""
        windows = f"{session.windows} window{'s' if session.windows != 1 else ''}"
        console.print(f"  • [cyan]{session.name}[/cyan] - {windows}{attached}")
