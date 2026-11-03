"""No-build committed-section/copy source checks and explicit native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import base64
import struct
from pathlib import Path
import re
import unittest

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_remote, remote_joint_pose, joint_interpolation
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
            ('interface/src/avatar/OtherAvatar.cpp','void OtherAvatar::interpolateJoints(','31ccb9b79a64501fb1be2eb58c888e73cc6435540b57594063047c688becc99a'),
            ('interface/src/avatar/OtherAvatar.cpp','void OtherAvatar::simulate(','c27955c7445d39ad413cc06793442bd4b42fe3ff549c423b349fc6ecfae94a40')]
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
        commit=body(source,'bool AvatarData::e2eCommitJointSection(')
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

    def test_current_remote3_accepts_actual_empty_local_rig_only_with_distinct_lineage_pose2(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); packet=owner.read(); subject=packet['source']['subject']
            self.assertEqual(3,packet['source']['picoRemoteAvatarVersion']); self.assertEqual({},subject['rig'])
            self.assertEqual(2,subject['remoteJointPose']['remoteJointPoseVersion'])
            self.assertNotIn('clip',subject['remoteJointPose']); self.assertNotIn('overrideActive',subject['remoteJointPose'])
            self.assertEqual(3,owner.store.read()['picoRemoteAvatarSourceVersion'])
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

    def legacy(self, *, empty=False, version=1):
        """Explicit historical Source1 encoding fixture, not a current producer."""
        m=self.model; store=source_store(m.adapter,'explicit-model',existing.RUN)
        identity=dict(picoRemoteAvatarSourceVersion=version,binding=m.binding,runId=existing.RUN,
            fixtureUrl=m.phase.fixture_url,subjectSessionId=existing.SUBJECT,producerHostProcessIdentity=host_identity(),primarySha256=None)
        if version == 2: identity['area']=m.phase.area
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
        m.sequence+=1; packet=m.packet(query,legacy=version==1)
        if version == 2:
            packet['source']['picoRemoteAvatarVersion']=2
            pose=packet['source']['subject']['remoteJointPose'];pose['remoteJointPoseVersion']=1
            del pose['interpolation'];del pose['rigInput']
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

    def test_source2_pose1_remains_exact_historical_data_without_source3_authority(self):
        m=self.model
        with m.lock.held():
            store,packet=self.legacy(version=2); raw=store.path.read_bytes()
            archived=PicoRemoteAvatarSource.archive(store,m.phase,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertEqual([packet],archived['packets']);self.assertFalse(archived['currentOwnership'])
            with self.assertRaises(NativeUIError): create(m.adapter,'explicit-model',m.phase,existing.SUBJECT,m.lock)
            self.assertEqual([],m.commands);self.assertEqual(raw,store.path.read_bytes())
            query=dict(schemaVersion=1,commandId=packet['requestId'],action=avatar_remote.ACTION,runId=existing.RUN,subjectSessionId=existing.SUBJECT)
            with self.assertRaises(NativeUIError): avatar_remote.validate(packet,query,31,20000,current=True)

    def test_source3_emotes_area_has_separate_namespace_and_cannot_relabel_source1(self):
        m=existing.RemoteBoundary(area='emotes'); self.addCleanup(m.close)
        with m.lock.held():
            owner=m.owner(); owner.read()
            self.assertEqual('emotes',owner.store.read()['area']); self.assertTrue(owner.store.path.name.startswith('emote-remote-owner-'))
            self.assertTrue(retained(m.adapter,'explicit-model'))
            archived=PicoRemoteAvatarSource.archive(owner.store,m.phase,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertTrue(archived['historicalOnly']); self.assertEqual('emotes',archived['header']['area'])


class JointInterpolationTests(unittest.TestCase):
    """Actual host/source composition; native interpolation is an explicit model."""
    def setUp(self): self.model=existing.RemoteBoundary();self.addCleanup(self.model.close)
    def packet(self):
        self.model.sequence+=1;return self.model.packet(dict(commandId='1'*32))
    def validate(self,packet):
        query=dict(schemaVersion=1,commandId=packet['requestId'],action=avatar_remote.ACTION,runId=existing.RUN,subjectSessionId=existing.SUBJECT)
        return avatar_remote.validate(packet,query,31,20000,current=True)
    @staticmethod
    def pose(packet): return packet['source']['subject']['remoteJointPose']
    @staticmethod
    def bits(values): return [struct.pack('>f',v).hex() for v in values]
    def test_actual_hooks_cover_partial_assignments_history_reset_append_prune_and_retained_inputs(self):
        parser=body((ROOT/'libraries/avatars/src/AvatarData.cpp').read_text(),'int AvatarData::parseDataFromBuffer(')
        self.assertEqual(2,parser.count('_e2eJointInterpolation.prepare(_jointData,true)'))
        self.assertEqual(2,parser.count('_e2eJointInterpolation.openAssignments()'))
        for section in ('if (hasJointData)', 'if (hasJointDefaultPoseFlags)'):
            part=parser[parser.index(section):]
            self.assertLess(part.index('_e2eJointInterpolation.openAssignments()'),part.index('_jointData.resize(numJoints)'))
        self.assertIn('source.value("sequence").toULongLong()<=_lastCommit',(ROOT/'libraries/avatars/src/JointInterpolationObservation.h').read_text())
        for kind in ('joint-data','default-flags'):
            self.assertLess(parser.index('e2eCommitJointSection("'+kind+'"'),parser.index('_e2eJointInterpolation.assigned(',parser.index('e2eCommitJointSection("'+kind+'"')))
        source=(ROOT/'interface/src/avatar/OtherAvatar.cpp').read_text(); simulate=body(source,'void OtherAvatar::simulate(')
        self.assertEqual(2,simulate.count('_e2eJointInterpolation.append('))
        self.assertLess(simulate.index('_jointHistory.resize('),simulate.index('_e2eJointInterpolation.resetHistory('))
        self.assertLess(simulate.index('_e2eJointInterpolation.prune('),simulate.index('_jointHistory[i].resize(OTHER_AVATAR_JOINT_HISTORY_LOOK_BACK)'))
        interpolate=body(source,'void OtherAvatar::interpolateJoints(')
        self.assertLess(interpolate.index('glm::slerp('),interpolate.index('_e2eJointInterpolation.selected('))
        self.assertLess(interpolate.index('computeExternalPoses('),interpolate.index('_e2eJointInterpolation.snapshot('))
        helper=(ROOT/'libraries/avatars/src/JointInterpolationObservation.h').read_text()
        for literal in ('tail.size()>45','entry.index-=oldSize-45','_budget->live>=MAX_LIVE_NODES','MAX_LIVE_NODES=256*4*(45+3)','visited.size()>=1024','depth>256',
                        'rawBytes>65536','unobserved-assignment','unobserved-partial-assignment','unretained-keyframe','inactive-storage-reveal','unobserved-contributing-input'):
            self.assertIn(literal,helper)
        self.assertNotIn('QWriteLocker',helper);self.assertNotIn('QReadLocker',helper)
        self.assertIn('roots.append(QVariant(ids(joint)))',helper)
        rig=(ROOT/'libraries/animation/src/Rig.cpp').read_text()
        self.assertIn('observedInputs.append(QVariant(overte::e2e::RemoteJointPoseObservation::input(data)))',rig)
        for channel in ('rotation','translation'):
            self.assertIn('value.'+channel+'IsDefaultPose || !'+channel+'Known',helper)
    def test_incoherent_original_lineage_is_durably_retained_before_refusal(self):
        for fault in ('cycle','missing-node','foreign-channel','foreign-subject','ignored-wire','raw-value','unavailable','bad-weight','future-index','same-sequence-rewrite','inactive-keyframe','uncommitted-identical','quota'):
            with self.subTest(fault=fault):
                m=existing.RemoteBoundary();self.addCleanup(m.close)
                def edit(packet):
                    pose=self.pose(packet);lineage=pose['interpolation'];node=lineage['nodes'][0];row=lineage['selection'][0]
                    if fault=='cycle': lineage['nodes'][-1]['parents'][0]=lineage['nodes'][-1]['id']
                    elif fault=='missing-node': lineage['nodes'].pop(0)
                    elif fault=='foreign-channel': node['channel']=1
                    elif fault=='foreign-subject': lineage['sections'][0]['subjectSessionId']=existing.SELF
                    elif fault=='ignored-wire':
                        source=lineage['sections'][0];raw=bytes([1,0,0])+struct.pack('<f',1.)
                        source.update(bytes=len(raw),base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
                        pose['received']['jointData']=deepcopy(source)
                    elif fault=='raw-value': node['value'][0]='3f800000'
                    elif fault=='unavailable': lineage.update(available=False,failure='unobserved-assignment')
                    elif fault=='bad-weight': row['thetaBits']='3f000000'
                    elif fault=='future-index': row['oldIndex']=False
                    elif fault=='same-sequence-rewrite': lineage['sections'][0]['committedEpochMs']-=1
                    elif fault=='uncommitted-identical': lineage['assignmentPending']=True
                    elif fault=='inactive-keyframe':
                        flag=deepcopy(lineage['nodes'][2]);flag.update(id=1000,op='initial',source=None,value=True)
                        lineage['nodes'].append(flag);row['old'][2]=1000
                    else: lineage['nodes']=[deepcopy(lineage['nodes'][2]) for _ in range(1025)]
                m.edit=edit
                with m.lock.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError): owner.read()
                    retained=decode(owner.raw(owner.state['pending']['raw'][-1]))
                    self.assertEqual(m.sample,retained);self.assertEqual('failed',owner.store.read()['phase']);self.assertEqual(1,len(m.commands))
    def test_explicit_direct_empty_future_clamp_and_interpolated_selection_models(self):
        for mode in ('direct-size-mismatch','empty-history-hold','oldest-future-hold','newest-clamp','interpolated'):
            with self.subTest(mode=mode):
                packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];row=lineage['selection'][0]
                if mode in ('direct-size-mismatch','empty-history-hold'):
                    lineage['nodes']=lineage['nodes'][:4];lineage['roots']=[row['old']]
                    lineage['selection']=[dict(joint=0,mode=mode,output=row['old'])]
                elif mode=='oldest-future-hold':
                    row.update(mode=mode,oldTimeUs=20001000,newTimeUs=20001000,thetaBits='00000000')
                    for node in lineage['nodes'][-2:]:node['detail']['thetaBits']='00000000'
                elif mode=='interpolated':
                    row.update(mode=mode,historySize=2,oldTimeUs=19999000,newTimeUs=20001000,newIndex=1,thetaBits='3f000000')
                    for node in lineage['nodes'][-2:]:node['detail']['thetaBits']='3f000000'
                self.validate(packet)
    def test_history_prune_uses_actual_shifted_45_entry_indices_and_does_not_retime_sections(self):
        packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];row=lineage['selection'][0]
        original=deepcopy(lineage['sections']);lineage.update(historyAppends=2001,historyPrunes=1)
        row.update(historySize=45,oldIndex=44,newIndex=44)
        self.validate(packet);self.assertEqual(original,lineage['sections'])
        row['oldIndex']=2000
        with self.assertRaises(NativeUIError):self.validate(packet)
    def test_translation_only_after_interpolation_preserves_original_rotation_and_nested_translation_dependencies(self):
        packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];received=deepcopy(pose['received']['jointData'])
        old=deepcopy(received);old.update(sequence=1,parsedEpochMs=18000,committedEpochMs=18001,parseTimestampUs=18000000)
        raw=bytes([1,0,1])+struct.pack('<fhhh',1.,6554,8192,9830)
        received.update(sequence=2,bytes=len(raw),base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
        pose['received']['jointData']=received;lineage['sections']=[old,deepcopy(received)]
        q=joint_interpolation.wire_value(old,0,0);q=[struct.unpack('>f',struct.pack('>f',v))[0] for v in q]
        oldp=joint_interpolation.wire_value(old,0,1);newp=joint_interpolation.wire_value(received,0,1);p=[(a+b)*.5 for a,b in zip(oldp,newp)]
        channels=[self.bits(q),self.bits(oldp),False,False]
        nodes=[dict(id=c+1,joint=0,channel=c,op='wire',value=deepcopy(v),parents=[],source=1,detail={}) for c,v in enumerate(channels)]
        nodes.extend([dict(id=5,joint=0,channel=1,op='wire',value=self.bits(newp),parents=[],source=2,detail={}),
            dict(id=6,joint=0,channel=3,op='wire',value=False,parents=[],source=2,detail={}),
            dict(id=7,joint=0,channel=0,op='interpolate',value=self.bits(q),parents=[1,1],source=None,detail=dict(thetaBits='3f000000')),
            dict(id=8,joint=0,channel=1,op='interpolate',value=self.bits(p),parents=[2,5],source=None,detail=dict(thetaBits='3f000000'))])
        lineage.update(nodes=nodes,roots=[[7,8,3,6]])
        lineage['selection'][0].update(mode='interpolated',historySize=2,newIndex=1,oldTimeUs=19999000,newTimeUs=20001000,
            thetaBits='3f000000',old=[1,2,3,4],new=[1,5,3,6],output=[7,8,3,6])
        pose['rigInput']['inputs']=[[self.bits(q),self.bits(p),False,False]]
        decision=pose['rigInput']['decisions'][0];decision.update(absoluteRotation=q,relativeRotation=q,translation=p)
        pose['relativeJoints']=pose['joints']=[q+p];self.validate(packet)
        self.assertEqual(18000,lineage['sections'][0]['parsedEpochMs']);self.assertEqual([1,1],nodes[-2]['parents'])
        # A later translation-only packet can append a previously interpolated
        # rotation/translation to history. Its nested ancestry must survive.
        newest=deepcopy(received);newraw=bytes([1,0,1])+struct.pack('<fhhh',1.,11469,13107,14746)
        newest.update(sequence=3,bytes=len(newraw),base64=base64.b64encode(newraw).decode(),sha256=hashlib.sha256(newraw).hexdigest())
        pose['received']['jointData']=newest;lineage['sections'].append(deepcopy(newest))
        newestp=joint_interpolation.wire_value(newest,0,1);p=[(a+b)*.5 for a,b in zip(p,newestp)]
        nodes.extend([dict(id=9,joint=0,channel=1,op='wire',value=self.bits(newestp),parents=[],source=3,detail={}),
            dict(id=10,joint=0,channel=3,op='wire',value=False,parents=[],source=3,detail={}),
            dict(id=11,joint=0,channel=0,op='interpolate',value=self.bits(q),parents=[7,7],source=None,detail=dict(thetaBits='3f000000')),
            dict(id=12,joint=0,channel=1,op='interpolate',value=self.bits(p),parents=[8,9],source=None,detail=dict(thetaBits='3f000000'))])
        nodes[:]=[node for node in nodes if node['id']!=4]  # Former flag is not a current dependency.
        lineage['roots']=[[11,12,3,10]];lineage['selection'][0].update(old=[7,8,3,6],new=[7,9,3,10],output=[11,12,3,10])
        pose['rigInput']['inputs'][0][1]=self.bits(p);decision['translation']=p;pose['relativeJoints']=pose['joints']=[q+p]
        self.validate(packet);self.assertEqual([7,7],nodes[-2]['parents']);self.assertEqual([1,1],next(node for node in nodes if node['id']==7)['parents'])
        # Fresh latest translation cannot supply the unchanged rotation channel.
        nodes[0]['source']=2
        with self.assertRaises(NativeUIError):self.validate(packet)
    def test_actual_rig_flag_nonfinite_and_zero_branches_preserve_raw_unused_inputs(self):
        for fault in ('rotation-nonfinite','rotation-zero','translation-nonfinite','rotation-flag'):
            with self.subTest(fault=fault):
                packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];rig=pose['rigInput'];row=rig['decisions'][0]
                if fault=='rotation-flag':
                    node=lineage['nodes'][2];node.update(op='initial',source=None,value=True);rig['inputs'][0][2]=True;rig['inputs'][0][0]=None;lineage['nodes'][4].update(op='inactive',value=None,parents=[],detail={})
                    row['rotationChoice']='default-flag';row['absoluteRotation']=row['relativeRotation']=[0.,0.,0.,1.]
                else:
                    channel=1 if fault=='translation-nonfinite' else 0
                    bits=['7fc00001']*(3 if channel else 4) if 'nonfinite' in fault else ['00000000']*4
                    lineage['nodes'][channel].update(op='initial',source=None,value=bits)
                    lineage['nodes'][4+channel]['value']=bits;rig['inputs'][0][channel]=bits
                    if channel: row.update(translationChoice='default-nonfinite',translation=[0.,0.,0.])
                    else:
                        row.update(rotationChoice='default-nonfinite' if 'nonfinite' in fault else 'default-zero',absoluteRotation=[0.,0.,0.,1.],relativeRotation=[0.,0.,0.,1.])
                pose['relativeJoints']=pose['joints']=[row['relativeRotation']+row['translation']];self.validate(packet)
                row['rotationChoice' if 'rotation' in fault else 'translationChoice']='rig-input'
                with self.assertRaises(NativeUIError):self.validate(packet)
    def test_actual_default_flag_section_is_distinct_from_invalid_unused_component_storage(self):
        packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];rig=pose['rigInput']
        source=deepcopy(pose['received']['jointData']);raw=bytes([1,1,0]);source.update(kind='default-flags',
            sequence=source['sequence']+1,bytes=3,base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
        pose['received']['defaultFlags']=source;lineage['sections'].append(deepcopy(source))
        lineage['nodes'][2].update(source=source['sequence'],value=True);lineage['nodes'][4].update(op='inactive',value=None,parents=[],detail={})
        rig['inputs'][0][0]=None;rig['inputs'][0][2]=True
        rig['decisions'][0].update(rotationChoice='default-flag',absoluteRotation=[0.,0.,0.,1.],relativeRotation=[0.,0.,0.,1.])
        pose['relativeJoints']=pose['joints']=[[0.,0.,0.,1.]+rig['decisions'][0]['translation']]
        self.validate(packet);self.assertIsNone(lineage['nodes'][4]['value'])
        lineage['nodes'][2]['value']=False
        with self.assertRaises(NativeUIError):self.validate(packet)

    def test_inactive_leaf_has_no_invented_arithmetic_and_cannot_authorize_active_input(self):
        packet=self.packet();pose=self.pose(packet);lineage=pose['interpolation'];rig=pose['rigInput'];decision=rig['decisions'][0]
        flag=lineage['nodes'][2];flag.update(op='initial',source=None,value=True)
        inactive=lineage['nodes'][4];inactive.update(op='inactive',value=None,parents=[],detail={})
        rig['inputs'][0][0]=None;rig['inputs'][0][2]=True
        decision.update(rotationChoice='default-flag',absoluteRotation=[0.,0.,0.,1.],relativeRotation=[0.,0.,0.,1.])
        pose['relativeJoints']=pose['joints']=[[0.,0.,0.,1.]+decision['translation']];self.validate(packet)
        self.assertEqual([],inactive['parents'])
        flag['value']=False;rig['inputs'][0][2]=False
        with self.assertRaises(NativeUIError):self.validate(packet)
        source=(ROOT/'libraries/avatars/src/JointInterpolationObservation.h').read_text()
        self.assertIn('values[c+2].toBool() ? node(joint,c,"inactive",QVariant(),{}, {},{})',source)

    def test_parent_absolute_rotation_is_joined_to_actual_relative_output(self):
        packet=self.packet();pose=self.pose(packet);rig=pose['rigInput']
        # The independently checked Rig component accepts an actual two-joint
        # skeleton. This is a DTO model, not a native skeleton execution.
        pose['inputJointCount']=2;pose['relativeJoints']*=2
        rig['inputs']*=2;rig['decisions'].append(deepcopy(rig['decisions'][0]));rig['decisions'][1].update(joint=1,parent=0,relativeRotation=[0.,0.,0.,1.])
        pose['relativeJoints'][1]=rig['decisions'][1]['relativeRotation']+rig['decisions'][1]['translation']
        joint_interpolation.validate_rig(rig,pose)
        rig['decisions'][1]['relativeRotation']=rig['decisions'][0]['absoluteRotation']
        with self.assertRaises(NativeUIError):joint_interpolation.validate_rig(rig,pose)


if __name__=='__main__': unittest.main()
