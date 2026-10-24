"""OpsArena Sandbox Service: Hardened HTTP Dispatch Server.

Listens on port 8000 inside the isolated container network (no internet egress).
Manages in-memory CloudMesh simulation state, executes typed domain tools,
enforces strict 4,000 character output bounds, scrubs credentials, and returns
deterministic state hashes.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sandbox.simulator.world import CloudMeshWorld
from sandbox.simulator.actions import ACTION_HANDLERS
from sandbox.simulator.security import clip_output, scrub_secrets
from sandbox.simulator.metrics import compute_service_metrics

PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY_BYTES = 1024 * 1024  # 1 MB maximum request body size

WORLD = CloudMeshWorld()
WORLD_LOCK = threading.Lock()

STATE_MUTATING_ACTIONS = {
    "scale_service",
    "rollback_release",
    "update_config",
    "reroute_traffic",
}


def do_reset(body):
    """Resets the simulation to the initial incident state for the given scenario and seed."""
    with WORLD_LOCK:
        seed = int(body.get("seed", 0))
        scenario = body.get("scenario", {})
        WORLD.seed = seed
        WORLD.load_scenario(scenario)
        return {
            "ok": True,
            "state_hash": WORLD.state_hash(),
            "instruction": scenario.get("instructions", "Resolve the active production incident."),
        }


def do_tool(body):
    """Executes a typed operational tool against the CloudMesh simulator."""
    name = body.get("name", "")
    args = body.get("args", {})

    if name not in ACTION_HANDLERS:
        err_msg = f"error: unknown tool '{name}'. Available tools: {list(ACTION_HANDLERS.keys())}"
        return {"output": clip_output(err_msg), "is_error": True}

    with WORLD_LOCK:
        if WORLD.finished and name in STATE_MUTATING_ACTIONS:
            err_msg = f"error: episode has already finished; further mutation via '{name}' is not permitted."
            return {"output": clip_output(err_msg), "is_error": True}

        try:
            output_str = ACTION_HANDLERS[name](WORLD, args)
            is_error = output_str.startswith("error:")
            return {"output": clip_output(output_str), "is_error": is_error}
        except Exception as exc:
            err_msg = f"error: {type(exc).__name__}: {exc}"
            return {"output": clip_output(err_msg), "is_error": True}


def do_state(_body=None):
    """Returns current state snapshot, hash, regression score, and telemetry for verifier scoring."""
    with WORLD_LOCK:
        services_dict = {name: s.to_dict() for name, s in WORLD.services.items()}
        # Compute telemetry for all services as single source of truth
        telemetry = {}
        for svc_name in WORLD.services:
            try:
                telemetry[svc_name] = {
                    "errors": compute_service_metrics(WORLD, svc_name, "errors")["raw_error_rate"],
                    "latency": compute_service_metrics(WORLD, svc_name, "latency")["raw_latency"],
                }
            except Exception:
                pass

        return {
            "ok": True,
            "hash": WORLD.state_hash(),
            "cost_spent": WORLD.cost_spent,
            "finished": WORLD.finished,
            "action_count": len(WORLD.action_history),
            "action_history": list(WORLD.action_history),
            "step_count": WORLD.step_count,
            "regression_score": WORLD.compute_regression_score(),
            "services": services_dict,
            "telemetry": telemetry,
        }


ROUTES_POST = {
    "/reset": do_reset,
    "/tool": do_tool,
}


class SandboxHandler(BaseHTTPRequestHandler):
    def _send(self, code, payload, close_connection=False):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "OpsArena Sandbox"})
        elif self.path == "/state":
            self._send(200, do_state())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        handler = ROUTES_POST.get(self.path)
        if handler is None:
            return self._send(404, {"error": "not found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY_BYTES:
                try:
                    self.rfile.read(length)
                except Exception:
                    pass
                self.close_connection = True
                return self._send(413, {"error": f"Payload too large (exceeds {MAX_BODY_BYTES} bytes)"}, close_connection=True)

            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            body = json.loads(raw_body.decode("utf-8") or "{}")
            self._send(200, handler(body))
        except Exception as exc:
            self._send(400, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, *args):
        # Keep stdout telemetry clean
        pass


if __name__ == "__main__":
    print(f"OpsArena sandbox listening on :{PORT}", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SandboxHandler)
    server.serve_forever()
