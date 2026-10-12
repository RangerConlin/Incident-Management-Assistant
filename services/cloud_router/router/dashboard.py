"""Self-contained HTML for the router's read-only status dashboard.

No build step, no external assets — this is a headless service, so the page
is a single inline template polling ``/dashboard/data`` on a timer. See
``create_router_app`` in ``app.py`` for how the data endpoint is assembled.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SARApp Cloud Router — Status</title>
<style>
  :root { color-scheme: light dark; }
  body {
    font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    max-width: 900px; margin: 2rem auto; padding: 0 1rem;
    background: Canvas; color: CanvasText;
  }
  h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
  .subtitle { color: GrayText; margin-top: 0; margin-bottom: 1.5rem; }
  .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
  .card {
    border: 1px solid color-mix(in srgb, CanvasText 20%, transparent);
    border-radius: 8px; padding: 0.75rem 1rem; min-width: 140px;
  }
  .card .value { font-size: 1.6rem; font-weight: 600; }
  .card .label { color: GrayText; font-size: 0.85rem; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
  th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid color-mix(in srgb, CanvasText 12%, transparent); }
  th { font-size: 0.8rem; text-transform: uppercase; color: GrayText; }
  .dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.4rem; }
  .dot.ok { background: #2e9e44; }
  .dot.stale { background: #d9a400; }
  .empty { color: GrayText; padding: 1rem 0; }
  .updated { color: GrayText; font-size: 0.8rem; margin-top: 1rem; }
  .error { color: #c0392b; }
</style>
</head>
<body>
  <h1>SARApp Cloud Router</h1>
  <p class="subtitle">Reverse-tunnel switchboard status — read-only, auto-refreshes every 3s.</p>

  <div class="cards">
    <div class="card"><div class="value" id="active-count">—</div><div class="label">Connected LAN servers</div></div>
    <div class="card"><div class="value" id="total-requests">—</div><div class="label">Total requests</div></div>
    <div class="card"><div class="value" id="total-timeouts">—</div><div class="label">Timeouts</div></div>
    <div class="card"><div class="value" id="total-503">—</div><div class="label">503 (busy/offline)</div></div>
    <div class="card"><div class="value" id="total-hb-timeouts">—</div><div class="label">Heartbeat timeouts</div></div>
  </div>

  <table id="tunnels-table">
    <thead>
      <tr>
        <th></th>
        <th>Connect code</th>
        <th>Server name</th>
        <th>Connected for</th>
        <th>Last heartbeat</th>
        <th>Pending requests</th>
        <th>Open WS channels</th>
      </tr>
    </thead>
    <tbody id="tunnels-body"></tbody>
  </table>
  <div class="empty" id="empty-message" style="display:none;">No LAN servers currently connected.</div>

  <p class="updated" id="updated-at"></p>
  <p class="error" id="error-message"></p>

<script>
function fmtSeconds(s) {
  if (s < 60) return Math.round(s) + "s";
  if (s < 3600) return Math.round(s / 60) + "m";
  return Math.round(s / 3600) + "h";
}

async function refresh() {
  try {
    const res = await fetch("/dashboard/data", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    document.getElementById("active-count").textContent = data.active_tunnel_count;
    document.getElementById("total-requests").textContent = data.metrics.total_requests;
    document.getElementById("total-timeouts").textContent = data.metrics.total_request_timeouts;
    document.getElementById("total-503").textContent = data.metrics.total_request_failures_503;
    document.getElementById("total-hb-timeouts").textContent = data.metrics.total_heartbeat_timeouts;

    const body = document.getElementById("tunnels-body");
    body.innerHTML = "";
    const empty = document.getElementById("empty-message");
    if (data.tunnels.length === 0) {
      empty.style.display = "block";
    } else {
      empty.style.display = "none";
      for (const t of data.tunnels) {
        const stale = t.last_pong_seconds_ago > 60;
        const row = document.createElement("tr");
        row.innerHTML =
          '<td><span class="dot ' + (stale ? "stale" : "ok") + '"></span></td>' +
          "<td>" + t.connect_code + "</td>" +
          "<td>" + t.server_name + "</td>" +
          "<td>" + fmtSeconds(t.connected_seconds_ago) + "</td>" +
          "<td>" + fmtSeconds(t.last_pong_seconds_ago) + " ago</td>" +
          "<td>" + t.pending_request_count + "</td>" +
          "<td>" + t.ws_channel_count + "</td>";
        body.appendChild(row);
      }
    }

    document.getElementById("updated-at").textContent = "Updated " + new Date().toLocaleTimeString();
    document.getElementById("error-message").textContent = "";
  } catch (err) {
    document.getElementById("error-message").textContent = "Failed to reach router: " + err;
  }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""
