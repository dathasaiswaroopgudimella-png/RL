"""OpsArena Tool Specifications and Argument Validation.

Defines the 8 typed operational tools available to agents, plus strict schema verification.
"""
from typing import Any, Dict, List, Optional

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_topology",
            "description": "Inspect active microservice topology, pod replicas, versions, dependencies, and budget spent.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_metrics",
            "description": "Query recent telemetry timeseries (p99 latency, errors, CPU, memory, QPS) for a service.",
            "parameters": {
                "type": "object",
                "required": ["service"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name (e.g. order-service, api-gateway, cache-cluster, db-primary, payment-service, inventory-service).",
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric to inspect: latency, errors, cpu, memory, qps, or rps (default: latency).",
                        "enum": ["latency", "errors", "cpu", "memory", "qps", "rps"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Query recent structured application log lines for a service with optional substring filter.",
            "parameters": {
                "type": "object",
                "required": ["service"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name.",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Optional case-insensitive substring filter for log messages (e.g. error, Exception, pool, timeout).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scale_service",
            "description": "Scale replica pod count for a target service to handle load or expand capacity (1 to 20 pods).",
            "parameters": {
                "type": "object",
                "required": ["service", "replicas"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name.",
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Desired replica count between 1 and 20.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_release",
            "description": "Rollback a misbehaving or buggy service deployment to a previous stable container version.",
            "parameters": {
                "type": "object",
                "required": ["service", "target_version"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name (e.g. order-service).",
                    },
                    "target_version": {
                        "type": "string",
                        "description": "Stable container version to rollback to (e.g. v2.4.0).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_config",
            "description": "Dynamically update a runtime configuration parameter for a service.",
            "parameters": {
                "type": "object",
                "required": ["service", "key", "value"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name.",
                    },
                    "key": {
                        "type": "string",
                        "description": "Configuration key valid for target service (e.g. db_pool_size, circuit_breaker_enabled, timeout_ms, lock_timeout_ms).",
                    },
                    "value": {
                        "description": "New configuration value (integer, boolean, or string).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reroute_traffic",
            "description": "Adjust ingress or canary traffic routing weight percentage (0 to 100).",
            "parameters": {
                "type": "object",
                "required": ["service", "weight"],
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Target microservice name supporting route split (order-service).",
                    },
                    "weight": {
                        "type": "integer",
                        "description": "Traffic percentage (0 to 100). 0 drains traffic from the canary route.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call this when the incident is resolved to complete the episode and request final scoring.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

SPECS: Dict[str, Dict[str, Any]] = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
TOOL_NAMES: List[str] = list(SPECS.keys())

SERVICE_ALLOWED_CONFIGS = {
    "inventory-service": {"db_pool_size", "db_timeout_ms"},
    "db-primary": {"lock_timeout_ms", "max_connections", "shared_buffers_mb"},
    "payment-service": {"gateway_timeout_ms", "circuit_breaker_enabled", "retry_attempts"},
    "order-service": {"max_threads", "timeout_ms", "circuit_breaker"},
    "api-gateway": {"rate_limit_rps", "timeout_ms"},
    "recommendation-service": {"cache_enabled", "batch_size"},
}


def check_args(name: str, args: Any) -> Optional[str]:
    """Validates tool arguments against the declared schema. Returns an error message if invalid."""
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    if name not in SPECS:
        return f"unknown tool '{name}'"

    spec = SPECS[name]
    required = spec.get("required", [])
    properties = spec.get("properties", {})

    for req in required:
        if req not in args:
            return f"missing required argument '{req}'"

    for key, val in args.items():
        if key not in properties:
            return f"unexpected argument '{key}'"
        prop_def = properties[key]
        expected_type = prop_def.get("type")
        if expected_type == "string":
            if not isinstance(val, str):
                return f"argument '{key}' must be a string"
        elif expected_type == "integer":
            if isinstance(val, bool) or not isinstance(val, int):
                return f"argument '{key}' must be an integer"
        elif expected_type == "boolean":
            if not isinstance(val, bool):
                return f"argument '{key}' must be a boolean"

    # Specific key-value validation for query_metrics
    if name == "query_metrics":
        metric = args.get("metric", "latency")
        if metric.lower() not in ("latency", "errors", "cpu", "memory", "qps", "rps"):
            return f"metric '{metric}' is not supported. Must be one of: latency, errors, cpu, memory, qps, rps"

    # Specific key-value validation for update_config
    if name == "update_config":
        svc = args.get("service")
        cfg_key = args.get("key")
        val = args.get("value")

        if svc in SERVICE_ALLOWED_CONFIGS:
            allowed_for_svc = SERVICE_ALLOWED_CONFIGS[svc]
            if cfg_key not in allowed_for_svc:
                return f"configuration key '{cfg_key}' is not configurable on '{svc}'. Allowed: {sorted(list(allowed_for_svc))}"

        if cfg_key in ("circuit_breaker_enabled", "cache_enabled"):
            if not isinstance(val, bool) and val not in ("true", "false", "True", "False"):
                return f"argument 'value' for '{cfg_key}' must be a boolean"
        elif cfg_key in ("db_pool_size", "lock_timeout_ms", "gateway_timeout_ms", "timeout_ms", "max_connections", "rate_limit_rps"):
            if isinstance(val, bool) or not (isinstance(val, int) or (isinstance(val, str) and val.isdigit())):
                return f"argument 'value' for '{cfg_key}' must be an integer"

    return None
