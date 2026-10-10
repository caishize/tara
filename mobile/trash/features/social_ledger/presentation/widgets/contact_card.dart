import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../shared/widgets/avatar_with_initials.dart';
import '../../../../shared/widgets/relationship_health_bar.dart';

/// A contact card showing relationship health and recent activities.
class ContactCard extends StatelessWidget {
  final String name;
  final String? imageUrl;
  final String relationship;
  final double healthPercentage;
  final List<ActivityItem> recentActivities;
  final String? suggestion;
  final VoidCallback? onTap;
  final bool isExpanded;

  const ContactCard({
    super.key,
    required this.name,
    this.imageUrl,
    required this.relationship,
    required this.healthPercentage,
    this.recentActivities = const [],
    this.suggestion,
    this.onTap,
    this.isExpanded = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppColors.cardShadow,
        ),
        child: Column(
          children: [
            // Header with avatar and name
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  AvatarWithInitials(
                    name: name,
                    imageUrl: imageUrl,
                    size: 48,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              name,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.chipBackground,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                relationship,
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: AppColors.primary,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            const Text(
                              '关系健康度',
                              style: TextStyle(
                                fontSize: 12,
                                color: AppColors.textSecondary,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: RelationshipHealthBar(
                                percentage: healthPercentage,
                                height: 6,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              '${healthPercentage.toInt()}%',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: _getHealthColor(),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    Icons.chevron_right,
                    color: AppColors.textTertiary,
                  ),
                ],
              ),
            ),
            // Recent activities (when expanded or has activities)
            if (recentActivities.isNotEmpty) ...[
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: recentActivities.take(3).map((activity) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        children: [
                          Text(
                            activity.date,
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textTertiary,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              activity.content,
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.textSecondary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ),
            ],
            // Suggestion
            if (suggestion != null) ...[
              const Divider(height: 1),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.badgeGreen.withValues(alpha: 0.5),
                  borderRadius: const BorderRadius.only(
                    bottomLeft: Radius.circular(16),
                    bottomRight: Radius.circular(16),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.lightbulb_outline,
                      size: 16,
                      color: AppColors.primary,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '建议：$suggestion',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.primary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _getHealthColor() {
    if (healthPercentage >= 80) return AppColors.success;
    if (healthPercentage >= 50) return AppColors.primary;
    if (healthPercentage >= 30) return AppColors.warning;
    return AppColors.error;
  }
}

/// An activity item for the contact card.
class ActivityItem {
  final String date;
  final String content;
  final IconData? icon;

  const ActivityItem({
    required this.date,
    required this.content,
    this.icon,
  });
}

/// A compact contact row for lists.
class ContactRow extends StatelessWidget {
  final String name;
  final String? imageUrl;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;

  const ContactRow({
    super.key,
    required this.name,
    this.imageUrl,
    this.subtitle,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: AvatarWithInitials(
        name: name,
        imageUrl: imageUrl,
        size: 44,
      ),
      title: Text(
        name,
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w500,
          color: AppColors.textPrimary,
        ),
      ),
      subtitle: subtitle != null
          ? Text(
              subtitle!,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
              ),
            )
          : null,
      trailing: trailing,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    );
  }
}
