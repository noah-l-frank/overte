"""Original held-inline native admission callable and issued-once fault receipts.

No fault request can provide replay bytes or an expected bridge result. Original
callback return, destruction and carrier/view retirement remain independent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters import tablet_web_source as native

VERSION=1
ACTION='feature-ios-tablet-web-deferred'
FAULT='feature-ios-tablet-web-defer'
FILE=ACTION+'.json'
FAULT_FILE=FAULT+'.json'
LIMIT=2097152
CLOCKS=('captured','delivering','returned','finally','discarded','expired','overdue')


def command(value,*,operation=False):
    need(type(value) is dict and type(operation) is bool and value.get('action')==(FAULT if operation else ACTION))
    original_=dict(value)
    if operation:
        need(value.get('operation') in ('arm','deliver','discard'));original_.pop('operation',None)
        if value['operation']!='arm':native.sources.identifier(value.get('recordId'));original_.pop('recordId',None)
    native.sources.command(dict(original_,action=native.sources.ACTION));return value


def envelope(value):
    need(type(value) is str and 0<len(value.encode())<=4096)
    def pairs(items):
        result={}
        for key,item in items:need(key not in result);result[key]=item
        return result
    outer=json.loads(value,object_pairs_hook=pairs,parse_constant=lambda _:need(False))
    need(type(outer) is dict and set(outer) in ({'type','object','method','args'},{'type','object','method','args','id'})
        and type(outer['type']) is int and outer['type']==6 and outer['object']=='eventBridge'
        and (integer(outer['method']) or outer['method'] in ('emitWebEvent','emitWebEvent(QVariant)'))
        and type(outer['args']) is list and len(outer['args'])==1 and type(outer['args'][0]) is str)
    if 'id' in outer:need(integer(outer['id']))
    body=json.loads(outer['args'][0],object_pairs_hook=pairs,parse_constant=lambda _:need(False));exact(body,{'contract','action','sequence'})
    need(body['contract']=='overte-web-parity-v1' and body['action']=='echo' and integer(body['sequence'],1,1000000))
    return body


def receipt(value,query,instance,ceiling):
    command(query,operation=True)
    exact(value,{'iosTabletWebDeferReceiptVersion','command','instance','sequence','issued','completed','status','record'})
    need(type(value['iosTabletWebDeferReceiptVersion']) is int and value['iosTabletWebDeferReceiptVersion']==VERSION
        and value['command']==query and value['instance']==instance and integer(value['sequence'],1)
        and value['status'] in ('issued','armed','refused','discarded','delivered'))
    native.sources.stamp(value['issued'],ceiling)
    if value['completed'] is None:need(value['status']=='issued')
    else:native.sources.stamp(value['completed'],ceiling,value['issued']);need(value['status']!='issued')
    if value['record'] is not None:native.sources.identifier(value['record'])
    if value['status'] in ('armed','discarded','delivered'):need(value['record'] is not None)
    if value['status'] not in ('issued','refused'):need({'armed':'arm','discarded':'discard','delivered':'deliver'}[value['status']]==query['operation'])
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletWebDeferredVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','failure','commandSequence','records','commands'})
    need(type(value['iosTabletWebDeferredVersion']) is int and value['iosTabletWebDeferredVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['sequence'],1) and integer(value['commandSequence']) and value['clockDomain']=='native-main-ios-tablet-web-deferred'
        and type(value['complete']) is bool and (value['failure'] is None or type(value['failure']) is str and 0<len(value['failure'])<=128)
        and type(value['records']) is list and len(value['records'])<=128 and type(value['commands']) is list and len(value['commands'])<=4096
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    if value['complete']:need(value['failure'] is None)
    native.sources.identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];native.sources.stamp(a);native.sources.stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    commands={};sequences=set();records={};occupied=0
    for item in value['commands']:
        need(type(item) is dict and type(item.get('command')) is dict);query_=item['command'];command(query_,operation=True)
        need(all(query_[k]==query[k] for k in ('runId','fixtureUrl')) and query_['commandId'] not in commands)
        receipt(item,query_,value['instance'],b);need(item['sequence']<=value['commandSequence'] and item['sequence'] not in sequences)
        commands[query_['commandId']]=item;sequences.add(item['sequence'])
    def associated(id_,operation):
        need(type(id_) is str and id_ in commands and commands[id_]['command']['operation']==operation);item=commands[id_]
        if operation!='arm':need(item['command']['recordId'] in {row['id'] for row in value['records']})
        return item
    for row in value['records']:
        exact(row,{'id','identity','armCommand','deliveryCommand','discardCommand','armed','bufferPending','callbackAlive','original',*CLOCKS})
        native.sources.identifier(row['id']);need(row['id'] not in records and type(row['bufferPending']) is bool and type(row['callbackAlive']) is bool)
        native.identity(row['identity'],dict(query,action=native.ACTION));ref=row['identity']['source']
        need(ref['carrier'] is not None and ref['binding'] is not None);native.sources.stamp(row['armed'],a)
        arm=associated(row['armCommand'],'arm');need(arm['record']==row['id'] and arm['status']=='armed')
        native.sources.stamp(row['armed'],arm['completed'],arm['issued'])
        for key in CLOCKS:
            if row[key] is not None:native.sources.stamp(row[key],b,row['armed'])
        if row['original'] is None:
            need(row['captured'] is None and not row['bufferPending'] and not row['callbackAlive']
                and all(row[k] is None for k in ('delivering','returned','finally','expired')))
        else:
            raw=row['original'];exact(raw,{'envelope','envelopeSha256','nonce','frame','mainFrame','generation'})
            envelope(raw['envelope']);need(hashlib.sha256(raw['envelope'].encode()).hexdigest()==raw['envelopeSha256']
                and raw['nonce']==row['identity']['nonce'] and raw['frame']==row['identity']['url'] and raw['mainFrame'] is True
                and type(raw['generation']) is int and raw['generation']==row['identity']['grant'] and row['captured'] is not None)
            need(row['captured']['monotonicMs']-row['armed']['monotonicMs']<30000)
            if row['delivering'] is None and row['discarded'] is None:need(row['bufferPending'] and row['callbackAlive'])
            else:need(not row['bufferPending'])
            if row['expired'] is None:need(row['callbackAlive'])
            else:
                need(not row['callbackAlive']);native.sources.stamp(row['expired'],b,row['finally'] or row['discarded'] or row['captured'])
        if row['deliveryCommand'] is not None:
            delivered=associated(row['deliveryCommand'],'deliver');need(delivered['command']['recordId']==row['id']);need(row['delivering'] is not None and row['original'] is not None and row['discarded'] is None)
            native.sources.stamp(row['delivering'],delivered['completed'] or b,delivered['issued'])
            if delivered['status']!='issued':need(delivered['record']==row['id'] and delivered['status']=='delivered')
        else:need(row['delivering'] is None and row['returned'] is None and row['finally'] is None)
        if row['returned'] is not None:
            need(row['finally'] is not None);native.sources.stamp(row['returned'],row['finally'],row['delivering'])
        if row['finally'] is not None:need(row['delivering'] is not None);native.sources.stamp(row['finally'],b,row['delivering'])
        if row['discardCommand'] is not None:
            discarded=associated(row['discardCommand'],'discard');need(discarded['command']['recordId']==row['id']);need(discarded['record']==row['id'] and discarded['status']=='discarded' and row['discarded'] is not None and row['deliveryCommand'] is None)
            native.sources.stamp(row['discarded'],discarded['completed'],discarded['issued'])
        else:need(row['discarded'] is None)
        if row['overdue'] is not None:need(not value['complete'] and row['overdue']['monotonicMs']-row['armed']['monotonicMs']>=30000)
        if row['bufferPending'] or row['callbackAlive'] or row['original'] is None and row['discarded'] is None and row['overdue'] is None:occupied+=1
        records[row['id']]=row
    need(occupied<=1)
    for item in commands.values():
        if item['record'] is not None:need(item['record'] in records)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and value['commandSequence']>=previous['commandSequence'] and (previous['complete'] or not value['complete'])
            and (previous['failure'] is None or value['failure']==previous['failure']) and len(value['records'])>=len(previous['records']))
        native.sources.stamp(a,floor=previous['clockAfter'])
        for index,old in enumerate(previous['records']):
            new=value['records'][index];need(all(new[k]==old[k] for k in ('id','identity','armCommand','armed')))
            for key in ('original','deliveryCommand','discardCommand',*CLOCKS):
                if old[key] is not None:need(new[key]==old[key])
                elif new[key] is not None and key in CLOCKS:native.sources.stamp(new[key],floor=previous['clockAfter'])
            if not old['callbackAlive'] and old['expired'] is not None:need(not new['callbackAlive'])
            if not old['bufferPending'] and old['captured'] is not None:need(not new['bufferPending'])
        for row in value['records'][len(previous['records']):]:native.sources.stamp(row['armed'],floor=previous['clockAfter'])
        for old in previous['commands']:
            need(old['command']['commandId'] in commands);new=commands[old['command']['commandId']]
            if old['status']!='issued':need(new==old)
            else:
                need(all(new[k]==old[k] for k in ('command','instance','sequence','issued')))
                if new['completed'] is not None:native.sources.stamp(new['completed'],floor=previous['clockAfter'])
        old_ids={item['command']['commandId'] for item in previous['commands']}
        for item in value['commands']:
            if item['command']['commandId'] not in old_ids:native.sources.stamp(item['issued'],floor=previous['clockAfter']);need(item['sequence']>previous['commandSequence'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join_sources(value,sources,transcript):
    """Original verified frame and live-at-arm/capture carrier provenance."""
    original(value);native.join_sources(transcript,sources)
    need(value['complete'] and all(value[k]==sources[k]==transcript[k] for k in ('runId','fixtureUrl','processId')))
    carriers={row['id']:row for row in sources['carriers']}
    for row in value['records']:
        for kind in ('native-finished','document-verified'):
            need(any(event['kind']==kind and event['identity']==row['identity'] and event['clock']['epochMs']<=row['armed']['epochMs'] for event in transcript['events']))
        ref=row['identity']['source'];need(ref['carrier'] in carriers);carrier=carriers[ref['carrier']]
        bindings=[item for item in carrier['bindings'] if item['id']==ref['binding']];need(len(bindings)==1)
        last=(row['captured'] or row['armed'])['epochMs']
        for item,key in ((carrier,'retired'),(carrier,'destroyed'),(bindings[0],'revoked')):
            if key in item:need(last<=item[key]['epochMs'])
    return deepcopy(value)


def held(value):
    original(value);need(value['complete']);rows=[row for row in value['records'] if row['bufferPending']]
    need(len(rows)==1 and rows[0]['original'] is not None and rows[0]['callbackAlive']);return deepcopy(rows[0])


def drained(admitted,current):
    original(admitted);validate(current,dict(schemaVersion=1,action=ACTION,commandId=current['commandId'],runId=current['runId'],fixtureUrl=current['fixtureUrl']),current['processId'],previous=admitted)
    need(admitted['complete'] and current['complete'] and all(not row['bufferPending'] and not row['callbackAlive']
        and (row['discarded'] is not None or row['returned'] is not None and row['finally'] is not None)
        and (row['original'] is None or row['expired'] is not None) for row in current['records']))
    return deepcopy(current['records'])


class IOSTabletWebDeferred(native.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT


class IOSTabletWebDefer:
    """One explicit already-journaled fault query; uncertain sends never retry.

    The caller supplies/persists the command nonce and original before packet.
    Reconciliation reads the passive history via resolve(), which does no I/O.
    """
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=None,sleep=None):
        import time
        self.send,self.read,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic=monotonic or time.monotonic;self.sleep=sleep or time.sleep
        need(integer(pid,1) and all(callable(x) for x in (send,read,clock_ms,guard,self.monotonic,self.sleep)))

    def issue(self,query,before):
        from adapters.native_feature_observation import number
        from adapters.operation_transport_guard import scope
        start=last=self.monotonic();failed=False;need(number(start,0,1e15))
        def check():
            nonlocal last,failed
            now=self.monotonic()
            if failed or not number(now,last,1e15) or now-start>=1.5:failed=True;need(False)
            last=now
        with scope(check):
            check();return self._issue(query,before)

    def _issue(self,query,before):
        from adapters.native_feature_observation import decode,number
        from adapters.normal_ui import NativeUIError
        try:
            command(query,operation=True);original(before)
            need(before['processId']==self.pid and all(before[k]==query[k] for k in ('runId','fixtureUrl')))
            if query['operation']!='arm':need(any(row['id']==query['recordId'] for row in before['records']))
            start=last=self.monotonic();need(number(start,0,1e15) and self.guard() is not False)
            epoch=self.clock_ms();need(integer(epoch,before['clockAfter']['epochMs']));need(self.guard() is not False)
            now=self.monotonic();need(number(now,last,1e15) and now-start<1.5);last=now
            self.send(deepcopy(query))
            for attempt in range(16):
                need(self.guard() is not False);raw=self.read();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw,limit=LIMIT) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,last,1e15) and now-start<1.5);last=now
                if type(value) is dict and type(value.get('command')) is dict and value['command'].get('commandId')==query['commandId']:
                    after=self.clock_ms();need(integer(after,epoch));receipt(value,query,before['instance'],None)
                    need(epoch<=value['issued']['epochMs']<=(value['completed'] or value['issued'])['epochMs']<=after)
                    need(value['issued']['epochMs']>=epoch);native.sources.stamp(value['issued'],floor=before['clockAfter'])
                    fresh((value['completed'] or value['issued'])['epochMs'],after)
                    need(self.guard() is not False);end=self.monotonic();need(number(end,last,1e15) and end-start<1.5)
                    return deepcopy(value)
                if attempt<15:self.sleep(.1)
        except Exception:raise NativeUIError('Original Tablet inline fault receipt is unavailable or invalid') from None
        raise NativeUIError('Original Tablet inline fault receipt is unavailable or invalid')

    @staticmethod
    def resolve(query,current):
        command(query,operation=True);original(current)
        need(all(current[k]==query[k] for k in ('runId','fixtureUrl')))
        matches=[item for item in current['commands'] if item['command']['commandId']==query['commandId']]
        need(len(matches)==1 and matches[0]['command']==query);return deepcopy(matches[0])
