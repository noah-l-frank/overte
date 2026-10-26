"""Real private SDK/Installed files for explicitly modeled terminal producers.

The native/SDK/candidate observations remain declared models. Actual ownership
files, original Installed bytes/inodes, frozen decoding and metadata CAS are
not replaced with an in-memory SDK slot or unrelated fixture pathname.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.adapter import IOSNativeMixin
from ios.adapters.installed_code import InstalledCodeBinding


def bind(domain,test):
    base=domain.runtime.adapter;domain.metadata_admissions={};scopes={};bundles={}
    def sdk(selector):return PrivateFeatureState(base.state_path(selector))
    for role,native in domain.natives.items():
        gate=domain.installed[role];old=gate.store.path;target=base.state_path(role).with_name('installed-code-binding.json')
        before=(old.stat().st_dev,old.stat().st_ino,old.read_bytes());test.assertFalse(os.path.lexists(target))
        old.rename(target)
        test.assertEqual(before,(target.stat().st_dev,target.stat().st_ino,target.read_bytes()))
        gate.store=PrivateFeatureState(target);gate.binding=gate.make()
        test.assertIsNone(sdk(role).read());sdk(role).write(deepcopy(native.state),None)
        scopes[role]=deepcopy(gate.scope);bundles[role]=deepcopy(gate.native.bundle)
        domain.metadata_admissions[role]=dict(installedOriginal=before,installedPath=target,previousInstalledPath=old)
    def save(selector,value):
        current=sdk(selector).read();need(current is not None and type(value) is dict)
        for key in ('sessionId','generation','targetFingerprint'):
            need(value.get(key)==current.get(key)==scopes[selector][key]
                and type(value[key]) is type(scopes[selector][key]))
        sdk(selector).write(deepcopy(value),current)
        # The modeled SDK server still identifies requests by its admitted
        # session. Host metadata reads below never fall back to this descriptor.
        domain.natives[selector].state=deepcopy(value)
    def candidate(selector,scope):
        native=domain.natives[selector]
        need(scope==scopes[selector] and scope['targetFingerprint']==native.fingerprint()
            and native.target['appId']==bundles[selector]['bundleId'])
        return deepcopy(native.target)
    def decode(selector,scope,value):
        candidate(selector,scope)
        class Frozen:
            def read(self):return deepcopy(value)
        def forbidden():raise AssertionError('Frozen historical metadata must not acquire native or SDK sources')
        return InstalledCodeBinding(Frozen(),scope,bundles[selector],forbidden,forbidden,forbidden).record()
    base.read_session=lambda selector:sdk(selector).read()
    base.save_session=save
    base._binding_store=lambda selector:domain.installed[selector].store
    base.reset_launch_state=lambda selector,state:IOSNativeMixin.reset_launch_state(base,selector,state)
    base._retired_candidate_scope=candidate
    base._avatar_retired_binding_record=decode
