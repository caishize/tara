import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_list.dart';

/// 购物清单卡片组件
class ShoppingListCard extends StatelessWidget {
  final ShoppingList shoppingList;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;

  const ShoppingListCard({
    super.key,
    required this.shoppingList,
    this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          onLongPress: onLongPress,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                const SizedBox(height: 12),
                _buildProgress(),
                const SizedBox(height: 12),
                _buildFooter(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: _getTypeColor().withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Center(
            child: Text(
              shoppingList.listTypeIcon,
              style: const TextStyle(fontSize: 22),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                shoppingList.listName,
                style: AppTextStyles.headline6,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  _buildStatusBadge(),
                  const SizedBox(width: 8),
                  Text(
                    shoppingList.listTypeName,
                    style: AppTextStyles.caption.copyWith(
                      color: _getTypeColor(),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (shoppingList.isOverdue)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.error.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.warning_amber_rounded, size: 14, color: AppColors.error),
                const SizedBox(width: 4),
                Text(
                  '已逾期',
                  style: AppTextStyles.overline.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildStatusBadge() {
    Color color;
    String label;
    switch (shoppingList.status) {
      case ListStatus.active:
        color = AppColors.info;
        label = '待采购';
        break;
      case ListStatus.inProgress:
        color = AppColors.warning;
        label = '采购中';
        break;
      case ListStatus.completed:
        color = AppColors.success;
        label = '已完成';
        break;
      case ListStatus.archived:
        color = AppColors.textTertiary;
        label = '已归档';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: AppTextStyles.overline.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildProgress() {
    final progress = shoppingList.completionRate;
    final purchasedCount = shoppingList.purchasedItemCount;
    final totalCount = shoppingList.totalItemCount;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '已完成 $purchasedCount / $totalCount 项',
              style: AppTextStyles.caption,
            ),
            Text(
              '${(progress * 100).toInt()}%',
              style: AppTextStyles.caption.copyWith(
                fontWeight: FontWeight.w600,
                color: AppColors.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            backgroundColor: AppColors.divider,
            valueColor: AlwaysStoppedAnimation<Color>(
              progress == 1.0 ? AppColors.success : AppColors.primary,
            ),
            minHeight: 6,
          ),
        ),
      ],
    );
  }

  Widget _buildFooter() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        if (shoppingList.estimatedTotal > 0)
          Row(
            children: [
              const Icon(Icons.attach_money, size: 16, color: AppColors.textTertiary),
              Text(
                '预估 ¥${shoppingList.estimatedTotal.toStringAsFixed(0)}',
                style: AppTextStyles.caption,
              ),
            ],
          )
        else
          const SizedBox.shrink(),
        if (shoppingList.dueDate != null)
          Row(
            children: [
              Icon(
                Icons.schedule,
                size: 14,
                color: shoppingList.isOverdue ? AppColors.error : AppColors.textTertiary,
              ),
              const SizedBox(width: 4),
              Text(
                _formatDueDate(),
                style: AppTextStyles.caption.copyWith(
                  color: shoppingList.isOverdue ? AppColors.error : null,
                ),
              ),
            ],
          ),
      ],
    );
  }

  String _formatDueDate() {
    final daysUntil = shoppingList.daysUntilDue;
    if (daysUntil == null) return '';
    if (daysUntil < 0) return '逾期${-daysUntil}天';
    if (daysUntil == 0) return '今天到期';
    if (daysUntil == 1) return '明天到期';
    if (daysUntil <= 7) return '$daysUntil天后到期';
    return '${shoppingList.dueDate!.month}/${shoppingList.dueDate!.day}到期';
  }

  Color _getTypeColor() {
    switch (shoppingList.listType) {
      case ListType.regular:
        return AppColors.primary;
      case ListType.replenishment:
        return AppColors.secondary;
      case ListType.seasonal:
        return AppColors.accent1;
      case ListType.bulk:
        return AppColors.accent3;
      case ListType.urgent:
        return AppColors.error;
    }
  }
}

/// 紧凑型购物清单卡片
class CompactShoppingListCard extends StatelessWidget {
  final ShoppingList shoppingList;
  final VoidCallback? onTap;

  const CompactShoppingListCard({
    super.key,
    required this.shoppingList,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 160,
      margin: const EdgeInsets.only(right: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      shoppingList.listTypeIcon,
                      style: const TextStyle(fontSize: 20),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        shoppingList.listName,
                        style: AppTextStyles.subtitle2,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const Spacer(),
                Text(
                  '${shoppingList.purchasedItemCount}/${shoppingList.totalItemCount}项',
                  style: AppTextStyles.caption,
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: shoppingList.completionRate,
                    backgroundColor: AppColors.divider,
                    valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
                    minHeight: 4,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
