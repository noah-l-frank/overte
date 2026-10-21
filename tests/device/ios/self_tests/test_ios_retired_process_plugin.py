"""Original retired-PID producer over synthetic SDK and unconnected sockets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

from ios.self_tests import test_ios_process_plugin as fixture

SOURCE=Path(__file__).resolve().parents[1]/'process_plugin/process_observer.cjs'
BOOT=fixture.BOOT+r'''
function lease(driver,appState=1,bundlePid=0,pidRunning=false) {
 const next=native(appState,bundlePid);next.checks=[];
 next.dvt.deviceInfo={async isRunningPid(pid){next.checks.push(pid);return pidRunning;}};
 driver.remoteXPCFacade=next.driver.remoteXPCFacade;driver.mobileQueryAppState=next.driver.mobileQueryAppState;
 return next;
}
const nonce=n=>'ios-'+n.toString(16).padStart(32,'0');
'''


class RetiredProcessPluginTests(unittest.TestCase):
    def run_node(self,body):
        program=BOOT+'\n(async()=>{'+body+'\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result=subprocess.run(['node','-e',program,str(SOURCE)],capture_output=True,text=True,timeout=8)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_original_anchor_and_fresh_numeric_pid_queries_survive_actual_bundle_absence(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);const first=native(0,0);
n.driver.remoteXPCFacade=first.driver.remoteXPCFacade;n.driver.mobileQueryAppState=first.driver.mobileQueryAppState;
assert.equal(await source.observe(n.driver,bundle),null); // Never erase the actual old anchor.
const current=lease(n.driver);const before=source.sourceInfo(n.driver,bundle,sdk);
const packet=await source.observeRetired(n.driver,bundle,nonce(1));
assert.equal(packet.iosRetiredProcessVersion,1);assert.equal(packet.instance,before.instance);
assert.equal(packet.source,'dvt-owned-pid-and-bundle-state');assert.equal(packet.clockDomain,'appium-node-host');
assert.deepEqual(packet.anchor.bundlePids,[42,42]);assert.deepEqual(packet.anchor.appStates,[4,4]);
assert.deepEqual(packet.bundlePids,[0,0]);assert.deepEqual(packet.appStates,[1,1]);assert.deepEqual(current.checks,[42,42]);
assert.deepEqual(packet.pidChecks,[{pid:42,running:false},{pid:42,running:false}]);
assert(packet.sequence>packet.anchor.sequence);assert(packet.clockBefore.epochMs>=packet.anchor.clockAfter.epochMs);
assert.equal(current.socket.destroyed,true);assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);
const saved=JSON.parse(JSON.stringify(packet.anchor));packet.anchor.pid=77;
const another=lease(n.driver);const next=await source.observeRetired(n.driver,bundle,nonce(2));
assert.deepEqual(next.anchor,saved);assert(next.sequence>packet.sequence);assert.deepEqual(another.checks,[42,42]);
''')

    def test_latest_actual_pid_replaces_old_anchor_without_echoing_an_expected_pid(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);const replacement=lease(n.driver,4,43,true);
assert.equal((await source.observe(n.driver,bundle)).pid,43);
const current=lease(n.driver);const packet=await source.observeRetired(n.driver,bundle,nonce(1));
assert.equal(packet.anchor.pid,43);assert.deepEqual(current.checks,[43,43]);
assert.deepEqual(packet.pidChecks,[{pid:43,running:false},{pid:43,running:false}]);
''')

    def test_bundle_absence_cannot_replace_actual_numeric_pid_presence(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver,0,0,true);
const packet=await source.observeRetired(n.driver,bundle,nonce(1));
assert.deepEqual(packet.bundlePids,[0,0]);assert.deepEqual(packet.pidChecks,[{pid:42,running:true},{pid:42,running:true}]);
assert.equal(current.socket.destroyed,true); // This original is presence, never absence success.
''')

    def test_missing_anchor_reused_nonce_and_replaced_driver_scope_fail_before_native_access(self):
        self.run_node(r'''
const empty=native();await assert.rejects(source.observeRetired(empty.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
assert.equal(empty.counts().services,0);empty.socket.destroy();
for(const fault of ['session','bundle','device']) {
 const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver);
 if(fault==='session')n.driver.sessionId='foreign-session';
 if(fault==='bundle')n.driver.opts.bundleId='org.example.foreign';
 if(fault==='device')n.driver.opts.udid='foreign-synthetic-device';
 await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
 assert.equal(current.counts().services,0);current.socket.destroy();
}
const n=native();await source.observe(n.driver,bundle);lease(n.driver);await source.observeRetired(n.driver,bundle,nonce(1));
const current=lease(n.driver);await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
assert.equal(current.counts().services,0);current.socket.destroy();
''')

    def test_invalid_boolean_pid_results_and_missing_actual_sdk_api_never_produce_empty_success(self):
        self.run_node(r'''
for(const fault of ['missing','boolean-pid','numeric-running','sdk-error']) {
 const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver);
 if(fault==='missing')delete current.dvt.deviceInfo;
 if(fault==='boolean-pid')current.dvt.processControl.getPidForBundleIdentifier=async()=>false;
 if(fault==='numeric-running')current.dvt.deviceInfo.isRunningPid=async()=>0;
 if(fault==='sdk-error')current.dvt.deviceInfo.isRunningPid=async()=>{throw Error('private-device-selector');};
 await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1)),e=>e.message==='OVT_IOS_PROCESS_SOURCE_UNAVAILABLE');
 assert.equal(current.socket.destroyed,true);
}
''')

    def test_close_ack_does_not_replace_original_socket_drain_or_clear_source_ownership(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver);current.service.close=async()=>{};
await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1)),/SOURCE_UNAVAILABLE/);
assert.equal(current.socket.destroyed,false);assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
let delegated=0;await assert.rejects(source.cleanup(async()=>{delegated++;},n.driver),/CLEANUP_INCOMPLETE/);
assert.equal(delegated,1);current.socket.destroy();
''')

    def test_original_socket_close_callback_must_drain_before_success_or_retirement(self):
        self.run_node(r'''
for(const expired of [false,true]) {
 const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver);let release,done=false;
 const destroy=current.socket._destroy;
 current.socket._destroy=function(error,callback){release=()=>destroy.call(this,error,callback);};
 const pending=source.observeRetired(n.driver,bundle,nonce(1),expired?15:1000);
 pending.then(()=>done=true,()=>{});await tick();
 assert.equal(current.socket.destroyed,true);assert.equal(done,false);
 assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
 await assert.rejects(source.cleanup(async()=>{},n.driver),/CLEANUP_INCOMPLETE/);
 if(expired)await assert.rejects(pending,/SOURCE_UNAVAILABLE/);
 release();await tick();await tick();
 if(!expired){const packet=await pending;assert.equal(packet.pidChecks[0].running,false);}
 assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);
 assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,!expired);
}
''')

    def test_late_owned_service_is_closed_without_returning_a_late_retired_packet(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);const current=lease(n.driver);let release;
n.driver.remoteXPCFacade.requireService=()=>new Promise(resolve=>release=resolve);
await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1),15),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
release(current.dvt);await tick();await tick();assert.equal(current.socket.destroyed,true);assert.deepEqual(current.checks,[]);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);
''')

    def test_pending_original_os_query_stays_owned_after_timeout_without_a_dvt_handle(self):
        self.run_node(r'''
const n=native();await source.observe(n.driver,bundle);let release;
n.driver.mobileQueryAppState=()=>new Promise(resolve=>release=resolve);
await assert.rejects(source.observeRetired(n.driver,bundle,nonce(1),15),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
await assert.rejects(source.cleanup(async()=>{},n.driver),/CLEANUP_INCOMPLETE/);
release(0);await tick();await tick();assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);
''')

    def test_dispatch_refuses_pid_selectors_and_preserves_the_closed_legacy_commands(self):
        self.run_node(r'''
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const file=path.join(path.dirname(process.argv[1]),'index.cjs'),output={exports:{}};
vm.runInNewContext(fs.readFileSync(file,'utf8'),{module:output,exports:output.exports,require(name){
 if(name==='appium/plugin')return {BasePlugin:class{}};
 if(name==='./process_observer.cjs')return source;if(name==='./read_sdk.cjs')return ()=>sdk;
 throw Error('unexpected dependency');
}});
const plugin=new output.exports.OverteProcessPlugin(),n=native(),next=async()=>{throw Error('No fallback');};
await source.observe(n.driver,bundle);const current=lease(n.driver);
for(const value of [{bundleId:bundle,commandId:nonce(1),pid:42},{bundleId:bundle,expectedPid:42},
 {bundleId:bundle,commandId:nonce(1),expectedAbsent:true}])
 await assert.rejects(plugin.execute(next,n.driver,'mobile: overteRetiredProcessInfo',[value]),/SOURCE_UNAVAILABLE/);
assert.equal(current.counts().services,0);
const packet=await plugin.execute(next,n.driver,'mobile: overteRetiredProcessInfo',[{commandId:nonce(1),bundleId:bundle}]);
assert.deepEqual(packet.pidChecks,[{pid:42,running:false},{pid:42,running:false}]);
''')


if __name__=='__main__':unittest.main()
