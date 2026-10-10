/// Application configuration read from compile-time environment.
///
/// Values are injected via `--dart-define` flags at build time:
///   flutter run --dart-define=API_BASE_URL=https://api.example.com/api/v1
///
/// Defaults to localhost for local development.
class AppConfig {
  const AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );

  /// When true, the app auto-authenticates with dev user credentials,
  /// bypassing the login screen. Matches backend STRICT_AUTH_ENABLED=false.
  static const bool devAutoLogin = bool.fromEnvironment(
    'DEV_AUTO_LOGIN',
    defaultValue: false,
  );

  /// Default dev user ID — must match backend _DEFAULT_USER_ID
  static const String devUserId = '123e4567-e89b-12d3-a456-426614174001';

  /// Default dev family ID — must match backend _DEFAULT_FAMILY_ID
  static const String devFamilyId = '123e4567-e89b-12d3-a456-426614174000';
}
