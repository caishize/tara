import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/shopping_item.dart';

/// 分类筛选芯片组件
class CategoryFilterChips extends StatelessWidget {
  final ItemCategory? selectedCategory;
  final ValueChanged<ItemCategory?> onCategoryChanged;
  final bool showAllOption;

  const CategoryFilterChips({
    super.key,
    this.selectedCategory,
    required this.onCategoryChanged,
    this.showAllOption = true,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 36,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        children: [
          if (showAllOption)
            _buildChip(
              label: '全部',
              icon: '📋',
              isSelected: selectedCategory == null,
              onTap: () => onCategoryChanged(null),
            ),
          ...ItemCategory.values.map((category) => _buildChip(
            label: _getCategoryName(category),
            icon: _getCategoryIcon(category),
            isSelected: selectedCategory == category,
            onTap: () => onCategoryChanged(category),
          )),
        ],
      ),
    );
  }

  Widget _buildChip({
    required String label,
    required String icon,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Material(
        color: isSelected ? AppColors.primary : Colors.white,
        borderRadius: BorderRadius.circular(18),
        elevation: isSelected ? 0 : 1,
        shadowColor: Colors.black12,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              border: isSelected ? null : Border.all(color: AppColors.divider),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(icon, style: const TextStyle(fontSize: 14)),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: AppTextStyles.caption.copyWith(
                    color: isSelected ? Colors.white : AppColors.textSecondary,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _getCategoryIcon(ItemCategory category) {
    switch (category) {
      case ItemCategory.dairy: return '🥛';
      case ItemCategory.meat: return '🥩';
      case ItemCategory.seafood: return '🐟';
      case ItemCategory.vegetable: return '🥬';
      case ItemCategory.fruit: return '🍎';
      case ItemCategory.grain: return '🍚';
      case ItemCategory.snack: return '🍪';
      case ItemCategory.beverage: return '🧃';
      case ItemCategory.household: return '🧹';
      case ItemCategory.personal: return '🧴';
      case ItemCategory.baby: return '🍼';
      case ItemCategory.pet: return '🐕';
      case ItemCategory.electronics: return '📱';
      case ItemCategory.clothing: return '👕';
      case ItemCategory.other: return '📦';
    }
  }

  String _getCategoryName(ItemCategory category) {
    switch (category) {
      case ItemCategory.dairy: return '乳制品';
      case ItemCategory.meat: return '肉类';
      case ItemCategory.seafood: return '海鲜';
      case ItemCategory.vegetable: return '蔬菜';
      case ItemCategory.fruit: return '水果';
      case ItemCategory.grain: return '粮油';
      case ItemCategory.snack: return '零食';
      case ItemCategory.beverage: return '饮料';
      case ItemCategory.household: return '家居';
      case ItemCategory.personal: return '个护';
      case ItemCategory.baby: return '母婴';
      case ItemCategory.pet: return '宠物';
      case ItemCategory.electronics: return '电子';
      case ItemCategory.clothing: return '服装';
      case ItemCategory.other: return '其他';
    }
  }
}

/// 列表状态筛选芯片
class ListStatusFilterChips extends StatelessWidget {
  final String? selectedStatus;
  final ValueChanged<String?> onStatusChanged;

  const ListStatusFilterChips({
    super.key,
    this.selectedStatus,
    required this.onStatusChanged,
  });

  static const _statusOptions = [
    {'key': null, 'label': '全部', 'icon': Icons.list},
    {'key': 'active', 'label': '待采购', 'icon': Icons.pending_outlined},
    {'key': 'in_progress', 'label': '采购中', 'icon': Icons.shopping_cart_outlined},
    {'key': 'completed', 'label': '已完成', 'icon': Icons.check_circle_outline},
  ];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: _statusOptions.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final option = _statusOptions[index];
          final isSelected = selectedStatus == option['key'];

          return Material(
            color: isSelected ? AppColors.primary : Colors.white,
            borderRadius: BorderRadius.circular(18),
            elevation: isSelected ? 0 : 1,
            shadowColor: Colors.black12,
            child: InkWell(
              onTap: () => onStatusChanged(option['key'] as String?),
              borderRadius: BorderRadius.circular(18),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(18),
                  border: isSelected ? null : Border.all(color: AppColors.divider),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      option['icon'] as IconData,
                      size: 16,
                      color: isSelected ? Colors.white : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      option['label'] as String,
                      style: AppTextStyles.caption.copyWith(
                        color: isSelected ? Colors.white : AppColors.textSecondary,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
