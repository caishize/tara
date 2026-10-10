"""User interruption control based on priority and time of day.

Decides how a notification should be delivered:
  - immediate:       sound + banner (P0 always, P1 during daytime)
  - badge_only:      silent badge increment (P2 daytime)
  - queue_for_later: held until morning delivery window (night hours, P3)

V8 architecture: docs/architecture-v8-secretary-brain.md section 5.3
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryDecision:
    """Immutable delivery decision returned by InterruptionController.

    Attributes:
        mode: One of "immediate", "badge_only", "queue_for_later".
        reason: Human-readable explanation of the decision.
    """

    mode: str
    reason: str = ""


class InterruptionController:
    """Stateless controller that maps (priority, hour) to a delivery mode.

    Night hours default to 23:00-07:00 but can be configured per instance.
    """

    def __init__(
        self,
        night_start: int = 23,
        night_end: int = 7,
    ):
        if not (0 <= night_start <= 23):
            raise ValueError(f"night_start must be 0-23, got {night_start}")
        if not (0 <= night_end <= 23):
            raise ValueError(f"night_end must be 0-23, got {night_end}")
        self._night_start = night_start
        self._night_end = night_end

    @property
    def night_start(self) -> int:
        return self._night_start

    @property
    def night_end(self) -> int:
        return self._night_end

    def is_night(self, hour_of_day: int) -> bool:
        """Check whether the given hour falls in the night window."""
        if self._night_start > self._night_end:
            # e.g. 23-07: night spans midnight
            return hour_of_day >= self._night_start or hour_of_day < self._night_end
        # e.g. 0-6: night is a single contiguous range
        return self._night_start <= hour_of_day < self._night_end

    def get_delivery_mode(
        self,
        priority_level: str,
        hour_of_day: int,
    ) -> DeliveryDecision:
        """Determine how to deliver a notification.

        Args:
            priority_level: P0-P3 from PriorityScore.
            hour_of_day: 0-23, user's local hour.

        Returns:
            Frozen DeliveryDecision.
        """
        night = self.is_night(hour_of_day)

        # P0: always immediate, even at night
        if priority_level == "P0":
            return DeliveryDecision(mode="immediate", reason="P0 urgent")

        if night:
            # During night hours only P0 gets through immediately
            if priority_level == "P1":
                return DeliveryDecision(
                    mode="badge_only",
                    reason="P1 during night hours",
                )
            return DeliveryDecision(
                mode="queue_for_later",
                reason=f"{priority_level} during night hours",
            )

        # Daytime delivery
        if priority_level == "P1":
            return DeliveryDecision(mode="immediate", reason="P1 important")
        if priority_level == "P2":
            return DeliveryDecision(mode="badge_only", reason="P2 moderate")

        # P3 and anything else
        return DeliveryDecision(mode="queue_for_later", reason="P3 low priority")
