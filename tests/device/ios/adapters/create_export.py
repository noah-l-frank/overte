"""Join actual native export bytes to the selected, rendered owned Model.

The ordinary product writes the export. This module never generates, repairs
or rewrites its bytes. Staged entity JSON and exported JSON remain distinct
original files; absence before the normal Save is a required original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib

from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.contract import json_document
from ios.adapters import create_files,create_state
from ios.adapters.create_product_state import model_texture,selected

VERSION=1


def exported(baseline,current,model_original,owned_id,*,after_native):
    """`baseline/current` retain the exact native query and returned carrier."""
    previous=None
    for original in (baseline,current):
        need(type(original) is dict and set(original)=={'query','packet'})
        query,packet=original['query'],original['packet']
        need(query['operation']=='observe')
        create_files.validate(packet,query,model_original['processId'],previous=previous)
        previous=packet
    first,last=baseline['packet'],current['packet'];query=current['query']
    need(first['runId']==last['runId']==model_original['runId'] and baseline['query']['ownerToken']==query['ownerToken']
         and first['source']['exists'] and last['source']['exists']
         and first['source']['directory']==last['source']['directory']
         and first['source']['files'][1]==dict(name='export.json',exists=False)
         and same(first['source']['files'][0],last['source']['files'][0])
         and type(after_native) is int and after_native>=first['clockAfter']['epochMs']
         and last['clockBefore']['epochMs']>=after_native
         and abs(last['clockAfter']['epochMs']-model_original['clockAfter']['epochMs'])<=1500)
    source=create_state.live(model_original)
    need(selected(source)==[owned_id]);rows=[row for row in source['entities'] if row['id']==owned_id]
    need(len(rows)==1);model=rows[0]
    need(model['type']=='Model' and model['hostType']=='domain' and model['lastEditedBy']==source['localSessionId']
         and not model['locked'] and model['visible'] and model_texture(model))
    row=last['source']['files'][1];need(row['exists'])
    need((row['identity']['device'],row['identity']['inode'])!=(last['source']['files'][0]['identity']['device'],last['source']['files'][0]['identity']['inode']))
    raw=create_files.original_bytes(row['base64'],65536);parsed=json_document(raw)
    need(type(parsed) is dict and type(parsed.get('DataVersion')) is int and parsed['DataVersion']==0
         and type(parsed.get('Entities')) is list and len(parsed['Entities'])==1)
    entity=parsed['Entities'][0];need(type(entity) is dict)
    need(all(entity.get(key)==model[key] for key in ('name','type','modelURL')))
    dimensions=entity.get('dimensions');need(type(dimensions) is dict and set(dimensions)==set('xyz')
        and all(type(dimensions[key]) in (float,int) and abs(dimensions[key]-actual)<.0001 for key,actual in zip('xyz',model['dimensions'])))
    textures=entity.get('textures');textures=json_document(textures) if type(textures) is str else textures
    need(same(textures,json_document(model['textures'])))
    if 'id' in entity:need(type(entity['id']) is str and entity['id'].strip('{}')==owned_id)
    need(hashlib.sha256(raw).hexdigest()==row['sha256'] and raw!=base64.b64decode(last['source']['files'][0]['base64'],validate=True))
    return dict(iosCreateExportVersion=VERSION,entityId=owned_id,bytes=len(raw),sha256=row['sha256'],
                identity=deepcopy(row['identity']),base64=row['base64'],nativeEpochMs=last['clockAfter']['epochMs'])
