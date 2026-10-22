"""Actual Qt pointer dispatch/contact originals, independent of release ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-pointer-state'
FILE=ACTION+'.json'
LIMIT=1048576
KINDS=('mouse-press','mouse-double','mouse-release','mouse-move','touch-begin','touch-update','touch-end','touch-cancel')
ROW={'id','batch','kind','device','target','qtTimestamp','button','buttons','mouseSource','position','points',
     'enteredSequence','enteredEpochMs','enteredMonotonicMs','returnedSequence','returnedEpochMs','returnedMonotonicMs','deliveryResult',
     'finallySequence','finallyEpochMs','finallyMonotonicMs'}
CONTACT={'kind','device','point','target','startDispatch','bornEpochMs'}


def nonce(value):need(type(value) is str and re.fullmatch('[a-f0-9]{32}',value));return value


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    nonce(value['runId']);return value


def point_position(value):need(type(value) is list and len(value)==2 and all(number(v,-1e7,1e7) for v in value));return value


def source(value,epoch):
    exact(value,{'iosPointerSourceVersion','instance','bornEpochMs','complete','startup','eventSequence','events','dispatches',
        'pendingDispatches','contacts','ends','devices','targets','qtMouseButtons','worldTapActive'})
    need(type(value['iosPointerSourceVersion']) is int and value['iosPointerSourceVersion']==1 and integer(value['bornEpochMs'],1,epoch)
        and type(value['complete']) is bool and type(value['worldTapActive']) is bool and integer(value['qtMouseButtons'],0,0x7ffffff))
    nonce(value['instance']);startup=value['startup'];exact(startup,{'observed','epochMs','monotonicMs','windowCount','mouseButtons'})
    need(type(startup['observed']) is bool)
    if startup['observed']:
        need(integer(startup['epochMs'],value['bornEpochMs'],epoch) and integer(startup['monotonicMs'],0)
            and integer(startup['windowCount'],0,10000) and integer(startup['mouseButtons'],0,0x7ffffff))
    else:need(startup==dict(observed=False,epochMs=0,monotonicMs=0,windowCount=-1,mouseButtons=-1))
    complete=startup['observed'] and startup['windowCount']==startup['mouseButtons']==0
    lookup={}
    for name,maximum in (('devices',16),('targets',64)):
        rows=value[name];need(type(rows) is list and len(rows)<=maximum);table={}
        for row in rows:
            exact(row,{'id','bornEpochMs','alive'}|({'deviceType'} if name=='devices' else {'className'}));nonce(row['id'])
            need(row['id'] not in table and integer(row['bornEpochMs'],value['bornEpochMs'],epoch) and type(row['alive']) is bool)
            if name=='devices':need(integer(row['deviceType'],1,65536))
            else:need(type(row['className']) is str and 1<=len(row['className'])<=256)
            table[row['id']]=row
        lookup[name]=table
    rows=value['dispatches'];need(type(rows) is list and len(rows)<=1024);dispatches={};last_entered=0
    for row in rows:
        exact(row,ROW);nonce(row['id']);nonce(row['batch'])
        need(row['id'] not in dispatches and row['kind'] in KINDS and row['device'] in lookup['devices'] and row['target'] in lookup['targets']
            and integer(row['qtTimestamp'],0,2**53-1) and integer(row['button'],0,0x7ffffff) and integer(row['buttons'],0,0x7ffffff)
            and integer(row['mouseSource'],0,3) and integer(row['enteredSequence'],last_entered+1,3072))
        need(integer(row['enteredEpochMs'],max(startup['epochMs'],lookup['devices'][row['device']]['bornEpochMs'],lookup['targets'][row['target']]['bornEpochMs']),epoch)
            and integer(row['enteredMonotonicMs'],startup['monotonicMs']))
        last_entered=row['enteredSequence'];dispatches[row['id']]=row
        for kind in ('returned','finally'):
            need(integer(row[kind+'Sequence'],0,3072))
            if row[kind+'Sequence']:
                need(row[kind+'Sequence']>row['enteredSequence'] and integer(row[kind+'EpochMs'],row['enteredEpochMs'],epoch)
                    and integer(row[kind+'MonotonicMs'],row['enteredMonotonicMs']))
            else:need(row[kind+'EpochMs']==row[kind+'MonotonicMs']==0)
        need((type(row['deliveryResult']) is bool) if row['returnedSequence'] else row['deliveryResult'] is None)
        if row['returnedSequence'] and row['finallySequence']:need(row['finallySequence']>row['returnedSequence'])
        if row['kind'].startswith('mouse-'):
            point_position(row['position']);need(row['points']==[])
            if row['kind']=='mouse-move':need(row['button']==0)
        else:
            need(row['position']==[] and row['button']==row['buttons']==row['mouseSource']==0 and type(row['points']) is list and len(row['points'])<=16)
            points=set()
            for point in row['points']:
                exact(point,{'id','state','position'});point_position(point['position'])
                need(integer(point['id'],0,2**31-1) and point['id'] not in points and type(point['state']) is int and point['state'] in (1,2,4,8));points.add(point['id'])
    events=value['events'];need(type(events) is list and len(events)<=3072 and value['eventSequence']==len(events) and type(value['eventSequence']) is int)
    active={};batches={};contacts={};ends=[];previous_epoch=value['bornEpochMs'];previous_mono=0
    def end(key,row):
        nonlocal complete
        if key not in contacts:complete=False;return
        contact=contacts.pop(key);ends.append(dict(contact,endDispatch=row['id']))
    def apply(row):
        nonlocal complete
        device,kind=row['device'],row['kind']
        def add(key,channel,point):
            nonlocal complete
            if key in contacts or len(contacts)>=32:complete=False;return
            contacts[key]=dict(kind=channel,device=device,point=point,target=row['target'],startDispatch=row['id'],bornEpochMs=row['enteredEpochMs'])
        if kind.startswith('mouse-'):
            button,buttons=row['button'],row['buttons'];key=(device,'mouse',button)
            if kind in ('mouse-press','mouse-double'):
                if button<=0 or not buttons&button:complete=False
                else:add(key,'mouse',button)
            elif kind=='mouse-release':
                if button<=0 or buttons&button:complete=False
                else:end(key,row)
            observed=0
            for d,channel,point in contacts:
                if d==device and channel=='mouse':observed|=point
            if observed!=buttons:complete=False
            return
        if kind=='touch-cancel':
            for key in sorted(contacts,key=lambda k:k[0]+':'+k[1]+':'+str(k[2])):
                if key[0]==device and key[1]=='touch':end(key,row)
            return
        for point in row['points']:
            key=(device,'touch',point['id'])
            if point['state']==1:add(key,'touch',point['id'])
            elif point['state']==8:end(key,row)
            elif key not in contacts:complete=False
        if kind=='touch-begin' and not row['points']:complete=False
        if kind=='touch-end' and any(k[0]==device and k[1]=='touch' for k in contacts):complete=False
    for index,event in enumerate(events,1):
        exact(event,{'sequence','dispatch','kind','epochMs','monotonicMs'})
        need(type(event['sequence']) is int and event['sequence']==index and event['dispatch'] in dispatches and event['kind'] in ('entered','returned','finally')
            and integer(event['epochMs'],previous_epoch,epoch) and integer(event['monotonicMs'],previous_mono))
        if index>1:need(abs(event['epochMs']-previous_epoch-event['monotonicMs']+previous_mono)<=250)
        previous_epoch,previous_mono=event['epochMs'],event['monotonicMs'];row=dispatches[event['dispatch']];kind=event['kind']
        need(row[kind+'Sequence']==index and row[kind+'EpochMs']==event['epochMs'] and row[kind+'MonotonicMs']==event['monotonicMs'])
        if kind=='entered':
            need(row['id'] not in active);active[row['id']]=False;batch=batches.get(row['batch'])
            if batch is None:batches[row['batch']]=dict(first=row,active=1);apply(row)
            else:
                need(batch['active']>0 and all(same(batch['first'][key],row[key]) for key in ('kind','device','qtTimestamp','button','buttons','mouseSource','position','points')))
                batch['active']+=1
        elif kind=='returned':need(row['id'] in active and active[row['id']] is False);active[row['id']]=True
        else:
            need(row['id'] in active)
            if not active.pop(row['id']):complete=False
            batch=batches[row['batch']];batch['active']-=1
    for row in rows:
        for kind in ('entered','returned','finally'):
            if row[kind+'Sequence']:need(row[kind+'Sequence']<=len(events) and events[row[kind+'Sequence']-1]['dispatch']==row['id'] and events[row[kind+'Sequence']-1]['kind']==kind)
    need(type(value['pendingDispatches']) is int and value['pendingDispatches']==len(active)
        and same(value['contacts'],[contacts[k] for k in sorted(contacts,key=lambda k:k[0]+':'+k[1]+':'+str(k[2]))]) and same(value['ends'],ends)
        and (not value['complete'] or complete))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosPointerStateVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosPointerStateVersion']) is int and value['iosPointerStateVersion']==1 and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1) and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-main-ios-pointer');nonce(value['instance'])
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs'];need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source(value['source'],after['epochMs'])
    if previous is not None:
        original(previous);old,new=previous['source'],value['source']
        need(value['runId']==previous['runId'] and value['processId']==previous['processId'] and value['instance']==previous['instance']
            and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'] and all(before[k]>=previous['clockAfter'][k] for k in before)
            and old['instance']==new['instance'] and old['bornEpochMs']==new['bornEpochMs'] and same(old['startup'],new['startup'])
            and (old['complete'] or not new['complete']) and same(new['events'][:len(old['events'])],old['events']) and len(new['events'])>=len(old['events']))
        need(len(new['dispatches'])>=len(old['dispatches'])
            and all(row['epochMs']>=previous['clockAfter']['epochMs'] for row in new['events'][len(old['events']):]))
        for a,b in zip(old['dispatches'],new['dispatches']):
            static=ROW-{key for kind in ('returned','finally') for key in (kind+'Sequence',kind+'EpochMs',kind+'MonotonicMs')}-{'deliveryResult'}
            need(all(same(a[k],b[k]) for k in static))
            for kind in ('returned','finally'):
                if a[kind+'Sequence']:need(all(a[kind+k]==b[kind+k] for k in ('Sequence','EpochMs','MonotonicMs')))
            if a['returnedSequence']:need(a['deliveryResult']==b['deliveryResult'])
        for key in ('devices','targets'):
            need(len(new[key])>=len(old[key]))
            for a,b in zip(old[key],new[key]):need(all(same(a[k],b[k]) for k in a if k!='alive') and (a['alive'] or not b['alive']))
        need(len(new['ends'])>=len(old['ends']) and same(new['ends'][:len(old['ends'])],old['ends']))
    return value


def original(value):return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def drained(before,current,*,after_epoch,require_delivery=False):
    original(before);validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=ACTION,runId=current['runId']),before['processId'],previous=before)
    need(type(require_delivery) is bool and integer(after_epoch,1,current['clockBefore']['epochMs']))
    for packet in (before,current):
        state=packet['source'];need(state['complete'] and state['startup']['observed'])
    state=current['source'];need(state['pendingDispatches']==0 and state['contacts']==[] and state['qtMouseButtons']==0 and state['worldTapActive'] is False)
    if require_delivery:
        new={row['id']:row for row in state['dispatches'][len(before['source']['dispatches']):]}
        need(any(row['startDispatch'] in new and row['endDispatch'] in new and new[row['startDispatch']]['enteredEpochMs']>=after_epoch
            and new[row['endDispatch']]['returnedSequence']>0 and new[row['endDispatch']]['finallySequence']>0 for row in state['ends']))
    return dict(iosPointerDrainVersion=1,sourceInstance=state['instance'],eventSequence=state['eventSequence'],nativeEpochMs=current['clockAfter']['epochMs'])


def delivered(before,current,*,kind,position: list,after_epoch):
    need(kind in ('touch','mouse'));wanted=position;point_position(wanted)
    drained(before,current,after_epoch=after_epoch,require_delivery=True)
    old=before['source'];new=current['source'];rows={row['id']:row for row in new['dispatches'][len(old['dispatches']):]};matches=[]
    for end in new['ends'][len(old['ends']):]:
        if end['kind']!=kind or end['startDispatch'] not in rows or end['endDispatch'] not in rows:continue
        first,last=rows[end['startDispatch']],rows[end['endDispatch']]
        if first['enteredEpochMs']<after_epoch:continue
        points=[first['position']] if kind=='mouse' else [row['position'] for row in first['points'] if row['id']==end['point'] and row['state']==1]
        if len(points)==1 and all(abs(a-b)<=1 for a,b in zip(points[0],wanted)):
            need(first['returnedSequence'] and first['finallySequence'] and last['returnedSequence'] and last['finallySequence']);matches.append(deepcopy(end))
    need(len(matches)==1);return matches[0]


class IOSPointerState(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosPointerStateAcquisitionVersion'
    _limit=LIMIT
