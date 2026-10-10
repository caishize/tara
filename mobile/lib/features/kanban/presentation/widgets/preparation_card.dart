import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_dimensions.dart';
import '../../data/models/kanban_models.dart';

/// Grouped preparation card containing MULTIPLE event groups.
/// Each group: title + horizontal checkbox row, separated by dividers.
class PreparationCard extends StatelessWidget {
  final List<KanbanEventModel> events;
  final void Function(String eventId, int itemIndex, bool done)? onToggleItem;

  const PreparationCard({
    super.key,
    required this.events,
    this.onToggleItem,
  });

  @override
  Widget build(BuildContext context) {
    if (events.isEmpty) return const SizedBox.shrink();

    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: AppDimensions.cardMarginH,
        vertical: AppDimensions.cardMarginV,
      ),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(AppDimensions.cardRadius),
        border: Border.all(
          color: colorScheme.outlineVariant,
          width: AppDimensions.cardBorderWidth,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (int i = 0; i < events.length; i++) ...[
            if (i > 0) const Divider(height: 1, color: AppColors.divider),
            _buildEventGroup(context, events[i]),
          ],
        ],
      ),
    );
  }

  Widget _buildEventGroup(BuildContext context, KanbanEventModel event) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title
          Text(
            event.title,
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.onSurface,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),
          // Horizontal checkbox row
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: event.preparationItems.asMap().entries.map((entry) {
              final index = entry.key;
              final item = entry.value;
              return _buildCheckChip(event.id, index, item);
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildCheckChip(String eventId, int index, PreparationItemModel item) {
    final isDone = item.done;

    return GestureDetector(
      onTap: onToggleItem != null
          ? () => onToggleItem!(eventId, index, !isDone)
          : null,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isDone ? AppColors.accentGreenLight : AppColors.bgMuted,
          borderRadius: BorderRadius.circular(8),
          border: isDone
              ? null
              : Border.all(color: AppColors.borderSubtle, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isDone ? Icons.check_circle : Icons.circle_outlined,
              size: 16,
              color: isDone ? AppColors.accentGreen : AppColors.textTertiary,
            ),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                item.item,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: isDone ? AppColors.accentGreen : AppColors.textPrimary,
                  decoration: isDone ? TextDecoration.lineThrough : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
