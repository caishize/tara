import 'package:flutter_test/flutter_test.dart';
import 'package:family_secretary/features/kanban/data/models/future_view_models.dart';

void main() {
  group('FutureViewSuggestionModel.groupKey', () {
    test('parsed from JSON', () {
      final json = {
        'id': 's1',
        'title': 'Test',
        'group_key': 'person:grace:relationship_maintenance',
        'group_label': 'Grace生日快到了',
      };
      final model = FutureViewSuggestionModel.fromJson(json);
      expect(model.groupKey, equals('person:grace:relationship_maintenance'));
      expect(model.groupLabel, equals('Grace生日快到了'));
    });

    test('defaults to empty when absent', () {
      final json = {
        'id': 's2',
        'title': 'Test',
      };
      final model = FutureViewSuggestionModel.fromJson(json);
      expect(model.groupKey, isEmpty);
      expect(model.groupLabel, isEmpty);
    });
  });

  group('groupSuggestionsByKey', () {
    FutureViewSuggestionModel _makeSuggestion({
      required String id,
      required String title,
      String groupKey = '',
      String groupLabel = '',
    }) {
      return FutureViewSuggestionModel.fromJson({
        'id': id,
        'title': title,
        'group_key': groupKey,
        'group_label': groupLabel,
      });
    }

    test('groups suggestions with same groupKey', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'A', groupKey: 'person:grace:rm', groupLabel: 'A'),
        _makeSuggestion(id: '2', title: 'B', groupKey: 'person:grace:rm', groupLabel: 'A'),
        _makeSuggestion(id: '3', title: 'C', groupKey: 'id:3', groupLabel: 'C'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      expect(groups.length, equals(2));
      expect(groups[0].suggestions.length, equals(2));
      expect(groups[1].suggestions.length, equals(1));
    });

    test('single-item groups remain flat', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'A', groupKey: 'id:1', groupLabel: 'A'),
        _makeSuggestion(id: '2', title: 'B', groupKey: 'id:2', groupLabel: 'B'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      expect(groups.length, equals(2));
      expect(groups[0].isSingleItem, isTrue);
      expect(groups[1].isSingleItem, isTrue);
    });

    test('preserves first-occurrence order', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'First', groupKey: 'g:a', groupLabel: 'First'),
        _makeSuggestion(id: '2', title: 'Second', groupKey: 'g:b', groupLabel: 'Second'),
        _makeSuggestion(id: '3', title: 'Third', groupKey: 'g:a', groupLabel: 'First'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      expect(groups.length, equals(2));
      expect(groups[0].groupKey, equals('g:a'));
      expect(groups[0].suggestions.length, equals(2));
      expect(groups[1].groupKey, equals('g:b'));
    });

    test('empty groupKey treated as unique per suggestion', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'A', groupKey: '', groupLabel: 'A'),
        _makeSuggestion(id: '2', title: 'B', groupKey: '', groupLabel: 'B'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      // Each empty-key suggestion should be its own group
      expect(groups.length, equals(2));
    });

    test('empty list returns empty', () {
      final groups = groupSuggestionsByKey([]);
      expect(groups, isEmpty);
    });

    test('group exposes groupLabel from first item', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'Grace生日', groupKey: 'p:grace', groupLabel: 'Grace生日'),
        _makeSuggestion(id: '2', title: 'Grace礼物', groupKey: 'p:grace', groupLabel: 'Grace生日'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      expect(groups[0].groupLabel, equals('Grace生日'));
    });

    test('allInsightIds returns all insight IDs in the group', () {
      final suggestions = [
        _makeSuggestion(id: '1', title: 'A', groupKey: 'g:x', groupLabel: 'A'),
        _makeSuggestion(id: '2', title: 'B', groupKey: 'g:x', groupLabel: 'A'),
      ];
      final groups = groupSuggestionsByKey(suggestions);
      expect(groups[0].allInsightIds, containsAll(['1', '2']));
    });
  });
}
