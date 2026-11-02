"""Production Create peer worker on an existing second Pico candidate.

No target discovery, launch, repair, product input or domain activation. This
native Model component does not publish the incomplete common Create facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sys
import time

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.chat_journey.source_chunks import digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode,exact,need,number,integer
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state as physical_state
from adapters.pico4.create_peer_source import PicoCreatePeerSource,scope
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.script_journey.lock import ScriptSourceLock,ScriptSourceBusy
from adapters.script_journey.history import canonical
from feature_journeys.contract import typed_equal,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from fixture.chat_observer_process import LinuxChatObserverProcess

VERSION=1
CONFIG_VERSION=5
RETURN_VERSION=2
READY='OVT_PICO_CREATE_PEER_RETURN_READY'
EXTRA={'artifactRoot','peerOwner','peerOwnerSha256','peerOwnerStamp','runId','originalRequestId',
    'workerExecutableSha256','workerEntrySha256'}


def canonical_path(value):
    need(type(value) is str);path=Path(value)
    need(path.is_absolute() and path.resolve(strict=True)==path);return path


def configuration(value):
    for key in ('runId','originalRequestId'):identifier(value[key])
    for key in ('peerOwnerSha256','workerExecutableSha256','workerEntrySha256'):
        need(type(value[key]) is str and len(value[key])==64 and all(ch in '0123456789abcdef' for ch in value[key]))
    need(type(value['peerOwnerStamp']) is list and len(value['peerOwnerStamp'])==8
        and all(type(field) is int for field in value['peerOwnerStamp']))
    directory=canonical_path(value['artifactRoot']);PrivateFeatureState(directory/'boundary.json')._parent()
    owner=PrivateFeatureState(canonical_path(value['peerOwner']));original,raw,physical=physical_state(owner)
    need(hashlib.sha256(raw).hexdigest()==value['peerOwnerSha256'] and physical==value['peerOwnerStamp'])
    exact(original,{'createPeerParentVersion','binding','runId','scope','phase','receipt','payload','sourceStamp'})
    need(type(original['createPeerParentVersion']) is int and original['createPeerParentVersion']==1
        and original['phase']=='issued' and original['receipt'] is original['payload'] is original['sourceStamp'] is None)
    source_scope=original['scope'];scope(source_scope)
    need(original['runId']==source_scope['runId']==value['runId']
        and typed_equal(context(original['binding']),context(source_scope['binding']))
        and source_scope['requestId']==value['originalRequestId']
        and source_scope['fixtureUrl']==value['fixtureUrl']+'/runs/'+value['runId']+'/')
    return original


class CreatePeerAdmission:
    """Original config/issued-owner OFDs and actual current worker program."""
    def __init__(self,path,value,*,monotonic=time.monotonic):
        need(callable(monotonic));self.monotonic=monotonic;self.started=monotonic()
        self.previous=self.started
        need(number(self.started,0,1e15));self.deadline=self.started+value['durationSeconds']
        self.value=deepcopy(value);self.value_sha=digest(value);self.host=host_identity()
        self.path=canonical_path(str(path));self.catalog=ChatArchiveCatalog();self.program=None;self.closed=False
        original=configuration(value)
        need(os.getppid()==int(original['scope']['parentHostProcessIdentity'].split(':')[0]))
        self.catalog.add('peer/configuration',PrivateFeatureState(self.path),value)
        self.catalog.add('primary/issued-create-owner',PrivateFeatureState(Path(value['peerOwner'])),original)
        row=self.catalog.rows['primary/issued-create-owner']
        need(row['sha256']==value['peerOwnerSha256'] and row['stamp']==value['peerOwnerStamp'])
        self.original=deepcopy(original);self.original_sha=digest(original)
        self.program=LinuxChatObserverProcess(self.host,Path(sys.argv[0]).resolve(strict=True),self.path,
            value['workerExecutableSha256'],value['workerEntrySha256'],lambda pid:pid==os.getpid() and self.base() is True)
        claim_path=Path(value['peerOwner']).with_name('create-peer-worker-claim-'+value['originalRequestId']+'.json')
        claim=dict(createPeerWorkerClaimVersion=VERSION,runId=value['runId'],originalRequestId=value['originalRequestId'],
            hostProcessIdentity=self.host,configurationSha256=self.catalog.rows['peer/configuration']['sha256'],
            issuedOwnerSha256=value['peerOwnerSha256'],startedMonotonic=self.started,deadlineMonotonic=self.deadline)
        # One original attempt per issued scope, including failed acquisition.
        # An existing claim is never adopted, overwritten or treated as repair.
        descriptor=os.open(claim_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(canonical(claim)+b'\n');stream.flush();os.fsync(stream.fileno())
        self.catalog.add('primary/worker-claim',PrivateFeatureState(claim_path),claim)
        self.control()

    def budget(self):
        now=self.monotonic();need(number(now,self.previous,self.deadline) and now<self.deadline
            and host_identity()==self.host);self.previous=now;return now

    def base(self):
        self.budget();need(not self.closed and digest(self.value)==self.value_sha and digest(self.original)==self.original_sha)
        self.catalog.verify_all();return True

    def control(self):
        self.base();need(self.program is not None and self.program.guard() is True);self.budget();return True

    def identity(self,binding):
        self.control();row=self.catalog.rows['peer/configuration'];claim=self.catalog.rows['primary/worker-claim']
        return dict(createPeerWorkerVersion=VERSION,runId=self.value['runId'],originalRequestId=self.value['originalRequestId'],
            hostProcessIdentity=self.host,binding=deepcopy(context(binding)),startedMonotonic=self.started,deadlineMonotonic=self.deadline,
            configurationPath=str(self.path),configurationSha256=row['sha256'],configurationStamp=deepcopy(row['stamp']),
            issuedOwnerPath=self.value['peerOwner'],issuedOwnerSha256=self.value['peerOwnerSha256'],
            issuedOwnerStamp=deepcopy(self.value['peerOwnerStamp']),program=deepcopy(self.program.inputs()),
            claimPath=str(claim['store'].path),claimSha256=claim['sha256'],claimStamp=deepcopy(claim['stamp']))

    def close(self):
        self.control();okay=self.catalog.close_host();okay=self.program.close() is True and okay
        need(okay and not self.catalog.uncertain
            and all(owner.closed and not owner.lost for owner in self.catalog.parents.values())
            and all(row['owner'].closed and not row['owner'].lost for row in self.catalog.rows.values())
            and self.program.fd_owner.closed and self.program.entry_owner.closed)
        self.closed=True;self.budget();return True


class PicoCreatePeerWorker:
    def __init__(self,adapter,admission,*,sleep=time.sleep):
        need(type(admission) is CreatePeerAdmission and callable(sleep))
        self.adapter,self.admission,self.sleep=adapter,admission,sleep;self.config=admission.value
        self.sender=None;self.failed=self.closed=False;self.source=None;self.disk=None
        self.store=PrivateFeatureState(Path(self.config['artifactRoot'])/'create-peer-worker.json')
        self.file=LifecycleProcessFile(self.store);need(self.file.file is None and self.store.read() is None)
        self.session=PicoScriptJourney(adapter).existing_input_session(self.config['target']);self.session.__enter__()
        admission.control();self.configuration_snapshot=deepcopy(adapter.pico_configuration)
        ui,_observe,binding=adapter._script_runtime(self.config['target'])
        self.ui=ui;self.native=adapter._native_feature_observer(self.config['target'])
        need(self.native.pid==int(binding['processIdentity'].split(':')[0]))
        self.identity=admission.identity(binding);self.identity_sha=digest(self.identity)
        self.save('acquire-issued')
        entities=adapter._create_entity_observer(self.config['target'],self.config['runId'])
        resources=adapter._create_model_resources_observer(self.config['target'],self.config['runId'])
        client=Client(self.config['fixtureUrl'],self.config['actorToken'])
        phases=PhaseFixtureReader(client,self.config['runId'],'create',epoch_ms=self.native.clock_ms,monotonic=self.native.monotonic)
        directory=Path(self.config['artifactRoot'])
        self.source=PicoCreatePeerSource(directory/'create-peer-originals.json',admission.original['scope'],binding,entities,resources,phases,
            ScriptSourceLock(directory/'script-sources.lock'),guard=self.control,monotonic=self.native.monotonic,sleep=self.native.sleep)
        self.save('watching');self.control()

    def metadata(self):
        need(not self.failed and digest(self.identity)==self.identity_sha and self.admission.host==host_identity()
            and self.store.read()==self.disk);self.file.guard()

    def control(self):
        self.metadata();self.admission.control();need(self.adapter.pico_configuration==self.configuration_snapshot)
        need(self.native.guard() is not False)
        # This is a fresh read of the already-bound UI source, with no input.
        need(self.ui.io.capture()['bridgeId']==self.identity['binding']['sessionId'])
        self.admission.budget();return True

    def save(self,phase,**changes):
        need(not self.failed and digest(self.identity)==self.identity_sha and host_identity()==self.admission.host)
        self.file.guard();need(self.store.read()==self.disk)
        value={**(self.disk or dict(self.identity,transport=None)),**deepcopy(changes),'phase':phase}
        self.file.write(value,self.disk);self.disk=deepcopy(value);self.file.guard();self.admission.budget()

    def proof(self):
        self.control();need(self.source is not None and self.disk['phase']=='watching')
        return dict(createPeerWorkerProofVersion=VERSION,journalPath=str(self.store.path),identity=deepcopy(self.identity))

    def fail(self):
        # Failure logging does not renew or excuse an expired budget. The
        # Parent still requires closed outcome AND actual zero exit status.
        try:
            self.file.guard();value={**self.disk,'phase':'failed'};self.file.write(value,self.disk);self.disk=value
        except Exception:pass
        self.failed=True

    def run(self):
        try:
            while self.sender is None:
                self.control()
                try:row=self.source.read()
                except ScriptSourceBusy:
                    # Only genuine contention before the source entered its
                    # acquisition is resumable. Its attempted flag keeps every
                    # issued/refused query sticky; the config clock is unchanged.
                    need(not self.source.failed and self.source.disk['pending'] is None)
                    self.control();self.sleep(.25);self.control();continue
                self.control()
                if row['phase']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}):
                    self.source.cleanup();self.control()
                    directory=self.store.path.parent
                    self.sender=self.source.sender(PrivateFeatureState(directory/'return.json'),PrivateFeatureState(directory/'consumption.json'),worker=self)
                    self.save('return-ready',transport=dict(payloadSha256=self.sender.scope['payloadSha256'],returnId=self.sender.scope['returnId']))
                    self.sender.publish();self.control()
                    # A fixed local publication notification carries no
                    # effect/cleanup verdict. The Parent still admits every
                    # original byte/program/nonce and actual kernel exit.
                    print(READY,flush=True);break
                self.sleep(.25);self.control()
            while self.sender.ack_store.read() is None:
                self.control();self.sender.control();self.sleep(.25);self.control()
            self.save('consume-issued');self.sender.consume();self.control()
            need(self.sender.consumed and not self.sender.failed)
            self.save('close-issued');self.session.__exit__(None,None,None);self.control()
            need(self.admission.close() is True)
            self.save('closed');need(self.file.close_host() is True)
            self.admission.budget();self.closed=True;return 0
        except Exception:
            self.fail();raise NativeUIError('Create peer worker unresolved; original ownership retained') from None


def validate_worker(payload,*,terminal=False,historical=False):
    proof=payload['worker'];exact(proof,{'createPeerWorkerProofVersion','journalPath','identity'})
    need(type(proof['createPeerWorkerProofVersion']) is int and proof['createPeerWorkerProofVersion']==VERSION)
    identity=proof['identity'];exact(identity,{'createPeerWorkerVersion','runId','originalRequestId','hostProcessIdentity','binding',
        'startedMonotonic','deadlineMonotonic','configurationPath','configurationSha256','configurationStamp',
        'issuedOwnerPath','issuedOwnerSha256','issuedOwnerStamp','program','claimPath','claimSha256','claimStamp'})
    need(type(identity['createPeerWorkerVersion']) is int and identity['createPeerWorkerVersion']==VERSION
        and identity['runId']==payload['scope']['runId'] and identity['originalRequestId']==payload['scope']['requestId']
        and identity['hostProcessIdentity']==payload['workerHostProcessIdentity']
        and typed_equal(context(identity['binding']),context(payload['actorBinding'])))
    config,config_raw,config_stamp=physical_state(PrivateFeatureState(canonical_path(identity['configurationPath'])))
    need(hashlib.sha256(config_raw).hexdigest()==identity['configurationSha256'] and config_stamp==identity['configurationStamp']
        and config['picoFeatureObserverVersion']==CONFIG_VERSION and config['area']=='create'
        and number(identity['startedMonotonic'],0,1e15)
        and identity['deadlineMonotonic']==identity['startedMonotonic']+config['durationSeconds']
        and config['peerOwner']==identity['issuedOwnerPath'] and config['peerOwnerSha256']==identity['issuedOwnerSha256']
        and config['peerOwnerStamp']==identity['issuedOwnerStamp'] and config['runId']==identity['runId']
        and config['originalRequestId']==identity['originalRequestId']
        and config['fixtureUrl']+'/runs/'+config['runId']+'/'==payload['scope']['fixtureUrl'])
    if not historical:
        original=configuration(config);need(typed_equal(original['scope'],payload['scope']))
    claim,claim_raw,claim_stamp=physical_state(PrivateFeatureState(canonical_path(identity['claimPath'])))
    need(hashlib.sha256(claim_raw).hexdigest()==identity['claimSha256'] and claim_stamp==identity['claimStamp']
        and Path(identity['claimPath'])==Path(identity['issuedOwnerPath']).with_name('create-peer-worker-claim-'+identity['originalRequestId']+'.json')
        and claim==dict(createPeerWorkerClaimVersion=VERSION,runId=identity['runId'],originalRequestId=identity['originalRequestId'],
            hostProcessIdentity=identity['hostProcessIdentity'],configurationSha256=identity['configurationSha256'],
            issuedOwnerSha256=identity['issuedOwnerSha256'],startedMonotonic=identity['startedMonotonic'],deadlineMonotonic=identity['deadlineMonotonic']))
    program=identity['program']
    need(program['identity']==identity['hostProcessIdentity'] and program['configuration']==identity['configurationPath']
        and program['configurationStamp']==identity['configurationStamp']
        and program['executableSha256']==config['workerExecutableSha256'] and program['entrySha256']==config['workerEntrySha256'])
    path=canonical_path(proof['journalPath']);need(path.name=='create-peer-worker.json'
        and path.parent==Path(config['artifactRoot'])==Path(payload['sourcePath']).parent)
    record,raw,physical=physical_state(PrivateFeatureState(path))
    exact(record,set(identity)|{'phase','transport'});need(all(typed_equal(record[key],field) for key,field in identity.items())
        and record['transport']==dict(payloadSha256=hashlib.sha256(canonical(payload)).hexdigest(),
            returnId=record['transport']['returnId']))
    need(record['phase']=='closed' if terminal else record['phase'] in ('return-ready','consume-issued','close-issued','closed'))
    return dict(identity=identity,journalSha256=hashlib.sha256(raw).hexdigest(),journalStamp=physical,
        returnId=record['transport']['returnId'])


def run(adapter,config,*,configuration_path,admission=None,monotonic=time.monotonic,sleep=time.sleep):
    need(config['area']=='create' and config['picoFeatureObserverVersion']==CONFIG_VERSION)
    admitted=CreatePeerAdmission(configuration_path,config,monotonic=monotonic) if admission is None else admission
    need(type(admitted) is CreatePeerAdmission and typed_equal(admitted.value,config) and admitted.path==Path(configuration_path))
    return PicoCreatePeerWorker(adapter,admitted,sleep=sleep).run()
