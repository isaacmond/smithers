"""GitHub CLI service for PR and repository operations."""

import json
import subprocess
from dataclasses import dataclass

from smithers.exceptions import DependencyMissingError, GitHubError
from smithers.logging_config import get_logger, log_subprocess_result

logger = get_logger("smithers.services.github")


@dataclass
class PRInfo:
    """Information about a pull request."""

    number: int
    title: str
    branch: str
    state: str
    url: str


@dataclass
class GitHubService:
    """Service for GitHub CLI (gh) operations."""

    def check_dependencies(self) -> list[str]:
        """Check for required dependencies and return list of missing ones."""
        logger.debug("Checking gh CLI dependencies")
        missing: list[str] = []

        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True,
                text=True,
            )
            logger.debug(f"gh version: {result.stdout.strip().split(chr(10))[0]}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("gh CLI not found or not working")
            missing.append("gh (GitHub CLI)")

        return missing

    def ensure_dependencies(self) -> None:
        """Ensure all required dependencies are installed."""
        missing = self.check_dependencies()
        if missing:
            raise DependencyMissingError(missing)

    def get_pr_info(self, pr_number: int) -> PRInfo:
        """Get information about a pull request.

        Args:
            pr_number: The PR number

        Returns:
            PRInfo with PR details

        Raises:
            GitHubError: If the operation fails
        """
        logger.info(f"Getting PR info: pr_number={pr_number}")
        cmd = [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,headRefName,state,url",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            log_subprocess_result(logger, cmd, result.returncode, result.stdout, result.stderr)
            data = json.loads(result.stdout)
            pr_info = PRInfo(
                number=data["number"],
                title=data["title"],
                branch=data["headRefName"],
                state=data["state"],
                url=data["url"],
            )
            logger.info(f"PR #{pr_number}: branch={pr_info.branch}, state={pr_info.state}")
            return pr_info
        except subprocess.CalledProcessError as e:
            log_subprocess_result(logger, cmd, e.returncode, e.stdout, e.stderr, success=False)
            logger.exception(f"Failed to get PR #{pr_number} info: {e.stderr}")
            raise GitHubError(f"Failed to get PR #{pr_number} info: {e.stderr}") from e
        except (json.JSONDecodeError, KeyError) as e:
            logger.exception(f"Failed to parse PR #{pr_number} info")
            raise GitHubError(f"Failed to parse PR #{pr_number} info: {e}") from e
