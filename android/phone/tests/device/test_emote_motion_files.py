"""Real private motion files from original synthetic native/image observations.

These checks exercise host ownership and validation, never product acceptance.
"""
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

from test_emote_observation import Model
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_motion_files import PhoneEmoteMotionFiles
from adapters.normal_ui import NativeUIError


class EmoteMotionFileTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-motion-file-');self.addCleanup(temporary.cleanup)
        self.model=m=Model(Path(temporary.name));m.use_included_source()
        self.intents=[];self.failure=None;self.okay=True
        with patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet),m.lock.held():
            self.call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(self.call)
            for _ in range(5):owner.source.read()
            scope=m.scope(owner,1);value=scope.read(self.call['ticket']);self.raw=scope.motion_bytes()
            packet=json.loads(self.raw)
            self.capture=dict(call=self.call,state=value['state'],capturedEpochMs=packet['after']['hostEpochMs'],
                requestId=packet['after']['group']['native']['requestId'],bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest())
        self.files=self.factory()

    def intent(self,value):
        self.intents.append(deepcopy(value))
        if value['phase']==self.failure:raise NativeUIError('Synthetic durable callback interruption')

    def factory(self,**options):
        m=self.model
        return PhoneEmoteMotionFiles(m.root,options.get('binding',m.binding),self.call['runId'],options.get('role','primary'),
            options.get('stage',1),lambda:self.okay,self.intent,monotonic=lambda:m.clock)

    def save(self):return self.files.write(self.call['ticket'],self.capture,self.raw)

    def test_actual_original_motion_and_inode_survive_historical_reopen_without_retiming(self):
        value=self.save();path=self.model.root/value['name'];calls=deepcopy(self.model.calls)
        self.assertEqual(['planned','opened','saved'],[row['phase'] for row in self.intents])
        self.assertEqual(self.raw,path.read_bytes());self.assertEqual(0o600,path.stat().st_mode&0o777)
        self.assertEqual(path.stat().st_ino,value['file']['inode']);self.assertEqual(self.raw,self.files.read(value))
        self.okay=False;self.model.epoch+=10000
        self.assertEqual(self.raw,PhoneEmoteMotionFiles.archive(self.model.root,value));self.assertEqual(calls,self.model.calls)
        with self.assertRaises(NativeUIError):self.files.read(value)

    def test_invalid_motion_state_request_or_hash_creates_neither_intent_nor_file(self):
        for change in (dict(requestId='f'*32),dict(state=self.capture['state']|dict(animation='Crying')),
                dict(capturedEpochMs=self.capture['capturedEpochMs']+1),dict(sha256='f'*64),dict(bytes=len(self.raw)-1)):
            with self.subTest(change=change),self.assertRaises((AssertionError,ValueError,NativeUIError)):
                self.files.write(self.call['ticket'],self.capture|change,self.raw)
        self.assertEqual([],self.intents);self.assertEqual([],list(self.model.root.glob('emote-motion-*.json')))

    def test_lost_planned_opened_and_saved_callbacks_preserve_exact_responsibility(self):
        for index,phase in enumerate(('planned','opened','saved'),1):
            self.failure=phase;files=self.factory(stage=index)
            with self.subTest(phase=phase),self.assertRaises(NativeUIError):files.write(self.call['ticket'],self.capture,self.raw)
            value=self.intents[-1];path=self.model.root/value['name']
            self.assertEqual(phase,value['phase'])
            if phase=='planned':self.assertTrue(files.absent(value))
            elif phase=='opened':
                self.assertEqual(b'',path.read_bytes())
                with self.assertRaises(NativeUIError):files.read(value)
            else:self.assertEqual(self.raw,files.read(value))

    def test_preexisting_file_is_not_overwritten_and_missing_file_is_not_success(self):
        value=self.save();path=self.model.root/value['name']
        with self.assertRaises(FileExistsError):self.save()
        self.assertEqual(self.raw,path.read_bytes());path.unlink();self.assertTrue(self.files.absent(value))
        with self.assertRaises(FileNotFoundError):self.files.read(value)

    def test_changed_bytes_replacement_inode_hardlink_and_symlink_cannot_inherit_evidence(self):
        value=self.save();path=self.model.root/value['name'];alias=path.with_name('replacement.json')
        path.write_bytes(self.raw[:-1])
        with self.assertRaises(NativeUIError):self.files.read(value)
        path.write_bytes(self.raw);os.link(path,alias)
        with self.assertRaises(NativeUIError):self.files.read(value)
        alias.unlink();path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.files.read(value)
        path.chmod(0o600);alias.write_bytes(self.raw);alias.chmod(0o600);os.replace(alias,path)
        with self.assertRaises(NativeUIError):self.files.read(value)
        path.rename(alias);path.symlink_to(alias)
        with self.assertRaises((NativeUIError,OSError)):self.files.read(value)

    def test_foreign_role_stage_candidate_and_unbounded_schema_are_rejected(self):
        value=self.save()
        for options in (dict(role='actor'),dict(stage=2),dict(binding=self.model.binding|dict(artifactSha256='f'*64))):
            with self.subTest(options=options),self.assertRaises(NativeUIError):self.factory(**options).read(value)
        for change in (dict(stage=True),dict(emoteMotionFileVersion=True),dict(name='../motion.json'),
                dict(bytes=2*1024*1024+1),dict(expected=True),dict(state=value['state']|dict(override=False))):
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):self.files.record(value|change)
        self.assertEqual(self.raw,self.files.read(value))


if __name__=='__main__':unittest.main()
