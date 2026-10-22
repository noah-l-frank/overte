"""Mandatory audio-controls foundation through normal tokenized Audio UI."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.token_audio_ui import TokenAudioUI
from overte_phone_script_history import same
from overte_phone_script_lock import PhoneScriptSourceLock


class PhoneAudioMute:
    def __init__(self,adapter,selector,store):
        self.adapter,self.selector,self.store=adapter,selector,store
        self.lock=PhoneScriptSourceLock(store.path.with_name('phone-script-sources.lock'))
        self.previous=self.state=None

    def save(self):
        self.lock.assert_held();self.store.write(self.state,self.previous);need(same(self.store.read(),self.state));self.previous=deepcopy(self.state)

    def load(self):
        self.previous=self.store.read();self.state=deepcopy(self.previous)
        _ui,_service,self.binding,self.guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        if self.state is not None:
            exact(self.state,{'audioMuteVersion','binding','originalMuted','requested','phase','intents'})
            need(type(self.state['audioMuteVersion']) is int and self.state['audioMuteVersion']==1 and same(context(self.state['binding']),self.binding) and type(self.state['originalMuted']) is bool and type(self.state['requested']) is bool and self.state['phase'] in ('ready','issued','observed') and type(self.state['intents']) is list and len(self.state['intents'])<=64)

    def controls(self):
        def intent(verb,ui,control):
            need(len(self.state['intents'])<64);self.state['intents'].append(dict(verb=verb,control=control,ui=deepcopy(ui)));self.save()
        return self.adapter._audio_controls(self.selector,intent)

    def native(self):
        value=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)
        need(not value['audio']['recording'] and not value['audio']['recordedVoice']['active']);self.guard();return value

    def open(self,ui):
        value=ui.capture()
        if ui.row(value,'audio.page') is not None:
            need(any(row['verb'] in ('open-audio','open-audio-settings') for row in self.state['intents']));return
        if ui.row(value,'audio.entry',ready=True):ui.activate('audio.entry','open-audio')
        else:
            if ui.row(value,'audio.settings-entry',ready=True) is None:
                ui.activate('settings.entry','open-settings');ui.wait(lambda value:ui.row(value,'audio.settings-entry',ready=True) is not None)
            ui.activate('audio.settings-entry','open-audio-settings')
        ui.wait(lambda value:ui.row(value,'audio.page') is not None)

    def act(self,enabled,*,cleanup=False):
        need(type(enabled) is bool)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();native=self.native()
            if self.state is None:
                if cleanup:return {'performed':True}
                ui=self.adapter._audio_controls(self.selector,lambda *_:need(False),read_only=True);need(ui.row(ui.capture(),'audio.page') is None)
                self.state=dict(audioMuteVersion=1,binding=deepcopy(self.binding),originalMuted=native['audio']['muted'],requested=enabled,phase='ready',intents=[]);self.save()
            if cleanup:enabled=self.state['originalMuted']
            if self.state['phase']=='observed':
                ui=self.controls();need(ui.row(ui.capture(),'audio.page') is None)
                if not cleanup:need(native['audio']['muted']==self.state['requested'])
                if enabled==self.state['requested']:
                    need(native['audio']['muted']==enabled)
                    if enabled==self.state['originalMuted']:self.store.discard(self.previous);self.previous=self.state=None
                    return {'performed':True}
                self.state['intents']=[];self.save()
            if self.state['phase']=='issued' and not cleanup:
                # Do not redeliver an uncertain toggle; resolve only from the
                # new original native value of its exact prior request.
                need(native['audio']['muted']==self.state['requested'])
            if self.state['requested']!=enabled or self.state['phase']=='ready':
                self.state.update(requested=enabled,phase='ready');self.save()
            ui=self.controls();self.open(ui);ui.current_mode()
            if self.state['phase']=='ready':
                self.state['phase']='issued';self.save();ui.mute(enabled)
            need(self.native()['audio']['muted']==enabled);self.state['phase']='observed';self.save()
            ui.activate('audio.back','back-audio');ui.wait(lambda value:ui.row(value,'audio.page') is None)
            need(self.native()['audio']['muted']==enabled)
            if enabled==self.state['originalMuted']:
                self.store.discard(self.previous);need(self.store.read() is None);self.previous=self.state=None
            return {'performed':True}

    def cleanup(self):return self.act(False,cleanup=True)
