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
}
