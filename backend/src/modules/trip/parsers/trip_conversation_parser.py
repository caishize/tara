"""
Travel conversation parser.
Extracts travel-related information from natural language input.
"""
from typing import Optional, Dict, List, Any
from datetime import date, datetime, timedelta
from uuid import UUID
import re

from ....core.utils.timezone import local_now, local_today


class TripConversationParser:
    """
    Parser for extracting travel planning information from conversation.

    Extracts:
    - Destination
    - Dates (start_date, end_date, duration)
    - Budget
    - Participants
    - Travel preferences
    """

    def __init__(self):
        # Common date patterns
        self.date_patterns = {
            "国庆": self._get_national_day,
            "春节": self._get_spring_festival,
            "清明": self._get_qingming,
            "五一": self._get_labor_day,
            "端午": self._get_dragon_boat,
            "中秋": self._get_mid_autumn,
        }

    def parse_travel_request(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse travel request from natural language.

        Args:
            text: User input text
            context: Optional context (family_id, user_id, etc.)

        Returns:
            Dictionary with extracted information:
            {
                "destination": str,
                "start_date": date,
                "end_date": date,
                "duration_days": int,
                "budget": float,
                "participants": List[UUID],
                "preferences": Dict,
                "confidence": float
            }
        """
        result = {
            "destination": self._extract_destination(text),
            "start_date": None,
            "end_date": None,
            "duration_days": self._extract_duration(text),
            "budget": self._extract_budget(text),
            "participants": [],
            "preferences": self._extract_preferences(text),
            "confidence": 0.0
        }

        # Extract dates
        dates = self._extract_dates(text)
        if dates:
            result["start_date"] = dates.get("start_date")
            result["end_date"] = dates.get("end_date")

        # Calculate missing date components
        if result["start_date"] and result["duration_days"] and not result["end_date"]:
            result["end_date"] = result["start_date"] + timedelta(days=result["duration_days"] - 1)
        elif result["start_date"] and result["end_date"] and not result["duration_days"]:
            result["duration_days"] = (result["end_date"] - result["start_date"]).days + 1

        # Calculate confidence
        result["confidence"] = self._calculate_confidence(result)

        return result

    def _extract_destination(self, text: str) -> Optional[str]:
        """Extract destination from text."""
        # Pattern: 去XXX, 到XXX, 想去XXX
        patterns = [
            r"去([^，。！？\s]{2,10})",
            r"到([^，。！？\s]{2,10})",
            r"想去([^，。！？\s]{2,10})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                destination = match.group(1)
                # Filter out common non-destination words
                if destination not in ["旅行", "玩", "游玩", "度假", "哪", "哪里", "哪儿"]:
                    return destination

        return None

    def _extract_dates(self, text: str) -> Dict[str, Optional[date]]:
        """Extract start and end dates from text."""
        result = {"start_date": None, "end_date": None}

        # Check for holiday keywords
        for holiday, date_func in self.date_patterns.items():
            if holiday in text:
                result["start_date"] = date_func()
                return result

        # Pattern: YYYY-MM-DD, MM月DD日
        date_pattern = r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})[日]?"
        matches = re.findall(date_pattern, text)
        if matches:
            try:
                year, month, day = map(int, matches[0])
                result["start_date"] = date(year, month, day)
            except ValueError:
                pass

        # Pattern: MM月DD日 (current year assumed)
        month_day_pattern = r"(\d{1,2})月(\d{1,2})日"
        matches = re.findall(month_day_pattern, text)
        if matches and not result["start_date"]:
            try:
                month, day = map(int, matches[0])
                current_year = local_now().year
                result["start_date"] = date(current_year, month, day)
            except ValueError:
                pass

        return result

    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract trip duration in days."""
        # Pattern: X天, X天Y夜
        patterns = [
            r"(\d+)天(\d+)夜",
            r"(\d+)天",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

        return None

    def _extract_budget(self, text: str) -> Optional[float]:
        """Extract budget from text."""
        # Pattern: XXX元, 预算XXX
        patterns = [
            r"预算[\s]*(\d+(?:\.\d+)?)[元万]?",
            r"(\d+(?:\.\d+)?)[元万]?[\s]*预算",
            r"(\d+(?:\.\d+)?)[元]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                amount = float(match.group(1))
                # Check if it's in 万 (ten thousands)
                if "万" in match.group(0):
                    amount *= 10000
                return amount

        return None

    def _extract_preferences(self, text: str) -> Dict[str, Any]:
        """Extract travel preferences from text."""
        preferences = {
            "trip_type": None,
            "pace": None,
            "focus": []
        }

        # Trip type
        if any(keyword in text for keyword in ["亲子", "孩子", "小朋友"]):
            preferences["trip_type"] = "family"
        elif any(keyword in text for keyword in ["商务", "出差", "会议"]):
            preferences["trip_type"] = "business"
        elif any(keyword in text for keyword in ["探亲", "看望", "回家"]):
            preferences["trip_type"] = "visit"
        else:
            preferences["trip_type"] = "leisure"

        # Pace
        if any(keyword in text for keyword in ["放松", "休闲", "慢节奏", "悠闲"]):
            preferences["pace"] = "relaxed"
        elif any(keyword in text for keyword in ["紧凑", "充实", "赶时间"]):
            preferences["pace"] = "packed"

        # Focus areas
        if any(keyword in text for keyword in ["景点", "名胜", "古迹", "风景"]):
            preferences["focus"].append("sightseeing")
        if any(keyword in text for keyword in ["美食", "小吃", "餐厅", "吃"]):
            preferences["focus"].append("food")
        if any(keyword in text for keyword in ["购物", "商场", "买"]):
            preferences["focus"].append("shopping")
        if any(keyword in text for keyword in ["文化", "博物馆", "历史"]):
            preferences["focus"].append("culture")

        return preferences

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score for parsed result."""
        score = 0.0
        weights = {
            "destination": 0.4,
            "start_date": 0.2,
            "duration_days": 0.2,
            "budget": 0.1,
            "preferences": 0.1
        }

        if result["destination"]:
            score += weights["destination"]
        if result["start_date"]:
            score += weights["start_date"]
        if result["duration_days"]:
            score += weights["duration_days"]
        if result["budget"]:
            score += weights["budget"]
        if result["preferences"].get("trip_type"):
            score += weights["preferences"]

        return score

    # Helper methods for holiday dates
    def _get_national_day(self) -> date:
        """Get National Day (Oct 1)."""
        current_year = local_now().year
        national_day = date(current_year, 10, 1)
        if national_day < date.today():
            national_day = date(current_year + 1, 10, 1)
        return national_day

    def _get_spring_festival(self) -> date:
        """Get Spring Festival (approximate)."""
        # Spring Festival is lunar-based, this is a placeholder
        current_year = local_now().year
        return date(current_year + 1, 2, 1)

    def _get_qingming(self) -> date:
        """Get Qingming Festival (April 4-6)."""
        current_year = local_now().year
        qingming = date(current_year, 4, 5)
        if qingming < date.today():
            qingming = date(current_year + 1, 4, 5)
        return qingming

    def _get_labor_day(self) -> date:
        """Get Labor Day (May 1)."""
        current_year = local_now().year
        labor_day = date(current_year, 5, 1)
        if labor_day < date.today():
            labor_day = date(current_year + 1, 5, 1)
        return labor_day

    def _get_dragon_boat(self) -> date:
        """Get Dragon Boat Festival (approximate)."""
        current_year = local_now().year
        return date(current_year, 6, 10)

    def _get_mid_autumn(self) -> date:
        """Get Mid-Autumn Festival (approximate)."""
        current_year = local_now().year
        return date(current_year, 9, 15)
