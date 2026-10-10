import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../data/models/future_view_models.dart';

/// Family member row for V4 future timeline view.
///
/// Shows avatar circle with initial, name/relationship, status line,
/// and a chevron indicator.
class FutureFamilyRow extends StatelessWidget {
  final FutureViewMemberModel member;
  final VoidCallback? onTap;

  const FutureFamilyRow({
    super.key,
    required this.member,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          _buildAvatar(),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${member.name} \u00B7 ${member.relationship}',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                    height: 1.3,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (member.statusLine.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    member.statusLine,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                      height: 1.3,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          const Icon(
            Icons.chevron_right,
            size: 16,
            color: Color(0xFFD1D0CD),
          ),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: member.avatarColorValue,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        member.avatarInitial,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: Colors.white,
          height: 1.2,
        ),
      ),
    );
  }
}
