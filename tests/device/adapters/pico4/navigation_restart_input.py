"""Original once-only Stop/Launch SDK boundary for the explicit Navigation step.

No bootstrap, retry, pose/setting setter, UI input or retirement is performed.
The original predecessor Session is retained by the restart owner before its
managed current entry is rotated for the genuinely new application process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib

from adapters.native_feature_observation import need
from adapters.pico4.navigation_restart import NavigationRestart
from adapters.pico4.navigation_originals import read_original
from adapters.script_journey.history import same


def issue_once(adapter,target,operation,owner):
    need(isinstance(owner,NavigationRestart) and operation in ('app.stop','app.launch')
        and adapter.pico_configuration is not None)
    owner.scope();plan=owner.inputs.read();binding=owner.binding
    need(owner.state['phase']=='prepared' and same(plan['oldBinding'],binding)
        and plan['phase']==('stop-issued' if operation=='app.stop' else 'launch-issued')
        and binding['targetFingerprint']==hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest())
    adapter.require(target);installed=adapter._installation(target)
    need(all(installed[key]==binding[key] for key in ('sourceRevision','artifactSha256')))
    if operation=='app.stop':
        need(adapter.require_controlled_debug_identity(target)==binding['processIdentity']
            and adapter.require_pico_session_identity(target)==binding['processIdentity']
            and adapter.adb.foreground_package(target)=='org.overte.pico')
        adapter.require_same_process(target,binding['processIdentity'],'owned Navigation restart Stop')
        arguments=('am','force-stop','org.overte.pico')
    else:
        # This independent original OS query may inspect only; a missing app
        # never invites bootstrap or repeating a formerly issued Launch.
        stopped=owner.stopped();need(type(stopped) is dict and stopped==dict(running=False,identity=None))
        activity=adapter.profile.get('e2e_activity','org.overte.pico/.E2eLauncherActivity')
        extra=adapter.debug_launcher_arguments(target)
        need(type(activity) is str and activity.startswith('org.overte.pico/') and len(activity)<=256
            and type(extra) is tuple and all(type(value) is str for value in extra))
        arguments=('am','start','-W','-n',activity,*extra)
    need(adapter._installation(target)==installed)
    # All actual SDK/candidate/process guards precede this final exact phase.
    owner.fence()
    session=adapter.pico_input_session(target)
    with session._lock():
        current=session._load()
        need(same(current,owner.state['session']) and same(read_original(session.state_path),owner.state['sessionFile']))
        if operation=='app.stop':need(same(current,owner.state['session']))
        else:
            need(same(current,owner.state['session']))
            owner.publish(operation)
            if current is not None:
                # Same canonical managed entry as discard_local_state(). Its
                # original exact body survives unchanged in the owner ledger.
                session.state_path.unlink()
        owner.publish(operation)
        adapter.adb.shell(target,*arguments)  # Exactly one original SDK input.
    return dict(requested=True)
