"""OpsArena Harness Entrypoint: Verification Gate, Episode Execution & Telemetry.

Execution command:
    docker compose up --build --abort-on-container-exit --exit-code-from harness

Protocol:
    1. Pre-flight health check on sandbox container.
    2. Baseline validation:
       - Reference Oracle >= 0.95 (PASS_SCORE)
       - No-Op Agent <= 0.05 (NOOP_MAX)
    3. Gate Enforcement: If either baseline check fails, abort immediately with exit code 2.
    4. Model Episode: If baselines pass, execute autonomous agent on TASK_ID.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .agents import make_client, noop_actions, oracle_actions
from .env import Env, PASS_SCORE
from .runner import JsonlLog, Limits, now, run_episode, run_scripted
from .tasks import DEMO_TASK, TASKS, build_task

ORACLE_MIN: float = PASS_SCORE  # Reference solution must reach at least 0.95
NOOP_MAX: float = 0.05          # No-op agent must stay at or below 0.05
MODES = ("full", "all", "baselines")
GATE_BUDGET_SECONDS = 120       # Pre-flight check budget


def load_env_if_present() -> None:
    """Loads variables from local .env if not already set in environment."""
    env_file = Path(".env")
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key, val = key.strip(), val.strip()
                    if key and key not in os.environ and val:
                        os.environ[key] = val
        except Exception:
            pass


def setting(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def wait_for_sandbox(url: str, seconds: int = 60) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            resp = requests.get(url + "/health", timeout=2)
            if resp.ok:
                return
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError(f"OpsArena sandbox at {url} did not become ready within {seconds}s")


def run_gate(env: Env, task_ids: List[str], seed: int, log_path: Path) -> Tuple[bool, List[Dict[str, Any]]]:
    """Runs Oracle and No-Op baselines for each target task. Returns (passed, rows)."""
    log = JsonlLog(log_path)
    rows = []
    print("\n== Pre-Flight Baseline Checks ==", flush=True)

    for task_id in task_ids:
        task = build_task(task_id, seed)
        oracle_score = run_scripted(env, task_id, seed, oracle_actions(task), "oracle", log)["total"]
        noop_score = run_scripted(env, task_id, seed, noop_actions(task), "noop", log)["total"]

        oracle_ok = bool(oracle_score >= ORACLE_MIN)
        noop_ok = bool(noop_score <= NOOP_MAX)
        row = {
            "task": task_id,
            "difficulty": task.difficulty,
            "oracle": oracle_score,
            "noop": noop_score,
            "oracle_ok": oracle_ok,
            "noop_ok": noop_ok,
        }
        rows.append(row)
        print(
            f"{task_id:<28} oracle {oracle_score:.2f} [{'PASS' if oracle_ok else 'FAIL'}]   "
            f"no-op {noop_score:.2f} [{'PASS' if noop_ok else 'FAIL'}]",
            flush=True,
        )

    log.close()
    all_passed = all(r["oracle_ok"] and r["noop_ok"] for r in rows)
    return all_passed, rows


INPUTS = Path("inputs")


def load_append(name: Optional[str]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Loads optional system-prompt instructions appended by judges from inputs/."""
    explicit = bool(name)
    name = name or "append.txt"
    for prefix in ("./inputs/", "inputs/", ".\\inputs\\", "inputs\\"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    path = (INPUTS / name).resolve()

    if INPUTS.resolve() not in path.parents:
        raise ValueError(f"APPEND_FILE must be within inputs/ directory, got '{name}'")
    if not path.is_file():
        if explicit:
            raise ValueError(f"APPEND_FILE inputs/{name} not found; place file in inputs/ folder")
        return "", None

    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"APPEND_FILE inputs/{name} is not valid UTF-8 text ({exc.reason})")

    if not text.strip():
        if explicit:
            raise ValueError(f"APPEND_FILE inputs/{name} is empty")
        return "", None

    info = {
        "file": f"inputs/{name}",
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return text, info


def main() -> int:
    load_env_if_present()

    url = setting("SANDBOX_URL", "http://localhost:8000")
    model = setting("MODEL", "mock/solver")
    api_key = setting("API_KEY")
    base_url = setting("BASE_URL") or None
    task_id = setting("TASK_ID", DEMO_TASK)
    mode = setting("MODE", "full")
    seed = int(setting("SEED", "0"))

    run_id = time.strftime("%Y%m%d-%H%M%S")
    out = Path("logs") / run_id
    out.mkdir(parents=True, exist_ok=True)

    limits = Limits(
        max_steps=int(setting("MAX_STEPS", "40")),
        max_seconds=int(setting("MAX_SECONDS", "600")),
    )

    if mode not in MODES:
        print(f"Unknown MODE '{mode}'. Available: {', '.join(MODES)}")
        return 3
    if mode == "full" and task_id not in TASKS:
        print(f"Unknown TASK_ID '{task_id}'. Available: {', '.join(TASKS)}")
        return 3

    try:
        client = None if mode == "baselines" else make_client(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=int(setting("MAX_TOKENS", "0")) or None,
        )
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 3

    try:
        append_text, append_info = ("", None) if mode == "baselines" else load_append(setting("APPEND_FILE"))
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 3

    if append_info:
        (out / "append.txt").write_text(append_text, encoding="utf-8")
        print(
            f"Extra instructions: {append_info['file']} ({append_info['chars']} chars, "
            f"sha256 {append_info['sha256'][:12]}) appended to system prompt.",
            flush=True,
        )

    try:
        wait_for_sandbox(url)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    env = Env(url)
    task_ids = [task_id] if mode == "full" else list(TASKS)
    gate_start = time.monotonic()
    passed, rows = run_gate(env, task_ids, seed, out / "gate.jsonl")
    gate_duration = round(time.monotonic() - gate_start, 2)
    print(f"Pre-flight baseline checks completed in {gate_duration}s", flush=True)

    (out / "gate.json").write_text(
        json.dumps({"seed": seed, "passed": passed, "gate_seconds": gate_duration, "tasks": rows}, indent=2),
        encoding="utf-8",
    )

    if mode == "baselines":
        print(f"\nBaseline results: {'ALL CHECKS PASSED' if passed else 'BASELINE CHECKS FAILED'} -> {out}/gate.json")
        return 0 if passed else 2

    if not passed:
        summary = {
            "run_id": run_id,
            "status": "gate_failed",
            "mode": mode,
            "tasks": task_ids,
            "seed": seed,
            "model_called": False,
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("\nPre-flight baseline check failed; model was NOT invoked per hackathon contract. See gate.json.")
        return 2

    if mode == "full":
        result = run_model(env, task_id, seed, client, model, append_text, limits, out / "episode.jsonl")
        summary = {
            "run_id": run_id,
            "status": "completed",
            "task": task_id,
            "seed": seed,
            "model": model,
            "model_called": True,
            "append": append_info,
            "finished_at": now(),
            **result,
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Episode logs saved to: {out}", flush=True)
        return 1 if result["termination"] == "crash" else 0

    # mode == "all"
    results = {}
    for tid in task_ids:
        try:
            results[tid] = run_model(env, tid, seed, client, model, append_text, limits, out / f"episode-{tid}.jsonl")
        except Exception as exc:
            print(f"Task {tid} crashed: {type(exc).__name__}: {exc}", flush=True)
            results[tid] = {
                "termination": "crash",
                "steps": 0,
                "reward": {"total": None},
                "error": f"{type(exc).__name__}: {exc}",
            }

    totals = [(r["reward"].get("total") or 0.0) for r in results.values() if isinstance(r.get("reward"), dict)]
    summary = {
        "run_id": run_id,
        "status": "completed",
        "mode": "all",
        "seed": seed,
        "model": model,
        "model_called": True,
        "append": append_info,
        "finished_at": now(),
        "solved": sum(r["termination"] == "success" for r in results.values()),
        "mean_reward": round(sum(totals) / max(1, len(totals)), 3),
        "tasks": results,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n== All Tasks Summary ==", flush=True)
    for tid, r in results.items():
        total = r["reward"].get("total") if isinstance(r.get("reward"), dict) else "-"
        print(f"{tid:<28} {r['termination']:<9} reward {total:<6} steps {r['steps']}", flush=True)
    print(f"Solved: {summary['solved']}/{len(results)} | Mean Reward: {summary['mean_reward']} | Logs: {out}", flush=True)
    return 1 if any(r["termination"] == "crash" for r in results.values()) else 0


def run_model(
    env: Env,
    task_id: str,
    seed: int,
    client: Any,
    model: str,
    append_text: str,
    limits: Limits,
    log_path: Path,
) -> Dict[str, Any]:
    print(f"\n== Model Run: {model} | Task: {task_id} | Seed: {seed} ==", flush=True)
    log = JsonlLog(log_path)
    try:
        result = run_episode(env, task_id, seed, client, append_text, limits, log)
    finally:
        log.close()
    print(
        f"\nTermination: {result['termination']} | Total Reward: {result['reward'].get('total') if isinstance(result.get('reward'), dict) else '-'} | Steps: {result['steps']}",
        flush=True,
    )
    return result


if __name__ == "__main__":
    sys.exit(main())
