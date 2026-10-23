"""OpsArena Task Contracts & Dataclasses."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

@dataclass
class TaskInstance:
    task_id: str
    title: str
    difficulty: str  # "easy", "medium", "hard"
    instructions: str
    scenario_spec: Dict[str, Any]
    oracle_actions: List[Tuple[str, Dict[str, Any]]]
    noop_actions: List[Tuple[str, Dict[str, Any]]] = field(default_factory=list)
    verifier_fn: Callable[[Dict[str, Any], float], Tuple[bool, float, float]] = None

    def evaluate_resolution(self, services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float]:
        """Returns (is_resolved, error_rate_pct, p99_latency_ms)."""
        if self.verifier_fn:
            return self.verifier_fn(services, cost_spent)
        return False, 50.0, 5000.0
