"""Fresh original Browser release sources for the existing archive mechanism.

The original common/VM/Java/capture quiet owners precede this warm handoff.
This observer neither unlinks a source nor grants complete feature cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import uuid

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_feature_observation import fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,state
from adapters.original_source_unlink_fence import OriginalSourceUnlinkFence
from adapters.pico4.browser_actor_retirement import acquire_original_retirement_frame,validate_original_frame
from adapters.script_journey.history import canonical,same
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1


class PicoBrowserArchiveReleaseSource:
    def __init__(self,primary,captures):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        from adapters.pico4.browser_remote_capture_retirement import PicoBrowserRemoteCaptureRetirement
        need(type(primary) is PicoTabletWebFeature and primary.role=='primary'
            and type(captures) is PicoBrowserRemoteCaptureRetirement and captures.primary is primary
            and captures.completed and not captures.failed and primary.cleanup_consumption is not None
            and primary.cleanup_consumption.complete and not primary.cleanup_consumption.failed
            and primary.vm_cache is not None and primary.history_cache is not None)
        self.flow,self.captures=primary,captures
        # Both historical receipts precede our distinct mutable source marker.
        self.capture_receipt=captures.receipt();self.return_receipt=captures.returned.receipt()
        self.store=PrivateFeatureState(primary.artifact_root/('tablet-web-'+primary.run+'-archive-release.json'))
        need(self.store.read() is None);ChatSourceChunks(self.store,{}).inventory(0)
        self.parent=parent_node(self.store);self.previous=None;self.root_stamp=None;self.previous_sha=json_digest(None)
        self.failed=False;self.frozen=False;self.started=self.epoch=None;self.last_sha=None
        self._proof_bytes=self._sealed_proof_bytes=None
        with primary.lock.held():
            owner=deepcopy(primary.owner());role=primary.role_state()
            self.history=primary.history_cache;self.history.matches(role)
            self.vm=primary.vm_cache;self.vm.verify();anchor=self.vm.frame(-1)
            inactive=deepcopy(captures.returned.graph.inactive['phaseAfter'])
            need(owner['phase']=='cleaned' and role['publication'] is None
                and role['quiet']['complete'] and role['native']['source']['retired'])
            self.scope=dict(picoBrowserArchiveReleaseVersion=VERSION,runId=primary.run,fixtureUrl=primary.fixture_url,
                binding=deepcopy(owner['binding']),ownerToken=owner['ownerToken'],
                captureReceiptSha256=digest(self.capture_receipt),actorReturnSha256=digest(self.return_receipt))
            original=dict(scope=self.scope,owner=owner,role=role,anchor=anchor,inactive=inactive,
                origin=self.vm.origin,proofs=deepcopy(captures.proofs))
            # These facts are historical and already consumed. Validate their
            # complete strict JSON once, then keep only exact immutable bytes.
            # Inspection copies can never mutate the admitted original graph.
            json_digest(original)
            self.admitted=canonical(original);self._sealed_admitted=self.admitted
            self.facts=self._sealed_facts=tuple(canonical(original[key]) for key in
                ('scope','owner','role','anchor','inactive','origin','proofs'))
            self.phase(inactive,role['phase'])
            self.reader=primary.adapter._tablet_web_retired_captures_observer(primary.selector,self.proofs,primary.lock,primary.run)
        self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.inventory(0)
        send=self.reader.send
        def issued(command):
            need(self.previous is not None and self.previous['phase']=='reading' and self.previous['pending']['capture'] is None)
            pending=deepcopy(self.previous['pending']);pending['capture']=deepcopy(command)
            self.save('reading',self.previous['chunks'],pending=pending)
            self.clocks([self.epoch]);send(command)
        self.reader.send=issued

    # Read copies preserve the existing dictionary/list grammar at semantic
    # call boundaries. No caller receives a mutable authoritative admission.
    @property
    def owner(self):return json.loads(self.facts[1])
    @property
    def state(self):return json.loads(self.facts[2])
    @property
    def anchor(self):return json.loads(self.facts[3])
    @property
    def inactive(self):return json.loads(self.facts[4])
    @property
    def proofs(self):return json.loads(self.facts[6])

    @property
    def last(self):
        # Lossless inspection of the complete last original. The authority is
        # immutable canonical bytes, never a mutable returned dictionary.
        return None if self._proof_bytes is None else json.loads(self._proof_bytes)

    def admission(self):
        return json.loads(self.admitted)

    def control(self):
        # Each sealed tuple member is an original immutable bytes object, not
        # a cached validation of a live or mutable DTO. The two mutable live
        # references in that original still get their full strict comparisons.
        json_digest(self.scope);json_digest(self.vm.origin)
        need(not self.failed and self.admitted is self._sealed_admitted
            and self.facts is self._sealed_facts and type(self.facts) is tuple
            and canonical(self.scope)==self.facts[0] and canonical(self.vm.origin)==self.facts[5]
            and json_digest(self.previous)==self.previous_sha
            and parent_node(self.store)==self.parent and same(self.store.read(),self.previous))
        if self.root_stamp is not None:need(state(self.store)[2]==self.root_stamp)
        self.chunks.verify()

    def save(self,phase,chunks,*,pending=None):
        self.control();value={**self.scope,'phase':phase,'chunks':deepcopy(chunks),'pending':deepcopy(pending)}
        self.store.write(value,self.previous);observed,_raw,self.root_stamp=state(self.store)
        need(same(observed,value));self.previous=deepcopy(value);self.previous_sha=json_digest(value);self.control()

    def phase(self,value,previous):
        f=self.flow;phase_packet(value,run=f.run,area='tablet-web',request=value['requestId'],epoch=value['capturedEpochMs'],previous=previous)
        need(value['active'] is False and same(value['activations'],self.state['phase']['activations'])
            and value['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))

    def clocks(self,epochs):
        f=self.flow;measured=f.monotonic();epoch=f.source.epoch_ms();ended=f.monotonic()
        need(number(measured,self.started,self.started+1.5) and number(ended,measured,self.started+1.5))
        for captured in epochs:
            fresh(captured,epoch)
            need(max(epoch-captured,self.epoch-captured+math.ceil((ended-self.started)*1000),
                epoch-captured+math.ceil((ended-measured)*1000))<=1500)
        return ended,epoch

    def cursors(self):
        return dict(scripts=self.vm.scripts.sequence,objects=deepcopy(self.vm.objects.last),
            captures=dict(sequence=self.reader.sequence,captured=self.reader.captured,floor=self.reader.floor,
                queries=sorted(self.reader.queries),inventoryQueries=sorted(self.reader.inventory_queries)),
            captureSha256=self.reader.last_sha256)

    def final(self,proof,*,expected_cursors=None):
        try:
            self.control();need(type(self._proof_bytes) is bytes and self._proof_bytes is self._sealed_proof_bytes
                and hashlib.sha256(self._proof_bytes).hexdigest()==self.last_sha and canonical(proof)==self._proof_bytes
                and proof['frame']['startedHost']==self.started and proof['frame']['startedEpoch']==self.epoch
                and self.epochs is self._sealed_epochs)
            if expected_cursors is not None:need(same(expected_cursors,self.cursors()))
            self.flow.runtime(dict(binding=self.scope['binding']));self.control();self.clocks(self.epochs)
        except BaseException:self.failed=True;raise

    def current_phase(self,proof):
        try:
            self.final(proof);current=self.flow.source.status(proof['frame']['phaseAfter'])
            self.phase(current,proof['frame']['phaseAfter']);self.final(proof);return current
        except BaseException:self.failed=True;raise

    def __call__(self,original=None):
        if original is not None:self.current_phase(original);return original
        f=self.flow
        try:
            need(not self.frozen)
            with f.lock.held(),f.adapter.existing_input_session(f.selector):
                self.control();need(self.previous is None or self.previous['phase']=='ready')
                self.started=f.monotonic();self.epoch=f.source.epoch_ms();f.runtime(self.owner)
                self.save('reading',[] if self.previous is None else self.previous['chunks'],
                    pending=dict(requestId=uuid.uuid4().hex,capture=None))
                self.clocks([self.epoch])
                frame,epochs,guard,active=acquire_original_retirement_frame(self,self.started,self.epoch,include_inactive=False)
                packet=self.reader.read();epochs.extend([packet['requestedEpochMs'],packet['capturedEpochMs']])
                epochs.extend(row['capturedEpochMs'] for row in packet['captures'])
                guard();f.runtime(self.owner);ended,epoch=self.clocks(epochs)
                frame.update(finishedHost=ended,finishedEpoch=epoch)
                validate_original_frame(frame,self.owner,self.state,self.anchor,self.vm.origin,active,
                    run=f.run,fixture_url=f.fixture_url,role='primary')
                proof=dict(frame=frame,captures=packet,raw=self.reader.last_raw.decode('utf-8'),rawSha256=self.reader.last_sha256)
                json_digest(proof);chunks=self.chunks.append(proof,self.previous['chunks']);self.save('ready',chunks)
                self.last_sha=json_digest(proof);self._proof_bytes=self._sealed_proof_bytes=canonical(proof)
                self.epochs=tuple(epochs);self._sealed_epochs=self.epochs
                result=deepcopy(proof);self.final(result)
            self.control();self.clocks(self.epochs);return result
        except BaseException:
            self.failed=True
            raise NativeUIError('Original Browser archive source is unresolved; all originals remain') from None


class PicoBrowserArchiveUnlinkFence(OriginalSourceUnlinkFence):
    def __init__(self,guard):
        need(type(guard) is PicoBrowserArchiveReleaseSource and not guard.failed)
        super().__init__(guard,now=lambda:guard.flow.monotonic(),clock_ms=lambda:guard.flow.source.epoch_ms(),
            source_sequence=lambda proof:proof['frame']['objectsAfter']['sequence'])
