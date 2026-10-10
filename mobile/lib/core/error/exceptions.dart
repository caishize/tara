/// Base exception class for the app
abstract class AppException implements Exception {
  final String message;
  final String? code;

  const AppException({
    required this.message,
    this.code,
  });

  @override
  String toString() => message;
}

/// Network related exceptions
class NetworkException extends AppException {
  const NetworkException({
    required super.message,
    super.code,
  });
}

/// Server error exceptions
class ServerException extends AppException {
  final int? statusCode;

  const ServerException({
    required super.message,
    this.statusCode,
    super.code,
  });
}

/// Unauthorized exceptions (401)
class UnauthorizedException extends AppException {
  const UnauthorizedException({
    super.message = '未授权的请求',
    super.code,
  });
}

/// Forbidden exceptions (403)
class ForbiddenException extends AppException {
  const ForbiddenException({
    super.message = '没有访问权限',
    super.code,
  });
}

/// Not found exceptions (404)
class NotFoundException extends AppException {
  const NotFoundException({
    super.message = '资源不存在',
    super.code,
  });
}

/// Validation exceptions (400, 422)
class ValidationException extends AppException {
  final Map<String, List<String>>? errors;

  const ValidationException({
    required super.message,
    this.errors,
    super.code,
  });
}

/// Cache exceptions
class CacheException extends AppException {
  const CacheException({
    super.message = '缓存读取失败',
    super.code,
  });
}

/// Local storage exceptions
class StorageException extends AppException {
  const StorageException({
    super.message = '本地存储错误',
    super.code,
  });
}
