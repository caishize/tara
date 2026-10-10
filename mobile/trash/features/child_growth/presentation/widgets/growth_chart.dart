import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/growth_record.dart';

/// 成长曲线图组件
class GrowthChart extends StatefulWidget {
  final GrowthCurveData data;

  const GrowthChart({super.key, required this.data});

  @override
  State<GrowthChart> createState() => _GrowthChartState();
}

class _GrowthChartState extends State<GrowthChart> {
  int _selectedMetric = 0; // 0: 身高, 1: 体重, 2: 头围

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [AppColors.shadowLight],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Text('成长曲线', style: AppTextStyles.subtitle1),
                const Spacer(),
                _buildMetricSelector(),
              ],
            ),
          ),
          SizedBox(
            height: 200,
            child: _buildChart(),
          ),
          _buildLegend(),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildMetricSelector() {
    final metrics = ['身高', '体重', '头围'];
    return Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, (index) {
          final isSelected = _selectedMetric == index;
          return GestureDetector(
            onTap: () => setState(() => _selectedMetric = index),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.primary : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                metrics[index],
                style: AppTextStyles.caption.copyWith(
                  color: isSelected ? Colors.white : AppColors.textSecondary,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildChart() {
    final points = _getDataPoints();
    if (points.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.show_chart, size: 48, color: AppColors.textTertiary),
            const SizedBox(height: 8),
            Text(
              '暂无${['身高', '体重', '头围'][_selectedMetric]}数据',
              style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: CustomPaint(
        size: const Size(double.infinity, 160),
        painter: GrowthChartPainter(
          points: points,
          color: _getMetricColor(),
          unit: _getUnit(),
        ),
      ),
    );
  }

  List<GrowthCurvePoint> _getDataPoints() {
    switch (_selectedMetric) {
      case 0:
        return widget.data.heightCurve;
      case 1:
        return widget.data.weightCurve;
      case 2:
        return widget.data.headCircumferenceCurve;
      default:
        return [];
    }
  }

  Color _getMetricColor() {
    switch (_selectedMetric) {
      case 0:
        return AppColors.primary;
      case 1:
        return AppColors.secondary;
      case 2:
        return AppColors.accent1;
      default:
        return AppColors.primary;
    }
  }

  String _getUnit() {
    switch (_selectedMetric) {
      case 0:
        return 'cm';
      case 1:
        return 'kg';
      case 2:
        return 'cm';
      default:
        return '';
    }
  }

  Widget _buildLegend() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildLegendItem('宝宝数据', _getMetricColor()),
          const SizedBox(width: 24),
          _buildLegendItem('WHO标准 (50%)', Colors.grey.shade400),
        ],
      ),
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 16,
          height: 3,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }
}

/// 成长曲线绘制器
class GrowthChartPainter extends CustomPainter {
  final List<GrowthCurvePoint> points;
  final Color color;
  final String unit;

  GrowthChartPainter({
    required this.points,
    required this.color,
    required this.unit,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final dotPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    final gridPaint = Paint()
      ..color = Colors.grey.withValues(alpha: 0.2)
      ..strokeWidth = 0.5;

    // 计算数据范围
    double minValue = points.map((p) => p.value).reduce((a, b) => a < b ? a : b);
    double maxValue = points.map((p) => p.value).reduce((a, b) => a > b ? a : b);

    // 增加一些padding
    final valueRange = maxValue - minValue;
    if (valueRange < 10) {
      minValue -= 5;
      maxValue += 5;
    } else {
      minValue -= valueRange * 0.1;
      maxValue += valueRange * 0.1;
    }

    final int minMonth = points.map((p) => p.ageMonths).reduce((a, b) => a < b ? a : b);
    final int maxMonth = points.map((p) => p.ageMonths).reduce((a, b) => a > b ? a : b);

    // 绘制网格线
    for (int i = 0; i <= 4; i++) {
      final y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // 绘制Y轴标签
    final textPainter = TextPainter(textDirection: TextDirection.ltr);
    for (int i = 0; i <= 4; i++) {
      final value = maxValue - (maxValue - minValue) * i / 4;
      textPainter.text = TextSpan(
        text: value.toStringAsFixed(0),
        style: TextStyle(color: Colors.grey.shade500, fontSize: 10),
      );
      textPainter.layout();
      textPainter.paint(canvas, Offset(0, size.height * i / 4 - 5));
    }

    // 绘制曲线
    final path = Path();
    for (int i = 0; i < points.length; i++) {
      final point = points[i];
      final x = (point.ageMonths - minMonth) / (maxMonth - minMonth + 1) * (size.width - 40) + 30;
      final y = size.height - (point.value - minValue) / (maxValue - minValue) * size.height;

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);

    // 绘制数据点
    for (final point in points) {
      final x = (point.ageMonths - minMonth) / (maxMonth - minMonth + 1) * (size.width - 40) + 30;
      final y = size.height - (point.value - minValue) / (maxValue - minValue) * size.height;
      canvas.drawCircle(Offset(x, y), 4, dotPaint);
      canvas.drawCircle(Offset(x, y), 2, Paint()..color = Colors.white);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
