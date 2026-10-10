import 'dart:convert';
import 'package:flutter/material.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/tool_execution_step.dart';
import 'key_results_widget.dart';
import 'progress_log_widget.dart';
import 'tool_display_names.dart';

/// Renders a single tool execution step in the generation sequence.
///
/// Three visual phases:
/// 1. **Running**: spinner + tool name + "..." label + real-time progress log
/// 2. **Complete/Success**: check icon + tool name + summary + duration badge
/// 3. **Error**: error icon + tool name + error message
///
/// Details (arguments, result, key results, full log) are collapsed by default,
/// expandable on tap.
class ToolStepWidget extends StatelessWidget {
  final ToolExecutionStep tool;
  final bool isExpanded;
  final VoidCallback? onToggle;

  const ToolStepWidget({
    super.key,
    required this.tool,
    required this.isExpanded,
    this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final isRunning = tool.status == 'start';
    final isError = tool.status == 'error';
    final displayName = getToolDisplayName(tool.toolName);
    final hasProgressLog = tool.progressLog.isNotEmpty;

    final hasArguments = tool.arguments != null && (tool.arguments as Map).isNotEmpty;
    final hasResult = tool.result != null && (tool.result as Map).isNotEmpty;
    final hasKeyResults = tool.keyResults != null && tool.keyResults!.isNotEmpty;
    final hasSummary = tool.summary != null && tool.summary!.isNotEmpty;
    final hasDuration = tool.durationMs != null;
    final hasDetails = hasArguments
        || hasResult
        || hasKeyResults
        || (!isRunning && (hasProgressLog || hasSummary || hasDuration));

    // Phase colors
    final Color bgColor;
    final Color iconColor;
    final IconData? statusIcon;
    if (isRunning) {
      bgColor = AppColors.warning.withValues(alpha: 0.08);
      iconColor = AppColors.warning;
      statusIcon = null; // spinner instead
    } else if (isError) {
      bgColor = AppColors.error.withValues(alpha: 0.08);
      iconColor = AppColors.error;
      statusIcon = Icons.error_outline;
    } else {
      bgColor = AppColors.success.withValues(alpha: 0.08);
      iconColor = AppColors.success;
      statusIcon = Icons.check_circle;
    }

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: hasDetails ? onToggle : null,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                // Phase 1: spinner, Phase 2/3: icon
                if (isRunning)
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(iconColor),
                    ),
                  )
                else
                  Icon(statusIcon, size: 14, color: iconColor),
                const SizedBox(width: 6),
                // Tool display name
                Text(
                  displayName,
                  style: AppTextStyles.caption.copyWith(
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
                    fontSize: 12,
                  ),
                ),
                // Duration badge (phase 2 only)
                if (!isRunning && hasDuration) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(
                      color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      tool.durationMs! < 1000
                          ? '${tool.durationMs}ms'
                          : '${(tool.durationMs! / 1000).toStringAsFixed(1)}s',
                      style: AppTextStyles.overline.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                        fontSize: 10,
                      ),
                    ),
                  ),
                ],
                // Summary arrow + text
                if (!isRunning && hasSummary) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Text(
                      '\u2192',
                      style: TextStyle(fontSize: 11, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      tool.summary!,
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        fontSize: 11,
                      ),
                      maxLines: isExpanded ? null : 1,
                      overflow: isExpanded ? null : TextOverflow.ellipsis,
                    ),
                  ),
                ] else if (isRunning) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Text(
                      '\u2192',
                      style: TextStyle(fontSize: 11, color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      '\u6b63\u5728\u6267\u884c...',
                      style: AppTextStyles.caption.copyWith(
                        color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ),
                ] else
                  const Spacer(),
                // Expand/collapse chevron
                if (hasDetails)
                  Icon(
                    isExpanded ? Icons.expand_less : Icons.expand_more,
                    size: 16,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
              ],
            ),
            // Real-time progress log (visible while running, collapsed after)
            if (isRunning && hasProgressLog)
              ProgressLogContainer(entries: tool.progressLog),
            // Expandable details section
            if (hasDetails && isExpanded) ...[
              const SizedBox(height: 8),
              const Divider(height: 1),
              const SizedBox(height: 8),
              if (hasKeyResults) ...[
                KeyResultsDisplay(keyResults: tool.keyResults!),
                const SizedBox(height: 8),
              ],
              if (hasSummary && !hasKeyResults) ...[
                Text(
                  tool.summary!,
                  style: AppTextStyles.caption.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    height: 1.5,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 8),
              ],
              if (!isRunning && hasProgressLog) ...[
                Text(
                  '\u6267\u884c\u65e5\u5fd7:',
                  style: AppTextStyles.caption.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 4),
                ProgressLogContainer(entries: tool.progressLog, maxHeight: 100),
                const SizedBox(height: 8),
              ],
              if (hasArguments) ...[
                Text(
                  '\u8f93\u5165\u53c2\u6570:',
                  style: AppTextStyles.caption.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Theme.of(context).scaffoldBackgroundColor,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: Theme.of(context).dividerColor),
                  ),
                  child: Text(
                    _formatJson(tool.arguments),
                    style: AppTextStyles.caption.copyWith(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                ),
              ],
              if (hasResult) ...[
                const SizedBox(height: 8),
                Text(
                  '\u8fd4\u56de\u7ed3\u679c:',
                  style: AppTextStyles.caption.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 4),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Theme.of(context).scaffoldBackgroundColor,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: Theme.of(context).dividerColor),
                  ),
                  child: Text(
                    _formatJson(tool.result),
                    style: AppTextStyles.caption.copyWith(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                    maxLines: 20,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  String _formatJson(dynamic data) {
    try {
      const encoder = JsonEncoder.withIndent('  ');
      return encoder.convert(data);
    } catch (e) {
      return data.toString();
    }
  }
}
