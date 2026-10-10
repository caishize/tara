import 'package:equatable/equatable.dart';
import 'trending_gift.dart';

/// Date type for occasions
enum OccasionDateType {
  solar,    // Fixed solar/gregorian date (e.g., Valentine's Day 02-14)
  lunar,    // Lunar calendar date (e.g., Spring Festival)
  relative, // Relative date (e.g., Mother's Day - 2nd Sunday of May)
}

extension OccasionDateTypeExtension on OccasionDateType {
  static OccasionDateType fromString(String value) {
    return OccasionDateType.values.firstWhere(
      (e) => e.name == value,
      orElse: () => OccasionDateType.solar,
    );
  }
}

/// Occasion (holiday/festival) entity
class Occasion extends Equatable {
  final String id;
  final String name;
  final String? nameEn;
  final DateTime? date;
  final int? daysUntil;
  final List<TrendingGiftCategory>? giftCategories;
  final String? description;

  const Occasion({
    required this.id,
    required this.name,
    this.nameEn,
    this.date,
    this.daysUntil,
    this.giftCategories,
    this.description,
  });

  /// Get urgency level based on days until
  String get urgencyLevel {
    if (daysUntil == null) return 'unknown';
    if (daysUntil! <= 3) return 'high';
    if (daysUntil! <= 7) return 'medium';
    if (daysUntil! <= 30) return 'normal';
    return 'low';
  }

  /// Get countdown text
  String get countdownText {
    if (daysUntil == null) return '日期未知';
    if (daysUntil == 0) return '就是今天！';
    if (daysUntil == 1) return '明天';
    return '还有 $daysUntil 天';
  }

  Occasion copyWith({
    String? id,
    String? name,
    String? nameEn,
    DateTime? date,
    int? daysUntil,
    List<TrendingGiftCategory>? giftCategories,
    String? description,
  }) {
    return Occasion(
      id: id ?? this.id,
      name: name ?? this.name,
      nameEn: nameEn ?? this.nameEn,
      date: date ?? this.date,
      daysUntil: daysUntil ?? this.daysUntil,
      giftCategories: giftCategories ?? this.giftCategories,
      description: description ?? this.description,
    );
  }

  factory Occasion.fromJson(Map<String, dynamic> json) {
    return Occasion(
      id: json['id'] as String,
      name: json['name'] as String,
      nameEn: json['name_en'] as String?,
      date: json['date'] != null
          ? DateTime.parse(json['date'] as String)
          : null,
      daysUntil: json['days_until'] as int?,
      giftCategories: json['gift_categories'] != null
          ? (json['gift_categories'] as List<dynamic>)
              .map((e) => TrendingGiftCategoryExtension.fromString(e as String))
              .toList()
          : null,
      description: json['description'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'name_en': nameEn,
      'date': date?.toIso8601String(),
      'days_until': daysUntil,
      'gift_categories': giftCategories?.map((e) => e.name).toList(),
      'description': description,
    };
  }

  @override
  List<Object?> get props => [
        id,
        name,
        nameEn,
        date,
        daysUntil,
        giftCategories,
        description,
      ];
}

/// Occasion with gift preview
class OccasionWithGifts extends Occasion {
  final List<TrendingGift> previewGifts;

  const OccasionWithGifts({
    required super.id,
    required super.name,
    super.nameEn,
    super.date,
    super.daysUntil,
    super.giftCategories,
    super.description,
    this.previewGifts = const [],
  });

  factory OccasionWithGifts.fromJson(Map<String, dynamic> json) {
    return OccasionWithGifts(
      id: json['id'] as String,
      name: json['name'] as String,
      nameEn: json['name_en'] as String?,
      date: json['date'] != null
          ? DateTime.parse(json['date'] as String)
          : null,
      daysUntil: json['days_until'] as int?,
      giftCategories: json['gift_categories'] != null
          ? (json['gift_categories'] as List<dynamic>)
              .map((e) => TrendingGiftCategoryExtension.fromString(e as String))
              .toList()
          : null,
      description: json['description'] as String?,
      previewGifts: json['preview_gifts'] != null
          ? (json['preview_gifts'] as List<dynamic>)
              .map((e) => TrendingGift.fromJson(e as Map<String, dynamic>))
              .toList()
          : const [],
    );
  }

  @override
  Map<String, dynamic> toJson() {
    return {
      ...super.toJson(),
      'preview_gifts': previewGifts.map((e) => e.toJson()).toList(),
    };
  }

  @override
  List<Object?> get props => [...super.props, previewGifts];
}
