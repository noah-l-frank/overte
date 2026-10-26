"""Actual repository plugin and host context over fake DVT/OS and real sockets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_share_process as source
from ios.adapters.snapshot_companion_artifact import share_artifact
from ios.self_tests import test_ios_process_plugin as plugin_fixture
from ios.self_tests.snapshot_share_admission_domain import ShareAdmissionDomain,BUNDLE
from ios.self_tests.snapshot_companion_domain import RUN
from ios.self_tests.test_ios_snapshot_share_original import received


PLUGIN=Path(__file__).resolve().parents[1]/'process_plugin/process_observer.cjs'
BOOT=plugin_fixture.BOOT.replace("assert.equal(bundle,'org.example.overte')","assert.equal(bundle,'org.example.overte.receiver')")+r'''
const nonce=n=>'ios-'+n.toString(16).padStart(32,'0');
function live() {const n=native(4,84);n.checks=[];n.dvt.deviceInfo={async isRunningPid(pid){n.checks.push(pid);return true;}};return n;}
function lease(driver,appState=0,bundlePid=0,pidRunning=false) {
 const n=native(appState,bundlePid);n.checks=[];n.dvt.deviceInfo={async isRunningPid(pid){n.checks.push(pid);return pidRunning;}};
 driver.remoteXPCFacade=n.driver.remoteXPCFacade;driver.mobileQueryAppState=n.driver.mobileQueryAppState;return n;
}
'''


class SnapshotShareProcessTests(unittest.TestCase):
    def node(self,body,*,bundle=None):
        boot=BOOT if bundle is None else BOOT.replace('org.example.overte',bundle)
        program=boot+'\n(async()=>{'+body+'\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result=subprocess.run(['node','-e',program,str(PLUGIN)],capture_output=True,text=True,timeout=8)
        self.assertEqual(0,result.returncode,result.stderr);return json.loads(result.stdout) if result.stdout.strip() else None

    def test_actual_live_PID_anchor_and_separate_closed_DVT_absence_do_not_echo_a_requested_PID(self):
        self.node(r'''
const n=live(),info=source.sourceInfo(n.driver,bundle,sdk);
const first=await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));
assert.equal(first.instance,info.instance);assert.equal(first.receiverBundleId,bundle+'.receiver');assert.equal(first.archiveBundleId,bundle);
assert.equal(first.anchor.pid,84);assert.deepEqual(n.checks,[84,84]);assert.equal(first.connectionClosed,true);assert.equal(n.socket.destroyed,true);
const current=lease(n.driver);const last=await source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(2));
assert.deepEqual(last.anchor,first.anchor);assert.deepEqual(last.bundlePids,[0,0]);assert.deepEqual(current.checks,[84,84]);
assert.deepEqual(last.pidChecks,[{pid:84,running:false},{pid:84,running:false}]);assert.equal(current.socket.destroyed,true);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);assert.equal(last.connectionClosed,true);
''')

    def test_missing_anchor_foreign_archive_reused_nonce_or_changed_scope_fail_before_native_access(self):
        self.node(r'''
const empty=live();await assert.rejects(source.observeRetiredSnapshotShareExtension(empty.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
await assert.rejects(source.observeSnapshotShareExtension(empty.driver,'org.foreign.archive',nonce(1)),/SOURCE_UNAVAILABLE/);
assert.equal(empty.counts().services,0);empty.socket.destroy();
for(const fault of ['session','bundle','device','nonce']) {
 const n=live();await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));const current=lease(n.driver);
 if(fault==='session')n.driver.sessionId='foreign-session';if(fault==='bundle')n.driver.opts.bundleId='org.foreign.archive';
 if(fault==='device')n.driver.opts.udid='foreign-synthetic-device';
 await assert.rejects(source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(fault==='nonce'?1:2)),/SOURCE_UNAVAILABLE/);
 assert.equal(current.counts().services,0);current.socket.destroy();
}
''')

    def test_continuation_cannot_reanchor_old_PID_to_new_live_extension_or_retime_old_anchor(self):
        self.node(r'''
const n=live(),first=await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));first.anchor.pid=77;
const still=lease(n.driver,4,84,true),next=await source.observeSnapshotShareExtension(n.driver,bundle,nonce(2));assert.equal(next.anchor.pid,84);
assert.equal(next.anchor.sequence,1);assert.deepEqual(still.checks,[84,84]);
const replaced=lease(n.driver,4,85,true);await assert.rejects(source.observeSnapshotShareExtension(n.driver,bundle,nonce(3)),/SOURCE_UNAVAILABLE/);
assert.deepEqual(replaced.checks,[84,84]);assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);
const after=lease(n.driver);await assert.rejects(source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(4)),/SOURCE_UNAVAILABLE/);
assert.equal(after.counts().services,0);after.socket.destroy();
''')

    def test_closed_connection_ACK_and_late_close_callbacks_cannot_produce_qualified_absence(self):
        self.node(r'''
const n=live();await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));const current=lease(n.driver);current.service.close=async()=>{};
await assert.rejects(source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(2)),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);assert.equal(current.socket.destroyed,false);
await assert.rejects(source.cleanup(async()=>{},n.driver),/CLEANUP_INCOMPLETE/);current.socket.destroy();
for(const expired of [false,true]) {
 const n=live();await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));const current=lease(n.driver);let release,done=false;
 const destroy=current.socket._destroy;current.socket._destroy=function(error,callback){release=()=>destroy.call(this,error,callback);};
 const pending=source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(2),expired?15:1000);pending.then(()=>done=true,()=>{});await tick();
 assert.equal(done,false);assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
 if(expired)await assert.rejects(pending,/SOURCE_UNAVAILABLE/);release();await tick();await tick();
 if(!expired)assert.equal((await pending).connectionClosed,true);
 assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,!expired);
}
''')

    def test_late_service_and_boolean_numeric_or_missing_DVT_producers_remain_unknown(self):
        self.node(r'''
for(const fault of ['boolean-pid','numeric-running','missing-api']) {
 const n=live();if(fault==='boolean-pid')n.dvt.processControl.getPidForBundleIdentifier=async()=>true;
 if(fault==='numeric-running')n.dvt.deviceInfo.isRunningPid=async()=>1;if(fault==='missing-api')delete n.dvt.deviceInfo;
 await assert.rejects(source.observeSnapshotShareExtension(n.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
 assert.equal(n.socket.destroyed,true);assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);
}
const n=live();let release;n.driver.remoteXPCFacade.requireService=()=>new Promise(resolve=>release=resolve);
await assert.rejects(source.observeSnapshotShareExtension(n.driver,bundle,nonce(1),15),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);release(n.dvt);await tick();await tick();
assert.equal(n.socket.destroyed,true);assert.deepEqual(n.checks,[]);assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);
''')

    def test_dispatch_never_accepts_foreign_extension_expected_PID_or_success_selectors(self):
        self.node(r'''
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),out={exports:{}};
vm.runInNewContext(fs.readFileSync(path.join(path.dirname(process.argv[1]),'index.cjs'),'utf8'),{module:out,exports:out.exports,require(name){
 if(name==='appium/plugin')return {BasePlugin:class{}};if(name==='./process_observer.cjs')return source;if(name==='./read_sdk.cjs')return ()=>sdk;throw Error('unexpected dependency');}});
const plugin=new out.exports.OverteProcessPlugin(),n=live(),next=async()=>{throw Error('No fallback');};
for(const value of [{bundleId:bundle,commandId:nonce(1),extensionBundleId:bundle+'.receiver'},
 {bundleId:bundle,commandId:nonce(1),pid:84},{bundleId:bundle,commandId:nonce(1),expectedAbsent:true}])
 await assert.rejects(plugin.execute(next,n.driver,'mobile: overteSnapshotShareExtensionInfo',[value]),/SOURCE_UNAVAILABLE/);
await assert.rejects(plugin.execute(next,n.driver,'mobile: overteProcessInfo',[{bundleId:bundle+'.receiver'}]),/SOURCE_UNAVAILABLE/);
assert.equal(n.counts().services,0);
const packet=await plugin.execute(next,n.driver,'mobile: overteSnapshotShareExtensionInfo',[{bundleId:bundle,commandId:nonce(1)}]);assert.equal(packet.anchor.pid,84);
''')

    def packets(self):
        return self.node(r'''
const n=live(),info=source.sourceInfo(n.driver,bundle,sdk),first=await source.observeSnapshotShareExtension(n.driver,bundle,nonce(1));
const packets=[first];
for(const [appState,bundlePid,pidRunning] of [[0,0,false],[0,0,true],[0,85,false],[4,0,false]]) {
 lease(n.driver,appState,bundlePid,pidRunning);packets.push(await source.observeRetiredSnapshotShareExtension(n.driver,bundle,nonce(packets.length+1)));
}
console.log(JSON.stringify({info,packets}));
''',bundle=BUNDLE)

    def test_host_original_reader_joins_real_Node_anchor_to_receiver_and_rejects_partial_absence(self):
        d=ShareAdmissionDomain(self);data=self.packets();artifact=share_artifact(d.ipa,d.scope['artifactSha256'])
        _n,_o,_e,receiver,_raw=received();receiver.update(receiverBundleId=BUNDLE+'.receiver',processId=84)
        first,last,*partial=data['packets'];source.original(first,first['commandId'],artifact,data['info'])
        source.original(last,last['commandId'],artifact,data['info'],first);self.assertEqual(84,source.absent(last,receiver,artifact,data['info'])['originalPid'])
        for packet in partial:
            source.original(packet,packet['commandId'],artifact,data['info'])
            with self.assertRaises(NativeUIError):source.absent(packet,receiver,artifact,data['info'])
        for fault in ('pid','archive','extension','anchor','connection','source'):
            packet=deepcopy(last);record=deepcopy(receiver)
            if fault=='pid':record['processId']=85
            elif fault=='archive':packet['archiveBundleId']='org.foreign.archive'
            elif fault=='extension':packet['receiverBundleId']='org.foreign.extension'
            elif fault=='anchor':packet['anchor']['pid']=85
            elif fault=='connection':packet['connectionClosed']=False
            else:packet['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.absent(packet,record,artifact,data['info'])

    def test_actual_admitted_archive_context_queries_extension_only_with_OS_background_guards(self):
        d=ShareAdmissionDomain(self);data=self.packets();d.source=data['info']['instance']
        with d.owner() as owner:
            owner.admit('d'*32);store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        actual=d.execute
        def execute(session,operation,query):
            if operation.startswith('mobile: overteSnapshotShareExtensionInfo'):
                d.sdk.append((session,operation,deepcopy(query)));self.assertEqual(dict(bundleId=BUNDLE,commandId=data['packets'][0]['commandId']),query)
                return deepcopy(data['packets'][0])
            value=actual(session,operation,query)
            if operation=='mobile: overteProcessInfo':value['foreground']=False
            return value
        d.execute=execute
        with lock.held():
            ctx=source.SnapshotShareArchiveContext(d,d.session,d.target,binding,d.ipa,store,lock,RUN,url,epoch_ms=d.epoch,monotonic=d.mono,sleep=lambda _:None)
            self.assertEqual(data['packets'][0],ctx.extension_query(data['packets'][0]['commandId']))
            with self.assertRaises(NativeUIError):ctx.foreground_runtime()
            d.source='0'*32;before=sum('ShareExtensionInfo' in operation for _session,operation,_query in d.sdk)
            with self.assertRaises(NativeUIError):ctx.extension_query('ios-'+'f'*32)
            self.assertEqual(before,sum('ShareExtensionInfo' in operation for _session,operation,_query in d.sdk))


if __name__=='__main__':unittest.main()
