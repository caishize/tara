import 'package:flutter/material.dart';
import '../../domain/entities/trip_expense.dart';

class BudgetOverviewCard extends StatelessWidget {
  final BudgetStatus budgetStatus;

  const BudgetOverviewCard({super.key, required this.budgetStatus});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOverBudget = budgetStatus.isOverBudget;
    final percentage = budgetStatus.usagePercentage;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  '预算概览',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: isOverBudget
                        ? Colors.red.withValues(alpha: 0.1)
                        : percentage > 80
                            ? Colors.orange.withValues(alpha: 0.1)
                            : Colors.green.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    isOverBudget
                        ? '超支'
                        : percentage > 80
                            ? '接近预算'
                            : '正常',
                    style: TextStyle(
                      color: isOverBudget
                          ? Colors.red
                          : percentage > 80
                              ? Colors.orange
                              : Colors.green,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Main budget display
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '已花费',
                      style: TextStyle(
                        color: Colors.grey[600],
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '¥${budgetStatus.totalSpent.toStringAsFixed(0)}',
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      isOverBudget ? '超支' : '剩余',
                      style: TextStyle(
                        color: Colors.grey[600],
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '¥${budgetStatus.remainingBudget.abs().toStringAsFixed(0)}',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: isOverBudget ? Colors.red : Colors.green,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (percentage / 100).clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  isOverBudget
                      ? Colors.red
                      : percentage > 80
                          ? Colors.orange
                          : theme.colorScheme.primary,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '预算 ¥${budgetStatus.totalBudget.toStringAsFixed(0)} · ${percentage.toStringAsFixed(0)}% 已使用',
              style: TextStyle(
                color: Colors.grey[600],
                fontSize: 12,
              ),
            ),
            // Category breakdown
            if (budgetStatus.categoryBreakdown.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text(
                '分类支出',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 12),
              ...budgetStatus.categoryBreakdown.entries.map(
                (entry) => _buildCategoryRow(
                  context,
                  entry.key,
                  entry.value,
                  budgetStatus.totalSpent,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryRow(
    BuildContext context,
    ExpenseCategory category,
    double amount,
    double total,
  ) {
    final percentage = total > 0 ? (amount / total * 100) : 0.0;
    final icon = _getCategoryIcon(category);
    final name = _getCategoryName(category);
    final color = Color(_getCategoryColor(category));

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 24,
            child: Text(icon),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 60,
            child: Text(
              name,
              style: TextStyle(
                color: Colors.grey[700],
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: percentage / 100,
                minHeight: 4,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 80,
            child: Text(
              '¥${amount.toStringAsFixed(0)}',
              textAlign: TextAlign.right,
              style: const TextStyle(
                fontWeight: FontWeight.w500,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _getCategoryIcon(ExpenseCategory category) {
    switch (category) {
      case ExpenseCategory.transportation:
        return '🚗';
      case ExpenseCategory.accommodation:
        return '🏨';
      case ExpenseCategory.tickets:
        return '🎟️';
      case ExpenseCategory.food:
        return '🍽️';
      case ExpenseCategory.shopping:
        return '🛍️';
      case ExpenseCategory.other:
        return '💰';
    }
  }

  String _getCategoryName(ExpenseCategory category) {
    switch (category) {
      case ExpenseCategory.transportation:
        return '交通';
      case ExpenseCategory.accommodation:
        return '住宿';
      case ExpenseCategory.tickets:
        return '门票';
      case ExpenseCategory.food:
        return '餐饮';
      case ExpenseCategory.shopping:
        return '购物';
      case ExpenseCategory.other:
        return '其他';
    }
  }

  int _getCategoryColor(ExpenseCategory category) {
    switch (category) {
      case ExpenseCategory.transportation:
        return 0xFF42A5F5;
      case ExpenseCategory.accommodation:
        return 0xFF7E57C2;
      case ExpenseCategory.tickets:
        return 0xFFFF7043;
      case ExpenseCategory.food:
        return 0xFF66BB6A;
      case ExpenseCategory.shopping:
        return 0xFFEC407A;
      case ExpenseCategory.other:
        return 0xFF78909C;
    }
  }
}
