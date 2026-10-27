"""Same actual PNG through Combined upload and the existing Share/Return path."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney,phase_prefix
from ios.adapters import normal_input
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests.snapshot_causal_parent_domain import CausalParentDomain
from ios.self_tests.snapshot_combined_upload_return_domain import CombinedUploadReturnFlow
from ios.self_tests import test_ios_snapshot_page_return as old_return


def phase(activations):
    return dict(fixturePhaseVersion=1,instance='e'*32,sequence=len(activations),requestId=format(len(activations),'032x'),runId='a'*32,area='snapshots',
        capturedEpochMs=20000,active=True,createdEpochMs=19000,retiredEpochMs=None,activations=activations)


class SnapshotCombinedJourneyContractTests(unittest.TestCase):
    def test_phase_prefix_keeps_original_birth_and_all_prior_activations(self):
        first=dict(sequence=1,ticket='1'*32,activatedEpochMs=19500,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png')))
        second=dict(sequence=2,ticket='2'*32,activatedEpochMs=19600,stimulus=dict(verb='upload',inputs={}))
        before=phase([first]);after=phase([first,second]);phase_prefix(before,after,'a'*32)
        for mutation in (lambda value:value.update(instance='7'*32),lambda value:value['activations'][0].update(ticket='8'*32),
                lambda value:value.update(sequence=before['sequence']),lambda value:value.update(requestId=before['requestId']),
                lambda value:value.update(capturedEpochMs=before['capturedEpochMs']-1)):
            changed=deepcopy(after);mutation(changed)
            with self.assertRaises(NativeUIError):phase_prefix(before,changed,'a'*32)
        with self.assertRaises(NativeUIError):phase_prefix(before,before,'a'*32)
        phase_prefix(before,before,'a'*32,strict=False)
    def test_opposite_or_unowned_profiles_refuse_before_any_child_proof(self):
        with self.assertRaises(NativeUIError):SnapshotCombinedJourney(object(),object())
        returned=object.__new__(SnapshotPageReturnOwner);returned.historical=True;returned.combined=False
        with self.assertRaises(NativeUIError):SnapshotCombinedJourney(returned,object())


class SnapshotCombinedJourneyAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=unittest.TestCase();cls.addClassCleanup(cls.fixture.doCleanups);cls.domain=CausalParentDomain(cls.fixture)
        cls.domain.prepare_native()
        with cls.domain.backend_owner() as backend:cls.expected=backend.original()
        with cls.domain.capture_owner() as capture:
            cls.copy_index=next(row['index'] for row in capture.state['slots'] if row['kind']=='filework' and row['label']=='copy-filework')
            cls.copy_frame=deepcopy(capture.history('filework',cls.copy_index).historical())
            probe=capture.observed('integration-later-filework','filework');cls.later=deepcopy(probe.historical())
        cls.commands=deepcopy(cls.domain.commands);cls.private_calls=deepcopy(cls.domain.private_calls)
    def test_current_capture_tail_cannot_replace_immutable_upload4_capture_boundary(self):
        d=self.domain
        with d.backend_owner() as backend:
            native=backend.native;self.assertNotEqual(native.capture.state['nativeTail'],native.capture_tail())
            self.assertEqual(self.copy_frame['acquisition']['nativeAfter'],native.capture_tail());self.assertEqual(self.expected,backend.proof())
        self.assertEqual(self.commands,d.commands);self.assertEqual(self.private_calls,d.private_calls);self.assertEqual(1,d.upload_count)
    def test_later_actual_native_after_cannot_be_loaned_to_old_copy_original(self):
        with self.domain.backend_owner() as backend:
            native=backend.native;read=native.capture.history;changed=deepcopy(self.copy_frame)
            changed['acquisition']['nativeAfter']=deepcopy(self.later['acquisition']['nativeAfter'])
            def borrowed(kind,index):
                child=read(kind,index)
                if kind=='filework' and index==self.copy_index:child.historical=lambda:deepcopy(changed)
                return child
            with patch.object(native.capture,'history',side_effect=borrowed),self.assertRaises(NativeUIError):native.capture_tail()
        self.assertEqual(1,self.domain.upload_count)


class SnapshotCombinedEarlyNameTests(unittest.TestCase):
    def test_actual_name_restoration_precedes_destinations_without_changing_png_or_repeating_input(self):
        d=CausalParentDomain(self)
        with d.capture_owner() as capture:
            result=capture.capture('f'*32);path=d.f.f.h.path;before=(path.stat().st_ino,path.read_bytes())
            restored=capture.restore_name_before_destination();requests=deepcopy(d.f.input_native.requests)
            self.assertEqual(restored,capture.restore_name_before_destination());self.assertEqual(result,capture.result())
            self.assertEqual(requests,d.f.input_native.requests);self.assertEqual('',d.f.input_native.name)
            self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(0,d.upload_count)
    def test_lost_actual_name_edit_return_recovers_original_before_current_restored_field_check(self):
        d=CausalParentDomain(self)
        with d.capture_owner() as capture:capture.capture('f'*32)
        send=normal_input.urlopen;lost=[]
        def actual(request,timeout):
            query=json.loads(request.data);result=send(request,timeout)
            if query['operation']=='edit' and query['input']['operation']=='replace' and query['input'].get('text')=='' and not lost:
                lost.append(query['input']['commandId']);raise OSError('Declared actual name edit return lost after native delivery')
            return result
        with patch.object(normal_input,'urlopen',side_effect=actual):
            with d.capture_owner() as capture,self.assertRaises((OSError,NativeUIError)):capture.restore_name_before_destination()
            self.assertEqual('',d.f.input_native.name)
            with d.capture_owner() as capture:
                restored=capture.restore_name_before_destination();self.assertTrue(capture.state['restored'])
                capture.restoration_original();self.assertIsNotNone(restored)
        edits=[row for row in d.f.input_native.requests if row['operation']=='edit' and row['input']['operation']=='replace' and row['input'].get('text')=='']
        self.assertEqual(1,len(edits));self.assertEqual([edits[0]['input']['commandId']],lost)
        self.assertEqual(0,d.upload_count);self.assertTrue(d.f.f.h.path.exists())


class SnapshotCombinedJourneyWholeTests(unittest.TestCase):
    def test_one_main_page_pending_png_upload4_backend4_share_archive_cleanup_and_return(self):
        with patch.object(old_return,'PageReturnFlow',CombinedUploadReturnFlow):d,host=old_return.SnapshotPageReturnOwnerTests.prepared(self)
        before=(host.stat().st_ino,host.read_bytes());self.assertEqual(4,d.backend_result['snapshotUploadBackendResultVersion'])
        self.assertEqual(1,d.main.upload_count);self.assertEqual(1,d.share_count)
        with d.return_owner() as returned:
            restored=returned.restore();self.assertEqual(2,restored['snapshotPageReturnedVersion'])
        with returned.lock.held(),returned.end.share.archive_lock.held():
            archived=SnapshotPageReturnOwner.history(returned.page,returned.files,returned.end,combined=True)
            native=IOSSnapshotUploadOwner.history(PrivateFeatureState(archived.root/'snapshot-upload-owner.json'),archived.lock,
                archived.binding,archived.run,archived.fixture_url,combined=True,frontend_http=True,frontend_caller=True)
            backend=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.main.domain_policy)
            calls,commands,private=deepcopy(d.main.ctx.files.reads),deepcopy(d.main.commands),deepcopy(d.main.private_calls)
            with (patch.object(d.archive,'execute',side_effect=AssertionError('Historical SDK command')),
                    patch.object(d.archive,'call',side_effect=AssertionError('Historical SDK read')),
                    patch.object(d.primary_ui,'call',side_effect=AssertionError('Historical UIKit read')),
                    patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical write'))):
                fact=SnapshotCombinedJourney(archived,backend).proof();self.assertTrue(fact['sameOriginalPNGJoined'])
                self.assertTrue(fact['originalMainAndPhasePrefixesJoined']);self.assertTrue(fact['wholeFeatureRequired'])
            self.assertEqual(calls,d.main.ctx.files.reads);self.assertEqual(commands,d.main.commands);self.assertEqual(private,d.main.private_calls)
        self.assertEqual(before,(host.stat().st_ino,host.read_bytes()));self.assertFalse(d.main.f.f.h.path.exists())
        self.assertEqual((2,1,1,1,1),(d.main.capture_count,d.main.cancel_count,d.main.png_count,d.main.upload_count,d.share_count))
        self.assertEqual((1,1),(d.archive.stop_calls,d.archive.delete_calls))


if __name__=='__main__':unittest.main()
