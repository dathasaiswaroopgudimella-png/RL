"""OpsArena: In-Memory CloudMesh Discrete-Event World Simulator.

Simulates an enterprise e-commerce microservices platform under production load.
Manages service topologies, container allocations, deployment versions, traffic weights,
operational budgets, and fault state transitions.
"""
import copy
import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Minimum safe pod capacity per microservice to satisfy nominal traffic without SLO degradation
MIN_SAFE_REPLICAS: Dict[str, int] = {
    "api-gateway": 3,
    "order-service": 3,
    "payment-service": 2,
    "inventory-service": 2,
    "recommendation-service": 1,
    "cache-cluster": 1,
    "db-primary": 1,
    "db-replica": 2,
}


@dataclass
class ServiceState:
    name: str
    tier: str  # "edge", "app", "data", "cache"
    replicas: int = 2
    version: str = "v2.4.0"
    cpu_limit_cores: float = 2.0
    memory_limit_mb: int = 2048
    circuit_breaker_enabled: bool = False
    traffic_weight: int = 100
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tier": self.tier,
            "replicas": self.replicas,
            "version": self.version,
            "cpu_limit_cores": self.cpu_limit_cores,
            "memory_limit_mb": self.memory_limit_mb,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "traffic_weight": self.traffic_weight,
            "config": copy.deepcopy(self.config),
            "dependencies": list(self.dependencies),
        }


class CloudMeshWorld:
    """Deterministic, discrete-event world model for cloud operations."""

    BUDGET_MAX = 150.0  # Max remediation budget in USD

    DEFAULT_SERVICES = {
        "api-gateway": ServiceState(
            name="api-gateway", tier="edge", replicas=3, version="v2.4.0",
            config={"rate_limit_rps": 5000, "timeout_ms": 2500},
            dependencies=["order-service", "recommendation-service"],
        ),
        "order-service": ServiceState(
            name="order-service", tier="app", replicas=3, version="v2.4.0",
            config={"max_threads": 200, "timeout_ms": 1500, "circuit_breaker": False},
            dependencies=["payment-service", "inventory-service", "cache-cluster"],
        ),
        "payment-service": ServiceState(
            name="payment-service", tier="app", replicas=2, version="v1.9.0",
            config={"gateway_timeout_ms": 3000, "circuit_breaker_enabled": False, "retry_attempts": 3},
            dependencies=["db-primary"],
        ),
        "inventory-service": ServiceState(
            name="inventory-service", tier="app", replicas=2, version="v3.1.2",
            config={"db_pool_size": 25, "db_timeout_ms": 800},
            dependencies=["db-primary", "db-replica"],
        ),
        "recommendation-service": ServiceState(
            name="recommendation-service", tier="app", replicas=2, version="v1.2.0",
            config={"cache_enabled": True, "batch_size": 32},
            dependencies=["cache-cluster"],
        ),
        "cache-cluster": ServiceState(
            name="cache-cluster", tier="cache", replicas=2, version="v7.2-redis",
            memory_limit_mb=4096,
            config={"maxmemory_policy": "allkeys-lru", "eviction_active": False},
            dependencies=[],
        ),
        "db-primary": ServiceState(
            name="db-primary", tier="data", replicas=1, version="postgres-16",
            cpu_limit_cores=4.0, memory_limit_mb=8192,
            config={"max_connections": 100, "shared_buffers_mb": 2048, "lock_timeout_ms": 5000},
            dependencies=[],
        ),
        "db-replica": ServiceState(
            name="db-replica", tier="data", replicas=2, version="postgres-16",
            cpu_limit_cores=2.0, memory_limit_mb=4096,
            config={"max_connections": 100, "read_only": True},
            dependencies=[],
        ),
    }

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.services: Dict[str, ServiceState] = {}
        self.active_incident: Optional[Dict[str, Any]] = None
        self.baseline_health: Dict[str, Dict[str, Any]] = {}
        self.cost_spent: float = 0.0
        self.step_count: int = 0
        self.finished: bool = False
        self.action_history: List[Dict[str, Any]] = []
        self._init_defaults()

    def _init_defaults(self):
        self.services = {name: copy.deepcopy(s) for name, s in self.DEFAULT_SERVICES.items()}
        self.baseline_health = {name: s.to_dict() for name, s in self.services.items()}
        self.cost_spent = 0.0
        self.step_count = 0
        self.finished = False
        self.action_history.clear()

    def load_scenario(self, scenario_spec: Dict[str, Any]):
        """Initializes a scenario with active root cause faults and telemetry profiles."""
        self._init_defaults()
        self.active_incident = copy.deepcopy(scenario_spec)

        # Apply initial service overrides from scenario
        for svc_name, overrides in scenario_spec.get("service_overrides", {}).items():
            if svc_name in self.services:
                svc = self.services[svc_name]
                if "replicas" in overrides:
                    svc.replicas = overrides["replicas"]
                if "version" in overrides:
                    svc.version = overrides["version"]
                if "memory_limit_mb" in overrides:
                    svc.memory_limit_mb = overrides["memory_limit_mb"]
                if "circuit_breaker_enabled" in overrides:
                    svc.circuit_breaker_enabled = overrides["circuit_breaker_enabled"]
                if "traffic_weight" in overrides:
                    svc.traffic_weight = overrides["traffic_weight"]
                if "config" in overrides:
                    svc.config.update(overrides["config"])

        # Capture post-override baseline for non-target regression checks
        self.baseline_health = {name: s.to_dict() for name, s in self.services.items()}

    def compute_regression_score(self) -> float:
        """Evaluates whether any non-target service was degraded, drained, or broken.
        Returns 1.0 if perfectly stable, down to 0.0 if regressions are caused.
        """
        incident = self.active_incident or {}
        task_id = incident.get("task_id", "")

        TARGET_MAP = {
            "task_01_cache_pressure": {"cache-cluster"},
            "task_02_bad_deployment": {"order-service"},
            "task_03_db_pool_exhaustion": {"inventory-service"},
            "task_04_downstream_timeout": {"payment-service"},
            "task_05_cascading_failure": {"order-service"},
            "task_06_canary_leak": {"order-service"},
            "task_07_cost_slo_rescue": {"api-gateway", "order-service", "db-replica"},
            "task_08_migration_lock": {"db-primary"},
        }
        target_services = TARGET_MAP.get(task_id, set(incident.get("target_services", [])))

        penalties = 0.0
        for name, svc in self.services.items():
            base = self.baseline_health.get(name, {})

            # Severe penalty if any service is completely drained below 1 pod
            if svc.replicas < 1:
                penalties += 0.50
            # Capacity penalty if scaled below minimum safe operational threshold
            elif svc.replicas < MIN_SAFE_REPLICAS.get(name, 1):
                penalties += 0.35

            if name in target_services:
                continue

            # Penalty if unneeded downscaling happened on an unaffected service
            if svc.replicas < base.get("replicas", 2):
                penalties += 0.25

            # Penalty if a non-target service's stable version was modified
            if svc.version != base.get("version", ""):
                penalties += 0.35

            # Penalty if traffic was drained from an unaffected route
            if svc.traffic_weight == 0:
                penalties += 0.40

            # Config regression check: penalize unauthorized config mutations on non-target services
            base_config = base.get("config", {})
            for cfg_k, cfg_v in svc.config.items():
                if cfg_k in base_config and base_config[cfg_k] != cfg_v:
                    penalties += 0.25
                elif cfg_k not in base_config:
                    penalties += 0.25

        return max(0.0, 1.0 - penalties)

    def state_hash(self) -> str:
        """Computes a full 64-character SHA-256 hash of topology, configs, fault state, and scenario spec."""
        incident = self.active_incident or {}
        # Filter instructions string to keep state compact while preserving all seeded parameters
        incident_spec = {k: v for k, v in sorted(incident.items()) if k != "instructions"}

        state_repr = {
            "services": {name: s.to_dict() for name, s in sorted(self.services.items())},
            "incident_id": incident.get("task_id", ""),
            "incident_spec": incident_spec,
            "cost_spent": round(self.cost_spent, 2),
            "step_count": self.step_count,
            "finished": self.finished,
        }
        raw_bytes = json.dumps(state_repr, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def deduct_cost(self, amount: float) -> Tuple[bool, str]:
        """Deducts operational cost from remediation budget."""
        if self.finished:
            return True, ""
        if self.cost_spent + amount > self.BUDGET_MAX:
            return False, f"Action denied: cost ${amount:.2f} exceeds remaining budget (${self.BUDGET_MAX - self.cost_spent:.2f} left)."
        self.cost_spent += amount
        return True, ""
