import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:shimmer/shimmer.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/notebook.dart';
import '../bloc/notebook_bloc.dart';

// Helper extension for haptic feedback
extension HapticHelper on BuildContext {
  void lightHaptic() => HapticFeedback.lightImpact();
  void mediumHaptic() => HapticFeedback.mediumImpact();
  void heavyHaptic() => HapticFeedback.heavyImpact();
  void selectionHaptic() => HapticFeedback.selectionClick();
}

class NotebookDetailPage extends StatefulWidget {
  final String notebookId;

  const NotebookDetailPage({
    super.key,
    required this.notebookId,
  });

  @override
  State<NotebookDetailPage> createState() => _NotebookDetailPageState();
}

class _NotebookDetailPageState extends State<NotebookDetailPage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _chatController = TextEditingController();
  final TextEditingController _urlController = TextEditingController();
  final TextEditingController _noteController = TextEditingController();
  final TextEditingController _noteTitleController = TextEditingController();
  final ScrollController _chatScrollController = ScrollController();
  final ScrollController _summaryScrollController = ScrollController();

  // Source filter state
  SourceType? _selectedSourceFilter;

  // Source search state
  bool _isSearching = false;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotebookBloc>().add(
        LoadNotebookDetailEvent(notebookId: widget.notebookId),
      );
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _chatController.dispose();
    _urlController.dispose();
    _noteController.dispose();
    _noteTitleController.dispose();
    _chatScrollController.dispose();
    _summaryScrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<NotebookBloc, NotebookState>(
      listener: (context, state) {
        if (state is NotebookError) {
          final bloc = context.read<NotebookBloc>();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Row(
                children: [
                  Icon(
                    _getErrorIcon(state.errorType),
                    color: Colors.white,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(child: Text(state.userMessage)),
                ],
              ),
              backgroundColor: Colors.red,
              behavior: SnackBarBehavior.floating,
              action: state.canRetry
                  ? SnackBarAction(
                      label: '重试',
                      textColor: Colors.white,
                      onPressed: () {
                        bloc.add(const RetryLastOperationEvent());
                      },
                    )
                  : null,
            ),
          );
        } else if (state is SourceAdded) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('来源添加成功'),
              backgroundColor: AppColors.success,
            ),
          );
        }
      },
      builder: (context, state) {
        if (state is NotebookLoading) {
          return _buildLoadingSkeleton(context);
        }

        if (state is NotebookDetailLoaded) {
          return _buildContent(context, state);
        }

        if (state is NotebookError) {
          return _buildErrorState(context, state);
        }

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
              onPressed: () => Navigator.of(context).pop(),
            ),
          ),
          body: const Center(child: Text('加载失败')),
        );
      },
    );
  }

  Widget _buildLoadingSkeleton(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Shimmer.fromColors(
          baseColor: Colors.grey[300]!,
          highlightColor: Colors.grey[100]!,
          child: Container(
            width: 150,
            height: 20,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Shimmer.fromColors(
            baseColor: Colors.grey[300]!,
            highlightColor: Colors.grey[100]!,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: List.generate(3, (index) => Container(
                  width: 80,
                  height: 24,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(4),
                  ),
                )),
              ),
            ),
          ),
        ),
      ),
      body: Shimmer.fromColors(
        baseColor: Colors.grey[300]!,
        highlightColor: Colors.grey[100]!,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              // Action buttons skeleton
              Row(
                children: [
                  Expanded(
                    child: Container(
                      height: 44,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Container(
                      height: 44,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // Source cards skeleton
              ...List.generate(4, (index) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  height: 80,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              )),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getErrorIcon(NotebookErrorType errorType) {
    switch (errorType) {
      case NotebookErrorType.network:
        return Icons.wifi_off;
      case NotebookErrorType.server:
        return Icons.cloud_off;
      case NotebookErrorType.notFound:
        return Icons.search_off;
      case NotebookErrorType.validation:
        return Icons.warning_amber;
      case NotebookErrorType.timeout:
        return Icons.timer_off;
      case NotebookErrorType.unknown:
        return Icons.error_outline;
    }
  }

  Widget _buildErrorState(BuildContext context, NotebookError state) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text('知识库'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(40),
                ),
                child: Icon(
                  _getErrorIcon(state.errorType),
                  size: 40,
                  color: Colors.red,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                state.errorType.displayName,
                style: AppTextStyles.headline6.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                state.userMessage,
                style: AppTextStyles.bodyText2.copyWith(
                  color: AppColors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              if (state.canRetry)
                ElevatedButton.icon(
                  onPressed: () {
                    context.read<NotebookBloc>().add(const RetryLastOperationEvent());
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('重试'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  ),
                ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('返回'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, NotebookDetailLoaded state) {
    final notebook = state.notebook;
    final color = _parseColor(notebook.color);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          children: [
            Text(notebook.icon, style: const TextStyle(fontSize: 20)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                notebook.name,
                style: AppTextStyles.headline6.copyWith(
                  color: AppColors.textPrimary,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.ios_share, color: AppColors.textPrimary),
            onPressed: notebook.totalSources > 0
                ? () => _showExportOptions(context, state)
                : null,
            tooltip: '导出知识库',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: color,
          unselectedLabelColor: AppColors.textSecondary,
          indicatorColor: color,
          tabs: [
            Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.source_outlined, size: 18),
                  const SizedBox(width: 4),
                  Text('来源 (${notebook.totalSources})'),
                ],
              ),
            ),
            const Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.chat_outlined, size: 18),
                  SizedBox(width: 4),
                  Text('问答'),
                ],
              ),
            ),
            const Tab(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.summarize_outlined, size: 18),
                  SizedBox(width: 4),
                  Text('摘要'),
                ],
              ),
            ),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSourcesTab(context, state),
          _buildChatTab(context, state),
          _buildSummaryTab(context, state),
        ],
      ),
    );
  }

  Widget _buildSourcesTab(BuildContext context, NotebookDetailLoaded state) {
    final notebook = state.notebook;
    final isAdding = state.isAddingSource;

    // Filter sources based on selected filter
    var filteredSources = _selectedSourceFilter == null
        ? notebook.sources
        : notebook.sources.where((s) => s.type == _selectedSourceFilter).toList();

    // Apply search filter
    if (_searchQuery.isNotEmpty) {
      final query = _searchQuery.toLowerCase();
      filteredSources = filteredSources.where((s) {
        final titleMatch = s.displayTitle.toLowerCase().contains(query);
        final contentMatch = s.originalContent?.toLowerCase().contains(query) ?? false;
        final urlMatch = s.originalUrl?.toLowerCase().contains(query) ?? false;
        return titleMatch || contentMatch || urlMatch;
      }).toList();
    }

    return Column(
      children: [
        // Add source buttons
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.white,
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: isAdding ? null : () => _showAddUrlDialog(context),
                      icon: isAdding
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.link, size: 18),
                      label: Text(isAdding ? '添加中...' : '添加链接'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: isAdding ? null : () => _showAddNoteDialog(context),
                      icon: const Icon(Icons.note_add, size: 18),
                      label: const Text('添加笔记'),
                    ),
                  ),
                ],
              ),
              // Filter and search (only show if there are sources)
              if (notebook.sources.isNotEmpty) ...[
                const SizedBox(height: 12),
                // Search bar
                AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  height: _isSearching ? 44 : 0,
                  child: _isSearching
                      ? TextField(
                          controller: _searchController,
                          autofocus: true,
                          decoration: InputDecoration(
                            hintText: '搜索来源...',
                            prefixIcon: const Icon(Icons.search, size: 20),
                            suffixIcon: IconButton(
                              icon: const Icon(Icons.close, size: 20),
                              onPressed: () {
                                setState(() {
                                  _isSearching = false;
                                  _searchQuery = '';
                                  _searchController.clear();
                                });
                              },
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(22),
                              borderSide: BorderSide.none,
                            ),
                            filled: true,
                            fillColor: AppColors.background,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                          ),
                          onChanged: (value) {
                            setState(() => _searchQuery = value);
                          },
                        )
                      : const SizedBox.shrink(),
                ),
                if (_isSearching) const SizedBox(height: 8),
                // Filter row
                Row(
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _buildFilterChip(
                              label: '全部',
                              count: notebook.sources.length,
                              isSelected: _selectedSourceFilter == null,
                              onTap: () {
                                HapticFeedback.selectionClick();
                                setState(() => _selectedSourceFilter = null);
                              },
                            ),
                            const SizedBox(width: 8),
                            if (notebook.urlCount > 0)
                              _buildFilterChip(
                                label: '链接',
                                count: notebook.urlCount,
                                isSelected: _selectedSourceFilter == SourceType.url,
                                onTap: () {
                                  HapticFeedback.selectionClick();
                                  setState(() => _selectedSourceFilter = SourceType.url);
                                },
                                icon: Icons.link,
                              ),
                            if (notebook.urlCount > 0) const SizedBox(width: 8),
                            if (notebook.textCount > 0)
                              _buildFilterChip(
                                label: '笔记',
                                count: notebook.textCount,
                                isSelected: _selectedSourceFilter == SourceType.text,
                                onTap: () {
                                  HapticFeedback.selectionClick();
                                  setState(() => _selectedSourceFilter = SourceType.text);
                                },
                                icon: Icons.note,
                              ),
                          ],
                        ),
                      ),
                    ),
                    // Search button
                    if (!_isSearching)
                      IconButton(
                        icon: const Icon(Icons.search, size: 22),
                        onPressed: () => setState(() => _isSearching = true),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                        tooltip: '搜索',
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
        // Sources list with refresh
        Expanded(
          child: notebook.sources.isEmpty
              ? _buildEmptySourcesState()
              : filteredSources.isEmpty
                  ? _buildNoFilterResultsState()
                  : RefreshIndicator(
                      onRefresh: () async {
                        context.read<NotebookBloc>().add(
                          LoadNotebookDetailEvent(notebookId: widget.notebookId),
                        );
                      },
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: filteredSources.length,
                        itemBuilder: (context, index) {
                          return TweenAnimationBuilder<double>(
                            tween: Tween(begin: 0.0, end: 1.0),
                            duration: Duration(milliseconds: 300 + (index * 50).clamp(0, 300)),
                            curve: Curves.easeOutCubic,
                            builder: (context, value, child) {
                              return Transform.translate(
                                offset: Offset(0, 20 * (1 - value)),
                                child: Opacity(
                                  opacity: value,
                                  child: child,
                                ),
                              );
                            },
                            child: _buildSourceCard(context, filteredSources[index]),
                          );
                        },
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _buildFilterChip({
    required String label,
    required int count,
    required bool isSelected,
    required VoidCallback onTap,
    IconData? icon,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : AppColors.background,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppColors.primary : Colors.transparent,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(
                icon,
                size: 14,
                color: isSelected ? Colors.white : AppColors.textSecondary,
              ),
              const SizedBox(width: 4),
            ],
            Text(
              '$label ($count)',
              style: AppTextStyles.caption.copyWith(
                color: isSelected ? Colors.white : AppColors.textSecondary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNoFilterResultsState() {
    final hasSearchQuery = _searchQuery.isNotEmpty;
    final hasFilter = _selectedSourceFilter != null;

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            hasSearchQuery ? Icons.search_off : Icons.filter_list_off,
            size: 48,
            color: AppColors.textTertiary.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 12),
          Text(
            hasSearchQuery
                ? '没有找到 "$_searchQuery"'
                : '没有符合筛选条件的内容',
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (hasSearchQuery)
                TextButton(
                  onPressed: () => setState(() {
                    _searchQuery = '';
                    _searchController.clear();
                  }),
                  child: const Text('清除搜索'),
                ),
              if (hasSearchQuery && hasFilter) const SizedBox(width: 8),
              if (hasFilter)
                TextButton(
                  onPressed: () => setState(() => _selectedSourceFilter = null),
                  child: const Text('清除筛选'),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptySourcesState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.inbox_outlined,
            size: 64,
            color: AppColors.textTertiary.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            '暂无内容来源',
            style: AppTextStyles.subtitle1.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '添加网页链接或笔记来构建你的知识库',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSourceCard(BuildContext context, NotebookSource source) {
    return Dismissible(
      key: Key(source.id),
      direction: DismissDirection.endToStart,
      background: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.red,
          borderRadius: BorderRadius.circular(12),
        ),
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.delete_outline, color: Colors.white),
            SizedBox(height: 4),
            Text('删除', style: TextStyle(color: Colors.white, fontSize: 12)),
          ],
        ),
      ),
      confirmDismiss: (direction) async {
        HapticFeedback.mediumImpact();
        return await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('删除来源'),
            content: Text('确定要删除 "${source.displayTitle}" 吗？'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('取消'),
              ),
              TextButton(
                onPressed: () {
                  HapticFeedback.heavyImpact();
                  Navigator.pop(dialogContext, true);
                },
                child: const Text('删除', style: TextStyle(color: Colors.red)),
              ),
            ],
          ),
        ) ?? false;
      },
      onDismissed: (direction) {
        context.read<NotebookBloc>().add(DeleteSourceEvent(
          notebookId: widget.notebookId,
          sourceId: source.id,
        ));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('已删除 "${source.displayTitle}"'),
            action: SnackBarAction(
              label: '撤销',
              onPressed: () {
                // Re-add the source (note: this is a simplified undo - in real app would need to store the full source data)
                context.read<NotebookBloc>().add(LoadNotebookDetailEvent(notebookId: widget.notebookId));
              },
            ),
          ),
        );
      },
      child: Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: InkWell(
        onTap: () => _showSourceDetail(context, source),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Center(
                  child: Text(source.type.icon, style: const TextStyle(fontSize: 22)),
                ),
              ),
              const SizedBox(width: 12),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildHighlightedText(
                      source.displayTitle,
                      style: AppTextStyles.bodyText2.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 2,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        _buildStatusChip(source.extractionStatus),
                        const SizedBox(width: 8),
                        Text(
                          _formatDate(source.createdAt),
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.textTertiary,
                          ),
                        ),
                      ],
                    ),
                    if (source.type == SourceType.url && source.originalUrl != null) ...[
                      const SizedBox(height: 4),
                      _buildHighlightedText(
                        source.originalUrl!,
                        style: AppTextStyles.caption.copyWith(
                          color: AppColors.textTertiary,
                        ),
                        maxLines: 1,
                      ),
                    ],
                    if (source.extractionError != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        '错误: ${source.extractionError}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.caption.copyWith(
                          color: Colors.red,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              // Actions
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert, size: 20),
                onSelected: (value) {
                  switch (value) {
                    case 'view':
                      _showSourceDetail(context, source);
                      break;
                    case 'open':
                      if (source.originalUrl != null) {
                        launchUrl(Uri.parse(source.originalUrl!));
                      }
                      break;
                    case 'delete':
                      _confirmDeleteSource(context, source);
                      break;
                  }
                },
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'view',
                    child: Row(
                      children: [
                        Icon(Icons.visibility_outlined, size: 18),
                        SizedBox(width: 8),
                        Text('查看内容'),
                      ],
                    ),
                  ),
                  if (source.type == SourceType.url && source.originalUrl != null)
                    const PopupMenuItem(
                      value: 'open',
                      child: Row(
                        children: [
                          Icon(Icons.open_in_new, size: 18),
                          SizedBox(width: 8),
                          Text('打开链接'),
                        ],
                      ),
                    ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        Icon(Icons.delete_outline, size: 18, color: Colors.red),
                        SizedBox(width: 8),
                        Text('删除', style: TextStyle(color: Colors.red)),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    if (diff.inDays == 0) {
      if (diff.inHours == 0) {
        return '${diff.inMinutes}分钟前';
      }
      return '${diff.inHours}小时前';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}天前';
    } else {
      return '${date.month}/${date.day}';
    }
  }

  void _showSourceDetail(BuildContext context, NotebookSource source) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.7,
          minChildSize: 0.3,
          maxChildSize: 0.95,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                // Handle
                Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                // Header
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      Text(source.type.icon, style: const TextStyle(fontSize: 24)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              source.displayTitle,
                              style: AppTextStyles.subtitle1.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Row(
                              children: [
                                _buildStatusChip(source.extractionStatus),
                                const SizedBox(width: 8),
                                Text(
                                  _formatDate(source.createdAt),
                                  style: AppTextStyles.caption,
                                ),
                              ],
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
                const Divider(),
                // Content
                Expanded(
                  child: ListView(
                    controller: scrollController,
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (source.type == SourceType.url && source.originalUrl != null) ...[
                        _buildDetailSection('原始链接', source.originalUrl!),
                        const SizedBox(height: 16),
                      ],
                      if (source.summary != null && source.summary!.isNotEmpty) ...[
                        _buildDetailSection('摘要', source.summary!),
                        const SizedBox(height: 16),
                      ],
                      if (source.hasExtractedText || (source.originalContent != null && source.originalContent!.isNotEmpty)) ...[
                        Text(
                          '内容',
                          style: AppTextStyles.subtitle2.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.background,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: SelectableText(
                            source.originalContent ?? '(已提取但未存储原始内容)',
                            style: AppTextStyles.bodyText2.copyWith(height: 1.6),
                          ),
                        ),
                      ] else if (source.extractionStatus == ExtractionStatus.pending ||
                          source.extractionStatus == ExtractionStatus.processing) ...[
                        Center(
                          child: Column(
                            children: [
                              const CircularProgressIndicator(),
                              const SizedBox(height: 12),
                              Text(
                                '正在提取内容...',
                                style: AppTextStyles.bodyText2.copyWith(
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ] else if (source.extractionStatus == ExtractionStatus.failed) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.red.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            children: [
                              const Icon(Icons.error_outline, color: Colors.red, size: 32),
                              const SizedBox(height: 8),
                              Text(
                                '内容提取失败',
                                style: AppTextStyles.subtitle1.copyWith(color: Colors.red),
                              ),
                              if (source.extractionError != null) ...[
                                const SizedBox(height: 4),
                                Text(
                                  source.extractionError!,
                                  style: AppTextStyles.caption.copyWith(color: Colors.red),
                                  textAlign: TextAlign.center,
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildDetailSection(String title, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: AppTextStyles.subtitle2.copyWith(
            color: AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: 8),
        SelectableText(
          content,
          style: AppTextStyles.bodyText2.copyWith(height: 1.5),
        ),
      ],
    );
  }

  Widget _buildStatusChip(ExtractionStatus status) {
    Color color;
    switch (status) {
      case ExtractionStatus.pending:
        color = Colors.orange;
        break;
      case ExtractionStatus.processing:
        color = Colors.blue;
        break;
      case ExtractionStatus.completed:
        color = Colors.green;
        break;
      case ExtractionStatus.failed:
        color = Colors.red;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        status.displayName,
        style: AppTextStyles.overline.copyWith(
          color: color,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildChatTab(BuildContext context, NotebookDetailLoaded state) {
    final hasHistory = state.notebook.chatHistory.isNotEmpty;
    final hasCurrentResponse = state.chatResponse != null && state.chatResponse!.isNotEmpty;
    final hasError = state.chatError != null;
    final isThinking = state.chatThinkingMessage != null;

    return Column(
      children: [
        // Clear history button if has content
        if (hasHistory || hasCurrentResponse)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: Colors.white,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton.icon(
                  onPressed: state.isChatting
                      ? null
                      : () => _clearChatHistory(context),
                  icon: const Icon(Icons.delete_sweep, size: 18),
                  label: const Text('清除对话'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.textTertiary,
                  ),
                ),
              ],
            ),
          ),
        // Chat area
        Expanded(
          child: (hasHistory || hasCurrentResponse || hasError || isThinking)
              ? _buildChatHistory(context, state)
              : _buildChatPlaceholder(),
        ),
        // Input area
        _buildChatInput(context, state),
      ],
    );
  }

  void _clearChatHistory(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        final bloc = context.read<NotebookBloc>();
        return AlertDialog(
          title: const Text('清除对话历史'),
          content: const Text('确定要清除所有对话历史吗？此操作不可撤销。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                bloc.add(ClearChatHistoryEvent(notebookId: widget.notebookId));
              },
              child: const Text('清除', style: TextStyle(color: Colors.red)),
            ),
          ],
        );
      },
    );
  }

  Widget _buildChatHistory(BuildContext context, NotebookDetailLoaded state) {
    // Auto-scroll to bottom when receiving new content
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_chatScrollController.hasClients && state.isChatting) {
        _chatScrollController.animateTo(
          _chatScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 100),
          curve: Curves.easeOut,
        );
      }
    });

    final chatHistory = state.notebook.chatHistory;

    return ListView.builder(
      controller: _chatScrollController,
      padding: const EdgeInsets.all(16),
      itemCount: chatHistory.length + (state.chatResponse != null || state.chatError != null || state.chatThinkingMessage != null ? 1 : 0),
      itemBuilder: (context, index) {
        // Show historical messages
        if (index < chatHistory.length) {
          final message = chatHistory[index];
          return _buildChatBubble(
            context,
            isUser: message.isUser,
            content: message.content,
            sources: message.sources,
          );
        }

        // Show current streaming response or error
        return _buildCurrentResponse(context, state);
      },
    );
  }

  Widget _buildChatBubble(
    BuildContext context, {
    required bool isUser,
    required String content,
    List<ChatSource> sources = const [],
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.primary.withValues(alpha: 0.1),
              child: const Icon(Icons.smart_toy, size: 18, color: AppColors.primary),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isUser ? AppColors.primary : Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 5,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isUser)
                    Text(
                      content,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: Colors.white,
                      ),
                    )
                  else
                    MarkdownBody(
                      data: content,
                      selectable: true,
                      styleSheet: MarkdownStyleSheet(
                        p: AppTextStyles.bodyText2.copyWith(height: 1.5),
                        h1: AppTextStyles.headline5,
                        h2: AppTextStyles.headline6,
                        h3: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.bold),
                        listBullet: AppTextStyles.bodyText2,
                        code: AppTextStyles.bodyText2.copyWith(
                          fontFamily: 'monospace',
                          backgroundColor: AppColors.background,
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: AppColors.background,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      onTapLink: (text, href, title) {
                        if (href != null) {
                          launchUrl(Uri.parse(href));
                        }
                      },
                    ),
                  if (sources.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    const Divider(height: 1),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: sources.map((source) {
                        return Chip(
                          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          padding: EdgeInsets.zero,
                          labelPadding: const EdgeInsets.symmetric(horizontal: 8),
                          avatar: const Icon(Icons.source_outlined, size: 14),
                          label: Text(
                            source.title,
                            style: AppTextStyles.overline,
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              radius: 16,
              backgroundColor: AppColors.primary,
              child: const Icon(Icons.person, size: 18, color: Colors.white),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCurrentResponse(BuildContext context, NotebookDetailLoaded state) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: AppColors.primary.withValues(alpha: 0.1),
            child: const Icon(Icons.smart_toy, size: 18, color: AppColors.primary),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16),
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(4),
                  bottomRight: Radius.circular(16),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 5,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (state.chatThinkingMessage != null) ...[
                    Row(
                      children: [
                        const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            state.chatThinkingMessage!,
                            style: AppTextStyles.caption.copyWith(
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (state.chatResponse != null && state.chatResponse!.isNotEmpty)
                      const SizedBox(height: 12),
                  ],
                  if (state.chatResponse != null && state.chatResponse!.isNotEmpty)
                    MarkdownBody(
                      data: state.chatResponse!,
                      selectable: true,
                      styleSheet: MarkdownStyleSheet(
                        p: AppTextStyles.bodyText2.copyWith(height: 1.5),
                        h1: AppTextStyles.headline5,
                        h2: AppTextStyles.headline6,
                        h3: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.bold),
                        listBullet: AppTextStyles.bodyText2,
                        code: AppTextStyles.bodyText2.copyWith(
                          fontFamily: 'monospace',
                          backgroundColor: AppColors.background,
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: AppColors.background,
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      onTapLink: (text, href, title) {
                        if (href != null) {
                          launchUrl(Uri.parse(href));
                        }
                      },
                    ),
                  if (state.chatError != null)
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: Colors.red, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              state.chatError!,
                              style: AppTextStyles.bodyText2.copyWith(
                                color: Colors.red,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  if (state.chatSources != null && state.chatSources!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    const Divider(height: 1),
                    const SizedBox(height: 8),
                    Text(
                      '参考来源',
                      style: AppTextStyles.overline.copyWith(color: AppColors.textTertiary),
                    ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: state.chatSources!.map((source) {
                        return GestureDetector(
                          onTap: () => _showCitationPreview(context, source, state.notebook),
                          child: Chip(
                            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                            padding: EdgeInsets.zero,
                            labelPadding: const EdgeInsets.symmetric(horizontal: 8),
                            avatar: const Icon(Icons.source_outlined, size: 14),
                            label: Text(
                              source.title,
                              style: AppTextStyles.overline,
                            ),
                            backgroundColor: AppColors.primary.withValues(alpha: 0.1),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                  if (!state.isChatting && state.chatResponse != null && state.chatResponse!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        InkWell(
                          onTap: () {
                            Clipboard.setData(ClipboardData(text: state.chatResponse!));
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('已复制到剪贴板')),
                            );
                          },
                          borderRadius: BorderRadius.circular(4),
                          child: Padding(
                            padding: const EdgeInsets.all(4),
                            child: Row(
                              children: [
                                Icon(Icons.copy, size: 14, color: AppColors.textTertiary),
                                const SizedBox(width: 4),
                                Text('复制', style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary)),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatPlaceholder() {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const SizedBox(height: 40),
            Icon(
              Icons.chat_bubble_outline,
              size: 64,
              color: AppColors.textTertiary.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 16),
            Text(
              '向知识库提问',
              style: AppTextStyles.subtitle1.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '基于知识库中的内容回答您的问题',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textTertiary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            // Quick start section
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.lightbulb_outline, size: 18, color: AppColors.primary),
                      const SizedBox(width: 8),
                      Text(
                        '试试这些问题',
                        style: AppTextStyles.subtitle2.copyWith(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _buildSuggestionChip('这个知识库讲了什么？', Icons.article_outlined),
                      _buildSuggestionChip('总结一下主要内容', Icons.summarize_outlined),
                      _buildSuggestionChip('有哪些重点？', Icons.star_outline),
                      _buildSuggestionChip('能给我解释一下吗？', Icons.help_outline),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestionChip(String text, [IconData? icon]) {
    return ActionChip(
      avatar: icon != null ? Icon(icon, size: 16) : null,
      label: Text(text),
      backgroundColor: Colors.white,
      side: BorderSide(color: AppColors.primary.withValues(alpha: 0.3)),
      onPressed: () {
        HapticFeedback.lightImpact();
        _chatController.text = text;
        _sendChatMessage();
      },
    );
  }

  Widget _buildChatInput(BuildContext context, NotebookDetailLoaded state) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _chatController,
              decoration: InputDecoration(
                hintText: '输入您的问题...',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                filled: true,
                fillColor: AppColors.background,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
              maxLines: null,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendChatMessage(),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: state.isChatting ? null : _sendChatMessage,
            icon: state.isChatting
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.send),
            color: AppColors.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryTab(BuildContext context, NotebookDetailLoaded state) {
    final hasContent = state.notebook.totalSources > 0;

    return Column(
      children: [
        // Summary format options
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.white,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '选择摘要格式',
                style: AppTextStyles.subtitle2.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: SummaryFormat.values.map((format) {
                  return ActionChip(
                    label: Text(format.displayName),
                    onPressed: (state.isSummarizing || !hasContent)
                        ? null
                        : () => _generateSummary(format),
                    tooltip: format.description,
                  );
                }).toList(),
              ),
              if (!hasContent)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    '请先添加内容后再生成摘要',
                    style: AppTextStyles.caption.copyWith(
                      color: Colors.orange,
                    ),
                  ),
                ),
            ],
          ),
        ),
        // Summary content
        Expanded(
          child: _buildSummaryContent(context, state),
        ),
      ],
    );
  }

  Widget _buildSummaryContent(BuildContext context, NotebookDetailLoaded state) {
    // Show thinking or response
    if (state.summaryThinkingMessage != null ||
        (state.summaryResponse != null && state.summaryResponse!.isNotEmpty) ||
        state.summaryError != null) {
      return _buildSummaryResponse(context, state);
    }

    // Empty state
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.summarize_outlined,
            size: 64,
            color: AppColors.textTertiary.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            '生成内容摘要',
            style: AppTextStyles.subtitle1.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '选择上方的格式来生成摘要',
            style: AppTextStyles.caption.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryResponse(BuildContext context, NotebookDetailLoaded state) {
    // Auto-scroll to bottom when receiving new content
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_summaryScrollController.hasClients && state.isSummarizing) {
        _summaryScrollController.animateTo(
          _summaryScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 100),
          curve: Curves.easeOut,
        );
      }
    });

    return SingleChildScrollView(
      controller: _summaryScrollController,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (state.summaryThinkingMessage != null) ...[
            Row(
              children: [
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    state.summaryThinkingMessage!,
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
          ],
          if (state.summaryResponse != null && state.summaryResponse!.isNotEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 5,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: MarkdownBody(
                data: state.summaryResponse!,
                selectable: true,
                styleSheet: MarkdownStyleSheet(
                  p: AppTextStyles.bodyText2.copyWith(height: 1.6),
                  h1: AppTextStyles.headline5,
                  h2: AppTextStyles.headline6,
                  h3: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.bold),
                  listBullet: AppTextStyles.bodyText2,
                  code: AppTextStyles.bodyText2.copyWith(
                    fontFamily: 'monospace',
                    backgroundColor: AppColors.background,
                  ),
                  codeblockDecoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  tableHead: AppTextStyles.bodyText2.copyWith(fontWeight: FontWeight.bold),
                  tableBody: AppTextStyles.bodyText2,
                ),
                onTapLink: (text, href, title) {
                  if (href != null) {
                    launchUrl(Uri.parse(href));
                  }
                },
              ),
            ),
          if (state.summaryError != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: Colors.red, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      state.summaryError!,
                      style: AppTextStyles.bodyText2.copyWith(
                        color: Colors.red,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          if (state.summarySources != null && state.summarySources!.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(
              '参考来源',
              style: AppTextStyles.caption.copyWith(
                color: AppColors.textSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: state.summarySources!.map((source) {
                return Chip(
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  avatar: const Icon(Icons.source_outlined, size: 14),
                  label: Text(
                    source.title,
                    style: AppTextStyles.caption,
                  ),
                );
              }).toList(),
            ),
          ],
          const SizedBox(height: 16),
          if (!state.isSummarizing && state.summaryResponse != null && state.summaryResponse!.isNotEmpty)
            Row(
              children: [
                OutlinedButton.icon(
                  onPressed: () {
                    Clipboard.setData(
                      ClipboardData(text: state.summaryResponse!),
                    );
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('已复制到剪贴板')),
                    );
                  },
                  icon: const Icon(Icons.copy, size: 16),
                  label: const Text('复制摘要'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () {
                    // Clear summary and allow regeneration
                    // Trigger a new summary with different format
                    _showRegenSummaryDialog(context);
                  },
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('重新生成'),
                ),
              ],
            ),
        ],
      ),
    );
  }

  void _showRegenSummaryDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('重新生成摘要'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('选择新的摘要格式:'),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: SummaryFormat.values.map((format) {
                  return ActionChip(
                    label: Text(format.displayName),
                    onPressed: () {
                      Navigator.pop(dialogContext);
                      _generateSummary(format);
                    },
                  );
                }).toList(),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
          ],
        );
      },
    );
  }

  void _sendChatMessage() {
    final question = _chatController.text.trim();
    if (question.isEmpty) return;

    context.read<NotebookBloc>().add(SendChatMessageEvent(
      notebookId: widget.notebookId,
      question: question,
    ));

    _chatController.clear();
  }

  void _generateSummary(SummaryFormat format) {
    context.read<NotebookBloc>().add(GenerateSummaryEvent(
      notebookId: widget.notebookId,
      format: format.name,
    ));
  }

  void _showAddUrlDialog(BuildContext context) {
    _urlController.clear();
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final bloc = context.read<NotebookBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('添加网页链接'),
          content: TextField(
            controller: _urlController,
            decoration: const InputDecoration(
              labelText: 'URL',
              hintText: 'https://...',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.link),
            ),
            keyboardType: TextInputType.url,
            autofocus: true,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () {
                final url = _urlController.text.trim();
                if (url.isEmpty || !url.startsWith('http')) {
                  scaffoldMessenger.showSnackBar(
                    const SnackBar(content: Text('请输入有效的URL')),
                  );
                  return;
                }
                Navigator.pop(dialogContext);
                bloc.add(AddSourceEvent(
                  notebookId: widget.notebookId,
                  type: 'url',
                  content: url,
                ));
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
              ),
              child: const Text('添加'),
            ),
          ],
        );
      },
    );
  }

  void _showCitationPreview(BuildContext context, ChatSource chatSource, Notebook notebook) {
    // Find the matching source in the notebook
    final matchingSource = notebook.sources.where(
      (s) => s.id == chatSource.id || s.displayTitle == chatSource.title,
    ).firstOrNull;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (bottomSheetContext) {
        return DraggableScrollableSheet(
          initialChildSize: 0.6,
          minChildSize: 0.3,
          maxChildSize: 0.9,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                // Handle
                Container(
                  margin: const EdgeInsets.only(top: 12),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                // Header
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.source_outlined, color: AppColors.primary),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              chatSource.title,
                              style: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.w600),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              '引用来源',
                              style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.pop(bottomSheetContext),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),
                // Content
                Expanded(
                  child: SingleChildScrollView(
                    controller: scrollController,
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Citation header
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.primary.withValues(alpha: 0.2)),
                          ),
                          child: Row(
                            children: [
                              Icon(Icons.format_quote, size: 16, color: AppColors.primary),
                              const SizedBox(width: 4),
                              Text(
                                '来源: ${chatSource.title}',
                                style: AppTextStyles.caption.copyWith(
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Full source content if available
                        if (matchingSource != null) ...[
                          Text(
                            '完整内容',
                            style: AppTextStyles.subtitle2.copyWith(fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 8),
                          if (matchingSource.type == SourceType.url && matchingSource.originalUrl != null) ...[
                            InkWell(
                              onTap: () => launchUrl(Uri.parse(matchingSource.originalUrl!)),
                              child: Row(
                                children: [
                                  Icon(Icons.link, size: 14, color: AppColors.primary),
                                  const SizedBox(width: 4),
                                  Expanded(
                                    child: Text(
                                      matchingSource.originalUrl!,
                                      style: AppTextStyles.caption.copyWith(
                                        color: AppColors.primary,
                                        decoration: TextDecoration.underline,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 8),
                          ],
                          SelectableText(
                            matchingSource.originalContent ?? matchingSource.summary ?? '暂无内容',
                            style: AppTextStyles.bodyText2,
                          ),
                        ] else ...[
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.grey[100],
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                Icon(Icons.info_outline, color: AppColors.textTertiary),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '该来源的完整内容不可用',
                                    style: AppTextStyles.bodyText2.copyWith(color: AppColors.textSecondary),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showAddNoteDialog(BuildContext context) {
    _noteController.clear();
    _noteTitleController.clear();
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final bloc = context.read<NotebookBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('添加笔记'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: _noteTitleController,
                  decoration: const InputDecoration(
                    labelText: '标题 (可选)',
                    hintText: '给笔记起个标题...',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.title),
                  ),
                  textCapitalization: TextCapitalization.sentences,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _noteController,
                  decoration: const InputDecoration(
                    labelText: '笔记内容',
                    hintText: '输入您的笔记...',
                    border: OutlineInputBorder(),
                    alignLabelWithHint: true,
                  ),
                  maxLines: 5,
                  autofocus: true,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            ElevatedButton(
              onPressed: () {
                final content = _noteController.text.trim();
                final title = _noteTitleController.text.trim();
                if (content.isEmpty) {
                  scaffoldMessenger.showSnackBar(
                    const SnackBar(content: Text('请输入笔记内容')),
                  );
                  return;
                }
                Navigator.pop(dialogContext);
                bloc.add(AddSourceEvent(
                  notebookId: widget.notebookId,
                  type: 'text',
                  content: content,
                  title: title.isNotEmpty ? title : null,
                ));
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
              ),
              child: const Text('添加'),
            ),
          ],
        );
      },
    );
  }

  void _confirmDeleteSource(BuildContext context, NotebookSource source) {
    final bloc = context.read<NotebookBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('删除来源'),
          content: Text('确定要删除 "${source.displayTitle}" 吗？'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                bloc.add(DeleteSourceEvent(
                  notebookId: widget.notebookId,
                  sourceId: source.id,
                ));
              },
              child: const Text('删除', style: TextStyle(color: Colors.red)),
            ),
          ],
        );
      },
    );
  }

  Color _parseColor(String colorHex) {
    try {
      return Color(int.parse(colorHex.replaceFirst('#', '0xFF')));
    } catch (_) {
      return AppColors.primary;
    }
  }

  /// Build text with highlighted search matches
  Widget _buildHighlightedText(String text, {TextStyle? style, int maxLines = 2}) {
    if (_searchQuery.isEmpty) {
      return Text(
        text,
        maxLines: maxLines,
        overflow: TextOverflow.ellipsis,
        style: style,
      );
    }

    final query = _searchQuery.toLowerCase();
    final textLower = text.toLowerCase();
    final spans = <TextSpan>[];
    int start = 0;

    while (true) {
      final index = textLower.indexOf(query, start);
      if (index == -1) {
        if (start < text.length) {
          spans.add(TextSpan(text: text.substring(start)));
        }
        break;
      }
      if (index > start) {
        spans.add(TextSpan(text: text.substring(start, index)));
      }
      spans.add(TextSpan(
        text: text.substring(index, index + query.length),
        style: TextStyle(
          backgroundColor: AppColors.primary.withValues(alpha: 0.3),
          fontWeight: FontWeight.bold,
        ),
      ));
      start = index + query.length;
    }

    return RichText(
      maxLines: maxLines,
      overflow: TextOverflow.ellipsis,
      text: TextSpan(
        style: style ?? AppTextStyles.bodyText2,
        children: spans,
      ),
    );
  }

  // ============ Export Functions ============

  void _showExportOptions(BuildContext context, NotebookDetailLoaded state) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (bottomSheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    '导出知识库',
                    style: AppTextStyles.headline6,
                  ),
                ),
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    '选择导出格式',
                    style: AppTextStyles.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                ListTile(
                  leading: Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.text_snippet, color: AppColors.primary),
                  ),
                  title: const Text('纯文本'),
                  subtitle: const Text('导出为可复制的文本格式'),
                  onTap: () {
                    Navigator.pop(bottomSheetContext);
                    _exportAsText(context, state);
                  },
                ),
                ListTile(
                  leading: Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: Colors.blue.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.code, color: Colors.blue),
                  ),
                  title: const Text('Markdown'),
                  subtitle: const Text('导出为 Markdown 格式'),
                  onTap: () {
                    Navigator.pop(bottomSheetContext);
                    _exportAsMarkdown(context, state);
                  },
                ),
                ListTile(
                  leading: Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: Colors.green.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.share, color: Colors.green),
                  ),
                  title: const Text('分享摘要'),
                  subtitle: const Text('仅分享知识库摘要'),
                  onTap: () {
                    Navigator.pop(bottomSheetContext);
                    _shareSummary(context, state);
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _exportAsText(BuildContext context, NotebookDetailLoaded state) {
    final notebook = state.notebook;
    final buffer = StringBuffer();

    buffer.writeln('${notebook.icon} ${notebook.name}');
    buffer.writeln('=' * 40);
    if (notebook.description != null && notebook.description!.isNotEmpty) {
      buffer.writeln(notebook.description);
    }
    buffer.writeln();
    buffer.writeln('来源数量: ${notebook.totalSources}');
    buffer.writeln('创建时间: ${_formatFullDate(notebook.createdAt)}');
    buffer.writeln();
    buffer.writeln('内容列表:');
    buffer.writeln('-' * 40);

    for (final source in notebook.sources) {
      buffer.writeln();
      buffer.writeln('【${source.type == SourceType.url ? '链接' : '笔记'}】${source.displayTitle}');
      if (source.type == SourceType.url && source.originalUrl != null) {
        buffer.writeln('URL: ${source.originalUrl}');
      }
      if (source.summary != null && source.summary!.isNotEmpty) {
        buffer.writeln('摘要: ${source.summary}');
      }
      if (source.originalContent != null && source.originalContent!.isNotEmpty) {
        buffer.writeln();
        buffer.writeln(source.originalContent);
      }
      buffer.writeln();
    }

    _copyAndShowResult(context, buffer.toString(), '知识库已复制为纯文本');
  }

  void _exportAsMarkdown(BuildContext context, NotebookDetailLoaded state) {
    final notebook = state.notebook;
    final buffer = StringBuffer();

    buffer.writeln('# ${notebook.icon} ${notebook.name}');
    buffer.writeln();
    if (notebook.description != null && notebook.description!.isNotEmpty) {
      buffer.writeln('> ${notebook.description}');
      buffer.writeln();
    }
    buffer.writeln('- **来源数量:** ${notebook.totalSources}');
    buffer.writeln('- **创建时间:** ${_formatFullDate(notebook.createdAt)}');
    buffer.writeln();
    buffer.writeln('---');
    buffer.writeln();
    buffer.writeln('## 内容列表');
    buffer.writeln();

    for (int i = 0; i < notebook.sources.length; i++) {
      final source = notebook.sources[i];
      buffer.writeln('### ${i + 1}. ${source.displayTitle}');
      buffer.writeln();
      buffer.writeln('**类型:** ${source.type == SourceType.url ? '链接' : '笔记'}');
      if (source.type == SourceType.url && source.originalUrl != null) {
        buffer.writeln('**URL:** [${source.originalUrl}](${source.originalUrl})');
      }
      buffer.writeln('**添加时间:** ${_formatFullDate(source.createdAt)}');
      buffer.writeln();

      if (source.summary != null && source.summary!.isNotEmpty) {
        buffer.writeln('**摘要:**');
        buffer.writeln('> ${source.summary}');
        buffer.writeln();
      }

      if (source.originalContent != null && source.originalContent!.isNotEmpty) {
        buffer.writeln('**内容:**');
        buffer.writeln();
        buffer.writeln(source.originalContent);
        buffer.writeln();
      }

      buffer.writeln('---');
      buffer.writeln();
    }

    _copyAndShowResult(context, buffer.toString(), '知识库已复制为 Markdown');
  }

  void _shareSummary(BuildContext context, NotebookDetailLoaded state) {
    final notebook = state.notebook;
    final buffer = StringBuffer();

    buffer.writeln('${notebook.icon} ${notebook.name}');
    buffer.writeln();
    if (notebook.description != null && notebook.description!.isNotEmpty) {
      buffer.writeln(notebook.description);
      buffer.writeln();
    }
    buffer.writeln('共收录 ${notebook.totalSources} 个来源:');
    buffer.writeln();

    final urlCount = notebook.urlCount;
    final textCount = notebook.textCount;
    if (urlCount > 0) buffer.writeln('- $urlCount 个网页链接');
    if (textCount > 0) buffer.writeln('- $textCount 条笔记');
    buffer.writeln();

    buffer.writeln('内容概览:');
    for (int i = 0; i < notebook.sources.length && i < 5; i++) {
      final source = notebook.sources[i];
      buffer.writeln('• ${source.displayTitle}');
    }
    if (notebook.sources.length > 5) {
      buffer.writeln('• ... 还有 ${notebook.sources.length - 5} 项');
    }

    _copyAndShowResult(context, buffer.toString(), '摘要已复制到剪贴板');
  }

  void _copyAndShowResult(BuildContext context, String content, String message) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: Colors.white, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: AppColors.success,
        behavior: SnackBarBehavior.floating,
        action: SnackBarAction(
          label: '查看',
          textColor: Colors.white,
          onPressed: () {
            _showExportPreview(context, content);
          },
        ),
      ),
    );
  }

  void _showExportPreview(BuildContext context, String content) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('导出预览'),
          content: SizedBox(
            width: double.maxFinite,
            height: 400,
            child: SingleChildScrollView(
              child: SelectableText(
                content,
                style: AppTextStyles.bodyText2.copyWith(
                  fontFamily: 'monospace',
                  fontSize: 12,
                ),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('关闭'),
            ),
            ElevatedButton.icon(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: content));
                Navigator.pop(dialogContext);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('已复制到剪贴板')),
                );
              },
              icon: const Icon(Icons.copy, size: 16),
              label: const Text('复制'),
            ),
          ],
        );
      },
    );
  }

  String _formatFullDate(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日 ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }
}
