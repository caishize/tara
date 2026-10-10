import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';

/// Category for network members
enum NetworkCategory {
  family,
  business,
  friend,
}

/// AI Insight suggestion for a member
class NetworkInsight {
  final String id;
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final VoidCallback? onDismiss;
  final DateTime timestamp;

  const NetworkInsight({
    required this.id,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.onDismiss,
    required this.timestamp,
  });
}

/// Network member data for the redesigned card
class NetworkMemberData {
  final String id;
  final String name;
  final String? title;
  final String? company;
  final String? avatarUrl;
  final int healthScore; // 0-100
  final NetworkCategory category;
  final int favorBalance; // Positive = they owe us, negative = we owe them
  final DateTime? lastInteractionDate; // Real date from API
  final String? statusBadge;
  final NetworkInsight? insight;
  final bool isOnline;

  const NetworkMemberData({
    required this.id,
    required this.name,
    this.title,
    this.company,
    this.avatarUrl,
    required this.healthScore,
    required this.category,
    this.favorBalance = 0,
    this.lastInteractionDate,
    this.statusBadge,
    this.insight,
    this.isOnline = false,
  });

  String get subtitle {
    if (title != null && company != null) {
      return '$title · $company';
    }
    return title ?? company ?? '';
  }

  /// Format last interaction as human-readable string
  String? get lastInteractionText {
    if (lastInteractionDate == null) return null;

    final now = DateTime.now();
    final diff = now.difference(lastInteractionDate!);

    if (diff.inDays == 0) return '今天';
    if (diff.inDays == 1) return '昨天';
    if (diff.inDays < 7) return '${diff.inDays}天前';
    if (diff.inDays < 14) return '1周前';
    if (diff.inDays < 30) return '${diff.inDays ~/ 7}周前';
    if (diff.inDays < 60) return '1个月前';
    return '${diff.inDays ~/ 30}个月前';
  }
}

/// Redesigned member card with light theme
class NetworkMemberCard extends StatelessWidget {
  final NetworkMemberData member;
  final VoidCallback? onTap;
  final bool isExpanded;

  const NetworkMemberCard({
    super.key,
    required this.member,
    this.onTap,
    this.isExpanded = false,
  });

  Color _getHealthColor(int score) {
    if (score >= 80) return AppColors.success;
    if (score >= 60) return AppColors.warning;
    if (score >= 40) return const Color(0xFFFF9800);
    return AppColors.error;
  }

  Color _getAvatarColor() {
    return AppColors.categoryColors[member.name.hashCode.abs() % AppColors.categoryColors.length];
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Main content row
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Avatar
                    _buildAvatar(),
                    const SizedBox(width: 12),

                    // Info
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Name and health score
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  member.name,
                                  style: const TextStyle(
                                    color: AppColors.textPrimary,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                              // Health score
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '${member.healthScore}%',
                                    style: TextStyle(
                                      color: _getHealthColor(member.healthScore),
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Text(
                                    '健康度',
                                    style: TextStyle(
                                      color: AppColors.textTertiary,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),

                          // Subtitle (title · company)
                          if (member.subtitle.isNotEmpty) ...[
                            const SizedBox(height: 2),
                            Text(
                              member.subtitle,
                              style: TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 13,
                              ),
                            ),
                          ],

                          const SizedBox(height: 8),

                          // Health progress bar
                          _buildHealthBar(),

                          const SizedBox(height: 10),

                          // Favor balance row
                          _buildFavorBalanceRow(),
                        ],
                      ),
                    ),
                  ],
                ),

                // AI Insight card (if available)
                if (member.insight != null) ...[
                  const SizedBox(height: 12),
                  _buildInsightCard(member.insight!),
                ],

                // Last interaction and status badge
                if (member.lastInteractionText != null || member.statusBadge != null) ...[
                  const SizedBox(height: 12),
                  _buildBottomRow(),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAvatar() {
    return Stack(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: member.avatarUrl != null ? null : _getAvatarColor().withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            image: member.avatarUrl != null
                ? DecorationImage(
                    image: NetworkImage(member.avatarUrl!),
                    fit: BoxFit.cover,
                  )
                : null,
          ),
          child: member.avatarUrl == null
              ? Center(
                  child: Text(
                    member.name.isNotEmpty ? member.name.substring(0, 1) : '?',
                    style: TextStyle(
                      color: _getAvatarColor(),
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                )
              : null,
        ),
        // Online indicator
        if (member.isOnline)
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: AppColors.success,
                shape: BoxShape.circle,
                border: Border.all(
                  color: AppColors.cardBackground,
                  width: 2,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildHealthBar() {
    return Container(
      height: 6,
      decoration: BoxDecoration(
        color: AppColors.divider,
        borderRadius: BorderRadius.circular(3),
      ),
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: member.healthScore / 100,
        child: Container(
          decoration: BoxDecoration(
            color: _getHealthColor(member.healthScore),
            borderRadius: BorderRadius.circular(3),
          ),
        ),
      ),
    );
  }

  Widget _buildFavorBalanceRow() {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: AppColors.chipBackground,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.swap_horiz,
                size: 14,
                color: AppColors.primary,
              ),
              const SizedBox(width: 4),
              Text(
                '人情余额',
                style: TextStyle(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                member.favorBalance >= 0
                    ? '+${member.favorBalance} 帮助'
                    : '${member.favorBalance} 欠'
                ,
                style: TextStyle(
                  color: member.favorBalance >= 0
                      ? AppColors.success
                      : AppColors.warning,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInsightCard(NetworkInsight insight) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.auto_awesome,
                      size: 12,
                      color: AppColors.primary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'AI 建议',
                      style: TextStyle(
                        color: AppColors.primary,
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                _formatTimestamp(insight.timestamp),
                style: TextStyle(
                  color: AppColors.textTertiary,
                  fontSize: 11,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Message
          Text(
            insight.message,
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 13,
              height: 1.4,
            ),
          ),

          // Actions
          if (insight.actionLabel != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: insight.onAction,
                    icon: const Icon(Icons.card_giftcard, size: 16),
                    label: Text(insight.actionLabel!),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: insight.onDismiss,
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.textSecondary,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 10,
                    ),
                  ),
                  child: const Text('忽略'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBottomRow() {
    return Row(
      children: [
        if (member.lastInteractionText != null) ...[
          Icon(
            Icons.access_time,
            size: 14,
            color: AppColors.textTertiary,
          ),
          const SizedBox(width: 4),
          Text(
            '最近互动: ${member.lastInteractionText}',
            style: TextStyle(
              color: AppColors.textTertiary,
              fontSize: 12,
            ),
          ),
        ],
        const Spacer(),
        if (member.statusBadge != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: _getStatusBadgeColor(),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              member.statusBadge!,
              style: TextStyle(
                color: _getStatusBadgeTextColor(),
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
      ],
    );
  }

  Color _getStatusBadgeColor() {
    if (member.statusBadge == null) return Colors.transparent;
    if (member.statusBadge!.contains('+')) {
      return AppColors.success.withValues(alpha: 0.1);
    }
    if (member.statusBadge!.contains('-')) {
      return AppColors.warning.withValues(alpha: 0.1);
    }
    return AppColors.textTertiary.withValues(alpha: 0.1);
  }

  Color _getStatusBadgeTextColor() {
    if (member.statusBadge == null) return Colors.transparent;
    if (member.statusBadge!.contains('+')) {
      return AppColors.success;
    }
    if (member.statusBadge!.contains('-')) {
      return AppColors.warning;
    }
    return AppColors.textSecondary;
  }

  String _formatTimestamp(DateTime timestamp) {
    final now = DateTime.now();
    final diff = now.difference(timestamp);

    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
    if (diff.inDays < 1) return '${diff.inHours}小时前';
    if (diff.inDays < 7) return '${diff.inDays}天前';
    return '${timestamp.month}/${timestamp.day}';
  }
}
