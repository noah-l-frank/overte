"""Real scope/source owners and factories; explicit native/session boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_accounts import AvatarAccountScopes
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.witness import Client
from ios.adapters import avatar_runtime
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_runtime import IOSAvatarRuntime,IOSAvatarLoginRuntime
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);os.chmod(self.path,0o700)
        self.root=self.path/'originals';self.root.mkdir(mode=0o700)
        self.epoch=1700000000000;self.run='a'*32;self.ticket='b'*32;self.mono=1.
        self.account=AccountProvider(epoch_ms=lambda:self.epoch)
        self.social=AvatarSocialProvider(account_authenticator(self.account),epoch_ms=lambda:self.epoch)
        self.scopes=AvatarAccountScopes(self.account,self.social);self.scopes.provision(self.run);self.scopes.activate(self.run,self.ticket)
        self.client=Client('https://controlled.invalid/feature-fixture/v1','a'*64);self.calls=[]
        self.mutate=None
        def request(path,**_kwargs):
            self.calls.append(path);prefix='/runs/'+self.run+'/avatar/'
            need(path.startswith(prefix));route=path[len(prefix):]
            value=self.scopes.snapshot(self.run) if route=='accounts' else self.scopes.credentials(self.run,route.split('/')[1])
            if self.mutate:self.mutate(route,value)
            return value
        self.client.request=request
        self.authority=AvatarAuthorityReader(self.client,self.run,epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
        self.adapter=SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True,
            state_path=lambda _selector:self.path/'session.json')

    def test_actual_distinct_child_scopes_and_separate_credentials_are_input_only(self):
        original=self.authority.read()
        for role in ('primary','actor'):
            credentials=self.authority.credentials(role)
            self.assertEqual('e2e-'+original['accounts'][role]['runId'],credentials['username'])
            self.assertNotIn(credentials['password'],repr(vars(self.authority)))
        self.assertTrue(all(row['accessTokens']==0 for row in self.authority.last['accounts'].values()))
        self.assertIsNone(self.authority.last['social'])

    def test_foreign_scope_changed_child_or_rewritten_time_cannot_become_owned(self):
        self.authority.read()
        for fault in ('instance','child','epoch','version','duplicate'):
            def mutate(route,value):
                if fault=='instance':value['instance']='f'*32
                elif fault=='child':value['accounts']['primary']['runId']='f'*32
                elif fault=='epoch':value['accounts']['actor']['capturedEpochMs']=self.epoch-2000
                elif fault=='version':value['avatarAccountsVersion']=True
                else:value['accounts']['actor']=deepcopy(value['accounts']['primary'])
            self.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.authority.read()

    def test_each_child_has_independent_original_HTTP_bracket_and_no_outer_time_is_invented(self):
        self.authority.read()
        def delayed(_route,value):
            self.epoch+=1600;self.mono+=1.6
        self.mutate=delayed
        with self.assertRaises(NativeUIError):self.authority.read()
        self.assertNotIn('capturedEpochMs',self.authority.last)

    def test_credential_mismatch_and_revocation_never_permit_new_login_input(self):
        def swapped(route,value):
            if route.startswith('credentials/'):value['username']='e2e-'+'f'*32
        self.mutate=swapped
        with self.assertRaises(NativeUIError):self.authority.credentials('primary')
        self.mutate=None;self.scopes.revoke(self.run);actual=self.authority.read();self.assertEqual('revoking',actual['phase'])
        with self.assertRaises(NativeUIError):self.authority.credentials('actor')
        with patch.object(IOSAvatarLoginRuntime,'_preference_admission') as admission:
            with self.assertRaises(NativeUIError):IOSAvatarRuntime(self.adapter)._avatar_login('target',self.authority,'primary')
        admission.assert_not_called()

    def test_actual_child_run_is_used_by_existing_ordinary_login_components_and_private_stores_are_separate(self):
        runtime=IOSAvatarRuntime(self.adapter);owners=[]
        with patch.object(IOSAvatarLoginRuntime,'_preference_admission',return_value={}) as admission:
            for role in ('primary','actor'):
                login=runtime._avatar_login('target',self.authority,role);owners.append(login)
                self.assertEqual(self.authority.last['accounts'][role]['runId'],login.run)
                self.assertEqual(self.run,login.avatar_run)
                self.assertIn('ios-avatar-'+role,login.private_login_input_store('target').path.name)
                self.assertNotIn('authentication',login.account_origin_store('target').path.name)
                self.assertIn(role,login.account_probe_store('target',role=role).path.name)
                with self.assertRaises(NativeUIError):login.invoke('target','app.launch',{})
        self.assertEqual(2,admission.call_count)
        self.assertNotEqual(owners[0].private_login_input_store('target').path,owners[1].private_login_input_store('target').path)
        self.assertNotEqual(owners[0].run,owners[1].run)

    def test_existing_session_factory_reuses_true_readers_and_archives_whole_source_group(self):
        fixture=SourcesFixture();fixture.phase.client.url=self.client.url;readers=fixture.readers()
        names={'avatar_state':'state','avatar_renderers':'renderers','avatar_social_http':'http','people_model':'people','avatar_scripts':'scripts','avatar_entities':'entities',
            'bound_native_observer':'native'}
        observer=SimpleNamespace(**{name:(lambda _clock,key=key:readers[key]) for name,key in names.items()})
        native=readers['ui'].native
        source=dict(observer=observer,clock_source=readers['native'],native=native,binding=BINDING,check=lambda:True,
            target=dict(testBuild=dict(launchEnvironment=dict(HIFI_METAVERSE_URL='https://controlled.invalid'))))
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,_selector):return source
        runtime=Runtime(self.adapter);lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        with lock.held(),patch.object(avatar_runtime,'PhaseFixtureReader',return_value=fixture.phase):
            owner=runtime._avatar_sources('target',self.client,fixture.run,'primary',self.root,lock)
            owner.epoch_ms=fixture.host;owner.monotonic=lambda:fixture.clock
            owner.originals.monotonic=lambda:fixture.clock
            original=owner.read()
        self.assertEqual(fixture.run,original['originals']['state']['runId'])
        self.assertEqual(BINDING,owner.binding);self.assertEqual(1,owner.state['revision'])
        self.assertTrue(list(self.root.glob('avatar-frame-*.json')))

    def test_peer_factories_bind_each_actual_role_sdk_and_fixed_original_receive_file(self):
        from adapters.native_avatar_receive import NativeAvatarReceive,FILE,LIMIT
        from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
        calls=[];observer=SimpleNamespace(remote='@org.example.client:documents/private/feature-native-observation.json',
            send=lambda value:calls.append(value),original=lambda **kwargs:calls.append(kwargs) or '{}')
        source=dict(observer=observer,native_clock=lambda:20000,binding=BINDING,check=lambda:True,
            target=dict(testBuild=dict(launchEnvironment=dict(HIFI_METAVERSE_URL='https://controlled.invalid'))))
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,_selector):return source
        runtime=Runtime(self.adapter);receiver=runtime._avatar_receive('target')
        self.assertIsInstance(receiver,NativeAvatarReceive);self.assertTrue(receiver.ios)
        self.assertEqual(int(BINDING['processIdentity']),receiver.pid);receiver.original()
        self.assertEqual(dict(remote=observer.remote.rsplit('/',1)[0]+'/'+FILE,limit=LIMIT),calls[-1])
        lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        with lock.held():
            for role in ('primary','actor'):
                owner=runtime._avatar_peer_sources('target',self.client,self.run,role,self.root,lock)
                self.assertIsInstance(owner,IOSAvatarPeerSources);self.assertEqual(role,owner.role)
                self.assertEqual('avatar-people',owner.phase.area);self.assertEqual(BINDING,owner.binding)
                self.assertEqual('ios-avatar-'+role+'-peer-sources.json',owner.store.path.name)
            source['target']['testBuild']['launchEnvironment']['HIFI_METAVERSE_URL']='https://foreign.invalid'
            with self.assertRaises(NativeUIError):runtime._avatar_peer_sources('target',self.client,self.run,'actor',self.root,lock)

    def test_marker_and_sample_factories_preserve_actual_sdk_role_lock_and_controlled_origin(self):
        from ios.adapters import avatar_marker_scope,avatar_samples
        source=dict(binding=BINDING,target=dict(testBuild=dict(launchEnvironment=dict(HIFI_METAVERSE_URL='https://controlled.invalid'))))
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,_selector):return source
        runtime=Runtime(self.adapter);lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        marker=object.__new__(avatar_marker_scope.IOSAvatarMarkerScope)
        marker.binding,marker.run,marker.role=BINDING,self.run,'actor';marker.fixture_url=self.client.url+'/runs/'+self.run+'/'
        marker.bound=lambda:lock.assert_held()
        with lock.held(),patch.object(avatar_marker_scope,'IOSAvatarMarkerScope',autospec=True) as constructor:
            constructor.return_value=marker
            self.assertIs(marker,runtime._avatar_marker_scope('target',self.client,self.run,'actor',self.root,self.ticket,lock))
            self.assertEqual((runtime,'target',self.root,self.run,'actor',marker.fixture_url,self.ticket,lock),constructor.call_args.args)
        with lock.held(),patch.object(avatar_samples,'IOSAvatarSamples',autospec=True) as constructor:
            made=runtime._avatar_samples('target',marker,self.client,self.root,dict(source='world-render-target'),lock)
            self.assertIs(constructor.return_value,made);phase=constructor.call_args.args[-2]
            self.assertEqual('avatar-people',phase.area);self.assertEqual(self.run,phase.run)
            self.assertIs(marker,constructor.call_args.args[2])
            source['binding']=BINDING|dict(artifactSha256='f'*64)
            with self.assertRaises(NativeUIError):runtime._avatar_samples('target',marker,self.client,self.root,{},lock)
            source['binding']=BINDING;source['target']['testBuild']['launchEnvironment']['HIFI_METAVERSE_URL']='https://foreign.invalid'
            with self.assertRaises(NativeUIError):runtime._avatar_marker_scope('target',self.client,self.run,'actor',self.root,self.ticket,lock)

    def test_consent_factory_owns_actor_only_under_actual_candidate_and_fixture_origin(self):
        fixture=SourcesFixture();fixture.phase.client.url=self.client.url;readers=fixture.readers()
        from ios.adapters.avatar_sources import IOSAvatarSources
        from ios.adapters.avatar_consent import IOSAvatarConsent
        actual=dict(binding=BINDING,check=lambda:True,client=object(),session='owned-sdk-session',
            target=dict(testBuild=dict(launchEnvironment=dict(HIFI_METAVERSE_URL='https://controlled.invalid'))))
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,_selector):return actual
        lock=ScriptSourceLock(self.path/'script-feature-sources.lock');runtime=Runtime(self.adapter)
        with lock.held():
            source=IOSAvatarSources(PrivateFeatureState(self.path/'ios-avatar-actor-sources.json'),self.root,BINDING,
                fixture.run,'actor',lock,lambda:True,fixture.phase,readers=readers,
                monotonic=lambda:fixture.clock,epoch_ms=fixture.host)
            consent=runtime._avatar_consent('target',source,'00000000-0000-4000-8000-000000000002','e2e-'+'e'*32)
            self.assertIsInstance(consent,IOSAvatarConsent);self.assertEqual('actor',consent.inputs.role)
            self.assertEqual('ios-avatar-actor-consent.json',consent.store.path.name)
            self.assertEqual('https://controlled.invalid',consent.origin)
            actual['binding']=BINDING|dict(artifactSha256='f'*64)
            with self.assertRaises(NativeUIError):runtime._avatar_consent('target',source,consent.peer,consent.username)


if __name__=='__main__':unittest.main()
