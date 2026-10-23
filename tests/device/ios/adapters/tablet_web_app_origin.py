"""Join actual app input readback, running VM, returned controls and call pins.

This is preparation provenance. It does not establish a Web navigation, input
delivery, echo, inline-document contents, or any cleanup result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact, integer, need
from adapters.native_script_files import NativeScriptFiles
from adapters.native_script_observation import validate as script_original, running_owned_engine, loaded_relative_modules
from adapters.normal_feature_state import context
from ios.adapters import tablet_web_buttons as buttons
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles, originals

VERSION=1
MODULES=['companion.js','script-bundle/companion.js','script-bundle/main.js']


class Frozen:
    def __init__(self,value):self.value=deepcopy(value)
    def read(self):return deepcopy(self.value)
    def write(self,*_args,**_kwargs):need(False)


def call_locations(raw,url):
    """Independent original root-code pins, with UTF-16 V8 column semantics."""
    need(type(raw) is bytes and type(url) is str and url.startswith('file:///'))
    source=raw.decode('utf-8');encoded=source.encode('utf-16le')
    pin=dict(sourceUrlSha256=hashlib.sha256(url.encode()).hexdigest(),sha256=hashlib.sha256(encoded).hexdigest(),codeUnits=len(encoded)//2)
    result=[]
    for token in ('emitScriptEvent(reply)','send(JSON.stringify','respond(message,"tablet",'):
        need(source.count(token)==1);offset=source.index(token);prefix=source[:offset]
        result.append(dict(pin,line=prefix.count('\n')+1,column=len(prefix.rsplit('\n',1)[-1].encode('utf-16le'))//2+1))
    return result


def admitted(owner,file_packet,scripts,button_packet,controls,binding,*,after_epoch):
    """Use originals only; no SDK, native query, filesystem write or selection."""
    binding=context(binding);need(integer(after_epoch,1) and re.fullmatch('[1-9][0-9]*',binding['processIdentity']))
    pid=int(binding['processIdentity']);owned=OwnedTabletWebAppFiles(None,Frozen(owner),binding).owned()
    need(owned['tabletWebAppFilesVersion']==2)
    exact(file_packet,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
    need(type(file_packet['schemaVersion']) is int and file_packet['schemaVersion']==1
        and type(file_packet['requestId']) is str and re.fullmatch('ios-[0-9a-f]{32}',file_packet['requestId'])
        and type(file_packet['instance']) is str and re.fullmatch('[0-9a-f]{32}',file_packet['instance'])
        and integer(file_packet['sequence'],1) and integer(file_packet['processId'],1) and file_packet['processId']==pid
        and file_packet['runId']==owned['runId'] and file_packet['operation']=='observe'
        and integer(file_packet['requestedEpochMs'],after_epoch) and integer(file_packet['capturedEpochMs'],file_packet['requestedEpochMs'])
        and file_packet['capturedEpochMs']-file_packet['requestedEpochMs']<5000)
    readback=file_packet['source'];NativeScriptFiles.validate_source(readback,'observe',owned['runId']);need(readback['exists'])
    raw=originals(owned['featureRun'],owned['fixtureUrl'],owned['ticket'],owned['nonce'])
    need(all(row['exists'] for row in readback['files'])
        and {row['name']:base64.b64decode(row['base64'],validate=True) for row in readback['files']}==raw)
    url=readback['directory']+'/script.js'
    script_original(scripts,scripts['requestId'],pid,scripts['capturedEpochMs'])
    need(type(scripts['requestId']) is str and re.fullmatch('ios-[0-9a-f]{32}',scripts['requestId'])
        and scripts['source'].get('sourceIdentityVersion')==1 and scripts['source'].get('membershipSourceVersion')==1
        and scripts['source']['membership']['complete'])
    engine=running_owned_engine(scripts,url);need(loaded_relative_modules(engine)==MODULES
        and len(engine['required']['modules'])==len(MODULES) and all(row['loaded'] for row in engine['required']['modules']))
    rows=[row for row in scripts['source']['membership']['managers'] if row['instance']==engine['required']['instance']]
    need(len(rows)==1);manager=rows[0];code=engine['code'];pins=call_locations(raw['script.js'],url)
    # An independent same-physical observer may read these exact files after
    # ordinary Script load. Actual submitted root bytes, not disk-read order,
    # identify the running VM. Required-module contents remain unclaimed.
    need(manager['assigned'] and manager['url']==url and after_epoch<=manager['assignedEpochMs']<=code['submittedEpochMs']
        and file_packet['capturedEpochMs']<=scripts['capturedEpochMs']
        and code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==pins[0]['codeUnits'] and code['sha256']==pins[0]['sha256']
        and all(code['submittedEpochMs']<=row['capturedEpochMs'] for row in engine['required']['modules']))
    profile=dict(engineInstance=manager['instance'],assignedUrl=url,loadGeneration=manager['loadGeneration'],assignedEpochMs=manager['assignedEpochMs'],code=deepcopy(code))
    buttons.original(button_packet)
    need(button_packet['processId']==pid and button_packet['runId']==owned['featureRun'] and button_packet['fixtureUrl']==owned['fixtureUrl']
        and scripts['capturedEpochMs']<=button_packet['clockAfter']['epochMs'] and type(controls) is dict and set(controls)=={'open','inline','return'})
    chosen={}
    for verb,control in controls.items():
        need(control['verb']==verb and control['nonce']==owned['nonce'])
        chosen[verb]=buttons.selected(button_packet,control,profile)
    expected={row['id'] for row in chosen.values()}
    actual={row['id'] for row in button_packet['buttons'] if buttons.SEMANTIC.fullmatch(row['semanticId'])[2]==owned['nonce']}
    need(len(expected)==3 and actual==expected)
    return dict(iosTabletWebAppOriginVersion=VERSION,profile=deepcopy(profile),locations=pins,manager=deepcopy(manager),controls=deepcopy(controls),storageRun=owned['runId'])
