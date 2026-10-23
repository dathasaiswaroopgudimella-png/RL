"""OpsArena Scenarios: 8 Deterministic Incident Response Families with Seeded Diversity.

All task instructions describe symptoms, business impact, and SLO constraints without
leaking hidden root causes or exact tool parameters.
"""
import random
from typing import Any, Dict, Tuple
from .base import TaskInstance
from sandbox.simulator.world import MIN_SAFE_REPLICAS


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
            "Production alert: The checkout flow is experiencing severe degradation with `db-primary` reporting "
            "near-100% CPU utilization and elevated query latency. Diagnose cache and database telemetry, "
            "identify why the database is being overwhelmed, and restore normal performance within operational budget limits."
        ),
        scenario_spec={
            "task_id": "task_01_cache_pressure",
            "seed": seed,
            "initial_mem": initial_mem,
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
            "Production alert: High HTTP 500 error rates detected on customer checkouts immediately following a recent "
            "deployment. Investigate service logs and telemetry across the checkout pipeline, determine the failing "
            "component and deployment status, and restore service health to meet the < 0.1% error rate SLO."
        ),
        scenario_spec={
            "task_id": "task_02_bad_deployment",
            "seed": seed,
            "bad_version": bad_version,
            "err_rate_initial": err_rate_initial,
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
            "Production alert: `inventory-service` is returning HTTP 504 Gateway Timeouts under burst checkout traffic. "
            "Investigate application logs to identify the resource bottleneck, adjust the necessary configuration parameters "
            "to support required throughput, and restore inventory responsiveness."
        ),
        scenario_spec={
            "task_id": "task_03_db_pool_exhaustion",
            "seed": seed,
            "initial_pool": initial_pool,
            "burst_rps": burst_rps,
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
        latency = 62.0 if is_resolved else (partner_hang_ms * 0.4)
        progress = 1.0 if is_resolved else 0.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_04_downstream_timeout",
        title="Slow Third-Party Gateway",
        difficulty="medium",
        instructions=(
            "Production alert: Intermittent payment processing delays are causing thread pool starvation in `payment-service` "
            "and cascading latency to upstream services. Investigate logs, identify the external dependency hang, and apply "
            "resilience controls to isolate the partner failure and bring p99 latency under 100ms."
        ),
        scenario_spec={
            "task_id": "task_04_downstream_timeout",
            "seed": seed,
            "partner_hang_ms": partner_hang_ms,
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
            "Production alert: A sudden traffic surge has caused critical queue backlogs and OutOfMemory errors across the "
            "ordering pipeline, pushing error rates over 30%. Analyze workload demand and service capacity, and scale the "
            "bottleneck service appropriately to absorb the surge and restore cluster SLOs."
        ),
        scenario_spec={
            "task_id": "task_05_cascading_failure",
            "seed": seed,
            "flash_rps": flash_rps,
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
            "Production alert: Memory usage alerts triggered across the order-processing tier with elevated error rates on "
            "canary traffic. Inspect canary and primary telemetry, locate the malfunctioning route, and reroute ingress traffic "
            "to safeguard customer traffic."
        ),
        scenario_spec={
            "task_id": "task_06_canary_leak",
            "seed": seed,
            "canary_split": canary_split,
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
    gw_pods = rng.choice([10, 12])
    order_pods = rng.choice([10, 12])
    replica_pods = rng.choice([8, 10])
    # Baseline non-target replicas:
    # payment-service (2) + inventory-service (2) + recommendation-service (2) + cache-cluster (1) + db-primary (1) = 8
    initial_pods = gw_pods + order_pods + replica_pods + 8
    burn_rate = initial_pods * 15  # $15/hr per pod ($540/hr to $630/hr)

    def verify(services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        total_replicas = sum(s.get("replicas", 0) for s in services.values())
        # Rigorous exploit prevention: verify every service satisfies minimum safe operational capacity
        safe_capacity = all(s.get("replicas", 0) >= MIN_SAFE_REPLICAS.get(name, 1) for name, s in services.items())

        if not safe_capacity:
            # Undersized cluster exploit: capacity starvation breaches SLO
            return False, 18.5, 1250.0, 0.0

        is_resolved = bool(total_replicas <= 18)
        progress = 1.0 if is_resolved else min(0.5, max(0.0, (initial_pods - total_replicas) / (initial_pods - 18.0) * 0.5))
        error_rate = 0.04
        latency = 55.0
        return is_resolved, error_rate, latency, progress

    return TaskInstance(
        task_id="task_07_cost_slo_rescue",
        title="Overprovisioned Financial Drain",
        difficulty="hard",
        instructions=(
            f"Production alert: Infrastructure billing reports show severe over-provisioning across multiple service tiers "
            f"with cluster CPU utilization averaging under 15% (${burn_rate}/hr burn rate). Audit service topologies and right-size "
            f"the over-allocated services to bring total cluster pods to 18 or fewer, while preserving sufficient capacity "
            f"for all services to meet the < 100ms latency and < 0.1% error rate SLOs."
        ),
        scenario_spec={
            "task_id": "task_07_cost_slo_rescue",
            "seed": seed,
            "gw_pods": gw_pods,
            "order_pods": order_pods,
            "replica_pods": replica_pods,
            "initial_pods": initial_pods,
            "burn_rate": burn_rate,
            "target_services": ["api-gateway", "order-service", "db-replica"],
            "service_overrides": {
                "api-gateway": {"replicas": gw_pods},
                "order-service": {"replicas": order_pods},
                "db-replica": {"replicas": replica_pods},
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
            "Production alert: Transaction pile-ups and connection exhaustion on `db-primary` are blocking checkout operations, "
            "resulting in elevated 504 errors. Investigate database logs to determine the cause of query blocking, "
            "and configure database timeout policies to prevent long-held locks from disrupting online traffic."
        ),
        scenario_spec={
            "task_id": "task_08_migration_lock",
            "seed": seed,
            "blocked_table": blocked_table,
            "migration_pid": migration_pid,
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
