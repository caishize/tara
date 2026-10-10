#!/usr/bin/env python3
"""
SDK Streaming Input Behavior Verification Tests.

Validates Claude Agent SDK's actual behavior for multi-query streaming input,
mid-turn injection, and interrupt+resume patterns.

Tests:
  1 - Simple multi-query: two simple questions, sequential (baseline)
  2 - Mid-turn injection: query() during tool execution (expected: FAIL)
  3 - Interrupt + immediate query: interrupt() + query() with no wait (expected: FAIL)
  4 - Post-result query: query() after ResultMessage with tool use (expected: PASS)
  5 - Interrupt + wait + query: interrupt() → wait for result → query() (expected: PASS)
  6 - Interrupt + delay + query: interrupt() → 500ms → query() (expected: PASS)

Usage:
    PYTHONUNBUFFERED=1 python3 tests/sdk_streaming_input_test.py [1|2|3|4|5|6|all]

Results (2026-02-21):
    Test 1: PASS - receive_messages() works across multiple turns
    Test 2: FAIL - CLI drops query() sent during tool execution
    Test 3: FAIL - CLI drops query() sent immediately after interrupt()
    Test 4: PASS - query() after ResultMessage is immediately processed
    Test 5: PASS - interrupt → wait result → query works perfectly
    Test 6: PASS - interrupt → 500ms delay → query works perfectly

Conclusion:
    - CLI does NOT support mid-turn message injection
    - interrupt() is <10ms, but must wait for error ResultMessage before new query()
    - Correct pattern: interrupt() → await ResultMessage(error) → query(new)
"""

import asyncio
import contextlib
import json
import os
import sys
import time
from datetime import datetime

# Unset CLAUDECODE to avoid nested-session detection in SDK >= 0.1.38
os.environ.pop("CLAUDECODE", None)

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)


def log(msg: str) -> None:
    t = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{t}] {msg}", flush=True)


def describe_msg(msg) -> str:
    if isinstance(msg, AssistantMessage):
        parts = []
        for b in msg.content:
            if isinstance(b, TextBlock):
                txt = (b.text or "")[:80].replace("\n", " ")
                parts.append(f'"{txt}"')
            elif isinstance(b, ToolUseBlock):
                parts.append(f"Tool({b.name})")
            else:
                parts.append(type(b).__name__)
        return f"Assistant[{', '.join(parts)}]"
    elif isinstance(msg, ResultMessage):
        return f"RESULT(subtype={getattr(msg, 'subtype', '?')})"
    else:
        return type(msg).__name__


async def safe_receive(client):
    """Wrapper around receive_messages() that skips unknown message types."""
    from claude_agent_sdk._errors import MessageParseError
    from claude_agent_sdk._internal.message_parser import parse_message

    if not client._query:
        return
    async for data in client._query.receive_messages():
        try:
            yield parse_message(data)
        except (MessageParseError, Exception) as e:
            if "Unknown message type" in str(e):
                log(f"  (skipped unknown msg type: {data.get('type', '?')})")
                continue
            raise


def make_client():
    return ClaudeSDKClient(options=ClaudeAgentOptions(
        permission_mode="bypassPermissions",
    ))


async def test1():
    """Simple multi-query (no tools) - baseline test."""
    log("=== TEST 1: Simple multi-query (no tools) ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0

        async def rx():
            nonlocal result_count
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1

        task = asyncio.create_task(rx())
        for q in ["What is 2+3? Just the number.", "What is 10*5? Just the number."]:
            log(f"  >>> Sending: {q}")
            await client.query(q)
            await asyncio.sleep(5)

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def test2():
    """Mid-turn injection: query() during tool execution."""
    log("=== TEST 2: Mid-turn injection (during tool) ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0
        injected = False

        async def rx():
            nonlocal result_count, injected
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1
                if isinstance(msg, AssistantMessage) and not injected:
                    if any(isinstance(b, ToolUseBlock) for b in msg.content):
                        injected = True
                        log(f"  >>> INJECTING during tool at {elapsed:.1f}s")
                        await client.query("What is 7*6? Just the number.")

        task = asyncio.create_task(rx())
        await client.query("Run: echo 'HELLO' && sleep 3 && echo 'WORLD'")

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def test3():
    """Interrupt + immediate query (no wait for result)."""
    log("=== TEST 3: interrupt() + immediate query() ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0
        interrupted = False

        async def rx():
            nonlocal result_count, interrupted
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1
                if isinstance(msg, AssistantMessage) and not interrupted:
                    if any(isinstance(b, ToolUseBlock) for b in msg.content):
                        interrupted = True
                        log(f"  >>> interrupt() at {elapsed:.1f}s")
                        await client.interrupt()
                        log(f"  >>> Immediate query()")
                        await client.query("What is 7*6? Just the number.")

        task = asyncio.create_task(rx())
        await client.query("Run: echo 'START' && sleep 10 && echo 'END'")

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def test4():
    """Post-result query: query() after ResultMessage."""
    log("=== TEST 4: query() after ResultMessage ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0
        q2_sent = False

        async def rx():
            nonlocal result_count, q2_sent
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1
                    if result_count == 1 and not q2_sent:
                        q2_sent = True
                        log(f"  >>> Sending Q2 after result at {elapsed:.1f}s")
                        await client.query("What is 7*6? Just the number.")

        task = asyncio.create_task(rx())
        await client.query("Run: echo 'HELLO WORLD'")

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def test5():
    """Interrupt + wait for result + then query."""
    log("=== TEST 5: interrupt() → wait result → query() ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0
        q2_sent = False

        async def rx():
            nonlocal result_count, q2_sent
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1
                    if result_count == 1 and not q2_sent:
                        q2_sent = True
                        log(f"  >>> Q2 after interrupt result at {elapsed:.1f}s")
                        await client.query("What is 7*6? Just the number.")

        task = asyncio.create_task(rx())
        await client.query("Run: echo 'START' && sleep 10 && echo 'END'")

        await asyncio.sleep(4)
        log("  >>> interrupt()")
        t_int = time.monotonic()
        await client.interrupt()
        log(f"  >>> interrupted in {(time.monotonic()-t_int)*1000:.0f}ms")

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def test6():
    """Interrupt + 500ms delay + query."""
    log("=== TEST 6: interrupt() → 500ms → query() ===")
    async with make_client() as client:
        t0 = time.monotonic()
        result_count = 0

        async def rx():
            nonlocal result_count
            async for msg in safe_receive(client):
                elapsed = time.monotonic() - t0
                log(f"  RX {elapsed:5.1f}s | {describe_msg(msg)}")
                if isinstance(msg, ResultMessage):
                    result_count += 1

        task = asyncio.create_task(rx())
        await client.query("Run: echo 'START' && sleep 10 && echo 'END'")

        await asyncio.sleep(4)
        log("  >>> interrupt()")
        await client.interrupt()
        await asyncio.sleep(0.5)
        log("  >>> query() after 500ms")
        await client.query("What is 7*6? Just the number.")

        while result_count < 2:
            if time.monotonic() - t0 > 30:
                break
            await asyncio.sleep(0.5)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    log(f"  Result: {'PASS' if result_count >= 2 else 'FAIL'} ({result_count}/2 results)")


async def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "all"
    tests = {
        "1": test1, "2": test2, "3": test3,
        "4": test4, "5": test5, "6": test6,
    }

    if choice == "all":
        for name, fn in tests.items():
            await fn()
            log("")
    elif choice in tests:
        await tests[choice]()
    else:
        log(f"Usage: python3 ... [1|2|3|4|5|6|all]")


if __name__ == "__main__":
    asyncio.run(main())
