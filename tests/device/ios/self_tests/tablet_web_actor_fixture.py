"""Separate host observer process using the real current Feature publisher.

The pipe carries process/publication scheduling metadata only. Native models,
shared boundary clocks and SDK transport are declared by paired_fixture. No
Primary product facts are an input to this worker.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.tablet_web_host_clock import advance
import os
import time
import traceback
from adapters.script_feature.lock import ScriptSourceBusy
from adapters.phase_witness_publisher import PublicationPending
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.witness import Client
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime,TabletObservationPending
from ios.adapters.tablet_web_source_owner import TabletSourcePhaseChanged
from ios.self_tests.tablet_web_paired_fixture import ExistingAdapter,SELECTOR,ACTOR
from ios.self_tests.test_ios_tablet_web_sources import RUN
from ios.self_tests.tablet_web_actor_profile import source_audit


def actor_until_stopped(inputs,clock,stop,pipe):
    try:
        root,metadata,settings,fixture_url,base=inputs
        def monotonic():return clock.value
        def epoch():return base+round(clock.value*1000)+10000
        def sleep(duration):advance(clock,duration)
        runtime=IOSTabletWebRuntime(ExistingAdapter(root,metadata));client=Client(fixture_url,ACTOR,monotonic=monotonic,sleep=sleep)
        feature=runtime._tablet_web_feature(SELECTOR,RUN,role='actor',client=client,settings=settings)
        feature.monotonic,feature.epoch_ms,feature.sleep=monotonic,epoch,sleep
        first=True;pending=[]
        def diagnostic(kind,detail):
            row=dict(kind=kind,detail=detail)
            if row not in pending:
                pending.append(row)
                if len(pending)>8:pending.pop(0)
        while not stop.is_set():
            try:
                sequence=feature.publish()
                if first and sequence is not None:pipe.send(dict(hostProcessId=os.getpid(),firstSequence=sequence));first=False
                if not first and sequence is None:
                    diagnostic('NoPublicationReturned',None if feature.state is None else feature.state['phase'])
            except (ScriptSourceBusy,PhasePending,TabletObservationPending,TabletSourcePhaseChanged,PublicationPending) as observed:
                if not first:diagnostic(type(observed).__name__,traceback.format_exc())
            # This yields real host CPU; it supplies no native/quiet time.
            time.sleep(.02)
        # Transfer bounded private diagnostics only when the worker exits.
        # Debug traffic must not block an active publication on a full pipe.
        pipe.send(dict(hostProcessId=os.getpid(),testWindowEnded=True,audit=source_audit(),pendingDiagnostics=pending))
    except Exception as error:
        seen=set();original=error
        while original.__context__ is not None and id(original) not in seen:
            seen.add(id(original));original=original.__context__
        pipe.send(dict(hostProcessId=os.getpid(),error=type(error).__name__,traceback=traceback.format_exc(),
            originalError=type(original).__name__,originalTraceback=''.join(traceback.format_exception(original))))
    finally:pipe.close()
