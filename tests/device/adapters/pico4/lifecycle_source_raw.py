"""Explicit SourceRaw4 pool over ONE original AudioRawArchive.

Background/Pending projections share reads, parts, original clocks and every
byte budget. A projection is provisional until its actual owner CAS is proved;
this pool deliberately supplies no public confirmation or cold-adoption API.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass
import os
import stat
import json
import hashlib

from adapters.native_feature_observation import LIMIT,exact,integer,need
from adapters.normal_feature_state import context
from adapters.chat_journey.source_chunks import json_digest
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundRaw3,LifecycleBackgroundRawHistory3
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.lifecycle_raw_ranges import BACKGROUND_ROLES,SOURCE_ROLES4,SOURCE_ROLES4_PENDING,PENDING_WIRE_LIMIT,verified_ranges,record_literal
from adapters.pico4.lifecycle_source import nonce
from adapters.script_journey.history import MAX_RAW,canonical

VERSION=4
REFERENCE={'lifecycleSourceRangeVersion','role','source','sha256'}
VIEW_ROLES={'background':BACKGROUND_ROLES,'pending':('ui','gesture','drive','pending')}


def scope(run,binding,*,pending_read_version=0):
    need(nonce(run) and type(pending_read_version) is int and pending_read_version in (0,1))
    result=dict(lifecycleSourceRawVersion=VERSION,runId=run,
        binding=deepcopy(context(binding)),role='lifecycle-source')
    if pending_read_version:result['pendingNativeReadVersion']=pending_read_version
    return result


def reference(scope_sha,record):
    return dict(lifecycleSourceRangeVersion=VERSION,role=record['role'],
        source=dict(audioRawRangeVersion=1,scopeSha256=scope_sha,
            read=record['read'],sha256=record['sha256']),sha256=record['sha256'])


def key(value):
    exact(value,REFERENCE);source=value['source']
    exact(source,{'audioRawRangeVersion','scopeSha256','read','sha256'})
    need(type(value['lifecycleSourceRangeVersion']) is int and value['lifecycleSourceRangeVersion']==VERSION
        and type(value['role']) is str and value['role'] in SOURCE_ROLES4 and type(source['audioRawRangeVersion']) is int
        and source['audioRawRangeVersion']==1 and integer(source['read'],0,511)
        and type(source['scopeSha256']) is str and len(source['scopeSha256'])==64
        and all(c in '0123456789abcdef' for c in source['scopeSha256'])
        and source['sha256']==value['sha256'] and type(value['sha256']) is str
        and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']))
    return value['role'],source['scopeSha256'],source['read'],value['sha256']


@dataclass(eq=False)
class LifecycleRangeProjection:
    view:object
    value:object
    encoded:object=None
    references:tuple=()
    peak:int=0
    failed:bool=False


class LifecycleSourceView4:
    """Warm, exact typed restriction; no owner facts arise from a raw receipt."""
    def __init__(self,bank,role):
        need(type(bank) is LifecycleSourceRaw4 and role in VIEW_ROLES)
        self.bank=self._bank=bank;self.role=self._role=role
        self.confirmed=self._confirmed=();self._seal=self._original_seal=(self.confirmed,2)
        self.pending=self._pending=None;self.held=self._held=[];self._held_seal=()

    def guard(self):
        need(self.bank is self._bank and self.role==self._role
            and type(self.role) is str and self._seal is self._original_seal
            and self.confirmed is self._confirmed is self._seal[0]
            and self.pending is self._pending and self.held is self._held
            and len(self.held)==len(self._held_seal)
            and all(row is saved[0] and row.value is saved[1] for row,saved in zip(self.held,self._held_seal))
            and (self.pending is None or self.pending in self.held and self.bank.pending_view is self.pending)
            and not self.bank.failed)
        for row in self.confirmed:
            if type(row) is tuple and len(row)==9:
                from adapters.pico4.lifecycle_pending_read import body_dto
                need(self.role=='pending' and self.bank.pending_read_version==1
                    and row[1]==self.bank.archive.scope_sha);body_dto(row)
            else:
                need(type(row) is tuple and len(row)==4 and row[0] in VIEW_ROLES[self.role]
                    and row[1]==self.bank.archive.scope_sha)

    def metadata_bytes(self):
        self.guard()
        # Retained projections are charged before copying/canonicalization.
        total=3*self._seal[1]
        for row in self.held:
            need(type(row) is LifecycleRangeProjection and row.view is self
                and integer(row.peak,0,MAX_RAW))
            size=4*canonical_size(row.value)+3*65536
            if row.encoded is not None:size=max(size,4*canonical_size(row.encoded)+3*65536)
            total+=max(size,row.peak)
        return total

    @property
    def manifest(self):
        self.guard();return self.reference_dtos(self.confirmed)

    def reference_dtos(self,rows):
        need(type(rows) is tuple);result=[]
        for row in rows:
            if type(row) is tuple and len(row)==9:
                from adapters.pico4.lifecycle_pending_read import body_dto
                need(self.role=='pending' and self.bank.pending_read_version==1)
                result.append(body_dto(row))
            else:
                need(type(row) is tuple and len(row)==4);role,scope,read,sha=row
                result.append(dict(lifecycleSourceRangeVersion=VERSION,role=role,
                    source=dict(audioRawRangeVersion=1,scopeSha256=scope,read=read,sha256=sha),sha256=sha))
        return result

    def confirm(self,gate,permit):
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4,FamilyPermit4
        need(type(gate) is LifecycleFamilyGate4 and type(permit) is FamilyPermit4
            and gate.raw is self.bank and gate.view is self and gate.pending is permit
            and permit.gate is gate and permit.writer is gate.writer and permit.committed
            and not permit.failed and self.bank.namespace._write is None
            and permit.projection is self.pending is self.bank.pending_view
            and permit.projection in self.held and gate.writer.disk==permit.root
            and permit.root['originalChunks']==self.reference_dtos(self.pending.references)
            and self.pending.references[:len(self.confirmed)]==self.confirmed)
        references=self.pending.references;size=canonical_size(self.reference_dtos(references))
        self.confirmed=self._confirmed=references;self._seal=self._original_seal=(references,size)
        self.held.remove(self.pending)
        self._held_seal=tuple(saved for saved in self._held_seal if saved[0] is not self.pending)
        self.pending=self._pending=None;self.bank.pending_view=self.bank._pending_view=None

    def project(self,value):
        bank=self.bank
        with bank.lock.held():
            # Hold the exact already-acquired graph BEFORE any guard/preflight
            # can fail. Failed reservation never discards it or admits input.
            projection=LifecycleRangeProjection(self,value);self.held.append(projection)
            self._held_seal=(*self._held_seal,(projection,value))
            try:
                self.guard();need(self.pending is None and bank.pending_view is None
                    and not bank.frozen)
                size=canonical_size(value)
                # Source DTO, encoded projection, canonical/pack work and one
                # complete root CAS coexist. This is additive to the ONE raw
                # journal and complete original namespace admission.
                if self.role=='pending' and bank.pending_read_version==1:
                    _size,encoded_bound,reference_work=bank.pending_projection_bound(value)
                    projection.peak=4*encoded_bound+3*65536+3*reference_work
                else:projection.peak=4*size+3*65536
                current=bank.other_bill();ours=bank.archive.bill()
                need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)
                by_read,records=bank.verify(materialize=True)
                by_digest={};body_digests={}
                for record in records.values():
                    if (record['kind']=='utf8' and record['role'] in VIEW_ROLES[self.role]
                            and not (self.role=='pending' and bank.pending_read_version==1 and record['role']=='pending')):
                        by_digest.setdefault(record['sha256'],reference(bank.archive.scope_sha,record))
                    elif self.role=='pending' and bank.pending_read_version==1 and record['role']=='pending-wire':
                        from adapters.pico4.lifecycle_pending_read import body_receipt,wire_extent
                        wire=by_read[record['read']]
                        if wire_extent(wire,record['command'].get('readNonce'))['status']!='complete':continue
                        ref,raw=body_receipt(wire,record,scope_sha=bank.archive.scope_sha,run=bank.run)
                        body_digests.setdefault((ref['sha256'],json_digest(record['command']['nativeRequest'])),ref)
                refs=list(self.confirmed)
                def encode(item,request_context=None):
                    if type(item) is dict:
                        if set(item)=={'raw','sha256'}:
                            need(type(item['raw']) is str and frame(item['raw'])==item)
                            if request_context is not None and self.role=='pending' and bank.pending_read_version==1:
                                from adapters.pico4.lifecycle_pending_read import body_key,body_original
                                lookup=(item['sha256'],json_digest(request_context));need(lookup in body_digests)
                                ref=body_digests[lookup];identity=body_key(ref)
                                need(body_original(by_read[identity[2]],ref,record=records[identity[2]],
                                    scope_sha=bank.archive.scope_sha,run=bank.run)==item['raw'])
                            else:
                                need(item['sha256'] in by_digest);ref=by_digest[item['sha256']];identity=key(ref)
                                need(by_read[identity[2]]==item['raw'].encode('utf-8'))
                            if identity not in refs:refs.append(identity)
                            return ref
                        need('lifecyclePendingBodyVersion' not in item)
                        context=None
                        if self.role=='pending' and bank.pending_read_version==1 and 'request' in item and 'original' in item:
                            from adapters.pending_commit_owner import command
                            context=command(item['request'])
                        return {name:encode(child,context if name=='original' else None) for name,child in item.items()}
                    if type(item) is list:return [encode(child) for child in item]
                    return deepcopy(item)
                projection.encoded=encode(value);projection.references=tuple(refs)
                if self.role=='pending' and bank.pending_read_version==1:
                    need(canonical_size(projection.encoded)<=encoded_bound)
                else:need(canonical_size(projection.encoded)<=size+4096*len(refs))
                self.pending=self._pending=projection;bank.pending_view=bank._pending_view=projection
                bank.verify();return projection
            except BaseException:
                projection.failed=True;bank.failed=True;raise


class LifecycleSourceRaw4(LifecycleBackgroundRaw3):
    version=VERSION
    roles=SOURCE_ROLES4

    def raw_scope(self,run,binding):
        self.profile_guard();return scope(run,binding,pending_read_version=self.pending_read_version)

    def profile_guard(self):
        need(self._profile is self._original_profile and type(self.pending_read_version) is int
            and self.pending_read_version==self._profile[0] and self.roles is self._profile[1]
            and self.roles is (SOURCE_ROLES4_PENDING if self.pending_read_version==1 else SOURCE_ROLES4))

    def __init__(self,path,run,binding,lock,identity,bill,clock,*,pending_read_version=0):
        need(type(pending_read_version) is int and pending_read_version in (0,1))
        self.pending_read_version=pending_read_version
        self.roles=SOURCE_ROLES4_PENDING if pending_read_version else SOURCE_ROLES4
        self._profile=self._original_profile=(pending_read_version,self.roles)
        self.pending_transport=self._pending_transport=None
        from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
        need(type(bill) is LifecycleNamespaceBill and bill.lock is lock and path.parent==bill.path
            and path.name=='lifecycle-background-raw.json' and type(self.version) is int and self.version==VERSION
            and self.roles is (SOURCE_ROLES4_PENDING if pending_read_version else SOURCE_ROLES4))
        self.views=self._views=();self.pending_view=self._pending_view=None;self.active_family=None
        self.families=self._families=()
        super().__init__(path,run,binding,lock,identity,bill,clock)
        self._write_gates=self.write_gates
        self.views=self._views=(LifecycleSourceView4(self,'background'),LifecycleSourceView4(self,'pending'))
        self.namespace.bind_expanded_guard(self)

    def literal_limit(self,role):
        return 32768 if role=='pending' else PENDING_WIRE_LIMIT if role=='pending-wire' else LIMIT

    def hook(self,reader,role):
        # Binary wires enter only through the exact one-time typed transport.
        need(role in SOURCE_ROLES4);return super().hook(reader,role)

    def bind_pending_transport(self,reader):
        from adapters.pico4.lifecycle_pending_read import PicoLifecyclePendingRead
        self.profile_guard()
        need(self.pending_read_version==1 and self.pending_transport is self._pending_transport is None
            and type(reader) is PicoLifecyclePendingRead and reader.bank is self and reader.archive is self.archive
            and reader.binding==self.binding and not reader.active and not reader.failed)
        self.pending_transport=self._pending_transport=reader

    def reserve_pending_wire(self,reader,description,*,side_bytes):
        self.profile_guard();need(reader is self.pending_transport is self._pending_transport
            and self.pending_read_version==1 and reader.bank is self and reader.archive is self.archive)
        self.verify();current=self.archive.bill()['literalBytes']
        token=self.archive.reserve('pending-wire',description,PENDING_WIRE_LIMIT,side_bytes=side_bytes)
        self.maximum_literal=max(self.maximum_literal,current+token['limit']);return token

    def view(self,role):
        need(self.views is self._views and role in VIEW_ROLES)
        return self.views[0 if role=='background' else 1]

    def view_bytes(self):
        need(self.views is self._views)
        return sum(view.metadata_bytes() for view in self.views)

    @property
    def manifest(self):return [] if not self.views else self.view('background').manifest

    def current_bill(self):
        if self.active_family is not None:return self.active_family.read_bill()
        return super().current_bill()

    def guard_namespace(self):
        if self.active_family is not None:return self.active_family.guard_namespace()
        return super().guard_namespace()

    def save_background(self,writer,value):
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        gate=self.write_gates.get('background')
        if gate is None:
            gate=LifecycleFamilyGate4(self,writer);self.write_gates['background']=gate
            self.families=self._families=(*self.families,('background',gate))
        need(type(gate) is LifecycleFamilyGate4 and gate.writer is writer)
        return gate.save(value)

    def check_hooks(self):
        self.profile_guard();need(self.pending_transport is self._pending_transport)
        if self.pending_transport is not None:
            need(self.pending_read_version==1 and not self.pending_transport.failed and self.pending_transport.bank is self
                and self.pending_transport.archive is self.archive)
        need(self.write_gates is self._write_gates and self.families is self._families)
        for role,gate in self.families:need(self.write_gates.get(role) is gate and gate.raw is self)
        return super().check_hooks()

    def expanded_owner_states(self):
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        self.check_hooks();result=[]
        for role,gate in self.families:
            need(type(gate) is LifecycleFamilyGate4 and gate.raw is self and gate.writer.originals is self)
            if gate.writer.state is None:need(gate.writer.disk is None)
            else:result.append(gate.writer.state)
        return result or None

    def require_expanded(self,value,size):
        # Namespace supplies its SAME actual callback result only after the
        # complete canonical size preflight, before a large output/decoder.
        need(integer(size,0,MAX_RAW))
        wanted=self.expanded_owner_states()
        if wanted is None:return
        found=[False]*len(wanted);visits=0
        def visit(item):
            nonlocal visits
            visits+=1;need(visits<=size+1)
            for index,target in enumerate(wanted):
                if item is target:found[index]=True
            if all(found):return
            if type(item) is dict:
                for child in item.values():
                    visit(child)
                    if all(found):break
            elif type(item) is list:
                for child in item:
                    visit(child)
                    if all(found):break
        visit(value);need(all(found))

    def pending_projection_bound(self,value):
        from adapters.pico4.lifecycle_pending_read import body_dto
        size=canonical_size(value);count=0
        def visit(item):
            nonlocal count
            if type(item) is dict:
                if set(item)=={'raw','sha256'}:count+=1
                else:
                    for child in item.values():visit(child)
            elif type(item) is list:
                for child in item:visit(child)
        visit(value)
        maximum=canonical_size(body_dto(('pending-body','f'*64,511,'f'*64,'f'*32,'f'*32,
            PENDING_WIRE_LIMIT,32768,'f'*64)))
        wire_records=sum(1 for page in self.archive.pages.values() for record in page['receipts']
            if record is not None and record['role']=='pending-wire')
        return size,size+count*maximum,wire_records*maximum

    def transport_bytes(self):
        return 0 if self.pending_transport is None else self.pending_transport.metadata_bytes()

    def metadata_capacity(self):return super().metadata_capacity()+self.view_bytes()+self.transport_bytes()

    def other_bill(self):
        result=super().other_bill();result['decodedBytes']+=self.view_bytes()+self.transport_bytes()
        need(result['decodedBytes']<=MAX_RAW);return result

    def _verify(self,*,materialize):
        self.verify_before_batch(materialize=materialize)
        need(type(self.version) is int and self.version==VERSION and self.roles is self._profile[1]
            and self.references==[] and self.views is self._views and self.pending_view is self._pending_view)
        pending_bodies=()
        if self.pending_read_version==1:
            from adapters.pico4.lifecycle_pending_read import body_dto
            pending_bodies=tuple(body_dto(identity) for identity in self.view('pending').confirmed if len(identity)==9)
        result=verified_ranges(self.archive,roles=self.roles,materialize=materialize,pending_bodies=pending_bodies)
        for view in self.views:
            view.guard()
            for identity in view.confirmed:
                if len(identity)==9:continue # The SAME verified literal pass just validated its complete body identity.
                role,scope,read,sha=identity
                need(read in result[1]);record=result[1][read]
                need(record['kind']=='utf8' and record['role']==role and record['sha256']==sha)
        self.archive.verify();return result

    def query_gate(self,*args,**kwargs):
        # No acquisition may enter while an owner projection/CAS is pending.
        need(self.pending_view is None and self.active_family is None)
        if self.pending_transport is not None:self.pending_transport.host_bindings()
        return super().query_gate(*args,**kwargs)

    def encode(self,value):need(False)
    def decode(self,value,*,role='background'):
        need(type(role) is str and role in VIEW_ROLES)
        with self.lock.held():
            size=canonical_size(value)
            current=self.other_bill();need(current['decodedBytes']+self.archive.bill()['decodedBytes']+3*size<=MAX_RAW)
            by_read,records=self.verify(materialize=True);view=self.view(role)
            if role=='pending' and self.pending_read_version==1:
                from adapters.pico4.lifecycle_pending_read import body_key,body_original
                expanded=size
                def measure(item):
                    nonlocal expanded
                    if type(item) is dict:
                        need(set(item)!={'raw','sha256'})
                        if 'lifecyclePendingBodyVersion' in item:
                            identity=body_key(item);need(identity in view.confirmed)
                            restored=frame(body_original(by_read[identity[2]],item,record=records[identity[2]],
                                scope_sha=self.archive.scope_sha,run=self.run))
                            expanded+=canonical_size(restored)-canonical_size(item)
                        elif set(item)==REFERENCE:
                            identity=key(item);need(identity in view.confirmed)
                            expanded+=canonical_size(frame(by_read[identity[2]].decode('utf-8')))-canonical_size(item)
                        else:
                            for child in item.values():measure(child)
                    elif type(item) is list:
                        for child in item:measure(child)
                measure(value)
                need(current['decodedBytes']+self.archive.bill()['decodedBytes']+3*expanded<=MAX_RAW)
            def decode(item):
                if type(item) is dict:
                    need(set(item)!={'raw','sha256'})
                    if 'lifecyclePendingBodyVersion' in item:
                        from adapters.pico4.lifecycle_pending_read import body_key,body_original
                        need(role=='pending' and self.pending_read_version==1)
                        identity=body_key(item);need(identity in view.confirmed)
                        return frame(body_original(by_read[identity[2]],item,record=records[identity[2]],
                            scope_sha=self.archive.scope_sha,run=self.run))
                    if set(item)==REFERENCE:
                        identity=key(item);need(identity in view.confirmed)
                        return frame(by_read[identity[2]].decode('utf-8'))
                    return {name:decode(child) for name,child in item.items()}
                if type(item) is list:return [decode(child) for child in item]
                return deepcopy(item)
            return decode(value)

    def close_host(self):
        closed=super().close_host()
        if self.pending_view is not None or any(view._held_seal for view in self._views):
            from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
            if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((self.path.parent,self))
            return False
        return closed


class LifecycleSourceRawHistory4(LifecycleBackgroundRawHistory3):
    """Passive ranges, never a live view or an acknowledged owner-CAS proof."""
    version=VERSION
    reference_fields=REFERENCE

    def expected_scope(self,run,binding):
        return scope(run,binding,pending_read_version=self._pending_profile[0])

    def __init__(self,path,run,binding,references,*,role,pending_read_version=0):
        need(type(pending_read_version) is int and pending_read_version in (0,1))
        self._pending_profile=self._original_pending_profile=(pending_read_version,
            SOURCE_ROLES4_PENDING if pending_read_version else SOURCE_ROLES4)
        need(type(role) is str and role in VIEW_ROLES and type(references) is list and len(references)<=512)
        self.role=role;self._cache_seal=self._original_cache_seal=None
        # Full actual raw namespace BEFORE reused passive page/part readers.
        # Include unknown tails; none can be removed or made a live receipt.
        names=[];stored=0;physical={}
        from adapters.chat_journey.archive_file import signature
        for index,child in enumerate(path.parent.iterdir()):
            need(index<4096)
            if child.name!=path.name and not child.name.startswith(path.name+'.'):continue
            info=child.lstat();need(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) in (0o400,0o600)
                and info.st_uid==os.geteuid() and info.st_nlink==1 and 0<=info.st_size<=65536)
            names.append(child.name);physical[child.name]=tuple(signature(info));stored+=info.st_size
        need(path.name in names and len(names)<=530 and 3*stored+4*LIMIT+3*65536<=MAX_RAW)
        if pending_read_version:
            need(3*stored+3*canonical_size(references)+4*LIMIT+3*65536<=MAX_RAW)
            from adapters.pico4.lifecycle_pending_read import body_key
            body_reads=set()
            for reference in references:
                if type(reference) is dict and 'lifecyclePendingBodyVersion' in reference:
                    identity=body_key(reference);need(role=='pending' and identity[2] not in body_reads)
                    body_reads.add(identity[2])
        self._physical_bill=self._original_physical_bill=(tuple(sorted(physical.items())),stored)
        super().__init__(path,run,binding,references)
        try:
            need(set(names)=={child.name for child in path.parent.iterdir()
                if child.name==path.name or child.name.startswith(path.name+'.')})
            for name,pin in physical.items():need(tuple(signature((path.parent/name).lstat()))==pin)
            state=self.archive.state;exact(state,{'reads','pending','parts','pages'})
            need(integer(state['reads'],0,512) and type(state['pending']) is list and len(state['pending'])<=512
                and type(state['parts']) is list and len(state['parts'])<=512
                and type(state['pages']) is list and len(state['pages'])<=16)
            for name,source in self.archive.files.items():
                if '.index-' in name:
                    raw,_stamp=source.read();need(canonical(json.loads(raw))+b'\n'==raw)
            for read,record in self.archive.receipts.items():
                need(integer(read,0,state['reads']-1))
                record_literal(record,index=read,roles=self._pending_profile[1],parts=self.archive.recorded_parts)
            metadata=self.cache_value();size=canonical_size(metadata)
            need(3*stored+2*size+4*LIMIT+3*65536<=MAX_RAW)
            self._cache_seal=self._original_cache_seal=(size,json_digest(metadata))
            self.verify()
        except BaseException:
            from adapters.pico4.lifecycle_background_raw_state import close_or_retain
            close_or_retain(path.parent,self);raise

    @property
    def stored_bytes(self):
        need(self._physical_bill is self._original_physical_bill)
        return self._physical_bill[1]

    def cache_value(self):
        need(self._pending_profile is self._original_pending_profile)
        archive=self.archive
        need(type(archive.disk) is dict and archive.state is archive.disk['state']
            and type(archive.receipts) is dict and len(archive.receipts)<=512
            and all(integer(read,0,511) for read in archive.receipts)
            and type(archive.recorded_parts) is list and len(archive.recorded_parts)<=512
            and all(type(part) is bytes and len(part)<=65536 for part in archive.recorded_parts)
            and type(archive.uncertain) is list and len(archive.uncertain)<=530
            and type(archive.pending) is bool and type(self.references) is list and len(self.references)<=512)
        return dict(disk=archive.disk,scopeSha256=archive.scope_sha,
            receipts=[[read,record] for read,record in sorted(archive.receipts.items())],
            parts=[[len(part),hashlib.sha256(part).hexdigest()] for part in archive.recorded_parts],
            uncertain=archive.uncertain,pending=archive.pending,references=self.references)

    def base_cost(self):
        need(self._cache_seal is self._original_cache_seal and self._cache_seal is not None)
        return 3*self.stored_bytes+2*self._cache_seal[0]+4*LIMIT+3*65536

    def verify(self):
        from adapters.chat_journey.archive_file import signature
        self.archive.guard();need(self._physical_bill is self._original_physical_bill)
        pins,stored=self._physical_bill;names=[]
        for index,path in enumerate(self.archive.path.parent.iterdir()):
            need(index<4096)
            if path.name==self.archive.path.name or path.name.startswith(self.archive.path.name+'.'):names.append(path.name)
        need(tuple(sorted(names))==tuple(name for name,pin in pins))
        for name,pin in pins:need(tuple(signature((self.archive.path.parent/name).lstat()))==pin)
        need(self.base_cost()<=MAX_RAW);metadata=self.cache_value()
        need(canonical_size(metadata,self._cache_seal[0])==self._cache_seal[0]
            and json_digest(metadata)==self._cache_seal[1])
        super().verify()

    def resolve(self,value):
        if self._cache_seal is not None:self.verify()
        return self.resolve_verified(value)

    def resolve_verified(self,value):
        need(type(value) is dict)
        if 'lifecyclePendingBodyVersion' in value:
            from adapters.pico4.lifecycle_pending_read import body_key,body_original
            need(self._pending_profile[0]==1 and self.role=='pending')
            identity=body_key(value);read=identity[2]
            need(identity[1]==self.archive.scope_sha and read in self.archive.receipts)
            wire=self.archive.literal(value['wireOriginal'])
            need(type(wire) is bytes)
            raw=body_original(wire,value,record=self.archive.receipts[read],scope_sha=self.archive.scope_sha,run=self.archive.disk['scope']['runId'])
            return frame(raw)
        role,scope_sha,read,sha=key(value)
        need(role in VIEW_ROLES[self.role] and scope_sha==self.archive.scope_sha
            and read in self.archive.receipts)
        record=self.archive.receipts[read]
        need(record['role']==role and record['kind']=='utf8' and record['sha256']==sha
            and integer(record['bytes'],0,32768 if role=='pending' else LIMIT))
        raw=self.archive.literal(value['source']);need(type(raw) is str)
        result=frame(raw);need(result['sha256']==sha);return result

    def decoder_budget(self,payload):
        exact(payload,{'encoding','bytes','sha256','data'})
        need(integer(payload['bytes'],2,MAX_RAW)
            and self.base_cost()+3*payload['bytes']<=MAX_RAW)

    def guard_value(self,value,seal):
        need(type(seal) is tuple and len(seal)==3 and value is seal[0]
            and canonical_size(value,seal[1])==seal[1] and self.base_cost()+3*seal[1]<=MAX_RAW
            and json_digest(value)==seal[2])

    def decode(self,value):
        self.verify();size=canonical_size(value)
        def expanded(item):
            nonlocal size
            if type(item) is dict:
                need(set(item)!={'raw','sha256'})
                if set(item)==REFERENCE or 'lifecyclePendingBodyVersion' in item:
                    need(item in self.references)
                    size+=canonical_size(self.resolve_verified(item))-canonical_size(item)
                    need(self.base_cost()+3*size<=MAX_RAW)
                else:
                    for child in item.values():expanded(child)
            elif type(item) is list:
                for child in item:expanded(child)
        need(self.base_cost()+3*size<=MAX_RAW)
        expanded(value)
        def decode(item):
            if type(item) is dict:
                if set(item)==REFERENCE or 'lifecyclePendingBodyVersion' in item:return self.resolve_verified(item)
                return {name:decode(child) for name,child in item.items()}
            if type(item) is list:return [decode(child) for child in item]
            return deepcopy(item)
        result=decode(value);self.verify();return result

    def report(self):
        self.verify();return dict(self.archive.report(),lifecycleSourceRawVersion=VERSION,viewRole=self.role,
            ownerCASAcknowledgementKnown=False)
