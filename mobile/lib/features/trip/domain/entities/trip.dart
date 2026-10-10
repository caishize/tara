import 'package:equatable/equatable.dart';

/// 顶层分类
enum TripCategory {
  personal,   // 个人出行
  business,   // 公务差旅
}

/// 旅行类型 (子分类)
enum TripType {
  // 个人出行
  leisure,      // 休闲游
  family,       // 亲子游
  visit,        // 探亲访友
  // 公务差旅
  businessTrip, // 商务出差
  conference,   // 会议培训
  clientVisit,  // 客户拜访
  // 通用
  other,        // 其他
}

/// 旅行状态
enum TripStatus {
  planning,     // 规划中
  confirmed,    // 已确认
  inProgress,   // 进行中
  completed,    // 已完成
  cancelled,    // 已取消
}

/// 旅行计划实体
class Trip extends Equatable {
  final String id;
  final String familyId;
  final String? tripName;
  final String destination;
  final DateTime startDate;
  final DateTime endDate;
  final TripCategory category;
  final TripType tripType;
  final double? budget;
  final double actualExpense;
  final List<String> participants;
  final TripStatus status;
  final String? notes;
  final Map<String, dynamic>? recommendationContext;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Trip({
    required this.id,
    required this.familyId,
    this.tripName,
    required this.destination,
    required this.startDate,
    required this.endDate,
    this.category = TripCategory.personal,
    this.tripType = TripType.leisure,
    this.budget,
    this.actualExpense = 0,
    this.participants = const [],
    this.status = TripStatus.planning,
    this.notes,
    this.recommendationContext,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 旅行天数
  int get durationDays => endDate.difference(startDate).inDays + 1;

  /// 预算使用百分比
  double? get budgetUsedPercentage {
    if (budget == null || budget == 0) return null;
    return (actualExpense / budget!) * 100;
  }

  /// 剩余预算
  double? get remainingBudget {
    if (budget == null) return null;
    return budget! - actualExpense;
  }

  /// 是否超预算
  bool get isOverBudget => remainingBudget != null && remainingBudget! < 0;

  /// 分类显示名称
  String get categoryName {
    switch (category) {
      case TripCategory.personal:
        return '个人出行';
      case TripCategory.business:
        return '公务差旅';
    }
  }

  /// 分类图标
  String get categoryIcon {
    switch (category) {
      case TripCategory.personal:
        return '🧳';
      case TripCategory.business:
        return '💼';
    }
  }

  /// 旅行类型显示名称
  String get tripTypeName {
    switch (tripType) {
      case TripType.leisure:
        return '休闲游';
      case TripType.family:
        return '亲子游';
      case TripType.visit:
        return '探亲访友';
      case TripType.businessTrip:
        return '商务出差';
      case TripType.conference:
        return '会议培训';
      case TripType.clientVisit:
        return '客户拜访';
      case TripType.other:
        return '其他';
    }
  }

  /// 旅行类型图标
  String get tripTypeIcon {
    switch (tripType) {
      case TripType.leisure:
        return '🏖️';
      case TripType.family:
        return '👨‍👩‍👧‍👦';
      case TripType.visit:
        return '🏠';
      case TripType.businessTrip:
        return '💼';
      case TripType.conference:
        return '📋';
      case TripType.clientVisit:
        return '🤝';
      case TripType.other:
        return '📍';
    }
  }

  /// 状态显示名称
  String get statusName {
    switch (status) {
      case TripStatus.planning:
        return '规划中';
      case TripStatus.confirmed:
        return '已确认';
      case TripStatus.inProgress:
        return '进行中';
      case TripStatus.completed:
        return '已完成';
      case TripStatus.cancelled:
        return '已取消';
    }
  }

  /// 状态颜色（返回颜色代码）
  int get statusColorValue {
    switch (status) {
      case TripStatus.planning:
        return 0xFFFFA726; // Orange
      case TripStatus.confirmed:
        return 0xFF42A5F5; // Blue
      case TripStatus.inProgress:
        return 0xFF66BB6A; // Green
      case TripStatus.completed:
        return 0xFF9E9E9E; // Grey
      case TripStatus.cancelled:
        return 0xFFEF5350; // Red
    }
  }

  /// 获取分类下的旅行类型列表
  static List<TripType> getTypesForCategory(TripCategory category) {
    switch (category) {
      case TripCategory.personal:
        return [
          TripType.leisure,
          TripType.family,
          TripType.visit,
          TripType.other,
        ];
      case TripCategory.business:
        return [
          TripType.businessTrip,
          TripType.conference,
          TripType.clientVisit,
          TripType.other,
        ];
    }
  }

  /// 根据类型获取所属分类
  static TripCategory getCategoryForType(TripType type) {
    switch (type) {
      case TripType.leisure:
      case TripType.family:
      case TripType.visit:
        return TripCategory.personal;
      case TripType.businessTrip:
      case TripType.conference:
      case TripType.clientVisit:
        return TripCategory.business;
      case TripType.other:
        return TripCategory.personal; // 默认归类为个人出行
    }
  }

  Trip copyWith({
    String? id,
    String? familyId,
    String? tripName,
    String? destination,
    DateTime? startDate,
    DateTime? endDate,
    TripCategory? category,
    TripType? tripType,
    double? budget,
    double? actualExpense,
    List<String>? participants,
    TripStatus? status,
    String? notes,
    Map<String, dynamic>? recommendationContext,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Trip(
      id: id ?? this.id,
      familyId: familyId ?? this.familyId,
      tripName: tripName ?? this.tripName,
      destination: destination ?? this.destination,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      category: category ?? this.category,
      tripType: tripType ?? this.tripType,
      budget: budget ?? this.budget,
      actualExpense: actualExpense ?? this.actualExpense,
      participants: participants ?? this.participants,
      status: status ?? this.status,
      notes: notes ?? this.notes,
      recommendationContext: recommendationContext ?? this.recommendationContext,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, familyId, tripName, destination, startDate, endDate,
    category, tripType, budget, actualExpense, participants, status,
    notes, recommendationContext, createdAt, updatedAt,
  ];
}
