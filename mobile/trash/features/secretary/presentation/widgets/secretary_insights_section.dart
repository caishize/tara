import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/models/insight_model.dart';

/// Dashboard section widget showing secretary insights
class SecretaryInsightsSection extends StatelessWidget {
  final List<InsightModel> insights;
  final bool isLoading;
  final VoidCallback? onViewAll;
  final void Function(InsightModel insight)? onInsightTap;
  final void Function(InsightModel insight)? onDismiss;

  const SecretaryInsightsSection({
    super.key,
    required this.insights,
    this.isLoading = false,
    this.onViewAll,
    this.onInsightTap,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  '智能秘书洞察',
                  style: AppTextStyles.subtitle1.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            if (onViewAll != null)
              TextButton(
                onPressed: onViewAll,
                child: Text(
                  '查看全部',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.primary,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        if (isLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(),
            ),
          )
        else if (insights.isEmpty)
          _buildEmptyState()
        else
          ...insights.take(3).map((insight) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _InsightTile(
                  insight: insight,
                  onTap: () => onInsightTap?.call(insight),
                  onDismiss: () => onDismiss?.call(insight),
                ),
              )),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        children: [
          Icon(
            Icons.lightbulb_outline,
            size: 48,
            color: AppColors.textTertiary.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 12),
          Text(
            '暂无新洞察',
            style: AppTextStyles.subtitle2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '秘书正在分析您的对话...',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}

class _InsightTile extends StatelessWidget {
  final InsightModel insight;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;

  const _InsightTile({
    required this.insight,
    this.onTap,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: _getInsightColor().withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Center(
                child:
                    Text(insight.typeIcon, style: const TextStyle(fontSize: 18)),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          insight.title,
                          style: AppTextStyles.bodyText1.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (insight.isHighPriority)
                        Container(
                          margin: const EdgeInsets.only(left: 8),
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            color: AppColors.warning,
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    insight.content,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                      height: 1.4,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            if (onDismiss != null)
              GestureDetector(
                onTap: onDismiss,
                child: Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Icon(
                    Icons.close,
                    size: 16,
                    color: AppColors.textTertiary,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Color _getInsightColor() {
    switch (insight.insightType) {
      case 'daily_briefing':
        return const Color(0xFF2196F3);
      case 'reminder':
        return const Color(0xFFFF9800);
      case 'suggestion':
      case 'proactive_suggestion':
        return const Color(0xFF4CAF50);
      case 'warning':
        return const Color(0xFFF44336);
      case 'follow_up':
      case 'plan_follow_up':
        return const Color(0xFF9C27B0);
      case 'relationship_reminder':
        return const Color(0xFF00BCD4);
      default:
        return AppColors.primary;
    }
  }
}
