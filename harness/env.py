"""OpsArena Environment: Client Bridge & Programmatic Reward Function.

Connects the harness to the isolated sandbox container via HTTP.
Evaluates multi-factor production rewards:
  Reward = P * [0.45 * SLO + 0.25 * Regressions + 0.15 * Budget + 0.15 * Efficiency]
Where P in [0.0, 1.0] reflects continuous incident remediation progress:
  - P = 0.00 for no-op / idle agents (guaranteeing score 0.0000 <= 0.05)
  - P in (0.0, 0.5] for partial mitigation progress
  - P = 1.00 for full SLO restoration and resolution
"""
import json
from typing import Any, Dict, Optional, Tuple
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
        """Executes a single operational tool call with network exception isolation."""
        try:
            result = self._post("/tool", {"name": name, "args": args}, self.tool_timeout)
            return result.get("output", ""), result.get("is_error", False)
        except requests.RequestException as exc:
            return f"error: sandbox communication failure: {exc}", True

    def state_hash(self) -> str:
        """Returns the full 64-character SHA-256 state hash of the sandbox environment."""
        try:
            state = self._get("/state", self.tool_timeout)
            return state.get("hash", "unknown")
        except requests.RequestException:
            return "unavailable"

    def score(self, model_turns: Optional[int] = None) -> Dict[str, Any]:
        """Programmatic multi-factor reward evaluation with dual telemetry verification.
        
        Calculates:
          1. Remediation Progress Factor (P in [0.0, 1.0])
          2. SLO Health (p99 latency <= 100ms, error rate <= 0.1%)
          3. Platform Stability / Non-Target Regression Score
          4. Budget Preservation (staying within $150.00 operating budget)
          5. Action Efficiency (measuring total model turns & mutations)
        """
        if self.task is None:
            return {"total": 0.0}

        try:
            state = self._get("/state", self.verify_timeout)
        except requests.RequestException as exc:
            return {
                "total": 0.0,
                "error": f"Scoring communication error: {exc}",
                "slo_recovery": 0.0,
                "no_regressions": 0.0,
                "budget_preservation": 0.0,
                "efficiency": 0.0,
            }

        services = state.get("services", {})
        cost_spent = float(state.get("cost_spent", 0.0))
        action_count = int(state.get("action_count", 0))
        reg_score = float(state.get("regression_score", 1.0))
        telemetry = state.get("telemetry", {})

        is_resolved, error_rate, latency_ms, progress = self.task.evaluate_resolution(services, cost_spent)

        # Telemetry consistency verification: If live telemetry shows severe error rates, resolution cannot pass
        if telemetry:
            target_services = self.task.scenario_spec.get("target_services", [])
            for ts in target_services:
                if ts in telemetry:
                    tel_err = telemetry[ts].get("errors", 0.0)
                    tel_lat = telemetry[ts].get("latency", 0.0)
                    if tel_err > 1.0 or tel_lat > 300.0:
                        is_resolved = False
                        progress = min(progress, 0.4)
                        error_rate = max(error_rate, tel_err)
                        latency_ms = max(latency_ms, tel_lat)

        if progress <= 0.0:
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

        # Budget Preservation Factor [0.0 - 1.0]
        # Optimal <= $50, linear decline to $150
        if cost_spent <= 50.0:
            bud_score = 1.0
        else:
            bud_score = max(0.0, 1.0 - (cost_spent - 50.0) / 100.0)

        # Action Efficiency Factor [0.0 - 1.0]
        # Measures total model turns and mutations; optimal <= 8 turns, linear decline up to 40
        eff_turns = max(action_count, model_turns or 0)
        if eff_turns <= 8:
            eff_score = 1.0
        else:
            eff_score = max(0.0, 1.0 - (eff_turns - 8) / 32.0)

        p_mult = float(progress)
        c_slo = round(0.45 * slo_score * p_mult, 4)
        c_reg = round(0.25 * reg_score * p_mult, 4)
        c_bud = round(0.15 * bud_score * p_mult, 4)
        c_eff = round(0.15 * eff_score * p_mult, 4)
        total = round(c_slo + c_reg + c_bud + c_eff, 4)

        return {
            "slo_recovery": c_slo,
            "no_regressions": c_reg,
            "budget_preservation": c_bud,
            "efficiency": c_eff,
            "total": total,
        }
