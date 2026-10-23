"""Durable private Assets INPUT leases; product consumer retirement is separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import secrets
import base64
from adapters.assets_input import documents,PREFIX,manifest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.pico4.assets_files import NativeAssetsFiles
from adapters.script_journey.history import pack,unpack,same
from feature_journeys.contract import identifier

PHASES=('reserved','stage-issuing','ready','primary-issuing','primary-retired','retiring','retired')


class OwnedAssetsFiles:
    def __init__(self,native,store,binding,run,ticket,fixture_url):
        need(isinstance(native,NativeAssetsFiles))
        self.native,self.store,self.binding=native,store,deepcopy(context(binding))
        self.run,self.ticket,self.url=identifier(run),identifier(ticket),fixture_url
        for resource in PREFIX:manifest(run,ticket,fixture_url,resource)
        self.inputs=documents();self.previous=store.read()
        self.state=dict(assetsFileOwnerVersion=1,binding=self.binding,runId=run,inputTicket=ticket,
            fixtureUrl=fixture_url,ownerToken=secrets.token_hex(32),stage=native.stage,phase='reserved',originals=pack([]))
        if self.previous is not None:
            value=deepcopy(self.previous)
            exact(value,set(self.state));need(type(value['assetsFileOwnerVersion']) is int and value['assetsFileOwnerVersion']==1
                and context(value['binding'])==self.binding and value['runId']==run and value['inputTicket']==ticket
                and value['fixtureUrl']==fixture_url and value['stage']==native.stage and value['phase'] in PHASES
                and type(value['ownerToken']) is str and len(value['ownerToken'])==64
                and all(ch in '0123456789abcdef' for ch in value['ownerToken']))
            self.state=value;native.restore(unpack(value['originals']))
            self.validate_history()

    def validate_history(self):
        files={};dirs={};root=None
        for original in self.native.history:
            call=original['command'];need(call['runId']==self.run and call['ownerToken']==self.state['ownerToken'])
            if call['operation']=='stage':need(call['files']=={name:base64.b64encode(raw).decode() for name,raw in self.inputs.items()})
            from adapters.native_feature_observation import decode
            actual=decode(original['raw'])['source']
            if actual['exists']:
                identity=actual['rootIdentity'];current=(identity['device'],identity['inode'])
                need(root in (None,current));root=current
                for row in actual['files']:
                    if not row['exists']:continue
                    raw=self.inputs[row['name']]
                    need(row['bytes']==len(raw) and row['sha256']==hashlib.sha256(raw).hexdigest())
                    if row['name'] in files:need(same(files[row['name']],row))
                    else:files[row['name']]=deepcopy(row)
                for row in actual['directories']:
                    current=(row['identity']['device'],row['identity']['inode'])
                    need(row['name'] not in dirs or dirs[row['name']]==current);dirs[row['name']]=current

    def save(self,phase=None):
        need(self.store.read()==self.previous)
        value=deepcopy(self.state);value['originals']=pack(self.native.history)
        if phase is not None:need(phase in PHASES);value['phase']=phase
        self.store.write(value,self.previous);self.previous=deepcopy(value);self.state=value
        return deepcopy(value)

    def read(self,operation='observe',files=None):
        need(self.previous is not None and self.store.read()==self.previous)
        result=self.native.request(operation,self.run,self.state['ownerToken'],files)
        self.validate_history();self.save();return result

    def prepare(self):
        if self.previous is None:self.save()
        need(self.state['phase'] in ('reserved','stage-issuing','ready'))
        if self.state['phase']=='reserved':
            actual=self.read()['source'];need(not actual['exists'] and not actual['retired'])
            self.save('stage-issuing');self.read('stage',self.inputs)
        # After lost stage reply only observe the original in-process lease.
        actual=self.read()['source'];need(actual['exists'] and not actual['retiring'] and not actual['retired']
            and not actual['primaryRetired'] and all(row['exists'] for row in actual['files']))
        self.save('ready');return actual['directory']

    def retire_primary(self):
        need(self.state['phase'] in ('ready','primary-issuing','primary-retired'))
        if self.state['phase']=='ready':
            actual=self.read()['source'];need(actual['exists'] and not actual['primaryRetired'])
            self.save('primary-issuing');self.read('retire-primary')
        actual=self.read()['source'];need(actual['exists'] and actual['primaryRetired'] and not actual['retiring'])
        self.save('primary-retired');return deepcopy(actual)

    def release(self,consumer_retirement):
        # The composed owner supplies fresh original QObject/file consumer proof.
        # Hidden UI, an ACK, or requested cleanup never authorizes an unlink.
        need(callable(consumer_retirement) and consumer_retirement() is True)
        if self.previous is None:self.save()
        if self.state['phase']=='retired':
            actual=self.read()['source'];need(actual['retired'] and not actual['exists']);return actual
        self.save('retiring');need(consumer_retirement() is True)
        self.read('release');actual=self.read()['source'];need(actual['retired'] and not actual['exists'])
        need(consumer_retirement() is True);self.save('retired');return deepcopy(actual)
