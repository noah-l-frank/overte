"""Original normal Snapshot widgets over the existing private Qt transport.

An input receipt proves delivery only. Capture, Save, Share and Upload require
their separate original native/file/provider/receiver observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_script_files import PhoneScriptFileIO,nonce
from overte_phone_snapshot_source import ROOTS

FILE='phone-snapshot-ui.json'


def control_id(value):
    return type(value) is str and (value in ('snapshot.entry','snapshot.page','snapshot.name','snapshot.mode','snapshot.format',
        'snapshot.capture','snapshot.cancel-capture','snapshot.cancel-upload','snapshot.cancel-export','snapshot.scrollbar','tablet.home')
        or re.fullmatch(r'(?:tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])|snapshot\.(?:save|share|upload)\.[0-9a-f]{64})',value) is not None)


def original_path(value):
    return type(value) is str and len(value)<=2048 and all(ord(ch)>=32 for ch in value) and any(
        value.startswith(root+'/') and '/' not in value[len(root)+1:] and value[len(root)+1:] not in ('','.','..')
        and '\\' not in value for root in ROOTS)


def metadata(row):
    base={'id','token','enabled','focused','inputReady'}
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token'))
        and all(type(row.get(key)) is bool for key in ('enabled','focused','inputReady')))
    id=row['id']
    if id=='snapshot.page':
        exact(row,base|{'profile','component','capturing','processing','captureSettingsLoaded','statusError','statusText','exportTicket','uploadPath'})
        url=urlsplit(row['component']);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
            and url.path.endswith('/system/snapshot/NativeSnapshotReview.qml') and row['profile']=='native-snapshot-review-v1'
            and all(type(row[key]) is bool for key in ('capturing','processing','captureSettingsLoaded','statusError'))
            and (not row['processing'] or row['capturing']) and row['inputReady'] is False
            and type(row['statusText']) is str and len(row['statusText'])<=2048
            and type(row['exportTicket']) is str and len(row['exportTicket'])<=64
            and (row['uploadPath']=='' or original_path(row['uploadPath'])))
    elif id=='snapshot.name':exact(row,base|{'text'});need(type(row['text']) is str and len(row['text'])<=48)
    elif id in ('snapshot.mode','snapshot.format'):
        exact(row,base|{'currentIndex','count','currentText','options'})
        need(integer(row['count'],1,8) and (id!='snapshot.mode' or row['count']==4) and integer(row['currentIndex'],0,row['count']-1)
            and type(row['options']) is list and len(row['options'])==row['count'] and len(set(row['options']))==row['count']
            and all(type(option) is str and 0<len(option)<=128 for option in row['options'])
            and row['currentText']==row['options'][row['currentIndex']])
        if id=='snapshot.format':need(all(option in ('png','jpg','jpeg','webp') for option in row['options']))
    elif id=='snapshot.scrollbar':
        exact(row,base|{'position','size'});need(number(row['position'],0,1) and number(row['size'],0,1))
    elif re.fullmatch(r'snapshot\.(save|share|upload)\.[0-9a-f]{64}',id):
        exact(row,base|{'path'});need(original_path(row['path']) and id.rsplit('.',1)[1]==hashlib.sha256(row['path'].encode()).hexdigest())
    else:exact(row,base)
    return row


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence','lastCommandSequence',
        'elapsedMs','capturedEpochMs','processId','snapshotControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command and value['action']=='observe'
        and nonce(value['instance']) and nonce(value['generation']) and integer(value['sourceSequence'],1)
        and integer(value['lastCommandSequence']) and integer(value['elapsedMs']) and integer(value['processId'],1) and value['processId']==pid
        and type(value['snapshotControlsVersion']) is int and value['snapshotControlsVersion']==1 and type(value['ready']) is bool
        and type(value['controls']) is list and len(value['controls'])<=128)
    fresh(value['capturedEpochMs'],epoch);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls']);return value


class PhoneSnapshotIO(PhoneScriptFileIO):
    wire_action='phone-snapshot-ui'
    validate_capture=staticmethod(validate)

    def __init__(self,*args,intent,**kwargs):
        need(callable(intent));self.intent=intent;super().__init__(*args,**kwargs)

    def input(self,id,action,*,reference,value=None):
        try:
            need(control_id(id) and id!='snapshot.page' and action in ('activate','replace','select-index','scroll'))
            if action=='replace':need(id=='snapshot.name' and type(value) is str and len(value)<=48 and all(32<=ord(ch)<=126 for ch in value))
            elif action=='select-index':need(id in ('snapshot.mode','snapshot.format') and integer(value,0,7))
            elif action=='scroll':need(id=='snapshot.scrollbar' and value in ('up','down'))
            else:need(value is None and id!='snapshot.scrollbar')
            validate(reference,reference['commandId'],self.pid,self.clock_ms());current=self.capture()
            need(all(current[key]==reference[key] for key in ('instance','generation','lastCommandSequence','processId'))
                and current['sourceSequence']>reference['sourceSequence'] and 0<=current['elapsedMs']-reference['elapsedMs']<=5000)
            before=[row for row in reference['controls'] if row['id']==id];after=[row for row in current['controls'] if row['id']==id]
            need(len(before)==len(after)==1 and before[0]==after[0] and current['ready'] and after[0]['enabled'] and after[0]['inputReady'])
            if action=='replace':need(after[0]['focused'])
            if action=='select-index':need(value<after[0]['count'])
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=reference['instance'],
                generation=reference['generation'],sequence=reference['lastCommandSequence']+1,observedElapsedMs=reference['elapsedMs'],
                controlId=id,controlToken=before[0]['token'])
            if action=='replace':request['text']=value
            elif action=='select-index':request['index']=value
            elif action=='scroll':request['direction']=value
            need(self.intent(dict(request=deepcopy(request),original=deepcopy(reference))) is not False)
            self.deliver(request,reference)
        except Exception:raise NativeUIError('Phone original Snapshot input delivery failed') from None

    def activate(self,id,*,reference):return self.input(id,'activate',reference=reference)
    def replace(self,id,value,*,reference):return self.input(id,'replace',reference=reference,value=value)
    def select_index(self,id,value,*,reference):return self.input(id,'select-index',reference=reference,value=value)
    def scroll(self,id,value,*,reference):return self.input(id,'scroll',reference=reference,value=value)
