import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/relationship_member.dart';

/// Card widget for network contacts (人脉圈)
class NetworkMemberCard extends StatelessWidget {
  final RelationshipMember member;
  final VoidCallback? onTap;
  final VoidCallback? onSendGift;
  final VoidCallback? onMessage;

  const NetworkMemberCard({
    super.key,
    required this.member,
    this.onTap,
    this.onSendGift,
    this.onMessage,
  });

  Color get _scoreColor {
    final score = member.score.total;
    if (score >= 90) return const Color(0xFF22C55E);
    if (score >= 70) return const Color(0xFF84CC16);
    if (score >= 50) return const Color(0xFFEAB308);
    if (score >= 30) return const Color(0xFFF97316);
    return const Color(0xFFEF4444);
  }

  Color get _avatarColor {
    final colors = AppColors.categoryColors;
    return colors[member.name.hashCode.abs() % colors.length];
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: const Color(0xFF1E293B), // Dark card background
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top row: Avatar, Name, Score
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Avatar with online indicator
                    Stack(
                      children: [
                        _buildAvatar(),
                        // Online indicator (optional)
                        if (member.score.daysSinceContact != null &&
                            member.score.daysSinceContact! < 7)
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
                                  color: const Color(0xFF1E293B),
                                  width: 2,
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 12),

                    // Name, title, company
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            member.displayName,
                            style: AppTextStyles.subtitle1.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _buildSubtitle(),
                            style: AppTextStyles.caption.copyWith(
                              color: Colors.white70,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // Score
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          '${member.score.total}%',
                          style: AppTextStyles.headline5.copyWith(
                            color: _scoreColor,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'HEALTH',
                          style: AppTextStyles.overline.copyWith(
                            color: Colors.white54,
                            letterSpacing: 1,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                // Progress bar
                _buildProgressBar(),

                const SizedBox(height: 12),

                // Favor balance row
                Row(
                  children: [
                    _buildFavorChip(),
                    const SizedBox(width: 8),
                    _buildLastContactChip(),
                  ],
                ),

                // AI Insight if available
                if (member.suggestedActions.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildInsightCard(),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: _avatarColor.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: member.avatarUrl != null
          ? ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.network(
                member.avatarUrl!,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => _buildAvatarText(),
              ),
            )
          : _buildAvatarText(),
    );
  }

  Widget _buildAvatarText() {
    return Center(
      child: Text(
        member.initials,
        style: AppTextStyles.subtitle1.copyWith(
          color: _avatarColor,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  String _buildSubtitle() {
    final parts = <String>[];
    if (member.occupation != null) parts.add(member.occupation!);
    if (member.workplace != null) parts.add(member.workplace!);
    if (parts.isEmpty) parts.add(member.relationDisplay);
    return parts.join(' \u2022 ');
  }

  Widget _buildProgressBar() {
    final score = member.score.total / 100;
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: LinearProgressIndicator(
        value: score.clamp(0.0, 1.0),
        minHeight: 6,
        backgroundColor: const Color(0xFF334155),
        valueColor: AlwaysStoppedAnimation<Color>(_scoreColor),
      ),
    );
  }

  Widget _buildFavorChip() {
    final balance = member.favorBalance ?? 0;
    final isPositive = balance > 0;
    final isNegative = balance < 0;

    String text;
    Color bgColor;
    Color textColor;
    IconData icon;

    if (isPositive) {
      text = '+${balance.abs()} 人情';
      bgColor = const Color(0xFF14532D);
      textColor = const Color(0xFF86EFAC);
      icon = Icons.trending_up;
    } else if (isNegative) {
      text = '-${balance.abs()} 欠人情';
      bgColor = const Color(0xFF7F1D1D);
      textColor = const Color(0xFFFCA5A5);
      icon = Icons.trending_down;
    } else {
      text = '0 平衡';
      bgColor = const Color(0xFF334155);
      textColor = Colors.white70;
      icon = Icons.balance;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: textColor),
          const SizedBox(width: 4),
          Text(
            text,
            style: AppTextStyles.caption.copyWith(
              color: textColor,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLastContactChip() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF334155),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.access_time, size: 14, color: Colors.white54),
          const SizedBox(width: 4),
          Text(
            member.lastContactText,
            style: AppTextStyles.caption.copyWith(
              color: Colors.white70,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInsightCard() {
    final action = member.suggestedActions.first;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF334155),
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
                  color: AppColors.primary.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.auto_awesome,
                      size: 12,
                      color: AppColors.primaryLight,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'AI INSIGHT',
                      style: AppTextStyles.overline.copyWith(
                        color: AppColors.primaryLight,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                'Just now',
                style: AppTextStyles.overline.copyWith(
                  color: Colors.white38,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Content
          Text(
            action.description,
            style: AppTextStyles.bodyText2.copyWith(
              color: Colors.white70,
            ),
          ),

          const SizedBox(height: 12),

          // Action buttons
          Row(
            children: [
              Expanded(
                child: Material(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(8),
                  child: InkWell(
                    onTap: onSendGift,
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                            Icons.card_giftcard,
                            size: 16,
                            color: Colors.white,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            action.title,
                            style: AppTextStyles.button.copyWith(
                              color: Colors.white,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Material(
                color: const Color(0xFF334155),
                borderRadius: BorderRadius.circular(8),
                child: InkWell(
                  onTap: () {
                    // Dismiss action
                  },
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 10,
                    ),
                    child: Text(
                      'Dismiss',
                      style: AppTextStyles.button.copyWith(
                        color: Colors.white70,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
