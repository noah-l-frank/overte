"""Avatar scene retirement before either ordinary account logout.

The scene stage leaves the two account sessions explicitly owned. Original
bilateral facts are retained separately before this owner closes any UI. Scene
publication can only consume the pure decoder, never an input/POST ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import Locator,NativeUI,NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.retirement_receipts import SCENE_CLASSES
from ios.adapters import avatar_cleanup_sources,avatar_operation_clock,avatar_restoration_image
from ios.adapters.avatar_code import pins
from ios.adapters.avatar_file_receipts import IOSAvatarFileReceipts
from ios.adapters.avatar_marker_entities import IOSAvatarMarkerEntities
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_observation import source_history
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_scene_transports import owners as receipt_owners
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.emote_native_prefix import follow
from ios.adapters.web_closures import drained_owned_resources

VERSION=1


class AvatarScenePending(NativeUIError):pass


class Frozen(PrivateFeatureState):
    def __init__(self,path,value):super().__init__(path);self.value=deepcopy(value)
    def read(self):return deepcopy(self.value)
    def write(self,*_args,**_kwargs):need(False)
    def discard(self,*_args,**_kwargs):need(False)


class IOSAvatarScene:
    VERSION=VERSION
    Marker=IOSAvatarMarkerScope
    Samples=IOSAvatarSamples
    def __init__(self,runtime,selector,sources,scope,samples,baseline,clock,*,epoch_ms,monotonic,sleep):
        need(isinstance(sources,IOSAvatarSources) and not sources.historical and type(scope) is self.Marker
            and isinstance(samples,IOSAvatarSamples) and sources.lock is scope.lock is samples.lock
            and same(sources.binding,scope.binding) and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.sources,self.scope,self.samples=runtime,selector,sources,scope,samples
        self.root,self.binding,self.run,self.role,self.lock=sources.root,context(sources.binding),sources.run,sources.role,sources.lock
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.baseline=deepcopy(baseline);exact(baseline,{'index','sha256'});need(integer(baseline['index'],1,len(sources.frames))
            and digest(sources.frames[baseline['index']-1])==baseline['sha256'])
        self.clock=deepcopy(avatar_operation_clock.validate(clock))
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-avatar-'+self.role+'-scene.json'))
        self.paths=dict(sources=sources.store.path,recovery=sources.store.path.with_name('ios-avatar-'+self.role+'-source-recovery.json'),
            samples=samples.store.path,entities=self.store.path.with_name('ios-avatar-'+self.role+'-marker-entities.json'),
            files=self.store.path.with_name('ios-avatar-'+self.role+'-file-receipts.json'),pointers=self.store.path.with_name('ios-avatar-'+self.role+'-pointers.json'),
            restoration=self.store.path.with_name('ios-avatar-'+self.role+'-restoration-frames.json'))
        self.historical=False;self.previous=self.store.read();self.state=dict(close=None,scopeClosed=False,endpoints=None,image=None,quiet=[],records=[],pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        """Historical scene sources and all private originals, no SDK or clock."""
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),context(binding),identifier(run),role,lock
        lock.assert_held();need(role in ('primary','actor') and isinstance(store,PrivateFeatureState) and store.path.parent==lock.path.parent
            and store.path.name=='ios-avatar-'+role+'-scene.json')
        result.historical=True;result.baseline=deepcopy(value.get('baseline'));result.clock=deepcopy(value.get('operationClock'))
        result.paths={key:Path(path) for key,path in value.get('paths',{}).items()}
        names=dict(sources='sources',recovery='source-recovery',samples='samples',entities='marker-entities',files='file-receipts',
            pointers='pointers',restoration='restoration-frames')
        need(set(result.paths)==set(names) and all(result.paths[key]==store.path.with_name('ios-avatar-'+role+'-'+suffix+'.json') for key,suffix in names.items()))
        rows=unpack(value['payload']);need(len(rows)==1 and rows[0]['records']);last=result.record(rows[0]['records'][-1])
        result.sources=source_history(last['source'],last['recovery'],store=Frozen(result.paths['sources'],last['source']),root=root,
            binding=binding,run=run,role=role,lock=lock)
        result.scope=cls.Marker.archive(last['scope'],root=root,binding=binding,run=run,role=role,lock=lock)
        result.previous=deepcopy(value);result.state=result.decode(value)
        return result

    def envelope(self,state):return dict(iosAvatarSceneVersion=self.VERSION,binding=self.binding,runId=self.run,role=self.role,
        artifactRoot=str(self.root),baseline=self.baseline,operationClock=self.clock,paths={key:str(path) for key,path in self.paths.items()},payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosAvatarSceneVersion','binding','runId','role','artifactRoot','baseline','operationClock','paths','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'close','scopeClosed','endpoints','image','quiet','records','pending'})
        need(type(state['scopeClosed']) is bool and type(state['quiet']) is list and len(state['quiet'])<=128
            and type(state['records']) is list and len(state['records'])<=64)
        if state['close'] is not None:
            event=state['close'];exact(event,{'before','phase','after'});need(event['phase'] in ('issued','delivered','observed'))
            self.source(event['before']);need(event['phase']=='observed' or event['after'] is None)
            if event['after'] is not None:need(not self.source(event['after'])['ui']['open'])
        for index,ref in enumerate(state['records'],1):need(ref['index']==index);self.record(ref)
        if state['pending'] is not None:exact(state['pending'],{'index','value'});need(state['pending']['index']==len(state['records'])+1)
        if state['pending'] is None and len(state['records'])<64 and not getattr(self,'historical',False):need(self.file(len(state['records'])+1).read() is None)
        return deepcopy(state)

    def source(self,ref):
        exact(ref,{'index','sha256'});need(integer(ref['index'],1,len(self.sources.frames)))
        frame=self.sources.frames[ref['index']-1];need(digest(frame)==ref['sha256']);return frame

    def ref(self):return dict(index=len(self.sources.frames),sha256=digest(self.sources.frames[-1]))

    def bound(self):
        self.lock.assert_held();need(not self.historical);self.sources.bound();self.scope.bound();need(same(self.store.read(),self.previous));self.deadline()

    def deadline(self):return avatar_operation_clock.check(self.clock,self.epoch_ms(),self.monotonic())

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def receipts(self):return receipt_owners(self.runtime,self.selector,self.scope,epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def close_tablet(self):
        """One UIKit close after a positively observed owned page was left.

        Unknown UIKit delivery stays issued. Neither an ACK nor a later empty
        root inventory can discharge an unobserved open/close responsibility.
        """
        self.bound();event=self.state['close']
        if event is not None:
            if event['phase']=='issued':raise AvatarScenePending('Original Avatar UIKit close remains owned and is not repeated')
            if event['phase']=='observed':
                need(event['after'] is not None and not self.source(event['after'])['ui']['open']);return
            need(event['phase']=='delivered')
        else:
            IOSAvatarSourceRecovery(self.sources).recover();frame=self.sources.read();self.deadline()
            need(not any(row['id'] in ('avatar.page','people.page') for row in frame['ui']['controls']))
            if not frame['ui']['open']:
                self.state['close']=dict(before=self.ref(),phase='observed',after=self.ref());self.save();return
            self.state['close']=dict(before=self.ref(),phase='issued',after=None);self.save()
            actual=self.runtime._sources(self.selector);need(same(actual['binding'],self.binding))
            sdk=NativeUI(actual['client'],actual['session'],actual['check']);private=copy(sdk)
            def continuous():self.deadline();need(sdk.check_continuity() is not False);self.deadline();return True
            private.check_continuity=continuous;self.deadline()
            private.click(Locator('accessibility id','OverteTabletClose'))
            self.state['close']['phase']='delivered';self.save()
        # A returned UIKit call is still only delivery. The actual original
        # source must independently show the tablet closed.
        for _ in range(101):
            frame=self.sources.read();self.deadline()
            if not frame['ui']['open']:
                self.state['close'].update(phase='observed',after=self.ref());self.save();return
            self.sleep(.1)
        raise AvatarScenePending('Original Avatar tablet did not close')

    def historical_sources(self):return source_history(self.sources.previous,IOSAvatarSourceRecovery(self.sources).previous,
        store=self.sources.store,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)

    def endpoints(self):
        """Retire marker, real EntityItems, files and every owned GPU object."""
        self.bound();self.close_tablet();receipts=self.receipts();pointers=receipts['pointers']
        need(pointers.state['records']) # Actual pre-marker startup admission.
        # An admitted run can be cancelled before its first image. Persist the
        # actual ready marker/sample ownership before stopping that marker.
        if self.samples.previous is None:self.samples.save()
        self.samples.drain()
        with self.runtime.existing_input_session(self.selector):self.scope.cleanup()
        need(self.scope.state['phase']=='released');self.state['scopeClosed']=True;self.save()
        entities=self.runtime._avatar_marker_entities(self.selector,self.scope,self.root,self.lock);entities.abandon();entities.capture();entities.closed(self.scope)
        files=receipts['files'];files.abandon();files.capture('absent',self.scope.state['fileOwnership'])
        self.sources.read();history=self.historical_sources();index=len(history.frames)
        cleanup=self.restored_sources(history,self.baseline['index'],index,fixture_url=self.scope.fixture_url,expected_code=pins())
        weak=avatar_cleanup_sources.wearable_lifetimes(history,self.baseline['index'],index,
            entities.original(entities.state['records'][0])['packet'],entities.latest()['packet'],fixture_url=self.scope.fixture_url,expected_code=pins())
        last_file=files.original(files.state['records'][-1]);follow(entities.latest()['clockJoin']['nativeAfter'],last_file['clockJoin']['nativeBefore'])
        after=self.sources.frames[-1]['clockJoin']['nativeAfter'];need(after['capturedEpochMs']>=max(cleanup['endpointEpochMs'],weak['endpointEpochMs']))
        follow(last_file['clockJoin']['nativeAfter'],self.sources.frames[-1]['clockJoin']['nativeBefore'])
        self.state['endpoints']=dict(source=self.ref(),entities=deepcopy(entities.previous),files=deepcopy(files.previous),native=deepcopy(after))
        self.save();return after

    def restoration(self,after):
        self.bound();owner=IOSAvatarRestorationFrames(self.runtime,self.selector,self.scope,self.root,self.lock,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
        owner.resolve()
        if owner.state['pending'] is not None:owner.abandon()
        initial=[row for row in owner.state['records'] if owner.original(row)['kind']=='initial'];need(len(initial)==1)
        current=owner.capture('cleanup');admission=self.scope.frames[self.scope.state['admissionFrame']-1]['world']
        proof=avatar_restoration_image.restored(owner,initial[0],current,admission,self.scope.state['admission']['marker']['id'],after_native=after)
        self.state['image']=dict(owner=deepcopy(owner.previous),baseline=deepcopy(initial[0]),current=deepcopy(current),proof=proof);self.save()
        return owner.frame(current)[0]['clockJoin']['nativeAfter']

    def cut(self):
        """Each subordinate passive acquisition has its own durable journal."""
        self.bound();receipts=self.receipts();pointers=receipts['pointers'];pointers.abandon();left=pointers.capture()
        IOSAvatarSourceRecovery(self.sources).recover();self.sources.read();ref=self.ref()
        frame=self.scope.capture('avatar-scene-quiet');right=pointers.capture()
        return dict(source=ref,scope=len(self.scope.frames),left=left,right=right)

    @staticmethod
    def restored_sources(*args,**kwargs):return avatar_cleanup_sources.restored(*args,**kwargs)

    @staticmethod
    def resource_quiet(frame,scope):
        return drained_owned_resources(frame['web'],scope.frames[scope.state['webAdmission']-1]['web'])

    @staticmethod
    def holders_unchanged(first,last,scope):return True

    def scene_summary(self,p,acquisition,native):
        return dict(sceneRetirementVersion=1,runId=self.run,sequence=p['sequence'],capturedEpochMs=acquisition['hostAfterEpochMs'],
            retired=list(SCENE_CLASSES),remaining=['account-session'],lifecycle=deepcopy(native['lifecycle']))

    def quiet_frame(self,cut):
        frame=self.scope.frames[cut['scope']-1];self.scope.ui_absent(frame);self.scope.dialog_drained(frame)
        baseline=self.scope.frames[self.scope.state['baseline']-1];self.scope.components.body_preserved(baseline['world'],frame['world'])
        self.scope.components.view_preserved(baseline['world'],frame['world'])
        self.scope.restored_marker(baseline,frame,self.scope.state['admission'],self.scope.state['stopBarrier'])
        self.resource_quiet(frame,self.scope)
        history=self.historical_sources();self.restored_sources(history,self.baseline['index'],cut['source']['index'],
            fixture_url=self.scope.fixture_url,expected_code=pins());return frame

    def quiet(self,after):
        self.bound();self.state['quiet']=[];self.save()
        for _ in range(80):
            self.deadline();cut=self.cut();frame=self.quiet_frame(cut)
            if self.state['quiet']:self.holders_unchanged(self.scope.frames[self.state['quiet'][-1]['scope']-1],frame,self.scope)
            follow(after,frame['clockJoin']['nativeBefore'])
            self.state['quiet'].append(cut);self.save();rows=self.state['quiet']
            if len(rows)>=3:
                first=self.quiet_frame(rows[0])
                if self.scope.quiet_interval(first,frame):
                    pointers=self.receipts()['pointers']
                    pointers.quiet([self.scope.frames[row['scope']-1] for row in rows]);return
            self.sleep(.15)
        raise AvatarScenePending('Avatar original scene endpoints have not remained quiet')

    def file(self,index):
        need(integer(index,1,64));return PrivateFeatureState(self.root/('avatar-scene-'+self.run+'-'+self.role+'-'+str(index)+'.json'))

    def record(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'iosAvatarSceneOriginalVersion','runId','role','binding','payload'})
        need(type(value['iosAvatarSceneOriginalVersion']) is int and value['iosAvatarSceneOriginalVersion']==self.VERSION and value['runId']==self.run
            and value['role']==self.role and same(value['binding'],self.binding));rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def finish(self,value):
        self.bound();p=self.state['pending'];need(p is not None and same(p['value'],value));store=self.file(p['index']);old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        ref=dict(index=p['index'],sha256=digest(value));self.record(ref);self.state['records'].append(ref);self.state['pending']=None;self.save();return ref

    def capture(self,*,ticket,phase_instance,sequence):
        """A fresh scene original; existing immutable records stay historical."""
        self.bound();identifier(ticket);identifier(phase_instance);need(integer(sequence,1) and len(self.state['records'])<64)
        if self.state['pending'] is not None:
            # This is a completed immutable local candidate, never an input or
            # SDK request. Adopt its exact saved bytes after a lost local return.
            p=self.state['pending'];self.finish(p['value'])
            raise AvatarScenePending('Saved scene original was adopted historically; a distinct fresh observation is required')
        after=self.endpoints();image_end=self.restoration(after);self.quiet(image_end)
        return self.retain(ticket=ticket,phase_instance=phase_instance,sequence=sequence)

    def refresh(self,*,ticket,phase_instance,sequence):
        """A distinct fresh suffix after both independent Scene-ready owners.

        No input, marker preparation, GPU capture or old publication is replayed.
        The original three-second interval and all old endpoints stay unchanged.
        """
        self.bound();need(self.state['records'] and self.state['quiet'] and self.state['image'] is not None)
        old=self.derive(self.state['records'][-1]);need(old['ticket']==ticket)
        cut=self.cut();self.quiet_frame(cut);self.state['quiet'].append(cut);self.save()
        return self.retain(ticket=ticket,phase_instance=phase_instance,sequence=sequence)

    def retain(self,*,ticket,phase_instance,sequence):
        self.bound();identifier(ticket);identifier(phase_instance);need(integer(sequence,1))
        receipts=self.receipts();pointers=receipts['pointers'];last=self.state['quiet'][-1]
        acquisition=dict(hostBeforeEpochMs=self.scope.frames[last['scope']-1]['clockJoin']['hostBeforeEpochMs'],
            hostBeforeMonotonic=self.scope.frames[last['scope']-1]['clockJoin']['hostBeforeMonotonic'],
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        # The separate quiet window starts after every scene endpoint. The
        # fresh return still uses this original final acquisition and includes
        # all subsequent validation and local storage below.
        source=source_history(self.sources.previous,IOSAvatarSourceRecovery(self.sources).previous,store=self.sources.store,
            root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        payload=dict(ticket=ticket,phaseInstance=phase_instance,sequence=sequence,baseline=deepcopy(self.baseline),
            paths={key:str(path) for key,path in self.paths.items()},imagePolicy=deepcopy(self.samples.policy),
            fixtureUrl=self.scope.fixture_url,expectedCode=pins(),source=deepcopy(source.previous),
            recovery=deepcopy(IOSAvatarSourceRecovery(self.sources).previous),scope=self.scope.snapshot(),
            endpoints=deepcopy(self.state['endpoints']),image=deepcopy(self.state['image']),quiet=deepcopy(self.state['quiet']),
            pointers=deepcopy(pointers.previous),samples=deepcopy(self.samples.previous),close=deepcopy(self.state['close']),acquisition=acquisition)
        value=dict(iosAvatarSceneOriginalVersion=self.VERSION,runId=self.run,role=self.role,binding=self.binding,payload=pack([payload]))
        self.state['pending']=dict(index=len(self.state['records'])+1,value=value);self.save()
        ref=self.finish(value);self.derive(ref)
        a=PhaseRetirementPublisher.acquisition(acquisition);now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,a['hostAfterEpochMs'],a['hostBeforeEpochMs']+1500) and now-a['hostBeforeEpochMs']<1500
            and number(mono,a['hostAfterMonotonic'],a['hostBeforeMonotonic']+1.5) and mono-a['hostBeforeMonotonic']<1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250)
        return ref

    def derive(self,reference):
        return self.joined(reference)[0]

    def joined(self,reference):
        """One original traversal returns its proof and already checked inputs."""
        self.lock.assert_held();need(reference in self.state['records']);p=self.record(reference)
        exact(p,{'ticket','phaseInstance','sequence','baseline','paths','imagePolicy','fixtureUrl','expectedCode','source','recovery','scope',
            'endpoints','image','quiet','pointers','samples','close','acquisition'})
        identifier(p['ticket']);identifier(p['phaseInstance']);need(integer(p['sequence'],1) and same(p['baseline'],self.baseline)
            and p['paths']=={key:str(path) for key,path in self.paths.items()} and p['expectedCode']==pins())
        history=source_history(p['source'],p['recovery'],store=Frozen(self.paths['sources'],p['source']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        scope=self.Marker.archive(p['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        need(scope.state['phase']=='released' and scope.state['pending'] is None and scope.state['cleanupMode']=='full'
            and scope.fixture_url==p['fixtureUrl'] and scope.state['webAdmission'] is not None)
        baseline=scope.frames[scope.state['baseline']-1];admission=scope.frames[scope.state['admissionFrame']-1]
        def source(ref):
            exact(ref,{'index','sha256'});need(integer(ref['index'],1,len(history.frames)))
            frame=history.frames[ref['index']-1];need(digest(frame)==ref['sha256']);return frame
        endpoint=p['endpoints'];exact(endpoint,{'source','entities','files','native'});end_frame=source(endpoint['source'])
        need(same(endpoint['native'],end_frame['clockJoin']['nativeAfter']))
        entities=IOSAvatarMarkerEntities.archive(endpoint['entities'],store=Frozen(self.paths['entities'],endpoint['entities']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock);entities.closed(scope)
        files=IOSAvatarFileReceipts.archive(endpoint['files'],store=Frozen(self.paths['files'],endpoint['files']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        need(files.state['pending'] is None and files.state['records']);file=files.original(files.state['records'][-1])
        need(file['kind']=='absent' and same(file['ownership'],scope.state['fileOwnership']))
        follow(entities.latest()['clockJoin']['nativeAfter'],file['clockJoin']['nativeBefore'])
        follow(file['clockJoin']['nativeAfter'],end_frame['clockJoin']['nativeBefore'])
        weak=avatar_cleanup_sources.wearable_lifetimes(history,self.baseline['index'],endpoint['source']['index'],
            entities.original(entities.state['records'][0])['packet'],entities.latest()['packet'],fixture_url=scope.fixture_url,expected_code=p['expectedCode'])
        closed=self.restored_sources(history,self.baseline['index'],endpoint['source']['index'],fixture_url=scope.fixture_url,expected_code=p['expectedCode'])
        need(endpoint['native']['capturedEpochMs']>=max(weak['endpointEpochMs'],closed['endpointEpochMs']))
        image=p['image'];exact(image,{'owner','baseline','current','proof'})
        frames=IOSAvatarRestorationFrames.archive(image['owner'],store=Frozen(self.paths['restoration'],image['owner']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        image_proof=avatar_restoration_image.restored(frames,image['baseline'],image['current'],admission['world'],
            scope.state['admission']['marker']['id'],after_native=endpoint['native']);need(same(image_proof,image['proof']))
        image_end=frames.frame(image['current'])[0]['clockJoin']['nativeAfter']
        samples=self.Samples.history(p['samples'],store=Frozen(self.paths['samples'],p['samples']),root=self.root,binding=self.binding,
            run=self.run,role=self.role,policy=p['imagePolicy'],lock=self.lock);need(samples.state['pending'] is None)
        pointers=IOSAvatarPointers.archive(p['pointers'],store=Frozen(self.paths['pointers'],p['pointers']),root=self.root,
            binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        need(type(p['quiet']) is list and len(p['quiet'])>=3);quiet=[];prior_source=prior_scope=0;first_source=None
        for cut in p['quiet']:
            exact(cut,{'source','scope','left','right'});need(integer(cut['scope'],prior_scope+1,len(scope.frames)))
            current=source(cut['source']);need(cut['source']['index']>prior_source);prior_source=cut['source']['index'];prior_scope=cut['scope']
            phase=current['phaseAfter'];need(phase['instance']==p['phaseInstance'] and phase['activations'][-1]['ticket']==p['ticket']
                and phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            frame=scope.frames[cut['scope']-1]
            if quiet:self.holders_unchanged(quiet[-1],frame,scope)
            quiet.append(frame);scope.ui_absent(frame);scope.dialog_drained(frame)
            scope.components.body_preserved(baseline['world'],frame['world']);scope.components.view_preserved(baseline['world'],frame['world'])
            scope.restored_marker(baseline,frame,scope.state['admission'],scope.state['stopBarrier'])
            self.resource_quiet(frame,scope)
            follow(image_end,frame['clockJoin']['nativeBefore'])
            component=self.restored_sources(history,self.baseline['index'],cut['source']['index'],
                fixture_url=scope.fixture_url,expected_code=p['expectedCode'])
            if first_source is None:first_source=current
            need(component['endpointEpochMs']<=first_source['clockJoin']['nativeBefore']['capturedEpochMs'])
            # No actual model/request/wearable API or owned HTTP suffix can run
            # between the accepted quiet cuts. Old unowned periodic timers are
            # allowed only under the independently checked zero dispatch depth.
            for name in ('state','entities','http'):
                a,b=first_source['originals'][name],current['originals'][name]
                if name=='state':need(same(a['source']['modelHistory'],b['source']['modelHistory']))
                elif name=='http':need(same(a['events'],b['events']))
                else:need(same(a['source'],b['source']))
            need(cut['left'] in pointers.state['records'] and cut['right'] in pointers.state['records'])
            left,right=pointers.original(cut['left']),pointers.original(cut['right'])
            follow(left['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore'])
            follow(current['clockJoin']['nativeAfter'],frame['clockJoin']['nativeBefore'])
            follow(frame['clockJoin']['nativeAfter'],right['clockJoin']['nativeBefore'])
        need(scope.quiet_interval(quiet[0],quiet[-1]));pointer_proof=pointers.quiet(quiet)
        # Actual startup was measured before the marker's first setup input.
        first_pointer=pointers.original(pointers.state['records'][0]);follow(first_pointer['clockJoin']['nativeAfter'],baseline['clockJoin']['nativeBefore'])
        close=p['close'];exact(close,{'before','phase','after'});need(close['phase']=='observed' and close['after'] is not None
            and not source(close['after'])['ui']['open'])
        a=PhaseRetirementPublisher.acquisition(p['acquisition']);last=quiet[-1];native=pointer_proof['last']['clockJoin']['nativeAfter']
        need(a['hostBeforeEpochMs']<=last['clockJoin']['hostBeforeEpochMs']<=last['clockJoin']['hostAfterEpochMs']<=a['hostAfterEpochMs']
            and a['hostBeforeMonotonic']<=last['clockJoin']['hostBeforeMonotonic']<=last['clockJoin']['hostAfterMonotonic']<=a['hostAfterMonotonic']
            and same(first_source['clockJoin']['nativeAfter']['lifecycle'],native['lifecycle']))
        right=pointers.original(p['quiet'][-1]['right'])['clockJoin']
        need(a['hostBeforeEpochMs']<=right['hostBeforeEpochMs']<=right['hostAfterEpochMs']<=a['hostAfterEpochMs']
            and a['hostBeforeMonotonic']<=right['hostBeforeMonotonic']<=right['hostAfterMonotonic']<=a['hostAfterMonotonic'])
        x,y=quiet[0]['world'],last['world'];quiet_proof=dict(hostAfterFirstEpochMs=quiet[0]['clockJoin']['hostAfterEpochMs'],
            hostBeforeLastEpochMs=last['clockJoin']['hostBeforeEpochMs'],hostAfterFirstMonotonic=quiet[0]['clockJoin']['hostAfterMonotonic'],
            hostBeforeLastMonotonic=last['clockJoin']['hostBeforeMonotonic'],nativeAfterFirstEpochMs=x['clockAfter']['epochMs'],
            nativeBeforeLastEpochMs=y['clockBefore']['epochMs'],nativeAfterFirstMonotonicMs=x['clockAfter']['monotonicMs'],
            nativeBeforeLastMonotonicMs=y['clockBefore']['monotonicMs'],nativeInstance=x['instance'],processId=x['processId'])
        scene=self.scene_summary(p,a,native)
        proof=dict(ticket=p['ticket'],scene=scene,acquisition=deepcopy(a),retirement=dict(originalSha256=reference['sha256'],quiet=quiet_proof,
            provenance=dict(version=1,namespace='ios-avatar-scene-original',reference=deepcopy(reference),originalSha256=reference['sha256'])))
        return proof,dict(reference=deepcopy(reference),scope=scope,history=history,quiet=quiet,original=p)
