# Vibekanban Integration

Smithers integrates with [Vibekanban](https://vibekanban.com/) to track Claude sessions as tasks in a kanban UI. This is enabled by default and requires no configuration.

## Zero Configuration

On first run, smithers will:

1. Auto-discover your vibekanban project
2. Save the project ID to `~/.smithers/config.json` for future runs

To list available projects:

```bash
smithers projects
```

## Manual Configuration (Optional)

If you have multiple projects and want to specify which one to use:

```json
{
  "vibekanban": {
    "project_id": "your-project-id"
  }
}
```

Or use an environment variable:

```bash
export SMITHERS_VIBEKANBAN_PROJECT_ID=your-project-id
```

To disable vibekanban integration:

```bash
export SMITHERS_VIBEKANBAN_ENABLED=false
```

### Fixed Port Configuration

By default, smithers runs vibe-kanban on port 8080. To use a different fixed port:

```json
{
  "vibekanban": {
    "port": 9000
  }
}
```

Or use an environment variable:

```bash
export SMITHERS_VIBEKANBAN_PORT=9000
```

The backend API runs on `port + 1` (e.g., port 9001 if the UI is on 9000).

## How It Works

Smithers creates a **separate vibekanban task for each Claude Code session**:

- **Implement mode**: One task per stage (e.g., `[impl] Stage 1: Add models`)
- **Fix mode**: One task per PR (e.g., `[fix] PR #123: feature-branch`)

Each task is:
1. **Found or created** when the Claude session starts (existing tasks are reused)
2. **Set to "in_progress"** while running
3. **Linked to the PR** when available (PR URL is attached to the task)
4. **Marked as "completed"** when the session succeeds
5. **Marked as "failed"** if the session fails

### Task Reuse

Smithers automatically reuses existing vibekanban tasks to avoid duplicates:

- Before creating a new task, smithers searches for an existing task with the same title
- If found, the existing task is reused and its status is updated to "in_progress"
- This prevents duplicate tasks when fix mode runs multiple iterations

### Skip When No Fixes Needed

In fix mode, vibekanban tasks are only created when there is actual work to do:

- Tasks are skipped if there are 0 unresolved comments AND 0 CI failures
- This keeps the kanban board clean by not tracking trivial iterations

This allows you to monitor individual Claude sessions in real-time through the vibekanban UI, with direct links to the associated PRs.

## Cleanup

To delete all smithers-created tasks from vibekanban:

```bash
smithers cleanup
```

This finds and removes all tasks with `[impl]` or `[fix]` prefixes across all statuses.

## Requirements

- Vibekanban must be installed: `npx vibe-kanban`
