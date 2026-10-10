import 'package:flutter/material.dart';

/// Footer widget for V4 future timeline view.
///
/// Displays end-of-list indicator with a pull-to-refresh hint.
class FutureFooter extends StatelessWidget {
  const FutureFooter({super.key});

  static const _footerColor = Color(0xFFD1D0CD);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(top: 16),
      width: double.infinity,
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            '\u2014 已经是全部了 \u2014',
            style: TextStyle(
              fontSize: 12,
              color: _footerColor,
              height: 1.3,
            ),
          ),
          SizedBox(height: 8),
          Text(
            '下拉刷新获取最新动态',
            style: TextStyle(
              fontSize: 11,
              color: _footerColor,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }
}
