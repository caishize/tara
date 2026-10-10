import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Card displayed on the profile page that shows insight history summary
/// and navigates to the full insight history page.
/// Matches the prototype design "WeLBH" (洞察管理 card).
class MemoryCard extends StatelessWidget {
  final int memoryCount;
  final String? latestInsight;
  final VoidCallback? onTap;

  const MemoryCard({
    super.key,
    required this.memoryCount,
    this.latestInsight,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row: icon + title + chevron
            Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AppColors.accentWarmLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    Icons.psychology_outlined,
                    color: AppColors.accentWarm,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    '洞察历史',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF1A1918),
                    ),
                  ),
                ),
                const Icon(
                  Icons.chevron_right,
                  color: Color(0xFF9C9B99),
                  size: 18,
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Stat text
            Text(
              '秘书已记住 $memoryCount 条信息',
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF6D6C6A),
              ),
            ),
            // Insight preview
            if (latestInsight != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: AppColors.accentWarmLight,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.lightbulb_outline,
                      size: 16,
                      color: AppColors.accentWarm,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        latestInsight!,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.accentWarm,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
