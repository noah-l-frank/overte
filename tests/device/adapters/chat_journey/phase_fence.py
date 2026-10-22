"""Fresh original fixture admission around an actual Chat input boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.chat_journey.flow_inputs import ChatFlowInputs
from adapters.native_feature_observation import need,number
from adapters.script_journey.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate

VERSION=1


def bind_phase_fence(owner,fence):
    need(type(fence) is ChatPhaseFence)
    previous=getattr(owner,'phase_fence',None)
    need(previous is None or previous is fence)
    owner.phase_fence=fence


class ChatPhaseFence:
    """Independent HTTP/clock reads only; never read Qt, UI or input ACKs.

    mark belongs before the child's durable intent. check belongs after its
    last durable write, immediately before actual command publication. There
    is no retry, late source adoption or freshness reset after a failed check.
    """
    def __init__(self,flow):
        need(type(flow) is ChatFlowInputs)
        source=flow.source
        self.flow=flow;self.source=PhaseFixtureReader(source.client,source.run,source.area,
            epoch_ms=source.epoch_ms,monotonic=source.monotonic)
        self.anchor=None;self.failed=False;self.frames=[]
        self.stream_intent=None
        self.before_send=self._before_send
        self.before_controller=self._before_controller
        self.stage_intent=self.controller_intent

    def _before_send(self,command):
        need(type(command) is dict)
        self.check()

    def _before_controller(self,operation):
        need(operation in ('tablet.open','tablet.close'))
        self.check()

    def original(self):
        self.flow.roles[0].locks[0].assert_held()
        need(not self.failed and self.flow.rows and self.flow.rows[-1]['phase']=='issued')
        return self.flow.rows[-1]['before']

    def read(self,expected):
        result=self.source.read(expected);packet=result['status']
        need(packet['active'] and same(packet['activations'],expected['activations'])
            and result['ticket']==self.flow.rows[-1]['ticket'])
        # The last copy also precedes the final original clock reads.
        original=deepcopy(packet);now=self.source.monotonic();epoch=self.source.epoch_ms()
        validate(original,run=self.source.run,area='chat',request=original['requestId'],epoch=epoch,previous=expected)
        self.frames.append(original);need(len(self.frames)<=512)
        return original,now,epoch

    def mark(self):
        try:
            expected=self.original();started=self.source.monotonic();epoch=self.source.epoch_ms()
            need(number(started,0,1e15) and number(epoch,1,1e16))
            packet,now,current=self.read(expected)
            need(number(now,started,started+1.5) and number(current,epoch,epoch+1500))
            self.anchor=dict(ticket=self.flow.rows[-1]['ticket'],before=deepcopy(expected),packet=packet,
                hostMonotonic=started,epochMs=epoch)
            return self.anchor
        except Exception:self.failed=True;raise

    def host_fresh(self):
        """Pure host check for an already locked original controller callback.

        Callers must perform check() before entering the native session lock.
        This method never performs HTTP, ADB, a guard or session reentry.
        """
        need(not self.failed and self.anchor is not None);now=self.source.monotonic();anchor=self.anchor
        need(number(now,anchor['hostMonotonic'],anchor['hostMonotonic']+1.5)
            and anchor['epochMs']-anchor['packet']['capturedEpochMs']+math.ceil((now-anchor['hostMonotonic'])*1000)<=1500)

    def check(self):
        try:
            expected=self.original();anchor=self.anchor
            need(anchor is not None and anchor['ticket']==self.flow.rows[-1]['ticket'] and same(anchor['before'],expected))
            # A fresh phase response cannot erase time spent in the original
            # child CAS, including a native jump under a frozen host clock.
            now=self.source.monotonic();epoch=self.source.epoch_ms()
            need(number(now,anchor['hostMonotonic'],anchor['hostMonotonic']+1.5)
                and number(epoch,anchor['epochMs'],anchor['epochMs']+1500))
            packet,now,current=self.read(expected)
            need(number(now,anchor['hostMonotonic'],anchor['hostMonotonic']+1.5)
                and number(current,anchor['epochMs'],anchor['epochMs']+1500))
            self.host_fresh();measured=self.source.monotonic();final_epoch=self.source.epoch_ms();ended=self.source.monotonic()
            need(number(measured,now,anchor['hostMonotonic']+1.5) and number(ended,measured,anchor['hostMonotonic']+1.5)
                and number(final_epoch,current,anchor['epochMs']+1500)
                and final_epoch-anchor['epochMs']+math.ceil((ended-measured)*1000)<=1500)
            validate(packet,run=self.source.run,area='chat',request=packet['requestId'],
                epoch=final_epoch+math.ceil((ended-measured)*1000),previous=expected)
            return packet
        except Exception:self.failed=True;raise

    def controller_intent(self,envelope):
        # This callback runs inside the original native session lock. Only
        # original host data and its elapsed-age bound may be touched here.
        try:
            self.host_fresh();need(callable(self.stream_intent))
            self.stream_intent(deepcopy(envelope));self.host_fresh()
        except Exception:self.failed=True;raise
