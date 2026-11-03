"""Transport-only Browser DTO owner model; no feature/native/Common proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
import time

import pico_operation_host_worker as base
from adapters.chat_journey.source_chunks import json_digest
from adapters.pico4.browser_operation_protocol import validate
from adapters.pico4.operation_protocol import need


class ProtocolOwner:
    def __init__(self, request):
        self.whole = request['wholeBudget']; self.sha = json_digest(self.whole)
        self.worker = None
        if base.fault == 'browser-factory-timeout': time.sleep(.4)
    def control(self):
        need(self.whole['startedMonotonic'] <= time.monotonic() < self.whole['deadlineMonotonic'])
    def dispatch(self, value):
        validate(value); self.control(); need(json_digest(value['wholeBudget']) == self.sha)
        base.record('browser-private-' + value['operation'])
        return dict(protocolOnly=True, completeCommonObservation=False,
            received=value['operation'], originalBudgetSha256=self.sha)
    def close_host(self):
        self.control(); base.record('browser-close')
    def unwind(self): pass


def owner(_adapter, _target, request, _parent):
    base.record('browser-factory')
    return ProtocolOwner(request)


if __name__ == '__main__':
    base.FakeAdapter._browser_operation_owner = owner
    base.cli.cli = lambda argv=None:(base.args, base.Binding)
    try: raise SystemExit(base.cli.main([]))
    except Exception:
        base.record('rejected'); raise SystemExit(2)
