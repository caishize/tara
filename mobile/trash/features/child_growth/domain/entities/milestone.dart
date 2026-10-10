import 'package:equatable/equatable.dart';

/// 里程碑类型
enum MilestoneType {
  physical,   // 运动发育
  cognitive,  // 认知发育
  language,   // 语言发育
  social,     // 社交发育
  emotional,  // 情感发育
}

/// 发育里程碑实体
class Milestone extends Equatable {
  final String id;
  final String childId;
  final MilestoneType type;
  final String title;           // 里程碑名称，如"第一次微笑"
  final String? description;
  final DateTime achievedDate;
  final int? ageMonths;         // 达成时的月龄
  final bool? isTypical;        // 是否在正常发育范围
  final int? typicalAgeMin;     // 正常发育范围最小月龄
  final int? typicalAgeMax;     // 正常发育范围最大月龄
  final String? photoUrl;       // 纪念照片
  final String? videoUrl;       // 纪念视频
  final String? notes;
  final DateTime createdAt;

  const Milestone({
    required this.id,
    required this.childId,
    required this.type,
    required this.title,
    this.description,
    required this.achievedDate,
    this.ageMonths,
    this.isTypical,
    this.typicalAgeMin,
    this.typicalAgeMax,
    this.photoUrl,
    this.videoUrl,
    this.notes,
    required this.createdAt,
  });

  /// 获取类型显示名称
  String get typeName {
    switch (type) {
      case MilestoneType.physical:
        return '运动发育';
      case MilestoneType.cognitive:
        return '认知发育';
      case MilestoneType.language:
        return '语言发育';
      case MilestoneType.social:
        return '社交发育';
      case MilestoneType.emotional:
        return '情感发育';
    }
  }

  /// 获取类型图标
  String get typeIcon {
    switch (type) {
      case MilestoneType.physical:
        return '🏃';
      case MilestoneType.cognitive:
        return '🧠';
      case MilestoneType.language:
        return '🗣️';
      case MilestoneType.social:
        return '👋';
      case MilestoneType.emotional:
        return '💕';
    }
  }

  /// 获取类型颜色值（用于UI显示）
  int get typeColorValue {
    switch (type) {
      case MilestoneType.physical:
        return 0xFF4CAF50; // 绿色
      case MilestoneType.cognitive:
        return 0xFF2196F3; // 蓝色
      case MilestoneType.language:
        return 0xFFFF9800; // 橙色
      case MilestoneType.social:
        return 0xFF9C27B0; // 紫色
      case MilestoneType.emotional:
        return 0xFFE91E63; // 粉色
    }
  }

  /// 发育状态描述
  String get developmentStatus {
    if (isTypical == null || typicalAgeMin == null || typicalAgeMax == null || ageMonths == null) {
      return '已达成';
    }
    if (ageMonths! < typicalAgeMin!) {
      return '提前发育';
    } else if (ageMonths! > typicalAgeMax!) {
      return '稍晚发育';
    } else {
      return '正常发育';
    }
  }

  /// 月龄显示
  String get ageDisplay {
    if (ageMonths == null) return '';
    if (ageMonths! < 12) {
      return '$ageMonths个月';
    } else {
      final years = ageMonths! ~/ 12;
      final months = ageMonths! % 12;
      if (months == 0) {
        return '$years岁';
      }
      return '$years岁$months个月';
    }
  }

  Milestone copyWith({
    String? id,
    String? childId,
    MilestoneType? type,
    String? title,
    String? description,
    DateTime? achievedDate,
    int? ageMonths,
    bool? isTypical,
    int? typicalAgeMin,
    int? typicalAgeMax,
    String? photoUrl,
    String? videoUrl,
    String? notes,
    DateTime? createdAt,
  }) {
    return Milestone(
      id: id ?? this.id,
      childId: childId ?? this.childId,
      type: type ?? this.type,
      title: title ?? this.title,
      description: description ?? this.description,
      achievedDate: achievedDate ?? this.achievedDate,
      ageMonths: ageMonths ?? this.ageMonths,
      isTypical: isTypical ?? this.isTypical,
      typicalAgeMin: typicalAgeMin ?? this.typicalAgeMin,
      typicalAgeMax: typicalAgeMax ?? this.typicalAgeMax,
      photoUrl: photoUrl ?? this.photoUrl,
      videoUrl: videoUrl ?? this.videoUrl,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  List<Object?> get props => [
    id, childId, type, title, description, achievedDate,
    ageMonths, isTypical, typicalAgeMin, typicalAgeMax,
    photoUrl, videoUrl, notes, createdAt,
  ];
}

/// 里程碑模板 - 预定义的常见里程碑
class MilestoneTemplate {
  final String title;
  final String description;
  final MilestoneType type;
  final int typicalAgeMin;  // 月龄
  final int typicalAgeMax;  // 月龄

  const MilestoneTemplate({
    required this.title,
    required this.description,
    required this.type,
    required this.typicalAgeMin,
    required this.typicalAgeMax,
  });

  /// 常见里程碑模板列表
  static const List<MilestoneTemplate> templates = [
    // 运动发育
    MilestoneTemplate(
      title: '抬头',
      description: '宝宝能够独立抬起头部',
      type: MilestoneType.physical,
      typicalAgeMin: 1,
      typicalAgeMax: 3,
    ),
    MilestoneTemplate(
      title: '翻身',
      description: '宝宝能够自己翻身',
      type: MilestoneType.physical,
      typicalAgeMin: 3,
      typicalAgeMax: 6,
    ),
    MilestoneTemplate(
      title: '独坐',
      description: '宝宝能够独立坐稳',
      type: MilestoneType.physical,
      typicalAgeMin: 5,
      typicalAgeMax: 8,
    ),
    MilestoneTemplate(
      title: '爬行',
      description: '宝宝开始爬行',
      type: MilestoneType.physical,
      typicalAgeMin: 6,
      typicalAgeMax: 10,
    ),
    MilestoneTemplate(
      title: '扶站',
      description: '宝宝能够扶着东西站立',
      type: MilestoneType.physical,
      typicalAgeMin: 8,
      typicalAgeMax: 12,
    ),
    MilestoneTemplate(
      title: '独立行走',
      description: '宝宝能够独立行走',
      type: MilestoneType.physical,
      typicalAgeMin: 10,
      typicalAgeMax: 15,
    ),
    // 语言发育
    MilestoneTemplate(
      title: '第一次发声',
      description: '宝宝发出第一声咿呀',
      type: MilestoneType.language,
      typicalAgeMin: 1,
      typicalAgeMax: 3,
    ),
    MilestoneTemplate(
      title: '咿呀学语',
      description: '宝宝开始有节奏的咿呀发声',
      type: MilestoneType.language,
      typicalAgeMin: 4,
      typicalAgeMax: 7,
    ),
    MilestoneTemplate(
      title: '叫爸爸妈妈',
      description: '宝宝第一次有意识叫爸爸或妈妈',
      type: MilestoneType.language,
      typicalAgeMin: 10,
      typicalAgeMax: 14,
    ),
    MilestoneTemplate(
      title: '说第一个词',
      description: '宝宝说出除爸妈外的第一个词',
      type: MilestoneType.language,
      typicalAgeMin: 11,
      typicalAgeMax: 18,
    ),
    // 认知发育
    MilestoneTemplate(
      title: '追视物体',
      description: '宝宝眼睛能够追随移动的物体',
      type: MilestoneType.cognitive,
      typicalAgeMin: 1,
      typicalAgeMax: 3,
    ),
    MilestoneTemplate(
      title: '认识家人',
      description: '宝宝能够分辨熟悉的家人',
      type: MilestoneType.cognitive,
      typicalAgeMin: 3,
      typicalAgeMax: 6,
    ),
    MilestoneTemplate(
      title: '找藏起的玩具',
      description: '宝宝能找到被藏起来的玩具',
      type: MilestoneType.cognitive,
      typicalAgeMin: 8,
      typicalAgeMax: 12,
    ),
    // 社交发育
    MilestoneTemplate(
      title: '社交性微笑',
      description: '宝宝看到人会微笑',
      type: MilestoneType.social,
      typicalAgeMin: 1,
      typicalAgeMax: 3,
    ),
    MilestoneTemplate(
      title: '认生',
      description: '宝宝开始对陌生人有反应',
      type: MilestoneType.social,
      typicalAgeMin: 6,
      typicalAgeMax: 10,
    ),
    MilestoneTemplate(
      title: '挥手再见',
      description: '宝宝学会挥手表示再见',
      type: MilestoneType.social,
      typicalAgeMin: 9,
      typicalAgeMax: 14,
    ),
    // 情感发育
    MilestoneTemplate(
      title: '第一次大笑',
      description: '宝宝第一次开怀大笑',
      type: MilestoneType.emotional,
      typicalAgeMin: 3,
      typicalAgeMax: 5,
    ),
    MilestoneTemplate(
      title: '表达喜好',
      description: '宝宝能表达对玩具或食物的喜好',
      type: MilestoneType.emotional,
      typicalAgeMin: 8,
      typicalAgeMax: 12,
    ),
  ];

  /// 根据类型筛选模板
  static List<MilestoneTemplate> getByType(MilestoneType type) {
    return templates.where((t) => t.type == type).toList();
  }

  /// 根据月龄获取即将到达的里程碑
  static List<MilestoneTemplate> getUpcoming(int currentAgeMonths, {int limit = 5}) {
    return templates
        .where((t) => t.typicalAgeMin >= currentAgeMonths - 2 && t.typicalAgeMin <= currentAgeMonths + 6)
        .take(limit)
        .toList();
  }
}
