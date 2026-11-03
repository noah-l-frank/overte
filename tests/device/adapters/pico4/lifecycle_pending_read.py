"""One bounded, opaque Pending SDK wire and verified body extent.

Private unintegrated prerequisite: no Native send, product input, new archive,
quota or factory. The caller selects the explicit profile before IO and owns
the same global archive/bill. This file does not enable Pending3 or Actor3.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import shlex
import stat
import subprocess
import time
import uuid

from adapters.android_snapshot_files import original_stat
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.pending_commit_owner import command
from adapters.pico4.audio_raw_archive import AudioRawArchive

VERSION=1
PAYLOAD_LIMIT=32768
WIRE_LIMIT=PAYLOAD_LIMIT+4096
PACKAGE='org.overte.pico'
PATH='files/overte-e2e/feature-pending-commit-owner.json'
ROLE='pending-wire'
HEADER=b'OVT_PICO_PENDING_READ_V1\n'
FOOTER=b'\nOVT_PICO_PENDING_READ_END_V1 '
BODY_KEYS={'lifecyclePendingBodyVersion','wireOriginal','readNonce','nativeCommandId','offset','bytes','sha256'}
UNRESOLVED=[]

# Source-only fixed file command. A new explicit Pico producer mode must save
# once per Native command before this transport is wired into the real route.
READ_SCRIPT=r'''
set -f
expected_pid=$1
expected_start=$2
requested_epoch=$3
deadline_epoch=$4
nonce=$5
original_path=files/overte-e2e/feature-pending-commit-owner.json
same_source_process() {
    process_stat=$(cat "/proc/$expected_pid/stat") || return 1
    process_fields=${process_stat##*) }
    set -- $process_fields
    [ "$#" -ge 20 ] || return 1
    shift 19
    [ "$1" = "$expected_start" ]
}
same_window() {
    current_epoch=$(date +%s%3N) || return 1
    case "$current_epoch" in ''|*[!0-9]*) return 1;; esac
    [ "$current_epoch" -ge "$requested_epoch" ] && [ "$current_epoch" -lt "$deadline_epoch" ]
}
printf 'OVT_PICO_PENDING_READ_V1\n%s\n' "$nonce"
[ -d files ] && [ ! -L files ] && [ -d files/overte-e2e ] && [ ! -L files/overte-e2e ] || exit 1
[ "$(stat -c %u files/overte-e2e)" = "$(id -u)" ] && [ "$(stat -c %a files/overte-e2e)" = 700 ] || exit 1
same_source_process && same_window || exit 1
if [ ! -e "$original_path" ] && [ ! -L "$original_path" ]; then
    same_source_process && same_window || exit 1
    printf 'missing\nabsent\n\nOVT_PICO_PENDING_READ_END_V1 %s\nabsent\n' "$nonce"
    exit 0
fi
[ -f "$original_path" ] && [ ! -L "$original_path" ] || exit 1
[ "$(stat -c %h "$original_path")" = 1 ] && [ "$(stat -c %u "$original_path")" = "$(id -u)" ] || exit 1
before=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ "${#before}" -le 512 ] || exit 1
exec 3<"$original_path" || exit 1
held_path="/proc/$$/fd/3"
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
printf 'present\n%s\n' "$before"
head -c 32769 <&3 || exit 1
after=$(stat -c '%d %i %f %u %h %s %y %z' "$original_path") || exit 1
[ ! -L "$original_path" ] && [ "$before" = "$after" ] || exit 1
[ "$before" = "$(stat -Lc '%d %i %f %u %h %s %y %z' "$held_path")" ] || exit 1
same_source_process && same_window || exit 1
printf '\nOVT_PICO_PENDING_READ_END_V1 %s\n%s\n' "$nonce" "$after"
'''.strip()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def wire_extent(wire,nonce):
    """No UTF8/JSON parser sees an arbitrary or oversized prefix as complete."""
    need(type(wire) is bytes and len(wire)<=WIRE_LIMIT and type(nonce) is str
        and re.fullmatch('[0-9a-f]{32}',nonce))
    prefix=HEADER+nonce.encode('ascii')+b'\n';need(wire.startswith(prefix))
    kind,separator,rest=wire[len(prefix):].partition(b'\n');need(separator and kind in (b'present',b'missing'))
    before,separator,data=rest.partition(b'\n');need(separator and 0<len(before)<=512)
    offset=len(wire)-len(data)
    suffix=FOOTER+nonce.encode('ascii')+b'\n'+before+b'\n'
    if kind==b'missing':
        need(before==b'absent' and data==suffix)
        return dict(status='missing',offset=offset,bytes=0,sourceBytes=None,originalStat=None)
    description=before.decode('ascii');fields=description.split()
    need(len(fields)==12 and fields[5].isascii() and fields[5].isdigit())
    size=int(fields[5]);need(original_stat(description,size))
    mode=int(fields[2],16);need(stat.S_ISREG(mode) and stat.S_IMODE(mode)==0o600)
    observed=min(size,PAYLOAD_LIMIT+1)
    need(len(data)==observed+len(suffix) and data[observed:]==suffix)
    return dict(status='complete' if size<=PAYLOAD_LIMIT else 'over-limit',offset=offset,
        bytes=observed,sourceBytes=size,originalStat=description)


def body_original(wire,reference,*,record,scope_sha,run):
    """Decode one verified archive record; caller verifies current parts first."""
    exact(reference,BODY_KEYS)
    need(type(reference['lifecyclePendingBodyVersion']) is int and reference['lifecyclePendingBodyVersion']==VERSION
        and type(reference['nativeCommandId']) is str and re.fullmatch('[0-9a-f]{32}',reference['nativeCommandId']))
    extent=wire_extent(wire,reference['readNonce'])
    need(extent['status']=='complete' and integer(reference['offset'],0,WIRE_LIMIT)
        and integer(reference['bytes'],0,PAYLOAD_LIMIT) and reference['offset']==extent['offset']
        and reference['bytes']==extent['bytes'])
    source=reference['wireOriginal'];exact(source,{'audioRawRangeVersion','scopeSha256','read','sha256'})
    need(type(source['audioRawRangeVersion']) is int and source['audioRawRangeVersion']==1
        and integer(source['read'],0,511) and type(source['scopeSha256']) is str
        and re.fullmatch('[0-9a-f]{64}',source['scopeSha256']) and source['scopeSha256']==scope_sha
        and source['sha256']==sha(wire))
    exact(record,{'read','role','command','hostMonotonic','returnedHostMonotonic','kind','bytes','sha256','ranges'})
    need(record['read']==source['read'] and record['role']==ROLE and record['kind']=='bytes'
        and record['bytes']==len(wire) and record['sha256']==source['sha256'])
    description=record['command']
    exact(description,{'lifecyclePendingReadVersion','nativeRequest','readNonce','originalStartedHost',
        'originalRequestedEpochMs','reservationEnteredHost'})
    need(type(description['lifecyclePendingReadVersion']) is int and description['lifecyclePendingReadVersion']==VERSION
        and description['readNonce']==reference['readNonce']
        and type(run) is str and re.fullmatch('[0-9a-f]{32}',run)
        and command(description['nativeRequest'])['commandId']==reference['nativeCommandId']
        and description['nativeRequest']['runId']==run
        and integer(description['originalRequestedEpochMs'],1))
    started=description['originalStartedHost'];entered=description['reservationEnteredHost']
    need(number(started,0,1e15) and number(entered,started,started+5)
        and number(record['hostMonotonic'],entered,started+5)
        and number(record['returnedHostMonotonic'],record['hostMonotonic'],started+5)
        and record['returnedHostMonotonic']-started<5)
    body=wire[extent['offset']:extent['offset']+extent['bytes']]
    need(reference['sha256']==sha(body));return body.decode('utf-8')


def body_key(reference):
    """Cheap closed identity, without materialization or source authority."""
    exact(reference,BODY_KEYS);source=reference['wireOriginal']
    exact(source,{'audioRawRangeVersion','scopeSha256','read','sha256'})
    need(type(reference['lifecyclePendingBodyVersion']) is int and reference['lifecyclePendingBodyVersion']==VERSION
        and type(source['audioRawRangeVersion']) is int and source['audioRawRangeVersion']==1
        and integer(source['read'],0,511) and integer(reference['offset'],0,WIRE_LIMIT)
        and integer(reference['bytes'],0,PAYLOAD_LIMIT))
    for item in (source['scopeSha256'],source['sha256'],reference['sha256']):
        need(type(item) is str and re.fullmatch('[0-9a-f]{64}',item))
    for item in (reference['readNonce'],reference['nativeCommandId']):
        need(type(item) is str and re.fullmatch('[0-9a-f]{32}',item))
    return ('pending-body',source['scopeSha256'],source['read'],source['sha256'],reference['readNonce'],
        reference['nativeCommandId'],reference['offset'],reference['bytes'],reference['sha256'])


def body_dto(identity):
    need(type(identity) is tuple and len(identity)==9 and identity[0]=='pending-body')
    _,scope,read,wire_sha,nonce,command_id,offset,size,digest=identity
    result=dict(lifecyclePendingBodyVersion=VERSION,
        wireOriginal=dict(audioRawRangeVersion=1,scopeSha256=scope,read=read,sha256=wire_sha),
        readNonce=nonce,nativeCommandId=command_id,offset=offset,bytes=size,sha256=digest)
    need(body_key(result)==identity);return result


def body_receipt(wire,record,*,scope_sha,run):
    """A typed extent of this verified record, not a second original row."""
    need(type(record) is dict and type(record.get('command')) is dict)
    description=record['command'];extent=wire_extent(wire,description.get('readNonce'))
    need(extent['status']=='complete' and type(description.get('nativeRequest')) is dict)
    reference=dict(lifecyclePendingBodyVersion=VERSION,
        wireOriginal=dict(audioRawRangeVersion=1,scopeSha256=scope_sha,read=record['read'],sha256=record['sha256']),
        readNonce=description['readNonce'],nativeCommandId=description['nativeRequest'].get('commandId'),
        offset=extent['offset'],bytes=extent['bytes'],sha256=sha(wire[extent['offset']:extent['offset']+extent['bytes']]))
    body_key(reference)
    return reference,body_original(wire,reference,record=record,scope_sha=scope_sha,run=run)


class PicoLifecyclePendingRead:
    """Exact issued wire reservation; no retry, resend or automatic cleanup."""
    def __init__(self,adapter,target,binding,archive,*,monotonic=time.monotonic,bank=None):
        from adapters.normal_feature_state import context
        need(adapter.kind=='pico' and adapter.profile['package']==PACKAGE and type(target) is str and target
            and type(archive) is AudioRawArchive and callable(monotonic))
        need(type(archive.scope.get('pendingNativeReadVersion')) is int and archive.scope['pendingNativeReadVersion']==VERSION
            and type(archive.scope.get('lifecycleSourceRawVersion')) is int and archive.scope['lifecycleSourceRawVersion']==4
            and archive.scope.get('binding')==context(binding)
            and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*',binding['processIdentity']))
        if bank is not None:
            from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
            need(type(bank) is LifecycleSourceRaw4 and bank.archive is archive and bank.pending_read_version==1
                and bank.run==archive.scope['runId'] and bank.binding==context(binding))
        self.bank=bank
        self.adapter,self.target,self.binding,self.archive=adapter,target,deepcopy(binding),archive
        self.monotonic=monotonic;self.binary=adapter.adb.execute_bytes
        self.profile=json_digest(adapter.profile);self.binding_sha=json_digest(self.binding)
        self._fixed=self._original_fixed=(adapter,target,archive,monotonic,self.binary,self.profile,self.binding_sha,bank)
        self.failed=False;self.active=False;self.acquired=None;self.pending=None;self.last=None;self.timing=None
        self.native_binding=self._native_binding=None;self.owner_binding=self._owner_binding=None
        self.exchange=None;self.request=None;self.pending_nonce=None;self.pending_anchor=None
        if bank is not None:bank.bind_pending_transport(self)

    def poison(self):
        self.failed=True
        if self.bank is not None:self.bank.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def admit_factory(self,adapter,target,binding):
        """Pure original holder/scope admission, before any cold SDK helper."""
        from adapters.normal_feature_state import context
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        need(adapter is self.adapter and target==self.target and binding is not None
            and type(self.bank) is LifecycleSourceRaw4 and self.bank.pending_read_version==1
            and not self.failed and not self.active and not self.bank.failed and not self.bank.frozen
            and self.native_binding is self._native_binding is None
            and self.owner_binding is self._owner_binding is None
            and self.bank.archive is self.archive and self.bank.pending_transport is self.bank._pending_transport is self
            and context(binding)==self.binding==self.archive.scope['binding']
            and self.bank.binding==self.binding and self.bank.run==self.archive.scope['runId']
            and self._fixed is self._original_fixed
            and self.adapter.adb.execute_bytes==self.binary and json_digest(self.adapter.profile)==self.profile
            and json_digest(self.binding)==self.binding_sha)
        self.bank.profile_guard();self.archive.lock.assert_held()
        need(self.archive.lock is self.bank.lock is self.bank.namespace.lock
            and self.archive.scope.get('pendingNativeReadVersion')==VERSION)

    def bind_native(self,native,original_write,selected_dispatch):
        from adapters.native_feature_observation import NativeFeatureObservation
        need(self.bank is not None and type(native) is NativeFeatureObservation
            and self.native_binding is self._native_binding is None and not self.failed
            and native.pid==int(self.binding['processIdentity'].split(':')[0]) and native.ios is False
            and native.monotonic is self.monotonic and callable(original_write)
            and selected_dispatch==self.dispatch)
        self.native_binding=self._native_binding=(native,native.send,native.guard,native.clock_ms,
            native.monotonic,native.sleep,original_write,selected_dispatch)

    def bind(self,owner,*,native,target,binding):
        from adapters.pending_commit_owner import NativePendingCommitOwner
        from adapters.normal_feature_state import context
        need(type(owner) is NativePendingCommitOwner and self.bank is not None and not self.failed
            and self.owner_binding is self._owner_binding is None and self.native_binding is self._native_binding
            and self.native_binding is not None and self.native_binding[0] is native
            and target==self.target and context(binding)==self.binding and owner.ios is False
            and not owner._io_admitted and owner.before_io is owner._before_io is None
            and owner.send is native.send and owner.guard is native.guard and owner.clock_ms is native.clock_ms
            and owner.monotonic is self.monotonic and owner.pid==native.pid)
        before,getter=self.before_io,self.get_original
        self.owner_binding=self._owner_binding=(owner,owner.send,owner.guard,owner.clock_ms,owner.monotonic,
            owner.sleep,owner.pid,owner.original,before,getter)
        try:
            owner.original=getter;owner.bind_before_io(before)
            self.host_bindings()
        except BaseException:self.poison();raise

    def host_bindings(self):
        need(self.native_binding is self._native_binding and self.owner_binding is self._owner_binding)
        if self.native_binding is not None:
            native,send,guard,clock,monotonic,sleep,write,dispatch=self.native_binding
            need(native.send is send and native.guard is guard and native.clock_ms is clock
                and native.monotonic is monotonic is self.monotonic and native.sleep is sleep
                and dispatch==self.dispatch and callable(write))
        if self.owner_binding is not None:
            owner,send,guard,clock,monotonic,sleep,pid,old_get,before,getter=self.owner_binding
            need(owner.send is send and owner.guard is guard and owner.clock_ms is clock
                and owner.monotonic is monotonic is self.monotonic and owner.sleep is sleep and owner.pid==pid
                and owner.before_io is owner._before_io is before and before==self.before_io
                and owner.original is getter and getter==self.get_original)

    def metadata_bytes(self):
        from adapters.pico4.lifecycle_namespace_bill import canonical_size
        # Accounting may run during archival-only retention after a Native
        # callback is lost. It measures actual graphs, not live source authority.
        value=dict(binding=self.binding,request=self.request,last=self.last,
            timing=None if self.timing is None else list(self.timing),
            exchange=None if self.exchange is None else list(self.exchange),readNonce=self.pending_nonce)
        need(self.acquired is None or type(self.acquired) is bytes)
        return 3*canonical_size(value)+(0 if self.acquired is None else len(self.acquired))

    def before_io(self,started,requested,stage):
        try:
            self.host_bindings();need(self.owner_binding is not None and not self.failed
                and stage in ('send','get') and number(started,0,1e15) and integer(requested,1))
            if stage=='send':
                need(not self.active and self.pending is None)
                self.exchange=(started,requested);self.request=None
            else:need(self.exchange==(started,requested) and self.request is not None)
            self.fresh(started)
        except BaseException:self.poison();raise

    def reserve(self,request,started,requested,entered):
        need(self.pending is None)
        nonce=uuid.uuid4().hex
        description=dict(lifecyclePendingReadVersion=VERSION,nativeRequest=deepcopy(request),readNonce=nonce,
            originalStartedHost=started,originalRequestedEpochMs=requested,reservationEnteredHost=entered)
        self.pending=(self.archive.reserve(ROLE,description,WIRE_LIMIT,side_bytes=8*WIRE_LIMIT+4096)
            if self.bank is None else self.bank.reserve_pending_wire(self,description,side_bytes=8*WIRE_LIMIT+4096))
        self.pending_nonce=nonce;self.pending_anchor=(started,requested)
        return nonce

    def dispatch(self,request,original_write):
        try:
            self.host_bindings();need(self.owner_binding is not None and not self.failed and not self.active
                and self.native_binding[6] is original_write and self.exchange is not None and self.request is None)
            command(request);need(request['runId']==self.archive.scope['runId'])
            started,requested=self.exchange;entered=self.monotonic();self.fresh(started)
            self.request=deepcopy(request);self.reserve(request,started,requested,entered)
            # Existing native send has already performed its ORIGINAL action's
            # guard/read-only phase fence. Reserve, full current bill and the
            # SAME original clocks precede this exact SDK dispatch.
            wrapper=deepcopy(request);wrapper['action']='feature-pico-pending-read';wrapper['picoPendingReadVersion']=VERSION
            self.bank.query_gate(self,'pending',self.exchange,request);self.fresh(started)
            return original_write(wrapper)
        except BaseException:self.poison();raise

    def get_original(self):
        try:
            self.host_bindings();need(self.owner_binding is not None and self.request is not None and self.exchange is not None)
            return self.read(self.request,*self.exchange)
        except BaseException:self.poison();raise

    def identity(self):
        need(not self.failed and self._fixed is self._original_fixed and
            (self.adapter,self.target,self.archive,self.monotonic,self.binary,json_digest(self.adapter.profile),json_digest(self.binding),self.bank)==self._fixed
            and self.adapter.adb.execute_bytes==self.binary)
        self.host_bindings();self.archive.lock.assert_held()
        if self.bank is not None:
            self.bank.profile_guard();need(self.bank.pending_transport is self.bank._pending_transport is self
                and self.bank.archive is self.archive)
        self.adapter.require_same_process(self.target,self.binding['processIdentity'],'Lifecycle Pending source read')

    def guard(self):
        self.identity()
        if self.native_binding is not None:
            need(self.native_binding[2]() is not False);self.host_bindings()
        return True

    def fresh(self,started):
        now=self.monotonic();need(number(now,started,started+5) and now-started<5);return now

    def read(self,request,started,requested):
        need(not self.active and not self.failed);self.active=True
        self.last=None;self.timing=(started,requested,None,None,None)
        try:
            entered=self.monotonic();self.timing=(started,requested,entered,None,None)
            command(request);need(number(started,0,1e15) and number(entered,started,started+5)
                and integer(requested,1) and request['runId']==self.archive.scope['runId'])
            self.identity();self.fresh(started)
            if self.pending is None:nonce=self.reserve(request,started,requested,entered)
            else:
                need(self.pending_anchor==(started,requested) and self.pending_nonce is not None
                    and self.pending['command']['nativeRequest']==request)
                nonce=self.pending_nonce
            pid,birth=self.binding['processIdentity'].split(':')
            remote=' '.join(shlex.quote(value) for value in ('run-as',PACKAGE,'sh','-c',READ_SCRIPT,
                'overte-lifecycle-pending-read',pid,birth,str(requested),str(requested+5000),nonce))
            if self.bank is not None:self.bank.query_gate(self,'pending',(started,requested),request)
            else:self.identity()
            now=self.fresh(started);need(now>=entered)
            self.timing=(started,requested,entered,now,None)
            try:
                wire=self.binary(['exec-out',remote],target=self.target,timeout=started+5-now,check=False)
            except (RuntimeError,subprocess.TimeoutExpired) as error:
                original=error if type(error) is subprocess.TimeoutExpired else error.__cause__
                if type(original) is subprocess.TimeoutExpired and type(original.output) is bytes:
                    self.acquired=original.output;self.archive.retain(self.pending,self.acquired);self.pending=None;self.pending_nonce=None;self.pending_anchor=None
                self.timing=(started,requested,entered,now,self.monotonic())
                raise
            # Retention is archival-only: no PID/candidate/clock query may
            # prevent already acquired bytes from reaching their issued row.
            self.acquired=wire;original=self.archive.retain(self.pending,wire);self.pending=None;self.pending_nonce=None;self.pending_anchor=None
            completed=self.monotonic();self.timing=(started,requested,entered,now,completed)
            need(number(completed,now,started+5));self.identity();self.fresh(started);extent=wire_extent(wire,nonce)
            if extent['status']=='missing':self.last=None;self.acquired=None;return ''
            need(extent['status']=='complete')
            body=wire[extent['offset']:extent['offset']+extent['bytes']]
            reference=dict(lifecyclePendingBodyVersion=VERSION,wireOriginal=original,readNonce=nonce,
                nativeCommandId=request['commandId'],offset=extent['offset'],bytes=extent['bytes'],sha256=sha(body))
            record=self.archive.pages[original['read']//32]['receipts'][original['read']%32]
            result=body_original(wire,reference,record=record,scope_sha=self.archive.scope_sha,run=self.archive.scope['runId']);self.identity();self.fresh(started)
            self.last=reference;self.acquired=None;return result
        except BaseException:
            self.poison();raise
        finally:self.active=False
