"""GitHub Pages publish adapter — push static dist/ to a Pages branch via git.

Non-secret YAML fields: ``github_owner``, ``github_repo``, optional
``github_pages_branch`` (default ``gh-pages``), optional ``github_pages_cname``.
PAT: ZK vault ``PUBLISH_GITHUB_TOKEN:{site}`` or Deploy Grant via
``configure(password=)``. Agent never sees the token.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

import httpx

from services.publish_providers.base import PublishDeployError, PublishProvider

GITHUB_API = "https://api.github.com"
USER_AGENT = "PenCMS-Publish/1.0"
GIT_AUTHOR = "PenCMS Publish <publish@pencms.local>"
DEFAULT_BRANCH = "gh-pages"

# Match token material in remote URLs / stderr so we never leak PATs.
_TOKEN_IN_URL_RE = re.compile(
    r"(https?://)(?:x-access-token:|oauth2:|[^:@/\s]+:)([^@/\s]+)@",
    re.IGNORECASE,
)


def _scrub_secrets(text: str, token: str = "") -> str:
    """Redact PATs from git/HTTP error strings before surfacing to logs/UI."""
    out = text or ""
    if token:
        out = out.replace(token, "***")
    out = _TOKEN_IN_URL_RE.sub(r"\1***@", out)
    return out


def _api_error_message(resp: httpx.Response, token: str = "") -> str:
    try:
        data = resp.json()
        if isinstance(data, dict):
            msg = data.get("message") or data.get("error") or data.get("detail")
            if msg:
                return _scrub_secrets(str(msg), token)
    except Exception:  # noqa: BLE001
        pass
    text = (resp.text or "").strip()
    if text:
        return _scrub_secrets(text[:400], token)
    return f"HTTP {resp.status_code}"


def _public_url(owner: str, repo: str, cname: Optional[str]) -> str:
    if cname:
        host = cname.strip().rstrip("/")
        if host.lower().startswith("https://"):
            host = host[8:]
        elif host.lower().startswith("http://"):
            host = host[7:]
        host = host.split("/")[0].strip()
        if host:
            return f"https://{host}/"
    if repo.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io/"
    return f"https://{owner}.github.io/{repo}/"


def _copy_dist_into(dest: Path, dist_dir: Path) -> int:
    """Copy dist/ files into dest (archive-root paths). Returns file count."""
    count = 0
    for path in sorted(dist_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(dist_dir)
        rel_posix = rel.as_posix()
        if not rel_posix or rel_posix.startswith(".."):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


class GithubPagesPublishProvider(PublishProvider):
    """Publish static ``dist/`` to GitHub Pages via orphan-branch git push."""

    id = "github_pages"
    label = "GitHub Pages"
    enabled = True
    vault_http_alias = "X-Vault-Publish-Github-Token"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "incremental": False,
            "auth_methods": ["token"],
            "force_full": True,
        }

    def vault_key(self, site_id: str) -> Optional[str]:
        return f"PUBLISH_GITHUB_TOKEN:{site_id}"

    def yaml_fields(self) -> List[str]:
        return [
            "github_owner",
            "github_repo",
            "github_pages_branch",
            "github_pages_cname",
        ]

    def is_configured(self, block: Optional[Dict[str, Any]]) -> bool:
        if not block or not isinstance(block, dict):
            return False
        return bool(
            self._opt_str(block.get("github_owner"))
            and self._opt_str(block.get("github_repo"))
        )

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        owner = self._opt_str(payload.get("github_owner"))
        repo = self._opt_str(payload.get("github_repo"))
        if not owner:
            raise ValueError("github_owner is required for GitHub Pages")
        if not repo:
            raise ValueError("github_repo is required for GitHub Pages")
        branch = self._opt_str(payload.get("github_pages_branch")) or DEFAULT_BRANCH
        return {
            "github_owner": owner,
            "github_repo": repo,
            "github_pages_branch": branch,
            "github_pages_cname": self._opt_str(payload.get("github_pages_cname")),
        }

    def ui_schema(self) -> Dict[str, Any]:
        return {
            "fields": [
                {
                    "name": "github_owner",
                    "label": "Owner",
                    "type": "text",
                    "required": True,
                    "placeholder": "octocat",
                    "help": "GitHub user or organization that owns the repository.",
                },
                {
                    "name": "github_repo",
                    "label": "Repository",
                    "type": "text",
                    "required": True,
                    "placeholder": "my-site",
                    "help": "Repository name only (not owner/repo).",
                },
                {
                    "name": "github_pages_branch",
                    "label": "Pages branch",
                    "type": "text",
                    "required": False,
                    "placeholder": "gh-pages",
                    "help": "Branch PenCMS force-pushes (default gh-pages).",
                },
                {
                    "name": "github_pages_cname",
                    "label": "Custom domain (optional)",
                    "type": "text",
                    "required": False,
                    "placeholder": "www.example.com",
                    "help": "Written as a CNAME file on publish.",
                },
            ],
            "secret": {
                "label": "GitHub personal access token",
                "placeholder": "Enter GitHub personal access token",
                "help": (
                    "Create a fine-grained or classic PAT with Contents write "
                    "on the target repo. PenCMS stores it only in your "
                    "Zero-Knowledge vault (or a Deploy Grant for agents)."
                ),
                "create_url": "https://github.com/settings/tokens",
                "create_label": "Create personal access token",
                "create_hint": "Contents write on the target repo.",
                "http_alias": self.vault_http_alias,
            },
            "public_url_help": (
                "Usually filled after the first successful GitHub Pages publish "
                "(e.g. https://owner.github.io/repo/). Override if you use a "
                "custom domain."
            ),
            "auth_hint": (
                "Unlock the vault, confirm the GitHub PAT in Settings, "
                "then Test Connection."
            ),
        }

    def _api_token(self) -> str:
        key = (self._password or "").strip()
        if not key:
            from services.storage_provider import vault_secrets

            vault_key = f"PUBLISH_GITHUB_TOKEN:{self._site_id}"
            key = (vault_secrets.get().get(vault_key) or "").strip()
        if not key:
            raise PublishDeployError(
                f"GitHub PAT missing (PUBLISH_GITHUB_TOKEN:{self._site_id})"
            )
        return key

    def _owner(self) -> str:
        owner = (self._target.get("github_owner") or "").strip()
        if not owner:
            raise PublishDeployError("github_owner is required for GitHub Pages")
        return owner

    def _repo(self) -> str:
        repo = (self._target.get("github_repo") or "").strip()
        if not repo:
            raise PublishDeployError("github_repo is required for GitHub Pages")
        return repo

    def _branch(self) -> str:
        branch = (self._target.get("github_pages_branch") or "").strip() or DEFAULT_BRANCH
        return branch

    def _cname(self) -> Optional[str]:
        cname = (self._target.get("github_pages_cname") or "").strip()
        return cname or None

    def _auth_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }

    def _run_git(
        self,
        args: List[str],
        *,
        cwd: Path,
        token: str,
        env: Optional[Dict[str, str]] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run git; scrub PAT from any raised error text."""
        run_env = dict(os.environ)
        if env:
            run_env.update(env)
        # Avoid interactive prompts leaking secrets into logs.
        run_env.setdefault("GIT_TERMINAL_PROMPT", "0")
        try:
            return subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                env=run_env,
                capture_output=True,
                text=True,
                check=check,
                timeout=180,
            )
        except subprocess.CalledProcessError as e:
            combined = "\n".join(
                filter(
                    None,
                    [
                        e.stdout or "",
                        e.stderr or "",
                        str(e),
                    ],
                )
            )
            raise PublishDeployError(
                f"git {' '.join(args[:3])}… failed: "
                f"{_scrub_secrets(combined, token)[:600]}"
            ) from None
        except subprocess.TimeoutExpired as e:
            raise PublishDeployError(
                f"git timed out: {_scrub_secrets(str(e), token)}"
            ) from None

    async def test(self) -> Dict[str, Any]:
        """Probe PAT + repo by GET /repos/{owner}/{repo}."""
        started = time.monotonic()
        try:
            token = self._api_token()
            owner = self._owner()
            repo = self._repo()
        except PublishDeployError as e:
            return {"success": False, "error": str(e)}

        url = (
            f"{GITHUB_API}/repos/"
            f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=self._auth_headers(token))
            latency_ms = int((time.monotonic() - started) * 1000)
            if resp.status_code >= 400:
                return {
                    "success": False,
                    "latency_ms": latency_ms,
                    "error": _api_error_message(resp, token),
                }
            return {"success": True, "latency_ms": latency_ms}
        except httpx.HTTPError as e:
            return {
                "success": False,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "error": f"GitHub request failed: {_scrub_secrets(str(e), token)}",
            }

    async def deploy(
        self,
        dist_dir: Path,
        *,
        force_full: bool,
        upload_rels: List[str],
        removed: List[str],
        total_files: int,
        log_line: Callable[[str], None],
        set_phase: Optional[Callable[[str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Orphan-commit dist/ onto the Pages branch and force-push."""
        _ = force_full, upload_rels, removed, total_files  # full tree always
        if set_phase:
            set_phase("uploading")

        token = self._api_token()
        owner = self._owner()
        repo = self._repo()
        branch = self._branch()
        cname = self._cname()

        if not dist_dir.is_dir():
            raise PublishDeployError(f"dist_dir missing: {dist_dir}")

        log_line(
            f"GitHub Pages pushing dist/ to {owner}/{repo}@{branch}…"
        )

        # Remote URL embeds the PAT; never write it to logs.
        remote_url = (
            f"https://x-access-token:{token}@github.com/"
            f"{quote(owner, safe='')}/{quote(repo, safe='')}.git"
        )
        safe_remote = f"https://github.com/{owner}/{repo}.git"

        work = Path(tempfile.mkdtemp(prefix="pencms-gh-pages-"))
        try:
            count = _copy_dist_into(work, dist_dir)
            if count == 0:
                raise PublishDeployError("dist/ has no files to publish")

            if cname:
                (work / "CNAME").write_text(cname.strip() + "\n", encoding="utf-8")
                log_line(f"GitHub Pages writing CNAME → {cname.strip()}")

            git_env = {
                "GIT_AUTHOR_NAME": "PenCMS Publish",
                "GIT_AUTHOR_EMAIL": "publish@pencms.local",
                "GIT_COMMITTER_NAME": "PenCMS Publish",
                "GIT_COMMITTER_EMAIL": "publish@pencms.local",
            }

            self._run_git(["init"], cwd=work, token=token, env=git_env)
            self._run_git(
                ["checkout", "--orphan", branch],
                cwd=work,
                token=token,
                env=git_env,
            )
            self._run_git(["add", "-A"], cwd=work, token=token, env=git_env)
            # Allow empty? Pages needs at least one file; we already checked count.
            self._run_git(
                [
                    "commit",
                    "-m",
                    f"Publish site {self._site_id or 'site'} ({count} files)",
                    f"--author={GIT_AUTHOR}",
                ],
                cwd=work,
                token=token,
                env=git_env,
            )
            self._run_git(
                ["remote", "add", "origin", remote_url],
                cwd=work,
                token=token,
                env=git_env,
            )
            log_line(f"GitHub Pages force-pushing orphan branch to {safe_remote}…")
            self._run_git(
                ["push", "--force", "origin", f"HEAD:{branch}"],
                cwd=work,
                token=token,
                env=git_env,
            )
        finally:
            shutil.rmtree(work, ignore_errors=True)

        public_url = _public_url(owner, repo, cname)
        log_line(f"GitHub Pages live at {public_url}")
        return {"public_url": public_url.rstrip("/")}
