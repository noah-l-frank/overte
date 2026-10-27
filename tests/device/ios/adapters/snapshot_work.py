"""Actual SNAP closure, submitted-code and native timer originals.

This component observes pending work. Neither its quiet state nor an input ACK
proves a render, encoded file, Photos save, external share or upload outcome.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.native_script_roots import root_url
from adapters.script_feature.history import same
from ios.adapters.avatar_ui_work import validate as timer_work
from ios.adapters.create_state import command as state_command, text
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-snapshot-work'
FILE=ACTION+'.json'
LIMIT=262144
MAIN='system/snapshot.js'
HELPER='system/snapshot/featureSnapshotWork.js'
PIN_FILE=Path(__file__).parents[1]/'snapshot-work-source-pins.v1.json'
TIMER_SUFFIXES=('/system/snapshot.js','/system/snapshot/featureSnapshotWork.js','/modules/request.js','/system/request-service.js')
COMBINED_FILES=('defaultScripts.js',MAIN,'modules/request.js',HELPER)
CLOSURES={'takeSnapshot','cancelNativeCapture','clearNativeCaptureTimers','scheduleNativeCapture',
          'onNativeCaptureStatus','onNativeUploadStatus','onClosingWindow','onMessage'}


def command(value,*,_combined=False):
    need(type(_combined) is bool)
    original=deepcopy(value);original['action']='feature-ios-create-state';state_command(original)
    need(value['action']==('feature-ios-snapshot-combined-work' if _combined else ACTION));return value


def code_sources(value,epoch,previous=None,*,_combined=False):
    need(type(_combined) is bool);marker='snapshotCombinedSourcesVersion' if _combined else 'snapshotSourcesVersion'
    exact(value,{marker,'complete','evaluations'})
    need(type(value[marker]) is int and value[marker]==1
         and type(value['complete']) is bool and type(value['evaluations']) is list and len(value['evaluations'])<=64)
    stamp=0
    for index,row in enumerate(value['evaluations']):
        exact(row,{'sequence','url','submittedEpochMs','encoding','codeUnits','sha256'})
        parsed=urlsplit(text(row['url']))
        need(type(row['sequence']) is int and row['sequence']==index+1 and parsed.scheme in ('file','qrc')
             and not parsed.netloc and not parsed.query and not parsed.fragment
             and (parsed.path.endswith(tuple('/'+path for path in COMBINED_FILES)) if _combined else '/system/snapshot/' in parsed.path or parsed.path.endswith('/'+MAIN))
             and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],1,4194304)
             and re.fullmatch('[a-f0-9]{64}',text(row['sha256'],64))
             and integer(row['submittedEpochMs'],1,epoch) and row['submittedEpochMs']>=stamp)
        stamp=row['submittedEpochMs']
    if previous is not None:
        code_sources(previous,epoch,_combined=_combined)
        need((previous['complete'] or not value['complete'])
             and same(value['evaluations'][:len(previous['evaluations'])],previous['evaluations']))
    return value


def pending(state):
    exact(state,{'nativeReview','revision','captureId','captureCounter','mode','timerHandles','pendingUploads','overlaysHidden','open'})
    need(all(type(state[key]) is bool for key in ('nativeReview','overlaysHidden','open'))
         and integer(state['revision'],0,1000000000) and integer(state['captureCounter'],0,1000000000)
         and integer(state['pendingUploads'],0,1000000000) and state['mode'] in ('still','animated','panorama','cubemap')
         and type(state['captureId']) is str and (state['captureId']=='' or re.fullmatch('snap_[0-9]{1,16}_[0-9]{1,10}',state['captureId']))
         and type(state['timerHandles']) is list and len(state['timerHandles'])<=256
         and all(integer(handle,1,2**31-1) for handle in state['timerHandles'])
         and state['timerHandles']==sorted(set(state['timerHandles'])))
    return bool(state['captureId'] or state['timerHandles'] or state['pendingUploads'] or state['overlaysHidden'])


def event(value,epoch,*,_combined=False):
    exact(value,{'sequence','capturedEpochMs','callerSequence','invokedEpochMs','event','closure','call','state'}|({'callerStackId'} if _combined else set()))
    if _combined:need(re.fullmatch('[a-f0-9]{32}',text(value['callerStackId'],32)))
    need(integer(value['sequence'],1,1000000000) and integer(value['callerSequence'],1,1000000000)
         and integer(value['capturedEpochMs'],1,epoch) and integer(value['invokedEpochMs'],1,value['capturedEpochMs'])
         and value['event'] in ('snapshot','entry','returned','finally','ending') and integer(value['call'],0,1000000000)
         and ((value['event'] in ('snapshot','ending'))==(value['call']==0 and value['closure']=='')))
    if value['call']:need(value['closure'] in CLOSURES)
    pending(value['state']);return value


def _member(value,epoch,*,_combined=False):
    membership(dict(complete=True,revision=1,managers=[value]),epoch)
    need(value['assigned'] and value['url'].endswith('/defaultScripts.js' if _combined else '/'+MAIN))


def _timers(value,epoch,previous=None,*,_combined=False,_after_original=None):
    exact(value,{'complete','revision','workers'})
    need(type(value['complete']) is bool and integer(value['revision']) and type(value['workers']) is list
         and len(value['workers'])<=128 and value['revision']>=len(value['workers']))
    ids=[];old={row['membership']['instance']:row for row in previous['workers']} if previous else {}
    for row in value['workers']:
        exact(row,{'membership','code','running','stopping','finished','done','codeSources','timerWork'})
        _member(row['membership'],epoch,_combined=_combined);ids.append(row['membership']['instance']);validate_code(row['code'],epoch)
        need(all(type(row[key]) is bool for key in ('running','stopping','finished','done')))
        prior=old.get(ids[-1]);code_sources(row['codeSources'],epoch,prior['codeSources'] if prior else None,_combined=_combined)
        if _combined:
            assigned=row['membership']['assignedEpochMs']
            if row['code']['submitted']:need(row['code']['submittedEpochMs']>=assigned)
            need(all(entry['submittedEpochMs']>=assigned for entry in row['codeSources']['evaluations']))
            timer_work(row['timerWork'],epoch,prior['timerWork'] if prior else None,schema='snapshotCombinedTimerWorkVersion',
                suffixes=('/system/snapshot.js','/system/snapshot/featureSnapshotWork.js'),_combined=True,code=row['codeSources']['evaluations'])
        else:timer_work(row['timerWork'],epoch,prior['timerWork'] if prior else None,schema='snapshotTimerWorkVersion',suffixes=TIMER_SUFFIXES)
        if prior:
            need(same(prior['membership'],row['membership']) and (not prior['finished'] or row['finished']) and (not prior['done'] or row['done']))
            if not _combined or prior['code']['submitted']:need(same(prior['code'],row['code']))
            elif row['code']['submitted']:need(integer(_after_original,1) and row['code']['submittedEpochMs']>=_after_original)
            else:need(same(prior['code'],row['code']))
            if _combined:
                need(integer(_after_original,1) and all(entry['submittedEpochMs']>=_after_original
                    for entry in row['codeSources']['evaluations'][len(prior['codeSources']['evaluations']):]))
    need(ids==sorted(set(ids)))
    if previous:
        need((previous['complete'] or not value['complete']) and value['revision']>=previous['revision'])
        # The all-known native manager set retains old lifetimes, including
        # stopped managers; disappearance is not a weak-death observation.
        need(set(old)<=set(ids))
    return value


def validate(value,query,pid,epoch=None,previous=None,*,_combined=False):
    command(query,_combined=_combined);marker='iosSnapshotCombinedWorkVersion' if _combined else 'iosSnapshotWorkVersion'
    exact(value,{marker,'requestId','runId','instance','sequence','processId',
                              'clockDomain','clockBefore','clockAfter','source'})
    need(type(value[marker]) is int and value[marker]==1
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid
         and re.fullmatch('[a-f0-9]{32}',text(value['instance'],32)) and integer(value['sequence'],1,1000000000)
         and value['clockDomain']==('native-main-snapshot-combined-work' if _combined else 'native-main-snapshot-work'))
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    before,after=value['clockBefore'],value['clockAfter'];delta=after['epochMs']-before['epochMs'];elapsed=after['monotonicMs']-before['monotonicMs']
    need(0<=delta<1500 and 0<=elapsed<1500 and abs(delta-elapsed)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','eventSequence','workers','timerSources'}|({'callerStacks'} if _combined else set()))
    need(type(source['complete']) is bool and integer(source['eventSequence'],0,1000000000)
         and type(source['workers']) is list and len(source['workers'])<=8)
    _timers(source['timerSources'],after['epochMs'],_combined=_combined)
    from ios.adapters import avatar_call_stack
    caller_table=avatar_call_stack.table(source['callerStacks'],after['epochMs'],_combined=True) if _combined else {};caller_histories={}
    ids=[];sequences=set()
    for row in source['workers']:
        exact(row,{'sourceUrl','manager','code','codeSources','calls','events','ended','state','latest'})
        _member(row['manager'],after['epochMs'],_combined=_combined);ids.append(row['manager']['instance'])
        expected=row['manager']['url'][:-len('defaultScripts.js')]+MAIN if _combined else row['manager']['url']
        need(row['sourceUrl']==expected and type(row['ended']) is bool)
        validate_code(row['code'],after['epochMs']);code_sources(row['codeSources'],after['epochMs'],_combined=_combined);need(row['code']['submitted'])
        if _combined:
            need(row['code']['submittedEpochMs']>=row['manager']['assignedEpochMs'] and all(
                item['submittedEpochMs']>=row['manager']['assignedEpochMs'] for item in row['codeSources']['evaluations']))
            main=[item for item in row['codeSources']['evaluations'] if item['url']==row['manager']['url']]
            need(main and all(all(item[key]==row['code'][key] for key in ('encoding','codeUnits','sha256')) and item['submittedEpochMs']>=row['code']['submittedEpochMs'] for item in main))
        def check_caller(entry,initial=False):
            if not _combined:return
            need(entry['callerStackId'] in caller_table);original=caller_table[entry['callerStackId']]
            required={'/system/snapshot/featureSnapshotWork.js'}|({'/system/snapshot.js'} if initial else set())
            avatar_call_stack.validate(original['callerStack'],original['callerModules'],entry['capturedEpochMs'],required=required,_combined=True)
            avatar_call_stack.evaluated(original['callerStack'],original['callerModules'],after['epochMs'],row['codeSources']['evaluations'],
                required=required,top='/system/snapshot/featureSnapshotWork.js',_combined=True)
            caller_histories.setdefault(row['manager']['instance'],avatar_call_stack.History()).accept(original['callerStack'])
        events=row['events'];need(type(events) is list and 1<=len(events)<=512 and events[0]['event']=='snapshot')
        stack=[];last_call=cursor=caller=stamp=0;ended=False
        for entry in events:
            event(entry,after['epochMs'],_combined=_combined);check_caller(entry,entry is events[0])
            need(not ended and entry['sequence']>cursor and entry['callerSequence']>caller and entry['capturedEpochMs']>=stamp
                 and entry['sequence'] not in sequences and entry['sequence']<=source['eventSequence'])
            sequences.add(entry['sequence']);cursor,caller,stamp=(entry[key] for key in ('sequence','callerSequence','capturedEpochMs'))
            if entry['event']=='entry':
                need(entry['call']>last_call);last_call=entry['call'];stack.append(dict(call=last_call,closure=entry['closure'],returned=False))
            elif entry['event'] in ('returned','finally'):
                need(stack and stack[-1]['call']==entry['call'] and stack[-1]['closure']==entry['closure'])
                if entry['event']=='returned':need(not stack[-1]['returned']);stack[-1]['returned']=True
                else:stack.pop()
            elif entry['event']=='ending':need(not stack);ended=True
        need(same(stack,row['calls']) and len(stack)<=32)
        latest=event(row['latest'],after['epochMs'],_combined=_combined);check_caller(latest);need(cursor<=latest['sequence']<=source['eventSequence']
            and latest['callerSequence']>=caller and latest['capturedEpochMs']>=stamp and same(latest['state'],row['state'])
            and row['ended']==ended and row['ended']==(latest['event']=='ending'))
        if latest['sequence']==cursor:need(same(latest,events[-1]))
        else:
            need(not ended and latest['event']=='snapshot' and latest['callerSequence']>caller
                 and same(latest['state'],events[-1]['state']) and latest['sequence'] not in sequences)
            sequences.add(latest['sequence'])
    need(ids==sorted(set(ids)) and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid,_combined=_combined)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
             and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
             and source['eventSequence']>=previous['source']['eventSequence'] and (previous['source']['complete'] or not source['complete']))
        _timers(source['timerSources'],after['epochMs'],previous['source']['timerSources'],_combined=_combined,
            _after_original=previous['clockBefore']['epochMs'] if _combined else None)
        if _combined:
            old=previous['source']['callerStacks'];need(len(source['callerStacks'])>=len(old) and same(source['callerStacks'][:len(old)],old))
        current={row['manager']['instance']:row for row in source['workers']}
        for old in previous['source']['workers']:
            need(old['manager']['instance'] in current);new=current[old['manager']['instance']]
            need(all(same(old[key],new[key]) for key in ('sourceUrl','manager','code'))
                 and same(new['events'][:len(old['events'])],old['events']) and new['latest']['sequence']>=old['latest']['sequence']
                 and (not old['ended'] or same(old,new)))
            need(all(entry['sequence']>old['latest']['sequence'] and entry['callerSequence']>old['latest']['callerSequence']
                     and entry['capturedEpochMs']>=old['latest']['capturedEpochMs'] for entry in new['events'][len(old['events']):]))
            if new['latest']['sequence']==old['latest']['sequence']:need(same(old['latest'],new['latest']))
            code_sources(new['codeSources'],after['epochMs'],old['codeSources'],_combined=_combined)
    return value


def original(value,*,_combined=False):
    return validate(value,dict(schemaVersion=1,action='feature-ios-snapshot-combined-work' if _combined else ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'),_combined=_combined)


def admit(value,scripts_root,*,quiet=False,_combined=False):
    original(value,_combined=_combined);root=root_url(scripts_root);source=value['source']
    need(source['complete'] and source['timerSources']['complete'])
    path=PIN_FILE.with_name('snapshot-combined-work-source-pins.v1.json') if _combined else PIN_FILE
    marker='snapshotCombinedWorkSourcePinsVersion' if _combined else 'snapshotWorkSourcePinsVersion'
    pins=json.loads(path.read_text());exact(pins,{marker,'encoding','sources'})
    need(type(pins[marker]) is int and pins[marker]==1
         and pins['encoding']=='utf-16le-code-units' and set(pins['sources'])==(set(COMBINED_FILES) if _combined else {MAIN,HELPER}))
    live=[row for row in source['workers'] if not row['ended']];need(len(live)==1);row=live[0]
    main='defaultScripts.js' if _combined else MAIN
    need(row['sourceUrl']==root+MAIN and row['manager']['url']==root+main and all(row['code'][key]==pins['sources'][main][key] for key in ('sha256','codeUnits'))
         and row['state']['nativeReview'] and row['codeSources']['complete'])
    fresh(row['latest']['capturedEpochMs'],value['clockAfter']['epochMs'])
    for path in (COMBINED_FILES if _combined else (MAIN,HELPER)):
        evaluations=[entry for entry in row['codeSources']['evaluations'] if entry['url']==root+path]
        need(len(evaluations)==1 and all(evaluations[0][key]==pins['sources'][path][key] for key in ('codeUnits','sha256')))
    native=[entry for entry in source['timerSources']['workers'] if entry['membership']['instance']==row['manager']['instance']]
    need(len(native)==1);native=native[0]
    need(same(native['membership'],row['manager']) and same(native['code'],row['code'])
         and same(native['codeSources'],row['codeSources']) and native['running']
         and not any(native[key] for key in ('stopping','finished','done')) and native['timerWork']['complete'])
    if _combined:
        from ios.adapters.avatar_call_stack import History
        history=History();callers={entry['id']:entry for entry in source['callerStacks']}
        for entry in row['events']+[row['latest']]:history.accept(callers[entry['callerStackId']]['callerStack'])
        for entry in native['timerWork']['callerStacks']:history.accept(entry['callerStack'])
    if quiet:
        need(not row['calls'] and not pending(row['state']))
        # No timer may be retired while its native timerFired stack is still
        # pending, even when a singleShot's QObject has already been destroyed.
        need(all(timer['destroyedEpochMs'] is not None and timer['depth']==timer['pendingDispatch']==0
                 for timer in native['timerWork']['timers']))
    return deepcopy(row)


class IOSSnapshotWork(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotWorkAcquisitionVersion'
