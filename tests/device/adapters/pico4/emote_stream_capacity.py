"""Opt-in capacity for actual native capture files in the SAME raw aggregate.

Select before the original Parent's first source IO. This owner records no
observed Avatar/GPU facts and creates no input, quota, clock or raw archive.
Native Policy2 must actually enforce its closed file limits before publishing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re

from adapters.graphics_journey.originals import GraphicsOriginals,record as image_record
from adapters.pico4.emote_stream_png_capacity import PicoEmotePNGCapacity

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need
from adapters.native_fd_owner import require_directory
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical,pack,MAX_RAW,MAX_FRAMES,same
from adapters.world_render_evidence import validate as capture_packet
from adapters.world_render_storage import command as storage_command

VERSION=1
PART=65536
NATIVE_PNG_LIMIT=33554432 # Existing GPU MEMORY allowance; not a file/RSS bill.
LIMITS=dict(picoEmoteCaptureFileCapacityVersion=1,worldFileBytes=262144,
    modelFileBytes=262144,inventoryFileBytes=262144,storageReceiptFileBytes=100000,
    pendingMarkerFileBytes=1024)
OWNED=[]
UNRESOLVED=[]


def descriptor():return deepcopy(LIMITS)


class PicoEmoteStreamCapacity:
    def __init__(self,parent,roles,*,source_profile=None):
        need(type(parent) is PicoEmoteNativeCycle and type(roles) is dict and set(roles)=={'primary','actor'})
        parent.source.lock.assert_held();parent.bound()
        need(parent.previous is None and parent.state is None and not parent.source.frames and parent.inputs.previous is None)
        if source_profile is not None:
            from adapters.pico4.emote_source_transaction_profile import PicoEmoteSourceProfile
            need(type(source_profile) is PicoEmoteSourceProfile);source_profile.identity()
        self.source_profile=self._source_profile=source_profile
        self.parent=self._parent=parent;self.lock=self._lock=parent.source.lock;self.host=host_identity()
        self.source=self._source=parent.source;self.clock=self._clock=parent.source.monotonic
        self.path=self._path=parent.store.path.with_name(parent.store.path.name+'.child-stream-capacity.json')
        self.store=self._store=PrivateFeatureState(self.path)
        need(self.store.read() is None and not any(p.name.startswith(self.path.name+'.') for p in self.path.parent.iterdir()))
        self.roles=self._roles=tuple((role,dict(roles[role],binding=deepcopy(roles[role]['binding']))) for role in ('primary','actor'))
        for role,row in self.roles:
            exact(row,{'adapter','target','native','binding','phase','lock','subject'});context(row['binding'])
            need(row['adapter'].kind=='pico' and row['adapter'].profile['package']=='org.overte.pico'
                and type(row['target']) is str and row['target'] and row['phase'].run==parent.source.run
                and row['phase'].area=='emotes')
        self.role_pins=tuple(self.role_pin(role,row) for role,row in self.roles)
        self.identity=dict(picoEmoteStreamCapacityVersion=VERSION if source_profile is None else 2,parentIdentity=deepcopy(parent.identity),limits=descriptor(),
            roles={role:dict(targetBinding=deepcopy(row['binding'])) for role,row in self.roles})
        if source_profile is not None:self.identity['sourceProfileSha256']=source_profile.sha256
        self.identity_bytes=canonical(self.identity);self.descriptor_sha=json_digest(LIMITS)
        self.state=self._state=dict(phase='prepared',originalClocks=None,receipts=[],pngs=[])
        self._state_bytes=canonical(self.state);self.previous=None;self.failed=False;self.admission_stopped=False
        self._pending_png=();self._png_files=();self._pending_retirement=();self._retirements=()
        self.archive=self._archive=None;self.aggregate_bill=self._aggregate_bill=None
        self.file=self._file=object.__new__(LifecycleProcessFile)
        OWNED.append(self) # Retain BEFORE a constructor can acquire actual OFDs.
        try:LifecycleProcessFile.__init__(self.file,self.store);self.require()
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise

    @staticmethod
    def role_pin(role,row):
        native,adapter,phase=row['native'],row['adapter'],row['phase']
        return (role,row,adapter,adapter.adb,adapter.adb.execute_bytes,row['target'],native,
            native.send,native.clock_ms,native.guard,row['binding'],json_digest(row['binding']),
            phase,phase.client,phase.client.request,phase.fixture_url,phase.run,phase.area,phase.epoch_ms,phase.monotonic,
            row['lock'],row['lock'].path,row['subject'])

    def host_identity(self):
        # Issued raw returns need resource authority, not a live business clock
        # or a successful later capacity CAS. The raw owner checks its OWN OFDs.
        need(host_identity()==self.host and self.parent is self._parent and self.source is self._source
            and self.parent.source is self.source and self.lock is self._lock and self.source.lock is self.lock
            and same_callable(self.clock,self._clock) and same_callable(self.source.monotonic,self._clock)
            and self.path==self._path and self.store is self._store and self.store.path==self.path and self.file is self._file)

    def configs(self):
        need(self.roles is self._roles and len(self.roles)==len(self.role_pins)==2)
        for (role,row),pin in zip(self.roles,self.role_pins):
            need(role==pin[0] and row is pin[1]);exact(row,{'adapter','target','native','binding','phase','lock','subject'})
            adapter,native,phase=row['adapter'],row['native'],row['phase']
            need(adapter is pin[2] and adapter.adb is pin[3] and same_callable(adapter.adb.execute_bytes,pin[4])
                and row['target']==pin[5] and native is pin[6] and same_callable(native.send,pin[7])
                and same_callable(native.clock_ms,pin[8]) and same_callable(native.guard,pin[9])
                and row['binding'] is pin[10] and json_digest(row['binding'])==pin[11]
                and phase is pin[12] and phase.client is pin[13] and same_callable(phase.client.request,pin[14])
                and (phase.fixture_url,phase.run,phase.area)==pin[15:18]
                and same_callable(phase.epoch_ms,pin[18]) and same_callable(phase.monotonic,pin[19])
                and row['lock'] is pin[20] and row['lock'].path==pin[21] and row['subject']==pin[22])

    def resource_identity(self):
        # Passive current host proof used before Cycle acquires its locks.
        # This calls no SDK, Native, phase, source advancement or input.
        self.host_identity();need(not self.failed);self.configs()
        need(self.source_profile is self._source_profile)
        if self.source_profile is not None:
            self.source_profile.identity();need(self.identity['sourceProfileSha256']==self.source_profile.sha256)
        need(canonical(self.identity)==self.identity_bytes and self.identity['limits']==LIMITS
            and self.state is self._state and canonical(self.state)==self._state_bytes
            and self.archive is self._archive and same_callable(self.aggregate_bill,self._aggregate_bill)
            and self.descriptor_sha==json_digest(LIMITS))
        self.file.guard();require_directory(self.file.parent,self.path.parent);need(same(self.store.read(),self.previous))
        if self.state['originalClocks'] is not None:
            state=self.parent.state;need(state is not None and self.state['originalClocks']==[
                state['started'],state['epochMs'],state['hostEpochMs']])
        for index,owner in self._png_files:
            need(self.state['pngs'][index]['phase']=='accounted' and same(owner.read(),self.state['pngs'][index]['fileProof']))
        for witness in self._retirements:witness.require()
        return True

    def require(self):
        self.lock.assert_held();return self.resource_identity()

    def admission(self):
        self.require();need(not self.admission_stopped)
        if self.state['originalClocks'] is not None:
            start=self.state['originalClocks'][0];need(start<=self.clock()<start+120)
        return True

    def guard(self):
        self.admission();self.parent.bound();self.admission();return True

    def matches(self,parent,roles):
        self.require();need(parent is self.parent and type(roles) is dict and set(roles)=={'primary','actor'})
        for role,row in self.roles:
            other=roles[role];exact(other,set(row))
            need(all(other[key] is row[key] for key in ('adapter','native','phase','lock'))
                and all(other[key]==row[key] for key in ('target','subject')) and same(other['binding'],row['binding']))
        return True

    def limits(self):self.require();return descriptor()

    def extra_bill(self,state=None):
        self.require();state=self.state if state is None else state
        receipts=sum(row['phase']!='retired' for row in state['receipts'])
        pngs=[row for row in state['pngs'] if row['phase']=='reserved']
        native=2*(3*262144+1024)+receipts*100000
        # Fixed native files, shared pending markers, actual receipt files and
        # future actual PNG file copies. Metadata/CAS copies share this bill.
        value=dict(parts=8+receipts+len(pngs)+3,storedBytes=native+sum(row['bytes'] for row in pngs)+3*PART,
            decodedBytes=native+sum(row['bytes'] for row in pngs)+3*PART+3*len(canonical(state)))
        if self.source_profile is not None:
            extra=self.source_profile.extra_bill();value={key:value[key]+extra[key] for key in value}
        return value

    def bind_archive(self,archive,aggregate_bill):
        self.require();need(self.archive is None and type(archive) is AudioRawArchive and callable(aggregate_bill)
            and self.state['phase']=='active')
        # Called before AudioRawArchive.__init__, not by replacing its sealed
        # identity/bill callbacks after source or archive acquisition.
        need(not hasattr(archive,'state'))
        self.archive=self._archive=archive;self.aggregate_bill=self._aggregate_bill=aggregate_bill

    def admit(self,state):
        self.guard();current=self.extra_bill();candidate=self.extra_bill(state)
        if self.archive is None:
            need(self.state['phase']=='prepared' and candidate['parts']<=MAX_FRAMES
                and max(candidate['storedBytes'],candidate['decodedBytes'])<=MAX_RAW);return
        self.archive.verify();need(self.archive.path==self.path.with_name(self.parent.store.path.name+'.child-stream-raw.json')
            and type(self.archive.scope.get('picoEmoteStreamOriginalsVersion')) is int
            and self.archive.scope['picoEmoteStreamOriginalsVersion']==(2 if self.source_profile is None else 3)
            and self.archive.scope.get('captureCapacitySha256')==self.descriptor_sha
            and self.archive.scope.get('parentIdentitySha256')==json_digest(self.parent.identity))
        ours=self.archive.bill();whole=self.aggregate_bill();pending=self.archive.state['pending']
        need(type(whole) is dict and set(whole)=={'parts','storedBytes','decodedBytes'})
        reserved_parts=sum(row['parts'] for row in pending);reserved=sum(row['limit']+row['sideBytes'] for row in pending)
        need(whole['parts']-current['parts']+candidate['parts']+ours['parts']+reserved_parts<=MAX_FRAMES
            and whole['storedBytes']-current['storedBytes']+candidate['storedBytes']+ours['storedBytes']+reserved+3*PART<=MAX_RAW
            and whole['decodedBytes']-current['decodedBytes']+candidate['decodedBytes']+ours['decodedBytes']+reserved+3*PART<=MAX_RAW)
        self.archive.metadata_capacity(pending);self.guard()

    def transition(self,kind,state,witness=None):
        old=self.state;exact(state,set(old));need(old['phase'] in ('prepared','active'))
        if kind=='activate':
            need(old['phase']=='prepared' and state['phase']=='active' and not old['receipts'] and not state['receipts']
                and not old['pngs'] and not state['pngs'] and self.parent.state is not None
                and state['originalClocks']==[self.parent.state[key] for key in ('started','epochMs','hostEpochMs')])
            return
        need(old['phase']==state['phase']=='active' and same(old['originalClocks'],state['originalClocks']))
        if kind in ('receipt','png'):
            key='receipts' if kind=='receipt' else 'pngs';other='pngs' if kind=='receipt' else 'receipts'
            need(same(old[other],state[other]) and len(state[key])==len(old[key])+1 and same(old[key],state[key][:-1])
                and state[key][-1]['phase']=='reserved')
            row=state[key][-1];need(row['role'] in ('primary','actor'))
            if kind=='receipt':
                exact(row,{'role','command','phase','retirement'});storage_command(row['command']);need(row['retirement'] is None)
                need(not any(item['command']['commandId']==row['command']['commandId'] for item in old[key]))
            else:
                exact(row,{'role','request','bytes','sha256','phase','fileProof'})
                need(type(row['request']) is str and re.fullmatch('[0-9a-f]{32}',row['request'])
                    and integer(row['bytes'],1,NATIVE_PNG_LIMIT) and row['fileProof'] is None
                    and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256'])
                    and not any(item['request']==row['request'] for item in old[key]))
            return
        if kind=='retirement':
            from adapters.pico4.emote_stream_capacity_retirement import PicoEmoteCapacityRetirement
            need(type(witness) is PicoEmoteCapacityRetirement and any(item is witness for item in self._pending_retirement)
                and same(old['pngs'],state['pngs']) and len(old['receipts'])==len(state['receipts']))
            link=witness.require();changed=[]
            for index,(a,b) in enumerate(zip(old['receipts'],state['receipts'])):
                if same(a,b):continue
                need(a['phase']=='reserved' and b['phase']=='retired' and a['retirement'] is None and same(b['retirement'],link)
                    and a['role']==b['role']==witness.role and same(a['command'],b['command'])
                    and a['command']['requestId']==witness.request and a['command']['commandId'] in witness.receipts)
                changed.append(a['command']['commandId'])
            need(set(changed)==set(witness.receipts) and len(changed)==len(witness.receipts));return
        need(kind=='png-accounted' and type(witness) is PicoEmotePNGCapacity
            and any(owner is witness for owner in self._pending_png) and same(old['receipts'],state['receipts'])
            and len(old['pngs'])==len(state['pngs']))
        changes=[index for index,(a,b) in enumerate(zip(old['pngs'],state['pngs'])) if not same(a,b)]
        need(len(changes)==1);index=changes[0];a,b=old['pngs'][index],state['pngs'][index]
        need(a['phase']=='reserved' and b['phase']=='accounted' and a['fileProof'] is None and same(b['fileProof'],witness.read())
            and all(same(a[key],b[key]) for key in a if key not in ('phase','fileProof')))

    def _commit(self,kind,*,witness=None,**changes):
        self.require();state=deepcopy(self.state);state.update(deepcopy(changes));self.transition(kind,state,witness)
        try:self.admit(state)
        except BaseException:self.admission_stopped=True;raise
        value=dict(self.identity,payload=pack([state]))
        try:
            self.file.write(value,self.previous);need(same(self.store.read(),value))
            self.previous=deepcopy(value);self.state=self._state=state;self._state_bytes=canonical(state);self.require()
        except BaseException:
            self.failed=True
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            raise

    def activate(self):
        self.guard();state=self.parent.state
        need(self.state['phase']=='prepared' and state is not None and state['phase']=='baseline-issued'
            and state['baseline'] is None and not state['steps'] and not self.parent.source.frames)
        self._commit('activate',phase='active',originalClocks=[state['started'],state['epochMs'],state['hostEpochMs']])

    def ready(self):
        self.guard();need(self.archive is not None and self.state['phase']=='active');self.admit(self.state);return True

    def receipt(self,role,command):
        self.ready();storage_command(command);need(role in ('primary','actor'))
        rows=deepcopy(self.state['receipts']);need(not any(row['command']['commandId']==command['commandId'] for row in rows))
        rows.append(dict(role=role,command=deepcopy(command),phase='reserved',retirement=None))
        self._commit('receipt',receipts=rows);self.guard()

    def png(self,role,packet):
        self.ready();need(role in ('primary','actor'));binding=dict(self.roles)[role]['binding'];pid=int(binding['processIdentity'].split(':')[0])
        capture_packet(packet,packet.get('requestId'),pid,packet.get('capturedEpochMs'),stereo=True,require_cameras=True)
        image=packet['source']['image'];need(integer(image['bytes'],1,NATIVE_PNG_LIMIT))
        rows=deepcopy(self.state['pngs']);need(not any(row['request']==packet['requestId'] for row in rows))
        rows.append(dict(role=role,request=packet['requestId'],bytes=image['bytes'],sha256=image['sha256'],phase='reserved',fileProof=None))
        self._commit('png',pngs=rows);self.guard()

    def png_accounted(self,role,images,value):
        # This conservation transfer cannot invent a smaller image. The
        # future-copy reserve becomes an already-billed ACTUAL original file.
        self.guard();need(type(images) is GraphicsOriginals);image_record(value)
        binding=dict(self.roles)[role]['binding'];key=hashlib.sha256(canonical(binding)).hexdigest()[:16]
        root=self.parent.source.artifact_root
        need(images.root.parent==root and re.fullmatch('emote-remote-images-'+self.parent.source.run+'-'+key+r'-[1-9][0-9]{0,2}',images.root.name)
            and images.role==role and images.run==self.parent.source.run and same(images.binding,binding)
            and value['kind']=='image' and value['phase']=='saved')
        rows=deepcopy(self.state['pngs']);matches=[index for index,row in enumerate(rows)
            if row['role']==role and row['request']==value['capture']['requestId']]
        need(len(matches)==1);index=matches[0];row=rows[index]
        need(row['phase']=='reserved' and row['bytes']==value['bytes'] and row['sha256']==value['sha256'])
        original=images.read(value);need(len(original)==row['bytes'] and hashlib.sha256(original).hexdigest()==row['sha256'])
        owner=object.__new__(PicoEmotePNGCapacity);self._pending_png=(*self._pending_png,owner)
        try:
            PicoEmotePNGCapacity.__init__(owner,images,deepcopy(value),self.host_identity)
            row.update(phase='accounted',fileProof=owner.read());self.guard()
            self._commit('png-accounted',pngs=rows,witness=owner)
            self._png_files=(*self._png_files,(index,owner));self._pending_png=tuple(item for item in self._pending_png if item is not owner)
            self.guard()
        except BaseException:
            self.failed=True
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            raise

    def retired(self,capture):
        from adapters.pico4.emote_stream_capacity_retirement import PicoEmoteCapacityRetirement
        self.guard();witness=object.__new__(PicoEmoteCapacityRetirement)
        self._pending_retirement=(*self._pending_retirement,witness)
        try:
            PicoEmoteCapacityRetirement.__init__(witness,self,capture);link=witness.require()
            rows=deepcopy(self.state['receipts'])
            for row in rows:
                if row['role']==witness.role and row['command']['requestId']==witness.request:
                    need(row['phase']=='reserved');row.update(phase='retired',retirement=deepcopy(link))
            self._commit('retirement',receipts=rows,witness=witness)
            self._retirements=(*self._retirements,witness)
            self._pending_retirement=tuple(item for item in self._pending_retirement if item is not witness)
            self.guard()
        except BaseException:
            self.failed=True
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            raise

    def close_host(self):
        owners=[owner for index,owner in self._png_files]+list(self._pending_png)
        result=all([owner.close_host() for owner in owners]+[self._file.close_host()])
        if result and self in OWNED:OWNED.remove(self)
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
