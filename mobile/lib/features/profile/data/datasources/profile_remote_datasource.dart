import '../../../../core/network/api_client.dart';
import '../models/user_stats_model.dart';
import '../models/smart_service_model.dart';
import '../models/service_execution_model.dart';
import '../models/work_report_model.dart';
import '../../domain/entities/insight_settings.dart';
import '../../domain/entities/work_report.dart';

class ProfileRemoteDataSource {
  final ApiClient _client;

  ProfileRemoteDataSource(this._client);

  /// Get user statistics
  Future<UserStatsModel> getUserStats() async {
    final response = await _client.get<Map<String, dynamic>>('/members/stats');
    return UserStatsModel.fromJson(response);
  }

  /// Get all smart services with their status
  Future<SmartServicesSummaryModel> getSmartServices() async {
    final response =
        await _client.get<Map<String, dynamic>>('/members/smart-services');
    return SmartServicesSummaryModel.fromJson(response);
  }

  /// Pause a scheduler service
  Future<void> pauseService(String serviceId) async {
    await _client.post('/scheduler/$serviceId/pause');
  }

  /// Resume a scheduler service
  Future<void> resumeService(String serviceId) async {
    await _client.post('/scheduler/$serviceId/resume');
  }

  /// Manually trigger a job in a scheduler
  Future<Map<String, dynamic>> triggerServiceJob(
      String serviceId, String jobName) async {
    final response = await _client
        .post<Map<String, dynamic>>('/scheduler/$serviceId/trigger/$jobName');
    return response;
  }

  /// Submit user feedback
  Future<void> submitFeedback(String content, String? contactInfo) async {
    await _client.post('/members/feedback', data: {
      'content': content,
      if (contactInfo != null) 'contact_info': contactInfo,
    });
  }

  /// Get execution history for a scheduler
  Future<ExecutionHistoryModel> getExecutionHistory({
    String? schedulerName,
    String? jobName,
    String? status,
    int limit = 50,
    int offset = 0,
  }) async {
    final queryParams = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (schedulerName != null) queryParams['scheduler_name'] = schedulerName;
    if (jobName != null) queryParams['job_name'] = jobName;
    if (status != null) queryParams['status'] = status;

    final response = await _client.get<Map<String, dynamic>>(
      '/scheduler/executions',
      queryParameters: queryParams,
    );
    return ExecutionHistoryModel.fromJson(response);
  }

  /// Get detailed status of a specific scheduler
  Future<Map<String, dynamic>> getSchedulerDetail(String schedulerName) async {
    final response = await _client
        .get<Map<String, dynamic>>('/scheduler/status/$schedulerName');
    return response;
  }

  /// Get activity summary for the secretary report
  Future<Map<String, dynamic>> getActivitySummary() async {
    try {
      final response =
          await _client.get<Map<String, dynamic>>('/members/activity-summary');
      return response;
    } catch (e) {
      // Return empty summary if API not available
      return {
        'total_tasks_completed': 0,
        'reminders_sent': 0,
        'gifts_recommended': 0,
        'price_alerts': 0,
        'holidays_synced': 0,
        'period': 'week',
      };
    }
  }

  /// Fetch insight settings from server
  Future<InsightSettings> fetchInsightSettings() async {
    final response = await _client.get<Map<String, dynamic>>(
      '/briefing/settings',
    );
    return InsightSettings.fromJson(response);
  }

  /// Update insight settings on server
  Future<void> updateInsightSettings(InsightSettings settings) async {
    await _client.put(
      '/briefing/settings',
      data: settings.toJson(),
    );
  }

  /// Reset insight settings to defaults
  Future<void> resetInsightSettings() async {
    await _client.delete('/briefing/settings');
  }

  /// Trigger manual timeline curation
  Future<void> triggerManualCuration() async {
    await _client.post('/curation/trigger', data: <String, dynamic>{});
  }

  /// Get secretary work report (curation + hygiene summary)
  Future<WorkReport> getWorkReport({int days = 30}) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/curation/work-report',
      queryParameters: {'days': days.toString()},
    );
    return WorkReportModel.fromJson(response);
  }

  /// Get detailed curation job with curated events and associations
  Future<CurationJobDetail> getCurationJobDetail(String jobId) async {
    final response = await _client.get<Map<String, dynamic>>(
      '/curation/jobs/$jobId',
    );
    return CurationJobDetailModel.fromJson(response);
  }

  /// Relation types that belong to the "family" (immediate family) category.
  static const _familyRelationTypes = {
    'self', 'spouse', 'father', 'mother', 'parent',
    'son', 'daughter', 'child', 'brother', 'sister', 'sibling',
  };

  /// Relation types that belong to the "relative" (extended family) category.
  static const _relativeRelationTypes = {
    'grandfather_paternal', 'grandmother_paternal',
    'grandfather_maternal', 'grandmother_maternal', 'grandparent',
    'grandson', 'granddaughter', 'grandchild',
    'uncle_paternal', 'aunt_paternal', 'uncle_maternal', 'aunt_maternal',
    'uncle_aunt', 'nephew', 'niece', 'nephew_niece', 'cousin',
    'father_in_law', 'mother_in_law', 'parent_in_law',
    'son_in_law', 'daughter_in_law', 'child_in_law',
    'brother_in_law', 'sister_in_law', 'sibling_in_law',
    'spouse_grandfather_paternal', 'spouse_grandmother_paternal',
    'spouse_grandfather_maternal', 'spouse_grandmother_maternal',
    'spouse_uncle_paternal', 'spouse_aunt_paternal',
    'spouse_uncle_maternal', 'spouse_aunt_maternal',
  };

  /// Fetch member stats (counts by type).
  /// Groups specific relation types into broad categories:
  /// family, relative, friend, colleague, other.
  /// Returns a map with category counts + a '_total' key for total members.
  Future<Map<String, int>> fetchMemberStats() async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/members/stats',
      );
      final total = (response['total'] as num?)?.toInt() ?? 0;
      final byRelation = response['by_relation'] as Map<String, dynamic>? ?? {};

      int familyCount = 0;
      int relativeCount = 0;
      int friendCount = 0;
      int colleagueCount = 0;
      int otherCount = 0;

      for (final entry in byRelation.entries) {
        final count = (entry.value as num?)?.toInt() ?? 0;
        if (_familyRelationTypes.contains(entry.key)) {
          familyCount += count;
        } else if (_relativeRelationTypes.contains(entry.key)) {
          relativeCount += count;
        } else if (entry.key == 'friend') {
          friendCount += count;
        } else if (entry.key == 'colleague' || entry.key == 'classmate') {
          colleagueCount += count;
        } else {
          otherCount += count;
        }
      }

      return {
        '_total': total,
        'family': familyCount,
        'relative': relativeCount,
        'friend': friendCount,
        'colleague': colleagueCount,
        'other': otherCount,
      };
    } catch (e) {
      return {};
    }
  }

  /// Fetch connection summary (count + connected provider types).
  /// Returns a map with 'count' (int) and 'provider_types' (List<String>).
  Future<Map<String, dynamic>> fetchConnectionSummary() async {
    try {
      final response = await _client.get<List<dynamic>>(
        '/connections/',
      );
      final providerTypes = <String>{};
      for (final item in response) {
        final providerType =
            (item as Map<String, dynamic>)['provider_type'] as String?;
        if (providerType != null) {
          providerTypes.add(providerType);
        }
      }
      return {
        'count': response.length,
        'provider_types': providerTypes.toList(),
      };
    } catch (e) {
      return {'count': 0, 'provider_types': <String>[]};
    }
  }

  /// Fetch memory stats
  Future<int> fetchMemoryStats() async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/memory/stats',
      );
      return (response['total'] as num?)?.toInt() ?? 0;
    } catch (e) {
      return 0;
    }
  }

  /// Fetch report summary for a time range
  Future<Map<String, dynamic>> fetchReportSummary({String range = 'week'}) async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/report/summary',
        queryParameters: {'range': range},
      );
      return response;
    } catch (e) {
      return {};
    }
  }

  /// Fetch report timeline entries
  Future<List<Map<String, dynamic>>> fetchReportTimeline({
    String range = 'week',
    int limit = 50,
  }) async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/report/timeline',
        queryParameters: {'range': range, 'limit': limit.toString()},
      );
      final items = response['items'] as List<dynamic>? ?? [];
      return items.cast<Map<String, dynamic>>();
    } catch (e) {
      return [];
    }
  }

  /// Fetch latest insight
  Future<String?> fetchLatestInsight() async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/memory/insights',
        queryParameters: {'limit': '1', 'unread_only': 'true'},
      );
      final items = response['items'] as List<dynamic>? ?? [];
      if (items.isNotEmpty) {
        final first = items.first as Map<String, dynamic>;
        return first['content'] as String?;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  /// Fetch data stats for data management
  Future<Map<String, dynamic>> fetchDataStats() async {
    try {
      final response = await _client.get<Map<String, dynamic>>(
        '/data/stats',
      );
      return response;
    } catch (e) {
      return {};
    }
  }

  /// Clear data by category
  Future<void> clearDataByCategory(String category, String password) async {
    await _client.post('/data/clear', data: {
      'category': category,
      'password': password,
    });
  }

  /// Clear all data
  Future<void> clearAllData(String password) async {
    await _client.post('/data/clear-all', data: {
      'password': password,
    });
  }
}
