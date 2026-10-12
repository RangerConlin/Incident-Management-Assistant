import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/app_config.dart';
import 'sarapp_api_client.dart';

class ChatChannel {
  ChatChannel({
    required this.id,
    required this.type,
    required this.participantIds,
    required this.createdAt,
    this.name,
    this.createdBy,
  });

  factory ChatChannel.fromJson(Map<String, dynamic> json) {
    return ChatChannel(
      id: '${json['id'] ?? json['_id'] ?? ''}',
      type: '${json['type'] ?? 'group'}',
      name: json['name'] as String?,
      participantIds: (json['participant_ids'] as List<dynamic>? ?? const [])
          .map((item) => '$item')
          .toList(),
      createdBy: json['created_by'] == null ? null : '${json['created_by']}',
      createdAt:
          DateTime.tryParse('${json['created_at'] ?? ''}') ?? DateTime.now(),
    );
  }

  final String id;
  final String type;
  final String? name;
  final List<String> participantIds;
  final String? createdBy;
  final DateTime createdAt;

  bool get isDirectMessage => type == 'dm';

  String displayTitleFor(String currentUserId) {
    if (!isDirectMessage) {
      final trimmed = name?.trim() ?? '';
      return trimmed.isEmpty ? 'Unnamed channel' : trimmed;
    }
    final otherParticipant = participantIds.firstWhere(
      (participant) => participant != currentUserId,
      orElse: () => '',
    );
    return otherParticipant.isEmpty ? 'Direct Message' : otherParticipant;
  }
}

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.channelId,
    required this.senderId,
    required this.text,
    required this.createdAt,
    this.senderName,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: '${json['id'] ?? json['_id'] ?? ''}',
      channelId: '${json['channel_id'] ?? ''}',
      senderId: '${json['sender_id'] ?? ''}',
      senderName: json['sender_name'] as String?,
      text: '${json['text'] ?? ''}',
      createdAt:
          DateTime.tryParse('${json['created_at'] ?? ''}') ?? DateTime.now(),
    );
  }

  final String id;
  final String channelId;
  final String senderId;
  final String? senderName;
  final String text;
  final DateTime createdAt;
}

/// REST + WebSocket client for incident-scoped chat.
///
/// Desktop and mobile both use the same incident-wide WebSocket
/// (`/api/incidents/{incident_id}/ws`) for live updates. Chat is filtered
/// out of the generic `messages` collection stream by `channel_id`.
class ChatService {
  ChatService({http.Client? httpClient, String? baseUrl})
    : _httpClient = httpClient ?? http.Client(),
      _ownsHttpClient = httpClient == null,
      baseUrl = baseUrl ?? AppConfig.sarAppBaseUrl;

  final http.Client _httpClient;
  final bool _ownsHttpClient;
  final String baseUrl;
  WebSocketChannel? _channel;
  StreamController<ChatMessage>? _liveController;
  StreamSubscription<dynamic>? _socketSubscription;

  Future<List<ChatChannel>> listChannels(
    String incidentId, {
    required String userId,
  }) async {
    final uri = Uri.parse('$baseUrl/api/incidents/$incidentId/chat/channels')
        .replace(queryParameters: {'user_id': userId});
    final response = await _httpClient.get(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SarAppApiException(
        'Failed to load chat channels',
        statusCode: response.statusCode,
      );
    }
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final items = decoded['items'] as List<dynamic>? ?? const [];
    return items
        .map((item) => ChatChannel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<ChatMessage>> fetchHistory(
    String incidentId, {
    required String channelId,
    int limit = 100,
    String? before,
  }) async {
    final queryParameters = <String, String>{'limit': '$limit'};
    if (before != null && before.isNotEmpty) {
      queryParameters['before'] = before;
    }
    final uri =
        Uri.parse(
          '$baseUrl/api/incidents/$incidentId/chat/channels/$channelId/messages',
        ).replace(queryParameters: queryParameters);
    final response = await _httpClient.get(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SarAppApiException(
        'Failed to load chat history',
        statusCode: response.statusCode,
      );
    }
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final items = decoded['items'] as List<dynamic>? ?? const [];
    return items
        .map((item) => ChatMessage.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<ChatMessage> sendMessage(
    String incidentId, {
    required String channelId,
    required String senderId,
    required String text,
    String? senderName,
  }) async {
    final uri = Uri.parse(
      '$baseUrl/api/incidents/$incidentId/chat/channels/$channelId/messages',
    );
    final response = await _httpClient.post(
      uri,
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'sender_id': senderId,
        'sender_name': senderName,
        'text': text,
      }),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SarAppApiException(
        'Failed to send message',
        statusCode: response.statusCode,
      );
    }
    return ChatMessage.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Stream<ChatMessage> connect(String incidentId, {required String channelId}) {
    disconnect();
    final wsUrl =
        '${baseUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://')}/api/incidents/$incidentId/ws';
    final channelSocket = WebSocketChannel.connect(Uri.parse(wsUrl));
    _channel = channelSocket;
    final controller = StreamController<ChatMessage>.broadcast();
    _liveController = controller;

    _socketSubscription = channelSocket.stream.listen(
      (event) {
        final payload = jsonDecode(event as String) as Map<String, dynamic>;
        if (payload['collection'] != 'messages') return;
        if (payload['op'] != 'created') return;
        final doc = payload['doc'] as Map<String, dynamic>?;
        if (doc == null || '${doc['channel_id'] ?? ''}' != channelId) return;
        final normalized = {...doc, 'id': doc['_id']};
        controller.add(ChatMessage.fromJson(normalized));
      },
      onError: controller.addError,
      onDone: () {
        if (!controller.isClosed) {
          controller.close();
        }
      },
    );

    return controller.stream;
  }

  void disconnect() {
    _socketSubscription?.cancel();
    _socketSubscription = null;
    _channel?.sink.close();
    _channel = null;
    final liveController = _liveController;
    if (liveController != null && !liveController.isClosed) {
      liveController.close();
    }
    _liveController = null;
  }

  void dispose() {
    disconnect();
    if (_ownsHttpClient) {
      _httpClient.close();
    }
  }
}
