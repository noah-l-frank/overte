"""Original QML review/upload callbacks with explicit Qt/native/wire models.

Real host input files feed the original QML functions. Independently serialized
read replies see bytes published by the modeled service after reading those
files, never bytes supplied by the owner or its expected bundle. No AssetServer,
Qt, native C++, installed candidate, compiler or device runs in this fixture.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
import weakref
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import assets_bundle_controls as controls
from ios.adapters.assets_controls import SUFFIXES
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.self_tests import assets_picker_fixture as picker
from ios.self_tests import assets_reply_fixture as replies
from self_tests.test_native_feature_observation import Boundary as ClockBoundary

RUN,TICKET,URL,BINDING=picker.RUN,picker.TICKET,picker.URL,picker.BINDING


def manifest(value):
    if value is None:return None
    return {key:deepcopy(value[key]) for key in ('root','urls','relativePaths','primaryIndex','primaryPath')}


class Boundary(picker.Boundary):
    def __init__(self,directory):
        self.bundle_sequence=0;self.bundle_instance=picker.uid();self.destination=picker.uid();self.events_seen=0;self.consumers={}
        self.reads=replies.Boundary();self.reads.data.clear()
        super().__init__(directory)
        # Both modeled producers independently stamp their newly produced
        # originals from this fixture clock; no retained reply is rewritten.
        self.reads.clock=self.clock;self.reads.tick=self.tick;self.reads.monotonic=self.monotonic;self.reads.sleep=self.sleep
        self.reads.stamp=lambda:dict(epochMs=self.clock(),monotonicMs=self.elapsed+5000)
        self.configure(allowBundleUploads=True)
        self.native_clock=ClockBoundary();self.native_clock.mutate=self.clock_original
        self.clock_reader=NativeFeatureObservation(self.native_clock.send,self.native_clock.original,self.clock,lambda:True,42,
            ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def clock_original(self,value):
        # This function is the declared clock producer, invoked only during
        # construction of a fresh original, not after observation acquisition.
        def stamp(node):
            if type(node) is dict:
                for key,child in node.items():
                    if key.endswith('EpochMs'):node[key]=self.clock()
                    else:stamp(child)
            elif type(node) is list:
                for child in node:stamp(child)
        stamp(value);value['processId']=42

    def exchange(self,value):
        result=super().exchange(value)
        events=result.get('bundleInfo',{}).get('serviceEvents',[])
        for event in events[self.events_seen:]:
            if event['kind']=='started':
                holder=picker.Consumer();self.consumers[event['id']]=holder
                self.jobs.append(dict(weak=weakref.ref(holder),row=dict(id=event['id'],kind='bundle',files=event['files'],created=self.stamp(),
                    alive=True,terminal=False,ended=None,expired=None,entered=0,returned=0,pendingBodies=0)))
                for file in event['files']:
                    upload=picker.Consumer();identity=picker.uid();self.consumers[identity]=upload
                    self.jobs.append(dict(weak=weakref.ref(upload),bundle=event['id'],row=dict(id=identity,kind='upload',files=[file],created=self.stamp(),
                        alive=True,terminal=False,ended=None,expired=None,entered=0,returned=0,pendingBodies=0)))
            elif event['kind']=='completion-entered':
                job=next(row for row in self.jobs if row['row']['id']==event['id']);job['row'].update(terminal=True,ended=self.stamp(),entered=1,pendingBodies=1)
                for row in event['actual']:self.reads.data[row['path']]=base64.b64decode(row['base64'],validate=True)
            elif event['kind']=='completion-returned':
                for job in self.jobs:
                    if job['row']['id']==event['id']:job['row'].update(returned=1,pendingBodies=0)
                    if job['row']['id']==event['id'] or job.get('bundle')==event['id']:self.consumers.pop(job['row']['id'],None)
        self.events_seen=len(events);return result

    def control_metadata(self,identifier,item,role):
        if identifier not in controls.IDS:return super().control_metadata(identifier,item,role)
        data=self.host_state['bundleInfo'];actual=manifest(data[role])
        return controls.metadata(dict(assetControlVersion=2,role=role,rootId=self.picker if role=='picker' else self.page,windowId=self.window,
            componentSource='qrc:'+SUFFIXES[role],controlId=identifier,ownerRootId=self.page,bundle=actual,fieldText=item.get('fieldText',''),
            destinationText='' if role=='picker' else data['destinationText'],
            choiceIndex=actual['primaryIndex'] if role=='picker' else -1,choiceCount=len(actual['urls']) if role=='picker' else 0,
            destinationId=None if role=='picker' else self.destination))

    def extensions(self,ui):
        self.bundle_sequence+=1;data=self.host_state['bundleInfo'];rows=[]
        for old in ui['roots']:
            if not old['alive']:continue
            role=old['role'];row=dict(rootId=old['rootId'],ownerRootId=self.page,role=role,bundle=manifest(data[role]))
            if role=='page':row.update(destinationId=self.destination,destinationVisible=data['destinationVisible'],
                destinationText=data['destinationText'],uploadedPrimaryUrl=data['uploadedPrimaryUrl'])
            rows.append(row)
        return dict(assetBundleControlsVersion=1,assetBundleInventory=dict(iosAssetsBundleUiVersion=1,instance=self.bundle_instance,
            sequence=self.bundle_sequence,processId=42,capturedEpochMs=self.clock(),available=True,complete=True,rows=rows))


class Fixture:
    def __init__(self,directory):
        self.boundary=Boundary(directory);self.lock=ScriptSourceLock(Path(directory)/'assets.lock');self.guard=self.lock.held();self.guard.__enter__()
        self.file_store=PrivateFeatureState(Path(directory)/'assets-files.json');self.picker_store=PrivateFeatureState(Path(directory)/'assets-picker.json')
        self.upload_store=PrivateFeatureState(Path(directory)/'assets-upload.json');self.reply_store=PrivateFeatureState(Path(directory)/'assets-replies.json')
        self.files=OwnedAssetsFiles(self.boundary.files_native(),self.file_store,BINDING,RUN,URL,lock=self.lock)
        self.input=self.boundary.native_input();self.picker=OwnedAssetsPicker(self.input,self.files,self.picker_store,BINDING,lock=self.lock,
            monotonic=self.boundary.monotonic,sleep=self.boundary.sleep)
        self.replies=OwnedAssetsReplyReads(self.boundary.reads.native(),self.reply_store,BINDING,RUN,URL,lock=self.lock)

    def close(self):self.guard.__exit__(None,None,None);self.boundary.close()

    def start(self):
        self.files.reserve(TICKET);self.files.stage();self.picker.reserve();self.picker.open_page();self.picker.open_picker();self.picker.choose_primary()
        self.replies.reserve(TICKET)

    def owner(self):
        from ios.adapters.assets_upload import OwnedAssetsUpload
        return OwnedAssetsUpload(self.input,self.boundary.clock_reader,self.files,self.picker,self.replies,self.upload_store,BINDING,
            lock=self.lock,monotonic=self.boundary.monotonic,sleep=self.boundary.sleep)
