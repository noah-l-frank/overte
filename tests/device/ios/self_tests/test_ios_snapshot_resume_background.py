"""Real canonical Snapshot/OS/file ownership over declared lower host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_resume_page import SnapshotResumePage
from ios.self_tests.snapshot_resume_os_domain import ResumeOSDomain,RESUME


class SnapshotResumeBackgroundTests(unittest.TestCase):
    def test_actual_canonical_capture_review_home_activation_and_new_page_keep_one_process_and_input_cursor(self):
        d=ResumeOSDomain(self);before=(d.installed.sessions,d.installed.launches);clicks=deepcopy(d.clicks)
        with d.resumed() as owner:
            result=owner.act(RESUME)
            self.assertTrue(result['sameProcessAndInputCursor'] and result['exactOneBackgroundAndActivation'])
            self.assertFalse(result['originalOSBridgeRequired'])
            self.assertTrue(all(result[key]for key in ('renderedResumeRequired','independentActorSceneRequired',
                'destinationCompositionRequired','pairedCleanupRequired','wholeFeatureRequired')))
            self.assertEqual('complete',owner.state['phase'])
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],d.os_commands)
        self.assertEqual(before,(d.installed.sessions,d.installed.launches));self.assertEqual(clicks,d.clicks)
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(1,d.screen_calls)
        d.block_native=True;pulls=deepcopy(d.native_pulls);commands=deepcopy(d.capture.commands)
        with d.resumed() as owner:self.assertEqual(result,owner.act(RESUME))
        self.assertEqual(pulls,d.native_pulls);self.assertEqual(commands,d.capture.commands)
        self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.screen_calls)

    def test_lost_delivered_home_reopens_in_background_without_native_queries_or_second_home(self):
        d=ResumeOSDomain(self);d.os_fault='lost-home'
        with d.resumed() as owner,self.assertRaises(OSError):owner.act(RESUME)
        self.assertFalse(d.installed.process['foreground']);self.assertEqual(['mobile: backgroundApp'],d.os_commands)
        d.block_native=True;before=deepcopy(d.native_pulls)
        with d.resumed() as owner:
            self.assertEqual(before,d.native_pulls);self.assertEqual('background-issued',owner.state['phase'])
            d.block_native=False;d.os_fault=None;result=owner.act(RESUME)
        self.assertFalse(result['originalOSBridgeRequired']);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_lost_delivered_activation_reopens_existing_foreground_without_another_activation_or_session(self):
        d=ResumeOSDomain(self);d.os_fault='lost-activation';births=(d.installed.sessions,d.installed.launches)
        with d.resumed() as owner,self.assertRaises(OSError):owner.act(RESUME)
        self.assertTrue(d.installed.process['foreground']);self.assertEqual(2,len(d.os_commands));d.os_fault=None
        with d.resumed() as owner:result=owner.act(RESUME)
        self.assertFalse(result['originalOSBridgeRequired']);self.assertEqual(2,len(d.os_commands))
        self.assertEqual(births,(d.installed.sessions,d.installed.launches))

    def test_ignored_home_remains_issued_and_never_becomes_activation_or_another_home(self):
        d=ResumeOSDomain(self);d.os_fault='ignored-home'
        for _attempt in range(2):
            with d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
            self.assertEqual('background-issued',owner.state['phase'])
        self.assertEqual(['mobile: backgroundApp'],d.os_commands);self.assertTrue(d.installed.process['foreground'])

    def test_ignored_activation_remains_backgrounded_and_cannot_query_native_or_resend(self):
        d=ResumeOSDomain(self);d.os_fault='ignored-activation'
        with d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
        self.assertFalse(d.installed.process['foreground']);before=deepcopy(d.native_pulls);d.block_native=True
        with d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
        self.assertEqual(before,d.native_pulls);self.assertEqual(2,len(d.os_commands));self.assertEqual('foreground-issued',owner.state['phase'])

    def test_os_return_without_original_native_transition_cannot_complete(self):
        d=ResumeOSDomain(self);d.os_fault='missing-native-transition'
        with d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
        self.assertEqual('after-issued',owner.state['phase']);self.assertIsNone(owner.state['result'])
        self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_extra_native_transition_or_relaunch_or_replaced_snapshot_root_is_not_the_original_resume(self):
        for fault in ('extra-transition','relaunch','root-replaced'):
            d=ResumeOSDomain(self);d.os_fault=fault
            with self.subTest(fault=fault),d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
            self.assertIsNone(owner.state['result']);self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_saved_after_page_lost_parent_return_recovers_original_inode_without_os_or_native_repetition(self):
        d=ResumeOSDomain(self);save=SnapshotResumePage.save
        def lost(page):
            if len(page.state['records'])==2:raise OSError('Actual saved resumed Page before parent CAS return')
            return save(page)
        with patch.object(SnapshotResumePage,'save',lost):
            with d.resumed() as owner,self.assertRaises(OSError):owner.act(RESUME)
        originals={p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('ios-snapshot-resume-page-frame-')}
        self.assertEqual(2,len(originals));pulls=deepcopy(d.native_pulls);d.block_native=True
        # Foreground factory verifies the existing installed-code bundle. It
        # may read that bundle original; the interrupted Page itself is adopted
        # from its actual complete saved file and may issue no native/UI query.
        with d.resumed() as owner:result=owner.act(RESUME)
        self.assertFalse(result['originalOSBridgeRequired']);self.assertEqual(pulls,d.native_pulls)
        self.assertEqual(originals,{p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.name.startswith('ios-snapshot-resume-page-frame-')})
        self.assertEqual(2,len(d.os_commands));self.assertEqual(1,d.capture.capture_count)

    def test_failed_durable_os_intent_cannot_send_home(self):
        d=ResumeOSDomain(self)
        with d.resumed() as owner,patch.object(owner.store,'write',side_effect=OSError('Actual failed OS intent CAS')):
            with self.assertRaises(OSError):owner.act(RESUME)
        self.assertEqual([],d.os_commands);self.assertTrue(d.installed.process['foreground'])

    def test_changed_actual_process_while_backgrounded_refuses_before_native_read_or_activation(self):
        d=ResumeOSDomain(self);d.os_fault='lost-home'
        with d.resumed() as owner,self.assertRaises(OSError):owner.act(RESUME)
        original=owner.store.path.read_bytes();pulls=deepcopy(d.native_pulls);d.block_native=True
        d.installed.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):
            with d.resumed():pass
        self.assertEqual(original,owner.store.path.read_bytes());self.assertEqual(pulls,d.native_pulls)
        self.assertEqual(['mobile: backgroundApp'],d.os_commands)

    def test_replaced_candidate_refuses_original_resume_before_home(self):
        d=ResumeOSDomain(self);d.installed.artifact.write_bytes(b'Actual foreign candidate bytes')
        with self.assertRaises((ValueError,NativeUIError)):
            with d.resumed():pass
        self.assertEqual([],d.os_commands)

    def test_unadmitted_resume_input_original_blocks_before_any_home_and_stays_retained(self):
        d=ResumeOSDomain(self);path=d.ctx.root/'snapshot-resume-native-inputs-frame-unadmitted.json'
        path.write_bytes(b'');path.chmod(0o600);original=(path.stat().st_ino,path.read_bytes())
        with d.resumed() as owner,self.assertRaises(NativeUIError):owner.act(RESUME)
        self.assertEqual([],d.os_commands);self.assertEqual(original,(path.stat().st_ino,path.read_bytes()))
