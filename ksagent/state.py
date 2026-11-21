"""Bounded run state and persistent evidence."""
from datetime import datetime, timezone
import json
import re
from time import monotonic


def now():
    return datetime.now(timezone.utc).isoformat()


def scrub(value):
    if isinstance(value, str):
        value = re.sub(r"(?i)(https?://)[^/\s@]+@", r"\1[REDACTED]@", value)
        value = re.sub(r"(?i)\b(?:sk-(?:proj-)?|hf_|gh[pousr]_)[a-z0-9_-]{16,}", "[REDACTED]", value)
        value = re.sub(r"(?i)(bearer\s+)[a-z0-9._=-]{12,}", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)([a-z]:[\\/]users[\\/])[^\\/\s]+", r"\1[USER]", value)
        return value
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class BudgetReached(Exception):
    pass


class Run:
    def __init__(self, directory, config, resume, fingerprint):
        self.directory = directory
        self.config = config
        self.budget = config["budget"]
        self.deadline = monotonic() + self.budget["wall_seconds"]
        self.calls = 0
        self.path = directory / "checkpoint.json"
        self.journal = directory / "events.jsonl"
        if resume:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.state["config_sha256"] != fingerprint:
                raise ValueError("Use the same research configuration to resume.")
        else:
            directory.mkdir(parents=True, exist_ok=False)
            goal = config["goal"]
            question = config["next_question"]
            self.state = {
                "goal": goal, "next_question": question, "findings": [],
                "recent_actions": [], "status": "new", "model_calls_total": 0,
                "steps_total": 0, "config_sha256": fingerprint,
            }
        self.log("invocation", resume=resume, budget=self.budget,
                 previous_status=self.state["status"])
        self.state["status"] = "running"
        self.save()

    def log(self, event, **details):
        row = scrub({"time_utc": now(), "event": event, **details})
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    def save(self):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(scrub(self.state), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        temp.replace(self.path)

    def timeout(self, requested):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise BudgetReached("wall_seconds")
        return min(requested, remaining)

    def start_call(self):
        if self.calls >= self.budget["model_calls"]:
            raise BudgetReached("model_calls")
        timeout = self.timeout(self.budget["model_timeout_seconds"])
        self.calls += 1
        self.state["model_calls_total"] += 1
        self.save()
        return timeout

    def observe(self, name, arguments, result):
        self.log("tool_result", name=name, result=result)
        observation = scrub({"tool": name, "arguments": arguments, "result": result})
        self.state["recent_actions"].append(observation)
        self.state["recent_actions"] = self.state["recent_actions"][-6:]
        self.save()
