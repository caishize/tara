import 'package:equatable/equatable.dart';

import '../../../../shared/utils/relation_utils.dart';

/// Member profile information
class MemberProfile extends Equatable {
  final String? occupation;
  final String? education;
  final List<String>? hobbies;
  final String? personality;
  final List<String>? favoriteColors;
  final String? clothingSize;

  const MemberProfile({
    this.occupation,
    this.education,
    this.hobbies,
    this.personality,
    this.favoriteColors,
    this.clothingSize,
  });

  @override
  List<Object?> get props => [occupation, education, hobbies, personality, favoriteColors, clothingSize];
}

/// Member preferences for gifts etc
class MemberPreferences extends Equatable {
  final List<String>? giftPreferences;
  final List<String>? avoidItems;

  const MemberPreferences({
    this.giftPreferences,
    this.avoidItems,
  });

  @override
  List<Object?> get props => [giftPreferences, avoidItems];
}

/// Member health information
class MemberHealthInfo extends Equatable {
  final String? bloodType;
  final List<String>? allergies;
  final List<String>? chronicConditions;
  final String? lastCheckupDate;

  const MemberHealthInfo({
    this.bloodType,
    this.allergies,
    this.chronicConditions,
    this.lastCheckupDate,
  });

  @override
  List<Object?> get props => [bloodType, allergies, chronicConditions, lastCheckupDate];
}

/// Member entity
class Member extends Equatable {
  final String id;
  final String name;
  final String? nickname;
  final String? gender;
  final String? birthDate;
  final int? age;
  final String? phone;
  final String? email;
  final String? idCard;
  final String relation;
  final int profileCompletion;
  final Map<String, dynamic>? locations;
  final String? defaultLocationType;
  final MemberProfile? profile;
  final MemberPreferences? preferences;
  final MemberHealthInfo? healthInfo;
  // Professional fields (职业信息)
  final String? currentCompany;   // 当前公司
  final String? currentPosition;  // 当前职位
  // PersonProfile fields (from person_profiles)
  final double favorBalance;
  final String? lastMentionedAt;
  final double importance;
  final String? organization;

  const Member({
    required this.id,
    required this.name,
    this.nickname,
    this.gender,
    this.birthDate,
    this.age,
    this.phone,
    this.email,
    this.idCard,
    this.relation = 'other',
    this.profileCompletion = 0,
    this.locations,
    this.defaultLocationType,
    this.profile,
    this.preferences,
    this.healthInfo,
    this.currentCompany,
    this.currentPosition,
    this.favorBalance = 0.0,
    this.lastMentionedAt,
    this.importance = 0.0,
    this.organization,
  });

  /// Get display name (nickname or name)
  String get displayName => nickname?.isNotEmpty == true ? nickname! : name;

  /// Get relation display text in Chinese
  String get relationText => RelationUtils.getRelationLabel(relation);

  /// Get gender display text
  String? get genderText {
    switch (gender?.toLowerCase()) {
      case 'male':
        return '男';
      case 'female':
        return '女';
      default:
        return null;
    }
  }

  /// Check if member is a child (son, daughter, grandchild)
  bool get isChild => relation == 'child' || relation == 'grandchild';

  @override
  List<Object?> get props => [
        id,
        name,
        nickname,
        gender,
        birthDate,
        age,
        phone,
        email,
        idCard,
        relation,
        profileCompletion,
        locations,
        defaultLocationType,
        profile,
        preferences,
        healthInfo,
        currentCompany,
        currentPosition,
        favorBalance,
        lastMentionedAt,
        importance,
        organization,
      ];
}
