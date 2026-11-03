"""Typed fresh original PC recorder/route query; never acoustic acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from feature_journeys.contract import identifier

VERSION=1
STATES=('issued','starting','capturing','closed','completed','failed','retired')


def process(value):
    exact(value,{'identity','executable','commandSha256'})
    need(type(value['identity']) is str and re.fullmatch(r'[1-9][0-9]*:[1-9][0-9]*:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['identity']) is not None)
    need(type(value['commandSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['commandSha256']) is not None)
    row=value['executable'];need(type(row) is list and len(row)==8 and all(type(field) is int and field>=0 for field in row)
        and row[1]>0 and row[4]>0)


def validate(value,capture,request,epoch):
    exact(value,{'audioPreviewSourceVersion','producerSha256','requestId','instance','sequence','provider','clientProcess','captureId',
        'requestedEpochMs','capturedEpochMs','source','physicalAudioHardwareTested'})
    need(type(value['audioPreviewSourceVersion']) is int and value['audioPreviewSourceVersion']==VERSION
        and value['requestId']==request and value['captureId']==capture and value['physicalAudioHardwareTested'] is False)
    identifier(value['requestId']);identifier(value['instance']);identifier(value['captureId']);process(value['provider']);process(value['clientProcess'])
    need(type(value['producerSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['producerSha256']) is not None)
    need(value['clientProcess']['identity']!=value['provider']['identity'])
    need(integer(value['sequence'],1) and integer(value['requestedEpochMs'],1,value['capturedEpochMs']))
    fresh(value['requestedEpochMs'],epoch);fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    if source is None:return value
    exact(source,{'generation','armRequestId','seconds','state','worker','route','startedEpochMs','exit','original'})
    identifier(source['generation']);identifier(source['armRequestId'])
    need(number(source['seconds'],3,10) and source['state'] in STATES)
    if source['worker'] is not None:process(source['worker']);need(source['worker']['identity'] not in (value['provider']['identity'],value['clientProcess']['identity']))
    if source['route'] is not None:
        route=source['route'];exact(route,{'monitorSha256','sourceIndex','streams'})
        need(type(route['monitorSha256']) is str and re.fullmatch('[0-9a-f]{64}',route['monitorSha256']) is not None
            and integer(route['sourceIndex'],0) and type(route['streams']) is list and 1<=len(route['streams'])<=16)
        ids=[]
        for row in route['streams']:
            exact(row,{'index','source','corked'});need(integer(row['index'],0) and row['source']==route['sourceIndex'] and type(row['source']) is int and row['corked'] is False);ids.append(row['index'])
        need(ids==sorted(set(ids)))
    if source['startedEpochMs'] is not None:need(integer(source['startedEpochMs'],1,value['capturedEpochMs']))
    if source['exit'] is not None:
        closed=source['exit'];exact(closed,{'returnCode','processAbsent','streamAbsent','capturedEpochMs'})
        need(type(closed['returnCode']) is int and closed['processAbsent'] is closed['streamAbsent'] is True
            and source['worker'] is not None and integer(closed['capturedEpochMs'],1,value['capturedEpochMs']))
    if source['state']=='capturing':
        need(source['worker'] is not None and source['route'] is not None and source['startedEpochMs'] is not None
            and source['exit'] is source['original'] is None)
    if source['state'] in ('closed','completed'):
        need(source['worker'] is not None and source['route'] is not None and source['exit'] is not None)
    if source['original'] is not None:
        original=source['original'];need(type(original) is dict and original.get('schemaVersion')==1 and type(original['schemaVersion']) is int
            and original.get('captureId')==capture and original.get('source')=='private-pc-playout-monitor'
            and original.get('physicalAudioHardwareTested') is False and source['exit'] is not None
            and integer(original.get('startedEpochMs'),source['startedEpochMs'],value['capturedEpochMs'])
            and integer(original.get('completedEpochMs'),source['exit']['capturedEpochMs'],value['capturedEpochMs']))
    if source['state']=='completed':need(source['original'] is not None)
    return value


def accept(previous,current):
    if previous is not None:
        need(current['producerSha256']==previous['producerSha256'] and current['instance']==previous['instance'] and current['provider']==previous['provider'] and current['clientProcess']==previous['clientProcess']
            and current['captureId']==previous['captureId'] and current['sequence']>previous['sequence']
            and current['capturedEpochMs']>=previous['capturedEpochMs'] and current['requestId']!=previous['requestId'])
        old,new=previous['source'],current['source']
        if old is not None:
            need(new is not None and all(new[key]==old[key] for key in ('generation','armRequestId','seconds')))
            allowed={'issued':STATES,'starting':STATES[1:],'capturing':STATES[2:],'closed':('closed','completed','failed','retired'),
                'completed':('completed','retired'),'failed':('failed','retired'),'retired':('retired',)}
            need(new['state'] in allowed[old['state']])
            for key in ('worker','route','startedEpochMs','exit','original'):
                if old[key] is not None:need(new[key]==old[key])
            if old['state'] in ('completed','retired'):need(new['state'] in (old['state'],'retired'))
            if old['exit'] is not None:need(new['state']!='capturing')
    return deepcopy(current)


def verify_kernel(value):
    """The existing controller is loopback-only; independently read its PIDs."""
    from voice_peer.preview_source import process as current_process,absent
    for key in ('provider','clientProcess'):
        original=value[key];pid=int(original['identity'].split(':',1)[0]);need(current_process(pid)==original)
    source=value['source']
    if source is not None and source['worker'] is not None:
        pid=int(source['worker']['identity'].split(':',1)[0])
        if source['state']=='capturing':need(current_process(pid)==source['worker'])
        elif source['exit'] is not None:absent(pid)
