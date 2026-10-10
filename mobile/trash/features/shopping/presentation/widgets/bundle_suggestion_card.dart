import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/bundle_opportunity.dart';

/// 凑单建议卡片
class BundleSuggestionCard extends StatelessWidget {
  final BundleOpportunity bundle;
  final VoidCallback? onTap;
  final VoidCallback? onDismiss;

  const BundleSuggestionCard({
    super.key,
    required this.bundle,
    this.onTap,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            bundle.isWorthIt ? AppColors.success.withValues(alpha: 0.1) : AppColors.warning.withValues(alpha: 0.1),
            bundle.isWorthIt ? AppColors.success.withValues(alpha: 0.05) : AppColors.warning.withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: bundle.isWorthIt ? AppColors.success.withValues(alpha: 0.3) : AppColors.warning.withValues(alpha: 0.3),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                const SizedBox(height: 12),
                _buildProgress(),
                const SizedBox(height: 12),
                _buildFooter(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: bundle.isWorthIt ? AppColors.success : AppColors.warning,
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(
            Icons.local_offer_outlined,
            color: Colors.white,
            size: 22,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                bundle.couponName,
                style: AppTextStyles.subtitle1.copyWith(
                  fontWeight: FontWeight.bold,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                bundle.displayMessage,
                style: AppTextStyles.caption.copyWith(
                  color: bundle.isWorthIt ? AppColors.success : AppColors.warning,
                ),
              ),
            ],
          ),
        ),
        if (onDismiss != null)
          IconButton(
            onPressed: onDismiss,
            icon: const Icon(Icons.close, size: 20),
            color: AppColors.textTertiary,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
          ),
      ],
    );
  }

  Widget _buildProgress() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '当前 ¥${bundle.currentTotal.toStringAsFixed(0)}',
              style: AppTextStyles.caption,
            ),
            Text(
              '差 ¥${bundle.gap.toStringAsFixed(0)}',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.error,
                fontWeight: FontWeight.w600,
              ),
            ),
            Text(
              '满 ¥${bundle.threshold.toStringAsFixed(0)}',
              style: AppTextStyles.caption,
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: bundle.progressPercentage,
            backgroundColor: AppColors.divider,
            valueColor: AlwaysStoppedAnimation<Color>(
              bundle.isWorthIt ? AppColors.success : AppColors.warning,
            ),
            minHeight: 8,
          ),
        ),
      ],
    );
  }

  Widget _buildFooter() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                '省 ¥${bundle.discount.toStringAsFixed(0)}',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.error,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
            if (bundle.roi >= 0.5)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.thumb_up, size: 12, color: AppColors.success),
                    const SizedBox(width: 4),
                    Text(
                      '超值',
                      style: AppTextStyles.overline.copyWith(
                        color: AppColors.success,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
        Text(
          'ROI ${(bundle.roi * 100).toStringAsFixed(0)}%',
          style: AppTextStyles.caption.copyWith(
            color: bundle.roi >= 0.5 ? AppColors.success : AppColors.textTertiary,
          ),
        ),
      ],
    );
  }
}

/// 凑单建议列表
class BundleSuggestionList extends StatelessWidget {
  final List<BundleOpportunity> bundles;
  final ValueChanged<BundleOpportunity>? onBundleTap;

  const BundleSuggestionList({
    super.key,
    required this.bundles,
    this.onBundleTap,
  });

  @override
  Widget build(BuildContext context) {
    if (bundles.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              const Icon(Icons.savings_outlined, size: 20, color: AppColors.warning),
              const SizedBox(width: 8),
              Text(
                '凑单建议',
                style: AppTextStyles.headline6,
              ),
              const Spacer(),
              Text(
                '${bundles.length}个机会',
                style: AppTextStyles.caption,
              ),
            ],
          ),
        ),
        ...bundles.take(3).map((bundle) => BundleSuggestionCard(
          bundle: bundle,
          onTap: () => onBundleTap?.call(bundle),
        )),
      ],
    );
  }
}
