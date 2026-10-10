"""
Hybrid Worker - Fast Haiku response + background Sonnet enhancement.

Architecture Note
-----------------
The Hybrid path is NOT a single worker class.  It is split across two
components that each handle one leg of the hybrid flow:

**Leg 1 (Fast, synchronous):**
    Handled by ``api.v1.ws_publishers.publish_hybrid_path()`` in the API layer.
    Uses ``FastWorker`` to produce an immediate response via Haiku and
    push chunks through WebSocket PubSub. At the end of the fast leg, a
    ``TaskPayload`` with ``route_type="hybrid_background"`` is enqueued
    into the Celery/Redis task queue.

**Leg 2 (Background, asynchronous):**
    Handled by ``AgentWorker.process()`` when it receives a task with
    ``route_type="hybrid_background"``.  The worker loads the enrichment
    directives from ``hybrid_enrichment.format_hybrid_section()`` and
    injects them into the system prompt.  The Sonnet SDK agent then
    cross-references user context (schedules, trips, memories) and
    publishes additional insights via Redis PubSub / WebSocket.

**Cooldown:**
    The ``IntentRouter._check_hybrid_frequency()`` method enforces a
    30-minute cooldown per topic per user to prevent over-notification.

Flow Diagram::

    User Request
         |
    IntentRouter (Haiku) → route_type=HYBRID
         |
    publish_hybrid_path()
         |--- FastWorker → immediate streamed response
         |--- enqueue(route_type=hybrid_background)
         |
    AgentWorker.process()
         |--- format_hybrid_section() → enrichment directives
         |--- Sonnet SDK → cross-reference user context
         |--- PubSub → WebSocket push to mobile
"""
