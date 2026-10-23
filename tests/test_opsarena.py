"""OpsArena Comprehensive Test Suite & Adversarial Verification.

Verifies:
1. Deterministic reset & 64-char SHA-256 state hash consistency across seeds.
2. Malformed config inputs ("banana", negative ints, invalid types) return clean errors without crashing the verifier.
3. Metric schema alignment (QPS vs RPS aliases, status, bounds).
4. Dynamic regression penalties when non-target services are disrupted or misconfigured.
5. Continuous partial credit progression on incremental mitigation steps.
6. Multi-seed baseline verification across all 8 tasks (Oracle >= 0.95, No-Op <= 0.05).
7. Append file loading & path traversal defense.
8. Task 7 Undersized Cluster Attack Defeat (scaling all pods to 1 fails verifier & SLO).
9. Dynamic telemetry & log consistency across seeded versions and parameters.
10. Secret scrubbing (API keys, bearer tokens, passwords redacted).
11. Cost preservation on invalid tool calls (no budget leak on bad inputs).
12. Strict 4,000 character output bound enforcement (including truncation marker).
13. Service-specific configuration key scope isolation.
"""
import threading
import time
from http.server import ThreadingHTTPServer
import pytest
import requests

from sandbox.simulator.world import CloudMeshWorld, MIN_SAFE_REPLICAS
from sandbox.simulator.actions import ACTION_HANDLERS
from sandbox.simulator.security import clip_output, scrub_secrets, MAX_OUTPUT_CHARS
from sandbox.simulator.metrics import compute_service_metrics
from sandbox.server import SandboxHandler
from harness.tools import TOOLS, SPECS, check_args
from harness.tasks import TASKS, DEMO_TASK, build_task
from harness.env import Env, PASS_SCORE
from harness.run import load_append, NOOP_MAX, ORACLE_MIN


@pytest.fixture(scope="module")
def local_sandbox():
    """Spins up a lightweight in-process sandbox HTTP server on an ephemeral port for integration tests."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), SandboxHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_world_deterministic_reset():
    """Identical seed must produce identical 64-char SHA-256 state hash."""
    w1 = CloudMeshWorld(seed=42)
    w2 = CloudMeshWorld(seed=42)
    assert w1.state_hash() == w2.state_hash()
    assert len(w1.state_hash()) == 64

    # Multiple resets of same seed
    t1 = build_task("task_01_cache_pressure", seed=10)
    w1.load_scenario(t1.scenario_spec)
    h1 = w1.state_hash()

    t2 = build_task("task_01_cache_pressure", seed=10)
    w2.load_scenario(t2.scenario_spec)
    h2 = w2.state_hash()
    assert h1 == h2


def test_state_hash_distinct_across_seeds():
    """Different seeds generate different initial state hashes due to scenario parameter variation."""
    t1 = build_task("task_01_cache_pressure", seed=10)
    t2 = build_task("task_01_cache_pressure", seed=99)
    w1 = CloudMeshWorld(seed=10)
    w2 = CloudMeshWorld(seed=99)
    w1.load_scenario(t1.scenario_spec)
    w2.load_scenario(t2.scenario_spec)
    assert w1.state_hash() != w2.state_hash()


def test_malformed_config_inputs_do_not_crash_scorer(local_sandbox):
    """Adversarial/malformed inputs must return clean errors and never cause TypeError in scoring."""
    env = Env(local_sandbox)
    env.reset("task_03_db_pool_exhaustion", seed=0)

    # 1. String where integer is expected (reviewer's test case)
    out, err = env.step("update_config", {"service": "inventory-service", "key": "db_pool_size", "value": "banana"})
    assert err is True
    assert "error:" in out
    assert "banana" in out

    # 2. Negative integer where bounded range required
    out, err = env.step("update_config", {"service": "db-primary", "key": "lock_timeout_ms", "value": -500})
    assert err is True
    assert "error:" in out

    # 3. Non-boolean string for boolean flag
    out, err = env.step("update_config", {"service": "payment-service", "key": "circuit_breaker_enabled", "value": "not_bool"})
    assert err is True
    assert "error:" in out

    # 4. Out of bounds integer
    out, err = env.step("update_config", {"service": "api-gateway", "key": "rate_limit_rps", "value": 9999999})
    assert err is True
    assert "error:" in out

    # 5. Unauthorized key
    out, err = env.step("update_config", {"service": "order-service", "key": "drop_tables", "value": True})
    assert err is True
    assert "error:" in out

    # Scorer must NOT crash with TypeError
    score_res = env.score()
    assert isinstance(score_res, dict)
    assert score_res["total"] <= NOOP_MAX


def test_metric_schema_and_alias_alignment(local_sandbox):
    """query_metrics must cleanly accept both 'qps' and 'rps' without errors."""
    env = Env(local_sandbox)
    env.reset("task_01_cache_pressure", seed=0)

    out_qps, err_qps = env.step("query_metrics", {"service": "api-gateway", "metric": "qps"})
    assert not err_qps, f"query_metrics with qps failed: {out_qps}"
    assert "req/s" in out_qps

    out_rps, err_rps = env.step("query_metrics", {"service": "api-gateway", "metric": "rps"})
    assert not err_rps, f"query_metrics with rps failed: {out_rps}"
    assert "req/s" in out_rps


def test_dynamic_regression_penalty(local_sandbox):
    """Disrupting an unrelated microservice must actively degrade the regression score."""
    env = Env(local_sandbox)
    env.reset("task_02_bad_deployment", seed=0)

    # Solve the primary incident
    env.step("rollback_release", {"service": "order-service", "target_version": "v2.4.0"})
    score_before = env.score()
    assert score_before["no_regressions"] == 0.25  # 100% of 0.25 weight

    # Cause unneeded damage to an unrelated service (scale payment-service down to 1 pod)
    env.step("scale_service", {"service": "payment-service", "replicas": 1})
    score_after = env.score()
    assert score_after["no_regressions"] < score_before["no_regressions"]
    assert score_after["total"] < score_before["total"]


def test_config_regression_on_non_target_services(local_sandbox):
    """Mutating configs on an unaffected service must incur a regression penalty."""
    env = Env(local_sandbox)
    env.reset("task_02_bad_deployment", seed=0)

    # Modify payment-service's gateway_timeout_ms (non-target service on Task 2)
    env.step("update_config", {"service": "payment-service", "key": "gateway_timeout_ms", "value": 15000})
    score = env.score()
    assert score["no_regressions"] < 0.25


def test_continuous_partial_credit_progression(local_sandbox):
    """Incremental progress must award bounded partial credit while no-op stays <= 0.05."""
    env = Env(local_sandbox)

    # Step 0: No-op
    env.reset("task_03_db_pool_exhaustion", seed=0)
    score_noop = env.score()["total"]
    assert score_noop == 0.0000

    # Step 1: Partial progress (pool size increased to 15, short of target 25)
    env.step("update_config", {"service": "inventory-service", "key": "db_pool_size", "value": 15})
    score_partial = env.score()["total"]
    assert 0.10 <= score_partial <= 0.40, f"Expected bounded partial credit, got {score_partial}"

    # Step 2: Full resolution (pool size increased to 25)
    env.step("update_config", {"service": "inventory-service", "key": "db_pool_size", "value": 25})
    score_full = env.score()["total"]
    assert score_full >= ORACLE_MIN, f"Expected full marks, got {score_full}"


def test_task_07_undersized_cluster_attack_defeated(local_sandbox):
    """The exploit of scaling every service to 1 pod (8 total pods <= 18) must be soundly rejected."""
    env = Env(local_sandbox)
    env.reset("task_07_cost_slo_rescue", seed=0)

    # Adversarial agent scales all services down to 1 replica
    for svc in ["api-gateway", "order-service", "db-replica", "payment-service", "inventory-service"]:
        env.step("scale_service", {"service": svc, "replicas": 1})
    env.step("finish", {})

    # Verifier must reject this as unresolved because capacity is starved
    score = env.score()
    assert score["total"] == 0.0000, f"Exploit was awarded positive score: {score}"
    assert score["slo_recovery"] == 0.0000


def test_task_02_bad_version_dynamic_telemetry(local_sandbox):
    """Metrics and logs must accurately reflect whatever bad version was seeded."""
    env = Env(local_sandbox)
    # Seed 0 generates bad_version 'v2.4.2'
    env.reset("task_02_bad_deployment", seed=0)

    out_metrics, err = env.step("query_metrics", {"service": "order-service", "metric": "errors"})
    assert not err
    assert "CRITICAL" in out_metrics

    out_logs, err = env.step("query_logs", {"service": "order-service", "filter": "version="})
    assert not err
    assert "version=v2.4.2" in out_logs or "v2.4.2" in out_logs


def test_secret_scrubbing_and_output_bounds():
    """Verify that credentials are fully redacted and output length never exceeds 4,000 chars."""
    raw = "Connected to host. api_key='sk-live1234567890abcdef123456' with Bearer eyJhbGciOiJIUzI1Ni. password: secretpassword123"
    scrubbed = scrub_secrets(raw)
    assert "sk-live" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed
    assert "secretpassword123" not in scrubbed

    # Test strict 4,000 char boundary
    long_text = "A" * 10000
    clipped = clip_output(long_text, max_chars=MAX_OUTPUT_CHARS)
    assert len(clipped) <= MAX_OUTPUT_CHARS
    assert "[output cut at 4000 characters]" in clipped


def test_cost_not_deducted_on_invalid_calls(local_sandbox):
    """Invalid service or metric names must NOT burn budget."""
    env = Env(local_sandbox)
    env.reset("task_01_cache_pressure", seed=0)

    # Initial cost spent is 0
    state_0 = requests.get(f"{local_sandbox}/state").json()
    assert state_0["cost_spent"] == 0.0

    # Call with unknown service
    out, err = env.step("query_metrics", {"service": "non-existent-service", "metric": "latency"})
    assert err is True
    state_1 = requests.get(f"{local_sandbox}/state").json()
    assert state_1["cost_spent"] == 0.0, "Cost was deducted for invalid service call!"

    # Call with unknown metric
    out, err = env.step("query_metrics", {"service": "api-gateway", "metric": "invalid_metric_xyz"})
    assert err is True
    state_2 = requests.get(f"{local_sandbox}/state").json()
    assert state_2["cost_spent"] == 0.0, "Cost was deducted for invalid metric call!"


def test_service_specific_config_key_isolation():
    """Setting a config key that belongs to another service must fail validation."""
    err = check_args("update_config", {"service": "api-gateway", "key": "db_pool_size", "value": 25})
    assert err is not None
    assert "not configurable on 'api-gateway'" in err


def test_all_eight_tasks_baselines_multi_seeds(local_sandbox):
    """All 8 tasks across multiple seeds must pass Oracle >= 0.95 and No-Op <= 0.05."""
    env = Env(local_sandbox)

    for seed in [0, 42, 99]:
        for task_id in TASKS:
            task = build_task(task_id, seed=seed)

            # 1. No-op verification
            env.reset(task_id, seed=seed)
            noop_score = env.score()["total"]
            assert noop_score <= NOOP_MAX, f"Task {task_id} seed {seed} failed no-op (got {noop_score})"

            # 2. Oracle verification
            env.reset(task_id, seed=seed)
            for name, args in task.oracle_actions:
                out, err = env.step(name, args)
                assert not err, f"Task {task_id} seed {seed} action {name} failed: {out}"

            oracle_score = env.score()["total"]
            assert oracle_score >= ORACLE_MIN, (
                f"Task {task_id} seed {seed} failed oracle check (got {oracle_score}, expected >= {ORACLE_MIN})"
            )


def test_append_file_loading():
    """Ensures inputs/ loading works and directory traversal is blocked."""
    text, info = load_append(None)
    assert text == ""
    assert info is None

    with pytest.raises(ValueError, match="must be within inputs/ directory"):
        load_append("../etc/passwd")
