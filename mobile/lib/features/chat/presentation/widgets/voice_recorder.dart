import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import '../../../../app/theme/app_colors.dart';

class VoiceRecorder extends StatefulWidget {
  final void Function(String filePath) onRecordingComplete;
  final VoidCallback onCancel;

  const VoiceRecorder({
    super.key,
    required this.onRecordingComplete,
    required this.onCancel,
  });

  @override
  State<VoiceRecorder> createState() => _VoiceRecorderState();
}

class _VoiceRecorderState extends State<VoiceRecorder>
    with SingleTickerProviderStateMixin {
  final AudioRecorder _recorder = AudioRecorder();
  bool _isRecording = false;
  Timer? _durationTimer;
  Timer? _autoStopTimer;
  int _elapsedSeconds = 0;
  late AnimationController _pulseController;

  static const int _maxDurationSeconds = 60;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    // Defer to post-frame to avoid Navigator issues if permission is denied
    WidgetsBinding.instance.addPostFrameCallback((_) => _startRecording());
  }

  @override
  void dispose() {
    _durationTimer?.cancel();
    _autoStopTimer?.cancel();
    _pulseController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('需要麦克风权限才能使用语音输入'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
        widget.onCancel();
      }
      return;
    }

    final tempDir = await getTemporaryDirectory();
    final filePath =
        '${tempDir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.m4a';

    try {
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 128000,
          sampleRate: 44100,
        ),
        path: filePath,
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('录音启动失败，请重试'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
          ),
        );
        widget.onCancel();
      }
      return;
    }

    if (!mounted) return;
    setState(() {
      _isRecording = true;
      _elapsedSeconds = 0;
    });

    _pulseController.repeat(reverse: true);

    _durationTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _elapsedSeconds++);
    });

    _autoStopTimer = Timer(
      const Duration(seconds: _maxDurationSeconds),
      _stopRecording,
    );
  }

  Future<void> _stopRecording() async {
    _durationTimer?.cancel();
    _autoStopTimer?.cancel();
    _pulseController.stop();

    final path = await _recorder.stop();
    if (path != null && path.isNotEmpty && mounted) {
      widget.onRecordingComplete(path);
    } else if (mounted) {
      widget.onCancel();
    }
  }

  Future<void> _cancelRecording() async {
    _durationTimer?.cancel();
    _autoStopTimer?.cancel();
    _pulseController.stop();
    final path = await _recorder.stop();
    // Delete partial recording file
    if (path != null && path.isNotEmpty) {
      try {
        await File(path).delete();
      } catch (_) {}
    }
    if (mounted) {
      widget.onCancel();
    }
  }

  String _formatDuration(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final s = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle bar
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2),
              ),
            ),

            // Duration display
            Text(
              _formatDuration(_elapsedSeconds),
              style: const TextStyle(
                fontSize: 40,
                fontWeight: FontWeight.w300,
                color: AppColors.textPrimary,
                fontFeatures: [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(height: 8),

            // Status text
            Text(
              _isRecording
                  ? '正在录音...'
                  : '准备录音',
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 24),

            // Animated recording indicator + controls
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Cancel button
                GestureDetector(
                  onTap: _cancelRecording,
                  child: Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppColors.divider),
                    ),
                    child: const Icon(
                      Icons.close,
                      color: AppColors.textSecondary,
                      size: 24,
                    ),
                  ),
                ),

                // Pulsing record/stop button
                GestureDetector(
                  onTap: _isRecording
                      ? _stopRecording
                      : null,
                  child: AnimatedBuilder(
                    animation: _pulseController,
                    builder: (context, child) {
                      final scale = _isRecording
                          ? 1.0 + (_pulseController.value * 0.15)
                          : 1.0;
                      return Transform.scale(
                        scale: scale,
                        child: Container(
                          width: 72,
                          height: 72,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: const LinearGradient(
                              colors: [Color(0xFFEF4444), Color(0xFFDC2626)],
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFFEF4444)
                                    .withValues(alpha: 0.3 + _pulseController.value * 0.2),
                                blurRadius: 16 + _pulseController.value * 8,
                                spreadRadius: _pulseController.value * 4,
                              ),
                            ],
                          ),
                          child: Icon(
                            _isRecording
                                ? Icons.stop_rounded
                                : Icons.mic,
                            color: Colors.white,
                            size: 32,
                          ),
                        ),
                      );
                    },
                  ),
                ),

                // Spacer for symmetry
                const SizedBox(width: 56, height: 56),
              ],
            ),

            const SizedBox(height: 16),

            // Max duration hint
            const Text(
              '最长 ${_maxDurationSeconds}s',
              style: TextStyle(
                fontSize: 12,
                color: AppColors.textTertiary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
