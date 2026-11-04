"""Actual retained HOST files; SDK/Qt/DOM authority is explicitly modeled.

No finalizer/deletion of original artifacts, hidden network or device work.
Individual finite components close only their actual physical host originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""ONE finite namespace-only actual cold Parent census; no product facts."""
import os
import uuid
from pathlib import Path
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
from adapters.pico4.world_root_resource import WorldRootSelection1,WorldRootParticipant1
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


class NamespaceOnlyAdapter:
    """Explicit namespace model; missing SDK methods cannot deliver input."""
    def __init__(self,root):
        self.pico_configuration=('namespace-only',root)
        self.source_lock=ScriptSourceLock(root/'script-sources.lock')
        self.sdk_calls=self.inputs=0
    def _script_journey(self):return self
    def _lock(self,target,source_lock=None):
        if source_lock is not None:assert source_lock is self.source_lock
        return self.source_lock


def normal_cold_parent_census(artifacts):
    base=artifacts/'namespace';base.mkdir(mode=0o700)
    original=NamespaceOnlyAdapter(base)
    flow=None;owner=None;proof={};error=None
    # Fixture configuration only, selected before any constructor. No service
    # is launched and Client.request is never called.
    required={'OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
        'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'https://world-resource.invalid/scene.json'}
    before={key:os.environ.get(key) for key in required};os.environ.update(required)
    try:
        binding=PicoWorldWebBinding(original)
        source=PhaseFixtureReader(Client('https://primary.invalid/feature-fixture/v1','n'*32),uuid.uuid4().hex,'world-web')
        flow=binding.prefix('namespace-target',source,'https://foreign.invalid/feature-fixture/v1',resource_selection=WorldRootSelection1())
        participant=flow.resource_participant
        assert type(flow) is PicoWorldWebPrefix and type(participant) is WorldRootParticipant1
        assert flow.disk is flow.state is flow.history is flow.vm is None and source.previous is None
        empty=participant.census()
        owner=object.__new__(LifecycleProcessFile)
        store=PrivateFeatureState(flow.root/'world-resource-counter.json')
        payload={'worldResourceCounterVersion':1,'purpose':'resource-census-only','inputAllowed':False}
        participant.hold_file_before_init(owner,store,payload)
        held_before_ctor=(participant.records[0]['owner'] is owner and not vars(owner))
        LifecycleProcessFile.__init__(owner,store)
        absent_before_write=not store.path.exists() and owner.raw is None and owner.file is None
        owner.write(payload,None)
        participant.file_ready(owner)
        full=participant.census()
        # All completion/custody/count assertions are OUTSIDE SourceLock and
        # normalization. This test never invokes Parent.prepare/save/read.
        assert empty['bill']['S']==0 and empty['pins']==[]
        assert held_before_ctor and absent_before_write
        assert len(full['pins'])==1 and full['bill']['S']==len(owner.raw)>0
        assert full['bill']['stored']<=16777216 and full['bill']['decoded']<=16777216
        assert full['bill']['precount']==2097152 and full['bill']['window']==196608
        assert len(participant.entry_claims)==2 and participant.records[0]['owner'] is owner
        assert participant.records[0]['raw'] is owner.raw and participant.records[0]['stamp'] is owner.stamp
        assert participant.failure is None and not full['inputAllowed'] and not full['sourceAllowed']
        assert flow.disk is flow.state is flow.history is flow.vm is None and source.previous is None
        assert original.sdk_calls==original.inputs==0
        proof={'case':'normal_cold_parent_census','empty':empty,'full':full,
            'heldBeforeFileCtor':held_before_ctor,'absentBeforeWrite':absent_before_write,
            'ownerRawSha256':full['pins'][0]['sha256'],'actualFileBytes':len(owner.raw),
            'sdkCalls':0,'inputs':0,'normalParentConstructor':True,'parentPrepared':False,
            'nativeQualified':False,'deviceQualified':False,'featureComplete':False,
            'wholeParentRetirementQualified':False,'fileOwnerKnownClose':False,'directoryKnownClose':False}
    except BaseException as caught:
        error=caught
        if flow is not None and flow.resource_participant is not None:flow.resource_participant.fail(caught)
        raise
    finally:
        close_results={}
        if owner is not None and hasattr(owner,'parent'):
            try:close_results['fileOwnerKnownClose']=owner.close_host()
            except BaseException as close_error:
                close_results['fileOwnerKnownClose']=False
                if error is None:raise
        if flow is not None and flow.resource_participant is not None:
            try:close_results['directoryKnownClose']=flow.resource_participant.close_host()
            except BaseException:
                close_results['directoryKnownClose']=False
                if error is None:raise
        proof.update(close_results)
        for key,value in before.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    assert proof['fileOwnerKnownClose'] and proof['directoryKnownClose']
    return proof


"""Two separate fresh resource-only fixtures; real owned IO/data faults."""
import gc,hashlib,os,uuid
from pathlib import Path
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_root_resource import WorldRootSelection1
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


class Fixture:
    def __init__(self,artifacts):
        base=artifacts/'namespace';base.mkdir(mode=0o700)
        self.original=NamespaceOnlyAdapter(base);self.owners=[];self.closes=[]
        self.environment={key:os.environ.get(key) for key in ('OVERTE_PICO_NORMAL_SCRIPTS','OVERTE_ANDROID_E2E_DEBUG','OVERTE_PICO_OPENXR_INPUT','OVERTE_E2E_SCENE_URL')}
        os.environ.update(OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL='https://world-resource.invalid/scene.json')
        self.binding=PicoWorldWebBinding(self.original)
        self.source=PhaseFixtureReader(Client('https://primary.invalid/feature-fixture/v1','n'*32),uuid.uuid4().hex,'world-web')
        self.parent=self.binding.prefix('namespace-target',self.source,'https://foreign.invalid/feature-fixture/v1',resource_selection=WorldRootSelection1())
        self.participant=self.parent.resource_participant
    def file(self):
        self.writer=object.__new__(LifecycleProcessFile);self.owners.append(self.writer)
        self.store=PrivateFeatureState(self.parent.root/'world-resource-counter.json')
        self.payload={'worldResourceCounterVersion':1,'purpose':'resource-census-only','inputAllowed':False}
        self.participant.hold_file_before_init(self.writer,self.store,self.payload)
        LifecycleProcessFile.__init__(self.writer,self.store);self.writer.write(self.payload,None)
        self.participant.file_ready(self.writer)
        return self.participant.census()
    def close(self):
        for owner in self.owners:
            self.closes.append(owner.close_host() if hasattr(owner,'parent') else False)
        self.closes.append(self.participant.close_host())
        for key,value in self.environment.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        return self.closes


def failure_numbers(participant):
    # No exception/traceback objects escape this function into test references.
    found=False;error_id=trace_id=None
    try:participant.census()
    except NativeUIError as original:
        found=True;error_id=id(original);trace_id=id(original.__traceback__)
    return found,error_id,trace_id


def owned_failure(participant,numbers):
    gc.collect()
    assert numbers[0] and participant.failure is not None
    error,tb=participant.failure
    assert id(error)==numbers[1]
    # Stored first TB starts at the original participant catch; the reraised
    # exception acquires the outside caller frame later. Match the exact stored
    # TB within that same original error chain; never invent an exception.
    chain=[];node=error.__traceback__;owned=False
    while node is not None:
        owned|=node is tb
        chain.append({'name':node.tb_frame.f_code.co_name,'line':node.tb_lineno,
            'source':node.tb_frame.f_code.co_filename})
        node=node.tb_next
    assert owned and id(error.__traceback__)==numbers[2]
    return {'ownerErrorIdentity':id(error),'ownerFirstTracebackIdentity':id(tb),
        'outsideOriginalTracebackIdentity':numbers[2],'trace':chain,'afterTestExceptionRefsDroppedAndGC':True}


def actual_root_inode_replacement(artifacts):
    f=Fixture(artifacts);report={};caught=None
    try:
        before=f.file();p=f.participant;original=f.writer
        original_node=p.directory.node;file_node=original.file.node
        replacement=object.__new__(LifecycleProcessFile)
        store=PrivateFeatureState(f.store.path)
        p.hold_counter_candidate(replacement,store,f.payload)
        assert p.counter_candidate[0] is replacement and not vars(replacement)
        f.owners.append(replacement)
        work=p.counter_candidate[3];assert work<=131072 and p.metadata_claims[-1]==131072
        protected=artifacts/'retained-original-root'
        assert len(str(protected).encode())<=len(str(store.path).encode())+512
        os.rename(f.parent.root,protected)
        f.parent.root.mkdir(mode=0o700)
        # Both directories are task-owned. Persist their actual rename/create.
        descriptor=os.open(f.parent.root.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        LifecycleProcessFile.__init__(replacement,store);replacement.write(f.payload,None)
        new_node=replacement.parent.node;new_file_node=replacement.file.node
        original.file.require(original.file.fd);p.directory.require(p.directory.fd)
        assert p.directory.node==original_node and original.file.node==file_node
        numbers=failure_numbers(p)
        custody=owned_failure(p,numbers)
        # Actual error source line proves names()/directory failure occurred
        # before Parent.pins, without replacing/instrumenting any function.
        rows=custody['trace'];assert any(row['name']=='require_directory' for row in rows)
        assert any(row['name']=='names' for row in rows)
        assert not any(row['name']=='pins' for row in rows)
        assert len(p.snapshots)==1 and len(p.metadata_claims)==2
        assert p.counter_candidate[0] is replacement and p.records[0]['owner'] is original
        assert new_node!=original_node and new_file_node!=file_node
        old_bytes=os.pread(original.file.fd,65537,0)
        assert old_bytes==original.raw==replacement.raw and hashlib.sha256(old_bytes).hexdigest()==before['pins'][0]['sha256']
        assert (protected/store.path.name).read_bytes()==old_bytes and store.path.read_bytes()==old_bytes
        assert f.original.sdk_calls==f.original.inputs==0 and f.parent.state is f.parent.disk is None
        report={'case':'actual_root_inode_replacement','firstCensus':before,'faultCredit':131072,
            'actualRequiredCounterBound':work,'originalRootNode':original_node,'replacementRootNode':new_node,
            'originalFileNode':file_node,'replacementFileNode':new_file_node,'sameBytes':len(old_bytes),
            'counterCandidateStrongBeforeCtor':True,'custody':custody,'sdkCalls':0,'inputs':0,
            'aggregateCapQualified':False,'parentNativeRetirementQualified':False}
    finally:report['knownHostCloses']=f.close()
    assert all(report['knownHostCloses'])
    return report


def credit_data_refusal(artifacts):
    f=Fixture(artifacts);report={}
    try:
        before=f.participant.census();p=f.participant
        original_claims=list(p.entry_claims);metadata=list(p.metadata_claims)
        p.credit['precount']=True
        numbers=failure_numbers(p);custody=owned_failure(p,numbers)
        assert p.entry_claims==original_claims and p.metadata_claims==metadata
        assert list(f.parent.root.iterdir())==[] and len(p.snapshots)==1
        assert any(row['name']=='check_data' for row in custody['trace'])
        assert not any(row['name'] in ('names','pins') for row in custody['trace'])
        assert f.original.sdk_calls==f.original.inputs==0 and p.precount==2097152 and p.window==196608
        report={'case':'credit_data_refusal','before':before,'creditDataType':'bool',
            'entryClaimsHeld':original_claims,'metadataClaimsHeld':metadata,'custody':custody,
            'actualNewFiles':0,'sdkCalls':0,'inputs':0,'actualAggregateCapQualified':False,
            'parentNativeRetirementQualified':False}
    finally:report['knownHostCloses']=f.close()
    assert all(report['knownHostCloses'])
    return report


"""Actual cold World source callsite: missing stage must precede factory SDK."""
import gc,os,uuid
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_root_resource import WorldRootSelection1
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


class NamespaceFactoryCounter(NamespaceOnlyAdapter):
    def __init__(self,path):
        super().__init__(path);self.current_factory_calls=0
    def _world_current_input_originals(self,target,*,source_lock,root_resources=None):
        self.current_factory_calls+=1
        raise RuntimeError('Missing-stage gate allowed the original factory')


def absent_current_stage(artifacts):
    base=artifacts/'namespace';base.mkdir(mode=0o700)
    adapter=NamespaceFactoryCounter(base);flow=None;report={}
    config={'OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
        'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'https://world-resource.invalid/scene.json'}
    previous={key:os.environ.get(key) for key in config};os.environ.update(config)
    try:
        binding=PicoWorldWebBinding(adapter)
        phase=PhaseFixtureReader(Client('https://primary.invalid/feature-fixture/v1','n'*32),uuid.uuid4().hex,'world-web')
        flow=binding.prefix('namespace-target',phase,'https://foreign.invalid/feature-fixture/v1',resource_selection=WorldRootSelection1())
        participant=flow.resource_participant
        found=False;error_id=None
        try:binding.world_prefix_current_source('namespace-target',flow)
        except NativeUIError as original:
            found=True;error_id=id(original)
        # The test's except reference is gone before GC. Only owner custody is
        # inspected afterwards. All assertions are outside SourceLock.
        gc.collect()
        assert found and participant.failure is not None and id(participant.failure[0])==error_id
        assert str(participant.failure[0])=='Typed current-source resource provider is absent'
        names=[];tb=participant.failure[0].__traceback__
        while tb is not None:
            names.append({'name':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno,'source':tb.tb_frame.f_code.co_filename});tb=tb.tb_next
        assert any(row['name']=='admit_current_factory' for row in names)
        assert any(row['name']=='world_prefix_current_source' for row in names)
        assert not any(row['name']=='_world_current_input_originals' for row in names)
        assert adapter.current_factory_calls==adapter.sdk_calls==adapter.inputs==0
        assert len(participant.snapshots)==1 and participant.snapshots[0]['bill']['S']==0
        assert flow.disk is flow.state is flow.history is flow.vm is phase.previous is None
        assert list(flow.root.iterdir())==[] and flow.lock._owner is None
        report={'case':'absent_current_stage','originalWorldSourceCallsite':True,
            'currentFactoryCalls':adapter.current_factory_calls,'sdkCalls':adapter.sdk_calls,'inputs':adapter.inputs,
            'actualRootFiles':0,'firstOwnerErrorIdentity':error_id,'ownerFirstTBHeldAfterGC':True,
            'trace':names,'entryClaims':list(participant.entry_claims),
            'metadataClaims':list(participant.metadata_claims),'resourceSnapshot':participant.snapshots[0],
            'positiveCurrentSourceQualified':False,'nativeDeviceQualified':False,'parentRetirementQualified':False}
    finally:
        if flow is not None:report['directoryKnownClose']=flow.resource_participant.close_host()
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    assert report['directoryKnownClose']
    return report


"""ONE proposed actual cold Parent/sameRoot/read-only HOST source component."""
import hashlib,os,time,uuid
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_current_document import PicoWorldCurrentDocument
from adapters.pico4.world_current_input import PicoWorldCurrentInput
from adapters.pico4.world_current_host_stage import WorldDocumentModelAdapter1,WorldCurrentHostSelection1,WorldRootCurrentParticipant2
from adapters.pico4.world_document_model import WorldDocumentModelContext1
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


def normal_cold_document(artifacts):
    run=uuid.uuid4().hex;url='https://primary.invalid/feature-fixture/v1/runs/'+run+'/'
    context=WorldDocumentModelContext1(run,url,*[uuid.uuid4().hex for _ in range(5)],str(uuid.uuid4()),uuid.uuid4().hex)
    # Positional fields are checked explicitly before owner birth. Entity is a
    # UUID; all nonce fields are128bit hex. No produced envelope is rewritten.
    context.validate()
    base=artifacts/'namespace';base.mkdir(mode=0o700)
    adapter=WorldDocumentModelAdapter1(base,context)
    config={'OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
        'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'https://world-resource.invalid/scene.json'}
    previous={key:os.environ.get(key) for key in config};os.environ.update(config)
    parent=None;binding=None;report={};first_error=None
    try:
        binding=PicoWorldWebBinding(adapter)
        phase=PhaseFixtureReader(Client('https://primary.invalid/feature-fixture/v1','n'*32),run,'world-web')
        parent=binding.prefix('namespace-target',phase,'https://foreign.invalid/feature-fixture/v1',resource_selection=WorldCurrentHostSelection1(context))
        resources=parent.resource_participant
        assert type(resources) is WorldRootCurrentParticipant2 and resources.ready
        assert parent.state is parent.disk is parent.history is parent.vm is phase.previous is None
        io=binding.world_prefix_current_source('namespace-target',parent)
        assert type(io) is PicoWorldCurrentInput and type(io.documents) is PicoWorldCurrentDocument
        assert io.documents is resources.reader and io.documents.resource_provider is resources
        assert io.documents.monotonic is phase.monotonic
        started=time.perf_counter();value=io.documents.read(run,url,context.owner);elapsed=time.perf_counter()-started
        # Completion assertions OUTSIDE all SourceLocks/normalizers. No retry.
        assert resources.current is None and resources.failure is None and len(resources.completed)==1
        call=resources.completed[0];plan=call['plan'];original=io.documents.original()
        assert value==io.documents.last and value is not io.documents.last
        assert value['commandId']==original['request']['commandId']==resources.model.request['commandId']
        assert resources.raw.state['reads']==2 and not resources.raw.state['pending']
        assert resources.model.sequence==1 and adapter.factory_calls==1
        literal=resources.raw.literal(call['raw_ref'])
        assert literal==original['raw'] and hashlib.sha256(literal.encode()).hexdigest()==call['raw_ref']['sha256']
        assert value['source']['originalFinish']['finishedEpochMs']==resources.model.finished_epoch
        assert value['source']['originalFinish']['grant']==1 and value['source']['authorityAfter']['native']['grant']==2
        assert parent.state is parent.disk is parent.history is parent.vm is phase.previous is None
        final=resources.census();assert final['decodedBytes']<=16777216 and final['storedBytes']<=16777216 and final['files']<=512
        assert adapter.sdk_calls==adapter.inputs==0
        report={'case':'normal_cold_document','elapsedOutsideBusinessClocks':elapsed,
            'actualParentConstructor':True,'factoryKind':'DECLARED_BOUNDED_HOST_MODEL','canonicalPicoBoundFactoryQualified':False,
            'originalCurrentDocumentMethod':True,'oneNewModelQuery':resources.model.sequence,
            'actualModelProtocolReceipts':resources.raw.state['reads'],'actualSDKCalls':adapter.sdk_calls,'inputs':adapter.inputs,
            'globalBill':final,'retainedCallWork':call['work'],'retainedEntry':call['entry'],
            'modelCredit':resources.model_credit,'rawSourceSha256':call['raw_ref']['sha256'],
            'rawReference':call['raw_ref'],'commandId':value['commandId'],'originalFinal1_5FencePassed':True,
            'finishEpochUnchanged':True,'plan':{'maxCanonical':plan.max_canonical,'nodes':plan.total_nodes,
                'depth':plan.combined_depth,'streams':list(plan.streams),'decodedData':plan.decoded_data,
                'decodedMetadata':plan.decoded_metadata,'callWork':plan.call_work},
            'sourceModelFileSha256':hashlib.sha256(resources.model.file.raw).hexdigest(),
            'nativeDeviceQualified':False,'normalFocusImeEffectQualified':False,'parentRetirementQualified':False,
            'wholeClaim':False,'parentPrepared':False}
    except BaseException as error:
        first_error=error
        if parent is None:parent=getattr(binding,'_resource_parent',None)
        if parent is not None and parent.resource_participant is not None:parent.resource_participant.fail(error)
        raise
    finally:
        if parent is not None and parent.resource_participant is not None:
            try:report['knownHostCloses']=parent.resource_participant.close_host()
            except BaseException:
                if first_error is None:raise
                report['knownHostCloses']=[False]
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    assert all(report['knownHostCloses'])
    return report



from copy import deepcopy
import json
RUN='1'*32;OWNER='2'*32;URL='http://127.0.0.1/feature-fixture/v1/runs/'+RUN+'/'

def fixture(request=None):
    request=request or dict(schemaVersion=1,commandId='3'*32,action='pico-world-web',runId=RUN,
                            fixtureUrl=URL,operation='observe-current-document',ownerToken=OWNER)
    url=URL+'tickets/'+'4'*32+'/index.html'
    base=dict(handle='1',creation=3,grant=6,page=1,url=url,sourceUrl=url)
    native=dict(base,itemInstance='5'*32,sourceIdentity='web-entity:12345678-1234-1234-1234-123456789abc',
                created=True,authorized=True,sessionActive=True,suspended=False,loading=False,capturedEpochMs=10000,capturedMonotonicMs=20000)
    java=dict(base,ownerCurrent=True,active=True,foreground=True,windowFocused=True,destroyed=False,closing=False,loading=False,
              capturedEpochMs=10001,capturedElapsedMs=30000)
    before=dict(native=deepcopy(native),java=deepcopy(java));native.update(capturedEpochMs=10003,capturedMonotonicMs=20003)
    java.update(capturedEpochMs=10003,capturedElapsedMs=30002);after=dict(native=native,java=java)
    finish=dict(handle='1',creation=3,grant=4,page=1,url=url,finishedEpochMs=9000)
    dom=dict(webDOMVersion=1,requestId=request['commandId'],instance='6'*32,sequence=1,capturedEpochMs=10002,
             document=dict(runId=RUN,href=url,responseId='7'*32,readyState='complete'),editor=dict(text='',focused=False),attempts=[],echoes=[])
    transaction=dict(before=before['java'],domRaw=json.dumps(json.dumps(dom)),after=after['java'])
    value=dict(picoWorldCurrentDocumentVersion=1,commandId=request['commandId'],runId=RUN,ownerToken=OWNER,instance='8'*32,
               sequence=1,processId=123,requestedEpochMs=10000,requestedMonotonicMs=20000,capturedEpochMs=10004,capturedMonotonicMs=20004,
               status='ready',source=dict(authorityBefore=before,authorityAfter=after,originalFinish=finish,documents=[deepcopy(finish)],
                                        domRaw=json.dumps(transaction),dom=dom))
    return request,value
