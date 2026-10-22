"""Once-only Pico Chat restart inputs and original unbound read-only sources.

No bootstrap/repair, retry, session discard or process-death verdict is hidden
inside this transport. RestartInputs and the whole parent own durable admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time

from adapters.android_process_query import AndroidProcessQuery
from adapters.native_chat_profile_current import NativeChatProfileCurrent,FILE as PROFILE_FILE,command as profile_command
from adapters.native_feature_observation import NativeFeatureObservation,FILE as NATIVE_FILE,integer,need
from adapters.native_process_presence import NativeProcessPresence,FILE as PRESENCE_FILE,command as presence_command
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same

VERSION=1
PACKAGE='org.overte.pico'


def process(value):
    need(type(value) is str and re.fullmatch('[1-9][0-9]{0,9}:[1-9][0-9]{0,19}',value))
    pid,start=map(int,value.split(':'));need(integer(pid,1,2147483647));return pid,start


class PicoChatRestartIO:
    def __init__(self,adapter,target,binding,*,monotonic=time.monotonic,sleep=time.sleep):
        context(binding);need(adapter.pico_configuration is not None and adapter.profile['package']==PACKAGE
            and binding['targetFingerprint']==hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest()
            and callable(monotonic) and callable(sleep))
        self.adapter,self.target,self.binding=adapter,target,deepcopy(binding);self.pid,self.start=process(binding['processIdentity'])
        self.monotonic,self.sleep=monotonic,sleep;self.stop_called=self.launch_called=False
        self.installed=deepcopy(adapter._installation(target));self.guard_candidate()
        self.session=adapter.pico_input_session(target);self.transfer=self.session.original_binding_transfer()
        try:
            self.cursor=self.transfer.capture();need(self.cursor['state']['processIdentity']==binding['processIdentity'])
            self.activity=adapter.profile.get('e2e_activity',PACKAGE+'/.E2eLauncherActivity')
            self.arguments=adapter.debug_launcher_arguments(target)
            need(type(self.arguments) is tuple and type(self.activity) is str and self.activity.startswith(PACKAGE+'/') and len(self.activity)<=256
                and all(type(value) is str and 0<len(value)<=8192 for value in self.arguments) and len(self.arguments)<=32)
            self.guard_candidate();self.last_process_query=None
        except Exception:self.transfer.close_host();raise

    def guard_candidate(self):
        self.adapter.require(self.target);need(self.adapter.profile['package']==PACKAGE)
        need(self.binding['targetFingerprint']==hashlib.sha256((self.target+'\0'+str(self.adapter.pico_configuration)).encode()).hexdigest())
        installed=self.adapter._installation(self.target)
        need(all(installed[key]==self.binding[key] for key in ('sourceRevision','artifactSha256')))
        if hasattr(self,'installed'):need(same(installed,self.installed))
        return True

    def stop(self,before_input):
        need(callable(before_input) and not self.stop_called);self.stop_called=True
        self.guard_candidate();identity=self.binding['processIdentity']
        need(self.adapter.require_controlled_debug_identity(self.target)==identity
            and self.adapter.require_pico_session_identity(self.target)==identity)
        self.adapter.require_same_process(self.target,identity,'original once-only Chat stop')
        need(self.transfer.capture()==self.cursor);self.guard_candidate()
        before_input() # Final original admission; the next call is the one SDK command.
        self.adapter.adb.shell(self.target,'am','force-stop',PACKAGE)
        return dict(requested=True) # Never absence, scope release or cursor retirement.

    def stopped(self):
        self.guard_candidate()
        source=AndroidProcessQuery(self.adapter.adb,PACKAGE,self.guard_candidate,monotonic=self.monotonic)
        receipt=source.read(self.target,self.pid);self.guard_candidate()
        self.last_process_query=deepcopy(receipt)
        running=bool(receipt['processIds'])
        return dict(running=running,identity=self.binding['processIdentity'] if running else None)

    def launch(self,before_input):
        need(callable(before_input) and not self.launch_called);self.launch_called=True
        self.guard_candidate();need(self.stopped()==dict(running=False,identity=None))
        current=self.adapter.adb.process_state(self.target,PACKAGE)
        need(current.get('running') is False and current.get('identity') is None
            and self.adapter.profile.get('e2e_activity',PACKAGE+'/.E2eLauncherActivity')==self.activity
            and tuple(self.adapter.debug_launcher_arguments(self.target))==self.arguments)
        need(self.transfer.capture()==self.cursor);self.guard_candidate()
        arguments=('am','start','-W','-n',self.activity,*self.arguments)
        before_input()
        self.adapter.adb.shell(self.target,*arguments)
        return dict(requested=True)

    def unbound_sources(self):
        """Read a new controlled process BEFORE replacing the original cursor.

        This uses the existing original raw debug identity, native writer and
        private result readers. It cannot send an input or use a stop ACK as
        ESRCH. A new process must separately prove all original joins.
        """
        self.guard_candidate();identity=self.adapter.controlled_debug_identity(self.target)
        pid,start=process(identity);need(pid!=self.pid and start>self.start)
        def guard():
            self.guard_candidate()
            need(self.adapter.controlled_debug_identity(self.target)==identity
                and self.adapter.adb.foreground_package(self.target)==PACKAGE)
            self.guard_candidate();return True
        def send(command):
            action=command.get('action')
            if action=='feature-native-observe':
                need(set(command)=={'schemaVersion','commandId','action'} and type(command['schemaVersion']) is int
                    and command['schemaVersion']==1 and type(command['commandId']) is str and re.fullmatch('[0-9a-f]{32}',command['commandId']))
            elif action=='feature-process-presence':presence_command(command)
            elif action=='feature-chat-profile-current':profile_command(command)
            else:raise NativeUIError('Unbound Chat restart transport accepts read-only original sources only')
            guard();self.adapter.write_control_command(self.target,identity,'original unbound Chat restart source',command)
        def read(filename):
            guard();return self.adapter.adb.read_debug_app_file(self.target,PACKAGE,'files/overte-e2e/'+filename,attempts=1)
        clock=lambda:self.adapter.adb.epoch_milliseconds(self.target)
        native=NativeFeatureObservation(send,lambda:read(NATIVE_FILE),clock,guard,pid,monotonic=self.monotonic,sleep=self.sleep)
        presence=NativeProcessPresence(send,lambda:read(PRESENCE_FILE),clock,guard,pid,monotonic=self.monotonic,sleep=self.sleep)
        profile=NativeChatProfileCurrent(send,lambda:read(PROFILE_FILE),clock,guard,pid,monotonic=self.monotonic,sleep=self.sleep)
        guard();return identity,native,presence,profile

    def close_host(self):return self.transfer.close_host()
