"""Closed source-pinned Avatar callsites, separate from module-origin evidence.

The native stack remains its original neutral DTO. Every indexed frame must fit
one whole reviewed profile; a matching module cannot hide another parent frame.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from adapters.native_feature_observation import exact,integer,need
from feature_journeys.contract import json_document
from ios.adapters import avatar_call_stack
from ios.adapters.places_http import installed

VERSION=1
FILE=Path(__file__).parents[1]/'avatar-callsite-pins.v1.json'
SOURCES=frozenset(avatar_call_stack.SUFFIXES)|{'/modules/appUi.js'}
KINDS=frozenset({'xhr-open','xhr-read','timer','entity-add','entity-delete'})
SHA=re.compile('[a-f0-9]{64}\\Z')


def validate_pins(value):
    exact(value,{'avatarCallsitePinsVersion','encoding','sources','profiles'})
    need(type(value['avatarCallsitePinsVersion']) is int and value['avatarCallsitePinsVersion']==VERSION
        and value['encoding']=='utf-16le-code-units')
    exact(value['sources'],SOURCES)
    for source in value['sources'].values():
        exact(source,{'codeUnits','sha256'})
        need(integer(source['codeUnits'],1,4194304) and type(source['sha256']) is str and SHA.fullmatch(source['sha256']))
    need(type(value['profiles']) is dict and 1<=len(value['profiles'])<=64)
    for name,profile in value['profiles'].items():
        need(type(name) is str and re.fullmatch('[a-z][a-z0-9]*(?:-[a-z0-9]+)*',name))
        exact(profile,{'kind','frames'});need(profile['kind'] in KINDS and type(profile['frames']) is list and 1<=len(profile['frames'])<=32)
        for frame in profile['frames']:
            exact(frame,{'source','line','column','token'})
            need(frame['source'] in SOURCES and integer(frame['line'],1,1000000) and integer(frame['column'],1,1000000)
                and type(frame['token']) is str and 1<=len(frame['token'])<=64
                and all(32<=ord(char)<127 for char in frame['token']))
    return deepcopy(value)


def pins():
    raw=FILE.read_bytes();need(len(raw)<=32768);return validate_pins(json_document(raw))


def qualify(value,modules,epoch,code,*,kind):
    """Return a reviewed full-stack profile without altering any source fields.

    Known native module rows must join actual submitted code first. The genuine
    installed root from those rows binds the additional appUi frame URL hash;
    appUi is not invented as an evaluated-code ledger entry. Its actual V8
    compiled bytes must independently equal the pinned original as every other
    frame must. First observation is never described as compilation time.
    """
    need(type(kind) is str and kind in KINDS)
    avatar_call_stack.evaluated(value,modules,epoch,code)
    need(bool(modules));roots=set()
    for module in modules:
        suffix=next(suffix for suffix in avatar_call_stack.SUFFIXES if module['url'].endswith(suffix))
        roots.add(module['url'][:-len(suffix)])
    need(len(roots)==1);root=next(iter(roots));expected=pins();matches=[]
    for name,profile in expected['profiles'].items():
        if profile['kind']!=kind or len(profile['frames'])!=len(value['frames']):continue
        matched=True
        for actual,pin in zip(value['frames'],profile['frames']):
            source=expected['sources'][pin['source']];url=root+pin['source'];installed(url,pin['source'])
            compiled=actual['compiled'];url_sha=hashlib.sha256(url.encode('utf-8')).hexdigest()
            if not (actual['line']==pin['line'] and actual['column']==pin['column']
                    and not actual['isEval'] and not actual['isConstructor']
                    and actual['sourceUrlSha256']==compiled['urlSha256']==url_sha
                    and compiled['sha256']==source['sha256'] and compiled['codeUnits']==source['codeUnits']):
                matched=False;break
        if matched:matches.append(name)
    need(len(matches)==1);return matches[0]


def entity_component(value,epoch,code):
    """Optional original component; Caller1 never gains an inferred stack."""
    exact(value,{'avatarEntityCallersVersion','complete','callerStack','callerModules'})
    need(type(value['avatarEntityCallersVersion']) is int and value['avatarEntityCallersVersion']==1 and value['complete'] is True)
    avatar_call_stack.evaluated(value['callerStack'],value['callerModules'],epoch,code,required={'/system/avatarapp.js'},top='/system/avatarapp.js')
    return value


def entity(value,epoch):
    """Strong entity callsite; ordinary legacy Caller1 remains weaker."""
    from ios.adapters.avatar_entities import caller
    caller(value,epoch);need('avatarCallers' in value)
    actual=entity_component(value['avatarCallers'],epoch,value['avatarCode']['code'])
    return qualify(actual['callerStack'],actual['callerModules'],epoch,value['avatarCode']['code'],
        kind='entity-add' if value['method']=='addEntity' else 'entity-delete')


def owned_timers(before,after,managers):
    """Check every actual timer birth after the admitted original baseline.

    Preexisting timer originals stay unchanged and remain the responsibility of
    their prior owner. This does not turn their module-origin proof into a new
    exact-callsite assertion. Full source/prefix validation always runs first.
    """
    from ios.adapters import avatar_scripts,avatar_ui_work
    avatar_scripts.original(before);avatar_scripts.original(after)
    need(before['iosAvatarScriptsVersion']==after['iosAvatarScriptsVersion']==2 and type(managers) is set and managers)
    avatar_scripts.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=avatar_scripts.ACTION,runId=after['runId']),
        after['processId'],previous=before)
    old={row['membership']['instance']:row for row in before['source']['workers']}
    current={row['membership']['instance']:row for row in after['source']['workers']};profiles={}
    for manager in managers:
        need(manager in old and manager in current and 'uiWork' in old[manager] and 'uiWork' in current[manager])
        a,b=old[manager]['uiWork'],current[manager]['uiWork'];avatar_ui_work.validate(b,after['clockAfter']['epochMs'],a)
        need(a['avatarUiWorkVersion']==b['avatarUiWorkVersion']==2 and a['complete'] and b['complete'])
        previous={row['timerId'] for row in a['timers']};table=avatar_call_stack.table(b['callerStacks'],after['clockAfter']['epochMs'],single_engine=True)
        for timer in b['timers']:
            if timer['timerId'] in previous:continue
            actual=table[timer['callerStackId']]
            profiles[(manager,timer['timerId'])]=qualify(actual['callerStack'],actual['callerModules'],timer['createdEpochMs'],
                current[manager]['avatar']['code'],kind='timer')
    return profiles


def consumed_http(scripts,value,consumption,expected):
    """Strong Open and actual responseText read, after existing effect joins."""
    from ios.adapters import avatar_scripts,avatar_social_http
    joined=avatar_scripts.join_http_code(scripts,value,consumption,expected,require_actual=True)
    selected=avatar_scripts.worker(scripts,joined['manager']['instance']);code=selected['avatar']['code']
    table=avatar_call_stack.table(value['callerStacks'],value['clockBefore']['epochMs']);profiles=[]
    for event,kind in ((consumption['nativeCreated'],'xhr-open'),(consumption['nativeRead'],'xhr-read')):
        actual=table[event['details']['callerStackId']]
        profiles.append(qualify(actual['callerStack'],actual['callerModules'],event['clock']['epochMs'],code,kind=kind))
    return tuple(profiles)
