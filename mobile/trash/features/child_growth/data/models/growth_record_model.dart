import '../../domain/entities/growth_record.dart';

/// 成长记录数据模型
class GrowthRecordModel extends GrowthRecord {
  const GrowthRecordModel({
    required super.id,
    required super.childId,
    required super.recordDate,
    super.height,
    super.weight,
    super.headCircumference,
    super.notes,
    super.photoUrl,
    super.location,
    required super.createdAt,
    required super.updatedAt,
  });

  factory GrowthRecordModel.fromJson(Map<String, dynamic> json) {
    return GrowthRecordModel(
      id: json['id'] as String? ?? '',
      childId: json['child_id'] as String? ?? '',
      recordDate: DateTime.parse(json['record_date'] as String? ?? DateTime.now().toIso8601String()),
      height: _parseDouble(json['height']),
      weight: _parseDouble(json['weight']),
      headCircumference: _parseDouble(json['head_circumference']),
      notes: json['notes'] as String?,
      photoUrl: json['photo_url'] as String?,
      location: json['location'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String? ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(json['updated_at'] as String? ?? DateTime.now().toIso8601String()),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'child_id': childId,
      'record_date': recordDate.toIso8601String().split('T').first,
      if (height != null) 'height': height,
      if (weight != null) 'weight': weight,
      if (headCircumference != null) 'head_circumference': headCircumference,
      if (notes != null) 'notes': notes,
      if (photoUrl != null) 'photo_url': photoUrl,
      if (location != null) 'location': location,
    };
  }

  factory GrowthRecordModel.fromEntity(GrowthRecord entity) {
    return GrowthRecordModel(
      id: entity.id,
      childId: entity.childId,
      recordDate: entity.recordDate,
      height: entity.height,
      weight: entity.weight,
      headCircumference: entity.headCircumference,
      notes: entity.notes,
      photoUrl: entity.photoUrl,
      location: entity.location,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}

/// 成长曲线数据模型
class GrowthCurveDataModel extends GrowthCurveData {
  const GrowthCurveDataModel({
    required super.childId,
    required super.childName,
    required super.birthDate,
    required super.records,
    required super.heightCurve,
    required super.weightCurve,
    required super.headCircumferenceCurve,
    super.whoStandards,
  });

  factory GrowthCurveDataModel.fromJson(Map<String, dynamic> json) {
    final records = (json['records'] as List<dynamic>? ?? [])
        .map((e) => GrowthRecordModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // 解析身高曲线
    final heightCurve = (json['height_curve'] as List<dynamic>? ?? [])
        .map((e) => GrowthCurvePointModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // 解析体重曲线
    final weightCurve = (json['weight_curve'] as List<dynamic>? ?? [])
        .map((e) => GrowthCurvePointModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // 解析头围曲线
    final headCurve = (json['head_circumference_curve'] as List<dynamic>? ?? [])
        .map((e) => GrowthCurvePointModel.fromJson(e as Map<String, dynamic>))
        .toList();

    // 解析WHO标准
    final whoStandards = json['who_standards'] != null
        ? (json['who_standards'] as List<dynamic>)
            .map((e) => WHOStandardModel.fromJson(e as Map<String, dynamic>))
            .toList()
        : null;

    return GrowthCurveDataModel(
      childId: json['child_id'] as String? ?? '',
      childName: json['child_name'] as String? ?? '',
      birthDate: DateTime.parse(json['birth_date'] as String? ?? DateTime.now().toIso8601String()),
      records: records,
      heightCurve: heightCurve,
      weightCurve: weightCurve,
      headCircumferenceCurve: headCurve,
      whoStandards: whoStandards,
    );
  }
}

/// 成长曲线数据点模型
class GrowthCurvePointModel extends GrowthCurvePoint {
  const GrowthCurvePointModel({
    required super.date,
    required super.value,
    required super.ageMonths,
  });

  factory GrowthCurvePointModel.fromJson(Map<String, dynamic> json) {
    return GrowthCurvePointModel(
      date: DateTime.parse(json['date'] as String? ?? DateTime.now().toIso8601String()),
      value: _parseDouble(json['value']) ?? 0,
      ageMonths: _parseInt(json['age_months']) ?? 0,
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}

/// WHO标准数据模型
class WHOStandardModel extends WHOStandard {
  const WHOStandardModel({
    required super.ageMonths,
    super.heightP3,
    super.heightP50,
    super.heightP97,
    super.weightP3,
    super.weightP50,
    super.weightP97,
    super.headP3,
    super.headP50,
    super.headP97,
  });

  factory WHOStandardModel.fromJson(Map<String, dynamic> json) {
    return WHOStandardModel(
      ageMonths: _parseInt(json['age_months']) ?? 0,
      heightP3: _parseDouble(json['height_p3']),
      heightP50: _parseDouble(json['height_p50']),
      heightP97: _parseDouble(json['height_p97']),
      weightP3: _parseDouble(json['weight_p3']),
      weightP50: _parseDouble(json['weight_p50']),
      weightP97: _parseDouble(json['weight_p97']),
      headP3: _parseDouble(json['head_p3']),
      headP50: _parseDouble(json['head_p50']),
      headP97: _parseDouble(json['head_p97']),
    );
  }

  /// Parse a value that could be String or num to double
  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  /// Parse a value that could be String or num to int
  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }
}
