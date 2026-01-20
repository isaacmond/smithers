"""Fix phase prompt templates for PR review comments and CI failures."""

from pathlib import Path

from smithers.prompts.templates import (
    MERGE_CONFLICT_SECTION,
    POST_PR_WORKFLOW_SECTION,
    QUALITY_CHECKS_SECTION,
    SELF_HEALING_SECTION,
    STACKED_PR_BRANCH_SECTION,
    STRICT_JSON_SECTION,
    render_template,
)

FIX_PLANNING_PROMPT_TEMPLATE = """You are creating a fix plan to address incomplete implementation, review comments, CI/CD failures and merge issues on pull requests.
{design_doc_section}{original_todo_section}
## PRs to Process
{pr_numbers}

## Your Task
1. **Check implementation completeness** (if Original Implementation TODO is provided above):
   - Review the PR diffs to see what was actually implemented
   - Compare against the design document and original TODO items
   - Identify any features, functionality, or requirements that are missing or incomplete
   - Note which PR should contain each missing item

2. Fetch ALL comments from each PR using the GitHub CLI:
   - gh pr view <pr_number> --json reviewThreads,comments
   - Use GraphQL to get detailed thread info including resolution status
   - **IMPORTANT**: PRs have TWO types of comments that MUST both be addressed:
     a) **Review thread comments** (line-level): Found in `reviewThreads`, tied to specific file/line, have `isResolved` status
     b) **General PR comments** (PR-level): Found in `comments`, NOT tied to specific lines, do NOT have `isResolved` status
   - Both types MUST be fetched and included in the TODO if unresolved

3. Check CI/CD status for each PR:
   - gh pr checks <pr_number>
   - NEVER wait for CI/CD. If checks are running or pending, assume they PASSED.
   - If any checks are failing, get the failure details:
     - gh run list --branch <branch_name> --limit 1
     - gh run view <run_id> --log-failed
   - Extract the specific test failures, lint errors, or type check errors

4. Check for merge conflicts in each PR

5. Create a TODO file at: {todo_file_path}

The TODO file should have this structure:

```markdown
# Review Fixes: [Feature Name]

## Overview
Addressing incomplete implementation, review comments and CI/CD failures on PRs: {pr_numbers}

## Incomplete Implementation Items
[List any items from the design doc or original TODO that are missing or incomplete]

### Missing: [Brief description]
- **Status**: pending
- **From**: [Design doc / Original TODO stage X]
- **Target PR**: #[which PR should contain this]
- **Details**: [What specifically needs to be implemented]
- **Action required**: [What code changes are needed]

[... more missing items as needed ...]

## PR #[number]: [PR title]

### CI/CD Failures (if any)
- **Status**: pending
- **Check name**: [e.g., tests, lint, type-check]
- **Error summary**: [Brief description of what's failing]
- **Error details**:
  ```
  [Actual error output from the logs]
  ```
- **Files affected**: [file paths if identifiable]
- **Action required**: [What needs to be fixed]

### Review Comment 1: [Brief summary of the comment]
- **Status**: pending
- **Type**: review_thread (line-level)
- **Author**: [reviewer name]
- **File**: [file path and line number]
- **Comment**: [The actual review comment text]
- **Action required**: [What needs to be done to address this]

[... more review thread comments as needed ...]

### General Comment 1: [Brief summary of the comment]
- **Status**: pending
- **Type**: general (PR-level)
- **Author**: [commenter name]
- **Comment**: [The actual comment text]
- **Action required**: [What needs to be done to address this]

[... more general PR comments as needed ...]

## PR #[next number]: [PR title]
[... CI failures and comments for this PR ...]

## Notes
[Any additional notes about dependencies between fixes or overall approach]
```

### Guidelines
- Check implementation completeness FIRST - missing functionality is highest priority
- Then check CI/CD status - failing tests/lint/type-checks are next priority
- Include specific error messages and stack traces from CI logs
- **Include BOTH types of unresolved comments:**
  - **Review thread comments** (line-level): Skip only if `isResolved == true`
  - **General PR comments** (PR-level): Include ALL unless they contain [RESOLVED] or start with [CLAUDE]
- Skip any comment that contains [RESOLVED] or starts with [CLAUDE]
- Group by PR, with incomplete items and CI failures listed before review comments
- List review thread comments first, then general PR comments
- Be specific about what action is needed for each item

### Output (CRITICAL - Valid JSON Required)
After creating the TODO file, output the following JSON block at the END of your response.
You MUST output valid, parseable JSON. All fields are required.

---JSON_OUTPUT---
{{
  "todo_file_created": "{todo_file_path}",
  "num_incomplete_items": <number of missing/incomplete implementation items>,
  "num_comments": <total number of unresolved comments across all PRs>,
  "num_ci_failures": <total number of failing CI checks across all PRs>,
  "error": null
}}
---END_JSON---

If you encounter an error, still output JSON:

---JSON_OUTPUT---
{{
  "todo_file_created": null,
  "num_incomplete_items": 0,
  "num_comments": 0,
  "num_ci_failures": 0,
  "error": "<description of what went wrong>"
}}
---END_JSON---

## Begin
Check implementation completeness, fetch PR comments, check CI status, and create the fix plan."""


FIX_PROMPT_TEMPLATE = """You are addressing review comments on PR #{pr_number}.

## IMPORTANT: You are working in a Git Worktree
- Worktree path: {worktree_path}
- Branch: {branch}
- PR Number: {pr_number}
- This is an isolated worktree, not the main repository
- All git operations are already scoped to this branch
{design_doc_section}{original_todo_section}
## Implementation Plan (TODO)
Location: {todo_file_path}

{todo_content}

## Your Task
Address all issues for PR #{pr_number}.
{self_healing_section}
**CRITICAL**: You MUST complete ALL steps below, even if there are 0 comments to address.
The fix process is not complete until:
1. Base branch is merged in (origin/main)
2. All merge conflicts are resolved
3. All CI/CD checks pass
4. All unresolved comments are addressed (if any)

### 1. Update Branch FIRST (ALWAYS REQUIRED - EVEN WITH 0 COMMENTS)
- You are already on branch '{branch}' in a worktree
- Fetch latest: git fetch origin
- Pull latest changes: git pull --rebase origin {branch}
- **ALWAYS rebase onto origin/main**: git rebase origin/main
- **IMMEDIATELY RESOLVE ALL REBASE CONFLICTS** if any occur (see Stacked PR Branch Management below)
- After resolving, run bin/run_lint.sh and bin/run_type_check.sh to verify
- Push with: git push --force-with-lease
- **This step is MANDATORY even if there are no review comments**

### 2. Check CI/CD Status (HIGHEST PRIORITY)
- Use: gh pr checks {pr_number}
- NEVER wait for CI/CD. If checks are running or pending, assume they PASSED.
- If ANY checks are failing:
  - Get the run ID: gh run list --branch {branch} --limit 1
  - View failure logs: gh run view <run_id> --log-failed
  - Identify the EXACT errors (test failures, lint errors, type errors)
  - These MUST be fixed before anything else

### 3. Fix ALL CI/CD Failures
If CI is failing, you MUST fix it:
- Read the error messages carefully from the TODO file or fetch fresh logs
- Fix test failures by correcting the code or updating tests
- Fix lint errors by reformatting or fixing style issues
- Fix type errors by correcting type annotations or logic
- Run local checks to verify (e.g. lint, type check, test)
- Commit and push the fixes
- Verify CI passes before moving to review comments

### 4. Fetch PR Details and ALL Comments
- Use gh CLI to get PR info: `gh pr view {pr_number} --json reviewThreads,comments`
- Use GraphQL API to check which review threads are resolved vs unresolved
- **IMPORTANT**: PRs have TWO types of comments that MUST both be addressed:
  a) **Review thread comments** (line-level): Found in `reviewThreads`, tied to specific file/line, have `isResolved` status
  b) **General PR comments** (PR-level): Found in `comments`, NOT tied to specific lines, do NOT have `isResolved` status

### 5. Identify Unresolved Comments (BOTH TYPES)
**For review thread comments (line-level):**
- Skip if `isResolved == true`
- Skip if comment body contains [RESOLVED]
- Skip if comment body starts with [CLAUDE]

**For general PR comments (PR-level):**
- These do NOT have `isResolved` status - address ALL of them unless:
- Skip if comment body contains [RESOLVED]
- Skip if comment body starts with [CLAUDE]

### 6. Address EVERY Unresolved Comment of BOTH Types (if any exist)
You MUST reply to EVERY single unresolved comment. No exceptions.
This includes BOTH review thread comments AND general PR comments.

For each comment:
- **Code change requests**: Make the fix, then reply confirming
- **Questions**: Answer based on your understanding
- **Suggestions you disagree with**: Explain your reasoning politely
- **Unclear comments**: Ask for clarification
- **Cursor Bugbot comments**: Address the issue or explain why not applicable

### 7. How to Reply
- For **review thread comments**: Use `gh api` to reply to the review thread
- For **general PR comments**: Use `gh pr comment {pr_number} --body "[CLAUDE] ..."`
- ALWAYS prefix replies with [CLAUDE] so reviewers know it's automated

### 8. Resolve Threads When Appropriate
- For **review thread comments**: Use the GitHub GraphQL API to resolve the thread after addressing
- For **general PR comments**: No resolution needed (just reply with [CLAUDE] prefix)

{update_design_doc_section}
### 10. Run post-PR quality workflow (see Post-PR Code Quality Workflow section below)
{post_pr_workflow_section}
{quality_checks_section}
### 11. Commit and Push
- Commit with descriptive message
- Push to the branch

### 12. Verify CI/CD Status After Push
After pushing, verify CI/CD status:
- Use: gh pr checks {pr_number}
- NEVER wait for CI/CD. If checks are running or pending, assume they PASSED.
- If any checks are FAILING, fix them
{stacked_pr_branch_section}
{merge_conflict_section}
{strict_json_section}
## Output Format
After processing PR #{pr_number}, output the following JSON block at the END of your response.
If CI/CD is running or pending, treat it as passed and set `ci_status` to "passing".

---JSON_OUTPUT---
{{
  "pr_number": {pr_number},
  "base_branch_rebased": <true if successfully rebased onto origin/main, false otherwise>,
  "rebase_conflicts": "<none|resolved|unresolved>",
  "unresolved_before": <count of ALL unresolved comments before processing (BOTH review thread AND general PR comments)>,
  "addressed": <count of ALL comments addressed (BOTH types)>,
  "ci_status": "<passing|failing>",
  "done": <true ONLY if all conditions below are met>,
  "error": null
}}
---END_JSON---

**IMPORTANT**: `done` can ONLY be true if ALL of the following are satisfied:
- Branch has been rebased onto origin/main
- There are NO unresolved rebase conflicts
- There are ZERO unresolved comments of EITHER type (review thread comments AND general PR comments)
- CI status is "passing"

If you fail after 5 retry attempts, output:

---JSON_OUTPUT---
{{
  "pr_number": {pr_number},
  "base_branch_rebased": false,
  "rebase_conflicts": "unresolved",
  "unresolved_before": <count>,
  "addressed": 0,
  "ci_status": "failing",
  "done": false,
  "error": "<description of what went wrong after 5 attempts>"
}}
---END_JSON---

## Begin
Process PR #{pr_number} now."""


def render_fix_planning_prompt(
    design_doc_path: Path | None,
    design_content: str | None,
    original_todo_content: str | None,
    pr_numbers: list[int],
    todo_file_path: Path,
) -> str:
    """Render the fix planning prompt.

    Args:
        design_doc_path: Path to the design document, or None if not provided
        design_content: Content of the design document, or None if not provided
        original_todo_content: Content of the original implementation TODO (from implement phase)
        pr_numbers: List of PR numbers to process
        todo_file_path: Path where the TODO file should be created

    Returns:
        The rendered prompt string
    """
    pr_numbers_str = " ".join(str(n) for n in pr_numbers)
    design_doc_section = _render_design_doc_section(design_doc_path, design_content)
    original_todo_section = _render_original_todo_section(original_todo_content)
    return render_template(
        FIX_PLANNING_PROMPT_TEMPLATE,
        design_doc_section=design_doc_section,
        original_todo_section=original_todo_section,
        pr_numbers=pr_numbers_str,
        todo_file_path=todo_file_path,
    )


def _render_design_doc_section(design_doc_path: Path | None, design_content: str | None) -> str:
    """Render the design document section.

    Args:
        design_doc_path: Path to the design document, or None if not provided
        design_content: Content of the design document, or None if not provided

    Returns:
        The rendered section string, or empty string if no design doc
    """
    if not design_doc_path or not design_content:
        return ""
    return f"""
## Design Document
Location: {design_doc_path}

{design_content}
"""


def _render_update_design_doc_section(design_doc_path: Path | None) -> str:
    """Render the update design document instruction section.

    Args:
        design_doc_path: Path to the design document, or None if not provided

    Returns:
        The rendered section string, or a note to skip if no design doc
    """
    if not design_doc_path:
        return """### 9. Update Design Document If Implementation Diverges
(No design document was provided - skip this step)

"""
    return f"""### 9. Update Design Document If Implementation Diverges
If PR comments or feedback have led you to implement something differently than what was originally specified in the design document:
- **Update the design document** at {design_doc_path} to reflect the actual implementation
- This keeps the design doc accurate and prevents future confusion
- Add a brief note explaining why the change was made (e.g., "Updated to use X instead of Y based on PR feedback for better Z")
- This is REQUIRED whenever the implementation differs from the original design

"""


def _render_original_todo_section(original_todo_content: str | None) -> str:
    """Render the original implementation TODO section.

    Args:
        original_todo_content: Content of the original implementation TODO, or None

    Returns:
        The rendered section string, or empty string if no original todo
    """
    if not original_todo_content:
        return ""
    return f"""
## Original Implementation TODO (from implement phase)

{original_todo_content}
"""


def render_fix_prompt(
    pr_number: int,
    branch: str,
    worktree_path: Path,
    design_doc_path: Path | None,
    design_content: str | None,
    original_todo_content: str | None,
    todo_file_path: Path,
    todo_content: str,
) -> str:
    """Render the fix prompt for a specific PR.

    Args:
        pr_number: The PR number to fix
        branch: The branch name for this PR
        worktree_path: Path to the worktree
        design_doc_path: Path to the design document, or None if not provided
        design_content: Content of the design document, or None if not provided
        original_todo_content: Content of the original implementation TODO (from implement phase)
        todo_file_path: Path to the TODO file
        todo_content: Content of the TODO file

    Returns:
        The rendered prompt string
    """
    design_doc_section = _render_design_doc_section(design_doc_path, design_content)
    original_todo_section = _render_original_todo_section(original_todo_content)
    update_design_doc_section = _render_update_design_doc_section(design_doc_path)
    return render_template(
        FIX_PROMPT_TEMPLATE,
        pr_number=pr_number,
        branch=branch,
        worktree_path=worktree_path,
        design_doc_section=design_doc_section,
        original_todo_section=original_todo_section,
        update_design_doc_section=update_design_doc_section,
        todo_file_path=todo_file_path,
        todo_content=todo_content,
        merge_conflict_section=MERGE_CONFLICT_SECTION,
        post_pr_workflow_section=POST_PR_WORKFLOW_SECTION,
        quality_checks_section=QUALITY_CHECKS_SECTION,
        self_healing_section=SELF_HEALING_SECTION,
        stacked_pr_branch_section=STACKED_PR_BRANCH_SECTION.format(base_branch="main"),
        strict_json_section=STRICT_JSON_SECTION,
    )
