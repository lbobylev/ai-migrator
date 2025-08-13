from typing import Any, List, Mapping
from github import Github
import os
import json

from app_types import GithubIssue


def to_github_issue(d: Mapping[str, Any]) -> GithubIssue:
    return {
        "number": int(d["number"]),
        "title": str(d.get("title") or ""),
        "body": str(d.get("body") or ""),
    }


def get_tasks_repo():
    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = next(
        (
            repo
            for repo in g.get_user().get_repos()
            if repo.name == "surge-tasks-reports"
        ),
        None,
    )
    if not repo:
        raise ValueError("Repository 'surge-tasks-reports' not found.")
    return repo


def get_issues() -> List[GithubIssue]:
    issues = []
    if os.path.exists("issues.json"):
        with open("issues.json", "r") as f:
            issues = json.load(f)
    else:
        repo = get_tasks_repo()
        xs = repo.get_issues(state="open", labels=["ams"])
        for issue in xs:
            issues.append(issue.raw_data)

    return [to_github_issue(issue) for issue in issues]


def get_issue(number: int) -> GithubIssue:
    repo = get_tasks_repo()
    issue = repo.get_issue(number)
    return to_github_issue(issue.raw_data)
