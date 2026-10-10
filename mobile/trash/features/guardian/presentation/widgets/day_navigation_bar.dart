import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// Navigation bar for selecting days in trip planning
class DayNavigationBar extends StatelessWidget {
  final int totalDays;
  final int selectedDay;
  final ValueChanged<int> onDaySelected;

  const DayNavigationBar({
    super.key,
    required this.totalDays,
    required this.selectedDay,
    required this.onDaySelected,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      margin: const EdgeInsets.symmetric(vertical: 8),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: totalDays,
        itemBuilder: (context, index) {
          final day = index + 1;
          final isSelected = day == selectedDay;

          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Material(
              color: isSelected ? AppColors.primary : AppColors.chipBackground,
              borderRadius: BorderRadius.circular(12),
              child: InkWell(
                onTap: () => onDaySelected(day),
                borderRadius: BorderRadius.circular(12),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                  child: Text(
                    'DAY $day',
                    style: AppTextStyles.button.copyWith(
                      color: isSelected ? Colors.white : AppColors.textSecondary,
                      fontWeight:
                          isSelected ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
