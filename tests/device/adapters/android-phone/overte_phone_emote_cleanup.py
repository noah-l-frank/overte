"""Cleanup-phase ordinary inputs, with retained original run/input ownership.

This proves only native/UI restoration. Timer, scene, image, actor and file
retirement remain obligations of the enclosing complete feature owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.emote_rig_measurements import source as source_group,continuation
from adapters.native_animation_caller import selected as selected_caller
from adapters.native_animation_history import restored_after
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_inputs import PhoneEmoteInputs,PhoneEmoteInputTransport
from overte_phone_emote_sources import PhoneEmoteSources,source_name
from overte_phone_script_history import canonical,pack,unpack,same
from overte_phone_script_ui import PhoneScriptUI

VERSION=1


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


class PhoneEmoteCleanup(PhoneEmoteInputTransport):
    def __init__(self,inputs):
        need(isinstance(inputs,PhoneEmoteInputs) and inputs.source.historical is False)
        source=inputs.source;source.lock.assert_held()
        self.inputs,self.source=inputs,source
        self.adapter,self.selector,self.lock=source.adapter,source.selector,source.lock
        self.run,self.fixture_url,self.binding=source.run,source.phase.fixture_url,deepcopy(context(source.binding))
        self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-cleanup-inputs.json'))
        self.previous=self.store.read();self.started=self.clock=None;self.failed=False
        self.origin=digest(inputs.previous)
        self.state=dict(current=None,origin=self.origin,normalRecovery=None,final=None)
        self.original_inputs()
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def original_inputs(self):
        need(same(self.inputs.store.read(),self.inputs.previous) and digest(self.inputs.previous)==self.origin)
        if self.inputs.previous is not None:
            state,history=self.inputs.decode(self.inputs.previous)
            need(same(state,self.inputs.state) and same(history,self.inputs.history_state))
            # An interrupted archive is not silently emptied by cleanup.
            need(history['pendingArchive'] is None)
        if self.source.previous is not None:
            state,frames=PhoneEmoteSources.archive(self.source.previous,phase=self.source.phase,artifact_root=self.source.artifact_root,
                binding=self.binding,guard=self.source.guard,monotonic=self.source.monotonic)
            need(same(state,self.source.state) and same(frames,self.source.frames))
        header=PrivateFeatureState(self.store.path.with_name(source_name('primary',0))).read()
        need(header is not None)
        _state,frames=PhoneEmoteSources.archive(header,phase=self.source.phase,artifact_root=self.source.artifact_root,
            binding=self.binding,guard=self.source.guard,monotonic=self.source.monotonic)
        need(frames)
        baseline=frames[0]
        for key in ('phaseBefore','phaseAfter'):
            need(baseline[key]['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
        # The run may only dismiss UI whose actual original baseline was closed.
        need(not baseline['ui']['open'] and not baseline['ui']['controls']
            and baseline['group']['native']['animation']['overrideActive'] is False)

    def active(self,call,status):
        phase_packet(status,run=self.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'])
        need(status['active'] and status['activations'])
        row=status['activations'][-1]
        need(row['ticket']==call['ticket'] and row['stimulus']==dict(verb='cleanup',inputs={}))

    def cancelling(self,current):return True

    def cancel_barrier(self,frame,value):
        super().cancel_barrier(frame,value)
        _selected,event=self.owned(frame)
        _profile,_native,urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        name=urls[event['request']['url']]
        need(value['controlId']=='emote.play.'+('Sit' if name in ('Sit1','Sit2','Sit3') else name))

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.source.historical is False
            and self.source.guard() is not False and same(self.store.read(),self.previous)
            and same(self.source.store.read(),self.source.previous)
            and same(self.inputs.store.read(),self.inputs.previous))
        now=self.source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<45));self.clock=now

    def call(self,value):
        exact(value,{'contractVersion','runId','ticket'})
        arguments('feature.emotes.cleanup',{key:value[key] for key in ('contractVersion','runId')})
        need(value['runId']==self.run and type(value['ticket']) is str and len(value['ticket'])==32
            and all(ch in '0123456789abcdef' for ch in value['ticket']))
        return value

    def decode(self,value):
        exact(value,{'emoteCleanupInputsVersion','runId','fixtureUrl','binding','artifactRoot','segment','payload'})
        need(type(value['emoteCleanupInputsVersion']) is int and value['emoteCleanupInputsVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and same(value['binding'],self.binding)
            and value['artifactRoot']==str(self.source.artifact_root) and type(value['segment']) is int
            and value['segment']==self.source.segment)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'current','origin','normalRecovery','final'});need(state['origin']==self.origin)
        row=state['current'];need(type(row) is dict)
        exact(row,{'call','phase','before','intents','idleReset'});self.call(row['call'])
        need(row['phase'] in ('acting','issuing','acknowledged') and row['idleReset'] is None
            and type(row['intents']) is list and len(row['intents'])<=64)
        plays=self.input_chain(row,row['call']);need(len(plays)<=1)
        for item in plays:
            page=[r for r in item['input']['original']['controls'] if r['id']=='emote.page']
            need(len(page)==1 and page[0]['activeName'] and item['input']['controlId']=='emote.play.'+page[0]['activeName'])
            self.owned(self.original(item['barrier']))
        if state['normalRecovery'] is not None:self.recovered_normal(self.original(state['normalRecovery']),call=row['call'])
        if state['final'] is not None:
            need(row['phase']=='acknowledged' and row['before'] is not None)
            self.restored(self.original(row['before']),self.original(state['final']),call=row['call'])
        else:need(row['phase']!='acknowledged')
        return deepcopy(state)

    def save(self):
        try:
            self.bound()
            value=dict(emoteCleanupInputsVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
                binding=deepcopy(self.binding),artifactRoot=str(self.source.artifact_root),segment=self.source.segment,payload=pack([self.state]))
            self.decode(value)
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def recovered_normal(self,frame,*,call=None):
        actual=self.state['current']['call'] if call is None else call
        self.active(actual,frame['phaseBefore']);self.active(actual,frame['phaseAfter'])
        row=self.inputs.state['current']
        if row is None or row['phase']!='issuing':return
        item=row['intents'][-1]
        need(item['after'] is None)
        if item['kind']=='qt':self.qt_receipt(item['input'],frame['ui'])
        else:
            before=self.inputs.original(item['before'])
            self.same_ui_before_input(before['ui'],frame['ui'])
            need(frame['ui']['open']==(item['controlId']=='tablet.open'))

    def owned(self,frame):
        """Identify an owned active native generation, including lost input ACKs.

        No loaded/moving/image success is claimed here: failed asset loads also
        need safe ordinary cancellation of their actual owned native request.
        """
        rows=self.inputs.state['history']+([self.inputs.state['current']] if self.inputs.state['current'] else [])
        plays=[(row,item) for row in rows if row['call']['verb'] in ('play','sit','override')
            for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        need(plays);row,item=plays[-1];before=self.inputs.original(item['barrier'])
        selected,native,urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        old,_packet,_urls=source_group(before['group'],self.source.pid,before['epochMs']);need(same(old,selected))
        continuation(before['group']['native'],native,self.source.pid)
        history=native['animation']['history'];floor=before['group']['native']['animation']['history']['callSequence']
        events=[e for e in history['events'] if e['kind']=='override' and e['eventSequence']>floor]
        need(len(events)==1);event=events[0]
        selected_caller(event,selected,after_epoch=before['group']['native']['capturedEpochMs'])
        name=urls.get(event['request']['url']);requested=item['input']['controlId'][len('emote.play.'):]
        need(name is not None and (name in ('Sit1','Sit2','Sit3') if requested=='Sit' else name==requested)
            and event['overrideSequence']==history['overrideSequence'])
        return selected,event

    def restored(self,before,after,*,call=None):
        self.active(self.state['current']['call'] if call is None else call,after['phaseAfter'])
        first,last=before['group']['native'],after['group']['native'];continuation(first,last,self.source.pid)
        need(last['animation']['overrideActive'] is False and after['ui']['open'] is False and not after['ui']['controls']
            and last['animation']['history']['overrideSequence']==first['animation']['history']['overrideSequence']
            and same(first['lifecycle'],last['lifecycle']))
        if first['animation']['overrideActive']:
            selected,event=self.owned(before)
            current,_native,_urls=source_group(after['group'],self.source.pid,after['epochMs']);need(same(current,selected))
            restore,frames=restored_after(last,event,after_epoch=first['capturedEpochMs']);need(len(frames)>=3)
            selected_caller(restore,selected,after_epoch=event['caller']['invokedEpochMs'])
        else:need(last['animation']['history']['callSequence']==first['animation']['history']['callSequence'])

    def recover(self):
        row=self.state['current']
        if row['phase']!='issuing':return
        after=self.capture();frame=self.original(after);item=row['intents'][-1]
        if item['kind']=='qt':self.qt_receipt(item['input'],frame['ui']);item['after']=deepcopy(frame['ui'])
        else:
            self.same_ui_before_input(self.original(item['before'])['ui'],frame['ui'])
            need(frame['ui']['open']==(item['controlId']=='tablet.open'));item['after']=after
        row['phase']='acting';self.save() # Observe delivery; never resend it.

    def cleanup(self,call,*,sleep=time.sleep):
        public=deepcopy(arguments('feature.emotes.cleanup',call));need(public['runId']==self.run and callable(sleep))
        need(self.started is None);self.started=self.source.monotonic()
        try:
            self.bound();self.original_inputs()
            if self.previous is not None:need(same(self.decode(self.previous),self.state))
            else:need(same(self.state,dict(current=None,origin=self.origin,normalRecovery=None,final=None)))
            status=self.source.phase.status();need(status['active'] and status['activations'])
            actual=dict(public,ticket=status['activations'][-1]['ticket']);self.active(actual,status)
            if self.state['current'] is None:
                self.state['current']=dict(call=actual,phase='acting',before=None,intents=[],idleReset=None);self.save()
            else:need(same(actual,self.state['current']['call']))
            row=self.state['current']
            if row['phase']=='acknowledged':
                ref=self.capture();self.restored(self.original(row['before']),self.original(ref));self.bound();return {'performed':True}
            with self.adapter.existing_input_session(self.selector):
                if row['before'] is None:row['before']=self.capture();self.save()
                if self.state['normalRecovery'] is None:
                    ref=self.capture();self.recovered_normal(self.original(ref));self.state['normalRecovery']=ref;self.save()
                self.recover()
                native,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector)
                need(same(context(binding),self.binding) and guard() is not False)
                tablet=PhoneScriptUI(native,'io.github.noah_be.overte.phone')
                ui=self.adapter._emote_controls(self.selector,self.intent,receipt=self.receipt)
                ref=self.capture();frame=self.original(ref)
                if frame['group']['native']['animation']['overrideActive']:
                    self.owned(frame)
                    # An earlier cancel may be queued after its consumed Qt
                    # receipt. Never toggle the active button a second time.
                    need(not any(item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.') for item in row['intents']))
                    need(frame['ui']['open']);ui.open();ui.cancel()
                if tablet.tablet_visible():ui.close();self.sdk(tablet,'tablet.close')
                for attempt in range(32):
                    ref=self.capture()
                    try:self.restored(self.original(row['before']),self.original(ref));break
                    except NativeUIError:
                        if attempt==31:raise
                        sleep(.1);self.bound()
                self.state['final']=ref;row['phase']='acknowledged';self.save()
            self.bound();return {'performed':True}
        finally:self.started=None
