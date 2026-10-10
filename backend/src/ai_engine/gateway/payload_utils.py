"""
Payload Utilities - Shared helpers for extracting data from action payloads.
"""

from typing import Any, Dict, Optional


def extract_amount(payload: Dict[str, Any]) -> Optional[float]:
    """
    Extract monetary amount from an action payload.

    Checks common field names, then falls back to quantity * price calculation.

    Returns:
        The extracted amount, or None if no amount is found.
    """
    for field in ('amount', 'price', 'total', 'total_price', 'cost'):
        if field in payload:
            try:
                return float(payload[field])
            except (ValueError, TypeError):
                pass

    if 'quantity' in payload and 'price' in payload:
        try:
            return float(payload['quantity']) * float(payload['price'])
        except (ValueError, TypeError):
            pass

    return None
