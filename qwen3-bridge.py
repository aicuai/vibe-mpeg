#!/usr/bin/env python3
"""
qwen3-bridge.py - Bridge between Qwen3 (via Ollama) and vibe-mpeg skills.

Provides a chat interface where Qwen3 can call vibe-mpeg video editing tools.
Works fully offline with Ollama.

Usage:
  python qwen3-bridge.py                    # Interactive chat mode
  python qwen3-bridge.py "make a slideshow with 3 slides about cats"  # One-shot
  python qwen3-bridge.py --model qwen3:8b   # Use specific model
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing requests...", file=sys.stderr)
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

SKILLS_DIR = Path(__file__).parent / "skills"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("VIBE_MODEL", "qwen3:8b")


def load_tools() -> list[dict]:
    """Load skill definitions as Ollama-compatible tool schemas."""
    tools = []
    for skill_path in SKILLS_DIR.glob("*.json"):
        with open(skill_path) as f:
            skill = json.load(f)
        tools.append({
            "type": "function",
            "function": {
                "name": skill["name"],
                "description": skill.get("description", ""),
                "parameters": skill.get("parameters", {}),
            },
        })
    return tools


def call_ollama(messages: list[dict], model: str, tools: list[dict]) -> dict:
    """Call Ollama chat API with tool support."""
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
    }

    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def execute_tool_call(tool_call: dict) -> str:
    """Execute a tool call via render.py and return the result."""
    import subprocess

    name = tool_call["function"]["name"]
    args = tool_call["function"].get("arguments", {})
    if isinstance(args, str):
        args = json.loads(args)

    input_data = json.dumps({"skill": name, "params": args})
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "render.py"), "--stdin"],
        input=input_data,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return result.stdout
    else:
        return json.dumps({"error": result.stderr[-1000:]})


def chat_loop(model: str):
    """Interactive chat loop with tool calling."""
    tools = load_tools()
    system_msg = {
        "role": "system",
        "content": (
            "You are vibe-mpeg, an offline video editing assistant. "
            "You help users create videos using Remotion. "
            "You have access to tools for creating slideshows, text overlays, and rendering videos. "
            "When the user asks to create a video, use the appropriate tool. "
            "Always confirm what you'll create before calling a tool."
        ),
    }
    messages = [system_msg]

    print("vibe-mpeg video editor (type 'quit' to exit)")
    print(f"Model: {model} | Tools: {[t['function']['name'] for t in tools]}")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = call_ollama(messages, model, tools)
        except requests.exceptions.ConnectionError:
            print(f"Error: Cannot connect to Ollama at {OLLAMA_URL}")
            print("Make sure Ollama is running: ollama serve")
            messages.pop()
            continue
        except Exception as e:
            print(f"Error: {e}")
            messages.pop()
            continue

        msg = response.get("message", {})
        messages.append(msg)

        # Handle tool calls
        if msg.get("tool_calls"):
            for tool_call in msg["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                fn_args = tool_call["function"].get("arguments", {})
                print(f"\n[Tool: {fn_name}] {json.dumps(fn_args, ensure_ascii=False)}")

                result = execute_tool_call(tool_call)
                print(f"[Result] {result.strip()}")

                messages.append({
                    "role": "tool",
                    "content": result,
                })

            # Get final response after tool execution
            try:
                final = call_ollama(messages, model, tools)
                final_msg = final.get("message", {})
                messages.append(final_msg)
                if final_msg.get("content"):
                    print(f"\nAssistant: {final_msg['content']}")
            except Exception as e:
                print(f"Error getting response: {e}")
        elif msg.get("content"):
            print(f"\nAssistant: {msg['content']}")

        print()


def one_shot(prompt: str, model: str):
    """Execute a single prompt."""
    tools = load_tools()
    messages = [
        {
            "role": "system",
            "content": (
                "You are vibe-mpeg, an offline video editing assistant. "
                "Use the available tools to fulfill the user's request. "
                "Call the appropriate tool immediately."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    response = call_ollama(messages, model, tools)
    msg = response.get("message", {})

    if msg.get("tool_calls"):
        for tool_call in msg["tool_calls"]:
            result = execute_tool_call(tool_call)
            print(result)
    elif msg.get("content"):
        print(msg["content"])


def main():
    parser = argparse.ArgumentParser(description="vibe-mpeg Qwen3 bridge")
    parser.add_argument("prompt", nargs="?", help="One-shot prompt")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    args = parser.parse_args()

    if args.list_tools:
        tools = load_tools()
        for t in tools:
            fn = t["function"]
            print(f"  {fn['name']}: {fn['description']}")
        return

    if args.prompt:
        one_shot(args.prompt, args.model)
    else:
        chat_loop(args.model)


if __name__ == "__main__":
    main()
