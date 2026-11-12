import 'package:flutter/material.dart';

import 'package:biletflow_verify/core/utils/date_format.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';


class VerdictStyle {
  const VerdictStyle(this.color, this.icon, this.title, this.instruction);

  final Color color;
  final IconData icon;
  final String title;
  final String instruction;

  static const _green = Color(0xFF1B7F3B);
  static const _amber = Color(0xFFB45F06);
  static const _red = Color(0xFFC62828);

  static VerdictStyle of(ScanVerdict verdict) => switch (verdict) {
        ScanVerdict.valid =>
          const VerdictStyle(_green, Icons.check_circle, 'VALID', 'Admit attendee.'),
        ScanVerdict.alreadyUsed => const VerdictStyle(
            _amber, Icons.history, 'ALREADY USED', 'This ticket was already checked in. Do not admit.'),
        ScanVerdict.wrongEvent => const VerdictStyle(
            _amber, Icons.event_busy, 'WRONG EVENT', 'This ticket is for a different event. Do not admit.'),
        ScanVerdict.cancelled => const VerdictStyle(
            _red, Icons.cancel, 'CANCELLED', 'This ticket was cancelled. Do not admit.'),
        ScanVerdict.refunded => const VerdictStyle(
            _red, Icons.money_off, 'REFUNDED', 'This ticket was refunded. Do not admit.'),
        ScanVerdict.invalid => const VerdictStyle(
            _red, Icons.gpp_bad, 'INVALID', 'Ticket could not be authenticated. Do not admit.'),
        ScanVerdict.campaignQr => const VerdictStyle(
            _red, Icons.campaign, 'NOT A TICKET', 'Campaign / promotional QR codes never grant entry.'),
      };
}

class ScanVerdictCard extends StatelessWidget {
  const ScanVerdictCard({super.key, required this.outcome, this.footnote});

  final ScanOutcome outcome;
  final String? footnote;

  @override
  Widget build(BuildContext context) {
    final style = VerdictStyle.of(outcome.verdict);
    final text = Theme.of(context).textTheme;
    final details = <String>[
      if (outcome.attendeeName != null) outcome.attendeeName!,
      if (outcome.ticketTypeName != null) outcome.ticketTypeName!,
      if (outcome.verdict == ScanVerdict.alreadyUsed && outcome.checkedInAt != null)
        'Checked in at ${formatClockTime(outcome.checkedInAt!)}',
      if (!outcome.admitted && outcome.serverMessage != null) outcome.serverMessage!,
      ?footnote,
    ];

    return Semantics(
      liveRegion: true, 
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(color: style.color, borderRadius: BorderRadius.circular(20)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(style.icon, color: Colors.white, size: 40),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    style.title,
                    style: text.headlineMedium
                        ?.copyWith(color: Colors.white, fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(style.instruction, style: text.titleMedium?.copyWith(color: Colors.white)),
            for (final line in details) ...[
              const SizedBox(height: 4),
              Text(line, style: text.bodyLarge?.copyWith(color: Colors.white)),
            ],
          ],
        ),
      ),
    );
  }
}