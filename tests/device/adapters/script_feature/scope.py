"""Explicit host-only ownership transfer, preserving the actual open UI."""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# Platform input and clocks are supplied by the owning runtime.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import fresh, need, number
from adapters.native_script_observation import NativeScriptObservation, measured_effect
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from adapters.script_ui_inventory import ui_state
from feature_journeys.contract import identifier
from adapters.script_feature.ui_source import ScriptUISource
from adapters.script_feature.measurements import owned_tree

VERSION = 1


def transfer_file_scope(run, manager, execution, ui):
    """Retire a proved stopped file scope into missing-URL input ownership.

    Native fixture ownership stays separate and unchanged. This sends only
    original observation requests; it never closes/reopens the actual page.
    """
    try:
        identifier(run)
        need(isinstance(manager,NormalScriptManager) and manager.source_kind=='script-file-bundle'
             and isinstance(execution,NativeScriptObservation) and isinstance(ui,ScriptUISource)
             and execution.pid==ui.pid==manager.file_owner.native.pid
             and manager.binding['processIdentity'].split(':')[0]==str(execution.pid))
        started=previous=manager.monotonic();need(number(started,0,1e15))
        def check():
            nonlocal previous
            manager.require_current()
            need(execution.guard() is not False and ui.guard() is not False)
            now=manager.monotonic();need(number(now,0,1e15) and previous<=now and now-started<20)
            previous=now
        check()
        need(manager.file_owner.owned()['runId']==run)
        need(manager.state['tabletOwned'] and manager.state['managerOwned'] and not manager.state['pickerOwned']
             and not manager.state['dialogOwned'] and not manager.state['loadAttempted']
             and manager.state['fileOwner'] is not None and manager.state['source'] is not None)
        directory=manager.file_owner.verify();owner=deepcopy(manager.file_owner.owned())
        need(directory==manager.state['fileOwner']['directory']);manager.check_file_owner(manager.state['fileOwner']);check()
        packet=execution.read(execution.sequence,require_effects=True,require_code_identity=True,
            require_load_history=True,require_membership=True)
        need(packet['instance']==manager.file_owner.native.instance)
        need(not any(owned_tree(engine['url'],directory)
            or any(owned_tree(module['url'],directory) for module in engine['required']['modules'])
            for engine in packet['source']['engines']))
        need(not any(row['assigned'] and owned_tree(row['url'],directory) for row in packet['source']['membership']['managers'])
             and measured_effect(packet,owner['runId']) is None)
        check();visual_packet=ui.capture();visual=ui_state(visual_packet);check()
        need(visual['open'] and not visual['picker'] and not visual['systemPending'])
        service=manager.sample_full();check()
        need(not any(owned_tree(row['url'],directory) or owned_tree(row['path'],directory) for row in service['scripts']))
        epoch=execution.clock_ms();check()
        for captured in (packet['capturedEpochMs'],visual_packet['capturedEpochMs'],service['sampleEpochMs']):fresh(captured,epoch)
        need(manager.file_owner.owned()==owner)
        original=deepcopy(manager.previous)
        replacement={key:deepcopy(value) for key,value in original.items()
                     if key not in {'fileOwnershipVersion','fileOwner','pickerOwned'}}
        replacement.update(schemaVersion=4,sourceKind='feature-script-missing',source=None,loadAttempted=False,
                           missingLoadVersion=1,missingLoad=None)
        # Validate the exact next schema using its existing strict constructor,
        # before the one private CAS. No product action occurs in construction.
        class Snapshot:
            def read(self):return deepcopy(replacement)
        NormalScriptManager(manager.ui,manager.observe,Snapshot(),manager.binding,
            source_kind='feature-script-missing',component_only=manager.file_owner.component_only)
        check();manager.store.write(replacement,original)
        need(manager.store.read()==replacement and execution.guard() is not False and ui.guard() is not False)
        now=manager.monotonic();need(number(now,0,1e15) and previous<=now and now-started<20)
        return deepcopy(replacement) # Private input/cleanup intent, not measured state.
    except Exception:
        raise NativeUIError('Script scope transfer sources are unavailable or inconsistent') from None
