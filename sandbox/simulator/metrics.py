"""OpsArena: Dynamic Telemetry & Metrics Engine.

Computes realistic timeseries telemetry across latency, error rates, CPU, memory,
and throughput based on service configuration, dependency graph, and active incidents.
Serves as the single source of truth for both query_metrics and task verification.
"""
from typing import Any, Dict, List, Tuple
from .world import CloudMeshWorld


def compute_service_metrics(world: CloudMeshWorld, service_name: str, metric_type: str) -> Dict[str, Any]:
    """Generates 10-minute timeseries window for the requested metric."""
    if service_name not in world.services:
        raise ValueError(f"Unknown service '{service_name}'. Available: {list(world.services.keys())}")

    svc = world.services[service_name]
    incident = world.active_incident or {}
    task_id = incident.get("task_id", "")

    # Normalize metric type aliases
    m_lower = metric_type.lower()
    if m_lower in ("qps", "rps", "throughput"):
        norm_metric = "rps"
    elif m_lower in ("errors", "error", "error_rate"):
        norm_metric = "errors"
    elif m_lower in ("latency", "lat", "p99", "p99_latency"):
        norm_metric = "latency"
    elif m_lower in ("cpu", "cpu_pct"):
        norm_metric = "cpu"
    elif m_lower in ("memory", "mem", "memory_pct"):
        norm_metric = "memory"
    else:
        norm_metric = m_lower

    # Base healthy cluster values (SLO targets: error < 0.1%, latency < 100ms)
    base_error_rate = 0.04   # 0.04% (SLO compliant: < 0.1%)
    base_latency = 45.0      # 45.0ms (SLO compliant: < 100ms)
    base_cpu = 35.0          # 35%
    base_memory = 45.0       # 45%
    base_rps = 1200          # 1200 RPS

    # Check for regressions caused by misconfiguration or unneeded downscaling of non-target services
    if svc.replicas < 1:
        base_error_rate = 100.0
        base_latency = 9999.0
        base_cpu = 0.0
    elif service_name == "api-gateway" and svc.replicas < 2 and task_id != "task_07_cost_slo_rescue":
        # API gateway starved
        base_error_rate = 15.0
        base_latency = 1200.0
        base_cpu = 98.0
    elif service_name == "payment-service" and svc.replicas < 2 and task_id != "task_07_cost_slo_rescue":
        base_error_rate = 12.0
        base_latency = 1100.0
        base_cpu = 95.0

    # Calculate dynamic effects based on active incident state
    if task_id == "task_01_cache_pressure":
        cache_mem = world.services["cache-cluster"].memory_limit_mb
        cache_reps = world.services["cache-cluster"].replicas
        if cache_reps < 2 and cache_mem < 8192:
            if service_name in ("cache-cluster", "db-primary", "order-service"):
                base_cpu = 96.5 if service_name == "db-primary" else 88.0
                base_latency = 1180.0 if service_name in ("db-primary", "order-service") else 450.0
                base_error_rate = 4.8 if service_name == "order-service" else 0.5
        else:
            # Resolved
            base_cpu = 42.0
            base_latency = 48.0
            base_error_rate = 0.04

    elif task_id == "task_02_bad_deployment":
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
        if isinstance(pool_size, (int, float)) and pool_size >= 25:
            base_error_rate = 0.04
            base_latency = 45.0
        else:
            if service_name == "inventory-service":
                base_error_rate = 12.8
                base_latency = 850.0
            elif service_name == "order-service":
                base_error_rate = 9.4
                base_latency = 920.0

    elif task_id == "task_04_downstream_timeout":
        cb = world.services["payment-service"].circuit_breaker_enabled
        timeout = world.services["payment-service"].config.get("gateway_timeout_ms", 3000)
        is_resolved = bool(cb or (isinstance(timeout, (int, float)) and timeout <= 1000))
        if not is_resolved:
            if service_name in ("payment-service", "order-service", "api-gateway"):
                base_latency = 2850.0
                base_error_rate = 8.6
                base_cpu = 89.0
        else:
            # Circuit breaker or fast timeout cleanly isolates partner hang
            base_latency = 62.0
            base_error_rate = 0.04  # Strictly below 0.1% SLO

    elif task_id == "task_05_cascading_failure":
        replicas = world.services["order-service"].replicas
        if replicas < 6:
            if service_name in ("order-service", "api-gateway"):
                base_error_rate = 34.0
                base_latency = 4200.0
                base_cpu = 99.0
        else:
            # Scaled to at least 6 replicas - absorbs flash surge
            base_error_rate = 0.05  # Strictly below 0.1% SLO
            base_latency = 65.0     # Strictly below 100ms SLO
            base_cpu = 52.0

    elif task_id == "task_06_canary_leak":
        weight = world.services["order-service"].traffic_weight
        if weight > 0:
            if service_name == "order-service":
                base_memory = 98.4
                base_error_rate = 6.2
                base_latency = 680.0
        else:
            base_memory = 42.0
            base_error_rate = 0.04
            base_latency = 46.0

    elif task_id == "task_07_cost_slo_rescue":
        total_replicas = sum(s.replicas for s in world.services.values())
        if total_replicas > 18:
            base_cpu = 12.0  # severely underutilized
            base_latency = 35.0
            base_error_rate = 0.01
        else:
            base_cpu = 58.0  # optimal utilization
            base_latency = 55.0
            base_error_rate = 0.04

    elif task_id == "task_08_migration_lock":
        lock_cfg = world.services["db-primary"].config.get("lock_timeout_ms", 0)
        is_resolved = isinstance(lock_cfg, (int, float)) and (500 <= lock_cfg <= 2000)
        if not is_resolved:
            if service_name in ("db-primary", "order-service"):
                base_latency = 5400.0
                base_error_rate = 22.0
        else:
            base_latency = 50.0
            base_error_rate = 0.04

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

    if norm_metric not in val_map:
        raise ValueError(f"Invalid metric '{metric_type}'. Must be one of: latency, errors, cpu, memory, rps, qps")

    # Generate small 5-step timeseries window
    timeseries = []
    current = raw_val[norm_metric]
    for i in range(5, 0, -1):
        jitter = ((i * 17) % 7 - 3) * 0.02 * current
        ts_val = max(0.0, current + jitter)
        unit = "%" if norm_metric in ("errors", "cpu", "memory") else ("ms" if norm_metric == "latency" else "rps")
        timeseries.append(f"T-{i*2}m: {ts_val:.1f}{unit}")

    return {
        "service": service_name,
        "metric": norm_metric,
        "current_value": val_map[norm_metric],
        "history": timeseries,
        "status": "CRITICAL" if (raw_val["errors"] > 2.0 or raw_val["latency"] > 300) else "HEALTHY",
        "raw_error_rate": base_error_rate,
        "raw_latency": base_latency,
    }
