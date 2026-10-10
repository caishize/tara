import '../../domain/entities/user.dart';

/// User data model
class UserModel extends User {
  const UserModel({
    required super.id,
    required super.username,
    super.nickname,
    super.email,
    super.phone,
    super.timezone,
    required super.familyId,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String,
      username: json['username'] as String,
      nickname: json['nickname'] as String?,
      email: json['email'] as String?,
      phone: json['phone'] as String?,
      timezone: json['timezone'] as String?,
      familyId: json['family_id'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'nickname': nickname,
      'email': email,
      'phone': phone,
      'timezone': timezone,
      'family_id': familyId,
    };
  }
}

/// Login response model
class LoginResponseModel {
  final String accessToken;
  final String refreshToken;
  final String tokenType;

  const LoginResponseModel({
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'bearer',
  });

  factory LoginResponseModel.fromJson(Map<String, dynamic> json) {
    return LoginResponseModel(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String? ?? 'bearer',
    );
  }
}
