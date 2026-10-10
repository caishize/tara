import 'package:equatable/equatable.dart';

/// Work history entity - Records member's work experience
class WorkHistory extends Equatable {
  final String id;
  final String memberId;
  final String familyId;
  final String companyName;     // 公司名称
  final String? position;       // 职位
  final String? department;     // 部门
  final String? startDate;      // 入职日期
  final String? endDate;        // 离职日期 (null=在职)
  final bool isCurrent;         // 是否当前工作
  final String? notes;          // 备注
  final String createdAt;
  final String updatedAt;

  const WorkHistory({
    required this.id,
    required this.memberId,
    required this.familyId,
    required this.companyName,
    this.position,
    this.department,
    this.startDate,
    this.endDate,
    this.isCurrent = false,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  @override
  List<Object?> get props => [
        id,
        memberId,
        familyId,
        companyName,
        position,
        department,
        startDate,
        endDate,
        isCurrent,
        notes,
        createdAt,
        updatedAt,
      ];

  /// Get display text for work period
  String get periodText {
    final start = startDate ?? '未知';
    final end = isCurrent ? '至今' : (endDate ?? '未知');
    return '$start - $end';
  }
}

/// Work history model with JSON serialization
class WorkHistoryModel extends WorkHistory {
  const WorkHistoryModel({
    required super.id,
    required super.memberId,
    required super.familyId,
    required super.companyName,
    super.position,
    super.department,
    super.startDate,
    super.endDate,
    super.isCurrent = false,
    super.notes,
    required super.createdAt,
    required super.updatedAt,
  });

  factory WorkHistoryModel.fromJson(Map<String, dynamic> json) {
    return WorkHistoryModel(
      id: json['id'] as String,
      memberId: json['member_id'] as String,
      familyId: json['family_id'] as String,
      companyName: json['company_name'] as String,
      position: json['position'] as String?,
      department: json['department'] as String?,
      startDate: json['start_date'] as String?,
      endDate: json['end_date'] as String?,
      isCurrent: json['is_current'] as bool? ?? false,
      notes: json['notes'] as String?,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'member_id': memberId,
      'family_id': familyId,
      'company_name': companyName,
      if (position != null) 'position': position,
      if (department != null) 'department': department,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      'is_current': isCurrent,
      if (notes != null) 'notes': notes,
      'created_at': createdAt,
      'updated_at': updatedAt,
    };
  }

  /// Create request body for API
  Map<String, dynamic> toCreateRequest() {
    return {
      'company_name': companyName,
      if (position != null) 'position': position,
      if (department != null) 'department': department,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      'is_current': isCurrent,
      if (notes != null) 'notes': notes,
    };
  }

  factory WorkHistoryModel.fromEntity(WorkHistory entity) {
    return WorkHistoryModel(
      id: entity.id,
      memberId: entity.memberId,
      familyId: entity.familyId,
      companyName: entity.companyName,
      position: entity.position,
      department: entity.department,
      startDate: entity.startDate,
      endDate: entity.endDate,
      isCurrent: entity.isCurrent,
      notes: entity.notes,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}
