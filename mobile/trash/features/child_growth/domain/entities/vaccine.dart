import 'package:equatable/equatable.dart';

/// 疫苗状态
enum VaccineStatus {
  scheduled,  // 待接种
  completed,  // 已完成
  overdue,    // 已过期
  skipped,    // 已跳过
}

/// 疫苗记录实体
class VaccineRecord extends Equatable {
  final String id;
  final String childId;
  final String vaccineName;
  final int doseNumber;         // 第几针
  final DateTime scheduledDate;
  final DateTime? actualDate;   // 实际接种日期
  final VaccineStatus status;
  final String? location;       // 接种地点
  final String? batchNumber;    // 批次号
  final String? certificateUrl; // 接种证明照片
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  const VaccineRecord({
    required this.id,
    required this.childId,
    required this.vaccineName,
    required this.doseNumber,
    required this.scheduledDate,
    this.actualDate,
    required this.status,
    this.location,
    this.batchNumber,
    this.certificateUrl,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  /// 是否已完成
  bool get isCompleted => status == VaccineStatus.completed;

  /// 是否待接种
  bool get isScheduled => status == VaccineStatus.scheduled;

  /// 是否已过期
  bool get isOverdue => status == VaccineStatus.overdue;

  /// 获取状态显示名称
  String get statusName {
    switch (status) {
      case VaccineStatus.scheduled:
        return '待接种';
      case VaccineStatus.completed:
        return '已完成';
      case VaccineStatus.overdue:
        return '已过期';
      case VaccineStatus.skipped:
        return '已跳过';
    }
  }

  /// 获取状态图标
  String get statusIcon {
    switch (status) {
      case VaccineStatus.scheduled:
        return '📅';
      case VaccineStatus.completed:
        return '✅';
      case VaccineStatus.overdue:
        return '⚠️';
      case VaccineStatus.skipped:
        return '⏭️';
    }
  }

  /// 获取状态颜色值
  int get statusColorValue {
    switch (status) {
      case VaccineStatus.scheduled:
        return 0xFF2196F3; // 蓝色
      case VaccineStatus.completed:
        return 0xFF4CAF50; // 绿色
      case VaccineStatus.overdue:
        return 0xFFF44336; // 红色
      case VaccineStatus.skipped:
        return 0xFF9E9E9E; // 灰色
    }
  }

  /// 剩余天数（负数表示已过期）
  int get daysUntil {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final scheduled = DateTime(scheduledDate.year, scheduledDate.month, scheduledDate.day);
    return scheduled.difference(today).inDays;
  }

  /// 剩余天数显示
  String get daysUntilDisplay {
    final days = daysUntil;
    if (isCompleted) return '已完成';
    if (days == 0) return '今天';
    if (days == 1) return '明天';
    if (days < 0) return '已过期${-days}天';
    if (days <= 7) return '$days天后';
    if (days <= 30) return '${(days / 7).ceil()}周后';
    return '${(days / 30).ceil()}个月后';
  }

  /// 完整疫苗名称（包含针次）
  String get fullName => '$vaccineName (第$doseNumber针)';

  VaccineRecord copyWith({
    String? id,
    String? childId,
    String? vaccineName,
    int? doseNumber,
    DateTime? scheduledDate,
    DateTime? actualDate,
    VaccineStatus? status,
    String? location,
    String? batchNumber,
    String? certificateUrl,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return VaccineRecord(
      id: id ?? this.id,
      childId: childId ?? this.childId,
      vaccineName: vaccineName ?? this.vaccineName,
      doseNumber: doseNumber ?? this.doseNumber,
      scheduledDate: scheduledDate ?? this.scheduledDate,
      actualDate: actualDate ?? this.actualDate,
      status: status ?? this.status,
      location: location ?? this.location,
      batchNumber: batchNumber ?? this.batchNumber,
      certificateUrl: certificateUrl ?? this.certificateUrl,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
    id, childId, vaccineName, doseNumber, scheduledDate, actualDate,
    status, location, batchNumber, certificateUrl, notes, createdAt, updatedAt,
  ];
}

/// 疫苗信息模板 - 中国标准疫苗接种计划
class VaccineTemplate {
  final String name;
  final String description;
  final List<int> scheduledAgeMonths; // 各针次的建议接种月龄
  final bool isFree;  // 是否免费（一类疫苗）

  const VaccineTemplate({
    required this.name,
    required this.description,
    required this.scheduledAgeMonths,
    required this.isFree,
  });

  /// 中国标准一类疫苗（免费）
  static const List<VaccineTemplate> freeVaccines = [
    VaccineTemplate(
      name: '乙肝疫苗',
      description: '预防乙型肝炎',
      scheduledAgeMonths: [0, 1, 6],  // 出生、1月龄、6月龄
      isFree: true,
    ),
    VaccineTemplate(
      name: '卡介苗',
      description: '预防结核病',
      scheduledAgeMonths: [0],
      isFree: true,
    ),
    VaccineTemplate(
      name: '脊灰疫苗',
      description: '预防脊髓灰质炎',
      scheduledAgeMonths: [2, 3, 4, 48],  // 2、3、4月龄，4岁
      isFree: true,
    ),
    VaccineTemplate(
      name: '百白破疫苗',
      description: '预防百日咳、白喉、破伤风',
      scheduledAgeMonths: [3, 4, 5, 18, 72],  // 3、4、5月龄，18月龄，6岁
      isFree: true,
    ),
    VaccineTemplate(
      name: '麻腮风疫苗',
      description: '预防麻疹、腮腺炎、风疹',
      scheduledAgeMonths: [8, 18],  // 8月龄、18月龄
      isFree: true,
    ),
    VaccineTemplate(
      name: '乙脑疫苗',
      description: '预防流行性乙型脑炎',
      scheduledAgeMonths: [8, 24, 72],  // 8月龄、2岁、6岁
      isFree: true,
    ),
    VaccineTemplate(
      name: 'A群流脑疫苗',
      description: '预防A群流行性脑脊髓膜炎',
      scheduledAgeMonths: [6, 9],  // 6、9月龄
      isFree: true,
    ),
    VaccineTemplate(
      name: 'A+C群流脑疫苗',
      description: '预防A+C群流行性脑脊髓膜炎',
      scheduledAgeMonths: [36, 72],  // 3岁、6岁
      isFree: true,
    ),
    VaccineTemplate(
      name: '甲肝疫苗',
      description: '预防甲型肝炎',
      scheduledAgeMonths: [18, 24],  // 18月龄、24月龄
      isFree: true,
    ),
  ];

  /// 常见二类疫苗（自费）
  static const List<VaccineTemplate> paidVaccines = [
    VaccineTemplate(
      name: '水痘疫苗',
      description: '预防水痘',
      scheduledAgeMonths: [12, 48],  // 1岁、4岁
      isFree: false,
    ),
    VaccineTemplate(
      name: '手足口疫苗',
      description: '预防手足口病',
      scheduledAgeMonths: [6, 7],  // 6、7月龄
      isFree: false,
    ),
    VaccineTemplate(
      name: '流感疫苗',
      description: '预防流行性感冒，每年接种',
      scheduledAgeMonths: [6],  // 6月龄起每年
      isFree: false,
    ),
    VaccineTemplate(
      name: '肺炎疫苗',
      description: '预防肺炎球菌感染',
      scheduledAgeMonths: [2, 4, 6, 12],  // 2、4、6、12月龄
      isFree: false,
    ),
    VaccineTemplate(
      name: '轮状病毒疫苗',
      description: '预防轮状病毒腹泻',
      scheduledAgeMonths: [2, 4, 6],  // 2、4、6月龄
      isFree: false,
    ),
    VaccineTemplate(
      name: 'Hib疫苗',
      description: '预防b型流感嗜血杆菌感染',
      scheduledAgeMonths: [2, 4, 6, 12],  // 2、4、6、12月龄
      isFree: false,
    ),
  ];

  /// 所有疫苗
  static List<VaccineTemplate> get all => [...freeVaccines, ...paidVaccines];

  /// 根据月龄获取应该接种的疫苗
  static List<VaccineScheduleItem> getScheduleForAge(int ageMonths) {
    final items = <VaccineScheduleItem>[];
    for (final vaccine in all) {
      for (int i = 0; i < vaccine.scheduledAgeMonths.length; i++) {
        final scheduleMonth = vaccine.scheduledAgeMonths[i];
        if (scheduleMonth <= ageMonths + 3 && scheduleMonth >= ageMonths - 1) {
          items.add(VaccineScheduleItem(
            vaccineName: vaccine.name,
            description: vaccine.description,
            doseNumber: i + 1,
            scheduledAgeMonths: scheduleMonth,
            isFree: vaccine.isFree,
          ));
        }
      }
    }
    items.sort((a, b) => a.scheduledAgeMonths.compareTo(b.scheduledAgeMonths));
    return items;
  }
}

/// 疫苗计划项
class VaccineScheduleItem {
  final String vaccineName;
  final String description;
  final int doseNumber;
  final int scheduledAgeMonths;
  final bool isFree;

  const VaccineScheduleItem({
    required this.vaccineName,
    required this.description,
    required this.doseNumber,
    required this.scheduledAgeMonths,
    required this.isFree,
  });

  String get fullName => '$vaccineName (第$doseNumber针)';

  String get ageDisplay {
    if (scheduledAgeMonths == 0) return '出生时';
    if (scheduledAgeMonths < 12) return '$scheduledAgeMonths月龄';
    final years = scheduledAgeMonths ~/ 12;
    final months = scheduledAgeMonths % 12;
    if (months == 0) return '$years岁';
    return '$years岁$months个月';
  }
}
