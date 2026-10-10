import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/models/memory_model.dart';

/// Card widget to display a secretary memory
class MemoryCard extends StatelessWidget {
  final MemoryModel memory;
  final VoidCallback? onTap;

  const MemoryCard({
    super.key,
    required this.memory,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(memory.typeIcon, style: const TextStyle(fontSize: 18)),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: _getTypeColor().withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    memory.typeDisplayName,
                    style: AppTextStyles.caption.copyWith(
                      color: _getTypeColor(),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  memory.timeAgoText,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              memory.content,
              style: AppTextStyles.bodyText2,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            if (memory.entities?.isNotEmpty == true) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _buildEntityChips(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _getTypeColor() {
    switch (memory.memoryType) {
      case 'emotion':
        return const Color(0xFF9C27B0); // Purple
      case 'plan':
        return const Color(0xFF2196F3); // Blue
      case 'schedule':
        return const Color(0xFF4CAF50); // Green
      case 'relationship':
        return const Color(0xFFFF9800); // Orange
      case 'preference':
        return const Color(0xFFE91E63); // Pink
      case 'life_event':
        return const Color(0xFF00BCD4); // Cyan
      case 'location':
        return const Color(0xFF795548); // Brown
      case 'health':
        return const Color(0xFFF44336); // Red
      default:
        return AppColors.primary;
    }
  }

  List<Widget> _buildEntityChips() {
    final entities = memory.entities ?? {};
    final chips = <Widget>[];

    entities.forEach((key, value) {
      if (value != null && value.toString().isNotEmpty) {
        chips.add(
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              '$key: $value',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
                fontSize: 11,
              ),
            ),
          ),
        );
      }
    });

    return chips.take(3).toList(); // Limit to 3 chips
  }
}

/// Compact memory list tile
class MemoryListTile extends StatelessWidget {
  final MemoryModel memory;
  final VoidCallback? onTap;

  const MemoryListTile({
    super.key,
    required this.memory,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Center(
          child: Text(memory.typeIcon, style: const TextStyle(fontSize: 16)),
        ),
      ),
      title: Text(
        memory.content,
        style: AppTextStyles.bodyText2,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '${memory.typeDisplayName} · ${memory.timeAgoText}',
        style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
      ),
    );
  }
}
