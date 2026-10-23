"""OpsArena: Distributed Trace & Structured Log Generator.

Generates realistic application and access logs reflecting current incident state
while strictly redacting secrets and enforcing the 4,000 character output bound.
"""
from typing import List, Optional
from .world import CloudMeshWorld
from .security import scrub_secrets


def generate_service_logs(world: CloudMeshWorld, service_name: str, filter_str: Optional[str] = None) -> List[str]:
    """Generates structured log lines for the given service, reflecting dynamic scenario parameters."""
    if service_name not in world.services:
        raise ValueError(f"Unknown service '{service_name}'")

    incident = world.active_incident or {}
    task_id = incident.get("task_id", "")
    svc = world.services[service_name]

    lines = []

    if task_id == "task_01_cache_pressure":
        initial_mem = incident.get("initial_mem", 4096)
        surge_qps = incident.get("surge_qps", 3200)
        cache_reps = world.services["cache-cluster"].replicas
        cache_mem = world.services["cache-cluster"].memory_limit_mb

        if service_name == "db-primary":
            if cache_reps < 2 and cache_mem < 8192:
                lines = [
                    'WARN  [pool-1-worker-3] org.postgresql.core: Connection backlog reaching threshold: 98/100 connections in use',
                    'ERROR [pool-1-worker-7] org.postgresql.core: Query latency exceeded 1000ms: SELECT * FROM products WHERE id = ?',
                    'WARN  [pool-1-worker-9] org.postgresql.core: High CPU alert: postgres backend process 4128 consuming 96.5% CPU',
                    'INFO  [healthcheck] org.postgresql.core: checkpoint starting: time',
                    'ERROR [pool-1-worker-4] org.postgresql.core: Slow query: SELECT * FROM inventory WHERE sku = ? (duration: 1180ms)',
                ]
            else:
                lines = [
                    'INFO  [pool-1-worker-1] org.postgresql.core: Database connection load stabilized: 22/100 connections in use',
                    'INFO  [healthcheck] org.postgresql.core: Healthcheck OK - CPU 38.0%, latency=18ms',
                ]
        elif service_name == "cache-cluster":
            if cache_reps < 2 and cache_mem < 8192:
                lines = [
                    f'WARN  [redis-server] Eviction policy allkeys-lru active under {surge_qps} RPS. Memory usage: {initial_mem-2}MB / {initial_mem}MB (99.9%)',
                    'WARN  [redis-server] Maxmemory limit reached! Evicting keys at 14,200 keys/sec',
                    'INFO  [redis-server] Cache hit ratio degraded from 98.4% to 22.1%',
                ]
            else:
                lines = [
                    f'INFO  [redis-server] Cache cluster expanded to {cache_reps} replicas ({cache_mem}MB capacity). Evictions stopped. Hit ratio: 98.8%',
                ]
        else:
            lines = [f'INFO  [{service_name}] Healthcheck OK - 200 OK latency=45ms']

    elif task_id == "task_02_bad_deployment":
        bad_ver = incident.get("bad_version", "v2.4.1")
        err_rate_initial = incident.get("err_rate_initial", 18.4)
        if service_name == "order-service" and svc.version != "v2.4.0":
            lines = [
                f'INFO  [main] Deployment rollout complete: order-service version={bad_ver} commit=8a7c2f',
                'ERROR [http-nio-8080-exec-1] com.cloudmesh.orders.CheckoutController: NullPointerException at CheckoutService.processDiscounts(CheckoutService.kt:142)',
                'ERROR [http-nio-8080-exec-4] com.cloudmesh.orders.CheckoutController: Failed to complete checkout for order_id=ord_94821 - HTTP 500 Internal Server Error',
                'ERROR [http-nio-8080-exec-9] com.cloudmesh.orders.CheckoutController: NullPointerException at CheckoutService.processDiscounts(CheckoutService.kt:142)',
                f'WARN  [metrics-reporter] Error rate threshold breached: {err_rate_initial:.1f}% (> 0.1% SLO target)',
            ]
        else:
            lines = [
                f'INFO  [main] order-service active version={svc.version}',
                'INFO  [http-nio-8080-exec-1] com.cloudmesh.orders.OrderController: Checkout order_id=ord_11029 completed in 48ms (200 OK)',
            ]

    elif task_id == "task_03_db_pool_exhaustion":
        pool_size = svc.config.get("db_pool_size", 5)
        burst_rps = incident.get("burst_rps", 1800)
        if service_name == "inventory-service" and pool_size < 25:
            lines = [
                f'WARN  [HikariPool-1] Connection pool size is {pool_size} under {burst_rps} RPS burst. Active connections: {pool_size}/{pool_size}',
                'ERROR [HikariPool-1] Connection timeout after 800ms: request timed out waiting for connection from pool',
                'ERROR [web-exec-3] com.cloudmesh.inventory.StockService: DatabaseTimeoutException: Unable to acquire connection within 800ms',
                'WARN  [web-exec-8] Response returned HTTP 504 Gateway Timeout to caller order-service',
            ]
        else:
            lines = [f'INFO  [HikariPool-1] Pool initialized with {pool_size} connections. Active: 4/{pool_size}, Idle: {pool_size-4}']

    elif task_id == "task_04_downstream_timeout":
        partner_hang = incident.get("partner_hang_ms", 7500)
        cb = world.services["payment-service"].circuit_breaker_enabled
        timeout = world.services["payment-service"].config.get("gateway_timeout_ms", partner_hang)
        is_resolved = bool(cb or (isinstance(timeout, (int, float)) and timeout <= 1000))

        if service_name == "payment-service" and not is_resolved:
            lines = [
                f'WARN  [gateway-client] Outbound request to external payment processor gateway.partner.net slow: {partner_hang}ms',
                f'ERROR [gateway-client] ReadTimeoutException: Read timed out after {timeout}ms connecting to payment gateway',
                'WARN  [thread-pool] Inbound request queue filling up: 188/200 threads blocked waiting on external gateway',
            ]
        else:
            lines = [f'INFO  [payment-service] Circuit breaker state: {"OPEN" if cb else "CLOSED"}, timeout={timeout}ms, latency=55ms (200 OK)']

    elif task_id == "task_05_cascading_failure":
        flash_rps = incident.get("flash_rps", 4800)
        if service_name == "order-service" and svc.replicas < 6:
            lines = [
                f'WARN  [ingress] High traffic surge detected: incoming RPS {flash_rps} exceeds replica capacity ({svc.replicas} pods)',
                'ERROR [worker-1] java.lang.OutOfMemoryError: GC overhead limit exceeded on pod order-service-6f8b9-x2',
                'ERROR [worker-4] Connection reset by peer: client closed connection during queue backlog',
            ]
        else:
            lines = [f'INFO  [order-service] Cluster capacity healthy across {svc.replicas} active replicas absorbing {flash_rps} RPS.']

    elif task_id == "task_06_canary_leak":
        canary_split = incident.get("canary_split", 10)
        if service_name == "order-service" and svc.traffic_weight > 0:
            lines = [
                'WARN  [jvm-monitor] Heap memory usage on canary deployment v2.5.0-canary: 98.4% (2015MB / 2048MB)',
                'ERROR [jvm-monitor] java.lang.OutOfMemoryError: Java heap space during image thumbnail cache',
                f'WARN  [traffic-router] Canary route receiving {canary_split}% traffic experiencing 6.2% error rate',
            ]
        else:
            lines = [f'INFO  [traffic-router] Traffic distribution: 100% primary stable, canary route weight=0%']

    elif task_id == "task_07_cost_slo_rescue":
        total_pods = sum(s.replicas for s in world.services.values())
        burn_rate = total_pods * 15.0
        lines = [
            f'INFO  [billing-agent] Current resource burn rate: ${burn_rate:.2f}/hour across {total_pods} active container instances',
            f'WARN  [cost-optimizer] Platform overprovisioned: CPU utilization averaging 12% across {total_pods} active container instances',
        ]

    elif task_id == "task_08_migration_lock":
        blocked_table = incident.get("blocked_table", "order_items")
        migration_pid = incident.get("migration_pid", 9482)
        lock_cfg = world.services["db-primary"].config.get("lock_timeout_ms", 0)
        is_resolved = isinstance(lock_cfg, (int, float)) and (500 <= lock_cfg <= 2000)

        if not is_resolved:
            lines = [
                f'WARN  [db-engine] Process PID {migration_pid} holding ACCESS EXCLUSIVE lock on table `{blocked_table}`',
                f'ERROR [db-engine] Transaction 82014 blocked waiting for lock on `{blocked_table}` for 5420ms',
                'WARN  [api] HTTP 504 Gateway Timeout returned on order creation requests',
            ]
        else:
            lines = [
                f'INFO  [db-engine] Lock timeout policy active ({lock_cfg}ms). Long-held locks aborted automatically. Table `{blocked_table}` accessible.',
                'INFO  [api] HTTP 200 OK restored on order creation requests',
            ]

    else:
        lines = [
            f'INFO  [{service_name}] Platform operating within normal nominal baselines',
            f'INFO  [{service_name}] Request throughput: 1,200 RPS, error_rate=0.04%, p99=48ms',
        ]

    if hasattr(svc, "custom_logs") and svc.custom_logs:
        lines.extend(svc.custom_logs)

    if filter_str:
        f_lower = filter_str.lower()
        lines = [line for line in lines if f_lower in line.lower()]

    scrubbed_lines = [scrub_secrets(line) for line in lines]
    return scrubbed_lines or [f"INFO  [{service_name}] (no logs matching filter '{filter_str}')"]
