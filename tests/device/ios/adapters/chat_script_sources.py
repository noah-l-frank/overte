"""Original submitted Chat VM bytes; QML/effects/lifetime joins stay separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.native_script_roots import root_url
from adapters.script_feature.history import same
from feature_journeys.contract import json_document
from ios.adapters.create_state import command as state_command,text
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-chat-script-sources'
FILE=ACTION+'.json'
LIMIT=262144
FILES=('communityScripts/armored-chat/armored_chat.js',)
PIN_FILE=Path(__file__).parents[1]/'chat-script-source-pins.v1.json'


def command(value):
    original=deepcopy(value);original['action']='feature-ios-create-state';state_command(original)
    need(value['action']==ACTION);return value


def code_sources(value,epoch,previous=None):
    exact(value,{'chatScriptSourcesVersion','complete','evaluations'})
    need(type(value['chatScriptSourcesVersion']) is int and value['chatScriptSourcesVersion']==1
        and type(value['complete']) is bool and type(value['evaluations']) is list and len(value['evaluations'])<=64)
    stamp=0
    for index,row in enumerate(value['evaluations'],1):
        exact(row,{'sequence','url','submittedEpochMs','encoding','codeUnits','sha256'})
        parsed=urlsplit(text(row['url'],4096))
        need(type(row['sequence']) is int and row['sequence']==index and parsed.scheme in ('file','qrc')
            and not parsed.netloc and not parsed.query and not parsed.fragment and '?' not in row['url'] and '#' not in row['url']
            and parsed.path.endswith(tuple('/'+name for name in FILES)) and row['encoding']=='utf-16le-code-units'
            and integer(row['codeUnits'],1,4194304) and re.fullmatch('[0-9a-f]{64}',text(row['sha256'],64))
            and integer(row['submittedEpochMs'],1,epoch) and row['submittedEpochMs']>=stamp)
        stamp=row['submittedEpochMs']
    if previous is not None:
        code_sources(previous,epoch)
        need((previous['complete'] or not value['complete']) and same(value['evaluations'][:len(previous['evaluations'])],previous['evaluations']))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosChatScriptSourcesVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosChatScriptSourcesVersion']) is int and value['iosChatScriptSourcesVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and re.fullmatch('[0-9a-f]{32}',text(value['instance'],32))
        and integer(value['sequence'],1,1000000000) and value['clockDomain']=='native-main-chat-script-sources')
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    before,after=value['clockBefore'],value['clockAfter'];delta=after['epochMs']-before['epochMs'];elapsed=after['monotonicMs']-before['monotonicMs']
    need(0<=delta<1500 and 0<=elapsed<1500 and abs(delta-elapsed)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','revision','workers'})
    need(type(source['complete']) is bool and integer(source['revision']) and type(source['workers']) is list
        and len(source['workers'])<=128 and source['revision']>=len(source['workers']))
    ids=[]
    for row in source['workers']:
        exact(row,{'membership','code','codeSources','running','stopping','finished','done'})
        member=row['membership'];membership(dict(complete=True,revision=1,managers=[member]),after['epochMs'])
        parsed=urlsplit(member['url']);need(member['assigned'] and parsed.scheme in ('file','qrc') and not parsed.netloc
            and not parsed.query and not parsed.fragment and parsed.path.endswith('/'+FILES[0]))
        validate_code(row['code'],after['epochMs']);code_sources(row['codeSources'],after['epochMs'])
        if row['code']['submitted']:need(row['code']['submittedEpochMs']>=member['assignedEpochMs'])
        need(all(item['submittedEpochMs']>=member['assignedEpochMs'] for item in row['codeSources']['evaluations']))
        need(all(type(row[key]) is bool for key in ('running','stopping','finished','done')))
        main=[item for item in row['codeSources']['evaluations'] if item['url']==member['url']]
        if main:
            need(row['code']['submitted'] and all(item['submittedEpochMs']>=row['code']['submittedEpochMs']
                and all(item[key]==row['code'][key] for key in ('encoding','codeUnits','sha256')) for item in main))
        ids.append(member['instance'])
    need(ids==sorted(set(ids)) and len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and source['revision']>=previous['source']['revision'] and (previous['source']['complete'] or not source['complete']))
        old={row['membership']['instance']:row for row in previous['source']['workers']}
        current={row['membership']['instance']:row for row in source['workers']};need(set(old)<=set(current))
        if set(old)!=set(current):need(source['revision']>previous['source']['revision'])
        for identity,row in old.items():
            newer=current[identity];need(same(row['membership'],newer['membership'])
                and (not row['finished'] or newer['finished']) and (not row['done'] or newer['done']))
            if row['code']['submitted']:need(same(row['code'],newer['code']))
            elif newer['code']['submitted']:need(newer['code']['submittedEpochMs']>=previous['clockBefore']['epochMs'])
            code_sources(newer['codeSources'],after['epochMs'],row['codeSources'])
            need(all(item['submittedEpochMs']>=previous['clockBefore']['epochMs']
                for item in newer['codeSources']['evaluations'][len(row['codeSources']['evaluations']):]))
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def pins():
    raw=PIN_FILE.read_bytes();need(len(raw)<=8192);value=json_document(raw)
    exact(value,{'iosChatScriptSourcePinsVersion','encoding','sources'})
    need(type(value['iosChatScriptSourcePinsVersion']) is int and value['iosChatScriptSourcePinsVersion']==1
        and value['encoding']=='utf-16le-code-units');exact(value['sources'],set(FILES))
    for row in value['sources'].values():
        exact(row,{'codeUnits','sha256'})
        need(integer(row['codeUnits'],1,4194304) and re.fullmatch('[0-9a-f]{64}',text(row['sha256'],64)))
    return deepcopy(value['sources'])


def admit(value,scripts_root):
    original(value);expected=pins();root=root_url(scripts_root);source=value['source'];need(source['complete'])
    live=[row for row in source['workers'] if row['running'] and not any(row[key] for key in ('stopping','finished','done'))]
    need(len(live)==1);row=live[0];need(row['membership']['url']==root+FILES[0] and row['code']['submitted'] and row['codeSources']['complete'])
    need(all(row['code'][key]==expected[FILES[0]][key] for key in ('codeUnits','sha256')))
    need(len(row['codeSources']['evaluations'])==len(FILES))
    for name in FILES:
        evaluations=[item for item in row['codeSources']['evaluations'] if item['url']==root+name]
        need(len(evaluations)==1 and all(evaluations[0][key]==expected[name][key] for key in ('codeUnits','sha256')))
    return deepcopy(row)


class IOSChatScriptSources(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosChatScriptSourcesAcquisitionVersion'
