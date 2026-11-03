"""Actual existing aggregate reservations refuse a cold getter BEFORE dispatch."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_stream_factory import WIRE_LIMIT
from adapters.script_journey.history import MAX_RAW
from self_tests.test_pico_emote_stream_factory import StreamFactoryTests,RETAINED


class StreamFactoryCapacityTests(StreamFactoryTests):
    def test_actual_pending_original_reservations_exhaust_same_bill_before_first_cold_getter(self):
        cycle,capture,factory,ticket=self.prepared();m=self.model;archive=cycle.originals.archive;held=[]
        def reserve_before_initial_reader():
            # These are actual durable opaque-literal capacity reservations,
            # not fabricated provider/relationship/receipt observations.
            with archive.lock.held():
                for index in range(6):
                    other=archive.other_bill();ours=archive.bill()
                    pending=sum(row['limit']+row['sideBytes'] for row in archive.state['pending'])
                    available=MAX_RAW-max(other['decodedBytes']+ours['decodedBytes'],
                        other['storedBytes']+ours['storedBytes'])-pending-3*65536
                    if available<9*WIRE_LIMIT:break
                    extent=min(4000000,available-1048576-4096)
                    self.assertGreater(extent,1)
                    held.append(archive.reserve('emote-stream-runtime-pending-fixture',
                        dict(declaredCapacityCounterOnly=True,slot=index),1,side_bytes=extent-1))
                self.assertTrue(held)
        m.before_runtime_process=reserve_before_initial_reader
        with cycle.held(),self.assertRaises(NativeUIError):capture.acquire(ticket)
        self.assertTrue(held);self.assertTrue(archive.stopped);self.assertTrue(factory.failed)
        self.assertEqual(held,archive.state['pending'])
        self.assertEqual([],m.runtime_calls);self.assertEqual([],m.native_commands);self.assertEqual([],m.normal_inputs)
        self.assertEqual(capture._component_started,factory.calls[0][3])
