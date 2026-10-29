"""Existing Primary/Actor owners with distinct GET-only/control authority.

Normal SDK/Qt/render boundaries are declared host models; HTTPS, original
files and existing production source/checkpoint/publisher owners are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.avatar_primary_control import prepare
from feature_journeys.contract import VERSION
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_primary_control import checkpoint_order
from ios.adapters import avatar_operation_clock
from ios.self_tests.avatar_strong_domain import StrongDomain,RUN
from ios.self_tests import test_ios_avatar_prepare_composed as preparation
from ios.self_tests.test_ios_avatar_held_terminal import original_role_api_calls


class ScopedPrimaryDomain(StrongDomain):
    def __init__(self,test):
        super().__init__(test)
        old=self.owners['primary'];self.control_root=self.scenes['primary'].root
        self.control_store=PrivateFeatureState(self.control_root/('avatar-primary-control-'+RUN+'.json'))
        prepare(self.client,self.control_store,RUN)
        config=dict(artifactRoot=str(old.root),imagePolicy=deepcopy(old.policy),actorTarget='actor',authorityControlRoot=str(self.control_root))
        # Before the first Feature state, native capture, login or input.
        self.owners['primary']=IOSAvatarFeature(self.runtime,'primary',self.primary_client,RUN,'primary',config,
            epoch_ms=self.host,monotonic=lambda:self.clock[0],sleep=self.sleep)


class AvatarPrimaryControlOwnerTests(unittest.TestCase):
    retain_originals=True
    domain_type=ScopedPrimaryDomain
    domain=preparation.AvatarPrepareComposedTests.domain
    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()

    def test_actual_session_POST_lost_local_return_reopens_issued_owner_without_second_POST_or_login(self):
        d=self.domain();p,a=d.owners['primary'],d.owners['actor']
        with a.held():a.initialize();a.login()
        request=p.primary_control.request;lost=[]
        def send(path,*args,**kwargs):
            result=request(path,*args,**kwargs)
            if path.endswith('/avatar/sessions'):
                lost.append(path);raise OSError('Lost actual scoped session-binding return')
            return result
        p.primary_control.request=send
        with self.assertRaisesRegex(OSError,'Lost actual scoped'):p.prepare()
        before={role:list(n.input_log) for role,n in d.natives.items()}
        with p.held(paired=True):
            p.load();issued=deepcopy(p.state['sessions']);self.assertEqual('issued',issued['phase'])
            self.assertEqual('ready',d.server.avatar_accounts.snapshot(RUN)['phase'])
            p.sessions(p.source_parts());self.assertEqual('bound',p.state['sessions']['phase'])
            self.assertEqual(issued['input'],p.state['sessions']['input'])
            self.assertEqual(issued['sources'],p.state['sessions']['sources'])
            self.assertEqual(issued['peers'],p.state['sessions']['peers'])
        self.assertEqual(1,len(lost));self.assertEqual(before,{role:list(n.input_log) for role,n in d.natives.items()})
        self.assertEqual(['bind-sessions'],p.primary_control.admit()['usedPurposes'])
        self.assertEqual([],d.primary_client.request('/runs/'+RUN)['entries'])
        for role in ('primary','actor'):self.assertEqual(1,d.natives[role].input_log.count('login.submit'))

    def test_missing_explicit_control_profile_refuses_GET_only_primary_before_state_or_native_input(self):
        d=self.domain();p=d.owners['primary'];before={role:list(n.input_log) for role,n in d.natives.items()}
        path=p.store.path;self.assertFalse(path.exists())
        with self.assertRaises(NativeUIError):IOSAvatarFeature(d.runtime,'primary',d.primary_client,RUN,'primary',
            dict(artifactRoot=str(p.root),imagePolicy=deepcopy(p.policy),actorTarget='actor'),
            epoch_ms=d.host,monotonic=lambda:d.clock[0],sleep=d.sleep)
        self.assertFalse(path.exists());self.assertEqual(before,{role:list(n.input_log) for role,n in d.natives.items()})

    def test_published_actual_Actor_checkpoint_orders_GET_only_primary_without_exposing_journal_facts(self):
        d=self.domain();p,a=d.owners['primary'],d.owners['actor']
        with a.held():a.initialize();a.login()
        sleep=p.sleep;scheduled=[]
        def advance(seconds):
            if not scheduled and p.state is not None and p.state['initial'] is not None:scheduled.append(True);a.prepare()
            sleep(seconds)
        p.sleep=advance;p.prepare();call=dict(contractVersion=VERSION,runId=RUN)
        for owner in (p,a):owner.observe(dict(call,afterSequence=0))
        ticket='9'*32;d.client.activate(ticket,'cleanup',{})
        with original_role_api_calls((p,a)) as invoke:
            for owner in (p,a):
                owner.requested_cleanup_clock=avatar_operation_clock.begin(d.host(),d.clock[0])
                self.assertTrue(invoke(owner,'restore_inputs',call,deepcopy(owner.requested_cleanup_clock)))
            invoke(p,'cleanup_checkpoint')
            with self.assertRaises(AvatarFeaturePending):checkpoint_order(p)
            invoke(a,'cleanup_checkpoint')
            before={role:list(n.input_log) for role,n in d.natives.items()}
            # The existing public adapter still deliberately cannot see facts.
            self.assertEqual([],d.primary_client.request('/runs/'+RUN)['entries'])
            receipt=invoke(p,'wait_actor_checkpoint')
            self.assertEqual((RUN,'actor',ticket),(receipt['runId'],receipt['role'],receipt['ticket']))
            self.assertEqual('cleanup-checkpoint-order',receipt['purpose']);self.assertGreater(receipt['sequence'],0)
            self.assertEqual(before,{role:list(n.input_log) for role,n in d.natives.items()})
            # Real original publication body tampering is not an ordering receipt.
            with a.held():
                a.load();event=next(row for row in a.state['cleanup'] if row['kind']=='checkpoint')
                raw=a.kept(event['publisher'])
                from adapters.script_feature.history import unpack
                ref=unpack(raw['payload'])[0]['records'][-1]
                store=PrivateFeatureState(a.store.path.with_name('phase-publication-avatar-people-'+RUN+'-actor-'+str(ref['ordinal'])+'.json'))
                old=store.read();changed=deepcopy(old);changed['runId']='f'*32;store.write(changed,old)
            with self.assertRaises(NativeUIError):invoke(p,'wait_actor_checkpoint')
            self.assertEqual(before,{role:list(n.input_log) for role,n in d.natives.items()})


if __name__=='__main__':unittest.main()
