import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:biletflow_verify/app/routes.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/utils/date_format.dart';
import 'package:biletflow_verify/core/widgets/error_view.dart';
import 'package:biletflow_verify/core/widgets/offline_banner.dart';
import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';
import 'package:biletflow_verify/features/events/presentation/providers/events_providers.dart';

class EventDashboardScreen extends ConsumerWidget {
  const EventDashboardScreen({super.key, required this.eventId});
  final String eventId;

  Future<void> _openAndRefresh(BuildContext context, WidgetRef ref, String location) async {
    await context.push(location);
    
    if (context.mounted) ref.invalidate(attendanceStatsProvider(eventId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final event = ref.watch(assignedEventProvider(eventId));
    final stats = ref.watch(attendanceStatsProvider(eventId));

    return Scaffold(
      appBar: AppBar(title: Text(event.value?.title ?? 'Event')),
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(
            child: event.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => ErrorView(
                error: error,
                onRetry: () => ref.invalidate(assignedEventsProvider),
              ),
              data: (ev) => RefreshIndicator(
                onRefresh: () async {
                  ref.invalidate(attendanceStatsProvider(eventId));
                  try {
                    await ref.read(attendanceStatsProvider(eventId).future);
                  } on Failure {
                    // find error
                  }
                },
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _EventHeader(event: ev),
                    const SizedBox(height: 16),
                    _AttendanceCard(
                      stats: stats,
                      onRetry: () => ref.invalidate(attendanceStatsProvider(eventId)),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(64)),
                      onPressed: () => _openAndRefresh(context, ref, AppRoutes.scan(eventId)),
                      icon: const Icon(Icons.qr_code_scanner, size: 28),
                      label: const Text('Scan tickets'),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                      onPressed: () => _openAndRefresh(context, ref, AppRoutes.search(eventId)),
                      icon: const Icon(Icons.person_search),
                      label: const Text('Find attendee by name or order ID'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EventHeader extends StatelessWidget {
  const _EventHeader({required this.event});
  final AssignedEvent event;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(event.title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        _IconLine(icon: Icons.schedule, text: formatEventDateTime(event.startsAt)),
        if (event.venueName != null) ...[
          const SizedBox(height: 4),
          _IconLine(icon: Icons.place_outlined, text: event.venueName!),
        ],
      ],
    );
  }
}

class _IconLine extends StatelessWidget {
  const _IconLine({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 6),
          Expanded(child: Text(text)),
        ],
      );
}

class _AttendanceCard extends StatelessWidget {
  const _AttendanceCard({required this.stats, required this.onRetry});

  final AsyncValue<AttendanceStats> stats;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    final data = stats.value;

    if (data == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: stats.hasError
              ? ErrorView(error: stats.error!, onRetry: onRetry)
              : const SizedBox(height: 120, child: Center(child: CircularProgressIndicator())),
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('Attendance', style: theme.textTheme.titleMedium),
                const Spacer(),
                if (stats.isLoading)
                  const SizedBox.square(
                    dimension: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _Metric(label: 'Checked in', value: data.checkedIn, emphasized: true),
                ),
                Expanded(child: _Metric(label: 'Registered', value: data.registered)),
                Expanded(child: _Metric(label: 'Remaining', value: data.remaining)),
              ],
            ),
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(value: data.progress, minHeight: 10),
            ),
            const SizedBox(height: 8),
            Text(
              '${(data.progress * 100).toStringAsFixed(0)}% arrived',
              style: theme.textTheme.bodySmall,
            ),
            if (stats.hasError) ...[
              const SizedBox(height: 8),
              Text(
                'Live update failed — showing last known counts.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value, this.emphasized = false});

  final String label;
  final int value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final style = emphasized ? theme.textTheme.displaySmall : theme.textTheme.headlineSmall;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$value',
          style: style?.copyWith(
            fontWeight: FontWeight.w700,
            color: emphasized ? theme.colorScheme.primary : null,
          ),
        ),
        Text(label, style: theme.textTheme.labelMedium),
      ],
    );
  }
}