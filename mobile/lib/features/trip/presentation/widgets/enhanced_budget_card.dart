import 'package:flutter/material.dart';
import '../../domain/entities/trip_expense.dart';

class EnhancedBudgetCard extends StatelessWidget {
  final BudgetStatus budgetStatus;
  final VoidCallback? onTap;

  const EnhancedBudgetCard({
    super.key,
    required this.budgetStatus,
    this.onTap,
  });

  Color _getProgressColor(double percentage) {
    if (percentage < 70) return Colors.green;
    if (percentage < 90) return Colors.orange;
    return Colors.red;
  }

  String _getStatusText(double percentage) {
    if (percentage < 70) return '预算充裕';
    if (percentage < 90) return '预算紧张';
    return '预算超支';
  }

  @override
  Widget build(BuildContext context) {
    final percentage = budgetStatus.usagePercentage;
    final progressColor = _getProgressColor(percentage);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          children: [
            // Warning banner (show when usage >= 80%)
            if (budgetStatus.usagePercentage >= 80)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.orange[50],
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                  border: Border(
                    left: BorderSide(color: Colors.orange[400]!, width: 4),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber_rounded, color: Colors.orange[700], size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '预算即将用完，请注意控制支出',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.orange[800],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header with status
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        '预算概况',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: progressColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _getStatusText(percentage),
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: progressColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Main budget display
                  Row(
                    children: [
                      Expanded(
                        child: _buildBudgetItem(
                          label: '已花费',
                          amount: budgetStatus.totalSpent,
                          color: Colors.orange[700]!,
                          icon: Icons.shopping_cart_outlined,
                        ),
                      ),
                      Container(
                        height: 40,
                        width: 1,
                        color: Colors.grey[200],
                      ),
                      Expanded(
                        child: _buildBudgetItem(
                          label: '剩余预算',
                          amount: budgetStatus.remainingBudget,
                          color: budgetStatus.isOverBudget ? Colors.red : Colors.green[700]!,
                          icon: budgetStatus.isOverBudget
                              ? Icons.warning_outlined
                              : Icons.account_balance_wallet_outlined,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Progress bar
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            '总预算: ¥${budgetStatus.totalBudget.toStringAsFixed(0)}',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                            ),
                          ),
                          Text(
                            '${percentage.toStringAsFixed(1)}%',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: progressColor,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: (percentage / 100).clamp(0.0, 1.0),
                          backgroundColor: Colors.grey[200],
                          valueColor: AlwaysStoppedAnimation<Color>(progressColor),
                          minHeight: 8,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Category breakdown
                  if (budgetStatus.categoryBreakdown.isNotEmpty) ...[
                    Text(
                      '分类支出',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Colors.grey[700],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: budgetStatus.categoryBreakdown.entries.map((entry) {
                        return _buildCategoryChip(entry.key, entry.value);
                      }).toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetItem({
    required String label,
    required double amount,
    required Color color,
    required IconData icon,
  }) {
    return Column(
      children: [
        Icon(icon, color: color, size: 24),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[600],
          ),
        ),
        const SizedBox(height: 2),
        Text(
          '¥${amount.abs().toStringAsFixed(0)}',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildCategoryChip(ExpenseCategory category, double amount) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(_getCategoryIcon(category), style: const TextStyle(fontSize: 14)),
          const SizedBox(width: 4),
          Text(
            '¥${amount.toStringAsFixed(0)}',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
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
}
