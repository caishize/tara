import 'package:equatable/equatable.dart';

enum TransactionType {
  income,    // 收入
  expense,   // 支出
}

enum TransactionCategory {
  // 收入类别
  salary,        // 工资
  bonus,         // 奖金
  investment,    // 投资收益
  transfer,      // 转账收入
  other_income,  // 其他收入

  // 支出类别
  food,          // 餐饮
  transport,     // 交通
  shopping,      // 购物
  entertainment, // 娱乐
  housing,       // 住房
  utilities,     // 水电燃气
  medical,       // 医疗
  education,     // 教育
  travel,        // 旅行
  childcare,     // 育儿
  gift,          // 礼物
  other_expense, // 其他支出
}

enum PaymentMethod {
  cash,     // 现金
  card,     // 银行卡
  wechat,   // 微信支付
  alipay,   // 支付宝
  transfer, // 转账
  other,    // 其他
}

class Transaction extends Equatable {
  final String id;
  final TransactionType type;
  final TransactionCategory category;
  final double amount;
  final String? description;
  final DateTime date;
  final String? memberId;
  final String? memberName;
  final PaymentMethod? paymentMethod;
  final String? merchant;
  final String? attachment;
  final DateTime createdAt;

  const Transaction({
    required this.id,
    required this.type,
    required this.category,
    required this.amount,
    this.description,
    required this.date,
    this.memberId,
    this.memberName,
    this.paymentMethod,
    this.merchant,
    this.attachment,
    required this.createdAt,
  });

  bool get isIncome => type == TransactionType.income;
  bool get isExpense => type == TransactionType.expense;

  String get categoryName {
    switch (category) {
      case TransactionCategory.salary:
        return '工资';
      case TransactionCategory.bonus:
        return '奖金';
      case TransactionCategory.investment:
        return '投资收益';
      case TransactionCategory.transfer:
        return '转账收入';
      case TransactionCategory.other_income:
        return '其他收入';
      case TransactionCategory.food:
        return '餐饮';
      case TransactionCategory.transport:
        return '交通';
      case TransactionCategory.shopping:
        return '购物';
      case TransactionCategory.entertainment:
        return '娱乐';
      case TransactionCategory.housing:
        return '住房';
      case TransactionCategory.utilities:
        return '水电燃气';
      case TransactionCategory.medical:
        return '医疗';
      case TransactionCategory.education:
        return '教育';
      case TransactionCategory.travel:
        return '旅行';
      case TransactionCategory.childcare:
        return '育儿';
      case TransactionCategory.gift:
        return '礼物';
      case TransactionCategory.other_expense:
        return '其他支出';
    }
  }

  String get categoryIcon {
    switch (category) {
      case TransactionCategory.salary:
        return '💰';
      case TransactionCategory.bonus:
        return '🎁';
      case TransactionCategory.investment:
        return '📈';
      case TransactionCategory.transfer:
        return '💳';
      case TransactionCategory.other_income:
        return '💵';
      case TransactionCategory.food:
        return '🍔';
      case TransactionCategory.transport:
        return '🚗';
      case TransactionCategory.shopping:
        return '🛒';
      case TransactionCategory.entertainment:
        return '🎬';
      case TransactionCategory.housing:
        return '🏠';
      case TransactionCategory.utilities:
        return '💡';
      case TransactionCategory.medical:
        return '🏥';
      case TransactionCategory.education:
        return '📚';
      case TransactionCategory.travel:
        return '✈️';
      case TransactionCategory.childcare:
        return '👶';
      case TransactionCategory.gift:
        return '🎀';
      case TransactionCategory.other_expense:
        return '📝';
    }
  }

  String? get paymentMethodName {
    if (paymentMethod == null) return null;
    switch (paymentMethod!) {
      case PaymentMethod.cash:
        return '现金';
      case PaymentMethod.card:
        return '银行卡';
      case PaymentMethod.wechat:
        return '微信支付';
      case PaymentMethod.alipay:
        return '支付宝';
      case PaymentMethod.transfer:
        return '转账';
      case PaymentMethod.other:
        return '其他';
    }
  }

  Transaction copyWith({
    String? id,
    TransactionType? type,
    TransactionCategory? category,
    double? amount,
    String? description,
    DateTime? date,
    String? memberId,
    String? memberName,
    PaymentMethod? paymentMethod,
    String? merchant,
    String? attachment,
    DateTime? createdAt,
  }) {
    return Transaction(
      id: id ?? this.id,
      type: type ?? this.type,
      category: category ?? this.category,
      amount: amount ?? this.amount,
      description: description ?? this.description,
      date: date ?? this.date,
      memberId: memberId ?? this.memberId,
      memberName: memberName ?? this.memberName,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      merchant: merchant ?? this.merchant,
      attachment: attachment ?? this.attachment,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
    id, type, category, amount, description, date,
    memberId, memberName, paymentMethod, merchant, attachment, createdAt,
  ];
}

class FinanceSummary extends Equatable {
  final double totalIncome;
  final double totalExpense;
  final double balance;
  final Map<TransactionCategory, double> categoryBreakdown;
  final DateTime periodStart;
  final DateTime periodEnd;

  const FinanceSummary({
    required this.totalIncome,
    required this.totalExpense,
    required this.balance,
    required this.categoryBreakdown,
    required this.periodStart,
    required this.periodEnd,
  });

  double get savingRate {
    if (totalIncome == 0) return 0;
    return (totalIncome - totalExpense) / totalIncome * 100;
  }

  @override
  List<Object?> get props => [
    totalIncome, totalExpense, balance, categoryBreakdown,
    periodStart, periodEnd,
  ];
}
