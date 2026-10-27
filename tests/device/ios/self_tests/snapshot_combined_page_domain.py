"""Ordinary Page boundary with independently produced Combined work originals.

Qt/V8/UIKit/native clocks and AFC are declared host models. The production
Page/Capture coordinators, W3C calls, CAS, host files and OS lock execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from ios.self_tests.snapshot_page_domain import SnapshotPageDomain
from ios.self_tests.snapshot_combined_capture_domain import CombinedCaptureDomain,ClockedOwner,RUN
from ios.self_tests.snapshot_combined_work_fixture import packet,entry
from ios.self_tests.test_ios_snapshot_completion import BASE


class CombinedPageDomain(SnapshotPageDomain):
    def __init__(self,case,**kwargs):
        capture=CombinedCaptureDomain(case);capture_effect=capture.capture_effect
        super().__init__(case,capture=capture,**kwargs)
        # This independent producer is initialized before any original is
        # persisted. No stored Separate1 source packet is converted or retimed.
        self.work_original=packet(BASE);row=self.work_original['source']['workers'][0]
        for state in (row['state'],row['events'][0]['state'],row['latest']['state']):state['open']=self.route=='snapshot'
        self.fault=None
        def captured():
            capture_effect();_before,after=self.f.work();model=after['source']['workers'][0]
            current=self.work_original['source']['workers'][0];revision=current['state']['revision'];call=self.call
            for original in model['events'][1:]:
                event=deepcopy(original);self.work_cursor+=1
                event.update(sequence=self.work_cursor,callerSequence=self.work_cursor,call=call+original['call'],callerStackId='c'*32)
                event['state']['revision']+=revision;current['events'].append(event)
            self.call=call+2;current['state']=deepcopy(event['state']);current['latest']=deepcopy(event)
            native=self.work_original['source']['timerSources']['workers'][0]['timerWork']
            native['timers']=[dict({key:deepcopy(value) for key,value in timer.items() if key!='callerChain'},callerStackId='f'*32)
                for timer in after['source']['timerSources']['workers'][0]['timerWork']['timers']]
            native['callerStacks']=[entry('f'*32,('system/snapshot.js','system/snapshot/featureSnapshotWork.js','defaultScripts.js'),BASE)]
        capture.capture_effect=captured

    def transition(self,opened):
        count=len(self.work_original['source']['workers'][0]['events']);super().transition(opened)
        for event in self.work_original['source']['workers'][0]['events'][count:]:event['callerStackId']='c'*32
        self.work_original['source']['workers'][0]['latest']['callerStackId']='c'*32

    def work_packet(self,query):
        # The inherited producer advances only actual modeled query/event
        # counters. Its optional retained timer is supplied here in the closed
        # Combined shape rather than borrowing Separate1 native identities.
        held=self.held_work;self.held_work=False
        try:value=super().work_packet(query)
        finally:self.held_work=held
        value['source']['workers'][0]['latest']['callerStackId']='d'*32
        if held:
            from ios.self_tests.snapshot_combined_work_fixture import timer
            row=timer(value,BASE);row.update(entered=0,left=0,pendingDispatch=1,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
        if self.fault:self.fault(value)
        return value

    def owner(self,*,combined=True):
        return ClockedOwner(self.runtime.page_owner('primary',RUN,self.capture.client(),combined=combined),self.capture)
