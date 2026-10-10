import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../bloc/assistant_bloc.dart';
import 'voice_stream_widget.dart';

class ChatInput extends StatefulWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final VoidCallback onSend;
  final bool isLoading;
  final bool isStreaming;
  final int queuedCount;
  final bool isDisconnected;
  final VoidCallback? onStop;
  final String? placeholder;
  final void Function(String audioPath)? onVoiceMessage;
  /// Full-duplex: brief signal hint text (auto-dismisses after 2-3s)
  final String? signalHint;
  /// Full-duplex: signal type for hint styling (drives color/icon)
  final String? signalHintType;

  const ChatInput({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.onSend,
    this.isLoading = false,
    this.isStreaming = false,
    this.queuedCount = 0,
    this.isDisconnected = false,
    this.onStop,
    this.placeholder,
    this.onVoiceMessage,
    this.signalHint,
    this.signalHintType,
  });

  @override
  State<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends State<ChatInput> {
  bool _hasText = false;
  bool _isVoiceMode = false;

  @override
  void initState() {
    super.initState();
    _hasText = widget.controller.text.trim().isNotEmpty;
    widget.controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onTextChanged);
    super.dispose();
  }

  void _onTextChanged() {
    final hasText = widget.controller.text.trim().isNotEmpty;
    if (hasText != _hasText) {
      setState(() => _hasText = hasText);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final ext = theme.extension<AppColorsExtension>()!;
    final bool inputDisabled = widget.isDisconnected;

    final String hintText;
    if (widget.isDisconnected) {
      hintText = '网络已断开';
    } else {
      hintText = widget.placeholder ?? '跟秘书说点什么...';
    }

    return BlocListener<AssistantBloc, AssistantState>(
      listenWhen: (prev, next) {
        if (prev is! AssistantLoaded || next is! AssistantLoaded) return false;
        return prev.isVoiceStreaming != next.isVoiceStreaming;
      },
      listener: (context, state) {
        if (state is AssistantLoaded && !state.isVoiceStreaming && _isVoiceMode) {
          setState(() => _isVoiceMode = false);
        }
      },
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        decoration: BoxDecoration(
          color: ext.cardBackground,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05 * ext.shadowOpacity),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Full-duplex: signal accepted hint (replaces queue hint when active)
            if (widget.signalHint != null && widget.signalHint!.isNotEmpty) ...[
              _buildSignalHint(ext),
              const SizedBox(height: 8),
            ] else if (widget.isStreaming || widget.queuedCount > 0) ...[
              _buildQueueHint(ext),
              const SizedBox(height: 8),
            ],
            // Inline voice recording strip or normal text input
            if (_isVoiceMode)
              const VoiceStreamWidget()
            else
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: Container(
                      constraints: const BoxConstraints(maxHeight: 120),
                      decoration: BoxDecoration(
                        color: ext.inputBackground,
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: TextField(
                        controller: widget.controller,
                        focusNode: widget.focusNode,
                        enabled: !widget.isDisconnected,
                        maxLines: null,
                        keyboardType: TextInputType.multiline,
                        textInputAction: TextInputAction.newline,
                        style: AppTextStyles.bodyText1,
                        decoration: InputDecoration(
                          hintText: hintText,
                          hintStyle: AppTextStyles.bodyText1.copyWith(
                            color: ext.textHint,
                          ),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 20,
                            vertical: 12,
                          ),
                        ),
                        onSubmitted: (_) {
                          if (!widget.isDisconnected &&
                              widget.controller.text.trim().isNotEmpty) {
                            widget.onSend();
                          }
                        },
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  _buildActionArea(context, inputDisabled),
                ],
              ),
          ],
        ),
      ),
    );
  }

  /// Returns (color, icon) for a given signal type.
  ({Color color, IconData icon}) _signalHintStyle() {
    switch (widget.signalHintType) {
      case 'correction':
        return (color: Colors.orange, icon: Icons.refresh);
      case 'cancel':
        return (color: Colors.red, icon: Icons.cancel_outlined);
      case 'additive':
        return (color: Colors.blue, icon: Icons.add_circle_outline);
      case 'confirm':
        return (color: Colors.green, icon: Icons.check_circle_outline);
      case 'digression':
        return (color: Colors.deepPurple, icon: Icons.swap_horiz);
      default:
        return (color: Colors.green, icon: Icons.check_circle_outline);
    }
  }

  Widget _buildSignalHint(AppColorsExtension ext) {
    final style = _signalHintStyle();
    return GestureDetector(
      onTap: () {
        // Tap-to-dismiss: dispatch event via context
        final bloc = context.read<AssistantBloc>();
        bloc.add(const AssistantSignalHintDismissed());
      },
      child: AnimatedOpacity(
        opacity: widget.signalHint != null ? 1.0 : 0.0,
        duration: const Duration(milliseconds: 300),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: style.color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            children: [
              Icon(style.icon, size: 14, color: style.color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  widget.signalHint ?? '',
                  style: AppTextStyles.caption.copyWith(
                    color: style.color.withValues(alpha: 0.85),
                  ),
                ),
              ),
              Icon(
                Icons.close,
                size: 12,
                color: style.color.withValues(alpha: 0.5),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQueueHint(AppColorsExtension ext) {
    final tipText = widget.queuedCount > 0
        ? '已排队${widget.queuedCount}条消息，当前回复完成后自动发送'
        : '正在回复中，可继续发送新消息';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.schedule_rounded,
            size: 14,
            color: AppColors.primary,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              tipText,
              style: AppTextStyles.caption.copyWith(color: ext.textTertiary),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionArea(BuildContext context, bool inputDisabled) {
    if (widget.isStreaming) {
      return _buildStreamingButtons(inputDisabled);
    }
    return _buildActionButton(context, inputDisabled || widget.isLoading);
  }

  Widget _buildStreamingButtons(bool inputDisabled) {
    final canSend = _hasText && !inputDisabled;
    final canStop = widget.onStop != null;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildSendButton(
          key: const ValueKey('send-while-streaming'),
          enabled: canSend,
          onTap: canSend ? widget.onSend : null,
        ),
        const SizedBox(width: 8),
        GestureDetector(
          key: const ValueKey('stop'),
          onTap: canStop ? widget.onStop : null,
          child: Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: canStop
                  ? AppColors.error
                  : AppColors.error.withValues(alpha: 0.35),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: Icon(Icons.stop_rounded, color: Colors.white, size: 22),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActionButton(BuildContext context, bool inputDisabled) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 200),
      transitionBuilder: (child, animation) {
        return ScaleTransition(scale: animation, child: child);
      },
      child: _buildCurrentButton(context, inputDisabled),
    );
  }

  Widget _buildCurrentButton(BuildContext context, bool inputDisabled) {
    // Has text → send button
    if (_hasText && !widget.isLoading) {
      return _buildSendButton(
        key: const ValueKey('send'),
        enabled: !inputDisabled,
        onTap: inputDisabled ? null : widget.onSend,
      );
    }

    // Loading → spinner
    if (widget.isLoading) {
      return Container(
        key: const ValueKey('loading'),
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: AppColors.primary.withValues(alpha: 0.15),
          shape: BoxShape.circle,
        ),
        child: const Center(
          child: SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
            ),
          ),
        ),
      );
    }

    // Default → mic button (standalone green circle)
    return GestureDetector(
      key: const ValueKey('mic'),
      onTap: inputDisabled ? null : () => setState(() => _isVoiceMode = true),
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: inputDisabled
              ? AppColors.primary.withValues(alpha: 0.3)
              : AppColors.primary,
          shape: BoxShape.circle,
        ),
        child: const Center(
          child: Icon(Icons.mic, color: Colors.white, size: 22),
        ),
      ),
    );
  }

  Widget _buildSendButton({
    required Key key,
    required bool enabled,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      key: key,
      onTap: onTap,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: enabled
              ? AppColors.primary
              : AppColors.primary.withValues(alpha: 0.3),
          shape: BoxShape.circle,
        ),
        child: const Center(
          child:
              Icon(Icons.arrow_upward_rounded, color: Colors.white, size: 22),
        ),
      ),
    );
  }
}
