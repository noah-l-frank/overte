"""Real Login owner histories retain actual host weak operands until expiry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_login_lifetime import AvatarLoginLifetime
from ios.self_tests import test_ios_avatar_login_owner as login
from ios.self_tests.avatar_login_roots_fixture import LoginRoots


class AvatarLoginLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):login.AvatarLoginOwnerTests.setUpClass()
    @classmethod
    def tearDownClass(cls):login.AvatarLoginOwnerTests.tearDownClass()
    def setUp(self):
        self.f=login.AvatarLoginOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.roots=LoginRoots(self.f.native);self.owner=self.f.owner();self.owner.prepare()
    def history(self,original=None):
        return AvatarLoginLifetime(self.owner.previous if original is None else original,binding=self.owner.state['binding'],
            run=self.f.run,child_run=self.f.runtime.run,role='primary',authority=self.f.authority)
    def at(self,history,value=None):
        value=self.f.native.observed() if value is None else value
        return history._at_widgets(value,original_sha256=digest(value))
    def test_original_completed_login_hidden_operand_is_held_until_actual_weak_expiry(self):
        self.owner.login('1'*32);self.f.native.sleep(1.1)
        inputs=list(self.f.native.input_log);history=self.history()
        held=self.at(history);self.assertEqual(1,len(held['heldResources']));self.assertTrue(held['endpoints'][0]['original']['weakAlive'])
        self.assertNotIn('login.submit',[row['id'] for row in self.f.native.observed()['controls']])
        self.roots.release();ended=self.at(history);self.assertEqual([],ended['heldResources'])
        self.assertFalse(ended['endpoints'][0]['original']['weakAlive']);self.assertEqual(inputs,self.f.native.input_log)
    def test_restored_original_history_uses_prior_admission_and_never_logout_ack_as_death(self):
        self.owner.login('1'*32);self.f.client.activate('2'*32);self.owner.logout('2'*32)
        self.f.client.activate('3'*32);self.owner.restore_preferences('3'*32)
        held=self.at(self.history());self.assertEqual(1,len(held['heldResources']))
        self.assertEqual('restored',self.owner.state['phase']);self.assertTrue(held['endpoints'][0]['original']['weakAlive'])
    def test_unknown_new_operand_incomplete_or_changed_identity_cannot_be_discarded(self):
        self.owner.login('1'*32);history=self.history();value=self.f.native.observed()
        for fault in ('new','incomplete','rebirth','truncated','missing'):
            changed=deepcopy(value);component=changed['loginRootOwnership'];source=component['ownership']
            if fault=='new':
                row=deepcopy(source['roots'][0]);row.update(observedIdentity='f'*32,firstObservedSequence=2)
                source['roots'].append(row);source['observationSequence']=2
            elif fault=='incomplete':component.update(complete=False,controls=[])
            elif fault=='rebirth':source['instance']='e'*32
            elif fault=='truncated':source.update(roots=[],observationSequence=0)
            else:del changed['loginRootOwnership']
            with self.subTest(fault=fault),self.assertRaises((KeyError,NativeUIError)):self.at(history,changed)
    def test_existing_unowned_baseline_root_and_foreign_login_envelope_fail_before_any_query(self):
        original=deepcopy(self.owner.previous);state=self.owner.decode(original)
        initial=state['preferences']['receipt']['observation'];self.roots.add(initial['sampleEpochMs'])
        initial['loginRootOwnership']=self.roots.capture(initial);bad=self.owner.envelope(state)
        before=list(self.f.native.commands)
        with self.assertRaises(NativeUIError):self.history(bad)
        foreign=deepcopy(original);foreign['childRunId']='f'*32
        with self.assertRaises(NativeUIError):self.history(foreign)
        self.assertEqual(before,self.f.native.commands)


if __name__=='__main__':unittest.main()
