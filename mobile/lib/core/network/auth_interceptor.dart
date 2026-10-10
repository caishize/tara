import 'package:dio/dio.dart';
import '../storage/auth_storage.dart';

/// Interceptor that adds authentication headers to requests
class AuthInterceptor extends Interceptor {
  final AuthStorage _authStorage;

  AuthInterceptor(this._authStorage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = _authStorage.getAccessToken();
    // Skip sending dev placeholder tokens — the backend accepts
    // unauthenticated requests when STRICT_AUTH_ENABLED=false
    if (token != null && token.isNotEmpty && !token.startsWith('dev-')) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      // Token expired, try to refresh
      final refreshToken = _authStorage.getRefreshToken();
      if (refreshToken != null) {
        try {
          // Attempt to refresh token
          final dio = Dio(BaseOptions(
            baseUrl: err.requestOptions.baseUrl,
          ));

          final response = await dio.post(
            '/auth/refresh',
            data: {'refresh_token': refreshToken},
          );

          if (response.statusCode == 200) {
            final newAccessToken = response.data['access_token'];
            final newRefreshToken = response.data['refresh_token'];

            await _authStorage.saveTokens(
              accessToken: newAccessToken,
              refreshToken: newRefreshToken,
            );

            // Retry the original request
            err.requestOptions.headers['Authorization'] = 'Bearer $newAccessToken';
            final retryResponse = await dio.fetch(err.requestOptions);
            return handler.resolve(retryResponse);
          }
        } catch (e) {
          // Refresh failed, clear auth and let error propagate
          await _authStorage.clearAuth();
        }
      }
    }
    handler.next(err);
  }
}
