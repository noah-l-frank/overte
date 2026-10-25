"""Same existing SDK with actual production worker and explicit OS models.

No duplicate Actor stop/session owner is introduced. Candidate selection is
the existing immutable metadata fixture; production CLI candidate preflight
remains a separate integration gate. Worker.run, source, terminal and original
SDK/OS reader implementations execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.tablet_web_host_clock import advance
import os
import sys
import cProfile
import io
from pathlib import Path
import pstats
import signal
import time
import traceback
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.tablet_web_observer import run
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,SELECTOR,ACTOR
from ios.self_tests.tablet_web_lifecycle_fixture import attach,ExistingLifecycleAdapter
from ios.self_tests.tablet_web_retired_fixture import TabletRetiredModel
from ios.self_tests.tablet_web_actor_profile import source_audit
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TerminalPairedTabletFixture(PairedTabletFixture):
    def __init__(self,test):
        super().__init__(test);self.lifecycle=attach(self,model_type=TabletRetiredModel)


def production_actor(inputs,clock,pipe):
    try:
        root,metadata,settings,fixture_url,base=inputs
        def monotonic():return clock.value
        def epoch():return base+round(clock.value*1000)+10000
        def sleep(duration):advance(clock,duration);time.sleep(duration)
        runtime=IOSTabletWebRuntime(ExistingLifecycleAdapter(root,metadata))
        config=dict(target=SELECTOR,runId=RUN,fixtureUrl=fixture_url,actorToken=ACTOR,durationSeconds=1800,
            physicalBinding=settings['physicalBinding'],setupNative=settings['setupNative'],origins=settings['origins'],
            screen=dict(artifactRoot=settings['artifactRoot'],policy=settings['imagePolicy']))
        pipe.send(dict(hostProcessId=os.getpid(),workerEntered=True))
        failures=[]
        def trace(frame,event,argument):
            if frame.f_code is not run.__code__:return None
            if event=='exception':
                _kind,error,_tb=argument
                # Actual test diagnostics only: the production failure journal
                # and run() exception/exit behavior remain unchanged.
                original=error;seen=set()
                while original.__context__ is not None and id(original) not in seen:seen.add(id(original));original=original.__context__
                failures.append(dict(kind=type(error).__name__,line=frame.f_lineno,
                    originalKind=type(original).__name__,originalTraceback=''.join(traceback.format_exception(original))))
                if len(failures)>8:failures.pop(0)
            return trace
        profile=cProfile.Profile();profile_enabled=os.environ.get('OVT_TABLET_WORKER_PROFILE')=='1'
        def save_profile():
            if not profile_enabled:return
            profile.disable();stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(35)
            Path('.ios-host-tmp/tablet-web-production-actor-profile-'+str(os.getpid())+'.log').write_text(stream.getvalue())
        def terminated(_number,frame):
            save_profile()
            Path('.ios-host-tmp/tablet-web-production-actor-stack-'+str(os.getpid())+'.log').write_text(''.join(traceback.format_stack(frame)))
            raise SystemExit(130)  # Actual failed-test teardown, not worker completion.
        signal.signal(signal.SIGTERM,terminated)
        previous=sys.gettrace();sys.settrace(trace)
        if profile_enabled:profile.enable()
        try:code=run(runtime,config,epoch_ms=epoch,monotonic=monotonic,sleep=sleep)
        finally:sys.settrace(previous);save_profile()
        pipe.send(dict(hostProcessId=os.getpid(),workerReturned=code,diagnostics=failures,audit=source_audit()))
    except Exception as error:pipe.send(dict(hostProcessId=os.getpid(),error=type(error).__name__,traceback=traceback.format_exc()))
    finally:pipe.close()
