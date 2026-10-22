"""Durable marker input-owner seams; Qt/native/SDK sources remain synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.create_marker_scope import CreateMarkerScope
from ios.adapters.create_marker_files import OwnedCreateMarkerFiles
from ios.adapters.create_originals import IOSCreateOriginals
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class MarkerScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()

    def owner(self,binding=BINDING):
        scope=object.__new__(CreateMarkerScope);scope.root=self.root;scope.lock=self.lock
        scope.run,scope.role,scope.binding=RUN,'primary',deepcopy(binding);scope.pid=int(binding['processIdentity'])
        scope.guard=lambda:True;scope.failed=False;scope.frames=[];scope.fixture_url='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
        scope.ticket='a'*32;scope.store=PrivateFeatureState(self.root/'ios-create-primary-marker.json')
        scope.files=OwnedCreateMarkerFiles(None,PrivateFeatureState(self.root/'ios-create-primary-marker-files.json'),scope.binding)
        scope.originals=IOSCreateOriginals(self.root,scope.binding,RUN,'primary',scope.guard,scope.storage_intent,kind='inputs')
        scope.previous=scope.store.read();scope._version=2 if scope.previous is None else scope.previous['iosCreateMarkerScopeVersion'];scope.state=dict(phase='preparing',revision=0,manifests=[],pending=None,baseline=None,
            admission=None,admissionFrame=None,loadBarrier=None,stopBarrier=None,webAdmission=None,directory=None,fileOwnership=None,fileAbsence=None,
            operations=[],leases=dict(tablet=False,address=False,menu=False),quiet=[],cleanupMode='full')
        if scope.previous is not None:scope.state=scope.decode(scope.previous)
        return scope

    def test_actual_returned_delivery_reconstructs_without_delivering_again(self):
        calls=[];owner=self.owner();receipt={'delivery':'synthetic SDK reply'}
        self.assertEqual(receipt,owner.once('open-marker-manager',lambda:calls.append('input') or receipt))
        self.assertEqual(receipt,self.owner().once('open-marker-manager',lambda:calls.append('replayed')))
        self.assertEqual(['input'],calls)

    def test_lost_input_return_persists_issued_phase_and_reconstruction_never_resends(self):
        calls=[]
        def lost():calls.append('delivered');raise NativeUIError('Synthetic lost normal UI return')
        with self.assertRaises(NativeUIError):self.owner().once('load-marker-script',lost)
        owner=self.owner();self.assertEqual('issued',owner.state['operations'][0]['phase'])
        with self.assertRaises(NativeUIError):owner.once('load-marker-script',lambda:calls.append('replayed'))
        self.assertEqual(['delivered'],calls)

    def test_foreign_candidate_or_process_cannot_reconstruct_the_delivery_owner(self):
        self.owner().once('stage-marker-files',lambda:None)
        for field,replacement in (('processIdentity','32'),('artifactSha256','f'*64),('targetFingerprint','0'*64)):
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.owner(BINDING|{field:replacement})

    def test_stale_owner_cannot_overwrite_another_invocation_or_send_unjournaled_input(self):
        first=self.owner();first.save();second=self.owner();second.once('open-marker-manager',lambda:None);calls=[]
        with self.assertRaises(NativeUIError):first.once('load-marker-script',lambda:calls.append('unsafe'))
        self.assertEqual([],calls)
    def test_quiet_window_excludes_first_and_last_acquisitions_and_requires_native_elapsed(self):
        def frame(before,after,native_before,native_after):
            return dict(clockJoin=dict(hostBeforeMonotonic=before,hostAfterMonotonic=after),world=dict(processId=31,instance='a'*32,
                clockBefore=dict(epochMs=20000+native_before,monotonicMs=native_before),
                clockAfter=dict(epochMs=20000+native_after,monotonicMs=native_after)))
        first=frame(0.,1.4,0,1400);last=frame(2.,3.4,2000,3400)
        self.assertFalse(CreateMarkerScope.quiet_interval(first,last))
        last=frame(4.4,4.5,4400,4500);self.assertTrue(CreateMarkerScope.quiet_interval(first,last))
        last['world']['clockBefore']['monotonicMs']=4300;self.assertFalse(CreateMarkerScope.quiet_interval(first,last))


if __name__=='__main__':unittest.main()
