"""Normalized local Git provenance for authoritative replay artifacts."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


FULL_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class LocalGitRepositoryError(ValueError):
    pass


def _git(repository_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repository_path,
            text=True,
            capture_output=True,
            check=check,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise LocalGitRepositoryError("LOCAL_GIT_REPOSITORY_UNREADABLE") from error


def read_local_git_repository_state(repository_path: Path | str) -> dict[str, Any]:
    """Read executable source identity without consulting a remote repository."""
    requested_path = Path(repository_path).resolve()
    inside = _git(requested_path, "rev-parse", "--is-inside-work-tree").stdout.strip()
    if inside != "true":
        raise LocalGitRepositoryError("LOCAL_GIT_REPOSITORY_UNREADABLE")
    root = Path(_git(requested_path, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    branch_result = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch_result.returncode == 0:
        branch = branch_result.stdout.strip()
        detached = False
    elif branch_result.returncode == 1:
        branch = None
        detached = True
    else:
        raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
    tracked_status = _git(root, "status", "--porcelain=v1", "--untracked-files=no").stdout
    return normalize_local_git_repository_state({
        "git_commit": commit,
        "git_branch": branch,
        "git_worktree_clean": not tracked_status.strip(),
        "git_detached_head": detached,
        "git_repository_path": str(root),
        "git_remote_name": None,
    }, root)


def normalize_local_git_repository_state(
    state: Mapping[str, Any],
    repository_path: Path | str,
) -> dict[str, Any]:
    commit = state.get("git_commit")
    if not isinstance(commit, str) or not commit:
        raise LocalGitRepositoryError("LOCAL_GIT_COMMIT_MISSING")
    if not FULL_GIT_SHA_RE.fullmatch(commit):
        raise LocalGitRepositoryError("LOCAL_GIT_COMMIT_MALFORMED")
    detached = state.get("git_detached_head")
    if not isinstance(detached, bool):
        raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
    branch = state.get("git_branch")
    if detached:
        if branch not in (None, "DETACHED_HEAD"):
            raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
        branch = None
    elif not isinstance(branch, str) or not branch.strip() or branch == "HEAD":
        raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
    clean = state.get("git_worktree_clean")
    if not isinstance(clean, bool):
        raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
    remote_name = state.get("git_remote_name")
    if remote_name is not None and (not isinstance(remote_name, str) or not remote_name.strip()):
        raise LocalGitRepositoryError("LOCAL_GIT_STATE_AMBIGUOUS")
    observed_path = state.get("git_repository_path") or repository_path
    return {
        "git_commit": commit.lower(),
        "git_branch": branch.strip() if isinstance(branch, str) else None,
        "git_worktree_clean": clean,
        "git_detached_head": detached,
        "git_repository_path": str(Path(observed_path).resolve()),
        "git_remote_name": remote_name.strip() if isinstance(remote_name, str) else None,
    }


def require_expected_local_git_state(
    state: Mapping[str, Any],
    expected_git_commit: str,
) -> dict[str, Any]:
    if not isinstance(expected_git_commit, str) or not expected_git_commit:
        raise LocalGitRepositoryError("EXPECTED_GIT_COMMIT_MISSING")
    if not FULL_GIT_SHA_RE.fullmatch(expected_git_commit):
        raise LocalGitRepositoryError("EXPECTED_GIT_COMMIT_MALFORMED")
    normalized = dict(state)
    if normalized["git_commit"] != expected_git_commit.lower():
        raise LocalGitRepositoryError("LOCAL_GIT_HEAD_MISMATCH")
    if normalized["git_worktree_clean"] is not True:
        raise LocalGitRepositoryError("LOCAL_GIT_TRACKED_WORKTREE_DIRTY")
    return normalized


def authoritative_git_binding(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "git_commit": state["git_commit"],
        "git_branch": state["git_branch"],
        "git_worktree_clean": state["git_worktree_clean"],
        "git_detached_head": state["git_detached_head"],
    }
