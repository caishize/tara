"""
SDK Stream Latency Integration Test
====================================

Tests both cold-start and warm-path SDK latency by hitting
the real chat API with force_slow_path=True.

Usage:
    # Start backend + worker first:
    #   cd backend && uvicorn src.main:app --port 8000
    #   cd backend && python -m src.ai_engine.worker_main
    #
    # Then run standalone:
    #   cd backend && python tests/integration/test_sdk_latency.py
    #
    # Or with pytest:
    #   cd backend && python -m pytest tests/integration/test_sdk_latency.py -v -s -k sdk_latency

Env vars:
    LATENCY_TEST_BASE_URL   (default http://localhost:8000)

Requires:
    - Running backend + agent worker
    - STRICT_AUTH_ENABLED=false + ENVIRONMENT=development (auth bypass)
    - CLAUDE_AGENT_ENABLED=true
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("LATENCY_TEST_BASE_URL", "http://localhost:8000")
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
API_PREFIX = "/api/v1"

# Default dev-mode user/family (when STRICT_AUTH_ENABLED=false)
DEFAULT_USER_ID = "123e4567-e89b-12d3-a456-426614174001"

# Messages for testing — use force_slow_path to ensure SDK execution
COLD_START_MESSAGE = "帮我想一个周末活动计划"
WARM_PATH_MESSAGE = "再加一个室内备选方案"

# Timeouts
HTTP_TIMEOUT = 15.0
WS_TIMEOUT = 180.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _connect_ws(user_id: str) -> Any:
    """Connect to WebSocket with dev-mode dummy token."""
    ws_uri = (
        f"{WS_URL}{API_PREFIX}/ws/{user_id}"
        f"?token=dev_bypass&device_id=latency_test"
    )
    return await websockets.connect(ws_uri, close_timeout=5)


async def _send_chat(
    client: httpx.AsyncClient,
    message: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """POST /api/v1/chat with force_slow_path=True."""
    payload: Dict[str, Any] = {
        "message": message,
        "force_slow_path": True,
    }
    if session_id:
        payload["session_id"] = session_id

    t0 = time.monotonic()
    resp = await client.post(
        f"{API_PREFIX}/chat",
        json=payload,
        timeout=HTTP_TIMEOUT,
    )
    t_http = time.monotonic() - t0

    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"Chat API {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    data["_http_latency_ms"] = round(t_http * 1000)
    return data


async def _collect_ws_events(
    ws: Any,
    job_id: str,
    timeout: float = WS_TIMEOUT,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Collect WS events for a job until 'done' or timeout.

    Returns (events, timing_dict) where timing values are in milliseconds
    measured from the moment this function was called (i.e. right after
    the HTTP POST returned).
    """
    events: List[Dict[str, Any]] = []
    t_start = time.monotonic()
    timing: Dict[str, float] = {}
    flags = {
        "first_event": False,
        "first_content": False,
        "first_thinking": False,
        "first_text": False,
        "first_tool": False,
    }

    try:
        while True:
            remaining = timeout - (time.monotonic() - t_start)
            if remaining <= 0:
                logger.warning("  [TIMEOUT] No completion after %.0fs", timeout)
                break

            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=min(remaining, 30),
                )
            except asyncio.TimeoutError:
                continue

            elapsed_ms = round((time.monotonic() - t_start) * 1000)

            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            # ---- filter to our job ----
            msg_job_id = msg.get("job_id") or msg.get("trace_id")
            payload = msg.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            payload_job = payload.get("job_id") or payload.get("trace_id")

            if msg_job_id != job_id and payload_job != job_id:
                # Also accept untagged keepalive / session events
                if msg_job_id or payload_job:
                    continue

            events.append({"elapsed_ms": elapsed_ms, "msg": msg})

            msg_type = (
                msg.get("message_type") or msg.get("type") or ""
            ).lower()
            p_type = payload.get("type", "")
            p_content = payload.get("content", "")
            p_phase = payload.get("phase", "")

            # ---- timing marks ----
            if not flags["first_event"]:
                flags["first_event"] = True
                timing["first_event_ms"] = elapsed_ms

            if not flags["first_content"] and msg_type == "content":
                flags["first_content"] = True
                timing["first_content_event_ms"] = elapsed_ms

            if not flags["first_thinking"] and (
                p_type in ("thinking", "thinking_start")
                or p_phase in ("start", "chunk")
            ):
                flags["first_thinking"] = True
                timing["first_thinking_ms"] = elapsed_ms
                logger.info("  [+%6.1fs] Thinking started", elapsed_ms / 1000)

            if not flags["first_tool"] and msg_type == "tool_execution":
                flags["first_tool"] = True
                timing["first_tool_ms"] = elapsed_ms
                logger.info(
                    "  [+%6.1fs] First tool: %s (%s)",
                    elapsed_ms / 1000,
                    payload.get("name", "?"),
                    payload.get("status", "?"),
                )

            if not flags["first_text"] and (
                msg_type == "content"
                and p_type == "content"
                and isinstance(p_content, str)
                and p_content.strip()
            ):
                flags["first_text"] = True
                timing["first_text_ms"] = elapsed_ms
                logger.info(
                    "  [+%6.1fs] First text: %.80s",
                    elapsed_ms / 1000,
                    p_content.strip(),
                )

            # tool execution progress logging
            if (
                msg_type == "tool_execution"
                and flags["first_tool"]
                and payload.get("status") in ("success", "error")
            ):
                logger.info(
                    "  [+%6.1fs] Tool done: %s → %s",
                    elapsed_ms / 1000,
                    payload.get("name", "?"),
                    payload.get("status"),
                )

            # ---- completion ----
            if p_type == "done" or msg_type == "complete":
                timing["complete_ms"] = elapsed_ms
                logger.info("  [+%6.1fs] Complete", elapsed_ms / 1000)
                break

            if msg_type == "error":
                timing["complete_ms"] = elapsed_ms
                logger.error(
                    "  [+%6.1fs] ERROR: %s",
                    elapsed_ms / 1000,
                    payload.get("message", str(payload)[:200]),
                )
                break

    except websockets.exceptions.ConnectionClosed as e:
        logger.error("  WebSocket closed unexpectedly: %s", e)
    except Exception as e:
        logger.error("  WS collection error: %s", e, exc_info=True)

    return events, timing


def _print_report(
    label: str,
    http_data: Dict[str, Any],
    timing: Dict[str, float],
    event_count: int,
) -> None:
    """Print a human-readable latency report."""
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Route type:          {http_data.get('route_type', '?')}")
    print(f"  Job ID:              {http_data.get('job_id', '?')}")
    print(f"  Session ID:          {http_data.get('session_id', '?')}")
    print()

    rows = [
        ("HTTP dispatch", http_data.get("_http_latency_ms", 0)),
        ("First WS event", timing.get("first_event_ms", 0)),
        ("First thinking", timing.get("first_thinking_ms", 0)),
        ("First tool call", timing.get("first_tool_ms", 0)),
        ("First text output", timing.get("first_text_ms", 0)),
        ("Complete", timing.get("complete_ms", 0)),
        ("Total E2E", timing.get("total_e2e_ms", 0)),
    ]
    for name, ms in rows:
        if ms:
            print(f"  {name:<22} {ms:>8.0f} ms")
        else:
            print(f"  {name:<22} {'---':>8}")

    print(f"  {'WS events total':<22} {event_count:>8}")
    print(f"{'='*65}\n")


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------

async def run_latency_test() -> None:
    """Run cold-start and warm-path latency tests."""

    print("\n" + "=" * 65)
    print("  SDK Stream Latency Test")
    print(f"  Target: {BASE_URL}")
    print("=" * 65)

    # 0. Health check
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        try:
            resp = await client.get("/health", timeout=5)
            logger.info("Health check: %d", resp.status_code)
        except Exception as e:
            print(f"\nERROR: Backend not reachable at {BASE_URL}")
            print(f"  {e}")
            print("Start with: cd backend && uvicorn src.main:app --port 8000")
            return

    # 1. Connect WebSocket
    logger.info("Connecting WebSocket for user %s ...", DEFAULT_USER_ID)
    try:
        ws = await _connect_ws(DEFAULT_USER_ID)
    except Exception as e:
        print(f"\nERROR: WebSocket connection failed: {e}")
        print("Ensure STRICT_AUTH_ENABLED=false and ENVIRONMENT=development")
        return
    logger.info("WebSocket connected")

    # Drain any stale messages before test
    try:
        while True:
            await asyncio.wait_for(ws.recv(), timeout=1.0)
    except (asyncio.TimeoutError, Exception):
        pass

    async with httpx.AsyncClient(base_url=BASE_URL) as client:

        # ==================================================================
        # Test 1: Cold Start (new session, new CLI process)
        # ==================================================================
        print("\n" + "-" * 65)
        logger.info("TEST 1: COLD START — new session, likely new CLI process")
        logger.info("Message: %s", COLD_START_MESSAGE)

        t_e2e = time.monotonic()
        http_data_1 = await _send_chat(client, COLD_START_MESSAGE)
        job_1 = http_data_1["job_id"]
        sess = http_data_1["session_id"]
        logger.info(
            "Dispatched: job=%s session=%s route=%s http=%dms",
            job_1, sess, http_data_1.get("route_type"),
            http_data_1["_http_latency_ms"],
        )

        events_1, timing_1 = await _collect_ws_events(ws, job_1)
        timing_1["total_e2e_ms"] = round((time.monotonic() - t_e2e) * 1000)

        _print_report("Test 1: COLD START", http_data_1, timing_1, len(events_1))

        # Brief pause — let the SDK client pool settle
        logger.info("Pausing 5s before warm-path test...")
        await asyncio.sleep(5)

        # ==================================================================
        # Test 2: Warm Path (same session, reuse pooled CLI)
        # ==================================================================
        print("-" * 65)
        logger.info("TEST 2: WARM PATH — same session, expect pooled CLI reuse")
        logger.info("Message: %s", WARM_PATH_MESSAGE)

        t_e2e = time.monotonic()
        http_data_2 = await _send_chat(client, WARM_PATH_MESSAGE, session_id=sess)
        job_2 = http_data_2["job_id"]
        logger.info(
            "Dispatched: job=%s session=%s route=%s http=%dms",
            job_2, sess, http_data_2.get("route_type"),
            http_data_2["_http_latency_ms"],
        )

        events_2, timing_2 = await _collect_ws_events(ws, job_2)
        timing_2["total_e2e_ms"] = round((time.monotonic() - t_e2e) * 1000)

        _print_report("Test 2: WARM PATH", http_data_2, timing_2, len(events_2))

        # ==================================================================
        # Summary comparison
        # ==================================================================
        metrics = [
            ("first_event_ms", "First WS event"),
            ("first_thinking_ms", "First thinking"),
            ("first_text_ms", "First text output"),
            ("complete_ms", "Complete"),
            ("total_e2e_ms", "Total E2E"),
        ]

        print("=" * 65)
        print("  COMPARISON")
        print("=" * 65)
        print(f"  {'Metric':<22} {'Cold':>10} {'Warm':>10} {'Speedup':>10}")
        print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*10}")

        for key, label in metrics:
            v1 = timing_1.get(key, 0)
            v2 = timing_2.get(key, 0)
            if v1 and v2:
                ratio = f"{v1 / v2:.1f}x"
            else:
                ratio = "—"
            c = f"{v1:.0f}ms" if v1 else "—"
            w = f"{v2:.0f}ms" if v2 else "—"
            print(f"  {label:<22} {c:>10} {w:>10} {ratio:>10}")

        print("=" * 65)

        # Interpretation
        cold_first = timing_1.get("first_text_ms", 0)
        warm_first = timing_2.get("first_text_ms", 0)
        if cold_first and warm_first:
            diff_s = (cold_first - warm_first) / 1000
            print(f"\n  Cold start added ~{diff_s:.1f}s to first-text latency.")
            if diff_s > 30:
                print("  >> CLI cold start is dominant. Consider pre-warming.")
            elif diff_s > 10:
                print("  >> Moderate cold-start penalty. Pool is helping but not fully warm.")
            else:
                print("  >> Cold start penalty is small — pool may already be warm.")
        print()

    await ws.close()
    logger.info("Done. Check backend worker logs for detailed SDK timing.")
    print(
        "\nTIP: Look in worker logs for these lines to see breakdown:\n"
        "  - 'CLI subprocess ready (startup_ms=...)'\n"
        "  - 'Cold-start prompt built: ...enriched_len=...'\n"
        "  - 'SDK stream latency first_content_text: ...'\n"
        "  - 'Streaming query submitted: ...cold_start=...'\n"
        "  - 'Reusing pooled client ...' or 'Pooled execution completed ...'\n"
    )


# ---------------------------------------------------------------------------
# pytest entry point
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason=(
        "Set RUN_INTEGRATION_TESTS=1 to run. "
        "Requires live backend + worker."
    ),
)
async def test_sdk_latency_cold_vs_warm():
    """Integration test: compare cold-start vs warm-path SDK latency."""
    await run_latency_test()


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_latency_test())
