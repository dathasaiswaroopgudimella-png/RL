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
                        "description": "Metric to inspect: latency, errors, cpu, memory, or qps (default: latency).",
                        "enum": ["latency", "errors", "cpu", "memory", "qps"],
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
                        "description": "Optional substring/regex filter for log messages (e.g. error, Exception, pool, timeout).",
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
                        "description": "Configuration key (e.g. db_pool_size, circuit_breaker_enabled, timeout_ms, lock_timeout_ms).",
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
                        "description": "Target microservice name.",
                    },
                    "weight": {
                        "type": "integer",
                        "description": "Traffic percentage (0 to 100). 0 drains traffic from the service route.",
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

    return None
