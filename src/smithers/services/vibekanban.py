"""Vibekanban MCP service for task tracking."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from smithers.logging_config import get_logger

logger = get_logger("smithers.services.vibekanban")


@dataclass
class TaskInfo:
    """Information about a vibekanban task."""

    task_id: str
    title: str
    status: str
    description: str = ""


@dataclass
class VibekanbanService:
    """Service for interacting with Vibekanban's MCP server.

    All operations fail gracefully - they log warnings but never raise exceptions.
    This ensures smithers continues working even if vibekanban is unavailable.
    """

    project_id: str | None = None
    enabled: bool = True

    def is_configured(self) -> bool:
        """Check if vibekanban is configured and enabled."""
        return self.enabled and self.project_id is not None

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the vibekanban MCP server.

        Args:
            tool_name: Name of the MCP tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool result as a dictionary, or empty dict on failure
        """
        server_params = StdioServerParameters(
            command="npx",
            args=["vibe-kanban@latest", "--mcp"],
        )

        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)

            # Extract text content from result
            for content in result.content:
                if hasattr(content, "text"):
                    text_value = str(content.text)
                    # Try to parse as JSON
                    try:
                        return json.loads(text_value)
                    except json.JSONDecodeError:
                        return {"text": text_value}

            return {}

    def create_task(
        self,
        title: str,
        description: str = "",
    ) -> str | None:
        """Create a task in vibekanban.

        Args:
            title: Task title
            description: Task description

        Returns:
            Task ID if successful, None otherwise.
        """
        if not self.is_configured():
            logger.debug("Vibekanban not configured, skipping task creation")
            return None

        try:
            result = asyncio.run(
                self._call_tool(
                    "create_task",
                    {
                        "project_id": self.project_id,
                        "title": title,
                        "description": description,
                    },
                )
            )
            task_id = result.get("task_id") or result.get("id")
            if task_id:
                logger.info(f"Created vibekanban task: {task_id}")
                return str(task_id)
            logger.warning(f"No task_id in vibekanban response: {result}")
            return None
        except Exception:
            logger.warning("Failed to create vibekanban task", exc_info=True)
            return None

    def update_task_status(
        self,
        task_id: str,
        status: str,
    ) -> bool:
        """Update a task's status.

        Args:
            task_id: The task ID
            status: New status (e.g., "in_progress", "completed", "failed")

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_configured() or not task_id:
            return False

        try:
            asyncio.run(
                self._call_tool(
                    "update_task",
                    {
                        "task_id": task_id,
                        "status": status,
                    },
                )
            )
            logger.info(f"Updated vibekanban task {task_id} status to {status}")
            return True
        except Exception:
            logger.warning(f"Failed to update vibekanban task {task_id}", exc_info=True)
            return False

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Get task information.

        Args:
            task_id: The task ID

        Returns:
            TaskInfo if successful, None otherwise.
        """
        if not self.is_configured() or not task_id:
            return None

        try:
            result = asyncio.run(
                self._call_tool(
                    "get_task",
                    {"task_id": task_id},
                )
            )
            return TaskInfo(
                task_id=result.get("id", task_id),
                title=result.get("title", ""),
                status=result.get("status", ""),
                description=result.get("description", ""),
            )
        except Exception:
            logger.warning(f"Failed to get vibekanban task {task_id}", exc_info=True)
            return None


def create_vibekanban_service() -> VibekanbanService:
    """Create a VibekanbanService from configuration.

    Loads configuration from ~/.smithers/config.json and environment variables.

    Returns:
        Configured VibekanbanService instance.
    """
    from smithers.services.config_loader import load_vibekanban_config

    config = load_vibekanban_config()
    return VibekanbanService(
        project_id=config.project_id,
        enabled=config.enabled,
    )
