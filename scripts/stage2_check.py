"""Exercise file scope, command status, and checkpoint recovery without a model."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ksagent.state import BudgetReached, Run
from ksagent.tools import make_tools

repo = Path.cwd()
scratch = repo / ".scratch"
scratch.mkdir(exist_ok=True)
with TemporaryDirectory(dir=scratch) as d:
    root = Path(d)
    config = dict(
        goal="Local integration probe", next_question="Verify tools",
        budget=dict(steps=4, model_calls=1, wall_seconds=20, model_timeout_seconds=10),
        permissions=dict(
            tools=["read_file", "write_file", "run_check", "save_finding"],
            read_paths=["experiments/"], write_paths=["experiments/"],
            commands={
                "verify": {
                    "argv": [sys.executable, "-c",
                             "from pathlib import Path; "
                             "assert Path('experiments/probe.py').read_text().splitlines() == ['value = 2']"],
                    "timeout_seconds": 5,
                    "artifacts": ["experiments/probe.py"],
                },
                "fail": {"argv": [sys.executable, "-c", "import sys; sys.exit(7)"], "timeout_seconds": 5},
            },
        ),
    )
    run_dir = root / "run"
    run = Run(run_dir, config, False, "scratch-probe")
    tools = {item.name: item for item in make_tools(root, run)}
    written = json.loads(tools["write_file"](path="experiments/probe.py", content="value = 2\n"))
    assert "+value = 2" in written["diff"]
    assert json.loads(tools["read_file"](path="experiments/probe.py"))["excerpt"] == "value = 2\n"
    assert not json.loads(tools["write_file"](path="../outside.py", content="x"))["ok"]
    assert not json.loads(tools["write_file"](path="README.md", content="x"))["ok"]
    passed = json.loads(tools["run_check"](command="verify"))
    assert passed["exit_code"] == 0 and passed["artifacts"][0]["sha256"] == written["sha256"]
    failed = json.loads(tools["run_check"](command="fail"))
    assert failed["exit_code"] == 7 and not failed["ok"]
    assert not json.loads(tools["run_check"](command="undefined"))["ok"]
    run.start_call()
    try:
        run.start_call()
    except BudgetReached as exc:
        assert str(exc) == "model_calls"
    else:
        raise AssertionError("Missing budget stop")
    resumed = Run(run_dir, config, True, "scratch-probe")
    assert resumed.state["model_calls_total"] == 1
    assert resumed.state["recent_actions"][-2]["result"]["exit_code"] == 7
    result = {
        "mode": "local tool integration checks; no model",
        "checks": {"file_write_read_diff": "passed", "out_of_scope_writes": "blocked",
                   "command_exit_statuses": [0, 7], "undeclared_alias": "blocked",
                   "command_artifact_sha256_matches_write": True,
                   "model_call_budget_guard": "passed", "checkpoint_restore": "passed"}
    }
    print(json.dumps(result, indent=2))
