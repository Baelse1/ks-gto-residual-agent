"""Verify and archive stage 4 artifacts and reconstruct agent-authored revisions."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def digest(data):
    return sha256(data).hexdigest()


def apply_unified_diff(old, patch):
    old_lines = old.splitlines(keepends=True)
    result = []
    index = 0
    active = False
    for line in patch.splitlines(keepends=True):
        match = HUNK.match(line)
        if match:
            start = int(match[1]) - (match[2] != "0")
            if start < index or start > len(old_lines):
                raise ValueError("Invalid hunk offset.")
            result.extend(old_lines[index:start])
            index, active = start, True
            continue
        if not active:
            continue
        marker, body = line[0], line[1:]
        if marker in " -":
            if index >= len(old_lines) or old_lines[index] != body:
                raise ValueError("Patch context does not match previous revision.")
            index += 1
        if marker in " +":
            result.append(body)
        if marker not in " -+":
            raise ValueError(f"Unexpected patch marker {marker!r}.")
    result.extend(old_lines[index:])
    return "".join(result)


def archive(root, stage):
    journal = stage / "agent" / "events.jsonl"
    state = stage / "agent" / "checkpoint.json"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    complete_reads = {}
    for row in rows:
        if row["event"] != "tool_result" or row["name"] != "read_file":
            continue
        result = row["result"]
        if result["ok"] and not result["truncated"] and "json_pointer" not in result:
            data = result["excerpt"].encode("utf-8")
            complete_reads[result["path"], digest(data)] = data
    decision, action = None, 0
    revisions, latest = {}, {}
    actions = []
    for row in rows:
        event = row["event"]
        if event == "decision":
            decision = row
        if event != "tool_result":
            continue
        if decision is None or decision["tool"] != row["name"]:
            raise ValueError("Missing paired decision in stage 4 journal.")
        action += 1
        res = row["result"]
        record = {
            "action": action, "utc": row["time_utc"], "tool": row["name"],
            "decision": decision["reason"], "next_question": decision["next_question"],
            "arguments": decision["arguments"],
        }
        for key in ("ok", "http_status", "url", "source_id", "scope", "excerpt_sha256",
                    "json_pointer", "truncated",
                    "exit_code", "argv", "error", "elapsed_seconds"):
            if key in res:
                record[key] = res[key]
        if row["name"] == "search_literature" and res["ok"]:
            record["returned_dois"] = [item["doi"] for item in res["items"]]
        if row["name"] == "write_file" and res["ok"]:
            relative = res["path"]
            updated = apply_unified_diff(revisions.get(relative, ""), res["diff"])
            content = updated.encode("utf-8")
            if digest(content) != res["sha256"]:
                raise ValueError(f"Revision digest mismatch for {relative}.")
            revisions[relative] = updated
            path = stage / "versions" / f"{action:02d}-{Path(relative).name}"
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)
            record["revision"] = path.relative_to(root).as_posix()
            record["sha256"] = res["sha256"]
        if row["name"] == "run_check":
            record["agent_files_at_execution"] = {
                name: digest(content.encode("utf-8")) for name, content in revisions.items()
                if name.endswith(".py")
            }
        if res.get("artifacts"):
            record["artifacts"] = []
            for artifact in res["artifacts"]:
                path = root / artifact["path"]
                try:
                    filename = path.resolve().relative_to(root / "runs" / "stage4")
                except ValueError:
                    continue
                target = stage / "results" / f"{action:02d}" / filename
                data = path.read_bytes() if path.is_file() else None
                if data is None or digest(data) != artifact["sha256"]:
                    data = complete_reads.get((artifact["path"], artifact["sha256"]))
                if data is not None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                if not target.is_file() or digest(target.read_bytes()) != artifact["sha256"]:
                    raise ValueError(f"Artifact digest mismatch for {path}.")
                record["artifacts"].append({**artifact, "archive": target.relative_to(root).as_posix()})
        actions.append(record)
        decision = None

    for relative, content in revisions.items():
        path = root / relative
        if path.read_bytes() != content.encode("utf-8"):
            raise ValueError(f"Current file differs from final journal revision: {relative}.")
        latest[relative] = digest(path.read_bytes())
    checkpoint = json.loads(state.read_text(encoding="utf-8"))
    config = root / "config" / "agent.stage4.json"
    if checkpoint["config_sha256"] != digest(config.read_bytes()):
        raise ValueError("Checkpoint and stage 4 configuration hash differ.")
    summary = {
        "journal_sha256": digest(journal.read_bytes()),
        "config_sha256": checkpoint["config_sha256"],
        "status": checkpoint["status"],
        "model_calls_total": checkpoint["model_calls_total"],
        "scientific_tool_actions": actions,
        "latest_agent_files_sha256": latest,
    }
    (stage / "audit.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    print(f"Verified {action} decisions/tool pairs and {len(latest)} agent-authored files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-dir", type=Path, default=Path("evidence/stage4"))
    args = parser.parse_args()
    archive(Path.cwd().resolve(), args.stage_dir.resolve())
