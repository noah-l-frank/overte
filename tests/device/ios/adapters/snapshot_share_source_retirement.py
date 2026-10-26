"""Exact seven named source unlinks and fresh native/host absence windows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_destination import stamp
from ios.adapters.snapshot_share_inventory import NAMES
from ios.adapters.snapshot_share_query_owner import host_clock

INTENT='snapshot-share-source-retire-intent.json'
ALL_NAMES=(*NAMES,INTENT)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def original(value,nonce,inventory):
    exact(value,{'snapshotShareSourceRetirementVersion','requestId','runId','processId','bundleId','instance','sourceInstance','sourceBirthClock',
        'inventorySha256','parentIdentity','outputs','clockBefore','clockAfter','intent','steps','readersClosed','parentDescriptorClosed','complete'})
    source,raw=inventory.original();inventory.proof()
    need(type(value['snapshotShareSourceRetirementVersion']) is int and value['snapshotShareSourceRetirementVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['requestId']==nonce
        and nonce not in (source['requestId'],inventory.sealed.original()[0]['requestId'])
        and value['runId']==inventory.run and integer(value['processId'],1,2147483647)
        and all(same(value[key],source[key]) for key in ('processId','bundleId','instance','sourceInstance','sourceBirthClock','parentIdentity'))
        and value['inventorySha256']==sha(raw) and type(value['outputs']) is list
        and same(value['outputs'],[{key:item for key,item in pin.items() if key!='data'} for pin in source['outputs']])
        and all(type(value[key]) is bool for key in ('readersClosed','parentDescriptorClosed','complete'))
        and type(value['steps']) is list and len(value['steps'])<=7)
    stamp(value['clockBefore'],source['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    intent=value['intent']
    if intent is None:need(not value['steps'] and not value['readersClosed'] and not value['complete'])
    else:
        exact(intent,{'name','revision','sha256','byteCount','parentIdentity','data'})
        need(intent['name']==INTENT and intent['parentIdentity']==source['parentIdentity'] and type(intent['revision']) is str
            and len(intent['revision'])==64 and all(char in '0123456789abcdef' for char in intent['revision'])
            and type(intent['data']) is str and len(intent['data'])<=349528)
        original_raw=base64.b64decode(intent['data'],validate=True)
        need(integer(intent['byteCount'],1,262144) and len(original_raw)==intent['byteCount'] and sha(original_raw)==intent['sha256']
            and base64.b64encode(original_raw).decode()==intent['data'])
        initial=decode(original_raw.decode('utf-8'))
        need(same(initial,dict(value,clockAfter=None,intent=None,steps=[],readersClosed=False,parentDescriptorClosed=False,complete=False)))
    previous=value['clockBefore']
    for index,(row,name) in enumerate(zip(value['steps'],ALL_NAMES),1):
        exact(row,{'sequence','name','unlinked','synchronized','absent','clock'})
        need(type(row['sequence']) is int and row['sequence']==index and row['name']==name and value['readersClosed'] and intent is not None
            and all(type(row[key]) is bool for key in ('unlinked','synchronized','absent'))
            and (row['unlinked'] or not row['synchronized'] and not row['absent'])
            and (all(row[key] for key in ('unlinked','synchronized','absent')) or index==len(value['steps'])))
        stamp(row['clock'],previous);previous=row['clock']
    stamp(value['clockAfter'],previous)
    if value['complete']:qualified(value)
    return value


def qualified(value):
    need(value['complete'] is True and value['readersClosed'] is True and value['parentDescriptorClosed'] is True
        and value['intent'] is not None and len(value['steps'])==7
        and all(row['unlinked'] and row['synchronized'] and row['absent'] for row in value['steps']));return value


def observation(value,nonce,retired,retired_raw,previous=None):
    exact(value,{'snapshotShareSourceRetirementObservationVersion','requestId','runId','processId','bundleId','instance','sourceInstance','retirementSha256',
        'parentIdentity','clockBefore','clockAfter','files','sourceNamespaceEmpty','observationErrors','parentDescriptorClosed'})
    need(type(value['snapshotShareSourceRetirementObservationVersion']) is int and value['snapshotShareSourceRetirementObservationVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['requestId']==nonce
        and nonce!=retired['requestId'] and integer(value['processId'],1,2147483647)
        and all(same(value[key],retired[key]) for key in ('runId','processId','bundleId','instance','sourceInstance','parentIdentity'))
        and value['retirementSha256']==sha(retired_raw) and all(type(value[key]) is bool for key in ('sourceNamespaceEmpty','observationErrors','parentDescriptorClosed'))
        and type(value['files']) is list and len(value['files'])==7)
    stamp(value['clockBefore'],retired['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<5500 and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<5500)
    for row,name in zip(value['files'],ALL_NAMES):exact(row,{'name','absent'});need(row['name']==name and type(row['absent']) is bool)
    if previous is not None:
        observation(previous,previous['requestId'],retired,retired_raw)
        need(value['requestId']!=previous['requestId']);stamp(value['clockBefore'],previous['clockAfter'])
    return value


def absent(value):
    need(value['sourceNamespaceEmpty'] is True and value['observationErrors'] is False and value['parentDescriptorClosed'] is True
        and all(row['absent'] is True for row in value['files']));return value


def quiet(values,hosts,run):
    need(type(values) is list and type(hosts) is list and len(values)==len(hosts)==3 and len({row['requestId'] for row in values})==3)
    previous=None
    for value,host in zip(values,hosts):
        absent(value);need(value['runId']==run);exact(host,{'before','after'});host_clock(host['before']);host_clock(host['after'],host['before'])
        need(host['after']['epochMs']-host['before']['epochMs']<5500 and host['after']['monotonicMs']-host['before']['monotonicMs']<5500)
        if previous is not None:
            need(all(same(value[key],previous[0][key]) for key in ('runId','processId','bundleId','instance','sourceInstance','retirementSha256','parentIdentity')))
            stamp(value['clockBefore'],previous[0]['clockAfter']);host_clock(host['before'],previous[1]['after'])
        previous=(value,host)
    native_a,native_b=values[0]['clockAfter'],values[-1]['clockBefore'];host_a,host_b=hosts[0]['after'],hosts[-1]['before']
    native_ms=native_b['monotonicMs']-native_a['monotonicMs'];host_ms=host_b['monotonicMs']-host_a['monotonicMs']
    need(min(native_ms,host_ms,native_b['epochMs']-native_a['epochMs'],host_b['epochMs']-host_a['epochMs'])>=3000)
    return dict(snapshotShareSourceFilesQuietVersion=1,runId=run,nativeMilliseconds=native_ms,hostMilliseconds=host_ms,
        requestIds=[value['requestId'] for value in values],historicalOriginalsOnly=True,wholeFeatureRequired=True)
