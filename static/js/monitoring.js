(() => {
    const style = document.createElement("style");
    style.textContent = `
        .monitor-table { width:100%; border-collapse:collapse; min-width:850px; font-size:13px; }
        .monitor-table th,.monitor-table td { padding:11px; text-align:left; border-bottom:1px solid #26364a; }
        .monitor-table th { color:#91a5bd; }
        .monitor-muted { color:#91a5bd; }
        .monitor-error { color:#ffb2b9; }
        .monitor-ok { color:#9ce4bd; }
        .monitor-time { color:#91a5bd; font-size:12px; }
    `;
    document.head.appendChild(style);

    const main = document.querySelector("main");
    if (!main) return;

    const panel = document.createElement("section");
    panel.className = "panel";
    panel.innerHTML = `
        <div class="section-heading">
            <h2>Live Rig Monitoring</h2>
            <span class="monitor-time" id="monitor-updated">Waiting for data...</span>
        </div>
        <div class="table-wrap">
            <table class="monitor-table">
                <thead><tr>
                    <th>Rig</th><th>Connection</th><th>CPU</th><th>RAM</th>
                    <th>Temperature</th><th>Hash rate (10s / 1m / 15m)</th>
                    <th>Accepted</th><th>Rejected</th><th>Pool</th><th>Uptime</th><th>XMRig</th>
                </tr></thead>
                <tbody id="monitor-rows">
                    <tr><td colspan="11" class="empty">Loading monitoring data...</td></tr>
                </tbody>
            </table>
        </div>`;
    main.insertBefore(panel, main.firstChild);

    const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    })[c]);

    const duration = seconds => {
        if (seconds == null) return "—";
        const d = Math.floor(seconds / 86400);
        const h = Math.floor(seconds % 86400 / 3600);
        const m = Math.floor(seconds % 3600 / 60);
        return `${d}d ${h}h ${m}m`;
    };

    let monitoringInFlight = false;

    async function refreshMonitoring() {
        if (monitoringInFlight) return;
        monitoringInFlight = true;
        const rows = document.getElementById("monitor-rows");
        const updated = document.getElementById("monitor-updated");
        try {
            const response = await fetch("/api/rigs/monitor", {cache:"no-store"});
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const rigs = data.rigs || [];

            if (!rigs.length) {
                rows.innerHTML = '<tr><td colspan="11" class="empty">No rigs registered.</td></tr>';
            } else {
                rows.innerHTML = rigs.map(rig => {
                    const online = rig.status === "online";
                    const connection = rig.status === "manual_auth_required"
                        ? '<span class="monitor-muted">Manual SSH</span>'
                        : online
                            ? '<span class="monitor-ok">Online</span>'
                            : `<span class="monitor-error" title="${esc(rig.error || "")}">Offline</span>`;
                    const cpu = rig.cpu_percent == null ? "—" : `${rig.cpu_percent}%`;
                    const ram = rig.ram_percent == null ? "—" : `${rig.ram_percent}%`;
                    const temp = rig.temperature_c == null ? "—" : `${rig.temperature_c} °C`;
                    const formatHash = value => {
                        if (value == null || !Number.isFinite(Number(value))) return "—";
                        let rate = Number(value);
                        const units = ["H/s", "kH/s", "MH/s", "GH/s", "TH/s"];
                        let unit = 0;
                        while (rate >= 1000 && unit < units.length - 1) {
                            rate /= 1000;
                            unit++;
                        }
                        return `${rate.toFixed(2)} ${units[unit]}`;
                    };
                    const hash = `10s: ${formatHash(rig.hash_rate_10s)}<br>1m: ${formatHash(rig.hash_rate_1m)}<br>15m: ${formatHash(rig.hash_rate_15m)}`;
                    const accepted = rig.shares_accepted ?? "—";
                    const rejected = rig.shares_rejected ?? "—";
                    const pool = rig.pool_name
                        ? `${esc(rig.pool_name)} · ${rig.pool_connected ? '<span class="monitor-ok">Connected</span>' : '<span class="monitor-error">Disconnected</span>'}`
                        : "—";
                    const worker = rig.xmrig_status === "running"
                        ? '<span class="monitor-ok">Running</span>'
                        : rig.xmrig_status === "stopped"
                            ? "Stopped" : "—";
                    return `<tr>
                        <td>${esc(rig.name)}</td><td>${connection}</td>
                        <td>${cpu}</td><td>${ram}</td><td>${temp}</td>
                        <td>${hash}</td><td>${esc(accepted)}</td><td>${esc(rejected)}</td>
                        <td>${pool}</td><td>${duration(rig.uptime_seconds)}</td><td>${worker}</td>
                    </tr>`;
                }).join("");
            }
            updated.textContent = `Updated ${new Date().toLocaleTimeString()} · refresh every 30s`;
        } catch (error) {
            updated.textContent = "Monitoring unavailable";
            rows.innerHTML = `<tr><td colspan="11" class="monitor-error">Could not load monitoring data: ${esc(error.message)}</td></tr>`;
        } finally {
            monitoringInFlight = false;
        }
    }

    refreshMonitoring();
    setInterval(refreshMonitoring, 30000);
})();
