"""Hardware-free feature logic proofs; the simulator is no product evidence.

The boundary model reduces input verbs independently of scenario checkpoints.
Fault injection then changes deliveries, state, original bytes, clocks, witnesses
and cleanup separately. No expected-state object is ever returned as a read.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from contracts import validate_operation_arguments, validate_operation_result
from feature_journeys.contract import arguments, result
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.fixtures import (challenge, companion, context, document, marker_bytes, wav_bytes)
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.server import make_server
from feature_journeys.witness import Client, Journal, projection

RUN = '01' * 16
TICKET = '02' * 16
SCREEN_POLICY = {'source': 'world-render-target', 'marker': [4, 4, 132, 36], 'subject': [0, 48, 160, 144]}

POLICY = {'screen': SCREEN_POLICY, 'file': SCREEN_POLICY}


class Boundary:
    def __init__(self, area, fault='', target=None):
        self.area, self.fault, self.target = area, fault, target
        self.run = RUN
        self.ctx = context(RUN)
        self.state = copy.deepcopy(SCENARIOS[area]['baseline'])
        self.journal = Journal(self.epoch)
        # The real coordinator generates the run; tests need a deterministic one.
        self.journal.runs[RUN] = dict(area=area, ticket=None, entries=[], sequence=0, activeEpochMs=self.epoch(), stimulus=None, tickets=set())
        self.clock = 0.0
        self.sequence = self.actor_sequence = 0
        self.ticket = None
        self.verb = 'baseline'
        self.inputs = {}
        self.actions, self.reports, self.files = [], [], {}
        self.resources = []
        self.lifecycle = dict(backgrounds=0, activations=1, launches=1)
        self.back_count = 0
        self.sit_count = 0
        self.current_resource = None
        self.last_image = None
        self.recorded_ticket = self.capture_ticket = self.model_ticket = self.texture_ticket = None
        self.ignored = False

    def epoch(self):
        return 2_000_000 + getattr(self, 'clock', 0) * 1000

    def activate(self, ticket, verb='baseline', inputs=None):
        self.ticket = ticket
        self.journal.activate(RUN, ticket, verb, inputs)

    def reduce(self, verb, data):
        s, a = self.state, self.area
        if verb == 'restart-app':
            if self.fault != 'restart-ignored':
                self.lifecycle['launches'] += 1
                self.lifecycle['activations'] += 1
            return
        if verb == 'background-resume':
            if self.fault != 'background-ignored':
                self.lifecycle['backgrounds'] += 1
                self.lifecycle['activations'] += 1
            if a == 'lifecycle-input':
                s.update(keyboard=False, focused=False)
            return
        if a == 'world-navigation':
            if verb in {'open', 'close'}: s['panel'] = verb == 'open'
            elif verb == 'bookmark-add': s.update(bookmark=True, bookmarkName=data['name'])
            elif verb == 'bookmark-rename': s['bookmarkName'] = data['name']
            elif verb == 'directory-search': s['searchResults'] = [self.ctx['destination']]
            elif verb == 'directory-select': s['location'] = 'B'
            elif verb == 'navigate-missing': s['error'] = 'not-found'
            elif verb == 'dismiss-error': s['error'] = 'none'
            elif verb == 'bookmark-visit': s['location'] = 'A'
            elif verb == 'bookmark-delete': s.update(bookmark=False, bookmarkName='')
        elif a == 'authentication':
            if verb == 'login-open': s['dialog'] = True
            elif verb == 'login-cancel': s.update(dialog=False, error='none', pending=False)
            elif verb == 'login-submit':
                if data['account'] == 'invalid': s['error'] = 'invalid-credentials'
                elif data['account'] == 'delayed': s['pending'] = True
                else: s.update(principal='owned', dialog=False, protectedAccess=True)
            elif verb == 'logout': s.update(principal='anonymous', protectedAccess=False)
        elif a == 'avatar-people':
            if verb == 'avatar-url':
                if data['resource'] == 'missing.fst': s['error'] = 'not-found'
                else: s['avatar'] = 'A'
            elif verb == 'avatar-bookmark-save': s['bookmarked'] = True
            elif verb == 'avatar-bookmark-delete': s['bookmarked'] = False
            elif verb == 'avatar-scale': s['scale'] = data['value']
            elif verb == 'wearable-add': s['wearable'] = True
            elif verb == 'dismiss-error': s['error'] = 'none'
            elif verb == 'avatar-bookmark-choose': s.update(scale=1.0, wearable=False)
            elif verb == 'connection-request': s.update(connection='pending', dialog=True)
            elif verb in {'connection-cancel', 'peer-reject', 'connection-remove'}: s.update(connection='none', dialog=False)
            elif verb == 'peer-accept': s.update(connection='connected', dialog=False)
            elif verb == 'avatar-restore': s['avatar'] = 'original'
        elif a == 'create':
            if verb in {'open','close'}: s['editor'] = verb == 'open'
            elif verb == 'import-local':
                s.update(objects=['model'], selection=['model']); self.model_ticket=self.ticket
            elif verb == 'apply-texture':
                s['textured'] = True; self.texture_ticket=self.ticket
            elif verb == 'delete-owned': s.update(objects=[], selection=[], textured=False, voxelValue=0)
            elif verb == 'voxel-create': s.update(objects=['voxel'], selection=['voxel'])
            elif verb == 'voxel-edit': s['voxelValue'] = 1
            elif verb == 'set-rez-permission': s.update(canRez=data['allowed'], error='none')
            elif verb == 'create-denied': s['error'] = 'permission-denied'
        elif a == 'emotes':
            if verb in {'open','close'}: s['panel'] = verb == 'open'
            elif verb == 'play': s.update(animation=data['name'], sit='Sit1' if data['name']=='Sit' else 'none', poseProgress=0.5)
            elif verb == 'sit':
                self.sit_count += 1
                s.update(animation='Sit', sit='Sit1' if self.fault=='sit-variant-stuck' else 'Sit'+str((self.sit_count-1)%3+1), poseProgress=0.5)
            elif verb == 'override': s.update(animation=data['name'], override=True, sit='none')
            elif verb == 'cancel': s.update(animation='idle', sit='none', override=False, poseProgress=0.0)
        elif a in {'world-web','tablet-web'}:
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close': s['focused'] = False
            elif verb == 'focus-type': s.update(text=data['text'], focused=True)
            elif verb == 'submit': s['bridgeMessages'] += 1
            elif verb == 'navigate':
                if data['resource'] == 'missing.html': s['error'] = 'not-found'
                else: s.update(page='B', focused=False)
            elif verb == 'back': s['page'] = 'reference'
            elif verb == 'reload': s['error'] = 'none'
            elif verb == 'open-inline-app': s['page'] = 'inline'
        elif a == 'graphics':
            if verb == 'open': s['dialog'] = True
            elif verb == 'preview-preset': s.update(preset='low', shadows=False, shadowPass=False)
            elif verb == 'cancel': s.update(dialog=False, preset='original', shadows=True, shadowPass=True)
            elif verb == 'set-resolution': s.update(resolution=data['value'], renderScale=data['value'])
            elif verb == 'set-shadows': s.update(shadows=data['enabled'], shadowPass=data['enabled'])
            elif verb == 'apply': s['dialog'] = False
            elif verb == 'mirror-enable': s['mirror'] = True
            elif verb == 'restore': s.update(resolution=1.0, renderScale=1.0, shadows=True, shadowPass=True, mirror=False)
        elif a == 'audio':
            if verb == 'set-microphone-permission': s.update(permission=data['state'], error='none')
            elif verb == 'record-start':
                if s['permission'] == 'denied': s['error'] = 'permission-denied'
                else:
                    s.update(recording=True, recordedFrames=120000)
                    self.recorded_ticket = self.ticket
            elif verb == 'record-cancel': s.update(recording=False, recordedFrames=0)
            elif verb == 'record-stop': s['recording'] = False
            elif verb == 'preview-start': s['preview'] = True
            elif verb == 'preview-stop': s['preview'] = False
            elif verb == 'mute': s['muted'] = data['enabled']
            elif verb == 'discard': s['recordedFrames'] = 0
        elif a == 'chat':
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close': s.update(focused=False, keyboard=False)
            elif verb == 'type': s.update(draft=data['text'], focused=True, keyboard=True)
            elif verb == 'back': s.update(focused=False, keyboard=False)
            elif verb == 'send' and s['error'] == 'none':
                s['messages'].append(s['draft']); s['draft'] = ''
            elif verb == 'peer-send' and not s['filtered']: s['messages'].append(data['text'])
            elif verb == 'filter-peer': s['filtered'] = data['enabled']
            elif verb == 'network-disconnect': s['error'] = 'offline'
            elif verb == 'network-reconnect': s['error'] = 'none'
        elif a == 'snapshots':
            if verb in {'open','close'}: s['open'] = verb == 'open'
            elif verb == 'set-storage-permission': s.update(permission=data['state'], error='none')
            elif verb == 'capture':
                if s['permission'] == 'denied': s['error'] = 'permission-denied'
                else:
                    s['files'] += 1; self.capture_ticket = self.ticket
            elif verb == 'share': s['shares'] += 1
            elif verb == 'upload-fail': s['error'] = 'offline'
            elif verb == 'upload': s.update(uploads=1, error='none')
        elif a == 'scripts':
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close': s['error'] = 'none'
            elif verb in {'load-local','load-folder'}:
                if data['resource'] == 'missing.js': s['error'] = 'not-found'
                else: s['consent'] = True
            elif verb in {'consent-cancel','consent-reject'}: s['consent'] = False
            elif verb == 'consent-accept': s.update(consent=False, running=['owned-script'], effects=4)
            elif verb == 'stop-owned': s.update(running=[], effects=0)
        elif a == 'assets':
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close': s['error'] = 'none'
            elif verb == 'upload':
                if data['resource'] == 'missing.gltf': s['error'] = 'not-found'
                else: s.update(mappings=[self.ctx['name']], selected=self.ctx['name'],
                    companions=['mesh/triangle.bin','textures/checker.png'] if data['resource']=='model.gltf' else ['materials/palette.mtl','textures/checker.png'])
            elif verb == 'rename': s.update(mappings=[data['name']], selected=data['name'])
            elif verb == 'bake': s['bakeState'] = 'ready'
            elif verb == 'import-selected': s['sceneModel'] = True
            elif verb == 'remove-owned-model': s['sceneModel'] = False
            elif verb == 'set-write-permission': s.update(canWrite=data['allowed'], error='none')
            elif verb == 'delete-denied': s['error'] = 'permission-denied'
            elif verb == 'delete-owned':
                s.update(mappings=[], selected='', bakeState='none')
                if self.fault != 'leaked-companions': s['companions']=[]
        elif a == 'lifecycle-input':
            if verb == 'open-editor': s.update(editor=data['editor'], focused=True, keyboard=True)
            elif verb == 'type': s['text'] = data['text']
            elif verb == 'back':
                if s['keyboard']: s.update(keyboard=False, focused=False)
                else: s['editor'] = 'none'
            elif verb == 'replace-context': s.update(generation=2, text='', editor='none', focused=False, keyboard=False)
            elif verb == 'world-input' and s['editor'] == 'none': s['worldDisplacement'] = 1.0
            elif verb == 'restore': s['worldDisplacement'] = 0.0

    def invoke(self, operation, fields):
        self.actions.append((operation, copy.deepcopy(fields)))
        kind = operation.rsplit('.', 1)[-1]
        if kind == 'observe': return self.observe(fields)
        if kind == 'cleanup':
            self.verb = 'cleanup'
            if self.fault != 'cleanup-ignored':
                self.state = copy.deepcopy(SCENARIOS[self.area]['baseline'])
            self.resources = ['entity:leaked'] if self.fault == 'cleanup-resource-leak' else []
        else:
            self.verb, self.inputs = fields['verb'], fields['inputs']
            if self.fault == 'input-ignored' and (self.target is None or self.target == self.verb):
                self.ignored = True
            else:
                self.reduce(self.verb, self.inputs)
        if self.fault == 'ack-verdict': return {'performed': True, 'passed': True}
        return {'performed': True}

    def image(self, ticket=None):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (160, 144), 'gray')
        image.paste(Image.open(io.BytesIO(marker_bytes(RUN, ticket or self.ticket))), (0, 0))
        digest = hashlib.sha256(json.dumps(self.state, sort_keys=True).encode()).digest()
        draw = ImageDraw.Draw(image)
        for i in range(16):
            color = tuple(digest[(i + offset) % 32] for offset in range(3))
            draw.rectangle((i % 4 * 40, 48 + i // 4 * 24, i % 4 * 40 + 39, 71 + i // 4 * 24), fill=color)
        out = io.BytesIO(); image.save(out, format='PNG')
        return out.getvalue()

    def observe(self, fields):
        self.sequence += 1
        if self.area=='scripts' and self.state['running'] and self.fault!='script-effects-stalled':
            self.state['effects'] += 1
        state = copy.deepcopy(self.state)
        if self.fault == 'product-echo-without-peer' and self.verb == self.target:
            # Deliberately forge only the product seam. The actor still sees the
            # unchanged real model; this must not satisfy the common journey.
            state.update(self.echo)
        if self.fault == 'script-effects-stalled' and self.verb=='consent-accept' and not getattr(self,'early_script_read',False):
            state.update(running=[],effects=0)
            self.early_script_read=True
        if self.fault == 'nonfinite':
            key = next((k for k,v in state.items() if type(v) is float), None)
            if key: state[key] = float('nan')
        artifacts = []
        if self.verb not in {'baseline','cleanup'}:
            content = self.image(TICKET if self.fault == 'foreign-image' else None)
            if self.fault == 'frozen-subject' and self.last_image is not None:
                from PIL import Image
                image = Image.open(io.BytesIO(content))
                old = Image.open(io.BytesIO(self.last_image))
                image.paste(old.crop((0,48,160,144)), (0,48))
                out=io.BytesIO(); image.save(out, format='PNG'); content=out.getvalue()
            self.last_image = content
            values = {'image': content}
            if self.area == 'audio':
                source = self.recorded_ticket if state['preview'] or self.verb == 'record-stop' else self.ticket
                audible = state['preview'] or self.verb == 'mute' and not state['muted']
                audio = wav_bytes(RUN, source or self.ticket)
                if not audible:
                    audio = audio[:44] + bytes(len(audio) - 44)
                values.update(audio=audio, file=wav_bytes(RUN, self.recorded_ticket or self.ticket))
            elif self.area == 'snapshots': values['file'] = self.image(self.capture_ticket or self.ticket)
            elif self.area == 'create': values['file'] = json.dumps(document(RUN, model_ticket=self.model_ticket, texture_ticket=self.texture_ticket)).encode()
            elif self.area == 'assets': values['file'] = companion('gltf-bundle/main.gltf')
            for kind, content in values.items():
                name = f'{self.sequence}-{kind}.bin'
                self.files[name] = content
                artifacts.append(dict(kind=kind, name=name, sequence=self.sequence,
                    ticket=TICKET if self.fault == 'foreign-artifact' else self.ticket,
                    capturedEpochMs=self.epoch() - (2000 if self.fault == 'stale-artifact' else 0)))
                if kind == 'image': artifacts[-1]['source'] = 'world-render-target'
            if self.fault == 'missing-evidence' or self.ignored:
                artifacts = []
        return dict(schemaVersion=1, contractVersion=1, runId='ff'*16 if self.fault == 'foreign-run' else RUN,
            sequence=1 if self.fault == 'replayed-sample' else self.sequence,
            capturedEpochMs=self.epoch() - (2000 if self.fault == 'stale-sample' else 0),
            state=state, artifacts=artifacts, resources=self.resources.copy(), lifecycle=self.lifecycle.copy())

    def witness(self):
        self.actor_sequence += 1
        if self.fault not in {'missing-witness','frozen-witness'} or self.actor_sequence == 1:
            facts = projection(self.area, self.state)
            self.journal.publish(RUN, dict(ticket=self.ticket, actor='owned-observer',
                actorSequence=self.actor_sequence, capturedEpochMs=self.epoch(), facts=facts))
        value = self.journal.snapshot(RUN)
        if self.fault == 'foreign-witness': value['runId'] = 'ab'*16
        return value

    def sleep(self, duration):
        self.clock += -duration if self.fault == 'clock-backwards' else duration

    def continuity(self, phase, verb):
        if self.fault == 'process-replaced' and phase == 'observed' and self.verb != 'baseline':
            raise AssertionError('Process replaced during normal observation')

    def execute(self):
        return Journey(self.area, RUN, f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
            invoke=self.invoke, witness=self.witness, activate=self.activate,
            read_artifact=self.files.__getitem__, image_policy=POLICY, continuity=self.continuity,
            monotonic=lambda:self.clock, epoch_ms=self.epoch, sleep=self.sleep, report=self.reports.append).execute()


class FeatureJourneys(unittest.TestCase):
    def test_all14_complete_with_independent_boundary_model_and_observed_cleanup(self):
        self.assertEqual(14, len(SCENARIOS))
        for area in SCENARIOS:
            with self.subTest(area=area):
                boundary = Boundary(area)
                phases = boundary.execute()
                self.assertGreaterEqual(len(phases), len(SCENARIOS[area]['steps']) + 2)
                self.assertTrue(boundary.reports[0]['sequenceCompleted'])
                self.assertTrue(boundary.reports[0]['cleanupSucceeded'])
                self.assertFalse(boundary.reports[0]['deviceAcceptance'])
                self.assertEqual(2, sum(op.endswith('.cleanup') for op,_ in boundary.actions))

    def test_ignored_effectful_actions_fail_in_each_area(self):
        targets = dict(zip(SCENARIOS, ['bookmark-add','login-submit','avatar-url','import-local','play','focus-type',
            'set-resolution','record-start','type','capture','consent-accept','upload','open-editor','focus-type']))
        for area, target in targets.items():
            with self.subTest(area=area):
                boundary = Boundary(area, 'input-ignored', target)
                with self.assertRaises((AssertionError, ValueError)):
                    boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_stale_foreign_and_missing_original_evidence_cannot_pass(self):
        for fault in ('foreign-image','foreign-artifact','stale-artifact','missing-evidence','frozen-subject'):
            with self.subTest(fault=fault):
                boundary=Boundary('graphics', fault)
                with self.assertRaises((AssertionError, ValueError)):
                    boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_independent_witness_and_product_freshness_are_both_mandatory(self):
        for fault in ('missing-witness','frozen-witness','foreign-witness','foreign-run',
                      'replayed-sample','stale-sample','nonfinite','clock-backwards','ack-verdict','process-replaced'):
            with self.subTest(fault=fault):
                boundary=Boundary('graphics', fault)
                with self.assertRaises((AssertionError, ValueError)):
                    boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_cleanup_acknowledgments_do_not_hide_remaining_resources_or_state(self):
        for fault in ('cleanup-ignored','cleanup-resource-leak'):
            boundary=Boundary('authentication', fault)
            # Finish the ordinary sequence with a nonbaseline state to test restore.
            if fault == 'cleanup-ignored':
                original=boundary.invoke
                def invoke(op, fields):
                    if op.endswith('.cleanup'):
                        boundary.state['dialog']=True
                    return original(op,fields)
                boundary.invoke=invoke
            with self.subTest(fault=fault), self.assertRaises(AssertionError): boundary.execute()
            self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

    def test_native_lifecycle_effects_are_required_for_acknowledged_resume_and_restart(self):
        for fault in ('restart-ignored','background-ignored'):
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                Boundary('graphics', fault).execute()

    def test_action_contract_never_accepts_checkpoints_foreign_inputs_or_verdicts(self):
        request=dict(contractVersion=1, runId=RUN, ticket=TICKET, fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
                     verb='set-resolution',inputs={'value':0.5})
        op='feature.graphics.act'
        self.assertEqual(request,validate_operation_arguments(op,request))
        for change in ({'expected':{'renderScale':0.5}},{'contractVersion':2},{'verb':'unknown'},
                       {'inputs':{'value':False}},{'fixtureUrl':'file:///private/secret'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_operation_arguments(op,{**request,**change})
        with self.assertRaises(ValueError): validate_operation_result(op,{'performed':True,'passed':True})

    def test_private_artifact_reader_rejects_symlinks_hardlinks_and_oversized_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); (root/'original').write_bytes(b'original')
            self.assertEqual(b'original',read_private_artifact(root,'original'))
            (root/'symlink').symlink_to(root/'original')
            with self.assertRaises(OSError): read_private_artifact(root,'symlink')
            os.link(root/'original',root/'hardlink')
            with self.assertRaises(ValueError): read_private_artifact(root,'original')

    def test_observation_provenance_is_retained_and_journal_history_is_immutable(self):
        boundary=Boundary('graphics'); boundary.execute()
        report=boundary.reports[0]
        self.assertEqual(RUN,report['runId'])
        for sample in report['samples']:
            self.assertGreaterEqual(sample['capturedEpochMs'],sample['actionBarrierEpochMs'])
            for proof in sample['evidence']:
                self.assertEqual(sample['ticket'],proof['acquisition']['ticket'])
                self.assertEqual(sample['sequence'],proof['acquisition']['sequence'])
        boundary=Boundary('chat');boundary.activate(TICKET);boundary.witness()
        snapshot=boundary.journal.snapshot(RUN)
        snapshot['entries'][0]['facts']['messages'].append('foreign text')
        boundary.state['messages'].append(context(RUN)['unicode'])
        self.assertEqual([],boundary.journal.snapshot(RUN)['entries'][0]['facts']['messages'])

    def test_fixture_journal_rejects_relabelled_replayed_and_late_actor_samples(self):
        boundary=Boundary('chat'); boundary.activate(TICKET); boundary.witness()
        row=boundary.journal.runs[RUN]['entries'][-1]
        value={key:row[key] for key in ('ticket','actor','actorSequence','capturedEpochMs','facts')}
        for change in ({'ticket':'ab'*16},{'actor':'adapter'}, {'capturedEpochMs':1},{'actorSequence':True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                boundary.journal.publish(RUN,{**value,**change})




class FeatureEvidenceCounterexamples(unittest.TestCase):
    def test_pre_input_actor_sample_is_not_proof_but_does_not_poison_later_fresh_reads(self):
        boundary=Boundary('authentication')
        original=boundary.activate
        def activate(ticket,verb='baseline',inputs=None):
            original(ticket,verb,inputs)
            boundary.witness()
            boundary.clock+=0.01
        boundary.activate=activate
        boundary.execute()
        self.assertTrue(boundary.reports[0]['sequenceCompleted'])

    def test_product_echo_cannot_replace_actual_independent_peer_effects(self):
        boundary=Boundary('world-navigation','product-echo-without-peer','bookmark-add')
        boundary.echo={'bookmark':True,'bookmarkName':context(RUN)['name']}
        original=boundary.reduce
        boundary.reduce=lambda verb,data: None if verb=='bookmark-add' else original(verb,data)
        with self.assertRaises(AssertionError): boundary.execute()
        self.assertTrue(boundary.reports[0]['cleanupSucceeded'])

    def test_pcm_requires_every_fresh_symbol_and_silent_negative_control(self):
        from feature_journeys.evidence import audio_observation
        good=wav_bytes(RUN,TICKET)
        audio_observation(good,RUN,TICKET)
        silence=good[:44]+bytes(len(good)-44)
        audio_observation(silence,RUN,TICKET,True)
        for payload,silent in ((wav_bytes('ab'*16,TICKET),False),(good[:len(good)//2],False),
                               (silence,False),(good,True)):
            with self.subTest(silent=silent,bytes=len(payload)), self.assertRaises((ValueError,AssertionError,EOFError)):
                audio_observation(payload,RUN,TICKET,silent)

    def test_original_exports_require_exact_geometry_and_owned_source(self):
        from feature_journeys.evidence import file_observation
        fixture_url=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/'
        good=document(RUN,fixture_url,TICKET)
        file_observation(json.dumps(good).encode(),'create',RUN,TICKET,POLICY,fixture_url,TICKET)
        for change in ('geometry','source','owner','empty','foreign-extra'):
            candidate=copy.deepcopy(good)
            if change=='geometry': candidate['Entities'][0]['dimensions']['x']=99
            elif change=='source': candidate['Entities'][0]['modelURL']='http://foreign.test/mesh.gltf'
            elif change=='owner': candidate['Entities'][0]['name']='someone-else'
            elif change=='empty': candidate['Entities']=[]
            else: candidate['Entities'].append(copy.deepcopy(candidate['Entities'][0]))
            with self.subTest(change=change),self.assertRaises(AssertionError):
                file_observation(json.dumps(candidate).encode(),'create',RUN,TICKET,POLICY,fixture_url,TICKET)
        with self.assertRaises(AssertionError):
            file_observation(b'wrong mapping','assets',RUN,TICKET,POLICY)

    def test_blank_truncated_foreign_and_same_subject_images_are_not_visual_success(self):
        from feature_journeys.evidence import image_observation
        boundary=Boundary('graphics'); boundary.ticket=TICKET
        good=boundary.image()
        _,previous=image_observation(good,RUN,TICKET,SCREEN_POLICY)
        for candidate,run,changed in ((good,'ab'*16,False),(good[:-8],RUN,False),(good,RUN,True)):
            with self.subTest(changed=changed,bytes=len(candidate)),self.assertRaises((ValueError,AssertionError)):
                image_observation(candidate,run,TICKET,SCREEN_POLICY,previous,changed)

    def test_private_product_and_actor_strings_fail_before_being_persisted(self):
        boundary=Boundary('authentication'); boundary.activate(TICKET)
        value=boundary.observe({'afterSequence':0}); value['state']['principal']='private@example.test'
        with self.assertRaises(ValueError): result('feature.authentication.observe',value)
        boundary.state['principal']='private@example.test'
        with self.assertRaises(ValueError): boundary.witness()

    def test_missing_results_and_primary_failures_still_attempt_cleanup(self):
        for fault in ('malformed','transport'):
            boundary=Boundary('authentication')
            original=boundary.invoke
            def invoke(op, fields):
                if op.endswith('.act'):
                    if fault=='transport': raise OSError('controlled transport unavailable')
                    return None
                return original(op,fields)
            boundary.invoke=invoke
            with self.subTest(fault=fault),self.assertRaises((OSError,ValueError)):
                boundary.execute()
            self.assertTrue(boundary.reports[0]['cleanupSucceeded'])
            self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_sit_requires_three_actually_observed_variants_without_variant_inputs(self):
        with self.assertRaises(AssertionError): Boundary('emotes','sit-variant-stuck').execute()

    def test_partial_bundle_cleanup_and_stalled_script_effects_cannot_pass(self):
        for area,fault in (('assets','leaked-companions'),('scripts','script-effects-stalled')):
            with self.subTest(area=area),self.assertRaises(AssertionError) as error:
                Boundary(area,fault).execute()
            if area=='scripts': self.assertIn('07-consent-accept',str(error.exception))

    def test_delayed_old_success_is_not_a_cancellation_result(self):
        boundary=Boundary('authentication')
        original=boundary.reduce
        def reduce(verb,data):
            original(verb,data)
            if verb=='release-stale-response':
                boundary.state.update(principal='owned',protectedAccess=True)
        boundary.reduce=reduce
        with self.assertRaises(AssertionError): boundary.execute()


class FeatureRegistrationAndTransport(unittest.TestCase):
    def test_http_fixture_separates_reader_actor_and_public_resource_roles(self):
        reader,actor=secrets.token_hex(32),secrets.token_hex(32)
        server=make_server(reader,actor)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}/feature-fixture/v1'
            client=Client(base,reader)
            run,url=client.register('chat');client.activate(TICKET)
            request=Request(base+f'/runs/{run}/samples',data=json.dumps(dict(ticket=TICKET,actor='owned-observer',
                actorSequence=1,capturedEpochMs=server.journal.clock(),facts=projection('chat',SCENARIOS['chat']['baseline']))).encode(),
                headers={'Authorization':'Bearer '+actor,'Content-Type':'application/json'})
            with urlopen(request,timeout=2) as response:self.assertEqual(200,response.status)
            self.assertEqual(1,len(client.observe()['entries']))
            request.headers['Authorization']='Bearer '+reader
            with self.assertRaises(HTTPError) as error:urlopen(request,timeout=2)
            self.assertEqual(403,error.exception.code)
            error.exception.close()
            with urlopen(url+f'tickets/{TICKET}/marker.png',timeout=2) as response:
                self.assertEqual(marker_bytes(run,TICKET),response.read())
            with self.assertRaises(HTTPError) as error:urlopen(base+f'/runs/{run}',timeout=2)
            error.exception.close()
            client.close();client.close()
            with self.assertRaises(ValueError):client.observe()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_new_suite_cannot_pass_when_a_required_adapter_capability_is_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            env={**os.environ,'OVERTE_MOCK_E2E_STATE':str(Path(temporary)/'state.json')}
            command=[sys.executable,str(DEVICE/'run.py'),'--adapter-manifest',str(DEVICE/'adapters/mock/adapter.json'),
                '--catalog',str(DEVICE/'catalog.json'),'--suite','feature-graphics','--allow-virtual',
                '--output-dir',str(Path(temporary)/'run')]
            completed=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            self.assertNotEqual(0,completed.returncode,completed.stdout)
            summary=json.loads((Path(temporary)/'run/summary.json').read_text())
            # Existing runner owns status classification; no parallel verdict path.
            self.assertEqual('failed',summary['status'])
            gate=next(row for row in summary['results'] if row['id']=='feature-graphics-required')
            self.assertEqual('error',gate['status'])
            self.assertEqual(75,gate['returncode'])
            self.assertTrue(summary)

    def test_inventory_coverage_and_existing_module_composition_remain_synchronized(self):
        from feature_journeys.inventory import inventory
        from feature_journeys.scenarios import FOUNDATIONS
        saved=json.loads((DEVICE/'feature_journeys/adapter-contract.v1.json').read_text())
        self.assertEqual(inventory(),saved)
        matrix=json.loads((DEVICE/'feature_journeys/coverage.v1.json').read_text())
        self.assertEqual(set(SCENARIOS),{row['area'] for row in matrix['rows']})
        catalog=json.loads((DEVICE/'catalog.json').read_text())
        for area,foundations in FOUNDATIONS.items():
            selected={m['id'] for m in catalog['modules'] if 'feature-'+area in m['suites']}
            self.assertEqual(set(foundations)|{'launch-smoke','feature-'+area,'feature-'+area+'-required'},selected)
        for row in matrix['rows']:
            self.assertEqual(len(SCENARIOS[row['area']]['steps']),row['declaredCheckpoints'])
            self.assertEqual(sorted({kind for step in SCENARIOS[row['area']]['steps'] for kind in step['evidence']}),row['requiredEvidence'])
        self.assertEqual(0,matrix['physicalRuns'])
        self.assertTrue(all(row['adapter']=='missing' and row['device']=='untested' for row in matrix['rows']))

    def test_gate_also_requires_reused_foundation_capabilities(self):
        catalog=json.loads((DEVICE/'catalog.json').read_text())
        required=set().union(*(set(m['requires']) for m in catalog['modules'] if 'feature-graphics' in m['suites']))
        env={**os.environ,'PYTHONPATH':str(DEVICE),'OVERTE_DEVICE_CAPABILITIES_JSON':json.dumps(sorted(required-{'render.snapshot'})),
             'OVERTE_DEVICE_ADAPTER_MANIFEST':str(DEVICE/'adapters/mock/adapter.json'),
             'OVERTE_DEVICE_TARGET_SELECTOR':'virtual-owned-target', 'OVERTE_DEVICE_ARTIFACT_DIR':tempfile.gettempdir()}
        command=[sys.executable,str(DEVICE/'modules/feature_capability_gate.py'),'--area','graphics']
        done=subprocess.run(command,env=env,text=True,capture_output=True,timeout=10)
        self.assertEqual(75,done.returncode,done.stdout+done.stderr)
        self.assertIn('render.snapshot',done.stdout)

    def test_domain_features_keep_a_real_domain_session_and_registered_prerequisites(self):
        from feature_journeys.session import prepare
        from feature_journeys.scenarios import DOMAIN_AREAS
        from unittest.mock import Mock
        catalog=json.loads((DEVICE/'catalog.json').read_text())
        profiles=json.loads((DEVICE/'execution-profiles.json').read_text())['suites']
        for area in SCENARIOS:
            session=Mock()
            prepare(session,area)
            with self.subTest(area=area):
                if area in DOMAIN_AREAS:
                    session.enter_controlled_domain.assert_called_once_with()
                    session.ensure_controlled_scene.assert_not_called()
                    self.assertEqual('domain',profiles['feature-'+area]['fixture'])
                    module=next(m for m in catalog['modules'] if m['id']=='feature-'+area)
                    self.assertIn('navigation.enter-domain',module['requires'])
                else:
                    session.ensure_controlled_scene.assert_called_once_with()
                    session.enter_controlled_domain.assert_not_called()

    def test_external_inputs_fail_planning_before_target_discovery(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog=DEVICE/'catalog.json'
        policy=load_policy(DEVICE/'acceptance-policy.json',catalog)
        profiles=load_profiles(DEVICE/'execution-profiles.json',catalog)
        plan=compile_plan(policy,catalog,profiles,'mock',['feature-journeys'],set(),False,set(),'auto')
        self.assertFalse(plan['ready'])
        self.assertTrue({'OVERTE_E2E_FEATURE_FIXTURE_URL','OVERTE_E2E_FEATURE_IMAGE_POLICY',
                          'OVERTE_E2E_FEATURE_READER_TOKEN'} <= set(plan['missingInputs']))

    def test_adapter_subprocess_receives_neither_reader_token_nor_evidence_policy(self):
        import adapter_client
        env={'OVERTE_E2E_FEATURE_READER_TOKEN':'private-reader', 'OVERTE_E2E_FEATURE_IMAGE_POLICY':'private-policy'}
        with patch.dict(os.environ,env),patch.object(adapter_client,'load_command',return_value=['fake-adapter']),patch.object(adapter_client.subprocess,'run') as execute:
            execute.return_value=subprocess.CompletedProcess([],0,'{}','')
            adapter_client.invoke(Path('unused'),'private-target','feature.graphics.observe',{})
            passed=execute.call_args.kwargs['env']
            self.assertNotIn('OVERTE_E2E_FEATURE_READER_TOKEN',passed)
            self.assertNotIn('OVERTE_E2E_FEATURE_IMAGE_POLICY',passed)
        import importlib.util
        spec=importlib.util.spec_from_file_location('feature_runner_privacy',DEVICE/'run.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with patch.object(runner.subprocess,'run') as execute:
            execute.return_value=subprocess.CompletedProcess([],0,'{}','')
            runner.adapter_call(['fake-adapter'],'discover',environment=env)
            self.assertNotIn('OVERTE_E2E_FEATURE_READER_TOKEN',execute.call_args.kwargs['env'])
            self.assertNotIn('OVERTE_E2E_FEATURE_IMAGE_POLICY',execute.call_args.kwargs['env'])



if __name__ == '__main__':
    unittest.main()
