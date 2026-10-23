"""OpsArena Runner: Episode Loop, Context Trimming, Scripted Baselines & Telemetry."""
import copy
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .env import PASS_SCORE
from .tools import SPECS, TOOLS, TOOL_NAMES, check_args

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
    max_steps: int = 40                   # Max model turns per episode
    max_seconds: int = 600                # 10-minute wall-clock cap
    max_tool_calls: int = 10              # Max tool calls executed per turn
    context_budget_tokens: int = 48000    # Context window trimming budget
    max_output_chars: int = 4000          # Per-tool output character limit


class JsonlLog:
    def __init__(self, path: Any):
        self.file = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, record: Dict[str, Any]) -> None:
        self.file.write(json.dumps(record, default=str) + "\n")

    def close(self) -> None:
        self.file.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def show(record: Dict[str, Any]) -> None:
    """Prints a concise, single-line telemetry update for each step."""
    tools = ",".join(a.get("tool", "?") for a in record.get("parsed_actions", [])) or "-"
    reward = record.get("reward", {}).get("total") if record.get("reward") else None
    reward_str = f"{reward:.3f}" if (reward is not None and isinstance(reward, (int, float))) else "-"
    state_hash = record.get("state", {}).get("hash", "unknown")
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
        if not shrunk:
            return


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
            "reward": env.score(),
            "tokens": 0,
            "latency_ms": 0,
        }
        log.write(record)
        show(record)

    final = env.score()
    log.write({
        "timestamp": now(),
        "agent": agent,
        "task": task_id,
        "event": "episode_end",
        "seed": seed,
        "steps": step,
        "reward": final,
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

    started: Optional[float] = None
    termination: Optional[str] = None
    finished: bool = False
    steps: int = 0

    for step in range(1, limits.max_steps + 1):
        if started is not None and (time.monotonic() - started) >= limits.max_seconds:
            termination = "time_cap"
            break
        if started is None:
            started = time.monotonic()

        trim_history(messages, limits.context_budget_tokens)
        sent = copy.deepcopy(messages)
        remaining = limits.max_seconds - (time.monotonic() - started)
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
            reply = client.complete(sent, TOOLS, timeout=max(5, min(120, remaining)))
        except Exception as exc:
            record["errors"].append({"kind": "model_call_failed", "detail": f"{type(exc).__name__}: {exc}"})
            log.write(record)
            show(record)
            termination = "crash"
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

        for index, call in enumerate(reply.tool_calls):
            args, parse_error = call.parse()
            record["parsed_actions"].append({"tool": call.name, "args": args, "parse_error": parse_error})

            if finished:
                result = "not run: the episode has already finished"
            elif index >= limits.max_tool_calls:
                result = f"not run: at most {limits.max_tool_calls} tool calls allowed per turn"
                record["errors"].append({"kind": "too_many_tool_calls", "detail": call.name})
            elif parse_error:
                result = f"error: {parse_error}"
                record["errors"].append({"kind": "unparsable_arguments", "detail": call.name})
            elif call.name not in SPECS:
                result = f"error: unknown tool '{call.name}'. Available: {', '.join(TOOL_NAMES)}"
                record["errors"].append({"kind": "unknown_tool", "detail": call.name})
            elif (problem := check_args(call.name, args)):
                result = f"error: {problem}"
                record["errors"].append({"kind": "invalid_arguments", "detail": f"{call.name}: {problem}"})
            elif call.name == "finish":
                finished = True
                result = "Episode finished. Verifying resolution and calculating score."
            else:
                result, is_error = env.step(call.name, args)
                if is_error:
                    record["errors"].append({"kind": "tool_error", "detail": result})

            result = result[:limits.max_output_chars]
            record["tool_result"].append(result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        record["state"] = {"hash": env.state_hash()}
        record["reward"] = env.score()
        log.write(record)
        show(record)

        if finished:
            break
    else:
        termination = "step_cap"

    try:
        final = env.score()
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
