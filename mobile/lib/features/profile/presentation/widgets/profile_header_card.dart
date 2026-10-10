import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

class ProfileHeaderCard extends StatelessWidget {
  final String displayName;
  final String? familyName;
  final int daysSinceJoined;
  final int familyMemberCount;
  final VoidCallback? onEditTap;

  const ProfileHeaderCard({
    super.key,
    required this.displayName,
    this.familyName,
    required this.daysSinceJoined,
    required this.familyMemberCount,
    this.onEditTap,
  });

  @override
  Widget build(BuildContext context) {
    final firstChar = displayName.isNotEmpty ? displayName[0] : '?';
    final description = familyName != null
        ? '$familyName · ${familyMemberCount}位成员'
        : '${displayName}的家庭 · ${familyMemberCount}位成员';

    return GestureDetector(
      onTap: onEditTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: AppColors.accentGreen,
                borderRadius: BorderRadius.circular(28),
              ),
              alignment: Alignment.center,
              child: Text(
                firstChar,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    displayName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF1A1918),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 13,
                      color: Color(0xFF6D6C6A),
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right,
              color: Color(0xFF9C9B99),
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}
