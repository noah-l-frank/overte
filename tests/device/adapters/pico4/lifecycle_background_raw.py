"""Opt-in Background3 raw ranges on the original warm source lock.

The transport hooks retain every actual getter return before its source parser.
The owner projection can only reference those receipts. Archival guards do not
query a candidate or refresh a source clock. No cold writer adoption exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import hashlib
import os

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import LIMIT,exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.observer_return import state as file_state
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_source import nonce
from adapters.script_journey.history import canonical,MAX_RAW

VERSION=3
ROLES=('ui','gesture','drive','background','feature')
REFERENCE={'lifecycleBackgroundRangeVersion','source','sha256'}


def scope(run,binding):
    need(nonce(run))
    return dict(lifecycleBackgroundOriginalsVersion=VERSION,runId=run,
        binding=deepcopy(context(binding)),role='lifecycle-background')


def original(value):
    exact(value,{'raw','sha256'})
    need(type(value['raw']) is str and len(value['raw'].encode('utf-8'))<=LIMIT
        and frame(value['raw'])==value)


class LifecycleBackgroundRaw3:
    """Explicit live layout; the argument is never inferred from cold files."""
    version=VERSION
    roles=ROLES

    def raw_scope(self,run,binding):return scope(run,binding)

    def literal_limit(self,role):return LIMIT

    def current_bill(self):return self.source_bill()

    def guard_namespace(self):self.namespace.guard_lease()

    def __init__(self,path,run,binding,lock,identity,bill,clock):
        self.run,self.binding,self.lock=run,deepcopy(context(binding)),lock
        with lock.held():
            need(PrivateFeatureState(path).read() is None and not list(path.parent.glob(path.name+'.*')))
        self.source_bill=self._source_bill=bill
        from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
        self.namespace=getattr(bill,'namespace',bill);need(type(self.namespace) is LifecycleNamespaceBill)
        self.references=[];self.hooks={};self.outer_anchor=self.world_anchor=self.world_hook=None
        self.phase_fence=self._phase_fence=None
        self.write_gates={}
        self.maximum_literal=0
        self.failed=False;self.published=False;self.frozen=False
        self.archive=AudioRawArchive.__new__(AudioRawArchive)
        try:AudioRawArchive.__init__(self.archive,path,self.raw_scope(run,binding),lock,identity,self.other_bill,clock)
        except BaseException:
            self.failed=True
            if hasattr(self.archive,'directory'):
                from adapters.pico4.lifecycle_background_raw_state import close_or_retain
                close_or_retain(path.parent,self.archive)
            raise
        self.path=self.archive.path
        self.namespace.bind_raw_capacity(self.metadata_capacity)

    def metadata_capacity(self):
        ours=self.archive.bill()
        pending=sum(row['limit']+row['sideBytes'] for row in self.archive.state['pending'])
        return (ours['decodedBytes']+2*ours['literalBytes']+LIMIT+2*ours['metadataBytes']
            +len(canonical(self.references))+pending+3*65536+self.namespace.write_extra()
            +sum(3*gate.metadata_bytes() for gate in self.write_gates.values()))

    def other_bill(self):
        need(self.source_bill is self._source_bill)
        self.phase_writes()
        current=self.current_bill();exact(current,{'parts','storedBytes','decodedBytes','files'})
        # A complete original-part pass and reconstructed range batch coexist
        # with the archive's own prefix/metadata and actual owner references.
        # No additional long-lived raw string or canonical DTO cache exists.
        ours=self.archive.bill()
        overlap=2*ours['literalBytes']+LIMIT+2*ours['metadataBytes']+len(canonical(self.references))
        overlap+=sum(3*gate.metadata_bytes() for gate in self.write_gates.values())
        result=deepcopy(current);result['decodedBytes']+=overlap
        need(result['decodedBytes']<=MAX_RAW);return result

    @property
    def disk(self):
        # Raw returns may precede the first owner CAS. They are durable retained
        # originals, but do not imply that an owner root has been committed.
        return self.archive.disk if self.published else None

    @property
    def manifest(self):return deepcopy(self.references)

    def verify(self,*,materialize=False):
        try:
            with self.lock.held():return self._verify(materialize=materialize)
        except BaseException:self.failed=True;raise

    def verify_before_batch(self,*,materialize):
        need(not self.failed)
        self.phase_writes()
        if materialize:
            # Before copying/decoding the complete batch, include its exact
            # temporary ranges alongside expanded owner/CAS and source bytes.
            current=self.other_bill();ours=self.archive.bill()
            need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)
        elif self.namespace.lease is not None:self.guard_namespace()
        else:need(not self.archive.state['parts'] and not self.references)
        need(self.archive.bill()['literalBytes']<=self.maximum_literal)
        self.archive.verify()
        self.check_hooks()
        if self.world_hook is not None:
            world,callback=self.world_hook;need(world.before_io is callback and world.lock is self.lock)
    def _verify(self,*,materialize):
        self.verify_before_batch(materialize=materialize)
        from adapters.pico4.lifecycle_raw_ranges import verified_ranges
        by_read,records=verified_ranges(self.archive,roles=ROLES,materialize=materialize)
        by_digest={}
        if materialize:
            for record in records.values():
                if record['kind']=='utf8':
                    # Earliest immutable original; later getters never renew
                    # the projection's original receipt clock.
                    by_digest.setdefault(record['sha256'],dict(lifecycleBackgroundRangeVersion=VERSION,
                        source=dict(audioRawRangeVersion=1,scopeSha256=self.archive.scope_sha,
                            read=record['read'],sha256=record['sha256']),sha256=record['sha256']))
        for value in self.references:
            exact(value,REFERENCE);reference=value['source']
            exact(reference,{'audioRawRangeVersion','scopeSha256','read','sha256'})
            need(type(value['lifecycleBackgroundRangeVersion']) is int and value['lifecycleBackgroundRangeVersion']==VERSION
                and type(reference['audioRawRangeVersion']) is int and reference['audioRawRangeVersion']==1
                and reference['scopeSha256']==self.archive.scope_sha
                and integer(reference['read'],0,self.archive.state['reads']-1))
            index=reference['read'];need(index in records);record=records[index]
            need(record['sha256']==reference['sha256']==value['sha256'] and record['kind']=='utf8')
        self.archive.verify()
        return by_read,by_digest

    def check_hooks(self):
        for reader,send_name,original_send,_transport,_getter,wrapped_send,wrapped_getter,before_io in self.hooks.values():
            need(getattr(reader,send_name) is wrapped_send and reader.original is wrapped_getter and reader.before_io is before_io)
            if send_name=='dispatch':need(reader.send is original_send)
        for gate in self.write_gates.values():
            need(gate.writer.storage_gate is gate and gate.writer._original_storage_gate is gate)

    def resolve(self,value):
        exact(value,REFERENCE)
        need(type(value['lifecycleBackgroundRangeVersion']) is int
            and value['lifecycleBackgroundRangeVersion']==VERSION)
        raw=self.archive.literal(value['source'])
        need(type(raw) is str and frame(raw)['sha256']==value['sha256'])
        return frame(raw)

    def begin_outer(self,started,requested):
        need(self.outer_anchor is None and number(started,0,1e15) and integer(requested,1))
        self.outer_anchor=(started,requested)

    def bind_phase(self,fence):
        from adapters.pico4.lifecycle_operations import LifecycleInputFence
        need(type(fence) is LifecycleInputFence and self.phase_fence is None
            and fence.owner.lock is self.lock and fence.owner.source.run==self.run
            and fence.owner.source.binding==self.binding and fence.owner.store.path.parent==self.path.parent)
        self.phase_fence=self._phase_fence=fence
        self.install_writer(fence.owner.source,'source')

    def install_writer(self,writer,role):
        from adapters.pico4.lifecycle_write_gate import LifecycleWriteGate
        need(role not in self.write_gates)
        gate=LifecycleWriteGate(self,writer,role);self.write_gates[role]=gate;return gate

    def phase_writes(self):
        need(self.phase_fence is self._phase_fence)
        if self.phase_fence is None or self.namespace.lease is None:return
        owner=self.phase_fence.owner;names,pins=self.namespace.lease
        saved=dict(pins).get(owner.store.path.name)
        if saved!=tuple(owner.stamp) or self.namespace.lease_names()!=names:
            self.namespace.phase_writer(owner)

    def end_outer(self,started,requested):
        need(self.outer_anchor==(started,requested));self.outer_anchor=None

    def bind_world(self,world):
        from adapters.pico4.lifecycle_world import PicoLifecycleWorld
        need(type(world) is PicoLifecycleWorld and world.lock is self.lock and world.before_io is None
            and self.world_hook is None)
        def before_io(started,requested,role):
            need(role in ('gesture','drive','ui') and number(started,0,1e15) and integer(requested,1))
            if role=='gesture':self.world_anchor=(started,requested)
            else:need(self.world_anchor==(started,requested))
        world.before_io=before_io;self.world_hook=(world,before_io)
        self.install_writer(world,'world')

    def query_gate(self,reader,role,anchor,command):
        need(anchor is not None and not self.failed and not self.frozen)
        started,requested=anchor;now=reader.monotonic()
        need(number(now,started,started+5) and now-started<5 and integer(requested,1))
        need(reader.guard() is not False)
        # Only the actual mutating Background arm/release inherits an existing
        # input phase fence. Quiet read-only observations do not invent one.
        fence=getattr(reader,'phase_fence',None)
        if role=='background' and command.get('operation')!='observe' and fence is not None:fence.host_fresh()
        now=reader.monotonic();need(number(now,started,started+5) and now-started<5)
        for outer in (self.outer_anchor,self.world_anchor if role in ('ui','gesture','drive') else None):
            if outer is not None:need(number(now,outer[0],outer[0]+1.5))

    def hook(self,reader,role):
        need(not self.failed and not self.frozen and role in self.roles
            and role not in self.hooks and callable(reader.send) and callable(reader.original)
            and reader.before_io is None)
        send_name='send';original_send=reader.send
        if role=='background':
            from adapters.pico4.lifecycle_background_source import NativeLifecycleBackground
            need(type(reader) is NativeLifecycleBackground)
            if reader.dispatch is not None:
                need(callable(reader.dispatch));send_name='dispatch'
        send,getter=getattr(reader,send_name),reader.original;pending=None;command=None;anchor=None

        def before_io(started,requested,stage):
            nonlocal anchor
            self.check_hooks()
            need(stage in ('send','get') and number(started,0,1e15) and integer(requested,1))
            if stage=='send':anchor=(started,requested)
            else:need(anchor==(started,requested))

        def reserve():
            # A literal, its canonical {raw,sha256} DTO, parsed source DTO and
            # temporary projection may coexist. This bound is reserved BEFORE
            # transport acquisition; already acquired bytes retain authority.
            current=self.archive.bill()['literalBytes']
            limit=self.literal_limit(role)
            token=self.archive.reserve(role,deepcopy(command),limit,side_bytes=6*limit)
            self.maximum_literal=max(self.maximum_literal,current+token['limit'])
            return token

        @wraps(send)
        def send_original(value):
            nonlocal pending,command
            try:
                need(not self.failed and not self.frozen and pending is None)
                json_digest(value);need(type(value) is dict);command=deepcopy(value)
                pending=reserve()
                self.verify()
                self.query_gate(reader,role,anchor,command)
                return send(value)
            except BaseException:
                self.failed=True
                # Delivery is uncertain. Keep its durable pending reservation;
                # there is no resend, replacement reader or fallback path.
                raise

        @wraps(getter)
        def get_original():
            nonlocal pending
            need(not self.failed and not self.frozen and command is not None)
            if pending is None:pending=reserve()
            token=pending
            try:
                self.verify()
                self.query_gate(reader,role,anchor,command)
                raw=getter()
                # Do not call reader.guard/native clock here. Death or expiry
                # after acquisition must not prevent retaining acquired bytes.
                reference=self.archive.retain(token,raw);pending=None
                return raw
            except BaseException:
                self.failed=True
                raise

        if role=='pending':
            from adapters.pending_commit_owner import NativePendingCommitOwner
            need(type(reader) is NativePendingCommitOwner);reader.bind_before_io(before_io)
        else:reader.before_io=before_io
        setattr(reader,send_name,send_original);reader.original=get_original
        self.hooks[role]=(reader,send_name,original_send,send,getter,send_original,get_original,before_io)

    def encode(self,value):
        with self.lock.held():return self._encode(value)

    def _encode(self,value):
        need(not self.failed and not self.frozen)
        by_read,by_digest=self.verify(materialize=True);json_digest(value)
        def encode(item):
            if type(item) is dict:
                if set(item)=={'raw','sha256'}:
                    original(item);need(item['sha256'] in by_digest)
                    reference=by_digest[item['sha256']]
                    need(by_read[reference['source']['read']]==item['raw'].encode('utf-8'))
                    if reference not in self.references:self.references.append(deepcopy(reference))
                    return deepcopy(reference)
                return {key:encode(child) for key,child in item.items()}
            if type(item) is list:return [encode(child) for child in item]
            return deepcopy(item)
        result=encode(value);self.published=True;self.verify();return result

    def decode(self,value):
        with self.lock.held():return self._decode(value)

    def _decode(self,value):
        by_read,_by_digest=self.verify(materialize=True)
        def decode(item):
            if type(item) is dict:
                if set(item)==REFERENCE:
                    need(item in self.references);raw=by_read[item['source']['read']].decode('utf-8')
                    need(frame(raw)['sha256']==item['sha256']);return frame(raw)
                return {key:decode(child) for key,child in item.items()}
            if type(item) is list:return [decode(child) for child in item]
            return deepcopy(item)
        return decode(value)

    def seal(self):
        need(not self.failed and not self.frozen)
        with self.lock.held():
            self.preflight_batch()
            self.verify();need(not self.archive.state['pending'])
            self.archive.seal_part();self.verify();self.frozen=True

    def close_host(self):
        self.frozen=True
        closed=all([*(gate.close_host() for gate in self.write_gates.values()),self.archive.close_host()])
        if closed is not True:
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((self.path.parent,self))
        return closed

    def owned_names(self):
        self.archive.verify();names={self.archive.path.name}
        names.update(self.archive.part_path(index).name for index in range(len(self.archive.state['parts'])))
        names.update(self.archive.page_store(index).path.name for index in self.archive.pages)
        return names

    def preflight_batch(self):
        current=self.other_bill();ours=self.archive.bill()
        need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)


class LifecycleBackgroundRawHistory3:
    """Passive original ranges, including receipts from failed live owners."""
    historical_only=True
    version=VERSION
    reference_fields=REFERENCE
    def expected_scope(self,run,binding):return scope(run,binding)

    def __init__(self,path,run,binding,references):
        self.archive=AudioPCRawOriginals(path)
        try:
            need(self.archive.disk['scope']==self.expected_scope(run,binding) and type(references) is list)
            self.references=deepcopy(references)
            self.pins={name:signature((self.archive.path.parent/name).lstat()) for name in self.archive.files}
            for value in self.references:self.resolve(value)
        except BaseException:
            from adapters.pico4.lifecycle_background_raw_state import close_or_retain
            close_or_retain(self.archive.path.parent,self.archive);raise

    def verify(self):
        self.archive.guard()
        for name,source in self.archive.files.items():
            path=self.archive.path.parent/name
            need(signature(path.lstat())==self.pins[name])
            if isinstance(source,OriginalDescriptor):
                # The reused passive reader explicitly closes its empty-file
                # window. A new read window checks that SAME immutable zero
                # byte original; it is never continuation of its closed OFD.
                window=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    window.require(window.fd);need(os.pread(window.fd,1,0)==b''
                        and signature(os.fstat(window.fd))==self.pins[name]);window.require(window.fd)
                finally:need(window.close())
            else:source.read()
            need(signature(path.lstat())==self.pins[name])
        self.archive.guard()

    def resolve(self,value):
        exact(value,REFERENCE)
        need(type(value['lifecycleBackgroundRangeVersion']) is int
            and value['lifecycleBackgroundRangeVersion']==VERSION)
        raw=self.archive.literal(value['source']);need(type(raw) is str)
        value_raw=frame(raw);need(value_raw['sha256']==value['sha256']);return value_raw

    def decode(self,value):
        self.verify();return self._decode(value)

    def _decode(self,value):
        if type(value) is dict:
            if set(value)==self.reference_fields:
                need(value in self.references);return self.resolve(value)
            return {key:self._decode(child) for key,child in value.items()}
        if type(value) is list:return [self._decode(child) for child in value]
        return deepcopy(value)

    def report(self):
        self.verify();return dict(self.archive.report(),lifecycleBackgroundOriginalsVersion=self.version)

    def originals(self):
        """Stream every actual file, including unconfirmed tails/extra parts.

        These are historical file originals, never new confirmed range receipts
        or source facts. A failed transfer's raw bytes are not silently omitted.
        """
        from adapters.chat_journey.archive_file import ClosedOriginalFile
        self.verify();root=self.archive.path;names=tuple(sorted(path.name for path in root.parent.iterdir()
            if path.name==root.name or path.name.startswith(root.name+'.')))
        need(len(names)<=530)
        pins={name:signature((root.parent/name).lstat()) for name in names}
        need(sum(stamp[5] for stamp in pins.values())+65536<=MAX_RAW)
        for name in names:
            path=root.parent/name;stamp=pins[name];need(0<=stamp[5]<=65536 and signature(path.lstat())==stamp)
            if stamp[5]==0:
                window=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    window.require(window.fd);raw=os.pread(window.fd,1,0)
                    need(raw==b'' and signature(os.fstat(window.fd))==stamp);window.require(window.fd)
                finally:need(window.close())
            else:
                source=self.archive.files.get(name) or ClosedOriginalFile(path,stamp[2]&0o777,self.archive.guard)
                try:raw,actual=source.read();need(actual==stamp)
                except BaseException:
                    from adapters.pico4.lifecycle_background_raw_state import close_or_retain
                    close_or_retain(root.parent,source);raise
            yield dict(name=name,raw=raw,sha256=hashlib.sha256(raw).hexdigest(),physical=stamp,
                historicalOnly=True,liveAuthority=False)
            need(signature(path.lstat())==stamp);self.archive.guard()
        need(names==tuple(sorted(path.name for path in root.parent.iterdir()
            if path.name==root.name or path.name.startswith(root.name+'.'))))

    def close(self):
        closed=self.archive.close()
        if closed is not True:
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((self.archive.path.parent,self))
        return closed


class LifecycleBackgroundHistory:
    """Read old1/new3 owners without creating any live owner or source reader."""
    historical_only=True
    def __init__(self,path):
        from adapters.chat_journey.archive_file import ClosedOriginalFile
        from adapters.pico4.lifecycle_background_originals import LifecycleBackgroundOriginals
        from adapters.script_journey.history import unpack
        self.path=path;self.directory=OriginalDescriptor(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.originals=None;self.root=None
        try:
            self.root=ClosedOriginalFile(path,0o600,lambda:require_directory(self.directory,path.parent))
            self.raw,self.physical=self.root.read()
            import json
            self.disk=json.loads(self.raw)
            exact(self.disk,{'lifecycleBackgroundOwnerVersion','runId','binding','originalChunks','payload'})
            need(canonical(self.disk)+b'\n'==self.raw)
            self.version=self.disk['lifecycleBackgroundOwnerVersion']
            need(type(self.version) is int and self.version in (1,VERSION,4,5));context(self.disk['binding'])
            if self.version==1:
                self.originals=LifecycleBackgroundOriginals(path.with_name('lifecycle-background-originals.json'),
                    self.disk['runId'],self.disk['binding'])
                need(self.originals.manifest==self.disk['originalChunks'])
            elif self.version==VERSION:
                self.originals=LifecycleBackgroundRawHistory3(path.with_name('lifecycle-background-raw.json'),
                    self.disk['runId'],self.disk['binding'],self.disk['originalChunks'])
            else:
                from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
                self.originals=LifecycleSourceRawHistory4.open_profile(path.with_name('lifecycle-background-raw.json'),
                    self.disk['runId'],self.disk['binding'],self.disk['originalChunks'],role='background')
                self.originals.decoder_budget(self.disk['payload'])
            self.value=self.originals.decode(unpack(self.disk['payload']))
            need(type(self.value) is list and len(self.value)==1)
            if self.version in (4,5):
                from adapters.pico4.lifecycle_namespace_bill import canonical_size
                self._value_seal=self._original_value_seal=(self.value,canonical_size(self.value),json_digest(self.value))
            self.read()
        except BaseException:
            from adapters.pico4.lifecycle_background_raw_state import close_or_retain
            close_or_retain(path.parent,self);raise

    def read(self):
        need(self.root.read()==(self.raw,self.physical))
        self.originals.verify()
        if hasattr(self,'_original_value_seal'):
            need(self.version in (4,5) and self._value_seal is self._original_value_seal)
            self.originals.guard_value(self.value,self._value_seal)
        return deepcopy(self.value[0])

    def close(self):
        results=[]
        if isinstance(self.originals,LifecycleBackgroundRawHistory3):results.append(self.originals.close())
        if self.root is not None:results.append(self.root.close())
        results.append(self.directory.close());closed=all(results)
        if not closed:
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((self.path.parent,self))
        return closed
