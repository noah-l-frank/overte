"""Original Worlds admission and ordinary active-run action coordination.

This is an internal vertical coordinator. Public observation, paired final
restoration and capability admission remain gated until their whole-run joins
are integrated. Child input journals, rather than this parent's ACK, determine
whether an interrupted operation may advance without resending an input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_places_actions import VERBS as PLACE_VERBS
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_observer import NavigationObserver
from ios.adapters.navigation_observation_owner import validation_round
from ios.adapters import navigation_source_prefix as source_prefix
from ios.adapters.graphics_history import follow_native
from navigation_observation import same_viewpoint,viewpoint_urls

VERSION=2
READS=(1,2)


class NavigationFeaturePending(NativeUIError):pass


class IOSNavigationFeature:
    def __init__(self,runtime,selector,client,run,root,*,role='primary',
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSNavigationRuntime) and isinstance(client,Client)
            and role in ('primary','actor') and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.root=Path(root);need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        PrivateFeatureState(self.root/'navigation-root-check')._parent()
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-navigation-feature.json'))
        self.lock=ScriptSourceLock(self.store.path.with_name('script-feature-sources.lock'))
        self.fixture=NavigationFixtureReader(client,run,epoch_ms=lambda:int(epoch_ms()),monotonic=monotonic)
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.previous=self.state=None;self.deadline=self.last_clock=self.operation_clock=None

    def clock(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.deadline is None or now<self.deadline))
        if self.operation_clock is not None:
            first=self.operation_clock;epoch=self.epoch_ms()
            need(number(now,first['monotonic'],first['monotonic']+30) and now-first['monotonic']<30
                and number(epoch,first['epochMs'],first['epochMs']+30000) and epoch-first['epochMs']<30000
                and abs(epoch-first['epochMs']-(now-first['monotonic'])*1000)<=250)
        self.last_clock=now;return now

    @contextmanager
    def held(self):
        outer=self.deadline;now=self.clock();self.deadline=now+30 if outer is None else min(outer,now+30)
        error=None
        try:
            # Retain exceptions across ScriptSourceLock's context manager.
            with self.lock.held():
                try:
                    with transport_scope(self.clock):
                        with validation_round():yield
                        self.clock()
                except BaseException as caught:error=caught
            if error is not None:raise error
        finally:self.deadline=outer

    def envelope(self,state,version=VERSION):
        return dict(iosNavigationFeatureVersion=version,runId=self.run,artifactRoot=str(self.root),payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:self.state=None;return
        exact(self.previous,{'iosNavigationFeatureVersion','runId','artifactRoot','payload'})
        version=self.previous['iosNavigationFeatureVersion']
        rows=unpack(self.previous['payload']);need(len(rows)==1 and type(version) is int
            and version in READS and same(self.previous,self.envelope(rows[0],version)))
        state=rows[0];exact(state,{'phase','binding','providerInstance','providerInputs','admissionSha256','entry','lastCall'}
            |({'initialBinding','stage','transferSha256','observerOffsets'} if version>=2 else set()))
        need(state['phase'] in ('preparing','ready','acting') and state['entry'] in ('pending','entered'))
        context(state['binding']);identifier(state['providerInstance'])
        need(state['admissionSha256'] is None or type(state['admissionSha256']) is str and len(state['admissionSha256'])==64)
        if state['phase']!='preparing':need(state['admissionSha256'] is not None and state['entry']=='entered')
        if state['lastCall'] is not None:
            row=state['lastCall'];exact(row,{'call','phase','started'})
            call=arguments('feature.world-navigation.act',row['call']);need(call['runId']==self.run
                and row['phase'] in ('issued','acknowledged'))
            exact(row['started'],{'epochMs','monotonic'})
            need(number(row['started']['epochMs'],1,1e15) and number(row['started']['monotonic'],0,1e15))
        if version==1:
            # Legacy originals describe only the first process. No transfer
            # or global cursor is inferred from a legacy ready/ACK flag.
            state=deepcopy(state)|dict(initialBinding=deepcopy(state['binding']),stage=0,transferSha256=None,
                observerOffsets=dict(primary=0,actor=0))
        context(state['initialBinding']);need(type(state['stage']) is int and state['stage'] in (0,1))
        exact(state['observerOffsets'],{'primary','actor'})
        need(all(type(value) is int and 0<=value<=512 for value in state['observerOffsets'].values()))
        if state['stage']==0:
            need(same(state['binding'],state['initialBinding']) and state['transferSha256'] is None
                and all(value==0 for value in state['observerOffsets'].values()))
        else:need(type(state['transferSha256']) is str and len(state['transferSha256'])==64
            and state['binding']['processIdentity']!=state['initialBinding']['processIdentity']
            and all(value>0 for value in state['observerOffsets'].values()))
        self.state=deepcopy(state)

    def save(self):
        self.lock.assert_held();self.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.clock()

    def current(self):
        self.lock.assert_held();self.clock();source=self.runtime._sources(self.selector)
        need(source['check']() is not False)
        if self.state is not None:need(same(source['binding'],self.state['binding']))
        return source

    def admission(self):
        if self.state['stage']==1:
            owner=self.transferred_owner();scope=self.runtime._navigation_process_scope(owner)
            need(same(scope.binding,self.state['binding']));return scope
        owner=self.runtime._navigation_admission_owner(self.selector,self.client,self.run,self.lock)
        need(isinstance(owner,NavigationAdmissionOwner) and owner.lock is self.lock
            and same(owner.binding,self.state['binding']))
        if self.state['admissionSha256'] is not None:
            need(digest(owner.store.read())==self.state['admissionSha256']);owner.archive()
        return self.limited(owner)

    def initial_owner(self):
        """Actual immutable admission carrier, independent of current SDK PID."""
        owner=NavigationAdmissionOwner(PrivateFeatureState(self.store.path.with_name('ios-navigation-scene-admission.json')),
            self.state['initialBinding'],self.run,self.lock,lambda:True,historical=True)
        need(digest(owner.store.read())==self.state['admissionSha256']);owner.archive();return owner

    def initial_admission(self):
        """Read the actual old carrier without consulting the ended process."""
        return self.initial_owner().archive()

    def publications(self,observer):
        from ios.adapters.navigation_publications import NavigationPublications
        need(isinstance(observer,NavigationObserver) and observer.stage==self.state['stage'] and observer.role==self.role)
        observers={0:observer} if self.state['stage']==0 else {0:self.prior_observers()[self.role],1:observer}
        return NavigationPublications(self.initial_owner(),observers,
            transfer=None if self.state['stage']==0 else self.transferred_owner(),guard=self.clock,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def prior_observers(self):
        """Old-process originals stay frozen after the actual lifecycle input."""
        from ios.adapters.navigation_samples import NavigationSamples
        result={}
        for role in ('primary','actor'):
            images=NavigationSamples(PrivateFeatureState(self.store.path.with_name('ios-navigation-'+role+'-0-samples.json')),
                self.root,self.state['initialBinding'],self.run,role,0,self.lock,lambda:True,historical=True)
            result[role]=NavigationObserver(PrivateFeatureState(self.store.path.with_name('ios-navigation-'+role+'-0-observer.json')),
                images,historical=True)
            need(result[role].state['sequence']>0 and result[role].state['rows'][-1]['status']=='observed')
        return result

    def restarter(self):
        prior=self.prior_observers()
        child=self.runtime._navigation_restart(self.selector,self.initial_admission(),
            {role:owner.images for role,owner in prior.items()},self.lock,self.fixture)
        if child.state is not None:self.validate_pre_stop(child,prior)
        return child

    def validate_pre_stop(self,child,observers):
        from ios.adapters.navigation_before_restart import NavigationBeforeRestart
        before=NavigationBeforeRestart.archive(child.state['before'],child.initial)
        current=deepcopy(before['originals']);current['navigationBefore']=current.pop('navigation')
        for owner in observers.values():
            last=owner.owners()[-1]
            follow_native(last.state['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
            source_prefix.follow(last.state['originals'],current,self.run,int(self.state['initialBinding']['processIdentity']))

    def transferred_owner(self):
        from ios.adapters.navigation_process_owner import NavigationProcessOwner
        from ios.adapters.navigation_before_restart import NavigationBeforeRestart
        child=self.restarter();need(child.state is not None and child.state['status']=='observed')
        before=NavigationBeforeRestart.archive(child.state['before'],child.initial)
        owner=self.runtime._navigation_process_owner(self.selector,self.client,child.initial,before,child.state['receipt'],self.lock)
        need(isinstance(owner,NavigationProcessOwner))
        if self.state['transferSha256'] is not None:
            need(digest(owner.store.read())==self.state['transferSha256'])
            value=owner.archive();need(same(value['restart'],child.state['receipt']))
            for role,prior in self.prior_observers().items():need(self.state['observerOffsets'][role]==prior.state['sequence'])
        return self.limited(owner)

    def restart(self,call,admission=None):
        """Only actual child receipts can advance the process stage/cursors."""
        from ios.adapters.navigation_restart import NavigationRestart
        self.lock.assert_held();need(self.role=='primary' and call['verb']=='restart-app')
        store=PrivateFeatureState(self.store.path.with_name('ios-navigation-restart.json'))
        if store.read() is None:
            need(admission is not None and self.state['stage']==0)
            observers={role:self.runtime._navigation_observer(self.selector,self.client,self.run,role,0,self.root,self.lock)
                for role in ('primary','actor')}
            for owner in observers.values():
                need(owner.state['sequence']>0 and owner.state['rows'][-1]['status']=='observed')
            samples={role:owner.images for role,owner in observers.items()}
            drains={role:source.drain() for role,source in samples.items()}
            source=self.current();pointer=source['observer'].pointer_state(source['clock_source'])
            first=pointer.read(self.run)
            before=self.runtime._navigation_before_restart(self.selector,admission,missing=self.missing(admission))
            if before.state is None:before.acquire()
            else:before.recover()
            last=pointer.read(self.run)
            child=self.runtime._navigation_restart(self.selector,self.initial_admission(),samples,self.lock,admission.fixture)
            need(isinstance(child,NavigationRestart));child.prepare(call,before,drains,first,last)
            self.validate_pre_stop(child,observers)
        else:child=self.restarter()
        need(same(child.state['arguments'],call));child.restart()
        owner=self.transferred_owner()
        if owner.state is None:owner.acquire(self.epoch_ms())
        elif owner.state['phase']=='reading':owner.recover()
        owner.archive();prior=self.prior_observers()
        self.state.update(stage=1,binding=deepcopy(owner.binding),transferSha256=digest(owner.store.read()),
            observerOffsets={role:observer.state['sequence'] for role,observer in prior.items()})
        self.current();self.save()

    def limited(self,owner):
        """Keep the enclosing deadline in every child's before-input guard."""
        original=owner.guard
        def guard():
            self.clock();result=original();self.clock();return result
        owner.guard=guard;return owner

    def prepare(self):
        with self.held():
            self.load();self.fixture.attach()
            if (self.state is not None and self.state['phase']=='acting' and self.state['lastCall'] is not None
                    and self.state['lastCall']['phase']=='issued' and self.state['lastCall']['call']['verb']=='restart-app'):
                if self.role!='primary':raise NavigationFeaturePending('Primary actual Worlds process transfer is pending')
                original_clock=self.operation_clock
                try:
                    self.operation_clock=deepcopy(self.state['lastCall']['started']);self.clock()
                    self.restart(self.state['lastCall']['call'])
                    self.state['phase']='ready';self.state['lastCall']['phase']='acknowledged';self.save()
                finally:self.operation_clock=original_clock
            source=self.current()
            if self.state is None:
                if self.role!='primary':raise NavigationFeaturePending('Primary original Worlds admission is pending')
                phase=self.fixture.read();need(phase['verb']=='baseline')
                self.state=dict(phase='preparing',binding=deepcopy(source['binding']),providerInstance=self.fixture.instance,
                    providerInputs=deepcopy(self.fixture.inputs),admissionSha256=None,entry='pending',lastCall=None,
                    initialBinding=deepcopy(source['binding']),stage=0,transferSha256=None,observerOffsets=dict(primary=0,actor=0));self.save()
            need(self.fixture.instance==self.state['providerInstance'] and same(self.fixture.inputs,self.state['providerInputs']))
            if self.state['phase']!='preparing':return
            if self.role!='primary':raise NavigationFeaturePending('Primary ordinary Worlds scene entry is pending')
            admission=self.admission()
            if self.state['admissionSha256'] is None:
                if admission.state is None:admission.acquire(self.epoch_ms())
                elif admission.state['phase']=='reading':admission.recover()
                admission.archive();self.state['admissionSha256']=digest(admission.store.read());self.save()
            inputs=self.runtime._navigation_scene_inputs(self.selector,admission)
            with self.runtime.existing_input_session(self.selector):inputs.enter()
            self.state.update(phase='ready',entry='entered');self.save()

    def act(self,call):
        outer,original=self.deadline,self.operation_clock;now=self.clock()
        self.deadline=now+30 if outer is None else min(outer,now+30)
        self.operation_clock=dict(epochMs=self.epoch_ms(),monotonic=now)
        try:return self._act(call)
        finally:self.deadline,self.operation_clock=outer,original

    def _act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.world-navigation.act',call));need(call['runId']==self.run)
        self.prepare()
        with self.held():
            self.load();self.current();admission=self.admission();phase=admission.fixture.read()
            need(call['fixtureUrl']==admission.fixture.fixture_url and phase['ticket']==call['ticket']
                and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
            prior=self.state['lastCall']
            if prior is not None and prior['call']['ticket']==call['ticket']:
                need(same(prior['call'],call))
                if prior['phase']=='issued':self.operation_clock=deepcopy(prior['started']);self.clock()
            else:
                need(prior is None or prior['phase']=='acknowledged')
                self.clock()
                self.state.update(phase='acting',lastCall=dict(call=call,phase='issued',started=deepcopy(self.operation_clock)));self.save()
            verb=call['verb']
            with self.runtime.existing_input_session(self.selector):
                if verb=='restart-app':
                    if self.state['stage']==0:self.restart(call,admission)
                    else:need(prior is not None and same(prior['call'],call) and prior['phase']=='acknowledged')
                elif verb in ('open','close'):
                    self.runtime._navigation_surface_actions(self.selector,admission).act(call)
                elif verb in ('directory-select','bookmark-visit'):
                    child=self.runtime._navigation_composite_actions(self.selector,admission)
                    self.limited(child.places)
                    row=None if child.state is None or not child.state['actions'] else child.state['actions'][-1]
                    if row is not None and same(row['call'],call) and row['phase']=='arriving':child.settle()
                    elif row is not None and same(row['call'],call) and row['phase']=='closing':child.recover_close()
                    else:child.act(call)
                elif verb in PLACE_VERBS:self.limited(self.runtime._navigation_places_actions(self.selector,admission)).act(call)
                elif verb in ('navigate-missing','dismiss-error'):
                    child=self.runtime._navigation_missing_actions(self.selector,admission)
                    if verb=='navigate-missing':child.navigate(call)
                    else:
                        if child.state is None or child.state['proof'] is None:
                            raise NavigationFeaturePending('Actual owned named-lookup failure must be independently observed before dismissal')
                        prior_dismiss=child.state['dismiss']
                        if prior_dismiss is None or prior_dismiss['phase']=='delivered':child.dismiss(call)
                        else:
                            need(prior_dismiss['phase']=='issued' and same(prior_dismiss['call'],call)
                                and any(intent['method']=='ERROR-OK' for intent in prior_dismiss['intents']))
                        if child.observe_cleared() is None:
                            raise NavigationFeaturePending('Actual owned error dialog and listener remain live')
                        address=self.runtime._navigation_address_dismiss(self.selector,admission)
                        if address.state is not None and address.state['after'] is not None:address.recover()
                        else:address.close()
                else:raise NavigationFeaturePending('Worlds process-transfer and final restoration coordination remain required')
            self.state.update(phase='ready');self.state['lastCall']['phase']='acknowledged';self.save()
            return {'performed':True}

    def observer(self):
        """Role-owned acquisition on the independently qualified current stage."""
        self.current()
        stage=self.state['stage']
        owner=self.runtime._navigation_observer(self.selector,self.client,self.run,self.role,stage,self.root,self.lock)
        need(isinstance(owner,NavigationObserver) and same(owner.binding,self.state['binding'])
            and owner.lock.path==self.lock.path and owner.images.root==self.root
            and owner.role==self.role and owner.stage==stage)
        return owner

    def return_to_original(self):
        """Deliver the owned final Go To once, without claiming restoration.

        A retained child return can resolve a lost parent result. An unknown
        input or incomplete acquisition remains owned and is never resent.
        Full static originals, PNG comparison and final lifetime retirement
        must still independently qualify the resulting product state.
        """
        need(self.role=='primary');self.prepare()
        with self.held():
            self.load();self.current();need(self.state['phase']=='ready' and self.state['stage']==1
                and (self.state['lastCall'] is None or self.state['lastCall']['phase']=='acknowledged'))
            scope=self.admission()
            child=self.runtime._navigation_process_return(self.selector,scope)
            with self.runtime.existing_input_session(self.selector):
                if child.state is not None and child.state['phase']=='issued':return child.recover_return()
                return child.return_to_original()

    def directory(self,observer,admission):
        """Re-derive the original first-open proof; never issue another read."""
        owners=observer.owners()
        found=[owner for owner in owners if owner.state['options']['directory'] is not None]
        if not found:return None
        surface=self.runtime._navigation_surface_actions(self.selector,admission)
        return surface.directory(found[0])

    def settle_directory(self,observer,admission):
        """Resolve only a complete first-open read, without replaying sources."""
        if not observer.state['rows'] or observer.state['rows'][-1]['status']!='reserved':return
        row=observer.state['rows'][-1]
        need(row['childStarted']);owner=observer.live(row)
        state=owner.state
        if state is None or state['phaseAfter'] is None:
            raise NavigationFeaturePending('An interrupted Worlds source acquisition remains owned')
        if state['options']['directory'] is None and state['phaseBefore']['verb']=='open':
            surface=self.runtime._navigation_surface_actions(self.selector,admission)
            observer.recover(directory=surface.directory(owner))
        else:observer.recover()

    def missing(self,admission):
        """Retain the actual missing-reply/modal join before full acquisition."""
        from ios.adapters.navigation_process_scope import owner_path
        store=PrivateFeatureState(owner_path(admission,'ios-navigation-missing-actions.json'))
        if store.read() is None:return None
        child=self.runtime._navigation_missing_actions(self.selector,admission)
        if child.state['proof'] is None:
            frames=child.state['frames']
            if (frames and frames[-1]['kind']=='missing' and frames[-1]['clockJoin'] is not None
                    and any(frames[-1]['originals'][name]['events'] for name in ('dialogs','replies'))):
                child.recover_missing()
            else:child.observe_missing()
        return deepcopy(child.state['proof'])

    def observe_active(self,after_sequence):
        """Fresh active originals; not the whole public cleanup/transfer API.

        A preliminary actual navigation read selects which of the two bounded
        viewpoints to qualify. It supplies no returned fact. The subsequent
        independent complete source/image acquisition must validate that pose.
        A historical first-open recovery is always followed by a new capture.
        """
        need(type(after_sequence) is int and after_sequence>=0)
        self.prepare()
        with self.held():
            self.load();admission=self.admission();observer=self.observer()
            publications=self.publications(observer)
            publication=publications.for_observer(observer)
            need(publication is None or publication['pending'] is None)
            offset=self.state['observerOffsets'][self.role]
            need(type(after_sequence) is int and 0<=after_sequence<=offset+observer.state['sequence'])
            self.settle_directory(observer,admission)
            directory=self.directory(observer,admission)
            owners=observer.owners();previous=owners[-1] if owners else None
            prototype=observer.factory(uuid.uuid4().hex,previous)
            started,epoch=self.monotonic(),self.epoch_ms()
            self.deadline=min(self.deadline,started+1.5)
            observed=prototype.navigation.read(self.run)
            urls=viewpoint_urls(self.fixture.inputs['sceneUrl'])
            labels=[label for label,url in urls.items() if same_viewpoint(observed['source']['sceneUrl'],url)]
            need(len(labels)==1);label=labels[0];phase=self.fixture.read()
            options=dict(baseline=admission.archive()['bookmarkBaseline'],provider_inputs=self.fixture.inputs,directory=directory)
            options['missing']=self.missing(admission)
            try:measured=observer.read(phase['ticket'],urls[label],label,epoch,publication_owner=publications,**options)
            except NativeUIError:
                # Only the retained complete first-open join can be resolved
                # here. Any partial, unrelated or invalid source remains owned.
                if directory is not None or observer.state['rows'][-1]['status']!='reserved':raise
                self.settle_directory(observer,admission)
                directory=self.directory(observer,admission);need(directory is not None)
                options['directory']=directory
                measured=observer.read(phase['ticket'],urls[label],label,self.epoch_ms(),publication_owner=publications,**options)
            initial=admission.archive();first=observer.owners()[0]
            follow_native(initial['clockJoin']['nativeAfter'],first.state['nativeStart']['nativeBefore'])
            before=deepcopy(initial['originals']);before['currentNavigation']=before.pop('navigation')
            source_prefix.follow(before,first.state['originals'],self.run,int(self.state['binding']['processIdentity']))
            self.current();ended,now=self.monotonic(),self.epoch_ms()
            measured['sequence']+=offset
            need(measured['sequence']>after_sequence and number(ended,started,started+1.5) and ended-started<1.5
                and number(now,epoch,epoch+1500) and now-epoch<1500
                and abs(now-epoch-(ended-started)*1000)<=250)
            return deepcopy(measured)

    def observe(self,after_sequence):
        """Public active originals with one original acquisition deadline."""
        started,epoch=self.monotonic(),self.epoch_ms();measured=self.observe_active(after_sequence)
        with self.held():
            self.deadline=min(self.deadline,started+1.5);self.clock();self.load()
            observer=self.observer();public=self.publications(observer).latest()
            need(public['sequence']==measured['sequence'] and public['sequence']>after_sequence
                and public['capturedEpochMs']==measured['capturedEpochMs'])
            self.current();self.clock();ended,now=self.monotonic(),self.epoch_ms()
            need(ended-started<1.5 and number(now,epoch,epoch+1500) and now-epoch<1500
                and abs(now-epoch-(ended-started)*1000)<=250)
            return deepcopy(public)
