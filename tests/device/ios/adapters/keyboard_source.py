"""Original UIKit notification/responder history, separate from Qt IME hints.

Unknown, transitioning or foreign-window keyboard state is never absence.
Native compilation and actual iOS keyboard behavior remain unverified here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-keyboard'
FILE=ACTION+'.json'
LIMIT=524288
KINDS={'will-show','did-show','will-hide','did-hide','will-change-frame','did-change-frame'}


def identifier(value):need(type(value) is str and re.fullmatch('[a-f0-9]{32}',value) is not None)
def sha(value):need(type(value) is str and re.fullmatch('[a-f0-9]{64}',value) is not None)


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) is not None)
    identifier(value['runId']);return value


def clock(value,*,floor=None,ceiling=None):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))
    if floor is not None:
        need(value['epochMs']>=floor['epochMs'] and value['monotonicMs']>=floor['monotonicMs']
            and abs(value['epochMs']-floor['epochMs']-value['monotonicMs']+floor['monotonicMs'])<=250)
    if ceiling is not None:need(value['epochMs']<=ceiling['epochMs'] and value['monotonicMs']<=ceiling['monotonicMs'])


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosKeyboardVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosKeyboardVersion']) is int and value['iosKeyboardVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['sequence'],1) and value['clockDomain']=='native-main-ios-keyboard')
    identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];exact(source,{'registered','complete','ownerAlive','applicationActive','events','objects','windows'})
    registered=source['registered'];clock(registered,ceiling=a)
    for key in ('complete','ownerAlive','applicationActive'):need(type(source[key]) is bool)
    need(type(source['objects']) is list and len(source['objects'])<=128
        and type(source['events']) is list and len(source['events'])<=256
        and type(source['windows']) is list and len(source['windows'])<=64)
    objects={}
    for row in source['objects']:
        exact(row,{'id','kind','born','expired','alive'});identifier(row['id'])
        need(row['id'] not in objects and type(row['kind']) is str and row['kind'] in ('window','responder') and type(row['alive']) is bool)
        clock(row['born'],floor=registered,ceiling=b)
        if row['expired'] is None:need(row['alive'])
        else:clock(row['expired'],floor=row['born'],ceiling=b);need(not row['alive'])
        objects[row['id']]=row
    seen=set();last=registered
    for index,row in enumerate(source['events'],1):
        exact(row,{'sequence','eventId','kind','clock','local','screenMatches','window','geometrySha256','frame'})
        need(type(row['sequence']) is int and row['sequence']==index and type(row['kind']) is str and row['kind'] in KINDS)
        identifier(row['eventId']);need(row['eventId'] not in seen);seen.add(row['eventId'])
        clock(row['clock'],floor=last,ceiling=b);last=row['clock']
        for key in ('local','screenMatches'):need(row[key] is None or type(row[key]) is bool)
        exact(row['frame'],{'valid','intersectsWindow'});need(type(row['frame']['valid']) is bool)
        need(type(row['frame']['intersectsWindow']) is bool if row['frame']['valid'] else row['frame']['intersectsWindow'] is None)
        if row['window'] is None:need(row['geometrySha256'] is None and row['screenMatches'] is None and not row['frame']['valid'])
        else:
            identifier(row['window']);need(row['window'] in objects and objects[row['window']]['kind']=='window')
            clock(row['clock'],floor=objects[row['window']]['born']);sha(row['geometrySha256'])
    windows=set()
    for row in source['windows']:
        exact(row,{'id','key','visible','sceneActive','geometrySha256','responder'});identifier(row['id'])
        need(row['id'] not in windows and row['id'] in objects and objects[row['id']]['kind']=='window' and objects[row['id']]['alive'])
        windows.add(row['id']);sha(row['geometrySha256'])
        for key in ('key','visible','sceneActive'):need(type(row[key]) is bool)
        if row['responder'] is not None:
            actual=row['responder'];exact(actual,{'id','className'});identifier(actual['id'])
            need(actual['id'] in objects and objects[actual['id']]['alive']
                and type(actual['className']) is str and 1<=len(actual['className'])<=256
                and all(ord(c)>=32 and ord(c)!=127 for c in actual['className']))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        clock(a,floor=previous['clockAfter']);old=previous['source']
        need(same(source['registered'],old['registered']) and same(source['events'][:len(old['events'])],old['events'])
            and len(source['objects'])>=len(old['objects']) and (old['complete'] or not source['complete'])
            and (old['ownerAlive'] or not source['ownerAlive']))
        for old_row,new_row in zip(old['objects'],source['objects']):
            need(all(same(old_row[key],new_row[key]) for key in ('id','kind','born')))
            if old_row['expired'] is not None:need(same(old_row,new_row))
    return value


def measured(value):
    """Return only a settled own-window OS result; a missing event is unknown."""
    query=dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId'])
    validate(value,query,value['processId']);source=value['source']
    need(source['complete'] and source['ownerAlive'] and source['applicationActive'] and source['events'])
    windows=[row for row in source['windows'] if row['key'] and row['visible'] and row['sceneActive']];need(len(windows)==1)
    window=windows[0];event=source['events'][-1]
    need(event['window']==window['id'] and event['geometrySha256']==window['geometrySha256']
        and event['local'] is True and event['screenMatches'] is not False)
    if event['kind']=='did-hide':visible=False
    else:
        need(event['kind'] in ('did-show','did-change-frame') and event['frame']['valid'])
        visible=event['frame']['intersectsWindow']
    return deepcopy(dict(keyboard=visible,windowId=window['id'],responder=window['responder'],notification=event))


class IOSKeyboard(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosKeyboardAcquisitionVersion'
