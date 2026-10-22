"""Composed actual owned files/jobs; native clocks and SDK explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_file_absence as source
from ios.self_tests.snapshot_cleanup_fixture import CleanupDomain
from ios.self_tests.test_ios_snapshot_owned_files import PREFIX


class SnapshotFileAbsence(unittest.TestCase):
    def setUp(self):self.d=CleanupDomain(self)
    def sample(self,group,guard=lambda:True):
        f=self.d.f
        return source.sample(*group,guard=guard,epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
    def quiet(self,delay=1600,capture=True):
        self.d.prepare(capture);groups=[];samples=[]
        for index in range(3):
            if index:self.d.f.model.now+=delay
            group=self.d.group();groups.append(group);samples.append(self.sample(group))
        return groups,samples
    def test_real_unlink_empty_manifests_and_actual_job_death_join_without_whole_cleanup_claim(self):
        with self.d.f.lock.held():
            groups,samples=self.quiet();fact=source.quiet(groups,samples)
            self.assertTrue(fact['pairedFeatureCleanupRequired']);self.assertTrue(fact['scriptCaptureAndDestinationQuietRequired'])
            self.assertEqual(3000,fact['fileChannelQuietMilliseconds']);self.assertEqual([],self.d.file_rows(PREFIX))
            self.assertTrue(self.d.f.model.jobs)
            def forbidden(*_a,**_k):raise AssertionError('Historical quiet touched SDK')
            self.d.f.feature.guard=self.d.f.feature.original=self.d.f.native=forbidden
            self.assertEqual(fact,source.quiet(groups,samples))
    def test_cancelled_before_output_still_needs_original_empty_reads_and_quiet(self):
        with self.d.f.lock.held():
            groups,samples=self.quiet(capture=False);self.assertFalse(self.d.f.model.files)
            source.quiet(groups,samples)
            with self.assertRaises(NativeUIError):source.quiet(groups[:2],samples[:2])
    def test_short_quiet_and_forged_old_host_envelope_cannot_become_green(self):
        with self.d.f.lock.held():
            groups,samples=self.quiet(delay=1000)
            with self.assertRaises(NativeUIError):source.quiet(groups,samples)
            changed=deepcopy(samples);changed[0]['hostAfterEpochMs']-=2000;changed[0]['hostAfterMonotonic']-=2
            with self.assertRaises(NativeUIError):source.quiet(groups,changed)
    def test_cached_real_manifest_functor_blocks_positive_absence_after_empty_result(self):
        with self.d.f.lock.held():
            self.d.prepare();self.d.hold_reads=True;group=self.d.group()
            self.assertEqual([],group[0][0].historical()['packet']['files'])
            self.assertTrue(group[1].historical()['packet']['source']['jobs'][-1]['alive'] or self.d.reads)
            with self.assertRaises(NativeUIError):self.sample(group)
    def test_reappearing_actual_file_is_not_hidden_by_previous_empty_original(self):
        with self.d.f.lock.held():
            self.d.prepare();group=self.d.group();self.sample(group)
            path=self.d.f.root/(PREFIX+'-snap_2_2.png');path.write_bytes(b'actual unexpected output')
            next_group=self.d.group()
            with self.assertRaises(NativeUIError):self.sample(next_group)
    def test_real_symlink_or_multiple_link_output_cannot_be_read_as_a_regular_capture(self):
        for kind in ('symlink','hardlink'):
            with self.subTest(kind=kind),self.d.f.lock.held():
                target=self.d.f.root/('ordinary-'+kind);target.write_bytes(b'private non-capture bytes')
                path=self.d.f.root/(PREFIX+'-snap_9_9.png')
                if kind=='symlink':path.symlink_to(target)
                else:path.hardlink_to(target)
                try:
                    with self.assertRaises(NativeUIError):self.d.file_rows(PREFIX)
                    self.assertEqual(b'private non-capture bytes',target.read_bytes())
                finally:path.unlink();target.unlink()

    def test_ignored_native_list_cannot_reuse_a_previous_empty_reply_nonce(self):
        with self.d.f.lock.held():
            self.d.prepare(capture=False);self.d.ignore_list=True
            with self.assertRaises(NativeUIError):self.d.manifest()
    def test_unowned_extra_read_during_quiet_and_reused_group_both_fail(self):
        with self.d.f.lock.held():
            self.d.prepare();groups=[];samples=[]
            for index in range(3):
                if index:self.d.f.model.now+=1600
                if index==1:
                    q=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='snapshot-files',operation='list',prefix=PREFIX)
                    self.d.list_body(q);self.d.reads.clear()
                group=self.d.group();groups.append(group);samples.append(self.sample(group))
            with self.assertRaises(NativeUIError):source.quiet(groups,samples)
            with self.assertRaises(NativeUIError):source.quiet([groups[0]]*3,[samples[0]]*3)
    def test_current_final_guard_includes_slow_history_validation_and_actual_original_mutation(self):
        with self.d.f.lock.held():
            self.d.prepare();group=self.d.group();calls=[0]
            def slow():
                calls[0]+=1
                if calls[0]==2:self.d.f.model.now+=2000
                return True
            with self.assertRaises(NativeUIError):self.sample(group,slow)
            work=group[1];parent=work.state['rawParts'];path=work.parts().store.path(parent['chunks'][0])
            with path.open('ab') as stream:stream.write(b' ')
            with self.assertRaises(NativeUIError):source.original_sample(*group)


if __name__=='__main__':unittest.main()
