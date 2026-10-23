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
            dependencies=["order-service", "recommendation-service"]
        ),
        "order-service": ServiceState(
            name="order-service", tier="app", replicas=3, version="v2.4.0",
            config={"max_threads": 200, "timeout_ms": 1500, "circuit_breaker": False},
            dependencies=["payment-service", "inventory-service", "cache-cluster"]
        ),
        "payment-service": ServiceState(
            name="payment-service", tier="app", replicas=2, version="v1.9.0",
            config={"gateway_timeout_ms": 3000, "circuit_breaker_enabled": False, "retry_attempts": 3},
            dependencies=["db-primary"]
        ),
        "inventory-service": ServiceState(
            name="inventory-service", tier="app", replicas=2, version="v3.1.2",
            config={"db_pool_size": 25, "db_timeout_ms": 800},
            dependencies=["db-primary", "db-replica"]
        ),
        "recommendation-service": ServiceState(
            name="recommendation-service", tier="app", replicas=2, version="v1.2.0",
            config={"cache_enabled": True, "batch_size": 32},
            dependencies=["cache-cluster"]
        ),
        "cache-cluster": ServiceState(
            name="cache-cluster", tier="cache", replicas=2, version="v7.2-redis",
            memory_limit_mb=4096,
            config={"maxmemory_policy": "allkeys-lru", "eviction_active": False},
            dependencies=[]
        ),
        "db-primary": ServiceState(
            name="db-primary", tier="data", replicas=1, version="postgres-16",
            cpu_limit_cores=4.0, memory_limit_mb=8192,
            config={"max_connections": 100, "shared_buffers_mb": 2048, "lock_timeout_ms": 5000},
            dependencies=[]
        ),
        "db-replica": ServiceState(
            name="db-replica", tier="data", replicas=2, version="postgres-16",
            cpu_limit_cores=2.0, memory_limit_mb=4096,
            config={"max_connections": 100, "read_only": True},
            dependencies=[]
        ),
    }

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.services: Dict[str, ServiceState] = {}
        self.active_incident: Optional[Dict[str, Any]] = None
        self.cost_spent: float = 0.0
        self.step_count: int = 0
        self.finished: bool = False
        self.action_history: List[Dict[str, Any]] = []
        self._init_defaults()

    def _init_defaults(self):
        self.services = {name: copy.deepcopy(s) for name, s in self.DEFAULT_SERVICES.items()}
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
                if "config" in overrides:
                    svc.config.update(overrides["config"])

    def state_hash(self) -> str:
        """Computes a deterministic hash of current topology, configurations, and fault status."""
        state_repr = {
            "services": {name: s.to_dict() for name, s in sorted(self.services.items())},
            "incident_id": self.active_incident.get("task_id", "") if self.active_incident else "",
            "cost_spent": round(self.cost_spent, 2),
            "finished": self.finished,
        }
        raw_bytes = json.dumps(state_repr, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()[:8]

    def deduct_cost(self, amount: float) -> Tuple[bool, str]:
        """Deducts operational cost from remediation budget."""
        if self.cost_spent + amount > self.BUDGET_MAX:
            return False, f"Action denied: cost ${amount:.2f} exceeds remaining budget (${self.BUDGET_MAX - self.cost_spent:.2f} left)."
        self.cost_spent += amount
        return True, ""
