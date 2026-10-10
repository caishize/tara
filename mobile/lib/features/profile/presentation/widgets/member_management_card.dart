import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

class MemberManagementCard extends StatelessWidget {
  final Map<String, int> memberCountsByType;
  final int attentionCount;
  final VoidCallback? onTap;

  const MemberManagementCard({
    super.key,
    required this.memberCountsByType,
    this.attentionCount = 0,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final total = memberCountsByType['_total'] ?? 0;
    final familyCount = memberCountsByType['family'] ?? 0;
    final friendCount = memberCountsByType['friend'] ?? 0;
    final colleagueCount = memberCountsByType['colleague'] ?? 0;
    final relativeCount = memberCountsByType['relative'] ?? 0;
    final categorized = familyCount + friendCount + colleagueCount + relativeCount;
    final otherCount = total > categorized ? total - categorized : (memberCountsByType['other'] ?? 0);

    final segments = <String>[];
    if (familyCount > 0) segments.add('家人 $familyCount');
    if (friendCount > 0) segments.add('朋友 $friendCount');
    if (colleagueCount > 0) segments.add('同事 $colleagueCount');
    if (relativeCount > 0) segments.add('亲戚 $relativeCount');
    if (otherCount > 0) segments.add('其他 $otherCount');

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.people_outline,
                    color: AppColors.primary,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('成员管理', style: AppTextStyles.subtitle1),
                ),
                const Icon(
                  Icons.chevron_right,
                  color: AppColors.textTertiary,
                  size: 20,
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (total > 0)
              Text(
                '共 $total 位联系人${segments.isNotEmpty ? '  ${segments.join(' · ')}' : ''}',
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            if (total == 0 && segments.isEmpty)
              Text(
                '暂无联系人',
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textTertiary,
                ),
              ),
            if (attentionCount > 0) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.info_outline,
                      size: 14,
                      color: AppColors.warning,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '$attentionCount 位联系人需要关注',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.warning,
                        fontWeight: FontWeight.w500,
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
}
