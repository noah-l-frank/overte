"""Actual V8 frame/module joins, never legacy wrapper-parent reconstruction."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_http import installed
from ios.adapters.web_script_emissions import stack

SUFFIXES=('/system/avatarapp.js','/system/pal.js','/system/libraries/peopleConnection.js','/modules/request.js','/system/request-service.js')


def validate(value,modules,epoch,*,required=frozenset()):
    stack(value,epoch);need(value is not None and value['complete'] and type(modules) is list and len(modules)<=32
        and type(required) in (set,frozenset) and required<=set(SUFFIXES))
    scripts={}
    for frame in value['frames']:
        need(same(scripts.get(frame['scriptId'],frame['compiled']),frame['compiled']))
        scripts[frame['scriptId']]=frame['compiled']
    previous=-1;found=set()
    for module in modules:
        exact(module,{'frame','url'});index=module['frame']
        need(integer(index,previous+1,len(value['frames'])-1));previous=index
        url=module['url'];need(type(url) is str)
        suffix=next((suffix for suffix in SUFFIXES if url.endswith(suffix)),None);need(suffix is not None);installed(url,suffix)
        frame=value['frames'][index];compiled=frame['compiled'];sha=hashlib.sha256(url.encode('utf-8')).hexdigest()
        need(frame['sourceUrlSha256']==compiled['urlSha256']==sha)
        found.add(suffix)
    need(required<=found);return value


def evaluated(value,modules,epoch,code,*,required=frozenset(),top=None):
    """Join actual frame bytes to actual submitted code; no candidate-pin fact."""
    validate(value,modules,epoch,required=required)
    need(type(code) is list)
    last=0
    for sequence,row in enumerate(code,1):
        exact(row,{'sequence','url','submittedEpochMs','encoding','codeUnits','sha256'})
        need(type(row['sequence']) is int and row['sequence']==sequence and integer(row['submittedEpochMs'],max(1,last),epoch)
            and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],1,4194304) and type(row['sha256']) is str)
        last=row['submittedEpochMs']
        need(type(row['url']) is str);suffix=next((suffix for suffix in SUFFIXES if row['url'].endswith(suffix)),None)
        need(suffix is not None);installed(row['url'],suffix)
    for module in modules:
        frame=value['frames'][module['frame']];compiled=frame['compiled'];url=module['url']
        need(not frame['isEval'])
        need(any(row['url']==url and row['sha256']==compiled['sha256'] and row['codeUnits']==compiled['codeUnits']
            and row['encoding']==compiled['encoding'] and row['submittedEpochMs']<=compiled['firstObservedEpochMs']<=epoch for row in code))
    if top is not None:
        need(type(top) is str and top in required and any(module['frame']==0 and module['url'].endswith(top) for module in modules))
    return deepcopy(value)


def bound(value,modules,epoch,code,expected,*,required,top=None):
    """Join real frames to separately reviewed pins and actual evaluation logs.

    `firstObservedEpochMs` remains the first frame observation. The independent
    submitted-code timestamps, not that observation, establish evaluation order.
    """
    evaluated(value,modules,epoch,code,required=required,top=top)
    need(type(expected) is dict and set(expected)<=set(SUFFIXES))
    for module in modules:
        frame=value['frames'][module['frame']];url=module['url'];compiled=frame['compiled']
        suffix=next(suffix for suffix in SUFFIXES if url.endswith(suffix));need(suffix in expected)
        pin=expected[suffix];exact(pin,{'codeUnits','sha256'})
        need(type(pin['sha256']) is str and integer(pin['codeUnits'],1,4194304)
            and compiled['sha256']==pin['sha256'] and compiled['codeUnits']==pin['codeUnits'])
    return deepcopy(value)


def continuity(before,after):
    """One actual engine birth and immutable compiled identity per ScriptId."""
    need(type(before) is dict and type(after) is dict and before['instance']==after['instance'])
    old={frame['scriptId']:frame['compiled'] for frame in before['frames']}
    for frame in after['frames']:
        if frame['scriptId'] in old:need(same(frame['compiled'],old[frame['scriptId']]))
    return after


def table(values,epoch,*,single_engine=False):
    """Decode immutable actual stack entries; references never invent frames."""
    from ios.adapters.avatar_state import identity
    need(type(values) is list and len(values)<=128 and type(single_engine) is bool);result={};histories={};seen=[]
    for row in values:
        exact(row,{'id','callerStack','callerModules'});identity(row['id']);need(row['id'] not in result)
        validate(row['callerStack'],row['callerModules'],epoch)
        histories.setdefault(row['callerStack']['instance'],History()).accept(row['callerStack'])
        if single_engine:need(len(histories)<=1)
        original=dict(callerStack=row['callerStack'],callerModules=row['callerModules'])
        need(not any(same(original,old) for old in seen));seen.append(original);result[row['id']]=row
    return result


class History:
    """Actual one-engine ScriptId identities across every retained frame."""
    def __init__(self):self.instance=None;self.scripts={}
    def accept(self,value):
        need(type(value) is dict and value['complete'])
        need(self.instance is None or value['instance']==self.instance);self.instance=value['instance']
        for frame in value['frames']:
            key=frame['scriptId'];compiled=frame['compiled']
            need(same(self.scripts.get(key,compiled),compiled));self.scripts[key]=deepcopy(compiled)
        return value
