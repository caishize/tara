import 'package:equatable/equatable.dart';

/// User entity
class User extends Equatable {
  final String id;
  final String username;
  final String? nickname;
  final String? email;
  final String? phone;
  final String? timezone;
  final String familyId;

  const User({
    required this.id,
    required this.username,
    this.nickname,
    this.email,
    this.phone,
    this.timezone,
    required this.familyId,
  });

  /// Get display name (nickname if available, otherwise username)
  String get displayName => nickname ?? username;

  /// Create a copy with updated fields
  User copyWith({
    String? id,
    String? username,
    String? nickname,
    String? email,
    String? phone,
    String? timezone,
    String? familyId,
  }) {
    return User(
      id: id ?? this.id,
      username: username ?? this.username,
      nickname: nickname ?? this.nickname,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      timezone: timezone ?? this.timezone,
      familyId: familyId ?? this.familyId,
    );
  }

  @override
  List<Object?> get props => [id, username, nickname, email, phone, timezone, familyId];
}

/// Authentication result containing tokens and user info
class AuthResult extends Equatable {
  final String accessToken;
  final String refreshToken;
  final User user;

  const AuthResult({
    required this.accessToken,
    required this.refreshToken,
    required this.user,
  });

  @override
  List<Object?> get props => [accessToken, refreshToken, user];
}
