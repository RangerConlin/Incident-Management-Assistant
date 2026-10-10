import { useEffect, useState } from "react";
import { useSession } from "../auth/SessionContext";
import { ApiError } from "../api/client";
import { listChannels, listMessages, sendMessage } from "../api/endpoints";
import type { ChatChannel, ChatMessage } from "../api/types";

export default function MessagingScreen() {
  const { incidentId, user, personnel } = useSession();
  const [channels, setChannels] = useState<ChatChannel[]>([]);
  const [activeChannel, setActiveChannel] = useState<ChatChannel | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const senderId = user?.user_id ?? "";
  const senderName = personnel?.name || user?.display_name || senderId;

  useEffect(() => {
    if (!incidentId || !senderId) return;
    listChannels(incidentId, senderId)
      .then((res) => setChannels(res.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load channels."));
  }, [incidentId, senderId]);

  useEffect(() => {
    if (!incidentId || !activeChannel) return;
    const load = () =>
      listMessages(incidentId, activeChannel.id)
        .then((res) => setMessages(res.items))
        .catch(() => {
          // transient poll failure — next interval retries
        });
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [incidentId, activeChannel]);

  const onSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incidentId || !activeChannel || !draft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const sent = await sendMessage(incidentId, activeChannel.id, senderId, senderName, draft.trim());
      setMessages((prev) => [...prev, sent]);
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send message.");
    } finally {
      setBusy(false);
    }
  };

  if (!activeChannel) {
    return (
      <div>
        <h3>Channels</h3>
        {error && <p className="error">{error}</p>}
        {channels.map((c) => (
          <div key={c.id} className="list-item" onClick={() => setActiveChannel(c)}>
            {c.name || "Direct Message"}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      <button className="secondary" style={{ width: "auto", marginBottom: 12 }} onClick={() => setActiveChannel(null)}>
        ← Channels
      </button>
      <h3>{activeChannel.name || "Direct Message"}</h3>
      <div className="message-list">
        {messages.map((m) => (
          <div key={m.id} className="message">
            <div className="meta">{m.sender_name || m.sender_id}</div>
            {m.text}
          </div>
        ))}
        {messages.length === 0 && <p>No messages yet.</p>}
      </div>
      <form onSubmit={onSend} style={{ display: "flex", gap: 8 }}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Message…"
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={busy} style={{ width: "auto" }}>
          Send
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
