"""Whole Create retirement from retained app originals, before paired release.

Normal cleanup intentions remain in CreateActions/MarkerScope. This owner joins
their actual outcomes to the original editor worker, scene, Qt pointer dispatch,
native files, GPU storage and fenced former-marker pixels. An unsuccessful or
interrupted acquisition remains responsibility; it cannot manufacture quiet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy,copy
from contextlib import contextmanager
import time

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import absent
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier,result
from ios.adapters import create_lifecycle,pointer_state,create_state,create_work
from ios.adapters.create_actions import CreateActions,semantic_map
from ios.adapters.create_actor_facts import CreateActorFacts
from ios.adapters.create_marker_measurements import body_preserved,view_preserved
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.create_primary import CreatePrimary
from ios.adapters.create_product_state import project
from ios.adapters.create_restoration_image import restored
from ios.adapters.create_sample import CreateSampleOwner
from ios.adapters.create_sources import CreateSources
from ios.adapters.create_world_input import CreateWorldInput

VERSION=1
MAX_RECORDS=160


def script_inventory(domain,work,scripts_root):
    source=domain['source']['scriptOriginal']['source']
    need(source.get('membershipSourceVersion')==1 and source['membership']['complete'])
    edit=next(row for row in create_work.admit(work,scripts_root)['roles'] if row['role']=='edit')
    need(any(same(row,edit['manager']) for row in source['membership']['managers']))
    actual=[row for row in source['engines'] if row['required']['instance']==edit['manager']['instance']]
    need(len(actual)==1 and actual[0]['url']==edit['manager']['url'] and same(actual[0].get('code'),edit['code'])
        and actual[0]['running'] and not actual[0]['stopping'] and not actual[0]['finished'])
    engines=[]
    for row in source['engines']:
        engines.append(dict(url=row['url'],running=row['running'],stopping=row['stopping'],finished=row['finished'],
            required=dict(instance=row['required']['instance'],sequence=row['required']['sequence'],
                modules=[{key:item[key] for key in ('url','loaded','cached','sequence')} for item in row['required']['modules']]),
            code=deepcopy(row.get('code'))))
    return dict(managers=sorted(source['membership']['managers'],key=lambda row:row['instance']),
        engines=sorted(engines,key=lambda row:row['required']['instance']))


class CreateRetirement:
    """Actual per-device whole cleanup; remote retirement is a separate join."""
    def __init__(self,store,source,history,pointer,*,actions=None,scope=None,before_image=None,
                 image_factory=None,epoch_ms=None,monotonic=None,sleep=time.sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(source,CreateSources)
            and source.role in ('primary','actor') and not source.historical
            and isinstance(pointer,pointer_state.IOSPointerState) and pointer.pid==source.pid)
        self.store,self.source,self.history,self.pointer=store,source,history,pointer
        self.lock,self.binding,self.run,self.role=source.lock,deepcopy(source.binding),source.run,source.role
        self.actions,self.scope,self.before_image,self.image_factory=actions,scope,before_image,image_factory
        self.epoch_ms=source.epoch_ms if epoch_ms is None else epoch_ms
        self.monotonic=source.monotonic if monotonic is None else monotonic;self.sleep=sleep
        need(all(callable(fn) for fn in (self.epoch_ms,self.monotonic,sleep))
            and store.path==source.store.path.with_name('ios-create-'+self.role+'-retirement.json'))
        if self.role=='primary':
            need(isinstance(history,CreatePrimary) and history.source is source and history.lock is self.lock
                and isinstance(scope,CreateMarkerScope) and scope.lock is self.lock and scope.run==self.run
                and same(scope.binding,self.binding) and (actions is None or isinstance(actions,CreateActions))
                and isinstance(before_image,CreateSampleOwner) and before_image.lock is self.lock
                and before_image.run==self.run and same(before_image.binding,self.binding) and callable(image_factory))
        else:
            need(isinstance(history,CreateActorFacts) and history.peer is source and history.lock is self.lock
                and actions is scope is before_image is image_factory is None)
        self.lock.assert_held();self.previous=store.read()
        self._source_validation=None
        self.state=dict(baseline=None,ticket=None,phase='new',images=[],imageScope=None,records=[],pending=None,interrupted=[],quiet=[])
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosCreateRetirementVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();self.source.bound()
        need(same(self.store.read(),self.previous) and self.source.binding==self.binding and self.source.run==self.run)

    def save(self):
        # Existing immutable records were validated when appended. Reopening
        # their entire dependency graph at every pending field write would make
        # one bounded native acquisition exceed its clock budget. Publication
        # and reconstruction independently reopen the whole actual prefix.
        self.bound();value=self.envelope(self.state)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    @contextmanager
    def validation_round(self):
        if self._source_validation is not None:
            yield;return
        packet=self.source.store.read();state,frames=self.source.decode(packet)
        self._source_validation=(packet,state,frames)
        try:yield
        finally:
            try:need(same(self.source.store.read(),packet))
            finally:self._source_validation=None

    def record_store(self,index):
        need(integer(index,1,MAX_RECORDS));return PrivateFeatureState(self.store.path.with_name('ios-create-'+self.role+'-retirement-'+str(index)+'.json'))

    def retain_component(self,kind,value):
        if value is None:return None
        need(type(kind) is str and kind in ('history','actions','scope','files','sample','gpu','world'))
        packet=dict(iosCreateRetirementComponentVersion=1,binding=self.binding,runId=self.run,role=self.role,kind=kind,value=value)
        sha=digest(packet);target=PrivateFeatureState(self.store.path.with_name('ios-create-'+self.role+'-retirement-component-'+sha+'.json'))
        previous=target.read()
        if previous is None:target.write(packet,None)
        need(same(target.read(),packet));return dict(sha256=sha)

    def load_component(self,kind,reference):
        if reference is None:return None
        exact(reference,{'sha256'});sha=reference['sha256']
        need(type(sha) is str and len(sha)==64 and all(char in '0123456789abcdef' for char in sha))
        value=PrivateFeatureState(self.store.path.with_name('ios-create-'+self.role+'-retirement-component-'+sha+'.json')).read()
        need(value is not None and digest(value)==sha);exact(value,{'iosCreateRetirementComponentVersion','binding','runId','role','kind','value'})
        need(type(value['iosCreateRetirementComponentVersion']) is int and value['iosCreateRetirementComponentVersion']==1
            and value['binding']==self.binding and value['runId']==self.run and value['role']==self.role and value['kind']==kind)
        return deepcopy(value['value'])

    def retain_components(self,value):
        fields=('history',) if self.role=='actor' else ('history','actions','scope','files')
        result=dict(iosCreateRetirementComponentsVersion=1,**{name:self.retain_component(name,value[name]) for name in fields})
        if self.role=='primary':
            result['samples']=[dict(requestId=row['requestId'],sample=self.retain_component('sample',row['sample']),
                native=self.retain_component('gpu',row['native'])) for row in value['samples']]
            result['worldInputs']=[dict(ticket=row['ticket'],owner=self.retain_component('world',row['owner'])) for row in value['worldInputs']]
        return result

    def load_components(self,value):
        fields=('history',) if self.role=='actor' else ('history','actions','scope','files')
        exact(value,{'iosCreateRetirementComponentsVersion',*fields}|(set() if self.role=='actor' else {'samples','worldInputs'}))
        need(type(value['iosCreateRetirementComponentsVersion']) is int and value['iosCreateRetirementComponentsVersion']==1)
        result={name:self.load_component(name,value[name]) for name in fields}
        if self.role=='primary':
            need(type(value['samples']) is list and len(value['samples'])<=80 and type(value['worldInputs']) is list and len(value['worldInputs'])<=128)
            result['samples']=[];result['worldInputs']=[]
            for row in value['samples']:
                exact(row,{'requestId','sample','native'});result['samples'].append(dict(requestId=row['requestId'],
                    sample=self.load_component('sample',row['sample']),native=self.load_component('gpu',row['native'])))
            for row in value['worldInputs']:
                exact(row,{'ticket','owner'});result['worldInputs'].append(dict(ticket=row['ticket'],owner=self.load_component('world',row['owner'])))
        return result

    def source_frame(self,reference):
        exact(reference,{'index','sha256'})
        # Reopen every carrier and its actual validated predecessors. A mutable
        # source.frames array never provides a floor, including warm uses.
        with self.validation_round():
            _,state,frames=self._source_validation
            need(integer(reference['index'],1,len(frames)) and same(reference,state['records'][reference['index']-1]))
            return deepcopy(frames[reference['index']-1])

    def frame(self,reference):
        with self.validation_round():return self._frame(reference)

    def _frame(self,reference):
        exact(reference,{'index','sha256'});packet=self.record_store(reference['index']).read()
        need(packet is not None and digest(packet)==reference['sha256'])
        exact(packet,{'iosCreateRetirementRecordVersion','binding','runId','role','payload'})
        rows=unpack(packet['payload']);need(len(rows)==1 and type(packet['iosCreateRetirementRecordVersion']) is int
            and packet['iosCreateRetirementRecordVersion']==VERSION and same(packet['binding'],self.binding)
            and packet['runId']==self.run and packet['role']==self.role)
        frame=rows[0];exact(frame,{'index','label','source','originals','clockJoin','components'})
        need(frame['index']==reference['index'] and frame['label'] in ('baseline','quiet','confirmation'))
        source=self.source_frame(frame['source']);originals=frame['originals'];clock=validate_join(frame['clockJoin'],originals)
        exact(originals,{'pointer','sourceEnd'}|({'files'} if 'files' in originals else set())
            |({'markerFiles'} if 'markerFiles' in originals else set())|{key for key in originals if key.startswith('gpu-')})
        need(same(originals['sourceEnd'],source['clockJoin']['nativeAfter'])
            and clock['nativeBefore']['processId']==clock['nativeAfter']['processId']==self.source.pid
            and clock['nativeBefore']['instance']==source['clockJoin']['nativeBefore']['instance']==clock['nativeAfter']['instance']
            and clock['nativeBefore']['capturedEpochMs']<=source['clockJoin']['nativeBefore']['capturedEpochMs']
            and source['clockJoin']['nativeAfter']['capturedEpochMs']<=originals['pointer']['clockBefore']['epochMs']
            and originals['pointer']['clockAfter']['epochMs']<=clock['nativeAfter']['capturedEpochMs']
            and clock['hostBeforeMonotonic']<=source['clockJoin']['hostBeforeMonotonic']
            and source['clockJoin']['hostAfterMonotonic']<=clock['hostAfterMonotonic']
            and same(clock['nativeBefore']['lifecycle'],clock['nativeAfter']['lifecycle']))
        pointer_state.original(originals['pointer']);need(originals['pointer']['runId']==self.run and originals['pointer']['processId']==self.source.pid)
        if frame['label']=='baseline':need(frame['components'] is None)
        else:self.components(frame['components'],frame)
        return deepcopy(frame)

    def decode(self,value):
        with self.validation_round():return self._decode(value)

    def _decode(self,value):
        exact(value,{'iosCreateRetirementVersion','binding','runId','role','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosCreateRetirementVersion']) is int and value['iosCreateRetirementVersion']==VERSION
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'baseline','ticket','phase','images','imageScope','records','pending','interrupted','quiet'})
        need(state['phase'] in ('new','admitted','cleaning','quiet','retired') and type(state['records']) is list
            and len(state['records'])<=MAX_RECORDS and type(state['images']) is list and len(state['images'])<=16
            and type(state['interrupted']) is list and len(state['interrupted'])<=16 and type(state['quiet']) is list)
        for name in state['images']:need(type(name) is str and name.startswith('ios-'));identifier(name[4:])
        need(len(set(state['images']))==len(state['images']))
        if state['ticket'] is not None:identifier(state['ticket'])
        if self.role=='actor':need(state['images']==[] and state['imageScope'] is None)
        old=None;history_prefix=None
        for index,ref in enumerate(state['records'],1):
            frame=self.frame(ref);need(frame['index']==index)
            if frame['components'] is not None:
                history=self.load_component('history',frame['components']['history'])
                # components() has already rederived this exact historical
                # original. Its chosen prefix cannot rewind or substitute an
                # earlier complete history while native clocks advance.
                current=unpack(history['payload'])[0]['records']
                if history_prefix is not None:need(len(current)>=len(history_prefix) and same(current[:len(history_prefix)],history_prefix))
                history_prefix=deepcopy(current)
            if old is not None:
                a,b=old['clockJoin'],frame['clockJoin'];need(a['hostAfterMonotonic']<=b['hostBeforeMonotonic']
                    and a['hostAfterEpochMs']<=b['hostBeforeEpochMs'] and a['nativeAfter']['instance']==b['nativeBefore']['instance']
                    and a['nativeAfter']['sequence']<b['nativeBefore']['sequence'])
                pointer_state.validate(frame['originals']['pointer'],dict(schemaVersion=1,commandId=frame['originals']['pointer']['requestId'],
                    action=pointer_state.ACTION,runId=self.run),self.source.pid,previous=old['originals']['pointer'])
            old=frame
        if state['baseline'] is not None:need(state['baseline']==state['records'][0] and self.frame(state['baseline'])['label']=='baseline')
        if state['phase']!='new':need(state['baseline'] is not None)
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            exact(pending,{'label','start','source','originals','components'});need(pending['label'] in ('baseline','quiet','confirmation')
                and type(pending['originals']) is dict)
        need(all(integer(index,2,len(state['records'])) for index in state['quiet'])
            and state['quiet']==sorted(set(state['quiet'])))
        if state['phase']=='retired':self.qualification(state)
        return deepcopy(state)

    def admit(self,*,unexecuted=False):
        self.bound();need(self.state['phase']=='new' and self.state['baseline'] is None)
        need(type(unexecuted) is bool);image=None
        if self.role=='primary':
            need(self.scope.state['phase']=='new' and self.before_image.state is not None)
            if unexecuted:
                # A lost raw pre-marker read never becomes an image. Only
                # the wholly unexecuted Scope may retire this native owner.
                need(self.before_image.state['phase']=='reading')
            else:
                from ios.adapters.create_restoration_image import original
                image,_=original(self.before_image)
                need(image['clockJoin']['nativeAfter']['capturedEpochMs']<=self.epoch_ms())
        else:need(not unexecuted and self.history.state['records'])
        frame=self.capture('baseline');source=self.source_frame(frame['source'])
        need(not source['originals']['createAfter']['source']['tabletShown'])
        initial_frame=self.history.frame(self.history.record_entries()[0]['before']) if self.role=='primary' else self.history.frame(self.history.peer,
            self.history.state['records'][0]['peer'])
        initial=self.history.baseline() if self.role=='primary' else initial_frame['originals']['createAfter']
        need(same(semantic_map(initial),semantic_map(source['originals']['createAfter'])))
        body_preserved(initial_frame['originals']['domain'],source['originals']['domain']);view_preserved(initial,source['originals']['createAfter'])
        if self.role=='primary' and image is not None:
            need(same(semantic_map(image['originals']['createAfter']),semantic_map(source['originals']['createAfter']))
                and image['clockJoin']['nativeAfter']['capturedEpochMs']<=source['clockJoin']['nativeBefore']['capturedEpochMs'])
        point=frame['originals']['pointer'];need(point['source']['complete'] and point['source']['pendingDispatches']==0
            and not point['source']['contacts'] and point['source']['qtMouseButtons']==0 and not point['source']['worldTapActive'])
        self.state['baseline']=deepcopy(self.state['records'][0]);self.state['phase']='admitted';self.save();return deepcopy(frame)

    def capture(self,label):
        self.bound();need(label in ('baseline','quiet','confirmation') and len(self.state['records'])<MAX_RECORDS)
        if self.state['pending'] is not None:
            # A complete orphan carrier is adopted by its exact durable prefix;
            # an incomplete read gets a new read-only acquisition, never retimed.
            extra=self.record_store(len(self.state['records'])+1).read()
            if extra is not None:
                ref=dict(index=len(self.state['records'])+1,sha256=digest(extra));old=self.frame(ref)
                need(old['label']==self.state['pending']['label'] and same(old['originals'],self.state['pending']['originals'])
                    and same(old['source'],self.state['pending']['source']) and same(old['components'],self.state['pending']['components'])
                    and all(same(old['clockJoin'][key],value) for key,value in self.state['pending']['start'].items()))
                self.state['records'].append(ref)
            else:self.state['interrupted'].append(deepcopy(self.state['pending']))
            self.state['pending']=None;self.save()
        pending=dict(label=label,start=None,source=None,originals={},components=None);self.state['pending']=pending;self.save()
        clock=NativeClockAcquisition(self.source.readers['native'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(self.epoch_ms());pending['start']=deepcopy(clock.started);self.save()
        source=self.source.capture('whole-'+label);pending['source']=deepcopy(self.source.state['records'][-1])
        pending['originals']['sourceEnd']=deepcopy(source['clockJoin']['nativeAfter']);self.save()
        if label!='baseline':
            pending['components']=self.retain_components(self.collect_components(pending['originals']));self.save()
        pending['originals']['pointer']=self.pointer.read(self.run);self.save()
        fields=[(name,field) for name,row in pending['originals'].items() if type(row) is dict for field in ('capturedEpochMs','sampleEpochMs') if field in row]
        frame=dict(index=len(self.state['records'])+1,label=label,source=deepcopy(pending['source']),originals=deepcopy(pending['originals']),
            components=deepcopy(pending['components']),clockJoin=clock.finish(pending['originals'],fields))
        carrier=dict(iosCreateRetirementRecordVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([frame]))
        target=self.record_store(frame['index']);need(target.read() is None);target.write(carrier,None)
        reference=dict(index=frame['index'],sha256=digest(carrier));self.frame(reference)
        self.state['records'].append(reference);self.state['pending']=None;self.save();return deepcopy(frame)

    def all_samples(self,state=None):
        if self.role=='actor':return []
        owners={owner.request:owner for owner in self.history.owned_samples()}
        owners[self.before_image.request]=self.before_image
        for request in (self.state if state is None else state)['images']:
            owner=self.image_factory(request);need(isinstance(owner,CreateSampleOwner) and owner.request==request
                and owner.run==self.run and owner.lock is self.lock and same(owner.binding,self.binding));owners[request]=owner
        return list(owners.values())

    def collect_components(self,originals):
        if self.role=='actor':return dict(history=deepcopy(self.history.store.read()))
        need(self.scope.state['phase']=='released')
        fresh=self.scope.capture('whole-cleanup')
        scope=self.scope.snapshot();archive=self.scope.archive(scope,root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        base=archive.frames[archive.state['baseline']-1];owned=archive.state['admission']
        if owned is not None:archive.restored_marker(base,fresh,owned,archive.state['stopBarrier'])
        else:archive.unexecuted(fresh)
        archive.ui_absent(fresh);archive.dialog_drained(fresh)
        if archive.state['fileOwnership'] is not None:
            token=archive.state['fileOwnership']['ownerToken'];value=self.scope.files.native.request('observe',self.run,token)
            need(value==dict(exists=False,files=[]));originals['markerFiles']=deepcopy(self.scope.files.native.last_packet)
        actions=None if self.actions is None else self.actions.store.read()
        files=None
        if self.actions is not None and self.actions.files.state is not None:
            need(self.actions.files.state['phase']=='retired');originals['files']=self.actions.files.observe();files=self.actions.files.store.read()
        samples=[]
        for owner in self.all_samples():
            proof=owner.retire_runtime()
            if proof is not None:originals['gpu-'+owner.request[4:]]=deepcopy(proof)
            samples.append(dict(requestId=owner.request,sample=deepcopy(owner.store.read()),native=deepcopy(owner.frame_owner.store.read())))
        worlds=[]
        if actions is not None:
            for call in self.actions.state['calls']:
                if call['query']['verb']!='voxel-edit':continue
                world=self.actions.world_factory(call['query']['ticket']);need(isinstance(world,CreateWorldInput))
                worlds.append(dict(ticket=call['query']['ticket'],owner=deepcopy(world.store.read())))
        return dict(history=deepcopy(self.history.store.read()),actions=deepcopy(actions),scope=scope,files=deepcopy(files),samples=samples,worldInputs=worlds)

    def components(self,value,frame):
        value=self.load_components(value)
        source=self.source_frame(frame['source']);epoch=frame['clockJoin']['nativeAfter']['capturedEpochMs']
        if self.role=='actor':
            exact(value,{'history'});self.history.decode(value['history']);return
        exact(value,{'history','actions','scope','files','samples','worldInputs'});self.history.decode(value['history'])
        scope=self.scope.archive(value['scope'],root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        need(value['scope']['iosCreateMarkerScopeVersion']>=2 and scope.state['phase']=='released' and scope.state['pending'] is None)
        current=scope.frames[-1];need(current['label']=='whole-cleanup'
            and source['clockJoin']['nativeAfter']['capturedEpochMs']<=current['clockJoin']['nativeBefore']['capturedEpochMs']
            and current['clockJoin']['nativeAfter']['capturedEpochMs']<=epoch)
        baseline=scope.frames[scope.state['baseline']-1]
        if scope.state['admission'] is not None:scope.restored_marker(baseline,current,scope.state['admission'],scope.state['stopBarrier'])
        else:scope.unexecuted(current)
        scope.ui_absent(current);scope.dialog_drained(current)
        if scope.state['fileOwnership'] is not None:
            packet=frame['originals']['markerFiles'];exact(packet,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
            old=scope.state['fileAbsence']
            need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['operation']=='observe'
                and type(packet['sequence']) is int and packet['sequence']>old['sequence'] and packet['instance']==old['instance']
                and packet['requestId']!=old['requestId'] and packet['source']==dict(exists=False,files=[]) and packet['runId']==self.run
                and packet['processId']==self.source.pid and current['clockJoin']['nativeAfter']['capturedEpochMs']<=packet['requestedEpochMs']<=packet['capturedEpochMs']<=epoch)
            from adapters.native_script_files import NativeScriptFiles
            NativeScriptFiles.validate_source(packet['source'],'observe',self.run)
        if value['actions'] is not None:
            need(self.actions is not None);actions=self.actions.decode(value['actions'])
            need(actions['phase']=='cleaning' and actions['cleanup'] is not None and actions['cleanup']['phase']=='acknowledged'
                and self.actions.cleanup_restored(source['originals']['createAfter']))
        else:need(self.actions is None or self.actions.state is None)
        expected=[] if value['actions'] is None else [call for call in actions['calls'] if call['query']['verb']=='voxel-edit']
        need(type(value['worldInputs']) is list and [row['ticket'] for row in value['worldInputs']]==[call['query']['ticket'] for call in expected])
        for row,call in zip(value['worldInputs'],expected):
            exact(row,{'ticket','owner'});world=self.actions.world_factory(row['ticket'])
            need(isinstance(world,CreateWorldInput) and world.binding==self.binding and world.run==self.run and world.ticket==row['ticket'])
            if row['owner'] is None:need(call['phase']=='acting');continue
            state=world.decode(row['owner'])
            if call['phase']=='acknowledged':need(state['phase'] in ('issued','released'))
            if state['phase'] in ('issued','released'):
                carrier=self.record_store(1).read();need(carrier is not None)
                baseline=self.frame(dict(index=1,sha256=digest(carrier)))
                pointer_state.delivered(baseline['originals']['pointer'],frame['originals']['pointer'],kind='touch',position=world.qt_position(state),
                    after_epoch=state['admission']['clockAfter']['epochMs'])
        if value['files'] is not None:
            need(self.actions is not None);files=self.actions.files.decode(value['files']);packet=frame['originals']['files']
            need(files['phase']=='retired' and packet['source']==dict(exists=False,files=[])
                and same(files['originals'][-1]['packet'],packet) and packet['clockAfter']['epochMs']<=epoch)
        need(type(value['samples']) is list and len(value['samples'])<=80)
        need(len({row['requestId'] for row in value['samples']})==len(value['samples']))
        samples={owner.request:owner for owner in self.all_samples()}
        for row in value['samples']:
            if row['requestId'] not in samples:
                need(callable(self.image_factory));owner=self.image_factory(row['requestId'])
                need(isinstance(owner,CreateSampleOwner) and owner.lock is self.lock and owner.run==self.run and same(owner.binding,self.binding))
                samples[row['requestId']]=owner
        for row in value['samples']:
            exact(row,{'requestId','sample','native'});owner=samples[row['requestId']];state=owner.decode(row['sample'])
            if row['native'] is None:need(state['phase']=='reading' and 'capture' not in state['originals']);continue
            packet=frame['originals']['gpu-'+owner.request[4:]];need(absent(packet) and same(row['native']['absence'],packet)
                and row['native']['requestId']==owner.request and row['native']['binding']==self.binding
                and source['clockJoin']['nativeAfter']['capturedEpochMs']<=packet['requestedEpochMs']<=packet['capturedEpochMs']<=epoch)
            # Validate the actual once-release/inspect transcript, including
            # incomplete GPU reads that have no qualified PNG to archive.
            class Frozen(PrivateFeatureState):
                def read(_self):return deepcopy(row['native'])
            frozen=VulkanWorldFrameOwner(Frozen(owner.frame_owner.store.path),owner.frame_owner.root,self.binding,self.run,
                self.role,0,owner.request,lambda *_:need(False),lambda:True,source_lock=self.lock)
            frozen._load();need(frozen.state['phase']=='released' and same(frozen.state['absence'],packet))

    def owned_ids(self,components):
        components=self.load_components(components)
        if self.role=='primary':return [] if components['actions'] is None else [row['id'] for row in self.actions.decode(components['actions'])['owned']]
        state=self.history.decode(components['history']);before=baseline=voxel=None;owned=[]
        for entry in state['records']:
            _,baseline,owned,voxel=self.history.derive(entry,before,baseline,owned,voxel);before=entry
        return owned

    def responsibility_ids(self,frame,baseline):
        """Also retain actually observed transient resources from lost facts.

        These IDs never authorize deleting an entity or claiming its action
        succeeded. They conservatively require positive native weak expiry,
        even when an independent publication/action admission was interrupted.
        """
        first=self.source_frame(baseline['source']);last=self.source_frame(frame['source'])
        initial=set(semantic_map(first['originals']['createAfter']));ids=set(self.owned_ids(frame['components']))
        with self.validation_round():
            _,state,frames=self._source_validation
            packets=[value['originals'][name] for value in frames[first['index']-1:last['index']]
                for name in ('createBefore','createAfter')]
            for partial in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
                for name in ('createBefore','createAfter'):
                    packet=partial['originals'].get(name)
                    if packet is not None and first['clockJoin']['nativeBefore']['capturedEpochMs']<=packet['clockAfter']['epochMs']<=last['clockJoin']['nativeAfter']['capturedEpochMs']:
                        create_state.original(packet);need(packet['runId']==self.run and packet['processId']==self.source.pid);packets.append(packet)
            for packet in packets:ids.update(set(semantic_map(packet))-initial)
        if self.role=='primary':
            value=self.load_components(frame['components'])
            scope=self.scope.archive(value['scope'],root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            if scope.state['admission'] is not None:
                actual=scope.returned_entity()['returned']['entityId']
                if actual is not None:ids.discard(actual)
        return sorted(ids)

    def drained(self,frame,baseline,*,state=None):
        state=self.state if state is None else state
        first=self.source_frame(baseline['source']);last=self.source_frame(frame['source']);a,b=first['originals'],last['originals']
        need(last['phaseAfter']['active'] and last['ticket']==state['ticket']
            and last['phaseAfter']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        body_preserved(a['domain'],b['domain']);view_preserved(a['createAfter'],b['createAfter'])
        need(same(script_inventory(a['domain'],a['work'],self.source.scripts_root),script_inventory(b['domain'],b['work'],self.source.scripts_root)))
        old,new=baseline['clockJoin'],frame['clockJoin'];need(old['nativeAfter']['instance']==new['nativeAfter']['instance']
            and same(old['nativeAfter']['lifecycle'],new['nativeAfter']['lifecycle']))
        editor_baseline=None
        components=self.load_components(frame['components'])
        if self.role=='primary' and components['actions'] is not None:editor_baseline=self.actions.decode(components['actions'])['editorBaseline']
        drain=create_lifecycle.drained(a['createAfter'],a['work'],a['worker'],b['createAfter'],b['work'],b['worker'],
            self.source.scripts_root,self.responsibility_ids(frame,baseline),editor_baseline=editor_baseline)
        points=pointer_state.drained(baseline['originals']['pointer'],frame['originals']['pointer'],after_epoch=old['nativeAfter']['capturedEpochMs'])
        # Actual physical dispatch activity joins the original worker activity;
        # heartbeat/read counters and naturally elapsing timers are not reset.
        return digest(dict(worker=drain['activitySha256'],pointer=points['eventSequence'],
            nativeLifecycle=new['nativeAfter']['lifecycle'],scene=semantic_map(b['createAfter'])))

    def cleanup(self,ticket):
        self.bound();identifier(ticket);need(self.state['phase']!='new')
        if self.state['ticket'] is None:self.state.update(ticket=ticket,phase='cleaning');self.save()
        need(self.state['ticket']==ticket)
        if self.state['phase']=='retired':return self.refresh()
        if self.role=='primary':
            if self.actions is not None and self.actions.state is not None:
                self.actions.cleanup(ticket)
                baseline=self.source_frame(self.frame(self.state['baseline'])['source'])
                # Wait for real ordinary browse/entity/model callbacks before
                # unlinking JSON inputs still potentially used by the product.
                current=self.source.capture('before-file-retirement');a,b=baseline['originals'],current['originals']
                create_lifecycle.drained(self.actions.state['baseline']['create'],a['work'],a['worker'],b['createAfter'],b['work'],b['worker'],
                    self.source.scripts_root,[row['id'] for row in self.actions.state['owned']],editor_baseline=self.actions.state['editorBaseline'])
                files=self.actions.files
                if files.state is not None:
                    if files.state['phase']=='staging':files.recover_stage()
                    if files.state['phase']=='reserved':
                        need(files.observe()['source']==dict(exists=False,files=[]));files.state['phase']='retired';files.save()
                    if files.state['phase']=='staged':files.release(files.observe()['source']['files'])
                    elif files.state['phase'] in ('releasing','retired'):files.recover_release()
                    else:need(False)  # An uncertain stage remains owned.
            self.scope.cleanup()
            if self.state['imageScope'] is None:self.state['imageScope']=self.scope.snapshot();self.save()
            for sample in self.all_samples():sample.retire_runtime()
            image_scope=self.scope.archive(self.state['imageScope'],root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            marker=image_scope.state['admission']
            if marker is not None:
                captures=[self.image_factory(request) for request in self.state['images']]
                current=next((owner for owner in reversed(captures) if owner.state is not None and owner.state['phase']=='captured'),None)
                if current is None:
                    import uuid
                    request='ios-'+uuid.uuid4().hex;self.state['images'].append(request);self.save();current=self.image_factory(request)
                    current.capture(ticket,self.epoch_ms())
                admission=image_scope.frames[image_scope.state['admissionFrame']-1]['create']
                barrier=image_scope.frames[-1]['clockJoin']['nativeAfter']['capturedEpochMs']
                restored(self.before_image,current,admission,None if marker['marker'] is None else marker['marker']['id'],after_native=barrier)
        self.state['phase']='quiet';self.state['quiet']=[];self.save();started=self.monotonic();activity=None
        for attempt in range(61):
            frame=self.capture('quiet')
            try:
                with self.validation_round():current=self.drained(frame,self.frame(self.state['baseline']))
            except NativeUIError:self.state['quiet']=[];activity=None
            else:
                if activity!=current:self.state['quiet']=[];activity=current
                self.state['quiet'].append(frame['index'])
            self.save()
            if len(self.state['quiet'])>=3 and self.interval(self.frame(self.state['records'][self.state['quiet'][0]-1]),frame):
                self.state['phase']='retired';self.save();return self.original()
            need(self.monotonic()-started<15)
            if attempt<60:self.sleep(.1)
        need(False)

    def refresh(self):
        """A new actual post-quiet read, without replaying any cleanup input."""
        self.bound();need(self.state['phase']=='retired')
        with self.validation_round():
            self.qualification(self.state);baseline=self.frame(self.state['baseline'])
            previous=self.frame(self.state['records'][self.state['quiet'][-1]-1]);activity=self.drained(previous,baseline)
        current=self.capture('confirmation')
        with self.validation_round():new=self.drained(current,baseline)
        if new!=activity:
            self.state.update(phase='quiet',quiet=[]);self.save();raise NativeUIError('Actual Create cleanup activity changed; a new original quiet window is required')
        self.state['quiet'].append(current['index'])
        # Keep the native originals. Only discard an obsolete choice of the
        # measured quiet-window boundary, never reset any observed counter.
        while len(self.state['quiet'])>3:
            first=self.frame(self.state['records'][self.state['quiet'][0]-1])
            if current['clockJoin']['hostBeforeEpochMs']-first['clockJoin']['hostAfterEpochMs']<59000:break
            self.state['quiet'].pop(0)
        self.save();return self.original()

    def interval(self,first,last):
        a,b=first['clockJoin'],last['clockJoin'];x,y=a['nativeAfter'],b['nativeBefore']
        domain_first=self.source_frame(first['source'])['originals']['domain'];domain_last=self.source_frame(last['source'])['originals']['domain']
        return (b['hostBeforeEpochMs']-a['hostAfterEpochMs']>=3000 and b['hostBeforeMonotonic']-a['hostAfterMonotonic']>=3
            and y['capturedEpochMs']-x['capturedEpochMs']>=3000
            and domain_last['clockBefore']['monotonicMs']-domain_first['clockAfter']['monotonicMs']>=3000
            and y['capturedEpochMs']-x['capturedEpochMs']<60000)

    def qualification(self,state):
        need(state['phase']=='retired' and state['ticket'] is not None and len(state['quiet'])>=3)
        baseline=self.frame(state['baseline']);frames=[self.frame(state['records'][index-1]) for index in state['quiet']]
        need(self.interval(frames[0],frames[-1]));activities=[self.drained(frame,baseline,state=state) for frame in frames];need(len(set(activities))==1)
        last=frames[-1];source=self.source_frame(last['source']);clock=last['clockJoin'];first=frames[0]['clockJoin']
        if self.role=='primary':
            samples={owner.request:owner for owner in self.all_samples(state)}
            final_components=self.load_components(last['components'])
            need(set(samples)=={row['requestId'] for row in final_components['samples']})
            image_scope=self.scope.archive(state['imageScope'],root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            final_scope=self.scope.archive(final_components['scope'],root=self.scope.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            need(image_scope.state['phase']=='released' and state['imageScope']['iosCreateMarkerScopeVersion']>=2
                and len(final_scope.frames)>=len(image_scope.frames)
                and all(same(a,b) for a,b in zip(image_scope.frames,final_scope.frames)))
            marker=image_scope.state['admission']
            if marker is not None:
                need(state['images'])
                current=samples[state['images'][-1]]
                admission=image_scope.frames[image_scope.state['admissionFrame']-1]['create']
                restored(self.before_image,current,admission,None if marker['marker'] is None else marker['marker']['id'],
                    after_native=image_scope.frames[-1]['clockJoin']['nativeAfter']['capturedEpochMs'])
                need(current.state['clockJoin']['nativeAfter']['capturedEpochMs']<=frames[0]['clockJoin']['nativeBefore']['capturedEpochMs'])
        need(all(self.source_frame(frame['source'])['phaseAfter']['activations'][-1]['activatedEpochMs']<=frame['clockJoin']['hostBeforeEpochMs'] for frame in frames))
        measured=project(source['originals']['createAfter'],self.run,self.owned_ids(last['components']))
        # A logical adapter cursor spans both actual active-history and actual
        # retirement records. Native source counters and clocks stay intact.
        history=self.load_component('history',last['components']['history'])
        active_count=len(self.history.decode(history)['records'])
        public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=active_count+len(state['records']),
            capturedEpochMs=clock['hostBeforeEpochMs'],state=measured,
            artifacts=[],resources=[],lifecycle=deepcopy(clock['nativeAfter']['lifecycle']))
        result('feature.create.observe',public)
        return dict(ticket=state['ticket'],public=public,
            acquisition={key:clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')},
            quiet=dict(hostAfterFirstEpochMs=first['hostAfterEpochMs'],hostBeforeLastEpochMs=clock['hostBeforeEpochMs'],
                hostAfterFirstMonotonic=first['hostAfterMonotonic'],hostBeforeLastMonotonic=clock['hostBeforeMonotonic'],
                nativeAfterFirstEpochMs=first['nativeAfter']['capturedEpochMs'],nativeBeforeLastEpochMs=clock['nativeBefore']['capturedEpochMs'],
                nativeAfterFirstMonotonicMs=self.source_frame(frames[0]['source'])['originals']['domain']['clockAfter']['monotonicMs'],
                nativeBeforeLastMonotonicMs=source['originals']['domain']['clockBefore']['monotonicMs'],
                nativeInstance=clock['nativeAfter']['instance'],processId=self.source.pid))

    def original(self):
        self.bound();self.decode(self.store.read())
        return deepcopy(dict(iosCreateRetirementOriginalVersion=VERSION,owner=self.store.read()))

    def validate_original(self,value):
        exact(value,{'iosCreateRetirementOriginalVersion','owner'});need(type(value['iosCreateRetirementOriginalVersion']) is int
            and value['iosCreateRetirementOriginalVersion']==VERSION)
        with self.validation_round():
            state=self.decode(value['owner']);measured=self.qualification(state)
        sha=digest(value);reference=state['records'][-1]
        return dict(ticket=measured['ticket'],public=measured['public'],acquisition=measured['acquisition'],retirement=dict(originalSha256=sha,
            quiet=measured['quiet'],provenance=dict(version=1,namespace='ios-create-retirement',reference=dict(index=reference['index'],sha256=sha),originalSha256=sha)))

    def frozen(self):
        """Retain actual typed original resolvers; validation performs no SDK I/O.

        This is not a fresh observation. Actual source/component bytes, PNGs,
        export bytes and file identities are still reopened by every decoder.
        """
        self.bound();need(self.state['phase']=='retired');result=copy(self)
        result.state=deepcopy(self.state);result.previous=deepcopy(self.previous);result._source_validation=None
        result.source=copy(self.source);result.source.guard=lambda:True
        result.history=copy(self.history);result.history.guard=lambda:True
        if self.role=='actor':
            result.history.peer=result.source;result.history.primary=copy(self.history.primary);result.history.primary.guard=lambda:True
            return result
        samples={}
        for original in self.all_samples():
            owner=copy(original);owner.guard=lambda:True;owner.frame_owner=copy(original.frame_owner);owner.frame_owner.guard=lambda:True
            samples[owner.request]=owner
        def sample(request):need(request in samples);return samples[request]
        exports={}
        for original in self.history.owned_exports():
            owner=copy(original);owner.guard=lambda:True;exports[owner.store.path.name]=owner
        def export(name):need(name in exports);return exports[name]
        result.history.source=result.source;result.history.sample_resolver=sample;result.history.export_resolver=export
        result.image_factory=sample;result.before_image=samples[self.before_image.request]
        if self.actions is not None:
            result.actions=copy(self.actions);result.actions.guard=lambda:True;worlds={}
            for call in self.actions.state['calls']:
                if call['query']['verb']=='voxel-edit':
                    world=copy(self.actions.world_factory(call['query']['ticket']));world.guard=lambda:True;worlds[world.ticket]=world
            def world(ticket):need(ticket in worlds);return worlds[ticket]
            result.actions.world_factory=world;result.history.actions=result.actions
        return result
