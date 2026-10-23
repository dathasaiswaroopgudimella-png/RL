"""OpsArena Scenarios: 8 Deterministic Incident Response Families."""
import random
from typing import Any, Dict, Tuple
from .base import TaskInstance

def build_cache_pressure_task(seed: int) -> TaskInstance:
    rng = random.Random(seed)
    initial_mem = rng.choice([2048, 4096])

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        cache = services.get("cache-cluster", {})
        replicas = cache.get("replicas", 1)
        mem = cache.get("memory_limit_mb", 4096)
        is_resolved = (replicas >= 2 or mem >= 8192)
        error_rate = 0.08 if is_resolved else 4.8
        latency = 65.0 if is_resolved else 1180.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_01_cache_pressure",
        title="Redis Eviction Storm",
        difficulty="easy",
        instructions=("A cache memory eviction storm on `cache-cluster` is causing a thundering herd on "
                      "`db-primary`, spiking CPU to 96% and latency to 1180ms. Investigate logs, scale "
                      "`cache-cluster` to at least 2 replicas to expand memory capacity, and resolve the incident."),
        scenario_spec={
            "task_id": "task_01_cache_pressure",
            "service_overrides": {
                "cache-cluster": {"replicas": 1, "memory_limit_mb": initial_mem}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        order_svc = services.get("order-service", {})
        is_resolved = (order_svc.get("version") == "v2.4.0")
        error_rate = 0.04 if is_resolved else 18.4
        latency = 52.0 if is_resolved else 310.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_02_bad_deployment",
        title="Bad Release Rollback",
        difficulty="easy",
        instructions=("Following deployment of `v2.4.1` on `order-service`, users are experiencing HTTP 500 errors "
                      "(18.4% error rate). Check the logs and metrics, roll back `order-service` to previous stable "
                      "release `v2.4.0`, and verify restoration."),
        scenario_spec={
            "task_id": "task_02_bad_deployment",
            "service_overrides": {
                "order-service": {"version": "v2.4.1"}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        inv = services.get("inventory-service", {})
        pool_size = inv.get("config", {}).get("db_pool_size", 5)
        is_resolved = (pool_size >= 20)
        error_rate = 0.06 if is_resolved else 12.8
        latency = 48.0 if is_resolved else 850.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_03_db_pool_exhaustion",
        title="Connection Pool Starvation",
        difficulty="medium",
        instructions=("Under checkout bursts, `inventory-service` is timing out waiting for database connections "
                      "(HTTP 504 errors). Diagnose the connection bottleneck and update `inventory-service`'s "
                      "`db_pool_size` configuration to at least 25."),
        scenario_spec={
            "task_id": "task_03_db_pool_exhaustion",
            "service_overrides": {
                "inventory-service": {"config": {"db_pool_size": 5}}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        pmt = services.get("payment-service", {})
        cb = pmt.get("circuit_breaker_enabled", False)
        timeout = pmt.get("config", {}).get("gateway_timeout_ms", 3000)
        is_resolved = (cb or timeout <= 1000)
        error_rate = 0.05 if is_resolved else 8.6
        latency = 72.0 if is_resolved else 2850.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_04_downstream_timeout",
        title="Slow Third-Party Gateway",
        difficulty="medium",
        instructions=("Outbound calls to external payment gateway are hanging for up to 8 seconds, causing thread "
                      "starvation in `payment-service` and cascading to API gateway. Enable `circuit_breaker_enabled` "
                      "on `payment-service` to isolate the degradation."),
        scenario_spec={
            "task_id": "task_04_downstream_timeout",
            "service_overrides": {
                "payment-service": {"circuit_breaker_enabled": False, "config": {"gateway_timeout_ms": 3000}}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        order = services.get("order-service", {})
        replicas = order.get("replicas", 2)
        is_resolved = (replicas >= 6)
        error_rate = 0.12 if is_resolved else 34.0
        latency = 95.0 if is_resolved else 4200.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_05_cascading_failure",
        title="Thundering Herd Cascade",
        difficulty="hard",
        instructions=("A flash sale traffic surge (4,800 RPS) has overwhelmed `order-service`, causing OOM crashes "
                      "and 34% error rate. Scale `order-service` replica pool to at least 6 pods to absorb traffic "
                      "and restore cluster SLO."),
        scenario_spec={
            "task_id": "task_05_cascading_failure",
            "service_overrides": {
                "order-service": {"replicas": 2}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        order = services.get("order-service", {})
        weight = order.get("traffic_weight", 10)
        is_resolved = (weight == 0)
        error_rate = 0.05 if is_resolved else 6.2
        latency = 50.0 if is_resolved else 680.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_06_canary_leak",
        title="Memory Leak in Canary Route",
        difficulty="medium",
        instructions=("Canary deployment for `order-service` has a severe memory leak (98.4% memory, 6.2% error rate). "
                      "Safely drain traffic from the failing canary route by shifting `order-service` traffic weight to 0."),
        scenario_spec={
            "task_id": "task_06_canary_leak",
            "service_overrides": {
                "order-service": {"traffic_weight": 10}
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        total_replicas = sum(s.get("replicas", 2) for s in services.values())
        is_resolved = (total_replicas <= 18)
        error_rate = 0.04 if is_resolved else 0.04
        latency = 55.0 if is_resolved else 55.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_07_cost_slo_rescue",
        title="Overprovisioned Financial Drain",
        difficulty="hard",
        instructions=("Platform services are excessively overscaled (36 total pods), burning $450/hr with average CPU "
                      "below 12%. Right-size `api-gateway`, `order-service`, and `db-replica` to safe capacity levels "
                      "(3 pods each, and 2 for db-replica, bringing total pods to <= 18) without violating latency SLOs."),
        scenario_spec={
            "task_id": "task_07_cost_slo_rescue",
            "service_overrides": {
                "api-gateway": {"replicas": 10},
                "order-service": {"replicas": 10},
                "db-replica": {"replicas": 8},
            }
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
    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        db = services.get("db-primary", {})
        lock_timeout = db.get("config", {}).get("lock_timeout_ms", 0)
        is_resolved = (lock_timeout > 0)
        error_rate = 0.08 if is_resolved else 22.0
        latency = 68.0 if is_resolved else 5400.0
        return is_resolved, error_rate, latency

    return TaskInstance(
        task_id="task_08_migration_lock",
        title="Database Migration Schema Lock",
        difficulty="hard",
        instructions=("A background migration acquired an exclusive table lock on `order_items` on `db-primary`, causing "
                      "write queries to block and timeout (22% error rate). Configure `lock_timeout_ms` to 1000ms on "
                      "`db-primary` to abort blocking locks and restore checkout throughput."),
        scenario_spec={
            "task_id": "task_08_migration_lock",
            "service_overrides": {
                "db-primary": {"config": {"lock_timeout_ms": 0}}
            }
        },
        oracle_actions=[
            ("get_topology", {}),
            ("query_logs", {"service": "db-primary", "filter": "lock"}),
            ("update_config", {"service": "db-primary", "key": "lock_timeout_ms", "value": 1000}),
            ("finish", {}),
        ],
        verifier_fn=verify,
    )
