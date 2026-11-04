"""One warm Source2 raw query owner in existing immutable chunks/bundles.

Explicit warm Parent composition; no default Scope1 change, cold live adoption
or settings restoration. Native/Qt execution remains a separate qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import threading
import time

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.snapshot_settings_codec import SnapshotSettingsCodec,WIRE_LIMIT,CANONICAL_LIMIT
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW

VERSION=2
NAME='snapshot-settings-query-originals.json'
UNRESOLVED=[]


def retained(adapter,target):
    """Pure-host Source2 ownership, including a failed pre-marker constructor."""
    if adapter.pico_configuration is None:return False
    need(type(target) is str and target)
    parent=adapter.pico_configuration[1]
    key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
    directory=parent/('feature-scripts-'+key);expected=directory/NAME
    for owner in UNRESOLVED:
        if type(owner) is SnapshotSettingsQueryOriginals:
            fields=vars(owner);path=fields.get('original_path');original_target=fields.get('original_target')
            if type(path) is type(expected) and type(original_target) is str and path==expected and original_target==target:return True
    try:info=directory.lstat()
    except FileNotFoundError:return False
    need(directory.is_absolute() and directory.resolve(strict=True)==directory
        and stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700)
    with os.scandir(directory) as entries:
        for index,entry in enumerate(entries):
            need(index<4096)
            if entry.name==NAME or entry.name.startswith((NAME+'.frame-',NAME+'.pending-')):return True
    return False


class SnapshotSettingsQueryOriginals:
    def __init__(self,base,target,*,actual_monotonic=time.monotonic):
        from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
        need(type(base) is PicoSnapshotCancelOwner and base.state is None and base.disk is None
            and base.snapshot.state is None and base.snapshot.ui.state is None and type(target) is str and target
            and callable(actual_monotonic))
        base.lock.assert_held()
        self.run,self.binding,self.lock=base.run,deepcopy(context(base.binding)),base.lock
        self.target=self.original_target=target
        self.path=self.original_path=self.lock.path.with_name(NAME);self.store=PrivateFeatureState(self.path)
        self.host,self.thread=host_identity(),threading.get_ident();self.real_clock=self.original_real_clock=actual_monotonic
        self.created_actual=self.real_clock();need(number(self.created_actual,0,1e15))
        self.scope=self.original_scope=dict(snapshotSettingsQueryOriginalsVersion=VERSION,runId=self.run,binding=self.binding,
            fixtureUrl=base.source.fixture_url,targetFingerprint=hashlib.sha256(target.encode()).hexdigest(),producerHostProcessIdentity=self.host)
        self.scope_bytes=self.original_scope_bytes=canonical(self.scope)
        self.file=self.original_file=object.__new__(LifecycleProcessFile)
        self.codec=self.original_codec=None;self.namespace=None;self.reader=self.original_reader=None
        self.state=None;self.children=self.original_children=[];self.failed=False;self.acquired=None;self.context=self.original_context=None
        self.pending_reader=self.pending_real=None;self.actual_anchor=None;self.last_reference=None
        self.history=ChatSourceChunks(self.store,self.scope)
        try:
            need(self.store.read() is None)
            with os.scandir(self.path.parent) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096 and not entry.name.startswith(NAME+'.'))
            LifecycleProcessFile.__init__(self.file,self.store)
            self._write(dict(self.scope,phase='reading',stage='codec-admitting',codec=None,queries=[],chunks=[],bundles=[],pending=None,pendingArchive=None))
            # The marker precedes codec construction. Unknown partial ownership
            # is visible to existing cleanup even without a baseline header.
            self.codec=self.original_codec=object.__new__(SnapshotSettingsCodec)
            SnapshotSettingsCodec.__init__(self.codec)
            from adapters.pico4.snapshot_settings_namespace import SnapshotSettingsNamespaceBill
            self.namespace=object.__new__(SnapshotSettingsNamespaceBill)
            SnapshotSettingsNamespaceBill.__init__(self.namespace,self)
            self._write(dict(self.state,stage='ready',codec=self.codec.public_profile()))
        except BaseException:self.poison();raise

    def poison(self):
        self.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def resource(self):
        need(self.host==host_identity() and self.thread==threading.get_ident()
            and self.real_clock is self.original_real_clock and self.path is self.original_path
            and self.target is self.original_target and type(self.target) is str
            and self.scope['targetFingerprint']==hashlib.sha256(self.target.encode()).hexdigest()
            and self.file is self.original_file and self.codec is self.original_codec
            and self.scope is self.original_scope and self.scope_bytes is self.original_scope_bytes
            and canonical(self.scope)==self.scope_bytes)
        self.lock.assert_held();self.file.guard()
        need(self.store.read()==self.state and self.children is self.original_children and type(self.children) is list)
        if self.state is not None:
            exact(self.state,set(self.scope)|{'phase','stage','codec','queries','chunks','bundles','pending','pendingArchive'})
            need(self.state['phase']=='reading' and self.state['stage'] in ('codec-admitting','ready','query-issued')
                and type(self.state['queries']) is list and len(self.state['queries'])<=34
                and type(self.state['chunks']) is list and len(self.state['chunks'])<=MAX_FRAMES
                and type(self.state['bundles']) is list and len(self.state['bundles'])<=MAX_FRAMES
                and all(type(self.state[key]) is type(value) and self.state[key]==value for key,value in self.scope.items()))

    def _write(self,value):
        need(self.file is self.original_file and self.host==host_identity() and self.thread==threading.get_ident())
        self.lock.assert_held();json_digest(value);need(len(canonical(value))+1<=65536)
        self.file.write(value,self.state);need(self.store.read()==value);self.state=deepcopy(value)

    def known_children(self):
        self.resource();need(len(self.children)==len(self.history.identities)==len(self.state['chunks']))
        rows=[]
        for index,original in enumerate(self.children):
            raw,physical=original.read();need(self.history.signature(index)==self.history.identities[index])
            rows.append((original.path,raw,physical))
        return rows

    def resource_bytes(self):
        # Count real already acquired bytes even after business/codec loss.
        need(self.acquired is None or type(self.acquired) is bytes)
        return (0 if self.acquired is None else len(self.acquired))+len(self.scope_bytes)

    def may_capture(self):
        # Only this original still-warm, never-issued root is exempt from the
        # generic retained namespace guard. No name-only or cold exemption.
        self.resource();need(self.failed is False and self.state['stage']=='ready'
            and not self.state['queries'] and not self.state['chunks'] and not self.children
            and self.state['pending'] is None and self.pending_reader is None)
        self.codec.verify()
        names=set()
        with os.scandir(self.path.parent) as entries:
            for index,entry in enumerate(entries):
                need(index<4096)
                if entry.name.startswith('snapshot-'):names.add(entry.name)
        return names=={self.path.name}

    def bind_reader(self,reader):
        need(self.reader is self.original_reader is None and self.state['stage']=='ready' and not self.state['queries'])
        self.reader=self.original_reader=reader

    def begin(self,context,command,anchor):
        self.resource();need(not self.failed and self.context is self.original_context is None
            and self.state['stage']=='ready' and self.state['pending'] is None and len(self.state['queries'])<34)
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        need(type(context) is PicoSnapshotSettingsScope2Baseline and context.raw is self and context.reader is self.reader and context.lock is self.lock
            and context.run==self.run and context.binding==self.binding)
        exact(command,{'schemaVersion','commandId','runId','action','settingsScope'})
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1
            and type(command['settingsScope']) is int and command['settingsScope']==2
            and command['action']=='feature-pico-snapshot-settings-originals'
            and command['runId']==self.run and type(command['commandId']) is str
            and len(command['commandId'])==32 and all(ch in '0123456789abcdef' for ch in command['commandId']))
        exact(anchor,{'hostMonotonic','nativeEpochMs','actualHostMonotonic'})
        need(number(anchor['hostMonotonic'],0,1e15) and integer(anchor['nativeEpochMs'],1)
            and number(anchor['actualHostMonotonic'],self.created_actual,self.created_actual+120))
        self.context=self.original_context=context;self.actual_anchor=deepcopy(anchor)
        query=dict(command=deepcopy(command),anchor=deepcopy(anchor),originals=[],status='issued',reservation=None,acceptedSha256=None)
        self._write(dict(self.state,stage='query-issued',queries=self.state['queries']+[query],pending=len(self.state['queries'])))
        self.fresh()

    def fresh(self):
        self.resource();need(not self.failed and self.context is self.original_context and self.context is not None)
        now=self.real_clock();anchor=self.actual_anchor
        need(number(now,anchor['actualHostMonotonic'],anchor['actualHostMonotonic']+1.5) and now<anchor['actualHostMonotonic']+1.5
            and number(now,self.created_actual,self.created_actual+120) and now<self.created_actual+120)
        self.codec.verify();self.context.source2_query_fence(anchor)
        finished=self.real_clock()
        need(number(finished,now,anchor['actualHostMonotonic']+1.5)
            and finished<anchor['actualHostMonotonic']+1.5 and finished<self.created_actual+120)

    def reserve_read(self):
        self.fresh();need(self.state['stage']=='query-issued' and self.pending_reader is None)
        query=self.state['queries'][self.state['pending']];need(len(query['originals'])<31)
        limits=self.codec.verify();bill=self.namespace.measure(self.context)
        need(bill['parts']+limits['parts']<=MAX_FRAMES
            and bill['decodedBytes']+bill['transientBytes']+limits['copies']<=MAX_RAW
            and bill['storedBytes']+limits['parts']*65536+3*65536<=MAX_RAW)
        # Complete prospective root/chunk/reference metadata, not only raw data.
        future=dict(self.state,chunks=self.state['chunks']+['f'*64]*limits['parts'],
            bundles=self.state['bundles']+[dict(parts=limits['parts'],bytes=CANONICAL_LIMIT,sha256='f'*64)])
        need(len(canonical(future))+2048<=65536)
        value=deepcopy(self.state);value['queries'][value['pending']]['reservation']=dict(attempt=len(query['originals']),parts=limits['parts'],copyBytes=limits['copies'],wireLimit=WIRE_LIMIT)
        self._write(value)
        token=object();self.pending_reader=token;self.pending_real=deepcopy(self.actual_anchor);self.fresh();return token

    def retain(self,token,raw):
        # No business clock/phase/source guard precedes actual acquired bytes.
        need(token is self.pending_reader and type(raw) is bytes)
        self.acquired=raw
        try:
            self.resource();need(len(raw)<=WIRE_LIMIT);self.codec.verify()
            query=self.state['queries'][self.state['pending']]
            record=dict(snapshotSettingsRawAttemptVersion=VERSION,query=self.state['pending'],attempt=len(query['originals']),
                bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode('ascii'))
            need(len(canonical(record))<=CANONICAL_LIMIT)
            index=len(self.state['bundles']);self.codec.verify()
            reference,parts=source_bundles.prepare(record,index,self.state['bundles']);self.codec.verify()
            need(len(parts)<=self.codec.limits[2])
            self._write(dict(self.state,pendingArchive=dict(bundle=index,reference=reference)))
            for number,part in enumerate(parts):
                self.resource();self.codec.verify();manifest=self.history.append(part,self.state['chunks']);self.codec.verify()
                path=self.history._path(len(manifest)-1);original=object.__new__(ClosedOriginalFile)
                self.children.append(original)
                ClosedOriginalFile.__init__(original,path,0o600,self.file.parent_guard)
                observed,physical=original.read();need(hashlib.sha256(canonical(self.history.store(len(manifest)-1).read())).hexdigest()==manifest[-1])
                value=deepcopy(self.state);value['chunks']=manifest
                if number==len(parts)-1:
                    value['bundles']=self.state['bundles']+[reference]
                    value['queries'][value['pending']]['originals'].append(index)
                    value['queries'][value['pending']]['reservation']=None;value['pendingArchive']=None
                self._write(value)
            self.pending_reader=self.pending_real=None;self.acquired=None
            self.last_reference=dict(snapshotSettingsRawReferenceVersion=VERSION,bundle=index,sha256=reference['sha256'])
            return deepcopy(self.last_reference)
        except BaseException:self.poison();raise

    def literal(self,reference):
        self.resource();self.codec.verify();exact(reference,{'snapshotSettingsRawReferenceVersion','bundle','sha256'})
        need(type(reference['snapshotSettingsRawReferenceVersion']) is int and reference['snapshotSettingsRawReferenceVersion']==VERSION)
        index=reference['bundle'];need(integer(index,0,len(self.state['bundles'])-1) and self.state['bundles'][index]['sha256']==reference['sha256'])
        value,raw=source_bundles.original(self.history,self.state['chunks'],self.state['bundles'],index);self.codec.verify()
        data=base64.b64decode(value['base64'],validate=True)
        need(base64.b64encode(data).decode()==value['base64'] and len(data)==value['bytes']
            and hashlib.sha256(data).hexdigest()==value['sha256']);return data

    def complete(self,reference,body_sha):
        self.fresh();need(self.pending_reader is None and self.last_reference==reference
            and type(body_sha) is str and len(body_sha)==64 and all(ch in '0123456789abcdef' for ch in body_sha))
        value=deepcopy(self.state);value['queries'][value['pending']]['status']='returned';value['queries'][value['pending']]['acceptedSha256']=body_sha;value.update(stage='ready',pending=None)
        self._write(value);self.fresh();self.context=self.original_context=None

    def close_host(self):
        if self.failed or self.state['pending'] is not None or self.pending_reader is not None or self.acquired is not None:return False
        self.resource()
        if any(not child.close() for child in self.children):self.poison();return False
        if not self.namespace.close_host() or not self.file.close_host() or not self.codec.close_host():self.poison();return False
        return True
