import 'package:flutter/material.dart';
import '../../domain/entities/shopping_item.dart';

/// 商品标签选择器
/// 匹配原型设计：日常采购、出差代购、礼物、紧急
class ItemTagSelector extends StatelessWidget {
  final List<ItemTag> selectedTags;
  final ValueChanged<List<ItemTag>> onTagsChanged;

  const ItemTagSelector({
    super.key,
    required this.selectedTags,
    required this.onTagsChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '标签分类',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w500,
              ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: ItemTag.values.map((tag) => _buildTagChip(context, tag)).toList(),
        ),
      ],
    );
  }

  Widget _buildTagChip(BuildContext context, ItemTag tag) {
    final isSelected = selectedTags.contains(tag);
    final tagInfo = _getTagInfo(tag);

    return FilterChip(
      label: Text(tagInfo.label),
      selected: isSelected,
      onSelected: (selected) {
        final newTags = List<ItemTag>.from(selectedTags);
        if (selected) {
          newTags.add(tag);
        } else {
          newTags.remove(tag);
        }
        onTagsChanged(newTags);
      },
      avatar: isSelected ? null : Text(tagInfo.icon, style: const TextStyle(fontSize: 14)),
      selectedColor: tagInfo.color.withOpacity(0.2),
      checkmarkColor: tagInfo.color,
      labelStyle: TextStyle(
        color: isSelected ? tagInfo.color : Colors.black87,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
      ),
      side: BorderSide(
        color: isSelected ? tagInfo.color : Colors.grey.shade300,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
    );
  }

  _TagInfo _getTagInfo(ItemTag tag) {
    switch (tag) {
      case ItemTag.daily:
        return _TagInfo(
          label: '日常采购',
          icon: '🛒',
          color: const Color(0xFF4CAF50),
        );
      case ItemTag.businessTrip:
        return _TagInfo(
          label: '出差代购',
          icon: '✈️',
          color: const Color(0xFF2196F3),
        );
      case ItemTag.gift:
        return _TagInfo(
          label: '礼物',
          icon: '🎁',
          color: const Color(0xFFE91E63),
        );
      case ItemTag.urgent:
        return _TagInfo(
          label: '紧急',
          icon: '⚡',
          color: const Color(0xFFFF5722),
        );
    }
  }
}

class _TagInfo {
  final String label;
  final String icon;
  final Color color;

  _TagInfo({
    required this.label,
    required this.icon,
    required this.color,
  });
}

/// 获取标签的显示文本
String getTagLabel(ItemTag tag) {
  switch (tag) {
    case ItemTag.daily:
      return '日常采购';
    case ItemTag.businessTrip:
      return '出差代购';
    case ItemTag.gift:
      return '礼物';
    case ItemTag.urgent:
      return '紧急';
  }
}

/// 获取标签的颜色
Color getTagColor(ItemTag tag) {
  switch (tag) {
    case ItemTag.daily:
      return const Color(0xFF4CAF50);
    case ItemTag.businessTrip:
      return const Color(0xFF2196F3);
    case ItemTag.gift:
      return const Color(0xFFE91E63);
    case ItemTag.urgent:
      return const Color(0xFFFF5722);
  }
}
