import 'package:flutter/material.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../data/models/memory_model.dart';

/// A card that shows contextual hints from the secretary
/// when related memories are found during conversation
class ContextHintCard extends StatelessWidget {
  final ContextCheckResult result;
  final VoidCallback? onDismiss;
  final VoidCallback? onTap;

  const ContextHintCard({
    super.key,
    required this.result,
    this.onDismiss,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (!result.hasInsight && result.relatedMemories.isEmpty) {
      return const SizedBox.shrink();
    }

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              const Color(0xFF667eea).withValues(alpha: 0.1),
              const Color(0xFF764ba2).withValues(alpha: 0.1),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: const Color(0xFF667eea).withValues(alpha: 0.3),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: const Color(0xFF667eea).withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.lightbulb_outline,
                    color: Color(0xFF667eea),
                    size: 16,
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  '💡 想起了相关的事情',
                  style: AppTextStyles.subtitle2.copyWith(
                    color: const Color(0xFF667eea),
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                if (onDismiss != null)
                  GestureDetector(
                    onTap: onDismiss,
                    child: Icon(
                      Icons.close,
                      size: 18,
                      color: AppColors.textTertiary,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            // Show insight content if available
            if (result.insight != null) ...[
              Text(
                result.insight!.content,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                  height: 1.5,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ] else if (result.relatedMemories.isNotEmpty) ...[
              // Show related memories
              ...result.relatedMemories.take(2).map((memory) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _MemoryHintItem(memory: memory),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}

class _MemoryHintItem extends StatelessWidget {
  final MemoryModel memory;

  const _MemoryHintItem({required this.memory});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(memory.typeIcon, style: const TextStyle(fontSize: 14)),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                memory.content,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 2),
              Text(
                '${memory.typeDisplayName} · ${memory.timeAgoText}',
                style: AppTextStyles.caption.copyWith(
                  color: AppColors.textTertiary,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// A compact inline hint that can be shown in the chat
class ContextHintInline extends StatelessWidget {
  final String content;
  final VoidCallback? onTap;

  const ContextHintInline({
    super.key,
    required this.content,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(left: 40, right: 16, bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0xFF667eea).withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: const Color(0xFF667eea).withValues(alpha: 0.2),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.lightbulb_outline,
              size: 14,
              color: Color(0xFF667eea),
            ),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                content,
                style: AppTextStyles.caption.copyWith(
                  color: const Color(0xFF667eea),
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
