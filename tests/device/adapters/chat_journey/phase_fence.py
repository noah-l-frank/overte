"""Fresh original fixture admission around an actual Chat input boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0

from adapters.chat_journey.flow_inputs import ChatFlowInputs
from adapters.native_feature_observation import need
from adapters.phase_input_fence import PhaseInputFence

VERSION=1


def bind_phase_fence(owner,fence):
    need(type(fence) is ChatPhaseFence)
    previous=getattr(owner,'phase_fence',None)
    need(previous is None or previous is fence)
    owner.phase_fence=fence


class ChatPhaseFence(PhaseInputFence):
    """Independent HTTP/clock reads only; never read Qt, UI or input ACKs.

    mark belongs before the child's durable intent. check belongs after its
    last durable write, immediately before actual command publication. There
    is no retry, late source adoption or freshness reset after a failed check.
    """
    def __init__(self,flow,*,cleanup=None):
        need(type(flow) is ChatFlowInputs)
        if cleanup is not None:
            from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
            need(type(cleanup) is ChatCleanupAdmission and cleanup.flow is flow)
        self.cleanup=cleanup
        self.flow=flow
        super().__init__(flow.source)

    def original(self):
        self.flow.roles[0].locks[0].assert_held()
        if self.cleanup is not None:
            need(not self.failed);return self.cleanup.original()
        need(not self.failed and self.flow.rows and self.flow.rows[-1]['phase']=='issued')
        return self.flow.rows[-1]['before']
