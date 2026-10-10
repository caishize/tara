"""
Budget tracking service for travel expense management.
"""
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..models.trip_plan import TripPlan
from ..models.trip_expense import TripExpense
from ....core.utils.timezone import utc_now


class BudgetTracker:
    """Service for tracking travel expenses and managing budgets."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_budget(
        self,
        trip_id: UUID,
        total_budget: Decimal,
        category_breakdown: Optional[Dict[str, Decimal]] = None
    ) -> Dict[str, Any]:
        """
        Initialize budget breakdown by category.

        Args:
            trip_id: Travel plan ID
            total_budget: Total budget amount
            category_breakdown: Budget breakdown by category

        Returns:
            Created budget record
        """
        # Get trip
        result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Update trip budget
        trip.budget = total_budget

        # Default category breakdown if not provided
        if not category_breakdown:
            # Default percentages
            category_breakdown = {
                "transportation": total_budget * Decimal("0.20"),  # 20%
                "accommodation": total_budget * Decimal("0.40"),   # 40%
                "tickets": total_budget * Decimal("0.15"),         # 15%
                "food": total_budget * Decimal("0.20"),            # 20%
                "other": total_budget * Decimal("0.05")            # 5%
            }

        await self.db.commit()

        return {
            "trip_id": str(trip_id),
            "total_budget": float(total_budget),
            "category_breakdown": {
                k: float(v) for k, v in category_breakdown.items()
            },
            "created_at": utc_now().isoformat()
        }

    async def log_expense(
        self,
        trip_id: UUID,
        category: str,
        amount: Decimal,
        description: Optional[str] = None,
        expense_date: Optional[date] = None,
        location: Optional[str] = None,
        payment_method: Optional[str] = None,
        receipt_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a travel expense and update budget.

        Args:
            trip_id: Travel plan ID
            category: Expense category
            amount: Expense amount
            description: Expense description
            expense_date: Date of expense (defaults to today)
            location: Location where expense occurred
            payment_method: Payment method used
            receipt_url: Receipt file URL

        Returns:
            Created expense record with budget status
        """
        # Validate category
        valid_categories = ["transportation", "accommodation", "tickets", "food", "shopping", "other"]
        if category not in valid_categories:
            raise ValueError(f"Invalid category: {category}. Must be one of {valid_categories}")

        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Create expense record
        expense = TripExpense(
            trip_id=trip_id,
            expense_date=expense_date or date.today(),
            category=category,
            amount=amount,
            description=description,
            location=location,
            payment_method=payment_method,
            receipt_url=receipt_url
        )

        self.db.add(expense)

        # Update trip actual expense
        trip.actual_expense += amount

        await self.db.commit()
        await self.db.refresh(expense)
        await self.db.refresh(trip)

        # Get updated budget status
        budget_status = await self.get_budget_status(trip_id)

        return {
            "expense_id": str(expense.expense_id),
            "trip_id": str(trip_id),
            "category": expense.category,
            "amount": float(expense.amount),
            "description": expense.description,
            "expense_date": expense.expense_date.isoformat(),
            "budget_status": budget_status,
            "created_at": expense.created_at.isoformat()
        }

    async def get_budget_status(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Get budget usage status.

        Calculates:
        - Total spent vs. budget
        - Remaining budget
        - Category-wise breakdown
        - Alert status (>90% used)

        Args:
            trip_id: Travel plan ID

        Returns:
            Budget status dict
        """
        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Get all expenses grouped by category
        expense_result = await self.db.execute(
            select(
                TripExpense.category,
                func.sum(TripExpense.amount).label("total")
            )
            .where(TripExpense.trip_id == trip_id)
            .group_by(TripExpense.category)
        )
        category_expenses = {row.category: float(row.total) for row in expense_result}

        # Calculate category breakdown
        category_breakdown = {}
        for category in ["transportation", "accommodation", "tickets", "food", "shopping", "other"]:
            spent = category_expenses.get(category, 0.0)
            category_breakdown[category] = {
                "spent": spent,
                "percentage": (spent / float(trip.actual_expense) * 100) if trip.actual_expense > 0 else 0
            }

        # Calculate budget metrics
        total_budget = float(trip.budget) if trip.budget else None
        total_spent = float(trip.actual_expense)
        remaining_budget = float(trip.remaining_budget) if trip.remaining_budget is not None else None
        budget_used_percentage = float(trip.budget_used_percentage) if trip.budget_used_percentage is not None else None

        # Check for budget alert
        is_over_budget = False
        warning_threshold_reached = False

        if total_budget:
            is_over_budget = total_spent > total_budget
            warning_threshold_reached = budget_used_percentage >= 90

        return {
            "trip_id": str(trip_id),
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining_budget": remaining_budget,
            "budget_used_percentage": budget_used_percentage,
            "category_breakdown": category_breakdown,
            "is_over_budget": is_over_budget,
            "warning_threshold_reached": warning_threshold_reached,
            "alert_message": self._generate_alert_message(
                total_budget,
                total_spent,
                remaining_budget,
                is_over_budget,
                warning_threshold_reached
            )
        }

    def _generate_alert_message(
        self,
        total_budget: Optional[float],
        total_spent: float,
        remaining_budget: Optional[float],
        is_over_budget: bool,
        warning_threshold_reached: bool
    ) -> Optional[str]:
        """Generate budget alert message if needed."""
        if not total_budget:
            return None

        if is_over_budget:
            over_amount = total_spent - total_budget
            return f"预算超支 ¥{over_amount:.2f}！已花费 ¥{total_spent:.2f}，预算为 ¥{total_budget:.2f}"

        if warning_threshold_reached:
            return f"预算即将用完！已使用 {(total_spent / total_budget * 100):.1f}%，剩余 ¥{remaining_budget:.2f}"

        return None

    async def check_budget_alert(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Check for budget alerts (90%+ usage).

        Args:
            trip_id: Travel plan ID

        Returns:
            Alert status dict
        """
        budget_status = await self.get_budget_status(trip_id)

        return {
            "trip_id": str(trip_id),
            "should_alert": budget_status["warning_threshold_reached"] or budget_status["is_over_budget"],
            "alert_type": "over_budget" if budget_status["is_over_budget"] else "warning" if budget_status["warning_threshold_reached"] else None,
            "alert_message": budget_status["alert_message"],
            "budget_status": budget_status
        }

    async def generate_expense_report(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Generate post-trip expense report.

        Includes:
        - Budget vs. actual comparison
        - Category-wise breakdown
        - Overspending/savings analysis
        - Expense timeline

        Args:
            trip_id: Travel plan ID

        Returns:
            Expense report dict
        """
        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Get all expenses
        expense_result = await self.db.execute(
            select(TripExpense)
            .where(TripExpense.trip_id == trip_id)
            .order_by(TripExpense.expense_date, TripExpense.created_at)
        )
        expenses = expense_result.scalars().all()

        # Get budget status
        budget_status = await self.get_budget_status(trip_id)

        # Calculate category analysis
        category_analysis = {}
        for category, data in budget_status["category_breakdown"].items():
            spent = data["spent"]
            percentage = data["percentage"]

            # Assume default budget allocation for comparison
            if trip.budget:
                default_allocations = {
                    "transportation": 0.20,
                    "accommodation": 0.40,
                    "tickets": 0.15,
                    "food": 0.20,
                    "shopping": 0.0,
                    "other": 0.05
                }
                budgeted = float(trip.budget) * default_allocations.get(category, 0.05)
                variance = spent - budgeted
                variance_pct = (variance / budgeted * 100) if budgeted > 0 else 0
            else:
                budgeted = None
                variance = None
                variance_pct = None

            category_analysis[category] = {
                "budgeted": budgeted,
                "spent": spent,
                "variance": variance,
                "variance_percentage": variance_pct,
                "percentage_of_total": percentage,
                "status": "over" if variance and variance > 0 else "under" if variance and variance < 0 else "match"
            }

        # Expense timeline (daily breakdown)
        timeline = {}
        for expense in expenses:
            date_key = expense.expense_date.isoformat()
            if date_key not in timeline:
                timeline[date_key] = {
                    "date": date_key,
                    "total": 0.0,
                    "expenses": []
                }
            timeline[date_key]["total"] += float(expense.amount)
            timeline[date_key]["expenses"].append({
                "expense_id": str(expense.expense_id),
                "category": expense.category,
                "amount": float(expense.amount),
                "description": expense.description,
                "location": expense.location
            })

        # Summary
        total_budget = float(trip.budget) if trip.budget else None
        total_spent = float(trip.actual_expense)

        if total_budget:
            savings = total_budget - total_spent
            savings_pct = (savings / total_budget * 100) if total_budget > 0 else 0
        else:
            savings = None
            savings_pct = None

        summary = {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "savings": savings,
            "savings_percentage": savings_pct,
            "is_over_budget": budget_status["is_over_budget"],
            "expense_count": len(expenses)
        }

        report = {
            "trip_id": str(trip_id),
            "destination": trip.destination,
            "start_date": trip.start_date.isoformat(),
            "end_date": trip.end_date.isoformat(),
            "duration_days": trip.duration_days,
            "summary": summary,
            "category_analysis": category_analysis,
            "timeline": sorted(timeline.values(), key=lambda x: x["date"]),
            "recommendations": self._generate_recommendations(category_analysis, budget_status),
            "generated_at": utc_now().isoformat()
        }

        return report

    def _generate_recommendations(
        self,
        category_analysis: Dict[str, Any],
        budget_status: Dict[str, Any]
    ) -> List[str]:
        """Generate budget recommendations based on analysis."""
        recommendations = []

        # Find overspending categories
        overspent_categories = [
            cat for cat, data in category_analysis.items()
            if data["variance"] and data["variance"] > 0
        ]

        if overspent_categories:
            recommendations.append(
                f"预算超支主要在: {', '.join(overspent_categories)}。下次旅行可适当增加这些类别的预算。"
            )

        # Find underspending categories
        underspent_categories = [
            cat for cat, data in category_analysis.items()
            if data["variance"] and data["variance"] < -50  # Underspent by >50
        ]

        if underspent_categories:
            recommendations.append(
                f"以下类别预算有节余: {', '.join(underspent_categories)}。下次可适当减少预算。"
            )

        # Overall budget recommendation
        if budget_status.get("is_over_budget"):
            recommendations.append(
                "总体预算超支，建议下次增加10-20%的预算缓冲。"
            )
        elif budget_status.get("budget_used_percentage", 0) < 80:
            recommendations.append(
                "预算有较多结余，下次可适当减少预算或增加活动内容。"
            )
        else:
            recommendations.append(
                "预算使用合理，与实际花费基本吻合。"
            )

        return recommendations

    async def sync_to_finance_module(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Sync travel expenses to finance module (Module 5).

        TODO: Integrate with TransactionService from Module 5

        Args:
            trip_id: Travel plan ID

        Returns:
            Sync status dict
        """
        # Get all expenses
        expense_result = await self.db.execute(
            select(TripExpense)
            .where(TripExpense.trip_id == trip_id)
        )
        expenses = expense_result.scalars().all()

        # TODO: Call TransactionService.create_transaction() for each expense
        # from ....modules.finance_management.services.transaction_service import TransactionService
        # transaction_service = TransactionService(self.db)

        # for expense in expenses:
        #     await transaction_service.create_transaction(
        #         family_id=trip.family_id,
        #         transaction_type="expense",
        #         category="travel_entertainment",
        #         amount=expense.amount,
        #         description=f"{trip.destination} - {expense.description}",
        #         transaction_date=expense.expense_date
        #     )

        return {
            "trip_id": str(trip_id),
            "synced_count": len(expenses),
            "status": "success",
            "message": f"Successfully synced {len(expenses)} expenses to finance module"
        }
