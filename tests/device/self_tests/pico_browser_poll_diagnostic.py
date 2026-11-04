"""Passive return decisions for the explicit host Browser diagnostic only.

The original Journey functions execute unchanged, with their own clock reads.
No callback calls a clock, source, artifact, predicate, or producer function.
This is diagnostic evidence and cannot qualify a candidate or device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys


class PollReturns:
    LIMIT = 16384

    def __init__(self, journey_type):
        self.rows = []
        self.codes = {getattr(journey_type, name).__code__: name for name in (
            'poll_original_current', 'poll_witness_current', 'observed_witness')}
        self.tool = None

    def __enter__(self):
        monitor = sys.monitoring
        for tool in range(5, -1, -1):
            if monitor.get_tool(tool) is None:
                monitor.use_tool_id(tool, 'pico-browser-poll-returns')
                self.tool = tool
                break
        if self.tool is None:
            raise RuntimeError('No unowned Python monitoring tool is available')
        try:
            monitor.register_callback(self.tool, monitor.events.PY_RETURN, self.returned)
            for code in self.codes:
                monitor.set_local_events(self.tool, code, monitor.events.PY_RETURN)
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def returned(self, code, _offset, result):
        frame = sys._getframe(1)
        if frame.f_code is not code or len(self.rows) >= self.LIMIT:
            raise RuntimeError('Original Browser poll diagnostic frame or bound changed')
        local = frame.f_locals
        name = self.codes[code]
        owner = local['self']
        row = dict(check=name, precedingPhase=None if not owner.samples else owner.samples[-1]['phase'])
        if name == 'observed_witness':
            okay, witness = result
            row.update(okay=okay, consume=local['consume'], ticket=local['ticket'],
                newCount=len(local['new']), actorSequence=None if witness is None else witness['actorSequence'])
        else:
            value = local['value'] if name == 'poll_original_current' else local['witness']
            row.update(okay=result, captured=local['captured'], epoch=local['epoch'], now=local['now'],
                sequence=value['sequence'])
            if name == 'poll_original_current':
                row.update(started=local['started'], requested=local['requested'])
            else:
                row.update(received=local['received'], epochAtReceipt=local['epoch_at_receipt'],
                    ticket=value['ticket'], actorSequence=value['actorSequence'])
        self.rows.append(row)

    def __exit__(self, *_failure):
        if self.tool is not None:
            monitor = sys.monitoring
            for code in self.codes:
                monitor.set_local_events(self.tool, code, 0)
            monitor.register_callback(self.tool, monitor.events.PY_RETURN, None)
            monitor.free_tool_id(self.tool)
            self.tool = None
