"""Small real-file CAS/copy counterexamples; no native continuation authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_rotation_fence as codec
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner

BINDING=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='42',sessionId='private-existing-model',
    generation=7,targetFingerprint='3'*64)
RUN='a'*32


class TabletRotationFenceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.scope=codec.scope(BINDING,RUN,'primary','http://127.0.0.1:1/feature-fixture/v1/runs/'+RUN+'/',42)
        self.old=dict(tabletWebSourceOwnerVersion=2,**deepcopy(self.scope),apps=[],records=[],pending=None,
            intent=None,inspection=None,appIntent=None,appPending=None,appInspection=None,reconciled=[])
        self.head=PrivateFeatureState(self.root/('tabletweb-source-owner-'+RUN+'-primary.json'))
        self.head.write(self.old,None);self.raw,self.signature=self.capture()
        self.old_fd=os.open(self.head.path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0));self.addCleanup(os.close,self.old_fd)
        self.copies=OriginalFrameStore(self.root,BINDING,RUN,'primary',self.copy_guard,self.copy_intent,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader')

    def capture(self):
        raw=self.head.path.read_bytes();s=self.head.path.stat()
        return raw,dict(device=s.st_dev,inode=s.st_ino,mode=s.st_mode,uid=s.st_uid,gid=s.st_gid,nlink=s.st_nlink,
            bytes=s.st_size,mtimeNs=s.st_mtime_ns,ctimeNs=s.st_ctime_ns)

    def fence(self):
        value=codec.make(self.raw,self.signature,self.scope);self.head.write(value,self.old);return value

    def copy_guard(self):
        self.lock.assert_held();codec.decode(self.head.read(),self.scope);return True

    def copy_intent(self,kind,intent):
        current=self.head.read();next_value=codec.with_copy_intent(current,kind,intent,self.scope)
        self.head.write(next_value,current)

    def test_real_CAS_fences_old_reader_and_new_barrier_before_any_child_access(self):
        fence=self.fence();self.assertEqual(3,self.head.read()['tabletWebSourceOwnerVersion'])
        self.assertEqual(self.raw,codec.decode(fence,self.scope))
        old_reader=object.__new__(TabletWebSourceOwner);old_reader.state=fence
        with self.assertRaises(NativeUIError):old_reader._history()
        touched=[]
        with self.assertRaises(codec.TabletHeaderRotating):
            codec.read_barrier(self.head.read(),self.scope);touched.append('child-or-native')
        self.assertEqual([],touched)

    def test_actual_constructor_reads_fence_before_original_child_or_capture_factories(self):
        self.fence()
        with patch('ios.adapters.tablet_web_source_owner.OriginalFrameStore',side_effect=AssertionError('Original factory forbidden')) as originals, \
                patch('ios.adapters.tablet_web_source_owner.TabletWebPackets',side_effect=AssertionError('Child factory forbidden')) as children, \
                patch.object(TabletWebSourceOwner,'capture',side_effect=AssertionError('Native capture forbidden')) as capture:
            with self.assertRaises(codec.TabletHeaderRotating):
                TabletWebSourceOwner(self.root,BINDING,RUN,'primary',self.scope['fixtureUrl'],42,self.lock,
                    lambda:self.fail('Historical rotating entry must not acquire SDK data'),historical=True)
            originals.assert_not_called();children.assert_not_called();capture.assert_not_called()

    def test_invalid_fence_constructor_never_falls_back_to_legacy_or_factories(self):
        value=self.fence();changed=deepcopy(value);changed['phase']='ready';self.head.write(changed,value)
        with patch('ios.adapters.tablet_web_source_owner.OriginalFrameStore',side_effect=AssertionError('Original factory forbidden')) as originals, \
                patch('ios.adapters.tablet_web_source_owner.TabletWebPackets',side_effect=AssertionError('Child factory forbidden')) as children:
            with self.assertRaises(NativeUIError):
                TabletWebSourceOwner(self.root,BINDING,RUN,'primary',self.scope['fixtureUrl'],42,self.lock,
                    lambda:self.fail('Invalid fence must not acquire SDK data'),historical=True)
            originals.assert_not_called();children.assert_not_called()
        self.assertEqual(changed,self.head.read())

    def test_lost_CAS_return_leaves_version3_and_never_restores_lower_floor(self):
        write=self.head.write
        def lost(value,previous):write(value,previous);raise OSError('Actual CAS return lost')
        with patch.object(self.head,'write',side_effect=lost),self.assertRaises(OSError):self.fence()
        actual=self.head.read();self.assertEqual(self.raw,codec.decode(actual,self.scope))
        with self.assertRaises(codec.TabletHeaderRotating):codec.read_barrier(actual,self.scope)
        self.assertEqual(3,self.head.read()['tabletWebSourceOwnerVersion'])

    def test_stale_structural_CAS_cannot_overwrite_a_changed_old_head(self):
        other=deepcopy(self.old);other['appPending']=dict(unresolved=True);self.head.write(other,self.old)
        raw=self.head.path.read_bytes();inode=self.head.path.stat().st_ino
        with self.assertRaises(NativeUIError):self.fence()
        self.assertEqual(raw,self.head.path.read_bytes());self.assertEqual(inode,self.head.path.stat().st_ino)

    def test_no_immutable_copy_is_created_before_the_rotating_fence(self):
        before={path.name for path in self.root.iterdir()}
        body=codec.copy_body(codec.make(self.raw,self.signature,self.scope),self.scope)
        with self.assertRaises(NativeUIError):self.copies.write(1,body)
        self.assertEqual(before,{path.name for path in self.root.iterdir()})

    def test_copy_has_its_own_real_identity_and_retains_exact_old_header_bytes(self):
        self.fence();body=codec.copy_body(self.head.read(),self.scope);reference=self.copies.write(1,body)
        current=self.head.read();self.assertEqual('saved',current['copyIntent']['phase'])
        self.assertEqual(body,self.copies.read(self.copies.expand(reference)))
        self.assertNotEqual(self.signature['inode'],reference['inode'])
        self.assertEqual(self.signature,current['previousHeader']['signature'])
        self.assertEqual(self.raw,codec.decode(current,self.scope))
        with self.assertRaises(codec.TabletHeaderRotating):codec.read_barrier(current,self.scope)

    def test_lost_opened_copy_intent_retains_real_empty_file_without_retry(self):
        self.fence();body=codec.copy_body(self.head.read(),self.scope);write=self.head.write
        def lost(value,previous):
            write(value,previous)
            if value['copyIntent'] is not None and value['copyIntent']['phase']=='opened':raise OSError('Actual opened intent return lost')
        with patch.object(self.head,'write',side_effect=lost),self.assertRaises(OSError):self.copies.write(1,body)
        current=self.head.read();intent=current['copyIntent'];self.assertEqual('opened',intent['phase'])
        path=self.copies.path(intent);self.assertEqual(b'',path.read_bytes());inode=path.stat().st_ino
        with self.assertRaises(NativeUIError):self.copies.read(intent)
        with self.assertRaises(codec.TabletHeaderRotating):codec.read_barrier(current,self.scope)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(b'',path.read_bytes())

    def test_complete_copy_after_lost_read_return_does_not_invent_ACK_or_ready(self):
        self.fence();body=codec.copy_body(self.head.read(),self.scope);read=self.copies.read
        def lost(value):read(value);raise OSError('Actual complete-copy read return lost')
        with patch.object(self.copies,'read',side_effect=lost),self.assertRaises(OSError):self.copies.write(1,body)
        current=self.head.read();self.assertEqual('opened',current['copyIntent']['phase'])
        self.assertEqual(body,self.copies.read(current['copyIntent']))
        self.assertEqual('opened',self.head.read()['copyIntent']['phase'])
        with self.assertRaises(codec.TabletHeaderRotating):codec.read_barrier(current,self.scope)

    def test_foreign_binding_role_candidate_or_copy_cannot_inherit_the_fence(self):
        value=self.fence()
        for field,foreign in (('role','actor'),('runId','b'*32),('processId',43),('fixtureUrl','http://127.0.0.1:2/feature-fixture/v1/runs/'+RUN+'/')):
            with self.subTest(field=field):
                changed=deepcopy(value);changed['scope'][field]=foreign
                with self.assertRaises(NativeUIError):codec.decode(changed,self.scope)
        changed=deepcopy(self.scope);changed['binding']['generation']+=1
        with self.assertRaises(NativeUIError):codec.decode(value,changed)
        self.copies.write(1,codec.copy_body(value,self.scope));changed=self.head.read()
        changed['copyIntent']['role']='actor'
        with self.assertRaises(NativeUIError):codec.decode(changed,self.scope)

    def test_partial_native_or_app_responsibility_cannot_be_encoded_as_closed(self):
        import json
        for field in ('pending','intent','inspection','appIntent','appPending','appInspection'):
            with self.subTest(field=field):
                value=deepcopy(self.old);value[field]=dict(unresolved=True);raw=json.dumps(value).encode()
                signature=dict(self.signature,bytes=len(raw))
                with self.assertRaises(NativeUIError):codec.make(raw,signature,self.scope)
        self.assertEqual(self.raw,self.head.path.read_bytes())

    def test_literal_version1_spacing_and_old_identity_are_not_normalized(self):
        import json
        value=deepcopy(self.old);value['tabletWebSourceOwnerVersion']=1;del value['reconciled']
        raw=b' \n'+json.dumps(value,indent=2).encode()+b'\n'
        self.head.path.write_bytes(raw);original,signature=self.capture()
        fence=codec.make(original,signature,self.scope)
        self.assertEqual(original,codec.decode(fence,self.scope));self.assertEqual(raw,self.head.path.read_bytes())
        self.assertEqual(signature,self.capture()[1]);self.assertIs(value,codec.read_barrier(value,self.scope))

    def test_duplicate_keys_bad_identity_capsule_and_phase_regression_are_refused(self):
        value=self.fence()
        for field,foreign in (('nlink',2),('inode',0),('bytes',len(self.raw)+1)):
            with self.subTest(field=field),self.assertRaises(NativeUIError):
                codec.make(self.raw,dict(self.signature,**{field:foreign}),self.scope)
        raw=self.raw.rstrip()[:-1]+b',"role":"primary"}'
        with self.assertRaises(NativeUIError):codec.make(raw,dict(self.signature,bytes=len(raw)),self.scope)
        changed=deepcopy(value);changed['previousHeader']['data']='A'*(codec.MAX_HEAD_BYTES+1)
        with self.assertRaises(NativeUIError):codec.decode(changed,self.scope)
        self.copies.write(1,codec.copy_body(value,self.scope));saved=self.head.read()
        with self.assertRaises(NativeUIError):codec.with_copy_intent(saved,'original',saved['copyIntent'],self.scope)


if __name__=='__main__':unittest.main()
