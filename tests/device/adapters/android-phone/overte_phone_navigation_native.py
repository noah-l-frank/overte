"""Original Places page/model/storage and token-bound ordinary Qt input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_roots import NativeScriptRoots
from overte_phone_script_files import PhoneScriptFileIO,nonce

VIEW_FILE='phone-navigation-view.json'
UI_FILE='phone-navigation-ui.json'
VIEW_ACTION='phone-navigation-view-observe'
CONTROL=re.compile(r'navigation\.(?:entry|page|placesTab|bookmarksTab|serversTab|refreshPlaces|addBookmark|maturityFilters|addServer|placesSearch|bookmarkName|bookmark\.(?:save|cancel)|error\.ok|rating_(?:everyone|teen|mature|adult|unrated)|(?:visitPlace|visitBookmark|renameBookmark|deleteBookmark|fetchServer|pinServer)\.(?:0|[1-9][0-9]{0,2}))')


def text(value,limit):return type(value) is str and len(value)<=limit and all(ord(c)>=32 and ord(c)!=127 for c in value)


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==VIEW_ACTION
        and nonce(value['commandId']) and nonce(value['runId']))
    return value


def validate(value,request,pid,epoch,*,previous=None):
    command(request)
    exact(value,{'navigationViewVersion','commandId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['navigationViewVersion']) is int and value['navigationViewVersion']==1
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1,1000000000) and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<=1500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'tabletShown','ui','storage','preferences','endpoint','protocolSignature','keyboard'})
    need(type(source['tabletShown']) is bool and text(source['endpoint'],512) and text(source['protocolSignature'],24))
    keyboard=source['keyboard'];exact(keyboard,{'available','backend','visible'})
    need(keyboard['available'] is True and keyboard['backend']=='native-touch-metrics' and type(keyboard['visible']) is bool)
    storage=source['storage'];exact(storage,{'present','sha256','bytes','bookmarks'})
    need(type(storage['present']) is bool and type(storage['sha256']) is str and re.fullmatch('[0-9a-f]{64}',storage['sha256'])
        and integer(storage['bytes'],0,262144) and type(storage['bookmarks']) is dict and len(storage['bookmarks'])<=1000
        and all(text(k,256) and text(v,4096) for k,v in storage['bookmarks'].items())
        and (storage['present'] or storage['bytes']==0 and storage['bookmarks']=={}))
    prefs=source['preferences'];exact(prefs,{'placesAppMetaverseToFetch','placesAppPinnedMetaverse','placesAppMaturityFilter','private/places/federation'})
    for pref in prefs.values():
        exact(pref,{'present','value'});need(type(pref['present']) is bool)
        need(pref['value'] is None or type(pref['value']) in (list,str,dict))
    ui=source['ui'];fields={'present','addressDialog','notFoundModal','bookmarkDialog','pendingCommands','activeTimers','notFound'}
    need(type(ui) is dict and type(ui.get('present')) is bool)
    exact(ui,fields|({'generation','source','query','records','model','servers','loading','maturity','currentAddress'} if ui['present'] else set()))
    need(all(type(ui[k]) is bool for k in ('present','addressDialog','notFoundModal','bookmarkDialog')) and integer(ui['pendingCommands'],0,128) and integer(ui['activeTimers'],0,16))
    if ui['notFoundModal']:
        exact(ui['notFound'],{'modalId','createdEpochMs','nativeEvent'})
        need(nonce(ui['notFound']['modalId']) and integer(ui['notFound']['createdEpochMs'],1,value['capturedEpochMs']) and type(ui['notFound']['nativeEvent']) is dict)
    else:need(ui['notFound']=={})
    if ui['present']:
        need(source['tabletShown'] and nonce(ui['generation']) and text(ui['source'],4096)
            and ui['source'].endswith('/scripts/system/places/PicoPlaces.qml') and text(ui['query'],4096)
            and type(ui['loading']) is bool and text(ui['currentAddress'],4096)
            and type(ui['records']) is list and len(ui['records'])<=1000 and all(type(v) is dict for v in ui['records'])
            and type(ui['model']) is list and len(ui['model'])<=1000 and type(ui['servers']) is list and len(ui['servers'])<=1000
            and type(ui['maturity']) is list and len(ui['maturity'])<=5 and len(set(ui['maturity']))==len(ui['maturity'])
            and set(ui['maturity'])<={'everyone','teen','mature','adult','unrated'})
        for row in ui['model']:
            exact(row,{'placeId','placeName','placeAddress'});need(all(text(v,4096) for v in row.values()))
        for row in ui['servers']:
            exact(row,{'serverUrl','serverIndex','fetched','pinned','failed'})
            need(text(row['serverUrl'],4096) and integer(row['serverIndex'],0,999) and all(type(row[k]) is bool for k in ('fetched','pinned','failed')))
    if previous is not None:
        validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action=VIEW_ACTION,runId=previous['runId']),pid,previous['capturedEpochMs'])
        need(value['runId']==previous['runId'] and value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['requestedEpochMs']>=previous['capturedEpochMs'])
    return value


class PhoneNavigationView(NativeScriptRoots):
    """Reuse the bounded existing original-read transport and freshness rules."""
    def read(self,run):
        barrier=self.clock_ms();request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=VIEW_ACTION,runId=run)
        value=self.exchange(request);validate(value,request,self.pid,self.clock_ms(),previous=self.last)
        need(value['requestedEpochMs']>=barrier and self.guard() is not False)
        self.last=deepcopy(value);return deepcopy(value)

    def exchange(self,request):
        import json
        from adapters.native_feature_observation import decode,number
        command(request);need(self.guard() is not False)
        start=previous=self.monotonic();need(number(start,0,1e15));self.send(deepcopy(request))
        for attempt in range(51):
            need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,previous,1e15) and now-start<5 and self.guard() is not False);previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:return value
            if attempt<50:self.sleep(.1)
        need(False)


def controls(value,request,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence','lastCommandSequence',
        'elapsedMs','capturedEpochMs','processId','navigationControlsVersion','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==request and value['action']=='observe'
        and nonce(value['instance']) and nonce(value['generation']) and integer(value['sourceSequence'],1)
        and integer(value['lastCommandSequence']) and integer(value['elapsedMs']) and type(value['processId']) is int and value['processId']==pid
        and type(value['navigationControlsVersion']) is int and value['navigationControlsVersion']==1 and value['ready'] is True
        and type(value['controls']) is list and len(value['controls'])<=384)
    fresh(value['capturedEpochMs'],epoch);ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict and type(row.get('id')) is str and CONTROL.fullmatch(row['id']) and nonce(row.get('token'))
            and row['id'] not in ids and row['token'] not in tokens and {'id','token','enabled','focused','inputReady'}<=set(row)
            and set(row)<={'id','token','enabled','focused','inputReady','text','dialogOriginalName','dialogAddress','checked','placeId','placeName','placeAddress','bookmarkName','bookmarkAddress','serverUrl','serverIndex'}
            and all(type(row[k]) is bool for k in ('enabled','focused','inputReady')))
        for key in set(row)-{'id','token','enabled','focused','inputReady','checked','serverIndex'}:need(text(row[key],4096))
        if 'checked' in row:need(type(row['checked']) is bool)
        if 'serverIndex' in row:need(integer(row['serverIndex'],0,999))
        ids.add(row['id']);tokens.add(row['token'])
    return value


class PhoneNavigationIO(PhoneScriptFileIO):
    wire_action='phone-navigation-ui'
    validate_capture=staticmethod(controls)
    def input(self,identifier,action,*,token,text_value=None):
        need(type(identifier) is str and CONTROL.fullmatch(identifier) and identifier!='navigation.page' and nonce(token)
            and action in ('activate','replace'))
        if action=='replace':need(identifier in ('navigation.placesSearch','navigation.bookmarkName') and type(text_value) is str
            and (text_value=='' or re.fullmatch('(?:e2e-|renamed-|hidden-)[0-9a-f]{32}',text_value)))
        else:need(text_value is None)
        value=self.capture();rows=[r for r in value['controls'] if r['id']==identifier];need(len(rows)==1)
        row=rows[0];need(row['token']==token and row['enabled'] and row['inputReady'] and (action!='replace' or row['focused']))
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,instance=value['instance'],generation=value['generation'],
            sequence=value['lastCommandSequence']+1,observedElapsedMs=value['elapsedMs'],controlId=identifier,controlToken=token)
        if action=='replace':request['text']=text_value
        self.deliver(request,value)
