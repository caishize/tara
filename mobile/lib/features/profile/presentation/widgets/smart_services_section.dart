import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/smart_service.dart';

class SmartServicesSection extends StatelessWidget {
  final List<SmartService> services;
  final int activeCount;
  final int totalCount;
  final bool isLoading;
  final String? loadingServiceId;
  final void Function(SmartService service)? onServiceTap;
  final VoidCallback? onViewAllTap;

  const SmartServicesSection({
    super.key,
    required this.services,
    required this.activeCount,
    required this.totalCount,
    this.isLoading = false,
    this.loadingServiceId,
    this.onServiceTap,
    this.onViewAllTap,
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
                const Icon(
                  Icons.auto_awesome,
                  color: AppColors.primary,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text('智能秘书服务', style: AppTextStyles.subtitle1),
              ],
            ),
            if (totalCount > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$activeCount/$totalCount 运行中',
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.success,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [AppColors.shadowLight],
          ),
          child: Column(
            children: [
              if (services.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(20),
                  child: Text('暂无服务'),
                )
              else ...[
                // Show first 4 services
                ...services.take(4).map((service) => _ServiceTile(
                      service: service,
                      isLoading: loadingServiceId == service.id,
                      onTap: () => onServiceTap?.call(service),
                    )),
                // View all button
                if (services.length > 4 || onViewAllTap != null)
                  InkWell(
                    onTap: onViewAllTap,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: const BoxDecoration(
                        border: Border(
                          top: BorderSide(color: AppColors.divider),
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            '查看全部',
                            style: AppTextStyles.bodyText2.copyWith(
                              color: AppColors.primary,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(
                            Icons.arrow_forward_ios,
                            size: 12,
                            color: AppColors.primary,
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _ServiceTile extends StatelessWidget {
  final SmartService service;
  final bool isLoading;
  final VoidCallback? onTap;

  const _ServiceTile({
    required this.service,
    this.isLoading = false,
    this.onTap,
  });

  IconData _getIconData() {
    switch (service.icon) {
      case 'notifications_active':
        return Icons.notifications_active_outlined;
      case 'celebration':
        return Icons.celebration_outlined;
      case 'card_giftcard':
        return Icons.card_giftcard_outlined;
      case 'redeem':
        return Icons.redeem_outlined;
      case 'trending_down':
        return Icons.trending_down_outlined;
      default:
        return Icons.settings_outlined;
    }
  }

  Color _getStatusColor() {
    if (service.isRunning) return AppColors.success;
    if (service.isEnabled) return AppColors.warning;
    return AppColors.textTertiary;
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: const BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AppColors.divider, width: 0.5),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                _getIconData(),
                color: AppColors.primary,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(service.displayName, style: AppTextStyles.bodyText1),
                  const SizedBox(height: 2),
                  Text(
                    service.description,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            if (isLoading)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: _getStatusColor(),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    service.statusText,
                    style: AppTextStyles.caption.copyWith(
                      color: _getStatusColor(),
                    ),
                  ),
                ],
              ),
            const SizedBox(width: 4),
            const Icon(
              Icons.chevron_right,
              color: AppColors.textTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}
