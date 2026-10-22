"""Owned PulseAudio/PipeWire streams and a local Overte voice-test controller."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import stat
from pathlib import Path
import secrets
import shutil
import signal as unix_signal
import subprocess
import threading
import time
import wave
import uuid

try:
    from .voice_signal import DURATION, RATE, analyze, sequence, write_wav
except ImportError:  # Direct CLI execution.
    from voice_signal import DURATION, RATE, analyze, sequence, write_wav


class InfrastructureError(RuntimeError):
    pass


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def command(args: list[str]) -> str:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=10, check=False)
    if result.returncode:
        # External stderr can include private device names and client log data.
        raise InfrastructureError(f"{Path(args[0]).name} failed (exit {result.returncode})")
    return result.stdout.strip()


def pulse_list(kind: str) -> list[dict]:
    return json.loads(command(["pactl", "--format=json", "list", kind]))


def pulse_modules() -> list[dict]:
    # PipeWire's JSON module inventory omits index on some pactl versions.
    # The supported short listing includes the numeric ownership handle.
    result = []
    for line in command(["pactl", "list", "short", "modules"]).splitlines():
        parts = line.split("\t")
        # PipeWire also lists built-in components with an empty handle. They
        # are not dynamically loaded modules and must never be unloaded here.
        if len(parts) >= 3 and parts[0].isdigit():
            result.append({"index": int(parts[0]), "name": parts[1], "argument": parts[2]})
    return result


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, unix_signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, unix_signal.SIGKILL)
        process.wait(timeout=3)
    except ProcessLookupError:
        process.wait(timeout=3)


class AudioRoutes:
    def __init__(self, session: str):
        self.names = {side: f"overte_voice_{session}_{side}" for side in ("tx", "rx")}
        self.modules: list[tuple[int, str]] = []

    def open(self) -> None:
        for name in self.names.values():
            index = int(command([
                "pactl", "load-module", "module-null-sink", f"sink_name={name}",
                "rate=24000", "channels=2", "channel_map=front-left,front-right",
                f"sink_properties=device.description={name}",
            ]))
            self.modules.append((index, name))
        self.ids = {side: next(item["index"] for item in pulse_list("sinks")
                               if item["name"] == name)
                    for side, name in self.names.items()}
        self.sources = {side: next(item["index"] for item in pulse_list("sources")
                                   if item["name"] == name + ".monitor")
                        for side, name in self.names.items()}

    def close(self) -> None:
        for index, name in reversed(self.modules):
            # Do not unload a reused module ID belonging to another process.
            modules = pulse_modules()
            if any(item["index"] == index and item["name"] == "module-null-sink"
                   and f"sink_name={name}" in item.get("argument", "").split()
                   for item in modules):
                command(["pactl", "unload-module", str(index)])
        self.modules.clear()

    def route_client(self, pid: int) -> dict:
        counts = {"input": 0, "output": 0}
        for kind, field, side, operation, count in (
            ("source-outputs", "source", "tx", "move-source-output", "input"),
            ("sink-inputs", "sink", "rx", "move-sink-input", "output"),
        ):
            wanted = self.sources[side] if field == "source" else self.ids[side]
            for stream in pulse_list(kind):
                if str(stream.get("properties", {}).get("application.process.id")) != str(pid):
                    continue
                if stream[field] != wanted:
                    command(["pactl", operation, str(stream["index"]),
                             self.names[side] + (".monitor" if field == "source" else "")])
                counts[count] += 1
        return counts

    def verify_client(self, pid: int) -> None:
        for kind, field, destination in (
            ("source-outputs", "source", self.sources["tx"]),
            ("sink-inputs", "sink", self.ids["rx"]),
        ):
            streams = [item for item in pulse_list(kind)
                       if str(item.get("properties", {}).get("application.process.id")) == str(pid)]
            if not streams or any(item[field] != destination for item in streams):
                raise InfrastructureError("Overte audio streams are missing or incorrectly routed")

    def play(self, path: Path) -> subprocess.Popen:
        return subprocess.Popen(["paplay", "--latency-msec=30", "--device=" + self.names["tx"], str(path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)

    @contextmanager
    def capture(self, root: Path):
        raw = root / "capture.raw"
        path = root / "capture.wav"
        with raw.open("wb") as output:
            recorder = subprocess.Popen([
                "parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=2",
                "--latency-msec=30",
                "--device=" + self.names["rx"] + ".monitor",
            ], stdout=output, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                time.sleep(0.35)
                streams = [item for item in pulse_list("source-outputs")
                           if str(item.get("properties", {}).get("application.process.id")) == str(recorder.pid)]
                if recorder.poll() is not None or not streams or any(
                        item["source"] != self.sources["rx"] for item in streams):
                    raise InfrastructureError("private receive capture did not start")
                yield path
                if recorder.poll() is not None:
                    raise InfrastructureError("receive capture exited early")
            finally:
                stop(recorder)
        data = raw.read_bytes()
        if len(data) % 4:
            raise InfrastructureError("receive capture ended with a partial PCM frame")
        with wave.open(str(path), "wb") as output:
            output.setparams((2, 2, RATE, 0, "NONE", "not compressed"))
            output.writeframes(data)
        raw.unlink()


class Peer:
    def __init__(self, root: Path, client: Path, domain: str, client_env: dict[str, str]):
        self.root, self.client_path, self.domain = root, client, domain
        self.session = secrets.token_hex(8)
        self.token = secrets.token_hex(32)
        self.routes = AudioRoutes(self.session)
        self.client = None
        self.snapshot = None
        self.snapshot_received = 0.0
        self.receiving_challenge = None
        self.receiving_preview = None
        self.preview_instance = secrets.token_hex(16)
        self.preview_used, self.preview_retired = set(), set()
        self.command = None
        self.guard = threading.RLock()
        self.operation = threading.Lock()
        self.done = threading.Event()
        self.client_env = client_env
        self.route_error = None
        self.runner_digest = hashlib.sha256(b"".join(
            (Path(__file__).parent / name).read_bytes()
            for name in ("voice_peer.py", "runtime.py", "voice_signal.py", "peer.js"))).hexdigest()

    def start(self, url: str) -> None:
        self.routes.open()
        with self.client_path.open("rb") as binary:
            self.client_digest = hashlib.file_digest(binary, "sha256").hexdigest()
        script = self.root / "peer-runtime.js"
        config = {"url": url, "token": self.token, "session": self.session, "domain": self.domain}
        script.write_text("var VOICE_PEER_CONFIG = " + json.dumps(config) + ";\n"
                          + Path(__file__).with_name("peer.js").read_text(), encoding="utf-8")
        script.chmod(0o600)
        for name in ("config", "data", "cache", "client-results"):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        empty = self.root / "empty-defaults.js"
        empty.write_text("// Dedicated voice-test profile; no default user scripts.\n")
        env = dict(os.environ, **self.client_env)
        env.update({
            "PULSE_SOURCE": self.routes.names["tx"] + ".monitor",
            "PULSE_SINK": self.routes.names["rx"],
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
        })
        # Register mixer callbacks before entering the domain. Connecting via
        # --url directly can deliver the first audio packet before peer.js loads.
        startup = self.root / "voice-startup.json"
        startup.write_text(json.dumps({"DataVersion": 3, "Entities": [], "Version": 1}))
        startup.chmod(0o600)
        # An isolated profile and explicit Pulse stream ownership avoid changing
        # host defaults, existing Overte preferences, or another application's audio.
        args = [str(self.client_path), "--allowMultipleInstances", "--no-updater",
                "--no-launcher", "--no-login-suggestion", "--display", "Desktop",
                "--suppress-settings-reset", "--cache", str(self.root / "cache"),
                "--defaultScriptsOverride", str(empty),
                "--testScript", str(script), "--testResultsLocation", str(self.root / "client-results"),
                "--url", startup.as_uri()]
        log = (self.root / "client.log").open("wb")
        try:
            self.client = subprocess.Popen(args, env=env, stdout=log, stderr=log,
                                           cwd=self.client_path.parent, start_new_session=True)
        finally:
            log.close()
        threading.Thread(target=self.monitor, daemon=True).start()

    def monitor(self) -> None:
        while not self.done.wait(0.25):
            try:
                if self.client.poll() is not None:
                    self.route_error = "Overte client exited"
                    return
                self.routes.route_client(self.client.pid)
                self.route_error = None
            except Exception:
                self.route_error = "private audio routing failed"

    def close(self) -> None:
        self.done.set()
        # Active captures/playbacks observe cancellation in ready() and reap
        # their own children before the virtual devices disappear.
        if self.operation.acquire(timeout=10):
            self.operation.release()
        stop(self.client)
        self.routes.close()
        for name in ("session.json", "peer-runtime.js"):
            (self.root / name).unlink(missing_ok=True)

    def observe(self, value: dict) -> None:
        if (value.get("session") != self.session
                or type(value.get("sequence")) is not int
                or type(value.get("muted")) is not bool
                or type(value.get("mixerReady")) is not bool):
            raise ValueError("invalid client snapshot")
        with self.guard:
            if self.snapshot and value["sequence"] <= self.snapshot["sequence"]:
                raise ValueError("stale client snapshot")
            self.snapshot, self.snapshot_received = value, time.monotonic()

    def status(self) -> dict:
        with self.guard:
            snapshot = dict(self.snapshot) if self.snapshot else None
            age = time.monotonic() - self.snapshot_received if snapshot else None
        running = self.client is not None and self.client.poll() is None
        routed = False
        if running:
            try:
                self.routes.verify_client(self.client.pid)
                routed = True
            except InfrastructureError:
                pass
        if snapshot:
            snapshot.pop("session", None)
            snapshot.pop("domainId", None)
        return {"schemaVersion": 1, "clientRunning": running, "audioRouted": routed,
                "snapshotFresh": age is not None and age < 3,
                "snapshotAgeSeconds": None if age is None else round(age, 3),
                "clientSha256": getattr(self, "client_digest", None), "client": snapshot,
                "receivingChallenge": self.receiving_challenge,
                "receivingPreview": self.receiving_preview,
                "previewProviderVersion": 1,
                "recordedPreviewEnabled": os.environ.get('OVERTE_E2E_RECORDED_PREVIEW_TESTS') == '1',
                "previewRunnerSha256": self.runner_digest,
                "proof": "PC partner readiness; no device acceptance claim"}

    def ready(self, mixer: bool = True) -> dict:
        if self.done.is_set():
            raise InfrastructureError("PC voice peer is stopping")
        status = self.status()
        if not status["clientRunning"] or not status["snapshotFresh"] or not status["audioRouted"]:
            raise InfrastructureError("PC client, fresh probe, and private audio routes are required")
        if mixer and (not status["client"].get("mixerReady") or not status["client"].get("connected")):
            raise InfrastructureError("PC client is not connected to an audio mixer")
        return status

    def configure(self, *, muted: bool, local_echo: bool = False, server_echo: bool = False,
                  position: dict | None = None) -> dict:
        value = {"id": secrets.token_hex(8), "muted": muted,
                 "localEcho": local_echo, "serverEcho": server_echo}
        if position is not None:
            if (set(position) != {"x", "y", "z"} or not all(
                    type(v) in (float, int) and math.isfinite(v) and abs(v) <= 100000
                    for v in position.values())):
                raise ValueError("position requires finite x/y/z coordinates within 100 km")
            value["position"] = position
        with self.guard:
            self.command = value
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = self.ready(mixer=False)
            current = status["client"]
            if (current.get("commandId") == value["id"] and not current.get("commandError")
                    and current.get("muted") == muted
                    and current.get("localEcho") == local_echo
                    and current.get("serverEcho") == server_echo):
                return status
            time.sleep(0.05)
        raise InfrastructureError("Overte did not apply the requested audio state")

    @contextmanager
    def artifacts(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="capture-", dir=self.root) as temporary:
            yield Path(temporary)

    def play_wait(self, path: Path, mixer: bool) -> float:
        player = self.routes.play(path)
        peak = 0.0
        deadline = time.monotonic() + DURATION + 5
        try:
            while player.poll() is None:
                status = self.ready(mixer)
                peak = max(peak, float(status["client"].get("inputPeak", 0)))
                if time.monotonic() > deadline:
                    raise InfrastructureError("challenge playback timed out")
                time.sleep(0.1)
            if player.returncode != 0:
                raise InfrastructureError("challenge playback failed")
            self.ready(mixer)
            return peak
        finally:
            stop(player)

    def run(self, request: dict) -> dict:
        action = request.get("action")
        if action in ('receive-preview','preview-files','preview-release'):
            return self.preview(request)
        if action == "status":
            return self.status()
        if action == "domain-check":
            self.ready()
            expected = uuid.UUID(request.get("domainId", "").strip("{}"))
            with self.guard:
                observed = self.snapshot.get("domainId", "")
            try:
                same = expected.int != 0 and uuid.UUID(observed.strip("{}")) == expected
            except (ValueError, AttributeError):
                same = False
            return {"schemaVersion": 1, "sameDomain": same}
        if action == "stop":
            self.done.set()
            return {"stopping": True}
        if not self.operation.acquire(blocking=False):
            raise InfrastructureError("another PC audio operation is active")
        try:
            started_at = datetime.now(timezone.utc).isoformat()
            local = action == "check-local"
            self.ready(mixer=not local)
            if action == "position":
                return self.configure(muted=True, position=request.get("position"))
            if action not in ("send", "send-muted", "receive", "check-local", "check-server"):
                raise ValueError("unknown PC operation")
            challenge = request.get("challenge") or secrets.token_hex(16)
            symbols = sequence(challenge)
            if action == "receive":
                seconds = request.get("seconds", 8)
                if type(seconds) not in (int, float) or not DURATION + 0.5 <= seconds <= 30:
                    raise ValueError("receive duration must be between 5.34 and 30 seconds")
                expect = request.get("expect", "present")
                if expect not in ("present", "absent") or not request.get("challenge"):
                    raise ValueError("receive requires an explicit challenge and present/absent expectation")
                self.configure(muted=True)
                audio_stats = []
                previous_sequence = None
                with self.artifacts() as root:
                    with self.routes.capture(root) as wav:
                        with self.guard:
                            self.receiving_challenge = challenge
                        deadline = time.monotonic() + seconds
                        while time.monotonic() < deadline:
                            observed = self.ready().get("client") or {}
                            sequence_number = observed.get("sequence")
                            stats = observed.get("audioStats")
                            if (sequence_number != previous_sequence and isinstance(stats, dict)
                                    and len(audio_stats) < 128):
                                audio_stats.append({"peerSequence": sequence_number, **stats})
                                previous_sequence = sequence_number
                            time.sleep(0.1)
                    result = analyze(wav, challenge, expect)
                    result["pcAudioStats"] = audio_stats
                    # Retain the exact owned loopback PCM until the device
                    # module copies it; the next receive replaces this pair.
                    content = wav.read_bytes()
                    retained = self.root / "receive-capture.wav"
                    retained.write_bytes(content)
                    retained.chmod(0o600)
                    write_json(self.root / "receive-capture.json", {
                        "challenge": challenge, "sha256": hashlib.sha256(content).hexdigest()})
            else:
                with self.artifacts() as root:
                    wav = root / "challenge.wav"
                    write_wav(wav, challenge)
                    self.configure(muted=action == "send-muted", local_echo=local,
                                   server_echo=action == "check-server")
                    if action in ("send", "send-muted"):
                        peak = self.play_wait(wav, True)
                        if action == "send" and peak <= 0.001:
                            raise InfrastructureError("challenge did not reach the PC microphone probe")
                        result = {"challenge": challenge, "symbols": symbols, "sent": True,
                                  "inputPeak": peak, "muted": action == "send-muted", "durationSeconds": DURATION,
                                  "proof": "PC microphone-path send only; remote reception must be measured"}
                    else:
                        with self.routes.capture(root) as captured:
                            peak = self.play_wait(wav, not local)
                            time.sleep(1.5)
                        result = analyze(captured, challenge)
                        result["inputPeak"] = peak
                        result["proof"] = ("PC microphone and local output loopback" if local
                                           else "PC microphone -> domain audio mixer -> PC output")
                        if not local and result["passed"]:
                            self.configure(muted=True, server_echo=True)
                            with self.routes.capture(root) as captured:
                                self.play_wait(wav, True)
                                time.sleep(1.5)
                            negative = analyze(captured, challenge, "absent")
                            result["mutedControl"] = negative
                            result["passed"] = result["passed"] and negative["passed"]
            result.update({"schemaVersion": 1, "clientSha256": self.client_digest,
                           "runnerSha256": self.runner_digest,
                           "startedAtUTC": started_at, "finishedAtUTC": datetime.now(timezone.utc).isoformat(),
                           "build": self.ready(not local)["client"].get("build"),
                           "physicalDevicesTested": False})
            write_json(self.root / "last-result.json", result)
            return result
        finally:
            with self.guard:
                self.receiving_challenge = None
            try:
                if self.client and self.client.poll() is None and self.snapshot:
                    self.configure(muted=True)
            finally:
                self.operation.release()

    def preview(self,request):
        """Original PC output acquisition, never a target fact or detector verdict.

        The existing logical voice path/isolated Pulse monitor is reused. This
        does not claim an acoustic speaker or physical microphone measurement.
        """
        if os.environ.get('OVERTE_E2E_RECORDED_PREVIEW_TESTS')!='1':raise ValueError('Recorded preview PC fixture is disabled')
        action=request.get('action');capture=request.get('capture_id');request_id=request.get('request_id')
        if type(capture) is not str or not re.fullmatch('[0-9a-f]{32}',capture):raise ValueError('Original preview capture identity is required')
        path=self.root/('preview-'+capture+'.wav');journal=self.root/('preview-'+capture+'.json')
        exists=lambda source:source.exists() or source.is_symlink()
        def read_private(source,limit):
            before=source.lstat()
            with os.fdopen(os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
                info=os.fstat(stream.fileno())
                if (before.st_dev,before.st_ino)!=(info.st_dev,info.st_ino) or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>limit:
                    raise InfrastructureError('Original private PC preview file changed')
                raw=stream.read(limit+1);after=os.fstat(stream.fileno());current=source.lstat()
                if len(raw)>limit or (info.st_dev,info.st_ino,info.st_size)!=(after.st_dev,after.st_ino,after.st_size) or (info.st_dev,info.st_ino,info.st_size)!=(current.st_dev,current.st_ino,current.st_size) or not stat.S_ISREG(current.st_mode) or current.st_nlink!=1 or stat.S_IMODE(current.st_mode)!=0o600:
                    raise InfrastructureError('Original private PC preview file changed')
            return raw
        def original():
            if not exists(path) and not exists(journal):return None
            for source in (path,journal):
                info=source.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>32*1024*1024:
                    raise InfrastructureError('Original private PC preview file ownership changed')
            def pairs(rows):
                value={}
                for key,item in rows:
                    if key in value:raise InfrastructureError('Duplicate original PC preview metadata')
                    value[key]=item
                return value
            value=json.loads(read_private(journal,65536),object_pairs_hook=pairs);content=read_private(path,32*1024*1024);info=path.lstat()
            if value.get('captureId')!=capture or value.get('sha256')!=hashlib.sha256(content).hexdigest() or value.get('bytes')!=len(content) or value.get('device')!=info.st_dev or value.get('inode')!=info.st_ino:
                raise InfrastructureError('Original PC preview PCM changed')
            return value
        if action!='receive-preview':
            if set(request)!={'action','capture_id','request_id'} or type(request_id) is not str or not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('Closed original preview file request required')
            if self.receiving_preview==capture:raise InfrastructureError('Original PC preview capture is still running')
            value=original()
            if action=='preview-release' and capture not in self.preview_used and capture not in self.preview_retired:
                raise ValueError('Cannot release an unowned PC preview capture')
            if action=='preview-release' and value is not None:
                path.unlink();journal.unlink()
            if action=='preview-release':
                self.preview_retired.add(capture)
            # A new query is required to prove absence after release.
            return dict(schemaVersion=1,requestId=request_id,instance=self.preview_instance,captureId=capture,capturedEpochMs=int(time.time()*1000),
                exists=exists(path) or exists(journal),retired=capture in self.preview_retired,
                original=value if action=='preview-files' else None)
        if set(request)!={'action','challenge','capture_id','seconds'}:raise ValueError('Closed original preview capture request required')
        challenge=request['challenge'];sequence(challenge,profile='recorded-preview-v1')
        seconds=request['seconds']
        if type(seconds) not in (int,float) or not 3<=seconds<=10 or exists(path) or exists(journal) or len(list(self.root.glob('preview-*.wav')))>=32 or capture in self.preview_used or capture in self.preview_retired or len(self.preview_used)>=128:
            raise ValueError('Original bounded PC preview capture is unavailable')
        if not self.operation.acquire(blocking=False):raise InfrastructureError('Another PC audio operation is active')
        try:
            self.preview_used.add(capture)
            before=self.ready();self.configure(muted=True)
            with self.artifacts() as temporary:
                with self.routes.capture(temporary) as wav:
                    started=int(time.time()*1000)
                    with self.guard:self.receiving_challenge=challenge;self.receiving_preview=capture
                    deadline=time.monotonic()+seconds;stats=[];previous=None
                    while time.monotonic()<deadline:
                        current=self.ready();client=current.get('client') or {}
                        if client.get('sequence')!=previous and len(stats)<128:
                            stats.append(dict(capturedEpochMs=int(time.time()*1000),peerSequence=client.get('sequence'),audioStats=client.get('audioStats')))
                            previous=client.get('sequence')
                        time.sleep(.1)
                content=wav.read_bytes();completed=int(time.time()*1000)
                if not content or len(content)>32*1024*1024:raise InfrastructureError('Original PC preview PCM is unavailable')
                with wave.open(str(wav),'rb') as source:
                    rate,channels,width,frames=source.getframerate(),source.getnchannels(),source.getsampwidth(),source.getnframes()
                    if not 8000<=rate<=48000 or channels not in (1,2) or width!=2 or not 3*rate<=frames<=11*rate:
                        raise InfrastructureError('Original PC preview format is unavailable')
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as output:
                    if output.write(content)!=len(content):raise InfrastructureError('Original PC preview write is incomplete')
                    output.flush();os.fsync(output.fileno());info=os.fstat(output.fileno())
                value=dict(schemaVersion=1,instance=self.preview_instance,captureId=capture,challenge=challenge,source='private-pc-playout-monitor',
                    startedEpochMs=started,completedEpochMs=completed,bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),
                    device=info.st_dev,inode=info.st_ino,sampleRate=rate,channels=channels,frames=frames,
                    clientSha256=self.client_digest,runnerSha256=self.runner_digest,pcAudioStats=stats,
                    physicalAudioHardwareTested=False)
                metadata=json.dumps(value,allow_nan=False).encode()
                if len(metadata)>65536:raise InfrastructureError('Original PC preview metadata exceeded its limit')
                descriptor=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as output:
                    if output.write(metadata)!=len(metadata):raise InfrastructureError('Original PC preview metadata write is incomplete')
                    output.flush();os.fsync(output.fileno())
                original();return dict(schemaVersion=1,captureId=capture,retained=True)
        finally:
            with self.guard:self.receiving_challenge=None;self.receiving_preview=None
            self.operation.release()


def make_handler(peer: Peer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status: int, value: dict):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def dispatch(self):
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + peer.token):
                self.reply(403, {"error": "local controller authentication required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 16384:
                    raise ValueError("request too large")
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise ValueError("request must be an object")
                if self.command == "POST" and self.path == "/snapshot":
                    peer.observe(body)
                    value = {"accepted": True}
                elif self.command == "GET" and self.path == "/command":
                    with peer.guard:
                        value = peer.command or {}
                elif self.command == "POST" and self.path == "/control":
                    value = peer.run(body)
                else:
                    self.reply(404, {"error": "unknown local endpoint"})
                    return
                self.reply(200, value)
            except (ValueError, TypeError, KeyError):
                self.reply(400, {"error": "invalid voice-peer request"})
            except InfrastructureError as error:
                self.reply(503, {"error": str(error)})
            except Exception:
                self.reply(503, {"error": "PC voice operation failed; inspect private local diagnostics"})

        do_GET = dispatch
        do_POST = dispatch

    return Handler


def serve(root: Path, client: Path, domain: str, client_env: dict[str, str]) -> None:
    import fcntl
    for executable in ("pactl", "paplay", "parec"):
        if not shutil.which(executable):
            raise InfrastructureError(f"required executable is missing: {executable}")
    if not client.is_file() or not os.access(client, os.X_OK):
        raise ValueError("client must be an executable file")
    if not domain.startswith("hifi://") or any(character.isspace() for character in domain):
        raise ValueError("domain must be a hifi:// address")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise ValueError("state directory must be owned by the current user")
    root.chmod(0o700)
    lock = (root / "owner.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise InfrastructureError("PC voice peer already owns this state directory")
    peer = Peer(root, client, domain, client_env)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(peer))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_address[1]}"
    def shutdown(_signal, _frame):
        peer.done.set()
    unix_signal.signal(unix_signal.SIGTERM, shutdown)
    unix_signal.signal(unix_signal.SIGINT, shutdown)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        peer.start(url)
        write_json(root / "session.json", {"url": url, "token": peer.token})
        print(json.dumps({"started": True, "control": "loopback", "clientSha256": peer.client_digest}), flush=True)
        while not peer.done.wait(0.25):
            if peer.client.poll() is not None:
                raise InfrastructureError("Overte client exited; inspect the private client log")
    finally:
        server.shutdown()
        server.server_close()
        try:
            peer.close()
        finally:
            lock.close()
