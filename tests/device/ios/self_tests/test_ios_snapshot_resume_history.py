"""Original-only resumed Snapshot graph after all live model ports refuse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import readonly
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import feature_observation
from ios.adapters.snapshot_resume_background import SnapshotResumeBackground
from ios.adapters.snapshot_resume_rendered_review_owner import SnapshotResumeRenderedReviewOwner
from ios.self_tests.snapshot_resume_os_domain import ResumeOSDomain,RESUME,RUN


class SnapshotResumeHistoryTests(unittest.TestCase):
    def completed(self):
        d=ResumeOSDomain(self)
        with d.runtime.rendered_resume_owner('test-only',RUN,d.resume_client(),RESUME,
                epoch_ms=d.capture.epoch,monotonic=d.capture.mono,sleep=d.capture.sleep) as owner:
            result=owner.acquire(RESUME);bundle=deepcopy(owner.os_bridge.os.gate.bundle)
            scope=dict(store=owner.store,lock=owner.lock,binding=owner.binding,run=RUN,fixture_url=owner.page.fixture_url,bundle=bundle)
        return d,result,scope

    def archive(self,scope):return SnapshotResumeRenderedReviewOwner.archive(**scope)

    def pins(self,d):
        return {p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.is_file()}

    def test_actual_completed_os_page_and_new_screen_proof_reopens_without_sdk_sources_clocks_or_writes(self):
        d,result,scope=self.completed();pins=self.pins(d);calls=(deepcopy(d.os_commands),d.screen_calls,d.ctx.native.sequence)
        def forbidden(*_a,**_k):raise AssertionError('Historical resume touched live authority')
        d.runtime._sources=d.installed.adapter._candidate_guard=forbidden
        d.canonical.client.call=d.canonical.client.execute=forbidden
        with scope['lock'].held(),readonly(),patch.object(feature_observation,'post_request',forbidden),\
                patch.object(PrivateFeatureState,'write',side_effect=forbidden):
            archived=self.archive(scope);self.assertTrue(archived.historical and archived.os_bridge.historical)
            self.assertIsNone(archived.os_bridge.os);self.assertTrue(archived.page.historical and archived.images.historical)
            self.assertEqual(result,archived.proof());self.assertFalse(archived.os_bridge.proof()['originalOSBridgeRequired'])
        self.assertEqual(pins,self.pins(d));self.assertEqual(calls,(d.os_commands,d.screen_calls,d.ctx.native.sequence))

    def test_historical_os_and_rendered_mutators_refuse_before_any_effect(self):
        d,result,scope=self.completed();pins=self.pins(d)
        with scope['lock'].held():
            archived=self.archive(scope);os=archived.os_bridge
            for call in (lambda:archived.acquire(RESUME),archived.save,archived.screen,
                    lambda:archived.observation('before','beforeCount'),lambda:os.act(RESUME),os.save,os.status,
                    lambda:os.wait(True),lambda:archived.images.capture(RESUME),archived.images.cleanup):
                with self.assertRaises(NativeUIError):call()
            self.assertEqual(result,archived.proof())
        self.assertEqual(pins,self.pins(d));self.assertEqual(2,len(d.os_commands));self.assertEqual(2,d.screen_calls)

    def test_foreign_independent_bundle_process_run_or_fixture_cannot_relabel_original_resume(self):
        _d,_result,scope=self.completed()
        for kind in ('bundle','process','run','fixture'):
            bad=dict(scope)
            if kind=='bundle':bad['bundle']=dict(scope['bundle'],bundleSha256='9'*64)
            elif kind=='process':bad['binding']=dict(scope['binding'],processIdentity='43')
            elif kind=='run':bad['run']='b'*32
            else:bad['fixture_url']='https://foreign.invalid/feature-fixture/v1/runs/'+RUN+'/'
            with self.subTest(kind=kind),scope['lock'].held(),self.assertRaises((ValueError,NativeUIError)):
                self.archive(bad).proof()

    def test_same_byte_new_resume_image_inode_refuses_historical_original_proof(self):
        d,_result,scope=self.completed()
        with scope['lock'].held():
            archived=self.archive(scope);path=archived.images.root/archived.images.rows[-1]['name'];raw=path.read_bytes();inode=path.stat().st_ino
        path.rename(path.with_name('retained-original-'+path.name));path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(inode,path.stat().st_ino)
        with scope['lock'].held(),self.assertRaises(NativeUIError):self.archive(scope).proof()
        self.assertEqual(2,d.screen_calls);self.assertEqual(2,len(d.os_commands))

    def test_changed_in_memory_os_verdict_cannot_replace_rederived_originals(self):
        _d,_result,scope=self.completed()
        with scope['lock'].held():
            archived=self.archive(scope);archived.os_bridge.state['result']['exactOneBackgroundAndActivation']=False
            with self.assertRaises(NativeUIError):archived.proof()

    def test_changed_in_memory_rendered_counts_cannot_bypass_full_saved_decoder(self):
        _d,_result,scope=self.completed()
        with scope['lock'].held():
            archived=self.archive(scope);archived.state['beforeCount']=0
            with self.assertRaises(NativeUIError):archived.proof()

    def test_historical_rendered_archive_refuses_saved_intermediate_phase(self):
        _d,_result,scope=self.completed()
        with scope['lock'].held():
            archived=self.archive(scope);state=deepcopy(archived.state)
            state.update(phase='after-saved',result=None)
            intermediate=archived.envelope(state);archived.decode(intermediate)
            scope['store'].write(intermediate,archived.previous)
            with self.assertRaises(NativeUIError):self.archive(scope)
