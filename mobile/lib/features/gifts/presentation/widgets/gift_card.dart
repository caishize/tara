import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/gift.dart';
import '../bloc/gifts_bloc.dart';

class GiftCard extends StatelessWidget {
  final Gift gift;
  final VoidCallback? onTap;

  const GiftCard({
    super.key,
    required this.gift,
    this.onTap,
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
              _buildImage(context),
              _buildInfo(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildImage(BuildContext context) {
    return Stack(
      children: [
        AspectRatio(
          aspectRatio: 1,
          child: ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
            child: gift.imageUrl != null
                ? CachedNetworkImage(
                    imageUrl: gift.imageUrl!,
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
        Positioned(
          top: 8,
          right: 8,
          child: _buildSaveButton(context),
        ),
        if (gift.hasDiscount)
          Positioned(
            top: 8,
            left: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.error,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '-${gift.discountPercent}%',
                style: AppTextStyles.overline.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
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
          gift.categoryIcon,
          style: const TextStyle(fontSize: 40),
        ),
      ),
    );
  }

  Widget _buildSaveButton(BuildContext context) {
    return GestureDetector(
      onTap: () {
        context.read<GiftsBloc>().add(GiftSaveToggled(
          giftId: gift.id,
          isSaved: !gift.isSaved,
        ));
      },
      child: Container(
        width: 32,
        height: 32,
        decoration: BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          boxShadow: [AppColors.shadowLight],
        ),
        child: Icon(
          gift.isSaved ? Icons.favorite : Icons.favorite_border,
          color: gift.isSaved ? AppColors.error : AppColors.textSecondary,
          size: 18,
        ),
      ),
    );
  }

  Widget _buildInfo() {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Flexible(
              child: Text(
                gift.name,
                style: AppTextStyles.bodyText2.copyWith(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '¥${gift.price.toStringAsFixed(0)}',
              style: AppTextStyles.subtitle1.copyWith(
                color: AppColors.error,
                fontWeight: FontWeight.bold,
                fontSize: 15,
              ),
            ),
            if (gift.description != null && gift.description!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                gift.description!,
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.primary,
                  fontSize: 10,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            if (gift.rating > 0) ...[
              const SizedBox(height: 2),
              Row(
                children: [
                  const Icon(Icons.star, color: Colors.amber, size: 12),
                  const SizedBox(width: 2),
                  Text(
                    gift.rating.toStringAsFixed(1),
                    style: AppTextStyles.caption.copyWith(fontSize: 11),
                  ),
                  Text(
                    ' (${gift.reviewCount})',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textTertiary,
                      fontSize: 11,
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

class CompactGiftCard extends StatelessWidget {
  final Gift gift;

  const CompactGiftCard({super.key, required this.gift});

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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 1,
            child: ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              child: gift.imageUrl != null
                  ? CachedNetworkImage(
                      imageUrl: gift.imageUrl!,
                      fit: BoxFit.cover,
                      errorWidget: (context, url, error) => Container(
                        color: AppColors.background,
                        child: Center(
                          child: Text(gift.categoryIcon, style: const TextStyle(fontSize: 32)),
                        ),
                      ),
                    )
                  : Container(
                      color: AppColors.background,
                      child: Center(
                        child: Text(gift.categoryIcon, style: const TextStyle(fontSize: 32)),
                      ),
                    ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  gift.name,
                  style: AppTextStyles.caption.copyWith(fontWeight: FontWeight.w600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  '¥${gift.price.toStringAsFixed(0)}',
                  style: AppTextStyles.bodyText2.copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
