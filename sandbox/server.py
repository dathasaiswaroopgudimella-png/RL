"""OpsArena Sandbox Service: Isolated HTTP Dispatch Server.

Listens on port 8000 inside the isolated container network (no internet egress).
Manages in-memory CloudMesh simulation state, executes typed domain tools,
enforces 4,000 character output bounds, and returns deterministic state hashes.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sandbox.simulator.world import CloudMeshWorld
from sandbox.simulator.actions import ACTION_HANDLERS

PORT = int(os.environ.get("PORT", "8000"))
MAX_OUTPUT = 4000  # Strictly enforce 4,000 character limit

WORLD = CloudMeshWorld()

def clip(text: str) -> str:
    """Clips text to 4,000 characters with explicit notification."""
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n[output cut at {MAX_OUTPUT} characters]"

def do_reset(body):
    """Resets the simulation to the initial incident state for the given scenario and seed."""
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
        return {
            "output": f"error: unknown tool '{name}'. Available tools: {list(ACTION_HANDLERS.keys())}",
            "is_error": True,
        }

    try:
        output_str = ACTION_HANDLERS[name](WORLD, args)
        is_error = output_str.startswith("error:")
        return {"output": clip(output_str), "is_error": is_error}
    except Exception as exc:
        return {"output": f"error: {type(exc).__name__}: {exc}", "is_error": True}

def do_state(_body=None):
    """Returns current state snapshot, hash, and metrics for verifier scoring."""
    return {
        "ok": True,
        "hash": WORLD.state_hash(),
        "cost_spent": WORLD.cost_spent,
        "finished": WORLD.finished,
        "action_count": len(WORLD.action_history),
        "services": {name: s.to_dict() for name, s in WORLD.services.items()},
    }

ROUTES_POST = {
    "/reset": do_reset,
    "/tool": do_tool,
}

class SandboxHandler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
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
