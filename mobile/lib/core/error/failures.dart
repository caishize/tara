import 'package:equatable/equatable.dart';

/// Base failure class for domain layer
abstract class Failure extends Equatable {
  final String message;

  const Failure(this.message);

  @override
  List<Object?> get props => [message];
}

/// Server failure
class ServerFailure extends Failure {
  const ServerFailure([super.message = '服务器错误，请稍后重试']);
}

/// Network failure
class NetworkFailure extends Failure {
  const NetworkFailure([super.message = '网络连接失败，请检查网络设置']);
}

/// Cache failure
class CacheFailure extends Failure {
  const CacheFailure([super.message = '本地数据读取失败']);
}

/// Authentication failure
class AuthFailure extends Failure {
  const AuthFailure([super.message = '认证失败']);
}

/// Validation failure
class ValidationFailure extends Failure {
  final Map<String, List<String>>? errors;

  const ValidationFailure([super.message = '数据验证失败', this.errors]);

  @override
  List<Object?> get props => [message, errors];
}

/// Not found failure
class NotFoundFailure extends Failure {
  const NotFoundFailure([super.message = '找不到请求的资源']);
}

/// Permission failure
class PermissionFailure extends Failure {
  const PermissionFailure([super.message = '没有权限执行此操作']);
}

/// Unknown failure
class UnknownFailure extends Failure {
  const UnknownFailure([super.message = '发生未知错误']);
}
