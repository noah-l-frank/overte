"""Real bounded original PNG fragments, independent of native/page models.

Only byte/inode ownership is qualified here. Product page/capture clocks belong
to the separate actual source/image composition tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_packet_segments import LIMIT
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_images import IOSTabletWebImages
from ios.adapters.tablet_web_screen_archive import TabletWebScreenArchive,raw_original
from self_tests.test_completed_frame_lease import BINDING,RUN


def png(extent=(160,40),*,entropy=False):
    image=Image.frombytes('RGB',extent,os.urandom(extent[0]*extent[1]*3)) if entropy else Image.new('RGB',extent,(20,60,140))
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def receipt(raw,extent):
    return dict(nativeScreenRawVersion=1,requestId='ios-'+'d'*32,source='native-screen',transport='webdriveragent-original-png',
        sessionId=BINDING['sessionId'],processId=int(BINDING['processIdentity']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),extent=list(extent))


class TabletWebScreenArchiveTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.current=None;self.transitions=[]
    def intent(self,value):self.current=deepcopy(value);self.transitions.append(deepcopy(value))
    def owner(self,intent=None):return TabletWebScreenArchive(self.root,BINDING,RUN,'primary',lambda:True,intent or self.intent,monotonic=lambda:0.)
    def test_actual_large_PNG_splits_into_private_bounded_files_and_reconstructs_exactly(self):
        raw=png((1500,1000),entropy=True);self.assertGreater(len(raw),LIMIT)
        owner=self.owner();original=receipt(raw,(1500,1000));saved=owner.write(original,raw,1)
        self.assertEqual(raw,owner.read(saved));self.assertEqual(2,len(saved['parts']))
        chunks=[chunk for part in saved['parts'] for chunk in part['chunks']];self.assertEqual(9,len(chunks))
        self.assertEqual(list(range(1,10)),[chunk['index'] for chunk in chunks])
        self.assertEqual([1,9],[part['first'] for part in saved['parts']])
        self.assertTrue(all(owner.parts.store.path(chunk).stat().st_size<=1024*1024 for chunk in chunks))
        files=[path for path in self.root.iterdir() if path.is_file()];self.assertTrue(files)
        self.assertTrue(all(path.stat().st_mode&0o777==0o600 and path.stat().st_nlink==1 for path in files))
        self.assertTrue(any(not item['complete'] for item in self.transitions));self.assertEqual(original,saved['raw'])
    def test_complete_opened_original_survives_lost_parent_return_without_relabel(self):
        def lose_saved_return(value):
            if any(child['phase']=='saved' for part in value['parts'] for child in part['chunks']):
                raise OSError('lost durable parent return')
            self.intent(value)
        raw=png();owner=self.owner(lose_saved_return)
        with self.assertRaisesRegex(OSError,'lost durable parent return'):owner.write(receipt(raw,(160,40)),raw,1)
        opened=self.current;self.assertFalse(opened['complete']);self.assertFalse(opened['parts'][0]['complete'])
        self.assertEqual('opened',opened['parts'][0]['chunks'][0]['phase'])
        files={path.name:(path.stat().st_dev,path.stat().st_ino,path.read_bytes()) for path in self.root.iterdir()}
        before=deepcopy(opened);transitions=deepcopy(self.transitions)
        self.assertEqual(raw,owner.retained(opened));self.assertEqual(before,opened)
        with self.assertRaises(NativeUIError):owner.read(opened)
        self.assertEqual(transitions,self.transitions)
        self.assertEqual(files,{path.name:(path.stat().st_dev,path.stat().st_ino,path.read_bytes()) for path in self.root.iterdir()})
    def test_foreign_parent_hash_raw_PNG_and_replaced_original_inode_are_rejected(self):
        raw=png();owner=self.owner();saved=owner.write(receipt(raw,(160,40)),raw,1)
        for fault in ('hash','request','raw'):
            changed=deepcopy(saved)
            if fault=='hash':changed['sha256']='0'*64
            elif fault=='request':changed['raw']['requestId']='ios-'+'e'*32
            else:changed['raw']['extent']=[1,1]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.read(changed)
        original=saved['parts'][0]['chunks'][0];file=owner.parts.store.path(original);file.rename(self.root/'preserved-original')
        file.write_bytes((self.root/'preserved-original').read_bytes());file.chmod(0o600)
        with self.assertRaises(NativeUIError):owner.read(saved)


if __name__=='__main__':unittest.main()
