"""OpsArena Agent Wrappers, Mock Clients, and Baseline Action Generators."""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # Raw JSON or string sent by model

    def parse(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Returns (args, error). args is a dict when valid JSON."""
        try:
            args = json.loads(self.arguments) if self.arguments else {}
        except json.JSONDecodeError as exc:
            return None, f"arguments are not valid JSON ({exc.msg})"
        if not isinstance(args, dict):
            return None, "arguments must be a JSON object"
        return args, None

    def history_arguments(self) -> str:
        """Returns clean JSON for chat message history, falling back to '{}' if malformed."""
        args, error = self.parse()
        return json.dumps(args) if error is None else "{}"


@dataclass
class Reply:
    text: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: str = ""
    tokens: int = 0


class OpenAIClient:
    """Invokes OpenAI-compatible LLM endpoints (e.g. gpt-6-luna at penpencil.guru)."""

    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, max_tokens: Optional[int] = None):
        import openai
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url or None, max_retries=2)
        self.model = model
        self.max_tokens = max_tokens

    def start(self, task: Any) -> None:
        pass

    def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], timeout: float) -> Reply:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "timeout": timeout,
        }
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        calls: List[ToolCall] = []
        for idx, call in enumerate(message.tool_calls or []):
            fn = getattr(call, "function", None)
            calls.append(
                ToolCall(
                    id=call.id or f"call_{idx}",
                    name=(fn.name if fn else "") or "",
                    arguments=(fn.arguments if fn else "") or "",
                )
            )

        usage = getattr(response, "usage", None)
        total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
        raw_json = response.model_dump_json() if hasattr(response, "model_dump_json") else str(response)

        return Reply(
            text=message.content,
            tool_calls=calls,
            raw=raw_json,
            tokens=total_tokens or 0,
        )


class MockClient:
    """Offline mock agents for testing without consuming API credits:
    - mock/solver: Replays the reference oracle actions for the current task.
    - mock/idle: Exits immediately without issuing operational commands.
    """

    def __init__(self, kind: str):
        self.kind = kind
        self.turn = 0
        self.task = None

    def start(self, task: Any) -> None:
        self.task = task
        self.turn = 0

    def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], timeout: float) -> Reply:
        self.turn += 1
        calls = []

        if self.kind == "solver" and self.turn == 1 and self.task:
            for name, args in self.task.oracle_actions:
                calls.append((name, args))
        else:
            calls.append(("finish", {}))

        tool_calls = [
            ToolCall(
                id=f"mock-{self.turn}-{i}",
                name=name,
                arguments=json.dumps(args),
            )
            for i, (name, args) in enumerate(calls)
        ]
        return Reply(
            text=None,
            tool_calls=tool_calls,
            raw=json.dumps({"mock": self.kind, "turn": self.turn}),
            tokens=42,
        )


def make_client(model: str, api_key: Optional[str], base_url: Optional[str], max_tokens: Optional[int] = None):
    if model.startswith("mock/"):
        kind = model.split("/", 1)[1]
        if kind not in ("solver", "idle"):
            raise ValueError("mock models must be 'mock/solver' or 'mock/idle'")
        return MockClient(kind)
    if not api_key:
        raise ValueError("API_KEY environment variable is not set")
    return OpenAIClient(model=model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)


def oracle_actions(task: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """Returns the targeted reference mitigation sequence."""
    return task.oracle_actions


def noop_actions(task: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """Returns an empty sequence representing an agent that does nothing."""
    return task.noop_actions or []
