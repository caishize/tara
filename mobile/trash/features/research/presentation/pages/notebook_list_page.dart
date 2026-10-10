import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';

import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_text_styles.dart';
import '../../domain/entities/notebook.dart';
import '../bloc/notebook_bloc.dart';

class NotebookListPage extends StatefulWidget {
  const NotebookListPage({super.key});

  @override
  State<NotebookListPage> createState() => _NotebookListPageState();
}

enum NotebookSortOption {
  nameAsc('名称 A-Z'),
  nameDesc('名称 Z-A'),
  dateNewest('最新创建'),
  dateOldest('最早创建'),
  sourcesCount('来源数量');

  final String label;
  const NotebookSortOption(this.label);
}

class _NotebookListPageState extends State<NotebookListPage> {
  NotebookSortOption _sortOption = NotebookSortOption.dateNewest;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotebookBloc>().add(const LoadNotebooksEvent());
    });
  }

  List<Notebook> _sortNotebooks(List<Notebook> notebooks) {
    final sorted = List<Notebook>.from(notebooks);
    switch (_sortOption) {
      case NotebookSortOption.nameAsc:
        sorted.sort((a, b) => a.name.compareTo(b.name));
        break;
      case NotebookSortOption.nameDesc:
        sorted.sort((a, b) => b.name.compareTo(a.name));
        break;
      case NotebookSortOption.dateNewest:
        sorted.sort((a, b) => b.createdAt.compareTo(a.createdAt));
        break;
      case NotebookSortOption.dateOldest:
        sorted.sort((a, b) => a.createdAt.compareTo(b.createdAt));
        break;
      case NotebookSortOption.sourcesCount:
        sorted.sort((a, b) => b.totalSources.compareTo(a.totalSources));
        break;
    }
    return sorted;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: AppColors.textPrimary),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Text(
          '知识库',
          style: AppTextStyles.headline6.copyWith(
            color: AppColors.textPrimary,
          ),
        ),
        actions: [
          PopupMenuButton<NotebookSortOption>(
            icon: const Icon(Icons.sort, color: AppColors.textSecondary),
            tooltip: '排序方式',
            onSelected: (option) {
              setState(() => _sortOption = option);
            },
            itemBuilder: (context) => NotebookSortOption.values.map((option) {
              final isSelected = option == _sortOption;
              return PopupMenuItem(
                value: option,
                child: Row(
                  children: [
                    if (isSelected)
                      const Icon(Icons.check, size: 18, color: AppColors.primary)
                    else
                      const SizedBox(width: 18),
                    const SizedBox(width: 8),
                    Text(
                      option.label,
                      style: TextStyle(
                        color: isSelected ? AppColors.primary : null,
                        fontWeight: isSelected ? FontWeight.w600 : null,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
          IconButton(
            icon: const Icon(Icons.add, color: AppColors.primary),
            onPressed: () => _showCreateNotebookDialog(context),
          ),
        ],
      ),
      body: BlocConsumer<NotebookBloc, NotebookState>(
        listener: (context, state) {
          if (state is NotebookError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message),
                backgroundColor: Colors.red,
              ),
            );
          } else if (state is NotebookCreated) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('知识库 "${state.notebook.name}" 创建成功'),
                backgroundColor: AppColors.success,
              ),
            );
          }
        },
        builder: (context, state) {
          if (state is NotebookLoading) {
            return _buildLoadingSkeleton();
          }

          if (state is NotebooksLoaded) {
            if (state.notebooks.isEmpty) {
              return _buildEmptyState(context);
            }
            return _buildNotebookGrid(context, _sortNotebooks(state.notebooks));
          }

          return _buildEmptyState(context);
        },
      ),
    );
  }

  Widget _buildLoadingSkeleton() {
    return Shimmer.fromColors(
      baseColor: Colors.grey[300]!,
      highlightColor: Colors.grey[100]!,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          childAspectRatio: 0.85,
        ),
        itemCount: 6,
        itemBuilder: (context, index) {
          return Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
          );
        },
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(50),
            ),
            child: const Icon(
              Icons.menu_book_outlined,
              size: 48,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            '暂无知识库',
            style: AppTextStyles.headline6.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '创建知识库来整理你的资料和笔记',
            style: AppTextStyles.bodyText2.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => _showCreateNotebookDialog(context),
            icon: const Icon(Icons.add),
            label: const Text('创建知识库'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotebookGrid(BuildContext context, List<Notebook> notebooks) {
    return RefreshIndicator(
      onRefresh: () async {
        context.read<NotebookBloc>().add(const RefreshNotebooksEvent());
      },
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 16,
          crossAxisSpacing: 16,
          childAspectRatio: 0.85,
        ),
        itemCount: notebooks.length,
        itemBuilder: (context, index) {
          // Calculate delay based on position for staggered animation
          final row = index ~/ 2;
          final col = index % 2;
          final delay = (row * 100 + col * 50).clamp(0, 400);

          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: Duration(milliseconds: 400 + delay),
            curve: Curves.easeOutCubic,
            builder: (context, value, child) {
              return Transform.scale(
                scale: 0.8 + (0.2 * value),
                child: Opacity(
                  opacity: value,
                  child: child,
                ),
              );
            },
            child: _buildNotebookCard(context, notebooks[index]),
          );
        },
      ),
    );
  }

  Widget _buildNotebookCard(BuildContext context, Notebook notebook) {
    final color = _parseColor(notebook.color);

    return GestureDetector(
      onTap: () async {
        await context.push(Routes.notebookDetail(notebook.id));
        if (context.mounted) {
          context.read<NotebookBloc>().add(const LoadNotebooksEvent());
        }
      },
      onLongPress: () => _showNotebookOptions(context, notebook),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppColors.cardShadow,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with icon and quick action
            Stack(
              children: [
                Container(
                  height: 80,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(16),
                    ),
                  ),
                  child: Center(
                    child: Text(
                      notebook.icon,
                      style: const TextStyle(fontSize: 36),
                    ),
                  ),
                ),
                // Quick action menu
                Positioned(
                  top: 4,
                  right: 4,
                  child: PopupMenuButton<String>(
                    icon: Icon(
                      Icons.more_horiz,
                      size: 20,
                      color: color.withValues(alpha: 0.8),
                    ),
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                    onSelected: (value) => _handleQuickAction(context, notebook, value),
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                        value: 'open',
                        child: Row(
                          children: [
                            Icon(Icons.open_in_new, size: 18),
                            SizedBox(width: 8),
                            Text('打开'),
                          ],
                        ),
                      ),
                      const PopupMenuItem(
                        value: 'chat',
                        child: Row(
                          children: [
                            Icon(Icons.chat_outlined, size: 18),
                            SizedBox(width: 8),
                            Text('开始问答'),
                          ],
                        ),
                      ),
                      const PopupMenuDivider(),
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
                ),
              ],
            ),
            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notebook.name,
                      style: AppTextStyles.subtitle1.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const Spacer(),
                    Row(
                      children: [
                        Icon(
                          Icons.article_outlined,
                          size: 14,
                          color: AppColors.textTertiary,
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: Text(
                            '${notebook.totalSources} 个来源',
                            style: AppTextStyles.caption.copyWith(
                              color: AppColors.textTertiary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _formatRelativeDate(notebook.updatedAt),
                      style: AppTextStyles.overline.copyWith(
                        color: AppColors.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _handleQuickAction(BuildContext context, Notebook notebook, String action) async {
    switch (action) {
      case 'open':
        await context.push(Routes.notebookDetail(notebook.id));
        if (context.mounted) {
          context.read<NotebookBloc>().add(const LoadNotebooksEvent());
        }
        break;
      case 'chat':
        // Navigate to notebook detail and switch to chat tab
        await context.push('${Routes.notebookDetail(notebook.id)}?tab=chat');
        if (context.mounted) {
          context.read<NotebookBloc>().add(const LoadNotebooksEvent());
        }
        break;
      case 'delete':
        _confirmDelete(context, notebook);
        break;
    }
  }

  String _formatRelativeDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) {
      return '刚刚';
    } else if (diff.inHours < 1) {
      return '${diff.inMinutes}分钟前';
    } else if (diff.inDays < 1) {
      return '${diff.inHours}小时前';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}天前';
    } else if (diff.inDays < 30) {
      return '${(diff.inDays / 7).floor()}周前';
    } else {
      return '${date.month}月${date.day}日';
    }
  }

  void _showCreateNotebookDialog(BuildContext context) {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    String selectedIcon = '📚';
    String selectedColor = '#6366F1';

    final icons = ['📚', '📖', '📝', '💡', '🎯', '🔬', '💼', '🎨', '🏠', '❤️'];
    final colors = ['#6366F1', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#8B5CF6'];

    // Capture the bloc before showing dialog to avoid context issues
    final notebookBloc = context.read<NotebookBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (builderContext, setDialogState) {
            return AlertDialog(
              title: const Text('创建知识库'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: '名称',
                        hintText: '例如：旅行攻略',
                        border: OutlineInputBorder(),
                      ),
                      autofocus: true,
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: descController,
                      decoration: const InputDecoration(
                        labelText: '描述（可选）',
                        hintText: '简短描述这个知识库的内容',
                        border: OutlineInputBorder(),
                      ),
                      maxLines: 2,
                    ),
                    const SizedBox(height: 16),
                    const Text('选择图标'),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: icons.map((icon) {
                        final isSelected = icon == selectedIcon;
                        return GestureDetector(
                          onTap: () => setDialogState(() => selectedIcon = icon),
                          child: Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? AppColors.primary.withValues(alpha: 0.1)
                                  : Colors.grey.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                              border: isSelected
                                  ? Border.all(color: AppColors.primary, width: 2)
                                  : null,
                            ),
                            child: Center(
                              child: Text(icon, style: const TextStyle(fontSize: 24)),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 16),
                    const Text('选择颜色'),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      children: colors.map((colorHex) {
                        final color = _parseColor(colorHex);
                        final isSelected = colorHex == selectedColor;
                        return GestureDetector(
                          onTap: () => setDialogState(() => selectedColor = colorHex),
                          child: Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: color,
                              shape: BoxShape.circle,
                              border: isSelected
                                  ? Border.all(color: Colors.black, width: 3)
                                  : null,
                            ),
                            child: isSelected
                                ? const Icon(Icons.check, color: Colors.white, size: 20)
                                : null,
                          ),
                        );
                      }).toList(),
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
                    final name = nameController.text.trim();
                    if (name.isEmpty) {
                      ScaffoldMessenger.of(dialogContext).showSnackBar(
                        const SnackBar(content: Text('请输入知识库名称')),
                      );
                      return;
                    }
                    Navigator.pop(dialogContext);
                    notebookBloc.add(CreateNotebookEvent(
                      name: name,
                      description: descController.text.trim().isEmpty
                          ? null
                          : descController.text.trim(),
                      icon: selectedIcon,
                      color: selectedColor,
                    ));
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('创建'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showNotebookOptions(BuildContext context, Notebook notebook) {
    final color = _parseColor(notebook.color);
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (bottomSheetContext) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Header
              Container(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Center(
                        child: Text(notebook.icon, style: const TextStyle(fontSize: 24)),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            notebook.name,
                            style: AppTextStyles.subtitle1.copyWith(fontWeight: FontWeight.w600),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            '${notebook.totalSources} 个来源 · ${_formatRelativeDate(notebook.updatedAt)}',
                            style: AppTextStyles.caption.copyWith(color: AppColors.textSecondary),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.open_in_new),
                title: const Text('打开知识库'),
                onTap: () async {
                  Navigator.pop(bottomSheetContext);
                  await context.push(Routes.notebookDetail(notebook.id));
                  if (context.mounted) {
                    context.read<NotebookBloc>().add(const LoadNotebooksEvent());
                  }
                },
              ),
              ListTile(
                leading: const Icon(Icons.chat_outlined),
                title: const Text('开始问答'),
                subtitle: Text(
                  '基于知识库内容进行问答',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                ),
                onTap: () async {
                  Navigator.pop(bottomSheetContext);
                  await context.push('${Routes.notebookDetail(notebook.id)}?tab=chat');
                  if (context.mounted) {
                    context.read<NotebookBloc>().add(const LoadNotebooksEvent());
                  }
                },
              ),
              ListTile(
                leading: const Icon(Icons.summarize_outlined),
                title: const Text('生成摘要'),
                subtitle: Text(
                  '生成知识库内容摘要',
                  style: AppTextStyles.caption.copyWith(color: AppColors.textTertiary),
                ),
                onTap: () async {
                  Navigator.pop(bottomSheetContext);
                  await context.push('${Routes.notebookDetail(notebook.id)}?tab=summary');
                  if (context.mounted) {
                    context.read<NotebookBloc>().add(const LoadNotebooksEvent());
                  }
                },
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.delete_outline, color: Colors.red),
                title: const Text('删除知识库', style: TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.pop(bottomSheetContext);
                  _confirmDelete(context, notebook);
                },
              ),
              const SizedBox(height: 8),
            ],
          ),
        );
      },
    );
  }

  void _confirmDelete(BuildContext context, Notebook notebook) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('删除知识库'),
          content: Text('确定要删除 "${notebook.name}" 吗？此操作无法撤销。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                context.read<NotebookBloc>().add(
                  DeleteNotebookEvent(notebookId: notebook.id),
                );
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
}
