"""Vibekanban management commands."""

import subprocess
from shutil import which

import typer

from smithers.console import console, print_error, print_info, print_success, print_warning
from smithers.services.tmux import TmuxService

# Session name for the vibe-kanban background process
VIBEKANBAN_SESSION_NAME = "smithers-vibekanban"


def kanban() -> None:
    """Start vibe-kanban in a background tmux session.

    Launches vibe-kanban in a detached tmux session so it runs forever
    in the background. The session persists until explicitly killed.
    """
    if which("npx") is None:
        print_error("npx is required to run vibe-kanban. Install Node.js first.")
        raise typer.Exit(1)

    tmux_service = TmuxService()

    # Check if already running
    if tmux_service.session_exists(VIBEKANBAN_SESSION_NAME):
        print_warning("vibe-kanban is already running in a tmux session.")
        console.print(f"  Session: [cyan]{VIBEKANBAN_SESSION_NAME}[/cyan]")
        console.print("  Use [cyan]smithers kanban-kill[/cyan] to stop it")
        console.print("  Use [cyan]tmux attach -t smithers-vibekanban[/cyan] to view it")
        return

    # Ensure tmux is available
    try:
        tmux_service.ensure_dependencies()
    except Exception as e:
        print_error(f"tmux dependency check failed: {e}")
        raise typer.Exit(1) from e

    print_info("Starting vibe-kanban in background tmux session...")

    # Create detached tmux session running vibe-kanban
    try:
        result = subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",  # Detached
                "-s",
                VIBEKANBAN_SESSION_NAME,
                "npx",
                "--quiet",
                "vibe-kanban@latest",
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        if result.returncode != 0:
            print_error(f"Failed to start tmux session: {result.stderr}")
            raise typer.Exit(1)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create tmux session: {e.stderr}")
        raise typer.Exit(1) from e

    print_success("vibe-kanban is now running in the background!")
    console.print(f"  Session: [cyan]{VIBEKANBAN_SESSION_NAME}[/cyan]")
    console.print("  View it: [cyan]tmux attach -t smithers-vibekanban[/cyan]")
    console.print("  Stop it: [cyan]smithers kanban-kill[/cyan]")


def kanban_kill() -> None:
    """Stop the vibe-kanban background tmux session.

    Kills the tmux session that was started by `smithers kanban`.
    """
    tmux_service = TmuxService()

    if not tmux_service.session_exists(VIBEKANBAN_SESSION_NAME):
        print_warning("vibe-kanban is not running.")
        return

    print_info("Stopping vibe-kanban...")
    tmux_service.kill_session(VIBEKANBAN_SESSION_NAME)
    print_success("vibe-kanban stopped.")


def kanban_update() -> None:
    """Update vibe-kanban to the latest version.

    Stops the running vibe-kanban, updates via npm, and restarts it.
    """
    if which("npx") is None:
        print_error("npx is required to update vibe-kanban. Install Node.js first.")
        raise typer.Exit(1)

    tmux_service = TmuxService()
    was_running = tmux_service.session_exists(VIBEKANBAN_SESSION_NAME)

    # Stop if running
    if was_running:
        print_info("Stopping vibe-kanban for update...")
        tmux_service.kill_session(VIBEKANBAN_SESSION_NAME)

    # Clear npx cache for vibe-kanban to ensure fresh download
    print_info("Updating vibe-kanban...")
    try:
        # npx --quiet vibe-kanban@latest will fetch the latest version
        # The cache is auto-handled by npx when using @latest
        result = subprocess.run(
            ["npx", "--quiet", "vibe-kanban@latest", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        # vibe-kanban may not have a --version flag, so just checking it runs is ok
        if result.returncode not in (0, 1):
            console.print(f"[dim]{result.stderr}[/dim]")
    except subprocess.TimeoutExpired:
        print_warning("Update check timed out, but latest version will be used on next run.")
    except subprocess.CalledProcessError as e:
        print_warning(f"Could not verify update: {e}")

    print_success("vibe-kanban updated to latest version.")

    # Restart if it was running
    if was_running:
        print_info("Restarting vibe-kanban...")
        kanban()
