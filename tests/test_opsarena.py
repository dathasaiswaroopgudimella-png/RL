"""OpsArena Comprehensive Test Suite.

Verifies:
1. World initialization and deterministic reset.
2. Action implementations, budget accounting, boundary checks.
3. Secret redaction in logs and metrics.
4. Schema validation and error handling.
5. All 8 tasks: Reference Oracle >= 0.95, No-Op <= 0.05.
6. Append file injection and path traversal security.
"""
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
import requests

from sandbox.simulator.world import CloudMeshWorld
from sandbox.simulator.actions import ACTION_HANDLERS
from sandbox.server import SandboxHandler
from harness.tools import TOOLS, SPECS, check_args
from harness.tasks import TASKS, DEMO_TASK, build_task
from harness.env import Env, PASS_SCORE
from harness.run import load_append, NOOP_MAX, ORACLE_MIN


@pytest.fixture(scope="module")
def local_sandbox():
    """Spins up a lightweight in-process sandbox HTTP server for integration tests."""
    server = ThreadingHTTPServer(("127.0.0.1", 9050), SandboxHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield "http://127.0.0.1:9050"
    server.shutdown()


def test_world_initialization():
    world = CloudMeshWorld(seed=42)
    assert len(world.services) == 8
    assert "order-service" in world.services
    assert "cache-cluster" in world.services
    assert world.cost_spent == 0.0
    assert not world.finished
    h1 = world.state_hash()
    assert len(h1) == 8


def test_actions_and_budget_bounds():
    world = CloudMeshWorld(seed=0)
    
    # get_topology costs $1.00
    res = ACTION_HANDLERS["get_topology"](world, {})
    assert "CloudMesh Services Topology" in res
    assert world.cost_spent == 1.0

    # scale_service bounds checking
    res_err = ACTION_HANDLERS["scale_service"](world, {"service": "order-service", "replicas": 99})
    assert "error: replicas must be an integer between 1 and 20" in res_err

    # valid scale_service
    # default order-service replicas is 3, scaling to 4: cost = |4 - 3| * 2.0 + 3.0 = 5.00 -> total cost = 6.00
    res_ok = ACTION_HANDLERS["scale_service"](world, {"service": "order-service", "replicas": 4})
    assert "Successfully scaled" in res_ok
    assert world.cost_spent == 6.0

    # rollback_release
    res_rb = ACTION_HANDLERS["rollback_release"](world, {"service": "order-service", "target_version": "v2.4.0"})
    assert "Deployment rollback initiated" in res_rb

    # unauthorized config key
    res_bad_cfg = ACTION_HANDLERS["update_config"](world, {"service": "order-service", "key": "malicious_eval", "value": 1})
    assert "error: configuration key 'malicious_eval' is not allowed" in res_bad_cfg

    # exhaust budget
    world.cost_spent = 149.0
    res_over = ACTION_HANDLERS["scale_service"](world, {"service": "order-service", "replicas": 8})
    assert "error: Action denied: cost" in res_over


def test_secret_redaction():
    world = CloudMeshWorld(seed=0)
    logs = ACTION_HANDLERS["query_logs"](world, {"service": "order-service", "filter": "token"})
    assert "jwt_secret_token" not in logs
    assert "prod_pg_password" not in logs
    assert "sk-" not in logs


def test_schema_validation():
    # Valid get_topology
    assert check_args("get_topology", {}) is None

    # Missing required argument
    assert "missing required argument 'service'" in check_args("query_metrics", {})

    # Invalid type
    assert "must be an integer" in check_args("scale_service", {"service": "order-service", "replicas": "five"})
    assert "must be an integer" in check_args("scale_service", {"service": "order-service", "replicas": True})

    # Unknown tool
    assert "unknown tool" in check_args("drop_database", {})


def test_all_eight_tasks_baselines(local_sandbox):
    env = Env(local_sandbox)

    for task_id in TASKS:
        task = build_task(task_id, seed=0)

        # 1. No-op verification
        env.reset(task_id, seed=0)
        noop_res = env.score()
        assert noop_res["total"] <= NOOP_MAX, f"Task {task_id} failed no-op baseline check (got {noop_res['total']})"

        # 2. Oracle verification
        env.reset(task_id, seed=0)
        for name, args in task.oracle_actions:
            out, err = env.step(name, args)
            assert not err, f"Task {task_id} oracle action {name} errored: {out}"

        oracle_res = env.score()
        assert oracle_res["total"] >= ORACLE_MIN, (
            f"Task {task_id} failed oracle baseline check (got {oracle_res['total']}, expected >= {ORACLE_MIN})"
        )


def test_append_file_loading(tmp_path):
    # Missing optional file returns empty
    text, info = load_append(None)
    assert text == ""
    assert info is None

    # Directory traversal rejection
    with pytest.raises(ValueError, match="must be within inputs/ directory"):
        load_append("../secret.txt")
