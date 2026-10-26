"""Normal page/recording W3C boundary sharing one declared native clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.script_feature.history import unpack
from ios.adapters.normal_input import observation
from ios.self_tests.test_ios_audio_page_inputs import PageModel
from ios.self_tests.test_ios_audio_completion_owner import AutomaticModel


class AudioPageCycleDomain(AutomaticModel):
    @property
    def clock(self):return self.page_model.clock
    @clock.setter
    def clock(self,value):self.page_model.clock=value

    def __init__(self,root):
        self.page_model=PageModel(root);self.page_capture=self.page_model.capture
        super().__init__();self.instance=self.page_model.instance
        self.page_model.capture=self.capture
        def actual_intents():
            raw=self.owner.store.read();state=unpack(raw['payload'])[0];pending=state['pending'];need(pending is not None)
            return dict(intents={row['label']:dict(control=row['identifier'],element=row['element'])
                for row in pending['inputs'] if row['verb']=='page'})
        self.page_model.store=SimpleNamespace(read=actual_intents)
        original_call=self.page_model.native.client.call
        def call(method,path,body=None):
            if method=='POST' and path.endswith('/click'):
                element=path.split('/element/',1)[1].split('/',1)[0]
                control,token=self.page_model.elements[element]
                if control in ('audio.record','audio.mute','audio.mode.desktop','audio.mode.vr'):
                    self.activate(control,token=token);return None
            return original_call(method,path,body)
        self.page_model.native.client.call=call
        self.page_model.native.check_continuity=self.guard

    def capture(self):
        if self.page_model.route=='audio':
            value=super().capture()
            value['controls'].extend([self.page_model.row('tablet.home'),self.page_model.row('tablet.close')])
        else:
            import uuid
            self.tick();self.owner.query_intent(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe'))
            value=self.page_capture()
        value['lastSequence']=self.inputs+self.page_model.sequence
        value['instance']=self.instance
        return observation(value,42,self.native_epoch())

    def io(self):
        result=super().io();result.original.ui=self.page_model.native;return result
