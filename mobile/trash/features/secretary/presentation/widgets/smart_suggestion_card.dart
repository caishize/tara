import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/smart_suggestion.dart';

/// A card widget that displays a smart suggestion with actions
class SmartSuggestionCard extends StatelessWidget {
  final SmartSuggestion suggestion;
  final VoidCallback? onDismiss;
  final void Function(String action)? onActionTap;
  final VoidCallback? onTap;
  final bool showActions;
  final bool compact;

  const SmartSuggestionCard({
    super.key,
    required this.suggestion,
    this.onDismiss,
    this.onActionTap,
    this.onTap,
    this.showActions = true,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final isHighUrgency = suggestion.urgency == SuggestionUrgency.high;

    return Dismissible(
      key: Key(suggestion.id),
      direction: DismissDirection.endToStart,
      onDismissed: (_) => onDismiss?.call(),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(
          color: Colors.red.shade400,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Icon(
          Icons.delete_outline,
          color: Colors.white,
          size: 28,
        ),
      ),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: compact
              ? const EdgeInsets.all(12)
              : const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isHighUrgency
                ? AppColors.primary.withValues(alpha: 0.05)
                : Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: isHighUrgency
                ? Border.all(color: AppColors.primary.withValues(alpha: 0.3), width: 1)
                : null,
            boxShadow: AppColors.cardShadow,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header: Icon + Title + Urgency badge
              Row(
                children: [
                  _buildIcon(isHighUrgency),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                suggestion.title,
                                style: compact
                                    ? AppTextStyles.subtitle2.copyWith(
                                        fontWeight: FontWeight.w600,
                                      )
                                    : AppTextStyles.subtitle1.copyWith(
                                        fontWeight: FontWeight.w600,
                                      ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (isHighUrgency) ...[
                              const SizedBox(width: 8),
                              _buildUrgencyBadge(),
                            ],
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          suggestion.typeName,
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textTertiary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(
                      Icons.close,
                      size: 20,
                      color: AppColors.textTertiary,
                    ),
                    onPressed: onDismiss,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),

              // Content
              if (!compact) ...[
                const SizedBox(height: 12),
                Text(
                  suggestion.content,
                  style: AppTextStyles.bodyText2.copyWith(
                    color: AppColors.textSecondary,
                    height: 1.4,
                  ),
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ] else ...[
                const SizedBox(height: 4),
                Text(
                  suggestion.content,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],

              // Action buttons
              if (showActions && suggestion.actionOptions.isNotEmpty) ...[
                const SizedBox(height: 12),
                _buildActionButtons(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIcon(bool isHighUrgency) {
    final iconData = _getIconData(suggestion.icon);
    final color = isHighUrgency ? AppColors.primary : AppColors.secondary;

    return Container(
      width: compact ? 36 : 44,
      height: compact ? 36 : 44,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        iconData,
        color: color,
        size: compact ? 18 : 22,
      ),
    );
  }

  Widget _buildUrgencyBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '紧急',
        style: AppTextStyles.overline.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    // Filter out 'ignore' as it's handled by dismiss gesture
    final actions = suggestion.actionOptions
        .where((a) => a != 'ignore')
        .take(3)
        .toList();

    if (actions.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: actions.map((action) {
        final isPrimary = action == actions.first;
        return _buildActionButton(action, isPrimary);
      }).toList(),
    );
  }

  Widget _buildActionButton(String action, bool isPrimary) {
    final actionName = SmartSuggestion.getActionName(action);

    if (isPrimary) {
      return ElevatedButton(
        onPressed: () => onActionTap?.call(action),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          elevation: 0,
        ),
        child: Text(
          actionName,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
        ),
      );
    }

    return OutlinedButton(
      onPressed: () => onActionTap?.call(action),
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.textSecondary,
        side: const BorderSide(color: AppColors.divider),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      child: Text(
        actionName,
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
      ),
    );
  }

  IconData _getIconData(String iconName) {
    switch (iconName) {
      case 'luggage':
        return Icons.luggage;
      case 'flight_takeoff':
        return Icons.flight_takeoff;
      case 'event':
        return Icons.event;
      case 'people':
        return Icons.people;
      case 'cake':
        return Icons.cake;
      case 'favorite':
        return Icons.favorite;
      case 'event_note':
        return Icons.event_note;
      case 'location_on':
        return Icons.location_on;
      case 'person':
        return Icons.person;
      case 'schedule':
        return Icons.schedule;
      case 'history':
        return Icons.history;
      default:
        return Icons.lightbulb_outline;
    }
  }
}

/// A horizontal scrollable list of suggestion cards
class SmartSuggestionsList extends StatelessWidget {
  final List<SmartSuggestion> suggestions;
  final void Function(SmartSuggestion)? onDismiss;
  final void Function(SmartSuggestion, String action)? onActionTap;
  final void Function(SmartSuggestion)? onTap;

  const SmartSuggestionsList({
    super.key,
    required this.suggestions,
    this.onDismiss,
    this.onActionTap,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (suggestions.isEmpty) {
      return _buildEmptyState();
    }

    return SizedBox(
      height: 180,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: suggestions.length,
        itemBuilder: (context, index) {
          final suggestion = suggestions[index];
          return Container(
            width: 280,
            margin: const EdgeInsets.only(right: 12),
            child: SmartSuggestionCard(
              suggestion: suggestion,
              compact: true,
              showActions: true,
              onDismiss: () => onDismiss?.call(suggestion),
              onActionTap: (action) => onActionTap?.call(suggestion, action),
              onTap: () => onTap?.call(suggestion),
            ),
          );
        },
      ),
    );
  }

  Widget _buildEmptyState() {
    return Container(
      height: 120,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.lightbulb_outline,
              size: 32,
              color: AppColors.textTertiary.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 8),
            Text(
              '暂无智能建议',
              style: AppTextStyles.bodyText2.copyWith(
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
