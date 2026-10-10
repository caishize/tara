import 'dart:convert';
import 'package:hive/hive.dart';

/// Local storage wrapper using Hive
class LocalStorage {
  final Box _box;

  LocalStorage(this._box);

  /// Save a value
  Future<void> save<T>(String key, T value) async {
    if (value is Map || value is List) {
      await _box.put(key, jsonEncode(value));
    } else {
      await _box.put(key, value);
    }
  }

  /// Get a value
  T? get<T>(String key) {
    final value = _box.get(key);
    if (value == null) return null;

    if (T == Map || T == List) {
      return jsonDecode(value as String) as T;
    }
    return value as T;
  }

  /// Get a value with default
  T getOrDefault<T>(String key, T defaultValue) {
    return get<T>(key) ?? defaultValue;
  }

  /// Remove a value
  Future<void> remove(String key) async {
    await _box.delete(key);
  }

  /// Check if key exists
  bool has(String key) {
    return _box.containsKey(key);
  }

  /// Clear all data
  Future<void> clear() async {
    await _box.clear();
  }

  /// Save JSON object
  Future<void> saveJson(String key, Map<String, dynamic> json) async {
    await _box.put(key, jsonEncode(json));
  }

  /// Get JSON object
  Map<String, dynamic>? getJson(String key) {
    final value = _box.get(key);
    if (value == null) return null;
    return jsonDecode(value as String) as Map<String, dynamic>;
  }

  /// Save list of JSON objects
  Future<void> saveJsonList(String key, List<Map<String, dynamic>> list) async {
    await _box.put(key, jsonEncode(list));
  }

  /// Get list of JSON objects
  List<Map<String, dynamic>>? getJsonList(String key) {
    final value = _box.get(key);
    if (value == null) return null;
    final decoded = jsonDecode(value as String) as List;
    return decoded.map((e) => e as Map<String, dynamic>).toList();
  }
}
