import 'package:equatable/equatable.dart';

/// 成长记录类型
enum GrowthRecordType {
  height,           // 身高
  weight,           // 体重
  headCircumference, // 头围
}

/// 成长记录实体
class GrowthRecord extends Equatable {
  final String id;
  final String childId;
  final DateTime recordDate;
  final double? height;      // cm
  final double? weight;      // kg
  final double? headCircumference; // cm
  final String? notes;
  final String? photoUrl;    // 体检照片
  final String? location;    // 体检地点
  final DateTime createdAt;
  final DateTime updatedAt;

  const GrowthRecord({
    required this.id,
    required this.childId,
    required this.recordDate,
    this.height,
    this.weight,
    this.headCircumference,
    this.notes,
    this.photoUrl,
    this.location,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 是否有身高记录
  bool get hasHeight => height != null && height! > 0;

  /// 是否有体重记录
  bool get hasWeight => weight != null && weight! > 0;

  /// 是否有头围记录
  bool get hasHeadCircumference => headCircumference != null && headCircumference! > 0;

  /// 格式化身高显示
  String get heightDisplay => hasHeight ? '${height!.toStringAsFixed(1)} cm' : '-';

  /// 格式化体重显示
  String get weightDisplay => hasWeight ? '${weight!.toStringAsFixed(2)} kg' : '-';

  /// 格式化头围显示
  String get headCircumferenceDisplay => hasHeadCircumference ? '${headCircumference!.toStringAsFixed(1)} cm' : '-';

  GrowthRecord copyWith({
    String? id,
    String? childId,
    DateTime? recordDate,
    double? height,
    double? weight,
    double? headCircumference,
    String? notes,
    String? photoUrl,
    String? location,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return GrowthRecord(
      id: id ?? this.id,
      childId: childId ?? this.childId,
      recordDate: recordDate ?? this.recordDate,
      height: height ?? this.height,
      weight: weight ?? this.weight,
      headCircumference: headCircumference ?? this.headCircumference,
      notes: notes ?? this.notes,
      photoUrl: photoUrl ?? this.photoUrl,
      location: location ?? this.location,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, childId, recordDate, height, weight, headCircumference,
    notes, photoUrl, location, createdAt, updatedAt,
  ];
}

/// 成长曲线数据点
class GrowthCurvePoint extends Equatable {
  final DateTime date;
  final double value;
  final int ageMonths; // 月龄

  const GrowthCurvePoint({
    required this.date,
    required this.value,
    required this.ageMonths,
  });

  @override
  List<Object?> get props => [date, value, ageMonths];
}

/// 成长曲线数据
class GrowthCurveData extends Equatable {
  final String childId;
  final String childName;
  final DateTime birthDate;
  final List<GrowthRecord> records;
  final List<GrowthCurvePoint> heightCurve;
  final List<GrowthCurvePoint> weightCurve;
  final List<GrowthCurvePoint> headCircumferenceCurve;
  final List<WHOStandard>? whoStandards;

  const GrowthCurveData({
    required this.childId,
    required this.childName,
    required this.birthDate,
    required this.records,
    required this.heightCurve,
    required this.weightCurve,
    required this.headCircumferenceCurve,
    this.whoStandards,
  });

  /// 计算当前月龄
  int get currentAgeMonths {
    final now = DateTime.now();
    return (now.year - birthDate.year) * 12 + (now.month - birthDate.month);
  }

  /// 计算当前年龄显示
  String get ageDisplay {
    final months = currentAgeMonths;
    if (months < 12) {
      return '$months个月';
    } else {
      final years = months ~/ 12;
      final remainingMonths = months % 12;
      if (remainingMonths == 0) {
        return '$years岁';
      }
      return '$years岁$remainingMonths个月';
    }
  }

  /// 获取最新身高
  double? get latestHeight {
    final heightRecords = records.where((r) => r.hasHeight).toList();
    if (heightRecords.isEmpty) return null;
    heightRecords.sort((a, b) => b.recordDate.compareTo(a.recordDate));
    return heightRecords.first.height;
  }

  /// 获取最新体重
  double? get latestWeight {
    final weightRecords = records.where((r) => r.hasWeight).toList();
    if (weightRecords.isEmpty) return null;
    weightRecords.sort((a, b) => b.recordDate.compareTo(a.recordDate));
    return weightRecords.first.weight;
  }

  @override
  List<Object?> get props => [
    childId, childName, birthDate, records,
    heightCurve, weightCurve, headCircumferenceCurve, whoStandards,
  ];
}

/// WHO生长标准数据
class WHOStandard extends Equatable {
  final int ageMonths;
  final double? heightP3;   // 3%分位
  final double? heightP50;  // 50%分位（中位数）
  final double? heightP97;  // 97%分位
  final double? weightP3;
  final double? weightP50;
  final double? weightP97;
  final double? headP3;
  final double? headP50;
  final double? headP97;

  const WHOStandard({
    required this.ageMonths,
    this.heightP3,
    this.heightP50,
    this.heightP97,
    this.weightP3,
    this.weightP50,
    this.weightP97,
    this.headP3,
    this.headP50,
    this.headP97,
  });

  @override
  List<Object?> get props => [
    ageMonths, heightP3, heightP50, heightP97,
    weightP3, weightP50, weightP97, headP3, headP50, headP97,
  ];
}
