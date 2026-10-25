"""Actual private raw/query owners and parsers; native/Web sources modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_marker_web_receipts import IOSAvatarMarkerWebReceipts
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL
from ios.self_tests.test_ios_graphics_measurements import BINDING
from self_tests.test_native_feature_observation import Boundary


class AvatarMarkerWebReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'ios-avatar-primary-marker-web.json');self.clock=0.;self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.native=Boundary();self.web=ClosureBoundary();self.web.version=5;self.web.retired=1
        self.web.resources['policy-grant']=dict(created=1,retired=1,pending=0)
        self.web.mutate=lambda value:value.update(capturedEpochMs=self.epoch())
        self.native.mutate=self.native_source;self.native_reader=self.native.reader(ios=True,native_clock_bound=False);self.native_reader.pid=42
        self.native_reader.monotonic=lambda:self.clock;self.native_reader.clock_ms=self.epoch
        self.reader=self.web.reader();self.reader.monotonic=lambda:self.clock
        self.native_reader.sleep=self.reader.sleep=lambda seconds:setattr(self,'clock',self.clock+seconds)
        self.reader.clock_ms=lambda:self.native_reader.read(self.native_reader.sequence)['capturedEpochMs']
        send=self.native_reader.send
        def owned_native(query):
            p=unpack(self.store.read()['payload'])[0]['pending'];self.assertEqual(query,p['nativeQueries'][-1]['query']);return send(query)
        self.native_reader.send=owned_native
        send_web=self.reader.send
        def owned_web(query):
            p=unpack(self.store.read()['payload'])[0]['pending'];self.assertEqual(query,p['query']);return send_web(query)
        self.reader.send=owned_web
    def epoch(self):return 20000+round(self.clock*1000)
    def native_source(self,value):
        self.clock+=.005;epoch=self.epoch();value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch)
        value['animation']['capturedEpochMs']=epoch;value['animation']['clip']['evaluatedEpochMs']=epoch;value['animationFence']['requestedEpochMs']=epoch
    def owner(self):
        return IOSAvatarMarkerWebReceipts(self.store,self.root,BINDING,RUN,'primary',self.lock,lambda:True,
            native=self.native_reader,reader=self.reader,fixture_url=URL,epoch_ms=lambda:90000+self.clock*1000,monotonic=lambda:self.clock)
    def archive(self,owner):
        return IOSAvatarMarkerWebReceipts.archive(owner.previous,store=self.store,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock,fixture_url=URL)
    def test_actual_query_raws_and_unbound_native_bracket_are_retained_without_world_or_new_transport(self):
        owner=self.owner();row=owner.capture();packet=owner.packet(row);self.assertEqual(5,packet['packet']['iosWebClosureVersion'])
        self.assertTrue(packet['packet']['contexts'][0]['resources']['vulkan-image']['pending'])
        self.assertGreater(len(row['partial']['nativeQueries']),2)
        counts=(len(self.native.commands),len(self.web.commands));files={p:(p.stat().st_ino,p.read_bytes()) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(packet,self.archive(owner).packet(row));self.assertEqual(counts,(len(self.native.commands),len(self.web.commands)))
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in files})
    def test_lost_web_return_keeps_issued_source_and_distinct_next_query_extends_original_floor(self):
        owner=self.owner();original=self.reader.original;lost=[]
        def raw():
            value=original()
            if not lost:lost.append(True);raise OSError('Actual Web return unavailable')
            return value
        with patch.object(self.reader,'original',side_effect=raw),self.assertRaises(NativeUIError):owner.capture()
        old=deepcopy(owner.state['pending']['query']);commands=len(self.web.commands)
        owner=self.owner();owner.recover();self.assertEqual(commands,len(self.web.commands))
        self.assertEqual('abandoned',owner.state['rows'][0]['status'])
        row=owner.capture();self.assertNotEqual(old,row['partial']['query']);self.assertEqual(commands+1,len(self.web.commands))
    def test_same_inode_abandoned_raw_mutation_cannot_be_replayed(self):
        owner=self.owner();write=owner.originals.write;lost=[]
        def failing(index,frame):
            result=write(index,frame)
            if owner.slot[0]=='web' and not lost:lost.append(True);raise OSError('Lost saved raw return')
            return result
        with patch.object(owner.originals,'write',side_effect=failing),self.assertRaises(NativeUIError):owner.capture()
        owner=self.owner();owner.recover();ref=owner.state['rows'][0]['partial']['raws'][0];path=owner.originals.path(ref);inode=path.stat().st_ino
        with path.open('ab') as stream:stream.write(b' ')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.owner()
    def test_stale_or_malformed_raws_stay_private_bytes_and_never_supply_this_queries_source(self):
        owner=self.owner();native=self.native_reader.original;web=self.reader.original;seen=set()
        def native_raw():
            key=self.native.sample['requestId']
            if key not in seen:seen.add(key);return '{'
            return native()
        web_seen=[]
        def web_raw():
            if not web_seen:web_seen.append(True);return '{'
            return web()
        with patch.object(self.native_reader,'original',side_effect=native_raw),patch.object(self.reader,'original',side_effect=web_raw):
            row=owner.capture()
        self.assertEqual('{',owner.raw(row['partial']['raws'][0])[1]);self.assertEqual(2,len(row['partial']['raws']))
        self.assertTrue(all(len(r['raws'])>=2 for r in row['partial']['nativeQueries']))
        self.assertEqual(owner.packet(row),self.archive(owner).packet(row))

    def test_planned_dangling_original_is_not_absence(self):
        owner=self.owner();storage=owner.originals.intent;injected=[]
        def malicious(kind,ref):
            result=storage(kind,ref)
            if ref['phase']=='planned' and not injected:
                injected.append(True);owner.originals.path(ref).symlink_to('missing-source-original')
                raise OSError('Planned filename replaced before open')
            return result
        with patch.object(owner.originals,'intent',side_effect=malicious),self.assertRaises(NativeUIError):owner.capture()
        before=len(self.native.commands)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,len(self.native.commands))

    def test_real_zero_byte_opened_inode_is_archived_and_same_inode_append_is_refused(self):
        owner=self.owner();storage=owner.originals.intent;lost=[]
        def opening(kind,ref):
            result=storage(kind,ref)
            if ref['phase']=='opened' and not lost:lost.append(True);raise OSError('Actual empty open return unavailable')
            return result
        with patch.object(owner.originals,'intent',side_effect=opening),self.assertRaises(NativeUIError):owner.capture()
        owner=self.owner();owner.recover();row=owner.state['rows'][0];self.assertEqual('abandoned',row['status'])
        ref=row['partial']['nativeQueries'][0]['raws'][0];path=owner.originals.path(ref);inode=path.stat().st_ino
        self.assertEqual(0,path.stat().st_size);self.assertEqual(0,row['files'][0]['bytes'])
        self.assertEqual('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',row['files'][0]['sha256'])
        from adapters.original_file_reads import scope as read_scope
        commands=len(self.native.commands)
        with read_scope(fresh=True) as reads:self.archive(owner)
        self.assertIn(path,reads);self.assertEqual(commands,len(self.native.commands))
        with path.open('ab') as stream:stream.write(b'x')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.owner()

    def test_candidate_changed_after_final_save_refuses_fresh_return_but_keeps_originals_historical(self):
        owner=self.owner();live=[True];owner.guard=lambda:live[0];write=self.store.write
        def saved(value,previous):
            write(value,previous)
            if owner.state['rows'] and owner.state['pending'] is None:live[0]=False
        with patch.object(self.store,'write',side_effect=saved),self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(1,len(owner.state['rows']));self.archive(owner)

    def test_actual_large_valid_web_source_uses_real_raw_file_without_metadata_limit_increase(self):
        def large(value):
            value['capturedEpochMs']=self.epoch();base=deepcopy(value['contexts'][0]);index=1
            while len(json.dumps(value).encode())<240000:
                index+=1;row=deepcopy(base);row['id']=index;row['descriptor']['handle']=index
                value['contexts'].append(row)
        self.web.mutate=large;owner=self.owner();row=owner.capture();packet=owner.packet(row)
        query,raw=owner.raw(row['partial']['raws'][0]);self.assertGreaterEqual(len(raw.encode()),240000)
        self.assertLessEqual(len(raw.encode()),262144);self.assertGreater(len(packet['packet']['contexts']),50)
        self.assertLessEqual(len(self.store.path.read_bytes()),49152)
        self.assertEqual(packet,self.archive(owner).packet(row))

    def test_complete_receipt_return_loss_adopts_only_exact_local_original_and_never_queries_again(self):
        owner=self.owner();write=owner.originals.write;lost=[]
        def writing(index,frame):
            result=write(index,frame)
            if owner.slot[0]=='receipt' and not lost:lost.append(True);raise OSError('Actual complete local return unavailable')
            return result
        with patch.object(owner.originals,'write',side_effect=writing),self.assertRaises(OSError):owner.capture()
        counts=(len(self.native.commands),len(self.web.commands));pending=deepcopy(owner.state['pending'])
        rebuilt=self.owner();rebuilt.recover();self.assertEqual(counts,(len(self.native.commands),len(self.web.commands)))
        self.assertEqual('observed',rebuilt.state['rows'][0]['status']);self.assertEqual(pending,rebuilt.state['rows'][0]['partial'])
        self.assertEqual(rebuilt.packet(rebuilt.state['rows'][0]),self.archive(rebuilt).packet(rebuilt.state['rows'][0]))

    def test_modern_host_utc_and_independent_native_offset_are_original_values_not_retimed(self):
        owner=self.owner();owner.epoch_ms=lambda:1800000000000+self.clock*1000
        row=owner.capture();value=owner.packet(row);join=value['clockJoin']
        self.assertGreaterEqual(join['hostBeforeEpochMs'],1800000000000)
        self.assertLess(join['nativeBefore']['capturedEpochMs'],30000)
        self.assertEqual(value,self.archive(owner).packet(row))

    def test_slow_original_storage_cannot_refresh_its_native_or_host_acquisition(self):
        owner=self.owner();write=self.store.write;slow=[]
        def writing(value,previous):
            write(value,previous)
            if owner.state['rows'] and owner.state['pending'] is None and not slow:self.clock+=1.501;slow.append(True)
        with patch.object(self.store,'write',side_effect=writing),self.assertRaises(NativeUIError):owner.capture()
        self.assertTrue(owner.state['rows']);self.archive(owner)


if __name__=='__main__':unittest.main()
