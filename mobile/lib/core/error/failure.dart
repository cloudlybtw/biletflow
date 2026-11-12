sealed class Failure implements Exception {
  const Failure(this.message);
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

final class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'Cannot reach the BiletFlow server. Check Wi-Fi or mobile data.']);
}

final class TimeoutFailure extends Failure {
  const TimeoutFailure([super.message = 'The server took too long to respond.']);
}

final class UnauthorizedFailure extends Failure {
  const UnauthorizedFailure([super.message = 'Your session has expired. Please sign in again.']);
}

final class ForbiddenFailure extends Failure {
  const ForbiddenFailure([super.message = 'You are not authorized for this action.']);
}

final class ValidationFailure extends Failure {
  const ValidationFailure(super.message);
}

final class ServerFailure extends Failure {
  const ServerFailure(super.message, {this.statusCode});
  final int? statusCode;
}