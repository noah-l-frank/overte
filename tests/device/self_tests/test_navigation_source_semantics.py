"""Original Places JavaScript/QML functions; Qt and network boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const qml=fs.readFileSync(process.argv[1],'utf8'),script=fs.readFileSync(process.argv[2],'utf8');
function section(source,start,end){let a=source.indexOf(start),b=source.indexOf(end,a+start.length);
assert(a>=0&&b>a,'Original source boundary changed');return source.slice(a,b);}
let rows=[];const ctx={records:[{id:'owned',name:'e2e-owned',address:'http://controlled.invalid/scene.json?location=/2,0,4',maturity:'everyone'}],
 search:{text:''},maturityFilter:['everyone'],qsTr:s=>s,placesModel:{clear:()=>rows=[],append:r=>rows.push(r)}};
vm.createContext(ctx);vm.runInContext(section(qml,'    function rebuildPlaces(', '    function toggleMaturity('),ctx);
'''


class NavigationSourceSemantics(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,str(ROOT/'scripts/system/places/PicoPlaces.qml'),
            str(ROOT/'scripts/system/places/places.js')],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_empty_and_owned_queries_and_maturity_filter_have_actual_results(self):
        self.run_case(r'''
ctx.rebuildPlaces();assert.equal(rows.length,1);assert.equal(rows[0].placeId,'owned');
ctx.search.text='hidden-owned';ctx.rebuildPlaces();assert.equal(rows.length,0);
ctx.search.text=' E2E-OWNED ';ctx.rebuildPlaces();assert.equal(rows.length,1);
ctx.maturityFilter=[];ctx.rebuildPlaces();assert.equal(rows.length,0);
''')

    def test_original_rebuild_clears_old_model_and_does_not_modify_input_query(self):
        self.run_case(r'''
ctx.search.text='e2e-owned';ctx.rebuildPlaces();ctx.records=[];ctx.rebuildPlaces();assert.equal(rows.length,0);
assert.equal(ctx.search.text,'e2e-owned');ctx.search={text:''};ctx.records=[{id:'new',address:'owned-new'}];
ctx.rebuildPlaces();assert.equal(rows[0].placeId,'new');assert.equal(ctx.search.text,'');
''')

    def test_original_directory_processor_requires_actual_matching_protocol_and_retains_record_identity(self):
        self.run_case(r'''
const row={id:'owned',name:'e2e-owned',description:'',thumbnail:'',maturity:'everyone',address:'http://controlled.invalid/scene.json?location=/2,0,4',
 visibility:'open',tags:[],managers:[],domain:{id:'domain',name:'controlled',protocol_version:'actual-signature',num_users:0,capacity:8}};
const p={Window:{protocolSignature:()=> 'actual-signature'},placesData:{data:{places:[row]}},portalList:[],placesOfTheCurrentDomain:[],
 nbrPlaceProtocolKnown:0,nbrPlacesNoProtocolMatch:0,location:{domainID:'other'},getSeededRandomForString:()=>.5,
 getListFromArray:a=>a.join(','),zeroPad:n=>String(n),aplphabetize:n=>n};
vm.createContext(p);vm.runInContext(section(script,'    function processData(', '    function getPositionFromPath('),p);
p.processData({order:0,url:'http://controlled.invalid',region:'owned'});assert.equal(p.portalList.length,1);
assert.equal(p.portalList[0].id,'owned');assert.equal(p.portalList[0].address,row.address);
p.portalList=[];row.domain.protocol_version='foreign';p.processData({});assert.equal(p.portalList.length,0);
row.domain={};p.processData({});assert.equal(p.portalList.length,0);
''')

    def test_original_bookmark_handlers_use_actual_location_preserve_unowned_and_guard_rapid_commands(self):
        self.run_case(r'''
let clock=1000;const native={Private:'hifi://unowned.invalid'},published=[];
const source={Date:class{getTime(){return clock;}},channel:'com.overte.places',timestamp:0,INTERCALL_DELAY:200,
 location:{href:'http://controlled.invalid/scene.json?location=/2,0,4'},
 LocationBookmarks:{getBookmarks:()=>({...native}),addBookmark:(name,url)=>native[name]=url,removeBookmark:name=>delete native[name]},
 sendToPlacesUi:value=>published.push(JSON.parse(JSON.stringify(value)))};
vm.createContext(source);
vm.runInContext(section(script,'    function onAppWebEventReceived(', '    function savePinnedMetaverseSetting(')
 +section(script,'    function getLocationBookmarks(', '    function processData('),source);
function send(action,fields={}){source.onAppWebEventReceived({channel:source.channel,action,...fields});}
send('ADD_BOOKMARK',{name:'owned',url:'http://requested.invalid'});
assert.equal(native.owned,source.location.href);assert.equal(native.Private,'hifi://unowned.invalid');
send('RENAME_BOOKMARK',{originalName:'owned',name:'renamed',url:native.owned});assert.equal(native.renamed,undefined);
clock+=230;send('RENAME_BOOKMARK',{originalName:'owned',name:'renamed',url:native.owned});
assert.equal(native.owned,undefined);assert.equal(native.renamed,source.location.href);
clock+=230;send('DELETE_BOOKMARK',{name:'renamed'});assert.deepEqual(native,{Private:'hifi://unowned.invalid'});
assert.equal(published.length,3);assert.equal(published.at(-1).action,'BOOKMARKS_DATA');
assert.deepEqual(published.at(-1).data,native);
''')

    def test_original_bookmark_dialog_cancel_dispatches_nothing_and_rename_keeps_original_address(self):
        self.run_case(r'''
const calls=[];let closed=0;
const source={bookmarkName:{text:' renamed '},bookmarkDialog:{originalName:'owned',address:'http://original.invalid/scene.json',close:()=>closed++},
 root:{dispatch:(action,fields)=>calls.push({action,...fields})}};
vm.createContext(source);
const accepted=section(qml,'            onAccepted: {','            onRejected:').slice('            onAccepted: '.length).trim();
vm.runInContext('function accept() '+accepted,source);
const rejected=qml.split('\n').find(line=>line.trim().startsWith('onRejected:')).split('onRejected:')[1];
vm.runInContext(rejected,source);assert.equal(closed,1);assert.equal(calls.length,0);
source.accept();assert.equal(closed,2);assert.deepEqual(calls,[{action:'RENAME_BOOKMARK',originalName:'owned',name:'renamed',url:source.bookmarkDialog.address}]);
''')

    def test_original_ready_refresh_discards_cached_portals_and_starts_current_generation_fetch(self):
        self.run_case(r'''
const calls=[];const source={requestGeneration:3,metaverseServers:['old'],portalList:['old'],
 nbrPlacesNoProtocolMatch:10,nbrPlaceProtocolKnown:20,abortActiveRequest:()=>calls.push('abort'),
 buildMetaverseServerList:()=>calls.push('servers'),fetchMetaverse:(index,generation)=>calls.push([index,generation])};
vm.createContext(source);vm.runInContext(section(script,'    function transmitPortalList(', '    function finishPortalList('),source);
source.transmitPortalList();assert.deepEqual(calls,['abort','servers',[0,4]]);assert.equal(source.portalList.length,0);
assert.equal(source.metaverseServers.length,0);assert.equal(source.nbrPlaceProtocolKnown,0);
''')

    def test_original_modal_button_path_selects_before_destroy_and_dispatches_once_per_platform(self):
        program=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const modal=fs.readFileSync(process.argv[1],'utf8'),button=fs.readFileSync(process.argv[2],'utf8');
const start=modal.indexOf('    function click(button) {'),end=modal.indexOf('    function exec()',start);
assert(start>=0&&end>start);
const calls=[],ctx={clickedButton:0,selected:value=>calls.push(['selected',value,ctx.clickedButton]),destroy:()=>calls.push(['destroy'])};
vm.createContext(ctx);vm.runInContext(modal.slice(start,end),ctx);
const android=button.split('androidClickAction: ')[1].split('\n')[0];
const ordinary=button.split('onClicked: ')[1].split('\n')[0];
assert(android&&ordinary);
const b={dialog:ctx,button:1024,usesAndroidClickAction:true};vm.createContext(b);
vm.runInContext('const android='+android+';function clicked() '+ordinary+';android();clicked();',b);
assert.deepEqual(calls,[['selected',1024,1024],['destroy']]);
calls.length=0;b.usesAndroidClickAction=false;vm.runInContext('clicked()',b);
assert.deepEqual(calls,[['selected',1024,1024],['destroy']]);
'''
        result=subprocess.run(['node','-e',program,str(ROOT/'interface/resources/qml/dialogs/TabletMessageBox.qml'),
            str(ROOT/'interface/resources/qml/dialogs/messageDialog/MessageDialogButton.qml')],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_directory_enter_commits_path_updates_auth_and_does_not_submit_credentials(self):
        program=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const text=fs.readFileSync(process.argv[1],'utf8');const field=text.indexOf('id: metaverseServerField');
const start=text.indexOf('Keys.onPressed: {',field)+'Keys.onPressed: '.length;
assert(field>=0&&start>field);let end=start,depth=0;do{if(text[end]==='{')depth++;if(text[end]==='}')depth--;end++;}while(depth&&end<text.length);
const calls=[],ctx={event:{key:4,accepted:false},Qt:{Key_Tab:1,Key_Backtab:2,Key_Enter:3,Key_Return:4},
 isLoggingInToDomain:false,metaverseServerField:{text:'https://original.invalid/server'},passwordField:{text:'unowned'},
 displayNameField:{focus:false},Settings:{setValue:(key,value)=>calls.push([key,value])},
 AccountServices:{isLoggedIn:()=>false,logOut:()=>calls.push('logout'),updateAuthURLFromMetaverseServerURL:()=>calls.push('auth')},
 console:{log:()=>{}}};vm.createContext(ctx);vm.runInContext('function press() '+text.slice(start,end),ctx);
ctx.press();assert.deepEqual(calls,[['private/selectedMetaverseURL','https://original.invalid/server'],'auth']);
assert.equal(ctx.passwordField.text,'');assert.equal(ctx.event.accepted,true);
calls.length=0;ctx.event.key=1;ctx.press();assert.equal(calls.length,0);assert.equal(ctx.displayNameField.focus,true);
ctx.event.key=4;ctx.isLoggingInToDomain=true;ctx.press();assert.equal(calls.length,0);
'''
        result=subprocess.run(['node','-e',program,str(ROOT/'interface/resources/qml/LoginDialog/LinkAccountBody.qml')],
            capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_fetch_reads_response_only_for_its_live_current_generation_before_publication(self):
        self.run_case(r'''
let reads=0,finished=0;const requests=[];
const source={shuttingDown:false,appStatus:true,requestGeneration:1,httpRequest:null,
 metaverseServers:[{fetch:true,url:'https://controlled.invalid'}],REQUEST_TIMEOUT:10000,
 processData:()=>{assert.equal(source.placesData.data.places[0].id,'owned');},finishPortalList:()=>finished++,
 XMLHttpRequest:function(){this.open=(method,url,async)=>{assert.equal(method,'GET');assert.equal(url,'https://controlled.invalid/api/v1/places?status=online&per_page=1000');assert.equal(async,true);};
 this.setRequestHeader=()=>{};this.send=()=>{};this.readyState=4;this.status=200;
 Object.defineProperty(this,'responseText',{get:()=>{reads++;return JSON.stringify({data:{places:[{id:'owned'}]}});}});requests.push(this);}};
vm.createContext(source);vm.runInContext(section(script,'    function fetchMetaverse(', '    function sendToPlacesUi('),source);
source.fetchMetaverse(0,1);source.requestGeneration=2;requests[0].onreadystatechange();assert.equal(reads,0);assert.equal(finished,0);
source.fetchMetaverse(0,2);requests[1].onreadystatechange();assert.equal(reads,1);assert.equal(finished,1);
requests[1].onreadystatechange();assert.equal(reads,1);assert.equal(finished,1);
source.fetchMetaverse(0,2);source.appStatus=false;requests[2].onreadystatechange();assert.equal(reads,1);assert.equal(finished,1);
''')


if __name__=='__main__':unittest.main()
