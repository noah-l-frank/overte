"""Avatar sources and ordinary login on an existing qualified iOS session.

The separate login facade binds the actual provisioned child account, while
Avatar evidence and input ownership remain bound to the whole feature run.
These factories neither create sessions nor advertise a complete capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
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
    def _avatar_marker_scope(self,selector,client,run,role,root,ticket,lock):
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        identifier(run);identifier(ticket)
        need(isinstance(client,Client) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock))
        lock.assert_held();need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        source=self._sources(selector)
        need(source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        return IOSAvatarMarkerScope(self,selector,root,run,role,client.url+'/runs/'+run+'/',ticket,lock)

    def _avatar_samples(self,selector,scope,client,root,policy,lock):
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        from ios.adapters.avatar_samples import IOSAvatarSamples
        need(isinstance(scope,IOSAvatarMarkerScope) and isinstance(client,Client) and isinstance(lock,ScriptSourceLock))
        scope.bound();lock.assert_held();source=self._sources(selector)
        need(source['binding']==scope.binding and lock.path==self.state_path(selector).with_name('script-feature-sources.lock')
            and scope.fixture_url==client.url+'/runs/'+scope.run+'/'
            and source['target'].get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==origin(client.url))
        return IOSAvatarSamples(self,selector,scope,root,policy,PhaseFixtureReader(client,scope.run,'avatar-people'),lock)

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
            sources,inputs,NativeUI(actual['client'],actual['session'],actual['check']),peer,username,owned_origin)

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
            NativeUI(actual['client'],actual['session'],actual['check']),peer,pins())

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

    def _avatar_login(self,selector,authority,role,*,initial=True):
        from ios.adapters.avatar_authority import AvatarAuthorityReader
        need(isinstance(authority,AvatarAuthorityReader) and role in ('primary','actor') and type(initial) is bool)
        actual=authority.read();need(actual['phase'] in ('allocated','ready'))
        child=actual['accounts'][role]['runId']
        result=IOSAvatarLoginRuntime(self.adapter,authority.client,authority.run,role,child)
        # Initial login admission remains strict: an actual existing account or
        # unrelated saved username is never converted into fixture ownership.
        if initial:result._preference_admission(selector,initial=True)
        else:
            from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
            lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
            with lock.held():
                need(IOSAvatarLoginOwner(result,selector,authority,lock).load() is not None)
        return result
