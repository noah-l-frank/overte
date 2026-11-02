"""Literal parent-retained Resource4 originals, never a new current reading."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64,hashlib
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import canonical
from ios.adapters.lifecycle_touch_resource_owner import owner_header,capture_original

VERSION=1

def original(value,binding,run,owner,preparation,*,previous=None):
    exact(value,{'iosLifecycleParentResourceOriginalVersion','ownerInstance','preparationReferenceJson',
        'reference','ownerReference','ownerBase64','captureBase64'})
    need(type(value['iosLifecycleParentResourceOriginalVersion']) is int and value['iosLifecycleParentResourceOriginalVersion']==1
        and value['ownerInstance']==owner and value['preparationReferenceJson']==canonical(preparation).decode('ascii'))
    captures={}
    for kind,key,limit in (('owner','ownerReference',65536),('capture','reference',1048576)):
        reference=value[key];exact(reference,{'index','sha256','bytes','device','inode'})
        need(integer(reference['index'],1,32) and integer(reference['bytes'],2,limit)
            and integer(reference['device'],0,2**64-1) and integer(reference['inode'],1,2**64-1))
        text=value[kind+'Base64'];need(type(text) is str and len(text)<=((limit+2)//3)*4)
        raw=base64.b64decode(text,validate=True)
        need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        body=decode(raw.decode('utf-8'),limit=limit)
        need(canonical(body)+(b'\n' if kind=='owner' else b'')==raw);captures[kind]=body
    need(value['reference']['index']==value['ownerReference']['index'])
    state=owner_header(captures['owner'],binding,run)
    need(state['pending'] is None and state['frames'] and state['frames'][-1]==value['reference'])
    body=captures['capture'];exact(body,{'iosLifecycleTouchResourceFrameVersion','kind','binding','runId','role','index','frame'})
    need(type(body['iosLifecycleTouchResourceFrameVersion']) is int and body['iosLifecycleTouchResourceFrameVersion']==1
        and body['kind']=='sources' and body['binding']==binding and body['runId']==run and body['role']=='primary'
        and type(body['index']) is int and body['index']==value['reference']['index'])
    prior=None if previous is None else original(previous,binding,run,owner,preparation)['capture']
    capture=capture_original(body['frame'],state,prior)
    if previous is not None:need(value['reference']['index']==previous['reference']['index']+1)
    # These exact bytes were received under the original child's FD/Task/source
    # guards. Their parent OriginalFrameStore now supplies historical physical
    # identity. Child owner WAL mutation cannot relabel them as a fresh source.
    return dict(owner=deepcopy(captures['owner']),capture=deepcopy(capture))
