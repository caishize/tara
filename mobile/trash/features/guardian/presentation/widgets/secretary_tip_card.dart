import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/poi.dart';
import '../../domain/entities/poi_category.dart';
import '../../domain/entities/secretary_recommendation.dart';

/// Card showing secretary recommendations
class SecretaryTipCard extends StatelessWidget {
  final SecretaryRecommendation recommendation;
  final VoidCallback? onViewAll;
  final ValueChanged<POI>? onPOITap;

  const SecretaryTipCard({
    super.key,
    required this.recommendation,
    this.onViewAll,
    this.onPOITap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppColors.primary.withValues(alpha: 0.08),
            AppColors.secondary.withValues(alpha: 0.08),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    size: 16,
                    color: AppColors.primary,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    recommendation.title,
                    style: AppTextStyles.subtitle2.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                if (onViewAll != null)
                  TextButton(
                    onPressed: onViewAll,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: Text(
                      '查看全部',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.primary,
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // POI horizontal scroll
          if (recommendation.recommendedPOIs.isNotEmpty)
            SizedBox(
              height: 100,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                itemCount: recommendation.recommendedPOIs.length,
                itemBuilder: (context, index) {
                  final poi = recommendation.recommendedPOIs[index];
                  return _buildMiniPOICard(poi);
                },
              ),
            ),

          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildMiniPOICard(POI poi) {
    return GestureDetector(
      onTap: onPOITap != null ? () => onPOITap!(poi) : null,
      child: Container(
        width: 100,
        margin: const EdgeInsets.symmetric(horizontal: 4),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(12)),
              child: poi.hasImages
                  ? Image.network(
                      poi.imageUrls.first,
                      height: 56,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          height: 56,
                          color: AppColors.chipBackground,
                          child: Center(
                            child: Text(
                              poi.category.icon,
                              style: const TextStyle(fontSize: 20),
                            ),
                          ),
                        );
                      },
                    )
                  : Container(
                      height: 56,
                      color: AppColors.chipBackground,
                      child: Center(
                        child: Text(
                          poi.category.icon,
                          style: const TextStyle(fontSize: 20),
                        ),
                      ),
                    ),
            ),

            // Name
            Padding(
              padding: const EdgeInsets.all(6),
              child: Text(
                poi.name,
                style: AppTextStyles.overline.copyWith(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w500,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
