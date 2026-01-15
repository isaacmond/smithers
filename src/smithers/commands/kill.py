"""Kill command - terminate running smithers tmux sessions."""

from pathlib import Path
from typing import Annotated

import typer

from smithers.console import console, print_error, print_header, print_info, print_warning
from smithers.services.git import GitService
from smithers.services.github import GitHubService
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
) -> None:
    """Kill a running smithers tmux session.

    If no session name is provided, kills the most recent smithers session.
    Use --all to kill all running smithers sessions.

    This will:
    - Terminate the tmux session (stops Claude Code and other processes)
    - Clean up session output files
    - Clean up git worktrees created by the session
    - For implement sessions: close all PRs and delete all branches
    """
    tmux_service = TmuxService()

    if all_sessions:
        _kill_all_sessions(tmux_service, force)
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

    # Gather cleanup info
    tracked_worktrees = tmux_service.get_session_worktrees(target_session)
    session_mode = TmuxService.get_session_mode(target_session)
    tracked_prs: list[int] = []
    if session_mode == "implement":
        tracked_prs = tmux_service.get_session_prs(target_session)
    plan_files = tmux_service.get_session_plan_files(target_session)

    # Confirm before killing (unless --force)
    if not force:
        _show_cleanup_info(target_session, session_mode, tracked_worktrees, tracked_prs, plan_files)

        confirm = typer.confirm(f"\nKill session '{target_session}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Kill the session with full cleanup
    _kill_session_with_cleanup(
        tmux_service=tmux_service,
        session_name=target_session,
        session_mode=session_mode,
        tracked_worktrees=tracked_worktrees,
        tracked_prs=tracked_prs,
        plan_files=plan_files,
    )
    print_info(f"Session '{target_session}' has been killed.")


def _show_cleanup_info(
    session_name: str,
    session_mode: str | None,
    tracked_worktrees: list[str],
    tracked_prs: list[int],
    plan_files: list[Path],
) -> None:
    """Show what will be cleaned up when killing a session."""
    console.print(f"\n[cyan]Session:[/cyan] {session_name}")

    if session_mode:
        console.print(f"[cyan]Mode:[/cyan] {session_mode}")

    if tracked_worktrees:
        console.print(f"\n[yellow]Will cleanup {len(tracked_worktrees)} worktree(s):[/yellow]")
        for wt in tracked_worktrees:
            console.print(f"  • {wt}")

    if session_mode == "implement" and tracked_prs:
        pr_count = len(tracked_prs)
        console.print(f"\n[yellow]Will close {pr_count} PR(s) and delete branches:[/yellow]")
        for pr in tracked_prs:
            console.print(f"  • PR #{pr}")

    if plan_files:
        console.print(f"\n[yellow]Will delete {len(plan_files)} plan file(s):[/yellow]")
        for pf in plan_files:
            console.print(f"  • {pf.name}")


def _kill_session_with_cleanup(
    tmux_service: TmuxService,
    session_name: str,
    session_mode: str | None,
    tracked_worktrees: list[str],
    tracked_prs: list[int],
    plan_files: list[Path] | None = None,
) -> None:
    """Kill a session and clean up all associated resources.

    Args:
        tmux_service: The tmux service instance
        session_name: Name of the session to kill
        session_mode: The session mode ("implement", "fix", or None)
        tracked_worktrees: List of worktree branches to clean up
        tracked_prs: List of PR numbers to close (for implement mode only)
        plan_files: List of plan file paths to delete
    """
    # Kill the tmux session (stops Claude Code)
    tmux_service.kill_session(session_name)

    # For implement mode, close PRs and delete branches
    if session_mode == "implement" and tracked_prs:
        github_service = GitHubService()
        console.print("\n[dim]Closing PRs and deleting branches...[/dim]")

        for pr_num in tracked_prs:
            try:
                # Get PR info to find the branch name
                pr_info = github_service.get_pr_info(pr_num)
                branch = pr_info.branch

                # Close the PR
                github_service.close_pr(
                    pr_num,
                    comment="Closed by `smithers kill` - session terminated.",
                )
                console.print(f"  [red]✗[/red] Closed PR #{pr_num}")

                # Delete the branch
                github_service.delete_branch(branch)
                console.print(f"  [red]✗[/red] Deleted branch: {branch}")
            except Exception as e:
                print_warning(f"Failed to cleanup PR #{pr_num}: {e}")

    # Always clean up worktrees
    if tracked_worktrees:
        git_service = GitService()
        console.print("\n[dim]Cleaning up worktrees...[/dim]")
        for branch in tracked_worktrees:
            try:
                git_service.cleanup_worktree(branch)
                console.print(f"  [red]✗[/red] Removed worktree: {branch}")
            except Exception as e:
                print_warning(f"Failed to remove worktree {branch}: {e}")

    # Clean up plan files
    if plan_files:
        console.print("\n[dim]Cleaning up plan files...[/dim]")
        for plan_file in plan_files:
            try:
                plan_file.unlink()
                console.print(f"  [red]✗[/red] Deleted plan: {plan_file.name}")
            except Exception as e:
                print_warning(f"Failed to delete plan file {plan_file.name}: {e}")


def _kill_all_sessions(tmux_service: TmuxService, force: bool) -> None:
    """Kill all running smithers sessions."""
    sessions = tmux_service.list_smithers_sessions()

    if not sessions:
        console.print("[yellow]No smithers sessions found to kill.[/yellow]")
        return

    print_header("Sessions to Kill")

    # Gather info for all sessions
    session_info: dict[str, dict[str, object]] = {}
    for session in sessions:
        mode = TmuxService.get_session_mode(session.name)
        worktrees = tmux_service.get_session_worktrees(session.name)
        prs = tmux_service.get_session_prs(session.name) if mode == "implement" else []
        plan_files = tmux_service.get_session_plan_files(session.name)

        session_info[session.name] = {
            "mode": mode,
            "worktrees": worktrees,
            "prs": prs,
            "plan_files": plan_files,
            "attached": session.attached,
        }

        attached = " [green](attached)[/green]" if session.attached else ""
        mode_str = f" [{mode}]" if mode else ""
        wt_info = f" ({len(worktrees)} worktree(s))" if worktrees else ""
        pr_info = f" ({len(prs)} PR(s))" if prs else ""
        plan_info = f" ({len(plan_files)} plan(s))" if plan_files else ""
        console.print(
            f"  • [cyan]{session.name}[/cyan]{mode_str}{attached}{wt_info}{pr_info}{plan_info}"
        )

    # Confirm before killing (unless --force)
    if not force:
        confirm = typer.confirm(f"\nKill all {len(sessions)} session(s)?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # Kill each session
    for session in sessions:
        info = session_info[session.name]
        _kill_session_with_cleanup(
            tmux_service=tmux_service,
            session_name=session.name,
            session_mode=str(info["mode"]) if info["mode"] else None,
            tracked_worktrees=list(info["worktrees"]),  # type: ignore[arg-type]
            tracked_prs=list(info["prs"]),  # type: ignore[arg-type]
            plan_files=list(info["plan_files"]),  # type: ignore[arg-type]
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
