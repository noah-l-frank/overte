"""Actual host weak objects and modeled native API/Tree DTO producers only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
import unittest
import uuid
import weakref

from adapters.normal_ui import NativeUIError
from ios.adapters import create_entities as source
from ios.self_tests.test_ios_create_marker_measurements import frames
from ios.self_tests.test_ios_create_state import RUN,EPOCH


class Item:pass


class NativeBoundary:
    def __init__(self):
        self.now=EPOCH-40;self.sequence=0;self.commands=[];self.packet=None;self.items={};self.rows=[];self.tree_events=[];self.call_events=[]
        self.tree_instance='d'*32;self.call_sequence=0;self.ignore_delete=False;self.tree_complete=True;self.calls_complete=True
        scripts=frames()[2]['source'];self.manager=deepcopy(scripts['membership']['managers'][0]);self.code=deepcopy(scripts['engines'][0]['code'])
    def tick(self):self.now+=1;return self.now
    def mono(self):return (self.now-EPOCH+1000)/1000
    def caller(self,method):
        self.call_sequence+=1;return dict(callerVersion=1,method=method,sequence=self.call_sequence,invokedEpochMs=self.tick(),manager=deepcopy(self.manager),code=deepcopy(self.code))
    def tree_event(self,kind,row):
        if not self.tree_complete or len(self.tree_events)>=1024 or kind=='inserted' and len(self.rows)>512:
            self.tree_complete=False;return
        stamp=self.tick();event=dict(sequence=len(self.tree_events)+1,kind=kind,id=row['id'],birth=row['birth'],epochMs=stamp,monotonicMs=stamp-EPOCH+1000)
        self.tree_events.append(event)
        if kind=='inserted':row.update(insertedSequence=event['sequence'],bornEpochMs=stamp,bornMonotonicMs=event['monotonicMs'])
        else:row.update(removedSequence=event['sequence'],removedEpochMs=stamp,removedMonotonicMs=event['monotonicMs'])
    def returned(self,kind,id_,caller):
        if not self.calls_complete or len(self.call_events)>=512:
            self.calls_complete=False;return
        stamp=self.tick();self.call_events.append(dict(sequence=len(self.call_events)+1,eventId=uuid.uuid4().hex,kind=kind,
            clock=dict(epochMs=stamp,monotonicMs=stamp-EPOCH+1000),caller=caller,entityId=id_,localTreeAvailable=True))
    def add(self,*,create=True,id_=None):
        self.now=max(self.now,EPOCH+5);caller=self.caller('addEntity');id_=str(uuid.uuid4()) if id_ is None else id_
        if create:
            item=Item();self.items[id_]=item
            row=dict(id=id_,birth=uuid.uuid4().hex,insertedSequence=0,bornEpochMs=0,bornMonotonicMs=0,removedSequence=0,removedEpochMs=0,
                removedMonotonicMs=0,destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
            if not self.tree_complete or len(self.rows)>=512:self.tree_complete=False
            else:self.rows.append((weakref.ref(item),row));self.tree_event('inserted',row)
        self.returned('add-returned',id_ if create else None,caller);return id_ if create else None
    def delete(self,id_):
        caller=self.caller('deleteEntity')
        if not self.ignore_delete:
            actual=self.items.pop(id_,None)
            found=False
            for weak,row in self.rows:
                if weak() is actual and row['removedSequence']==0:self.tree_event('removed',row);found=True
            if actual is not None and not found:self.tree_complete=False
            del actual
        self.returned('delete-returned',id_,caller)
    def send(self,query):
        source.command(query);self.commands.append(deepcopy(query));self.sequence+=1;before=self.tick();observed=self.tick()
        rows=[]
        for weak,row in self.rows:
            if weak() is None and not row['destroyed']:row.update(destroyed=True,destructionObservedEpochMs=observed,destructionObservedMonotonicMs=observed-EPOCH+1000)
            rows.append(deepcopy(row))
        tree=dict(entityTreeLifetimesVersion=1,treeInstance=self.tree_instance,treeBornEpochMs=EPOCH-1000,complete=self.tree_complete,eventSequence=len(self.tree_events),
            observedEpochMs=observed,observedMonotonicMs=observed-EPOCH+1000,events=deepcopy(self.tree_events),entities=rows)
        after=self.tick();self.packet=dict(iosCreateEntitiesVersion=1,requestId=query['commandId'],runId=RUN,instance='f'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-create-entities',clockBefore=dict(epochMs=before,monotonicMs=before-EPOCH+1000),
            clockAfter=dict(epochMs=after,monotonicMs=after-EPOCH+1000),source=dict(calls=dict(createEntityCallsVersion=1,instance='e'*32,complete=self.calls_complete,events=deepcopy(self.call_events)),tree=tree))
    def original(self):return json.dumps(self.packet)
    def reader(self):return source.IOSCreateEntities(self.send,self.original,self.tick,lambda:True,42,monotonic=self.mono,sleep=lambda seconds:None)


class CreateEntitiesTests(unittest.TestCase):
    def test_real_returned_uuid_actual_tree_birth_and_weak_expiry_are_independent_originals(self):
        native=NativeBoundary();reader=native.reader();before=reader.read(RUN);id_=native.add();created=reader.read(RUN)
        owned=source.returned(created,before,native.manager,native.code,after_epoch=EPOCH-30)
        self.assertEqual(id_,owned['returned']['entityId']);self.assertEqual(id_,owned['birth']['id'])
        held=native.items[id_];native.delete(id_);removed=reader.read(RUN)
        self.assertGreater(removed['source']['tree']['entities'][0]['removedSequence'],0);self.assertFalse(removed['source']['tree']['entities'][0]['destroyed'])
        with self.assertRaises(NativeUIError):source.retired(removed,owned,after_epoch=created['clockAfter']['epochMs'])
        del held;gc.collect();gone=reader.read(RUN);self.assertTrue(source.retired(gone,owned,after_epoch=created['clockAfter']['epochMs'])['destroyed'])
        self.assertEqual(4,len(native.commands));self.assertEqual(created['source']['calls']['events'],gone['source']['calls']['events'][:1])
    def test_api_ack_or_operand_without_actual_removal_and_wrong_vm_returned_identity_cannot_retire(self):
        native=NativeBoundary();reader=native.reader();before=reader.read(RUN);id_=native.add();created=reader.read(RUN)
        owned=source.returned(created,before,native.manager,native.code,after_epoch=EPOCH-30);native.ignore_delete=True;native.delete(id_);current=reader.read(RUN)
        with self.assertRaises(NativeUIError):source.retired(current,owned,after_epoch=created['clockAfter']['epochMs'])
        for fault in ('return','birth','code','caller','tree'):
            value=deepcopy(created)
            if fault=='return':value['source']['calls']['events'][0]['entityId']=str(uuid.uuid4())
            elif fault=='birth':value['source']['tree'].update(entities=[],events=[],eventSequence=0)
            elif fault=='code':value['source']['calls']['events'][0]['caller']['code']['sha256']='0'*64
            elif fault=='caller':value['source']['calls']['events'][0]['caller']['manager']['instance']='0'*32
            else:value['source']['tree']['treeInstance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.returned(value,before,native.manager,native.code,after_epoch=EPOCH-30)
    def test_actual_null_add_return_is_preserved_and_cannot_be_forged_from_a_delete_operand(self):
        native=NativeBoundary();reader=native.reader();before=reader.read(RUN);self.assertIsNone(native.add(create=False));after=reader.read(RUN)
        owned=source.returned(after,before,native.manager,native.code,after_epoch=EPOCH-30);self.assertIsNone(owned['birth']);self.assertIsNone(source.retired(after,owned,after_epoch=EPOCH+1))
        fake=deepcopy(after);event=fake['source']['calls']['events'][0];event['kind']='delete-returned';event['caller']['method']='deleteEntity'
        forged=deepcopy(owned);forged['returned']=deepcopy(event)
        with self.assertRaises(NativeUIError):source.retired(fake,forged,after_epoch=EPOCH+1)
    def test_reused_uuid_has_another_native_birth_and_cannot_hide_a_live_replacement(self):
        native=NativeBoundary();reader=native.reader();before=reader.read(RUN);id_=native.add();first=reader.read(RUN)
        owned=source.returned(first,before,native.manager,native.code,after_epoch=EPOCH-30);native.delete(id_);gone=reader.read(RUN)
        source.retired(gone,owned,after_epoch=first['clockAfter']['epochMs'])
        native.add(id_=id_);replacement=reader.read(RUN)
        self.assertEqual(id_,replacement['source']['tree']['entities'][1]['id'])
        self.assertNotEqual(owned['birth']['birth'],replacement['source']['tree']['entities'][1]['birth'])
        with self.assertRaises(NativeUIError):source.retired(replacement,owned,after_epoch=first['clockAfter']['epochMs'])
    def test_null_return_with_unjoined_actual_tree_birth_is_unresolved(self):
        native=NativeBoundary();reader=native.reader();before=reader.read(RUN);native.add();current=reader.read(RUN)
        current['source']['calls']['events'][0]['entityId']=None
        with self.assertRaises(NativeUIError):source.returned(current,before,native.manager,native.code,after_epoch=EPOCH-30)
    def test_native_prefix_destruction_history_overflow_and_birth_identity_never_reset(self):
        native=NativeBoundary();reader=native.reader();baseline=reader.read(RUN);id_=native.add();created=reader.read(RUN);native.delete(id_);current=reader.read(RUN)
        source.original(current)
        for fault in ('event-prefix','birth','revive','tree-born','sequence','overflow','wrong-run'):
            value=deepcopy(current)
            if fault=='event-prefix':value['source']['tree']['events'][0]['epochMs']+=1
            elif fault=='birth':value['source']['tree']['entities'][0]['birth']='0'*32
            elif fault=='revive':value['source']['tree']['entities'][0].update(destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
            elif fault=='tree-born':value['source']['tree']['treeBornEpochMs']-=1
            elif fault=='sequence':value['sequence']=created['sequence']
            elif fault=='overflow':value['source']['tree']['eventSequence']=1025
            else:value['runId']='0'*32
            prior=current if fault=='revive' else created
            query=dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query,42,previous=prior)
        poisoned=deepcopy(current);poisoned['source']['tree']['complete']=False;source.original(poisoned)
        with self.assertRaises(NativeUIError):source.returned(poisoned,baseline,native.manager,native.code,after_epoch=EPOCH-30)
    def test_unknown_real_removal_and_bounded_overflow_remain_incomplete_without_reset(self):
        native=NativeBoundary();reader=native.reader();baseline=reader.read(RUN)
        unknown=str(uuid.uuid4());native.items[unknown]=Item();native.now=EPOCH+5;native.delete(unknown)
        packet=reader.read(RUN);self.assertFalse(packet['source']['tree']['complete'])
        native.add();later=reader.read(RUN);self.assertFalse(later['source']['tree']['complete'])
        with self.assertRaises(NativeUIError):source.returned(later,baseline,native.manager,native.code,after_epoch=EPOCH-30)
        large=NativeBoundary()
        for _ in range(513):large.add()
        query=dict(schemaVersion=1,commandId='ios-'+'1'*32,action=source.ACTION,runId=RUN);large.send(query)
        self.assertFalse(large.packet['source']['tree']['complete']);self.assertFalse(large.packet['source']['calls']['complete'])
        self.assertEqual(512,len(large.packet['source']['tree']['entities']));self.assertEqual(512,len(large.packet['source']['calls']['events']))
        source.original(large.packet)
    def test_closed_read_transport_rejects_supplied_ids_wanted_results_and_false_native_binding(self):
        query=dict(schemaVersion=1,commandId='ios-'+'1'*32,action=source.ACTION,runId=RUN)
        for field,value in (('entityId',str(uuid.uuid4())),('destroyed',True),('reset',True),('afterSequence',0)):
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(query|{field:value})
        native=NativeBoundary();reader=native.reader();packet=reader.read(RUN)
        for field,value in (('processId',43),('instance','bad'),('clockDomain','host-clock')):
            changed=deepcopy(packet);changed[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.validate(changed,dict(query,commandId=packet['requestId']),42)


if __name__=='__main__':unittest.main()
