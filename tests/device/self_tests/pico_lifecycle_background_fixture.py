"""Existing native background model on the canonical SDK/UI/Feature objects.

OS, native Qt and SDK remain declared models. Only executed ordinary SDK
commands produce application-state effects; no requested checkpoint supplies
the original history, current editor, text, keyboard or lifecycle counters.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import lifecycle_background_source as source
from adapters.script_journey.history import unpack
from self_tests.test_pico_lifecycle_background_source import Native


class CanonicalLifecycleBackgroundModel:
    def __init__(self,target):
        self.target=target;self.foreground=True;self.backgrounds=0;self.activations=1
        self.inputs=[];self.rejected_queries=[];self.ignore=self.lost=None
        self.history=Native();self.history.host=target.native.clock;self.history.epoch=target.native.epoch()
        self.path=target.root/'lifecycle-background-owner.json'
        history=self.history;frame=history.frame
        def actual_frame(cause):
            frame(cause)
            target.native.ui.send(dict(commandId=uuid.uuid4().hex,runId=target.run))
            packet=target.native.ui.value
            rows=[row for row in packet['source']['editors'] if row['id']==packet['source']['current']]
            need(len(rows)==1 and rows[0]['kind']=='chat' and rows[0]['id']==history.original)
            keyboard=packet['source']['keyboard'];value=history.frames[-1]
            value.update(uiInstance=packet['instance'],uiSequence=packet['sequence'],
                uiCapturedEpochMs=packet['capturedEpochMs'],tabletShown=packet['source']['tabletShown'],
                onHomeScreen=packet['source']['onHomeScreen'],currentId=packet['source']['current'],
                editor=deepcopy(rows[0]),focusedEditors=sum(row['focused'] for row in packet['source']['editors']))
            value['keyboard']={key:keyboard[key] for key in ('instance','sequence','created','enabled','visible','raised')}
            value['keyboard'].update(keyCount=len(keyboard['keys']),pressedKeys=sum(row['pressed'] for row in keyboard['keys']))
        history.frame=actual_frame
        target_model=self
        class Pending:
            def read(self):
                value=PrivateFeatureState(target_model.path).read();need(value is not None)
                return dict(inputs=deepcopy(unpack(value['payload'])[0]['inputs']))
        history.pending=Pending()
        sleep=target.native.sleep
        def timer(seconds):
            sleep(seconds);history.host=target.native.clock;history.epoch=target.native.epoch()
            if history.active:history.frame('timer')
        target.native.sleep=timer
        shell=target.os.shell
        def actual_shell(selector,*arguments,**options):
            operation=('lifecycle.background' if arguments==('input','keyevent','KEYCODE_HOME') else
                       'app.launch' if arguments[:4]==('am','start','-W','-n') else None)
            if operation is None:return shell(selector,*arguments,**options)
            need(selector==target.target)
            value=PrivateFeatureState(self.path).read();need(value is not None)
            state=unpack(value['payload'])[0]
            need(state['phase']==('home-issued' if operation=='lifecycle.background' else 'resume-issued'))
            self.inputs.append(dict(operation=operation,arguments=list(arguments),pid=target.os.identity,
                capturedEpochMs=target.native.epoch()))
            if self.ignore!=operation:
                self.foreground=operation=='app.launch'
                self.backgrounds+=not self.foreground;self.activations+=self.foreground
                current=[row for row in target.native.ui.rows if row['current']]
                need(len(current)==1 and current[0]['kind']=='chat')
                current[0]['focused']=False;target.native.ui.raised=False
                target.chat.focus=False;target.chat.keyboard_request=False
                history.host=target.native.clock;history.epoch=target.native.epoch()
                history.publish('active' if self.foreground else 'hidden');target.native.clock=history.host
            if self.lost==operation:raise RuntimeError('Original modeled OS reply lost after actual SDK effect')
            return ''
        target.os.shell=actual_shell
        foreground=target.os.foreground_package
        target.os.foreground_package=lambda selector:foreground(selector) if self.foreground else 'com.android.launcher'
        feature=target.products.case.native_producer;mutate=feature.mutate
        def activity(value):
            mutate(value);value['lifecycle'].update(backgrounds=self.backgrounds,activations=self.activations)
        feature.mutate=activity
        dispatch=target.products.dispatch
        def native(action,value):
            if action in ('ui','gesture','drive','pending','feature','subject') and not self.foreground:
                self.rejected_queries.append(action);need(False)
            if action=='background':
                history.host=target.native.clock;history.epoch=target.native.epoch()
                history.send(value);return history.raw
            return dispatch(action,value)
        target.products.dispatch=native
        read,write=target.os.read_debug_app_file,target.os.write_debug_app_file
        def original(selector,package,path,**options):
            if path!='files/overte-e2e/'+source.FILE:return read(selector,package,path,**options)
            need(selector==target.target and package=='org.overte.pico');return history.raw
        def command(selector,package,path,raw):
            if path!=source.COMMAND:return write(selector,package,path,raw)
            need(selector==target.target and package=='org.overte.pico')
            native('background',json.loads(raw))
        target.os.read_debug_app_file=original;target.os.write_debug_app_file=command
