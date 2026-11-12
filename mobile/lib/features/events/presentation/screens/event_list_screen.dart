import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:biletflow_verify/app/routes.dart';
import 'package:biletflow_verify/core/error/failure.dart';
import 'package:biletflow_verify/core/utils/date_format.dart';
import 'package:biletflow_verify/core/widgets/error_view.dart';
import 'package:biletflow_verify/core/widgets/offline_banner.dart';
import 'package:biletflow_verify/features/auth/presentation/providers/auth_controller.dart';
import 'package:biletflow_verify/features/events/domain/entities/event_entities.dart';
import 'package:biletflow_verify/features/events/presentation/providers/events_providers.dart';

class EventListScreen extends ConsumerWidget {
  const EventListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(assignedEventsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your events'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authControllerProvider.notifier).signOut(),
          ),
        ],
      ),
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(
            child: events.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => ErrorView(
                error: error,
                onRetry: () => ref.invalidate(assignedEventsProvider),
              ),
              data: (list) => RefreshIndicator(
                onRefresh: () async {
                  ref.invalidate(assignedEventsProvider);
                  try {
                    await ref.read(assignedEventsProvider.future);
                  } on Failure {
                    // find error 
                  }
                },
                child: list.isEmpty
                    ? ListView(children: const [SizedBox(height: 96), _NoEventsAssigned()])
                    : ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: list.length,
                        separatorBuilder: (context, index) => const SizedBox(height: 12),
                        itemBuilder: (context, index) => _EventCard(event: list[index]),
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EventCard extends StatelessWidget {
  const _EventCard({required this.event});
  final AssignedEvent event;

  @override
  Widget build(BuildContext context) {
    final subtitle = [
      formatEventDateTime(event.startsAt),
      if (event.venueName != null) event.venueName!,
    ].join('\n');

    return Card(
      clipBehavior: Clip.antiAlias,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: const CircleAvatar(child: Icon(Icons.event)),
        title: Text(event.title, style: Theme.of(context).textTheme.titleMedium),
        subtitle: Text(subtitle),
        isThreeLine: event.venueName != null,
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.go(AppRoutes.dashboard(event.id)),
      ),
    );
  }
}

class _NoEventsAssigned extends StatelessWidget {
  const _NoEventsAssigned();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        children: [
          Icon(Icons.event_busy, size: 56, color: theme.colorScheme.outline),
          const SizedBox(height: 16),
          Text('No events assigned to you', style: theme.textTheme.titleMedium),
          const SizedBox(height: 8),
          const Text(
            'Ask the event organizer to add you as check-in staff, then pull down to refresh.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}