"""Plan and publish immutable, version-file-driven GitHub releases."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def run(*args):
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def semver(value):
    match = re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?", value
    )
    if not match:
        raise ValueError(f"Invalid release version: {value}")
    pre = match[4]
    parts = []
    if pre is not None:
        for part in pre.split("."):
            if not part or (part.isdigit() and len(part) > 1 and part.startswith("0")):
                raise ValueError(f"Invalid prerelease: {value}")
            parts.append((0, int(part)) if part.isdigit() else (1, part))
    return (*map(int, match.group(1, 2, 3)), pre is None, tuple(parts))


def decide(version, sha, tags, releases):
    """Skip published versions, recover same-commit attempts, reject downgrades."""
    current = semver(version)
    tag = f"v{version}"
    existing = next((item for item in releases if item["tag_name"] == tag), None)
    if existing:
        if (
            existing["draft"]
            or existing["prerelease"] != ("-" in version)
            or tag not in tags
        ):
            raise ValueError(
                f"Release {tag} has inconsistent state; resolve it before retrying"
            )
        return False
    if tag in tags and tags[tag] != sha:
        raise ValueError(f"Tag {tag} belongs to another commit; never overwrite it")
    for other in tags:
        try:
            newer = semver(other.removeprefix("v")) > current
        except ValueError:
            continue
        if newer:
            raise ValueError(f"Refusing to publish {tag} behind newer tag {other}")
    return True


def context(version_file):
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Releases must run from main")
    path = Path(version_file)
    version = (
        json.loads(path.read_text())["version"]
        if path.suffix == ".json"
        else path.read_text().strip()
    )
    semver(version)
    notes = Path(f"docs/releases/{version}.md")
    if not notes.is_file() or not notes.read_text(encoding="utf-8").strip():
        raise ValueError(f"Missing release notes: {notes}")
    sha = os.environ["GITHUB_SHA"]
    if run("git", "rev-parse", "HEAD") != sha:
        raise ValueError("Checkout does not match the workflow commit")
    repo = os.environ["GITHUB_REPOSITORY"]
    # Fetch errors and API failures are fatal, never interpreted as 'not released'.
    run("git", "fetch", "origin", "--tags")
    tags = {
        tag: run("git", "rev-list", "-n", "1", tag)
        for tag in run("git", "tag", "--list").splitlines()
    }
    pages = json.loads(
        run("gh", "api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100")
    )
    releases = [release for page in pages for release in page]
    publish = decide(version, sha, tags, releases)
    return version, sha, repo, notes, tags, publish


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "tag", "publish"])
    parser.add_argument("--version-file", required=True)
    parser.add_argument("--title", default="Route Progress")
    args = parser.parse_args()
    version, sha, repo, notes, tags, publish = context(args.version_file)
    tag = f"v{version}"
    if args.command == "plan":
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(
                f"version={version}\npublish={str(publish).lower()}\nprerelease={str('-' in version).lower()}\n"
            )
        print(f"{'Publish' if publish else 'Already published; skip'} {tag}")
        return
    if not publish:
        if args.command == "tag":
            raise ValueError(
                "Release was published after planning; stop before rebuilding its image"
            )
        print(f"Already published; leaving {tag} unchanged")
        return
    if tag not in tags:
        # Reserve the exact commit before uploading versioned images. A failed
        # publication can resume at this commit, never overwrite a different one.
        run(
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{repo}/git/refs",
            "-f",
            f"ref=refs/tags/{tag}",
            "-f",
            f"sha={sha}",
        )
    if args.command == "tag":
        return
    run(
        "gh",
        "release",
        "create",
        tag,
        "--repo",
        repo,
        "--verify-tag",
        "--title",
        f"{args.title} v{version}",
        "--notes-file",
        str(notes),
        *(["--prerelease", "--latest=false"] if "-" in version else ["--latest"]),
    )
    release = json.loads(run("gh", "api", f"repos/{repo}/releases/tags/{tag}"))
    if release["draft"] or release["prerelease"] != ("-" in version):
        raise ValueError("Published release does not have the expected visibility")
    print(release["html_url"])


if __name__ == "__main__":
    main()
