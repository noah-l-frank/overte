"""Actual CLI stdout boundary and original Actor getter fences, explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_peer import PicoAudioPeer
from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
from self_tests.test_pico_audio_pc_start import AudioPCStartTests


class AudioRawTransportTests(unittest.TestCase):
    setUp=AudioPCStartTests.setUp
    def records(self):return [row for page in self.actor.raws.pages.values() for row in page['receipts'] if row is not None]
    def test_actual_cli_stdout_one_mib_noise_is_durable_before_utf8_or_json_parser(self):
        raw=random.Random(717).randbytes(1024*1024);peer=PicoAudioPeer(self.pc.config,None,lambda:True)
        peer.bind_literal_source(self.actor.literal_source());before=len(self.records())
        with patch('adapters.pico4.audio_peer.subprocess.run',return_value=SimpleNamespace(stdout=raw,returncode=0)) as call:
            with self.assertRaises((ValueError,UnicodeDecodeError,NativeUIError)):peer.request('status')
        self.assertEqual(1,call.call_count);self.assertEqual(before+1,len(self.records()))
        self.assertEqual(raw,self.actor.raws.literal(peer.last_raw_reference))
    def test_original_native_getter_quarter_mib_noise_is_sealed_before_decoder(self):
        import json,string
        rng=random.Random(716);body=''.join(rng.choice(string.ascii_letters+string.digits) for _ in range(256*1024-2))
        self.f.native.native.sample=body;raw=json.dumps(body)
        self.assertEqual(256*1024,len(raw.encode()))
        with self.actor.held():
            self.actor._begin('native-observation',None)
            returned=self.actor.native.original()
            reference=self.actor.state['pending']['raws'][-1]['rawReference']
            self.assertEqual(raw,returned);self.assertEqual(raw,self.actor.raws.literal(reference))
            from adapters.native_feature_observation import validate
            with self.assertRaises(NativeUIError):validate(decode(returned),'f'*32,123,20000)
        self.assertIsNotNone(self.actor.state['pending'])
    def test_actual_cli_stdout_one_mib_nul_survives_existing_parser_limit(self):
        raw=b'\0'*(1024*1024);peer=PicoAudioPeer(self.pc.config,None,lambda:True)
        peer.bind_literal_source(self.actor.literal_source())
        with patch('adapters.pico4.audio_peer.subprocess.run',return_value=SimpleNamespace(stdout=raw,returncode=0)):
            with self.assertRaises(NativeUIError):peer.request('status')
        self.assertEqual(raw,self.actor.raws.literal(peer.last_raw_reference))
    def raw_source(self,label):return self.actor.raw_hooks[label][2]
    def test_actual_cli_capacity_refusal_calls_zero_subprocess(self):
        (self.pc.root/'owned-capacity.bin').write_bytes(b'\0'*(16*1024*1024))
        peer=PicoAudioPeer(self.pc.config,None,lambda:True);peer.bind_literal_source(self.actor.literal_source())
        with patch('adapters.pico4.audio_peer.subprocess.run') as call,self.assertRaises(NativeUIError):peer.request('status')
        call.assert_not_called()
    def test_actual_getter_capacity_refusal_never_calls_captured_source(self):
        (self.pc.root/'owned-capacity.bin').write_bytes(b'\0'*(16*1024*1024))
        # hook's first effect must be reservation, before its captured callback.
        hook=self.raw_source('pages');before=self.f.native.pages.sequence
        with self.assertRaises(NativeUIError):hook()
        self.assertEqual(before,self.f.native.pages.sequence)
    def test_actual_native_dispatch_capacity_refusal_sends_zero_original_command(self):
        (self.pc.root/'owned-capacity.bin').write_bytes(b'\0'*(16*1024*1024))
        before=deepcopy(self.f.native.native.commands)
        with self.actor.held():
            self.actor._begin('native-observation',None)
            with self.assertRaises(NativeUIError):self.actor.native.read(0,require_recorded_history=True)
        self.assertEqual(before,self.f.native.native.commands)

    def test_original_stdout_survives_late_actor_header_loss_but_next_dispatch_refuses(self):
        peer=PicoAudioPeer(self.pc.config,None,lambda:True);peer.bind_literal_source(self.actor.literal_source())
        literal=b'{"actualObservedBeforeHeaderLoss":true}';before=len(self.records())
        def returned(*args,**kwargs):
            path=self.actor.header.path;replacement=path.with_name('counter-foreign-header')
            replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
            return SimpleNamespace(stdout=literal,returncode=0)
        with patch('adapters.pico4.audio_peer.subprocess.run',side_effect=returned) as call:
            try:peer.request('status')
            except NativeUIError:pass
            self.assertEqual(1,call.call_count)
        self.assertEqual(before+1,len(self.records()),'Already returned stdout was lost behind admission guard')
        self.assertEqual(literal,self.actor.raws.literal(peer.last_raw_reference))
        with patch('adapters.pico4.audio_peer.subprocess.run') as call,self.assertRaises(NativeUIError):peer.request('status')
        call.assert_not_called()
        before=deepcopy(self.f.native.actions)
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(before,self.f.native.actions)

    def test_parser_refusal_keeps_literal_and_stops_next_real_cli_dispatch(self):
        peer=PicoAudioPeer(self.pc.config,None,lambda:True);peer.bind_literal_source(self.actor.literal_source())
        literal=b'\0'*(1024*1024)
        with patch('adapters.pico4.audio_peer.subprocess.run',return_value=SimpleNamespace(stdout=literal,returncode=0)) as call:
            with self.assertRaises(NativeUIError):peer.request('status')
            self.assertEqual(1,call.call_count)
            with self.assertRaises(NativeUIError):peer.request('status')
            self.assertEqual(1,call.call_count)
        self.assertTrue(self.actor.raws.stopped);self.assertFalse(self.actor.raws.failed)
        self.assertEqual(literal,self.actor.raws.literal(peer.last_raw_reference))

    def test_missing_raw_root_refuses_actual_cli_dispatch_without_adoption(self):
        archive=self.actor.raws;archive.store.path.unlink()
        peer=PicoAudioPeer(self.pc.config,None,lambda:True);peer.bind_literal_source(self.actor.literal_source())
        with patch('adapters.pico4.audio_peer.subprocess.run') as call,self.assertRaises(NativeUIError):peer.request('status')
        call.assert_not_called();self.assertFalse(archive.store.path.exists())
    def test_replaced_append_lock_inode_refuses_actual_getter(self):
        archive=self.actor.raws;path=archive.lock.path;replacement=path.with_name('foreign-append-lock')
        replacement.touch(mode=0o600);os.replace(replacement,path);before=self.f.native.pages.sequence
        with self.assertRaises(NativeUIError):self.actor.pages.read()
        self.assertEqual(before,self.f.native.pages.sequence)

    def test_legacy_actor1_passive_reader_retains_actual_old_layout_without_migration(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.chat_journey.source_chunks import ChatSourceChunks
        from adapters.script_journey.history import pack
        from adapters.pico4.audio_pc_originals import AudioPCActorOriginals
        from tempfile import mkdtemp
        root=Path(mkdtemp(prefix='pico-audio-legacy1-'));store=PrivateFeatureState(root/'audio-recipe-pc-actor.json')
        scope=dict(audioPCActorVersion=1,role='historical-test-only');history=ChatSourceChunks(store,scope)
        value=dict(audioPCActorVersion=1,scope=scope,phase='reading',chunks=[],payload=pack([dict(pending=None)]));store.write(value,None)
        frame=dict(kind='legacy-original',raws=[dict(label='native',raw='actual retained old literal')])
        chunks=history.append(frame,[]);next_value=dict(value,chunks=chunks);store.write(next_value,value)
        before={str(p):p.read_bytes() for p in root.iterdir()};reader=AudioPCActorOriginals(store.path);self.addCleanup(reader.close)
        self.assertEqual(frame,reader.original(0));self.assertEqual(1,reader.report()['actorVersion'])
        self.assertFalse(reader.report()['liveAuthority']);self.assertFalse(reader.report()['completeRawTransport'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.iterdir()})
        print('Retained original Audio legacy1 history:',root,flush=True)

    def test_original_cli_worker_return_is_retained_while_primary_source_lock_is_held(self):
        import threading
        peer=PicoAudioPeer(self.pc.config,None,lambda:True);peer.bind_literal_source(self.actor.literal_source())
        completed=threading.Event();errors=[];literal=b'{"actualOriginal":true}'
        def worker():
            try:peer.request('status')
            except BaseException as error:errors.append(error)
            finally:completed.set()
        with patch('adapters.pico4.audio_peer.subprocess.run',return_value=SimpleNamespace(stdout=literal,returncode=0)):
            with self.f.owner.lock.held():
                thread=threading.Thread(target=worker);thread.start()
                self.assertTrue(completed.wait(1),'Worker archival waited on held Primary source lock')
                self.assertEqual([],errors);self.assertEqual(literal,self.actor.raws.literal(peer.last_raw_reference))
            thread.join(1);self.assertFalse(thread.is_alive())

    def test_passive_reader_exposes_partial_tail_without_claiming_live_authority(self):
        archive=self.actor.raws;token=archive.reserve('pc',dict(action='partial'),32)
        # A genuine append was fsynced, then its metadata response was lost.
        with archive.lock.held():
            if archive.writer is None:archive._new_part()
            writer=archive.writer;writer.require(writer.fd);os.write(writer.fd,b'uncertain');os.fsync(writer.fd)
        archive.failed=True
        passive=AudioPCRawOriginals(archive.path);self.addCleanup(passive.close)
        result=passive.report();self.assertFalse(result['liveAuthority']);self.assertTrue(result['pendingOrUncertain'])
        self.assertTrue(any(row.get('unconfirmedTailBytes')==9 for row in result['unconfirmed']))

if __name__=='__main__':unittest.main()
