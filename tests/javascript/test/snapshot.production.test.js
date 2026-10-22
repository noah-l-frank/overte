// SPDX-License-Identifier: Apache-2.0
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { FakeSignal, createScriptApi, runProductionScript } = require("../support");
const source = path.resolve(__dirname,"../../../scripts/system/snapshot.js");
function start(native=true,observe=false) {
    const Script=createScriptApi(), settings=new Map(), calls=[], messages=[], requests=[], cancelled=[];
    const work=[];
    const Test=observe?{featureIOSSnapshotEvent(value){work.push(structuredClone(value));}}:undefined;
    if(observe){Script.update=new FakeSignal();}
    let ui;
    function AppUi(options) { ui=this; this.options=options;this.isOpen=true;this.sendMessage=value=>messages.push(value);this.openNewAppOnTop=()=>{}; }
    Script.include=()=>{};Script.resourcesPath=()=>"/packaged/";Script.getExternalPath=(_,p)=>p;Script.ExternalPaths={HF_Content:1};
    Script.require=name=>name==="./snapshot/featureSnapshotWork.js"
        ?runProductionScript(path.resolve(__dirname,"../../../scripts/system/snapshot/featureSnapshotWork.js"),{Script,Test,module:{exports:{}}}).context.module.exports
        :name==="appUi"?AppUi:name==="contextMenu"?{enable(){},disable(){}}:{request(options,callback){requests.push({options,callback});}};
    const Window={snapshotShared:new FakeSignal(),stillSnapshotTaken:new FakeSignal(),processingGifStarted:new FakeSignal(),processingGifCompleted:new FakeSignal(),browseDirChanged:new FakeSignal(),
        takeSnapshot(...args){calls.push(["still",...args]);},takeSecondaryCamera360Snapshot(...args){calls.push(["360",...args]);},shareSnapshot(...args){calls.push(["upload",...args]);}};
    const Snapshot={nativeReviewEnabled:()=>native,getSnapshotFormat:()=>"png",getSnapshotsLocation:()=>"/app/Snapshots",captureStatusChanged:new FakeSignal(),uploadStatusChanged:new FakeSignal(),snapshotLocationSet:new FakeSignal(),
        cancelCapture(id){cancelled.push(["capture",id]);},cancelUpload(file){cancelled.push(["upload",file]);}};
    const Reticle={visible:true,allowMouseCapture:true},Menu={overlays:true,isOptionChecked(){return this.overlays;},setIsOptionChecked(_,value){this.overlays=value;}};
    const Account={metaverseServerURL:"https://metaverse.invalid",isLoggedIn:()=>true};
    const HMD={active:false,displayModeChanged:new FakeSignal(),closeTablet(){calls.push(["close"]);},openTablet(){calls.push(["open"]);}};
    const GlobalServices={myUsernameChanged:new FakeSignal()};
    runProductionScript(source,{Script,Test,Snapshot,Window,Account,GlobalServices,Reticle,Menu,HMD,print(){},openLoginWindow(){},
        Settings:{getValue(key,fallback=""){return settings.has(key)?settings.get(key):fallback;},setValue(key,value){settings.set(key,value);}},
        Controller:{getDeviceNames:()=>[],newMapping:()=>({enable(){},disable(){},from(){return{to(){}};}})},
        Entities:{canRez:()=>false,canRezTmp:()=>false,canRezChanged:new FakeSignal(),canRezTmpChanged:new FakeSignal()},
        Tablet:{getTablet:()=>({fromQml:new FakeSignal(),returnToPreviousApp(){}})},
        SoundCache:{getSound:()=>({})},Audio:{playSound(){}},MyAvatar:{position:{x:1,y:2,z:3}},Rates:{render:60},
        location:{href:"hifi://place/path",domainID:"{domain}"},UserActivityLogger:{logAction(){}},Desktop:{show(){}},DialogsManager:{}});
    // AppUi invokes that.onOpened() after wiring the actual QML bridge.
    ui.options.onOpened.call(ui);
    function message(action,extra={}) { ui.options.onMessage({type:"snapshot",action,...extra}); }
    function delayedCapture() { for(const delay of [350,500]){const entry=[...Script.timers].find(([,timer])=>timer.delay===delay);assert.ok(entry);Script.runTimer(entry[0]);} }
    return{Script,Snapshot,Window,Account,GlobalServices,Reticle,Menu,HMD,ui,settings,calls,messages,requests,cancelled,work,message,delayedCapture};
}
test("native SNAP loads actual QML while desktop retains full HTML review",()=>{
    const mobile=start();assert.match(mobile.ui.options.home,/NativeSnapshotReview.qml$/);
    assert.equal(mobile.Snapshot.captureStatusChanged.listenerCount,1);
    assert.match(start(false).ui.options.home,/SnapshotReview.html$/);
});
test("all four modes retain real capture API arguments and filenames",()=>{
    for(const mode of ["still","animated","panorama","cubemap"]){
        const h=start();h.message("takeSnapshot",{mode,filename:"../Photo"});h.delayedCapture();
        const capture=h.calls.find(row=>row[0]===(mode==="panorama"||mode==="cubemap"?"360":"still"));
        assert.ok(capture);assert.equal(capture.length,6);assert.match(capture[5],/^snap_/);
        assert.match(capture[4],/^___Photo-snap_.*\.png$/);assert.ok(!capture[4].includes("/"));
        assert.equal(capture[2],mode==="animated"||mode==="cubemap");
        h.Script.end();assert.equal(h.Script.timers.size,0);
    }
});
test("ordinary GIF selection persists before capture and is restored through ready",()=>{
    const h=start();
    for(const [action,expected] of [["captureStillAndGif",true],["captureStillOnly",false]]){
        h.message(action);
        assert.equal(h.settings.get("alsoTakeAnimatedSnapshot"),expected);
        assert.equal(h.calls.filter(row=>row[0]==="still"||row[0]==="360").length,0);
        h.message("ready");
        const observed=h.messages.filter(row=>row.action==="captureSettings").at(-1);
        assert.equal(observed.setting,expected);
    }
});
test("native open initializes preferences after bridge wiring without a ready request",()=>{
    const h=start();
    assert.equal(h.messages.filter(row=>row.action==="captureSettings").at(-1)?.setting,true);
    h.settings.set("alsoTakeAnimatedSnapshot",false);
    h.ui.options.onOpened.call(h.ui);
    assert.equal(h.messages.filter(row=>row.action==="captureSettings").at(-1)?.setting,false);
    assert.equal(start(false).messages.filter(row=>row.action==="captureSettings").length,0);
});
test("cancel before renderer submission clears delays and restores overlays",()=>{
    const h=start();h.message("takeSnapshot",{mode:"still"});assert.equal(h.Reticle.visible,false);assert.equal(h.Menu.overlays,false);
    h.message("cancelSnapshotCapture");assert.equal(h.Script.timers.size,0);assert.equal(h.Reticle.visible,true);assert.equal(h.Menu.overlays,true);
    assert.equal(h.calls.filter(row=>row[0]==="still").length,0);assert.match(h.cancelled[0][1],/^snap_/);
});
test("replacement drops old capture callback; late domain response cannot revive closed review",()=>{
    const h=start();h.message("takeSnapshot",{mode:"still"});h.delayedCapture();const old=h.calls.find(row=>row[0]==="still")[5];
    h.message("cancelSnapshotCapture");h.message("takeSnapshot",{mode:"still"});h.delayedCapture();
    const before=h.messages.length;h.Snapshot.captureStatusChanged.emit(old,"complete","/app/Snapshots/old.png","");assert.equal(h.messages.length,before);
    const current=h.calls.filter(row=>row[0]==="still").at(-1)[5];h.Snapshot.captureStatusChanged.emit(current,"complete","/app/Snapshots/new.png","");
    assert.equal(h.Script.timers.size,0);const lookup=h.requests.at(-1);assert.ok(lookup);
    h.ui.isOpen=false;h.ui.options.onClosed();const closed=h.messages.length;
    lookup.callback(null,{status:"success",total_entries:1});assert.equal(h.messages.length,closed);
});
test("GIF review preserves still frame, processing and animation completion",()=>{
    const h=start();h.message("takeSnapshot",{mode:"animated"});h.delayedCapture();const id=h.calls.find(row=>row[0]==="still")[5];
    h.Snapshot.captureStatusChanged.emit(id,"processing","/app/Snapshots/still.png","");
    h.requests.at(-1).callback(null,{status:"success",total_entries:1});
    assert.equal(h.messages.filter(row=>row.action==="addImages").at(-1).image_data[0].localPath,"/app/Snapshots/still.png");
    h.Snapshot.captureStatusChanged.emit(id,"complete","/app/Snapshots/still.gif","");h.requests.at(-1).callback(null,{status:"success",total_entries:1});
    const completed=h.messages.filter(row=>row.action==="addImages").at(-1);
    assert.equal(completed.options.processingGif,false);assert.equal(completed.options.canBlast,true);assert.equal(completed.image_data[0].localPath,"/app/Snapshots/still.gif");
});
test("upload errors and native cancellation reach review; close cancels current native upload",()=>{
    const h=start();h.settings.set("previousSnapshotDomainID","{domain}");h.message("shareSnapshotForUrl",{data:"/app/Snapshots/photo.png"});
    h.requests.at(-1).callback(null,{status:"success",total_entries:1});assert.equal(h.calls.at(-1)[0],"upload");
    h.Snapshot.uploadStatusChanged.emit("/app/Snapshots/photo.png","error","file-unavailable");
    assert.equal(h.messages.at(-1).error,"file-unavailable");
    h.message("shareSnapshotForUrl",{data:"/app/Snapshots/next.png"});h.requests.at(-1).callback(null,{status:"success",total_entries:1});
    h.ui.options.onClosed();assert.deepEqual(h.cancelled.at(-1),["upload","/app/Snapshots/next.png"]);
});
test("closing between connection-story lookup and POST prevents later mutation",()=>{
    const h=start();h.message("blastToConnections",{story_id:7,isGif:false});const lookup=h.requests.at(-1);
    h.ui.options.onClosed();const count=h.requests.length;
    lookup.callback(null,{status:"success",user_story:{path:"/",place_name:"place",thumbnail_url:"https://x/thumbnail.png",details:{image_url:"https://x/image.png"}}});
    assert.equal(h.requests.length,count);
});
test("desktop still capture and shutdown keep original signal route",()=>{
    const h=start(false);h.message("takeSnapshot");h.delayedCapture();assert.equal(h.calls.find(row=>row[0]==="still").length,4);
    assert.equal(h.Window.processingGifStarted.listenerCount,1);h.Script.end();assert.equal(h.Window.snapshotShared.listenerCount,0);
});

test("idle Cancel cannot fabricate an actual pending-capture cancellation proof",()=>{
    const h=start();
    h.message("cancelSnapshotCapture");
    assert.equal(h.cancelled.length,0);
    assert.equal(h.messages.filter(row=>row.action==="captureStatus"&&row.phase==="cancelled").length,0);
    h.message("takeSnapshot",{mode:"animated"});
    assert.equal(h.messages.filter(row=>row.action==="clearPreviousImages").length,1);
    assert.equal(h.calls.filter(row=>row[0]==="still"||row[0]==="360").length,0);
    h.message("cancelSnapshotCapture");
    assert.equal(h.cancelled.length,1);assert.match(h.cancelled[0][1],/^snap_/);
    assert.equal(h.messages.at(-1).phase,"cancelled");assert.equal(h.Script.timers.size,0);
    h.message("cancelSnapshotCapture");
    assert.equal(h.cancelled.length,1);
    assert.equal(h.messages.filter(row=>row.action==="captureStatus"&&row.phase==="cancelled").length,1);
});

test("test observer retains real delayed capture state and cancellation closure order",()=>{
    const h=start(true,true);
    assert.equal(h.work[0].event,"snapshot");assert.equal(h.work[0].state.captureId,"");
    assert.equal(h.Script.timers.size,0);assert.equal(h.Script.update.listenerCount,1);
    h.message("takeSnapshot",{mode:"animated"});h.Script.update.emit();
    const pending=h.work.at(-1).state;
    assert.match(pending.captureId,/^snap_/);assert.equal(pending.mode,"animated");
    assert.equal(pending.overlaysHidden,true);assert.equal(pending.timerHandles.length,2);
    assert.deepEqual(pending.timerHandles.map(id=>h.Script.timers.get(id).delay).sort((a,b)=>a-b),[350,60000]);
    assert.equal(h.calls.filter(row=>row[0]==="still").length,0);
    h.message("cancelSnapshotCapture");h.Script.update.emit();
    const cancel=h.work.filter(row=>row.closure==="cancelNativeCapture");
    assert.deepEqual(cancel.slice(-3).map(row=>row.event),["entry","returned","finally"]);
    assert.equal(cancel.at(-3).state.captureId,pending.captureId);
    assert.equal(cancel.at(-1).state.captureId,"");assert.equal(cancel.at(-1).state.timerHandles.length,0);
    assert.equal(cancel.at(-1).state.overlaysHidden,false);assert.equal(h.Script.timers.size,0);
    assert.equal(h.calls.filter(row=>row[0]==="still").length,0);
    h.Script.end();assert.equal(h.work.at(-1).event,"ending");
    assert.equal(h.Script.update.listenerCount,0);assert.equal(h.work.at(-1).state.captureId,"");
});

test("observer preserves actual thrown cancellation and never fabricates returned or restored overlays",()=>{
    const h=start(true,true);h.message("takeSnapshot",{mode:"still"});
    const thrown={nativeFailure:true};h.Snapshot.cancelCapture=()=>{throw thrown;};
    assert.throws(()=>h.message("cancelSnapshotCapture"),value=>value===thrown);
    const cancel=h.work.filter(row=>row.closure==="cancelNativeCapture").slice(-2);
    assert.deepEqual(cancel.map(row=>row.event),["entry","finally"]);
    assert.equal(cancel.at(-1).state.overlaysHidden,true);
    assert.equal(h.calls.filter(row=>row[0]==="still").length,0);
});
