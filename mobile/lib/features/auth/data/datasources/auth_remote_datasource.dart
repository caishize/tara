import '../../../../core/network/api_client.dart';
import '../models/user_model.dart';

/// Remote data source for authentication
class AuthRemoteDataSource {
  final ApiClient _client;

  AuthRemoteDataSource(this._client);

  /// Register a new user with email, password, and family name
  Future<LoginResponseModel> register({
    required String email,
    required String password,
    required String familyName,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/auth/register',
      data: {
        'email': email,
        'password': password,
        'family_name': familyName,
      },
    );
    return LoginResponseModel.fromJson(response);
  }

  /// Login with email and password
  Future<LoginResponseModel> login({
    required String email,
    required String password,
  }) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/auth/login',
      data: {
        'login': email,
        'password': password,
      },
    );
    return LoginResponseModel.fromJson(response);
  }

  /// Get current user info
  Future<UserModel> getCurrentUser() async {
    final response = await _client.get<Map<String, dynamic>>('/auth/me');
    return UserModel.fromJson(response);
  }

  /// Logout
  Future<void> logout() async {
    await _client.post('/auth/logout');
  }

  /// Refresh token
  Future<LoginResponseModel> refreshToken(String refreshToken) async {
    final response = await _client.post<Map<String, dynamic>>(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    return LoginResponseModel.fromJson(response);
  }

  /// Get current user profile
  Future<UserModel> getProfile() async {
    final response = await _client.get<Map<String, dynamic>>('/auth/me');
    return UserModel.fromJson(response);
  }

  /// Update user profile
  Future<UserModel> updateProfile({
    String? username,
    String? nickname,
    String? phone,
    String? email,
    String? timezone,
  }) async {
    final data = <String, dynamic>{};
    if (username != null) data['username'] = username;
    if (nickname != null) data['nickname'] = nickname;
    if (phone != null) data['phone'] = phone;
    if (email != null) data['email'] = email;
    if (timezone != null) data['timezone'] = timezone;

    final response = await _client.put<Map<String, dynamic>>(
      '/auth/profile',
      data: data,
    );
    return UserModel.fromJson(response);
  }

  /// Change password
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _client.post<Map<String, dynamic>>(
      '/auth/change-password',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
  }

  /// Delete account
  Future<void> deleteAccount({required String password}) async {
    await _client.delete<Map<String, dynamic>>(
      '/auth/account',
      data: {'password': password},
    );
  }
}
