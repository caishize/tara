import 'package:flutter/material.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../../app/router/routes.dart';
import '../../../../app/theme/app_colors.dart';
import '../../../../core/network/api_client.dart';
import '../../../../shared/widgets/avatar_with_initials.dart';
import '../../data/models/kanban_models.dart';
import '../../domain/entities/curated_event.dart';

/// Full-screen detail page for a kanban event.
///
/// Accepts an optional pre-loaded [event] model (passed via router `extra`).
/// When [event] is null, fetches event data from the backend using [eventId].
class EventDetailPage extends StatefulWidget {
  final KanbanEventModel? event;
  final String eventId;

  const EventDetailPage({
    super.key,
    required this.event,
    required this.eventId,
  });

  @override
  State<EventDetailPage> createState() => _EventDetailPageState();
}

class _EventDetailPageState extends State<EventDetailPage> {
  KanbanEventModel? _event;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _event = widget.event;
    if (_event == null && widget.eventId.isNotEmpty) {
      _fetchEvent();
    }
  }

  Future<void> _fetchEvent() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final apiClient = GetIt.I<ApiClient>();
      final response = await apiClient.get<Map<String, dynamic>>(
        '/kanban/events/${widget.eventId}/context',
        parser: (data) => data as Map<String, dynamic>,
      );
      final eventJson = response['event'] as Map<String, dynamic>?;
      if (eventJson != null && mounted) {
        setState(() {
          _event = KanbanEventModel.fromJson(eventJson);
          _loading = false;
        });
      } else if (mounted) {
        setState(() {
          _error = '事件不存在';
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '加载失败';
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: const BackButton(color: AppColors.textPrimary),
          title: const Text(
            '事件详情',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 17),
          ),
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_event == null) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: const BackButton(color: AppColors.textPrimary),
          title: const Text(
            '事件详情',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 17),
          ),
        ),
        body: Center(
          child: Text(
            _error ?? '事件不存在',
            style: const TextStyle(color: AppColors.textSecondary),
          ),
        ),
      );
    }

    final ev = _event!;
    final typeColor = Color(ev.eventType?.colorValue ?? 0xFF78909C);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: const BackButton(color: AppColors.textPrimary),
        title: const Text(
          '事件详情',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: AppColors.textPrimary),
            onSelected: (_) {},
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'edit', child: Text('编辑')),
              const PopupMenuItem(value: 'delete', child: Text('删除')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildHeroHeader(ev, typeColor),
                  if (ev.tags != null && ev.tags!.isNotEmpty)
                    _buildRelatedPeople(ev),
                  if (ev.preparationItems.isNotEmpty)
                    _buildPreparationChecklist(ev),
                  if (_userFacingNotes(ev.notes) != null)
                    _buildSecretaryTip(ev),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
          _buildBottomActions(context, ev),
        ],
      ),
    );
  }

  Widget _buildHeroHeader(KanbanEventModel ev, Color typeColor) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [typeColor, typeColor.withAlpha((0.75 * 255).round())],
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: typeColor.withAlpha((0.3 * 255).round()),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Event type icon + title
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                ev.eventType?.icon ?? '',
                style: const TextStyle(fontSize: 24),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  ev.title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Date range
          if (ev.startTime != null)
            Row(
              children: [
                const Icon(Icons.access_time, size: 16, color: Colors.white70),
                const SizedBox(width: 6),
                Text(
                  _formatDateRange(ev.startTime!, ev.endTime),
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          // Location
          if (ev.location != null && ev.location!.isNotEmpty) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                const Icon(Icons.place_outlined, size: 16, color: Colors.white70),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    ev.location!,
                    style: const TextStyle(fontSize: 14, color: Colors.white70),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
          // Status badge
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withAlpha((0.2 * 255).round()),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              _statusLabel(ev.status),
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRelatedPeople(KanbanEventModel ev) {
    final names = ev.tags!;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '相关人员',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 72,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: names.length,
              separatorBuilder: (_, __) => const SizedBox(width: 16),
              itemBuilder: (_, i) => SizedBox(
                width: 56,
                child: Column(
                  children: [
                    AvatarWithInitials(name: names[i], size: 48),
                    const SizedBox(height: 4),
                    Text(
                      names[i],
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPreparationChecklist(KanbanEventModel ev) {
    final doneCount = ev.prepDoneCount;
    final totalCount = ev.prepTotalCount;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '准备清单 \u00B7 $doneCount/$totalCount 已搞定',
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          ...ev.preparationItems.map((item) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    Icon(
                      item.done ? Icons.check_circle : Icons.radio_button_unchecked,
                      size: 22,
                      color: item.done ? AppColors.success : AppColors.textTertiary,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        item.item,
                        style: TextStyle(
                          fontSize: 14,
                          color: item.done
                              ? AppColors.textTertiary
                              : AppColors.textPrimary,
                          decoration: item.done
                              ? TextDecoration.lineThrough
                              : TextDecoration.none,
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildSecretaryTip(KanbanEventModel ev) {
    final cleaned = _userFacingNotes(ev.notes)!;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.primary.withAlpha((0.08 * 255).round()),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.primary.withAlpha((0.15 * 255).round()),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.auto_awesome,
            size: 20,
            color: AppColors.primary.withAlpha((0.7 * 255).round()),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              cleaned,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.textPrimary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Strip internal system annotations like [随行程取消: ...] / [取消原因: ...]
  /// from notes. Returns null if nothing user-facing remains.
  static String? _userFacingNotes(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    final cleaned = raw
        .replaceAll(RegExp(r'\[随行程取消:.*?\]'), '')
        .replaceAll(RegExp(r'\[取消原因:.*?\]'), '')
        .trim();
    return cleaned.isEmpty ? null : cleaned;
  }

  static bool _isTripType(CuratedEventType? type) {
    return type == CuratedEventType.businessTrip ||
        type == CuratedEventType.travel;
  }

  Widget _buildBottomActions(BuildContext context, KanbanEventModel ev) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha((0.05 * 255).round()),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => context.go(Routes.conversation),
              icon: const Icon(Icons.chat_bubble_outline, size: 18),
              label: const Text('在对话中继续'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.primary,
                side: const BorderSide(color: AppColors.primary),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          if (ev.tripId != null && _isTripType(ev.eventType)) ...[
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => context.push(Routes.tripDetail(ev.tripId!)),
              child: const Text(
                '查看行程详情',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  String _formatDateRange(DateTime start, DateTime? end) {
    final localStart = start.toLocal();
    final startStr = DateFormat('M月d日 HH:mm').format(localStart);

    if (end == null) return startStr;

    final localEnd = end.toLocal();
    final sameDay = localStart.year == localEnd.year &&
        localStart.month == localEnd.month &&
        localStart.day == localEnd.day;

    if (sameDay) {
      return '$startStr - ${DateFormat('HH:mm').format(localEnd)}';
    }
    return '$startStr - ${DateFormat('M月d日 HH:mm').format(localEnd)}';
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'confirmed':
        return '已确认';
      case 'tentative':
        return '待确认';
      case 'cancelled':
        return '已取消';
      case 'completed':
        return '已完成';
      case 'pending':
      default:
        return '待处理';
    }
  }
}
