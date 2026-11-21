"""Workspace-scoped tools and bounded public literature retrieval."""
from difflib import unified_diff
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import NamedTemporaryFile
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from smolagents import tool

from .state import BudgetReached, scrub

HOSTS = {
    "api.crossref.org", "doi.org", "arxiv.org", "export.arxiv.org",
    "epubs.siam.org", "pubs.aip.org", "pubs.acs.org", "pubs.rsc.org", "link.aps.org",
    "math.berkeley.edu", "michael-herbst.com", "pyscf.org",
    "lab409chem.ccu.edu.tw",
}
TEXT_LIMIT = 14000
DOWNLOAD_LIMIT = 6_000_000


def check_url(url):
    parts = urlparse(url)
    if (parts.scheme != "https" or parts.hostname not in HOSTS
            or parts.username or parts.password or parts.port not in (443, None)):
        raise ValueError(f"Public HTTPS host {parts.hostname!r} is outside the scholarly allowlist. "
                         "Try an arXiv full-text URL or an allowed author-hosted manuscript.")


class ScholarlyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "noscript", "head"}:
            self.hidden.append(tag)
        if not self.hidden and tag in {"h1", "h2", "h3", "p", "li", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self):
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def allowed_path(root, path, scopes):
    candidate = Path(path)
    if (candidate.is_absolute() or candidate.drive or ".." in candidate.parts
            or any(":" in part or part.rstrip(" .") != part for part in candidate.parts)):
        raise ValueError("Use an allowed relative project path.")
    target = (root / candidate).resolve()
    relative = target.relative_to(root)
    for part in relative.parts:
        if part.startswith(".") or "secret" in part.casefold() or "credential" in part.casefold():
            raise ValueError("Hidden or credential-related paths are excluded.")
    name = relative.as_posix()
    if not any(name.startswith(scope) if scope.endswith("/") else name == scope for scope in scopes):
        raise ValueError("Path is outside the configured scope.")
    return target, name


def make_tools(root, run):
    permissions = run.config["permissions"]
    sources = run.state.setdefault("sources", {})

    def fetch(url):
        check_url(url)
        request = Request(url, headers={"User-Agent": "KSAgent/0.2 scholarly research"})
        with build_opener(ScholarlyRedirects()).open(request, timeout=run.timeout(18)) as reply:
            deadline = monotonic() + run.timeout(18)
            chunks = bytearray()
            while len(chunks) <= DOWNLOAD_LIMIT:
                if monotonic() >= deadline:
                    raise TimeoutError("Source body deadline exceeded.")
                chunk = reply.read1(min(65536, DOWNLOAD_LIMIT + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            if len(chunks) > DOWNLOAD_LIMIT:
                raise ValueError("Source download exceeds the size limit.")
            return bytes(chunks), reply.geturl(), reply.headers.get_content_type()

    def invoke(name, arguments, action):
        run.log("tool_start", name=name, arguments=arguments)
        try:
            run.timeout(1)
            result = {"ok": True, **action()}
        except HTTPError as error:
            result = {"ok": False, "error_type": type(error).__name__,
                      "http_status": error.code, "url": error.url, "error": str(error)[:700]}
        except (ValueError, OSError, subprocess.SubprocessError, BudgetReached) as error:
            result = {"ok": False, "error_type": type(error).__name__, "error": str(error)[:700]}
        result = scrub(result)
        public_result = dict(result)
        if name == "read_source":
            public_result.pop("excerpt", None)
        run.observe(name, arguments, public_result)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def search_literature(query: str) -> str:
        """Search Crossref bibliography using a query generated for the research question.

        Args:
            query: Search phrase containing at most 240 characters.
        """
        def action():
            if not 3 <= len(query.strip()) <= 240:
                raise ValueError("Query length must be 3 to 240 characters.")
            url = "https://api.crossref.org/works?" + urlencode({
                "query.bibliographic": query, "rows": 5, "select": "DOI,title,published,URL",
            })
            body, resolved, _ = fetch(url)
            items = []
            for item in json.loads(body)["message"]["items"]:
                record = {"doi": item["DOI"], "title": next(iter(item.get("title", [])), ""),
                          "url": item.get("URL", ""), "published": item.get("published", {})}
                items.append(record)
            return {"url": resolved, "http_status": 200, "scope": "bibliographic metadata", "items": items}

        return invoke("search_literature", {"query": query}, action)

    @tool
    def read_source(url: str, focus: str) -> str:
        """Read public primary text from arXiv, RSC, or another supported scholarly host. HTML focus matches a text phrase.

        Args:
            url: Public HTTPS paper, preprint, DOI, or official documentation URL.
            focus: Phrase to locate in HTML or description of the evidence sought in PDF.
        """
        def action():
            data, resolved, media = fetch(url)
            if media == "application/pdf" or data.startswith(b"%PDF-"):
                executable = shutil.which("pdftotext")
                if not executable:
                    raise OSError("pdftotext unavailable. Try an HTML manuscript.")
                source = run.directory / "source.tmp.pdf"
                try:
                    source.write_bytes(data)
                    result = subprocess.run([executable, "-f", "1", "-l", "4", "-enc", "UTF-8",
                                             str(source), "-"], capture_output=True,
                                            timeout=run.timeout(15), check=True)
                finally:
                    source.unlink(missing_ok=True)
                excerpt = result.stdout.decode("utf-8", errors="replace")[:TEXT_LIMIT]
                scope = f"PDF pages 1–4, first {len(excerpt)} extracted characters"
            else:
                parser = ArticleText()
                parser.feed(data.decode("utf-8", errors="replace"))
                content = parser.text()
                position = content.casefold().find(focus.strip().casefold()) if focus.strip() else -1
                start = max(0, position - 1200) if position >= 0 else 0
                excerpt = content[start:start + TEXT_LIMIT]
                scope = f"HTML text offsets {start}–{start + len(excerpt)}"
            if not excerpt.strip():
                raise ValueError("No readable text returned.")
            excerpt = scrub(excerpt)
            source_id = hashlib.sha256(resolved.encode()).hexdigest()[:12]
            digest = hashlib.sha256(excerpt.encode()).hexdigest()
            cache = root / ".scratch" / "source-cache"
            cache.mkdir(parents=True, exist_ok=True)
            (cache / digest).write_bytes(excerpt.encode("utf-8"))
            sources[source_id] = {"url": resolved, "scope": scope, "excerpt_sha256": digest}
            return {"requested_url": url, "url": resolved, "scope": scope, "http_status": 200,
                    "source_id": source_id, "excerpt_sha256": digest,
                    "excerpt": excerpt}

        return invoke("read_source", {"url": url, "focus": focus}, action)

    @tool
    def read_file(path: str) -> str:
        """Read bounded UTF-8 text. For large JSON, select a subtree with #json=/key/0.

        Args:
            path: Project-relative file, optionally followed by #json= and an RFC 6901 pointer.
        """
        def action():
            name, selector, pointer = path.partition("#json=")
            target, relative = allowed_path(root, name, permissions["read_paths"])
            if selector:
                if target.suffix != ".json" or not pointer.startswith("/"):
                    raise ValueError("Use a .json file and a pointer starting with /.")
                if target.stat().st_size > DOWNLOAD_LIMIT:
                    raise ValueError("JSON source exceeds the size limit.")
                value = json.loads(target.read_text(encoding="utf-8-sig"))
                for part in pointer[1:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    try:
                        if isinstance(value, list) and key.isdecimal():
                            value = value[int(key)]
                        elif isinstance(value, dict):
                            value = value[key]
                        else:
                            raise ValueError("Cannot select this JSON key or index.")
                    except (KeyError, IndexError) as error:
                        raise ValueError(f"Missing key or index {key!r} at {pointer}.") from error
                excerpt = json.dumps(value, ensure_ascii=False)
                return {"path": relative, "json_pointer": pointer, "excerpt": excerpt[:TEXT_LIMIT],
                        "truncated": len(excerpt) > TEXT_LIMIT}
            with target.open("r", encoding="utf-8-sig") as stream:
                excerpt = stream.read(TEXT_LIMIT + 1)
            return {"path": relative, "excerpt": excerpt[:TEXT_LIMIT],
                    "truncated": len(excerpt) > TEXT_LIMIT}

        return invoke("read_file", {"path": path}, action)

    @tool
    def write_file(path: str, content: str) -> str:
        """Save a research note, source file, or configuration and return its unified diff.

        Args:
            path: Project-relative file in the write scope.
            content: Complete UTF-8 replacement, at most 14000 characters.
        """
        def action():
            target, relative = allowed_path(root, path, permissions["write_paths"])
            if target.suffix not in {".py", ".md", ".json", ".csv", ".txt"}:
                raise ValueError("This file type cannot be written.")
            if len(content) > TEXT_LIMIT or "\x00" in content:
                raise ValueError("File content exceeds tool limits.")
            old = ""
            if target.exists():
                with target.open("r", encoding="utf-8-sig") as stream:
                    old = stream.read(TEXT_LIMIT + 1)
                if len(old) > TEXT_LIMIT:
                    raise ValueError("Existing file exceeds safe diff size.")
            diff = "".join(unified_diff(old.splitlines(True), content.splitlines(True),
                                        fromfile=f"a/{relative}", tofile=f"b/{relative}"))
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                        dir=target.parent, prefix=".ksagent-", delete=False) as stream:
                    temp = Path(stream.name)
                    stream.write(content)
                temp.replace(target)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
            return {"path": relative, "diff": diff, "sha256": hashlib.sha256(content.encode()).hexdigest()}

        return invoke("write_file", {"path": path, "content_characters": len(content)}, action)

    @tool
    def run_check(command: str) -> str:
        """Execute an owner-configured check alias without interpolating model text into commands.

        Args:
            command: Exact configured alias, such as git_status or numerics_smoke.
        """
        def action():
            spec = permissions["commands"].get(command)
            if spec is None:
                raise ValueError("Unknown alias. Options: " + ", ".join(permissions["commands"]))
            argv = spec["argv"]
            started = monotonic()
            run.log("command_start", alias=command, argv=argv)
            env_names = {"path", "systemroot", "windir", "pathext", "comspec", "lang", "lc_all"}
            env = {k: v for k, v in os.environ.items() if k.lower() in env_names}
            subprocess_options = dict(cwd=root, env=env, encoding="utf-8", errors="replace",
                                      capture_output=True, timeout=run.timeout(spec["timeout_seconds"]))
            try:
                result = subprocess.run(argv, **subprocess_options)
            except subprocess.TimeoutExpired:
                return {"ok": False, "status": "timeout", "argv": argv, "exit_code": None}
            artifacts = []
            for artifact in spec.get("artifacts", []):
                target, relative = allowed_path(root, artifact, permissions["read_paths"])
                if target.is_file() and target.stat().st_size <= DOWNLOAD_LIMIT:
                    artifacts.append({"path": relative,
                                      "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
            return {"ok": result.returncode == 0, "argv": argv, "exit_code": result.returncode,
                    "elapsed_seconds": round(monotonic() - started, 3), "artifacts": artifacts,
                    "stdout": result.stdout[-4000:], "stderr": result.stderr[-2500:]}

        return invoke("run_check", {"command": command}, action)

    @tool
    def save_finding(source_id: str, source_claim: str, inference: str, uncertainty: str) -> str:
        """Persist a literature observation and project inference as separate fields.

        Args:
            source_id: Source ID from a successful read_source result in this run.
            source_claim: Paraphrase of what the observed source excerpt supports.
            inference: Research decision or implication for this project.
            uncertainty: Limitation, unmet assumption, or remaining question.
        """
        def action():
            if source_id not in sources:
                raise ValueError("Use a source ID returned by a successful read_source call.")
            finding = {"source_id": source_id, **sources[source_id],
                       "source_claim": source_claim[:1600], "inference": inference[:1600],
                       "uncertainty": uncertainty[:1600]}
            run.state["findings"].append(scrub(finding))
            return {"finding": finding}

        return invoke("save_finding", {"source_id": source_id}, action)

    enabled = set(permissions["tools"])
    available = [search_literature, read_source, read_file, write_file, run_check, save_finding]
    if enabled - {item.name for item in available}:
        raise ValueError("Unknown configured tool.")
    return [item for item in available if item.name in enabled]
