"""Original native Script-file dialog response completion, without input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel
from feature_journeys.contract import identifier

VERSION=1
ACTION='feature-ios-script-dialogs'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    identifier(value['runId']);return value


def ledger(value,epoch,pid):
    exact(value,{'scriptDialogLedgerVersion','instance','processId','complete','eventSequence','events'})
    need(type(value['scriptDialogLedgerVersion']) is int and value['scriptDialogLedgerVersion']==1
        and value['processId']==pid and type(value['processId']) is int and value['complete'] is True)
    identifier(value['instance']);need(integer(value['eventSequence'],0,512) and type(value['events']) is list
        and len(value['events'])==value['eventSequence'])
    stages={};destroyed=set();last_epoch=last_mono=0
    for index,row in enumerate(value['events']):
        exact(row,{'eventSequence','capturedEpochMs','monotonicMs','dialogInstance','kind','response','fileExists','manager'})
        token=identifier(row['dialogInstance']);need(type(row['eventSequence']) is int and row['eventSequence']==index+1
            and integer(row['capturedEpochMs'],max(1,last_epoch),epoch) and integer(row['monotonicMs'],last_mono))
        kind=row['kind'];need(kind in ('listener-created','response-entered','response-returned','listener-destroyed'))
        if kind=='listener-created':
            need(token not in stages and len(stages)<128);stages[token]=0
        else:
            need(token in stages)
            if kind=='response-entered':
                need(stages[token]==0);stages[token]=1;response=row['response']
                exact(response,{'text','encoding','codeUnits','sha256'});text=response['text']
                need(type(text) is str and len(text.encode('utf-16le'))//2<=4096
                    and response['encoding']=='utf-16le-code-units' and type(response['codeUnits']) is int
                    and response['codeUnits']==len(text.encode('utf-16le'))//2
                    and response['sha256']==hashlib.sha256(text.encode('utf-16le')).hexdigest()
                    and type(row['fileExists']) is bool and (not row['fileExists'] or bool(text)))
            elif kind=='response-returned':
                need(stages[token]==1);stages[token]=2
                if row['manager'] is not None:
                    membership(dict(complete=True,revision=1,managers=[row['manager']]),row['capturedEpochMs'])
                    need(row['manager']['assigned'])
            else:need(token not in destroyed);destroyed.add(token)
        if kind!='response-entered':need(row['response'] is None and row['fileExists'] is None)
        if kind!='response-returned':need(row['manager'] is None)
        last_epoch,last_mono=row['capturedEpochMs'],row['monotonicMs']
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosScriptDialogVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosScriptDialogVersion']) is int and value['iosScriptDialogVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and value['clockDomain']=='native-main-script-dialog' and integer(value['sequence'],1,1000000000))
    identifier(value['instance'])
    a,b=value['clockBefore'],value['clockAfter']
    for clock in (a,b):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    need(0<=b['epochMs']-a['epochMs']<1500 and 0<=b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    ledger(value['source'],b['epochMs'],pid)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(previous['instance']==value['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and a['epochMs']>=previous['clockAfter']['epochMs']
            and a['monotonicMs']>=previous['clockAfter']['monotonicMs'])
        before,after=previous['source'],value['source']
        need(before['instance']==after['instance'] and after['eventSequence']>=before['eventSequence']
            and same(after['events'][:len(before['events'])],before['events']))
    return value


def completed(value,before,*,after_epoch):
    """One actually created listener and its returned Application callback."""
    validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'],previous=before)
    need(integer(after_epoch,1));floor=before['source']['eventSequence']
    born=[row for row in value['source']['events'][floor:] if row['kind']=='listener-created']
    need(len(born)==1 and born[0]['capturedEpochMs']>=after_epoch)
    rows=[row for row in value['source']['events'] if row['dialogInstance']==born[0]['dialogInstance']]
    entered=[r for r in rows if r['kind']=='response-entered'];returned=[r for r in rows if r['kind']=='response-returned']
    need(len(entered)==len(returned)==1 and returned[0]['eventSequence']>entered[0]['eventSequence'])
    return deepcopy(dict(dialog=born[0]['dialogInstance'],entered=entered[0],returned=returned[0]))


class IOSScriptDialogs(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosScriptDialogAcquisitionVersion'
