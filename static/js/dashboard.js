const $ = (id) => document.getElementById(id);
let rigs = [];
let pools = [];

function log(message) {
    const stamp = new Date().toLocaleTimeString();
    $("activity").textContent = `[${stamp}] ${message}\n` + $("activity").textContent;
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    return body;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}

function badge(value) {
    const safe = String(value || "unknown");
    const cls = safe === "online" || safe === "running"
        ? "online" : safe === "offline" || safe === "stopped" ? "offline" : "";
    return `<span class="status ${cls}">${escapeHtml(safe)}</span>`;
}

async function loadWallet() {
    const settings = await api("/api/mining/settings");
    $("wallet-address").value = settings.wallet_address || "";
}

async function loadData() {
    try {
        [rigs, pools] = await Promise.all([api("/api/rigs"), api("/api/pools")]);
        renderRigs();
        renderPools();
        $("rig-count").textContent = rigs.length;
        $("online-count").textContent = rigs.filter(r => r.connection_status === "online").length;
        $("mining-count").textContent = rigs.filter(r => r.worker_status === "running").length;
        $("pool-count").textContent = pools.length;
        $("rig-pool").innerHTML = '<option value="">No pool assigned</option>' +
            pools.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
    } catch (error) {
        log(`Unable to load data: ${error.message}`);
    }
}

function renderRigs() {
    const body = $("rig-list");
    if (!rigs.length) {
        body.innerHTML = '<tr><td colspan="9" class="empty">No servers registered.</td></tr>';
        return;
    }
    body.innerHTML = rigs.map(r => `
        <tr>
            <td><strong>${escapeHtml(r.name)}</strong></td>
            <td>${escapeHtml(r.worker_id || r.name)}</td>
            <td>${escapeHtml(r.host)}:${r.ssh_port}</td>
            <td>${escapeHtml(r.ssh_username)}</td>
            <td>${r.cpu_threads ?? "Unknown"}</td>
            <td>${r.cpu_limit_percent}%</td>
            <td>${badge(r.connection_status)}</td>
            <td>${badge(r.worker_status)}</td>
            <td><div class="row-actions">
                <button type="button" data-edit-rig="${r.id}">Edit</button>
                <button data-worker="${r.id}">Worker ID</button>
                <button data-probe="${r.id}">Probe</button>
                <button data-deploy="${r.id}">Install</button>
                <button data-action="status" data-id="${r.id}">Status</button>
                <button data-action="start" data-id="${r.id}">Start</button>
                <button data-action="stop" data-id="${r.id}" class="danger">Stop</button>
                <button data-action="restart" data-id="${r.id}">Restart</button>
                <button type="button" class="danger" data-delete-rig="${r.id}">Delete</button>
            </div></td>
        </tr>`).join("");

    body.querySelectorAll("[data-edit-rig]").forEach(b =>
        b.addEventListener("click", () => editRig(Number(b.dataset.editRig))));
    body.querySelectorAll("[data-worker]").forEach(b =>
        b.addEventListener("click", () => configureWorker(Number(b.dataset.worker), b)));
    body.querySelectorAll("[data-probe]").forEach(b =>
        b.addEventListener("click", () => probeRig(Number(b.dataset.probe), b)));
    body.querySelectorAll("[data-deploy]").forEach(b =>
        b.addEventListener("click", () => deployRig(Number(b.dataset.deploy), b)));
    body.querySelectorAll("[data-action]").forEach(b =>
        b.addEventListener("click", () => miningAction(Number(b.dataset.id), b.dataset.action, b)));
    body.querySelectorAll("[data-delete-rig]").forEach(b =>
        b.addEventListener("click", () => deleteRig(Number(b.dataset.deleteRig))));
}

function editRig(id) {
    const rig = rigs.find(r => r.id === id);
    if (!rig) return;

    const form = $("rig-form");
    form.elements.name.value = rig.name || "";
    form.elements.host.value = rig.host || "";
    form.elements.ssh_port.value = rig.ssh_port ?? 22;
    form.elements.ssh_username.value = rig.ssh_username || "";
    form.elements.ssh_auth_method.value = rig.ssh_auth_method || "key";
    form.elements.cpu_limit_percent.value = rig.cpu_limit_percent ?? 75;
    form.elements.cpu_threads.value = rig.cpu_threads ?? "";
    form.elements.pool_id.value = rig.pool_id ?? "";

    form.dataset.editingId = String(id);
    $("rig-form-title").textContent = `Edit server: ${rig.name}`;
    $("rig-submit").textContent = "Update server";
    form.classList.remove("hidden");
    form.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function deleteRig(id) {
    const rig = rigs.find(r => r.id === id);
    if (!rig || !window.confirm(`Delete rig "${rig.name}"?`)) return;

    try {
        await api(`/api/rigs/${id}`, { method: "DELETE" });
        log(`Rig deleted: ${rig.name}`);
        await loadData();
    } catch (error) {
        log(`Unable to delete rig: ${error.message}`);
    }
}

function renderPools() {
    $("pool-list").innerHTML = pools.length ? pools.map(p => `
        <article class="pool-card">
            <strong>${escapeHtml(p.name)} ${p.is_default ? "★" : ""}</strong>
            <span>${escapeHtml(p.url)}</span>
            <span>Type: ${escapeHtml(p.pool_type)} · ${p.enabled ? "Enabled" : "Disabled"}</span>
            <button type="button" data-edit-pool="${p.id}">Edit</button>
            <button type="button" class="danger" data-delete-pool="${p.id}">Delete</button>
        </article>`).join("") : '<p class="empty">No pools configured.</p>';

    $("pool-list").querySelectorAll("[data-edit-pool]").forEach(button => {
        button.addEventListener("click", () => editPool(Number(button.dataset.editPool)));
    });
    $("pool-list").querySelectorAll("[data-delete-pool]").forEach(button => {
        button.addEventListener("click", () => deletePool(Number(button.dataset.deletePool)));
    });
}

function getSSHPassword(rig) {
    if (rig.ssh_auth_method !== "password") return null;
    return window.prompt(`SSH password for ${rig.name} (used for this request only):`);
}

async function configureWorker(id, button) {
    const rig = rigs.find(r => r.id === id);
    const worker = window.prompt(`Worker ID for ${rig.name}:`, rig.worker_id || rig.name);
    if (worker === null) return;
    button.disabled = true;
    try {
        await api(`/api/rigs/${id}/worker`, {
            method: "PUT", body: JSON.stringify({ worker_id: worker.trim() })
        });
        log(`Worker ID saved for ${rig.name}: ${worker.trim()}`);
        await loadData();
    } catch (error) {
        log(`Unable to save Worker ID: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

async function probeRig(id, button) {
    const rig = rigs.find(r => r.id === id);
    const password = getSSHPassword(rig);
    if (rig.ssh_auth_method === "password" && password === null) return;
    button.disabled = true;
    try {
        const result = await api(`/api/rigs/${id}/probe`, {
            method: "POST", body: password === null ? null : JSON.stringify({ password })
        });
        log(`SSH connected: ${rig.name}; host=${result.hostname}; CPU=${result.cpu_threads}; OS=${result.operating_system}`);
        await loadData();
    } catch (error) {
        log(`SSH probe failed for ${rig.name}: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

async function deployRig(id, button) {
    const rig = rigs.find(r => r.id === id);
    if (!rig.pool_id) return log(`Assign a pool to ${rig.name} before installing XMRig.`);
    if (!$("wallet-address").value.trim()) {
        log("Configure the global Monero wallet before installing XMRig.");
        $("wallet-address").focus();
        return;
    }
    const password = getSSHPassword(rig);
    if (rig.ssh_auth_method === "password" && password === null) return;
    if (!window.confirm(
        `Install XMRig on ${rig.name}?\n\nShared wallet: ${$("wallet-address").value.trim()}\nWorker ID: ${rig.worker_id}\n\nMining will NOT start.`
    )) return;

    button.disabled = true;
    try {
        const payload = {};
        if (password !== null) payload.password = password;
        const result = await api(`/api/rigs/${id}/deploy`, {
            method: "POST", body: JSON.stringify(payload)
        });
        log(`XMRig installed on ${rig.name}. Worker: ${rig.worker_id}. Version: ${result.installation?.version || "unknown"}. Miner remains stopped.`);
        await loadData();
    } catch (error) {
        log(`XMRig installation failed on ${rig.name}: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

async function miningAction(id, action, button) {
    const rig = rigs.find(r => r.id === id);
    if (action === "start" && !window.confirm(
        `Start Monero mining on ${rig.name}?\n\nCPU limit: ${rig.cpu_limit_percent}%`
    )) return;
    if (action === "stop" && !window.confirm(`Stop the XMRig worker on ${rig.name}?`)) return;
    const password = getSSHPassword(rig);
    if (rig.ssh_auth_method === "password" && password === null) return;

    button.disabled = true;
    try {
        const payload = { action };
        if (password !== null) payload.password = password;
        const result = await api(`/api/rigs/${id}/action`, {
            method: "POST", body: JSON.stringify(payload)
        });
        log(`${rig.name}: ${action} → ${JSON.stringify(result)}`);
        await loadData();
    } catch (error) {
        log(`${action} failed for ${rig.name}: ${error.message}`);
    } finally {
        button.disabled = false;
    }
}

$("wallet-form").onsubmit = async event => {
    event.preventDefault();
    try {
        const wallet = $("wallet-address").value.trim();
        await api("/api/mining/settings", {
            method: "PUT", body: JSON.stringify({ wallet_address: wallet })
        });
        log("Global Monero wallet saved. It will be used by every rig on its next deployment.");
    } catch (error) {
        log(`Unable to save global wallet: ${error.message}`);
    }
};

function editPool(id) {
    const pool = pools.find(p => p.id === id);
    if (!pool) return;

    const form = $("pool-form");

    $("pool-form-title").textContent = `Edit pool: ${pool.name}`;
    $("pool-submit").textContent = "Save changes";

    form.elements.name.value = pool.name;
    form.elements.url.value = pool.url;
    form.elements.pool_type.value = pool.pool_type;
    form.elements.is_default.checked = pool.is_default;

    form.dataset.editingId = id;
    form.classList.remove("hidden");
    form.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function deletePool(id) {
    const pool = pools.find(p => p.id === id);
    if (!pool || !window.confirm(`Delete pool "${pool.name}"?`)) return;

    try {
        await api(`/api/pools/${id}`, { method: "DELETE" });
        log(`Pool deleted: ${pool.name}`);
        await loadData();
    } catch (error) {
        log(`Unable to delete pool: ${error.message}`);
        window.alert(error.message);
    }
}

$("show-rig-form").onclick = () => {
    const form = $("rig-form");
    if (form.dataset.editingId) {
        form.reset();
        delete form.dataset.editingId;
        $("rig-form-title").textContent = "Register Debian server";
        $("rig-submit").textContent = "Save server";
    }
    form.classList.toggle("hidden");
};
$("show-pool-form").onclick = () => $("pool-form").classList.toggle("hidden");
$("cancel-rig").onclick = () => {
    const form = $("rig-form");
    form.reset();
    delete form.dataset.editingId;
    $("rig-form-title").textContent = "Register Debian server";
    $("rig-submit").textContent = "Save server";
    form.classList.add("hidden");
};
$("cancel-pool").onclick = () => $("pool-form").classList.add("hidden");
$("refresh").onclick = async () => { await Promise.all([loadData(), loadWallet()]); };

$("rig-form").onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    const data = Object.fromEntries(form.entries());
    data.ssh_port = Number(data.ssh_port);
    data.cpu_limit_percent = Number(data.cpu_limit_percent);
    data.cpu_threads = data.cpu_threads ? Number(data.cpu_threads) : null;
    data.pool_id = data.pool_id ? Number(data.pool_id) : null;
    const editingId = event.target.dataset.editingId;
    const endpoint = editingId ? `/api/rigs/${editingId}` : "/api/rigs";
    const method = editingId ? "PUT" : "POST";

    try {
        await api(endpoint, { method, body: JSON.stringify(data) });
        event.target.reset();
        delete event.target.dataset.editingId;
        $("rig-form-title").textContent = "Register Debian server";
        $("rig-submit").textContent = "Save server";
        $("rig-form").classList.add("hidden");
        log(editingId ? `Server updated: ${data.name}` : `Server registered: ${data.name}; Worker ID initialized from rig name.`);
        await loadData();
    } catch (error) {
        log(`Unable to save server: ${error.message}`);
    }
};

$("pool-form").onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    const data = Object.fromEntries(form.entries());
    data.enabled = true;
    data.is_default = form.has("is_default");
    const editingId = event.target.dataset.editingId;
    const endpoint = editingId ? `/api/pools/${editingId}` : "/api/pools";
    const method = editingId ? "PUT" : "POST";

    try {
        await api(endpoint, { method, body: JSON.stringify(data) });
        event.target.reset();
        delete event.target.dataset.editingId;
        $("pool-form-title").textContent = "Register mining pool";
        $("pool-submit").textContent = "Save pool";
        $("pool-form").classList.add("hidden");
        log(editingId ? `Pool updated: ${data.name}` : `Pool registered: ${data.name}`);
        await loadData();
    } catch (error) {
        log(`Unable to save pool: ${error.message}`);
    }
};

Promise.all([loadData(), loadWallet()]).catch(error =>
    log(`Initialization failed: ${error.message}`));
