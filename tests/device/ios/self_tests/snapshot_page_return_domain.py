"""One original main instance for normal page entry, Pending and PNG capture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from adapters.native_feature_observation import need
from ios.self_tests.snapshot_journey_files_domain import SnapshotJourneyFilesDomain
from ios.self_tests.snapshot_page_domain import SnapshotPageDomain
from ios.self_tests.snapshot_pending_domain import RUN,REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_share_archive_end_domain import SourceArchiveEndFlow
from ios.self_tests.snapshot_share_domain import SYSTEM_UI
from ios.adapters import snapshot_share_runtime
from unittest.mock import patch


class PageJourneyDomain(SnapshotPageDomain):
    def __init__(self,case):
        main=SnapshotJourneyFilesDomain(case);self.actual_work=main.work_packet
        main.script_state['open']=False
        for row in main.script_events:row['state']['open']=False
        main.activations=[dict(sequence=1,ticket='a'*32,activatedEpochMs=main.epoch()-1,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png')))]
        super().__init__(case,capture=main)
    def work_packet(self,query):return self.actual_work(query)
    def transition(self,opened):
        main=self.capture;main.call_sequence+=1;call=main.call_sequence
        closure='onMessage' if opened else 'onClosingWindow';main.event('entry',closure,call)
        main.script_state.update(open=opened,revision=main.script_state['revision']+1)
        main.event('returned',closure,call);main.event('finally',closure,call)
    @contextmanager
    def owner(self):
        with self.runtime.page_owner('primary',RUN,self.capture.client()) as owner:
            owner.epoch_ms=lambda:int(REAL_TIME()*1000);owner.monotonic=REAL_MONOTONIC;owner.sleep=self.capture.sleep
            owner.phase.epoch_ms=owner.epoch_ms;owner.phase.monotonic=REAL_MONOTONIC;yield owner
    def prepare_png(self):
        with self.owner() as owner:opened=owner.open('a'*32)
        main=self.capture;main.advance()
        main.activations.append(dict(sequence=2,ticket='f'*32,activatedEpochMs=main.epoch(),stimulus=dict(verb='capture-cancel',inputs=dict(mode='animated',format='png'))))
        with main.owner() as pending_owner:pending=pending_owner.cancel('f'*32)
        main.advance();main.activations.append(dict(sequence=3,ticket='c'*32,activatedEpochMs=main.epoch(),stimulus=dict(verb='capture',inputs=dict(mode='still',format='png'))))
        with main.capture_owner() as capture:
            captured=capture.capture('c'*32);need(capture.state['phaseOriginal']['activations']==main.activations)
            phase=deepcopy(capture.state['phaseOriginal'])
        return dict(page=opened,pending=pending,capture=captured,phase=phase)


class PageReturnFlow(SourceArchiveEndFlow):
    def advance(self):self.main.advance()
    def client(self):
        client=super().client();request=client.request
        def current(*args,**kwargs):self.advance();return request(*args,**kwargs)
        client.request=current;return client
    def prepare_main(self,case):
        self.page=PageJourneyDomain(case);prepared=self.page.prepare_png();main=self.page.capture
        main.runtime._sources=self.page.runtime._sources
        return main,deepcopy(prepared['phase']['activations']),prepared['phase']['createdEpochMs']
    def __init__(self,case):
        super().__init__(case);self.runtime.existing_input_session=self.main.runtime.existing_input_session
    @contextmanager
    def return_owner(self):
        def primary(runtime,selector,binding):
            need(runtime is self.runtime and selector=='primary' and binding==self.primary.binding);return self.primary
        with patch.object(snapshot_share_runtime,'PhotosClientContext',primary):
            with self.runtime.page_return_owner('primary',RUN,self.client(),self.archive_config(),
                    SYSTEM_UI,
                    epoch_ms=lambda:REAL_TIME()*1000,monotonic=REAL_MONOTONIC,sleep=self.main.sleep) as owner:yield owner
