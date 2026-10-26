"""Actual host files + original QML JS, with explicit native/Qt boundary models.

No C++ is compiled. These modeled observations cannot qualify an installed
candidate, native acquisition, UIKit input, server work, or actual devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import uuid
import weakref
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import assets_files as files
from ios.adapters.assets_controls import SUFFIXES
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.normal_input import NativeInput,observation

RUN,TICKET='a'*32,'b'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
EPOCH=1900000000000
BINDING=dict(sourceRevision='d'*40,artifactSha256='e'*64,processIdentity='42',sessionId='bound-assets-session',generation=1,targetFingerprint='f'*64)
ROOT=Path(__file__).resolve().parents[4]


def uid():return str(uuid.uuid4())


class Consumer:
    pass


class Boundary:
    host_extra=()
    def __init__(self,directory):
        self.directory=Path(directory);self.elapsed=0;self.live=True;self.requests=[];self.packet=None;self.sequence=0;self.ui_sequence=0;self.work_sequence=0
        self.channel=uuid.uuid4().hex;self.ui_instance=uid();self.work_instance=uid();self.normal_instance=uid();self.window=uid();self.page=uid();self.picker=uid();self.model=uid();self.menu=uid()
        self.roots=[];self.tokens={};self.sequence_input=0;self.inputs=[];self.jobs=[];self.holders=[];self.mutate=None;self.lost=None;self.freeze_native_clock=False
        self.host=subprocess.Popen(['node',str(Path(__file__).with_name('assets_picker_host.js')),
            str(ROOT/'interface/resources/qml/hifi/dialogs/TabletAssetServer.qml'),str(ROOT/'interface/resources/qml/dialogs/NativeFileBrowser.qml'),
            str(ROOT/'interface/resources/qml/hifi/tablet/TabletNavigation.qml'),*self.host_extra],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:self.host_state=self.exchange(dict(op='configure',initialDirectory=str(self.directory)))
        except BaseException:self.close();raise

    def close(self):
        self.host.terminate()
        try:self.host.wait(timeout=5)
        except subprocess.TimeoutExpired:self.host.kill();self.host.wait(timeout=5)
        self.host.stdin.close();self.host.stdout.close();self.host.stderr.close()

    def exchange(self,value):
        self.host.stdin.write(json.dumps(value)+'\n');self.host.stdin.flush()
        if not select.select([self.host.stdout],[],[],5)[0]:raise AssertionError('Original-QML host response timed out')
        line=self.host.stdout.readline()
        if not line:raise AssertionError('Original-QML host did not return: '+self.host.stderr.read())
        result=json.loads(line)
        if 'error' in result:raise AssertionError(result['error'])
        self.host_state=result;return result

    def configure(self,**values):return self.exchange(dict(op='configure',**values))
    def clock(self):return EPOCH+(0 if self.freeze_native_clock else self.elapsed)
    def tick(self,milliseconds=1):self.elapsed+=milliseconds;return self.clock()
    def monotonic(self):return self.elapsed/1000
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)
    def stamp(self):return dict(epochMs=self.clock(),monotonicMs=0 if self.freeze_native_clock else self.elapsed)

    def ui(self):
        state=self.exchange(dict(op='snapshot'));self.ui_sequence+=1
        for role,alive,identity in (('page',state['pageAlive'],self.page),('picker',state['pickerAlive'],self.picker)):
            if alive and not any(row['rootId']==identity for row in self.roots):
                self.roots.append(dict(rootId=identity,role=role,componentSource='qrc:'+SUFFIXES[role],ownerRootId=self.page,firstObservedEpochMs=self.clock(),alive=True))
        result=deepcopy(self.roots)
        for row in result:
            row['alive']=state[row['role']+'Alive']
            if not row['alive']:continue
            row.update(windowId=self.window,visible=True)
            if row['role']=='picker':row.update(deepcopy(state['ui']))
            else:row.update(deepcopy(state['page']),canWrite=True,selectedPath='',selectedUrl='',modelId=self.model,modelRevision=1)
        return dict(iosAssetUiInventoryVersion=1,available=True,complete=True,instance=self.ui_instance,sequence=self.ui_sequence,
            capturedEpochMs=self.clock(),processId=42,roots=result)

    def work(self):
        self.work_sequence+=1;result=[]
        for job in self.jobs:
            row=deepcopy(job['row']);row['alive']=job['weak']() is not None
            if not row['alive'] and job['row']['expired'] is None:job['row']['expired']=self.stamp();row['expired']=deepcopy(job['row']['expired'])
            result.append(row)
        return dict(iosAssetUploadWorkVersion=1,available=True,complete=True,instance=self.work_instance,processId=42,
            sequence=self.work_sequence,clock=self.stamp(),jobs=result)

    def hold_consumer(self,*,pending=0):
        holder=Consumer();self.holders.append(holder)
        self.jobs.append(dict(weak=weakref.ref(holder),row=dict(id=uid(),kind='bundle',files=[str(self.root/'main.gltf')],created=self.stamp(),
            alive=True,terminal=True,ended=self.stamp(),expired=None,entered=pending,returned=0,pendingBodies=pending)))

    def normal(self):
        self.tick();ui=self.ui();controls=[]
        for index,item in enumerate(self.host_state['controls']):
            identifier=item['id'];role='menu' if identifier in ('assets.menu','assets.open') else 'picker' if identifier.startswith('asset-file.') else 'page'
            metadata=self.control_metadata(identifier,item,role)
            signature=json.dumps(metadata,sort_keys=True)
            old=self.tokens.get(identifier)
            if old is None or old[0]!=signature:self.tokens[identifier]=(signature,uid())
            controls.append(dict(id=identifier,token=self.tokens[identifier][1],enabled=item.get('enabled',True),focused=item.get('focused',False),
                frame=dict(x=0,y=index*48,width=100,height=48),assetControl=metadata))
        value=dict(schemaVersion=1,instance=self.normal_instance,frameSpace='qt-window-logical',processId=42,sampleEpochMs=self.clock(),
            elapsedMs=self.elapsed,lastSequence=self.sequence_input,tabletShown=self.host_state['pageAlive'],ready=True,controls=controls,
            assetControlsVersion=1,assetInventory=ui,**self.extensions(ui))
        return observation(value,42,self.clock())

    def control_metadata(self,identifier,item,role):
        metadata=dict(assetControlVersion=1,role=role,rootId=self.menu if role=='menu' else self.picker if role=='picker' else self.page,
            windowId=self.window,componentSource='qrc:'+SUFFIXES[role],controlId=identifier)
        if role=='menu':metadata.update(sourceType=2 if identifier=='assets.menu' else 1,
            labelSha256=hashlib.sha256(('Edit' if identifier=='assets.menu' else 'Asset Browser').encode()).hexdigest())
        else:metadata.update(ownerRootId=self.page,rowUrl=item.get('rowUrl',''),fieldText=item.get('fieldText',''),
            navigationSource='qrc:/hifi/tablet/TabletNavigation.qml' if identifier=='assets.home' else '')
        return metadata

    def extensions(self,ui):return {}

    def native_input(self):
        boundary=self
        class ModeledInput(NativeInput):
            def __init__(self):
                self.monotonic=boundary.monotonic;self.sleep=boundary.sleep;self.native_epoch_ms=boundary.clock
                self.process=dict(pid=42);self.instance=boundary.normal_instance;self.last_receipt=None
            def capture(self):
                query=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe')
                intent=getattr(self,'observe_intent',None)
                if intent is not None:intent(deepcopy(query))
                value=boundary.normal();self.last_receipt=dict(schemaVersion=1,commandId=query['commandId'],observation=deepcopy(value));return value
            def deliver(self,command,*,before_send=None):
                if before_send is not None:need(before_send() is not False)
                need(command['sequence']==boundary.sequence_input+1 and command['instance']==boundary.normal_instance)
                controls=boundary.normal()['controls'];targets=[row for row in controls if row['token']==command['fieldToken']];need(len(targets)==1)
                boundary.sequence_input=command['sequence'];boundary.inputs.append(deepcopy(command))
                result=boundary.exchange(dict(op='input',id=targets[0]['id'],action=command['operation'],
                    **{key:command[key] for key in ('text','index') if key in command}))
                boundary.tick()
                if result.get('lost'):raise NativeUIError('Modeled ordinary input return was lost')
                self.last_receipt=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,status=dict(schemaVersion=1,commandId=command['commandId'],
                    instance=command['instance'],sequence=command['sequence'],performed=True,processId=42,sampleEpochMs=boundary.clock()))
                return dict(performed=True)
        return ModeledInput()

    def file_rows(self,resource):
        result=[]
        for name in files.BUNDLES[resource][1]:
            path=self.root/name;row=dict(path=name,exists=path.exists())
            if row['exists']:
                info=path.lstat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600)
                raw=path.read_bytes();row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=files.encoded(raw),
                    identity={key:str(value) for key,value in dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
                        modifiedSeconds=info.st_mtime_ns//10**9,modifiedNanoseconds=info.st_mtime_ns%10**9,
                        changedSeconds=info.st_ctime_ns//10**9,changedNanoseconds=info.st_ctime_ns%10**9).items()})
            result.append(row)
        return result

    @staticmethod
    def node(path):
        info=path.lstat();need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700)
        return dict(device=str(info.st_dev),inode=str(info.st_ino))

    def send(self,query):
        files.command(query);self.requests.append(deepcopy(query));before=self.tick();source=dict(ui=self.ui(),work=self.work());operation=query['operation']
        self.root=self.directory/('feature-assets-'+query['runId']+'-'+query['ownerToken'][:16])
        if operation=='stage':
            self.root.mkdir(mode=0o700);manifest_files=[]
            for name,encoded in query['files'].items():
                path=self.root/name;path.parent.mkdir(mode=0o700,exist_ok=True);raw=files.original_bytes(encoded);path.write_bytes(raw);path.chmod(0o600)
            for name in files.BUNDLES[query['resource']][1]:
                raw=(self.root/name).read_bytes();manifest_files.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            manifest=dict(assetFileOwnerVersion=1,runId=query['runId'],ownerToken=query['ownerToken'],ticket=query['ticket'],resource=query['resource'],
                primaryPath=files.BUNDLES[query['resource']][0],files=manifest_files)
            owner_bytes=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
            (self.root/'.owner.v1.json').write_bytes(owner_bytes);(self.root/'.owner.v1.json').chmod(0o600)
            sealed=[dict(path=row['path'],identity=row['identity'],parent=self.node((self.root/row['path']).parent)) for row in self.file_rows(query['resource'])]
            seal=dict(assetFileSealVersion=1,ownerSha256=hashlib.sha256(owner_bytes).hexdigest(),root=self.node(self.root),files=sealed)
            (self.root/'.complete.v1.json').write_text(json.dumps(seal,sort_keys=True,separators=(',',':')));(self.root/'.complete.v1.json').chmod(0o600);result=dict(performed=True)
        elif operation=='observe':
            result=dict(exists=self.root.exists(),files=self.file_rows(query['resource']) if self.root.exists() else [])
            if result['exists']:
                need(self.root.is_dir() and not self.root.is_symlink())
                owner_bytes=(self.root/'.owner.v1.json').read_bytes();manifest=json.loads(owner_bytes)
                need(owner_bytes==json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
                    and all(manifest[key]==query[key] for key in ('runId','ticket','ownerToken','resource')))
                seal=json.loads((self.root/'.complete.v1.json').read_text());need(seal['root']==self.node(self.root))
                for row,original in zip(result['files'],seal['files']):
                    need(row['path']==original['path'] and self.node((self.root/row['path']).parent)==original['parent'])
                    if row['exists']:need(row['identity']==original['identity'])
                result.update(directory=self.root.as_uri(),complete=(self.root/'.complete.v1.json').exists(),retiredPrimary=(self.root/'.retire-primary.v1.json').exists(),
                    releasing=(self.root/'.release.v1.json').exists(),manifest=manifest,ownerBase64=files.encoded(owner_bytes),seal=seal)
        else:
            need(same(query['originals'],self.file_rows(query['resource'])))
            files.quiet(source,selected=self.root.as_uri()+'/'+files.BUNDLES[query['resource']][0] if operation=='retire-primary' else None)
            marker='.retire-primary.v1.json' if operation=='retire-primary' else '.release.v1.json'
            (self.root/marker).write_text('{}');(self.root/marker).chmod(0o600)
            if operation=='retire-primary':(self.root/files.BUNDLES[query['resource']][0]).unlink()
            else:
                for name in files.BUNDLES[query['resource']][1]:(self.root/name).unlink(missing_ok=True)
                for path in sorted(self.root.iterdir()):
                    if path.is_dir():path.rmdir()
                    else:path.unlink()
                self.root.rmdir()
            result=dict(performed=True)
        source['files']=result;self.sequence+=1;after=self.tick()
        self.packet=dict(iosAssetsFilesVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.channel,sequence=self.sequence,processId=42,
            clockDomain='native-main-assets-files',clockBefore=dict(epochMs=before,monotonicMs=before-EPOCH),
            clockAfter=dict(epochMs=after,monotonicMs=after-EPOCH),source=source)
        if self.mutate:self.mutate(self.packet)
        if self.lost==operation:self.lost=None;raise NativeUIError('Modeled native storage return was lost')

    def source(self):return json.dumps(self.packet)
    def files_native(self):return files.IOSAssetsFiles(self.send,self.source,self.clock,lambda:self.live,42,monotonic=self.monotonic,sleep=self.sleep)


class Fixture:
    def __init__(self,directory):
        self.boundary=Boundary(directory);self.lock=ScriptSourceLock(Path(directory)/'assets.lock');self.lock_guard=self.lock.held();self.lock_guard.__enter__()
        self.file_store=PrivateFeatureState(Path(directory)/'assets-files.json');self.picker_store=PrivateFeatureState(Path(directory)/'assets-picker.json')
        self.files=files.OwnedAssetsFiles(self.boundary.files_native(),self.file_store,BINDING,RUN,URL,lock=self.lock)
        self.input=self.boundary.native_input();self.picker=OwnedAssetsPicker(self.input,self.files,self.picker_store,BINDING,lock=self.lock,
            monotonic=self.boundary.monotonic,sleep=self.boundary.sleep)

    def close(self):self.lock_guard.__exit__(None,None,None);self.boundary.close()
    def start(self):
        self.files.reserve(TICKET);self.files.stage();self.picker.reserve();self.picker.open_page();self.picker.open_picker();self.picker.choose_primary()
    def unavailable(self):self.start();return self.picker.retire_and_select()
