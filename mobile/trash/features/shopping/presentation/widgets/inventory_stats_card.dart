import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/inventory_item.dart';
import '../../domain/repositories/inventory_repository.dart';

/// 库存统计卡片
class InventoryStatsCard extends StatelessWidget {
  final InventorySummary summary;
  final VoidCallback? onTap;
  final VoidCallback? onLowStockTap;

  const InventoryStatsCard({
    super.key,
    required this.summary,
    this.onTap,
    this.onLowStockTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                const SizedBox(height: 16),
                _buildStats(),
                if (summary.topLowStockItems.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Divider(height: 1),
                  const SizedBox(height: 12),
                  _buildLowStockList(),
                ],
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
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: AppColors.secondary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(
            Icons.inventory_2_outlined,
            color: AppColors.secondary,
            size: 22,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '家庭库存',
                style: AppTextStyles.subtitle1.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                '共${summary.totalItems}种商品',
                style: AppTextStyles.caption,
              ),
            ],
          ),
        ),
        const Icon(Icons.chevron_right, color: AppColors.textTertiary),
      ],
    );
  }

  Widget _buildStats() {
    return Row(
      children: [
        _buildStatItem(
          label: '库存不足',
          value: summary.lowStockCount.toString(),
          color: AppColors.warning,
          icon: Icons.warning_amber_rounded,
        ),
        const SizedBox(width: 16),
        _buildStatItem(
          label: '即将过期',
          value: summary.expiringCount.toString(),
          color: AppColors.accent1,
          icon: Icons.schedule,
        ),
        const SizedBox(width: 16),
        _buildStatItem(
          label: '已过期',
          value: summary.expiredCount.toString(),
          color: AppColors.error,
          icon: Icons.error_outline,
        ),
      ],
    );
  }

  Widget _buildStatItem({
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 16, color: color),
                const SizedBox(width: 4),
                Text(
                  value,
                  style: AppTextStyles.numberMedium.copyWith(
                    color: color,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: AppTextStyles.overline.copyWith(
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLowStockList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '需要补货',
              style: AppTextStyles.subtitle2,
            ),
            GestureDetector(
              onTap: onLowStockTap,
              child: Text(
                '查看全部',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.primary,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: summary.topLowStockItems.take(5).map((item) {
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(item.categoryIcon, style: const TextStyle(fontSize: 14)),
                  const SizedBox(width: 6),
                  Text(
                    item.productName,
                    style: AppTextStyles.caption.copyWith(
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '${item.currentQuantity.toStringAsFixed(0)}${item.unit ?? ''}',
                    style: AppTextStyles.overline.copyWith(
                      color: AppColors.warning,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ],
    );
  }
}

/// 库存商品卡片
class InventoryItemCard extends StatelessWidget {
  final InventoryItem item;
  final VoidCallback? onTap;
  final VoidCallback? onAddToList;

  const InventoryItemCard({
    super.key,
    required this.item,
    this.onTap,
    this.onAddToList,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
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
            child: Row(
              children: [
                _buildIcon(),
                const SizedBox(width: 12),
                Expanded(child: _buildInfo()),
                _buildStock(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildIcon() {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: _getStatusColor().withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Center(
        child: Text(
          item.categoryIcon,
          style: const TextStyle(fontSize: 24),
        ),
      ),
    );
  }

  Widget _buildInfo() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          item.productName,
          style: AppTextStyles.subtitle2.copyWith(
            color: AppColors.textPrimary,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            if (item.storageLocation != null) ...[
              Icon(Icons.location_on_outlined, size: 12, color: AppColors.textTertiary),
              const SizedBox(width: 2),
              Text(
                item.storageLocation!,
                style: AppTextStyles.overline,
              ),
              const SizedBox(width: 8),
            ],
            if (item.expiryDate != null) ...[
              Icon(
                Icons.schedule,
                size: 12,
                color: item.isExpiringSoon ? AppColors.warning : AppColors.textTertiary,
              ),
              const SizedBox(width: 2),
              Text(
                _formatExpiryDate(),
                style: AppTextStyles.overline.copyWith(
                  color: item.isExpiringSoon ? AppColors.warning : null,
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildStock() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              item.currentQuantity.toStringAsFixed(item.currentQuantity == item.currentQuantity.roundToDouble() ? 0 : 1),
              style: AppTextStyles.subtitle1.copyWith(
                color: _getStatusColor(),
                fontWeight: FontWeight.bold,
              ),
            ),
            if (item.unit != null)
              Text(
                item.unit!,
                style: AppTextStyles.caption.copyWith(
                  color: _getStatusColor(),
                ),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: _getStatusColor().withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            _getStatusLabel(),
            style: AppTextStyles.overline.copyWith(
              color: _getStatusColor(),
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  Color _getStatusColor() {
    switch (item.stockStatus) {
      case StockStatus.adequate:
        return AppColors.success;
      case StockStatus.low:
        return AppColors.warning;
      case StockStatus.critical:
        return AppColors.error;
    }
  }

  String _getStatusLabel() {
    switch (item.stockStatus) {
      case StockStatus.adequate:
        return '充足';
      case StockStatus.low:
        return '偏低';
      case StockStatus.critical:
        return '不足';
    }
  }

  String _formatExpiryDate() {
    final days = item.daysUntilExpiry;
    if (days == null) return '';
    if (days < 0) return '已过期';
    if (days == 0) return '今日到期';
    if (days <= 3) return '$days天后过期';
    if (days <= 7) return '一周内过期';
    return '${item.expiryDate!.month}/${item.expiryDate!.day}过期';
  }
}

/// 补货建议卡片
class ReplenishmentSuggestionCard extends StatelessWidget {
  final InventoryItem item;
  final VoidCallback? onAddToList;

  const ReplenishmentSuggestionCard({
    super.key,
    required this.item,
    this.onAddToList,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 120,
      margin: const EdgeInsets.only(right: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onAddToList,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Center(
                    child: Text(
                      item.categoryIcon,
                      style: const TextStyle(fontSize: 20),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  item.productName,
                  style: AppTextStyles.caption.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 4),
                Text(
                  '剩余${item.currentQuantity.toStringAsFixed(0)}${item.unit ?? ''}',
                  style: AppTextStyles.overline.copyWith(
                    color: AppColors.warning,
                  ),
                ),
                const Spacer(),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add, size: 14, color: Colors.white),
                      SizedBox(width: 2),
                      Text(
                        '加入清单',
                        style: TextStyle(
                          fontSize: 10,
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
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
