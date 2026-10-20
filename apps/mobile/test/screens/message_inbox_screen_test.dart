import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ics_mobile_app/models/home_nav_args.dart';
import 'package:ics_mobile_app/screens/message_inbox_screen.dart';
import 'package:ics_mobile_app/services/chat_service.dart';

class FakeChatService extends ChatService {
  FakeChatService()
    : _liveController = StreamController<ChatMessage>.broadcast(),
      super(baseUrl: 'https://test.local');

  final StreamController<ChatMessage> _liveController;
  final List<String> listedUsers = [];
  final List<String> fetchedChannels = [];
  final List<Map<String, String?>> sentMessages = [];
  List<ChatChannel> channels = <ChatChannel>[];
  Map<String, List<ChatMessage>> historyByChannel = <String, List<ChatMessage>>{};

  Map<String, String> displayNames = <String, String>{};
  List<PresenceEntry> presence = <PresenceEntry>[];
  final List<Map<String, String?>> createdChannels = [];
  final List<Map<String, String>> createdDms = [];

  @override
  Future<List<ChatChannel>> listChannels(
    String incidentId, {
    required String userId,
  }) async {
    listedUsers.add(userId);
    return channels;
  }

  @override
  Future<Map<String, String>> fetchDisplayNames(String incidentId) async {
    return displayNames;
  }

  @override
  Future<List<PresenceEntry>> listPresence(String incidentId) async {
    return presence;
  }

  @override
  Future<void> sendPresenceHeartbeat(
    String incidentId, {
    required String userId,
    String status = 'online',
  }) async {}

  @override
  Future<ChatChannel> createChannel(
    String incidentId, {
    required String name,
    required String createdBy,
    List<String> participantIds = const [],
  }) async {
    createdChannels.add({'name': name, 'createdBy': createdBy});
    return ChatChannel(
      id: 'created-${createdChannels.length}',
      type: 'group',
      participantIds: const [],
      name: name,
      createdBy: createdBy,
      createdAt: DateTime.parse('2026-07-18T12:10:00Z'),
    );
  }

  @override
  Future<ChatChannel> findOrCreateDm(
    String incidentId, {
    required String userA,
    required String userB,
  }) async {
    createdDms.add({'userA': userA, 'userB': userB});
    return ChatChannel(
      id: 'dm-$userA-$userB',
      type: 'dm',
      participantIds: [userA, userB],
      createdAt: DateTime.parse('2026-07-18T12:10:00Z'),
    );
  }

  @override
  Future<List<ChatMessage>> fetchHistory(
    String incidentId, {
    required String channelId,
    int limit = 100,
    String? before,
  }) async {
    fetchedChannels.add(channelId);
    return historyByChannel[channelId] ?? const [];
  }

  @override
  Stream<ChatMessage> connect(String incidentId, {required String channelId}) {
    return _liveController.stream.where((message) => message.channelId == channelId);
  }

  @override
  Future<ChatMessage> sendMessage(
    String incidentId, {
    required String channelId,
    required String senderId,
    required String text,
    String? senderName,
  }) async {
    sentMessages.add({
      'channelId': channelId,
      'senderId': senderId,
      'senderName': senderName,
      'text': text,
    });
    return ChatMessage(
      id: 'sent-${sentMessages.length}',
      channelId: channelId,
      senderId: senderId,
      senderName: senderName,
      text: text,
      createdAt: DateTime.parse('2026-07-18T12:05:00Z'),
    );
  }

  void emit(ChatMessage message) {
    _liveController.add(message);
  }

  @override
  void disconnect() {}

  @override
  void dispose() {
    _liveController.close();
  }
}

HomeNavArgs _args() => const HomeNavArgs(
  incidentId: 'INC1',
  incidentName: 'Missing Aircraft Search',
  teamId: '4',
  teamName: 'GT-4 Alpha',
  session: {'person_id': 'P100'},
  incidentType: 'Missing Person',
);

Widget _wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('loads shared chat channels and initial General history', (tester) async {
    final service = FakeChatService()
      ..channels = [
        ChatChannel(
          id: 'general',
          type: 'group',
          participantIds: const [],
          name: 'General',
          createdAt: DateTime.parse('2026-07-18T11:00:00Z'),
        ),
        ChatChannel(
          id: 'ops',
          type: 'group',
          participantIds: const [],
          name: 'Operations',
          createdAt: DateTime.parse('2026-07-18T11:01:00Z'),
        ),
      ]
      ..historyByChannel = {
        'general': [
          ChatMessage(
            id: 'm1',
            channelId: 'general',
            senderId: 'OSC',
            senderName: 'OSC',
            text: 'Stage at ICP until weather clears.',
            createdAt: DateTime.parse('2026-07-18T12:00:00Z'),
          ),
        ],
      };

    await tester.pumpWidget(
      _wrap(MessageInboxScreen(args: _args(), chatService: service)),
    );
    await tester.pumpAndSettle();

    expect(service.listedUsers, ['P100']);
    expect(service.fetchedChannels, ['general']);
    expect(find.text('General'), findsWidgets);
    expect(find.text('Stage at ICP until weather clears.'), findsOneWidget);
  });

  testWidgets('switching channels loads the selected thread and live messages append', (
    tester,
  ) async {
    final service = FakeChatService()
      ..channels = [
        ChatChannel(
          id: 'general',
          type: 'group',
          participantIds: const [],
          name: 'General',
          createdAt: DateTime.parse('2026-07-18T11:00:00Z'),
        ),
        ChatChannel(
          id: 'ops',
          type: 'group',
          participantIds: const [],
          name: 'Operations',
          createdAt: DateTime.parse('2026-07-18T11:01:00Z'),
        ),
      ]
      ..historyByChannel = {
        'general': const [],
        'ops': [
          ChatMessage(
            id: 'm2',
            channelId: 'ops',
            senderId: 'Planning',
            senderName: 'Planning',
            text: 'Check the updated branch assignment.',
            createdAt: DateTime.parse('2026-07-18T12:02:00Z'),
          ),
        ],
      };

    await tester.pumpWidget(
      _wrap(MessageInboxScreen(args: _args(), chatService: service)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Operations').last);
    await tester.pumpAndSettle();

    expect(service.fetchedChannels, ['general', 'ops']);
    expect(find.text('Check the updated branch assignment.'), findsOneWidget);

    service.emit(
      ChatMessage(
        id: 'm3',
        channelId: 'ops',
        senderId: 'OSC',
        senderName: 'OSC',
        text: 'Resource request approved.',
        createdAt: DateTime.parse('2026-07-18T12:03:00Z'),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Resource request approved.'), findsOneWidget);
  });

  testWidgets('sending a message uses the active channel and signed-in user', (
    tester,
  ) async {
    final service = FakeChatService()
      ..channels = [
        ChatChannel(
          id: 'general',
          type: 'group',
          participantIds: const [],
          name: 'General',
          createdAt: DateTime.parse('2026-07-18T11:00:00Z'),
        ),
      ];

    await tester.pumpWidget(
      _wrap(MessageInboxScreen(args: _args(), chatService: service)),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'Team en route from trailhead.');
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(
      service.sentMessages,
      [
        {
          'channelId': 'general',
          'senderId': 'P100',
          'senderName': 'P100',
          'text': 'Team en route from trailhead.',
        },
      ],
    );
    expect(find.text('Team en route from trailhead.'), findsNothing);
  });
}
