"""Native deferral model driven by actual held host JS admission callables.

Native clocks/metadata are models. Python weak capture lifetime, original Node
callbacks and delivered/discarded commands actually execute. No request supplies
message bytes, and no callback weak death is inferred from its body return.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import uuid
import weakref
from adapters.native_feature_observation import need
from ios.adapters import tablet_web_deferred as source
from ios.self_tests.test_ios_tablet_web_sources import stamp


class TabletDeferredModel:
    def __init__(self,boundary):
        self.b=weakref.proxy(boundary);self.callback=None;self.captures={};self.seen=0
    @property
    def value(self):return self.b.template['deferred']
    def sweep(self):
        for row in self.value['records']:
            weak=self.captures.get(row['id'])
            if weak is not None and row['expired'] is None and weak() is None:
                row.update(callbackAlive=False,expired=self.b.tick())
    def received(self,output):
        events=output.get('deferredEvents',[])
        for event in events[self.seen:]:
            self.seen+=1
            if event['kind']!='captured':continue
            rows=[row for row in self.value['records'] if row['original'] is None and row['discarded'] is None and row['overdue'] is None]
            need(len(rows)==1);row=rows[0]
            envelope=json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[event['message']]))
            source.envelope(envelope);need(event['frame']==row['identity']['url'])
            self.b.sleep(max(0,event['epoch']-self.b.epoch())/1000)
            row.update(captured=stamp(event['epoch']),bufferPending=True,callbackAlive=True,
                original=dict(envelope=envelope,envelopeSha256=hashlib.sha256(envelope.encode()).hexdigest(),nonce=row['identity']['nonce'],
                    frame=event['frame'],mainFrame=True,generation=row['identity']['grant']))
            app=weakref.ref(self.b.host_app);boundary=self.b
            def invoke():
                actual=app()
                if actual is not None and actual.process.poll() is None:
                    result=actual.call('defer-deliver',epoch=boundary.epoch());boundary.sync_messages(result)
                    if boundary.template['state']['presentations']:boundary.focus(result)
            self.callback=invoke;self.captures[row['id']]=weakref.ref(invoke)
    def command(self,query):
        source.command(query,operation=True);self.sweep();value=self.value
        old=[row for row in value['commands'] if row['command']['commandId']==query['commandId']]
        if old:need(len(old)==1 and old[0]['command']==query);return deepcopy(old[0])
        value['commandSequence']+=1
        receipt=dict(iosTabletWebDeferReceiptVersion=1,command=deepcopy(query),instance=value['instance'],sequence=value['commandSequence'],
            issued=self.b.tick(),completed=None,status='issued',record=None)
        value['commands'].append(receipt);rows=value['records'];operation=query['operation']
        if operation=='arm':
            occupied=any(row['callbackAlive'] or row['bufferPending'] or row['original'] is None and row['discarded'] is row['overdue'] is None for row in rows)
            current=self.b.page_identity
            if not occupied and current is not None and current['source']['carrier'] is not None and self.b.template['state']['presentations']:
                self.b.host_app.call('defer-arm')
                row=dict(id=uuid.uuid4().hex,identity=deepcopy(current),armCommand=query['commandId'],deliveryCommand=None,discardCommand=None,
                    armed=self.b.tick(),bufferPending=False,callbackAlive=False,original=None,**{key:None for key in source.CLOCKS})
                rows.append(row);receipt.update(record=row['id'],status='armed',completed=self.b.tick());return deepcopy(receipt)
        else:
            matches=[row for row in rows if row['id']==query['recordId']]
            if len(matches)==1:
                row=matches[0]
                if operation=='deliver' and row['bufferPending'] and self.callback is not None:
                    actual=self.callback;self.callback=None
                    row.update(deliveryCommand=query['commandId'],delivering=self.b.tick(),bufferPending=False)
                    receipt.update(record=row['id'],status='delivered',completed=self.b.tick())
                    try:actual();row['returned']=self.b.tick()
                    finally:row['finally']=self.b.tick()
                    return deepcopy(receipt)
                if operation=='discard' and row['deliveryCommand'] is row['discardCommand'] is None:
                    self.b.host_app.call('defer-discard',epoch=self.b.epoch());self.callback=None
                    row.update(discardCommand=query['commandId'],discarded=self.b.tick(),bufferPending=False)
                    receipt.update(record=row['id'],status='discarded',completed=self.b.tick());return deepcopy(receipt)
        receipt.update(status='refused',completed=self.b.tick());return deepcopy(receipt)
