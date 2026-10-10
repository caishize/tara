import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/associated_item.dart';

/// 筛选芯片组件
class FilterChips extends StatelessWidget {
  final ItemType? activeFilter;
  final ValueChanged<ItemType?> onFilterChanged;
  final Map<ItemType, int>? counts;

  const FilterChips({
    super.key,
    this.activeFilter,
    required this.onFilterChanged,
    this.counts,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          _FilterChip(
            label: '全部',
            isActive: activeFilter == null,
            onTap: () => onFilterChanged(null),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: '人物',
            icon: Icons.person_outline,
            count: counts?[ItemType.person],
            isActive: activeFilter == ItemType.person,
            onTap: () => onFilterChanged(ItemType.person),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: '任务',
            icon: Icons.check_circle_outline,
            count: counts?[ItemType.task],
            isActive: activeFilter == ItemType.task,
            onTap: () => onFilterChanged(ItemType.task),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: '物品',
            icon: Icons.card_giftcard_outlined,
            count: counts?[ItemType.gift],
            isActive: activeFilter == ItemType.gift,
            onTap: () => onFilterChanged(ItemType.gift),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: '地点',
            icon: Icons.place_outlined,
            count: counts?[ItemType.place],
            isActive: activeFilter == ItemType.place,
            onTap: () => onFilterChanged(ItemType.place),
          ),
          const SizedBox(width: 8),
          _FilterChip(
            label: '商务',
            icon: Icons.business_outlined,
            count: counts?[ItemType.business],
            isActive: activeFilter == ItemType.business,
            onTap: () => onFilterChanged(ItemType.business),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final IconData? icon;
  final int? count;
  final bool isActive;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    this.icon,
    this.count,
    required this.isActive,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? AppColors.primary : AppColors.chipBackground,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isActive ? AppColors.primary : AppColors.divider,
            width: 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(
                icon,
                size: 16,
                color: isActive ? Colors.white : AppColors.textSecondary,
              ),
              const SizedBox(width: 6),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: isActive ? Colors.white : AppColors.textSecondary,
              ),
            ),
            if (count != null && count! > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isActive
                      ? Colors.white.withValues(alpha: 0.2)
                      : AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  count.toString(),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: isActive ? Colors.white : AppColors.primary,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
