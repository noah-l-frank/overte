"""Actual World publisher/Observer/Source files and HTTP; native modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_reads
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebWitnessDecodeRoundTests(unittest.TestCase):
    @contextmanager
    def owners(self):
        f=FeatureWorldWeb()
        try:
            call=dict(contractVersion=16,runId=f.network.run,afterSequence=0)
            f.primary.observe(call);f.secondary.observe(call);f.secondary.observe(call)
            with f.secondary.held():
                parts,_status=f.secondary.ensure();publisher=f.secondary.publisher(parts)
                yield f,parts['history'],publisher
        finally:f.close()
    def test_actual_connected_actor_publish_reuses_only_one_current_source_decode_per_journal_decode(self):
        with self.owners() as (f,history,publisher):
            self.assertEqual(2,len(publisher.state['records']))
            self.assertEqual(2,len(f.network.server.journal.snapshot(f.network.run)['entries']))
            self.assertIs(publisher.decode_context.__self__,history)
            self.assertIs(publisher.decode_context.__func__,history.validation_round.__func__)
            before=(deepcopy(f.requests),deepcopy(f.own),{key:value.native_calls for key,value in f.models.items()})
            raw=publisher.store.path.read_bytes();inode=publisher.store.path.stat().st_ino
            with patch.object(history.source,'_decode',wraps=history.source._decode) as source_decode:
                self.assertEqual(publisher.state,publisher.decode(publisher.previous))
                self.assertEqual(1,source_decode.call_count)
            self.assertIsNone(history._round);self.assertIsNone(history.source._round);self.assertIsNone(history.peer._round)
            self.assertEqual(before,(f.requests,f.own,{key:value.native_calls for key,value in f.models.items()}))
            self.assertEqual(raw,publisher.store.path.read_bytes());self.assertEqual(inode,publisher.store.path.stat().st_ino)
    def test_actual_source_new_inode_same_inode_and_changed_owner_context_refuse_no_post(self):
        for mode in ('new-inode','same-inode','membership','context'):
            with self.subTest(mode=mode),self.owners() as (f,history,publisher):
                validate=publisher.validate_original;altered=[];before=deepcopy(f.requests)
                raw=publisher.store.path.read_bytes();inode=publisher.store.path.stat().st_ino
                def changed(value):
                    measured=validate(value)
                    if not altered:
                        altered.append(True);path=history.source.store.path;body=path.read_bytes()
                        if mode=='new-inode':
                            other=path.with_suffix('.replacement');other.write_bytes(body);other.chmod(0o600);other.replace(path)
                        elif mode=='same-inode':path.write_bytes(body+b'\n')
                        elif mode=='membership':
                            orphan=path.with_name('unowned-created-during-decode.json');orphan.write_bytes(b'{}');orphan.chmod(0o600)
                        else:history.origins['foreign']='http://foreign-owner-drift.invalid'
                    return measured
                with patch.object(publisher,'validate_original',side_effect=changed),self.assertRaises(NativeUIError):publisher.decode(publisher.previous)
                self.assertTrue(altered);self.assertEqual(before,f.requests)
                self.assertEqual(raw,publisher.store.path.read_bytes());self.assertEqual(inode,publisher.store.path.stat().st_ino)
                self.assertIsNone(history._round);self.assertIsNone(history.source._round)
    def test_new_file_census_replays_actual_source_and_observation_membership_each_time(self):
        with self.owners() as (_f,history,publisher):
            seen=[]
            for _ in range(2):
                with original_reads(fresh=True) as reads:self.assertEqual(publisher.state,publisher.decode(publisher.previous))
                self.assertIn(publisher.record_store(1).path,reads)
                self.assertIn(history.record_store(1).path,reads)
                self.assertIn(history.source.store.path,reads);seen.append(reads)
                self.assertIsNone(history._round)
            self.assertIsNot(seen[0],seen[1])
    def test_real_round_exit_rejects_source_change_after_literal_decode_before_next_wal_save(self):
        with self.owners() as (f,history,publisher):
            actual=publisher.decode_context;before=deepcopy(f.requests)
            raw=publisher.store.path.read_bytes();inode=publisher.store.path.stat().st_ino
            @contextmanager
            def exiting():
                with actual():
                    yield
                    path=history.source.store.path;path.write_bytes(path.read_bytes()+b'\n')
            publisher.decode_context=exiting
            with self.assertRaises(NativeUIError):publisher.save()
            self.assertEqual(before,f.requests);self.assertEqual(raw,publisher.store.path.read_bytes());self.assertEqual(inode,publisher.store.path.stat().st_ino)
            self.assertIsNone(history._round);self.assertIsNone(history.source._round);self.assertIsNone(history.peer._round)


if __name__=='__main__':unittest.main()
