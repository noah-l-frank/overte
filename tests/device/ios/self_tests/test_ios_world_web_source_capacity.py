"""Measured cumulative callback capacity retains closed historical byte limits."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,world_web_source as source
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL


def callbacks(count=800):
    actual=OriginalSources()
    for _ in range(count):
        entry=actual.event('evaluation-enter',dict(codeSha256='7'*64))
        actual.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False)))
        actual.event('callback-return',dict(entry=entry['sequence']))
    return actual


class WorldWebSourceCapacityTests(unittest.TestCase):
    def test_actual_large_original_uses_existing_closed_afc_factory_and_default_decoder_stays_small(self):
        actual=callbacks();sdk=Native();observer=sdk.observer();retained={}
        class Clock:
            sequence=0
            def read(self,after):
                self.sequence+=1;return dict(capturedEpochMs=actual.clock())
        clock=Clock();observer.monotonic=lambda:actual.epoch/1000
        def post(request,timeout):
            query=sdk.fixture.set_client_command(json.loads(request.data));sdk.commands.append(deepcopy(query));sdk.echo=json.dumps(query).encode()
            retained['value']=actual.ledger(query);return sdk
        def execute(session,operation,values):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
            self.assertTrue(values['remotePath'].endswith('/'+source.FILE));sdk.reads.append(deepcopy(values))
            raw=json.dumps(retained['value'],separators=(',',':'));retained['raw']=raw
            return base64.b64encode(raw.encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(sdk,'execute',side_effect=execute):
            packet=observer.world_web(clock).read(RUN,URL)
        self.assertEqual(retained['value'],packet);self.assertGreater(len(retained['raw'].encode()),1048576)
        self.assertLessEqual(len(retained['raw'].encode()),source.LIMIT);self.assertEqual(1,len(sdk.commands));self.assertEqual(1,len(sdk.reads))
        with self.assertRaises(NativeUIError):decode(retained['raw'])
        with self.assertRaises(NativeUIError):decode(retained['raw'],limit=1048576)
        self.assertEqual(packet,decode(retained['raw'],limit=source.LIMIT))

    def test_real_callback_prefix_above_old_event_bound_cannot_be_relabelled_historical(self):
        current=callbacks().ledger();source.original(current)
        self.assertGreater(len(current['events']),2048)
        for version in (1,2):
            old=deepcopy(current);old['iosWorldWebVersion']=version
            with self.subTest(version=version),self.assertRaises(NativeUIError):source.original(old)
        current['complete']=False;source.original(current)
        with self.assertRaises(NativeUIError):source.pending(current)

    def test_historical_byte_limit_remains_closed_below_legacy_event_count(self):
        actual=OriginalSources(transcript_version=2)
        for _ in range(300):actual.event('script-delivery',dict(message='x'*4096))
        old=actual.ledger();self.assertLess(len(old['events']),2048)
        self.assertGreater(len(json.dumps(old,separators=(',',':')).encode()),1048576)
        with self.assertRaises(NativeUIError):source.original(old)
        # A separate actual producer supplies current capacity. Never rewrite
        # this old original in order to qualify an active journey.
        current=OriginalSources()
        for _ in range(300):current.event('script-delivery',dict(message='x'*4096))
        source.original(current.ledger())

    def test_current_overflow_stays_unavailable_without_truncating_actual_events(self):
        actual=callbacks(1364);packet=actual.ledger();self.assertGreater(len(packet['events']),4096)
        with self.assertRaises(NativeUIError):source.original(packet)
        packet=callbacks().ledger();packet['events'][7]['detail']['result']['error']=True
        with self.assertRaises(NativeUIError):source.validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=source.ACTION,runId=RUN,fixtureUrl=URL),42,previous=callbacks().ledger())


if __name__=='__main__':unittest.main()
