import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/research_session.dart';

class SynthesisPanel extends StatefulWidget {
  final String content;
  final List<SynthesisSource> sources;
  final bool isSynthesizing;
  final int selectedCount;
  final void Function(SynthesisFormat format) onGenerate;
  final VoidCallback onCopy;

  const SynthesisPanel({
    super.key,
    required this.content,
    required this.sources,
    required this.isSynthesizing,
    required this.selectedCount,
    required this.onGenerate,
    required this.onCopy,
  });

  @override
  State<SynthesisPanel> createState() => _SynthesisPanelState();
}

class _SynthesisPanelState extends State<SynthesisPanel> {
  SynthesisFormat _selectedFormat = SynthesisFormat.summary;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Format selector and generate button
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.white,
          child: Column(
            children: [
              // Format selector
              Row(
                children: [
                  const Text('输出格式: '),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SegmentedButton<SynthesisFormat>(
                      segments: const [
                        ButtonSegment(
                          value: SynthesisFormat.summary,
                          label: Text('摘要'),
                          icon: Icon(Icons.short_text, size: 18),
                        ),
                        ButtonSegment(
                          value: SynthesisFormat.outline,
                          label: Text('大纲'),
                          icon: Icon(Icons.format_list_bulleted, size: 18),
                        ),
                        ButtonSegment(
                          value: SynthesisFormat.detailed,
                          label: Text('详细'),
                          icon: Icon(Icons.article, size: 18),
                        ),
                      ],
                      selected: {_selectedFormat},
                      onSelectionChanged: (Set<SynthesisFormat> selection) {
                        setState(() {
                          _selectedFormat = selection.first;
                        });
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Generate button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: widget.isSynthesizing || widget.selectedCount == 0
                      ? null
                      : () => widget.onGenerate(_selectedFormat),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  icon: widget.isSynthesizing
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Icon(Icons.auto_awesome),
                  label: Text(
                    widget.isSynthesizing
                        ? '正在生成...'
                        : '生成报告 (${widget.selectedCount} 项)',
                    style: AppTextStyles.button.copyWith(color: Colors.white),
                  ),
                ),
              ),
            ],
          ),
        ),
        // Content area
        Expanded(
          child: widget.content.isEmpty
              ? _buildEmptyState()
              : _buildContent(),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.article_outlined,
              size: 64,
              color: AppColors.textTertiary,
            ),
            const SizedBox(height: 16),
            Text(
              '还没有生成报告',
              style: AppTextStyles.bodyText1.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '选择搜索结果或添加内容后，点击上方按钮生成综合报告',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Copy button
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            TextButton.icon(
              onPressed: widget.onCopy,
              icon: const Icon(Icons.copy, size: 18),
              label: const Text('复制'),
            ),
          ],
        ),
        // Report content
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 10,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: SelectableText(
            widget.content,
            style: AppTextStyles.bodyText1.copyWith(
              height: 1.6,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        // Sources
        if (widget.sources.isNotEmpty) ...[
          const SizedBox(height: 24),
          Text(
            '参考来源',
            style: AppTextStyles.subtitle1.copyWith(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          ...widget.sources.map((source) => _buildSourceItem(source)),
        ],
      ],
    );
  }

  Widget _buildSourceItem(SynthesisSource source) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: () => _launchUrl(source.url),
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppColors.divider),
          ),
          child: Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Icon(
                  Icons.link,
                  size: 16,
                  color: AppColors.primary,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  source.title,
                  style: AppTextStyles.bodyText2.copyWith(
                    color: AppColors.primary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(
                Icons.open_in_new,
                size: 16,
                color: AppColors.textSecondary,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}
