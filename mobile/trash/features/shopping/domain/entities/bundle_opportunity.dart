import 'package:equatable/equatable.dart';
import 'product_recommendation.dart';

/// 凑单机会实体
class BundleOpportunity extends Equatable {
  final String couponName;           // 优惠券名称
  final double threshold;            // 门槛金额
  final double discount;             // 优惠金额
  final double currentTotal;         // 当前购物车总价
  final double gap;                  // 差额
  final double potentialSavings;     // 潜在节省
  final List<ProductRecommendation> suggestedItems; // 推荐商品列表
  final String? message;             // 提示信息
  final double roi;                  // 投资回报率

  const BundleOpportunity({
    required this.couponName,
    required this.threshold,
    required this.discount,
    required this.currentTotal,
    required this.gap,
    required this.potentialSavings,
    this.suggestedItems = const [],
    this.message,
    this.roi = 0.0,
  });

  /// 是否值得凑单（ROI > 50%）
  bool get isWorthIt => roi > 0.5;

  /// 距离门槛的百分比
  double get progressPercentage => (currentTotal / threshold).clamp(0.0, 1.0);

  /// 获取显示消息
  String get displayMessage {
    if (message != null) return message!;
    if (gap <= 0) {
      return '已满足满减条件！可省 ¥${discount.toStringAsFixed(0)}';
    }
    return '再买 ¥${gap.toStringAsFixed(0)} 可省 ¥${discount.toStringAsFixed(0)}';
  }

  /// 获取ROI显示
  String get roiDisplay {
    final roiPercent = (roi * 100).toStringAsFixed(0);
    return '$roiPercent%';
  }

  BundleOpportunity copyWith({
    String? couponName,
    double? threshold,
    double? discount,
    double? currentTotal,
    double? gap,
    double? potentialSavings,
    List<ProductRecommendation>? suggestedItems,
    String? message,
    double? roi,
  }) {
    return BundleOpportunity(
      couponName: couponName ?? this.couponName,
      threshold: threshold ?? this.threshold,
      discount: discount ?? this.discount,
      currentTotal: currentTotal ?? this.currentTotal,
      gap: gap ?? this.gap,
      potentialSavings: potentialSavings ?? this.potentialSavings,
      suggestedItems: suggestedItems ?? this.suggestedItems,
      message: message ?? this.message,
      roi: roi ?? this.roi,
    );
  }

  @override
  List<Object?> get props => [
    couponName, threshold, discount, currentTotal, gap,
    potentialSavings, suggestedItems, message, roi,
  ];
}
