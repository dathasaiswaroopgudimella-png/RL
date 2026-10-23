"""OpsArena: Action Handlers & Tool Implementations.

Executes typed, schema-validated operational actions against the CloudMeshWorld state machine.
Enforces budget deductions, boundary checks, and format sanitization.
"""
from typing import Any, Dict
from .world import CloudMeshWorld
from .metrics import compute_service_metrics
from .logs import generate_service_logs

def action_get_topology(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    ok, err = world.deduct_cost(1.0)
    if not ok:
        return f"error: {err}"

    topo = {}
    for name, s in world.services.items():
        topo[name] = {
            "tier": s.tier,
            "replicas": s.replicas,
            "version": s.version,
            "dependencies": s.dependencies,
            "circuit_breaker": s.circuit_breaker_enabled,
        }
    return f"CloudMesh Services Topology (Active Budget Spent: ${world.cost_spent:.2f}):\n" + \
           "\n".join(f"- {name} [{s['tier']}]: {s['replicas']} pods, ver={s['version']}, deps={s['dependencies']}"
                     for name, s in topo.items())

def action_query_metrics(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    metric = args.get("metric", "latency")

    ok, err = world.deduct_cost(2.0)
    if not ok:
        return f"error: {err}"

    res = compute_service_metrics(world, service, metric)
    history_str = ", ".join(res["history"])
    return f"Service '{service}' metric '{metric}' (status: {res['status']}):\n" \
           f"Current: {res['current_value']}\n" \
           f"Recent Window: [{history_str}]"

def action_query_logs(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    filter_str = args.get("filter")

    ok, err = world.deduct_cost(3.0)
    if not ok:
        return f"error: {err}"

    lines = generate_service_logs(world, service, filter_str)
    return f"Log tail for '{service}' (matching filter '{filter_str or '*'}'):\n" + "\n".join(lines)

def action_scale_service(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    replicas = args.get("replicas")

    if service not in world.services:
        return f"error: unknown service '{service}'"
    if not isinstance(replicas, int) or replicas < 1 or replicas > 20:
        return f"error: replicas must be an integer between 1 and 20 (got {replicas})"

    old_replicas = world.services[service].replicas
    cost = abs(replicas - old_replicas) * 2.0 + 3.0
    ok, err = world.deduct_cost(cost)
    if not ok:
        return f"error: {err}"

    world.services[service].replicas = replicas
    # If scaling cache memory in cache-pressure
    if service == "cache-cluster":
        world.services["cache-cluster"].memory_limit_mb = replicas * 4096

    world.action_history.append({"action": "scale_service", "service": service, "from": old_replicas, "to": replicas})
    return f"Successfully scaled '{service}' from {old_replicas} to {replicas} replicas (Cost: ${cost:.2f})."

def action_rollback_release(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    target_version = args.get("target_version", "")

    if service not in world.services:
        return f"error: unknown service '{service}'"

    ALLOWED_RELEASES = {
        "order-service": ["v2.4.0", "v2.4.1"],
        "payment-service": ["v1.8.4", "v1.9.0"],
        "inventory-service": ["v3.1.0", "v3.1.2"],
    }
    if target_version not in ALLOWED_RELEASES.get(service, []):
        return f"error: target_version '{target_version}' not found in release registry for {service}"

    cost = 20.0
    ok, err = world.deduct_cost(cost)
    if not ok:
        return f"error: {err}"

    prev = world.services[service].version
    world.services[service].version = target_version
    world.action_history.append({"action": "rollback_release", "service": service, "from": prev, "to": target_version})
    return f"Deployment rollback initiated: '{service}' reverted from {prev} to {target_version} (Cost: ${cost:.2f}). Deployment healthy."

CONFIG_KEY_SPECS = {
    "db_pool_size": {"type": int, "min": 1, "max": 100, "desc": "integer between 1 and 100"},
    "lock_timeout_ms": {"type": int, "min": 0, "max": 60000, "desc": "integer between 0 and 60000"},
    "gateway_timeout_ms": {"type": int, "min": 100, "max": 30000, "desc": "integer between 100 and 30000"},
    "timeout_ms": {"type": int, "min": 100, "max": 30000, "desc": "integer between 100 and 30000"},
    "max_connections": {"type": int, "min": 1, "max": 1000, "desc": "integer between 1 and 1000"},
    "rate_limit_rps": {"type": int, "min": 100, "max": 50000, "desc": "integer between 100 and 50000"},
    "circuit_breaker_enabled": {"type": bool, "desc": "boolean true or false"},
    "cache_enabled": {"type": bool, "desc": "boolean true or false"},
}

def action_update_config(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    key = args.get("key", "")
    value = args.get("value")

    if service not in world.services:
        return f"error: unknown service '{service}'"

    if key not in CONFIG_KEY_SPECS:
        return f"error: configuration key '{key}' is not allowed or unsupported. Allowed: {sorted(list(CONFIG_KEY_SPECS.keys()))}"

    spec = CONFIG_KEY_SPECS[key]
    validated_value = None

    if spec["type"] is bool:
        if isinstance(value, bool):
            validated_value = value
        elif isinstance(value, str) and value.strip().lower() in ("true", "1"):
            validated_value = True
        elif isinstance(value, str) and value.strip().lower() in ("false", "0"):
            validated_value = False
        else:
            return f"error: key '{key}' must be a boolean (got '{value}')"
    elif spec["type"] is int:
        if isinstance(value, bool):
            return f"error: key '{key}' must be an integer (got boolean)"
        parsed_val = None
        if isinstance(value, int):
            parsed_val = value
        elif isinstance(value, str):
            try:
                parsed_val = int(value.strip())
            except ValueError:
                return f"error: key '{key}' must be an {spec['desc']} (got '{value}')"
        else:
            return f"error: key '{key}' must be an {spec['desc']} (got '{value}')"

        if parsed_val < spec["min"] or parsed_val > spec["max"]:
            return f"error: key '{key}' must be an {spec['desc']} (got {parsed_val})"
        validated_value = parsed_val

    cost = 5.0
    ok, err = world.deduct_cost(cost)
    if not ok:
        return f"error: {err}"

    if key == "circuit_breaker_enabled":
        world.services[service].circuit_breaker_enabled = validated_value
    else:
        world.services[service].config[key] = validated_value

    world.action_history.append({"action": "update_config", "service": service, "key": key, "value": validated_value})
    return f"Configuration updated: '{service}.{key}' set to {validated_value} (Cost: ${cost:.2f}). Reload succeeded."

def action_reroute_traffic(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    service = args.get("service", "")
    weight = args.get("weight")

    if service not in world.services:
        return f"error: unknown service '{service}'"
    if not isinstance(weight, int) or weight < 0 or weight > 100:
        return f"error: weight must be an integer between 0 and 100 (got {weight})"

    cost = 10.0
    ok, err = world.deduct_cost(cost)
    if not ok:
        return f"error: {err}"

    old_weight = world.services[service].traffic_weight
    world.services[service].traffic_weight = weight
    world.action_history.append({"action": "reroute_traffic", "service": service, "from": old_weight, "to": weight})
    return f"Ingress traffic rerouted: '{service}' weight shifted from {old_weight}% to {weight}% (Cost: ${cost:.2f})."

def action_finish(world: CloudMeshWorld, args: Dict[str, Any]) -> str:
    world.finished = True
    return "Incident mitigation completed. Triggering final telemetry verification and scoring."

ACTION_HANDLERS = {
    "get_topology": action_get_topology,
    "query_metrics": action_query_metrics,
    "query_logs": action_query_logs,
    "scale_service": action_scale_service,
    "rollback_release": action_rollback_release,
    "update_config": action_update_config,
    "reroute_traffic": action_reroute_traffic,
    "finish": action_finish,
}
