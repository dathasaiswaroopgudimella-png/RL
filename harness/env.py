"""OpsArena Environment: Client Bridge & Programmatic Reward Function.

Connects the harness to the isolated sandbox container via HTTP.
Evaluates multi-factor production rewards:
  Reward = P * [0.45 * SLO + 0.25 * Regressions + 0.15 * Budget + 0.15 * Efficiency]
Where P = 0 if the primary incident is not mitigated (guaranteeing no-op <= 0.05).
"""
import hashlib
import json
from typing import Any, Dict, Tuple
import requests
from .tasks import build_task

PASS_SCORE: float = 0.95  # Target score threshold for reference oracle


class Env:
    def __init__(self, sandbox_url: str = "http://sandbox:8000", tool_timeout: int = 60, verify_timeout: int = 120):
        self.url = sandbox_url.rstrip("/")
        self.tool_timeout = tool_timeout
        self.verify_timeout = verify_timeout
        self.task = None

    def _post(self, path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        resp = requests.post(self.url + path, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str, timeout: int) -> Dict[str, Any]:
        resp = requests.get(self.url + path, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def reset(self, task_id: str, seed: int = 0) -> str:
        """Starts a clean episode with deterministic state."""
        self.task = build_task(task_id, seed)
        payload = {
            "seed": seed,
            "scenario": {
                **self.task.scenario_spec,
                "instructions": self.task.instructions,
            },
        }
        res = self._post("/reset", payload, self.tool_timeout)
        return (
            f"Active Production Incident: {self.task.title} [{self.task.difficulty.upper()}]\n"
            f"{self.task.instructions}\n\n"
            "Use the provided tools to inspect topology, query metrics/logs, execute mitigation actions, "
            "and call `finish` when the incident is resolved."
        )

    def step(self, name: str, args: Dict[str, Any]) -> Tuple[str, bool]:
        """Executes a single operational tool call."""
        result = self._post("/tool", {"name": name, "args": args}, self.tool_timeout)
        return result.get("output", ""), result.get("is_error", False)

    def state_hash(self) -> str:
        """Returns the deterministic state hash of the sandbox environment."""
        state = self._get("/state", self.tool_timeout)
        return state.get("hash", "unknown")

    def score(self) -> Dict[str, Any]:
        """Programmatic multi-factor reward evaluation.
        
        Calculates:
          1. Incident Resolution (P in {0, 1})
          2. SLO Health (p99 latency <= 100ms, error rate <= 0.1%)
          3. Platform Stability / No Regressions
          4. Budget Preservation (staying within $150.00 operating budget)
          5. Action Efficiency (minimizing redundant iterations)
        """
        if self.task is None:
            return {"total": 0.0}

        state = self._get("/state", self.verify_timeout)
        services = state.get("services", {})
        cost_spent = float(state.get("cost_spent", 0.0))
        action_count = int(state.get("action_count", 0))

        is_resolved, error_rate, latency_ms = self.task.evaluate_resolution(services, cost_spent)

        if not is_resolved:
            return {
                "slo_recovery": 0.0,
                "no_regressions": 0.0,
                "budget_preservation": 0.0,
                "efficiency": 0.0,
                "total": 0.0,
            }

        # SLO Recovery Factor [0.0 - 1.0]
        # Target: error_rate <= 0.1%, latency <= 100ms
        err_factor = max(0.0, min(1.0, 1.0 - (error_rate / 2.0)))
        lat_factor = max(0.0, min(1.0, 1.0 - max(0.0, latency_ms - 80.0) / 1000.0))
        slo_score = 0.5 * err_factor + 0.5 * lat_factor

        # Platform Stability / Regression Factor [0.0 - 1.0]
        # Verify non-target services were not crashed or drained to 0 replicas
        unhealthy = 0
        for name, s in services.items():
            if s.get("replicas", 1) < 1:
                unhealthy += 1
        reg_score = max(0.0, 1.0 - (unhealthy * 0.25))

        # Budget Preservation Factor [0.0 - 1.0]
        # Optimal <= $50, linear decline to $150
        if cost_spent <= 50.0:
            bud_score = 1.0
        else:
            bud_score = max(0.0, 1.0 - (cost_spent - 50.0) / 100.0)

        # Action Efficiency Factor [0.0 - 1.0]
        # Optimal <= 8 actions, linear decline up to 40 actions
        if action_count <= 8:
            eff_score = 1.0
        else:
            eff_score = max(0.0, 1.0 - (action_count - 8) / 32.0)

        c_slo = round(0.45 * slo_score, 4)
        c_reg = round(0.25 * reg_score, 4)
        c_bud = round(0.15 * bud_score, 4)
        c_eff = round(0.15 * eff_score, 4)
        total = round(c_slo + c_reg + c_bud + c_eff, 4)

        return {
            "slo_recovery": c_slo,
            "no_regressions": c_reg,
            "budget_preservation": c_bud,
            "efficiency": c_eff,
            "total": total,
        }
