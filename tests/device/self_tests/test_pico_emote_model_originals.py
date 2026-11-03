"""Actual remote capture retains malformed/late model replies before refusal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
from adapters.pico4.emote_model_originals import EmoteModelOriginals
from adapters.script_journey.history import canonical
from self_tests.test_pico_emote_capture import RemoteCaptureModel


class EmoteModelOriginalTests(unittest.TestCase):
    def setUp(self):self.model=RemoteCaptureModel(self)
    def originals(self,owner):
        source=AudioPCRawOriginals(owner.model_originals.path);self.addCleanup(source.close)
        self.assertEqual(owner.model_originals.scope,canonical(source.disk['scope']))
        return source,[source.literal(dict(audioRawRangeVersion=1,scopeSha256=source.scope_sha,read=index,sha256=row['sha256']))
            for index,row in sorted(source.receipts.items())]
    def reader(self,transform):
        m=self.model;factory=m.gpu.models.reader
        def make():
            reader=factory();original=reader.original
            reader.original=lambda:transform(original())
            return reader
        m.gpu.models.reader=make
    def test_malformed_first_literal_survives_parser_poll_and_actual_valid_reply(self):
        m=self.model;malformed='{bad model reply\u0000\u03b1';seen=[]
        def transform(value):
            seen.append(value);return malformed if len(seen)==1 else value
        self.reader(transform)
        with m.held():
            owner=m.owner();owner.read(m.ticket());source,raw=self.originals(owner)
            self.assertEqual([malformed,seen[-1]],raw);self.assertFalse(source.pending)
            self.assertEqual('complete',owner.state['phase']);self.assertEqual(1,len(m.gpu.models.commands))
            self.assertEqual(owner.state['modelRequest'],source.receipts[0]['command'])
            self.assertEqual(owner.state['modelRequest'],source.receipts[1]['command'])
    def test_full_megabyte_literal_is_durable_before_original_parser_size_refusal(self):
        m=self.model;literal='\0'*(1024*1024)
        self.reader(lambda _value:literal)
        with m.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            source,raw=self.originals(owner)
            self.assertEqual([literal],raw);self.assertFalse(source.pending)
            self.assertEqual('failed',owner.state['phase']);self.assertIsNone(owner.state['draws'])
            self.assertEqual(1,len(m.gpu.models.commands));self.assertEqual(16,len(source.state['parts']))

    def test_actual_late_return_is_durable_before_business_clock_refuses_it(self):
        m=self.model;seen=[]
        def transform(value):
            seen.append(value);m.cycle.s.clock+=6;return value
        self.reader(transform)
        with m.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            source,raw=self.originals(owner);self.assertEqual(seen,raw);self.assertEqual(1,len(raw));self.assertFalse(source.pending)
            self.assertEqual('failed',owner.state['phase']);self.assertIsNone(owner.state['draws'])
            self.assertEqual('saved',owner.state['image']['phase']);before=len(m.gpu.models.commands)
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual(before,len(m.gpu.models.commands))
    def test_changed_raw_journal_blocks_warm_delivery_but_original_resources_can_retire(self):
        m=self.model
        with m.held():
            owner=m.owner();owner.read(m.ticket());raw=owner.model_originals.path
            raw.unlink() # Only this test's already acquired, independently owned journal.
            queries=len(m.gpu.models.commands)
            with self.assertRaises(NativeUIError):owner.original()
            self.assertEqual(queries,len(m.gpu.models.commands))
            self.assertIsNone(m.gpu.owner_store().read())
            self.assertTrue(list(raw.parent.glob(raw.name+'.part-*.bin')))

    def test_raw_reservation_work_cannot_authorize_late_model_send_or_getter(self):
        m=self.model;actual=EmoteModelOriginals.other_bill
        def delayed(owner):
            result=actual(owner);m.cycle.s.clock+=6;return result
        with m.held(),patch.object(EmoteModelOriginals,'other_bill',delayed):
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.read(m.ticket())
            self.assertEqual([],m.gpu.models.commands);self.assertIsNotNone(owner.state['modelRequest'])
            self.assertEqual('saved',owner.state['image']['phase']);self.assertEqual('failed',owner.state['phase'])
    def test_complete_existing_footprint_refuses_model_dispatch_without_raising_budget(self):
        m=self.model
        # These independently retained files consume the same real private
        # namespace. They are counted only; no ownership is inferred from names.
        for index in range(512):
            path=m.cycle.s.root/('retained-footprint-'+str(index)+'.bin');path.write_bytes(b'original\n');path.chmod(0o600)
        refused=False
        with m.held():
            owner=m.owner()
            try:owner.read(m.ticket())
            except NativeUIError:refused=True
        # Assertions follow the real outer release: SourceLock must not mask
        # an old implementation's absent refusal as a serialization error.
        self.assertTrue(refused);self.assertEqual([],m.gpu.models.commands)
        self.assertEqual('saved',owner.state['image']['phase']);self.assertEqual('failed',owner.state['phase'])
        self.assertTrue(all((m.cycle.s.root/('retained-footprint-'+str(i)+'.bin')).exists() for i in range(512)))


if __name__=='__main__':unittest.main()
