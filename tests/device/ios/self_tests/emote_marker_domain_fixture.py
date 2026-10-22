"""Synthetic Domain/native producer driven by actual ordinary Script UI recipe.

The exact staged marker/companion bytes execute in an isolated host Node VM.
No native, device, compiler, installed Overte VM or renderer is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_script_manager import NormalScriptManager
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from ios.adapters.web_closures import KINDS,resources_for
from ios.adapters.graphics_history import restore_native
from ios.self_tests.test_ios_emote_marker_owner import Domain
from ios.self_tests.test_ios_emote_marker_measurements import frames
from self_tests.test_token_script_ui import NativeBoundary as Qt
from self_tests.test_token_script_file_ui import NativeBoundary as Picker
from ios.self_tests.test_ios_script_dialogs import events as dialog_events

PROGRAM=r'''
const fs=require('node:fs'),vm=require('node:vm');
const data=JSON.parse(fs.readFileSync(0,'utf8'));let added=[],deleted=[],endings=[];
const sandbox={Script:{require:path=>{if(path!=='./companion.js')throw Error('foreign module');
 const module={exports:{}};vm.runInNewContext(data.companion,{module});return module.exports;},scriptEnding:{connect:f=>endings.push(f)}},
 Entities:{addEntity:(properties,host)=>{added.push({id:data.uuid,properties,host});return data.uuid;},deleteEntity:id=>deleted.push(id)},
 MyAvatar:{position:{x:0,y:0,z:4},orientation:{x:0,y:0,z:0,w:1}},Vec3:{sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z}),multiplyQbyV:(_q,v)=>v}};
vm.runInNewContext(data.main,sandbox,{timeout:1000});for(const ending of endings)ending();
process.stdout.write(JSON.stringify({added,deleted}));
'''


class DiskFiles:
    def __init__(self,domain):self.domain=domain;self.root=domain.scope.root/('feature-script-'+domain.scope.run);self.calls=[]
    def request(self,operation,run,owner,files=None):
        import base64
        self.calls.append((operation,run,owner));assert run==self.domain.scope.run
        if operation=='stage':
            self.root.mkdir(mode=0o700);(self.root/'script-bundle').mkdir(mode=0o700)
            for name,raw in files.items():(self.root/name).write_bytes(raw)
            return dict(performed=True)
        if operation=='release':
            for name in ('script.js','companion.js','script-bundle/main.js','script-bundle/companion.js'):(self.root/name).unlink(missing_ok=True)
            if self.root.exists():(self.root/'script-bundle').rmdir();self.root.rmdir()
            return dict(performed=True)
        if not self.root.exists():return dict(exists=False,files=[])
        return dict(exists=True,directory=self.root.as_uri(),files=[dict(name=name,exists=True,base64=base64.b64encode((self.root/name).read_bytes()).decode())
            for name in ('script.js','companion.js','script-bundle/main.js','script-bundle/companion.js')])


class IO:
    def __init__(self,domain):self.domain=domain;self.qt=Qt();self.file=Picker(domain.files.root);self.actions=[]
    def sleep(self,seconds):self.qt.sleep(seconds);self.file.sleep(seconds);self.domain.sleep(seconds)
    def capture(self):
        value=self.qt.capture();value.update(fileControlsVersion=1,instance='actual-synthetic-marker-ui')
        if self.qt.opened and self.qt.page=='scripts':
            files=self.file.capture();value['controls']=files['controls'] if self.file.opened else value['controls']+files['controls']
        return value
    def activate(self,identifier,*,source=None):
        self.actions.append(identifier)
        if identifier.startswith('script-file.') or identifier=='scripts.from-file':
            self.file.activate(identifier,source=source)
            if identifier=='scripts.from-file':self.domain.dialog_birth()
            if identifier=='script-file.confirm' and not self.file.opened:
                self.qt.rows.append(dict(url=self.file.accepted[-1],path=self.file.accepted[-1]));self.domain.start();self.domain.dialog_return(self.file.accepted[-1],True,self.domain.worker)
            if identifier in ('script-file.cancel','script-file.review-cancel') and not self.file.opened:self.domain.dialog_return('',False,None)
        else:
            self.qt.activate(identifier,source=source)
            if identifier=='scripts.stop.0' and not self.qt.rows:self.domain.stop()
    def tablet(self,opened):
        self.actions.append('tablet.open' if opened else 'tablet.close');page=self.qt.page;self.qt.tablet(opened)
        if not opened:self.qt.page=page  # Hiding alone leaves the real-page analogue alive.
    def replace(self,identifier,text):self.file.replace(identifier,text)
    def submit(self,identifier):self.file.submit(identifier)
    def select_index(self,identifier,index):self.file.select_index(identifier,index)
    def release(self):self.actions.append('release')
    def observe(self,after):
        value,_epoch=self.qt.observe(after);value['sampleEpochMs']=self.domain.epoch();return value,self.domain.epoch()


class RunningDomain(Domain):
    def __init__(self,scope):
        super().__init__(scope);self.files=DiskFiles(self);scope.files.native=self.files;self.io=IO(self)
        self.worker=None;self.engine=None;self.marker=None;self.terminal_events=[];self.context=None;self.running=False;self.sequences['work']=0
        self.world_template['source']['view']['mode']='first person look at'
        scope.manager=self.manager;scope.surface=lambda:SimpleNamespace(select_camera=self.select_view)
        scope.work=SimpleNamespace(last=None,read=self.work)
    def attach(self,scope):
        self.scope=scope;scope.files.native=self.files;scope.monotonic=lambda:self.time;scope.epoch_ms=lambda:90000+self.time*1000;scope.sleep=self.sleep
        scope.native=NativeFeatureObservation(self.native_send,lambda:self.boundary.original(),self.epoch,lambda:True,31,
            ios=True,native_clock_bound=True,monotonic=lambda:self.time,sleep=self.sleep)
        last=scope.frames[-1];restore_native(scope.native,last['clockJoin']['nativeAfter'])
        scope.world=SimpleNamespace(last=deepcopy(last['world']),read=self.world);scope.terminals=SimpleNamespace(last=deepcopy(last['terminal']),read=self.terminal)
        scope.dialogs=SimpleNamespace(last=deepcopy(last['dialogs']),read=self.dialogs)
        scope.web=SimpleNamespace(last=deepcopy(last['web']),read=self.web);work=[row['work'] for row in scope.frames if row['work'] is not None]
        scope.work=SimpleNamespace(last=deepcopy(work[-1]) if work else None,read=self.work);scope.live=dict(native=SimpleNamespace(capture=self.widgets))
        scope.manager=self.manager;scope.surface=lambda:SimpleNamespace(select_camera=self.select_view)
    def manager(self):
        s=self.scope;ui=TokenScriptUI(self.io,monotonic=lambda:self.time,sleep=self.io.sleep)
        picker=TokenScriptFilePicker(self.io,self.files.root.as_uri(),monotonic=lambda:self.time,sleep=self.io.sleep)
        return NormalScriptManager(ui,self.io.observe,PrivateFeatureState(s.store.path.with_name('ios-emote-'+s.role+'-marker-script.json')),
            s.binding,source_kind='script-file-bundle',file_owner=s.files,file_picker=picker,monotonic=lambda:self.time,sleep=self.io.sleep)
    def select_view(self,mode):
        self.io.tablet(True)
        if self.io.qt.page=='scripts':self.io.activate('tablet.home')
        self.io.actions.append('view.'+mode);self.world_template['source']['view']['mode']=mode;self.io.tablet(False)
    def start(self):
        raw=(self.files.root/'script-bundle/main.js').read_bytes();companion=(self.files.root/'script-bundle/companion.js').read_text()
        actual_id=str(uuid.uuid4());result=subprocess.run(['node','-e',PROGRAM],input=json.dumps(dict(main=raw.decode(),companion=companion,uuid=actual_id)),
            capture_output=True,text=True,timeout=5,check=True);self.vm=json.loads(result.stdout)
        assert len(self.vm['added'])==1 and self.vm['deleted']==[actual_id]
        self.time+=.005;self.worker=dict(instance=uuid.uuid4().hex,assigned=True,url=self.file_url(),loadGeneration=1,assignedEpochMs=self.epoch())
        self.time+=.005;self.terminal_events=[dict(eventSequence=1,capturedEpochMs=self.epoch(),monotonicMs=round(self.time*1000),kind='thread-bound',
            threadInstance='a'*32,manager=deepcopy(self.worker),code=None,work=None)]
        self.time+=.005;code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(raw.decode().encode('utf-16le'))//2,
            sha256=hashlib.sha256(raw.decode().encode('utf-16le')).hexdigest(),submittedEpochMs=self.epoch())
        self.engine=deepcopy(frames()[1]['source']['scriptOriginal']['source']['engines'][0]);self.engine.update(url=self.file_url(),code=code)
        self.engine['required']['instance']=self.worker['instance'];self.engine['required']['modules'][0]['url']=(self.files.root/'script-bundle/companion.js').as_uri()
        properties=self.vm['added'][0]['properties'];stamp=str(self.epoch()*1000)
        self.marker={k:properties[k] for k in ('name','type','userData','sourceUrl','visible','collisionless')}
        self.marker.update(id=actual_id,hostType=self.vm['added'][0]['host'],lastEditedEpochUs=stamp)
        for key in ('position','dimensions'):self.marker[key]=[properties[key][axis] for axis in ('x','y','z')]
        self.marker['rotation']=[properties['rotation'][axis] for axis in ('x','y','z','w')];self.running=True
    def file_url(self):return (self.files.root/'script-bundle/main.js').as_uri()
    def dialog_birth(self):
        assert not self.dialog_events
        self.time+=.005;row=dialog_events()[0];row.update(capturedEpochMs=self.epoch(),monotonicMs=round(self.time*1000));self.dialog_events=[row]
    def dialog_return(self,text,exists,manager):
        assert len(self.dialog_events)==1
        for row in dialog_events(text,exists,deepcopy(manager))[1:]:
            self.time+=.005;row.update(capturedEpochMs=self.epoch(),monotonicMs=round(self.time*1000));self.dialog_events.append(row)
    def stop(self):
        assert self.worker is not None and self.running and self.vm['deleted']==[self.marker['id']]
        for kind in ('shutdown-drained','thread-finished'):
            self.time+=.005;self.terminal_events.append(dict(eventSequence=len(self.terminal_events)+1,capturedEpochMs=self.epoch(),
                monotonicMs=round(self.time*1000),kind=kind,threadInstance='a'*32,manager=deepcopy(self.worker),code=deepcopy(self.engine['code']),
                work=dict(signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=0) if kind=='shutdown-drained' else None))
        self.running=False
    def world(self,run):
        value=super().world(run);source=value['source'];script=source['scriptOriginal']['source']
        script['engines']=[deepcopy(self.engine)] if self.running else [];script['membership'].update(revision=0 if self.worker is None else 1 if self.running else 2,
            managers=[deepcopy(self.worker)] if self.running else [])
        if self.running:
            source['markers']=[deepcopy(self.marker)];marker=self.marker
            script['effects'].update(scannedEntities=1,entities=[dict(id=marker['id'],name=marker['name'],type=marker['type'],hostType=marker['hostType'],
                userData=marker['userData'],lastEditedEpochUs=int(marker['lastEditedEpochUs']),color=[0,0,0])])
            source['tree'].update(totalEntities=1,entities=[dict(id=marker['id'],hostType=marker['hostType'],ready=True,createdEpochUs=marker['lastEditedEpochUs'],
                lastEditedEpochUs=marker['lastEditedEpochUs'],lastEditedAfterEpochUs=marker['lastEditedEpochUs'],semanticBytes=100,semanticSha256='d'*64)])
        source['tree'].update(revisionBefore=1 if self.worker is None else 2 if self.running else 3,revisionAfter=1 if self.worker is None else 2 if self.running else 3)
        return value
    def terminal(self,after):
        value=super().terminal(after);value['source'].update(eventSequence=len(self.terminal_events),events=deepcopy(self.terminal_events));self.scope.terminals.last=deepcopy(value);return value
    def work(self,manager,after):
        assert self.running and manager==self.worker['instance'];sequence=self.tick('work');request='ios-'+format(6000+sequence,'032x')
        source=dict(complete=True,revision=1,manager=deepcopy(self.worker),code=deepcopy(self.engine['code']),workers=[dict(membership=deepcopy(self.worker),
            running=True,stopping=False,finished=False,done=False)],work=dict(scriptWorkVersion=1,requestId=request,sequence=sequence,requestedEpochMs=self.epoch(),
            capturedEpochMs=self.epoch(),signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=[]))
        value=dict(schemaVersion=1,requestId=request,instance='7'*32,sequence=sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)
        self.scope.work.last=deepcopy(value);return value
    def widgets(self):
        value=super().widgets();shown=self.io.qt.opened;value['tabletShown']=shown
        inventory=value['scriptInventory'];inventory['tabletShown']=shown
        if self.io.qt.page=='scripts':
            inventory['managers']=[dict(managerSourceVersion=1,available=True,componentSource='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml',
                statusText='',labelText='',rootVisible=shown,labelVisible=False)]
        if self.io.file.opened:inventory['pickers']=[dict(componentSource='qrc:/qml/dialogs/NativeFileBrowser.qml',visible=True,closing=False,requestId='',errorText='')]
        return value
    def web(self,run,url):
        value=super().web(run,url)
        if self.context is not None:
            row=deepcopy(self.context);row['updatedEpochMs']=self.epoch()
            if not self.running:
                for group in ('callbacks','resources'):
                    for counter in row[group].values():counter.update(retired=counter['created'],pending=0)
            value['contexts']=[row]
        return value
    def paint(self):
        assert self.running;self.context=dict(id=1,descriptor=dict(handle=1,creation=1,grant=1,page=1,surface='world-entity',identitySha256='8'*64,
            sourceUrl=self.marker['sourceUrl']),createdEpochMs=self.epoch(),updatedEpochMs=self.epoch(),
            callbacks={key:dict(created=1,retired=0,pending=1) for key in KINDS},resources={key:dict(created=1,retired=0,pending=1) for key in resources_for(5)})
