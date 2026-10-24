"""OpsArena Runner: Episode Loop, Context Trimming, Scripted Baselines & Telemetry."""
import copy
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .env import PASS_SCORE
from .tools import SPECS, TOOLS, TOOL_NAMES, check_args
from sandbox.simulator.security import clip_output

SYSTEM_PROMPT = (
    "You are an expert autonomous site reliability engineering (SRE) agent operating in the OpsArena cloud mesh. "
    "Your objective is to diagnose and mitigate active production incidents, restore Service Level Objectives "
    "(p99 latency < 100ms, error rate < 0.1%), preserve platform stability, and adhere to operational budget limits. "
    "Use the provided tools to inspect topology, query timeseries metrics, inspect distributed logs, scale services, "
    "rollback faulty releases, adjust configuration parameters, and reroute canary traffic. "
    "Always respond with tool calls. When the incident is fully mitigated and verified, call the `finish` tool."
)

TRIMMED = "[older tool output removed to save context budget]"
TRIMMED_ARGS = '{"note": "arguments removed to save context budget"}'


@dataclass
class Limits:
    max_steps: int = 40                   # Max model turns per episode (hard cap: 40)
    max_seconds: int = 600                # Max wall-clock budget (hard cap: 600s / 10 min)
    max_tool_calls: int = 10              # Max tool calls executed per turn
    context_budget_tokens: int = 48000    # Context window trimming budget
    max_output_chars: int = 4000          # Per-tool output character limit


class JsonlLog:
    def __init__(self, path: Any):
        self.file = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, record: Dict[str, Any]) -> None:
        self.file.write(json.dumps(record, default=str) + "\n")

    def close(self) -> None:
        if not self.file.closed:
            self.file.close()

    def __enter__(self) -> "JsonlLog":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def show(record: Dict[str, Any]) -> None:
    """Prints a concise, single-line telemetry update for each step."""
    tools = ",".join(a.get("tool", "?") for a in record.get("parsed_actions", [])) or "-"
    reward = record.get("reward", {}).get("total") if record.get("reward") else None
    reward_str = f"{reward:.3f}" if (reward is not None and isinstance(reward, (int, float))) else "-"
    state_hash = str(record.get("state", {}).get("hash", "unknown"))[:8]
    errors = len(record.get("errors", []))
    print(
        f"[{record.get('agent', 'agent'):<7} step {record.get('step', 0):>2}] "
        f"tools={tools:<35} reward={reward_str:<6} state={state_hash} errors={errors}",
        flush=True,
    )


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    return len(json.dumps(messages, default=str)) // 4


def trim_history(messages: List[Dict[str, Any]], budget: int) -> None:
    """Progressively trims older tool outputs and parameters to fit within context limits."""
    while estimate_tokens(messages) > budget:
        last_assistant = max((i for i, m in enumerate(messages) if m.get("role") == "assistant"), default=0)
        victim = next(
            (m for i, m in enumerate(messages) if m.get("role") == "tool" and m.get("content") != TRIMMED and i < last_assistant),
            None,
        )
        if victim is not None:
            victim["content"] = TRIMMED
            continue

        shrunk = False
        for m in messages[:last_assistant]:
            for call in m.get("tool_calls", []):
                fn = call.get("function", {})
                if fn.get("arguments") != TRIMMED_ARGS:
                    fn["arguments"] = TRIMMED_ARGS
                    shrunk = True
                    break
            if shrunk:
                break
        if shrunk:
            continue

        # If tool results and arguments are already trimmed, drop older turns while preserving system [0] and task description [1]
        if len(messages) > 3:
            messages.pop(2)
            continue
        break


def run_scripted(env: Any, task_id: str, seed: int, actions: List[Any], agent: str, log: JsonlLog) -> Dict[str, Any]:
    """Executes a deterministic scripted sequence (oracle or no-op) through identical env paths."""
    env.reset(task_id, seed)
    step = 0
    for step, (name, args) in enumerate(actions, start=1):
        text, is_error = env.step(name, args)
        record = {
            "timestamp": now(),
            "agent": agent,
            "task": task_id,
            "step": step,
            "seed": seed,
            "model_input": None,
            "model_output_raw": None,
            "parsed_actions": [{"tool": name, "args": args}],
            "tool_result": [text],
            "errors": [{"kind": "tool_error", "detail": text}] if is_error else [],
            "state": {"hash": env.state_hash()},
            "reward": env.score(model_turns=step),
            "tokens": 0,
            "latency_ms": 0,
        }
        log.write(record)
        show(record)

    final = env.score(model_turns=step)
    termination = "success" if (final.get("total") or 0.0) >= PASS_SCORE else "failure"
    log.write({
        "timestamp": now(),
        "agent": agent,
        "task": task_id,
        "event": "episode_end",
        "seed": seed,
        "steps": step,
        "termination": termination,
        "reward": final,
        "state": {"hash": env.state_hash()},
    })
    return final


def run_episode(
    env: Any,
    task_id: str,
    seed: int,
    client: Any,
    append_text: str,
    limits: Limits,
    log: JsonlLog,
) -> Dict[str, Any]:
    """Executes a full interactive model episode with strict resource and step boundaries."""
    prompt = env.reset(task_id, seed)
    client.start(env.task)
    system = SYSTEM_PROMPT + (("\n\n" + append_text) if append_text else "")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    max_steps = min(40, limits.max_steps)
    max_seconds = min(600, limits.max_seconds)

    started: Optional[float] = None
    termination: Optional[str] = None
    finished: bool = False
    steps: int = 0

    for step in range(1, max_steps + 1):
        if started is not None and (time.monotonic() - started) >= max_seconds:
            termination = "time_cap"
            break
        if started is None:
            started = time.monotonic()

        remaining = max_seconds - (time.monotonic() - started)
        if remaining <= 0:
            termination = "time_cap"
            break

        call_timeout = min(remaining, 120.0)
        if call_timeout <= 0:
            termination = "time_cap"
            break

        trim_history(messages, limits.context_budget_tokens)
        if estimate_tokens(messages) > limits.context_budget_tokens:
            termination = "context_limit"
            record: Dict[str, Any] = {
                "timestamp": now(),
                "agent": "model",
                "task": task_id,
                "step": step,
                "seed": seed,
                "model_input": [],
                "model_output_raw": None,
                "parsed_actions": [],
                "tool_result": [],
                "errors": [{"kind": "context_limit_exceeded", "detail": "Context budget exceeded hard bound"}],
                "state": {"hash": env.state_hash()},
                "reward": None,
                "tokens": 0,
                "latency_ms": 0,
            }
            log.write(record)
            show(record)
            break

        sent = copy.deepcopy(messages)
        call_start = time.monotonic()
        steps = step

        record: Dict[str, Any] = {
            "timestamp": now(),
            "agent": "model",
            "task": task_id,
            "step": step,
            "seed": seed,
            "model_input": sent,
            "model_output_raw": None,
            "parsed_actions": [],
            "tool_result": [],
            "errors": [],
            "state": {"hash": env.state_hash()},
            "reward": None,
            "tokens": 0,
            "latency_ms": 0,
        }

        try:
            reply = client.complete(sent, TOOLS, timeout=call_timeout)
        except Exception as exc:
            if started is not None and (time.monotonic() - started) >= max_seconds:
                termination = "time_cap"
            else:
                termination = "crash"
            record["errors"].append({"kind": "model_call_failed", "detail": f"{type(exc).__name__}: {exc}"})
            log.write(record)
            show(record)
            break

        record["latency_ms"] = int((time.monotonic() - call_start) * 1000)
        record["model_output_raw"] = reply.raw
        record["tokens"] = reply.tokens

        assistant_msg = {"role": "assistant", "content": reply.text}
        if reply.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.history_arguments()},
                }
                for c in reply.tool_calls
            ]
        messages.append(assistant_msg)

        if not reply.tool_calls:
            record["errors"].append({"kind": "no_tool_call", "detail": "Model response contained no tool calls."})
            messages.append({
                "role": "user",
                "content": "No tool call was received. Call one of the available operational tools, or call `finish` when done.",
            })

        dispatched_count = 0
        for index, call in enumerate(reply.tool_calls):
            args, parse_error = call.parse()
            record["parsed_actions"].append({"tool": call.name, "args": args, "parse_error": parse_error})

            # --- Validation gate: determine whether this call should execute ---
            rejected = False
            result = ""

            if finished:
                result = "not run: the episode has already finished"
                rejected = True
            elif dispatched_count >= limits.max_tool_calls:
                result = f"not run: at most {limits.max_tool_calls} tool calls allowed per turn"
                record["errors"].append({"kind": "too_many_tool_calls", "detail": call.name})
                rejected = True
            elif parse_error:
                result = f"error: {parse_error}"
                record["errors"].append({"kind": "unparsable_arguments", "detail": call.name})
                rejected = True
            elif call.name not in SPECS:
                result = f"error: unknown tool '{call.name}'. Available: {', '.join(TOOL_NAMES)}"
                record["errors"].append({"kind": "unknown_tool", "detail": call.name})
                rejected = True
            elif (problem := check_args(call.name, args)):
                result = f"error: {problem}"
                record["errors"].append({"kind": "invalid_arguments", "detail": f"{call.name}: {problem}"})
                rejected = True

            # --- Time budget check ---
            tool_rem = max_seconds - (time.monotonic() - started) if started else max_seconds
            if tool_rem <= 0:
                termination = "time_cap"
                result = "not run: episode wall-clock time limit reached"
                record["errors"].append({"kind": "time_limit_exceeded", "detail": "Wall-clock time limit reached"})
                result = clip_output(result, limits.max_output_chars)
                record["tool_result"].append(result)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                break

            # --- Dispatch only if validation passed ---
            if not rejected:
                tool_timeout = min(env.tool_timeout, max(1, int(tool_rem)))
                if call.name == "finish":
                    finished = True
                result, is_error = env.step(call.name, args, timeout=tool_timeout)
                if is_error:
                    record["errors"].append({"kind": "tool_error", "detail": result})
                dispatched_count += 1

            result = clip_output(result, limits.max_output_chars)
            record["tool_result"].append(result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        record["state"] = {"hash": env.state_hash()}
        record["reward"] = env.score(model_turns=step)
        log.write(record)
        show(record)

        if finished:
            break
    else:
        termination = "step_cap"

    try:
        final = env.score(model_turns=steps)
    except Exception as exc:
        final = {"total": None, "error": str(exc)}
        termination = termination or "crash"

    if termination is None:
        total_val = final.get("total") if isinstance(final, dict) else 0.0
        termination = "success" if (total_val or 0.0) >= PASS_SCORE else "failure"

    log.write({
        "timestamp": now(),
        "agent": "model",
        "task": task_id,
        "event": "episode_end",
        "seed": seed,
        "steps": steps,
        "termination": termination,
        "reward": final,
        "elapsed_s": round(time.monotonic() - started, 1) if started else 0,
    })

    return {
        "termination": termination,
        "steps": steps,
        "reward": final,
        "elapsed_s": round(time.monotonic() - started, 1) if started else 0,
    }
