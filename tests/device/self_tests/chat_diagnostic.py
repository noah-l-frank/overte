"""Private lossless host diagnostics; never original live-source admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import base64
import hashlib
import re

from adapters.chat_journey.source_bundles import prepare,original,logical_bytes
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same


def write(directory,name,value):
    need(type(name) is str and re.fullmatch('[a-z][a-z0-9-]*',name))
    store=PrivateFeatureState(Path(directory)/(name+'.json'))
    need(store.read() is None)
    scope=dict(chatHostDiagnosticVersion=1,scope='host-diagnostic-not-source-admission',name=name)
    history=ChatSourceChunks(store,scope);history.inventory(0)
    ref,parts=prepare(value,0,[]);previous=None;manifest=[]
    def save(phase):
        nonlocal previous
        current={**scope,'phase':phase,'bundles':[ref],'logicalBytes':logical_bytes([ref]),'chunks':manifest}
        store.write(current,previous);need(same(store.read(),current));previous=current
    save('reading')
    for part in parts:
        manifest=history.append(part,manifest);save('reading')
    decoded,_raw=original(history,manifest,[ref],0);need(same(decoded,value));save('complete')
    return store


def read(store):
    need(type(store) is PrivateFeatureState);root=store.read()
    exact(root,{'chatHostDiagnosticVersion','scope','name','phase','bundles','logicalBytes','chunks'})
    need(type(root['chatHostDiagnosticVersion']) is int and root['chatHostDiagnosticVersion']==1
        and root['scope']=='host-diagnostic-not-source-admission' and root['phase']=='complete'
        and type(root['name']) is str and re.fullmatch('[a-z][a-z0-9-]*',root['name'])
        and store.path.name==root['name']+'.json' and type(root['logicalBytes']) is int
        and type(root['bundles']) is list and len(root['bundles'])==1
        and root['logicalBytes']==logical_bytes(root['bundles']))
    scope={key:root[key] for key in ('chatHostDiagnosticVersion','scope','name')}
    history=ChatSourceChunks(store,scope);history.load(root['chunks'])
    value,raw=original(history,root['chunks'],root['bundles'],0)
    need(same(store.read(),root));return value,raw


def exception(error):
    """Keep suppressed original contexts and actual unpublished pack inputs."""
    contexts=[];seen=set();current=error
    while current is not None and id(current) not in seen:
        seen.add(id(current));frames=[];tb=current.__traceback__
        while tb is not None:
            frame=tb.tb_frame;code=frame.f_code
            row=dict(file=code.co_filename,line=tb.tb_lineno,function=code.co_name)
            if code.co_name=='pack' and code.co_filename.endswith('/adapters/script_journey/history.py'):
                raw=frame.f_locals.get('raw');encoded=frame.f_locals.get('encoded')
                if type(raw) is bytes:
                    row['failedPackInput']=dict(scope='unpublished-original-pack-input',committedSourceSample=False,
                        rawBase64=base64.b64encode(raw).decode('ascii'),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                        encodedBytes=len(encoded) if type(encoded) is str else None)
            frames.append(row);tb=tb.tb_next
        contexts.append(dict(type=type(current).__name__,message=str(current),frames=frames))
        current=current.__cause__ if current.__cause__ is not None else current.__context__
    return dict(scope='original-exception-contexts-not-source-admission',contexts=contexts)
