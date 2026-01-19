"""Parsing utilities for Smithers."""

from urllib.parse import urlparse


def parse_pr_identifier(identifier: str) -> int:
    """Parse a PR number from either a number string or a GitHub PR URL.

    Args:
        identifier: Either a PR number (e.g., "123") or a GitHub PR URL
                   (e.g., "https://github.com/owner/repo/pull/123")

    Returns:
        The PR number as an integer

    Raises:
        ValueError: If the identifier cannot be parsed as a PR number
    """
    # Try parsing as a simple integer first
    try:
        return int(identifier)
    except ValueError:
        pass

    # Try parsing as a GitHub PR URL
    parsed = urlparse(identifier)
    if parsed.netloc in ("github.com", "www.github.com"):
        # URL format: https://github.com/owner/repo/pull/123
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 4 and parts[2] == "pull":
            try:
                return int(parts[3])
            except ValueError:
                pass

    # Check if it looks like a file path and provide a helpful hint
    if identifier.endswith(".md"):
        raise ValueError(
            f"Invalid PR identifier: {identifier}. "
            "This looks like a markdown file. Did you mean to use --design-doc/-d?"
        )

    raise ValueError(
        f"Invalid PR identifier: {identifier}. "
        "Expected a PR number (e.g., 123) or GitHub URL (e.g., https://github.com/owner/repo/pull/123)"
    )
