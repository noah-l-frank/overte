"""Actual host callback/weak lifetimes with modeled native Qt DTO producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import pointer_state as source

RUN='a'*32
EPOCH=1700000000000


class Object:pass


class NativePointerBoundary:
    def __init__(self):
        self.now=EPOCH;self.sequence=0;self.requests=[];self.packet=None;self.rows=[];self.events=[];self.contacts={};self.ends=[]
        self.devices=[];self.targets=[];self.batches={};self.pending=set();self.complete=True;self.started=True
        self.world_tap=False;self.qt_buttons=0;self.device=Object();self.target=Object();self.product_contacts=set();self.event_batches={}
    def tick(self):self.now+=1;return self.now
    def mono(self):return (self.now-EPOCH+1000)/1000
    def weak_id(self,table,obj,device=False):
        for weak,row in table:
            if weak() is obj:return row['id']
        row=dict(id=uuid.uuid4().hex,bornEpochMs=self.tick())
        row.update(deviceType=8) if device else row.update(className='ActualHostWindow')
        table.append((weakref.ref(obj),row));return row['id']
    def edge(self,row,kind):
        stamp=self.tick();event=dict(sequence=len(self.events)+1,dispatch=row['id'],kind=kind,epochMs=stamp,monotonicMs=stamp-EPOCH+1000)
        self.events.append(event);row.update({kind+'Sequence':event['sequence'],kind+'EpochMs':stamp,kind+'MonotonicMs':event['monotonicMs']})
    def apply(self,row):
        device,kind=row['device'],row['kind']
        def add(channel,point):
            key=device+':'+channel+':'+str(point)
            if key in self.contacts:self.complete=False;return
            self.contacts[key]=dict(kind=channel,device=device,point=point,target=row['target'],startDispatch=row['id'],bornEpochMs=row['enteredEpochMs'])
        def end(key):
            if key not in self.contacts:self.complete=False;return
            self.ends.append(dict(self.contacts.pop(key),endDispatch=row['id']))
        if kind.startswith('mouse-'):
            if kind in ('mouse-press','mouse-double'):add('mouse',row['button'])
            elif kind=='mouse-release':end(device+':mouse:'+str(row['button']))
            buttons=0
            for point in self.contacts.values():
                if point['kind']=='mouse' and point['device']==device:buttons|=point['point']
            if buttons!=row['buttons']:self.complete=False
        elif kind=='touch-cancel':
            for key in sorted(self.contacts):
                if key.startswith(device+':touch:'):end(key)
        else:
            for point in row['points']:
                if point['state']==1:add('touch',point['id'])
                elif point['state']==8:end(device+':touch:'+str(point['id']))
                elif device+':touch:'+str(point['id']) not in self.contacts:self.complete=False
    def enter(self,event):
        if not self.started or not self.complete or len(self.rows)>=1024:self.complete=False;return None
        kind=event['kind'];device=self.weak_id(self.devices,self.device,True);target=self.weak_id(self.targets,self.target)
        batch=self.event_batches.setdefault(id(event),uuid.uuid4().hex);nested=batch in self.batches
        self.batches[batch]=self.batches.get(batch,0)+1
        row=dict(id=uuid.uuid4().hex,batch=batch,kind=kind,device=device,target=target,qtTimestamp=event.get('timestamp',self.now-EPOCH),
            button=event.get('button',0),buttons=event.get('buttons',0),mouseSource=0,position=deepcopy(event.get('position',[])),points=deepcopy(event.get('points',[])),
            enteredSequence=0,enteredEpochMs=0,enteredMonotonicMs=0,returnedSequence=0,returnedEpochMs=0,returnedMonotonicMs=0,
            deliveryResult=None,finallySequence=0,finallyEpochMs=0,finallyMonotonicMs=0)
        self.rows.append(row);self.pending.add(row['id']);self.edge(row,'entered')
        if not nested:self.apply(row)
        return row
    def returned(self,row,result):
        if row is not None:row['deliveryResult']=result;self.edge(row,'returned')
    def finished(self,row,event):
        if row is None:return
        if not row['returnedSequence']:self.complete=False
        self.edge(row,'finally');self.pending.remove(row['id']);self.batches[row['batch']]-=1
        if not self.batches[row['batch']]:self.batches.pop(row['batch']);self.event_batches.pop(id(event),None)
    def notify(self,event,handler=lambda:True):
        row=self.enter(event)
        try:result=handler();self.returned(row,result);return result
        finally:self.finished(row,event)
    def touch(self,kind,*,point=3,position=(25,40),handler=None):
        event=dict(kind=kind,points=[] if kind=='touch-cancel' else [dict(id=point,state=1 if kind=='touch-begin' else 8 if kind=='touch-end' else 4,position=list(position))])
        def delivered():
            if kind=='touch-begin':self.product_contacts.add(point);self.world_tap=True
            elif kind in ('touch-end','touch-cancel'):self.product_contacts.discard(point);self.world_tap=False
            return True if handler is None else handler()
        return self.notify(event,delivered)
    def send(self,query):
        source.command(query);self.requests.append(deepcopy(query));self.sequence+=1;stamp=self.tick()
        def weak_rows(table):return [dict(row,alive=weak() is not None) for weak,row in table]
        payload=dict(iosPointerSourceVersion=1,instance='b'*32,bornEpochMs=EPOCH-10,complete=self.complete and self.started,
            startup=dict(observed=True,epochMs=EPOCH,monotonicMs=1000,windowCount=0,mouseButtons=0) if self.started else
                dict(observed=False,epochMs=0,monotonicMs=0,windowCount=-1,mouseButtons=-1),
            eventSequence=len(self.events),events=deepcopy(self.events),dispatches=deepcopy(self.rows),pendingDispatches=len(self.pending),
            contacts=[deepcopy(self.contacts[k]) for k in sorted(self.contacts)],ends=deepcopy(self.ends),devices=weak_rows(self.devices),targets=weak_rows(self.targets),
            qtMouseButtons=self.qt_buttons,worldTapActive=self.world_tap)
        self.packet=dict(iosPointerStateVersion=1,requestId=query['commandId'],runId=query['runId'],instance='c'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-ios-pointer',clockBefore=dict(epochMs=stamp,monotonicMs=stamp-EPOCH+1000),
            clockAfter=dict(epochMs=stamp,monotonicMs=stamp-EPOCH+1000),source=payload)
    def original(self):return json.dumps(self.packet,separators=(',',':'))
    def reader(self):return source.IOSPointerState(self.send,self.original,self.tick,lambda:True,42,monotonic=self.mono,sleep=lambda duration:None)


class PointerStateTests(unittest.TestCase):
    def test_actual_dispatch_returns_and_real_contact_end_are_separate_from_release_ack(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);barrier=native.tick()
        native.touch('touch-begin');active=reader.read(RUN)
        with self.assertRaises(NativeUIError):source.drained(before,active,after_epoch=barrier,require_delivery=True)
        native.touch('touch-end');after=reader.read(RUN);result=source.delivered(before,after,kind='touch',position=[25,40],after_epoch=barrier)
        self.assertEqual('touch',result['kind']);self.assertEqual(set(),native.product_contacts)
        self.assertEqual(['entered','returned','finally']*2,[row['kind'] for row in after['source']['events']])
        with self.assertRaises(NativeUIError):source.delivered(before,after,kind='touch',position=[80,90],after_epoch=barrier)
    def test_nested_read_during_release_has_zero_contacts_but_positive_pending_callback_until_return_and_finally(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);native.touch('touch-begin');nested=[]
        def during():
            value=reader.read(RUN);nested.append(value);self.assertEqual([],value['source']['contacts']);self.assertEqual(1,value['source']['pendingDispatches'])
            with self.assertRaises(NativeUIError):source.drained(before,value,after_epoch=before['clockAfter']['epochMs'],require_delivery=True)
            return True
        native.touch('touch-end',handler=during);after=reader.read(RUN)
        self.assertEqual(0,after['source']['pendingDispatches']);source.drained(before,after,after_epoch=before['clockAfter']['epochMs'],require_delivery=True)
        self.assertEqual(0,nested[0]['source']['dispatches'][-1]['returnedSequence'])
    def test_actual_nested_notify_of_the_same_event_never_manufactures_a_second_contact(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN)
        event=dict(kind='touch-begin',points=[dict(id=4,state=1,position=[25,40])],timestamp=1)
        native.notify(event,lambda:native.notify(event));active=reader.read(RUN);self.assertEqual(1,len(active['source']['contacts']))
        native.touch('touch-end',point=4);after=reader.read(RUN);source.drained(before,after,after_epoch=before['clockAfter']['epochMs'],require_delivery=True)
        self.assertEqual(after['source']['dispatches'][0]['batch'],after['source']['dispatches'][1]['batch'])
    def test_unreturned_release_finally_is_not_positive_handler_return(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);native.touch('touch-begin')
        def thrown():raise RuntimeError('Actual host product callback throws')
        with self.assertRaises(RuntimeError):native.touch('touch-end',handler=thrown)
        after=reader.read(RUN);self.assertEqual([],after['source']['contacts']);self.assertEqual(0,after['source']['pendingDispatches']);self.assertFalse(after['source']['complete'])
        with self.assertRaises(NativeUIError):source.drained(before,after,after_epoch=before['clockAfter']['epochMs'],require_delivery=True)
    def test_doubleclick_and_actual_touch_cancel_retain_original_positive_end(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN)
        native.notify(dict(kind='mouse-double',button=1,buttons=1,position=[25,40]));native.notify(dict(kind='mouse-release',button=1,buttons=0,position=[25,40]))
        after=reader.read(RUN);source.delivered(before,after,kind='mouse',position=[25,40],after_epoch=before['clockAfter']['epochMs'])
        before=after;native.touch('touch-begin');native.touch('touch-cancel');after=reader.read(RUN)
        source.delivered(before,after,kind='touch',position=[25,40],after_epoch=before['clockAfter']['epochMs'])
        self.assertEqual('touch-cancel',after['source']['dispatches'][-1]['kind'])
    def test_weak_target_death_and_input_ack_cannot_clear_a_contact_or_world_tap(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);native.touch('touch-begin')
        del native.target;after=reader.read(RUN);self.assertFalse(after['source']['targets'][0]['alive']);self.assertTrue(after['source']['contacts'])
        with self.assertRaises(NativeUIError):source.drained(before,after,after_epoch=before['clockAfter']['epochMs'])
        native.target=Object();native.touch('touch-end');after=reader.read(RUN);native.world_tap=True;tap=reader.read(RUN)
        with self.assertRaises(NativeUIError):source.drained(before,tap,after_epoch=before['clockAfter']['epochMs'])
        native.world_tap=False;native.qt_buttons=1;button=reader.read(RUN)
        with self.assertRaises(NativeUIError):source.drained(before,button,after_epoch=before['clockAfter']['epochMs'])
    def test_false_native_dispatch_return_is_retained_without_becoming_an_accepted_product_effect(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN)
        native.touch('touch-begin',handler=lambda:False);native.touch('touch-end',handler=lambda:False);after=reader.read(RUN)
        ended=source.delivered(before,after,kind='touch',position=[25,40],after_epoch=before['clockAfter']['epochMs'])
        row=next(row for row in after['source']['dispatches'] if row['id']==ended['endDispatch'])
        self.assertIs(False,row['deliveryResult']);self.assertEqual(0,after['source']['pendingDispatches'])
        # Only actual input/lifetime end is proven. Separate scene/UI/worker
        # original owners must still establish every feature effect.

    def test_never_observed_missing_startup_unknown_end_and_overflow_are_distinct_from_a_positive_delivery(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);quiet=reader.read(RUN)
        source.drained(before,quiet,after_epoch=before['clockAfter']['epochMs'])
        with self.assertRaises(NativeUIError):source.drained(before,quiet,after_epoch=before['clockAfter']['epochMs'],require_delivery=True)
        native.touch('touch-end');unknown=reader.read(RUN);self.assertFalse(unknown['source']['complete'])
        with self.assertRaises(NativeUIError):source.drained(before,unknown,after_epoch=before['clockAfter']['epochMs'])
        missing=NativePointerBoundary();missing.started=False;reader=missing.reader();value=reader.read(RUN);self.assertFalse(value['source']['startup']['observed'])
        with self.assertRaises(NativeUIError):source.drained(value,reader.read(RUN),after_epoch=value['clockAfter']['epochMs'])
        bounded=NativePointerBoundary()
        for _ in range(1025):bounded.notify(dict(kind='mouse-move',button=0,buttons=0,position=[25,40]))
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=source.ACTION,runId=RUN);bounded.send(query)
        self.assertEqual(1024,len(bounded.rows));self.assertFalse(bounded.complete);source.original(bounded.packet)
    def test_native_original_prefix_cannot_be_reset_relabelled_revived_or_retimed(self):
        native=NativePointerBoundary();reader=native.reader();before=reader.read(RUN);native.touch('touch-begin');active=reader.read(RUN);native.touch('touch-end');after=reader.read(RUN)
        for fault in ('event','startup','source','return','counter','point','point-bool','contact','alive'):
            value=deepcopy(after)
            if fault=='event':value['source']['events'][0]['epochMs']+=1
            elif fault=='startup':value['source']['startup']['epochMs']-=1
            elif fault=='source':value['source']['instance']='f'*32
            elif fault=='return':value['source']['dispatches'][0]['deliveryResult']=False
            elif fault=='counter':value['sequence']=active['sequence']
            elif fault=='point':value['source']['dispatches'][0]['points'][0]['position'][0]+=10
            elif fault=='point-bool':value['source']['dispatches'][0]['points'][0]['state']=True
            elif fault=='contact':value['source']['contacts']=deepcopy(active['source']['contacts'])
            else:value['source']['targets'][0]['alive']=False;active=deepcopy(active);active['source']['targets'][0]['alive']=False;value['source']['targets'][0]['alive']=True
            query=dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query,42,previous=active)
        for field in ('contacts','worldTapActive','reset','afterSequence'):
            query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=source.ACTION,runId=RUN)
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(query|{field:False})


if __name__=='__main__':unittest.main()
