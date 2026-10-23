"""Historical actual ATP request objects; no current null-member death inference."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import decode,exact,need


def integer(value,minimum=0):return type(value) is int and minimum<=value<=9007199254740991
def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) and value!='0'*32
def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value)
def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def validate_history(frames,pid,run):
    need(type(frames) is list and 1<=len(frames)<=512 and integer(pid,1) and nonce(run))
    previous=None
    for value in frames:
        exact(value,{'assetsRequestLifetimesVersion','instance','runId','processId','sequence','capturedEpochMs','objects'})
        need(type(value['assetsRequestLifetimesVersion']) is int and value['assetsRequestLifetimesVersion']==1
            and nonce(value['instance']) and value['runId']==run and type(value['processId']) is int and value['processId']==pid
            and integer(value['sequence'],1) and value['sequence']<=512 and integer(value['capturedEpochMs'],1)
            and type(value['objects']) is list and len(value['objects'])<=64)
        seen=set();parents=set()
        for row in value['objects']:
            exact(row,{'id','kind','resourceId','sourceSha256','firstObservedEpochMs','firstObservedAbsentEpochMs','alive','sameThreadAsResource'})
            need(nonce(row['id']) and row['id'] not in seen and row['kind'] in ('resource','mapping','asset') and digest(row['sourceSha256'])
                and integer(row['firstObservedEpochMs'],1) and row['firstObservedEpochMs']<=value['capturedEpochMs']
                and type(row['alive']) is bool and type(row['sameThreadAsResource']) is bool)
            seen.add(row['id']);absent=row['firstObservedAbsentEpochMs']
            need(absent is None if row['alive'] else integer(absent,row['firstObservedEpochMs']) and absent<=value['capturedEpochMs'])
            if row['kind']=='resource':
                need(row['resourceId']=='' and row['sameThreadAsResource'] is True);parents.add(row['id'])
            else:need(nonce(row['resourceId']) and row['resourceId'] in parents)
        start=0
        if previous is not None:
            need(value['instance']==previous['instance'] and value['sequence']==previous['sequence']+1
                and value['capturedEpochMs']>=previous['capturedEpochMs'] and len(value['objects'])>=len(previous['objects']))
            start=len(previous['objects'])
            for before,after in zip(previous['objects'],value['objects']):
                need({key:before[key] for key in before if key not in ('alive','firstObservedAbsentEpochMs')}
                    =={key:after[key] for key in after if key not in ('alive','firstObservedAbsentEpochMs')})
                if not before['alive']:need(after==before)
        else:need(value['sequence']==1 and value['objects']==[])
        # A first-seen dead object supplies no admitted original live identity.
        need(all(row['alive'] is True and row['firstObservedAbsentEpochMs'] is None
            and (previous is None or row['firstObservedEpochMs']>=previous['capturedEpochMs']) for row in value['objects'][start:]))
        previous=value
    return deepcopy(previous)


def require_retired(frames,pid,run,resources):
    last=validate_history(frames,pid,run);need(type(resources) is list and 1<=len(resources)<=16)
    expected={}
    for resource in resources:
        need(type(resource) is dict and type(resource.get('url')) is str and digest(resource.get('sha256')))
        url=resource['url'];need(urlsplit(url).scheme=='atp' and sha(url) not in expected)
        expected[sha(url)]=(sha(urlsplit(url).path),sha(resource['sha256']))
    rows=last['objects'];need(len(rows)==3*len(expected) and all(row['alive'] is False for row in rows))
    parents={row['sourceSha256']:row for row in rows if row['kind']=='resource'};need(set(parents)==set(expected))
    for source,parent in parents.items():
        children=[row for row in rows if row['resourceId']==parent['id']]
        need(len(children)==2 and {row['kind'] for row in children}=={'mapping','asset'})
        need(next(row for row in children if row['kind']=='mapping')['sourceSha256']==expected[source][0])
        need(next(row for row in children if row['kind']=='asset')['sourceSha256']==expected[source][1])
    return last


def replay_originals(originals,container=None):
    """Decode actual raw originals or exact immutable-container references once."""
    need(type(originals) is list and 1<=len(originals)<=512)
    values=[];parent=None
    for original in originals:
        need(type(original) is dict)
        if 'raw' in original:
            exact(original,{'command','raw','sha256'});command=original['command']
            exact(command,{'action','runId'})
            need(command['action']=='host-original-resource-lifetimes' and nonce(command['runId'])
                and type(original['raw']) is str and len(original['raw'].encode())<=65536
                and digest(original['sha256']) and sha(original['raw'])==original['sha256'])
            value=decode(original['raw']);need(type(value) is dict and value.get('runId')==command['runId'])
        else:
            exact(original,{'containerSha256','field','index'})
            need(type(container) is str and digest(original['containerSha256']) and sha(container)==original['containerSha256']
                and original['field']=='requestLifetimeOriginals' and integer(original['index']))
            if parent is None:parent=decode(container)
            need(type(parent) is dict and type(parent.get(original['field'])) is list
                and len(parent[original['field']])<=512 and original['index']<len(parent[original['field']]))
            value=deepcopy(parent[original['field']][original['index']]);need(type(value) is dict and value.get('runId')==parent.get('runId'))
        values.append(value)
    return values
