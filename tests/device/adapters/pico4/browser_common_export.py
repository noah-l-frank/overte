"""Original common consumption transport for a separately owned adapter host.

Only an actual live Journey callback can emit this historical record. It is
not an input, product observation or complete feature receipt. The receiving
typed owner must independently bind the original producer and native history.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey.source_bundles import prepare,original as original_bundle
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.operation_protocol import dto_bytes,REQUEST_LIMIT
from adapters.script_journey.history import canonical,same,pack,MAX_RAW,MAX_FRAMES
from feature_journeys.contract import identifier,json_document
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=2
SAMPLE_FIELDS=('phase','ticket','actionBarrierEpochMs','sequence','capturedEpochMs',
    'state','resources','lifecycle','witness')
PHASE_FIELDS=('phase','advancingSamples','stableSeconds','lastSequence')
UNRESOLVED=[]


def projection(journey):
    """All actual comparison samples; image policy/analysis is not transferred.

    Native image originals remain in their existing artifact ownership graph.
    Witness values are actual received observations, not expected recipe state.
    """
    need(type(journey) is Journey)
    return dict(phases=[{key:row[key] for key in PHASE_FIELDS} for row in journey.phases],
        samples=[{key:row[key] for key in SAMPLE_FIELDS} for row in journey.samples],
        finalSequence=journey.sequence,sequenceSucceeded=journey._cleanup_sequence_succeeded)


class JourneyConsumptionExport:
    """One callback, existing lossless bundles, original root OFDs, no replay."""
    def __init__(self,root,area,run,fixture_url,nonce,send,guard):
        identifier(run);identifier(nonce)
        need(area=='tablet-web' and isinstance(root,Path) and root.is_absolute()
            and fixture_url.endswith('/runs/'+run+'/') and callable(send) and callable(guard))
        self.root,self.area,self.run,self.url,self.nonce=root,area,run,fixture_url,nonce
        self.send=self._send=send;self.external_guard=self._external_guard=guard
        self.host=host_identity();self.journey=None;self.callback=self.consume
        self.scope=dict(journeyConsumptionExportVersion=VERSION,contractVersion=CONTRACT_VERSION,
            area=area,runId=run,fixtureUrl=fixture_url,nonce=nonce,producerHostProcessIdentity=self.host)
        self.scope_sha=json_digest(self.scope)
        self.store=PrivateFeatureState(root/('tablet-web-'+run+'-common-export-'+nonce+'.json'))
        self.started=self.failed=self.complete=False;self.previous=None
        self.raw=self.record_raw=self.original_raw=self.original_stamp=self.result=None
        self.file=object.__new__(LifecycleProcessFile)
        try:
            need(self.store.read() is None)
            self.history=ChatSourceChunks(self.store,self.scope);self.history.inventory(0)
            LifecycleProcessFile.__init__(self.file,self.store)
            self.guard()
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise

    def guard(self):
        need(not self.failed and host_identity()==self.host
            and self.send is self._send and self.external_guard is self._external_guard
            and json_digest(self.scope)==self.scope_sha and self.store.path.parent==self.root)
        self.external_guard();self.file.guard();self.history.verify()
        need(same(self.store.read(),self.previous))

    def attach(self,journey):
        self.guard()
        need(type(journey) is Journey and journey.area==self.area and journey.run==self.run
            and journey.url==self.url and self.journey is None and not self.started
            and journey.after_cleanup_baseline is self.callback and not journey.cleanup_hook_started
            and journey.cleanup_consumption is None)
        self.journey=journey

    def save(self,phase,chunks,reference=None):
        self.guard()
        value=dict(**self.scope,phase=phase,chunks=deepcopy(chunks),reference=deepcopy(reference))
        self.file.write(value,self.previous);self.previous=deepcopy(value);self.guard()

    def consume(self,raw):
        try:
            need(not self.started and not self.failed);self.started=True
            self.guard();journey=self.journey
            need(type(journey) is Journey and journey.cleanup_hook_started
                and raw is journey.cleanup_consumption and type(raw) is bytes and 0<len(raw)<=MAX_RAW
                and journey.after_cleanup_baseline is self.callback)
            value=json_document(raw)
            exact(value,{'cleanupConsumptionVersion','contractVersion','area','runId','fixtureUrl','ticket',
                'actionBarrierEpochMs','sequenceSucceeded','phase','samples','finalSequence'})
            need(type(value['cleanupConsumptionVersion']) is int and value['cleanupConsumptionVersion']==1
                and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION
                and value['area']==self.area and value['runId']==self.run and value['fixtureUrl']==self.url
                and type(value['sequenceSucceeded']) is bool
                and value['sequenceSucceeded'] is journey._cleanup_sequence_succeeded
                and value['samples'] and same(value['samples'],journey.samples[-len(value['samples']):])
                and same(value['phase'],journey.phases[-1]) and value['phase']['phase']=='cleanup-restored-baseline'
                and value['phase']['stableSeconds']>=3 and value['finalSequence']==journey.sequence)
            self.raw=raw
            # Preserve the exact JSON lexical original too: re-encoding a
            # parsed value could change escapes, Unicode or whitespace.
            record=dict(**self.scope,commonRaw=raw.decode('utf-8'),journey=projection(journey))
            # Use the reviewed streaming exact-size counter before allocating
            # canonical/compression/Base64/fragment or CAS work buffers. These
            # are protocol byte/copy extents, not a Python RSS measurement.
            size=canonical_size(record)
            compressed=size+(size>>12)+(size>>14)+(size>>25)+13
            encoded=4*((compressed+2)//3);parts_bound=max(1,(encoded+24575)//24576)
            need(parts_bound<=MAX_FRAMES and (parts_bound+1)*65536<=MAX_RAW
                and 2*len(raw)+3*size+compressed+3*encoded+5*65536+4096*(parts_bound+1)<=MAX_RAW)
            self.record_raw=canonical(record);need(len(self.record_raw)+2<=MAX_RAW)
            self.save('reading',[])
            reference,parts=prepare(record,0,[]);manifest=[]
            for part in parts:
                manifest=self.history.append(part,manifest);self.save('reading',manifest)
            self.save('sealed',manifest,reference)
            actual,actual_raw=original_bundle(self.history,manifest,[reference],0)
            need(actual_raw==self.record_raw and same(actual,record))
            self.original_raw=self.store.path.read_bytes();self.original_stamp=tuple(self.file.stamp)
            request=dict(journeyConsumptionExportVersion=VERSION,name=self.store.path.name,
                rootSha256=hashlib.sha256(self.original_raw).hexdigest(),rootStamp=list(self.original_stamp),
                recordSha256=hashlib.sha256(self.record_raw).hexdigest(),
                commonSha256=hashlib.sha256(raw).hexdigest(),nonce=self.nonce,
                chunkPins=pack([[list(row) for row in self.history.identities]]))
            dto_bytes(request,REQUEST_LIMIT,arguments=True)
            reply=self.send(deepcopy(request))
            # This acknowledges only receipt of the original record. Native,
            # independent Actor and whole retirement checks are NOT inferred.
            exact(reply,{'journeyConsumptionReceivedVersion','nonce','recordSha256','commonSha256'})
            need(type(reply['journeyConsumptionReceivedVersion']) is int and reply['journeyConsumptionReceivedVersion']==VERSION
                and all(reply[key]==request[key] for key in ('nonce','recordSha256','commonSha256')))
            self.guard();need(tuple(self.file.stamp)==self.original_stamp and self.store.path.read_bytes()==self.original_raw
                and canonical(projection(journey))==canonical(record['journey'])
                and journey.cleanup_consumption is raw)
            self.result=deepcopy(request);self.complete=True
        except BaseException:
            self.failed=True
            if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
            raise

    def receipt(self):
        need(self.complete and not self.failed);self.guard()
        need(self.store.path.read_bytes()==self.original_raw and tuple(self.file.stamp)==self.original_stamp)
        reference=self.previous['reference']
        _value,raw=original_bundle(self.history,self.previous['chunks'],[reference],0)
        need(raw==self.record_raw);return deepcopy(self.result)

    def close_host(self):
        # Known original handles may close even after delivery failed. This
        # neither discards files nor grants any target/resource cleanup.
        return self.file.close_host()
