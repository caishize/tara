import 'dart:async';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:hive/hive.dart';

/// Secure storage for authentication data.
///
/// JWT tokens are stored via [FlutterSecureStorage] (Keychain / Keystore).
/// Non-sensitive user metadata is kept in Hive for fast synchronous reads.
class AuthStorage {
  final Box _box;
  final FlutterSecureStorage _secureStorage;

  static const String _keyAccessToken = 'access_token';
  static const String _keyRefreshToken = 'refresh_token';
  static const String _keyUserId = 'user_id';
  static const String _keyFamilyId = 'family_id';
  static const String _keyUserInfo = 'user_info';

  // In-memory cache for synchronous access to tokens
  String? _cachedAccessToken;
  String? _cachedRefreshToken;

  // Stream controller for auth state changes
  final _authStateController = StreamController<bool>.broadcast();

  /// Stream that emits auth state changes (true = authenticated, false = logged out)
  Stream<bool> get authStateStream => _authStateController.stream;

  AuthStorage(this._box, {FlutterSecureStorage? secureStorage})
      : _secureStorage = secureStorage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
            );

  /// Initialize by loading tokens from secure storage into memory cache.
  /// Must be called before accessing tokens synchronously.
  Future<void> initialize() async {
    _cachedAccessToken = await _secureStorage.read(key: _keyAccessToken);
    _cachedRefreshToken = await _secureStorage.read(key: _keyRefreshToken);
  }

  // Token management
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _secureStorage.write(key: _keyAccessToken, value: accessToken);
    await _secureStorage.write(key: _keyRefreshToken, value: refreshToken);
    _cachedAccessToken = accessToken;
    _cachedRefreshToken = refreshToken;
    _authStateController.add(true);
  }

  String? getAccessToken() {
    return _cachedAccessToken;
  }

  String? getRefreshToken() {
    return _cachedRefreshToken;
  }

  bool get isAuthenticated {
    final token = getAccessToken();
    return token != null && token.isNotEmpty;
  }

  // User info management (non-sensitive, kept in Hive for fast sync reads)
  Future<void> saveUserInfo({
    required String userId,
    required String familyId,
    String? username,
    String? email,
  }) async {
    await _box.put(_keyUserId, userId);
    await _box.put(_keyFamilyId, familyId);
    await _box.put(_keyUserInfo, jsonEncode({
      'id': userId,
      'family_id': familyId,
      'username': username,
      'email': email,
    }));
  }

  String? getUserId() {
    return _box.get(_keyUserId);
  }

  String? getFamilyId() {
    return _box.get(_keyFamilyId);
  }

  Map<String, dynamic>? getUserInfo() {
    final json = _box.get(_keyUserInfo);
    if (json == null) return null;
    return jsonDecode(json) as Map<String, dynamic>;
  }

  // Clear all auth data
  Future<void> clearAuth() async {
    await _secureStorage.delete(key: _keyAccessToken);
    await _secureStorage.delete(key: _keyRefreshToken);
    _cachedAccessToken = null;
    _cachedRefreshToken = null;
    await _box.delete(_keyUserId);
    await _box.delete(_keyFamilyId);
    await _box.delete(_keyUserInfo);
    _authStateController.add(false);
  }

  /// Dispose resources
  void dispose() {
    _authStateController.close();
  }
}
