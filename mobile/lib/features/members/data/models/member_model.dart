import '../../domain/entities/member.dart';

class MemberModel extends Member {
  const MemberModel({
    required super.id,
    required super.name,
    super.nickname,
    super.gender,
    super.birthDate,
    super.age,
    super.phone,
    super.email,
    super.idCard,
    super.relation = 'other',
    super.profileCompletion = 0,
    super.locations,
    super.defaultLocationType,
    super.profile,
    super.preferences,
    super.healthInfo,
    super.currentCompany,
    super.currentPosition,
    super.favorBalance = 0.0,
    super.lastMentionedAt,
    super.importance = 0.0,
    super.organization,
  });

  factory MemberModel.fromJson(Map<String, dynamic> json) {
    return MemberModel(
      id: json['id'] as String,
      name: json['name'] as String,
      nickname: json['nickname'] as String?,
      gender: json['gender'] as String?,
      birthDate: json['birth_date'] as String?,
      age: json['age'] as int?,
      phone: json['phone'] as String?,
      email: json['email'] as String?,
      idCard: json['id_card'] as String?,
      relation: json['relation'] as String? ?? 'other',
      profileCompletion: json['profile_completion'] as int? ?? 0,
      locations: json['locations'] as Map<String, dynamic>?,
      defaultLocationType: json['default_location_type'] as String?,
      profile: _parseProfile(json['profile']),
      preferences: _parsePreferences(json['preferences']),
      healthInfo: _parseHealthInfo(json['health_info']),
      currentCompany: json['current_company'] as String?,
      currentPosition: json['current_position'] as String?,
      favorBalance: (json['favor_balance'] as num?)?.toDouble() ?? 0.0,
      lastMentionedAt: json['last_mentioned_at'] as String?,
      importance: (json['importance'] as num?)?.toDouble() ?? 0.0,
      organization: json['organization'] as String?,
    );
  }

  static MemberProfile? _parseProfile(dynamic json) {
    if (json == null) return null;
    final map = json as Map<String, dynamic>;
    return MemberProfile(
      occupation: map['occupation'] as String?,
      education: map['education'] as String?,
      hobbies: (map['hobbies'] as List<dynamic>?)?.cast<String>(),
      personality: map['personality'] as String?,
      favoriteColors: (map['favorite_colors'] as List<dynamic>?)?.cast<String>(),
      clothingSize: map['clothing_size'] as String?,
    );
  }

  static MemberPreferences? _parsePreferences(dynamic json) {
    if (json == null) return null;
    final map = json as Map<String, dynamic>;
    return MemberPreferences(
      giftPreferences: (map['gift_preferences'] as List<dynamic>?)?.cast<String>(),
      avoidItems: (map['avoid_items'] as List<dynamic>?)?.cast<String>(),
    );
  }

  static MemberHealthInfo? _parseHealthInfo(dynamic json) {
    if (json == null) return null;
    final map = json as Map<String, dynamic>;
    return MemberHealthInfo(
      bloodType: map['blood_type'] as String?,
      allergies: (map['allergies'] as List<dynamic>?)?.cast<String>(),
      chronicConditions: (map['chronic_conditions'] as List<dynamic>?)?.cast<String>(),
      lastCheckupDate: map['last_checkup_date'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      if (nickname != null) 'nickname': nickname,
      if (gender != null) 'gender': gender,
      if (birthDate != null) 'birth_date': birthDate,
      if (phone != null) 'phone': phone,
      if (email != null) 'email': email,
      if (idCard != null) 'id_card': idCard,
      'relation': relation,
      if (locations != null) 'locations': locations,
      if (defaultLocationType != null) 'default_location_type': defaultLocationType,
      if (profile != null) 'profile': _profileToJson(profile!),
      if (preferences != null) 'preferences': _preferencesToJson(preferences!),
      if (healthInfo != null) 'health_info': _healthInfoToJson(healthInfo!),
      if (currentCompany != null) 'current_company': currentCompany,
      if (currentPosition != null) 'current_position': currentPosition,
    };
  }

  static Map<String, dynamic> _profileToJson(MemberProfile profile) {
    return {
      if (profile.occupation != null) 'occupation': profile.occupation,
      if (profile.education != null) 'education': profile.education,
      if (profile.hobbies != null) 'hobbies': profile.hobbies,
      if (profile.personality != null) 'personality': profile.personality,
      if (profile.favoriteColors != null) 'favorite_colors': profile.favoriteColors,
      if (profile.clothingSize != null) 'clothing_size': profile.clothingSize,
    };
  }

  static Map<String, dynamic> _preferencesToJson(MemberPreferences prefs) {
    return {
      if (prefs.giftPreferences != null) 'gift_preferences': prefs.giftPreferences,
      if (prefs.avoidItems != null) 'avoid_items': prefs.avoidItems,
    };
  }

  static Map<String, dynamic> _healthInfoToJson(MemberHealthInfo health) {
    return {
      if (health.bloodType != null) 'blood_type': health.bloodType,
      if (health.allergies != null) 'allergies': health.allergies,
      if (health.chronicConditions != null) 'chronic_conditions': health.chronicConditions,
      if (health.lastCheckupDate != null) 'last_checkup_date': health.lastCheckupDate,
    };
  }

  /// Create request body for API
  Map<String, dynamic> toCreateRequest() {
    return {
      'name': name,
      if (nickname != null) 'nickname': nickname,
      if (gender != null) 'gender': gender,
      if (birthDate != null) 'birth_date': birthDate,
      if (phone != null) 'phone': phone,
      if (email != null) 'email': email,
      if (idCard != null) 'id_card': idCard,
      'relation': relation,
      if (locations != null) 'locations': locations,
      if (defaultLocationType != null) 'default_location_type': defaultLocationType,
      if (profile != null) 'profile': _profileToJson(profile!),
      if (preferences != null) 'preferences': _preferencesToJson(preferences!),
      if (healthInfo != null) 'health_info': _healthInfoToJson(healthInfo!),
    };
  }

  factory MemberModel.fromEntity(Member member) {
    return MemberModel(
      id: member.id,
      name: member.name,
      nickname: member.nickname,
      gender: member.gender,
      birthDate: member.birthDate,
      age: member.age,
      phone: member.phone,
      email: member.email,
      idCard: member.idCard,
      relation: member.relation,
      profileCompletion: member.profileCompletion,
      locations: member.locations,
      defaultLocationType: member.defaultLocationType,
      profile: member.profile,
      preferences: member.preferences,
      healthInfo: member.healthInfo,
      currentCompany: member.currentCompany,
      currentPosition: member.currentPosition,
      favorBalance: member.favorBalance,
      lastMentionedAt: member.lastMentionedAt,
      importance: member.importance,
      organization: member.organization,
    );
  }
}
