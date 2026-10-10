import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

class DataConnectionsCard extends StatelessWidget {
  final int connectionCount;
  final List<String> connectedProviderTypes;
  final VoidCallback? onTap;

  const DataConnectionsCard({
    super.key,
    required this.connectionCount,
    this.connectedProviderTypes = const [],
    this.onTap,
  });

  static const _providerTypeIcons = <String, IconData>{
    'calendar': Icons.calendar_today,
    'email': Icons.mail_outline,
    'notes': Icons.note_outlined,
    'transport': Icons.directions_car_outlined,
    'shopping': Icons.shopping_cart_outlined,
    'smart_home': Icons.home_outlined,
    'custom': Icons.extension_outlined,
  };

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [AppColors.shadowLight],
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.connectionAccent.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.link,
                color: AppColors.connectionAccent,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('\u6570\u636e\u8fde\u63a5', style: AppTextStyles.subtitle1),
                  const SizedBox(height: 2),
                  Text(
                    connectionCount > 0
                        ? '\u5df2\u8fde\u63a5 $connectionCount \u4e2a\u670d\u52a1'
                        : '\u6682\u672a\u8fde\u63a5\u670d\u52a1',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            if (connectionCount > 0) ...[
              _buildProviderIcons(),
              const SizedBox(width: 8),
            ],
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

  Widget _buildProviderIcons() {
    final uniqueTypes = connectedProviderTypes.toSet().toList();
    final displayCount = uniqueTypes.length.clamp(0, 3);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(displayCount, (i) {
        final icon = _providerTypeIcons[uniqueTypes[i]] ?? Icons.link;
        return Container(
          width: 24,
          height: 24,
          margin: EdgeInsets.only(left: i > 0 ? 4 : 0),
          decoration: BoxDecoration(
            color: AppColors.connectionAccent.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Icon(
            icon,
            size: 14,
            color: AppColors.connectionAccent,
          ),
        );
      }),
    );
  }
}
