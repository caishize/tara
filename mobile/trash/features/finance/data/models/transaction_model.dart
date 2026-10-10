import '../../domain/entities/transaction.dart';

class TransactionModel extends Transaction {
  const TransactionModel({
    required super.id,
    required super.type,
    required super.category,
    required super.amount,
    super.description,
    required super.date,
    super.memberId,
    super.memberName,
    super.paymentMethod,
    super.merchant,
    super.attachment,
    required super.createdAt,
  });

  factory TransactionModel.fromJson(Map<String, dynamic> json) {
    return TransactionModel(
      id: json['id']?.toString() ?? '',
      type: _parseType(json['type'] ?? json['transaction_type']),
      category: _parseCategory(json['category']),
      amount: _parseDouble(json['amount']) ?? 0,
      description: json['description'],
      date: DateTime.parse(json['date'] ?? json['transaction_date']),
      memberId: json['member_id']?.toString(),
      memberName: json['member_name'],
      paymentMethod: _parsePaymentMethod(json['payment_method']),
      merchant: json['merchant'],
      attachment: json['attachment'],
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
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
      'id': id,
      'type': type.name,
      'category': category.name,
      'amount': amount,
      'description': description,
      'date': date.toIso8601String().split('T')[0],
      'member_id': memberId,
      'payment_method': paymentMethod?.name,
      'merchant': merchant,
      'attachment': attachment,
    };
  }

  Map<String, dynamic> toCreateJson() {
    return {
      'transaction_type': type.name,
      'category': category.name,
      'amount': amount,
      'transaction_date': date.toIso8601String().split('T')[0],
      if (description != null) 'description': description,
      if (memberId != null) 'member_id': memberId,
      if (paymentMethod != null) 'payment_method': paymentMethod!.name,
      if (merchant != null) 'merchant': merchant,
    };
  }

  static TransactionType _parseType(String? type) {
    if (type == null) return TransactionType.expense;
    return TransactionType.values.firstWhere(
      (t) => t.name.toLowerCase() == type.toLowerCase(),
      orElse: () => TransactionType.expense,
    );
  }

  static TransactionCategory _parseCategory(String? category) {
    if (category == null) return TransactionCategory.other_expense;
    return TransactionCategory.values.firstWhere(
      (c) => c.name.toLowerCase() == category.toLowerCase(),
      orElse: () => TransactionCategory.other_expense,
    );
  }

  static PaymentMethod? _parsePaymentMethod(String? method) {
    if (method == null) return null;
    return PaymentMethod.values.firstWhere(
      (p) => p.name.toLowerCase() == method.toLowerCase(),
      orElse: () => PaymentMethod.other,
    );
  }

  static TransactionModel fromEntity(Transaction entity) {
    return TransactionModel(
      id: entity.id,
      type: entity.type,
      category: entity.category,
      amount: entity.amount,
      description: entity.description,
      date: entity.date,
      memberId: entity.memberId,
      memberName: entity.memberName,
      paymentMethod: entity.paymentMethod,
      merchant: entity.merchant,
      attachment: entity.attachment,
      createdAt: entity.createdAt,
    );
  }
}

class FinanceSummaryModel extends FinanceSummary {
  const FinanceSummaryModel({
    required super.totalIncome,
    required super.totalExpense,
    required super.balance,
    required super.categoryBreakdown,
    required super.periodStart,
    required super.periodEnd,
  });

  factory FinanceSummaryModel.fromJson(Map<String, dynamic> json) {
    final breakdown = <TransactionCategory, double>{};
    if (json['category_breakdown'] != null) {
      (json['category_breakdown'] as Map<String, dynamic>).forEach((key, value) {
        final category = TransactionCategory.values.firstWhere(
          (c) => c.name.toLowerCase() == key.toLowerCase(),
          orElse: () => TransactionCategory.other_expense,
        );
        breakdown[category] = _parseDouble(value) ?? 0;
      });
    }

    return FinanceSummaryModel(
      totalIncome: _parseDouble(json['total_income']) ?? 0,
      totalExpense: _parseDouble(json['total_expense']) ?? 0,
      balance: _parseDouble(json['balance']) ?? 0,
      categoryBreakdown: breakdown,
      periodStart: DateTime.parse(json['period_start']),
      periodEnd: DateTime.parse(json['period_end']),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }
}
