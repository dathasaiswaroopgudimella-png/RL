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
    verifier_fn: Callable[[Dict[str, Any], float], Tuple[Any, ...]] = None

    def evaluate_resolution(self, services: Dict[str, Any], cost_spent: float) -> Tuple[bool, float, float, float]:
        """Returns (is_resolved, error_rate_pct, p99_latency_ms, progress_ratio)."""
        if self.verifier_fn:
            res = self.verifier_fn(services, cost_spent)
            if len(res) >= 4:
                return bool(res[0]), float(res[1]), float(res[2]), float(res[3])
            elif len(res) == 3:
                prog = 1.0 if res[0] else 0.0
                return bool(res[0]), float(res[1]), float(res[2]), prog
        return False, 50.0, 5000.0, 0.0
