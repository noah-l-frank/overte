"""Whole preparation through real HTTPS, owned originals and Node marker code.

This qualifies preparation; it does not qualify the entire Avatar journey or
native execution. Qt/OS/renderer producers are explicitly modeled boundaries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from ios.self_tests import test_ios_installed_code as installed
from ios.self_tests.retained_host_roots import retain_owned_root
from ios.self_tests.avatar_prepare_fixture import PrepareDomain,RUN,TICKET
from self_tests import test_account_provider as tls


class AvatarPrepareComposedTests(unittest.TestCase):
    retain_originals=True
    @classmethod
    def setUpClass(cls):
        tls.AccountProviderTests.setUpClass()
        retain_owned_root(tls.AccountProviderTests.temporary,expected_root=tls.AccountProviderTests.path)
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def domain(self):
        setup=installed.InstalledCodeTests.setUp
        def retained(case):
            setup(case);retain_owned_root(case.temp,expected_root=Path(case.temp.name))
        with patch.object(installed.InstalledCodeTests,'setUp',retained):return PrepareDomain(self)

    def test_actual_both_owned_accounts_then_both_untouched_frames_and_normal_scripts(self):
        d=self.domain();primary,actor=d.owners['primary'],d.owners['actor']
        # The independent worker first signs in through its own normal login.
        with actor.held():actor.initialize();actor.login()
        original_sleep=primary.sleep;started=[]
        def schedule(seconds):
            if not started and primary.state is not None and primary.state['initial'] is not None:started.append(True);actor.prepare()
            original_sleep(seconds)
        primary.sleep=schedule
        primary.prepare()
        for role,owner in d.owners.items():
            with owner.held(paired=True):
                owner.load();self.assertEqual('ready',owner.state['phase']);self.assertEqual('bound',owner.state['sessions']['phase'])
                frame=owner.initial_original();self.assertLessEqual(frame['clockJoin']['hostAfterMonotonic'],d.scenes[role].scope.frames[0]['clockJoin']['hostBeforeMonotonic'])
                self.assertIsNotNone(owner.state['initialBarrier']);self.assertEqual('observed',owner.state['preparationClose']['phase'])
                self.assertFalse(owner.preparation_closed_original()['ui']['open'])
                self.assertTrue(d.natives[role].account['loggedIn']);self.assertEqual(1,d.natives[role].input_log.count('login.submit'))
                self.assertEqual(1,len(d.scenes[role].domain.vm['added']));self.assertEqual('local',d.scenes[role].domain.vm['added'][0]['host'])
        self.assertEqual('ready',d.server.avatar_accounts.snapshot(RUN)['phase'])
        self.assertEqual(2,sum(row['accountExists'] for row in d.server.avatar_accounts.snapshot(RUN)['accounts'].values()))
    def test_lost_actual_uikit_close_return_reopens_real_closed_original_without_replaying_login_or_close(self):
        from adapters.normal_ui import NativeUIError
        d=self.domain();owner=d.owners['primary'];native=d.natives['primary'];call=native.call;lost=[]
        def request(method,path,body=None):
            result=call(method,path,body)
            if method=='POST' and path.endswith('/click') and native.input_log[-1:] == ['OverteTabletClose'] and not lost:
                lost.append(True);raise OSError('Lost actual completed UIKit close return')
            return result
        native.call=request
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertFalse(native.shown);before=list(native.input_log)
        with owner.held():
            owner.load();pending=deepcopy(owner.state['preparationClose']);self.assertEqual('issued',pending['phase'])
            intent_ref=deepcopy(pending['issuedIntent']);intent=deepcopy(owner.preparation_issued_original())
            self.assertEqual(dict(phase='issued',before=pending['before'],after=None),intent['intent'])
            intent_wire=owner.snapshot_ledger().entries()[intent_ref['index']-1]
            intent_path=owner.snapshot_ledger().originals.path(intent_wire);intent_stat=intent_path.lstat();intent_bytes=intent_path.read_bytes()
            # Reconstruct source/history from its actual persisted originals;
            # this resumes only the passive close effect, never all prepare.
            owner.close_preparation_tablet();closed=owner.preparation_closed_original()
            actual=owner.state['preparationClose'];self.assertEqual('observed',actual['phase'])
            self.assertEqual(pending['before'],actual['before']);self.assertNotEqual(actual['before'],actual['after'])
            self.assertEqual(intent_ref,actual['issuedIntent']);self.assertEqual(intent,owner.preparation_issued_original())
            after_stat=intent_path.lstat();self.assertEqual(intent_bytes,intent_path.read_bytes())
            for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'):
                self.assertEqual(getattr(intent_stat,key),getattr(after_stat,key))
            self.assertFalse(closed['ui']['open']);self.assertTrue(closed['originals']['native']['account']['loggedIn'])
            for fault in ('rebase-before','foreign-intent-hash'):
                changed={'before':actual['after']} if fault=='rebase-before' else {'issuedIntent':dict(intent_ref,sha256='0'*64)}
                with self.subTest(fault=fault),patch.dict(actual,changed),self.assertRaises(NativeUIError):owner.preparation_closed_original()
            saved=deepcopy(actual);owner.load();owner.close_preparation_tablet();self.assertEqual(saved,owner.state['preparationClose'])
        self.assertEqual(before,native.input_log);self.assertEqual(1,before.count('login.submit'));self.assertEqual(1,before.count('OverteTabletClose'))

    def test_original_unowned_open_tablet_prevents_login_and_cannot_be_claimed_as_our_close(self):
        from adapters.normal_ui import NativeUIError
        d=self.domain();owner=d.owners['primary'];native=d.natives['primary'];native.shown=True
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([],native.input_log)
        with owner.held():owner.load();self.assertIsNone(owner.state['preparationClose']);self.assertEqual('preparing',owner.state['phase'])


    def lost_close(self):
        from adapters.normal_ui import NativeUIError
        d=self.domain();owner=d.owners['primary'];native=d.natives['primary'];call=native.call;lost=[]
        def request(method,path,body=None):
            result=call(method,path,body)
            if method=='POST' and path.endswith('/click') and native.input_log[-1:] == ['OverteTabletClose'] and not lost:
                lost.append(True);raise OSError('Lost actual completed UIKit close return')
            return result
        native.call=request
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([True],lost);self.assertFalse(native.shown)
        with owner.held():owner.load();self.assertEqual('issued',owner.state['preparationClose']['phase'])
        return d,owner,native

    def test_unconfirmed_close_with_a_current_open_original_stays_issued_without_another_click(self):
        d,owner,native=self.lost_close();inputs=list(native.input_log)
        # The declared native producer reopens its actual Qt tablet. A fresh
        # source read must observe that open state rather than reuse old pixels.
        native.shown=True;interrupted=RuntimeError('Interrupt after one actual open-state retry')
        with patch.object(owner,'sleep',side_effect=interrupted):
            with owner.held():
                owner.load();pending=deepcopy(owner.state['preparationClose'])
                with self.assertRaises(RuntimeError) as raised:owner.close_preparation_tablet()
                self.assertIs(interrupted,raised.exception);self.assertEqual(pending,owner.state['preparationClose'])
                source=owner.own_source();self.assertTrue(source.frames[-1]['ui']['open'])
        self.assertEqual(inputs,native.input_log);self.assertEqual(1,inputs.count('OverteTabletClose'))

    def test_changed_actual_process_refuses_lost_close_recovery_without_login_or_click_replay(self):
        d,owner,native=self.lost_close();inputs=list(native.input_log);native.pid+=1
        # The composed installed-code boundary has its own OS producer. Change
        # that actual producer too; changing only Native.pid does not replace
        # the independently admitted process in this fixture.
        installed=d.installed['primary'];installed.process['pid']=native.pid
        self.assertEqual(native.pid,installed.process['pid'])
        self.assertEqual(31,installed.store.read()['process']['pid'])
        with owner.held():
            owner.load();pending=deepcopy(owner.state['preparationClose'])
            with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_REJECTED'):owner.close_preparation_tablet()
            self.assertEqual(pending,owner.state['preparationClose']);self.assertEqual('issued',pending['phase'])
        self.assertEqual(inputs,native.input_log)



    def issued_original_pin(self,path):
        first=path.lstat();raw=path.read_bytes();last=path.lstat()
        fields=('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        self.assertEqual(tuple(getattr(first,key) for key in fields),tuple(getattr(last,key) for key in fields))
        return tuple(getattr(last,key) for key in fields)+(raw,)

    def lose_successfully_retained_issued_intent(self):
        d=self.domain();owner=d.owners['primary'];native=d.natives['primary'];keep=owner.keep;retained=[]
        failure=RuntimeError('Declared local return lost AFTER successful original issued-intent retain, BEFORE UIKit Close')
        def losing(value):
            reference=keep(value)
            if value.get('kind')=='avatar-preparation-close-issued' and not retained:
                self.assertEqual('issued',owner.state['preparationClose']['phase'])
                self.assertNotIn('issuedIntent',owner.state['preparationClose'])
                self.assertEqual(owner.previous,owner.store.read())
                ledger=owner.snapshot_ledger();entry=deepcopy(ledger.entries()[reference['index']-1])
                self.assertEqual('saved',entry['phase']);self.assertEqual(value,ledger.read(reference))
                path=ledger.originals.path(entry)
                retained.append(dict(reference=deepcopy(reference),value=deepcopy(value),entries=deepcopy(ledger.entries()),
                    path=path,pin=self.issued_original_pin(path)))
                raise failure
            return reference
        with patch.object(owner,'keep',side_effect=losing),self.assertRaises(RuntimeError) as raised:
            owner.prepare()
        self.assertIs(failure,raised.exception);self.assertEqual(1,len(retained))
        self.assertTrue(native.shown);self.assertEqual(1,native.input_log.count('login.submit'))
        self.assertEqual(0,native.input_log.count('OverteTabletClose'))
        return d,owner,native,retained[0]

    def test_saved_issued_intent_lost_local_return_deduplicates_but_open_effect_stays_uncertain_without_close_replay(self):
        d,owner,native,retained=self.lose_successfully_retained_issued_intent();inputs=list(native.input_log)
        with owner.held():
            owner.load();self.assertNotIn('issuedIntent',owner.state['preparationClose'])
            self.assertEqual(retained['entries'],owner.snapshot_ledger().entries())
            before=deepcopy(owner.state['preparationClose']['before'])
            owner.retain_preparation_issued()
            self.assertEqual(retained['reference'],owner.state['preparationClose']['issuedIntent'])
            self.assertEqual(retained['entries'],owner.snapshot_ledger().entries())
            self.assertEqual(retained['value'],owner.preparation_issued_original())
            self.assertEqual(retained['pin'],self.issued_original_pin(retained['path']))
            pending=deepcopy(owner.state['preparationClose']);interrupted=RuntimeError('Stop only after a real current open-state source read')
            with patch.object(owner,'sleep',side_effect=interrupted),self.assertRaises(RuntimeError) as raised:
                owner.close_preparation_tablet()
            self.assertIs(interrupted,raised.exception);self.assertEqual(pending,owner.state['preparationClose'])
            self.assertEqual(before,owner.state['preparationClose']['before'])
            self.assertEqual('issued',pending['phase']);self.assertIsNone(pending['after'])
            self.assertTrue(owner.own_source().frames[-1]['ui']['open'])
            self.assertEqual(retained['entries'],owner.snapshot_ledger().entries())
            self.assertEqual(retained['pin'],self.issued_original_pin(retained['path']))
            owner.load();self.assertEqual(pending,owner.state['preparationClose'])
        self.assertEqual(inputs,native.input_log);self.assertEqual(0,native.input_log.count('OverteTabletClose'))

    def test_archived_issued_original_reopens_real_files_with_live_sdk_source_and_product_clocks_forbidden(self):
        from contextlib import ExitStack
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.normal_ui import NativeUI,NativeUIError
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from feature_journeys.witness import Client
        from ios.adapters.avatar_authority import AvatarAuthorityReader
        from ios.adapters.avatar_feature import IOSAvatarFeature
        from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
        from ios.adapters.avatar_sources import IOSAvatarSources

        d,owner,native,retained=self.lose_successfully_retained_issued_intent()
        with owner.held():
            owner.load();owner.retain_preparation_issued();saved=deepcopy(owner.previous)
            expected=deepcopy(owner.preparation_issued_original());inputs=list(native.input_log)
            def census():
                return {str(path.relative_to(owner.root)):self.issued_original_pin(path)
                    for path in owner.root.rglob('*') if path.is_file()}
            files=census()
            def forbidden(*_args,**_kwargs):raise AssertionError('Archived issued intent must not acquire, input, write or consult a product clock')
            with ExitStack() as guards:
                for target,names in ((owner,('actual','own_source','epoch_ms','monotonic','sleep')),
                        (owner.runtime,('_sources','_avatar_sources','_avatar_login','existing_input_session')),
                        (owner.runtime.adapter,('_candidate_guard',)),
                        (d,('host','sleep')),
                        (IOSAvatarFeature,('clock',)),(IOSAvatarSources,('read',)),
                        (IOSAvatarSourceRecovery,('recover',)),(NativeUI,('click',)),
                        (PhaseFixtureReader,('read','status')),(AvatarAuthorityReader,('read',)),
                        (Client,('request',)),(PrivateFeatureState,('write','discard'))):
                    for name in names:guards.enter_context(patch.object(target,name,side_effect=forbidden))
                for boundary in d.natives.values():
                    for name in ('epoch','host_epoch','sleep','call','execute','post','poll'):
                        guards.enter_context(patch.object(boundary,name,side_effect=forbidden))
                # Actual archive/load and original decoder stay untouched.
                # state_path is the existing pure local path router; original
                # file-store host monotonic budgets and file guards stay real.
                archived=IOSAvatarFeature.archive(owner.runtime,saved,owner.client,owner.locks)
                self.assertEqual(expected,archived.preparation_issued_original())
                archived.load();self.assertEqual(expected,archived.preparation_issued_original())
                event=archived.state['preparationClose'];reference=event['issuedIntent']
                for changed in (dict(reference,index=True),dict(reference,index=0),dict(reference,sha256='0'*64)):
                    with self.subTest(reference=changed),patch.dict(event,issuedIntent=changed),self.assertRaises(NativeUIError):
                        archived.preparation_issued_original()
                self.assertEqual(files,census());self.assertEqual(saved,owner.store.read())
            self.assertEqual(retained['pin'],self.issued_original_pin(retained['path']))
        self.assertEqual(inputs,native.input_log)



if __name__=='__main__':unittest.main()
