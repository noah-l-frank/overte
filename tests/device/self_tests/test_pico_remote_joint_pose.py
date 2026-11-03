"""No-build committed-section/copy source checks and explicit native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import unittest

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_remote, remote_joint_pose
from adapters.pico4.avatar_remote_source import PicoRemoteAvatarSource, create
from adapters.pico4.avatar_remote_state import source_store, retained
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical
from self_tests import test_pico_avatar_remote as existing

ROOT=Path(__file__).resolve().parents[3]


def without_e2e(text):
    """Extract the actual non-E2E source branch; no compiler/preprocessor call."""
    rows=[]; stack=[]; skip=False
    for line in text.splitlines():
        value=line.strip()
        if re.match(r'#\s*(if|ifdef|ifndef)\b',value):
            selected='OVERTE_E2E_FEATURE_TESTS' in value
            stack.append((skip,selected)); skip=skip or selected
            if not skip: rows.append(line)
        elif re.match(r'#\s*endif\b',value):
            parent,_selected=stack.pop(); old=skip; skip=parent
            if not old: rows.append(line)
        elif re.match(r'#\s*(else|elif)\b',value) and stack and stack[-1][1]: skip=stack[-1][0] or not skip
        elif not skip: rows.append(line)
    return '\n'.join(rows)


def body(text,signature):
    start=text.index(signature); opening=text.index('{',start); depth=0
    for index in range(opening,len(text)):
        if text[index]=='{': depth+=1
        elif text[index]=='}':
            depth-=1
            if depth==0: return '\n'.join(line for line in text[start:index+1].splitlines() if line.strip())
    raise AssertionError('Actual producer source boundary is incomplete')


class ProducerSourceTests(unittest.TestCase):
    def test_non_e2e_product_bodies_match_original_preinstrumentation_hashes(self):
        originals=[('libraries/animation/src/Rig.cpp','void Rig::copyJointsFromJointData(','6da2ba340467c1719aefad0ba36fb3d6c632a8e31ff074d921f48c39540196b5'),
            ('libraries/animation/src/Rig.cpp','void Rig::computeExternalPoses(','e14934924670ae3ec7bb6141448c73a2c41adffd43d172166c69c541180df8d1'),
            ('libraries/avatars/src/AvatarData.cpp','int AvatarData::parseDataFromBuffer(','9627812f8d3e5e8adcc69fde792ce3f39aba3d899e3d40cc7c3c87bd910912c6'),
            ('interface/src/avatar/OtherAvatar.cpp','void OtherAvatar::interpolateJoints(','31ccb9b79a64501fb1be2eb58c888e73cc6435540b57594063047c688becc99a')]
        for path,signature,sha in originals:
            with self.subTest(path=path,signature=signature):
                self.assertEqual(sha,hashlib.sha256(body(without_e2e((ROOT/path).read_text()),signature).encode()).hexdigest())

    def test_actual_remote_path_uses_wire_copy_and_external_build_not_local_animation_evaluator(self):
        source=(ROOT/'interface/src/avatar/OtherAvatar.cpp').read_text()
        current=body(source,'void OtherAvatar::interpolateJoints(')
        order=['QWriteLocker writeLock(&_jointDataLock)','e2eJointCopySequence()',
            'copyJointsFromJointData(_jointData)','computeExternalPoses(rootTransform)',
            'e2eRemoteJointPose(getSessionUUID()','_e2eRemoteJointPose=pose','writeLock.unlock()']
        self.assertEqual(sorted(current.index(value) for value in order),[current.index(value) for value in order])
        self.assertNotIn('e2eAnimationObservation',current)
        getter=body(source,'QVariantMap OtherAvatar::e2eRemoteJointPose()')
        self.assertNotIn('_jointDataLock',getter); self.assertNotIn('currentMSecsSinceEpoch',getter)
        self.assertIn('QReadLocker observed(&_e2eRemoteJointPoseLock)',getter)

    def test_actual_joint_section_receipts_follow_only_complete_original_assignments(self):
        source=(ROOT/'libraries/avatars/src/AvatarData.cpp').read_text()
        parser=body(source,'int AvatarData::parseDataFromBuffer(')
        self.assertLess(parser.index('data.translation *= maxTranslationDimension'),parser.index('e2eCommitJointSection("joint-data"'))
        self.assertLess(parser.index('jointData[i].translationIsDefaultPose = value'),parser.index('e2eCommitJointSection("default-flags"'))
        self.assertEqual(2,parser.count('e2eCommitJointSection('))
        commit=body(source,'void AvatarData::e2eCommitJointSection(')
        self.assertNotIn('QReadLocker',commit); self.assertNotIn('QWriteLocker',commit)
        self.assertIn('end-begin',commit); self.assertIn('raw.toBase64()',commit)
        self.assertIn('parsedEpochMs',commit); self.assertIn('parseTimestampUs',commit)

    def test_actual_copy_rejections_clear_previous_state_before_early_returns_and_external_does_not_retime(self):
        source=(ROOT/'libraries/animation/src/Rig.cpp').read_text(); copy=body(source,'void Rig::copyJointsFromJointData(')
        self.assertLess(copy.index('_e2eRemoteJointPose.begin('),copy.index('if (!_animSkeleton)'))
        self.assertLess(copy.index('_internalPoseSet._relativePoses[i].trans() = data.translation'),copy.index('_e2eRemoteJointPose.copied('))
        external=body(source,'void Rig::computeExternalPoses(')
        self.assertLess(external.index('_externalPoseSet = _internalPoseSet'),external.index('_e2eRemoteJointPose.external('))
        helper=(ROOT/'libraries/animation/src/RemoteJointPoseObservation.h').read_text()
        self.assertIn('_copied=_external=0',helper); self.assertIn('_external==_copied',helper)
        self.assertNotIn('overrideActive',helper); self.assertNotIn('clip',helper)


class RemoteJointPoseTests(unittest.TestCase):
    def setUp(self): self.model=existing.RemoteBoundary(); self.addCleanup(self.model.close)

    def packet(self):
        m=self.model; m.sequence+=1; return m.packet(dict(commandId='1'*32))

    def test_current_remote2_accepts_actual_empty_local_rig_only_with_distinct_committed_pose1(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); packet=owner.read(); subject=packet['source']['subject']
            self.assertEqual(2,packet['source']['picoRemoteAvatarVersion']); self.assertEqual({},subject['rig'])
            self.assertEqual(1,subject['remoteJointPose']['remoteJointPoseVersion'])
            self.assertNotIn('clip',subject['remoteJointPose']); self.assertNotIn('overrideActive',subject['remoteJointPose'])
            self.assertEqual(2,owner.store.read()['picoRemoteAvatarSourceVersion'])
            self.assertEqual('avatar-people',owner.store.read()['area'])

    def test_fresh_recopy_of_old_committed_wire_section_stays_stale_and_is_retained_before_refusal(self):
        m=self.model
        def stale(value):
            pose=value['source']['subject']['remoteJointPose']; row=pose['received']['jointData']
            row.update(parsedEpochMs=18000,committedEpochMs=18001,parseTimestampUs=18000000)
        m.edit=stale
        with m.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError): owner.read()
            raw=owner.raw(owner.state['pending']['raw'][-1]); observed=decode(raw)['source']['subject']['remoteJointPose']
            self.assertEqual(18000,observed['received']['jointData']['parsedEpochMs'])
            self.assertGreater(observed['capturedEpochMs'],19500); self.assertEqual('failed',owner.store.read()['phase'])

    def test_same_raw_foreign_committed_section_identity_cannot_supply_this_subject(self):
        m=self.model; raw=[]
        def foreign(value):
            received=value['source']['subject']['remoteJointPose']['received']['jointData']; raw.append(received['sha256'])
            received['subjectSessionId']=existing.SELF
        m.edit=foreign
        with m.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError): owner.read()
            retained=decode(owner.raw(owner.state['pending']['raw'][-1]))['source']['subject']['remoteJointPose']['received']['jointData']
            self.assertEqual(raw[0],retained['sha256']); self.assertEqual(existing.SELF,retained['subjectSessionId'])

    def test_missing_rejected_or_old_success_pose_cannot_complete_current_source(self):
        for fault in ('missing','rejected','external','count'):
            with self.subTest(fault=fault):
                m=existing.RemoteBoundary(); self.addCleanup(m.close)
                def reject(value):
                    subject=value['source']['subject']; pose=subject['remoteJointPose']
                    if fault=='missing': subject['remoteJointPose']={}
                    elif fault=='rejected': pose['available']=False
                    elif fault=='external': pose['externalSequence']=0
                    else: pose['inputJointCount']+=1
                m.edit=reject
                with m.lock.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError): owner.read()
                    self.assertEqual('failed',owner.store.read()['phase']); self.assertTrue(owner.state['pending']['raw'])

    def test_copied_data_change_requires_new_receive_not_just_new_copy_or_quaternion_sign(self):
        packet=self.packet(); a=packet['source']['subject']['remoteJointPose']; b=deepcopy(a)
        b.update(copySequence=a['copySequence']+1,copiedSequence=a['copySequence']+1,externalSequence=a['copySequence']+1,
            begunEpochMs=20001,copiedEpochMs=20002,capturedEpochMs=20003)
        b['joints'][0][4]+=.1
        with self.assertRaises(NativeUIError): remote_joint_pose.changed(a,b)
        b['received']['jointData'].update(sequence=a['received']['jointData']['sequence']+1,parsedEpochMs=20000,committedEpochMs=20000)
        measured=remote_joint_pose.changed(a,b); self.assertEqual([0],measured['changedJoints'])
        self.assertEqual(['joint-data'],measured['newCommittedSections'])
        self.assertNotIn('animation',measured); self.assertNotIn('sit',measured)
        sign=deepcopy(b); sign['joints']=deepcopy(a['joints']); sign['joints'][0][:4]=[-v for v in sign['joints'][0][:4]]
        with self.assertRaises(NativeUIError): remote_joint_pose.changed(a,sign)

    def legacy(self, *, empty=False):
        """Explicit historical Source1 encoding fixture, not a current producer."""
        m=self.model; store=source_store(m.adapter,'explicit-model',existing.RUN)
        identity=dict(picoRemoteAvatarSourceVersion=1,binding=m.binding,runId=existing.RUN,
            fixtureUrl=m.phase.fixture_url,subjectSessionId=existing.SUBJECT,producerHostProcessIdentity=host_identity(),primarySha256=None)
        header=dict(identity,phase='reading',chunks=[],records=[],pending=None,started=0.,epochMs=20000,hostEpochMs=20000)
        file=LifecycleProcessFile(store); previous=None
        def save():
            nonlocal previous
            file.write(header,previous); previous=deepcopy(header)
        save(); chunks=ChatSourceChunks(store,identity); chunks.load([])
        rows=[]
        def put(value):
            index=len(rows); header['chunks']=chunks.append(value,header['chunks']); rows.append(value); save(); return index
        query=avatar_remote.command(dict(schemaVersion=1,commandId='1'*32,action=avatar_remote.ACTION,runId=existing.RUN,subjectSessionId=existing.SUBJECT))
        before=m.phase.read()['status']; before_index=put(dict(kind='phase',value=before)); request=put(dict(kind='request',value=query))
        m.sequence+=1; packet=m.packet(query,legacy=True)
        if empty: packet['source']['subject']['rig']={}
        raw=canonical(packet).decode(); parts=[put(dict(kind='raw',value=raw[offset:offset+4096])) for offset in range(0,len(raw),4096)]
        reference=dict(parts=parts,bytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest())
        after=m.phase.status(before); after_index=put(dict(kind='phase',value=after))
        if empty:
            header.update(phase='failed',pending=dict(request=request,raw=[reference],partialRaw=None,before=before_index,after=after_index,hostStarted=0.))
        else:
            header.update(phase='ready',records=[dict(request=request,raw=reference,before=before_index,after=after_index,hostStarted=0.,hostFinished=0.)])
        save(); self.assertTrue(file.close_host()); return store,packet

    def test_v1_modeled_local_rig_remains_historical_without_current_source2_authority(self):
        m=self.model
        with m.lock.held():
            store,packet=self.legacy(); raw=store.path.read_bytes()
            archived=PicoRemoteAvatarSource.archive(store,m.phase,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertTrue(archived['historicalOnly']); self.assertFalse(archived['currentOwnership']); self.assertEqual([packet],archived['packets'])
            other=existing.RemoteBoundary(area='emotes'); self.addCleanup(other.close)
            with self.assertRaises(NativeUIError): PicoRemoteAvatarSource.archive(store,other.phase,guard=lambda:True,monotonic=lambda:m.clock)
            with self.assertRaises(NativeUIError): create(m.adapter,'explicit-model',m.phase,existing.SUBJECT,m.lock)
            self.assertEqual([],m.commands); self.assertEqual(raw,store.path.read_bytes())

    def test_v1_actual_remote_empty_rig_is_preserved_as_failed_raw_not_reinterpreted_pose1(self):
        m=self.model
        with m.lock.held():
            store,packet=self.legacy(empty=True)
            archived=PicoRemoteAvatarSource.archive(store,m.phase,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertEqual([],archived['packets']); self.assertEqual(packet,decode(archived['pendingRaw'][-1]))
            with self.assertRaises(NativeUIError): avatar_remote.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=avatar_remote.ACTION,
                runId=existing.RUN,subjectSessionId=existing.SUBJECT),31,20000)

    def test_source2_emotes_area_has_separate_namespace_and_cannot_relabel_source1(self):
        m=existing.RemoteBoundary(area='emotes'); self.addCleanup(m.close)
        with m.lock.held():
            owner=m.owner(); owner.read()
            self.assertEqual('emotes',owner.store.read()['area']); self.assertTrue(owner.store.path.name.startswith('emote-remote-owner-'))
            self.assertTrue(retained(m.adapter,'explicit-model'))
            archived=PicoRemoteAvatarSource.archive(owner.store,m.phase,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertTrue(archived['historicalOnly']); self.assertEqual('emotes',archived['header']['area'])


if __name__=='__main__': unittest.main()
