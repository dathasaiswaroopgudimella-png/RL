"""OpsArena: Distributed Trace & Structured Log Generator.

Generates realistic application and access logs reflecting current incident state
while strictly redacting secrets and enforcing the 4,000 character output bound.
"""
from typing import List, Optional
from .world import CloudMeshWorld

def generate_service_logs(world: CloudMeshWorld, service_name: str, filter_str: Optional[str] = None) -> List[str]:
    """Generates structured log lines for the given service."""
    if service_name not in world.services:
        raise ValueError(f"Unknown service '{service_name}'")

    incident = world.active_incident or {}
    task_id = incident.get("task_id", "")
    svc = world.services[service_name]

    lines = []

    if task_id == "task_01_cache_pressure":
        if service_name == "db-primary":
            lines = [
                'WARN  [pool-1-worker-3] org.postgresql.core: Connection backlog reaching threshold: 98/100 connections in use',
                'ERROR [pool-1-worker-7] org.postgresql.core: Query latency exceeded 1000ms: SELECT * FROM products WHERE id = ?',
                'WARN  [pool-1-worker-9] org.postgresql.core: High CPU alert: postgres backend process 4128 consuming 96.2% CPU',
                'INFO  [healthcheck] org.postgresql.core: checkpoint starting: time',
                'ERROR [pool-1-worker-4] org.postgresql.core: Slow query: SELECT * FROM inventory WHERE sku = ? (duration: 1240ms)',
            ]
        elif service_name == "cache-cluster":
            lines = [
                'WARN  [redis-server] Eviction policy allkeys-lru active. Memory usage: 4094MB / 4096MB (99.9%)',
                'WARN  [redis-server] Maxmemory limit reached! Evicting keys at 14,200 keys/sec',
                'INFO  [redis-server] Cache hit ratio degraded from 98.4% to 22.1%',
            ]
        else:
            lines = [f'INFO  [{service_name}] Healthcheck OK - 200 OK latency=45ms']

    elif task_id == "task_02_bad_deployment":
        if service_name == "order-service" and svc.version == "v2.4.1":
            lines = [
                'INFO  [main] Deployment rollout complete: order-service version=v2.4.1 commit=8a7c2f',
                'ERROR [http-nio-8080-exec-1] com.cloudmesh.orders.CheckoutController: NullPointerException at CheckoutService.processDiscounts(CheckoutService.kt:142)',
                'ERROR [http-nio-8080-exec-4] com.cloudmesh.orders.CheckoutController: Failed to complete checkout for order_id=ord_94821 - HTTP 500 Internal Server Error',
                'ERROR [http-nio-8080-exec-9] com.cloudmesh.orders.CheckoutController: NullPointerException at CheckoutService.processDiscounts(CheckoutService.kt:142)',
                'WARN  [metrics-reporter] Error rate threshold breached: 18.4% (> 1.0% SLO target)',
            ]
        else:
            lines = [
                f'INFO  [main] order-service active version={svc.version}',
                'INFO  [http-nio-8080-exec-1] com.cloudmesh.orders.OrderController: Checkout order_id=ord_11029 completed in 48ms (200 OK)',
            ]

    elif task_id == "task_03_db_pool_exhaustion":
        pool_size = svc.config.get("db_pool_size", 5)
        if service_name == "inventory-service" and pool_size < 20:
            lines = [
                f'WARN  [HikariPool-1] Connection pool size is {pool_size}. Active connections: {pool_size}/{pool_size}',
                'ERROR [HikariPool-1] Connection timeout after 800ms: request timed out waiting for connection from pool',
                'ERROR [web-exec-3] com.cloudmesh.inventory.StockService: DatabaseTimeoutException: Unable to acquire connection within 800ms',
                'WARN  [web-exec-8] Response returned HTTP 504 Gateway Timeout to caller order-service',
            ]
        else:
            lines = [f'INFO  [HikariPool-1] Pool initialized. Active: 4/{pool_size}, Idle: {pool_size-4}']

    elif task_id == "task_04_downstream_timeout":
        cb = world.services["payment-service"].circuit_breaker_enabled
        if service_name == "payment-service" and not cb:
            lines = [
                'WARN  [gateway-client] Outbound request to external payment processor gateway.partner.net slow: 8200ms',
                'ERROR [gateway-client] ReadTimeoutException: Read timed out after 3000ms connecting to payment gateway',
                'WARN  [thread-pool] Inbound request queue filling up: 188/200 threads blocked waiting on external gateway',
            ]
        else:
            lines = [f'INFO  [payment-service] Circuit breaker state: {"OPEN" if cb else "CLOSED"}, latency=55ms']

    elif task_id == "task_05_cascading_failure":
        if service_name == "order-service" and svc.replicas < 6:
            lines = [
                'WARN  [ingress] High traffic surge detected: incoming RPS 4,800 exceeds replica capacity',
                'ERROR [worker-1] java.lang.OutOfMemoryError: GC overhead limit exceeded on pod order-service-6f8b9-x2',
                'ERROR [worker-4] Connection reset by peer: client closed connection during queue backlog',
            ]
        else:
            lines = [f'INFO  [order-service] Cluster capacity healthy across {svc.replicas} active replicas.']

    elif task_id == "task_06_canary_leak":
        if service_name == "order-service" and svc.traffic_weight > 0:
            lines = [
                'WARN  [jvm-monitor] Heap memory usage on canary deployment v2.5.0-canary: 98.4% (2015MB / 2048MB)',
                'ERROR [jvm-monitor] java.lang.OutOfMemoryError: Java heap space during image thumbnail cache',
                'WARN  [traffic-router] Canary route receiving 10% traffic experiencing 6.2% error rate',
            ]
        else:
            lines = [f'INFO  [traffic-router] Traffic distribution: 100% primary stable, canary route weight=0%']

    elif task_id == "task_07_cost_slo_rescue":
        lines = [
            f'INFO  [billing-agent] Current resource burn rate: ${sum(s.replicas * 15.0 for s in world.services.values()):.2f}/hour',
            'WARN  [cost-optimizer] Platform overprovisioned: CPU utilization averaging 12% across 32 active container instances',
        ]

    elif task_id == "task_08_migration_lock":
        lines = [
            'WARN  [db-engine] Process PID 9482 holding ACCESS EXCLUSIVE lock on table `order_items`',
            'ERROR [db-engine] Transaction 82014 blocked waiting for lock on `order_items` for 5420ms',
            'WARN  [api] HTTP 504 Gateway Timeout returned on order creation requests',
        ]

    else:
        lines = [
            f'INFO  [{service_name}] Platform operating within normal nominal baselines',
            f'INFO  [{service_name}] Request throughput: 1,200 RPS, error_rate=0.04%, p99=48ms',
        ]

    if filter_str:
        lines = [line for line in lines if filter_str.lower() in line.lower()]

    return lines or [f"INFO  [{service_name}] (no logs matching filter '{filter_str}')"]
