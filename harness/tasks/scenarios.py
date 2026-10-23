"""OpsArena Scenarios: 8 Deterministic Incident Response Families with Seeded Diversity."""
import random
from typing import Any, Dict, Tuple
from .base import TaskInstance


def build_cache_pressure_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    initial_mem = rng.choice([1024, 2048, 4096])
    surge_qps = rng.choice([2800, 3200, 3600])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        cache = services.get("cache-cluster", {})
        replicas = cache.get("replicas", 1)
        mem = cache.get("memory_limit_mb", initial_mem)
        is_resolved = bool(replicas >= 2 or mem >= 8192)
        error_rate = 0.04 if is_resolved else 4.8
        latency = 48.0 if is_resolved else 1180.0
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_01_cache_pressure",
        title="Redis Eviction Storm",
        difficulty="easy",
        instructions=(
            f"A cache memory eviction storm on `cache-cluster` (initial memory: {initial_mem}MB, surge traffic: {surge_qps} RPS) "
            "is causing a thundering herd on `db-primary`, spiking CPU to 96% and latency to 1180ms. "
            "Investigate logs, scale `cache-cluster` to at least 2 replicas to expand memory capacity, and resolve the incident."
        ),
        scenario_spec={
            "task_id": "task_01_cache_pressure",
            "seed": seed,
            "surge_qps": surge_qps,
            "target_services": ["cache-cluster"],
            "service_overrides": {
                "cache-cluster": {"replicas": 1, "memory_limit_mb": initial_mem}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_metrics", {"service": "db-primary", "metric": "latency"}),
            ("query_logs", {"service": "cache-cluster", "filter": "maxmemory"}),
            ("scale_service", {"service": "cache-cluster", "replicas": 2}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_bad_deployment_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    bad_version = rng.choice(["v2.4.1", "v2.4.2", "v2.5.0-beta"])
    err_rate_initial = rng.choice([16.5, 18.4, 21.0])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        order_svc = services.get("order-service", {})
        ver = order_svc.get("version")
        is_resolved = bool(ver == "v2.4.0")
        error_rate = 0.04 if is_resolved else err_rate_initial
        latency = 52.0 if is_resolved else 310.0
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_02_bad_deployment",
        title="Bad Release Rollback",
        difficulty="easy",
        instructions=(
            f"Following deployment of `{bad_version}` on `order-service`, users are experiencing HTTP 500 errors "
            f"({err_rate_initial}% error rate). Check the logs and metrics, roll back `order-service` to previous stable "
            "release `v2.4.0`, and verify restoration."
        ),
        scenario_spec={
            "task_id": "task_02_bad_deployment",
            "seed": seed,
            "target_services": ["order-service"],
            "service_overrides": {
                "order-service": {"version": bad_version}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_metrics", {"service": "order-service", "metric": "errors"}),
            ("query_logs", {"service": "order-service", "filter": "NullPointerException"}),
            ("rollback_release", {"service": "order-service", "target_version": "v2.4.0"}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_db_pool_exhaustion_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    initial_pool = rng.choice([3, 5, 8])
    burst_rps = rng.choice([1600, 1800, 2200])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        inv = services.get("inventory-service", {})
        pool_size = inv.get("config", {}).get("db_pool_size", initial_pool)
        if isinstance(pool_size, (int, float)):
            is_resolved = bool(pool_size >= 25)
            progress = 1.0 if is_resolved else min(0.5, max(0.0, (pool_size - initial_pool) / (25 - initial_pool) * 0.5))
        else:
            is_resolved = False
            progress = 0.0
        error_rate = 0.04 if is_resolved else 12.8
        latency = 45.0 if is_resolved else 850.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_03_db_pool_exhaustion",
        title="Connection Pool Starvation",
        difficulty="medium",
        instructions=(
            f"Under checkout bursts ({burst_rps} RPS), `inventory-service` (initial pool: {initial_pool}) is timing out "
            "waiting for database connections (HTTP 504 errors). Diagnose the connection bottleneck and update "
            "`inventory-service`'s `db_pool_size` configuration to at least 25."
        ),
        scenario_spec={
            "task_id": "task_03_db_pool_exhaustion",
            "seed": seed,
            "target_services": ["inventory-service"],
            "service_overrides": {
                "inventory-service": {"config": {"db_pool_size": initial_pool}}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_logs", {"service": "inventory-service", "filter": "pool"}),
            ("update_config", {"service": "inventory-service", "key": "db_pool_size", "value": 25}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_downstream_timeout_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    partner_hang_ms = rng.choice([6000, 7500, 9000])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        pmt = services.get("payment-service", {})
        cb = pmt.get("circuit_breaker_enabled", False)
        timeout = pmt.get("config", {}).get("gateway_timeout_ms", partner_hang_ms)
        is_resolved = bool(cb or (isinstance(timeout, (int, float)) and timeout <= 1000))
        error_rate = 0.04 if is_resolved else 8.6
        latency = 62.0 if is_resolved else 2850.0
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_04_downstream_timeout",
        title="Slow Third-Party Gateway",
        difficulty="medium",
        instructions=(
            f"Outbound calls to external payment gateway are hanging for up to {partner_hang_ms}ms, causing thread "
            "starvation in `payment-service` and cascading to API gateway. Enable `circuit_breaker_enabled` on "
            "`payment-service` (or reduce `gateway_timeout_ms` to <= 1000) to isolate the degradation."
        ),
        scenario_spec={
            "task_id": "task_04_downstream_timeout",
            "seed": seed,
            "target_services": ["payment-service"],
            "service_overrides": {
                "payment-service": {
                    "circuit_breaker_enabled": False,
                    "config": {"gateway_timeout_ms": partner_hang_ms},
                }
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_logs", {"service": "payment-service", "filter": "timeout"}),
            ("update_config", {"service": "payment-service", "key": "circuit_breaker_enabled", "value": True}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_cascading_failure_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    flash_rps = rng.choice([4400, 4800, 5200])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        order = services.get("order-service", {})
        replicas = order.get("replicas", 2)
        is_resolved = bool(replicas >= 6)
        progress = 1.0 if is_resolved else min(0.5, max(0.0, (replicas - 2) / 4.0 * 0.5))
        error_rate = 0.05 if is_resolved else 34.0
        latency = 65.0 if is_resolved else 4200.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_05_cascading_failure",
        title="Thundering Herd Cascade",
        difficulty="hard",
        instructions=(
            f"A flash sale traffic surge ({flash_rps} RPS) has overwhelmed `order-service`, causing OOM crashes "
            "and 34% error rate. Scale `order-service` replica pool to at least 6 pods to absorb traffic "
            "and restore cluster SLO."
        ),
        scenario_spec={
            "task_id": "task_05_cascading_failure",
            "seed": seed,
            "target_services": ["order-service"],
            "service_overrides": {
                "order-service": {"replicas": 2}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_metrics", {"service": "order-service", "metric": "cpu"}),
            ("scale_service", {"service": "order-service", "replicas": 6}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_canary_leak_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    canary_split = rng.choice([5, 10, 15])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        order = services.get("order-service", {})
        weight = order.get("traffic_weight", canary_split)
        is_resolved = bool(weight == 0)
        error_rate = 0.04 if is_resolved else 6.2
        latency = 46.0 if is_resolved else 680.0
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_06_canary_leak",
        title="Memory Leak in Canary Route",
        difficulty="medium",
        instructions=(
            f"Canary deployment for `order-service` ({canary_split}% traffic) has a severe memory leak (98.4% memory, 6.2% error rate). "
            "Safely drain traffic from the failing canary route by shifting `order-service` traffic weight to 0."
        ),
        scenario_spec={
            "task_id": "task_06_canary_leak",
            "seed": seed,
            "target_services": ["order-service"],
            "service_overrides": {
                "order-service": {"traffic_weight": canary_split}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_metrics", {"service": "order-service", "metric": "memory"}),
            ("reroute_traffic", {"service": "order-service", "weight": 0}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_cost_slo_rescue_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    # Exactly 36 initial pods total:
    # api-gateway (10) + order-service (10) + db-replica (8) + payment-service (2) +
    # inventory-service (2) + recommendation-service (2) + cache-cluster (1) + db-primary (1) = 36 pods
    # Burn rate: 36 * $15/hr = $540/hr

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        total_replicas = sum(s.get("replicas", 0) for s in services.values())
        all_alive = all(s.get("replicas", 0) >= 1 for s in services.values())
        is_resolved = bool(total_replicas <= 18 and all_alive)
        progress = 1.0 if is_resolved else min(0.5, max(0.0, (36 - total_replicas) / 18.0 * 0.5))
        error_rate = 0.04
        latency = 55.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_07_cost_slo_rescue",
        title="Overprovisioned Financial Drain",
        difficulty="hard",
        instructions=(
            "Platform services are excessively overscaled (36 total pods), burning $540/hr with average CPU below 12%. "
            "Right-size `api-gateway`, `order-service`, and `db-replica` to safe capacity levels (3 pods each, and 2 for db-replica, "
            "bringing total cluster pods to <= 18) without violating latency SLOs."
        ),
        scenario_spec={
            "task_id": "task_07_cost_slo_rescue",
            "seed": seed,
            "target_services": ["api-gateway", "order-service", "db-replica"],
            "service_overrides": {
                "api-gateway": {"replicas": 10},
                "order-service": {"replicas": 10},
                "db-replica": {"replicas": 8},
                "cache-cluster": {"replicas": 1},
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("scale_service", {"service": "api-gateway", "replicas": 3}),
            ("scale_service", {"service": "order-service", "replicas": 3}),
            ("scale_service", {"service": "db-replica", "replicas": 2}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )


def build_migration_lock_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    blocked_table = rng.choice(["order_items", "orders", "inventory_logs"])
    migration_pid = rng.randint(4200, 8900)

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        db = services.get("db-primary", {})
        lock_timeout = db.get("config", {}).get("lock_timeout_ms", 0)
        is_resolved = bool(isinstance(lock_timeout, (int, float)) and 500 <= lock_timeout <= 2000)
        error_rate = 0.04 if is_resolved else 22.0
        latency = 50.0 if is_resolved else 5400.0
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_08_migration_lock",
        title="Database Migration Schema Lock",
        difficulty="hard",
        instructions=(
            f"A background migration (PID {migration_pid}) acquired an exclusive table lock on `{blocked_table}` on `db-primary`, "
            "causing write queries to block and timeout (22% error rate). Configure `lock_timeout_ms` to 1000ms on "
            "`db-primary` to abort blocking locks and restore checkout throughput."
        ),
        scenario_spec={
            "task_id": "task_08_migration_lock",
            "seed": seed,
            "target_services": ["db-primary"],
            "service_overrides": {
                "db-primary": {"config": {"lock_timeout_ms": 0}}
            },
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_logs", {"service": "db-primary", "filter": "lock"}),
            ("update_config", {"service": "db-primary", "key": "lock_timeout_ms", "value": 1000}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )
