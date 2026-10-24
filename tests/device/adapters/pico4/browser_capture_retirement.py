"""Durable complete-history capture absence before browser archival.

This warm owner retains every source, PNG and query intent. It does not unlink
journals or grant a whole feature/host-close receipt.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
import hashlib
import json
import math

from adapters.chat_journey.archive_file import signature,ClosedOriginalFile
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.graphics_journey.samples import retirement
from adapters.native_feature_observation import fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_stereo import original_name
from adapters.script_journey.history import canonical,same,unpack

VERSION=1


class PicoBrowserCaptureRetirement:
    """One warm transaction, cached by its actual parent before admission."""
    def __init__(self,primary,actor):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        need(type(primary) is type(actor) is PicoTabletWebFeature and primary is not actor
            and primary.role=='primary' and actor.role=='actor' and primary.store.path==actor.store.path
            and primary.run==actor.run and primary.fixture_url==actor.fixture_url
            and primary.artifact_root==actor.artifact_root and primary.lock.path==actor.lock.path
            and primary.source.client is not actor.source.client)
        self.initialize(primary,actor,'pico-tablet-web-capture-retirement.json')

    def initialize(self,primary,actor,filename):
        self.primary,self.actor=primary,actor
        self.store=PrivateFeatureState(primary.store.path.with_name(filename))
        self.catalog=ChatArchiveCatalog(hold_files=False)
        self.previous=None;self.started=self.failed=self.completed=False
        self.proofs=[];self.frames=();self.reader=self.chunks=None;self.initialize_pngs()
        self.scope=self.admitted=self._sealed_admitted=self.completed_root=self.stamp=None
        self.copying_catalog=False;self.catalog_rows=self._sealed_catalog_rows=None
        self.indexed_rows=self._sealed_indexed_rows=None

    def initialize_pngs(self):
        self._png_bytes=self._sealed_png_bytes=b'[]'
        self._png_sha=self._sealed_png_sha=hashlib.sha256(self._png_bytes).hexdigest()
        self._png_windows=self._sealed_png_windows=()

    def immutable_pngs(self):
        need(self._png_bytes is self._sealed_png_bytes and type(self._png_bytes) is bytes
            and self._png_sha is self._sealed_png_sha and type(self._png_sha) is str
            and self._png_windows is self._sealed_png_windows and type(self._png_windows) is tuple)

    @property
    def pngs(self):
        self.immutable_pngs();return json.loads(self._png_bytes)

    def append_png(self,row):
        # Only actual admitted capture originals enter this warm inventory.
        # Keep the entire original JSON, while the physical reader needs only
        # its name, byte count, hash, inode and complete original stamp.
        self.immutable_pngs();need(self.admitted is None and self.reader is None and self.previous is None)
        json_digest(row);value=row['value'];stamp=tuple(row['stamp'])
        need(len(stamp)==8 and all(type(part) is int for part in stamp)
            and type(value['name']) is str and bool(value['name']) and '/' not in value['name'] and '\\' not in value['name']
            and integer(value['bytes'],1) and type(value['sha256']) is str and len(value['sha256'])==64
            and all(part in '0123456789abcdef' for part in value['sha256'])
            and integer(value['file']['device']) and integer(value['file']['inode'],1)
            and all(window[0]!=value['name'] for window in self._png_windows))
        window=(value['name'],value['bytes'],value['sha256'],value['file']['device'],value['file']['inode'],stamp)
        raw=canonical(row);prefix=b'[' if not self._png_windows else self._png_bytes[:-1]+b','
        self._png_bytes=self._sealed_png_bytes=prefix+raw+b']'
        self._png_sha=self._sealed_png_sha=hashlib.sha256(self._png_bytes).hexdigest()
        self._png_windows=self._sealed_png_windows=self._png_windows+(window,)

    def original_png_windows(self):
        self.immutable_pngs()
        return self._png_sha,tuple((dict(name=name,bytes=size,sha256=sha,file=dict(device=device,inode=inode)),list(stamp))
            for name,size,sha,device,inode,stamp in self._png_windows)

    def add(self,store,value,role):
        need(value is not None)
        for row in self.catalog.rows.values():
            if row['store'].path==store.path:
                need(same(row['expected'],value));self.catalog.verify(row);return
        self.catalog.add(('primary/' if role=='primary' else 'peer/')+store.path.name,store,value)

    def graph(self,owner,role):
        self.add(owner.store,owner.disk if hasattr(owner,'disk') else owner.previous,role)
        chunks=owner.chunks;chunks.verify()
        for index in range(len(chunks.identities)):
            child=chunks.store(index);self.add(child,child.read(),role)

    def role(self,flow):
        with flow.lock.held():
            owner=flow.owner();state=flow.role_state()
            need(owner is not None and owner['phase']=='cleaned' and owner['scriptUrl'] is not None
                and flow.manager_store().read() is None and state['quiet'] is not None and state['quiet']['complete']
                and state['native']['source']['retired'] and state['phase']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={})
                and (flow.role!='actor' or state['publication'] is not None and state['publication']['phase']=='accepted'))
            history=flow.source_history(owner);history.matches(state);vm=flow.vm_reader(owner);vm.verify()
            need(history.disk['phase']=='ready' and history.disk['intent'] is None and vm.previous['phase']=='ready')
            need(vm.quiet(math.ceil(state['phase']['activations'][-1]['activatedEpochMs'])))
            if self.scope is None:
                self.binding=deepcopy(owner['binding']);self.owner=deepcopy(owner)
            else:need(same(owner,self.owner))
            self.add(flow.store,flow.originals[flow.store.path],flow.role)
            self.add(flow.role_store,flow.originals[flow.role_store.path],flow.role)
            self.graph(history,flow.role);self.graph(vm,flow.role)
            quiet=flow.cleanup_window(owner);quiet.verify();need(quiet.value['complete']);self.graph(quiet,flow.role)
            # The current role list cannot silently omit an older successful
            # acquisition. Derive the complete manifest from every admitted
            # original sample, including the independent actor's samples.
            historical={}
            for entry in history.rows:
                if entry['event']!='sample':continue
                artifacts=entry['original']['sample']['artifacts']
                if not artifacts:continue
                need(len(artifacts)==2 and {item['kind'] for item in artifacts}=={'image','file'})
                metadata=next(item['name'] for item in artifacts if item['kind']=='file')
                png=next(item['name'] for item in artifacts if item['kind']=='image')
                need(metadata not in historical);historical[metadata]=png
            need(set(historical)=={original_name(flow.run,flow.role,image['journalId']) for image in state['images']})
            flow.verify_images(state,flow.role)
            for image in state['images']:
                need(image['phase']=='saved')
                name=original_name(flow.run,flow.role,image['journalId']);raw=flow.metadata(name,image['metadata'])
                record=json.loads(raw);rows=unpack(record['payload']);need(len(rows)==1 and rows[0]['phase']=='complete')
                original=rows[0];proof=original['proof'];retirement(proof,proof['owner'],
                    int(self.binding['processIdentity'].split(':',1)[0]),self.binding,flow.role)
                need(original['captureIntent']==proof['owner']['capture'] and original['ticket']==image['ticket']
                    and original['image']['name']==historical[name])
                self.proofs.append(deepcopy(proof));self.add(PrivateFeatureState(flow.artifact_root/name),record,flow.role)
                png=deepcopy(original['image']);_bytes,stamp=flow.original_image(png)
                self.append_png(dict(role=flow.role,value=png,stamp=stamp))
            return owner,state

    def inventory(self):
        expected={row['store'].path for row in self.catalog.rows.values()}
        parent=self.primary.store.path.parent
        actual={path for path in parent.iterdir() if path.name.startswith('pico-tablet-web-')
            and path!=self.store.path and not path.name.startswith(self.store.path.name+'.frame-')}
        need(actual=={path for path in expected if path.parent==parent})
        artifacts=self.primary.artifact_root
        metadata={path for path in artifacts.iterdir() if path.name.startswith('tablet-web-'+self.primary.run+'-')}
        need(metadata=={path for path in expected if path.parent==artifacts})
        pngs={path.name for path in artifacts.iterdir() if path.name.startswith('graphics-'+self.primary.run+'-')}
        need(pngs=={row['value']['name'] for row in self.pngs})

    def admission(self):
        return dict(scope=self.scope,proofs=self.proofs,pngs=self.pngs,owner=self.owner,
            catalog=[dict(label=label,path=str(row['store'].path),stamp=row['stamp'],sha256=row['sha256'])
                for label,row in self.catalog.rows.items()])

    def originals(self):
        self.primary.lock.assert_held();self.physical()

    def physical_index(self):
        """Immutable historical inventory between complete query-boundary reads.

        This does not validate or cache a native answer. Each query still has
        complete original byte windows before send, after its answer and after
        the real outer lock exit. Host-only CAS operations check every original
        identity/stamp, held directory, namespace and sealed in-memory DTO.
        """
        need(self.admitted is self._sealed_admitted and canonical(self.admission())==self.admitted
            and self.indexed_rows is self._sealed_indexed_rows and type(self.indexed_rows) is tuple
            and len(self.indexed_rows)==len(self.catalog.rows) and not self.catalog.failed)
        for parent in self.catalog.parents:self.catalog.verify_parent(parent)
        for (label,row),frozen in zip(self.catalog.rows.items(),self.indexed_rows):
            name,path,owner,raw,stamp,expected_sha=frozen
            need(label==name and row['store'].path==path and row['owner'] is owner
                and type(owner) is ClosedOriginalFile and not owner.failed and owner.active is None
                and owner.path==path and row['raw'] is raw and owner.raw is raw
                and row['stamp']==owner.stamp==list(stamp)==signature(path.lstat())
                and json_digest(row['expected'])==expected_sha)
        for row in self.pngs:
            need(signature((self.primary.artifact_root/row['value']['name']).lstat())==list(row['stamp']))
        self.inventory()
        if self.chunks is not None:
            self.chunks.verify();need(same(self.store.read(),self.previous))
        if self.completed_root is not None:need(canonical(self.previous)==self.completed_root)
        for parent in self.catalog.parents:self.catalog.verify_parent(parent)

    def physical(self):
        need(self.admitted is self._sealed_admitted and canonical(self.admission())==self.admitted)
        # One full byte pass lies between complete physical inventories. A
        # second immediate reread of every historical JSON adds no new native
        # observation; changed paths/stamps/DTOs still refuse at either end.
        self.physical_index();self.catalog.verify_all()
        for row in self.pngs:self.primary._original_image_bytes(row['value'],expected=row['stamp'])
        self.physical_index()

    def write(self,phase,chunks,*,pending=None,complete=False):
        need(type(self.copying_catalog) is bool)
        if self.copying_catalog:
            need(phase in ('reading','admitting') and pending is None and complete is False)
            self.catalog_copy_fence()
        else:
            self.primary.lock.assert_held();self.physical_index()
        value={**self.scope,'phase':phase,'chunks':deepcopy(chunks),
            'pending':deepcopy(pending),'complete':complete}
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def append(self,row,phase,*,complete=False):
        if self.previous['phase']!='reading':self.write('reading',self.previous['chunks'])
        json_digest(row);chunks=self.chunks.append(row,self.previous['chunks'])
        self.write(phase,chunks,complete=complete)

    def catalog_copy_fence(self):
        """Only immutable host copies, between two complete byte passes.

        No capture reader exists in this interval. Every original physical
        stamp, path, directory and namespace remains checked at each CAS;
        full source/PNG bytes are checked again before publishing ready.
        """
        self.primary.lock.assert_held()
        need(self.copying_catalog is True and self.reader is None and not self.frames
            and self.catalog_rows is self._sealed_catalog_rows and type(self.catalog_rows) is tuple
            and self.admitted is self._sealed_admitted and canonical(self.admission())==self.admitted
            and self.previous is not None and self.previous['phase'] in ('admitting','reading')
            and self.previous['pending'] is None and self.previous['complete'] is False)
        for parent in self.catalog.parents:self.catalog.verify_parent(parent)
        for row in self.catalog.rows.values():
            owner=row['owner']
            need(type(owner) is ClosedOriginalFile and not owner.failed and owner.active is None
                and owner.path==row['store'].path and type(row['raw']) is bytes and owner.raw is row['raw']
                and owner.stamp==row['stamp']==signature(row['store'].path.lstat()))
        for row in self.pngs:
            need(signature((self.primary.artifact_root/row['value']['name']).lstat())==list(row['stamp']))
        self.inventory();self.chunks.verify();need(same(self.store.read(),self.previous))
        for parent in self.catalog.parents:self.catalog.verify_parent(parent)

    def clocks(self,started,epoch_started,epochs):
        flow=self.primary;measured=flow.monotonic();epoch=flow.source.epoch_ms();ended=flow.monotonic()
        need(number(measured,started,started+1.5) and number(ended,measured,started+1.5)
            and ended-started<1.5 and integer(epoch,epoch_started))
        for captured in epochs:
            fresh(captured,epoch)
            need(max(epoch-captured,epoch_started-captured+math.ceil((ended-started)*1000),
                epoch-captured+math.ceil((ended-measured)*1000))<1500)

    def admit(self):
        actor=self.actor.actor_retirement
        need(actor is not None and actor.flow is self.actor)
        actor_receipt=actor.receipt() # Outside the parent's distinct same-inode OS lock.
        need(self.store.read() is None)
        primary_owner,_primary=self.role(self.primary)
        # Preserve the first actual parent for the independent-role comparison.
        self.scope=dict(picoBrowserCaptureRetirementVersion=VERSION,runId=self.primary.run,
            fixtureUrl=self.primary.fixture_url,binding=deepcopy(self.binding),ownerToken=primary_owner['ownerToken'])
        actor_owner,_actor=self.role(self.actor);need(same(primary_owner,actor_owner))
        with self.actor.lock.held():
            actor.originals();need(same(actor.store.read(),actor_receipt));self.graph(actor,'actor')
        need(self.proofs)
        self.scope.update(capturesSha256=digest(self.proofs),actorRetirementSha256=digest(actor_receipt))
        self.begin_original_queries()

    def begin_original_queries(self):
        self.admitted=canonical(self.admission());self._sealed_admitted=self.admitted
        self.indexed_rows=self._sealed_indexed_rows=tuple(
            (label,row['store'].path,row['owner'],row['raw'],tuple(row['stamp']),json_digest(row['expected']))
            for label,row in self.catalog.rows.items())
        with self.primary.lock.held():
            self.originals();self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.inventory(0)
            self.write('admitting',[])
            # These copies describe already admitted originals, not new target
            # observations. Freeze their exact bytes before the first child.
            original=self.admission();json_digest(dict(catalog=original['catalog'],proofs=original['proofs']))
            need(canonical(original)==self.admitted)
            admitted=json.loads(self.admitted);sources=admitted['catalog'];proofs=admitted['proofs']
            rows=[dict(kind='source-catalog',sources=sources[index:index+32]) for index in range(0,len(sources),32)]
            rows.extend(dict(kind='capture-proofs',proofs=proofs[index:index+8]) for index in range(0,len(proofs),8))
            json_digest(rows)
            self.catalog_rows=self._sealed_catalog_rows=tuple(canonical(row) for row in rows)
            self.copying_catalog=True
            try:
                for raw in self.catalog_rows:self.append(json.loads(raw),'admitting')
                self.catalog_copy_fence()
                # Complete bounded child reads must match the frozen original
                # catalogue before any ready state or native query can exist.
                reader=copy(self.chunks);loaded=reader.load(self.previous['chunks'])
                need(tuple(canonical(row) for row in loaded)==self.catalog_rows
                    and reader.identities==self.chunks.identities and reader.raw_bytes==self.chunks.raw_bytes)
                self.catalog_copy_fence()
            finally:self.copying_catalog=False
            self.write('ready',self.previous['chunks'])
            self.originals()
            self.reader=self.primary.adapter._tablet_web_retired_captures_observer(
                self.primary.selector,self.proofs,self.primary.lock,self.primary.run)
            send=self.reader.send
            def once(request):
                need(self.previous['phase']=='ready' and self.previous['pending'] is None)
                self.write('reading',self.previous['chunks'],pending=request)
                self.originals();self.clocks(self.round_started,self.round_epoch,[self.round_epoch]);send(request)
            self.reader.send=once

    def run(self):
        need(not self.started and not self.failed);self.started=True
        try:
            self.admit();flow=self.primary;start=flow.monotonic()
            for attempt in range(64):
                with flow.lock.held(),flow.adapter.existing_input_session(flow.selector):
                    self.round_started=flow.monotonic();self.round_epoch=flow.source.epoch_ms()
                    need(number(self.round_started,start,start+20));self.physical_index();flow.runtime(self.owner)
                    packet=self.reader.read();host=flow.monotonic()
                    clocks=[packet['requestedEpochMs'],packet['capturedEpochMs']]+[row['capturedEpochMs'] for row in packet['captures']]
                    if self.frames:
                        previous=json.loads(self.frames[-1]);old=previous['packet']
                        prior=[old['requestedEpochMs'],old['capturedEpochMs']]+[row['capturedEpochMs'] for row in old['captures']]
                        need(0<host-previous['host']<=.5 and all(0<y-x<=500 for x,y in zip(prior,clocks)))
                    first=None if not self.frames else json.loads(self.frames[0])
                    first_clocks=[] if first is None else [first['packet']['requestedEpochMs'],first['packet']['capturedEpochMs']]
                    if first is not None:first_clocks.extend(row['capturedEpochMs'] for row in first['packet']['captures'])
                    complete=len(self.frames)>=2 and host-first['host']>=3 and all(y-x>=3000 for x,y in zip(first_clocks,clocks))
                    row=dict(kind='absence-window',host=host,packet=packet,raw=self.reader.last_raw.decode('utf-8'),
                        rawSha256=self.reader.last_sha256,startedHost=self.round_started,startedEpoch=self.round_epoch)
                    frozen=canonical(row);self.originals()
                    self.append(row,'ready',complete=complete);self.frames=self.frames+(frozen,)
                    flow.runtime(self.owner);self.physical_index();result=deepcopy(self.previous)
                    completed_root=canonical(self.previous) if complete else None
                    stamp=signature(self.store.path.lstat()) if complete else None
                    self.clocks(self.round_started,self.round_epoch,clocks)
                self.physical()
                if complete:need(signature(self.store.path.lstat())==stamp)
                self.clocks(self.round_started,self.round_epoch,clocks)
                if complete:
                    self.completed_root,self.stamp=completed_root,stamp
                    self.completed=True;return result
                need(attempt<63);flow.sleep(.2)
        except Exception:
            self.failed=True;self.completed=False
            raise NativeUIError('Original browser capture retirement is incomplete; all ownership is retained') from None

    def receipt(self):
        need(self.completed and not self.failed and self.completed_root is not None)
        try:
            with self.primary.lock.held():
                self.originals();need(signature(self.store.path.lstat())==self.stamp)
                reader=copy(self.chunks);identities=tuple(self.chunks.identities);raw_bytes=self.chunks.raw_bytes
                rows=reader.load(self.previous['chunks'])
                frames=tuple(canonical(row) for row in rows if row['kind']=='absence-window')
                need(frames==self.frames and tuple(reader.identities)==identities and reader.raw_bytes==raw_bytes
                    and tuple(self.chunks.identities)==identities and self.chunks.raw_bytes==raw_bytes)
                self.originals();need(signature(self.store.path.lstat())==self.stamp);return deepcopy(self.previous)
        except Exception:self.failed=True;raise
