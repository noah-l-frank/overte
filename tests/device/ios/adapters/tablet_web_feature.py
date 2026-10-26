"""Whole ordinary Tablet act/observe and live cleanup on one physical SDK.

The primary alone owns input and eventual canonical Stop/SDK deletion. Actor
uses its own real process, queries, files and publication, sharing only the
actual physical SDK/source lock. Terminal process-end composition is separate;
this unqualified implementation advertises no complete feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_feature_observation import exact,need,number
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.adapters.tablet_web_actions import TabletWebActions
from ios.adapters.tablet_web_app_owner import input_scopes
from ios.adapters.tablet_web_cleanup import TabletWebCleanupAppOwner
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import scripts_drained
from ios.adapters.tablet_web_cleanup_observation import validate as cleanup_original
from ios.adapters.tablet_web_background import TabletWebBackground
from ios.adapters.tablet_web_native_semantics import scope as native_semantics_scope
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope as record_scope

VERSION=1


class IOSTabletWebFeature:
    def __init__(self,runtime,selector,client,run,role,binding,setup_native,origins,*,monotonic=time.monotonic,
                 epoch_ms=lambda:int(time.time()*1000),sleep=time.sleep,screen=None):
        need(isinstance(runtime,IOSTabletWebRuntime) and isinstance(client,Client) and role in ('primary','actor'))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.binding,self.setup,self.origins=deepcopy(context(binding)),deepcopy(setup_native),deepcopy(origins)
        self.screen=deepcopy(screen)
        if screen is not None:
            exact(screen,{'artifactRoot','policy'});path=Path(screen['artifactRoot'])
            need(path.is_absolute() and path.resolve()==path and path.is_dir());exact(screen['policy'],{'source','marker','subject'})
            need(screen['policy']['source']=='native-screen')
        self.monotonic,self.epoch_ms,self.sleep=monotonic,epoch_ms,sleep;self.deadline=None;self.last=None;self.failed=False
        self.root=runtime.state_path(selector).parent
        self.store=PrivateFeatureState(self.root/('tabletweb-feature-'+run+'-'+role+'.json'));self.saved=None;self.state=None
    def clock(self):
        now=self.monotonic()
        if self.failed or not number(now,0,1e15) or self.last is not None and now<self.last or self.deadline is not None and now>=self.deadline:
            self.failed=True;need(False)
        self.last=now;return now
    @contextmanager
    def operation(self):
        old=self.deadline
        if old is None:self.failed=False;self.record_cache=TabletRecordCache()
        now=self.clock();self.deadline=now+60 if old is None else min(old,now+60)
        try:
            with transport_scope(self.clock),record_scope(self.record_cache):yield;self.clock()
        finally:self.deadline=old
    def envelope(self):return dict(tabletWebFeatureVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
        setupSha256=digest(self.setup),origins=self.origins,screen=self.screen,payload=pack([self.state]))
    def load(self,observer,*,historical=False):
        need(type(historical) is bool)
        if historical:need(observer.observer.source.historical)
        else:observer.check()
        self.saved=self.store.read()
        if self.saved is None:self.state=None;return
        exact(self.saved,{'tabletWebFeatureVersion','binding','runId','role','setupSha256','origins','screen','payload'})
        rows=unpack(self.saved['payload']);need(len(rows)==1);self.state=rows[0]
        need(type(self.saved['tabletWebFeatureVersion']) is int and self.saved['tabletWebFeatureVersion']==VERSION
            and same(self.saved,self.envelope()))
        exact(self.state,{'phase','initial','cleanupBefore','cleanupStop','quiet','cleanupOriginal','lastCall','filesReleased'})
        need(type(self.state['filesReleased']) is bool and self.state['phase'] in ('active','cleaning','quiet','sealed','ended') and type(self.state['quiet']) is list and len(self.state['quiet'])<=128)
        observer.validate_original(self.state['initial'])
        if self.state['cleanupOriginal'] is not None:cleanup_original(observer,self.state['cleanupOriginal'])
    def save(self,observer):
        observer.check();value=self.envelope();self.store.write(value,self.saved);self.saved=deepcopy(value)
    @contextmanager
    def parts(self):
        if self.role=='primary':
            background=TabletWebBackground(self.runtime,self.selector,self.run,self.binding,
                fixture_url=self.client.url+'/runs/'+self.run+'/',monotonic=self.monotonic,sleep=self.sleep)
            if background.state is not None and background.state['phase']!='observed':background.recover_foreground()
        with ExitStack() as stack:
            while True:
                self.clock()
                try:
                    observer=stack.enter_context(self.runtime.observer_runtime(self.selector,self.run,self.role,self.client,self.origins,self.binding,self.setup,
                        epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep));break
                except ScriptSourceBusy:self.sleep(.025);self.clock()
            observer.proof_roots=[observer.observer.source.root]
            if self.screen is not None:observer.proof_roots.append(Path(self.screen['artifactRoot']))
            with native_semantics_scope(observer.native_semantics):self.load(observer);yield observer
    @contextmanager
    def locked(self,lock=None):
        lock=lock or ScriptSourceLock(self.root/'script-feature-sources.lock')
        need(lock.path==self.root/'script-feature-sources.lock')
        with ExitStack() as stack:
            while True:
                self.clock()
                try:stack.enter_context(lock.held());break
                except ScriptSourceBusy:self.sleep(.025);self.clock()
            yield lock;self.clock()
    def initial(self,observer):
        if self.state is not None:return
        original=observer.observe();value=observer.validate_original(original)
        need(not value['public']['resources'] and not observer.observer.source.state['apps'])
        self.state=dict(phase='active',initial=original,cleanupBefore=None,cleanupStop=None,quiet=[],cleanupOriginal=None,lastCall=None,filesReleased=False)
        self.save(observer)
    def observe(self,call):
        call=arguments('feature.tablet-web.observe',call);need(call['runId']==self.run)
        with self.operation():
            while True:
                with self.parts() as observer:
                    self.initial(observer)
                    if self.state['phase'] in ('cleaning','quiet'):value=self.cleanup_live(observer)
                    else:
                        need(self.state['phase']=='active');value=observer.publication_original(self.active_original(observer))['public']
                if value is not None:return value
                # Actual quiet time passes outside the sole shared SDK lock;
                # Actor can acquire its own original frames in this interval.
                self.sleep(1.6);self.clock()
    def active_original(self,observer):
        original=observer.observe();measured=observer.validate_original(original)
        phase=observer.observer.phase.previous;need(phase is not None and phase['active'])
        verb=phase['activations'][-1]['stimulus']['verb']
        if self.screen is not None and measured['public']['state']['open'] and verb in (
                'open','navigate','back','navigate-foreign','reload','background-resume','open-inline-app','return-from-inline'):
            before=dict(tabletWebTailSourceVersion=1,bootstrap=deepcopy(original['bootstrap']),primaryBootstrap=deepcopy(original['primaryBootstrap']),
                observation=deepcopy(original['observation']))
            return observer.observe_image(Path(self.screen['artifactRoot']),self.screen['policy'],measured['ticket'],readiness=False,before=before)
        return original
    def act(self,call):
        call=deepcopy(arguments('feature.tablet-web.act',call));need(self.role=='primary' and call['runId']==self.run
            and call['fixtureUrl']==self.client.url+'/runs/'+self.run+'/')
        with self.operation():
            while True:
                with self.parts() as observer:
                    self.initial(observer);need(self.state['phase']=='active')
                    if call['verb']=='background-resume':
                        phase=observer.observer.phase.read();need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
                        background=TabletWebBackground(self.runtime,self.selector,self.run,self.binding,
                            fixture_url=self.client.url+'/runs/'+self.run+'/',monotonic=self.monotonic,sleep=self.sleep)
                        background.start(observer,call);result=background.finish(observer)
                    else:result=TabletWebActions(observer).act(call)
                    if result is not None:self.state['lastCall']=call;self.save(observer);return result
                self.sleep(.25);self.clock()  # Same original budget, outside the shared SDK lock.
    def cleanup_live(self,observer):
        """Ordinary primary inputs, both roles' independent actual quiet tails."""
        need(self.state is not None and self.state['phase'] in ('active','cleaning','quiet'))
        source=observer.observer.source
        if self.role=='primary' and self.state['cleanupBefore'] is not None and self.state['cleanupStop'] is None:
            from ios.adapters.tablet_web_app_readiness import ready
            if not ready(observer,input_scopes(source.root,source.binding,source.run,ready_only=True)):return None
        tail=TabletWebTail(observer)
        ownerships=input_scopes(source.root,source.binding,source.run)
        observer.recover_auxiliaries(ownerships)
        if tail.state['pending'] is not None:
            if tail.state['original'] is not None:tail.recover_original()
            else:tail.archive_failed()
        if self.state['cleanupBefore'] is None:
            self.state['cleanupBefore']=tail.capture(ownerships);self.state['phase']='cleaning';self.save(observer)
            if self.role=='primary':return None  # Let the independent Actor retain its live app originals outside this lock.
        if self.role=='primary' and self.state['cleanupStop'] is None:
            cleanup=TabletWebCleanupAppOwner(observer);cleanup.close_page();cleanup.stop_apps()
        if self.state['cleanupStop'] is None:
            self.state['cleanupStop']=tail.capture(ownerships);self.save(observer)
        if self.role=='primary' and not self.state['filesReleased']:
            current=tail.capture(ownerships)
            # Actual worker exit/dialog return may follow the normal Stop
            # asynchronously. A new complete frame is required on each retry;
            # nothing is resent and all earlier originals remain retained.
            from adapters.normal_ui import NativeUIError
            try:scripts_drained(tail.read(self.state['cleanupBefore']),tail.read(self.state['cleanupStop']),tail.read(current),source.app_sources())
            except NativeUIError:return None
            cleanup=TabletWebCleanupAppOwner(observer)
            cleanup.release_files(self.state['cleanupBefore'],self.state['cleanupStop'],current)
            self.state['filesReleased']=True;self.save(observer)
        if self.screen is not None:
            from ios.adapters.tablet_web_samples import TabletWebSamples
            samples=TabletWebSamples(observer,Path(self.screen['artifactRoot']),self.screen['policy']);samples.cleanup_files()
        # Actor never repeats Primary input, stage/release, Stop or SDK deletion.
        # It acquires its own original NativeFiles absence and native lifetime
        # dispositions after the actual primary effects become observable.
        need(len(self.state['quiet'])<128)
        self.state['quiet'].append(tail.capture(ownerships));self.save(observer)
        if len(self.state['quiet'])<3:return None
        from ios.adapters.tablet_web_cleanup_observation import candidates
        possibilities=candidates(observer,self.state['cleanupBefore'],self.state['cleanupStop'],self.state['quiet'])
        if not possibilities or possibilities[-1]['quiet'][-1]!=self.state['quiet'][-1]:return None
        original=possibilities[-1]
        value=cleanup_original(observer,original)
        self.state.update(phase='quiet',cleanupOriginal=original);self.save(observer);return value['public']
    def cleanup(self,call):
        call=arguments('feature.tablet-web.cleanup',call);need(call['runId']==self.run)
        with self.operation():
            while True:
                with self.parts() as observer:
                    self.initial(observer);value=self.cleanup_live(observer)
                if value is not None:return {'performed':True}
                self.sleep(1.6);self.clock()
    def publish(self):
        need(self.role=='actor')
        # This is a durable input responsibility cue only. The independent
        # observer must not query a foreground-only native source while the
        # primary's actual ordinary background/activation is unresolved.
        with self.locked():
            background=TabletWebBackground(self.runtime,self.selector,self.run,self.binding,
                fixture_url=self.client.url+'/runs/'+self.run+'/',monotonic=self.monotonic,sleep=self.sleep)
            if background.state is not None and background.state['phase']!='observed':return None
            primary=PrivateFeatureState(self.root/('tabletweb-feature-'+self.run+'-primary.json')).read()
            if primary is not None:
                need(same(primary.get('binding'),self.binding) and primary.get('runId')==self.run and primary.get('role')=='primary')
                rows=unpack(primary['payload']);need(len(rows)==1)
                if rows[0]['phase']=='active':
                    all_scopes=input_scopes(self.root,self.binding,self.run);ready_scopes=input_scopes(self.root,self.binding,self.run,ready_only=True)
                    if len(ready_scopes)<len(all_scopes):return None
        with self.operation(),self.parts() as observer:
            self.initial(observer)
            publisher=observer.actor_publisher()
            # An actual issued publication keeps its original body/clock and
            # must reconcile read-only before acquiring another VM/page frame.
            if publisher.state['pending'] is not None:return publisher.resolve()
            from ios.adapters.tablet_web_app_readiness import retain
            for metadata in input_scopes(self.root,self.binding,self.run,ready_only=True):retain(observer,metadata,observer.remember_app(metadata))
            primary=PrivateFeatureState(self.root/('tabletweb-feature-'+self.run+'-primary.json')).read()
            if primary is not None:
                need(same(primary.get('binding'),self.binding) and primary.get('runId')==self.run and primary.get('role')=='primary')
                rows=unpack(primary['payload']);need(len(rows)==1)
                # This is only a cleanup responsibility cue; effects below
                # come exclusively from this actor's independent raw originals.
                if rows[0]['phase'] in ('cleaning','quiet'):
                    if self.cleanup_live(observer) is None:return None
                    return publisher.publish(self.state['cleanupOriginal'])
            if not self.input_returned(observer,primary):return None
            return publisher.publish(self.active_original(observer))
    def input_returned(self,observer,primary):
        """Private completed-input cue; all effects still need Actor originals.

        Ordinary app preparation can release the shared lock for independent
        app admission. Publishing the previous page under that new ticket in
        this interval would leave stale entries before the first checkpoint.
        The actual saved act call only orders acquisition; it proves no page,
        callback, input delivery or feature result.
        """
        phase=observer.observer.phase.read();need(phase['status']['active'])
        if primary is None:return phase['verb']=='baseline'
        exact(primary,{'tabletWebFeatureVersion','binding','runId','role','setupSha256','origins','screen','payload'})
        need(type(primary['tabletWebFeatureVersion']) is int and primary['tabletWebFeatureVersion']==VERSION
            and same(primary['binding'],self.binding) and primary['runId']==self.run and primary['role']=='primary')
        rows=unpack(primary['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','initial','cleanupBefore','cleanupStop','quiet','cleanupOriginal','lastCall','filesReleased'})
        need(state['phase']=='active')
        if phase['verb']=='baseline':return True
        call=state['lastCall']
        if call is None:return False
        call=arguments('feature.tablet-web.act',call)
        need(call['runId']==self.run and call['fixtureUrl']==observer.observer.source.fixture)
        if call['ticket']!=phase['ticket']:return False
        need(call['verb']==phase['verb'] and same(call['inputs'],phase['inputs']))
        return True
    def terminal(self,call):
        from feature_journeys import terminal as protocol
        from ios.adapters.tablet_web_terminal import TabletWebTerminal
        call=deepcopy(protocol.arguments('tablet-web',call));need(call['runId']==self.run and self.role=='primary')
        with self.operation():
            if call['stage']=='finish':
                from ios.adapters.tablet_web_terminal_finish import finish
                response=dict(stage='finish',end=finish(self,call['seal']))
            else:
                with self.parts() as observer:
                    need(self.state is not None and self.state['phase']=='quiet');owner=TabletWebTerminal(self,observer.observer.source.lock)
                    if call['stage']=='inspect':response=dict(stage='inspect',description=owner.inspect(observer))
                    else:response=dict(stage='seal',seal=owner.seal(observer,call['description'],call['samples']))
            protocol.result('tablet-web',response);return response
