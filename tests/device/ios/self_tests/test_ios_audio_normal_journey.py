"""All fourteen ordinary Audio actions through the existing recording owner.

Actual private originals, CAS, normal input codecs and interruption ownership
execute. Audio/Qt/SDK/OS/automatic timers and clocks are explicit models.
This supplies neither independent acoustic/peer evidence nor resource end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import check as transport_check
from adapters.recorded_preview_history import measured_state
from feature_journeys.contract import state
from feature_journeys.engine import matches
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.audio_authorization_sources import AudioAuthorizationSources
from ios.adapters.audio_authorized_start import AudioAuthorizedStarts
from ios.adapters.audio_page_inputs import AudioPageInputs
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters import audio_session_source
from ios.self_tests.audio_background_domain import AudioBackgroundDomain
from ios.self_tests.test_ios_audio_pcm_lease import PCMModel
from ios.self_tests.test_ios_audio_session_source import Boundary


class AudioNormalJourneyTests(unittest.TestCase):
    def test_all_fourteen_normal_actions_authorized_cycles_pcm_and_same_process_resume(self):
        self.run_normal_journey()

    def run_normal_journey(self,*,pcm_model=PCMModel,pcm_profile=None,close_evidence=False):
        b=AudioBackgroundDomain(self,pages=True,prepare_recording=False);m=b.m;parent=b.parent;m.automatic=True
        class Session(Boundary):
            def stamp(self):m.tick();return dict(epochMs=m.native_epoch(),monotonicMs=round(m.clock*1000))
            def send(self,query):super().send(query);m.sleep(self.delay/1000)
        session=Session(20000);session.instance=m.native_instance;source=b.runtime._sources
        def audio_sources(selector):
            value=source(selector)
            def audio_session(clock_source):
                return audio_session_source.IOSAudioSession(session.send,lambda:session.raw,
                    lambda:clock_source.read(clock_source.sequence)['capturedEpochMs'],m.guard,42,
                    monotonic=lambda:m.clock,sleep=m.sleep)
            from types import SimpleNamespace
            value['observer']=SimpleNamespace(audio_session=audio_session)
            return value
        b.runtime._sources=audio_sources
        ui=parent.ui.io.original.ui;click=ui.click_with_token
        def guarded(locator,token):transport_check();return click(locator,token)
        ui.click_with_token=guarded
        authorization=b.runtime.authorization_sources('test-only',parent,epoch_ms=m.epoch,monotonic=lambda:m.clock)
        starts=AudioAuthorizedStarts(PrivateFeatureState(b.root/'ios-audio-authorized-starts.json'),parent,authorization)
        lease=None;retired=None;steps=[];closing=[False];close_results=[]
        source_before_close=b.runtime._sources
        if close_evidence:
            def closing_sources(selector):
                value=source_before_close(selector)
                if closing[0]:
                    from types import SimpleNamespace
                    value['observer']=SimpleNamespace(recorded_preview_observer=lambda:pcm.reader()[1])
                return value
            b.runtime._sources=closing_sources
            def close_owner(owner):
                closing[0]=True
                try:close_results.append(b.runtime.close_recording_evidence('test-only',owner))
                finally:closing[0]=False
            parent.close_evidence=close_owner
        for index,step in enumerate(SCENARIOS['audio']['steps'],1):
            verb,inputs=step['verb'],step['inputs'];ticket=format(index+32,'032x');m.add_phase(verb,ticket,**inputs)
            if verb=='record-start':result=starts.act(ticket)
            elif verb=='background-resume':
                result=b.runtime.resume_recording('test-only',parent,ticket,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
            else:result=parent.act(ticket,verb,**inputs)
            self.assertTrue(result['performed'])
            original=parent.original(parent.state['records'][-1]);observed=measured_state(original['originals']['native'])
            observed['open']=AudioPageInputs.route(original['originals']['ui'])=='audio'
            state('audio',observed,parent.run);self.assertTrue(matches(observed,step['state']),(index,verb,observed))
            steps.append(dict(step=index,verb=verb,phase=observed['phase'],cycle=original['originals']['native']['audio']['recordedVoice']['cycle']))
            print(json.dumps(steps[-1]),flush=True)
            if verb=='await-completion':
                pcm=pcm_model(m);native,preview=pcm.reader()
                lease=IOSAudioPCMLease(PrivateFeatureState(b.root/'ios-audio-pcm-lease.json'),parent,native=native,preview=preview,profile=pcm_profile)
                snapshot=lease.capture();self.assertEqual(ticket,parent.state['operations'][-1]['ticket'])
                self.assertEqual(3,snapshot['recording']['cycle']);retired=lease.retire()
                activate=m.activate
                def new_cycle(identifier,*,token):
                    before=m.cycle;answer=activate(identifier,token=token)
                    if m.cycle!=before:pcm.memory=True
                    return answer
                m.activate=new_cycle
        self.assertEqual(14,len(steps));self.assertEqual(5,m.cycle);self.assertEqual(6,m.actions.count('audio.record'))
        self.assertEqual(4,m.actions.count('audio.mute'));self.assertEqual(2,len(b.inputs));self.assertEqual('closed',m.page_model.route)
        self.assertTrue(retired['retired']);self.assertIsNone(parent.state['pending']);self.assertIsNone(authorization.state['pending'])
        # Later product cycles allocate fresh evidence memory. Retirement of
        # cycle3 alone cannot establish absence for cycles4/5 or complete Audio.
        # Explicit Close integration separately retires the latest owned cycle.
        self.assertEqual(not close_evidence,pcm.memory)
        if close_evidence:
            self.assertEqual(1,len(close_results));self.assertTrue(close_results[0]['retired']);self.assertFalse(close_results[0]['captured'])
            self.assertEqual(5,close_results[0]['recording']['cycle']);self.assertFalse(pcm.files)
            self.assertEqual(1,pcm.count('feature-recorded-audio-observe'))
            self.assertEqual(1,sum(row['action']=='feature-recorded-audio-release' and row['schemaVersion']==2 for row in pcm.commands))
        def census():
            files={}
            for path in sorted(b.root.rglob('*')):
                if path.is_file():
                    info=path.lstat();files[str(path)]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                        hashlib.sha256(path.read_bytes()).hexdigest())
            return files
        originals=census();inputs=deepcopy((m.actions,m.page_model.actions,b.inputs));queries=(b.reads,len(session.queries),deepcopy(pcm.commands))
        b.native_blocked=True
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical normal journey attempted a write')):
            archive=IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,parent.run,b.lock,parent.fixture_url)
            archived_authorization=AudioAuthorizationSources.archive(authorization.store,archive)
            archived_starts=AudioAuthorizedStarts.archive(starts.store,archive,archived_authorization)
            self.assertEqual(parent.state,archive.state);self.assertEqual(starts.state,archived_starts.state)
            self.assertEqual(retired,IOSAudioPCMLease.archive(lease.store,archive).retired())
            if close_evidence:
                closed=IOSAudioPCMLease.archive(PrivateFeatureState(b.root/'ios-audio-close-lease.json'),archive)
                self.assertEqual(close_results[0],closed.retired());self.assertIsNone(closed.state['allocation'])
        self.assertEqual(inputs,(m.actions,m.page_model.actions,b.inputs));self.assertEqual(queries,(b.reads,len(session.queries),pcm.commands))
        self.assertEqual(originals,census());print('Unchanged original Audio files: '+str(len(originals)),flush=True)
        if close_evidence:return lease,retired,close_results[0],pcm
        return lease,retired


if __name__=='__main__':unittest.main()
