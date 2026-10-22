"""Explicit Qt delivery models; no native keyboard or device is executed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_keys as keys

RUN='a'*32


class QtKeys:
    def __init__(self):
        self.epoch=100000;self.rows=[];self.events=[];self.active={};self.down={};self.ended=[];self.preedit={}
        self.target='b'*32;self.device='c'*32;self.sequence=0;self.alive=True;self.started=True;self.complete=True
    def tick(self):self.epoch+=1;return self.epoch
    def edge(self,row,kind):
        stamp=self.tick();index=len(self.events)+1
        self.events.append(dict(sequence=index,dispatch=row['id'],kind=kind,epochMs=stamp,monotonicMs=stamp-99999))
        row.update({kind+'Sequence':index,kind+'EpochMs':stamp,kind+'MonotonicMs':stamp-99999})
    def enter(self,kind,*,batch=None,repeat=False,preedit='',commit=''):
        batch=secrets.token_hex(16) if batch is None else batch;id=secrets.token_hex(16)
        detail=dict(commit=commit,preedit=preedit,replacementStart=0,replacementLength=0) if kind=='input-method' else dict(
            key=65,text='a',modifiers=0,scanCode=4,virtualKey=65,autoRepeat=repeat,count=1,qtTimestamp=self.epoch)
        row=dict(id=id,batch=batch,kind=kind,target=self.target,device='' if kind=='input-method' else self.device,detail=detail,
            enteredSequence=0,enteredEpochMs=0,enteredMonotonicMs=0,returnedSequence=0,returnedEpochMs=0,returnedMonotonicMs=0,
            deliveryResult=None,finallySequence=0,finallyEpochMs=0,finallyMonotonicMs=0)
        nested=batch in self.active.values();self.active[id]=batch;self.rows.append(row);self.edge(row,'entered')
        if not nested:
            if kind=='input-method':self.preedit[self.target]=dict(target=self.target,text=preedit,dispatch=id)
            elif not repeat:
                key=self.device+':4:65'
                if kind=='key-press':self.down[key]=dict(device=self.device,key=65,scanCode=4,target=self.target,pressDispatch=id,releaseDispatch='')
                else:
                    ended=self.down.pop(key);ended['releaseDispatch']=id;self.ended.append(ended)
        return row
    def finish(self,row,result=True):
        row['deliveryResult']=result;self.edge(row,'returned');self.edge(row,'finally');del self.active[row['id']]
    def packet(self):
        self.sequence+=1;before=self.tick();after=self.tick()
        return dict(iosWorldWebKeysVersion=1,requestId='ios-'+secrets.token_hex(16),runId=RUN,instance='d'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-ios-world-web-keys',clockBefore=dict(epochMs=before,monotonicMs=before-99998),clockAfter=dict(epochMs=after,monotonicMs=after-99998),
            source=dict(iosWorldWebKeySourceVersion=1,instance='e'*32,bornEpochMs=99999,complete=self.complete,startup=dict(
                observed=self.started,epochMs=100000 if self.started else 0,monotonicMs=1 if self.started else 0,windowCount=0 if self.started else -1,modifiers=0 if self.started else -1),
                eventSequence=len(self.events),events=deepcopy(self.events),dispatches=deepcopy(self.rows),pendingDispatches=len(self.active),
                down=[deepcopy(self.down[key]) for key in sorted(self.down)],ended=deepcopy(self.ended),preedit=[deepcopy(self.preedit[key]) for key in sorted(self.preedit)],
                devices=[] if not any(row['device'] for row in self.rows) else [dict(id=self.device,bornEpochMs=100001,className='QInputDevice',alive=True)],
                targets=[] if not self.rows else [dict(id=self.target,bornEpochMs=100001,className='QQuickWindow',alive=self.alive)],qtModifiers=0))


class WorldWebKeysTests(unittest.TestCase):
    def test_positive_startup_actual_press_release_and_returned_false_do_not_claim_effect(self):
        qt=QtKeys();keys.drained(qt.packet());press=qt.enter('key-press');qt.finish(press)
        held=qt.packet();keys.original(held)
        with self.assertRaises(NativeUIError):keys.drained(held)
        release=qt.enter('key-release');qt.finish(release,result=False);after=qt.packet()
        keys.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=keys.ACTION,runId=RUN),42,previous=held)
        self.assertEqual(1,len(keys.drained(after)['ended']))
        self.assertFalse(after['source']['dispatches'][-1]['deliveryResult'])

    def test_entered_release_is_not_drained_until_actual_qt_callback_return_and_finally(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));release=qt.enter('key-release');pending=qt.packet();keys.original(pending)
        self.assertEqual([],pending['source']['down'])
        with self.assertRaises(NativeUIError):keys.drained(pending)
        qt.finish(release);keys.drained(qt.packet())

    def test_nested_notify_same_original_event_does_not_manufacture_second_key_birth(self):
        qt=QtKeys();outer=qt.enter('key-press');inner=qt.enter('key-press',batch=outer['batch'])
        qt.finish(inner);qt.finish(outer);held=qt.packet();keys.original(held);self.assertEqual(1,len(held['source']['down']))
        qt.finish(qt.enter('key-release'));keys.drained(qt.packet())

    def test_auto_repeat_release_retains_original_down_until_real_release(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release',repeat=True));qt.finish(qt.enter('key-press',repeat=True))
        with self.assertRaises(NativeUIError):keys.drained(qt.packet())
        qt.finish(qt.enter('key-release'));keys.drained(qt.packet())

    def test_ime_commit_and_preedit_are_actual_originals_target_death_does_not_clear_them(self):
        qt=QtKeys();qt.finish(qt.enter('input-method',preedit='東京'))
        qt.finish(qt.enter('input-method',commit='東京',preedit=''));keys.drained(qt.packet())
        qt.finish(qt.enter('input-method',preedit='Ω'));qt.alive=False;current=qt.packet();keys.original(current)
        with self.assertRaises(NativeUIError):keys.drained(current)

    def test_unknown_startup_counter_rollover_and_release_ack_cannot_manufacture_empty_source(self):
        qt=QtKeys();qt.complete=qt.started=False
        with self.assertRaises(NativeUIError):keys.drained(qt.packet())
        qt=QtKeys();qt.finish(qt.enter('key-press'));current=qt.packet()
        for fault in ('empty','pending','overflow','eventClock','unknownEnd','booleanKey'):
            value=deepcopy(current)
            if fault=='empty':value['source']['down']=[]
            elif fault=='pending':value['source']['pendingDispatches']=1
            elif fault=='overflow':value['source']['eventSequence']=3073
            elif fault=='eventClock':value['source']['events'][-1]['epochMs']-=100
            elif fault=='unknownEnd':value['source']['dispatches'][0]['kind']='key-release'
            else:value['source']['dispatches'][0]['detail']['key']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):keys.original(value)

    def test_historical_source_prefix_target_death_and_completed_return_cannot_be_rewritten(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));before=qt.packet();qt.finish(qt.enter('key-release'));after=qt.packet()
        query=dict(schemaVersion=1,commandId=after['requestId'],action=keys.ACTION,runId=RUN);keys.validate(after,query,42,previous=before)
        for fault in ('result','sourceBirth','startup','device','event'):
            value=deepcopy(after)
            if fault=='result':value['source']['dispatches'][0]['deliveryResult']=False
            elif fault=='sourceBirth':value['source']['instance']='f'*32
            elif fault=='startup':value['source']['startup']['epochMs']+=1
            elif fault=='device':value['source']['devices'][0]['className']='DifferentDevice'
            else:value['source']['events'][0]['monotonicMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):keys.validate(value,query,42,previous=before)


if __name__=='__main__':unittest.main()
