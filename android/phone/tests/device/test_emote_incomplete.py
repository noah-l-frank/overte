"""Incomplete parent transfers retain failure over synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_emote_observation import Model,POLICY
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_capture import PhoneEmoteCapture
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_observation import PhoneEmoteObservation,ObservationOriginals
from overte_phone_script_history import pack,unpack


class EmoteIncompleteTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-incomplete-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        mock.start();self.addCleanup(mock.stop)

    def scope(self,*,keep_child=False,role='primary'):
        m=self.model;call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call)
        scope=m.scope(owner,1,role=role);cleanup=PhoneEmoteCapture.cleanup
        def lost(child):
            if not keep_child:cleanup(child)
            raise NativeUIError('Synthetic lost parent cleanup return')
        with patch.object(PhoneEmoteCapture,'cleanup',lost),self.assertRaises(NativeUIError):scope.read(call['ticket'])
        self.assertEqual('captured',scope.state['phase']);self.assertIsNone(scope.state['retirement'])
        return m.scope(PhoneEmoteInputs(m.source()),1,role=role),call

    def target_reads(self):
        return [kind for kind in self.model.calls if kind!='phase-read']

    def outcome_failure(self):
        m=self.model;call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1);save=scope.save
        def fail():
            if scope.state['phase']=='complete':raise OSError('Synthetic failed final complete-phase write')
            return save()
        with patch.object(scope,'save',side_effect=fail),self.assertRaises(OSError):scope.read(call['ticket'])
        return m.scope(PhoneEmoteInputs(m.source()),1)

    def partial(self,phase='opened'):
        m=self.model;call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
        intent=scope.originals.intent
        def lost(kind,value):
            if phase=='full-opened' and value['phase']=='saved':raise NativeUIError('Synthetic full file before saved intent')
            result=intent(kind,value)
            if value['phase']==phase:raise NativeUIError('Synthetic interrupted parent original intent')
            return result
        scope.originals.intent=lost
        with self.assertRaises(NativeUIError):scope.read(call['ticket'])
        return m.scope(PhoneEmoteInputs(m.source()),1)

    def test_lost_cleanup_return_transfers_original_failure_without_new_input_or_measurement(self):
        m=self.model;retained=[]
        with m.lock.held():
            scope,call=self.scope();before=self.target_reads();inputs=deepcopy(m.controls.input_requests)
            packet=scope.transfer_incomplete(lambda proof:retained.append(deepcopy(proof)))
            self.assertEqual([packet],retained);self.assertIsNone(scope.store.read())
            state=unpack(packet['header']['payload'])[0];self.assertEqual('captured',state['phase'])
            self.assertIsNotNone(state['retirement']);self.assertIsNone(state['outcome'])
            self.assertNotIn('result',packet);self.assertNotIn('state',packet);self.assertNotIn('pixels',packet)
            self.assertEqual(packet,PhoneEmoteObservation.incomplete_archive(packet,scope.effects,1,POLICY))
            with self.assertRaises(NativeUIError):scope.original()
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual(before,self.target_reads());self.assertEqual(inputs,m.controls.input_requests)
            self.assertEqual(1,m.world.counters['capture']);self.assertTrue(scope.source.store.path.exists())
            self.assertTrue(scope.effects.inputs.store.path.exists())

    def test_existing_exact_complete_child_is_retired_before_parent_transfer(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope(keep_child=True);child=m.root/'phone-emote-primary-capture-1.json'
            self.assertTrue(child.exists());before=len(m.world.calls)
            packet=scope.transfer_incomplete(lambda proof:self.assertFalse(child.exists()))
            self.assertFalse(child.exists());self.assertIsNone(scope.store.read())
            self.assertEqual(before,len(m.world.calls));self.assertEqual(1,m.world.counters['capture'])
            PhoneEmoteObservation.incomplete_archive(packet,scope.effects,1,POLICY)

    def test_actor_incomplete_transfer_reopens_only_its_original_context(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope(role='actor');packet=scope.transfer_incomplete(lambda *_:None)
            self.assertEqual('actor',packet['header']['role']);self.assertEqual('actor',packet['sourceHeader']['role'])
            self.assertEqual('primary',packet['inputSourceHeader']['role'])
            self.assertEqual(packet,PhoneEmoteObservation.incomplete_archive(packet,scope.effects,1,POLICY))
            effects=PhoneEmoteEffects(scope.effects.inputs)
            with self.assertRaises(NativeUIError):PhoneEmoteObservation.incomplete_archive(packet,effects,1,POLICY)

    def test_failed_parent_retention_preserves_scope_and_all_originals_then_can_retry_transfer(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope(keep_child=True)
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda *_:False)
            self.assertIsNotNone(scope.store.read());self.assertIsNotNone(scope.state['retirement'])
            self.assertFalse((m.root/'phone-emote-primary-capture-1.json').exists())
            packet=scope.transfer_incomplete(lambda *_:None)
            PhoneEmoteObservation.incomplete_archive(packet,scope.effects,1,POLICY)
            self.assertEqual(1,m.world.counters['capture'])

    def test_postimage_interrupted_source_remains_pending_after_parent_transfer(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            send=m.native_send
            def lost(request):
                send(request)
                if m.world.counters['capture']:raise NativeUIError('Synthetic lost post-image native source return')
            with patch.object(m,'native_send',side_effect=lost),self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual('measuring',scope.state['phase']);self.assertEqual('reading',scope.source.state['phase'])
            current=m.scope(PhoneEmoteInputs(m.source()),1);before=self.target_reads()
            packet=current.transfer_incomplete(lambda *_:None)
            self.assertEqual('reading',unpack(packet['sourceHeader']['payload'])[0]['phase'])
            self.assertTrue(current.source.store.path.exists());self.assertEqual(before,self.target_reads())
            PhoneEmoteObservation.incomplete_archive(packet,current.effects,1,POLICY)
            context=current.effects._archive_context(packet['inputHeader'],packet['inputSourceHeader'],packet['sourceHeader'],ready=False)
            with self.assertRaises(NativeUIError):context.source.read()
            with self.assertRaises(NativeUIError):context.inputs.bound()
            with self.assertRaises(NativeUIError):context.measure(context.reference())
            with self.assertRaises(NativeUIError):
                current.effects._archive_context(packet['inputHeader'],packet['inputSourceHeader'],packet['sourceHeader'])

    def test_saved_outcome_is_recomputed_without_promoting_uncommitted_complete_phase(self):
        m=self.model
        with m.lock.held():
            current=self.outcome_failure()
            self.assertEqual('measuring',current.state['phase']);self.assertIsNotNone(current.state['outcome'])
            packet=current.transfer_incomplete(lambda *_:None)
            self.assertEqual('measuring',unpack(packet['header']['payload'])[0]['phase'])
            PhoneEmoteObservation.incomplete_archive(packet,current.effects,1,POLICY)
            self.assertNotIn('result',packet);self.assertEqual(1,m.world.counters['capture'])

    def test_faulty_writer_saved_effect_is_recomputed_before_incomplete_transfer(self):
        m=self.model
        with m.lock.held():
            current=self.outcome_failure();outcome=deepcopy(current.load('outcome'));outcome['effect']['state']['animation']='Love'
            writer=ObservationOriginals(m.root,current.source.binding,current.source.run,'primary',lambda:True,lambda *_:None,
                kind='observations',monotonic=lambda:m.clock)
            reference=writer.write(2,outcome);header=deepcopy(current.previous);state=unpack(header['payload'])[0]
            state['outcome']=reference;header['payload']=pack([state]);current.store.write(header,current.previous)
            current=m.scope(PhoneEmoteInputs(m.source()),1);retained=[]
            with self.assertRaises(NativeUIError):current.transfer_incomplete(lambda packet:retained.append(packet))
            self.assertEqual([],retained);self.assertIsNotNone(current.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_incomplete_archive_rejects_forged_context_and_extra_results(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope();packet=scope.transfer_incomplete(lambda *_:None)
            for fault in ('version','result','role','binding','ticket','retirement','complete','missing-capture'):
                value=deepcopy(packet);state=unpack(value['header']['payload'])[0]
                if fault=='version':value['emoteObservationIncompleteArchiveVersion']=True
                elif fault=='result':value['result']=dict(passed=True)
                elif fault=='role':value['header']['role']='actor'
                elif fault=='binding':value['header']['binding']['processIdentity']='32:foreign'
                elif fault=='ticket':state['ticket']='f'*32
                elif fault=='retirement':state['retirement']=None
                elif fault=='complete':state['phase']='complete'
                else:state['capture']=None
                value['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,OSError)):
                    PhoneEmoteObservation.incomplete_archive(value,scope.effects,1,POLICY)

    def test_missing_or_equal_byte_replaced_png_cannot_retire_parent(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope();captured=scope.load('capture');state=unpack(captured['header']['payload'])[0]
            path=m.root/state['image']['name'];raw=path.read_bytes();replacement=path.with_suffix('.replacement')
            replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda *_:None)
            self.assertIsNotNone(scope.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_foreign_current_world_owner_is_not_released_or_hidden_by_old_cleanup_proof(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope();owned=m._world_render_capture('x',read_only=True,role='primary',require_frame_view=True)
            owned.owner.intent(dict(schemaVersion=1,commandId='f'*32,action='feature-world-render-observe'));before=owned.owner.owned()
            calls=len(m.world.calls)
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda *_:None)
            self.assertEqual(before,owned.owner.owned());self.assertEqual(calls,len(m.world.calls));self.assertIsNotNone(scope.store.read())

    def test_changed_source_in_retention_callback_preserves_parent_even_when_old_archive_is_valid(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope()
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda *_:scope.source.read())
            self.assertIsNotNone(scope.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_missing_parent_capture_or_pending_original_never_uses_this_recovery_path(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            intent=scope.originals.intent
            def lost(kind,value):
                result=intent(kind,value)
                if value['phase']=='opened':raise NativeUIError('Synthetic partial parent original write')
                return result
            scope.originals.intent=lost
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            current=m.scope(PhoneEmoteInputs(m.source()),1);before=len(m.world.calls)
            with self.assertRaises(NativeUIError):current.transfer_incomplete(lambda *_:None)
            self.assertIsNotNone(current.state['pending']);self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())
            self.assertEqual(before,len(m.world.calls));self.assertIsNotNone(current.store.read())

    def test_late_retention_and_new_child_metadata_cannot_discard_scope(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope()
            def late(_packet):m.clock+=6
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(late)
            self.assertIsNotNone(scope.store.read());current=m.scope(PhoneEmoteInputs(m.source()),1)
            def child(_packet):
                PrivateFeatureState(m.root/'phone-emote-primary-capture-1.json').write(current.load('capture')['header'],None)
            with self.assertRaises(NativeUIError):current.transfer_incomplete(child)
            self.assertIsNotNone(current.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_lost_retirement_write_return_requires_reconstruction_without_input_or_child_recreation(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope();write=scope.store.write;retained=[]
            def lost(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['retirement'] is not None:raise OSError('Synthetic lost retirement write return')
            with patch.object(scope.store,'write',side_effect=lost),self.assertRaises(OSError):
                scope.transfer_incomplete(lambda packet:retained.append(packet))
            self.assertTrue(scope.failed);self.assertEqual([],retained)
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda *_:None)
            current=m.scope(PhoneEmoteInputs(m.source()),1);current.transfer_incomplete(lambda packet:retained.append(packet))
            self.assertEqual(1,len(retained));self.assertEqual(1,m.world.counters['capture'])
            self.assertFalse((m.root/'phone-emote-primary-capture-1.json').exists())

    def test_initial_slow_guard_is_inside_whole_transfer_deadline(self):
        m=self.model
        with m.lock.held():
            scope,_call=self.scope();guard=scope.source.guard;retained=[]
            def slow():m.clock+=6;return guard()
            scope.source.guard=slow
            with self.assertRaises(NativeUIError):scope.transfer_incomplete(lambda packet:retained.append(packet))
            self.assertEqual([],retained);self.assertIsNotNone(scope.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_opened_partial_parent_original_and_child_cleanup_are_retained_before_either_scope_deletion(self):
        m=self.model;retained=[]
        with m.lock.held():
            scope=self.partial();child=m.root/'phone-emote-primary-capture-1.json'
            original=scope.state['pending']['original'];path=scope.originals.path(original)
            self.assertEqual(0,path.stat().st_size);before=self.target_reads()
            def retain(packet):
                self.assertTrue(child.exists());self.assertIsNotNone(scope.store.read());retained.append(deepcopy(packet))
            packet=scope.transfer_failed(retain);self.assertEqual([packet],retained)
            diagnostic=packet['pendingDiagnostic'];self.assertEqual(0,diagnostic['bytes'])
            self.assertEqual(hashlib.sha256(b'').hexdigest(),diagnostic['sha256']);self.assertNotEqual(original['sha256'],diagnostic['sha256'])
            self.assertEqual('opened',unpack(packet['header']['payload'])[0]['pending']['original']['phase'])
            self.assertFalse(child.exists());self.assertIsNone(scope.store.read());self.assertTrue(path.exists())
            self.assertEqual(packet,PhoneEmoteObservation.failure_archive(packet,scope.effects,1,POLICY))
            self.assertEqual(before,self.target_reads());self.assertNotIn('result',packet);self.assertEqual(1,m.world.counters['capture'])

    def test_full_opened_pending_file_remains_a_failed_original(self):
        m=self.model
        with m.lock.held():
            scope=self.partial('full-opened');original=scope.state['pending']['original'];packet=scope.transfer_failed(lambda *_:None)
            self.assertEqual(original['bytes'],packet['pendingDiagnostic']['bytes'])
            self.assertEqual(original['sha256'],packet['pendingDiagnostic']['sha256'])
            self.assertEqual('opened',unpack(packet['header']['payload'])[0]['pending']['original']['phase'])
            self.assertIsNone(unpack(packet['header']['payload'])[0]['capture']);self.assertNotIn('result',packet)

    def test_planned_parent_original_is_proven_absent_without_invented_bytes(self):
        m=self.model
        with m.lock.held():
            scope=self.partial('planned');path=scope.originals.path(scope.state['pending']['original'])
            packet=scope.transfer_failed(lambda *_:None);self.assertIsNone(packet['pendingDiagnostic']);self.assertFalse(path.exists())
            self.assertEqual('planned',unpack(packet['header']['payload'])[0]['pending']['original']['phase'])

    def test_saved_pending_original_is_reopened_without_adopting_a_completed_parent(self):
        m=self.model
        with m.lock.held():
            scope=self.partial('saved');packet=scope.transfer_failed(lambda *_:None);self.assertIsNone(packet['pendingDiagnostic'])
            state=unpack(packet['header']['payload'])[0];self.assertIsNone(state['capture']);self.assertEqual('capturing',state['phase'])
            self.assertEqual('saved',state['pending']['original']['phase']);PhoneEmoteObservation.failure_archive(packet,scope.effects,1,POLICY)

    def test_lost_failed_child_cleanup_return_requires_exact_retained_parent_proof_without_new_capture(self):
        m=self.model;retained=[]
        with m.lock.held():
            scope=self.partial();discard=PrivateFeatureState.discard
            def lost(store,previous):
                discard(store,previous)
                if store.path.name=='phone-emote-primary-capture-1.json':raise OSError('Synthetic lost child discard return')
            with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(OSError):
                scope.transfer_failed(lambda packet:retained.append(deepcopy(packet)))
            self.assertEqual(1,len(retained));self.assertIsNotNone(scope.store.read())
            current=m.scope(PhoneEmoteInputs(m.source()),1)
            with self.assertRaises(NativeUIError):current.transfer_failed(lambda *_:None)
            packet=current.transfer_failed(lambda packet:self.assertEqual(retained[0],packet),retained=retained[0])
            self.assertEqual(retained[0],packet);self.assertIsNone(current.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_rejected_failure_retention_keeps_both_scopes_and_partial_bytes(self):
        m=self.model
        with m.lock.held():
            scope=self.partial();path=scope.originals.path(scope.state['pending']['original'])
            with self.assertRaises(NativeUIError):scope.transfer_failed(lambda *_:False)
            self.assertIsNotNone(scope.store.read());self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())
            self.assertTrue(path.exists());packet=scope.transfer_failed(lambda *_:None)
            self.assertEqual(0,packet['pendingDiagnostic']['bytes']);self.assertEqual(1,m.world.counters['capture'])

    def test_changed_partial_file_during_retention_prevents_child_and_parent_deletion(self):
        m=self.model
        with m.lock.held():
            scope=self.partial();path=scope.originals.path(scope.state['pending']['original'])
            def changed(_packet):path.write_bytes(b'changed actual partial bytes')
            with self.assertRaises(NativeUIError):scope.transfer_failed(changed)
            self.assertIsNotNone(scope.store.read());self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())
            self.assertEqual(b'changed actual partial bytes',path.read_bytes())

    def test_foreign_file_at_planned_parent_path_is_never_adopted_or_deleted(self):
        m=self.model
        with m.lock.held():
            scope=self.partial('planned');path=scope.originals.path(scope.state['pending']['original']);path.write_bytes(b'foreign');path.chmod(0o600)
            with self.assertRaises(NativeUIError):scope.transfer_failed(lambda *_:None)
            self.assertEqual(b'foreign',path.read_bytes());self.assertIsNotNone(scope.store.read())
            self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())

    def test_native_failed_image_acquisition_transfers_only_actual_resource_retirement(self):
        m=self.model;m.capture_fault='lost-return'
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            current=m.scope(PhoneEmoteInputs(m.source()),1);packet=current.transfer_failed(lambda *_:None)
            self.assertFalse(packet['childRetirement']['cleanup']['completeImageRecord'])
            self.assertIsNotNone(packet['childRetirement']['cleanup']['retirement']);self.assertIsNone(packet['pendingDiagnostic'])
            self.assertIsNone(unpack(packet['header']['payload'])[0]['capture']);self.assertEqual(1,m.world.counters['capture'])

    def test_undrained_failed_image_cannot_discard_either_scope_then_recovery_never_repeats_capture(self):
        m=self.model;m.world.storage.ignore_release=True
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            current=m.scope(PhoneEmoteInputs(m.source()),1)
            with self.assertRaises(NativeUIError):current.transfer_failed(lambda *_:None)
            self.assertIsNotNone(current.store.read());self.assertTrue((m.world_root/'world-primary.json').exists())
            m.world.storage.ignore_release=False;packet=current.transfer_failed(lambda *_:None)
            self.assertFalse(packet['childRetirement']['cleanup']['completeImageRecord']);self.assertEqual(1,m.world.counters['capture'])
            self.assertFalse((m.world_root/'world-primary.json').exists());PhoneEmoteObservation.failure_archive(packet,current.effects,1,POLICY)

    def test_reused_phase_index_cannot_borrow_an_old_child_retirement_or_relabel_its_parent(self):
        m=self.model
        with m.lock.held():
            old=self.partial();packet=old.transfer_failed(lambda *_:None)
            call=m.call('cancel');PhoneEmoteInputs(m.source()).act(call)
            current=self.partial();self.assertNotEqual(old.scope_id,current.scope_id)
            foreign=deepcopy(packet);foreign.update(header=deepcopy(current.previous),inputHeader=deepcopy(current.effects.inputs.previous),
                inputSourceHeader=deepcopy(current.effects.inputs.source.previous),sourceHeader=deepcopy(current.source.previous),
                pendingDiagnostic=current.pending_diagnostic())
            with self.assertRaises(NativeUIError):PhoneEmoteObservation.failure_archive(foreign,current.effects,1,POLICY)
            foreign['childRetirement']['header']['parentScope']=current.scope_id
            with self.assertRaises(NativeUIError):PhoneEmoteObservation.failure_archive(foreign,current.effects,1,POLICY)
            self.assertIsNotNone(current.store.read());self.assertEqual(2,m.world.counters['capture'])

    def test_equal_partial_bytes_with_changed_file_metadata_cannot_reuse_retained_diagnostic(self):
        m=self.model
        with m.lock.held():
            scope=self.partial();path=scope.originals.path(scope.state['pending']['original'])
            def changed(packet):
                stat=path.stat();os.utime(path,ns=(stat.st_atime_ns,packet['pendingDiagnostic']['file']['modifiedNs']+1))
            with self.assertRaises(NativeUIError):scope.transfer_failed(changed)
            self.assertEqual(b'',path.read_bytes());self.assertIsNotNone(scope.store.read())
            self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())

    def test_legacy_complete_headers_remain_readable_without_assigning_a_new_parent_identity(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1);scope.read(call['ticket'])
            capture=deepcopy(scope.load('capture'));capture['header']['emoteCaptureVersion']=1;capture['header'].pop('parentScope')
            writer=ObservationOriginals(m.root,scope.source.binding,scope.source.run,'primary',lambda:True,lambda *_:None,
                kind='observations',monotonic=lambda:m.clock)
            reference=writer.write(1,capture);header=deepcopy(scope.previous);header['emoteObservationVersion']=1;header.pop('scopeId')
            state=unpack(header['payload'])[0];state['capture']=reference;header['payload']=pack([state]);scope.store.write(header,scope.previous)
            legacy=m.scope(PhoneEmoteInputs(m.source()),1);self.assertIsNone(legacy.scope_id)
            result=legacy.original();self.assertEqual(1,result['image']['emoteCaptureVersion']);self.assertEqual(1,result['emoteObservationResultVersion'])
            packet=legacy.transfer(lambda *_:None);self.assertEqual(result,PhoneEmoteObservation.archive(packet,legacy.effects,1,POLICY))
            self.assertNotIn('scopeId',packet['header']);self.assertNotIn('parentScope',packet['result']['image'])

    def test_preparation_failure_transfers_only_parent_metadata_and_preserves_interrupted_source(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            send=m.native_send
            def ignored(request):send(request);raise NativeUIError('Synthetic preparation native result loss')
            with patch.object(m,'native_send',side_effect=ignored),self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual('preparing',scope.state['phase']);current=m.scope(PhoneEmoteInputs(m.source()),1);before=self.target_reads()
            packet=current.transfer_failed(lambda *_:None);self.assertIsNone(packet['childRetirement']);self.assertIsNone(packet['pendingDiagnostic'])
            self.assertEqual('preparing',unpack(packet['header']['payload'])[0]['phase'])
            self.assertEqual('reading',unpack(packet['sourceHeader']['payload'])[0]['phase']);self.assertTrue(current.source.store.path.exists())
            self.assertEqual(before,self.target_reads());self.assertEqual(0,m.world.counters['capture'])
            PhoneEmoteObservation.failure_archive(packet,current.effects,1,POLICY)

    def test_ambiguous_capturing_without_child_or_retained_proof_never_uses_preparation_recovery(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            save=scope.save
            def failed():
                result=save()
                if scope.state['phase']=='capturing':raise OSError('Synthetic interruption after capture responsibility')
                return result
            with patch.object(scope,'save',side_effect=failed),self.assertRaises(OSError):scope.read(call['ticket'])
            current=m.scope(PhoneEmoteInputs(m.source()),1);self.assertEqual('capturing',current.state['phase'])
            with self.assertRaises(NativeUIError):current.transfer_failed(lambda *_:None)
            self.assertIsNotNone(current.store.read());self.assertEqual(0,m.world.counters['capture'])

    def test_partial_child_png_retains_actual_zero_bytes_without_parent_outcome_or_image_success(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            intent=PhoneEmoteCapture._image_intent
            def failed(child,value):
                intent(child,value)
                if value['phase']=='opened':raise NativeUIError('Synthetic interrupted child PNG write')
            with patch.object(PhoneEmoteCapture,'_image_intent',failed),self.assertRaises(NativeUIError):scope.read(call['ticket'])
            current=m.scope(PhoneEmoteInputs(m.source()),1);packet=current.transfer_failed(lambda *_:None)
            child=packet['childRetirement'];self.assertFalse(child['cleanup']['completeImageRecord']);self.assertTrue(child['cleanup']['retainedPartialImage'])
            self.assertEqual(0,child['partialFile']['bytes']);self.assertEqual(hashlib.sha256(b'').hexdigest(),child['partialFile']['sha256'])
            self.assertTrue((m.root/child['partialFile']['name']).exists());self.assertIsNone(unpack(packet['header']['payload'])[0]['capture'])
            self.assertEqual(1,m.world.counters['capture']);PhoneEmoteObservation.failure_archive(packet,current.effects,1,POLICY)

    def test_missing_native_owner_after_undrained_request_cannot_be_recreated_by_failed_parent_cleanup(self):
        m=self.model;m.world.storage.ignore_release=True;retained=[]
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,1)
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            store=PrivateFeatureState(m.world_root/'world-primary.json');store.discard(store.read());current=m.scope(PhoneEmoteInputs(m.source()),1)
            with self.assertRaises(NativeUIError):current.transfer_failed(lambda packet:retained.append(packet))
            self.assertEqual([],retained);self.assertIsNone(store.read());self.assertIsNotNone(current.store.read())
            self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists());self.assertEqual(1,m.world.counters['capture'])

    def test_expected_parent_bytes_or_foreign_child_id_cannot_replace_actual_failure_archive(self):
        m=self.model
        with m.lock.held():
            scope=self.partial();packet=scope.transfer_failed(lambda *_:None);original=unpack(packet['header']['payload'])[0]['pending']['original']
            for fault in ('version','bytes','hash','file','child-parent','native-owner'):
                value=deepcopy(packet)
                if fault=='version':value['emoteObservationFailureArchiveVersion']=True
                elif fault=='bytes':value['pendingDiagnostic']['bytes']=original['bytes']
                elif fault=='hash':value['pendingDiagnostic']['sha256']=original['sha256']
                elif fault=='file':value['pendingDiagnostic']['file']['inode']+=1
                elif fault=='child-parent':value['childRetirement']['header']['parentScope']='f'*32
                else:value['childRetirement']['cleanup']['retirement']['memory']['present']=True
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,OSError)):
                    PhoneEmoteObservation.failure_archive(value,scope.effects,1,POLICY)

    def test_slow_failed_retention_keeps_both_metadata_owners(self):
        m=self.model
        with m.lock.held():
            scope=self.partial()
            def late(_packet):m.clock+=6
            with self.assertRaises(NativeUIError):scope.transfer_failed(late)
            self.assertIsNotNone(scope.store.read());self.assertTrue((m.root/'phone-emote-primary-capture-1.json').exists())
            self.assertEqual(1,m.world.counters['capture'])


if __name__=='__main__':unittest.main()
