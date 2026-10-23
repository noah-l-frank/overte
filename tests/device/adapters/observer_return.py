"""Original opaque host return/consumption transport; no feature verdicts.

Typed feature owners admit the payload separately. These classes move only
unchanged original bytes, a fresh independently consumed nonce, and an actual
original host-process absence sample. No actor live object crosses processes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy,copy
import hashlib
import os
from pathlib import Path
import re
import uuid

from adapters.chat_journey.evidence_archive import private,stamp
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_fd_owner import OriginalDescriptor
from adapters.script_journey.history import canonical,same
from fixture.chat_observer_process import LinuxChatObserverProcess

VERSION=1
SCOPE={'observerReturnTransportVersion','runId','family','producerHostProcessIdentity','originalRequestId','returnId',
    'payloadSha256','payloadBytes','sourceStamp'}
ACK={'observerReturnConsumptionVersion','scopeSha256','returnId','originalRequestId','producerHostProcessIdentity',
    'consumerHostProcessIdentity','nonce','readyRootSha256','readyRootStamp','payloadSha256'}


def parent_node(store):
    store._parent();info=store.path.parent.lstat()
    return (info.st_dev,info.st_ino,info.st_uid,info.st_mode)


def raw_file(store):
    store._parent();owner=OriginalDescriptor(store.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    descriptor=owner.fd
    try:
        info=os.fstat(descriptor);private(info);physical=stamp(info);raw=os.pread(descriptor,65537,0)
        owner.require(descriptor)
        need(len(raw)==info.st_size and stamp(os.fstat(descriptor))==physical==stamp(store.path.lstat()))
        store._parent();owner.require(descriptor);return raw,physical
    finally:
        # A same-file recycled number is not this read's original OFD.
        # Keep both uncertain halves for actual host process finalization.
        need(OriginalDescriptor.close(owner) is True)


def state(store):
    raw,physical=raw_file(store);value=store.read()
    need(raw==canonical(value)+b'\n' and stamp(store.path.lstat())==physical)
    return value,raw,physical


def physical(value):
    need(type(value) is list and len(value)==8 and all(type(field) is int for field in value))


def identifier(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{32}',value))


def host(value,*,current=False):
    need(type(value) is str and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*:[0-9a-f-]{36}',value))
    pid,start,boot=value.split(':');root=Path('/proc')/pid
    fields=(root/'stat').read_text().rsplit(')',1)[1].split()
    need(root.stat().st_uid==os.geteuid() and fields[0] not in ('Z','X') and fields[19]==start
        and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot)
    if current:need(value==host_identity())


def scope(value):
    exact(value,SCOPE)
    need(type(value['observerReturnTransportVersion']) is int and value['observerReturnTransportVersion']==VERSION
        and type(value['family']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',value['family'])
        and type(value['payloadSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['payloadSha256'])
        and integer(value['payloadBytes'],1,65536))
    for name in ('runId','originalRequestId','returnId'):identifier(value[name])
    physical(value['sourceStamp'])
    need(type(value['producerHostProcessIdentity']) is str
        and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*:[0-9a-f-]{36}',value['producerHostProcessIdentity']))


class ObserverReturnSender:
    """One warm producer, one immutable payload, one consumed Parent nonce."""
    def __init__(self,store,ack_store,identity,raw,source_stamp,*,guard):
        exact(identity,{'runId','family','producerHostProcessIdentity','originalRequestId'})
        need(type(store) is PrivateFeatureState and type(ack_store) is PrivateFeatureState
            and store.path.parent==ack_store.path.parent and store.path!=ack_store.path
            and store.read() is None and ack_store.read() is None and type(raw) is bytes and callable(guard))
        self.scope={**deepcopy(identity),'observerReturnTransportVersion':VERSION,'returnId':uuid.uuid4().hex,
            'payloadSha256':hashlib.sha256(raw).hexdigest(),'payloadBytes':len(raw),'sourceStamp':deepcopy(source_stamp)}
        scope(self.scope);host(self.scope['producerHostProcessIdentity'],current=True)
        self.scope_sha=digest(self.scope);self.raw,self.guard,self.store,self.ack_store=raw,guard,store,ack_store
        self.parent=parent_node(store)
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        ChatSourceChunks(ack_store,self.scope).inventory(0)
        self.previous=None;self.previous_sha=digest(None);self.root_stamp=None;self.failed=self.started=self.consumed=False

    def control(self):
        need(not self.failed and parent_node(self.store)==self.parent and digest(self.scope)==self.scope_sha and digest(self.previous)==self.previous_sha
            and type(self.raw) is bytes and hashlib.sha256(self.raw).hexdigest()==self.scope['payloadSha256']
            and self.guard() is True and same(self.store.read(),self.previous))
        host(self.scope['producerHostProcessIdentity'],current=True);self.history.verify()
        ChatSourceChunks(self.ack_store,self.scope).inventory(0)
        if self.root_stamp is not None:need(stamp(self.store.path.lstat())==self.root_stamp)

    def write(self,phase,**changes):
        self.control();value={**(self.previous or {**self.scope,'chunks':[]}),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);observed,_raw,physical_stamp=state(self.store)
        need(same(value,observed));self.previous=deepcopy(value);self.previous_sha=digest(value);self.root_stamp=physical_stamp
        self.control()

    def publish(self):
        need(not self.started and not self.failed);self.started=True
        try:
            self.write('reading')
            for index,start in enumerate(range(0,len(self.raw),16384)):
                row=dict(index=index,rawBase64=base64.b64encode(self.raw[start:start+16384]).decode('ascii'))
                chunks=self.history.append(row,self.previous['chunks']);self.write('reading',chunks=chunks)
            self.write('ready');self.ready,self.ready_raw,self.ready_stamp=state(self.store)
            result=deepcopy(self.ready);self.control();return result
        except BaseException:self.failed=True;raise

    def consume(self):
        need(self.started and not self.failed and not self.consumed and self.previous['phase']=='ready')
        try:
            self.control();value,raw,physical_stamp=state(self.ack_store);exact(value,ACK)
            identifier(value['nonce']);physical(value['readyRootStamp'])
            need(type(value['observerReturnConsumptionVersion']) is int and value['observerReturnConsumptionVersion']==VERSION
                and value['scopeSha256']==self.scope_sha and value['returnId']==self.scope['returnId']
                and value['originalRequestId']==self.scope['originalRequestId']
                and value['producerHostProcessIdentity']==self.scope['producerHostProcessIdentity']
                and value['consumerHostProcessIdentity']!=self.scope['producerHostProcessIdentity']
                and value['readyRootSha256']==hashlib.sha256(self.ready_raw).hexdigest()
                and value['readyRootStamp']==self.ready_stamp and value['payloadSha256']==self.scope['payloadSha256'])
            host(value['consumerHostProcessIdentity']);self.control()
            again,again_stamp=raw_file(self.ack_store);need(again==raw and again_stamp==physical_stamp)
            self.write('consumed',consumption=value,consumptionSha256=hashlib.sha256(raw).hexdigest(),consumptionStamp=physical_stamp)
            again,again_stamp=raw_file(self.ack_store);need(again==raw and again_stamp==physical_stamp)
            result=deepcopy(self.previous);self.control();self.consumed=True;return result
        except BaseException:self.failed=True;raise


class ObserverReturnReceiver:
    """Original live process acquisition precedes any payload admission.

    The typed admission callback is historical feature validation, never a
    callable expected effect or a transport-provided feature success verdict.
    A lost ACK write is reconciled only from the same original nonce and the
    independently consumed echo, with no second write or cold reconstruction.
    """
    def __init__(self,owner,store,ack_store,expected,*,admit):
        need(type(owner) is LinuxChatObserverProcess and callable(admit)
            and type(store) is PrivateFeatureState and type(ack_store) is PrivateFeatureState
            and store.path.parent==ack_store.path.parent and store.path!=ack_store.path and ack_store.read() is None)
        exact(expected,{'runId','family','producerHostProcessIdentity','originalRequestId'})
        need(expected['producerHostProcessIdentity']==owner.process_identity)
        self.owner,self.store,self.ack_store,self.admit=owner,store,ack_store,admit
        self.expected=deepcopy(expected);self.parent=parent_node(store);self.intent=None;self.consumed_stamp=self.consumed_raw=None
        self.issued=self.complete=False;owner.guard()
        value,self.ready_raw,self.ready_stamp=state(store);exact(value,SCOPE|{'phase','chunks'})
        self.scope={name:value[name] for name in SCOPE};scope(self.scope)
        need(value['phase']=='ready' and all(same(value[name],field) for name,field in expected.items()))
        ChatSourceChunks(ack_store,self.scope).inventory(0)
        self.ready=deepcopy(value);self.scope_sha=digest(self.scope);self.history=ChatSourceChunks(store,self.scope)
        need(type(value['chunks']) is list and len(value['chunks'])==(self.scope['payloadBytes']+16383)//16384)
        admitted=tuple(self.history.signature(index) for index in range(len(value['chunks'])))
        frames=self.history.load(value['chunks']);need(tuple(self.history.identities)==admitted)
        parts=[]
        for index,row in enumerate(frames):
            exact(row,{'index','rawBase64'});need(type(row['index']) is int and row['index']==index and type(row['rawBase64']) is str)
            part=base64.b64decode(row['rawBase64'],validate=True);need(1<=len(part)<=16384);parts.append(part)
        self.raw=b''.join(parts)
        need(len(self.raw)==self.scope['payloadBytes'] and hashlib.sha256(self.raw).hexdigest()==self.scope['payloadSha256'])
        self.admitted=admitted;self.ready_sha=hashlib.sha256(self.ready_raw).hexdigest()
        need(admit(self.raw,deepcopy(self.scope['sourceStamp'])) is True)
        self.verify_ready();owner.guard()

    def verify_parts(self):
        ChatSourceChunks(self.ack_store,self.scope).inventory(0)
        need(parent_node(self.store)==self.parent and digest(self.scope)==self.scope_sha
            and canonical(self.ready)+b'\n'==self.ready_raw
            and hashlib.sha256(self.ready_raw).hexdigest()==self.ready_sha
            and self.history.scope==self.scope_sha and self.history.root is self.store)
        scope(self.scope);need(type(self.raw) is bytes and tuple(self.history.identities)==self.admitted);self.history.verify()
        reader=copy(self.history);frames=reader.load(self.ready['chunks'])
        need(tuple(reader.identities)==self.admitted and tuple(self.history.identities)==self.admitted)
        parts=[base64.b64decode(row['rawBase64'],validate=True) for row in frames]
        need(b''.join(parts)==self.raw and hashlib.sha256(self.raw).hexdigest()==self.scope['payloadSha256'])

    def verify_ready(self):
        value,raw,physical_stamp=state(self.store)
        need(same(value,self.ready) and raw==self.ready_raw and physical_stamp==self.ready_stamp);self.verify_parts()

    def acknowledge(self):
        need(not self.issued and not self.complete);self.issued=True
        self.verify_ready();self.owner.guard();need(self.ack_store.read() is None)
        self.intent=dict(observerReturnConsumptionVersion=VERSION,scopeSha256=digest(self.scope),returnId=self.scope['returnId'],
            originalRequestId=self.scope['originalRequestId'],producerHostProcessIdentity=self.scope['producerHostProcessIdentity'],
            consumerHostProcessIdentity=host_identity(),nonce=uuid.uuid4().hex,readyRootSha256=self.ready_sha,
            readyRootStamp=deepcopy(self.ready_stamp),payloadSha256=self.scope['payloadSha256'])
        self.intent_raw=canonical(self.intent)+b'\n';self.intent_sha=digest(self.intent)
        # The same exact intent remains available after a lost write reply.
        # There is no path that writes it again.
        self.ack_store.write(self.intent,None)
        raw,_physical=raw_file(self.ack_store);need(raw==self.intent_raw)
        result=deepcopy(self.intent);self.verify_ready();self.owner.guard();return result

    def receipt(self):
        need(self.issued and self.intent is not None and not self.complete
            and digest(self.intent)==self.intent_sha and canonical(self.intent)+b'\n'==self.intent_raw)
        value,raw,physical_stamp=state(self.store)
        exact(value,SCOPE|{'phase','chunks','consumption','consumptionSha256','consumptionStamp'})
        need(value['phase']=='consumed' and all(same(value[name],field) for name,field in self.scope.items())
            and same(value['chunks'],self.ready['chunks']) and same(value['consumption'],self.intent)
            and value['consumptionSha256']==hashlib.sha256(self.intent_raw).hexdigest())
        ack_raw,ack_stamp=raw_file(self.ack_store)
        need(ack_raw==self.intent_raw and ack_stamp==value['consumptionStamp'])
        if self.consumed_stamp is None:self.consumed_stamp,self.consumed_raw=physical_stamp,raw
        need(physical_stamp==self.consumed_stamp and raw==self.consumed_raw);self.verify_parts()
        absence=self.owner.require_absent()
        result=dict(observerReturnReceiptVersion=VERSION,runId=self.scope['runId'],family=self.scope['family'],
            producerHostProcessIdentity=self.scope['producerHostProcessIdentity'],originalRequestId=self.scope['originalRequestId'],
            returnId=self.scope['returnId'],payloadSha256=self.scope['payloadSha256'],readyRootSha256=self.ready_sha,
            consumedRootSha256=hashlib.sha256(raw).hexdigest(),consumptionSha256=value['consumptionSha256'],processAbsence=absence)
        result=deepcopy(result);self.verify_parts()
        need(raw_file(self.store)==(self.consumed_raw,self.consumed_stamp)
            and raw_file(self.ack_store)==(self.intent_raw,ack_stamp))
        self.owner.final_absence(absence);self.complete=True;return result
