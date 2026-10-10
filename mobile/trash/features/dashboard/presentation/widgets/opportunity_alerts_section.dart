import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Types of opportunity alerts.
enum OpportunityType {
  travel,      // Upcoming trip
  reconnect,   // Reconnect with someone
  gift,        // Gift recommendation
  milestone,   // Relationship milestone
}

/// An opportunity alert item.
class OpportunityItem {
  final String id;
  final String title;
  final String subtitle;
  final OpportunityType type;
  final String? imageUrl;
  final String? avatarUrl;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? onTap;
  final Map<String, dynamic>? metadata;

  const OpportunityItem({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.type,
    this.imageUrl,
    this.avatarUrl,
    this.actionLabel,
    this.onAction,
    this.onTap,
    this.metadata,
  });
}

/// Opportunity Alerts section showing travel, reconnect, and gift opportunities.
class OpportunityAlertsSection extends StatelessWidget {
  final List<OpportunityItem> items;
  final VoidCallback? onViewAll;

  const OpportunityAlertsSection({
    super.key,
    required this.items,
    this.onViewAll,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }

    // Group items by trip context if applicable
    final travelItems = items.where((i) => i.type == OpportunityType.travel).toList();
    final otherItems = items.where((i) => i.type != OpportunityType.travel).toList();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Row(
            children: [
              // Spark icon like demo
              const Text('✨', style: TextStyle(fontSize: 18)),
              const SizedBox(width: 6),
              Text(
                '机会提醒',
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
          // Opportunity cards container
          Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF1A1F2E),
                  Color(0xFF252D3D),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppColors.primary.withValues(alpha: 0.2),
                width: 1,
              ),
            ),
            child: Column(
              children: [
                // Travel item at top (if any)
                if (travelItems.isNotEmpty)
                  _buildTravelHeader(travelItems.first),
                // Other opportunity items
                ...otherItems.asMap().entries.map((entry) {
                  final index = entry.key;
                  final item = entry.value;
                  final isLast = index == otherItems.length - 1 && travelItems.isEmpty;
                  return _buildOpportunityItem(item, isLast);
                }),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTravelHeader(OpportunityItem travel) {
    final daysUntil = travel.metadata?['days_until'] ?? 0;
    final duration = travel.metadata?['duration'] ?? 0;

    return GestureDetector(
      onTap: travel.onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: Colors.white.withValues(alpha: 0.1),
              width: 1,
            ),
          ),
        ),
        child: Row(
          children: [
            // Travel image or icon
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: const Color(0xFF3B82F6).withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(12),
                image: travel.imageUrl != null
                    ? DecorationImage(
                        image: NetworkImage(travel.imageUrl!),
                        fit: BoxFit.cover,
                      )
                    : null,
              ),
              child: travel.imageUrl == null
                  ? const Center(
                      child: Text('✈️', style: TextStyle(fontSize: 28)),
                    )
                  : null,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    travel.title,
                    style: AppTextStyles.subtitle1.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '$daysUntil天后出发 · ${duration}天行程',
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right,
              color: Colors.white.withValues(alpha: 0.5),
              size: 24,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOpportunityItem(OpportunityItem item, bool isLast) {
    return GestureDetector(
      onTap: item.onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(
                  bottom: BorderSide(
                    color: Colors.white.withValues(alpha: 0.05),
                    width: 1,
                  ),
                ),
        ),
        child: Row(
          children: [
            // Avatar or icon
            _buildItemAvatar(item),
            const SizedBox(width: 12),
            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: AppTextStyles.subtitle2.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.subtitle,
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.white.withValues(alpha: 0.5),
                    ),
                  ),
                ],
              ),
            ),
            // Action button or indicator
            _buildItemAction(item),
          ],
        ),
      ),
    );
  }

  Widget _buildItemAvatar(OpportunityItem item) {
    if (item.avatarUrl != null) {
      return CircleAvatar(
        radius: 20,
        backgroundImage: NetworkImage(item.avatarUrl!),
        backgroundColor: Colors.grey.shade800,
      );
    }

    Color bgColor;
    String icon;
    switch (item.type) {
      case OpportunityType.reconnect:
        bgColor = const Color(0xFF8B5CF6).withValues(alpha: 0.2);
        icon = '👤';
        break;
      case OpportunityType.gift:
        bgColor = const Color(0xFFF59E0B).withValues(alpha: 0.2);
        icon = '🎁';
        break;
      case OpportunityType.milestone:
        bgColor = const Color(0xFFEC4899).withValues(alpha: 0.2);
        icon = '🎉';
        break;
      case OpportunityType.travel:
        bgColor = const Color(0xFF3B82F6).withValues(alpha: 0.2);
        icon = '✈️';
        break;
    }

    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Center(
        child: Text(icon, style: const TextStyle(fontSize: 18)),
      ),
    );
  }

  Widget _buildItemAction(OpportunityItem item) {
    if (item.actionLabel != null && item.onAction != null) {
      return GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          item.onAction!();
        },
        child: Text(
          item.actionLabel!,
          style: AppTextStyles.caption.copyWith(
            color: AppColors.primary,
            fontWeight: FontWeight.w600,
          ),
        ),
      );
    }

    // Send message action for reconnect type
    if (item.type == OpportunityType.reconnect) {
      return GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          item.onAction?.call();
        },
        child: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(18),
          ),
          child: const Icon(
            Icons.send,
            color: Colors.white,
            size: 16,
          ),
        ),
      );
    }

    return Icon(
      Icons.chevron_right,
      color: Colors.white.withValues(alpha: 0.3),
      size: 20,
    );
  }
}
