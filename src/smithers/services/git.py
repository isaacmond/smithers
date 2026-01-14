"""Git and worktree management service."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from smithers.console import print_info, print_warning
from smithers.exceptions import DependencyMissingError, WorktreeError
from smithers.logging_config import get_logger, log_subprocess_result

logger = get_logger("smithers.services.git")


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
