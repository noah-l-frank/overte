"""Actual resumed Page/input owners; native/UI/SDK producers are host models.

The original combined capture, resume Page3, raw segmented input packet, CAS,
held lock and immutable inode readers execute. No OS transition or pixel claim
is established by these input-prefix counters.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest,validate_join
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_inputs
from ios.adapters.snapshot_resume_cursor import cursor
from ios.adapters.snapshot_resume_inputs import SnapshotResumeInputsPacket
from ios.adapters.snapshot_source_packet import SnapshotInputsPacket
from ios.adapters.snapshot_owned_packet import qualified
from ios.self_tests.test_ios_snapshot_resume_page import ResumePageDomain,RESUME,RUN


class SnapshotResumeCursorTests(unittest.TestCase):
    def owner(self,d,page,*,historical=False):
        cls=SnapshotResumeInputsPacket
        store=PrivateFeatureState(d.ctx.root/(cls._store_prefix+'-primary-'+cls._name+'-0001.json'))
        args=(store,page.lock,page.binding,RUN,'primary',1)
        if historical:return cls.history(*args)
        source=d.runtime._sources('primary')
        return cls(*args,source['observer'],source['clock_source'],source['check'],epoch_ms=d.capture.epoch,monotonic=d.capture.mono)

    def retained(self,d,page):
        page.prepare(RESUME);original=page.record(1)
        packet=self.owner(d,page);packet.reserve();packet.send();frame=packet.retain()
        return original,packet,frame

    def encoded(self,frame):
        frame['raw']=json.dumps(frame['packet'],indent=1)+'\n'
        snapshot_inputs.original(frame['packet']);qualified(frame,42,'inputs');return frame

    def test_actual_normal_capture_and_resume_page_join_complete_original_input_prefix_without_repeating_input(self):
        d=ResumePageDomain(self);clicks=deepcopy(d.clicks)
        with d.resumed_page() as page:
            original,owner,frame=self.retained(d,page);result=cursor(original,frame,page.binding,RUN)
            self.assertEqual(original['originals']['ui']['lastSequence'],result['sequence'])
            self.assertTrue(all(result[key]for key in ('normalInputOutcomeRequired','originalPageAndPacketOwnersRequired',
                'originalOSBridgeRequired','renderedResumeRequired','independentActorSceneRequired','wholeFeatureRequired')))
            pins={p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.is_file()}
            commands=deepcopy(d.capture.commands);native=d.ctx.native.sequence
            historical=self.owner(d,page,historical=True)
            with patch.object(type(owner.store),'write',side_effect=AssertionError('Historical input-prefix write')):
                self.assertEqual(result,cursor(page.record(1),historical.historical(),page.binding,RUN))
            self.assertEqual(pins,{p.name:(p.stat().st_ino,p.read_bytes())for p in d.ctx.root.iterdir()if p.is_file()})
            self.assertEqual(commands,d.capture.commands);self.assertEqual(native,d.ctx.native.sequence)
            self.assertTrue(owner.parts().store.namespace.startswith('snapshot-resume-inputs-parts'))
            with self.assertRaises(NativeUIError):SnapshotInputsPacket.history(owner.store,page.lock,page.binding,RUN,'primary',1)
        self.assertEqual(clicks,d.clicks);self.assertEqual(1,d.capture.capture_count);self.assertEqual(0,d.screen_calls)

    def test_well_formed_complete_native_source_with_missing_return_cannot_anchor_the_ui_cursor(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            original,_owner,frame=self.retained(d,page);changed=deepcopy(frame)
            changed['packet']['source']['events'].pop();self.encoded(changed)
            with self.assertRaises(NativeUIError):cursor(original,changed,page.binding,RUN)

    def test_well_formed_foreign_root_or_input_instance_and_wrong_ui_cursor_are_rejected(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            original,_owner,frame=self.retained(d,page)
            for fault in ('root','instance','ui-cursor'):
                current,packet=deepcopy(original),deepcopy(frame)
                events=packet['packet']['source']['events'];received=[r for r in events if r['kind']=='received']
                returned=[r for r in events if r['kind']=='returned']
                if fault=='root':received[-1]['details']['root']['rootId']='99999999-9999-4999-8999-999999999999'
                elif fault=='instance':
                    for row in received:row['details']['command']['instance']='99999999-9999-4999-8999-999999999999'
                    for row in returned:row['details']['status']['instance']='99999999-9999-4999-8999-999999999999'
                else:
                    current['originals']['ui']['lastSequence']+=1
                    current['clockJoin']['originalsSha256']=digest(current['originals'])
                    validate_join(current['clockJoin'],current['originals'])
                self.encoded(packet)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):cursor(current,packet,page.binding,RUN)

    def test_actual_same_byte_new_part_inode_refuses_historical_prefix_before_any_query(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            _original,owner,_frame=self.retained(d,page)
            path=owner.parts().store.path(owner.state['rawParts']['chunks'][0]);raw=path.read_bytes();old=path.stat().st_ino
            path.rename(path.with_suffix('.retained-original'));path.write_bytes(raw);path.chmod(0o600)
            self.assertNotEqual(old,path.stat().st_ino);commands=deepcopy(d.capture.commands)
            with self.assertRaises(NativeUIError):self.owner(d,page,historical=True)
            self.assertEqual(commands,d.capture.commands)

    def test_other_process_binding_cannot_consume_real_resume_page_or_original_packet(self):
        d=ResumePageDomain(self)
        with d.resumed_page() as page:
            original,_owner,frame=self.retained(d,page);binding=deepcopy(page.binding);binding['processIdentity']='43'
            with self.assertRaises(NativeUIError):cursor(original,frame,binding,RUN)
