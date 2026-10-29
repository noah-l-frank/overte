"""Explicit new-test native boundary around fresh actual passive JS reads.

The native envelope/clock remains modeled. Each DOM body is a new actual
page.read(commandId) from one persistent original generated app/reference JS;
stored bodies, original reference events and source clocks are never retimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from ios.self_tests.test_ios_tablet_web_source_owner import Boundary
from ios.self_tests.tablet_web_echo_fixture import actual_js
from ios.self_tests.test_ios_tablet_web_sources import stamp


class FreshEchoBoundary(Boundary):
    def __init__(self,case,original):
        super().__init__(original);self.native_epoch=None
        self.dom_session,_app=actual_js(session=True);case.addCleanup(self.dom_session.close)
    def native(self):
        # The current clock is not the parity of the PREVIOUS query. Preserve
        # monotonic current native time across reader construction and expose
        # freshly produced callback time after the original send, unchanged.
        reader=super().native();declared=reader.send
        def clock():return max(self.native_epoch or 0,self.epoch-100)
        def send(query):
            declared(query)
            packet=json.loads(self.native_raw)
            assert type(packet['capturedEpochMs']) is int
            self.native_epoch=max(self.native_epoch or 0,packet['capturedEpochMs'])
        reader.clock_ms=clock;reader.send=send;return reader
    def reader(self,name):
        reader=super().reader(name)
        if name!='dom':return reader
        declared=reader.send
        def send(query):
            declared(query)
            # This body is freshly produced by original passive observer JS,
            # not a copy of an already-saved snapshot with fields changed.
            current=self.dom_session.read(query['commandId'],self.epoch)
            assert type(current['capturedEpochMs']) is int and current['capturedEpochMs']>=self.epoch
            self.epoch=current['capturedEpochMs']
            packet=json.loads(self.raw['dom']);packet['source']['dom']=current
            packet['clockBefore']=packet['clockAfter']=stamp(self.epoch)
            self.raw['dom']=json.dumps(packet)
        reader.send=send;return reader
