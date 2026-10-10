import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Relationship type for display.
enum RelationshipType {
  partner,
  parent,
  child,
  sibling,
  friend,
  colleague,
  other,
}

/// A relationship health item.
class RelationshipHealthItem {
  final String id;
  final String name;
  final RelationshipType type;
  final int healthScore; // 0-100
  final String suggestion;
  final String? avatarUrl;
  final int? daysSinceContact;
  final VoidCallback? onTap;
  final VoidCallback? onAction;

  const RelationshipHealthItem({
    required this.id,
    required this.name,
    required this.type,
    required this.healthScore,
    required this.suggestion,
    this.avatarUrl,
    this.daysSinceContact,
    this.onTap,
    this.onAction,
  });

  /// Get health level based on score.
  HealthLevel get healthLevel {
    if (healthScore >= 70) return HealthLevel.good;
    if (healthScore >= 40) return HealthLevel.needsAttention;
    return HealthLevel.critical;
  }
}

enum HealthLevel {
  good,
  needsAttention,
  critical,
}

/// Relationship Health section showing key relationships status.
class RelationshipHealthSection extends StatelessWidget {
  final List<RelationshipHealthItem> items;
  final VoidCallback? onViewAll;
  final bool isLoading;

  const RelationshipHealthSection({
    super.key,
    required this.items,
    this.onViewAll,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Row(
            children: [
              Text(
                '关系健康度',
                style: AppTextStyles.headline6.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (onViewAll != null)
                GestureDetector(
                  onTap: onViewAll,
                  child: Text(
                    '查看全部',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Relationship cards in horizontal scroll or grid
          if (isLoading)
            _buildLoadingState()
          else if (items.isEmpty)
            _buildEmptyState()
          else
            _buildRelationshipCards(),
        ],
      ),
    );
  }

  Widget _buildRelationshipCards() {
    // Show max 2-3 cards in a row
    final displayItems = items.take(3).toList();

    return Row(
      children: displayItems.asMap().entries.map((entry) {
        final index = entry.key;
        final item = entry.value;
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(
              right: index < displayItems.length - 1 ? 12 : 0,
            ),
            child: _RelationshipHealthCard(item: item),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildLoadingState() {
    return Row(
      children: List.generate(2, (index) {
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: index == 0 ? 12 : 0),
            child: Container(
              height: 120,
              decoration: BoxDecoration(
                color: Colors.grey.shade200,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Center(
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.textTertiary,
                  ),
                ),
              ),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildEmptyState() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppColors.success.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.people_outline,
              color: AppColors.success,
              size: 24,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '关系状态良好',
                  style: AppTextStyles.subtitle1.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '暂无需要关注的关系',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Individual relationship health card.
class _RelationshipHealthCard extends StatelessWidget {
  final RelationshipHealthItem item;

  const _RelationshipHealthCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.lightImpact();
        item.onTap?.call();
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with icon and score
            Row(
              children: [
                _buildTypeIcon(),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item.name,
                    style: AppTextStyles.subtitle2.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  '${item.healthScore}%',
                  style: AppTextStyles.subtitle2.copyWith(
                    color: _getScoreColor(),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: item.healthScore / 100,
                backgroundColor: Colors.grey.shade200,
                valueColor: AlwaysStoppedAnimation<Color>(_getScoreColor()),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 10),
            // Suggestion text
            Text(
              item.suggestion,
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypeIcon() {
    IconData icon;
    Color color;

    switch (item.type) {
      case RelationshipType.partner:
        icon = Icons.favorite;
        color = const Color(0xFFEC4899);
        break;
      case RelationshipType.parent:
        icon = Icons.people;
        color = const Color(0xFF8B5CF6);
        break;
      case RelationshipType.child:
        icon = Icons.child_care;
        color = const Color(0xFF10B981);
        break;
      case RelationshipType.sibling:
        icon = Icons.people_outline;
        color = const Color(0xFF3B82F6);
        break;
      case RelationshipType.friend:
        icon = Icons.person;
        color = const Color(0xFFF59E0B);
        break;
      case RelationshipType.colleague:
        icon = Icons.work_outline;
        color = const Color(0xFF6B7280);
        break;
      case RelationshipType.other:
        icon = Icons.person_outline;
        color = const Color(0xFF6B7280);
        break;
    }

    return Icon(icon, color: color, size: 18);
  }

  Color _getScoreColor() {
    switch (item.healthLevel) {
      case HealthLevel.good:
        return const Color(0xFF10B981);
      case HealthLevel.needsAttention:
        return const Color(0xFFF59E0B);
      case HealthLevel.critical:
        return const Color(0xFFEF4444);
    }
  }
}

/// Compact relationship health badge for inline display.
class RelationshipHealthBadge extends StatelessWidget {
  final int healthScore;
  final double size;

  const RelationshipHealthBadge({
    super.key,
    required this.healthScore,
    this.size = 36,
  });

  @override
  Widget build(BuildContext context) {
    final color = _getColor();

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: 0.1),
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 2,
        ),
      ),
      child: Center(
        child: Text(
          '$healthScore',
          style: TextStyle(
            fontSize: size * 0.35,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
      ),
    );
  }

  Color _getColor() {
    if (healthScore >= 70) return const Color(0xFF10B981);
    if (healthScore >= 40) return const Color(0xFFF59E0B);
    return const Color(0xFFEF4444);
  }
}
