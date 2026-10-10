import 'package:equatable/equatable.dart';

/// Professional relation type enum
enum ProfessionalRelationType {
  boss('boss', '上级'),
  subordinate('subordinate', '下属'),
  peer('peer', '同事'),
  mentor('mentor', '导师'),
  mentee('mentee', '学员'),
  client('client', '客户'),
  vendor('vendor', '供应商'),
  partner('partner', '合作伙伴'),
  other('other', '其他');

  final String value;
  final String label;

  const ProfessionalRelationType(this.value, this.label);

  static ProfessionalRelationType fromValue(String value) {
    return ProfessionalRelationType.values.firstWhere(
      (type) => type.value == value,
      orElse: () => ProfessionalRelationType.other,
    );
  }

  /// Get the inverse relation type (for perspective switching)
  ProfessionalRelationType get inverse {
    switch (this) {
      case ProfessionalRelationType.boss:
        return ProfessionalRelationType.subordinate;
      case ProfessionalRelationType.subordinate:
        return ProfessionalRelationType.boss;
      case ProfessionalRelationType.mentor:
        return ProfessionalRelationType.mentee;
      case ProfessionalRelationType.mentee:
        return ProfessionalRelationType.mentor;
      case ProfessionalRelationType.client:
        return ProfessionalRelationType.vendor;
      case ProfessionalRelationType.vendor:
        return ProfessionalRelationType.client;
      case ProfessionalRelationType.peer:
      case ProfessionalRelationType.partner:
      case ProfessionalRelationType.other:
        return this; // Symmetric relations stay the same
    }
  }
}

/// Professional relation entity - Records professional relationships between members
class ProfessionalRelation extends Equatable {
  final String id;
  final String familyId;
  final String fromMemberId;    // "我"
  final String toMemberId;      // 对方成员
  final String relationType;    // 职业关系类型
  final String relationTypeLabel; // 职业关系显示文本
  final String? companyName;    // 共事公司
  final String? startDate;      // 关系开始时间
  final String? endDate;        // 关系结束时间
  final bool isCurrent;         // 是否当前关系
  final String? notes;          // 备注
  final String? fromMemberName; // 发起方名称
  final String? toMemberName;   // 目标方名称
  final String createdAt;
  final String updatedAt;

  const ProfessionalRelation({
    required this.id,
    required this.familyId,
    required this.fromMemberId,
    required this.toMemberId,
    required this.relationType,
    required this.relationTypeLabel,
    this.companyName,
    this.startDate,
    this.endDate,
    this.isCurrent = true,
    this.notes,
    this.fromMemberName,
    this.toMemberName,
    required this.createdAt,
    required this.updatedAt,
  });

  @override
  List<Object?> get props => [
        id,
        familyId,
        fromMemberId,
        toMemberId,
        relationType,
        relationTypeLabel,
        companyName,
        startDate,
        endDate,
        isCurrent,
        notes,
        fromMemberName,
        toMemberName,
        createdAt,
        updatedAt,
      ];

  /// Get display text for relation with time context
  String get displayText {
    final prefix = isCurrent ? '' : '前';
    return '$prefix$relationTypeLabel';
  }

  /// Get display text from a specific member's perspective
  ///
  /// When [viewingMemberId] is the `toMemberId`, the relation type is inverted.
  /// For example: if relation is "subordinate" and we're viewing from the subordinate's
  /// perspective, it should show "上级" instead of "下属".
  String getDisplayTextForMember(String viewingMemberId) {
    final prefix = isCurrent ? '' : '前';

    // If viewing from the "to" member's perspective, invert the relation
    if (viewingMemberId == toMemberId) {
      final type = ProfessionalRelationType.fromValue(relationType);
      final invertedType = type.inverse;
      return '$prefix${invertedType.label}';
    }

    // If viewing from the "from" member's perspective, use original label
    return '$prefix$relationTypeLabel';
  }

  /// Get full display text including company
  String get fullDisplayText {
    if (companyName != null && companyName!.isNotEmpty) {
      return '$displayText (@ $companyName)';
    }
    return displayText;
  }
}

/// Professional relation model with JSON serialization
class ProfessionalRelationModel extends ProfessionalRelation {
  const ProfessionalRelationModel({
    required super.id,
    required super.familyId,
    required super.fromMemberId,
    required super.toMemberId,
    required super.relationType,
    required super.relationTypeLabel,
    super.companyName,
    super.startDate,
    super.endDate,
    super.isCurrent = true,
    super.notes,
    super.fromMemberName,
    super.toMemberName,
    required super.createdAt,
    required super.updatedAt,
  });

  factory ProfessionalRelationModel.fromJson(Map<String, dynamic> json) {
    return ProfessionalRelationModel(
      id: json['id'] as String,
      familyId: json['family_id'] as String,
      fromMemberId: json['from_member_id'] as String,
      toMemberId: json['to_member_id'] as String,
      relationType: json['relation_type'] as String,
      relationTypeLabel: json['relation_type_label'] as String? ?? '其他',
      companyName: json['company_name'] as String?,
      startDate: json['start_date'] as String?,
      endDate: json['end_date'] as String?,
      isCurrent: json['is_current'] as bool? ?? true,
      notes: json['notes'] as String?,
      fromMemberName: json['from_member_name'] as String?,
      toMemberName: json['to_member_name'] as String?,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'family_id': familyId,
      'from_member_id': fromMemberId,
      'to_member_id': toMemberId,
      'relation_type': relationType,
      'relation_type_label': relationTypeLabel,
      if (companyName != null) 'company_name': companyName,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      'is_current': isCurrent,
      if (notes != null) 'notes': notes,
      if (fromMemberName != null) 'from_member_name': fromMemberName,
      if (toMemberName != null) 'to_member_name': toMemberName,
      'created_at': createdAt,
      'updated_at': updatedAt,
    };
  }

  /// Create request body for API
  Map<String, dynamic> toCreateRequest() {
    return {
      'from_member_id': fromMemberId,
      'to_member_id': toMemberId,
      'relation_type': relationType,
      if (companyName != null) 'company_name': companyName,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      'is_current': isCurrent,
      if (notes != null) 'notes': notes,
    };
  }

  factory ProfessionalRelationModel.fromEntity(ProfessionalRelation entity) {
    return ProfessionalRelationModel(
      id: entity.id,
      familyId: entity.familyId,
      fromMemberId: entity.fromMemberId,
      toMemberId: entity.toMemberId,
      relationType: entity.relationType,
      relationTypeLabel: entity.relationTypeLabel,
      companyName: entity.companyName,
      startDate: entity.startDate,
      endDate: entity.endDate,
      isCurrent: entity.isCurrent,
      notes: entity.notes,
      fromMemberName: entity.fromMemberName,
      toMemberName: entity.toMemberName,
      createdAt: entity.createdAt,
      updatedAt: entity.updatedAt,
    );
  }
}
