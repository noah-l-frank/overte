"""Declared native probe producer + actual fixed-script/SDK consumer fixture.

The producer emits its actual modeled probe JSON BEFORE SDK parsing. The
unchanged fixed script reads a real private file through a declared exec-out
facade. No device, ADB server, compiler or Domain is activated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import MethodType,SimpleNamespace
import time
from unittest.mock import patch

from adapters import common
from adapters.android.adapter import AndroidAdapter,ANDROID_DEBUG_PROBE
from adapters.pico4 import probe_originals as source


class NavigationProbeProducer:
    def __init__(self,world,model):
        self.world,self.model=world,model;self.calls=0;self.last_wire=None;self.literal=None;self.post=None
        self.root=Path(tempfile.mkdtemp(prefix='pico-navigation-probe-native-'));self.root.chmod(0o700)
        (self.root/'files').mkdir(mode=0o700);(self.root/'files/overte-e2e').mkdir(mode=0o700)
        self.path=self.root/ANDROID_DEBUG_PROBE
        print('Retained actual modeled probe app-private fixture:',self.root,file=sys.stderr)

    def execute_bytes(self,arguments,*,target,timeout):
        assert target=='owned-model' and arguments[0]=='exec-out' and 0<timeout<=5
        argv=shlex.split(arguments[1]);assert len(argv)==8
        assert argv[:4]==['run-as','org.overte.pico','sh','-c'] and argv[4]==source.SCRIPT
        assert argv[5]=='overte-pico-probe' and argv[7]==str(source.LIMIT+1)
        self.model.guard();self.calls+=1
        if self.literal is None:
            # This is the explicit pre-wire native producer boundary model,
            # not the SDK's returned/parsed DTO. It advances on actual emission.
            packet=self.world.probe(0)
            raw=json.dumps(packet,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        else:raw=self.literal
        with self.path.open('wb') as output:output.write(raw)
        self.path.chmod(0o600)
        completed=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.root,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=timeout,check=False)
        self.last_wire=completed.stdout
        if self.post:self.post()
        return self.last_wire


def install_sdk(test,adapter,world,model):
    if not hasattr(world,'navigation_probe_producer'):
        world.navigation_probe_producer=NavigationProbeProducer(world,model)
    producer=world.navigation_probe_producer
    adapter.kind='pico';adapter.profile=dict(package='org.overte.pico')
    adapter.read_probe_snapshot=MethodType(AndroidAdapter.read_probe_snapshot,adapter)
    adapter.probe_maximum_age_seconds=lambda:1.5
    adapter.adb.execute_bytes=producer.execute_bytes
    return producer


def sdk_model_clock(test,clock_ms):
    # Isolate the modeled OS wall clock used by the ACTUAL SDK freshness
    # validator. Never alter a returned packet, captured stamp or read anchor.
    facade=SimpleNamespace(time=lambda:clock_ms()/1000,sleep=time.sleep,monotonic=time.monotonic)
    change=patch.object(common,'time',facade);change.start();test.addCleanup(change.stop)


def probe_factory(owner,adapter,target,guard,role):
    return source.PicoProbeOriginals(adapter,target,owner.raw,guard,role=role,monotonic=owner.monotonic)
