"""Actual closed POST/AFC codecs for large original Qt keyboard transcripts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,world_web_keys as keys
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_world_web_keys import QtKeys,RUN


class WorldWebKeysTransportTests(unittest.TestCase):
    def transport(self,producer,*,mutate=None,process=None):
        native=Native();observer=native.observer();observer.monotonic=lambda:producer.epoch/1000
        if process is not None:observer.observe_process=process
        class Clock:
            sequence=0
            def read(self,after):self.sequence+=1;return dict(capturedEpochMs=producer.tick())
        clock=Clock();current={}
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            value=producer.packet();value.update(requestId=query['commandId'],runId=query['runId'])
            if mutate:mutate(value)
            current['raw']=json.dumps(value,separators=(',',':')).encode();current['value']=deepcopy(value);return native
        def execute(session,operation,arguments):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
            self.assertEqual('@org.example.client:documents/owned-results/'+keys.FILE,arguments['remotePath'])
            native.reads.append(deepcopy(arguments));return base64.b64encode(current['raw']).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            value=observer.world_web_keys(clock).read(RUN)
        self.assertEqual(current['value'],value);self.assertEqual(1,len(native.commands));self.assertEqual(1,len(native.reads))
        return value,current['raw']

    def test_actual_large_original_roundtrip_keeps_native_clock_source_and_old_default_decoder_bound(self):
        qt=QtKeys()
        for _ in range(200):qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'))
        value,raw=self.transport(qt);self.assertGreater(len(raw),400000);self.assertLess(len(raw),keys.LIMIT)
        self.assertEqual(400,len(keys.drained(value)['dispatches']))
        with self.assertRaises(NativeUIError):decode(raw.decode())
        self.assertEqual(value,decode(raw.decode(),limit=keys.LIMIT))

    def test_original_native_header_clock_and_pristine_process_binding_are_required(self):
        for fault in ('pid','clock','sourceBirth','before','instance'):
            qt=QtKeys();qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'))
            def mutate(value):
                if fault=='pid':value['processId']=43
                elif fault=='clock':value['clockAfter']['monotonicMs']+=500
                elif fault=='sourceBirth':value['source']['bornEpochMs']=value['clockAfter']['epochMs']+1
                elif fault=='before':value['clockBefore']['epochMs']=1
                else:value['instance']='unknown'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.transport(qt,mutate=mutate)

    def test_overflow_unknown_startup_and_held_release_remain_unavailable_for_retirement(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));value,_raw=self.transport(qt)
        with self.assertRaises(NativeUIError):keys.drained(value)
        qt=QtKeys();qt.started=qt.complete=False;value,_raw=self.transport(qt)
        with self.assertRaises(NativeUIError):keys.drained(value)
        qt=QtKeys()
        def overflow(value):value['source']['eventSequence']=3073
        with self.assertRaises(NativeUIError):self.transport(qt,mutate=overflow)

    def test_actual_afc_limit_rejects_excess_before_a_fabricated_empty_transcript_can_be_used(self):
        qt=QtKeys()
        def excess(value):value['source']['unexpectedBytes']='a'*keys.LIMIT
        with self.assertRaises(NativeUIError):self.transport(qt,mutate=excess)


if __name__=='__main__':unittest.main()
