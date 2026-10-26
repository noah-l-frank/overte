"""Durable original-source recovery and real distinct host quiet intervals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.snapshot_share_query_owner import SnapshotShareQueryOwner,ShareExtensionQueryPending
from ios.self_tests.snapshot_share_query_domain import ShareQueryDomain
from ios.self_tests.snapshot_companion_domain import RUN
from ios.self_tests import test_ios_snapshot_share_process as process_fixture


class SnapshotShareQueryTests(unittest.TestCase):
    def pins(self,d):
        return {path.name:(path.stat().st_dev,path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns,path.stat().st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
            for path in d.root.iterdir() if path.name.startswith(('share-extension-query-frame-','share-extension-receiver-frame-'))}
    def test_actual_node_PID_original_receiver_bytes_and_both_real_quiet_clocks_survive_archive(self):
        d=ShareQueryDomain(self)
        with d.queries() as owner:
            live=owner.query('receiver-live');self.assertEqual(84,live['anchor']['pid']);receiver=d.bind(owner);self.assertEqual(84,receiver['processId'])
            self.assertEqual(d.metadata,owner.receiver()[1]);d.node.call('mode',value='absent');quiet=owner.quiet()
            self.assertGreaterEqual(quiet['nodeMilliseconds'],3000);self.assertGreaterEqual(quiet['hostMilliseconds'],3000)
            self.assertTrue(quiet['filesystemRetirementRequired']);self.assertTrue(quiet['wholeFeatureRequired'])
            store=owner.store
        pins=self.pins(d);stats=d.node.call('stats');calls=len(d.sdk)
        with d.source_lock.held():
            history=SnapshotShareQueryOwner.history(store,d.source_lock,d.binding,RUN,d.fixture_url,d.ipa,d.admission_store)
            self.assertEqual(quiet,history.quiet_result());self.assertEqual(live,history.query_original(1))
            with self.assertRaises(NativeUIError):history.query('new-live')
        self.assertEqual(pins,self.pins(d));self.assertEqual(stats,d.node.call('stats'));self.assertEqual(calls,len(d.sdk));self.assertEqual(4,d.query_deliveries)

    def test_lost_SDK_return_reads_unchanged_source_JSON_once_without_second_query_or_clock(self):
        d=ShareQueryDomain(self);d.lose=True
        with d.queries() as owner,self.assertRaises(NativeUIError):owner.query('live')
        stats=d.node.call('stats');self.assertEqual(1,stats['queries'])
        with d.queries() as owner:
            packet=owner.query('live');frame,_packet=owner.frame(owner.state['queries'][0]);raw=frame['original']['raw'];before=packet['clockBefore'];after=packet['clockAfter']
            self.assertEqual(84,packet['anchor']['pid'])
        pins=self.pins(d)
        with d.queries() as owner:
            self.assertEqual(packet,owner.query('live'));restored,_=owner.frame(owner.state['queries'][0])
            self.assertEqual(raw,restored['original']['raw']);self.assertEqual(before,packet['clockBefore']);self.assertEqual(after,packet['clockAfter'])
        self.assertEqual(pins,self.pins(d));self.assertEqual(stats['services'],d.node.call('stats')['services']);self.assertEqual(1,d.query_deliveries)

    def test_unknown_undelivered_query_remains_durable_and_cannot_send_again_or_start_new_query(self):
        d=ShareQueryDomain(self);d.ignore=True
        with d.queries() as owner,self.assertRaises(NativeUIError):owner.query('live')
        d.ignore=False
        for _ in range(2):
            with d.queries() as owner:
                with self.assertRaises(NativeUIError):owner.query('live')
                with self.assertRaises(NativeUIError):owner.query('another')
                self.assertEqual('issued',owner.state['queries'][0]['phase'])
        self.assertEqual(1,d.query_deliveries);self.assertEqual(0,d.node.call('stats')['queries'])

    def test_saved_original_before_parent_CAS_recovers_same_file_without_source_lookup(self):
        d=ShareQueryDomain(self)
        with d.queries() as owner:
            actual=owner.frames.intent
            def lost(kind,value):
                actual(kind,value)
                if value['phase']=='saved':raise OSError('Declared parent return lost after exact original save')
            owner.frames.intent=lost
            with self.assertRaises(OSError):owner.query('live')
        pins=self.pins(d);stats=d.node.call('stats')
        with d.queries() as owner:self.assertEqual(84,owner.query('live')['anchor']['pid'])
        self.assertEqual(pins,self.pins(d));self.assertEqual(stats,d.node.call('stats'));self.assertEqual(1,d.query_deliveries)

    def test_partial_opened_original_freezes_original_inode_and_never_queries_or_rewrites_it(self):
        d=ShareQueryDomain(self)
        with d.queries() as owner:
            actual=owner.frames.intent
            def lost(kind,value):
                actual(kind,value)
                if value['phase']=='opened':raise OSError('Declared original write interrupted')
            owner.frames.intent=lost
            with self.assertRaises(OSError):owner.query('live')
        paths=[path for path in d.root.iterdir() if path.name.startswith('share-extension-query-frame-')];self.assertEqual(1,len(paths));self.assertEqual(b'',paths[0].read_bytes())
        pins=self.pins(d);stats=d.node.call('stats')
        with self.assertRaises(NativeUIError):
            with d.queries():pass
        self.assertEqual(pins,self.pins(d));self.assertEqual(stats,d.node.call('stats'));self.assertEqual(1,d.query_deliveries)

    def test_foreign_receiver_PID_is_retained_as_unqualified_original_and_cannot_replace_binding(self):
        d=ShareQueryDomain(self);record=json.loads(d.metadata);record['processId']=85
        path=d.documents/('snapshot-share-'+RUN)/'original-extension.json';path.write_text(json.dumps(record))
        with d.queries() as owner:
            owner.query('live')
            with self.assertRaises(NativeUIError):d.bind(owner)
        pins=self.pins(d);path.write_bytes(d.metadata)
        with self.assertRaises(NativeUIError):
            with d.queries():pass
        self.assertEqual(pins,self.pins(d));self.assertEqual(1,d.query_deliveries)

    def test_bundle_absence_with_original_PID_still_running_cannot_fill_the_quiet_window(self):
        d=ShareQueryDomain(self)
        with d.queries() as owner:
            owner.query('live');d.bind(owner);d.node.call('mode',value='held')
            with self.assertRaises(ShareExtensionQueryPending):owner.quiet()
            self.assertEqual([],owner.state['quiet']);self.assertEqual(2,len(owner.state['queries']))
        d.node.call('mode',value='absent')
        with d.queries() as owner:self.assertGreaterEqual(owner.quiet()['nodeMilliseconds'],3000)
        self.assertEqual(5,d.query_deliveries)

    def test_late_original_is_retained_historically_without_new_source_clocks_or_quiet_qualification(self):
        d=ShareQueryDomain(self);d.lose=True
        with d.queries() as owner,self.assertRaises(NativeUIError):owner.query('live')
        time.sleep(5.6)
        with d.queries() as owner:
            original=owner.query('live');frame,_packet=owner.frame(owner.state['queries'][0])
            self.assertGreaterEqual(frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs'],5500)
            with self.assertRaises(NativeUIError):owner.qualified(1)
            fresh=owner.query('fresh-live');owner.qualified(2)
            self.assertEqual(original['anchor'],fresh['anchor']);self.assertEqual(1,owner.state['anchorQuery'])
        self.assertEqual(2,d.query_deliveries)

    def test_same_byte_replacement_cannot_supply_the_retained_original_file_identity(self):
        d=ShareQueryDomain(self)
        with d.queries() as owner:owner.query('live')
        path=next(path for path in d.root.iterdir() if path.name.startswith('share-extension-query-frame-'));raw=path.read_bytes();inode=path.stat().st_ino
        replacement=path.with_name('replacement.json');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
        self.assertEqual(raw,path.read_bytes());self.assertNotEqual(inode,path.stat().st_ino);stats=d.node.call('stats')
        with self.assertRaises(NativeUIError):
            with d.queries():pass
        self.assertEqual(stats,d.node.call('stats'));self.assertEqual(1,d.query_deliveries)


class SnapshotShareOriginalReplyTests(unittest.TestCase):
    def node(self,body):return process_fixture.SnapshotShareProcessTests.node(self,body)
    def test_saved_source_JSON_lookup_never_reexecutes_DVT_retimes_or_returns_mutable_cache(self):
        self.node(r'''
const n=live(),packet=await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1)),counts=n.counts();
const original=source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1));assert.deepEqual(JSON.parse(original.raw),packet);
packet.anchor.pid=77;original.raw='changed';const same=source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1));
assert.equal(JSON.parse(same.raw).anchor.pid,84);assert.deepEqual(n.counts(),counts);
assert.deepEqual(source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1)),same);
assert.throws(()=>source.snapshotShareExtensionOriginal(n.driver,'org.foreign.archive',nonce(1)),/SOURCE_UNAVAILABLE/);
assert.throws(()=>source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(2)),/SOURCE_UNAVAILABLE/);
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),out={exports:{}};
vm.runInNewContext(fs.readFileSync(path.join(path.dirname(process.argv[1]),'index.cjs'),'utf8'),{module:out,exports:out.exports,require(name){
 if(name==='appium/plugin')return {BasePlugin:class{}};if(name==='./process_observer.cjs')return source;if(name==='./read_sdk.cjs')return ()=>sdk;throw Error('unexpected dependency');}});
const plugin=new out.exports.OverteProcessPlugin(),next=async()=>{throw Error('No fallback');};
assert.deepEqual(await plugin.execute(next,n.driver,'mobile: overteSnapshotShareExtensionOriginal',[{bundleId:bundle,commandId:nonce(1)}]),same);
await assert.rejects(plugin.execute(next,n.driver,'mobile: overteSnapshotShareExtensionOriginal',[{bundleId:bundle,commandId:nonce(1),pid:84}]),/SOURCE_UNAVAILABLE/);
assert.deepEqual(n.counts(),counts);
''')
    def test_pending_original_has_no_payload_and_only_actual_closed_completion_becomes_original(self):
        self.node(r'''
const n=live();let release;n.driver.remoteXPCFacade.requireService=()=>new Promise(resolve=>release=resolve);
const pending=source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));await tick();
const before=source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1));assert.equal(before.status,'issued');assert.equal(before.raw,null);
release(n.dvt);const packet=await pending;const after=source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1));
assert.equal(after.status,'complete');assert.deepEqual(JSON.parse(after.raw),packet);assert.equal(n.socket.destroyed,true);
''')
    def test_failed_original_cannot_invent_absence_or_clear_owned_connection(self):
        self.node(r'''
const n=live();n.service.close=async()=>{};await assert.rejects(source.observeSnapshotShareExtension(n.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
const original=source.snapshotShareExtensionOriginal(n.driver,bundle,nonce(1));assert.equal(original.status,'failed');assert.equal(original.raw,null);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);n.socket.destroy();
''')


if __name__=='__main__':unittest.main()
