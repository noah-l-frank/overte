"""Original Node observer over synthetic SDK calls and original Node sockets.

No Appium server, device, DVT service or workstation laboratory is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'process_plugin/process_observer.cjs'
BOOT=r'''
const assert=require('node:assert/strict'),{Socket}=require('node:net');
const source=require(process.argv[1]);
const sdk={appium:'3.7.0',xcuitest:'12.8.0',remoteXpc:'5.15.3'};
function native(appState=4,pid=42) {
 const socket=new Socket(); let queries=0,pids=0,closes=0,services=0;
 const service={socket,connection:{},isHandshakeComplete:true,async close(){closes++;this.connection=null;this.socket=null;this.isHandshakeComplete=false;socket.destroy();}};
 const dvt={dvtService:service,processControl:{async getPidForBundleIdentifier(bundle){assert.equal(bundle,'org.example.overte');pids++;return pid;}}};
 const driver={sessionId:'test-only-session',opts:{platformName:'iOS',bundleId:'org.example.overte',udid:'synthetic-device'},
  isRealDevice:()=>true,async mobileQueryAppState(bundle){assert.equal(bundle,'org.example.overte');queries++;return appState;},
  remoteXPCFacade:{eligible:true,async requireService(label,factory){assert.equal(label,'read configured iOS process');services++;
   return await factory({async startDVTService(udid){assert.equal(udid,'synthetic-device');return dvt;}});}}};
 return {driver,dvt,service,socket,counts:()=>({queries,pids,closes,services})};
}
const bundle='org.example.overte';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
'''


class ProcessPluginTests(unittest.TestCase):
    def run_node(self,body):
        program=BOOT+'\n(async()=>{'+body+'\n})().catch(error=>{console.error(error);process.exitCode=1;});'
        result=subprocess.run(['node','-e',program,str(SOURCE)],capture_output=True,text=True,timeout=8)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_foreground_background_and_absence_queries_never_use_cached_pid(self):
        self.run_node(r'''
for(const [appState,pid] of [[4,42],[3,42],[2,42],[1,0],[0,0]]) {
 const n=native(appState,pid);const value=await source.observe(n.driver,bundle);
 assert.deepEqual(value,pid?{bundleId:bundle,pid,foreground:appState===4}:null);
 assert.deepEqual(n.counts(),{queries:2,pids:2,closes:1,services:1});assert.equal(n.socket.destroyed,true);
 assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);
}
const n=native();const first=await source.observe(n.driver,bundle);
const fresh=native();n.driver.remoteXPCFacade=fresh.driver.remoteXPCFacade;
fresh.dvt.processControl.getPidForBundleIdentifier=async()=>43;
assert.equal((await source.observe(n.driver,bundle)).pid,43);assert.equal(first.pid,42);
''')

    def test_foreign_bundle_or_platform_session_changes_and_bad_pid_fail(self):
        self.run_node(r'''
const invalid=native();await assert.rejects(source.observe(invalid.driver,'org.example.foreign'),/SOURCE_UNAVAILABLE/);
assert.equal(invalid.counts().services,0);
for(const fault of ['pid','foreground','bundle','session','boolean','conflict','sdk-error']) {
 const n=native();let calls=0;
 n.dvt.processControl.getPidForBundleIdentifier=async()=>{
  calls++;if(fault==='bundle')n.driver.opts.bundleId='org.example.foreign';
  if(fault==='session')n.driver.sessionId='replaced';
  if(fault==='boolean')return true;if(fault==='conflict')return 0;
  if(fault==='sdk-error')throw Error('private-device-selector');
  return fault==='pid'&&calls>1?43:42;
 };
 if(fault==='foreground'){let reads=0;n.driver.mobileQueryAppState=async()=>++reads===1?4:3;}
 await assert.rejects(source.observe(n.driver,bundle),error=>error.message==='OVT_IOS_PROCESS_SOURCE_UNAVAILABLE');
 assert.equal(n.socket.destroyed,true);
}
''')

    def test_close_ack_without_original_socket_release_is_an_incomplete_cleanup(self):
        self.run_node(r'''
const n=native();n.service.close=async()=>{};
await assert.rejects(source.observe(n.driver,bundle),/SOURCE_UNAVAILABLE/);
assert.equal(n.socket.destroyed,false);const info=source.sourceInfo(n.driver,bundle,sdk);
assert.equal(info.available,false);assert.equal(info.cleanupPending,true);
let delegated=0;await assert.rejects(source.cleanup(async()=>{delegated++;return {};},n.driver),/CLEANUP_INCOMPLETE/);
assert.equal(delegated,1);n.socket.destroy();
''')

    def test_timeout_owns_and_closes_a_late_dvt_acquisition_without_returning_late_results(self):
        self.run_node(r'''
const n=native();let release;
n.driver.remoteXPCFacade.requireService=()=>new Promise(resolve=>release=resolve);
await assert.rejects(source.observe(n.driver,bundle,15),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
release(n.dvt);await tick();await tick();
assert.equal(n.socket.destroyed,true);assert.equal(n.counts().pids,0);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,false);
await source.cleanup(async()=>({deleted:true}),n.driver);
await assert.rejects(source.observe(n.driver,bundle),/SOURCE_UNAVAILABLE/);
''')

    def test_stalled_read_destroys_only_its_original_owned_socket_and_never_retries(self):
        self.run_node(r'''
const n=native(),other=native();let calls=0;
n.dvt.processControl.getPidForBundleIdentifier=()=>new Promise((_,reject)=>{
 calls++;n.socket.once('close',()=>reject(Error('closed original connection')));
});
await assert.rejects(source.observe(n.driver,bundle,15),/SOURCE_UNAVAILABLE/);await tick();await tick();
assert.equal(calls,1);assert.equal(n.socket.destroyed,true);assert.equal(other.socket.destroyed,false);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).available,false);other.socket.destroy();
''')

    def test_missing_native_handle_and_concurrent_reads_cannot_claim_clean_or_complete(self):
        self.run_node(r'''
const n=native();n.driver.remoteXPCFacade.requireService=async()=>({});
await assert.rejects(source.observe(n.driver,bundle),/SOURCE_UNAVAILABLE/);
assert.equal(source.sourceInfo(n.driver,bundle,sdk).cleanupPending,true);
await assert.rejects(source.cleanup(async()=>({deleted:true}),n.driver),/CLEANUP_INCOMPLETE/);n.socket.destroy();
const m=native();let release;m.driver.remoteXPCFacade.requireService=()=>new Promise(resolve=>release=resolve);
const pending=source.observe(m.driver,bundle,1000);await tick();
await assert.rejects(source.observe(m.driver,bundle),/SOURCE_UNAVAILABLE/);
release(m.dvt);assert.equal((await pending).pid,42);assert.equal(m.socket.destroyed,true);
''')

    def test_original_plugin_dispatch_is_closed_and_other_appium_commands_are_preserved(self):
        self.run_node(r'''
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const filename=path.join(path.dirname(process.argv[1]),'index.cjs');const output={exports:{}};
const context={module:output,exports:output.exports,require(name){
 if(name==='appium/plugin')return {BasePlugin:class{}};
 if(name==='./process_observer.cjs')return source;
 if(name==='./read_sdk.cjs')return ()=>sdk;
 return {version:name.startsWith('appium-ios')?'5.15.3':name.startsWith('appium-xcuitest')?'12.8.0':'3.7.0'};
}};
vm.runInNewContext(fs.readFileSync(filename,'utf8'),context,{filename});
const plugin=new output.exports.OverteProcessPlugin(),n=native();let delegated=0;
const next=async()=>{delegated++;return 99;};
assert.equal(await plugin.execute(next,n.driver,'mobile: queryAppState',[{bundleId:bundle}]),99);
for(const args of [[],[{bundleId:bundle,expectedPid:42}],[{bundleId:bundle},{bundleId:bundle}],['private']])
 await assert.rejects(plugin.execute(next,n.driver,'mobile: overteProcessInfo',args),/SOURCE_UNAVAILABLE/);
assert.equal(delegated,1);assert.equal(n.counts().pids,0);
const unsupported=native();unsupported.driver.isRealDevice=()=>{throw Error('private-device-selector');};
await assert.rejects(plugin.execute(next,unsupported.driver,'mobile: overteProcessSourceInfo',[{bundleId:bundle}]),
 error=>error.message==='OVT_IOS_PROCESS_SOURCE_UNAVAILABLE');unsupported.socket.destroy();
const info=await plugin.execute(next,n.driver,'mobile: overteProcessSourceInfo',[{bundleId:bundle}]);
assert.equal(info.processSourceVersion,1);assert.equal(info.sdk.remoteXpc,'5.15.3');
const observed=await plugin.execute(next,n.driver,'mobile: overteProcessInfo',[{bundleId:bundle}]);assert.equal(observed.pid,42);
assert.equal(await plugin.deleteSession(next,n.driver),99);assert.equal(delegated,2);
''')

    def test_sdk_mismatch_fails_before_any_driver_or_native_access(self):
        self.run_node(r'''
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const file=path.join(path.dirname(process.argv[1]),'index.cjs');
assert.throws(()=>vm.runInNewContext(fs.readFileSync(file,'utf8'),{module:{exports:{}},require(name){
 if(name==='appium/plugin')return {BasePlugin:class{}};
 if(name==='./process_observer.cjs')return source;
 if(name==='./read_sdk.cjs')return ()=>({appium:'unqualified'});
 return {version:'unqualified'};
}}),/SDK_UNAVAILABLE/);
''')

    def test_locked_esm_metadata_uses_loader_search_order_and_actual_driver_dependency(self):
        self.run_node(r'''
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{createRequire}=require('node:module');
const readSdk=require(path.join(path.dirname(process.argv[1]),'read_sdk.cjs'));
const root=fs.mkdtempSync(path.join(os.tmpdir(),'overte-sdk-source-'));
try {
 function pkg(base,name,version){const folder=path.join(base,'node_modules',name);fs.mkdirSync(folder,{recursive:true});
  fs.writeFileSync(path.join(folder,'package.json'),JSON.stringify({name,version,exports:{'.':{import:'./index.js'}}}));
  fs.writeFileSync(path.join(folder,'index.js'),'module.exports={}');return folder;}
 pkg(root,'appium','3.7.0');const driver=pkg(root,'appium-xcuitest-driver','12.8.0');
 const remote=pkg(driver,'appium-ios-remotexpc','5.15.3');pkg(root,'appium-ios-remotexpc','foreign');
 const resolver=createRequire(path.join(root,'entry.cjs'));
 assert.throws(()=>resolver.resolve('appium-xcuitest-driver'),/exports/);
 assert.throws(()=>resolver('appium-ios-remotexpc/package.json'),/not defined by "exports"/);
 assert.deepEqual(readSdk(resolver),sdk);
 fs.writeFileSync(path.join(remote,'package.json'),JSON.stringify({name:'wrong',version:'5.15.3'}));
 assert.throws(()=>readSdk(resolver),/SDK_UNAVAILABLE/);
}finally{fs.rmSync(root,{recursive:true,force:true});}
''')


if __name__=='__main__':unittest.main()
