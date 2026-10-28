"""PARTIAL normal Mute/Echo restore with exact typed-source drift guards.

This cannot restore hidden PTT, permission-driven replacements, every Audio
setting, acoustic/Peer evidence or source/process/SDK lifetimes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.token_audio_ui import TokenAudioUI
from ios.adapters.audio_settings_sources import AudioSettingsSources
from ios.adapters import audio_settings_source as source
from ios.adapters.audio_api_clock import operation
from ios.adapters.normal_input import observation as ui_packet

VERSION=1
CONTROL={'muted':('audio.mute','mute'),'localEcho':('audio.live-echo','live-echo')}


class AudioSettingsOwner:
    def __init__(self,store,sources,io,*,sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,AudioSettingsSources) and callable(sleep)
            and store.path==sources.parent.store.path.with_name('ios-audio-settings-restore.json'))
        self.store,self.sources,self.parent,self.binding,self.run=store,sources,sources.parent,deepcopy(sources.binding),sources.run
        self.monotonic,self.sleep=sources.monotonic,sleep;self.previous=store.read();self.historical=sources.historical
        self.state=dict(baseline=None,operations=[],pending=None,verify=[])
        self.ui=TokenAudioUI(io,self.intent,monotonic=self.monotonic,sleep=sleep)
        if self.previous is not None:self.state=self.decode(self.previous)
    def bound(self):self.sources.bound();need(same(self.store.read(),self.previous));return True
    def save(self):
        need(not self.historical);self.bound();value=dict(iosAudioSettingsOwnerVersion=1,binding=self.binding,runId=self.run,state=deepcopy(self.state))
        self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def packet(self,ref):
        need(ref in self.sources.state['frames']);return self.sources.frame(ref)['originals']['settings']
    def decode(self,value):
        exact(value,{'iosAudioSettingsOwnerVersion','binding','runId','state'})
        need(type(value['iosAudioSettingsOwnerVersion']) is int and value['iosAudioSettingsOwnerVersion']==1 and same(value['binding'],self.binding) and value['runId']==self.run)
        state=deepcopy(value['state']);exact(state,{'baseline','operations','pending','verify'})
        need(type(state['operations']) is list and len(state['operations'])<=2 and type(state['verify']) is list and len(state['verify'])<=4)
        if state['baseline'] is not None:source.admissible(self.packet(state['baseline']))
        else:need(not state['operations'] and state['pending'] is None and not state['verify'])
        rows=state['operations']+([] if state['pending'] is None else [state['pending']]);keys=set()
        for row in rows:
            exact(row,{'key','wanted','admittedBefore','before','after','input','navigation','returned','queries'})
            need(row['key'] in CONTROL and row['key'] not in keys and type(row['wanted']) is bool and type(row['returned']) is bool
                and type(row['queries']) is list and len(row['queries'])<=256);keys.add(row['key'])
            admitted=self.guarded(self.packet(row['admittedBefore']),state);admitted_values=source.selected(admitted)
            need(admitted_values[row['key']]!=row['wanted'])
            seen=set()
            for query in row['queries']:
                self.parent.query(query);need(query['commandId'] not in seen);seen.add(query['commandId'])
            need(type(row['navigation']) is list and len(row['navigation'])<=8)
            for nav in row['navigation']:
                exact(nav,{'verb','identifier','ui','before'})
                need((nav['identifier']=='audio.scrollbar' and nav['verb'] in ('scroll-up','scroll-down'))
                    or nav['identifier'] in ('audio.mode.desktop','audio.mode.vr') and nav['verb']=='select-current-mode')
                self.admitted(self.packet(nav['before']),row,state)
                need(nav['before']['index']>=row['admittedBefore']['index']
                    and (row['input'] is None or nav['before']['index']<=row['before']['index']))
                ui_packet(nav['ui'],self.packet(nav['before'])['processId'],nav['ui']['sampleEpochMs'])
            need(row['wanted']==source.selected(self.packet(state['baseline']))[row['key']])
            self.admitted(self.packet(row['before']),row,state)
            need(row['before']['index']>=row['admittedBefore']['index'])
            if row['input'] is not None:
                value=row['input'];exact(value,{'verb','identifier','ui'})
                need((value['identifier'],value['verb'])==CONTROL[row['key']])
                packet=self.packet(row['before']);ui_packet(value['ui'],packet['processId'],value['ui']['sampleEpochMs'])
                need(0<=packet['clockAfter']['epochMs']-value['ui']['sampleEpochMs']<1500)
                control=TokenAudioUI.row(value['ui'],value['identifier'],ready=True);need(control is not None)
                field='nativeMuted' if row['key']=='muted' else 'nativeEcho'
                need(control[field]==source.selected(packet)[row['key']] and control[field]!=row['wanted'])
            if row['returned']:need(row['input'] is not None)
            if row['after'] is not None:
                need(row['input'] is not None);packet=self.packet(row['after']);self.guarded(packet,state)
                need(row['after']['index']>row['before']['index'] and source.selected(packet)[row['key']]==row['wanted'])
                other=next(key for key in CONTROL if key!=row['key'])
                need(source.selected(packet)[other]==admitted_values[other])
            if row in state['operations']:need(row['after'] is not None)
        for ref in state['verify']:
            packet=self.packet(ref);self.guarded(packet,state);need(same(source.selected(packet),source.selected(self.packet(state['baseline']))))
        return state
    def guarded(self,packet,state=None):
        state=self.state if state is None else state;need(state['baseline'] is not None)
        baseline=self.packet(state['baseline']);need(same(source.guards(packet),source.guards(baseline)))
        source.validate(packet,dict(schemaVersion=1,action=source.ACTION,commandId=packet['requestId'],runId=self.run),packet['processId'])
        return packet
    def admitted(self,packet,row,state=None):
        # Preparation/navigation may change no selected setting. Keep the
        # operation's durable original admission separate from the fresh
        # pre-dispatch cut; an external change must not become a new baseline.
        self.guarded(packet,state)
        need(same(source.selected(packet),source.selected(self.packet(row['admittedBefore']))))
        return packet
    def query_intent(self,query):
        # Actual readonly UI/clock requests outside source capture remain
        # intents owned by the pending input; no unknown input is replayed.
        self.bound();need(self.state['pending'] is not None and len(self.state['pending']['queries'])<256)
        self.parent.query(query);self.state['pending']['queries'].append(deepcopy(query));self.save()
    def intent(self,verb,value,identifier):
        self.bound();row=self.state['pending'];need(row is not None and row['input'] is None)
        if verb in ('scroll-up','scroll-down','select-current-mode'):
            need(len(row['navigation'])<8)
            ref=self.sources.capture('before-input');self.admitted(self.packet(ref),row)
            row['navigation'].append(dict(verb=verb,identifier=identifier,ui=deepcopy(value),before=ref));self.save();return
        need((identifier,verb)==CONTROL[row['key']])
        ref=self.sources.capture('before-input');packet=self.admitted(self.packet(ref),row);need(source.selected(packet)[row['key']]!=row['wanted'])
        row['before']=ref;row['input']=dict(verb=verb,identifier=identifier,ui=deepcopy(value));self.save()
    @operation
    def baseline(self):
        self.bound();need(not self.historical and self.state['baseline'] is None and not self.parent.state['operations'] and self.parent.state['pending'] is None)
        # This capability check precedes normal Open/unmute and all mutation.
        ref=self.sources.capture('baseline');source.admissible(self.packet(ref));self.state['baseline']=ref;self.save();return deepcopy(ref)
    @operation
    def resolve(self):
        self.bound();row=self.state['pending'];need(row is not None and row['input'] is not None)
        ref=self.sources.capture('after-input');packet=self.guarded(self.packet(ref))
        need(source.selected(packet)[row['key']]==row['wanted'])
        other=next(key for key in CONTROL if key!=row['key'])
        need(source.selected(packet)[other]==source.selected(self.packet(row['admittedBefore']))[other])
        # The actual new original resolves effect. A lost return stays false.
        row['after']=ref;self.state['operations'].append(row);self.state['pending']=None;self.save();return deepcopy(ref)
    @operation
    def restore(self):
        self.bound();need(not self.historical and self.state['baseline'] is not None and self.state['pending'] is None and self.parent.state['pending'] is None)
        original=source.selected(self.packet(self.state['baseline']))
        for key in ('localEcho','muted'):
            ref=self.sources.capture('verify');packet=self.guarded(self.packet(ref))
            if source.selected(packet)[key]==original[key]:continue
            need(not any(row['key']==key for row in self.state['operations']))
            self.state['pending']=dict(key=key,wanted=original[key],admittedBefore=deepcopy(ref),before=ref,after=None,input=None,navigation=[],returned=False,queries=[]);self.save()
            identifier,verb=CONTROL[key];control=self.ui.visible(identifier)
            self.ui.activate(identifier,verb,token=control['token'])
            self.state['pending']['returned']=True;self.save();self.resolve()
        return self.verify()
    @operation
    def verify(self):
        self.bound();need(self.state['pending'] is None and self.state['baseline'] is not None and len(self.state['verify'])<4)
        ref=self.sources.capture('verify');packet=self.guarded(self.packet(ref))
        need(same(source.selected(packet),source.selected(self.packet(self.state['baseline']))));self.state['verify'].append(ref);self.save()
        return dict(observedSelectedMuteEchoValuesRestored=True,wholeSettingsRestorationAvailable=False,
            independentAcousticsAvailable=False,processSdkRetirementAvailable=False,original=deepcopy(ref))
