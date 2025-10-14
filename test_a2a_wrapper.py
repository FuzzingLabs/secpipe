#!/usr/bin/env python3
"""
Test script for A2A wrapper module
Sends tasks to the task-agent to verify functionality
"""
import asyncio
import sys
from pathlib import Path

# Add ai module to path
ai_src = Path(__file__).parent / "ai" / "src"
sys.path.insert(0, str(ai_src))

from fuzzforge_ai.a2a_wrapper import send_agent_task, get_agent_config


async def test_basic_task():
    """Test sending a basic task to the agent"""
    print("=" * 80)
    print("Test 1: Basic task without model specification")
    print("=" * 80)

    result = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        message="What is 2+2? Answer in one sentence.",
        timeout=30
    )

    print(f"Context ID: {result.context_id}")
    print(f"Response:\n{result.text}")
    print()
    return result.context_id


async def test_with_model_and_prompt():
    """Test sending a task with custom model and prompt"""
    print("=" * 80)
    print("Test 2: Task with model and prompt specification")
    print("=" * 80)

    result = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        model="gpt-4o-mini",
        provider="openai",
        prompt="You are a concise Python expert. Answer in 2 sentences max.",
        message="Write a simple Python function that checks if a number is prime.",
        context="python_test",
        timeout=60
    )

    print(f"Context ID: {result.context_id}")
    print(f"Response:\n{result.text}")
    print()
    return result.context_id


async def test_fuzzing_task():
    """Test a fuzzing-related task"""
    print("=" * 80)
    print("Test 3: Fuzzing harness generation task")
    print("=" * 80)

    result = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        model="gpt-4o-mini",
        provider="openai",
        prompt="You are a security testing expert. Provide practical, working code.",
        message="Generate a simple fuzzing harness for a C function that parses JSON strings. Include only the essential code.",
        context="fuzzing_session",
        timeout=90
    )

    print(f"Context ID: {result.context_id}")
    print(f"Response:\n{result.text}")
    print()


async def test_get_config():
    """Test getting agent configuration"""
    print("=" * 80)
    print("Test 4: Get agent configuration")
    print("=" * 80)

    config = await get_agent_config(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        timeout=30
    )

    print(f"Agent Config:\n{config}")
    print()


async def test_multi_turn():
    """Test multi-turn conversation with same context"""
    print("=" * 80)
    print("Test 5: Multi-turn conversation")
    print("=" * 80)

    # First message
    result1 = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        message="What is the capital of France?",
        context="geography_quiz",
        timeout=30
    )
    print(f"Q1: What is the capital of France?")
    print(f"A1: {result1.text}")
    print()

    # Follow-up in same context
    result2 = await send_agent_task(
        url="http://127.0.0.1:10900/a2a/litellm_agent",
        message="What is the population of that city?",
        context="geography_quiz",  # Same context
        timeout=30
    )
    print(f"Q2: What is the population of that city?")
    print(f"A2: {result2.text}")
    print()


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("FuzzForge A2A Wrapper Test Suite")
    print("=" * 80 + "\n")

    try:
        # Run tests
        await test_basic_task()
        await test_with_model_and_prompt()
        await test_fuzzing_task()
        await test_get_config()
        await test_multi_turn()

        print("=" * 80)
        print("✅ All tests completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
