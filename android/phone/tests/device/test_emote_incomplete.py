"""Incomplete parent transfers retain failure over synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
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


if __name__=='__main__':unittest.main()
