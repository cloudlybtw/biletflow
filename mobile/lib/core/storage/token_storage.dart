import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

final tokenStorageProvider = Provider<TokenStorage>(
  (ref) => TokenStorage(
    const FlutterSecureStorage(aOptions: AndroidOptions(encryptedSharedPreferences: true)),
  ),
);




class TokenStorage {

  TokenStorage(this._storage);
  final FlutterSecureStorage _storage;
  static const _accessKey = 'biletflow.access_token';
  static const _refreshKey = 'biletflow.refresh_token';
  String? _cachedAccess;

  
  Future<String?> accessToken() async => _cachedAccess ??= await _storage.read(key: _accessKey);

  Future<String?> refreshToken() => _storage.read(key: _refreshKey);

  Future<void> save({required String accessToken, String? refreshToken}) async
  {
    _cachedAccess = accessToken;
    await _storage.write(key: _accessKey, value: accessToken);
    if (refreshToken != null) await _storage.write(key: _refreshKey, value: refreshToken);
  }

  Future<void> clear() async 
  {
    _cachedAccess = null;
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}