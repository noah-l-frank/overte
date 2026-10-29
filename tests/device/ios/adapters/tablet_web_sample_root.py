"""Owned second32-screen epoch beside the unchanged original Sample1 WAL.

Every PNG still has the original WDA receipt, raw fragments, before/after
source frames and unchanged1.5s page/clock join. This introduces no capture,
native freshness, GPU or whole-feature fact independent of those originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters import tablet_web_child_rotation as header,tablet_web_rotation_fence as fence
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_aggregate_root import TabletWebAggregateRoot
from ios.adapters.tablet_web_samples import TabletWebSamples

VERSION=1
OWNER_VERSION=2
EPOCH_SIZE=32


def canonical_name(run,role):return 'tabletweb-screen-samples-'+run+'-'+role+'.json'


def root_name(run,role):return 'tabletweb-screen-root-'+run+'-'+role+'.json'


def legacy_header(value,source,root,policy):
    exact(value,{'tabletWebSamplesVersion','binding','runId','role','artifactRoot','policy','payload'})
    need(type(value['tabletWebSamplesVersion']) is int and value['tabletWebSamplesVersion']==1
        and same(value['binding'],source.binding) and value['runId']==source.run and value['role']==source.role
        and value['artifactRoot']==str(root) and same(value['policy'],policy))
    rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
    exact(state,{'records','pending','original','nextRaw'})
    need(type(state['records']) is list and len(state['records'])==EPOCH_SIZE
        and state['pending'] is state['original'] is None)
    return state


class TabletWebSampleRoot(TabletWebSamples):
    def __init__(self,runtime,root,policy,*,historical=False,tail_validator=None):
        source=runtime.observer.source
        need(type(source) is TabletWebAggregateRoot and type(historical) is bool)
        self.runtime,self.source=runtime,source
        self.binding,self.run,self.role,self.lock=source.binding,source.run,source.role,source.lock
        self.root=Path(root);need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.policy=deepcopy(policy);exact(policy,{'source','marker','subject'});need(policy['source']=='native-screen')
        need(tail_validator is None or historical and callable(tail_validator))
        self.tail_validator=runtime.validate_tail_source if tail_validator is None else runtime._image_tail_validator(tail_validator)
        self.historical=historical;self.started=self.last=None;self.failed=False
        self.parent_store=PrivateFeatureState(source.root/canonical_name(self.run,self.role))
        raw,self.parent_signature=header._raw(self.parent_store.path);self.parent_sha=hashlib.sha256(raw).hexdigest()
        self.legacy=legacy_header(self.parent_store.read(),source,self.root,self.policy)
        self.store=PrivateFeatureState(source.root/root_name(self.run,self.role));self.saved=self.store.read()
        need(self.saved is not None)
        exact(self.saved,{'tabletWebSamplesVersion','tabletWebSampleRootVersion','binding','runId','role','artifactRoot','policy','parent','payload'})
        need(type(self.saved['tabletWebSamplesVersion']) is int and self.saved['tabletWebSamplesVersion']==OWNER_VERSION
            and type(self.saved['tabletWebSampleRootVersion']) is int and self.saved['tabletWebSampleRootVersion']==VERSION
            and same(self.saved['binding'],self.binding) and self.saved['runId']==self.run and self.saved['role']==self.role
            and self.saved['artifactRoot']==str(self.root) and same(self.saved['policy'],self.policy)
            and self.saved['parent']==dict(signature=self.parent_signature,sha256=self.parent_sha))
        exact(self.saved['parent'],{'signature','sha256'})
        fence._signature(self.saved['parent']['signature'],self.saved['parent']['signature']['bytes'])
        rows=unpack(self.saved['payload']);need(len(rows)==1);self.state=rows[0]
        self._parent_guard();self._original_storage();self.decode()

    def _parent_guard(self):
        self.lock.assert_held();self.source._parent_guard()
        raw,signature=header._raw(self.parent_store.path)
        need(signature==self.parent_signature and hashlib.sha256(raw).hexdigest()==self.parent_sha
            and same(legacy_header(self.parent_store.read(),self.source,self.root,self.policy),self.legacy))
        return True

    def record_references(self):return self.legacy['records']+self.state['records']

    def file_guard(self):
        self._parent_guard();return super().file_guard()

    def screen_guard(self):return self.file_guard

    def save(self):
        self.live();self._parent_guard()
        value=dict(tabletWebSamplesVersion=OWNER_VERSION,tabletWebSampleRootVersion=VERSION,
            binding=self.binding,runId=self.run,role=self.role,artifactRoot=str(self.root),policy=self.policy,
            parent=dict(signature=self.parent_signature,sha256=self.parent_sha),payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)

    def decode(self):
        self._parent_guard()
        roots=[self.source.root]
        if not self.root.is_relative_to(self.source.root):roots.append(self.root)
        leases=[EmoteOriginalLease(root,[]) for root in roots]
        result=super().decode()
        need(all(self.originals.read(self.originals.expand(ref))['status']=='returned' for ref in self.legacy['records']))
        self._parent_guard()
        for lease in leases:lease.guard()
        return result

    def recover_original(self):
        """Adopt only the actual complete new-epoch original, never resend GET."""
        self.live();self.decode();reference=self.state['original'];row=self.state['pending']
        need(len(self.state['records'])<EPOCH_SIZE and reference is not None and row is not None and row['status']=='returned'
            and reference['phase'] in ('opened','saved') and reference['index']==self._next_index())
        inspection=self.pending_original();need(inspection is not None and inspection['complete'])
        actual=self.originals.read(reference);need(same(actual,row));self.record(actual,reference['index'])
        # Both source fences, raw PNG bytes, original screen receipt and pixel
        # policy must qualify before the same original may join this WAL.
        before=self.runtime.validate_tail_source(row['before']);after=self.runtime.validate_tail_source(row['after'])
        from ios.adapters.tablet_web_image_measurements import compose
        compose(self.run,row['ticket'],self.binding,before,after,row['png']['capture'],self.raw.read(row['archive']),self.policy)
        compact=self.originals.compact(dict(reference,phase='saved'))
        self.state['records'].append(compact);self.state['pending']=self.state['original']=None;self.save()
        self.read(compact);self.decode();return deepcopy(compact)

    def cleanup_files(self):
        # The existing normal Feature cleanup calls this exact method. Only
        # a complete already-owned original can settle a lost local return.
        # Unknown/partial native delivery stays owned; never issue another GET.
        self.live();self.decode()
        if self.state['pending'] is not None or self.state['original'] is not None:self.recover_original()
        return super().cleanup_files()

    def files_absent(self):
        self.decode();need(self.state['pending'] is self.state['original'] is None)
        return super().files_absent()


def samples_owner(runtime,root,policy,*,historical=False,tail_validator=None,for_capture=False):
    """Literal default; second epoch requires actual owned Source4 and32 rows."""
    need(type(for_capture) is bool and (not historical or not for_capture))
    source=runtime.observer.source;path=source.root/root_name(source.run,source.role)
    if os.path.lexists(path):return TabletWebSampleRoot(runtime,root,policy,historical=historical,tail_validator=tail_validator)
    owner=TabletWebSamples(runtime,root,policy,historical=historical,tail_validator=tail_validator)
    if not for_capture or type(source) is not TabletWebAggregateRoot or len(owner.state['records'])<EPOCH_SIZE:return owner
    # The unchanged default decoded every original/receipt/source fence above.
    # No screenshot, query, input, native source or grant is created here.
    source.bound();need(owner.state['pending'] is owner.state['original'] is None)
    state=legacy_header(owner.saved,source,owner.root,owner.policy)
    need(all(owner.originals.read(owner.originals.expand(ref))['status']=='returned' for ref in state['records']))
    raw,signature=header._raw(owner.store.path)
    value=dict(tabletWebSamplesVersion=OWNER_VERSION,tabletWebSampleRootVersion=VERSION,
        binding=source.binding,runId=source.run,role=source.role,artifactRoot=str(owner.root),policy=owner.policy,
        parent=dict(signature=signature,sha256=hashlib.sha256(raw).hexdigest()),
        payload=pack([dict(records=[],pending=None,original=None,nextRaw=state['nextRaw'])]))
    PrivateFeatureState(path).write(value,None)
    return TabletWebSampleRoot(runtime,root,policy)
