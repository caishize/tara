import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../app/theme/app_colors.dart';
import '../../domain/entities/trip.dart';

/// Horizontal progress bar showing trip temporal progress.
/// Only rendered for in-progress or completed trips.
class TripProgressBar extends StatelessWidget {
  final Trip trip;

  const TripProgressBar({super.key, required this.trip});

  @override
  Widget build(BuildContext context) {
    if (trip.status != TripStatus.inProgress &&
        trip.status != TripStatus.completed) {
      return const SizedBox.shrink();
    }

    final totalDays = trip.durationDays;
    final now = DateTime.now();
    final startDay = DateTime(
      trip.startDate.year,
      trip.startDate.month,
      trip.startDate.day,
    );
    final daysElapsed = now.difference(startDay).inDays + 1;
    final clampedDays = daysElapsed.clamp(0, totalDays);
    final progress = totalDays > 0 ? clampedDays / totalDays : 1.0;
    final dateFormat = DateFormat('M/d');

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        children: [
          // Labels
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                dateFormat.format(trip.startDate),
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
              Text(
                trip.status == TripStatus.completed
                    ? '已完成'
                    : '第 $clampedDays 天 / 共 $totalDays 天',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              Text(
                dateFormat.format(trip.endDate),
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textTertiary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          // Progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              minHeight: 6,
              backgroundColor: AppColors.chipBackground,
              valueColor:
                  const AlwaysStoppedAnimation<Color>(AppColors.primary),
            ),
          ),
        ],
      ),
    );
  }
}
