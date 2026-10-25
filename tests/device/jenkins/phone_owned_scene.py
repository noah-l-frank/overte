# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Task-owned lifecycle for the unchanged original controlled HTTP scene.

Import into the focused runner, under its existing reservation/child owner.
No DUT/SDK operation, browser input, trust change or adoption of an old runtime.
Failures retain this run's service until an explicit state-bound disposition.
"""
import hashlib
import ipaddress
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit

def static_exception(error, source_root, codes, diagnostic_files=()):
    # Full unredacted trace remains in the worker's private runtime log.
    # A closed class name is sufficient for this service's private receipt.
    return {'class': type(error).__name__}



def read_bytes(path):
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        data = stream.read()
    after = path.lstat()
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    assert signature(before) == signature(after)
    return data


def digest(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def write(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    assert json.loads(read_bytes(path)) == value


def _read_proc_file(directory, name, limit):
    with os.fdopen(os.open(name, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK, dir_fd=directory), 'rb') as stream:
        value = stream.read(limit+1)
    assert len(value) <= limit, 'OVT_SCENE_PROC_READ_BOUND'
    return value


def _proc_stat(directory, pid):
    raw = _read_proc_file(directory, 'stat', 65536).decode('utf-8')
    assert int(raw[:raw.index('(')].strip()) == pid, 'OVT_SCENE_PROC_PID'
    fields = raw[raw.rfind(')')+2:].split()
    assert len(fields) >= 20 and fields[19].isdigit(), 'OVT_SCENE_PROC_STAT'
    return {'birth':fields[19], 'ppid':int(fields[1]), 'pgid':int(fields[2]), 'state':fields[0]}


def _proc_observation(pid, expected=None, *, private=True):
    """Anchor one known PID directory and bookend all private metadata reads."""
    try:
        directory = os.open('/proc/'+str(pid), os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    except (FileNotFoundError, ProcessLookupError):
        return None
    try:
        before = os.fstat(directory); left = _proc_stat(directory,pid)
        namespaces = {name:os.readlink('ns/'+name,dir_fd=directory) for name in ('pid','mnt')}
        anchor = dict(pid=pid, birth=left['birth'], uid=before.st_uid, pgid=left['pgid'],
            ppid=left['ppid'], procDevice=before.st_dev, procInode=before.st_ino, namespaces=namespaces)
        if expected is not None:
            assert anchor == expected, 'OVT_SCENE_POPEN_ANCHOR_CHANGED'
        executable = None; command = None
        if private and left['state'] not in ('Z','X'):
            try:
                executable = os.readlink('exe',dir_fd=directory)
                command = _read_proc_file(directory,'cmdline',65536)
            except (FileNotFoundError, ProcessLookupError):
                # An own child may be crossing exec/exit. Recheck its complete
                # anchor before describing this as pending, never as ready.
                pass
        right = _proc_stat(directory,pid); after = os.fstat(directory)
        assert left['birth'] == right['birth'] and left['ppid'] == right['ppid'] and left['pgid'] == right['pgid'], 'OVT_SCENE_PROC_LIFETIME_CHANGED'
        assert (before.st_dev,before.st_ino,before.st_uid) == (after.st_dev,after.st_ino,after.st_uid), 'OVT_SCENE_PROC_DIRECTORY_CHANGED'
        assert namespaces == {name:os.readlink('ns/'+name,dir_fd=directory) for name in namespaces}, 'OVT_SCENE_PROC_NAMESPACE_CHANGED'
        if right['state'] in ('Z','X'):
            executable = command = None
        return {'anchor':anchor,'state':right['state'],'executable':executable,
            'argvSha256':hashlib.sha256(command).hexdigest() if command is not None else None,
            'argvBytes':len(command) if command is not None else None,
            'argvComplete':command is not None and bool(command) and command.endswith(b'\0'),
            'command':command}
    except (FileNotFoundError, ProcessLookupError):
        return None
    finally:
        os.close(directory)


def _identity(observed):
    if observed is None or observed['state'] in ('Z','X'):
        return None
    anchor=observed['anchor']
    return {key:anchor[key] for key in ('pid','birth','uid','pgid')} | {
        'executable':observed['executable'],'argvSha256':observed['argvSha256']}


def identity(pid):
    # Group-survivor and post-reap checks need no private executable/argv.
    observed = _proc_observation(pid, private=False)
    return None if observed is None or observed['state'] in ('Z','X') else observed['anchor']


def require_owner(expected, *, anchor=None):
    actual = _identity(_proc_observation(expected['pid'],anchor))
    assert actual is None or actual == expected, 'Scene process identity changed; no signal permitted'
    return actual


def group_survivors(pgid):
    members = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdecimal():
            try:
                pid = int(entry.name)
                if os.getpgid(pid) != pgid:
                    continue  # Never inspect unrelated processes' private executable/argv.
                value = identity(pid)
                if value:
                    assert value['pgid'] == pgid
                    members.append(value['pid'])
            except ProcessLookupError:
                pass
    return sorted(members)


def listener_host(config, allow_ephemeral_loopback=False):
    assert {'bind', 'port', 'publicHost'} <= set(config) <= {'bind', 'port', 'publicHost', 'readyFile'}, 'OVT_SCENE_CONFIG_FIELDS'
    assert type(config['port']) is int and (1 <= config['port'] <= 65535 or allow_ephemeral_loopback and config['port']==0 and config['bind']==config['publicHost']=='127.0.0.1'), 'OVT_SCENE_CONFIG_PORT'
    bind = ipaddress.IPv4Address(config['bind'])
    assert not bind.is_multicast and not bind.is_reserved, 'OVT_SCENE_BIND_ADDRESS'
    assert isinstance(config['publicHost'], str) and config['publicHost'], 'OVT_SCENE_PUBLIC_HOST'
    # Preserve the reviewed explicit interface. Loopback is suitable only when
    # the original listener binds all IPv4 interfaces. No public-origin rewrite.
    return '127.0.0.1' if bind.is_unspecified else str(bind)


def strict_json(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, 'OVT_SCENE_HTTP_DUPLICATE_KEY'
            result[key] = value
        return result
    def nonfinite(_value):
        raise ValueError('OVT_SCENE_HTTP_NONFINITE')
    return json.loads(payload, object_pairs_hook=pairs, parse_constant=nonfinite)


def expected_http_document(source, manifest, relative, public_origin):
    expected = strict_json(read_bytes(source / 'tests/device/fixture' / relative))
    if relative == manifest['scene']:
        scripted = manifest['scriptedInteraction']['script']
        for entity in expected['Entities']:
            if entity.get('script') == scripted:
                entity['script'] = public_origin + '/' + scripted
    else:
        assert relative == 'fixture-manifest.json', 'OVT_SCENE_HTTP_ROUTE'
    return expected


def read_listener_json(opener, host, port, relative, expected, artifact):
    try:
        response = opener.open(Request('http://' + host + ':' + str(port) + '/' + relative), timeout=1)
    except HTTPError as error:
        response = error
    with response:
        payload = response.read(1024*1024+1)
        metadata = {'status': response.status, 'contentType': response.headers.get('Content-Type'),
                    'declaredLength': response.headers.get('Content-Length'), 'actualBytes': len(payload),
                    'actualPayloadSha256': hashlib.sha256(payload).hexdigest(), 'route': relative,
                    'actualPayloadFile': artifact.name}
    # Preserve the actual response before semantic validation, including RED.
    with os.fdopen(os.open(artifact, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    assert read_bytes(artifact) == payload
    write(artifact.with_suffix('.metadata.json'), metadata)
    assert len(payload)<=1024*1024 and metadata['status']==200, 'OVT_SCENE_HTTP_STATUS_OR_SIZE'
    assert isinstance(metadata['contentType'],str) and metadata['contentType'].split(';',1)[0].strip().lower()=='application/json', 'OVT_SCENE_HTTP_CONTENT_TYPE'
    assert isinstance(metadata['declaredLength'],str) and metadata['declaredLength'].isdigit() and int(metadata['declaredLength'])==len(payload), 'OVT_SCENE_HTTP_LENGTH'
    actual = strict_json(payload)
    assert json.dumps(actual,sort_keys=True,separators=(',',':')) == json.dumps(expected,sort_keys=True,separators=(',',':')), 'OVT_SCENE_HTTP_SOURCE_RENDERED_SEMANTICS'
    return metadata


def read_fresh_ready(path, started_epoch_ns, config, allow_ephemeral_loopback=False):
    assert path.lstat().st_mtime_ns >= started_epoch_ns
    ready = json.loads(read_bytes(path))
    assert ready['schemaVersion'] == 1
    origin = urlsplit(ready['baseUrl'])
    assert origin.scheme=='http' and origin.hostname==config['publicHost'] and origin.port is not None and 1<=origin.port<=65535 and not origin.path and not origin.query and not origin.fragment and origin.username is None and origin.password is None
    if config['port']==0:
        assert allow_ephemeral_loopback and config['bind']==config['publicHost']=='127.0.0.1'
    else:
        assert origin.port==config['port']
    assert urlsplit(ready['sceneUrl'])._replace(path='', query='', fragment='').geturl() == ready['baseUrl']
    return ready


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Scene readiness cannot follow redirects')


class OwnedScene:
    def __init__(self, source_root, inventory, inventory_sha256, configuration,
                 configuration_sha256, runtime_root, *, allow_ephemeral_loopback=False):
        assert type(allow_ephemeral_loopback) is bool
        self.allow_ephemeral_loopback = allow_ephemeral_loopback
        self.source = Path(source_root)
        self.inventory_path = Path(inventory)
        self.inventory_sha256 = inventory_sha256
        self.configuration = Path(configuration)
        self.configuration_sha256 = configuration_sha256
        self.runtime = Path(runtime_root)
        self.process = None
        self.owner = None
        self.environment = None
        self.cleanup = None
        self.startup_anchor = None
        self.startup_events = []
        self.startup_deadline = None
        assert self.source.is_absolute() and self.source.resolve() == self.source
        assert self.runtime.is_absolute() and self.runtime.parent.resolve() == self.runtime.parent
        assert not self.runtime.exists() and not self.runtime.is_symlink()

    def pins(self):
        assert digest(self.inventory_path) == self.inventory_sha256
        assert digest(self.configuration) == self.configuration_sha256
        for name, expected in self.source_pins.items():
            assert digest(self.source / name) == expected

    @staticmethod
    def startup_now():
        return time.monotonic()

    def _pin_startup_anchor(self):
        observed = _proc_observation(self.process.pid, private=False)
        assert observed is not None and observed['state'] not in ('Z','X') and self.process.poll() is None, 'OVT_SCENE_CHILD_EXITED_BEFORE_ANCHOR'
        anchor = observed['anchor']
        expected_namespaces = {name:os.readlink('/proc/self/ns/'+name) for name in ('pid','mnt')}
        assert anchor['uid'] == os.geteuid() and anchor['pid'] == anchor['pgid'] == self.process.pid, 'OVT_SCENE_POPEN_PID_UID_PGID'
        assert anchor['ppid'] == os.getpid() and anchor['namespaces'] == expected_namespaces, 'OVT_SCENE_POPEN_PARENT_OR_NAMESPACE'
        self.startup_anchor = anchor
        write(self.runtime/'startup-anchor.actual.json', {'startupAnchorVersion':1,
            'scope':'OWN_POPEN_CLEANUP_ANCHOR_ONLY_NOT_EXEC_OR_READINESS','anchor':anchor,
            'startedEpochNs':self.started})

    def _startup_event(self, kind, observed=None):
        event = {'kind':kind}
        if observed is not None:
            event.update(executable=observed['executable'],argvSha256=observed['argvSha256'],
                argvBytes=observed['argvBytes'],argvComplete=observed['argvComplete'])
        if not self.startup_events or any(self.startup_events[-1].get(key) != value for key,value in event.items()):
            assert len(self.startup_events) < 64, 'OVT_SCENE_STARTUP_OBSERVATION_LIMIT'
            self.startup_events.append(dict(event,observedMonotonic=self.startup_now()))

    def _await_intended_exec(self, argv):
        expected_command = b'\0'.join(os.fsencode(value) for value in argv)+b'\0'
        expected_executable = str(Path(argv[0]).resolve(strict=True))
        outcome = 'ERROR'
        try:
            while self.startup_now() < self.startup_deadline:
                self.pins()
                observed = _proc_observation(self.process.pid,self.startup_anchor)
                if observed is None or observed['state'] in ('Z','X') or self.process.poll() is not None:
                    self._startup_event('OWN_CHILD_EXITED_BEFORE_EXEC')
                    raise AssertionError('OVT_SCENE_CHILD_EXITED_BEFORE_INTENDED_EXEC')
                match = observed['argvComplete'] and observed['command'] == expected_command and observed['executable'] == expected_executable
                self._startup_event('OWN_CHILD_EXEC_CONFIRMED' if match else 'OWN_CHILD_EXEC_PENDING',observed)
                if match:
                    # A second anchored actual read closes the adoption window.
                    # Expected argv/exe are comparisons, never returned facts.
                    final = _proc_observation(self.process.pid,self.startup_anchor)
                    assert final is not None and final['state'] not in ('Z','X') and self.process.poll() is None, 'OVT_SCENE_CHILD_EXITED_AT_EXEC_ADMISSION'
                    assert final['argvComplete'] and final['command']==observed['command'] and final['executable']==observed['executable'], 'OVT_SCENE_EXEC_CHANGED_DURING_ADMISSION'
                    assert self.startup_now() < self.startup_deadline, 'OVT_SCENE_INTENDED_EXEC_TIMEOUT'
                    outcome='ACTUAL_INTENDED_EXEC_ADMITTED'
                    return _identity(final)
                time.sleep(.01)
            self._startup_event('OWN_CHILD_EXEC_TIMEOUT')
            raise AssertionError('OVT_SCENE_INTENDED_EXEC_TIMEOUT')
        finally:
            write(self.runtime/'startup-exec.actual.json', {'startupExecVersion':1,'status':outcome,
                'scope':'ACTUAL_PROCESS_EXEC_IDENTITY_ONLY_NOT_HTTP_OR_SCENE_READINESS',
                'anchor':self.startup_anchor,'expectedArgvSha256':hashlib.sha256(expected_command).hexdigest(),
                'expectedExecutable':expected_executable,'startupBudgetSeconds':35,
                'startupDeadlineMonotonic':self.startup_deadline,'observations':self.startup_events})

    def __enter__(self):
        assert digest(self.inventory_path) == self.inventory_sha256
        inventory = json.loads(read_bytes(self.inventory_path))
        selected = ['tests/device/fixture/orchestrate.py', 'tests/device/probe/overte_e2e_probe.js']
        selected += [name for name in inventory if name.startswith('tests/device/fixture/')]
        assert 'tests/device/fixture/serve.py' in selected
        self.source_pins = {name: inventory[name] for name in sorted(set(selected))}
        self.pins()
        config = json.loads(read_bytes(self.configuration))
        readiness_host = listener_host(config, self.allow_ephemeral_loopback)
        spec = importlib.util.spec_from_file_location('original_scene_orchestrate', self.source / 'tests/device/fixture/orchestrate.py')
        self.original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.original)
        self.runtime.mkdir(mode=0o700)
        ready_path = self.runtime / 'scene-ready.actual.json'
        argv = [sys.executable, str(self.source / 'tests/device/fixture/serve.py'),
                '--bind', config['bind'], '--port', str(config['port']),
                '--public-host', config['publicHost'], '--ready-file', str(ready_path)]
        self.started = time.time_ns()
        self.startup_deadline = self.startup_now()+35
        try:
            with os.fdopen(os.open(self.runtime / 'server.private.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as log:
                self.process = subprocess.Popen(argv, cwd=self.source, env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            self._pin_startup_anchor()
            self.owner = self._await_intended_exec(argv)
            assert self.startup_now() < self.startup_deadline, 'OVT_SCENE_STARTUP_TIMEOUT'
            assert self.owner and self.owner['uid'] == os.geteuid() and self.owner['pgid'] == self.process.pid
            write(self.runtime / 'owner.actual.json', {'identity': self.owner, 'startedEpochNs': self.started, 'argv': argv, 'sourcePins': self.source_pins, 'configurationSha256': self.configuration_sha256})
            end = self.startup_deadline
            opener = build_opener(ProxyHandler({}), NoRedirect())
            ready = None
            attempt = 0
            http_evidence = []
            while self.startup_now() < end:
                assert require_owner(self.owner,anchor=self.startup_anchor) and self.process.poll() is None
                self.pins()
                if ready_path.exists():
                    ready = read_fresh_ready(ready_path, self.started, config, self.allow_ephemeral_loopback)
                    try:
                        # Independently read actual bytes from the new listener,
                        # not expected values returned as a client observation.
                        attempt += 1
                        evidence_dir = self.runtime / ('http-attempt-' + str(attempt))
                        evidence_dir.mkdir(mode=0o700)
                        manifest = strict_json(read_bytes(self.source / 'tests/device/fixture/fixture-manifest.json'))
                        http_evidence = []
                        for relative in ('fixture-manifest.json', manifest['scene']):
                            expected = expected_http_document(self.source, manifest, relative, ready['baseUrl'])
                            http_evidence.append(read_listener_json(opener, readiness_host, urlsplit(ready['baseUrl']).port, relative, expected, evidence_dir / (relative + '.actual.bin')))
                        break
                    except (URLError, TimeoutError):
                        ready = None
                time.sleep(.05)
            assert ready is not None, 'Original scene did not become independently ready'
            assert require_owner(self.owner,anchor=self.startup_anchor)
            self.pins()
            assert self.startup_now() < self.startup_deadline, 'OVT_SCENE_STARTUP_TIMEOUT'
            self.ready = ready
            self.environment = self.original.environment(ready, None)
            write(self.runtime / 'environment.actual.private.json', {'schemaVersion': 1, 'environment': self.environment})
            write(self.runtime / 'START_RESULT.actual.json', {'status': 'PASS', 'scope': 'Original scene infrastructure only; no client acceptance', 'identity': self.owner, 'startupAnchor':self.startup_anchor, 'startupExecSha256':digest(self.runtime/'startup-exec.actual.json'), 'readySha256': digest(ready_path), 'configurationSha256': self.configuration_sha256, 'sourceInventorySha256': self.inventory_sha256, 'readyQueryPresent': bool(urlsplit(ready['sceneUrl']).query), 'actualHttpEvidence': http_evidence})
            return self
        except BaseException as error:
            # Preserve the owned process and its complete logs on failure.
            # The worker enters DebugHold before any cleanup or next target.
            write(self.runtime / 'START_FAILURE.actual.json', {'status': 'ERROR', 'exception': static_exception(error, self.source, set(), diagnostic_files=(Path(__file__),)), 'cleanup': self.cleanup,
                'startup':{'anchor':self.startup_anchor,'ownerAdmitted':self.owner is not None,
                    'actualPopenReturncode':self.process.poll() if self.process is not None else None,
                    'startupBudgetSeconds':35,'startupDeadlineMonotonic':self.startup_deadline,
                    'observations':self.startup_events}})
            raise

    def stop(self):
        if self.cleanup is not None:
            return self.cleanup
        result = {'complete': False, 'errors': [], 'survivingPids': []}
        try:
            if self.process is not None:
                if self.owner is None:
                    # A child may exit before /proc capture. Its original Popen
                    # may be reaped, but no live process/group can be signalled.
                    if self.process.poll() is None:
                        assert self.startup_anchor is not None, 'Unknown live child ownership; refuse signal'
                        actual = _proc_observation(self.process.pid,self.startup_anchor,private=False)
                        assert actual is not None and actual['anchor']==self.startup_anchor, 'OVT_SCENE_PRE_ADMISSION_CLEANUP_ANCHOR'
                        assert actual['anchor']['ppid']==os.getpid(), 'OVT_SCENE_PRE_ADMISSION_NOT_ORIGINAL_PARENT'
                    self.original.stop(self.process)
                    result['survivingPids'] = group_survivors(self.process.pid)
                    assert not result['survivingPids']
                else:
                    require_owner(self.owner,anchor=self.startup_anchor)
                    # Use the existing source's actual lifecycle stop, unchanged.
                    self.original.stop(self.process)
                    assert self.process.poll() is not None
                    result['survivingPids'] = group_survivors(self.owner['pgid'])
                    assert not result['survivingPids']
                    assert identity(self.owner['pid']) is None
            result['complete'] = True
        except BaseException as error:
            result['errors'].append({'exception': static_exception(error, self.source, set(), diagnostic_files=(Path(__file__),))})
        self.cleanup = result
        write(self.runtime / 'STOP_RESULT.actual.json', result)
        return result

    def __exit__(self, kind, error, traceback):
        if error is not None:
            return False  # Preserve the failing service and its original logs.
        cleanup = self.stop()
        if not cleanup['complete']:
            raise RuntimeError('Owned original scene cleanup incomplete')
        return False
