import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/poi.dart';
import '../../domain/entities/poi_category.dart';
import '../bloc/guardian_bloc.dart';
import '../bloc/guardian_event.dart';
import '../bloc/guardian_state.dart';

/// POI detail page showing full information about a place
class POIDetailPage extends StatelessWidget {
  final String poiId;

  const POIDetailPage({
    super.key,
    required this.poiId,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: BlocBuilder<GuardianBloc, GuardianState>(
        builder: (context, state) {
          if (state is GuardianLoading) {
            return const _LoadingView();
          }

          if (state is GuardianError) {
            return _ErrorView(
              message: state.message,
              onRetry: () {
                context.read<GuardianBloc>().add(POIDetailLoadRequested(poiId));
              },
            );
          }

          if (state is POIDetailLoaded) {
            return _POIDetailContent(
              poi: state.poi,
              isFavorite: state.isFavorite,
            );
          }

          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _POIDetailContent extends StatelessWidget {
  final POI poi;
  final bool isFavorite;

  const _POIDetailContent({
    required this.poi,
    required this.isFavorite,
  });

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      slivers: [
        // Image header with back button
        SliverAppBar(
          expandedHeight: 250,
          pinned: true,
          backgroundColor: AppColors.cardBackground,
          leading: IconButton(
            onPressed: () => context.pop(),
            icon: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.arrow_back_ios_new,
                color: Colors.white,
                size: 18,
              ),
            ),
          ),
          actions: [
            IconButton(
              onPressed: () {
                context.read<GuardianBloc>().add(TogglePOIFavorite(poi.id));
                HapticFeedback.lightImpact();
              },
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.3),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isFavorite ? Icons.favorite : Icons.favorite_border,
                  color: isFavorite ? Colors.red : Colors.white,
                  size: 18,
                ),
              ),
            ),
          ],
          flexibleSpace: FlexibleSpaceBar(
            background: poi.hasImages
                ? Image.network(
                    poi.imageUrls.first,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) {
                      return Container(
                        color: AppColors.chipBackground,
                        child: const Center(
                          child: Icon(
                            Icons.image_not_supported_outlined,
                            color: AppColors.textTertiary,
                            size: 64,
                          ),
                        ),
                      );
                    },
                  )
                : Container(
                    color: AppColors.chipBackground,
                    child: Center(
                      child: Text(
                        poi.category.icon,
                        style: const TextStyle(fontSize: 64),
                      ),
                    ),
                  ),
          ),
        ),

        // Content
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Name
                Text(
                  poi.name,
                  style: AppTextStyles.headline5.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),

                // Rating and reviews
                Row(
                  children: [
                    const Icon(Icons.star, color: Colors.amber, size: 20),
                    const SizedBox(width: 4),
                    Text(
                      poi.rating.toStringAsFixed(1),
                      style: AppTextStyles.subtitle1.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (poi.reviewCount > 0) ...[
                      const SizedBox(width: 4),
                      Text(
                        '(${_formatReviewCount(poi.reviewCount)})',
                        style: AppTextStyles.bodyText2.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                    if (poi.priceRange != null) ...[
                      const SizedBox(width: 16),
                      Text(
                        '人均${poi.priceRange}',
                        style: AppTextStyles.bodyText2.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 16),

                // Tags
                if (poi.tags.isNotEmpty) ...[
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: poi.tags.map((tag) {
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          tag,
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 20),
                ],

                // Location and hours
                _buildInfoSection(context),

                // Secretary review
                if (poi.hasSecretaryReview) ...[
                  const SizedBox(height: 20),
                  _buildSecretaryReview(),
                ],

                const SizedBox(height: 24),

                // Action buttons
                _buildActionButtons(context),

                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppColors.cardShadow,
      ),
      child: Column(
        children: [
          // Address
          _buildInfoRow(
            icon: Icons.location_on_outlined,
            title: poi.address,
            trailing: poi.distance != null
                ? Text(
                    poi.formattedDistance,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.primary,
                    ),
                  )
                : null,
          ),

          // Opening hours
          if (poi.openingHours != null) ...[
            const Divider(height: 24),
            _buildInfoRow(
              icon: Icons.access_time,
              title: '营业中',
              subtitle: poi.openingHours,
            ),
          ],

          // Phone
          if (poi.phone != null) ...[
            const Divider(height: 24),
            _buildInfoRow(
              icon: Icons.phone_outlined,
              title: poi.phone!,
              onTap: () => _makePhoneCall(poi.phone!),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoRow({
    required IconData icon,
    required String title,
    String? subtitle,
    Widget? trailing,
    VoidCallback? onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Row(
        children: [
          Icon(
            icon,
            size: 20,
            color: AppColors.textSecondary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.bodyText2,
                ),
                if (subtitle != null)
                  Text(
                    subtitle,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
              ],
            ),
          ),
          if (trailing != null) trailing,
        ],
      ),
    );
  }

  Widget _buildSecretaryReview() {
    return Container(
      padding: const EdgeInsets.all(16),
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
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.auto_awesome,
                  size: 16,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '秘书点评',
                style: AppTextStyles.subtitle2.copyWith(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            poi.secretaryReview!,
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => _makePhoneCall(poi.phone ?? ''),
            icon: const Icon(Icons.phone_outlined, size: 18),
            label: const Text('电话'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.textPrimary,
              side: BorderSide(color: AppColors.divider),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => _openMaps(poi.address),
            icon: const Icon(Icons.navigation_outlined, size: 18),
            label: const Text('导航'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.textPrimary,
              side: BorderSide(color: AppColors.divider),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('预订功能开发中')),
              );
            },
            icon: const Icon(Icons.calendar_today_outlined, size: 18),
            label: const Text('预订'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }

  String _formatReviewCount(int count) {
    if (count >= 10000) {
      return '${(count / 10000).toStringAsFixed(1)}万条点评';
    } else if (count >= 1000) {
      return '${(count / 1000).toStringAsFixed(1)}k条点评';
    }
    return '$count条点评';
  }

  Future<void> _makePhoneCall(String phoneNumber) async {
    final uri = Uri.parse('tel:$phoneNumber');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  Future<void> _openMaps(String address) async {
    final encodedAddress = Uri.encodeComponent(address);
    final uri = Uri.parse('https://maps.apple.com/?q=$encodedAddress');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: CircularProgressIndicator(color: AppColors.primary),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: AppColors.error),
          const SizedBox(height: 16),
          Text(message),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: onRetry, child: const Text('重试')),
        ],
      ),
    );
  }
}
