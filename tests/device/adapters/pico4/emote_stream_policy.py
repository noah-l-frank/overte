"""Original Parent policy for opt-in passive remote source4, before source IO.

SDK clock anchors are explicit execution policy, never native attestation or
measured pose/effect evidence. The same old Parent owns all input and120s.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path

from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import raw_file
from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
from adapters.script_journey.history import canonical,same

VERSION=1
ROLE_FRAMES=256
INTERVAL_MS=500
UNRESOLVED=[]


class PicoEmoteStreamPolicy:
    """One immutable role budget admitted at the SAME baseline-issued Parent.

    ``roles`` contains actual resolved binding+SDK clock callbacks, not desired
    observations. Its two frozen allowances sum512; neither arm nor reads may
    create another policy or reset either original clock.
    """
    def __init__(self,parent,roles):
        need(type(parent) is PicoEmoteNativeCycle and type(roles) is dict and set(roles)=={'primary','actor'})
        self.parent=parent;self.source=parent.source;self.lock=self.original_lock=parent.source.lock;self.lock.assert_held();parent.bound()
        need(parent.state is not None and parent.state['phase']=='baseline-issued' and parent.state['baseline'] is None
            and not parent.state['steps'] and not parent.source.frames and parent.inputs.previous is None)
        self.host=host_identity();self.run=parent.source.run;self.parent_identity=canonical(parent.identity)
        self.started=parent.state['started'];self.deadline=self.started+120
        self.native_epoch=parent.state['epochMs'];self.provider_epoch=parent.state['hostEpochMs']
        self.path=self._path=parent.store.path.with_name(parent.store.path.name+'.child-stream-budget.json')
        self.baseline_path=self._baseline_path=parent.store.path.with_name(parent.store.path.name+'.child-stream-baseline.json')
        self._lock_path=self.lock.path
        self.store=PrivateFeatureState(self.path);self.failed=False;self.previous=self.disk=None
        self.budget_file=self.baseline_file=None
        for bound in roles.values():exact(bound,{'binding','clock'});context(bound['binding']);need(callable(bound['clock']))
        self.original_roles=tuple((role,deepcopy(roles[role]['binding']),roles[role]['clock']) for role in ('primary','actor'))
        need(self.store.read() is None and not self.baseline_path.exists()
            and not any(p.name.startswith(self.path.name+'.') for p in self.path.parent.iterdir()))
        try:
            parent.file.guard();raw,physical=raw_file(parent.store)
            need(raw==canonical(parent.previous)+b'\n' and same(parent.previous['state'],parent.state))
            self.baseline_sha=hashlib.sha256(raw).hexdigest()
            descriptor=os.open(self.baseline_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400)
            with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            self.baseline_file=ClosedOriginalFile(self.baseline_path,0o400,self.host_identity)
            observed,pin=self.baseline_file.read();need(observed==raw)
            self.baseline_pin=pin;policies={};bindings={}
            for role,binding,clock in self.original_roles:
                parent.bound();native_now=clock();now=parent.source.monotonic();parent.bound()
                need(integer(native_now,1) and number(now,self.started,self.deadline) and now<self.deadline)
                epoch=self.native_epoch if role=='primary' else native_now
                need(native_now>=epoch)
                # The later Actor SDK anchor gets ONLY the remaining original
                # host window. It is not backdated as a fabricated sample.
                end=min(epoch+120000,native_now+int((self.deadline-now)*1000))
                need(epoch<end<=epoch+120000)
                policy=dict(picoRemoteAvatarStreamPolicyVersion=VERSION,runId=self.run,role=role,
                    parentScopeSha256=hashlib.sha256(self.parent_identity).hexdigest(),parentBaselineSha256=self.baseline_sha,
                    parentHostProcessIdentity=self.host,processId=int(binding['processIdentity'].split(':')[0]),
                    originalNativeEpochMs=epoch,deadlineNativeEpochMs=end,
                    originalHostStartedMonotonic=repr(self.started),originalHostDeadlineMonotonic=repr(self.deadline),
                    nativeFrameLimit=ROLE_FRAMES,sampleIntervalMs=INTERVAL_MS)
                policies[role]=canonical(policy).decode('ascii');bindings[role]=deepcopy(binding)
            need(bindings['primary']==parent.source.binding and bindings['primary']!=bindings['actor'])
            self.disk=dict(picoEmoteStreamBudgetVersion=VERSION,parentIdentity=deepcopy(parent.identity),
                baselineSha256=self.baseline_sha,baselinePhysical=list(physical),baselineCopyPhysical=pin,
                policyAnchorKind='original-sdk-clock-execution-policy-not-native-attestation',
                originalHostStartedMonotonic=self.started,originalHostDeadlineMonotonic=self.deadline,
                originalParentNativeEpochMs=self.native_epoch,originalProviderEpochMs=self.provider_epoch,
                bindings=bindings,policies=policies,totalNativeFrameAllowance=512)
            self.store.write(self.disk,None);actual,unused=raw_file(self.store)
            need(actual==canonical(self.disk)+b'\n');self.raw=actual
            self.budget_file=ClosedOriginalFile(self.path,0o600,self.host_identity)
            observed,self.budget_pin=self.budget_file.read();need(observed==self.raw)
            self.original=self.original_pins=(self.parent,self.lock,self.path,self.baseline_path,self.raw,self.started,self.deadline,
                self.native_epoch,self.provider_epoch,self.parent_identity,self.original_roles,self.disk)
            self.bound()
        except BaseException:
            self.failed=True;UNRESOLVED.append(self);raise

    def host_identity(self):
        # Already issued returns retain their own immutable policy/file/OFD
        # authority after a lost or expired business Parent. No send/read here.
        need(host_identity()==self.host and self.path==self._path and self.baseline_path==self._baseline_path
            and self.path.parent==self.baseline_path.parent and self.store.path==self._path
            and self.lock is self.original_lock and self.lock.path==self._lock_path)

    def identity(self):
        self.host_identity();need(not self.failed and self.original is self.original_pins and self.disk is self.original[-1]
            and self.parent.source is self.source and self.source.lock is self.lock
            and self.original_roles is self.original[-2] and self.original==(self.parent,self.lock,self.path,self.baseline_path,
            self.raw,self.started,self.deadline,self.native_epoch,self.provider_epoch,self.parent_identity,self.original_roles,self.disk))
        need(canonical(self.disk)+b'\n'==self.raw and self.parent_identity==canonical(self.parent.identity))
        raw,pin=self.budget_file.read();need(raw==self.raw and pin==self.budget_pin)
        raw,pin=self.baseline_file.read();need(hashlib.sha256(raw).hexdigest()==self.baseline_sha and pin==self.baseline_pin)

    def bound(self):
        self.lock.assert_held();self.identity();self.parent.bound()
        need(self.parent.state is not None and self.parent.state['started']==self.started
            and self.parent.state['epochMs']==self.native_epoch and self.parent.state['hostEpochMs']==self.provider_epoch
            and self.parent.source.monotonic()<self.deadline)
        self.identity()

    def policy(self,role):
        need(role in ('primary','actor'));self.bound();return self.disk['policies'][role]

    def close_host(self):
        result=all([reader.close() for reader in (self.budget_file,self.baseline_file) if reader is not None])
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
