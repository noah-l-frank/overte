"""Actual fresh Source/Node/HTTP originals; native/SDK clocks are declared models.

The long case creates every earlier frame through its original acquisition.
It neither clones a saved frame nor supplies normalized outcomes to an owner.
No real-CPU API/deadline or full public journey qualification follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import os
import pstats
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebForeignSequenceRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=FeatureWorldWeb();self.addCleanup(self.f.close)
        self.f.primary.observe(dict(contractVersion=16,runId=self.f.network.run,afterSequence=0))
        self.assertEqual(dict(performed=True),self.f.primary.act(self.f.sdk.activate('open',{})))

    def posts(self):return [row for row in self.f.requests if row[1]=='POST' and row[2].endswith('/actions')]

    def parts(self):return self.f.primary.parts()

    def assert_released(self,source):
        self.assertIsNone(source._input_sequence);self.assertIsNone(source._round);self.assertIsNone(source._write_round)

    def test_genuine_fifty_four_prior_acquisitions_keep_foreign_sequence_fresh_and_normal_without_redecoding_each_input(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];actions=parts['actions']
            # The original producer is selected by FeatureWorldWeb construction
            # before its first read. Each loop issues new native/source queries
            # and writes a new original record/parts; no old DTO is retimed.
            with source.input_sequence(actions.inputs.store):
                while len(source.state['records'])<54:
                    current=actions.current('genuine-prior-'+str(len(source.state['records'])+1))
                    self.assertEqual(len(source.state['records']),current['index'])
            self.assertEqual(54,len(source.state['records']))
            with source.validation_round():originals=[source.frame(ref) for ref in source.state['records']]
            requests=[frame['clockJoin']['nativeBefore']['requestId'] for frame in originals]
            self.assertEqual(54,len(set(requests)))
            sequences=[frame['clockJoin']['nativeBefore']['sequence'] for frame in originals]
            self.assertTrue(all(left<right for left,right in zip(sequences,sequences[1:])))
            pins=source.original_pins(source.previous);pins.pop(source.store.path)
            call=self.f.sdk.activate('navigate-foreign',dict(resource='reference.html'))
            actual=source.native.send;active=[]
            def sending(query):
                if source._input_sequence is not None:
                    active.append(query['commandId']);lease=source._write_round[0]
                    self.assertNotIn(actions.store.path,lease.mutable)
                    self.assertNotIn(parts['scope'].store.path,lease.mutable)
                    self.assertIn(actions.inputs.store.path,lease.mutable)
                return actual(query)
            source.native.send=sending
            profile=cProfile.Profile();profile.enable()
            try:self.assertEqual(dict(performed=True),actions.act(call))
            finally:profile.disable();source.native.send=actual
            code=WorldWebSources._decode.__code__;calls=pstats.Stats(profile).stats.get((code.co_filename,code.co_firstlineno,code.co_name))
            # Original typed graph decoding still occurs at actual owner/WAL
            # boundaries. The same full old graph need not be rebuilt for each
            # query, Current projection and input save in this one sequence.
            self.assertIsNotNone(calls);self.assertLessEqual(calls[1],6)
            self.assertTrue(active);self.assert_released(source)
            self.assertEqual(pins,{path:source.original_signature(path) for path in pins})
            rows=[row for row in actions.inputs.state['records'] if row['ticket']==call['ticket']]
            self.assertEqual(['focus-foreign-url','type-foreign-url','navigate-foreign-url'],[row['label'] for row in rows])
            self.assertTrue(all(row['phase']=='returned' and row['releaseReturned'] for row in rows))
            last=source.frame(actions.state['calls'][-1]['after'])
            from ios.adapters.world_web_measurements import current_document
            raw=last['originals'];observed=current_document(raw['ledgerAfter'],raw['document'],raw['browser'],self.f.sdk.origins)
            self.assertEqual(('foreign','foreign',200),(observed['origin'],observed['page'],observed['response']['status']))
            before=self.posts();count=len(source.state['records']);self.assertEqual(dict(performed=True),actions.act(call))
            self.assertEqual(before,self.posts());self.assertEqual(count,len(source.state['records']))

    def passive_fault(self,kind):
        with self.f.primary.held():
            parts=self.parts();actions=parts['actions'];source=parts['source'];store=actions.inputs.store
            if kind!='birth':actions.inputs.save()
            before=self.posts();actual=source.native.send;seen=[]
            def sending(query):
                result=actual(query);seen.append(query['commandId'])
                if len(seen)==1:
                    if kind=='birth':store.write(actions.inputs.envelope(actions.inputs.state),None)
                    elif kind=='inode':value=store.read();store.write(value,value)
                    else:store.path.write_bytes(store.path.read_bytes()+b' ')
                return result
            source.native.send=sending
            try:
                with self.assertRaises(NativeUIError),source.input_sequence(store):actions.current('nested-passive-'+kind)
            finally:source.native.send=actual
            self.assertEqual(1,len(seen));self.assertEqual(before,self.posts());self.assert_released(source)

    def test_nested_passive_current_keeps_actual_input_wal_bytes_immutable(self):self.passive_fault('bytes')
    def test_nested_passive_current_keeps_same_body_input_wal_inode_immutable(self):self.passive_fault('inode')
    def test_nested_passive_current_keeps_original_input_wal_absence_immutable(self):self.passive_fault('birth')

    def immutable_owner_fault(self,role):
        with self.f.primary.held():
            parts=self.parts();actions=parts['actions'];source=parts['source'];owner=actions if role=='action' else parts['scope']
            before=self.posts();actual=source.native.send;seen=[]
            def sending(query):
                result=actual(query);seen.append(query['commandId'])
                if len(seen)==1:
                    value=owner.store.read();self.assertIsNotNone(value);owner.store.write(value,value)
                return result
            source.native.send=sending
            try:
                with self.assertRaises(NativeUIError),source.input_sequence(actions.inputs.store):actions.current('immutable-'+role)
            finally:source.native.send=actual
            self.assertEqual(1,len(seen));self.assertEqual(before,self.posts());self.assert_released(source)

    def test_action_wal_same_body_replacement_remains_outside_mutable_exclusions(self):self.immutable_owner_fault('action')
    def test_scope_wal_same_body_replacement_remains_outside_mutable_exclusions(self):self.immutable_owner_fault('scope')

    def test_private_frame_memory_drift_refuses_before_delivery_and_failed_reuse_is_invalidated(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();ref=deepcopy(source.state['records'][0]);original=source.frame(ref)
            with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                source._round[2][0]['label']='forged-private-frame'
                source.guard_saved_state()
            self.assertEqual(0,len(source._cache));self.assert_released(source)
            self.assertEqual(original,source.frame(ref));self.assertEqual(before,self.posts())

    def test_replaced_reader_during_sequence_refuses_and_restored_reader_rederives_originals(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();original=source.frame
            try:
                with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                    source.frame=lambda _reference:None
                    source.guard_originals()
            finally:source.frame=original
            self.assertEqual(0,len(source._cache));self.assert_released(source)
            self.assertTrue(source.frame(source.state['records'][-1])['originals']['keys']['source']['complete'])
            self.assertEqual(before,self.posts())

    def test_substituted_reader_at_entry_keeps_literal_current_round_and_original_error(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();original=source.frame;first=OSError('Declared original substituted reader')
            def changed(_reference):raise first
            source.frame=changed
            try:
                with source.input_sequence(parts['actions'].inputs.store):
                    self.assertIsNone(source._input_sequence)
                    with self.assertRaises(OSError) as caught:parts['actions'].current('literal-current-reader')
            finally:source.frame=original
            self.assertIs(first,caught.exception);self.assertEqual(before,self.posts());self.assert_released(source)

    def test_foreign_mutable_handle_cannot_borrow_the_original_input_lease(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];inputs=parts['actions'].inputs;before=self.posts()
            with source.input_sequence(inputs.store):
                with self.assertRaises(NativeUIError),source.input_round(PrivateFeatureState(inputs.store.path)):pass
            self.assertEqual(before,self.posts());self.assert_released(source)

    def test_original_header_pid_drift_still_refuses_before_native_or_product_input(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();pid=source.pid
            try:
                with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                    source.pid+=1;source.guard_originals()
            finally:source.pid=pid
            self.assertEqual(before,self.posts());self.assert_released(source)

    def test_new_unknown_member_inside_sequence_is_not_added_to_original_membership(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts()
            with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                path=source.store.path.parent/'world-sequence-unowned-original.bin';path.write_bytes(b'actual unknown original');path.chmod(0o600)
                source.guard_originals()
            self.assertEqual(before,self.posts());self.assert_released(source)

    def test_same_bytes_original_carrier_inode_replacement_is_not_hidden_by_sequence_reuse(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts()
            with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                frame=source.frame(source.state['records'][0]);retained=source.record_store(frame['index']).read()
                from adapters.script_feature.history import unpack
                part=unpack(retained['payload'])[0]['originals']['keys'];path=source.parts.paths(part)[0]
                raw=path.read_bytes();original=path.stat().st_ino
                replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
                self.assertNotEqual(original,path.stat().st_ino);self.assertEqual(raw,path.read_bytes())
                source.guard_originals()
            self.assertEqual(before,self.posts());self.assert_released(source)

    def test_callable_changed_by_original_entry_guard_cannot_become_post_decode_baseline(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();actual_guard=source.guard;actual_frame=source.frame;seen=[]
            def changed(_reference):raise AssertionError('Changed frame must not be called')
            def guard():
                result=actual_guard()
                if not seen:seen.append(True);source.frame=changed
                return result
            source.guard=guard
            try:
                with self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                    self.fail('A changed entry callable must not publish a reuse context')
            finally:source.guard=actual_guard;source.frame=actual_frame
            self.assertEqual([True],seen);self.assertEqual(0,len(source._cache))
            self.assertEqual(before,self.posts());self.assert_released(source)

    def test_same_function_foreign_bound_receivers_refuse_before_any_foreign_method_or_input(self):
        from types import MethodType
        foreign_calls=[]
        class ForeignReceiver:
            def __eq__(self,_other):
                foreign_calls.append('equality');raise AssertionError('Receiver equality must not execute')
            def __getattribute__(self,name):
                foreign_calls.append(name);raise AssertionError('Foreign receiver method must not execute: '+name)
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts()
            for owner,name in ((source,'frame'),(source.native,'read'),(source.parts.snapshot,'packet'),
                    (source.parts,'read_frame'),(source.store,'read'),(source.lock,'assert_held')):
                original=getattr(owner,name);foreign=ForeignReceiver()
                self.assertIsNotNone(getattr(original,'__func__',None))
                try:
                    with self.subTest(method=name),self.assertRaises(NativeUIError),source.input_sequence(parts['actions'].inputs.store):
                        setattr(owner,name,MethodType(original.__func__,foreign))
                        # Assert the complete body AND all mandatory exits.
                        # An original NativeUIError may retain a later exit
                        # AssertionError as a note; assertRaises alone would
                        # therefore miss an actual foreign invocation.
                        source.guard_originals()
                finally:setattr(owner,name,original)
                self.assertEqual([],foreign_calls)
                self.assertEqual(0,len(source._cache));self.assert_released(source)
            self.assertEqual(before,self.posts())

    def test_prebound_foreign_receivers_keep_literal_entry_without_invoking_foreign_methods(self):
        from types import MethodType
        class ForeignReceiver:
            def __eq__(self,_other):raise AssertionError('Receiver equality must not execute')
            def __getattribute__(self,name):raise AssertionError('Foreign receiver must not execute: '+name)
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts()
            for owner,name in ((source,'frame'),(source.native,'read'),(source.parts.snapshot,'packet'),
                    (source.parts,'read_frame'),(source.store,'read'),(source.lock,'assert_held')):
                original=getattr(owner,name)
                try:
                    setattr(owner,name,MethodType(original.__func__,ForeignReceiver()))
                    with self.subTest(method=name),source.input_sequence(parts['actions'].inputs.store):
                        self.assertIsNone(source._input_sequence);self.assertIsNone(source._round)
                finally:setattr(owner,name,original)
                self.assert_released(source)
            self.assertEqual(before,self.posts())

    def test_body_error_stays_original_when_actual_immutable_inventory_also_changes(self):
        with self.f.primary.held():
            parts=self.parts();source=parts['source'];before=self.posts();first=OSError('Declared original sequence failure')
            with self.assertRaises(OSError) as caught:
                with source.input_sequence(parts['actions'].inputs.store):
                    store=parts['actions'].store;value=store.read();store.write(value,value)
                    raise first
            self.assertIs(first,caught.exception)
            self.assertIn('Source input-sequence validation also failed; original error preserved.',first.__notes__)
            self.assertIn('Source append-boundary validation also failed; original error preserved.',first.__notes__)
            self.assertEqual(before,self.posts());self.assert_released(source)


if __name__=='__main__':unittest.main()
