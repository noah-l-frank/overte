"""Actual integrated Policy2 source composition; declared native/GPU issuer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest

from adapters.chat_journey.archive_file import signature
from adapters.pico4.emote_stream_archive import PicoEmoteStreamArchive
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture
from adapters.script_journey.history import MAX_RAW,MAX_FRAMES
from self_tests.pico_emote_stream_capacity_cycle_fixture import CapacityCycleModel
from self_tests.pico_emote_stream_fixture import RUN

RETAINED=[]


class StreamCapacityCycleTests(unittest.TestCase):
    def setUp(self):
        self.model=CapacityCycleModel();self.addCleanup(self.finalize)
        print('Retained actual Policy2/Cycle/native-model original roots:',*[str(p) for p in self.model.roots],flush=True)

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in self.model.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(roots=[str(p) for p in self.model.roots],files=after,originalModelCloseCalled=True))

    def finish(self,cycle):
        m=self.model
        cycle.act(m.m.input.call('cancel'));cycle.act(m.m.input.call('close'))
        m.m.s.journal.activate(RUN,'f'*32,'cleanup');cycle.cleanup(sleep=m.m.sleep)
        for producer in m.streams.values():producer.event_loop_turn()
        result=cycle.drain();self.assertTrue(result['sourceDrained'])
        self.assertFalse(result['wholeFeatureComplete'] or result['independentActorQualified'] or result['stereoQualified'])
        self.assertTrue(all(publisher.drained for publisher in m.publishers.values()))

    def test_original_policy2_and_scope2_arm_sample_normal_cancel_close_quiet_share_original_parent(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();self.assertEqual(2,cycle.policy.disk['picoEmoteStreamBudgetVersion'])
            self.assertEqual(2,cycle.originals.archive.scope['picoEmoteStreamOriginalsVersion'])
            self.assertIs(cycle.capacity.archive,cycle.originals.archive)
            clocks=[cycle.parent.state[key] for key in ('started','epochMs','hostEpochMs')]
            self.assertEqual(clocks,cycle.capacity.state['originalClocks'])
            cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}));cycle.sample_pair()
            for role,source in cycle.streams.items():
                reader=PicoEmoteStreamArchive(source.store,cycle.originals.path,guard=lambda:True)
                try:self.assertEqual(2,reader.policy['picoRemoteAvatarStreamPolicyVersion']);self.assertFalse(reader.report()['liveAuthority'])
                finally:self.assertTrue(reader.close())
            bill=cycle.originals.other_bill();raw=cycle.originals.archive.bill()
            self.assertLessEqual(bill['parts']+raw['parts'],MAX_FRAMES)
            self.assertLessEqual(bill['storedBytes']+raw['storedBytes'],MAX_RAW)
            self.finish(cycle);self.assertEqual(clocks,cycle.capacity.state['originalClocks'])

    def test_policy2_source4_capture3_actual_bounded_files_png_and_authoritative_retirement(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            cycle.baseline();cycle.act(m.m.input.call('open'));cycle.act(m.m.input.call('play',{'name':'Waving'}))
            capture=PicoEmoteStreamCapture(cycle,1,m.world,m.models);m.captures.append(capture)
            capture.acquire(cycle.parent.state['steps'][1]['call']['ticket'])
            self.assertEqual('accounted',cycle.capacity.state['pngs'][0]['phase'])
            self.assertTrue(any(row['phase']=='reserved' for row in cycle.capacity.state['receipts']))
        m.m.tick(500) # Both original role locks are released during autonomous production.
        with cycle.held():
            frame=capture.complete();self.assertLess(frame['avatarBefore']['sampleSequence'],frame['avatarAfter']['sampleSequence'])
            self.assertTrue(all(row['phase']=='retired' for row in cycle.capacity.state['receipts']))
            self.assertEqual(1,len(cycle.capacity._retirements));self.assertIsNone(m.world_store().read())
            self.assertFalse(m.storage.present);self.assertEqual(1,len(m.renderer.commands));self.assertEqual(1,len(m.model_commands))
            self.finish(cycle)
