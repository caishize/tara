import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/trip.dart';

class TripCard extends StatelessWidget {
  final Trip plan;
  final VoidCallback? onTap;

  const TripCard({
    super.key,
    required this.plan,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MM/dd');
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with destination image placeholder
            Container(
              height: 120,
              width: double.infinity,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: _getGradientColors(plan.category, plan.tripType),
                ),
              ),
              child: Stack(
                children: [
                  // Destination name overlay
                  Positioned(
                    left: 16,
                    bottom: 16,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          plan.destination,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            shadows: [
                              Shadow(
                                offset: Offset(1, 1),
                                blurRadius: 3,
                                color: Colors.black38,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${plan.tripTypeIcon} ${plan.tripTypeName}',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Category badge (top-left)
                  Positioned(
                    left: 12,
                    top: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: _getCategoryColor(plan.category),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _getCategoryIcon(plan.category),
                            color: Colors.white,
                            size: 14,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            plan.categoryName,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  // Status badge (top-right)
                  Positioned(
                    right: 12,
                    top: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Color(plan.statusColorValue),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        plan.statusName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // Content
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Trip name
                  if (plan.tripName != null) ...[
                    Text(
                      plan.tripName!,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  // Date range
                  Row(
                    children: [
                      Icon(
                        Icons.calendar_today,
                        size: 16,
                        color: Colors.grey[600],
                      ),
                      const SizedBox(width: 6),
                      Text(
                        '${dateFormat.format(plan.startDate.toLocal())} - ${dateFormat.format(plan.endDate.toLocal())}',
                        style: TextStyle(
                          color: Colors.grey[700],
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primaryContainer,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          '${plan.durationDays}天',
                          style: TextStyle(
                            color: theme.colorScheme.onPrimaryContainer,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Budget progress
                  if (plan.budget != null) _buildBudgetProgress(context),
                  // Participants
                  if (plan.participants.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Icon(
                          Icons.people,
                          size: 16,
                          color: Colors.grey[600],
                        ),
                        const SizedBox(width: 6),
                        Text(
                          '${plan.participants.length} 人参与',
                          style: TextStyle(
                            color: Colors.grey[700],
                            fontSize: 14,
                          ),
                        ),
                      ],
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

  Widget _buildBudgetProgress(BuildContext context) {
    final percentage = plan.budgetUsedPercentage ?? 0;
    final isOverBudget = plan.isOverBudget;
    final remaining = plan.remainingBudget ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '预算',
              style: TextStyle(
                color: Colors.grey[600],
                fontSize: 12,
              ),
            ),
            Text(
              isOverBudget
                  ? '超支 ¥${(-remaining).toStringAsFixed(0)}'
                  : '剩余 ¥${remaining.toStringAsFixed(0)}',
              style: TextStyle(
                color: isOverBudget ? Colors.red : Colors.green,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: (percentage / 100).clamp(0.0, 1.0),
          backgroundColor: Colors.grey[200],
          valueColor: AlwaysStoppedAnimation<Color>(
            isOverBudget
                ? Colors.red
                : percentage > 80
                    ? Colors.orange
                    : Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '¥${plan.actualExpense.toStringAsFixed(0)} / ¥${plan.budget!.toStringAsFixed(0)}',
          style: TextStyle(
            color: Colors.grey[500],
            fontSize: 11,
          ),
        ),
      ],
    );
  }

  Color _getCategoryColor(TripCategory category) {
    switch (category) {
      case TripCategory.personal:
        return const Color(0xFF4CAF50); // Green
      case TripCategory.business:
        return const Color(0xFF607D8B); // Blue-grey
    }
  }

  IconData _getCategoryIcon(TripCategory category) {
    switch (category) {
      case TripCategory.personal:
        return Icons.person;
      case TripCategory.business:
        return Icons.business_center;
    }
  }

  List<Color> _getGradientColors(TripCategory category, TripType type) {
    // Business trips have more professional colors
    if (category == TripCategory.business) {
      switch (type) {
        case TripType.businessTrip:
          return [const Color(0xFF607D8B), const Color(0xFF455A64)];
        case TripType.conference:
          return [const Color(0xFF5C6BC0), const Color(0xFF3949AB)];
        case TripType.clientVisit:
          return [const Color(0xFF26A69A), const Color(0xFF00897B)];
        default:
          return [const Color(0xFF78909C), const Color(0xFF546E7A)];
      }
    }

    // Personal trips have more vibrant colors
    switch (type) {
      case TripType.leisure:
        return [const Color(0xFF4FC3F7), const Color(0xFF0288D1)];
      case TripType.family:
        return [const Color(0xFF81C784), const Color(0xFF388E3C)];
      case TripType.visit:
        return [const Color(0xFFFFB74D), const Color(0xFFF57C00)];
      default:
        return [const Color(0xFF90A4AE), const Color(0xFF607D8B)];
    }
  }
}
