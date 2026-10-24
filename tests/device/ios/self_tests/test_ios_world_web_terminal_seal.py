"""Real bounded carriers; role/window/native payloads are grammar sentinels.

These storage tests do not qualify native cleanup or process retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore,LIMIT
from adapters.script_feature.history import canonical
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import projection
from ios.adapters.world_web_terminal_seal import KEY,original,project,verify
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebTerminalSealTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.root.chmod(0o700)
        self.store=OriginalFrameStore(self.root,BINDING,'a'*32,'primary',lambda:True,lambda *_args:None,
            namespace='ios-world-web-terminal',schema_prefix='iosWorldWebTerminal')
        binding=binding_from_context(BINDING)
        self.roles={role:dict(retained=role) for role in terminal.ROLES}
        self.description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='world-web',runId='a'*32,ticket='b'*32,
            roles={role:dict(binding=deepcopy(binding),heldResources=[],originalSha256=digest(self.roles[role])) for role in terminal.ROLES})
        self.samples=[]
        for index in range(3):
            primary=dict(schemaVersion=1,contractVersion=16,runId='a'*32,sequence=index+1,capturedEpochMs=100000+index*1600,
                state=deepcopy(SCENARIOS['world-web']['baseline']),artifacts=[],resources=[],lifecycle=dict(backgrounds=0,activations=1,launches=1))
            actor=dict(ticket='b'*32,actor='owned-observer',actorSequence=index+1,capturedEpochMs=primary['capturedEpochMs'],
                receivedEpochMs=primary['capturedEpochMs']+10,facts=projection('world-web',primary['state']),sequence=index+1)
            self.samples.append(dict(primary=primary,actor=actor))
        terminal.window(self.samples,self.description)

    def seal(self,measured):
        return dict(featureTerminalSealVersion=1,description=deepcopy(self.description),windowSha256=digest(self.samples),
            liveOriginalSha256=digest(dict(roles=self.roles,window=measured)))

    def test_large_graph_is_retained_separately_and_bounded_projection_reads_both_versions(self):
        # Real child original bytes, not a digest standing in for a native fact.
        children=[]
        for index in range(2):
            child=OriginalFrameStore(self.root,BINDING,'a'*32,'primary',lambda:True,lambda *_args:None,
                namespace='seal-test-child-'+str(index),schema_prefix='sealTestChild')
            ref=child.write(1,dict(payload='x'*600000,index=index));children.append((child,ref))
        measured=[child.read(child.expand(ref)) for child,ref in children]
        seal=self.seal(measured);legacy={KEY:1,'samples':self.samples,'measured':measured,'seal':seal}
        self.assertGreater(len(canonical(legacy)),LIMIT)
        with self.assertRaises(NativeUIError):self.store.write(1,legacy)
        value=project(self.samples,measured,seal);reference=self.store.write(1,value)
        self.assertLess(reference['bytes'],10000)
        retained=self.store.read(self.store.expand(reference));self.assertEqual(measured,verify(retained,measured,self.roles))
        small=dict(original='literal historical sentinel');legacy={KEY:1,'samples':self.samples,'measured':small,'seal':self.seal(small)}
        self.assertEqual(legacy,original(legacy));self.assertEqual(small,verify(legacy,small,self.roles))
        owner=object.__new__(WorldWebTerminal);owner.frames=self.store;owner.state=dict(records=[reference,reference])
        self.assertEqual(value,owner.private(2))
        returned=verify(retained,measured,self.roles);returned[0]['payload']='caller mutation'
        self.assertEqual(measured,verify(retained,measured,self.roles))

    def test_rehashed_changed_graph_or_roles_cannot_replace_the_sealed_original_join(self):
        measured=dict(source='original',nonce='old');seal=self.seal(measured);value=project(self.samples,measured,seal)
        changed=dict(source='original',nonce='other')
        with self.assertRaises(NativeUIError):verify(value,changed,self.roles)
        repaired=project(self.samples,changed,seal)
        with self.assertRaises(NativeUIError):verify(repaired,changed,self.roles)
        with self.assertRaises(NativeUIError):verify(value,measured,dict(primary={},actor={}))
        changed=deepcopy(value);changed['samples'][0]['primary']['capturedEpochMs']-=1
        with self.assertRaises(ValueError):verify(changed,measured,self.roles)

    def test_actual_missing_changed_or_same_bytes_replaced_children_are_not_recovered_from_hash(self):
        child=OriginalFrameStore(self.root,BINDING,'a'*32,'primary',lambda:True,lambda *_args:None,
            namespace='seal-test-child',schema_prefix='sealTestChild')
        reference=child.write(1,dict(nonce='actual-original'));expanded=child.expand(reference);path=child.path(expanded)
        measured=child.read(expanded);value=project(self.samples,measured,self.seal(measured))
        self.assertEqual(measured,verify(value,child.read(expanded),self.roles))
        raw=path.read_bytes();replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):verify(value,child.read(expanded),self.roles)
        path.write_bytes(raw.replace(b'actual-original',b'changed-original'))
        with self.assertRaises(NativeUIError):verify(value,child.read(expanded),self.roles)
        path.unlink()
        with self.assertRaises(FileNotFoundError):verify(value,child.read(expanded),self.roles)

    def test_closed_schema_rejects_boolean_future_ambiguous_and_invalid_hash(self):
        value=project(self.samples,{},self.seal({}))
        for mode in ('boolean','future','ambiguous','hash'):
            changed=deepcopy(value)
            if mode=='boolean':changed[KEY]=True
            elif mode=='future':changed[KEY]=3
            elif mode=='ambiguous':changed['measured']={}
            else:changed['measuredSha256']='a'*63
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):original(changed)


if __name__=='__main__':unittest.main()
