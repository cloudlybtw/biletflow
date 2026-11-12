import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/config/env.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/features/check_in/di.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';

sealed class ScanState {
  const ScanState();
}


final class ScanReady extends ScanState {
  const ScanReady();
}

final class ScanValidating extends ScanState {
  const ScanValidating({this.isSlow = false});
  final bool isSlow;
}

enum UndoStatus { idle, inProgress, done }


final class ScanDecided extends ScanState {
  const ScanDecided(
    this.outcome, {
    this.undo = UndoStatus.idle,
    this.undoError,
    this.followsUnconfirmedAttempt = false,
  });

  final ScanOutcome outcome;
  final UndoStatus undo;
  final String? undoError;


  final bool followsUnconfirmedAttempt;

  ScanDecided withUndo(UndoStatus undo, {String? error}) => ScanDecided(
        outcome,
        undo: undo,
        undoError: error,
        followsUnconfirmedAttempt: followsUnconfirmedAttempt,
      );
}


final class ScanNotVerified extends ScanState {
  const ScanNotVerified(this.failure, this.rawPayload);
  final Failure failure;
  final String rawPayload;
}

final scanControllerProvider =
    NotifierProvider.autoDispose<ScanController, ScanState>(ScanController.new);

class ScanController extends Notifier<ScanState> {

  static const _sameCodeCooldown = Duration(milliseconds: 1500);

  String? _lastPayload;
  DateTime _readySince = DateTime.fromMillisecondsSinceEpoch(0);

  @override
  ScanState build() => const ScanReady();

  
  Future<void> onDetected({required String eventId, required String rawPayload}) async {
    if (state is! ScanReady) return;
    final stillInFrame = rawPayload == _lastPayload &&
        DateTime.now().difference(_readySince) < _sameCodeCooldown;
    if (stillInFrame) return;
    await _validate(eventId, rawPayload);
  }

  Future<void> retry(String eventId) async {
    if (state case ScanNotVerified(:final rawPayload)) {
      await _validate(eventId, rawPayload, isRetry: true);
    }
  }

  void scanNext() {
    _readySince = DateTime.now();
    state = const ScanReady();
  }

  Future<void> undoCheckIn({required String eventId, required String reason}) async {
    final current = state;
    if (current is! ScanDecided || !current.outcome.canUndo || current.undo != UndoStatus.idle) {
      return;
    }
    state = current.withUndo(UndoStatus.inProgress);
    try {
      await ref.read(reverseCheckInProvider).call(
            eventId: eventId,
            checkInId: current.outcome.checkInId!,
            reason: reason,
          );
      if (ref.mounted) state = current.withUndo(UndoStatus.done);
    } on Failure catch (f) {
      if (!ref.mounted) return;
      final message = f is ForbiddenFailure
          ? 'You are not authorized to undo check-ins for this event.'
          : f.message;
      state = current.withUndo(UndoStatus.idle, error: message);
    }
  }

  Future<void> _validate(String eventId, String rawPayload, {bool isRetry = false}) async {
    _lastPayload = rawPayload;
    state = const ScanValidating();

    
    final slowTimer = Timer(Env.scanSlowThreshold, () {
      if (ref.mounted && state is ScanValidating) state = const ScanValidating(isSlow: true);
    });

    try {
      final outcome = await ref
          .read(validateTicketScanProvider)
          .call(eventId: eventId, rawPayload: rawPayload);
      if (ref.mounted) state = ScanDecided(outcome, followsUnconfirmedAttempt: isRetry);
    } on Failure catch (failure) {
      if (ref.mounted) state = ScanNotVerified(failure, rawPayload);
    } finally {
      slowTimer.cancel();
    }
  }
}