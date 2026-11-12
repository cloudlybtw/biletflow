import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final isOnlineProvider = StreamProvider<bool>((ref) async* 
{
  final connectivity = Connectivity();
  yield _hasInterface(await connectivity.checkConnectivity());
  yield* connectivity.onConnectivityChanged.map(_hasInterface);
}

);

bool _hasInterface(List<ConnectivityResult> results) => results.any((r) => r != ConnectivityResult.none);
