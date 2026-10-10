import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

class StatsCard extends StatelessWidget {
  final int daysSinceJoined;
  final int totalRecords;
  final int reminderCount;
  final int insightCount;

  const StatsCard({
    super.key,
    required this.daysSinceJoined,
    required this.totalRecords,
    required this.reminderCount,
    required this.insightCount,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.accentGreenLight,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: sparkle icon + "这XX天里"
          Row(
            children: [
              Icon(
                Icons.auto_awesome,
                size: 16,
                color: AppColors.accentGreen,
              ),
              const SizedBox(width: 6),
              Text(
                '✨ 这${daysSinceJoined}天里',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.accentGreen,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Stats row
          Row(
            children: [
              _buildStatItem('$totalRecords', '件事我帮你记着'),
              _buildStatItem('$reminderCount', '次我提醒了你'),
              _buildStatItem('$insightCount', '个发现你没注意到'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String number, String label) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            number,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: AppColors.accentGreen,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: Color(0xFF6D6C6A),
            ),
          ),
        ],
      ),
    );
  }
}
