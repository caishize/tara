import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Weather information chip for homepage header.
class WeatherChip extends StatelessWidget {
  final String? icon;
  final String? temperature;
  final String? condition;
  final bool isLoading;
  final VoidCallback? onTap;

  const WeatherChip({
    super.key,
    this.icon,
    this.temperature,
    this.condition,
    this.isLoading = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return _buildLoadingState();
    }

    if (temperature == null) {
      return const SizedBox.shrink();
    }

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.cardBackground,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _getWeatherIcon(),
              style: const TextStyle(fontSize: 18),
            ),
            const SizedBox(width: 6),
            Text(
              temperature!,
              style: AppTextStyles.subtitle2.copyWith(
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingState() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.cardBackground,
        borderRadius: BorderRadius.circular(20),
      ),
      child: const SizedBox(
        width: 50,
        height: 20,
        child: Center(
          child: SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppColors.textTertiary,
            ),
          ),
        ),
      ),
    );
  }

  String _getWeatherIcon() {
    if (icon != null) return icon!;

    // Default weather icons based on condition
    final cond = condition?.toLowerCase() ?? '';
    if (cond.contains('sunny') || cond.contains('clear') || cond.contains('晴')) {
      return '☀️';
    } else if (cond.contains('cloud') || cond.contains('多云') || cond.contains('阴')) {
      return '☁️';
    } else if (cond.contains('rain') || cond.contains('雨')) {
      return '🌧️';
    } else if (cond.contains('snow') || cond.contains('雪')) {
      return '❄️';
    } else if (cond.contains('thunder') || cond.contains('雷')) {
      return '⛈️';
    } else if (cond.contains('fog') || cond.contains('雾') || cond.contains('霾')) {
      return '🌫️';
    }
    return '☀️';
  }
}

/// Extended weather card for detail view.
class WeatherDetailCard extends StatelessWidget {
  final String temperature;
  final String condition;
  final String? highTemp;
  final String? lowTemp;
  final String? humidity;
  final String? wind;
  final String? location;

  const WeatherDetailCard({
    super.key,
    required this.temperature,
    required this.condition,
    this.highTemp,
    this.lowTemp,
    this.humidity,
    this.wind,
    this.location,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.info.withValues(alpha: 0.1),
            AppColors.primary.withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppColors.info.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (location != null)
            Row(
              children: [
                const Icon(
                  Icons.location_on_outlined,
                  size: 14,
                  color: AppColors.textSecondary,
                ),
                const SizedBox(width: 4),
                Text(
                  location!,
                  style: AppTextStyles.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                temperature,
                style: AppTextStyles.headline3.copyWith(
                  fontWeight: FontWeight.w300,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    condition,
                    style: AppTextStyles.subtitle1.copyWith(
                      color: AppColors.textPrimary,
                    ),
                  ),
                  if (highTemp != null && lowTemp != null)
                    Text(
                      '$highTemp / $lowTemp',
                      style: AppTextStyles.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                ],
              ),
            ],
          ),
          if (humidity != null || wind != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                if (humidity != null) ...[
                  const Icon(
                    Icons.water_drop_outlined,
                    size: 14,
                    color: AppColors.info,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    humidity!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
                if (humidity != null && wind != null) const SizedBox(width: 16),
                if (wind != null) ...[
                  const Icon(
                    Icons.air,
                    size: 14,
                    color: AppColors.info,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    wind!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}
