import 'package:flutter/material.dart';
import '../../domain/entities/itinerary_version.dart';

/// 替代方案选择对话框
class AlternativeSelectorDialog extends StatefulWidget {
  final String activityTitle;
  final List<SelectableAlternative> alternatives;
  final Function(SelectableAlternative) onSelect;
  final VoidCallback? onRequestMore;
  final bool isLoading;

  const AlternativeSelectorDialog({
    super.key,
    required this.activityTitle,
    required this.alternatives,
    required this.onSelect,
    this.onRequestMore,
    this.isLoading = false,
  });

  @override
  State<AlternativeSelectorDialog> createState() =>
      _AlternativeSelectorDialogState();
}

class _AlternativeSelectorDialogState extends State<AlternativeSelectorDialog> {
  SelectableAlternative? _selectedAlternative;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 500, maxHeight: 600),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(16),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.swap_horiz,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '选择替代方案',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          '替换: ${widget.activityTitle}',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),

            // Content
            Flexible(
              child: widget.isLoading
                  ? const Center(
                      child: Padding(
                        padding: EdgeInsets.all(32),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircularProgressIndicator(),
                            SizedBox(height: 16),
                            Text('正在搜索替代方案...'),
                          ],
                        ),
                      ),
                    )
                  : widget.alternatives.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(32),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Icons.search_off,
                                  size: 48,
                                  color: Colors.grey[400],
                                ),
                                const SizedBox(height: 16),
                                const Text('暂无替代方案'),
                                if (widget.onRequestMore != null) ...[
                                  const SizedBox(height: 16),
                                  ElevatedButton(
                                    onPressed: widget.onRequestMore,
                                    child: const Text('搜索更多'),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        )
                      : ListView.builder(
                          shrinkWrap: true,
                          padding: const EdgeInsets.all(16),
                          itemCount: widget.alternatives.length,
                          itemBuilder: (context, index) {
                            final alt = widget.alternatives[index];
                            final isSelected = _selectedAlternative?.id == alt.id;

                            return _AlternativeCard(
                              alternative: alt,
                              isSelected: isSelected,
                              onTap: () {
                                setState(() {
                                  _selectedAlternative = alt;
                                });
                              },
                            );
                          },
                        ),
            ),

            // Footer
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey[50],
                borderRadius: const BorderRadius.vertical(
                  bottom: Radius.circular(16),
                ),
              ),
              child: Row(
                children: [
                  if (widget.onRequestMore != null)
                    TextButton.icon(
                      onPressed: widget.onRequestMore,
                      icon: const Icon(Icons.refresh, size: 18),
                      label: const Text('刷新推荐'),
                    ),
                  const Spacer(),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _selectedAlternative == null
                        ? null
                        : () {
                            widget.onSelect(_selectedAlternative!);
                            Navigator.pop(context);
                          },
                    child: const Text('确认替换'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AlternativeCard extends StatelessWidget {
  final SelectableAlternative alternative;
  final bool isSelected;
  final VoidCallback onTap;

  const _AlternativeCard({
    required this.alternative,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: isSelected
            ? BorderSide(color: theme.colorScheme.primary, width: 2)
            : BorderSide.none,
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title row
              Row(
                children: [
                  if (isSelected)
                    Container(
                      margin: const EdgeInsets.only(right: 8),
                      child: Icon(
                        Icons.check_circle,
                        color: theme.colorScheme.primary,
                        size: 20,
                      ),
                    ),
                  Expanded(
                    child: Text(
                      alternative.title,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: isSelected ? theme.colorScheme.primary : null,
                      ),
                    ),
                  ),
                  if (alternative.estimatedCost != null)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.orange[50],
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '¥${alternative.estimatedCost!.toStringAsFixed(0)}',
                        style: TextStyle(
                          color: Colors.orange[800],
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                ],
              ),

              // Location
              if (alternative.location != null &&
                  alternative.location!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(Icons.location_on, size: 14, color: Colors.grey[600]),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        alternative.location!,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey[600],
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],

              // Description
              if (alternative.description != null &&
                  alternative.description!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  alternative.description!,
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[700],
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],

              // Reason tag
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primaryContainer.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.lightbulb_outline,
                      size: 14,
                      color: theme.colorScheme.primary,
                    ),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        alternative.reason,
                        style: TextStyle(
                          fontSize: 12,
                          color: theme.colorScheme.primary,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),

              // Similarity score
              if (alternative.similarityScore != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Text(
                      '相似度: ',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[500],
                      ),
                    ),
                    Container(
                      width: 60,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey[200],
                        borderRadius: BorderRadius.circular(2),
                      ),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: alternative.similarityScore!,
                        child: Container(
                          decoration: BoxDecoration(
                            color: _getSimilarityColor(alternative.similarityScore!),
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${(alternative.similarityScore! * 100).toInt()}%',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _getSimilarityColor(double score) {
    if (score >= 0.8) return Colors.green;
    if (score >= 0.6) return Colors.blue;
    if (score >= 0.4) return Colors.orange;
    return Colors.grey;
  }
}
