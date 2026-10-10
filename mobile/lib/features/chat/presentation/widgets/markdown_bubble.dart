import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/generation_step.dart';
import 'stream_markdown_buffer.dart';

/// Renders markdown content for chat messages.
///
/// Supports two modes:
/// - **User messages**: white text on primary color background.
/// - **Assistant messages**: dark text on white background.
///
/// When [isStreaming] is true, uses [StreamMarkdownBuffer] to hold back
/// incomplete markdown tokens so the renderer does not flash malformed output.
class MarkdownBubbleContent extends StatelessWidget {
  final String content;
  final bool isUser;
  final bool isStreaming;

  const MarkdownBubbleContent({
    super.key,
    required this.content,
    required this.isUser,
    this.isStreaming = false,
  });

  static final _buffer = StreamMarkdownBuffer();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textColor = isUser ? Colors.white : theme.colorScheme.onSurface;
    final linkColor = isUser ? Colors.white.withValues(alpha: 0.9) : theme.colorScheme.primary;

    final displayContent = isStreaming && !isUser
        ? _buffer.process(content).renderable
        : content;

    if (displayContent.isEmpty) return const SizedBox.shrink();

    return MarkdownBody(
      data: displayContent,
      selectable: false,
      softLineBreak: true,
      onTapLink: (text, href, title) {
        if (href != null) {
          _handleLinkTap(context, href);
        }
      },
      styleSheet: _buildStyleSheet(textColor, linkColor, isUser,
          theme.extension<AppColorsExtension>()!.inputBackground,
          theme.colorScheme.primary),
    );
  }

  static MarkdownStyleSheet _buildStyleSheet(
    Color textColor,
    Color linkColor,
    bool isUser,
    Color inputBackground,
    Color primaryColor,
  ) {
    return MarkdownStyleSheet(
      p: AppTextStyles.bodyText1.copyWith(
        color: textColor,
        height: 1.5,
      ),
      h1: AppTextStyles.headline1.copyWith(
        color: textColor,
        fontSize: 20,
        fontWeight: FontWeight.bold,
      ),
      h2: AppTextStyles.headline2.copyWith(
        color: textColor,
        fontSize: 18,
        fontWeight: FontWeight.bold,
      ),
      h3: AppTextStyles.headline3.copyWith(
        color: textColor,
        fontSize: 16,
        fontWeight: FontWeight.w600,
      ),
      h4: AppTextStyles.bodyText1.copyWith(
        color: textColor,
        fontSize: 15,
        fontWeight: FontWeight.w600,
      ),
      h5: AppTextStyles.bodyText1.copyWith(
        color: textColor,
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
      h6: AppTextStyles.bodyText2.copyWith(
        color: textColor,
        fontWeight: FontWeight.w600,
      ),
      strong: TextStyle(
        color: textColor,
        fontWeight: FontWeight.bold,
      ),
      em: TextStyle(
        color: textColor,
        fontStyle: FontStyle.italic,
      ),
      a: TextStyle(
        color: linkColor,
        decoration: TextDecoration.underline,
        decorationColor: linkColor.withValues(alpha: 0.5),
      ),
      listBullet: AppTextStyles.bodyText1.copyWith(
        color: textColor,
      ),
      code: TextStyle(
        color: textColor,
        backgroundColor: isUser
            ? Colors.white.withValues(alpha: 0.15)
            : inputBackground,
        fontFamily: 'monospace',
        fontSize: 13,
      ),
      codeblockDecoration: BoxDecoration(
        color: isUser
            ? Colors.white.withValues(alpha: 0.1)
            : inputBackground,
        borderRadius: BorderRadius.circular(8),
      ),
      codeblockPadding: const EdgeInsets.all(12),
      blockquote: AppTextStyles.bodyText1.copyWith(
        color: textColor.withValues(alpha: 0.8),
        fontStyle: FontStyle.italic,
      ),
      blockquoteDecoration: BoxDecoration(
        border: Border(
          left: BorderSide(
            color: isUser
                ? Colors.white.withValues(alpha: 0.5)
                : primaryColor.withValues(alpha: 0.5),
            width: 3,
          ),
        ),
      ),
      blockquotePadding: const EdgeInsets.only(left: 12),
      horizontalRuleDecoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: textColor.withValues(alpha: 0.3),
            width: 1,
          ),
        ),
      ),
      tableHead: TextStyle(
        color: textColor,
        fontWeight: FontWeight.bold,
      ),
      tableBody: TextStyle(
        color: textColor,
      ),
      tableBorder: TableBorder.all(
        color: textColor.withValues(alpha: 0.3),
        width: 1,
      ),
      h1Padding: const EdgeInsets.only(top: 8, bottom: 4),
      h2Padding: const EdgeInsets.only(top: 8, bottom: 4),
      h3Padding: const EdgeInsets.only(top: 6, bottom: 2),
      h4Padding: const EdgeInsets.only(top: 4, bottom: 2),
      pPadding: const EdgeInsets.symmetric(vertical: 2),
      listIndent: 20,
    );
  }

  static void _handleLinkTap(BuildContext context, String url) {
    if (url.startsWith('/')) {
      final uri = Uri.parse(url);
      final path = uri.path;

      if (path.startsWith('/research')) {
        final sessionId = uri.queryParameters['session'];
        if (sessionId != null) {
          context.push('/research/$sessionId');
        } else {
          context.push('/research');
        }
        return;
      } else if (path.startsWith('/discover/recommend/')) {
        context.push(url);
        return;
      } else if (path.startsWith('/members/')) {
        context.push(url);
        return;
      } else if (path.startsWith('/trips/')) {
        context.push(url);
        return;
      } else if (path.startsWith('/dates/')) {
        context.push(url);
        return;
      }

      try {
        context.push(url);
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('无法打开: $url'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    } else if (url.startsWith('http://') || url.startsWith('https://')) {
      _launchExternalUrl(context, url);
    }
  }

  static Future<void> _launchExternalUrl(BuildContext context, String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('无法打开链接: $url'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          ),
        );
      }
    }
  }
}

/// Renders a ContentStep from the generation sequence.
///
/// Uses [StreamMarkdownBuffer] for streaming content to avoid flashing
/// incomplete markdown.
class ContentStepWidget extends StatelessWidget {
  final ContentStep step;

  const ContentStepWidget({
    super.key,
    required this.step,
  });

  static final _buffer = StreamMarkdownBuffer();

  @override
  Widget build(BuildContext context) {
    final trimmed = step.content.trim();
    if (trimmed.isEmpty || trimmed == '(no content)' || trimmed == '(No content)') {
      return const SizedBox.shrink();
    }

    final displayContent = !step.isComplete
        ? _buffer.process(step.content).renderable
        : step.content;

    if (displayContent.isEmpty) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final onSurface = theme.colorScheme.onSurface;
    final primary = theme.colorScheme.primary;
    final ext = theme.extension<AppColorsExtension>()!;

    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: MarkdownBody(
        data: displayContent,
        selectable: false,
        softLineBreak: true,
        onTapLink: (text, href, title) {
          if (href != null) {
            MarkdownBubbleContent._handleLinkTap(context, href);
          }
        },
        styleSheet: MarkdownStyleSheet(
          p: AppTextStyles.bodyText1.copyWith(
            color: onSurface,
            height: 1.5,
          ),
          h1: AppTextStyles.headline1.copyWith(
            color: onSurface,
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
          h2: AppTextStyles.headline2.copyWith(
            color: onSurface,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
          h3: AppTextStyles.headline3.copyWith(
            color: onSurface,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
          strong: TextStyle(
            color: onSurface,
            fontWeight: FontWeight.bold,
          ),
          em: TextStyle(
            color: onSurface,
            fontStyle: FontStyle.italic,
          ),
          a: TextStyle(
            color: primary,
            decoration: TextDecoration.underline,
            decorationColor: primary.withValues(alpha: 0.5),
          ),
          listBullet: AppTextStyles.bodyText1.copyWith(
            color: onSurface,
          ),
          code: TextStyle(
            color: onSurface,
            backgroundColor: ext.inputBackground,
            fontFamily: 'monospace',
            fontSize: 13,
          ),
          codeblockDecoration: BoxDecoration(
            color: ext.inputBackground,
            borderRadius: BorderRadius.circular(8),
          ),
          codeblockPadding: const EdgeInsets.all(12),
          blockquote: AppTextStyles.bodyText1.copyWith(
            color: onSurface.withValues(alpha: 0.8),
            fontStyle: FontStyle.italic,
          ),
          blockquoteDecoration: BoxDecoration(
            border: Border(
              left: BorderSide(
                color: primary.withValues(alpha: 0.5),
                width: 3,
              ),
            ),
          ),
          blockquotePadding: const EdgeInsets.only(left: 12),
          tableBorder: TableBorder.all(
            color: onSurface.withValues(alpha: 0.3),
            width: 1,
          ),
          pPadding: const EdgeInsets.symmetric(vertical: 2),
          listIndent: 20,
        ),
      ),
    );
  }
}
