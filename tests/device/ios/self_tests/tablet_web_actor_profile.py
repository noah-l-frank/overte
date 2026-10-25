"""Commanded real observer calls for bounded original-decoder CPU measurement.

Commands schedule publisher calls only. No expected product fields or Primary
facts are inputs. This is a host diagnostic, not the production worker CLI.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.tablet_web_host_clock import advance
import cProfile
import io
import hashlib
import json
import os
from pathlib import Path
import pstats
import sys
import traceback
from feature_journeys.witness import Client
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.self_tests.tablet_web_paired_fixture import ExistingAdapter,SELECTOR,ACTOR
from ios.self_tests.test_ios_tablet_web_sources import RUN


def source_audit():
    manifest=os.environ.get('OVT_TABLET_PROFILE_FREEZE')
    if not manifest:return None
    start=json.loads(Path(manifest).read_text());root=Path.cwd().resolve();actual={}
    for module in tuple(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            path=Path(file).resolve()
            if path.is_relative_to(root) and path.suffix=='.py':actual[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(actual=actual,drift=[name for name,sha in start.items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha],
        added=sorted(set(actual)-set(start)))


def commanded_actor(inputs,clock,channel):
    root,metadata,settings,fixture_url,base=inputs
    def monotonic():return clock.value
    def epoch():return base+round(clock.value*1000)+10000
    def sleep(duration):advance(clock,duration)
    try:
        runtime=IOSTabletWebRuntime(ExistingAdapter(root,metadata));client=Client(fixture_url,ACTOR,monotonic=monotonic,sleep=sleep)
        feature=runtime._tablet_web_feature(SELECTOR,RUN,role='actor',client=client,settings=settings)
        feature.monotonic,feature.epoch_ms,feature.sleep=monotonic,epoch,sleep
        while True:
            command=channel.recv()
            if command=='end':return
            if command!='publish':raise ValueError('Unknown host diagnostic schedule')
            profiler=cProfile.Profile();profiler.enable()
            try:sequence=feature.publish()
            finally:profiler.disable()
            output=io.StringIO();pstats.Stats(profiler,stream=output).sort_stats('cumulative').print_stats(35)
            channel.send(dict(hostProcessId=os.getpid(),sequence=sequence,profile=output.getvalue(),audit=source_audit()))
    except Exception as error:channel.send(dict(hostProcessId=os.getpid(),error=type(error).__name__,traceback=traceback.format_exc()))
    finally:channel.close()
