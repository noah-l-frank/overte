"""Actual fixture/phase/CAS code; consumed input rows are explicit metadata seams.

No 25-step target effects, native cleanup or product input is claimed here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
from adapters.chat_journey.flow_inputs import recipe
from adapters.chat_journey.phase_fence import ChatPhaseFence
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same
from self_tests import test_chat_witness as witness_seams
from self_tests.test_native_chat_observation import RUN


class ChatCleanupAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.h=witness_seams.WitnessTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.baseline();self.flow=self.h.flow
        # The input owner metadata is fully consumed. Model references below
        # are metadata seams; real Dispatcher/native proofs remain separate.
        with self.flow.session():
            for index,step in enumerate(recipe(RUN)[1:],1):
                ticket=uuid.uuid4().hex;self.h.journal.activate(RUN,ticket,step['verb'],step['inputs'])
                before=self.flow.source.read()['status'];after=self.flow.source.read(before)['status']
                refs=[dict(index=index,ticket=uuid.uuid4().hex,queries=[uuid.uuid4().hex for _ in range(4)],
                    epochs=[int(before['capturedEpochMs'])]*4) for _ in range(2)]
                self.flow.rows.append(dict(ticket=ticket,**deepcopy(step),phase='completed',before=before,after=after,references=refs))
                self.flow.save()
        self.store=PrivateFeatureState(self.h.h.h.root/'cleanup-admission.json')
        self.owner=ChatCleanupAdmission(self.flow,self.store)
    def activate(self,verb='cleanup'):
        ticket=uuid.uuid4().hex;self.h.journal.activate(RUN,ticket,verb,{})
        return ticket
    def queries(self):return [len(value.commands) for value in (self.h.h.h.primary,self.h.h.h.peer,self.h.h.h.view,self.h.h.h.native)]

    def test_actual_cleanup_prefix_is_admitted_once_and_fenced_independently_without_qt_or_input(self):
        ticket=self.activate();before=self.queries()
        with self.flow.session():
            packet=self.owner.admit();fence=ChatPhaseFence(self.flow,cleanup=self.owner)
            fence.mark();first=fence.check();second=fence.check()
            self.assertTrue(same(packet['activations'],first['activations']))
            self.assertEqual(ticket,second['activations'][-1]['ticket']);self.assertEqual(27,len(second['activations']))
            self.assertNotEqual(first['requestId'],second['requestId'])
            with self.assertRaises(NativeUIError):ChatPhaseFence(self.flow).mark()
        self.assertEqual(before,self.queries());self.assertEqual('admitted',self.store.read()['phase'])
        with self.assertRaises(NativeUIError):ChatCleanupAdmission(self.flow,self.store)

    def test_incomplete_flow_cannot_admit_cleanup_even_with_actual_cleanup_activation(self):
        self.activate();self.flow.rows.pop()
        with self.flow.session():
            self.flow.save()
            with self.assertRaises(NativeUIError):self.owner.admit()
        self.assertIsNone(self.store.read());self.assertTrue(self.owner.failed)

    def test_wrong_actual_phase_or_changed_original_prefix_is_retained_without_adoption(self):
        for fault in ('wrong-phase','prefix'):
            if fault!='wrong-phase':self.setUp()
            self.activate('open' if fault=='wrong-phase' else 'cleanup')
            if fault=='prefix':self.h.journal.runs[RUN]['phaseActivations'][0]['ticket']=uuid.uuid4().hex
            with self.subTest(fault=fault),self.flow.session(),self.assertRaises((ValueError,NativeUIError)):self.owner.admit()
            self.assertEqual('reading',self.store.read()['phase'])

    def test_retired_or_replaced_cleanup_phase_prevents_transport_after_original_child_cas(self):
        for fault in ('retired','replaced'):
            if fault!='retired':self.setUp()
            self.activate()
            with self.flow.session():
                self.owner.admit();fence=ChatPhaseFence(self.flow,cleanup=self.owner);fence.mark()
                if fault=='retired':
                    row=self.h.journal.runs.pop(RUN);row['retiredEpochMs']=self.h.h.native.epoch;self.h.journal.retired_phases[RUN]=row
                else:self.activate()
                with self.subTest(fault=fault),self.assertRaises((ValueError,NativeUIError)):fence.check()
            self.assertTrue(fence.failed);self.assertIsNotNone(self.store.read())

    def test_slow_initial_or_final_cas_cannot_be_refreshed_by_new_phase_response(self):
        for final in (False,True):
            for clock in ('host','native'):
                self.setUp();self.activate();write=self.store.write
                def slow(value,previous):
                    write(value,previous)
                    if (value['phase']=='admitted')==final:
                        if clock=='host':self.h.h.native.host+=2
                        else:self.h.h.native.epoch+=2000
                self.store.write=slow
                with self.subTest(final=final,clock=clock),self.flow.session(),self.assertRaises((ValueError,NativeUIError)):self.owner.admit()
                original=self.store.read();self.assertIsNotNone(original);self.assertTrue(self.owner.failed)
                with self.flow.session(),self.assertRaises((ValueError,NativeUIError)):self.owner.admit()
                self.assertEqual(original,self.store.read())

    def test_lost_original_cleanup_receipt_is_not_overwritten_or_readmitted(self):
        self.activate();write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='admitted':raise OSError('Explicit lost original admission receipt')
        self.store.write=lost
        with self.assertRaises(NativeUIError),self.flow.session():self.owner.admit()
        original=self.store.read();self.assertEqual('admitted',original['phase'])
        with self.assertRaises(NativeUIError),self.flow.session():self.owner.admit()
        self.assertEqual(original,self.store.read())


if __name__=='__main__':unittest.main()
