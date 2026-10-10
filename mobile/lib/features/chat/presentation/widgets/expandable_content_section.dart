import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';

/// A reusable expandable section that renders markdown content.
///
/// Used by all card bubble widgets to display the AI's text analysis alongside
/// structured card data. When [content] is substantial (>200 chars), the
/// section starts expanded so the user sees the AI's analysis first.
class ExpandableContentSection extends StatefulWidget {
  final String content;
  final String title;
  final bool? initiallyExpanded;

  const ExpandableContentSection({
    super.key,
    required this.content,
    this.title = 'AI 分析建议',
    this.initiallyExpanded,
  });

  @override
  State<ExpandableContentSection> createState() =>
      _ExpandableContentSectionState();
}

class _ExpandableContentSectionState extends State<ExpandableContentSection> {
  late bool _expanded;

  @override
  void initState() {
    super.initState();
    _expanded =
        widget.initiallyExpanded ?? (widget.content.length > 200);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Theme.of(context).extension<AppColorsExtension>()!.cardBackground,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05 * Theme.of(context).extension<AppColorsExtension>()!.shadowOpacity),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header - toggles expansion
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.vertical(
              top: const Radius.circular(12),
              bottom: _expanded ? Radius.zero : const Radius.circular(12),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Icon(Icons.lightbulb_outline,
                      size: 16, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.title,
                          style: AppTextStyles.subtitle2.copyWith(
                            color: Theme.of(context).colorScheme.onSurface,
                            fontSize: 13,
                          ),
                        ),
                        if (!_expanded)
                          Text(
                            _extractPreview(widget.content),
                            style: AppTextStyles.caption.copyWith(
                              color: Theme.of(context).extension<AppColorsExtension>()!.textTertiary,
                              fontSize: 11,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                      ],
                    ),
                  ),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
            ),
          ),
          // Expandable content
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: Container(
              constraints: const BoxConstraints(maxHeight: 400),
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                child: MarkdownBody(
                  data: widget.content,
                  selectable: false,
                  softLineBreak: true,
                  onTapLink: (text, href, title) {
                    if (href != null) _handleLinkTap(context, href);
                  },
                  styleSheet: _markdownStyle(),
                ),
              ),
            ),
            crossFadeState:
                _expanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 200),
          ),
        ],
      ),
    );
  }

  /// Extract a short preview from the markdown content for collapsed state.
  static String _extractPreview(String content) {
    for (final line in content.split('\n')) {
      final trimmed = line.trim();
      if (trimmed.isEmpty) continue;
      if (trimmed.startsWith('#')) continue;
      if (trimmed.startsWith('---')) continue;
      final clean = trimmed
          .replaceAll(RegExp(r'\*+'), '')
          .replaceAll(RegExp(r'`+'), '')
          .replaceAll(RegExp(r'\[([^\]]+)\]\([^)]+\)'), r'$1')
          .trim();
      if (clean.isNotEmpty) return clean;
    }
    return '点击展开查看详情';
  }

  MarkdownStyleSheet _markdownStyle() {
    return MarkdownStyleSheet(
      p: AppTextStyles.bodyText2.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
        height: 1.5,
        fontSize: 13,
      ),
      h2: AppTextStyles.subtitle2.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
        fontSize: 15,
        fontWeight: FontWeight.bold,
      ),
      h3: AppTextStyles.subtitle2.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
        fontSize: 14,
        fontWeight: FontWeight.w600,
      ),
      strong: TextStyle(
        fontWeight: FontWeight.bold,
        color: Theme.of(context).colorScheme.onSurface,
      ),
      em: TextStyle(
        fontStyle: FontStyle.italic,
        color: Theme.of(context).colorScheme.onSurface,
      ),
      listBullet: AppTextStyles.bodyText2.copyWith(
        color: Theme.of(context).colorScheme.onSurface,
        fontSize: 13,
      ),
      a: TextStyle(
        color: Theme.of(context).colorScheme.primary,
        decoration: TextDecoration.underline,
        decorationColor: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5),
      ),
      blockquoteDecoration: BoxDecoration(
        border: Border(
          left: BorderSide(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5),
            width: 3,
          ),
        ),
      ),
      blockquotePadding: const EdgeInsets.only(left: 12),
      horizontalRuleDecoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
      ),
      pPadding: const EdgeInsets.symmetric(vertical: 2),
      h2Padding: const EdgeInsets.only(top: 8, bottom: 4),
      h3Padding: const EdgeInsets.only(top: 6, bottom: 2),
      listIndent: 20,
    );
  }

  void _handleLinkTap(BuildContext context, String url) {
    if (url.startsWith('/')) {
      context.push(url);
    } else if (url.startsWith('http://') || url.startsWith('https://')) {
      launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    }
  }
}
