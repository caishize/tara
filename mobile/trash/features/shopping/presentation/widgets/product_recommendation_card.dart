import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/product_recommendation.dart';

/// 产品推荐卡片
class ProductRecommendationCard extends StatelessWidget {
  final ProductRecommendation recommendation;
  final VoidCallback? onTap;
  final VoidCallback? onAddToList;

  const ProductRecommendationCard({
    super.key,
    required this.recommendation,
    this.onTap,
    this.onAddToList,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildImage(),
              _buildInfo(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildImage() {
    return Stack(
      children: [
        AspectRatio(
          aspectRatio: 1,
          child: ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            child: recommendation.imageUrl != null
                ? CachedNetworkImage(
                    imageUrl: recommendation.imageUrl!,
                    fit: BoxFit.cover,
                    placeholder: (context, url) => Container(
                      color: AppColors.background,
                      child: const Center(child: CircularProgressIndicator()),
                    ),
                    errorWidget: (context, url, error) => _buildPlaceholder(),
                  )
                : _buildPlaceholder(),
          ),
        ),
        // 推荐原因标签
        Positioned(
          top: 8,
          left: 8,
          child: _buildReasonBadge(),
        ),
        // 降价标签
        if (recommendation.hasPriceDrop)
          Positioned(
            top: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.error,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.trending_down, size: 12, color: Colors.white),
                  const SizedBox(width: 2),
                  Text(
                    '-${recommendation.priceDropPercentage?.toStringAsFixed(0) ?? '0'}%',
                    style: AppTextStyles.overline.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ),
        // 添加按钮
        if (onAddToList != null)
          Positioned(
            bottom: 8,
            right: 8,
            child: GestureDetector(
              onTap: onAddToList,
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  shape: BoxShape.circle,
                  boxShadow: [AppColors.shadowLight],
                ),
                child: const Icon(Icons.add, size: 18, color: Colors.white),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: AppColors.background,
      child: Center(
        child: Text(
          recommendation.reasonIcon,
          style: const TextStyle(fontSize: 40),
        ),
      ),
    );
  }

  Widget _buildReasonBadge() {
    Color color;
    switch (recommendation.reason) {
      case RecommendationReason.frequentPurchase:
        color = AppColors.primary;
        break;
      case RecommendationReason.lowStock:
        color = AppColors.warning;
        break;
      case RecommendationReason.priceDrop:
        color = AppColors.error;
        break;
      case RecommendationReason.seasonal:
        color = AppColors.secondary;
        break;
      case RecommendationReason.bundleSuggestion:
        color = AppColors.accent3;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            recommendation.reasonIcon,
            style: const TextStyle(fontSize: 10),
          ),
          const SizedBox(width: 4),
          Text(
            recommendation.reasonName,
            style: AppTextStyles.overline.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfo() {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Text(
                recommendation.productName,
                style: AppTextStyles.bodyText2.copyWith(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Text(
                  '¥${recommendation.estimatedPrice?.toStringAsFixed(0) ?? '0'}',
                  style: AppTextStyles.subtitle1.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
                if (recommendation.hasPriceDrop && recommendation.baselinePrice != null) ...[
                  const SizedBox(width: 6),
                  Text(
                    '¥${recommendation.baselinePrice!.toStringAsFixed(0)}',
                    style: AppTextStyles.caption.copyWith(
                      decoration: TextDecoration.lineThrough,
                      color: AppColors.textTertiary,
                    ),
                  ),
                ],
              ],
            ),
            if (recommendation.merchant != null) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.store_outlined, size: 12, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      recommendation.merchant!,
                      style: AppTextStyles.overline.copyWith(
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 紧凑型推荐卡片
class CompactRecommendationCard extends StatelessWidget {
  final ProductRecommendation recommendation;
  final VoidCallback? onTap;
  final VoidCallback? onAddToList;

  const CompactRecommendationCard({
    super.key,
    required this.recommendation,
    this.onTap,
    this.onAddToList,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 140,
      margin: const EdgeInsets.only(right: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  AspectRatio(
                    aspectRatio: 1,
                    child: ClipRRect(
                      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                      child: recommendation.imageUrl != null
                          ? CachedNetworkImage(
                              imageUrl: recommendation.imageUrl!,
                              fit: BoxFit.cover,
                              errorWidget: (context, url, error) => Container(
                                color: AppColors.background,
                                child: Center(
                                  child: Text(
                                    recommendation.reasonIcon,
                                    style: const TextStyle(fontSize: 32),
                                  ),
                                ),
                              ),
                            )
                          : Container(
                              color: AppColors.background,
                              child: Center(
                                child: Text(
                                  recommendation.reasonIcon,
                                  style: const TextStyle(fontSize: 32),
                                ),
                              ),
                            ),
                    ),
                  ),
                  if (recommendation.hasPriceDrop)
                    Positioned(
                      top: 6,
                      left: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.error,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '-${recommendation.priceDropPercentage?.toStringAsFixed(0) ?? '0'}%',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recommendation.productName,
                      style: AppTextStyles.caption.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '¥${recommendation.estimatedPrice?.toStringAsFixed(0) ?? '0'}',
                          style: AppTextStyles.bodyText2.copyWith(
                            color: AppColors.error,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        if (onAddToList != null)
                          GestureDetector(
                            onTap: onAddToList,
                            child: Container(
                              width: 24,
                              height: 24,
                              decoration: BoxDecoration(
                                color: AppColors.primary,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: const Icon(
                                Icons.add,
                                size: 16,
                                color: Colors.white,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 推荐商品列表区域
class RecommendationSection extends StatelessWidget {
  final String title;
  final List<ProductRecommendation> recommendations;
  final ValueChanged<ProductRecommendation>? onItemTap;
  final ValueChanged<ProductRecommendation>? onAddToList;
  final VoidCallback? onSeeAll;

  const RecommendationSection({
    super.key,
    required this.title,
    required this.recommendations,
    this.onItemTap,
    this.onAddToList,
    this.onSeeAll,
  });

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: AppTextStyles.headline6),
              if (onSeeAll != null)
                GestureDetector(
                  onTap: onSeeAll,
                  child: Row(
                    children: [
                      Text(
                        '查看全部',
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.primary,
                        ),
                      ),
                      const Icon(
                        Icons.chevron_right,
                        size: 16,
                        color: AppColors.primary,
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        SizedBox(
          height: 210,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: recommendations.length,
            itemBuilder: (context, index) {
              final item = recommendations[index];
              return CompactRecommendationCard(
                recommendation: item,
                onTap: () => onItemTap?.call(item),
                onAddToList: () => onAddToList?.call(item),
              );
            },
          ),
        ),
      ],
    );
  }
}
