"""Quick connectivity check: sends one test message to your model and prints the reply.

Usage:
    API_KEY=... BASE_URL=... MODEL=... python check_model.py
"""
import os
import sys

def load_dotenv_if_present():
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k not in os.environ and v:
                        os.environ[k] = v

def main():
    load_dotenv_if_present()
    api_key = os.environ.get("API_KEY")
    base_url = os.environ.get("BASE_URL") or None
    model = os.environ.get("MODEL", "gpt-4o-mini")

    if not api_key:
        print("ERROR: API_KEY environment variable is not set.", file=sys.stderr)
        print("Example: API_KEY=your-key BASE_URL=https://... MODEL=gpt-luna python check_model.py", file=sys.stderr)
        sys.exit(1)

    import openai
    print(f"Connecting to model '{model}' at base_url='{base_url or 'default OpenAI'}'...")
    try:
        client = openai.OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi, are you ready for OpsArena RL evaluation?"}],
            max_tokens=60,
            timeout=30.0,
        )
        print("\nSuccess! Model reply:")
        print(response.choices[0].message.content)
        if hasattr(response, "usage") and response.usage:
            print(f"\nTokens used: {response.usage.total_tokens}")
    except Exception as exc:
        print(f"\nConnection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
