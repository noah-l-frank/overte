"""Selected final-capture costs and ORIGINAL cadence locals; diagnostic only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import inspect
import sys
import time
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
from adapters.pico4.world_render_retirements import PicoWorldRenderRetirements


class RetirementCosts:
    LIMIT=10000

    def __init__(self):
        functions=[ChatArchiveCatalog.verify_all,PicoWorldRenderRetirements.read]
        functions.extend(getattr(PicoBrowserCaptureRetirement,name) for name in
            ('physical_index','physical','admission_bytes','append','write'))
        self.codes={fn.__code__:fn.__qualname__ for fn in functions}
        self.costs={name:[0,0.,0.] for name in self.codes.values()}
        self.run=PicoBrowserCaptureRetirement.run.__code__
        lines,first=inspect.getsourcelines(PicoBrowserCaptureRetirement.run)
        selected=[first+i for i,line in enumerate(lines) if line.strip().startswith("need(0<host-previous['host']")]
        if len(selected)!=1:raise RuntimeError('Original retirement cadence location changed')
        self.cadence_line=selected[0];self.gaps=[];self.stack=[];self.events=0;self.tool=None

    def count(self):
        self.events+=1
        if self.events>self.LIMIT:raise RuntimeError('Selected retirement diagnostic event bound exceeded')

    def started(self,code,_offset):
        self.count();self.stack.append([code,time.perf_counter(),0.])

    def returned(self,code,_offset,_result):
        ended=time.perf_counter();self.count()
        original,started,children=self.stack.pop()
        if original is not code:raise RuntimeError('Selected retirement diagnostic stack changed')
        elapsed=ended-started;row=self.costs[self.codes[code]]
        row[0]+=1;row[1]+=elapsed;row[2]+=elapsed-children
        if self.stack:self.stack[-1][2]+=elapsed

    def line(self,code,line):
        if line!=self.cadence_line:return sys.monitoring.DISABLE
        self.count();frame=sys._getframe(1)
        if frame.f_code is not code:raise RuntimeError('Original cadence diagnostic frame changed')
        local=frame.f_locals
        # Already acquired ORIGINAL clock fields only. No source/clock call,
        # requested-state filter, predicate replacement or timestamp renewal.
        native=[y-x for x,y in zip(local['prior'],local['clocks'])]
        self.gaps.append(dict(hostSeconds=local['host']-local['previous']['host'],
            nativeMinMilliseconds=min(native),nativeMaxMilliseconds=max(native),nativeClocks=len(native)))

    def __enter__(self):
        monitor=sys.monitoring
        self.tool=next((i for i in range(5,-1,-1) if monitor.get_tool(i) is None),None)
        if self.tool is None:raise RuntimeError('No unowned monitoring tool for retirement diagnostic')
        monitor.use_tool_id(self.tool,'pico-browser-retirement-costs')
        try:
            for event,callback in ((monitor.events.PY_START,self.started),(monitor.events.PY_RETURN,self.returned),
                    (monitor.events.LINE,self.line)):
                monitor.register_callback(self.tool,event,callback)
            for code in self.codes:monitor.set_local_events(self.tool,code,monitor.events.PY_START|monitor.events.PY_RETURN)
            monitor.set_local_events(self.tool,self.run,monitor.events.LINE)
        except BaseException:
            self.__exit__(None,None,None);raise
        return self

    def __exit__(self,*_failure):
        if self.tool is not None:
            monitor=sys.monitoring
            for code in (*self.codes,self.run):monitor.set_local_events(self.tool,code,0)
            for event in (monitor.events.PY_START,monitor.events.PY_RETURN,monitor.events.LINE):
                monitor.register_callback(self.tool,event,None)
            monitor.free_tool_id(self.tool);self.tool=None

    def report(self):
        return dict(scope='Selected original finalization methods with declared product producers; completed method spans only, not unprofiled or whole speedup',
            events=self.events,cadence=self.gaps,unreturnedSelectedFrames=[self.codes[frame[0]] for frame in self.stack],
            costs={name:dict(calls=row[0],inclusiveMilliseconds=row[1]*1000,exclusiveMilliseconds=row[2]*1000)
                for name,row in self.costs.items()})
