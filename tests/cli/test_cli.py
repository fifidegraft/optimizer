import json
from pathlib import Path

import pytest

from optimizer import cli, pipeline
from optimizer.verifier import snapshot

from .conftest import LIB, TESTS_PASS, WORKLOAD, StubClient, candidate, fake_measure

FASTER = LIB.replace("range(3000)", "range(1)")


def test_no_args_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == cli.EXIT_USAGE
    assert "usage:" in capsys.readouterr().err


def test_run_requires_workload(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["run", "."])
    assert exc.value.code == cli.EXIT_USAGE
    assert "--workload" in capsys.readouterr().err


def test_missing_path_fails_cleanly(capsys):
    code = cli.main(["run", "/definitely/not/here", "--workload", "python x.py", "--no-color"])
    assert code == pipeline.EXIT_FAILED
    assert "Not a directory" in capsys.readouterr().out


def test_main_maps_pipeline_result(monkeypatch, capsys):
    seen = {}

    def fake_run(config, console, confirm):
        seen["config"] = config
        seen["confirm"] = confirm
        console.print("progress")
        return pipeline.RunResult(pipeline.EXIT_NOTHING_APPLIED)

    monkeypatch.setattr(pipeline, "run", fake_run)
    code = cli.main([
        "run", "proj", "--workload", "python w.py", "--test", "pytest -q", "--passes", "2",
        "--hotspot", "a", "--hotspot", "b", "--yes", "--min-improvement", "0.1", "--iterations", "3",
        "--timeout", "42", "--no-color",
    ])
    assert code == pipeline.EXIT_NOTHING_APPLIED
    c = seen["config"]
    assert c.path == "proj" and c.workload == "python w.py" and c.test == "pytest -q"
    assert c.passes == 2 and c.hotspots == ("a", "b") and c.yes is True
    assert c.min_improvement == 0.1 and c.iterations == 3 and c.timeout == 42
    assert seen["confirm"] is cli._confirm
    assert capsys.readouterr().out == "progress\n"


def test_json_mode_keeps_stdout_clean(project, monkeypatch, capsys):
    client = StubClient([candidate("candidate_a", FASTER)])
    timing = fake_measure(800.0, 200.0)
    real_init = pipeline.RunConfig.__init__

    def patched_init(self, *a, **kw):
        real_init(self, *a, **kw)
        self.client = client
        self.measure_fn = timing
        self.profile_fn = None

    monkeypatch.setattr(pipeline.RunConfig, "__init__", patched_init)
    code = cli.main(["run", str(project), "--workload", WORKLOAD, "--test", TESTS_PASS,
                     "--hotspot", "parse", "--yes", "--json"])
    out, err = capsys.readouterr()
    assert code == pipeline.EXIT_OK
    payload = json.loads(out)
    assert payload["report"]["speedup"] == 4.0
    assert payload["passes"][0]["winner"]["candidate_id"] == "candidate_a"
    assert "Scanning repository" in err and "\x1b[" not in err


def test_json_without_yes_never_applies(project, monkeypatch, capsys):
    client = StubClient([candidate("candidate_a", FASTER)])
    real_init = pipeline.RunConfig.__init__

    def patched_init(self, *a, **kw):
        real_init(self, *a, **kw)
        self.client, self.measure_fn, self.profile_fn = client, fake_measure(800.0, 200.0), None

    monkeypatch.setattr(pipeline.RunConfig, "__init__", patched_init)
    code = cli.main(["run", str(project), "--workload", WORKLOAD, "--hotspot", "parse", "--json"])
    out, err = capsys.readouterr()
    assert code == pipeline.EXIT_OK
    assert json.loads(out)["applied"] is False
    assert "--json without --yes" in err
    assert (project / "lib.py").read_text() == LIB


def test_no_color_flag_and_env(project, monkeypatch, capsys):
    monkeypatch.setattr(pipeline, "run", lambda config, console, confirm: (console.ok("fine"), pipeline.RunResult(0))[1])
    cli.main(["run", str(project), "--workload", "x", "--no-color"])
    assert capsys.readouterr().out == "fine\n"
    monkeypatch.setenv("NO_COLOR", "1")
    cli.main(["run", str(project), "--workload", "x"])
    assert capsys.readouterr().out == "fine\n"


def test_inspect_prints_summary_and_json(project, capsys):
    assert cli.main(["inspect", str(project), "--no-color"]) == pipeline.EXIT_OK
    out = capsys.readouterr().out
    assert "1 Python files found" in out and "Performance opportunities" in out

    assert cli.main(["inspect", str(project), "--json"]) == pipeline.EXIT_OK
    out, _ = capsys.readouterr()
    info = json.loads(out)
    assert info["functions"] == 2 and info["hotspots"][0]["function"] == "summarize"


def test_recover_with_and_without_backups(project, capsys):
    assert cli.main(["recover", str(project), "--no-color"]) == pipeline.EXIT_OK
    assert "Nothing to recover" in capsys.readouterr().out

    snap = snapshot(project, ["lib.py"])
    (project / "lib.py").write_text("broken\n")
    assert cli.main(["recover", str(project), "--no-color"]) == pipeline.EXIT_OK
    out = capsys.readouterr().out
    assert f"Restored 1 file(s) from backup {snap['id']}" in out and "- lib.py" in out
    assert (project / "lib.py").read_text() == LIB
    assert not (project / ".optimizer" / "backups" / snap["id"]).exists()

    assert cli.main(["recover", str(project / "nope")]) == pipeline.EXIT_FAILED


def test_python_dash_m_entry_point(project):
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "optimizer", "inspect", str(project), "--no-color"],
        capture_output=True, text=True, check=False, cwd=Path(__file__).resolve().parents[2],
    )
    assert proc.returncode == 0, proc.stderr
    assert "functions indexed" in proc.stdout
