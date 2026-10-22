"""Actual incomplete Create marker execution, without invented entity births."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.native_feature_observation import need
from adapters.native_script_observation import running_owned_engine
from adapters.native_script_terminal import terminal,validate as terminal_validate,ACTION as TERMINAL_ACTION
from adapters.script_feature.history import same
from ios.adapters.create_actions import semantic_map
from ios.adapters.create_marker_files import originals
from ios.adapters.create_marker_identity import marker
from ios.adapters.create_marker_measurements import admitted as full_admitted,restored as full_restored,body_preserved,view_preserved
from ios.adapters.emote_marker_partial import drained_partial

VERSION=1


def admitted(before,after,files,directory,*,after_epoch):
    body_preserved(before['world'],after['world'])
    return full_admitted(before['create'],after['create'],after['world']['source']['scriptOriginal'],files,directory,after_epoch=after_epoch)


def execution_code(files,directory,manager,code,after_epoch):
    need(manager['assigned'] and manager['url']==directory+'/script-bundle/main.js'
        and after_epoch<=manager['assignedEpochMs']<=code['submittedEpochMs'])
    raw=originals(files['runId'],files['fixtureUrl'],files['ticket'],files['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
    need(code['submitted'] and code['encoding']=='utf-16le-code-units' and code['codeUnits']==len(raw)//2 and code['sha256']==hashlib.sha256(raw).hexdigest())


def executed(before,after,files,directory,*,after_epoch):
    body_preserved(before['world'],after['world']);view_preserved(before['create'],after['create'])
    source=after['world']['source']['scriptOriginal'];url=directory+'/script-bundle/main.js';engine=running_owned_engine(source,url)
    membership=source['source'].get('membership');need(source['source'].get('membershipSourceVersion')==1 and membership['complete'])
    rows=[row for row in membership['managers'] if row['instance']==engine['required']['instance']];need(len(rows)==1);manager=rows[0];code=engine['code']
    execution_code(files,directory,manager,code,after_epoch)
    observed=None
    for row in after['create']['source']['entities']:
        if row['type']!='Web' or not row['userData']:continue
        try:data=json.loads(row['userData'])
        except ValueError:continue
        if type(data) is dict and data.get('kind')=='create-marker-v1' and data.get('runId')==files['runId']:
            need(observed is None);observed=marker(after['create'],files['nonce'],files['fixtureUrl']+'tickets/'+files['ticket']+'/graphics-marker.v1.html')
    ids=[] if observed is None else [observed['id']]
    need(same(semantic_map(before['create']),semantic_map(after['create'],ids)))
    return dict(iosCreatePartialMarkerVersion=VERSION,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=url,marker=observed)


def finished(before,after,files,directory,packet,*,after_sequence,after_epoch):
    body_preserved(before['world'],after['world']);view_preserved(before['create'],after['create'])
    need(same(semantic_map(before['create']),semantic_map(after['create'])))
    terminal_validate(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=TERMINAL_ACTION),after['create']['processId'],packet['capturedEpochMs'])
    url=directory+'/script-bundle/main.js';rows=[row for row in packet['source']['events'] if row['manager']['url']==url]
    need(type(after_sequence) is int and after_sequence>=0 and type(after_epoch) is int and after_epoch>0 and len(rows)==3
        and [row['kind'] for row in rows]==['thread-bound','shutdown-drained','thread-finished'] and rows[0]['eventSequence']>after_sequence
        and all(row['capturedEpochMs']>=after_epoch for row in rows))
    manager,code=rows[0]['manager'],rows[1]['code'];need(rows[2]['code']==code and all(row['manager']==manager for row in rows))
    execution_code(files,directory,manager,code,after_epoch)
    owned=dict(iosCreatePartialMarkerVersion=VERSION,manager=deepcopy(manager),code=deepcopy(code),sourceUrl=url,marker=None)
    restored(before,after,owned,packet,after_sequence=rows[0]['eventSequence'],after_epoch=rows[0]['capturedEpochMs'])
    return owned


def restored(before,after,owned,packet,*,after_sequence,after_epoch):
    body_preserved(before['world'],after['world']);view_preserved(before['create'],after['create'])
    if owned.get('iosCreateMarkerAdmissionVersion')==1:
        return full_restored(before['create'],after['create'],after['world']['source']['scriptOriginal'],owned,packet,after_sequence=after_sequence,after_epoch=after_epoch)
    need(owned.get('iosCreatePartialMarkerVersion')==VERSION and same(semantic_map(before['create']),semantic_map(after['create'])))
    scripts=after['world']['source']['scriptOriginal']['source'];membership=scripts.get('membership')
    need(scripts.get('membershipSourceVersion')==1 and membership['complete']
        and not any(row['instance']==owned['manager']['instance'] or row['url']==owned['sourceUrl'] for row in membership['managers'])
        and not any(row['url']==owned['sourceUrl'] or row['required']['instance']==owned['manager']['instance'] for row in scripts['engines']))
    need(packet['processId']==after['create']['processId']);return terminal(packet,owned['manager'],owned['code'],after_sequence=after_sequence,after_epoch=after_epoch)
