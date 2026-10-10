import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_item.dart';
import 'item_tag_selector.dart';

/// 购物商品列表项组件
/// 匹配原型图设计：复选框 + 名称 + 标签 + 描述
class ShoppingItemTile extends StatelessWidget {
  final ShoppingItem item;
  final VoidCallback? onTap;
  final VoidCallback? onTogglePurchased;
  final VoidCallback? onDelete;
  final bool showSwipeActions;
  final bool compactMode; // 紧凑模式，隐藏分类图标

  const ShoppingItemTile({
    super.key,
    required this.item,
    this.onTap,
    this.onTogglePurchased,
    this.onDelete,
    this.showSwipeActions = true,
    this.compactMode = false,
  });

  @override
  Widget build(BuildContext context) {
    final tile = Container(
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
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: _buildCheckbox(),
                ),
                const SizedBox(width: 12),
                Expanded(child: _buildInfo()),
              ],
            ),
          ),
        ),
      ),
    );

    if (!showSwipeActions) return tile;

    return Dismissible(
      key: Key(item.id),
      direction: DismissDirection.endToStart,
      background: _buildDeleteBackground(),
      confirmDismiss: (_) async {
        onDelete?.call();
        return false;
      },
      child: tile,
    );
  }

  Widget _buildCheckbox() {
    return GestureDetector(
      onTap: onTogglePurchased,
      child: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: item.isPurchased ? AppColors.success : Colors.transparent,
          border: Border.all(
            color: item.isPurchased ? AppColors.success : AppColors.divider,
            width: 2,
          ),
          borderRadius: BorderRadius.circular(6),
        ),
        child: item.isPurchased
            ? const Icon(Icons.check, size: 16, color: Colors.white)
            : null,
      ),
    );
  }

  Widget _buildInfo() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 物品名称
        Text(
          item.productName,
          style: AppTextStyles.subtitle2.copyWith(
            decoration: _isCompleted ? TextDecoration.lineThrough : null,
            color: _isCompleted ? AppColors.textTertiary : AppColors.textPrimary,
            fontWeight: FontWeight.w500,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 6),
        // 标签行（匹配原型图：出差代购、配送中、已完成、紧急等）
        _buildTagsRow(),
        // 描述文字
        if (item.notes != null && item.notes!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            item.notes!,
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textSecondary,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ],
    );
  }

  /// 是否已完成（配送/已购买）
  bool get _isCompleted => item.itemStatus == ItemStatus.delivered || item.isPurchased;

  /// 构建标签行（匹配原型图设计）
  Widget _buildTagsRow() {
    final List<Widget> tagWidgets = [];

    // 1. 商品标签（出差代购、礼物、紧急、日常采购）
    for (final tag in item.tags) {
      tagWidgets.add(_buildItemTag(tag));
    }

    // 2. 状态标签（配送中、已完成等）- 仅显示非 pending 状态
    if (item.itemStatus != ItemStatus.pending) {
      tagWidgets.add(_buildStatusTag());
    }

    // 3. 预计送达（如果有且未完成）
    final deliveryText = item.deliveryText;
    if (deliveryText != null && item.itemStatus != ItemStatus.delivered) {
      tagWidgets.add(_buildDeliveryTag(deliveryText));
    }

    if (tagWidgets.isEmpty) {
      // 无标签时显示数量
      return Text(
        '${item.quantity.toInt()}${item.unit ?? '件'}',
        style: AppTextStyles.caption,
      );
    }

    return Wrap(
      spacing: 6,
      runSpacing: 4,
      children: tagWidgets,
    );
  }

  /// 构建商品标签（出差代购、礼物、紧急等）
  Widget _buildItemTag(ItemTag tag) {
    final color = getTagColor(tag);
    final label = getTagLabel(tag);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  /// 构建状态标签（配送中、已完成等）
  Widget _buildStatusTag() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: item.itemStatusColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        item.itemStatusName,
        style: TextStyle(
          color: item.itemStatusColor,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  /// 构建送达时间标签
  Widget _buildDeliveryTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.info.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: AppColors.info,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }


  Widget _buildDeleteBackground() {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: 20),
      decoration: BoxDecoration(
        color: AppColors.error,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Icon(Icons.delete_outline, color: Colors.white),
    );
  }

}

/// 添加商品的空状态提示
class EmptyItemsPlaceholder extends StatelessWidget {
  final VoidCallback? onAddItem;

  const EmptyItemsPlaceholder({super.key, this.onAddItem});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.shopping_cart_outlined,
              size: 40,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '清单是空的',
            style: AppTextStyles.headline6.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '点击下方按钮添加商品',
            style: AppTextStyles.caption,
          ),
          if (onAddItem != null) ...[
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onAddItem,
              icon: const Icon(Icons.add),
              label: const Text('添加商品'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
