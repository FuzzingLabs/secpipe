#!/usr/bin/env python3
"""
Simple example of using the A2A wrapper
Run from project root: python examples/test_a2a_simple.py
"""
import asyncio


async def main():
    # Clean import!
    from fuzzforge_ai.a2a_wrapper import send_agent_task

    print("Sending task to agent at http://127.0.0.1:10900...")

    result = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        model="gpt-4o-mini",
        provider="openai",
        prompt="You are concise.",
        message="Give me a simple Python function that adds two numbers.",
        context="test_session",
        timeout=120
    )

    print(f"\nContext ID: {result.context_id}")
    print(f"\nResponse:\n{result.text}")


if __name__ == "__main__":
    asyncio.run(main())
