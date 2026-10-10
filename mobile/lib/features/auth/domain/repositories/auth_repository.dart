import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/user.dart';

/// Authentication repository interface
abstract class AuthRepository {
  /// Register a new user
  Future<Either<Failure, AuthResult>> register({
    required String email,
    required String password,
    required String familyName,
  });

  /// Login with email and password
  Future<Either<Failure, AuthResult>> login({
    required String email,
    required String password,
  });

  /// Logout
  Future<Either<Failure, void>> logout();

  /// Check if user is authenticated
  Future<bool> isAuthenticated();

  /// Get current user
  Future<Either<Failure, User>> getCurrentUser();

  /// Refresh token
  Future<Either<Failure, AuthResult>> refreshToken();

  /// Get current user profile from API
  Future<Either<Failure, User>> getProfile();

  /// Update user profile
  Future<Either<Failure, User>> updateProfile({
    String? username,
    String? nickname,
    String? phone,
    String? email,
    String? timezone,
  });

  /// Change password
  Future<Either<Failure, void>> changePassword({
    required String currentPassword,
    required String newPassword,
  });

  /// Delete account
  Future<Either<Failure, void>> deleteAccount({
    required String password,
  });
}
