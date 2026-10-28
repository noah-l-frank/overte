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
    domain_type=PrepareDomain
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
        with patch.object(installed.InstalledCodeTests,'setUp',retained):return self.domain_type(self)

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



    def recovered_public_preparation(self):
        from contextlib import ExitStack
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.normal_ui import NativeUIError
        from adapters.script_feature.history import unpack
        from ios.adapters.avatar_feature import IOSAvatarFeature

        d=self.domain();primary,actor=d.owners['primary'],d.owners['actor']
        # Keep the existing normal-case worker order: the Actor establishes
        # only its own original account before Primary session admission.
        with actor.held():actor.initialize();actor.login()
        lost=[];kept={}
        with ExitStack() as callbacks:
            for role,native in d.natives.items():
                call=native.call
                def request(method,path,body=None,role=role,native=native,call=call):
                    result=call(method,path,body)
                    if method=='POST' and path.endswith('/click') and native.input_log[-1:]==['OverteTabletClose'] and role not in lost:
                        lost.append(role)
                        raise OSError('Declared lost return AFTER actual owned UIKit Close')
                    return result
                callbacks.enter_context(patch.object(native,'call',side_effect=request))

            # BOTH failures enter via public prepare(), after the real close
            # effect, before session/initial/marker setup. No close helper is
            # invoked directly by this vertical case.
            for role in ('primary','actor'):
                owner=d.owners[role];native=d.natives[role]
                with self.assertRaises(NativeUIError):owner.prepare()
                self.assertFalse(native.shown);self.assertTrue(native.account['loggedIn'])
                self.assertEqual(1,native.input_log.count('login.submit'))
                self.assertEqual(1,native.input_log.count('OverteTabletClose'))
                with owner.held():
                    owner.load();event=deepcopy(owner.state['preparationClose'])
                    self.assertEqual('preparing',owner.state['phase']);self.assertEqual('issued',event['phase'])
                    self.assertIsNone(event['after']);self.assertIsNone(owner.state['initial'])
                    self.assertIsNone(owner.state['initialBarrier']);self.assertIsNone(owner.state['sessions'])
                    self.assertEqual(1,owner.state['protected'])
                    issued=deepcopy(owner.preparation_issued_original());before=deepcopy(owner.preparation_source(event['before']))
                    self.assertTrue(before['ui']['open']);self.assertFalse(d.scenes[role].domain.running)
                    self.assertEqual([],d.scenes[role].scope.frames)
                    ledger=owner.snapshot_ledger();wires=ledger.entries();pins={}
                    for field in ('before','issuedIntent'):
                        reference=event[field];path=ledger.originals.path(wires[reference['index']-1])
                        pins[field]=(path,self.issued_original_pin(path))
                    login_path=owner.store.path.with_name('ios-avatar-'+role+'-login.json')
                    login=unpack(PrivateFeatureState(login_path).read()['payload'])[0]
                    self.assertEqual('logged-in',login['phase']);self.assertEqual(1,len(login['actions']))
                    self.assertTrue(login['actions'][0]['complete']);self.assertEqual('login-submit',login['actions'][0]['verb'])
                    self.assertEqual(1,len(login['protected']));self.assertEqual('complete',login['protected'][0]['phase'])
                    self.assertIsNotNone(login['protected'][0]['probe']);self.assertIsNotNone(login['protected'][0]['released'])
                    self.assertIsNotNone(login['protected'][0]['originAbsent'])
                    kept[role]=dict(event=event,issued=issued,before=before,pins=pins,
                        loginPath=login_path,loginPin=self.issued_original_pin(login_path),inputs=list(native.input_log))
            self.assertEqual(['primary','actor'],lost)

            # This is the original normal-case scheduler: first Primary's
            # untouched frame, then the Actor's complete public preparation.
            # The two public retries must reopen the issued effects and must
            # not replay either login or Close.
            sleep=primary.sleep;started=[]
            def schedule(seconds):
                if not started and primary.state is not None and primary.state['initial'] is not None:
                    started.append(True);actor.prepare()
                sleep(seconds)
            primary.sleep=schedule
            try:primary.prepare()
            finally:primary.sleep=sleep
            self.assertEqual([True],started);self.assertEqual(['primary','actor'],lost)

            initial={};peer_initial={};marker_before={}
            for role,owner in d.owners.items():
                native=d.natives[role];saved=kept[role]
                with owner.held(paired=True):
                    owner.load();self.assertEqual('ready',owner.state['phase']);self.assertEqual('bound',owner.state['sessions']['phase'])
                    self.assertEqual(1,owner.state['protected'])
                    event=owner.state['preparationClose'];self.assertEqual('observed',event['phase'])
                    self.assertEqual(saved['event']['before'],event['before'])
                    self.assertEqual(saved['event']['issuedIntent'],event['issuedIntent'])
                    self.assertTrue(saved['issued']==owner.preparation_issued_original(),'Original issued intent changed')
                    self.assertTrue(saved['before']==owner.preparation_source(event['before']),'Original BEFORE source changed')
                    for path,original in saved['pins'].values():
                        self.assertTrue(original==self.issued_original_pin(path),'Original close carrier bytes or identity changed')
                    self.assertTrue(saved['loginPin']==self.issued_original_pin(saved['loginPath']),'Original account/protected proof changed')
                    closed=owner.preparation_closed_original();self.assertFalse(closed['ui']['open'])
                    initial[role]=owner.initial_original()
                    self.assertLessEqual(closed['clockJoin']['nativeAfter']['capturedEpochMs'],initial[role]['clockJoin']['nativeBefore']['capturedEpochMs'])
                    scene=d.scenes[role];self.assertIsNotNone(scene.scope.state['baseline']);self.assertIsNotNone(scene.scope.state['webAdmission'])
                    marker_before[role]=scene.scope.frames[0]['clockJoin']['hostBeforeMonotonic']
                    self.assertEqual(1,len(scene.domain.vm['added']));self.assertEqual('local',scene.domain.vm['added'][0]['host'])
                    barrier=owner.state['initialBarrier'];other='actor' if role=='primary' else 'primary'
                    self.assertEqual(other,barrier['subject']);self.assertEqual(d.owners[other].state['initial']['reference'],barrier['reference'])
                    peer=IOSAvatarFeature.archive(owner.runtime,owner.kept(barrier['owner']),owner.client,owner.locks)
                    peer_initial[role]=peer.initial_original()
                    self.assertEqual(barrier['reference'],peer.state['initial']['reference'])
                self.assertEqual(saved['inputs'],native.input_log)
                self.assertEqual(1,native.input_log.count('login.submit'));self.assertEqual(1,native.input_log.count('OverteTabletClose'))
                self.assertTrue(native.account['loggedIn'])
            for role,frame in peer_initial.items():
                self.assertTrue(frame==initial['actor' if role=='primary' else 'primary'],'Actual retained peer initial handoff changed')
            # Both untouched originals, across both roles, precede EITHER
            # normal marker preparation baseline/camera change.
            for frame in initial.values():
                for before in marker_before.values():self.assertLessEqual(frame['clockJoin']['hostAfterMonotonic'],before)
            authority=d.server.avatar_accounts.snapshot(RUN)
            self.assertEqual('ready',authority['phase']);self.assertEqual(2,sum(row['accountExists'] for row in authority['accounts'].values()))
            for owner in d.owners.values():self.assertEqual(owner.state['sessions']['input'],{key:authority['sessionBinding'][key] for key in ('sessions','domain')})
            # This helper establishes only preparation/marker admission.
            # The caller must independently acquire any later active facts.
            return d,kept

    def test_both_public_prepare_retries_after_lost_actual_uikit_close_reach_paired_initial_and_marker_admission_once(self):
        self.recovered_public_preparation()


if __name__=='__main__':unittest.main()
