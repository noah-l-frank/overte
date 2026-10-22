"""Durable actual private Assets inputs, reusing the existing file owner journal.

Normal browser selection/upload is separate. Input bytes are pinned fixtures;
none of this component's return values supplies a mapping or bake verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import hashlib
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import identifier
from overte_phone_assets_files import PhoneAssetsFiles,source
from overte_phone_assets_fixture import documents,NAMES,PREFIX,manifest
from overte_phone_create_file_owner import OwnedCreateFiles,MAX_ORIGINALS
from overte_phone_script_history import pack,unpack,same


class OwnedAssetsFiles(OwnedCreateFiles):
    INPUT_NAMES=NAMES
    def __init__(self,native,store,binding,run,ticket,fixture_url):
        need(isinstance(native,PhoneAssetsFiles) and isinstance(store,PrivateFeatureState))
        self.native,self.store,self.binding=native,store,deepcopy(context(binding))
        self.run,self.ticket,self.url=identifier(run),identifier(ticket),fixture_url
        for resource in PREFIX:manifest(run,ticket,fixture_url,resource)
        self.inputs=documents();self.previous=store.read();self.frames=[]
        self.state=dict(assetsFileOwnerVersion=1,binding=self.binding,runId=run,inputTicket=ticket,fixtureUrl=fixture_url,
            ownerToken=secrets.token_hex(32),phase='reserved',originals=pack([]))
        if self.previous is not None:
            value=deepcopy(self.previous)
            exact(value,{'assetsFileOwnerVersion','binding','runId','inputTicket','fixtureUrl','ownerToken','phase','originals'})
            need(type(value['assetsFileOwnerVersion']) is int and value['assetsFileOwnerVersion']==1 and context(value['binding'])==self.binding
                and value['runId']==run and value['inputTicket']==ticket and value['fixtureUrl']==fixture_url
                and type(value['ownerToken']) is str and len(value['ownerToken'])==64 and all(ch in '0123456789abcdef' for ch in value['ownerToken'])
                and value['phase'] in ('reserved','stage-issuing','ready','primary-issuing','primary-retired','retiring','retired'))
            frames=unpack(value['originals']);need(len(frames)<=MAX_ORIGINALS)
            for frame in frames:
                self.validate_original(frame)
                if self.frames:
                    before=self.frames[-1];need(frame['instance']==before['instance'] and frame['sequence']>before['sequence'] and frame['capturedEpochMs']>=before['capturedEpochMs'])
                self.frames.append(deepcopy(frame))
            self.state=value
            if self.frames:need(native.last is None);native.last=deepcopy(self.frames[-1])

    def validate_original(self,value):
        exact(value,{'schemaVersion','requestId','runId','operation','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run
            and value['operation'] in ('stage','observe','retire-primary','release') and integer(value['processId'],1) and value['processId']==self.native.pid
            and integer(value['sequence'],1) and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
            and value['capturedEpochMs']-value['requestedEpochMs']<5000)
        identifier(value['requestId']);identifier(value['instance']);actual=source(value['source'],self.run)
        if actual['exists']:
            for row in actual['files']:
                if row['exists']:
                    self.validate_input_row(row)
                    previous=next((old for frame in self.frames if frame['source']['exists'] for old in frame['source']['files'] if old['name']==row['name'] and old['exists']),None)
                    if previous is not None:need(same(previous,row))
            for row in actual['directories']:
                previous=next((old for frame in self.frames if frame['source']['exists'] for old in frame['source']['directories'] if old['name']==row['name']),None)
                if previous is not None:need(all(previous['identity'][key]==row['identity'][key] for key in ('device','inode')))
        return value

    def validate_input_row(self,row):
        original=self.inputs[row['name']]
        need(row['bytes']==len(original) and row['sha256']==hashlib.sha256(original).hexdigest())

    def prepare(self):
        if self.previous is None:self.reserve()
        need(self.state['phase'] in ('reserved','stage-issuing','ready'))
        if self.state['phase']=='reserved':
            before=self.read();need(not before['source']['exists'] and not before['source']['retired'])
            self.save(phase='stage-issuing');self.read('stage',self.inputs)
        value=self.read();actual=value['source']
        need(actual['exists'] and not actual['retiring'] and not actual['retired'] and not actual['primaryRetired']
            and all(row['exists'] for row in actual['files']))
        self.save(phase='ready');return actual['directory']

    def retire_primary(self):
        need(self.state['phase'] in ('ready','primary-issuing','primary-retired'))
        if self.state['phase']=='ready':
            before=self.read();need(before['source']['exists'] and not before['source']['primaryRetired'])
            self.save(phase='primary-issuing');self.read('retire-primary')
        actual=self.read()['source'];need(actual['exists'] and actual['primaryRetired'] and not actual['retiring'])
        self.save(phase='primary-retired');return deepcopy(self.previous)

    def cleanup(self):
        if self.previous is None:self.reserve()
        self.save(phase='retiring')
        # Native cleanup proves its exact known directory/inodes itself. This
        # also permits honest cleanup after an incomplete stage/read failure.
        self.read('release');actual=self.read()['source'];need(actual['retired'] and not actual['exists'])
        self.save(phase='retired');return deepcopy(self.previous)
