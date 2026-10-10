import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/generation_step.dart';

/// Renders a collapsible thinking/reasoning step in the generation sequence.
///
/// Shows a compact header with "思考中..." while streaming and "思考过程"
/// when complete. Tapping toggles the content visibility.
class ThinkingStepWidget extends StatelessWidget {
  final ThinkingStep step;
  final bool isExpanded;
  final VoidCallback? onToggle;

  const ThinkingStepWidget({
    super.key,
    required this.step,
    required this.isExpanded,
    this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    if (step.content.isEmpty && step.isComplete) return const SizedBox.shrink();

    final isStreaming = !step.isComplete;
    final hasContent = step.content.isNotEmpty;

    final previewText = hasContent ? step.content.split('\n').first.trim() : '';
    final truncatedPreview = previewText.length > 40
        ? '${previewText.substring(0, 40)}...'
        : previewText;

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: hasContent ? onToggle : null,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.12),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (isStreaming)
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        Theme.of(context).colorScheme.primary.withValues(alpha: 0.6),
                      ),
                    ),
                  )
                else
                  Icon(
                    Icons.psychology_outlined,
                    size: 14,
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.7),
                  ),
                const SizedBox(width: 6),
                Text(
                  isStreaming ? '思考中...' : '思考过程',
                  style: AppTextStyles.caption.copyWith(
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.8),
                    fontWeight: FontWeight.w500,
                    fontSize: 12,
                  ),
                ),
                if (!isExpanded && !isStreaming && hasContent) ...[
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      truncatedPreview,
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                        fontSize: 11,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ] else
                  const Spacer(),
                if (hasContent)
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 16,
                    color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5),
                  ),
              ],
            ),
            if (hasContent)
              AnimatedCrossFade(
                firstChild: const SizedBox.shrink(),
                secondChild: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(
                    step.content,
                    style: AppTextStyles.caption.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontStyle: FontStyle.italic,
                      height: 1.5,
                      fontSize: 12,
                    ),
                  ),
                ),
                crossFadeState: isExpanded
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 200),
              ),
          ],
        ),
      ),
    );
  }
}
