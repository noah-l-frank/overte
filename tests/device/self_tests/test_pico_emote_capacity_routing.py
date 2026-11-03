"""Concrete early-refusal/no-fallback regressions; native remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid

from adapters.host_process_identity import host_identity
from adapters.pico4.emote_stream_capacity import descriptor
from adapters.pico4.emote_stream_frame import control_command
from adapters.script_journey.history import canonical
from self_tests.pico_emote_capacity_routing_model import CaptureRoutingModel
from self_tests.test_pico_emote_stream_capacity import StreamCapacityTests,RETAINED


class StreamRoutingTests(StreamCapacityTests):
    def policies(self):
        capacity=self.active();m=self.model;clocks=capacity.state['originalClocks']
        # A declared execution POLICY, not a relabelled native observation.
        old=dict(picoRemoteAvatarStreamPolicyVersion=1,runId=m.parent.source.run,role='actor',processId=31,
            parentScopeSha256=hashlib.sha256(canonical(m.parent.identity)).hexdigest(),parentBaselineSha256=hashlib.sha256(m.baseline_parent_bytes).hexdigest(),
            parentHostProcessIdentity=host_identity(),originalNativeEpochMs=clocks[1],deadlineNativeEpochMs=clocks[1]+120000,
            originalHostStartedMonotonic=repr(clocks[0]),originalHostDeadlineMonotonic=repr(clocks[0]+120),
            nativeFrameLimit=256,sampleIntervalMs=500)
        new=dict(old,picoRemoteAvatarStreamPolicyVersion=2,**descriptor());return canonical(old).decode(),canonical(new).decode()

    def arm_request(self,policy):
        return control_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-remote-avatar-stream-control',
            operation='arm',runId=self.model.parent.source.run,subjectSessionId=self.model.streams['actor'].subject_id,ownerPolicy=policy))

    def router(self):return CaptureRoutingModel(self.model.scope_root,lambda:self.model.m.s.clock,self.model.m.tick)

    def original(self,name='world-render-observation.json'):
        path=self.model.scope_root/name;path.write_bytes(b'actual retained prior original');path.chmod(0o600);return path

    def test_explicit_policy2_selected_before_queue_remote_lifecycle_and_expired_arm_refusals(self):
        old,new=self.policies();path=self.original();raw=path.read_bytes()
        for failure in ('queue','remote','lifecycle','late'):
            with self.subTest(failure=failure):
                router=self.router();router.failure=failure
                self.assertFalse(router.arm(self.arm_request(new)))
                self.assertTrue(router.selected);self.assertFalse(router.save(path.name,b'forbidden legacy bytes'))
                self.assertFalse(router.remove(path.name));self.assertEqual(raw,path.read_bytes())
                self.assertEqual((0,0),(router.legacy_writes,router.legacy_removes));self.assertEqual(1,len(router.requests))

    def test_selected_policy2_absent_publisher_never_deletes_or_overwrites_real_original(self):
        old,new=self.policies();path=self.original('world-render-storage-'+uuid.uuid4().hex+'.json');raw=path.read_bytes()
        router=self.router();router.failure='publisher';self.assertFalse(router.arm(self.arm_request(new)))
        self.assertFalse(router.remove(path.name));self.assertFalse(router.save(path.name,b'replaced'))
        self.assertEqual(raw,path.read_bytes());self.assertEqual((0,0),(router.legacy_writes,router.legacy_removes))

    def test_malformed_duplicate_and_string_policy2_cannot_restore_legacy_route(self):
        old,new=self.policies();path=self.original();raw=path.read_bytes()
        duplicate=new[:-1]+',"picoRemoteAvatarStreamPolicyVersion":1}'
        variants=(new[:-1],duplicate,new.replace('"picoRemoteAvatarStreamPolicyVersion":2','"picoRemoteAvatarStreamPolicyVersion":"2"'))
        for value in variants:
            router=self.router();router.failure='queue';self.assertFalse(router.arm(self.arm_request(value)))
            self.assertTrue(router.selected);self.assertFalse(router.save(path.name,b'forbidden'));self.assertFalse(router.remove(path.name))
        self.assertEqual(raw,path.read_bytes())

    def test_exact_canonical_legacy_policy1_keeps_original_file_behavior(self):
        old,new=self.policies();router=self.router();self.assertTrue(router.arm(self.arm_request(old)))
        self.assertFalse(router.selected);self.assertTrue(router.save('world-render-observation.json',b'legacy actual byte payload'))
        self.assertEqual(b'legacy actual byte payload',(self.model.scope_root/'world-render-observation.json').read_bytes())
        self.assertTrue(router.remove('world-render-observation.json'));self.assertEqual((1,1),(router.legacy_writes,router.legacy_removes))
