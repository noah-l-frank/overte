"""Durable process/run-bound responsibility for actual Create fixture/output files.

This owner never opens a product dialog or writes selection.json. The public
coordinator must issue ordinary inputs separately and retain the final original
file transcript before this component's journal can be retired.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import secrets

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import identifier
from overte_phone_create_fixture import documents,NAMES
from overte_phone_create_files import PhoneCreateFiles,source
from overte_phone_script_history import pack,unpack,same,canonical

VERSION=1
MAX_ORIGINALS=128


class OwnedCreateFiles:
    INPUT_NAMES=NAMES
    def __init__(self,native,store,binding,run,ticket,fixture_url):
        need(isinstance(native,PhoneCreateFiles) and isinstance(store,PrivateFeatureState))
        self.native,self.store,self.binding=native,store,deepcopy(context(binding))
        self.run,self.ticket,self.url=identifier(run),identifier(ticket),fixture_url
        self.inputs=documents(run,ticket,fixture_url)
        self.previous=store.read();self.frames=[]
        self.state=dict(createFileOwnerVersion=VERSION,binding=self.binding,runId=run,inputTicket=ticket,
            fixtureUrl=fixture_url,ownerToken=secrets.token_hex(32),phase='reserved',originals=pack([]),export=None)
        if self.previous is not None:
            value=deepcopy(self.previous)
            exact(value,{'createFileOwnerVersion','binding','runId','inputTicket','fixtureUrl','ownerToken','phase','originals','export'})
            need(type(value['createFileOwnerVersion']) is int and value['createFileOwnerVersion']==VERSION
                 and context(value['binding'])==self.binding and value['runId']==run and value['inputTicket']==ticket
                 and value['fixtureUrl']==fixture_url and type(value['ownerToken']) is str
                 and len(value['ownerToken'])==64 and all(ch in '0123456789abcdef' for ch in value['ownerToken'])
                 and value['phase'] in ('reserved','stage-issuing','ready','export-pending','export-sealing','exported','retiring','retired'))
            self.frames=unpack(value['originals']);need(len(self.frames)<=MAX_ORIGINALS)
            for frame in self.frames:self.validate_original(frame)
            for before,after in zip(self.frames,self.frames[1:]):
                need(after['instance']==before['instance'] and after['sequence']>before['sequence']
                     and after['capturedEpochMs']>=before['capturedEpochMs'])
            self.state=value
            if self.frames:
                need(native.last is None);native.last=deepcopy(self.frames[-1])
            if value['export'] is not None:self.validate_output(value['export'])

    def validate_original(self,value):
        exact(value,{'schemaVersion','requestId','runId','operation','instance','sequence','processId',
                     'requestedEpochMs','capturedEpochMs','source'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run
             and value['operation'] in ('stage','observe','seal-export','release') and integer(value['processId'],1)
             and value['processId']==self.native.pid and integer(value['sequence'],1)
             and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
             and value['capturedEpochMs']-value['requestedEpochMs']<5000)
        identifier(value['requestId']);identifier(value['instance']);source(value['source'],self.run)
        return value

    @staticmethod
    def validate_output(row):
        exact(row,{'name','exists','identity','bytes','sha256','base64'})
        need(row['name']=='selection.json' and row['exists'] is True)
        # Reuse the exact original source reader, without presenting historical
        # capture times as fresh. The complete stored output row is retained.
        from overte_phone_create_files import identity
        identity(row['identity'])
        raw=base64.b64decode(row['base64'],validate=True)
        need(integer(row['bytes'],1,65536) and len(raw)==row['bytes'] and int(row['identity']['size'])==len(raw)
             and base64.b64encode(raw).decode()==row['base64'] and hashlib.sha256(raw).hexdigest()==row['sha256'])
        return row

    def save(self,**changes):
        value=self.state|changes|dict(originals=pack(self.frames));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.state=self.previous=deepcopy(value)

    def reserve(self):
        if self.previous is None:self.save()
        need(self.state['phase']=='reserved')

    def validate_input_row(self,row):
        need(base64.b64decode(row['base64'],validate=True)==self.inputs[row['name']])

    def read(self,operation='observe',files=None):
        need(self.previous is not None and same(self.store.read(),self.previous) and len(self.frames)<MAX_ORIGINALS)
        value=self.native.request(operation,self.run,self.state['ownerToken'],files)
        self.validate_original(value)
        if self.frames:
            previous=self.frames[-1]
            need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
                 and value['capturedEpochMs']>=previous['capturedEpochMs'])
        actual=value['source']
        if actual['exists']:
            prior=next((frame['source']['rootIdentity'] for frame in self.frames if frame['source']['exists']),None)
            if prior is not None:need(all(prior[key]==actual['rootIdentity'][key] for key in ('device','inode')))
            for row in actual['files']:
                if row['name'] in self.INPUT_NAMES and row['exists']:
                    self.validate_input_row(row)
                    previous=next((old for frame in self.frames if frame['source']['exists'] for old in frame['source']['files']
                                   if old['name']==row['name'] and old['exists']),None)
                    if previous is not None:need(same(previous,row))
                if row['name']=='selection.json' and row['exists'] and self.state['export'] is not None:
                    need(same(row,self.state['export']))
        self.frames.append(deepcopy(value));self.save();return deepcopy(value)

    def prepare(self):
        if self.previous is None:self.reserve()
        phase=self.state['phase']
        need(phase in ('reserved','stage-issuing','ready'))
        if phase=='reserved':
            before=self.read();need(not before['source']['exists'] and not before['source']['retired'])
            self.save(phase='stage-issuing') # Persist before the only stage send.
            self.read('stage',self.inputs)
        # An interrupted stage is reconciled from actual originals. Absent or
        # partial input is retained/red; it never authorizes another stage send.
        value=self.read();actual=value['source']
        need(actual['exists'] and not actual['retired'] and not actual['retiring'] and not actual['exportSealed'])
        rows={row['name']:row for row in actual['files']}
        need(all(rows[name]['exists'] for name in NAMES) and not rows['selection.json']['exists'])
        self.save(phase='ready');return actual['directory']

    def begin_export(self):
        need(self.state['phase']=='ready')
        value=self.read();need(value['source']['exists'] and not value['source']['retiring'])
        need(not next(row for row in value['source']['files'] if row['name']=='selection.json')['exists'])
        self.save(phase='export-pending')
        return value['source']['directory']+'/selection.json'

    def finish_export(self):
        need(self.state['phase'] in ('export-pending','export-sealing','exported'))
        value=self.read();actual=value['source'];need(actual['exists'] and not actual['retiring'])
        row=next(row for row in actual['files'] if row['name']=='selection.json');self.validate_output(row)
        if self.state['export'] is None:self.save(phase='export-sealing',export=deepcopy(row))
        else:need(same(self.state['export'],row))
        if not actual['exportSealed']:
            self.read('seal-export') # Native seals the original observed inode/bytes.
        final=self.read();need(final['source']['exists'] and final['source']['exportSealed'])
        self.save(phase='exported');return base64.b64decode(self.state['export']['base64'],validate=True)

    def cleanup(self):
        if self.previous is None:self.reserve()
        value=self.read();actual=value['source']
        if actual['exists']:
            output=next(row for row in actual['files'] if row['name']=='selection.json')
            if output['exists']:
                need(self.state['phase'] in ('export-pending','export-sealing','exported','retiring'))
                self.validate_output(output)
                if self.state['export'] is None:self.save(export=deepcopy(output))
                else:need(same(output,self.state['export']))
                if not actual['exportSealed']:self.read('seal-export')
        self.save(phase='retiring')
        if not actual['retired']:self.read('release')
        final=self.read();need(final['source']['retired'] and not final['source']['exists'])
        self.save(phase='retired');return deepcopy(self.previous)

    def retire(self,retain):
        need(callable(retain) and self.state['phase']=='retired' and same(self.store.read(),self.previous))
        # Obtain another actual native absence before transferring the exact
        # final transcript. An ignored host unlink never yields green success.
        final=self.read();need(final['source']['retired'] and not final['source']['exists'])
        original=deepcopy(self.previous);digest=hashlib.sha256(canonical(original)).hexdigest()
        need(retain(deepcopy(original))==digest and same(self.store.read(),original))
        self.store.discard(original);need(self.store.read() is None);self.previous=None
        return original
