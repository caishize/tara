import 'dart:async';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:app_links/app_links.dart';

/// OAuth authentication mode
enum OAuthMode {
  /// Use in-app WebView (better UX)
  webView,

  /// Use system browser with deep link callback
  systemBrowser,
}

/// Result of an OAuth authentication attempt
class OAuthResult {
  final bool success;
  final String? code;
  final String? state;
  final String? error;
  final String? errorDescription;

  const OAuthResult({
    required this.success,
    this.code,
    this.state,
    this.error,
    this.errorDescription,
  });

  factory OAuthResult.success({
    required String code,
    String? state,
  }) {
    return OAuthResult(
      success: true,
      code: code,
      state: state,
    );
  }

  factory OAuthResult.failure({
    required String error,
    String? errorDescription,
  }) {
    return OAuthResult(
      success: false,
      error: error,
      errorDescription: errorDescription,
    );
  }

  factory OAuthResult.cancelled() {
    return const OAuthResult(
      success: false,
      error: 'cancelled',
      errorDescription: '用户取消了授权',
    );
  }
}

/// Handler for OAuth authentication flows
class OAuthHandler {
  static const String _callbackScheme = 'secretary';
  static const String _callbackPath = 'oauth/callback';

  /// Get the callback URL for OAuth redirects
  static String get callbackUrl => '$_callbackScheme://$_callbackPath';

  /// Stream subscription for deep links
  StreamSubscription? _linkSubscription;
  Completer<OAuthResult>? _pendingCompleter;

  /// Perform OAuth authentication
  ///
  /// [authUrl] - The OAuth authorization URL
  /// [mode] - The authentication mode to use (auto-detected if not specified)
  Future<OAuthResult> authorize(
    String authUrl, {
    OAuthMode? mode,
  }) async {
    final preferredMode = mode ?? _detectBestMode(authUrl);

    if (preferredMode == OAuthMode.webView) {
      return _authorizeWithWebView(authUrl);
    } else {
      return _authorizeWithSystemBrowser(authUrl);
    }
  }

  /// Detect the best OAuth mode based on the auth URL
  OAuthMode _detectBestMode(String url) {
    // Google prefers system browser for security
    if (url.contains('accounts.google.com')) {
      return OAuthMode.systemBrowser;
    }
    // Microsoft works well with both
    if (url.contains('login.microsoftonline.com')) {
      return OAuthMode.webView;
    }
    // Default to WebView for better UX
    return OAuthMode.webView;
  }

  /// Authorize using in-app WebView
  Future<OAuthResult> _authorizeWithWebView(String authUrl) async {
    try {
      final result = await FlutterWebAuth2.authenticate(
        url: authUrl,
        callbackUrlScheme: _callbackScheme,
        options: const FlutterWebAuth2Options(
          timeout: 300, // 5 minutes
          preferEphemeral: true,
        ),
      );

      return _parseCallbackUrl(result);
    } catch (e) {
      final errorString = e.toString().toLowerCase();
      // Check for user cancellation
      if (errorString.contains('cancel') || errorString.contains('user_cancel')) {
        return OAuthResult.cancelled();
      }
      return OAuthResult.failure(
        error: 'auth_error',
        errorDescription: e.toString(),
      );
    }
  }

  /// Authorize using system browser with deep link callback
  Future<OAuthResult> _authorizeWithSystemBrowser(String authUrl) async {
    final uri = Uri.parse(authUrl);

    // Check if URL can be launched
    if (!await canLaunchUrl(uri)) {
      return OAuthResult.failure(
        error: 'cannot_launch_url',
        errorDescription: '无法打开授权页面',
      );
    }

    // Set up deep link listener
    _pendingCompleter = Completer<OAuthResult>();
    final appLinks = AppLinks();

    _linkSubscription = appLinks.uriLinkStream.listen((Uri uri) {
      if (uri.scheme == _callbackScheme) {
        _handleCallback(uri);
      }
    });

    // Launch browser
    await launchUrl(uri, mode: LaunchMode.externalApplication);

    try {
      // Wait for callback with timeout
      return await _pendingCompleter!.future.timeout(
        const Duration(minutes: 5),
        onTimeout: () {
          return OAuthResult.failure(
            error: 'timeout',
            errorDescription: '授权超时，请重试',
          );
        },
      );
    } finally {
      _cleanup();
    }
  }

  /// Handle the OAuth callback URL
  void _handleCallback(Uri uri) {
    if (_pendingCompleter == null || _pendingCompleter!.isCompleted) return;

    final result = _parseCallbackUrl(uri.toString());
    _pendingCompleter!.complete(result);
  }

  /// Parse the callback URL and extract OAuth result
  OAuthResult _parseCallbackUrl(String callbackUrl) {
    final uri = Uri.parse(callbackUrl);
    final params = uri.queryParameters;

    // Check for error
    if (params.containsKey('error')) {
      return OAuthResult.failure(
        error: params['error'] ?? 'unknown_error',
        errorDescription: params['error_description'],
      );
    }

    // Check for code
    final code = params['code'];
    if (code == null || code.isEmpty) {
      return OAuthResult.failure(
        error: 'no_code',
        errorDescription: '未收到授权码',
      );
    }

    return OAuthResult.success(
      code: code,
      state: params['state'],
    );
  }

  /// Cancel any pending authorization
  void cancel() {
    if (_pendingCompleter != null && !_pendingCompleter!.isCompleted) {
      _pendingCompleter!.complete(OAuthResult.cancelled());
    }
    _cleanup();
  }

  /// Clean up resources
  void _cleanup() {
    _linkSubscription?.cancel();
    _linkSubscription = null;
    _pendingCompleter = null;
  }

  /// Dispose the handler
  void dispose() {
    cancel();
  }
}
