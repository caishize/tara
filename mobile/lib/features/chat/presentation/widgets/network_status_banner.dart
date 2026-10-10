import 'dart:async';
import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';

/// Connection status for the network banner.
enum ConnectionStatus {
  connected,
  disconnected,
  reconnecting,
}

/// A banner that slides in/out at the top of the chat area to indicate
/// network connectivity status.
///
/// - Red banner when disconnected.
/// - Orange/amber banner when reconnecting.
/// - Green "reconnected" banner that auto-hides after 2 seconds.
class NetworkStatusBanner extends StatefulWidget {
  final ConnectionStatus status;

  const NetworkStatusBanner({
    super.key,
    required this.status,
  });

  @override
  State<NetworkStatusBanner> createState() => _NetworkStatusBannerState();
}

class _NetworkStatusBannerState extends State<NetworkStatusBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<Offset> _slideAnimation;
  Timer? _hideTimer;

  /// Track previous status to detect reconnection.
  ConnectionStatus? _previousStatus;

  /// Whether we are showing the "reconnected" banner before hiding.
  bool _showingReconnected = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _slideAnimation = Tween<Offset>(
      begin: const Offset(0.0, -1.0),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    ));

    _applyStatus(widget.status);
  }

  @override
  void didUpdateWidget(covariant NetworkStatusBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.status != widget.status) {
      _previousStatus = oldWidget.status;
      _applyStatus(widget.status);
    }
  }

  void _applyStatus(ConnectionStatus status) {
    _hideTimer?.cancel();

    switch (status) {
      case ConnectionStatus.disconnected:
      case ConnectionStatus.reconnecting:
        _showingReconnected = false;
        _controller.forward();
        break;
      case ConnectionStatus.connected:
        final wasDisconnected = _previousStatus == ConnectionStatus.disconnected ||
            _previousStatus == ConnectionStatus.reconnecting;
        if (wasDisconnected) {
          // Show green "reconnected" banner, then hide after 2s.
          _showingReconnected = true;
          _controller.forward();
          _hideTimer = Timer(const Duration(seconds: 2), () {
            if (mounted) {
              _controller.reverse().then((_) {
                if (mounted) {
                  setState(() => _showingReconnected = false);
                }
              });
            }
          });
        } else {
          // Already connected, hide immediately.
          _showingReconnected = false;
          _controller.reverse();
        }
        break;
    }
  }

  @override
  void dispose() {
    _hideTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnimation,
      child: AnimatedSize(
        duration: const Duration(milliseconds: 200),
        child: _buildBannerContent(),
      ),
    );
  }

  Widget _buildBannerContent() {
    final Color backgroundColor;
    final Color textColor;
    final IconData icon;
    final String text;

    if (_showingReconnected && widget.status == ConnectionStatus.connected) {
      backgroundColor = AppColors.success;
      textColor = Colors.white;
      icon = Icons.cloud_done_outlined;
      text = '已重新连接';
    } else {
      switch (widget.status) {
        case ConnectionStatus.disconnected:
          backgroundColor = AppColors.error;
          textColor = Colors.white;
          icon = Icons.cloud_off_outlined;
          text = '网络已断开，正在重连...';
          break;
        case ConnectionStatus.reconnecting:
          backgroundColor = AppColors.warning;
          textColor = AppColors.secondaryDark;
          icon = Icons.sync;
          text = '正在重新连接...';
          break;
        case ConnectionStatus.connected:
          // Fully connected and not showing reconnected — empty.
          return const SizedBox.shrink();
      }
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: backgroundColor,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: textColor, size: 16),
          const SizedBox(width: 8),
          Text(
            text,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: textColor,
            ),
          ),
        ],
      ),
    );
  }
}
