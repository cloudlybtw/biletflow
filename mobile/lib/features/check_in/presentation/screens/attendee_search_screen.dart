import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/utils/date_format.dart';
import 'package:biletflow_verify/core/widgets/error_view.dart';
import 'package:biletflow_verify/core/widgets/offline_banner.dart';
import 'package:biletflow_verify/features/check_in/di.dart';
import 'package:biletflow_verify/features/check_in/domain/entities/check_in_entities.dart';
import 'package:biletflow_verify/features/check_in/domain/usecases/check_in_usecases.dart';
import 'package:biletflow_verify/features/check_in/presentation/providers/attendee_search_providers.dart';
import 'package:biletflow_verify/features/check_in/presentation/widgets/scan_verdict_card.dart';
import 'package:biletflow_verify/features/events/presentation/providers/events_providers.dart';

class AttendeeSearchScreen extends ConsumerStatefulWidget {
  const AttendeeSearchScreen({super.key, required this.eventId});
  final String eventId;

  @override
  ConsumerState<AttendeeSearchScreen> createState() => _AttendeeSearchScreenState();
}

class _AttendeeSearchScreenState extends ConsumerState<AttendeeSearchScreen> {
  final _input = TextEditingController();
  Timer? _debounce;
  String _query = '';
  String? _busyTicketId;

  AttendeeQuery get _key => (eventId: widget.eventId, query: _query);

  @override
  void dispose() {
    _debounce?.cancel();
    _input.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _query = value.trim());
    });
  }

  Future<bool> _confirm(AttendeeMatch match) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('Check in ${match.fullName}?'),
        content: const Text(
          'Manual check-in skips the QR signature check. '
          'Confirm the attendee’s identity before admitting them.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Check in'),
          ),
        ],
      ),
    );
    return ok ?? false;
  }



  Future<void> _checkIn(AttendeeMatch match) async {
    final confirmed = await _confirm(match);
    if (!confirmed || !mounted) return;

    setState(() => _busyTicketId = match.ticketId);
    try {
      final outcome = await ref
          .read(manualCheckInProvider)
          .call(eventId: widget.eventId, ticketId: match.ticketId);
      if (!mounted) return;
      ref
        ..invalidate(attendeeSearchProvider(_key))
        ..invalidate(attendanceStatsProvider(widget.eventId));
      await showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (sheetContext) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: ScanVerdictCard(outcome: outcome),
          ),
        ),
      );
    } on Failure catch (f) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Not checked in: ${f.message}')));
      }
    } finally {
      if (mounted) setState(() => _busyTicketId = null);
    }
  }



  @override
  Widget build(BuildContext context) {
    final searching = _query.length >= SearchAttendees.minQueryLength;
    final results = searching ? ref.watch(attendeeSearchProvider(_key)) : null;

    return Scaffold(
      appBar: AppBar(title: const Text('Find attendee')),
      body: Column(
        children: [
          const OfflineBanner(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _input,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onChanged: _onChanged,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Attendee name or order ID',
              ),
            ),
          ),
          Expanded(
            child: results == null
                ? const _Hint('Type at least 2 characters of a name, or paste an order ID.')
                : results.when(
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (error, _) => ErrorView(
                      error: error,
                      onRetry: () => ref.invalidate(attendeeSearchProvider(_key)),
                    ),
                    data: (matches) => matches.isEmpty
                        ? const _Hint('No attendees match this search.')
                        : ListView.separated(
                            itemCount: matches.length,
                            separatorBuilder: (context, index) => const Divider(height: 1),
                            itemBuilder: (context, index) {
                              final match = matches[index];
                              return _AttendeeTile(
                                match: match,
                                busy: _busyTicketId == match.ticketId,
                                onCheckIn: () => _checkIn(match),
                              );
                            },
                          ),
                  ),
          ),
        ],
      ),
    );
  }
}




class _AttendeeTile extends StatelessWidget {
  const _AttendeeTile({required this.match, required this.busy, required this.onCheckIn});

  final AttendeeMatch match;
  final bool busy;
  final VoidCallback onCheckIn;

  static const _green = Color(0xFF1B7F3B);
  static const _red = Color(0xFFC62828);

  @override
  Widget build(BuildContext context) {
    final details = [
      if (match.orderId != null) 'Order ${match.orderId}',
      if (match.ticketTypeName != null) match.ticketTypeName!,
      if (match.email != null) match.email!,
    ].join(' · ');

    return ListTile(
      title: Text(match.fullName),
      subtitle: details.isEmpty
          ? null
          : Text(details, maxLines: 2, overflow: TextOverflow.ellipsis),
      trailing: switch (match.status) {
        TicketStatus.valid => FilledButton.tonal(
            onPressed: busy ? null : onCheckIn,
            child: busy
                ? const SizedBox.square(
                    dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Check in'),
          ),
        TicketStatus.checkedIn => _StatusChip(
            label: match.checkedInAt == null
                ? 'Checked in'
                : 'In at ${formatClockTime(match.checkedInAt!)}',
            color: _green,
          ),
        TicketStatus.cancelled => const _StatusChip(label: 'Cancelled', color: _red),
        TicketStatus.refunded => const _StatusChip(label: 'Refunded', color: _red),
        TicketStatus.unknown => const _StatusChip(label: 'Unknown', color: Colors.grey),
      },
    );
  }
}




class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Chip(
        avatar: Icon(Icons.circle, size: 10, color: color),
        label: Text(label),
        visualDensity: VisualDensity.compact,
      );
}

class _Hint extends StatelessWidget {
  const _Hint(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(text, textAlign: TextAlign.center),
        ),
      );
}

