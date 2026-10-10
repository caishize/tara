"""ReactiveSessionActor tests have been split into focused modules.

See:
- test_actor_state_machine.py  — State machine, non-interruptible, public interface
- test_actor_signals.py        — Signal queue, dispatch, dedup, job ID, extract text
- test_actor_handlers.py       — Intervention handlers, deferred, buffering, sidekick
- test_actor_recovery.py       — Session status staleness, resume logic
"""
