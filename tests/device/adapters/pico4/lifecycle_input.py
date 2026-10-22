"""One original process-preserving Pico OS input with final owned admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.normal_feature_state import context


def issue_once(adapter,target,operation,binding,*,before_input):
    context(binding);binding=deepcopy(binding)
    need(operation in ('lifecycle.background','app.launch') and callable(before_input)
        and adapter.pico_configuration is not None and binding['targetFingerprint']==hashlib.sha256(
            (target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest())
    adapter.require(target)
    installed=adapter._installation(target)
    need(all(installed[key]==binding[key] for key in ('sourceRevision','artifactSha256')))
    identity=binding['processIdentity']
    need(adapter.require_controlled_debug_identity(target)==identity
        and adapter.require_pico_session_identity(target)==identity)
    foreground=adapter.adb.foreground_package(target)
    need(type(foreground) is str and bool(foreground)
        and (foreground=='org.overte.pico')==(operation=='lifecycle.background'))
    adapter.require_same_process(target,identity,'owned once-only lifecycle input')
    need(adapter._installation(target)==installed)
    if operation=='lifecycle.background':arguments=('input','keyevent','KEYCODE_HOME')
    else:
        package='org.overte.pico';activity=adapter.profile.get('e2e_activity',package+'/.E2eLauncherActivity')
        need(type(activity) is str and activity.startswith(package+'/') and len(activity)<=256)
        arguments=('am','start','-W','-n',activity)
    # No guards, retries, probes or bootstrap calls between this admission and
    # the actual original SDK command. A lost response remains uncertain.
    before_input()
    try:adapter.adb.shell(target,*arguments)
    finally:
        adapter.require_same_process(target,identity,'owned once-only lifecycle input')
        need(adapter.require_pico_session_identity(target)==identity and adapter._installation(target)==installed)
    return dict(requested=True)
