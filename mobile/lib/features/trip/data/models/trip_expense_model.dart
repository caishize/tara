import '../../../../core/utils/timezone_utils.dart';

import '../../domain/entities/trip_expense.dart';

class TripExpenseModel extends TripExpense {
  const TripExpenseModel({
    required super.id,
    required super.tripId,
    required super.category,
    required super.amount,
    required super.expenseDate,
    super.description,
    super.location,
    super.paymentMethod,
    super.receiptUrl,
    super.itineraryItemId,
    required super.createdAt,
    required super.updatedAt,
  });

  factory TripExpenseModel.fromJson(Map<String, dynamic> json) {
    return TripExpenseModel(
      id: json['expense_id']?.toString() ?? json['id']?.toString() ?? '',
      tripId: json['trip_id']?.toString() ?? '',
      category: _parseCategory(json['category']),
      amount: _parseDouble(json['amount']) ?? 0,
      expenseDate: TimezoneUtils.parseApiTime(json['expense_date']),
      description: json['description'],
      location: json['location'],
      paymentMethod: json['payment_method'],
      receiptUrl: json['receipt_url'],
      itineraryItemId: json['itinerary_item_id']?.toString(),
      createdAt: json['created_at'] != null
          ? TimezoneUtils.parseApiTime(json['created_at'])
          : DateTime.now().toUtc(),
      updatedAt: json['updated_at'] != null
          ? TimezoneUtils.parseApiTime(json['updated_at'])
          : DateTime.now().toUtc(),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'expense_id': id,
      'trip_id': tripId,
      'category': category.name,
      'amount': amount,
      'expense_date': TimezoneUtils.formatDateForApi(expenseDate),
      'description': description,
      'location': location,
      'payment_method': paymentMethod,
      'receipt_url': receiptUrl,
      'itinerary_item_id': itineraryItemId,
    };
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'category': category.name,
      'amount': amount,
      'expense_date': TimezoneUtils.formatDateForApi(expenseDate),
      'description': description,
      'location': location,
      'payment_method': paymentMethod,
    };
  }

  static ExpenseCategory _parseCategory(String? category) {
    if (category == null) return ExpenseCategory.other;
    return ExpenseCategory.values.firstWhere(
      (c) => c.name.toLowerCase() == category.toLowerCase(),
      orElse: () => ExpenseCategory.other,
    );
  }

  static TripExpenseModel fromEntity(TripExpense expense) {
    return TripExpenseModel(
      id: expense.id,
      tripId: expense.tripId,
      category: expense.category,
      amount: expense.amount,
      expenseDate: expense.expenseDate,
      description: expense.description,
      location: expense.location,
      paymentMethod: expense.paymentMethod,
      receiptUrl: expense.receiptUrl,
      itineraryItemId: expense.itineraryItemId,
      createdAt: expense.createdAt,
      updatedAt: expense.updatedAt,
    );
  }
}

class BudgetStatusModel extends BudgetStatus {
  const BudgetStatusModel({
    required super.tripId,
    required super.totalBudget,
    required super.totalSpent,
    required super.categoryBreakdown,
    required super.isOverBudget,
    required super.remainingBudget,
    required super.usagePercentage,
  });

  factory BudgetStatusModel.fromJson(Map<String, dynamic> json) {
    final Map<ExpenseCategory, double> breakdown = {};
    if (json['category_breakdown'] != null) {
      (json['category_breakdown'] as Map<String, dynamic>).forEach((key, value) {
        final category = ExpenseCategory.values.firstWhere(
          (c) => c.name.toLowerCase() == key.toLowerCase(),
          orElse: () => ExpenseCategory.other,
        );
        // Handle both direct number values and Map objects with 'spent' field
        if (value is Map<String, dynamic>) {
          breakdown[category] = _parseDouble(value['spent']);
        } else {
          breakdown[category] = _parseDouble(value);
        }
      });
    }

    return BudgetStatusModel(
      tripId: json['trip_id']?.toString() ?? '',
      totalBudget: _parseDouble(json['total_budget']),
      totalSpent: _parseDouble(json['total_spent']),
      categoryBreakdown: breakdown,
      isOverBudget: json['is_over_budget'] ?? false,
      remainingBudget: _parseDouble(json['remaining_budget']),
      usagePercentage: _parseDouble(json['usage_percentage'] ?? json['budget_used_percentage']),
    );
  }

  /// Helper to parse various numeric formats (String, int, double) to double
  static double _parseDouble(dynamic value) {
    if (value == null) return 0.0;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value) ?? 0.0;
    return 0.0;
  }
}
