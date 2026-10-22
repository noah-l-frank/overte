"""Synthetic Qt/SDK boundaries only; no native, device or renderer execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import TokenEmoteUI,NAMES
from ios.adapters.emote_controls import IOSEmoteIO,project
from self_tests.test_token_emote_ui import EmoteBoundary


class NativeBoundary(EmoteBoundary):
    def __init__(self):
        super().__init__();self.instance=str(uuid.uuid4());self.generation=str(uuid.uuid4());self.requests=[]
    def capture(self):
        value=super().capture();scope=value['scope'];rows=value['controls']
        for row in rows:
            row['token']=str(uuid.UUID(row['token']));row['frame']=dict(x=0.,y=0.,width=40.,height=40.)
            if not row['id'].startswith('emote.'):row.pop('inputReady')
        return dict(schemaVersion=1,instance=scope['instance'],frameSpace='qt-window-logical',
            processId=scope['processId'],sampleEpochMs=scope['capturedEpochMs'],elapsedMs=scope['elapsedMs'],
            lastSequence=scope['sequence'],tabletShown=value['open'],ready=value['ready'],controls=rows,
            emoteControlsVersion=1,emoteGeneration=scope['generation'],emoteSourceSequence=scope['sourceSequence'])
    def deliver(self,request):
        self.requests.append(deepcopy(request));scope=project(self.capture())['scope']
        need(request['instance']==self.instance and request['sequence']==self.command_sequence+1
            and request['observedElapsedMs']<=scope['elapsedMs'])
        matches=[r for r in project(self.capture())['controls'] if r['token']==request['fieldToken']]
        need(len(matches)==1 and matches[0]['inputReady']);row=matches[0]
        self.command_sequence+=1
        identifier=row['id'];self.actions.append(identifier)
        if self.fault=='lost':raise NativeUIError('Synthetic lost return after actual delivery')
        if identifier=='emote.entry':self.page=True
        elif identifier=='tablet.home':self.page=False
        elif identifier=='emote.grid':
            direction=request['direction'];self.offset=max(0,min(6,self.offset+(-2 if direction=='up' else 2)))
            self.moving_until=self.clock+.2
        elif identifier.startswith('emote.play.'):
            name=identifier[len('emote.play.'):];self.active='' if self.active==name else name


class IOSEmoteControlsTests(unittest.TestCase):
    def ui(self):
        native=NativeBoundary();io=IOSEmoteIO(native)
        return native,io,TokenEmoteUI(io,native.intent,monotonic=lambda:native.clock,sleep=native.sleep)
    def test_actual_ios_uuid_tokens_and_native_clocks_are_preserved(self):
        native,io,_=self.ui();value=io.capture();original=io.original_packet
        self.assertEqual(original['sampleEpochMs'],value['scope']['capturedEpochMs'])
        self.assertEqual(original['emoteSourceSequence'],value['scope']['sourceSequence'])
        self.assertEqual(original['controls'][0]['token'],value['controls'][0]['token'])
        self.assertNotIn('animation',value)
    def test_all_ten_names_use_actual_original_tokens_and_native_sequence(self):
        native,io,ui=self.ui();ui.open()
        for name in NAMES:ui.play(name)
        ui.cancel();ui.close()
        self.assertFalse(native.page);self.assertEqual('',native.active)
        self.assertEqual(len(native.requests),native.command_sequence)
        self.assertEqual(list(range(1,len(native.requests)+1)),[r['sequence'] for r in native.requests])
        self.assertTrue(all('text' not in r for r in native.requests));self.assertIn('emote.grid',native.actions)
    def test_changed_real_token_refuses_delivery(self):
        native,io,_=self.ui();before=io.capture();native.active='Waving'
        with self.assertRaises(NativeUIError):io.activate('emote.entry',reference=before)
        self.assertEqual([],native.requests)
    def test_missing_generation_or_source_sequence_prevents_input(self):
        native,io,_=self.ui();original=native.capture()
        for key in ('emoteControlsVersion','emoteGeneration','emoteSourceSequence'):
            value=deepcopy(original);value.pop(key)
            with self.assertRaises((NativeUIError,KeyError)):project(value)
        self.assertEqual([],native.requests)
    def test_lost_input_result_propagates_without_transport_retry(self):
        native,io,_=self.ui();before=io.capture();native.fault='lost'
        with self.assertRaises(NativeUIError):io.activate('emote.entry',reference=before)
        self.assertEqual(1,len(native.requests));self.assertEqual(1,native.command_sequence)

if __name__=='__main__':unittest.main()
