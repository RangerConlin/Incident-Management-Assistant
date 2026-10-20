import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ics_mobile_app/services/chat_service.dart';

void main() {
  test('listChannels uses the shared chat endpoint contract', () async {
    late Uri requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'c1',
              'type': 'group',
              'name': 'General',
              'participant_ids': [],
            },
          ],
        }),
        200,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );
    final channels = await service.listChannels('INC1', userId: 'P100');

    expect(
      requestedUri.toString(),
      'https://test.local/api/incidents/INC1/chat/channels?user_id=P100',
    );
    expect(channels.single.id, 'c1');
    expect(channels.single.displayTitleFor('P100'), 'General');
  });

  test('fetchHistory and sendMessage use channel-scoped message routes', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'GET') {
        return http.Response(
          jsonEncode({
            'items': [
              {
                'id': 'm1',
                'channel_id': 'c1',
                'sender_id': 'P100',
                'text': 'Ready to deploy',
                'created_at': '2026-07-18T12:00:00Z',
              },
            ],
          }),
          200,
        );
      }
      return http.Response(
        jsonEncode({
          'id': 'm2',
          'channel_id': 'c1',
          'sender_id': 'P100',
          'sender_name': 'P100',
          'text': 'Moving now',
          'created_at': '2026-07-18T12:01:00Z',
        }),
        201,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );

    final history = await service.fetchHistory(
      'INC1',
      channelId: 'c1',
      limit: 50,
      before: '2026-07-18T12:30:00Z',
    );
    final sent = await service.sendMessage(
      'INC1',
      channelId: 'c1',
      senderId: 'P100',
      senderName: 'P100',
      text: 'Moving now',
    );

    expect(
      requests.first.url.toString(),
      'https://test.local/api/incidents/INC1/chat/channels/c1/messages?limit=50&before=2026-07-18T12%3A30%3A00Z',
    );
    expect(
      requests.last.url.toString(),
      'https://test.local/api/incidents/INC1/chat/channels/c1/messages',
    );
    expect(requests.last.body, contains('"sender_id":"P100"'));
    expect(requests.last.body, contains('"text":"Moving now"'));
    expect(history.single.channelId, 'c1');
    expect(sent.id, 'm2');
  });

  test('createChannel and findOrCreateDm post to the chat group/dm routes', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.url.path.endsWith('/chat/channels')) {
        return http.Response(
          jsonEncode({
            'id': 'c2',
            'type': 'group',
            'name': 'Logistics Overflow',
            'created_by': 'P100',
            'participant_ids': [],
            'is_default': false,
          }),
          201,
        );
      }
      return http.Response(
        jsonEncode({
          'id': 'dm1',
          'type': 'dm',
          'participant_ids': ['P100', 'P200'],
        }),
        200,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );

    final channel = await service.createChannel(
      'INC1',
      name: 'Logistics Overflow',
      createdBy: 'P100',
    );
    final dm = await service.findOrCreateDm(
      'INC1',
      userA: 'P100',
      userB: 'P200',
    );

    expect(
      requests.first.url.toString(),
      'https://test.local/api/incidents/INC1/chat/channels',
    );
    expect(requests.first.body, contains('"name":"Logistics Overflow"'));
    expect(channel.id, 'c2');
    expect(channel.isDefault, isFalse);

    expect(
      requests.last.url.toString(),
      'https://test.local/api/incidents/INC1/chat/dms',
    );
    expect(requests.last.body, contains('"user_a":"P100"'));
    expect(dm.isDirectMessage, isTrue);
  });

  test('is_default channels parse the protection flag', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': 'general',
              'type': 'group',
              'name': 'General',
              'participant_ids': [],
              'is_default': true,
            },
          ],
        }),
        200,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );
    final channels = await service.listChannels('INC1', userId: 'P100');

    expect(channels.single.isDefault, isTrue);
  });

  test('presence heartbeat/list round trip the roster contract', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      if (request.method == 'POST') {
        return http.Response(jsonEncode({'user_id': 'P100', 'status': 'away'}), 200);
      }
      return http.Response(
        jsonEncode({
          'items': [
            {'user_id': 'P100', 'status': 'away'},
            {'user_id': 'P200', 'status': 'online'},
          ],
        }),
        200,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );

    await service.sendPresenceHeartbeat('INC1', userId: 'P100', status: 'away');
    final roster = await service.listPresence('INC1');

    expect(
      requests.first.url.toString(),
      'https://test.local/api/incidents/INC1/presence/heartbeat',
    );
    expect(requests.first.body, contains('"status":"away"'));
    expect(
      requests.last.url.toString(),
      'https://test.local/api/incidents/INC1/presence',
    );
    expect(roster.map((e) => e.userId), ['P100', 'P200']);
    expect(roster.first.status, 'away');
  });

  test('fetchDisplayNames maps the checkin roster by person_id', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/incidents/INC1/checkin/roster');
      return http.Response(
        jsonEncode([
          {'person_id': 'P100', 'name': 'Alex Rivera'},
          {'person_id': '', 'name': 'No Login Id'},
          {'person_id': 'P200', 'name': ''},
        ]),
        200,
      );
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );
    final names = await service.fetchDisplayNames('INC1');

    expect(names, {'P100': 'Alex Rivera'});
  });

  test('fetchDisplayNames fails soft on a server error', () async {
    final client = MockClient((request) async {
      return http.Response('boom', 500);
    });

    final service = ChatService(
      httpClient: client,
      baseUrl: 'https://test.local',
    );

    expect(await service.fetchDisplayNames('INC1'), <String, String>{});
  });
}
