"""Real background ownership with synthetic OS/SDK/native boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION as CONTRACT_VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_emote_background import PhoneEmoteBackground
from test_emote_effects import EffectsModel
from test_emote_sources import RUN
from overte_phone_script_history import pack,unpack


class Model(EffectsModel):
    def __init__(self,root):
        super().__init__(root);self.foreground=True;self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.normal_inputs=[];self.ignore='';self.lose='';self.native_changed=True;self.os_unavailable=False
        self.foreign=False;self.background_native_accesses=0;self.source_lost=False

    def normal_feature_runtime(self,*args,**kwargs):
        if not self.foreground:
            self.background_native_accesses+=1
            raise NativeUIError('Synthetic foreground-only source unavailable')
        ui,service,binding,guard,installed=super().normal_feature_runtime(*args,**kwargs)
        return ui,service,binding,lambda:guard() and self.foreground,installed

    def native_send(self,request):
        if not self.foreground:
            self.background_native_accesses+=1
            raise NativeUIError('Synthetic native getter unavailable in background')
        super().native_send(request);self.value['lifecycle']=deepcopy(self.lifecycle)
        if self.source_lost:raise NativeUIError('Synthetic lost original read result')

    def _emote_lifecycle_status(self,_selector,binding):
        if self.os_unavailable:raise NativeUIError('Synthetic original OS unavailable')
        observed=deepcopy(self.binding)
        if self.foreign:observed['processIdentity']='32:19'
        return dict(binding=observed,foreground=self.foreground,running=True,appState=4 if self.foreground else 3)

    def invoke(self,_selector,operation,values):
        assert values=={} and operation in ('lifecycle.background','app.launch');self.normal_inputs.append(operation)
        if operation!=self.ignore:
            if operation=='lifecycle.background':
                self.foreground=False
                if self.native_changed:self.lifecycle['backgrounds']+=1
            else:
                self.foreground=True
                if self.native_changed:self.lifecycle['activations']+=1
        if self.lose==operation:raise NativeUIError('Synthetic lost ordinary input return')
        return {'performed':True}

    def owner(self,*,segment=0):
        phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)
        return PhoneEmoteBackground(self,'synthetic-selector',phase,self.lock,artifact_root=self.root,
            monotonic=lambda:self.clock,sleep=self.sleep,segment=segment)


class PhoneEmoteBackgroundTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-background-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))

    def cleanup_call(self,model=None,*,ticket='e'*32):
        m=self.model if model is None else model
        m.journal.activate(RUN,ticket,'cleanup',{})
        return dict(contractVersion=CONTRACT_VERSION,runId=RUN)

    def interrupt(self,model=None,*,segment=0):
        m=self.model if model is None else model;m.lose='lifecycle.background'
        owner=m.owner(segment=segment);call=m.call('background-resume')
        with self.assertRaises(NativeUIError):owner.act(call)
        m.lose='';return owner,call

    def target_reads(self):
        return [kind for kind in self.model.calls if kind!='phase-read']

    def test_later_namespace_background_uses_only_its_original_source_and_input_journals(self):
        m=self.model
        with m.lock.held():
            first=m.source();first.read();frozen=deepcopy(first.previous)
            m.source(segment=1).read();owner=m.owner(segment=1);call=m.call('background-resume');owner.act(call)
            self.assertEqual(1,owner.previous['sourceSegment'])
            self.assertEqual('phone-emote-primary-sources-segment-1.json',owner.sources.path.name)
            self.assertEqual(frozen,first.store.read())
            with self.assertRaises(NativeUIError):m.owner()
            retained=[];current=m.owner(segment=1);current.retire(retain=lambda header:retained.append(header))
            self.assertEqual(1,retained[0]['sourceSegment']);self.assertIsNone(current.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_cleanup_phase_returns_to_foreground_and_retains_old_failure_without_native_getters(self):
        m=self.model;retained=[]
        with m.lock.held():
            original,old=self.interrupt();call=self.cleanup_call();before=self.target_reads()
            current=m.owner();result=current.recover_foreground(call)
            self.assertEqual(1,result['emoteForegroundRecoveryVersion']);self.assertTrue(m.foreground)
            self.assertEqual(before,self.target_reads());self.assertEqual('background-issued',current.state['phase'])
            self.assertEqual(old,current.state['call']);self.assertIsNone(current.state['afterHeader'])
            self.assertEqual('observed',current.state['cleanup']['phase'])
            with self.assertRaises(NativeUIError):current.act(old)
            with self.assertRaises(NativeUIError):current.retire()
            packet=current.retire_recovery(lambda proof:retained.append(deepcopy(proof)))
            self.assertEqual([packet],retained);self.assertIsNone(current.store.read());self.assertIsNotNone(current.sources.read())
            self.assertEqual(packet,m.owner().recovery_archive(packet));self.assertEqual(before,self.target_reads())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_lost_cleanup_launch_return_observes_real_foreground_without_a_second_launch(self):
        m=self.model
        with m.lock.held():
            self.interrupt();call=self.cleanup_call();m.lose='app.launch';current=m.owner()
            with self.assertRaises(NativeUIError):current.recover_foreground(call)
            self.assertTrue(m.foreground);self.assertEqual('foreground-issued',current.state['cleanup']['phase'])
            m.lose='';current=m.owner();current.recover_foreground(call);current.retire_recovery(lambda *_:None)
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_ignored_cleanup_launch_is_not_repeated_and_keeps_lease_unresolved(self):
        m=self.model
        with m.lock.held():
            self.interrupt();call=self.cleanup_call();m.ignore='app.launch';current=m.owner()
            with self.assertRaises(NativeUIError):current.recover_foreground(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.recover_foreground(call)
            with self.assertRaises(NativeUIError):current.retire_recovery(lambda *_:None)
            self.assertIsNotNone(current.store.read());self.assertFalse(m.foreground)
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_cleanup_already_in_foreground_adds_no_launch_and_does_not_complete_ignored_home(self):
        m=self.model;m.ignore='lifecycle.background'
        with m.lock.held():
            current=m.owner();old=m.call('background-resume')
            with self.assertRaises(NativeUIError):current.act(old)
            call=self.cleanup_call();current=m.owner();current.recover_foreground(call)
            self.assertEqual('background-issued',current.state['phase']);self.assertIsNone(current.state['background'])
            self.assertIsNone(current.state['afterHeader']);current.retire_recovery(lambda *_:None)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_cleanup_after_pending_original_read_transfers_only_its_lease_and_keeps_source_failure(self):
        m=self.model;invoke=m.invoke
        def lose(*args):
            value=invoke(*args)
            if args[1]=='app.launch':m.source_lost=True
            return value
        m.invoke=lose
        with m.lock.held():
            current=m.owner();old=m.call('background-resume')
            with self.assertRaises(NativeUIError):current.act(old)
            self.assertEqual('observing',current.state['phase']);call=self.cleanup_call();current=m.owner();before=self.target_reads()
            current.recover_foreground(call);packet=current.retire_recovery(lambda *_:None)
            self.assertEqual('reading',unpack(packet['sourceHeader']['payload'])[0]['phase'])
            self.assertIsNotNone(current.sources.read());self.assertEqual(before,self.target_reads())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_noncleanup_phase_foreign_run_or_new_fixture_birth_cannot_authorize_cleanup_launch(self):
        for fault in ('old-phase','other-phase','foreign-run','new-birth','retired'):
            root=self.model.root/fault;root.mkdir(mode=0o700);m=Model(root)
            with self.subTest(fault=fault),m.lock.held():
                self.interrupt(m);call=dict(contractVersion=CONTRACT_VERSION,runId=RUN)
                if fault!='old-phase':call=self.cleanup_call(m)
                if fault=='other-phase':m.call('close')
                elif fault=='foreign-run':call['runId']='f'*32
                elif fault=='new-birth':m.journal.phase_instance='9'*32
                elif fault=='retired':m.journal.close(RUN)
                current=m.owner()
                with self.assertRaises((NativeUIError,ValueError)):current.recover_foreground(call)
                self.assertFalse(m.foreground);self.assertIsNotNone(current.store.read())
            self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_lost_cleanup_intent_commit_return_never_dispatches_or_replays_uncertain_launch(self):
        m=self.model
        with m.lock.held():
            self.interrupt();call=self.cleanup_call();current=m.owner();write=current.store.write
            def lost(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['cleanup'] is not None:raise OSError('Synthetic lost cleanup intent commit return')
            with patch.object(current.store,'write',side_effect=lost),self.assertRaises(OSError):current.recover_foreground(call)
            self.assertTrue(current.failed);current=m.owner()
            with self.assertRaises(NativeUIError):current.recover_foreground(call)
            self.assertFalse(m.foreground);self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_failed_slow_or_changed_retention_keeps_recovery_journal_and_originals(self):
        for fault in ('rejected','slow','background','source','new-cleanup','missing-source'):
            root=self.model.root/fault;root.mkdir(mode=0o700);m=Model(root)
            with self.subTest(fault=fault),m.lock.held():
                self.interrupt(m);call=self.cleanup_call(m);current=m.owner();current.recover_foreground(call)
                def retain(packet):
                    if fault=='rejected':return False
                    if fault=='slow':m.clock+=31
                    elif fault=='background':m.foreground=False
                    elif fault=='source':
                        header=current.sources.read();state=unpack(header['payload'])[0];state['revision']=0;header['payload']=pack([state])
                        current.sources.write(header,current.sources.read())
                    elif fault=='new-cleanup':self.cleanup_call(m,ticket='d'*32)
                    else:current.sources.discard(current.sources.read())
                with self.assertRaises((NativeUIError,ValueError,OSError)):current.retire_recovery(retain)
                self.assertIsNotNone(current.store.read())

    def test_legacy_background_header_replays_only_in_segment_zero_and_upgrades_on_save(self):
        m=self.model
        with m.lock.held():
            current,old=self.interrupt();before=current.previous;legacy=deepcopy(before)
            legacy['emoteBackgroundVersion']=1;legacy.pop('sourceSegment')
            state=unpack(legacy['payload'])[0];state.pop('cleanup');legacy['payload']=pack([state])
            current.store.write(legacy,before);current=m.owner();self.assertIsNone(current.state['cleanup'])
            with self.assertRaises(NativeUIError):m.owner(segment=1)
            current.act(old);self.assertEqual(2,current.previous['emoteBackgroundVersion']);current.retire()

    def test_cleanup_recovery_retains_later_namespace_without_touching_frozen_predecessor(self):
        m=self.model
        with m.lock.held():
            first=m.source();first.read();frozen=deepcopy(first.previous);m.source(segment=1).read()
            self.interrupt(segment=1);call=self.cleanup_call();current=m.owner(segment=1);current.recover_foreground(call)
            packet=current.retire_recovery(lambda *_:None)
            self.assertEqual(1,packet['header']['sourceSegment']);self.assertEqual(frozen,first.store.read())
            with self.assertRaises(NativeUIError):m.owner().recovery_archive(packet)
            self.assertEqual(packet,m.owner(segment=1).recovery_archive(packet))
        self.assertEqual(0,m.background_native_accesses);self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_archived_recovery_rejects_forged_versions_namespace_context_and_source_loss(self):
        m=self.model
        with m.lock.held():
            self.interrupt();call=self.cleanup_call();current=m.owner();current.recover_foreground(call)
            packet=current.retire_recovery(lambda *_:None);current=m.owner()
            for fault in ('version','namespace','role','birth','foreground','call','ticket'):
                value=deepcopy(packet);state=unpack(value['header']['payload'])[0]
                if fault=='version':value['emoteForegroundRetirementVersion']=True
                elif fault=='namespace':value['header']['sourceSegment']=1
                elif fault=='role':value['sourceHeader']['role']='actor'
                elif fault=='birth':state['cleanup']['provider']['instance']='9'*32
                elif fault=='foreground':state['cleanup']['foreground']['foreground']=False
                elif fault=='call':state['call']['ticket']='f'*32
                else:state['cleanup']['provider']['activations'][-1]['ticket']=state['call']['ticket']
                value['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,OSError)):current.recovery_archive(value)
            from overte_phone_emote_originals import PhoneEmoteOriginals
            original=PhoneEmoteOriginals(m.root,m.binding,RUN,'primary',lambda:True,lambda *_:False)
            source=unpack(packet['sourceHeader']['payload'])[0];entries=original.manifest(source['manifests'][0])
            original.path(original.expand(entries[0])).unlink()
            with self.assertRaises((NativeUIError,OSError)):current.recovery_archive(packet)

    def test_recovery_rejects_mutated_live_state_without_new_ordinary_input(self):
        m=self.model
        with m.lock.held():
            self.interrupt();call=self.cleanup_call();current=m.owner();current.state['call']['ticket']='f'*32
            with self.assertRaises(NativeUIError):current.recover_foreground(call)
            self.assertIsNotNone(current.store.read());self.assertFalse(m.foreground)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_normal_retention_failure_or_late_callback_keeps_original_cycle_lease(self):
        for fault in ('rejected','slow','background','missing-source'):
            root=self.model.root/fault;root.mkdir(mode=0o700);m=Model(root)
            with self.subTest(fault=fault),m.lock.held():
                current=m.owner();current.act(m.call('background-resume'))
                def retain(header):
                    self.assertEqual(current.previous,header)
                    if fault=='rejected':return False
                    if fault=='slow':m.clock+=31
                    elif fault=='background':m.foreground=False
                    else:current.sources.discard(current.sources.read())
                with self.assertRaises((NativeUIError,OSError)):current.retire(retain=retain)
                self.assertIsNotNone(current.store.read())

    def test_later_same_phase_native_source_reads_do_not_prevent_retaining_the_original_completed_cycle(self):
        m=self.model;retained=[]
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));original=deepcopy(current.previous)
            source=current.live();source.read();self.assertNotEqual(current.state['afterHeader'],source.previous)
            current.retire(retain=lambda header:retained.append(deepcopy(header)))
            self.assertEqual([original],retained);self.assertIsNone(current.store.read());self.assertIsNotNone(source.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_completed_archive_reopens_original_cycle_after_lease_retirement_without_queries_or_retiming(self):
        m=self.model;retained=[]
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));source=current.live();source.read()
            current.retire(retain=lambda header:retained.append(deepcopy(header)));reads=m.calls.count('native-read')
            state,before,after=PhoneEmoteBackground.completed_archive(retained[0],source)
            self.assertEqual('observed',state['phase']);self.assertLess(before[-1]['group']['native']['sequence'],after[-1]['group']['native']['sequence'])
            self.assertEqual(1,after[-1]['group']['native']['lifecycle']['backgrounds'])
            original=deepcopy((state,before,after));m.epoch+=5000
            self.assertEqual(original,PhoneEmoteBackground.completed_archive(retained[0],source))
            self.assertEqual(reads,m.calls.count('native-read'));self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_completed_archive_can_bind_an_independent_actor_without_forwarding_current_native_facts(self):
        m=self.model
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));actor=m.source('actor');reads=m.calls.count('native-read')
            state,before,after=PhoneEmoteBackground.completed_archive(current.previous,actor)
            self.assertEqual([],actor.frames);self.assertEqual(reads,m.calls.count('native-read'))
            self.assertEqual('primary',state['beforeHeader']['role']);self.assertEqual('primary',state['afterHeader']['role'])
            self.assertTrue(before and after);self.assertNotIn('fresh',state)

    def test_completed_archive_cannot_issue_live_inputs_cleanup_or_new_source_reads(self):
        m=self.model;views=[];decode=PhoneEmoteBackground.decode
        with m.lock.held():
            current=m.owner();call=m.call('background-resume');current.act(call);source=current.live()
            def spy(scope,value):
                if scope.historical:views.append(scope)
                return decode(scope,value)
            with patch.object(PhoneEmoteBackground,'decode',spy):PhoneEmoteBackground.completed_archive(current.previous,source)
            self.assertEqual(1,len(views));view=views[0]
            for action in (lambda:view.act(call),view.live,view.save,view.retire,
                    lambda:view.recover_foreground(dict(contractVersion=CONTRACT_VERSION,runId=RUN)),
                    lambda:view.retire_recovery(lambda *_:None)):
                with self.assertRaises(NativeUIError):action()
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_changed_phase_or_new_native_override_cannot_retire_a_completed_cycle_through_later_observations(self):
        m=self.model
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));m.start('Waving');source=current.live();source.read()
            with self.assertRaises(NativeUIError):current.retire()
            self.assertIsNotNone(current.store.read());m.restore();m.call('close');source=current.live();source.read()
            with self.assertRaises(NativeUIError):current.retire()
            self.assertIsNotNone(current.store.read())

    def test_completed_archive_rejects_changed_context_failed_phase_and_missing_original(self):
        m=self.model
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));source=current.live()
            for fault in ('version','phase','process','segment','source-role'):
                value=deepcopy(current.previous);state=unpack(value['payload'])[0]
                if fault=='version':value['emoteBackgroundVersion']=True
                elif fault=='phase':state['phase']='background-issued'
                elif fault=='process':state['binding']['processIdentity']='32:foreign'
                elif fault=='segment':value['sourceSegment']=True
                else:state['beforeHeader']['role']='actor'
                value['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,OSError)):
                    PhoneEmoteBackground.completed_archive(value,source)
            from overte_phone_emote_originals import PhoneEmoteOriginals
            originals=PhoneEmoteOriginals(m.root,m.binding,RUN,'primary',lambda:True,lambda *_:False)
            state=unpack(current.state['beforeHeader']['payload'])[0];rows=originals.manifest(state['manifests'][0])
            originals.path(originals.expand(rows[0])).unlink()
            with self.assertRaises((NativeUIError,OSError)):PhoneEmoteBackground.completed_archive(current.previous,source)

    def test_later_fixture_phase_alone_cannot_retire_the_original_background_cycle(self):
        m=self.model
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));source=current.live()
            m.call('close');source.read()
            self.assertEqual(0,source.frames[-1]['group']['native']['animation']['history']['callSequence'])
            with self.assertRaises(NativeUIError):current.retire()
            self.assertIsNotNone(current.store.read())

    def test_completed_archive_initial_guard_is_inside_its_five_second_bound(self):
        m=self.model
        with m.lock.held():
            current=m.owner();current.act(m.call('background-resume'));source=current.live();guard=source.guard
            reads=m.calls.count('native-read')
            def slow():m.clock+=6;return guard()
            source.guard=slow
            with self.assertRaises(NativeUIError):PhoneEmoteBackground.completed_archive(current.previous,source)
            self.assertIsNotNone(current.store.read());self.assertEqual(reads,m.calls.count('native-read'))

    def test_ordinary_home_and_activation_require_original_os_and_native_lifecycle_then_retire_metadata(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');self.assertEqual({'performed':True},owner.act(call))
            self.assertEqual('observed',owner.state['phase']);self.assertFalse(owner.state['background']['foreground'])
            self.assertTrue(owner.state['foreground']['foreground']);self.assertLess(owner.store.path.stat().st_size,65536)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)
            current=m.owner();current.retire();self.assertIsNone(current.store.read())
            self.assertIsNotNone(owner.sources.read()) # Source originals are not the background input lease.
        self.assertEqual(0,m.background_native_accesses)

    def test_lost_home_return_reconstructs_in_background_without_native_access_or_second_home(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertFalse(m.foreground);self.assertEqual('background-issued',owner.state['phase'])
            m.lose='';current=m.owner();current.act(call)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);current.retire()
        self.assertEqual(0,m.background_native_accesses)

    def test_lost_activation_return_reconstructs_original_foreground_and_does_not_launch_twice(self):
        m=self.model;m.lose='app.launch'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertTrue(m.foreground);self.assertEqual('foreground-issued',owner.state['phase'])
            m.lose='';current=m.owner();current.act(call);current.retire()
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_ignored_home_ack_cannot_be_success_or_repeated_after_reconstruction(self):
        m=self.model;m.ignore='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
            self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_ignored_activation_ack_cannot_be_success_or_repeated_after_reconstruction(self):
        m=self.model;m.ignore='app.launch'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_os_transition_without_actual_native_background_and_activation_is_not_success(self):
        m=self.model;m.native_changed=False
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual('observing',owner.state['phase']);self.assertIsNotNone(owner.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_active_animation_baseline_does_not_hide_an_extra_restore_input_in_background(self):
        m=self.model;m.start('Waving')
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertIsNone(owner.store.read())
        self.assertEqual([],m.normal_inputs);self.assertEqual([],m.controls.input_requests)

    def test_changed_candidate_process_or_missing_os_evidence_prevents_an_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            m.foreign=True
            with self.assertRaises(NativeUIError):m.owner()
            m.foreign=False;m.os_unavailable=True
            with self.assertRaises(NativeUIError):m.owner()
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_changed_or_missing_primary_header_cannot_authorize_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            owner.sources.discard(owner.sources.read());current=m.owner();m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_lost_final_source_result_keeps_pending_originals_without_repeating_os_inputs(self):
        m=self.model;original=m.invoke
        def lose_after_activation(*args):
            value=original(*args)
            if args[1]=='app.launch':m.source_lost=True
            return value
        m.invoke=lose_after_activation
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
            self.assertIsNotNone(current.sources.read());self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_failed_pre_input_journal_write_cannot_issue_home_or_succeed_on_same_object_retry(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');writer=owner.store.write
            owner.store.write=lambda *_args:(_ for _ in ()).throw(OSError('Synthetic interrupted journal write'))
            with self.assertRaises((NativeUIError,OSError)):owner.act(call)
            owner.store.write=writer
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.normal_inputs)

    def test_foreign_ticket_cannot_resume_an_existing_owned_input(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();other=m.call('background-resume')
            with self.assertRaises(NativeUIError):current.act(other)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_changed_actual_fixture_phase_cannot_activate_an_old_background_call(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();m.call('close');m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertFalse(m.foreground);self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_new_fixture_birth_with_same_ticket_cannot_borrow_old_background_authority(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();m.journal.phase_instance='8'*32;m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_unresolved_ordinary_emote_input_blocks_a_new_background_action(self):
        m=self.model;m.widgets.tablet=False;m.input_fault='lost-sdk'
        from overte_phone_emote_inputs import PhoneEmoteInputs
        with m.lock.held(),patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet):
            inputs=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):inputs.act(m.call('open'))
            self.assertEqual('issuing',inputs.state['current']['phase'])
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call('background-resume'))
            self.assertIsNone(owner.store.read())
        self.assertEqual([],m.normal_inputs)

    def test_corrupt_or_missing_originals_in_background_cannot_authorize_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            from overte_phone_script_history import unpack
            from overte_phone_emote_originals import PhoneEmoteOriginals
            header=owner.state['beforeHeader'];state=unpack(header['payload'])[0]
            originals=PhoneEmoteOriginals(m.root,m.binding,RUN,'primary',lambda:True,lambda *_args:False)
            entries=originals.manifest(state['manifests'][0]);originals.path(originals.expand(entries[0])).unlink()
            with self.assertRaises((NativeUIError,OSError)):m.owner()
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_failed_final_journal_write_resumes_only_original_reads_without_os_redelivery(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');writer=owner.store.write
            from overte_phone_script_history import unpack
            def fail_observed(value,previous):
                if unpack(value['payload'])[0]['phase']=='observed':raise OSError('Synthetic lost final commit')
                return writer(value,previous)
            owner.store.write=fail_observed
            with self.assertRaises((NativeUIError,OSError)):owner.act(call)
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();current.act(call);current.retire()
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_original_replay_has_no_native_transport_and_retains_original_clocks(self):
        m=self.model
        with m.lock.held():
            source=m.source();m.call('background-resume');frame=source.read();before=list(m.calls)
            from overte_phone_emote_sources import PhoneEmoteSources
            state,frames=PhoneEmoteSources.archive(source.previous,phase=source.phase,artifact_root=m.root,
                binding=m.binding,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertEqual(before,m.calls);self.assertEqual(frame,frames[-1]);self.assertEqual('ready',state['phase'])

    def test_retirement_refuses_unobserved_background_and_preserves_original_ownership(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.retire()
            self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background'],m.normal_inputs)


if __name__=='__main__':unittest.main()
