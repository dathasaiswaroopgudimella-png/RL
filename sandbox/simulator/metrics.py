"""OpsArena: Dynamic Telemetry & Metrics Engine.

Computes realistic timeseries telemetry across latency, error rates, CPU, memory,
and throughput based on service configuration, dependency graph, and active incidents.
"""
from typing import Any, Dict, List
from .world import CloudMeshWorld

def compute_service_metrics(world: CloudMeshWorld, service_name: str, metric_type: str) -> Dict[str, Any]:
    """Generates 10-minute timeseries window for the requested metric."""
    if service_name not in world.services:
        raise ValueError(f"Unknown service '{service_name}'. Available: {list(world.services.keys())}")

    svc = world.services[service_name]
    incident = world.active_incident or {}
    task_id = incident.get("task_id", "")

    # Base healthy values
    base_error_rate = 0.05   # 0.05%
    base_latency = 45.0      # 45ms
    base_cpu = 35.0          # 35%
    base_memory = 45.0       # 45%
    base_rps = 1200          # 1200 RPS

    # Calculate dynamic effects based on active incident state
    if task_id == "task_01_cache_pressure":
        # Cache memory saturation thrashes DB
        cache_mem = world.services["cache-cluster"].memory_limit_mb
        if cache_mem < 8192:
            if service_name in ("cache-cluster", "db-primary", "order-service"):
                base_cpu = 96.5 if service_name == "db-primary" else 88.0
                base_latency = 1180.0 if service_name in ("db-primary", "order-service") else 450.0
                base_error_rate = 4.8 if service_name == "order-service" else 0.5
        else:
            # Resolved
            base_cpu = 42.0
            base_latency = 65.0
            base_error_rate = 0.08

    elif task_id == "task_02_bad_deployment":
        # Bad deployment on order-service v2.4.1
        order_ver = world.services["order-service"].version
        if order_ver == "v2.4.1":
            if service_name == "order-service":
                base_error_rate = 18.4
                base_latency = 310.0
            elif service_name == "api-gateway":
                base_error_rate = 14.2
                base_latency = 350.0
        else:
            # Rolled back to v2.4.0
            base_error_rate = 0.04
            base_latency = 52.0

    elif task_id == "task_03_db_pool_exhaustion":
        pool_size = world.services["inventory-service"].config.get("db_pool_size", 5)
        if pool_size < 20:
            if service_name == "inventory-service":
                base_error_rate = 12.8
                base_latency = 850.0
            elif service_name == "order-service":
                base_error_rate = 9.4
                base_latency = 920.0
        else:
            base_error_rate = 0.06
            base_latency = 48.0

    elif task_id == "task_04_downstream_timeout":
        cb = world.services["payment-service"].circuit_breaker_enabled
        timeout = world.services["payment-service"].config.get("gateway_timeout_ms", 3000)
        if not cb and timeout > 1000:
            if service_name in ("payment-service", "order-service", "api-gateway"):
                base_latency = 2850.0
                base_error_rate = 8.6
                base_cpu = 89.0
        else:
            # Circuit breaker or fast timeout mitigates cascading hang
            base_latency = 85.0
            base_error_rate = 0.9  # Graceful fallback degradation

    elif task_id == "task_05_cascading_failure":
        replicas = world.services["order-service"].replicas
        if replicas < 6:
            if service_name in ("order-service", "api-gateway"):
                base_error_rate = 34.0
                base_latency = 4200.0
                base_cpu = 99.0
        else:
            base_error_rate = 0.12
            base_latency = 95.0
            base_cpu = 54.0

    elif task_id == "task_06_canary_leak":
        weight = world.services["order-service"].traffic_weight
        if weight > 0:
            if service_name == "order-service":
                base_memory = 98.4
                base_error_rate = 6.2
                base_latency = 680.0
        else:
            base_memory = 42.0
            base_error_rate = 0.05
            base_latency = 50.0

    elif task_id == "task_07_cost_slo_rescue":
        # All SLOs green, but overprovisioned
        replicas = sum(s.replicas for s in world.services.values())
        if replicas > 25:
            base_cpu = 12.0  # severely underutilized
            base_latency = 35.0
            base_error_rate = 0.01
        else:
            base_cpu = 62.0  # optimal utilization
            base_latency = 55.0
            base_error_rate = 0.04

    elif task_id == "task_08_migration_lock":
        lock_cfg = world.services["db-primary"].config.get("lock_timeout_ms", 0)
        if lock_cfg == 0:
            if service_name in ("db-primary", "order-service"):
                base_latency = 5400.0
                base_error_rate = 22.0
        else:
            base_latency = 68.0
            base_error_rate = 0.08

    # Format points for the requested metric
    val_map = {
        "errors": f"{base_error_rate:.2f}%",
        "latency": f"{base_latency:.1f}ms",
        "cpu": f"{base_cpu:.1f}%",
        "memory": f"{base_memory:.1f}%",
        "rps": f"{base_rps} req/s",
    }
    raw_val = {
        "errors": base_error_rate,
        "latency": base_latency,
        "cpu": base_cpu,
        "memory": base_memory,
        "rps": base_rps,
    }

    if metric_type not in val_map:
        raise ValueError(f"Invalid metric '{metric_type}'. Must be one of: {list(val_map.keys())}")

    # Generate small 5-step timeseries window
    timeseries = []
    current = raw_val[metric_type]
    for i in range(5, 0, -1):
        # Deterministic micro-jitter
        jitter = ((i * 17) % 7 - 3) * 0.02 * current
        ts_val = max(0.0, current + jitter)
        unit = "%" if metric_type in ("errors", "cpu", "memory") else ("ms" if metric_type == "latency" else "rps")
        timeseries.append(f"T-{i*2}m: {ts_val:.1f}{unit}")

    return {
        "service": service_name,
        "metric": metric_type,
        "current_value": val_map[metric_type],
        "history": timeseries,
        "status": "CRITICAL" if (raw_val["errors"] > 2.0 or raw_val["latency"] > 300) else "HEALTHY",
    }
