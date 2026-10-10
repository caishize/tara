import 'package:dio/dio.dart';
import '../error/exceptions.dart';

/// Generic API client wrapper around Dio
class ApiClient {
  final Dio _dio;

  ApiClient(this._dio);

  /// GET request
  Future<T> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.get(
        path,
        queryParameters: queryParameters,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// POST request
  Future<T> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
    Duration? timeout,
  }) async {
    try {
      final response = await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: timeout != null
            ? Options(
                sendTimeout: timeout,
                receiveTimeout: timeout,
              )
            : null,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// PUT request
  Future<T> put<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// DELETE request
  Future<T> delete<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// PATCH request
  Future<T> patch<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.patch(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// POST with multipart form data (for file uploads)
  Future<T> postMultipart<T>(
    String path, {
    required FormData formData,
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? parser,
    void Function(int, int)? onSendProgress,
  }) async {
    try {
      final response = await _dio.post(
        path,
        data: formData,
        queryParameters: queryParameters,
        onSendProgress: onSendProgress,
      );
      return _handleResponse(response, parser);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  T _handleResponse<T>(Response response, T Function(dynamic)? parser) {
    if (response.statusCode != null &&
        response.statusCode! >= 200 &&
        response.statusCode! < 300) {
      if (parser != null) {
        return parser(response.data);
      }
      return response.data as T;
    }
    throw ServerException(
      message: 'Server error: ${response.statusCode}',
      statusCode: response.statusCode,
    );
  }

  AppException _handleError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const NetworkException(message: '网络连接超时，请稍后重试');
      case DioExceptionType.connectionError:
        return const NetworkException(message: '网络连接失败，请检查网络设置');
      case DioExceptionType.badResponse:
        return _handleBadResponse(e.response);
      case DioExceptionType.cancel:
        return const NetworkException(message: '请求已取消');
      default:
        return NetworkException(message: '网络请求失败: ${e.message}');
    }
  }

  AppException _handleBadResponse(Response? response) {
    if (response == null) {
      return const ServerException(message: '服务器无响应');
    }

    final statusCode = response.statusCode ?? 0;
    final data = response.data;
    String message = '服务器错误';

    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String) {
        message = detail;
      } else if (detail is List && detail.isNotEmpty) {
        // FastAPI validation errors: [{"msg": "...", "loc": [...], ...}]
        message = detail
            .map((e) => e is Map ? e['msg'] ?? '' : e.toString())
            .join('; ');
      } else {
        message = data['message'] as String? ?? message;
      }
    }

    switch (statusCode) {
      case 400:
        return ValidationException(message: message);
      case 401:
        return const UnauthorizedException(message: '登录已过期，请重新登录');
      case 403:
        return const ForbiddenException(message: '没有权限执行此操作');
      case 404:
        return const NotFoundException(message: '请求的资源不存在');
      case 422:
        return ValidationException(message: message);
      case 500:
      case 502:
      case 503:
        return ServerException(message: '服务器繁忙，请稍后重试', statusCode: statusCode);
      default:
        return ServerException(message: message, statusCode: statusCode);
    }
  }
}
