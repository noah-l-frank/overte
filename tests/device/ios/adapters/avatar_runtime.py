"""Avatar sources and ordinary login on an existing qualified iOS session.

The separate login facade binds the actual provisioned child account, while
Avatar evidence and input ownership remain bound to the whole feature run.
These factories neither create sessions nor advertise a complete capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.authentication_origin import origin
from ios.adapters.authentication_runtime import IOSAuthenticationRuntime
from ios.adapters.avatar_controls import IOSAvatarIO
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSAvatarLoginRuntime(IOSAuthenticationRuntime):
    """Reuse original login/preference/probe behavior with separate ownership."""
    def __init__(self,adapter,client,avatar_run,role,child_run):
        identifier(avatar_run);identifier(child_run)
        need(role in ('primary','actor') and child_run!=avatar_run and isinstance(client,Client))
        super().__init__(adapter,client,child_run)
        self.avatar_run,self.avatar_role=avatar_run,role

    def _avatar_store(self,selector,kind):
        need(kind in ('account-origin','account-probe','private-login-input'))
        return PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+self.avatar_role+'-'+kind+'.json'))

    def account_origin_store(self,selector):return self._avatar_store(selector,'account-origin')
    def account_probe_store(self,selector,*,role='primary'):
        need(role==self.avatar_role);return self._avatar_store(selector,'account-probe')
    def private_login_input_store(self,selector):return self._avatar_store(selector,'private-login-input')
    def _account_probe(self,selector,*,role=None,read_only=False):
        need(role in (None,self.avatar_role))
        return super()._account_probe(selector,role=self.avatar_role,read_only=read_only)

    # The Authentication full journey, restart and operation entrypoints do not
    # describe Avatar preparation. Do not expose inherited dispatch accidentally.
    def _authentication_actions(self,*_args,**_kwargs):need(False)
    def _authentication_feature(self,*_args,**_kwargs):need(False)
    def invoke(self,*_args,**_kwargs):need(False)


class IOSAvatarRuntime(IOSScriptRuntime):
    def _avatar_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.avatar_configuration import settings as validate_settings
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(role in ('primary','actor') and isinstance(client,Client));identifier(run)
        selected=validate_settings(settings,role=role,target=selector)
        return IOSAvatarFeature(self,selector,client,run,role,selected)

    def _avatar_postlogout_tail(self,selector,client,run,role,subject,root,lock,*,child_run,ticket,baseline,logout_before,epoch_ms=None,monotonic=None,held=False):
        from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
        identifier(run);identifier(child_run);identifier(ticket);need(isinstance(client,Client) and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector);binding=source['binding']
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        def factory():
            current=self._sources(selector);need(current['binding']==binding);return current
        need(type(held) is bool);Tail=IOSAvatarPostLogoutTail
        if held:
            from ios.adapters.avatar_held_tail import IOSAvatarHeldTail
            Tail=IOSAvatarHeldTail
        return Tail(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-'+subject+'-postlogout-tail.json')),
            root,binding,run,role,subject,lock,source['check'],factory,child_run=child_run,fixture_url=client.url+'/runs/'+child_run+'/',ticket=ticket,
            baseline=baseline,logout_before=logout_before,epoch_ms=(lambda:time.time()*1000) if epoch_ms is None else epoch_ms,
            monotonic=time.monotonic if monotonic is None else monotonic)

    def _avatar_marker_web_receipts(self,selector,client,run,role,root,lock,*,fixture_url,epoch_ms,monotonic):
        from ios.adapters.avatar_marker_web_receipts import IOSAvatarMarkerWebReceipts
        need(isinstance(client,Client) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor'))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock')
            and fixture_url==client.url+'/runs/'+identifier(run)+'/')
        actual=self._sources(selector)
        return IOSAvatarMarkerWebReceipts(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-marker-web.json')),
            root,actual['binding'],run,role,lock,actual['check'],native=actual['clock_source'],reader=actual['observer'].web_closures(),
            fixture_url=fixture_url,epoch_ms=epoch_ms,monotonic=monotonic)

    def _avatar_postlogout_reads(self,selector,client,run,role,subject,root,lock,*,child_run,ticket,baseline,logout_before,epoch_ms=None,monotonic=None):
        from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
        identifier(run);identifier(child_run);identifier(ticket);lock.assert_held()
        source=self._sources(selector);binding=source['binding'];need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        epoch_ms=(lambda:time.time()*1000) if epoch_ms is None else epoch_ms
        monotonic=time.monotonic if monotonic is None else monotonic
        need(callable(epoch_ms) and callable(monotonic))
        def accounts():return self._avatar_account_reads(selector,client,run,role,subject,root,lock,epoch_ms=epoch_ms,monotonic=monotonic)
        def model():
            current=self._sources(selector);need(current['binding']==binding)
            return current['observer'].avatar_state(current['clock_source']),current['clock_source']
        return IOSAvatarPostLogoutReads(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-'+subject+'-postlogout.json')),
            root,binding,run,role,subject,lock,source['check'],accounts,model,child_run=child_run,fixture_url=client.url+'/runs/'+child_run+'/',
            ticket=ticket,baseline=baseline,logout_before=logout_before,epoch_ms=epoch_ms,monotonic=monotonic)

    def _avatar_account_reads(self,selector,client,run,role,subject,root,lock,*,epoch_ms=None,monotonic=None):
        from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
        identifier(run);need(isinstance(client,Client) and role in ('primary','actor') and subject in ('primary','actor')
            and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector);observer,clock=source['observer'],source['clock_source']
        # This observes the original account on an existing SDK session. It
        # deliberately does not require an Avatar UUID or joined Domain.
        epoch_ms=(lambda:time.time()*1000) if epoch_ms is None else epoch_ms
        monotonic=time.monotonic if monotonic is None else monotonic
        return IOSAvatarAccountReads(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-'+subject+'-account-reads.json')),
            root,source['binding'],run,role,subject,lock,source['check'],observer.bound_native_observer(clock),clock_source=clock,epoch_ms=epoch_ms,monotonic=monotonic)

    def _avatar_marker_scope(self,selector,client,run,role,root,ticket,lock):
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        identifier(run);identifier(ticket)
        need(isinstance(client,Client) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector)
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        return IOSAvatarMarkerScope(self,selector,root,run,role,client.url+'/runs/'+run+'/',ticket,lock)

    def _avatar_held_marker_scope(self,selector,client,run,role,root,ticket,lock):
        from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
        identifier(run);identifier(ticket)
        need(isinstance(client,Client) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector)
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        return IOSAvatarHeldMarkerScope(self,selector,root,run,role,client.url+'/runs/'+run+'/',ticket,lock)

    def _avatar_marker_entities(self,selector,scope,root,lock):
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        from ios.adapters.avatar_marker_entities import IOSAvatarMarkerEntities
        need(isinstance(scope,IOSAvatarMarkerScope) and isinstance(lock,ScriptSourceLock))
        lock.assert_held();scope.bound();source=self._sources(selector)
        need(source['binding']==scope.binding and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        observer,clock=source['observer'],source['clock_source']
        return IOSAvatarMarkerEntities(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+scope.role+'-marker-entities.json')),
            root,scope.binding,scope.run,scope.role,lock,source['check'],native=observer.bound_native_observer(clock),
            entities=observer.create_entities(clock),epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic)

    def _avatar_samples(self,selector,scope,client,root,policy,lock):
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        from ios.adapters.avatar_samples import IOSAvatarSamples
        need(isinstance(scope,IOSAvatarMarkerScope) and isinstance(client,Client) and isinstance(lock,ScriptSourceLock))
        scope.bound();lock.assert_held();source=self._sources(selector)
        need(source['binding']==scope.binding and lock.path==self.state_path(selector).with_name('script-feature-sources.lock')
            and scope.fixture_url==client.url+'/runs/'+scope.run+'/'
            and source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        Samples=IOSAvatarSamples
        from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
        if type(scope) is IOSAvatarHeldMarkerScope:
            from ios.adapters.avatar_held_samples import IOSAvatarHeldSamples
            Samples=IOSAvatarHeldSamples
        return Samples(self,selector,scope,root,policy,PhaseFixtureReader(client,scope.run,'avatar-people'),lock)

    def _avatar_consent(self,selector,sources,peer,username):
        from ios.adapters.avatar_consent import IOSAvatarConsent
        from ios.adapters.avatar_input_owner import AvatarInputOwner
        need(isinstance(sources,IOSAvatarSources) and not sources.historical and sources.role=='actor')
        sources.bound();actual=self._sources(selector);need(actual['binding']==sources.binding)
        owned_origin=origin(sources.phase.client.url)
        need(actual['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==owned_origin)
        inputs=AvatarInputOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-actor-inputs.json')),
            sources.lock,sources.binding,sources.run,'actor',sources.phase.fixture_url,sources.guard)
        return IOSAvatarConsent(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-actor-consent.json')),
            sources,inputs,NativeUI(actual['client'],actual['session'],actual['check']),peer,username,owned_origin,
            input_reads=self._avatar_input_reads(selector,sources))

    def _avatar_receive(self,selector):
        from adapters.native_avatar_receive import NativeAvatarReceive,FILE,LIMIT
        source=self._sources(selector);observer=source['observer'];remote=observer.remote.rsplit('/',1)[0]+'/'+FILE
        return NativeAvatarReceive(observer.send,lambda:observer.original(remote=remote,limit=LIMIT),
            source['native_clock'],source['check'],int(source['binding']['processIdentity']),ios=True)

    def _avatar_peer_sources(self,selector,client,run,role,root,lock):
        from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
        identifier(run);need(isinstance(client,Client) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector)
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        return IOSAvatarPeerSources(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-peer-sources.json')),
            root,source['binding'],run,PhaseFixtureReader(client,run,'avatar-people'),lock,source['check'],
            runtime=self,selector=selector,role=role)

    def _avatar_actions(self,selector,sources,peer):
        from ios.adapters.avatar_actions import IOSAvatarActions
        from ios.adapters.avatar_input_owner import AvatarInputOwner
        from ios.adapters.avatar_code import pins
        need(isinstance(sources,IOSAvatarSources) and not sources.historical and sources.role=='primary')
        sources.bound();actual=self._sources(selector);need(actual['binding']==sources.binding)
        inputs=AvatarInputOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-primary-inputs.json')),
            sources.lock,sources.binding,sources.run,'primary',sources.phase.fixture_url,sources.guard)
        return IOSAvatarActions(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-primary-actions.json')),sources,inputs,
            NativeUI(actual['client'],actual['session'],actual['check']),peer,pins(),input_reads=self._avatar_input_reads(selector,sources))

    def _avatar_input_reads(self,selector,sources):
        from ios.adapters.avatar_input_reads import IOSAvatarInputReads
        need(isinstance(sources,IOSAvatarSources) and not sources.historical);sources.bound();actual=self._sources(selector)
        need(actual['binding']==sources.binding and sources.lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        reader=actual['observer'].avatar_inputs(actual['clock_source'])
        return IOSAvatarInputReads(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+sources.role+'-input-reads.json')),
            sources.root,sources.binding,sources.run,sources.role,sources.lock,actual['check'],reader)

    def _avatar_cleanup_controls(self,selector,sources):
        from ios.adapters.avatar_cleanup_inputs import AvatarCleanupInputOwner
        from ios.adapters.avatar_cleanup_controls import IOSAvatarCleanupControls
        need(isinstance(sources,IOSAvatarSources) and not sources.historical);sources.bound();actual=self._sources(selector)
        need(actual['binding']==sources.binding)
        inputs=AvatarCleanupInputOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+sources.role+'-cleanup-inputs.json')),
            sources.lock,sources.binding,sources.run,sources.role,sources.phase.fixture_url,actual['check'])
        return IOSAvatarCleanupControls(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+sources.role+'-cleanup-controls.json')),
            sources,inputs,NativeUI(actual['client'],actual['session'],actual['check']),self._avatar_input_reads(selector,sources))

    def _avatar_sources(self,selector,client,run,role,root,lock):
        identifier(run);need(isinstance(client,Client) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock))
        expected_origin=origin(client.url);lock.assert_held()
        need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector);observer=source['observer'];clock=source['clock_source']
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==expected_origin)
        readers=dict(state=observer.avatar_state(clock),renderers=observer.avatar_renderers(clock),
            http=observer.avatar_social_http(clock),people=observer.people_model(clock),scripts=observer.avatar_scripts(clock),entities=observer.avatar_entities(clock),
            native=observer.bound_native_observer(clock),ui=IOSAvatarIO(source['native']))
        return IOSAvatarSources(PrivateFeatureState(self.state_path(selector).with_name('ios-avatar-'+role+'-sources.json')),
            root,source['binding'],run,role,lock,source['check'],PhaseFixtureReader(client,run,'avatar-people'),readers=readers)

    def _avatar_login(self,selector,authority,role,*,initial=True,lock=None):
        from ios.adapters.avatar_authority import AvatarAuthorityReader
        need(isinstance(authority,AvatarAuthorityReader) and role in ('primary','actor') and type(initial) is bool)
        # A whole coordinator already owns this exact SDK lock. Reuse only
        # the explicitly supplied, path/process/thread-validated instance; a
        # second instance would contend with the caller's own OS flock.
        need(lock is None or isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        if lock is not None:lock.assert_held()
        actual=authority.read();need(actual['phase'] in ('allocated','ready'))
        child=actual['accounts'][role]['runId']
        result=IOSAvatarLoginRuntime(self.adapter,authority.client,authority.run,role,child)
        # Initial login admission remains strict: an actual existing account or
        # unrelated saved username is never converted into fixture ownership.
        if initial:result._preference_admission(selector,initial=True)
        else:
            from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
            lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock')) if lock is None else lock
            with lock.held():
                need(IOSAvatarLoginOwner(result,selector,authority,lock).load() is not None)
        return result
