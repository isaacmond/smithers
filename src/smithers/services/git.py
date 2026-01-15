"""Git and worktree management service."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from smithers.console import console, print_info, print_warning
from smithers.exceptions import DependencyMissingError, WorktreeError
from smithers.logging_config import get_logger, log_subprocess_result

logger = get_logger("smithers.services.git")


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: Path
    branch: str
    status: str  # 'ok', 'missing', 'prunable', etc.

    @property
    def is_main_repo(self) -> bool:
        """Check if this is the main repository (not a worktree)."""
        return self.branch == "main" or "(detached)" in self.branch


@dataclass
class GitService:
    """Service for Git and worktree operations using gtr (git-worktree-runner)."""

    created_worktrees: list[str] = field(default_factory=list)

    def check_dependencies(self) -> list[str]:
        """Check for required dependencies and return list of missing ones."""
        logger.debug("Checking git dependencies")
        missing: list[str] = []

        # Check git
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                text=True,
            )
            logger.debug(f"git version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("git not found or not working")
            missing.append("git")

        # Check gtr (git-worktree-runner)
        try:
            result = subprocess.run(
                ["git", "gtr", "version"],
                capture_output=True,
                check=True,
                text=True,
            )
            logger.debug(f"gtr version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("git-worktree-runner (gtr) not found or not working")
            missing.append("git-worktree-runner (gtr)")

        return missing

    def ensure_dependencies(self) -> None:
        """Ensure all required dependencies are installed."""
        missing = self.check_dependencies()
        if missing:
            raise DependencyMissingError(missing)

    def create_worktree(self, branch: str, base: str = "main") -> Path:
        """Create a worktree for the given branch, or return existing one.

        Args:
            branch: The branch name for the new worktree
            base: The base ref to create the branch from

        Returns:
            Path to the created or existing worktree

        Raises:
            WorktreeError: If worktree creation fails
        """
        logger.info(f"create_worktree: branch={branch}, base={base}")

        # Check if worktree already exists
        existing_path = self.get_worktree_path(branch)
        if existing_path is not None:
            logger.info(f"Using existing worktree: {existing_path}")
            print_info(f"Using existing worktree for branch: {branch} at {existing_path}")
            # Track for cleanup if not already tracked
            if branch not in self.created_worktrees:
                self.created_worktrees.append(branch)
            return existing_path

        print_info(f"Creating worktree for branch: {branch} (from {base})")

        cmd = ["git", "gtr", "new", branch, "--from", base, "--yes"]
        logger.debug(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            log_subprocess_result(logger, cmd, result.returncode, result.stdout, result.stderr)
            logger.info(f"Worktree created for branch: {branch}")
        except subprocess.CalledProcessError as e:
            log_subprocess_result(logger, cmd, e.returncode, e.stdout, e.stderr, success=False)
            logger.exception(f"Failed to create worktree for {branch}: {e.stderr}")
            raise WorktreeError(f"Failed to create worktree for {branch}: {e.stderr}") from e

        # Track for cleanup
        self.created_worktrees.append(branch)

        # Get the worktree path
        worktree_path = self.get_worktree_path(branch)
        if worktree_path is None:
            logger.error(f"Worktree created but path not found for {branch}")
            raise WorktreeError(f"Worktree created but path not found for {branch}")

        logger.info(f"Worktree path: {worktree_path}")
        return worktree_path

    def get_worktree_path(self, branch: str) -> Path | None:
        """Get the filesystem path for a worktree.

        Args:
            branch: The branch name

        Returns:
            Path to the worktree, or None if not found
        """
        logger.debug(f"get_worktree_path: branch={branch}")
        try:
            result = subprocess.run(
                ["git", "gtr", "go", branch],
                capture_output=True,
                check=True,
                text=True,
            )
            path_str = result.stdout.strip()
            if path_str:
                logger.debug(f"Worktree path for {branch}: {path_str}")
                return Path(path_str)
        except subprocess.CalledProcessError:
            logger.debug(f"No worktree found for {branch}")
        return None

    def cleanup_worktree(self, branch: str) -> None:
        """Remove a worktree.

        Args:
            branch: The branch name of the worktree to remove
        """
        logger.info(f"Cleaning up worktree: branch={branch}")
        print_info(f"Cleaning up worktree for branch: {branch}")

        cmd = ["git", "gtr", "rm", branch, "--yes"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,  # Don't raise on error
                text=True,
            )
            if result.returncode == 0:
                logger.debug(f"Worktree {branch} cleaned up successfully")
            else:
                logger.warning(f"Worktree cleanup for {branch} returned {result.returncode}")
                log_subprocess_result(
                    logger, cmd, result.returncode, result.stdout, result.stderr, success=False
                )
        except subprocess.CalledProcessError:
            logger.warning(f"Failed to cleanup worktree for {branch}")
            print_warning(f"Failed to cleanup worktree for {branch}")

        # Remove from tracking
        if branch in self.created_worktrees:
            self.created_worktrees.remove(branch)

    def cleanup_all_worktrees(self) -> None:
        """Remove all created worktrees."""
        logger.info(f"Cleaning up all worktrees: {self.created_worktrees}")
        for branch in list(self.created_worktrees):
            self.cleanup_worktree(branch)

    def get_branch_dependency_base(
        self,
        depends_on: str | None,
        default_base: str = "main",
    ) -> str:
        """Determine the base ref for a stage based on its dependencies.

        Args:
            depends_on: The dependency branch name (e.g., "stage-1-models") or None/"none"
            default_base: Default base if no dependency

        Returns:
            The base ref to use
        """
        if depends_on is None or depends_on.lower() == "none":
            return default_base

        # depends_on is now the actual branch name (no more "Stage N" parsing needed)
        return depends_on

    def list_worktrees(self) -> list[WorktreeInfo]:
        """List all worktrees in the repository.

        Returns:
            List of WorktreeInfo objects for each worktree
        """
        logger.debug("Listing all worktrees")
        worktrees: list[WorktreeInfo] = []

        try:
            result = subprocess.run(
                ["git", "gtr", "list", "--porcelain"],
                capture_output=True,
                check=True,
                text=True,
            )

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    path_str, branch, status = parts[0], parts[1], parts[2]
                    worktrees.append(
                        WorktreeInfo(
                            path=Path(path_str),
                            branch=branch,
                            status=status,
                        )
                    )
                    logger.debug(f"Found worktree: {branch} at {path_str} ({status})")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to list worktrees: {e.stderr}")
        except FileNotFoundError:
            logger.warning("git or gtr not found")

        return worktrees

    def clean_stale_worktrees(self, dry_run: bool = False) -> tuple[int, list[str]]:
        """Clean up stale/prunable worktrees using git gtr clean.

        Args:
            dry_run: If True, only show what would be removed

        Returns:
            Tuple of (number of cleaned worktrees, list of cleaned paths/branches)
        """
        logger.info(f"Cleaning stale worktrees (dry_run={dry_run})")

        cmd = ["git", "gtr", "clean", "--yes"]
        if dry_run:
            cmd.append("--dry-run")

        cleaned: list[str] = []

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                text=True,
            )
            log_subprocess_result(logger, cmd, result.returncode, result.stdout, result.stderr)

            # Parse output to count cleaned worktrees
            for line in result.stdout.split("\n"):
                if line.strip() and ("removed" in line.lower() or "would remove" in line.lower()):
                    cleaned.append(line.strip())

            return len(cleaned), cleaned

        except FileNotFoundError:
            logger.warning("git or gtr not found")
            return 0, []

    def remove_worktrees(
        self,
        branches: list[str],
        delete_branch: bool = False,
        force: bool = False,
    ) -> tuple[int, int]:
        """Remove multiple worktrees by branch name.

        Args:
            branches: List of branch names to remove
            delete_branch: Also delete the git branch
            force: Force removal even if dirty

        Returns:
            Tuple of (removed_count, failed_count)
        """
        logger.info(f"Removing worktrees: {branches}")
        removed = 0
        failed = 0

        for branch in branches:
            cmd = ["git", "gtr", "rm", branch, "--yes"]
            if delete_branch:
                cmd.append("--delete-branch")
            if force:
                cmd.append("--force")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    check=False,
                    text=True,
                )

                if result.returncode == 0:
                    logger.debug(f"Removed worktree: {branch}")
                    console.print(f"  [red]x[/red] Removed worktree: [cyan]{branch}[/cyan]")
                    removed += 1
                else:
                    logger.warning(f"Failed to remove worktree {branch}: {result.stderr}")
                    console.print(f"  [yellow]![/yellow] Failed to remove: [cyan]{branch}[/cyan]")
                    failed += 1

            except FileNotFoundError:
                logger.warning("git or gtr not found")
                failed += 1

        return removed, failed
