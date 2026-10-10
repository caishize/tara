import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/member.dart';

class MemberCard extends StatelessWidget {
  final Member member;
  final VoidCallback? onTap;

  const MemberCard({
    super.key,
    required this.member,
    this.onTap,
  });

  Color _getAvatarColor() {
    // Generate color based on name
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
            child: Row(
              children: [
                // Avatar
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: _getAvatarColor().withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Center(
                    child: Text(
                      member.name.isNotEmpty ? member.name.substring(0, 1) : '?',
                      style: AppTextStyles.headline4.copyWith(
                        color: _getAvatarColor(),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),

                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            member.displayName,
                            style: AppTextStyles.subtitle1,
                          ),
                          if (member.name != member.nickname &&
                              member.nickname != null) ...[
                            const SizedBox(width: 8),
                            Text(
                              '(${member.name})',
                              style: AppTextStyles.caption,
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          _buildTag(member.relationText),
                          if (member.genderText != null) ...[
                            const SizedBox(width: 8),
                            _buildTag(member.genderText!),
                          ],
                          if (member.age != null) ...[
                            const SizedBox(width: 8),
                            _buildTag('${member.age}岁'),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),

                // Profile completion indicator
                Stack(
                  alignment: Alignment.center,
                  children: [
                    SizedBox(
                      width: 36,
                      height: 36,
                      child: CircularProgressIndicator(
                        value: member.profileCompletion / 100,
                        strokeWidth: 3,
                        backgroundColor: AppColors.divider,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          member.profileCompletion >= 80
                              ? AppColors.success
                              : member.profileCompletion >= 50
                                  ? AppColors.warning
                                  : AppColors.textTertiary,
                        ),
                      ),
                    ),
                    Text(
                      '${member.profileCompletion}',
                      style: AppTextStyles.overline.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),

                const SizedBox(width: 8),
                const Icon(
                  Icons.chevron_right,
                  color: AppColors.textTertiary,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.chipBackground,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: AppTextStyles.overline.copyWith(
          color: AppColors.primary,
        ),
      ),
    );
  }
}
