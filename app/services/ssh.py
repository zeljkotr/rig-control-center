import base64
import json
import shlex
import paramiko


def _connect(host: str, port: int, username: str, password: str | None = None):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.load_host_keys("/home/zeljko/.ssh/known_hosts")
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        key_filename="/home/zeljko/.ssh/rig_truenas_ed25519",
        timeout=10,
        banner_timeout=10,
        auth_timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def _run(client, command: str, timeout: int = 60) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(error.strip() or output.strip() or f"Remote command failed ({code})")
    return output.strip()


def probe_host(host: str, port: int, username: str, password: str | None = None) -> dict:
    client = _connect(host, port, username, password)
    try:
        command = (
            "printf 'HOSTNAME='; hostname; "
            "printf 'CPU_THREADS='; nproc; "
            "printf 'CPU_MODEL='; "
            "lscpu | awk -F: '/Model name/ {gsub(/^[ \\t]+/, \"\", $2); print $2; exit}'; "
            "printf 'MEMORY_KB='; awk '/MemTotal/ {print $2}' /proc/meminfo; "
            "printf 'OS='; . /etc/os-release 2>/dev/null; printf '%s\\n' \"$PRETTY_NAME\"; "
            "printf 'UPTIME='; cut -d. -f1 /proc/uptime; "
            "printf 'XMRIG='; pgrep -a xmrig || true"
        )
        output = _run(client, command, 20)
        result = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                result[key] = value.strip()
        return {
            "connected": True,
            "hostname": result.get("HOSTNAME"),
            "cpu_threads": int(result["CPU_THREADS"]) if result.get("CPU_THREADS", "").isdigit() else None,
            "cpu_model": result.get("CPU_MODEL"),
            "memory_kb": int(result["MEMORY_KB"]) if result.get("MEMORY_KB", "").isdigit() else None,
            "operating_system": result.get("OS"),
            "uptime_seconds": int(result["UPTIME"]) if result.get("UPTIME", "").isdigit() else None,
            "xmrig_process": result.get("XMRIG") or None,
        }
    finally:
        client.close()


def collect_metrics(host: str, port: int, username: str) -> dict:
    """Collect live rig metrics using SSH key authentication."""
    client = _connect(host, port, username)
    try:
        command = r'''
set -- $(awk '/^cpu / {idle=$5+$6; total=$2+$3+$4+$5+$6+$7+$8+$9; print idle, total}' /proc/stat)
idle1=$1; total1=$2
sleep 1
set -- $(awk '/^cpu / {idle=$5+$6; total=$2+$3+$4+$5+$6+$7+$8+$9; print idle, total}' /proc/stat)
idle2=$1; total2=$2
awk -v i1="$idle1" -v t1="$total1" -v i2="$idle2" -v t2="$total2" 'BEGIN {d=t2-t1; if (d>0) printf "CPU_PERCENT=%.1f\n", 100*(1-(i2-i1)/d); else print "CPU_PERCENT=0"}'
awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {if(t>0) printf "RAM_PERCENT=%.1f\nRAM_TOTAL_MB=%.0f\n", 100*(t-a)/t, t/1024}' /proc/meminfo
printf 'UPTIME_SECONDS='; cut -d. -f1 /proc/uptime
printf 'TEMPERATURE_C='
found=0
for f in /sys/class/thermal/thermal_zone*/temp; do
    if test -r "$f"; then
        awk '{printf "%.1f\n", $1/1000}' "$f"
        found=1
        break
    fi
done
test "$found" -eq 1 || echo unknown
if pgrep -x xmrig >/dev/null 2>&1; then
    echo 'XMRIG_STATUS=running'
else
    echo 'XMRIG_STATUS=stopped'
fi
curl -fsS --max-time 3 http://127.0.0.1:18088/1/summary 2>/dev/null |
python3 -c 'import json,sys
d=json.load(sys.stdin)
h=d.get("hashrate",{}).get("total",[])
r=d.get("results",{})
c=d.get("connection",{})
good=int(r.get("shares_good",0) or 0)
total=int(r.get("shares_total",0) or 0)
print("HASH_10S="+str(h[0] if len(h)>0 else ""))
print("HASH_1M="+str(h[1] if len(h)>1 else ""))
print("HASH_15M="+str(h[2] if len(h)>2 else ""))
print("SHARES_ACCEPTED="+str(good))
print("SHARES_REJECTED="+str(max(0,total-good)))
print("POOL_NAME="+str(c.get("pool","")))
print("POOL_CONNECTED="+str(bool(c.get("pool")) and not bool(c.get("error"))).lower())' 2>/dev/null || true
'''
        output = _run(client, command, 15)
        values = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip()

        def number(key, cast=float):
            try:
                return cast(values[key])
            except (KeyError, TypeError, ValueError):
                return None

        return {
            "online": True,
            "cpu_percent": number("CPU_PERCENT"),
            "ram_percent": number("RAM_PERCENT"),
            "ram_total_mb": number("RAM_TOTAL_MB", int),
            "temperature_c": number("TEMPERATURE_C"),
            "uptime_seconds": number("UPTIME_SECONDS", int),
            "xmrig_status": values.get("XMRIG_STATUS", "unknown"),
            "hash_rate": values.get("HASH_10S") or None,
            "hash_rate_10s": number("HASH_10S"),
            "hash_rate_1m": number("HASH_1M"),
            "hash_rate_15m": number("HASH_15M"),
            "shares_accepted": number("SHARES_ACCEPTED", int),
            "shares_rejected": number("SHARES_REJECTED", int),
            "pool_name": values.get("POOL_NAME") or None,
            "pool_connected": values.get("POOL_CONNECTED") == "true",
        }
    finally:
        client.close()


def deploy_xmrig(
    host: str,
    port: int,
    username: str,
    wallet: str,
    worker_id: str,
    pool_url: str,
    cpu_limit: int,
    password: str | None = None,
) -> dict:
    client = _connect(host, port, username, password)
    try:
        installer = r'''
import json, os, platform, pathlib, tarfile, urllib.request
root = pathlib.Path.home() / ".local" / "opt" / "xmrig"
root.mkdir(parents=True, exist_ok=True)
arch = platform.machine().lower()
asset_suffix = {"x86_64": "linux-static-x64", "amd64": "linux-static-x64",
                "aarch64": "linux-static-arm64", "arm64": "linux-static-arm64"}.get(arch)
if not asset_suffix:
    raise SystemExit("Unsupported CPU architecture: " + arch)
request = urllib.request.Request(
    "https://api.github.com/repos/xmrig/xmrig/releases/latest",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "RIG-Control-Center"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)
assets = [a for a in release.get("assets", [])
          if a["name"].endswith(asset_suffix + ".tar.gz")]
if not assets:
    raise SystemExit("No official XMRig release asset for " + asset_suffix)
asset = assets[0]
req = urllib.request.Request(asset["browser_download_url"],
    headers={"User-Agent": "RIG-Control-Center"})
archive = root / "xmrig-release.tar.gz"
with urllib.request.urlopen(req, timeout=120) as response, archive.open("wb") as out:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        out.write(chunk)
with tarfile.open(archive, "r:gz") as bundle:
    members = [m for m in bundle.getmembers()
               if pathlib.PurePosixPath(m.name).name == "xmrig"
               and m.isfile() and not m.issym() and not m.islnk()]
    if not members:
        raise SystemExit("xmrig executable not found in release archive")
    member = members[0]
    source = bundle.extractfile(member)
    binary = root / "xmrig"
    with source, binary.open("wb") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
binary.chmod(0o750)
archive.unlink(missing_ok=True)
print(json.dumps({"installed": True, "version": release.get("tag_name"),
                  "binary": str(binary)}))
'''
        encoded = base64.b64encode(installer.encode()).decode()
        install_command = (
            "python3 -c " + shlex.quote(
                "exec(__import__('base64').b64decode(" + repr(encoded) + "))"
            )
        )
        install_result = _run(client, install_command, 180)

        config = {
            "autosave": True,
            "background": False,
            "colors": False,
            "cpu": {
                "enabled": True,
                "huge-pages": False,
                "max-threads-hint": cpu_limit,
            },
            "pools": [{
                "url": pool_url,
                "user": wallet,
                "pass": worker_id,
                "keepalive": True,
                "tls": pool_url.startswith("stratum+ssl://"),
            }],
            "print-time": 60,
            "http": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 18088,
                "access-token": None,
                "restricted": True,
            },
            "api": {"id": None, "worker-id": worker_id},
        }
        config_data = base64.b64encode(json.dumps(config).encode()).decode()
        remote_config = (
            "mkdir -p ~/.config/xmrig && "
            "printf %s " + shlex.quote(config_data) +
            " | base64 -d > ~/.config/xmrig/config.json && "
            "chmod 600 ~/.config/xmrig/config.json"
        )
        _run(client, remote_config, 20)
        return {
            "installed": True,
            "started": False,
            "worker_id": worker_id,
            "cpu_limit_percent": cpu_limit,
            "pool": pool_url,
            "installation": json.loads(install_result),
        }
    finally:
        client.close()


def control_xmrig(
    host: str,
    port: int,
    username: str,
    action: str,
    password: str | None = None,
) -> dict:
    client = _connect(host, port, username, password)
    try:
        root = "$HOME/.local/opt/xmrig/xmrig"
        pidfile = "$HOME/.local/opt/xmrig/xmrig.pid"
        log = "$HOME/.local/opt/xmrig/xmrig.log"

        if action == "status":
            command = (
                f"if test -s {pidfile} && kill -0 \"$(cat {pidfile})\" 2>/dev/null; "
                "then echo running; else echo stopped; fi"
            )
            return {"status": _run(client, command, 10)}

        if action == "start":
            command = (
                f"test -x {root} || {{ echo 'XMRig is not installed' >&2; exit 1; }}; "
                f"test -f $HOME/.config/xmrig/config.json || "
                "{ echo 'XMRig configuration is missing' >&2; exit 1; }; "
                f"if test -s {pidfile} && kill -0 \"$(cat {pidfile})\" 2>/dev/null; "
                "then echo 'already running'; "
                "else "
                f"nohup {root} --config=$HOME/.config/xmrig/config.json "
                f">> {log} 2>&1 < /dev/null & "
                f"echo $! > {pidfile}; sleep 2; "
                f"kill -0 \"$(cat {pidfile})\" 2>/dev/null "
                "|| { echo 'XMRig failed to start; inspect its log' >&2; exit 1; }; "
                "echo started; fi"
            )
            return {"status": _run(client, command, 15)}

        if action == "stop":
            command = (
                f"if test -s {pidfile}; then "
                f"pid=$(cat {pidfile}); "
                "if kill -0 \"$pid\" 2>/dev/null && "
                "tr '\\0' ' ' < \"/proc/$pid/cmdline\" | grep -Fq \"$HOME/.local/opt/xmrig/xmrig\"; "
                "then kill -TERM \"$pid\"; "
                "for i in 1 2 3 4 5 6 7 8 9 10; do "
                "kill -0 \"$pid\" 2>/dev/null || break; sleep 1; done; "
                "kill -0 \"$pid\" 2>/dev/null && { echo 'XMRig did not stop' >&2; exit 1; }; "
                "fi; rm -f " + pidfile + "; echo stopped; "
                "else echo already-stopped; fi"
            )
            return {"status": _run(client, command, 20)}

        if action == "restart":
            self_stop = control_xmrig(host, port, username, "stop", password)
            self_start = control_xmrig(host, port, username, "start", password)
            return {"stop": self_stop, "start": self_start}

        raise ValueError("Unsupported XMRig action")
    finally:
        client.close()
