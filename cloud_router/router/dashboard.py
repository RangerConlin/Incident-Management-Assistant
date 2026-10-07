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
  :root {
    color-scheme: dark;
    --bg: #0d1218;
    --panel: #151c24;
    --panel-2: #111820;
    --line: #2a3745;
    --line-soft: #22303c;
    --text: #e8eef5;
    --muted: #94a6b8;
    --accent: #67b7ff;
    --accent-2: #56d39a;
    --warn: #f0b84f;
    --danger: #ff7167;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
  }
  header {
    border-bottom: 1px solid var(--line);
    background: #111922;
  }
  .shell { width: min(1480px, calc(100vw - 32px)); margin: 0 auto; }
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 20px 0;
  }
  h1 { font-size: 1.35rem; margin: 0; letter-spacing: 0; }
  .subtitle { color: var(--muted); margin: 6px 0 0; }
  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--panel);
    color: var(--muted);
    white-space: nowrap;
  }
  .pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-2);
    box-shadow: 0 0 0 4px rgba(86, 211, 154, 0.13);
  }
  main { padding: 24px 0 32px; }
  .cards {
    display: grid;
    grid-template-columns: repeat(5, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 18px;
  }
  .card {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 16px;
    background: var(--panel);
  }
  .card .value { font-size: 2rem; line-height: 1; font-weight: 700; margin-bottom: 8px; }
  .card .label { color: var(--muted); font-size: 0.86rem; }
  .panel {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    overflow: hidden;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px;
    border-bottom: 1px solid var(--line-soft);
  }
  .panel-head h2 { margin: 0; font-size: 1rem; }
  .updated { color: var(--muted); font-size: 0.84rem; }
  .table-wrap { overflow: auto; }
  table { width: 100%; min-width: 820px; border-collapse: separate; border-spacing: 0; }
  th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--line-soft); vertical-align: middle; }
  th { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); background: var(--panel-2); }
  tbody tr:hover { background: rgba(103, 183, 255, 0.06); }
  tbody tr:last-child td { border-bottom: 0; }
  .code { font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; color: #d7eaff; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: #111820;
    color: var(--text);
    white-space: nowrap;
  }
  .dot { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; }
  .dot.ok { background: var(--accent-2); }
  .dot.stale { background: var(--warn); }
  .empty { color: var(--muted); padding: 28px 18px; text-align: center; }
  .error { color: var(--danger); margin: 12px 0 0; }
  @media (max-width: 920px) {
    .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .topbar { align-items: flex-start; flex-direction: column; }
  }
  @media (max-width: 560px) {
    .shell { width: min(100vw - 20px, 1480px); }
    .cards { grid-template-columns: 1fr; }
    .card .value { font-size: 1.65rem; }
  }
</style>
</head>
<body>
  <header>
    <div class="shell topbar">
      <div>
        <h1>SARApp Cloud Router</h1>
        <p class="subtitle">Reverse-tunnel switchboard status. Read-only and auto-refreshing every 3 seconds.</p>
      </div>
      <div class="status-pill"><span class="pulse"></span><span id="router-state">Monitoring</span></div>
    </div>
  </header>

  <main class="shell">
    <div class="cards">
      <div class="card"><div class="value" id="active-count">-</div><div class="label">Connected servers</div></div>
      <div class="card"><div class="value" id="total-requests">-</div><div class="label">Total requests</div></div>
      <div class="card"><div class="value" id="total-timeouts">-</div><div class="label">Request timeouts</div></div>
      <div class="card"><div class="value" id="total-503">-</div><div class="label">Busy or offline</div></div>
      <div class="card"><div class="value" id="total-hb-timeouts">-</div><div class="label">Heartbeat timeouts</div></div>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h2>Registered Tunnels</h2>
        <span class="updated" id="updated-at"></span>
      </div>
      <div class="table-wrap">
        <table id="tunnels-table">
          <thead>
            <tr>
              <th>Status</th>
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
      </div>
      <div class="empty" id="empty-message" style="display:none;">No LAN or cloud servers are currently connected.</div>
    </section>

    <p class="error" id="error-message"></p>
  </main>

<script>
function fmtSeconds(s) {
  if (s < 60) return Math.round(s) + "s";
  if (s < 3600) return Math.round(s / 60) + "m";
  return Math.round(s / 3600) + "h";
}

function text(value) {
  return String(value ?? "");
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
        const statusCell = document.createElement("td");
        const chip = document.createElement("span");
        chip.className = "chip";
        const dot = document.createElement("span");
        dot.className = "dot " + (stale ? "stale" : "ok");
        chip.appendChild(dot);
        chip.appendChild(document.createTextNode(stale ? "Stale" : "Live"));
        statusCell.appendChild(chip);
        row.appendChild(statusCell);

        const codeCell = document.createElement("td");
        codeCell.className = "code";
        codeCell.textContent = text(t.connect_code);
        row.appendChild(codeCell);

        for (const value of [
          t.server_name,
          fmtSeconds(t.connected_seconds_ago),
          fmtSeconds(t.last_pong_seconds_ago) + " ago",
          t.pending_request_count,
          t.ws_channel_count,
        ]) {
          const cell = document.createElement("td");
          cell.textContent = text(value);
          row.appendChild(cell);
        }
        body.appendChild(row);
      }
    }

    document.getElementById("updated-at").textContent = "Updated " + new Date().toLocaleTimeString();
    document.getElementById("router-state").textContent = "Monitoring";
    document.getElementById("error-message").textContent = "";
  } catch (err) {
    document.getElementById("router-state").textContent = "Connection error";
    document.getElementById("error-message").textContent = "Failed to reach router: " + err;
  }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""
