"""Strict original Android export callback source; no success inference."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,integer,need

KINDS={'request-active','share-uri','document-launched','document-result','share-chosen','destination-created',
    'destination-copied','destination-published','destination-deleted','destination-delete-failed','result-ready','delivered','cancelled'}
IDENTITY={'request','handle','ticket','generation','action','source'}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def text(value,limit):return type(value) is str and len(value)<=limit and all(ord(ch)>=32 and ord(ch)!=127 for ch in value)
def decimal(value):return type(value) is str and re.fullmatch('[1-9][0-9]{0,18}',value) is not None and int(value)<=2**63-1
def uri(value):
    need(text(value,4096));parts=urlsplit(value)
    need(parts.scheme=='content' and parts.netloc and '@' not in parts.netloc and ':' not in parts.netloc
        and not parts.query and not parts.fragment and parts.path.startswith('/'))
    return parts


def exports(value,valid_path):
    exact(value,{'snapshotExportObservationVersion','instance','complete','capturedEpochMs','elapsedMs','sequence','activeRequest','events'})
    need(type(value['snapshotExportObservationVersion']) is int and value['snapshotExportObservationVersion']==1
        and nonce(value['instance']) and value['complete'] is True and integer(value['capturedEpochMs'],1)
        and integer(value['elapsedMs'],0) and integer(value['sequence'],0,256) and type(value['events']) is list
        and len(value['events'])==value['sequence'] and (value['activeRequest']=='' or nonce(value['activeRequest'])))
    requests={};ready={};tickets=set();active='';epoch=elapsed=0
    for sequence,row in enumerate(value['events'],1):
        exact(row,IDENTITY|{'sequence','kind','value','auxiliary','capturedEpochMs','elapsedMs'})
        need(type(row['sequence']) is int and row['sequence']==sequence and nonce(row['request'])
            and all(decimal(row[key]) for key in ('handle','ticket','generation')) and row['action'] in ('save','share')
            and valid_path(row['source']) and row['kind'] in KINDS and text(row['value'],4096)
            and text(row['auxiliary'],1024) and integer(row['capturedEpochMs'],max(1,epoch),value['capturedEpochMs'])
            and integer(row['elapsedMs'],elapsed,value['elapsedMs']))
        identity={key:row[key] for key in IDENTITY};kind=row['kind'];data=row['value'];aux=row['auxiliary']
        if kind=='request-active':
            need(not active and row['request'] not in requests and row['ticket'] not in tickets and not data and not aux)
            requests[row['request']]=identity;active=row['request']
            tickets.add(row['ticket'])
        else:need(requests.get(row['request'])==identity)
        if kind in ('result-ready','delivered'):
            need(active==row['request'] and data in ('success','cancelled','error'))
            if kind=='delivered':need(ready.get(row['request'])==(data,aux))
            else:ready[row['request']]=(data,aux)
        elif kind=='cancelled':need(active==row['request'] and data=='cancelled' and not aux)
        elif kind=='document-launched':need(row['action']=='save' and not data and not aux)
        elif kind=='share-chosen':need(row['action']=='share' and bool(data) and not aux)
        elif kind=='share-uri':
            need(row['action']=='share' and uri(data).netloc=='io.github.noah_be.overte.phone.snapshot.files' and not aux)
        elif kind=='document-result':
            if data:uri(data)
            need(re.fullmatch('[0-9]{1,10}:-?[0-9]{1,11}',aux) is not None)
        elif kind.startswith('destination-'):
            uri(data);need(row['action']=='save')
            if kind=='destination-published':need(aux=='1')
            elif kind=='destination-deleted':need(re.fullmatch('[0-9]{1,10}',aux) is not None)
            else:need(not aux)
        if kind in ('delivered','cancelled'):active=''
        epoch,elapsed=row['capturedEpochMs'],row['elapsedMs']
    need(active==value['activeRequest'])
    return value


def continuity(before,after):
    need(after['instance']==before['instance'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and after['elapsedMs']>=before['elapsedMs'] and after['sequence']>=before['sequence']
        and after['events'][:len(before['events'])]==before['events'])
