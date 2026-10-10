import 'package:dartz/dartz.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/storage/auth_storage.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';

/// Implementation of AuthRepository
class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remoteDataSource;
  final AuthStorage authStorage;

  AuthRepositoryImpl({
    required this.remoteDataSource,
    required this.authStorage,
  });

  @override
  Future<Either<Failure, AuthResult>> register({
    required String email,
    required String password,
    required String familyName,
  }) async {
    try {
      final loginResponse = await remoteDataSource.register(
        email: email,
        password: password,
        familyName: familyName,
      );

      await authStorage.saveTokens(
        accessToken: loginResponse.accessToken,
        refreshToken: loginResponse.refreshToken,
      );

      final user = await remoteDataSource.getCurrentUser();

      await authStorage.saveUserInfo(
        userId: user.id,
        familyId: user.familyId,
        username: user.username,
        email: user.email,
      );

      return Right(AuthResult(
        accessToken: loginResponse.accessToken,
        refreshToken: loginResponse.refreshToken,
        user: user,
      ));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('注册失败: $e'));
    }
  }

  @override
  Future<Either<Failure, AuthResult>> login({
    required String email,
    required String password,
  }) async {
    try {
      // Login and get tokens
      final loginResponse = await remoteDataSource.login(
        email: email,
        password: password,
      );

      // Save tokens
      await authStorage.saveTokens(
        accessToken: loginResponse.accessToken,
        refreshToken: loginResponse.refreshToken,
      );

      // Get user info
      final user = await remoteDataSource.getCurrentUser();

      // Save user info
      await authStorage.saveUserInfo(
        userId: user.id,
        familyId: user.familyId,
        username: user.username,
        email: user.email,
      );

      return Right(AuthResult(
        accessToken: loginResponse.accessToken,
        refreshToken: loginResponse.refreshToken,
        user: user,
      ));
    } on UnauthorizedException {
      return const Left(AuthFailure('用户名或密码错误'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('登录失败: $e'));
    }
  }

  @override
  Future<Either<Failure, void>> logout() async {
    try {
      await remoteDataSource.logout();
      await authStorage.clearAuth();
      return const Right(null);
    } catch (e) {
      // Still clear local auth even if remote fails
      await authStorage.clearAuth();
      return const Right(null);
    }
  }

  @override
  Future<bool> isAuthenticated() async {
    return authStorage.isAuthenticated;
  }

  @override
  Future<Either<Failure, User>> getCurrentUser() async {
    try {
      final user = await remoteDataSource.getCurrentUser();
      return Right(user);
    } on UnauthorizedException {
      return const Left(AuthFailure('未登录或登录已过期'));
    } on NetworkException catch (e) {
      // Try to get from cache
      final cached = authStorage.getUserInfo();
      if (cached != null) {
        return Right(User(
          id: cached['id'] as String,
          username: cached['username'] as String,
          email: cached['email'] as String?,
          familyId: cached['family_id'] as String,
        ));
      }
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return const Left(ServerFailure('获取用户信息失败'));
    }
  }

  @override
  Future<Either<Failure, AuthResult>> refreshToken() async {
    try {
      final refreshToken = authStorage.getRefreshToken();
      if (refreshToken == null) {
        return const Left(AuthFailure('登录已过期'));
      }

      final response = await remoteDataSource.refreshToken(refreshToken);

      await authStorage.saveTokens(
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
      );

      final user = await remoteDataSource.getCurrentUser();

      return Right(AuthResult(
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        user: user,
      ));
    } catch (e) {
      await authStorage.clearAuth();
      return const Left(AuthFailure('登录已过期，请重新登录'));
    }
  }

  @override
  Future<Either<Failure, User>> getProfile() async {
    try {
      final user = await remoteDataSource.getProfile();
      await authStorage.saveUserInfo(
        userId: user.id,
        familyId: user.familyId,
        username: user.username,
        email: user.email,
      );
      return Right(user);
    } on UnauthorizedException {
      return const Left(AuthFailure('未登录或登录已过期'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('获取资料失败: $e'));
    }
  }

  @override
  Future<Either<Failure, User>> updateProfile({
    String? username,
    String? nickname,
    String? phone,
    String? email,
    String? timezone,
  }) async {
    try {
      final user = await remoteDataSource.updateProfile(
        username: username,
        nickname: nickname,
        phone: phone,
        email: email,
        timezone: timezone,
      );

      // Update stored user info
      await authStorage.saveUserInfo(
        userId: user.id,
        familyId: user.familyId,
        username: user.username,
        email: user.email,
      );

      return Right(user);
    } on UnauthorizedException {
      return const Left(AuthFailure('未登录或登录已过期'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('更新资料失败: $e'));
    }
  }

  @override
  Future<Either<Failure, void>> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    try {
      await remoteDataSource.changePassword(
        currentPassword: currentPassword,
        newPassword: newPassword,
      );
      return const Right(null);
    } on UnauthorizedException {
      return const Left(AuthFailure('当前密码错误'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('修改密码失败: $e'));
    }
  }

  @override
  Future<Either<Failure, void>> deleteAccount({
    required String password,
  }) async {
    try {
      await remoteDataSource.deleteAccount(password: password);
      await authStorage.clearAuth();
      return const Right(null);
    } on UnauthorizedException {
      return const Left(AuthFailure('密码错误'));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(e.message));
    } catch (e) {
      return Left(ServerFailure('注销账户失败: $e'));
    }
  }
}
