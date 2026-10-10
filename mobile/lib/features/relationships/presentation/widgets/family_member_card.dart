import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/relationship_member.dart';

/// Card widget for family members (家人圈)
class FamilyMemberCard extends StatelessWidget {
  final RelationshipMember member;
  final VoidCallback? onTap;
  final VoidCallback? onCall;
  final VoidCallback? onMessage;

  const FamilyMemberCard({
    super.key,
    required this.member,
    this.onTap,
    this.onCall,
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
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              boxShadow: AppColors.cardShadow,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top row: Avatar, Name, Score
                Row(
                  children: [
                    // Avatar
                    _buildAvatar(),
                    const SizedBox(width: 12),

                    // Name and relation
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            member.displayName,
                            style: AppTextStyles.subtitle1.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            member.relationDisplay,
                            style: AppTextStyles.bodyText2.copyWith(
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),

                    // Score with heart emoji
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              member.status.emoji,
                              style: const TextStyle(fontSize: 16),
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '${member.score.total}%',
                              style: AppTextStyles.subtitle1.copyWith(
                                color: _scoreColor,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '亲密度',
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textTertiary,
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

                // Info row: Last contact and upcoming date
                Row(
                  children: [
                    // Last contact
                    Expanded(
                      child: _buildInfoChip(
                        icon: Icons.access_time,
                        text: member.lastContactText,
                        isWarning: member.isOverdue,
                      ),
                    ),

                    // Upcoming date if any
                    if (member.upcomingDates.isNotEmpty) ...[
                      const SizedBox(width: 8),
                      Expanded(
                        child: _buildInfoChip(
                          icon: Icons.cake,
                          text: _getUpcomingDateText(),
                          isHighlight: true,
                        ),
                      ),
                    ],
                  ],
                ),

                // Action buttons
                if (member.phone != null || member.suggestedActions.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildActionButtons(),
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
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        color: _avatarColor.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(16),
      ),
      child: member.avatarUrl != null
          ? ClipRRect(
              borderRadius: BorderRadius.circular(16),
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
        style: AppTextStyles.headline4.copyWith(
          color: _avatarColor,
        ),
      ),
    );
  }

  Widget _buildProgressBar() {
    final score = member.score.total / 100;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score.clamp(0.0, 1.0),
            minHeight: 6,
            backgroundColor: AppColors.divider,
            valueColor: AlwaysStoppedAnimation<Color>(_scoreColor),
          ),
        ),
        const SizedBox(height: 6),
        // Score breakdown
        Row(
          children: [
            _buildScoreLabel('联络', member.score.contactScore),
            const SizedBox(width: 12),
            _buildScoreLabel('关怀', member.score.careScore),
            const SizedBox(width: 12),
            _buildScoreLabel('了解', member.score.understandingScore),
          ],
        ),
      ],
    );
  }

  Widget _buildScoreLabel(String label, double score) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: AppTextStyles.overline.copyWith(
            color: AppColors.textTertiary,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          '${score.toInt()}',
          style: AppTextStyles.overline.copyWith(
            color: AppColors.textSecondary,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  Widget _buildInfoChip({
    required IconData icon,
    required String text,
    bool isWarning = false,
    bool isHighlight = false,
  }) {
    final Color bgColor;
    final Color textColor;

    if (isWarning) {
      bgColor = AppColors.warning.withValues(alpha: 0.1);
      textColor = AppColors.warning;
    } else if (isHighlight) {
      bgColor = AppColors.primary.withValues(alpha: 0.1);
      textColor = AppColors.primary;
    } else {
      bgColor = AppColors.chipBackground;
      textColor = AppColors.textSecondary;
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
          Flexible(
            child: Text(
              text,
              style: AppTextStyles.caption.copyWith(color: textColor),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  String _getUpcomingDateText() {
    if (member.upcomingDates.isEmpty) return '';
    final date = member.upcomingDates.first;
    return '${date.title}还有${date.daysUntil}天';
  }

  Widget _buildActionButtons() {
    return Row(
      children: [
        if (member.phone != null) ...[
          Expanded(
            child: _buildActionButton(
              icon: Icons.phone,
              label: '打电话',
              onTap: onCall,
              isPrimary: true,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _buildActionButton(
              icon: Icons.message,
              label: '发消息',
              onTap: onMessage,
            ),
          ),
        ],
        // Show suggestion if no phone
        if (member.phone == null && member.suggestedActions.isNotEmpty) ...[
          Expanded(
            child: _buildSuggestionChip(member.suggestedActions.first),
          ),
        ],
      ],
    );
  }

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    VoidCallback? onTap,
    bool isPrimary = false,
  }) {
    return Material(
      color: isPrimary
          ? AppColors.primary
          : AppColors.chipBackground,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 16,
                color: isPrimary ? Colors.white : AppColors.primary,
              ),
              const SizedBox(width: 4),
              Text(
                label,
                style: AppTextStyles.button.copyWith(
                  color: isPrimary ? Colors.white : AppColors.primary,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSuggestionChip(SuggestedAction action) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.lightbulb_outline,
            size: 16,
            color: AppColors.primary,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              action.title,
              style: AppTextStyles.caption.copyWith(
                color: AppColors.primary,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
