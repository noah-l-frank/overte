"""Ordinary W3C/Qt file input with actual disk bytes and host JS execution.

The native Qt/UIKit/VM DTO producers remain explicit models. No native/device
execution is claimed. Ordinary input handlers select actual files; only their
subsequent host JS execution creates the modeled returned app controls.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import gc
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import weakref
from urllib.parse import unquote,urlsplit
from adapters.native_script_files import NAMES
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary
from ios.self_tests.test_ios_normal_scripts import Native
from ios.self_tests.test_ios_tablet_web_buttons import Boundary as Buttons
from ios.self_tests.test_ios_tablet_web_sources import stamp
from ios.self_tests.world_web_ui_roots_fixture import Root
from self_tests.test_token_script_file_ui import NativeBoundary as Picker
from self_tests.test_script_manager_status import observed


class TabletNormalBoundary(TabletWholeBoundary):
    def __init__(self,test,**options):
        super().__init__(test,**options)
        self.ui=Native();self.ui.epoch=self.epoch;self.ui.qt.sleep=self.sleep
        self.ui.execute=self.execute;self.runtime.client=self.ui
        self.ui.qt.clock=self.elapsed;self.ui.file_source=None
        self.directories={};self.owners={};self.manager=None;self.code=None;self.modules=[];self.loaded=[]
        # Host observer journals do not live inside the iOS app sandbox. Keep
        # the modeled native Documents namespace physically separate as well;
        # the ordinary picker still enumerates every real entry in that scope.
        self.native_documents=self.root/'native-app-documents';self.native_documents.mkdir(mode=0o700)
        self.button_source=Buttons();self.button_source.now=self.epoch()
        self.controls={};self.manager_root=None;self.picker_root=None;self.script_inputs=[];self.ignored=False
        self.picker_fault=''
        self.dialog_events=[];self.listener=None;self.listener_weak=None;self.dialog_id=None
        original_controls=self.ui.controls
        def controls():
            rows=original_controls()
            for row in rows:
                if row['id']=='scripts.from-file':row['manager']=observed(componentSource='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml')
            if self.ui.qt.opened and self.ui.qt.page=='home':
                for verb,metadata in self.controls.items():
                    rows.append(dict(id='tablet-web-app.'+verb,token=str(uuid.uuid5(uuid.NAMESPACE_URL,metadata['control'])),enabled=True,focused=False,
                        frame=dict(x=10,y=80+60*len(rows),width=200,height=48),tabletAppButton=deepcopy(metadata)))
            return rows
        self.ui.controls=controls
        call=self.ui.call
        def input_call(method,path,body=None):
            was_open=bool(self.ui.file_ui and self.ui.file_ui.opened)
            result=call(method,path,body)
            if method=='POST' and path.endswith('/click'):
                self.sync_roots()
                if was_open and not self.ui.file_ui.opened:
                    selected=self.ui.file_ui.accepted[-1] if self.ui.file_ui.accepted else ''
                    self.dialog_event('response-entered',selected)
                    if selected and selected not in self.loaded:
                        self.loaded.append(selected)
                        if not self.ignored:self.load(selected)
                    self.dialog_event('response-returned',manager=self.manager)
                    self.listener=None;gc.collect()
            return result
        self.ui.call=input_call

    def sync_roots(self):
        if self.ui.qt.page=='scripts' and self.manager_root is None:
            self.manager_root=Root('manager');self.roots.elapsed=self.epoch()-20000;self.roots.observe(self.manager_root)
        if self.ui.file_ui and self.ui.file_ui.opened and self.picker_root is None:
            self.picker_root=Root('picker');self.roots.elapsed=self.epoch()-20000;self.roots.observe(self.picker_root)
            self.listener=Root('picker');self.listener_weak=weakref.ref(self.listener);self.dialog_id=uuid.uuid4().hex
            self.dialog_event('listener-created')

    def dialog_event(self,kind,text='',manager=None):
        self.sleep(.001);response=None;exists=None
        if kind=='response-entered':
            encoded=text.encode('utf-16le');response=dict(text=text,encoding='utf-16le-code-units',codeUnits=len(encoded)//2,sha256=hashlib.sha256(encoded).hexdigest())
            exists=bool(text and Path(unquote(urlsplit(text).path)).is_file())
        self.dialog_events.append(dict(eventSequence=len(self.dialog_events)+1,capturedEpochMs=self.epoch(),monotonicMs=self.epoch()-19000,
            dialogInstance=self.dialog_id,kind=kind,response=response,fileExists=exists,manager=deepcopy(manager)))

    def inventory(self):
        self.sync_roots();self.roots.elapsed=self.epoch()-20000;source=self.roots.source();source['processId']=42
        managers=[];pickers=[];membership=dict(managers=[],pickers=[])
        if self.manager_root:
            managers=[observed(componentSource=self.manager_root.source,rootVisible=self.ui.qt.opened and self.ui.qt.page=='scripts',
                labelVisible=self.ui.qt.opened and self.ui.qt.page=='scripts')]
            membership['managers']=[self.roots.observe(self.manager_root)]
        if self.picker_root:
            pickers=[dict(componentSource=self.picker_root.source,visible=self.ui.file_ui.opened,closing=False,requestId='',errorText='')]
            membership['pickers']=[self.roots.observe(self.picker_root)]
        return dict(inventoryVersion=2,complete=True,tabletPresent=True,tabletShown=self.ui.qt.opened,managers=managers,pickers=pickers,
            rootOwnership=source,rootMembership=membership)

    def execute_app(self,path):
        program=r'''const fs=require('fs'),vm=require('vm');const file=process.argv[1],rows=[];
const tablet={addButton(p){rows.push(p);return {clicked:{connect(){},disconnect(){}}}},webEventReceived:{connect(){},disconnect(){}}};
const Script={require(p){const module={exports:{}};vm.runInNewContext(fs.readFileSync(require('path').resolve(require('path').dirname(file),p),'utf8'),{module});return module.exports},scriptEnding:{connect(){}}};
vm.runInNewContext(fs.readFileSync(file,'utf8'),{Script,Tablet:{getTablet(){return tablet}}},{filename:require('url').pathToFileURL(file).href});
process.stdout.write(JSON.stringify(rows));'''
        actual=subprocess.run(['node','-e',program,str(path)],capture_output=True,text=True,timeout=5)
        self.test.assertEqual(0,actual.returncode,actual.stderr);return json.loads(actual.stdout)

    def load(self,url):
        """Only reached from the actual file picker's accepted file result."""
        path=Path(unquote(urlsplit(url).path));self.test.assertTrue(path.is_file())
        properties=self.execute_app(path);self.test.assertEqual(3,len(properties))
        epoch=self.epoch();self.manager=dict(instance=uuid.uuid4().hex,assigned=True,url=url,loadGeneration=1,assignedEpochMs=epoch)
        encoded=path.read_text().encode('utf-16le');self.code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(encoded)//2,
            sha256=hashlib.sha256(encoded).hexdigest(),submittedEpochMs=epoch)
        self.modules=[dict(url=(path.parent/name).as_uri(),loaded=True,cached=False,sequence=index,capturedEpochMs=epoch)
            for index,name in enumerate(('script-bundle/companion.js','companion.js','script-bundle/main.js'),1)]
        self.button_source.manager=deepcopy(self.manager);self.button_source.code=deepcopy(self.code);self.button_source.now=epoch
        for props in properties:
            verb=props['semanticId'].rsplit('.',1)[1];key=self.button_source.add(verb)
            row=self.button_source.rows[-1];row['semanticId']=props['semanticId'];row['fixtureUrl']=props['fixtureUrl']
            metadata=self.button_source.bind(key);match=props['semanticId'].split('.')
            metadata.update(featureRun=match[1],nonce=match[2],semanticId=props['semanticId'],fixtureUrl=props['fixtureUrl'])
            self.controls[verb]=metadata
        self.ui.qt.rows=[dict(url=url,path=str(path))]
        self.sleep(.05)

    def produce(self,query):
        action=query['action'];epoch=self.epoch()
        if action=='feature-ios-script-dialogs':
            if self.listener_weak is not None and self.listener_weak() is None and self.dialog_events[-1]['kind']!='listener-destroyed':self.dialog_event('listener-destroyed')
            name,value=super().produce(query);value['clockBefore']=stamp(self.epoch());value['clockAfter']=stamp(self.epoch())
            value['source'].update(eventSequence=len(self.dialog_events),events=deepcopy(self.dialog_events));return name,value
        if action=='feature-script-files':
            self.sequence[action]=self.sequence.get(action,0)+1;run=query['runId'];operation=query['operation']
            directory=self.native_documents/('feature-script-'+run)
            if operation=='stage':
                self.test.assertNotIn(run,self.owners);self.owners[run]=query['ownerToken'];directory.mkdir(mode=0o700);(directory/'script-bundle').mkdir(mode=0o700)
                for name,encoded in query['files'].items():
                    path=directory/name;path.write_bytes(base64.b64decode(encoded,validate=True));path.chmod(0o600)
                self.directories[run]=directory;self.ui.file_ui=Picker(directory);self.ui.file_ui.fault=self.picker_fault;source=dict(performed=True)
            else:
                self.test.assertEqual(self.owners.get(run),query['ownerToken'])
                if operation=='release':
                    for name in NAMES:(directory/name).unlink()
                    (directory/'script-bundle').rmdir();directory.rmdir();source=dict(performed=True)
                elif operation=='locate':source=dict(locationVersion=1,exists=directory.exists(),directory=directory.as_uri())
                elif not directory.exists():source=dict(exists=False,files=[])
                else:
                    source=dict(exists=True,directory=directory.as_uri(),files=[])
                    for name in NAMES:
                        raw=(directory/name).read_bytes();source['files'].append(dict(name=name,exists=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode()))
            return 'feature-script-files.json',dict(schemaVersion=1,requestId=query['commandId'],instance='d'*32,sequence=self.sequence[action],
                requestedEpochMs=epoch,capturedEpochMs=epoch,processId=42,runId=run,operation=operation,source=source)
        if action=='normal-ui-input':
            if query['operation']=='observe':
                self.sequence[action]=self.sequence.get(action,0)+1;self.ui.qt.clock=self.elapsed
                value=self.ui.observed();value.update(elapsedMs=round(self.elapsed*1000),scriptObservationVersion=1,scriptSourceSequence=self.sequence[action],
                    scriptInventory=self.inventory(),tabletAppControlsVersion=1)
                return 'ios-normal-ui-request-result.json',dict(schemaVersion=1,commandId=query['commandId'],observation=value)
            self.script_inputs.append(deepcopy(query));self.ui.post(type('Request',(),dict(data=json.dumps(query).encode()))(),1)
            return 'ios-normal-ui-request-result.json',deepcopy(self.ui.receipt)
        if action=='normal-feature-observe':
            self.sequence[action]=self.sequence.get(action,0)+1
            return 'normal-feature-observation.json',dict(schemaVersion=1,requestId=query['commandId'],instance='f'*32,sampleSequence=self.sequence[action],
                sampleEpochMs=epoch,complete=True,scripts=deepcopy(self.ui.qt.rows))
        if action=='feature-script-observe' and self.manager is not None:
            self.sequence[action]=self.sequence.get(action,0)+1
            engine=dict(url=self.manager['url'],running=True,stopping=False,finished=False,code=deepcopy(self.code),required=dict(instance=self.manager['instance'],sequence=3,modules=deepcopy(self.modules)))
            return 'feature-script-observation.json',dict(schemaVersion=1,requestId=query['commandId'],instance='5'*32,sequence=self.sequence[action],processId=42,
                requestedEpochMs=epoch,capturedEpochMs=epoch,source=dict(complete=True,sourceIdentityVersion=1,membershipSourceVersion=1,
                    membership=dict(complete=True,revision=1,managers=[deepcopy(self.manager)]),engines=[engine]))
        if action=='feature-ios-tablet-app-buttons':
            self.button_source.now=max(self.button_source.now,epoch);value=self.button_source.snapshot();value.update(commandId=query['commandId'],processId=42,fixtureUrl=self.source.fixture)
            # The actual modeled weak sweeps/return observation take time.
            # Preserve their original clocks and let the outer native clock
            # progress through that work instead of retiming the receipt.
            self.sleep(max(0,value['clockAfter']['epochMs']-self.epoch())/1000)
            return action+'.json',value
        return super().produce(query)
