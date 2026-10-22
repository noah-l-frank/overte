"""Real Tablet byte ownership and unchanged Avatar v1 storage boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_packet_segments import OriginalPacketSegments,CHUNK_BYTES
from adapters.script_feature.history import canonical
from ios.adapters.tablet_web_segments import TabletWebSourceSegments
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.self_tests.test_ios_world_web_keys import RUN
from ios.self_tests import test_ios_avatar_tail_segments as avatar_tests


class OriginalAvatarProfile(OriginalPacketSegments):
    PROFILE='avatar-tail'


class ExtractedAvatarRegression(avatar_tests.AvatarTailSegmentsTests):
    def make(self,subject='primary'):
        return OriginalAvatarProfile(self.root,BINDING,RUN,'primary',subject,lambda:True,
            lambda value:self.parents.append(deepcopy(value)),monotonic=lambda:0.)


class TabletWebSegmentsTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700)
        self.parents=[];self.owner=self.make();self.tag=hashlib.sha256(b'actual-tablet-query').hexdigest()
    def make(self,subject='uikit',role='primary'):
        return TabletWebSourceSegments(self.root,BINDING,RUN,role,subject,lambda:True,
            lambda value:self.parents.append(deepcopy(value)),monotonic=lambda:0.)
    def test_two_mebibyte_source_has_own_namespace_exact_bytes_and_real_private_files(self):
        raw=os.urandom(2*1024*1024);parent=self.owner.write('uikit',self.tag,raw,1)
        self.assertEqual(1,parent['tabletWebSourceSegmentsVersion']);self.assertEqual(4,len(parent['chunks']))
        self.assertEqual(raw,self.owner.read(parent));self.assertFalse(self.parents[0]['complete'])
        self.assertTrue(self.parents[-1]['complete'])
        for ref in parent['chunks']:
            path=self.owner.store.path(ref);self.assertTrue(path.name.startswith('tabletweb-uikit-source-parts-frame-sources-'))
            self.assertLess(path.stat().st_size,1024*1024);self.assertEqual(0o600,path.stat().st_mode&0o777)
        for subject,role in (('dom','primary'),('uikit','actor')):
            with self.subTest(subject=subject,role=role),self.assertRaises((NativeUIError,FileNotFoundError)):
                self.make(subject,role).read(parent)
    def test_closed_profiles_labels_and_subjects_cannot_create_unbound_or_avatar_carriers(self):
        for subject in ('primary','avatar','unknown'):
            with self.subTest(subject=subject),self.assertRaises(NativeUIError):self.make(subject)
        with self.assertRaises(NativeUIError):self.owner.write('expected-cleanup',self.tag,b'{}',1)
        with self.assertRaises(NativeUIError):OriginalPacketSegments(self.root,BINDING,RUN,'primary','uikit',lambda:True,lambda v:None,monotonic=lambda:0.)
        self.assertEqual([],list(self.root.iterdir()))
    def test_opened_zero_prefix_and_complete_lost_flush_remain_original_without_replay(self):
        callback=self.owner.intent
        def lost(value):
            callback(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='opened':raise OSError('Actual opened return lost')
        self.owner.intent=lost
        with self.assertRaises(OSError):self.owner.write('uikit',self.tag,b'{}',1)
        first=self.parents[-1];snap=self.owner.inspect(first);self.assertEqual(0,snap[0]['bytes'])
        with self.assertRaises(NativeUIError):self.owner.read(first)
        self.owner.retained(first,snap);self.owner.intent=callback
        with patch('adapters.original_frame_store.os.fsync',side_effect=OSError('Actual flush return lost')),self.assertRaises(OSError):
            self.owner.write('uikit',self.tag,b'{}',2)
        second=self.parents[-1];self.assertFalse(second['complete']);self.assertEqual(b'{}',self.owner.read(second))
        self.assertEqual(b'',self.owner.store.path(first['chunks'][0]).read_bytes())
    def test_independent_literal_avatar_v1_file_reads_byte_for_byte_without_rewrite(self):
        raw=b'original callback bytes';tag=hashlib.sha256(b'old query').hexdigest()
        body={'avatarTailSegmentBodyVersion':1,'subject':'primary','label':'uikit','tag':tag,
            'parentBytes':len(raw),'parentSha256':hashlib.sha256(raw).hexdigest(),'offset':0,'data':base64.b64encode(raw).decode()}
        frame={'avatarTailSegmentFrameVersion':1,'kind':'sources','binding':deepcopy(BINDING),'runId':RUN,
            'role':'primary','index':1,'frame':body}
        encoded=canonical(frame);digest=hashlib.sha256(encoded).hexdigest()
        path=self.root/('avatar-primary-tail-parts-frame-sources-'+RUN+'-primary-0001-'+digest+'.json')
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(encoded)
        info=path.stat();ref={'avatarTailSegmentOriginalVersion':1,'kind':'sources','binding':deepcopy(BINDING),
            'runId':RUN,'role':'primary','index':1,'sha256':digest,'bytes':len(encoded),'phase':'saved',
            'file':{'device':info.st_dev,'inode':info.st_ino}}
        parent={'avatarTailSegmentsVersion':1,'label':'uikit','tag':tag,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
            'first':1,'chunks':[ref],'complete':True}
        old=OriginalAvatarProfile(self.root,BINDING,RUN,'primary','primary',lambda:True,lambda v:None,monotonic=lambda:0.)
        self.assertEqual(raw,old.read(parent));self.assertEqual(encoded,path.read_bytes());self.assertEqual(info,path.stat())
        with self.assertRaises(NativeUIError):self.owner.parent(parent)


if __name__=='__main__':unittest.main()
