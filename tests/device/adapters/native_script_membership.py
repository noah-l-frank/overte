"""Actual all-known manager membership includes pre-callback Script loads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact, integer, need
from adapters.native_script_loads import identifier

VERSION = 1


def validate(value, captured):
    need(type(value) is dict and type(value.get('complete')) is bool and integer(captured,1))
    if not value['complete']:
        exact(value,{'complete'})
        return value
    exact(value,{'complete','revision','managers'})
    need(integer(value['revision']) and type(value['managers']) is list and len(value['managers'])<=128
         and value['revision']>=len(value['managers']))
    ids=set()
    for row in value['managers']:
        exact(row,{'instance','assigned','url','loadGeneration','assignedEpochMs'})
        need(identifier(row['instance']) and row['instance'] not in ids and type(row['assigned']) is bool
             and type(row['url']) is str and len(row['url'])<=4096
             and integer(row['loadGeneration']) and integer(row['assignedEpochMs']))
        ids.add(row['instance'])
        if not row['assigned']:
            need(row['url']=='' and row['loadGeneration']==0 and row['assignedEpochMs']==0)
        else:
            need(bool(row['url']) and not any(ord(char)<32 for char in row['url'])
                 and '?' not in row['url'] and '#' not in row['url']
                 and row['loadGeneration']>0 and 0<row['assignedEpochMs']<=captured)
            parsed=urlsplit(row['url'])
            need(parsed.scheme in ('file','http','https','atp','qrc') and parsed.username is None and parsed.password is None)
            need(parsed.port is None or 1<=parsed.port<=65535)
            if parsed.scheme in ('http','https'):need(bool(parsed.hostname))
    return value


def accept(previous, value, retired, captured):
    validate(value,captured);need(value['complete'])
    need(type(retired) is set and all(identifier(item) for item in retired))
    current={row['instance']:row for row in value['managers']}
    need(not set(current)&retired)
    if previous is not None:
        validate(previous,captured);need(previous['complete'] and value['revision']>=previous['revision'])
        old={row['instance']:row for row in previous['managers']}
        need(set(current)==set(old) or value['revision']>previous['revision'])
        for instance,row in current.items():
            if instance not in old:continue
            before=old[instance]
            need(row['loadGeneration']>=before['loadGeneration'] and row['assignedEpochMs']>=before['assignedEpochMs'])
            if row['loadGeneration']==before['loadGeneration']:need(row==before)
        retired=retired | (set(old)-set(current))
    need(len(retired | set(current))<=4096)
    return deepcopy(value),set(retired)
