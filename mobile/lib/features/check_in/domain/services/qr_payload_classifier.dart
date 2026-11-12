enum QrPayloadKind { ticketCandidate, campaignLink, unreadable }

abstract final class QrPayloadClassifier {

  static const maxPayloadLength = 2048;

  static QrPayloadKind classify(String raw) {

    final value = raw.trim();
    if (value.isEmpty || value.length > maxPayloadLength) return QrPayloadKind.unreadable;

    final uri = Uri.tryParse(value);
    final isWebLink = uri != null && (uri.isScheme('http') || uri.isScheme('https'));
    return isWebLink ? QrPayloadKind.campaignLink : QrPayloadKind.ticketCandidate;
    
  }
}