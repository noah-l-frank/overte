"""Real private artifact files, inode checks and namespace compatibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import scope
from ios.adapters.avatar_originals import IOSAvatarOriginals
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.self_tests.test_ios_avatar_input_owner import BINDING,RUN


class AvatarOriginalTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);os.chmod(self.root,0o700);self.intents=[]
        self.store=IOSAvatarOriginals(self.root,BINDING,RUN,'primary',lambda:True,
            lambda kind,value:self.intents.append((kind,deepcopy(value))))

    def test_large_actual_original_is_private_immutable_and_reconstructed_from_exact_manifest(self):
        frame=dict(original='separate unmodified source '*20000)
        reference=self.store.write(1,frame);manifests=self.store.append([],reference)
        restored=IOSAvatarOriginals(self.root,BINDING,RUN,'primary',lambda:True,lambda *_:None)
        self.assertEqual([frame],restored.restore(manifests,1))
        original=self.store.expand(reference);path=self.store.path(original)
        self.assertGreater(reference['bytes'],65536);self.assertEqual(0o600,path.stat().st_mode&0o777)
        self.assertTrue(path.name.startswith('avatar-frame-sources-'+RUN+'-primary-'))
        self.assertEqual(['planned','opened','saved'],[value['phase'] for kind,value in self.intents if kind=='original'])
        self.assertEqual('avatarOriginalVersion',next(key for key in original if key.endswith('OriginalVersion')))

    def test_generic_store_reads_committed_Emote_v1_bytes_namespaces_and_manifest_unchanged(self):
        # Frozen e6c8a47960 v1 envelope and filename grammar, constructed without
        # either current writer. Real inode/mode remain original file facts.
        def legacy_bytes(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        def write(path,raw):
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(raw)
        frame=dict(explicitOriginal='existing emote v1')
        body=dict(emoteFrameVersion=1,kind='sources',binding=BINDING,runId=RUN,role='actor',index=1,frame=frame)
        raw=legacy_bytes(body);digest=hashlib.sha256(raw).hexdigest()
        path=self.root/('emote-frame-sources-'+RUN+'-actor-0001-'+digest+'.json');write(path,raw);info=path.stat()
        reference=dict(index=1,sha256=digest,bytes=len(raw),device=info.st_dev,inode=info.st_ino)
        manifest=dict(emoteManifestVersion=1,kind='sources',binding=BINDING,runId=RUN,role='actor',block=1,entries=[reference])
        manifest_raw=legacy_bytes(manifest);manifest_digest=hashlib.sha256(manifest_raw).hexdigest()
        manifest_path=self.root/('emote-index-sources-'+RUN+'-actor-1-1-'+manifest_digest+'.json');write(manifest_path,manifest_raw)
        manifests=[dict(block=1,count=1,sha256=manifest_digest,bytes=len(manifest_raw))]
        old=IOSEmoteOriginals(self.root,BINDING,RUN,'actor',lambda:True,lambda *_:None)
        generic=OriginalFrameStore(self.root,BINDING,RUN,'actor',lambda:True,lambda *_:None,
            namespace='emote',schema_prefix='emote')
        self.assertEqual([frame],generic.restore(manifests,1))
        self.assertEqual([frame],old.restore(manifests,1))
        self.assertEqual(old.path(old.expand(reference)),generic.path(generic.expand(reference)))
        self.assertEqual(raw,path.read_bytes());self.assertEqual(manifest_raw,manifest_path.read_bytes())
        self.assertEqual(0o600,path.stat().st_mode&0o777)
        with self.assertRaises((NativeUIError,FileNotFoundError)):
            IOSAvatarOriginals(self.root,BINDING,RUN,'actor',lambda:True,lambda *_:None).restore(manifests,1)

    def test_replaced_inode_hardlink_or_changed_original_cannot_be_adopted(self):
        reference=self.store.write(1,dict(actual='original'));value=self.store.expand(reference);path=self.store.path(value)
        raw=path.read_bytes();path.unlink();path.write_bytes(raw);os.chmod(path,0o600)
        with self.assertRaises(NativeUIError):self.store.read(value)
        value['file']=dict(device=path.stat().st_dev,inode=path.stat().st_ino)
        alias=path.with_name('hardlink');os.link(path,alias)
        with self.assertRaises(NativeUIError):self.store.read(value)
        alias.unlink();path.write_bytes(raw+b' ')
        with self.assertRaises(NativeUIError):self.store.read(value)

    def test_lost_opened_journal_retains_actual_partial_file_and_never_replays_over_it(self):
        def intent(kind,value):
            self.intents.append((kind,deepcopy(value)))
            if kind=='original' and value['phase']=='opened':raise NativeUIError('Journal unavailable')
        self.store.intent=intent
        with self.assertRaises(NativeUIError):self.store.write(1,dict(actual='owned partial'))
        opened=self.intents[-1][1];path=self.store.path(opened);self.assertTrue(path.exists())
        self.assertEqual(0,path.stat().st_size)
        with self.assertRaises(NativeUIError):self.store.read(opened)
        self.store.intent=lambda *_:None
        with self.assertRaises(FileExistsError):self.store.write(1,dict(actual='owned partial'))
        self.assertTrue(path.exists())

    def test_fresh_parsed_frame_is_isolated_from_other_reads_caller_input_and_store_context(self):
        frame=dict(nested={'values':[1,{'original':'unchanged'}]},binding=deepcopy(BINDING))
        reference=self.store.write(1,frame);value=self.store.expand(reference);path=self.store.path(value)
        before=(path.stat().st_ino,path.read_bytes());binding=deepcopy(self.store.binding)
        with scope(fresh=True) as first_reads:first=self.store.read(value)
        with scope(fresh=True) as second_reads:second=self.store.read(value)
        self.assertEqual({path},first_reads);self.assertEqual(first_reads,second_reads)
        self.assertIsNot(first,second);self.assertIsNot(first['nested'],second['nested'])
        self.assertIsNot(first['nested']['values'][1],second['nested']['values'][1])
        first['nested']['values'][1]['original']='caller changed';first['binding']['generation']=99
        self.assertEqual(frame,second);self.assertEqual(frame,self.store.read(value));self.assertEqual(binding,self.store.binding)
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))

    def test_slow_fresh_parse_or_failed_original_guard_cannot_record_membership(self):
        reference=self.store.write(1,dict(original='unchanged'));value=self.store.expand(reference)
        clock=[0.];self.store.clock=None;self.store.monotonic=lambda:clock[0]
        original=json.loads
        def slow(*args,**kwargs):
            result=original(*args,**kwargs);clock[0]=5.;return result
        with scope(fresh=True) as reads,patch('adapters.original_frame_store.json.loads',side_effect=slow),self.assertRaises(NativeUIError):
            self.store.read(value)
        self.assertEqual(set(),reads)
        self.store.guard=lambda:False
        with scope(fresh=True) as failed,self.assertRaises(NativeUIError):self.store.read(value)
        self.assertEqual(set(),failed)


if __name__=='__main__':unittest.main()
