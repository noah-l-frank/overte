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
from feature_journeys.scenarios import SCENARIOS, VERSION
from feature_journeys.server import make_server
from feature_journeys.witness import Client, Journal, projection

RUN = '01' * 16
TICKET = '02' * 16
SCREEN_POLICY = {'source': 'world-render-target', 'marker': [4, 4, 132, 36], 'subject': [0, 48, 160, 144]}

POLICY = {'screen': SCREEN_POLICY, 'file': SCREEN_POLICY}


class Boundary:
    def __init__(self, area, fault='', target=None, *, snapshot_backend='photos-add-only'):
        self.area, self.fault, self.target = area, fault, target
        self.run = RUN
        self.ctx = context(RUN)
        self.state = copy.deepcopy(SCENARIOS[area]['baseline'])
        if area=='snapshots':self.state.update(saveBackend=snapshot_backend,savePermission='granted' if snapshot_backend=='photos-add-only' else 'not-required')
        self.snapshot_original_state=copy.deepcopy(self.state);self.snapshot_original=None
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
        self.emote_started=self.emote_restored=self.emote_due=None
        self.emote_final=False
        self.auth_process=1;self.auth_delayed_process=None;self.auth_delayed_held=False;self.auth_delayed_valid=False
        self.web_ready=False;self.web_history=[];self.web_late_at=None
        self.navigation_responses=[]

    def epoch(self):
        return 2_000_000 + getattr(self, 'clock', 0) * 1000

    def activate(self, ticket, verb='baseline', inputs=None):
        self.ticket = ticket
        self.journal.activate(RUN, ticket, verb, inputs)
        if self.area in {'world-web','tablet-web'} and verb=='restore-resource':
            self.web_ready=self.fault!='web-restore-ignored'
        if self.area=='authentication':
            if verb=='release-stale-response':
                if not self.auth_delayed_held:raise AssertionError('No actual model delayed request')
                self.auth_delayed_held=False
                self.auth_delayed_valid=self.fault!='delayed-grant-not-issued'
                if self.auth_delayed_valid and (self.auth_delayed_process==self.auth_process or self.fault=='old-response-adopted'):
                    self.state.update(principal='owned',pending=False,protectedAccess=True)
            elif verb=='cleanup' and self.fault!='backend-revocation-ignored':
                self.auth_delayed_valid=False;self.auth_delayed_held=False

    def reduce(self, verb, data):
        s, a = self.state, self.area
        if verb == 'restart-app':
            if self.fault != 'restart-ignored':
                self.lifecycle['launches'] += 1
                self.lifecycle['activations'] += 1
                if a=='authentication':
                    self.auth_process+=1
                    s.update(dialog=self.fault=='startup-login-open' and s['principal']=='anonymous',pending=False,error='none')
                if a=='scripts':
                    # The reviewed mobile startup routes load system defaults,
                    # not the saved user-source list. This is model behavior,
                    # independently reduced from the checkpoint assertions.
                    previous_effects=s['effects']
                    if self.fault not in {'script-restart-keeps-running','script-restart-forged-absence'}:
                        s.update(running=[],effects=0,companions=[])
                    if self.fault=='script-restart-residual-effect':s['effects']=previous_effects
                    s.update(picker=False,error='none',open=self.fault=='script-restart-keeps-editor')
                    self.script_restarted=True;self.script_restart_clock=self.clock
            return
        if verb == 'background-resume':
            if self.fault != 'background-ignored':
                self.lifecycle['backgrounds'] += 1
                self.lifecycle['activations'] += 1
            if a == 'audio' and s['recording']:
                s.update(recording=False, phase='cancelled', history=['capturing', 'cancelled'],
                         bufferedFrames=0, error='backgrounded')
            if a in ('lifecycle-input','chat'):
                s.update(keyboard=False, focused=False)
            if a=='chat' and self.fault=='chat-resume-loses-history':s.update(domainMessages=[],messages=[])
            if a=='chat' and self.fault=='chat-resume-default-channel':s.update(channel='local',messages=list(s['localMessages']))
            if a=='chat' and self.fault=='chat-resume-ghost-keyboard':s.update(focused=True,keyboard=True)
            if a in {'world-web','tablet-web'}:
                s.update(text='',focused=False)
                if self.fault!='web-resume-old-document':s['documentLoads']+=1
            return
        if a == 'world-navigation':
            if verb in {'open','close'}:
                s.update(panel=verb=='open',searchQuery='',searchResults=[self.ctx['destination']] if verb=='open' else [])
                if self.fault=='navigation-reused-query' and verb=='open':s.update(searchQuery=self.ctx['name'])
                if verb=='open' and self.fault!='navigation-no-http-directory':self.navigation_response('directory')
            elif verb == 'bookmark-add': s.update(bookmark=True, bookmarkName=data['name'])
            elif verb == 'bookmark-add-cancel' and self.fault=='navigation-cancel-add-saved':s.update(bookmark=True,bookmarkName=data['name'])
            elif verb == 'bookmark-rename-cancel' and self.fault=='navigation-cancel-rename-saved':s['bookmarkName']=data['name']
            elif verb == 'bookmark-rename': s['bookmarkName'] = data['name']
            elif verb == 'directory-search' and self.fault!='navigation-ignored-search':
                s.update(searchQuery=data['query'],searchResults=[] if data['query']==self.ctx['hidden'] else [self.ctx['destination']])
            elif verb in {'directory-select','bookmark-visit'}:
                s.update(location='B' if verb=='directory-select' else 'A',panel=False,searchQuery='',searchResults=[])
                if self.fault=='navigation-ack-without-arrival':s['location']='A' if verb=='directory-select' else 'B'
                if self.fault=='navigation-old-model':s['searchResults']=[self.ctx['destination']]
            elif verb == 'navigate-missing':
                s.update(error='none' if self.fault=='navigation-no-native-error' else 'not-found',addressDialog=True)
                if self.fault=='navigation-missing-changes-location':s['location']='A'
                if self.fault!='navigation-no-http-404':self.navigation_response('missing-name')
            elif verb == 'dismiss-error':
                s.update(error='none',addressDialog=self.fault=='navigation-unclosed-address-dialog')
            elif verb == 'bookmark-delete': s.update(bookmark=False, bookmarkName='')
        elif a == 'authentication':
            if verb == 'login-open': s['dialog'] = True
            elif verb == 'login-cancel':
                s.update(dialog=False,error='none')
                if self.fault=='cancel-invents-network-abort':s['pending']=False
            elif verb == 'login-submit':
                if data['account'] == 'invalid': s['error'] = 'invalid-credentials'
                elif data['account'] == 'delayed':
                    s['pending']=True;self.auth_delayed_held=True;self.auth_delayed_process=self.auth_process
                else: s.update(principal='owned', dialog=False, protectedAccess=True)
            elif verb == 'logout': s.update(principal='anonymous', protectedAccess=False)
        elif a == 'avatar-people':
            if verb == 'avatar-url':
                if data['resource'] == 'missing.fst':
                    s.update(requestedAvatar='missing',avatar='unavailable',modelLoaded=False,loadFailed=True)
                    if self.fault=='avatar-retains-old-model':s.update(avatar='A',modelLoaded=True)
                    if self.fault=='avatar-no-failure-event':s['loadFailed']=False
                    if self.fault=='avatar-native-fallback':s.update(avatar='fallback',modelLoaded=True)
                else:s.update(avatar='A',requestedAvatar='A',modelLoaded=True,loadFailed=False)
            elif verb == 'avatar-bookmark-save': s['bookmarked'] = True
            elif verb == 'avatar-bookmark-delete': s['bookmarked'] = False
            elif verb == 'avatar-scale': s['scale'] = data['value']
            elif verb == 'wearable-add':
                if data['resource']!='gltf-bundle/main.gltf':raise AssertionError('Model URL required')
                s['wearable'] = self.fault!='avatar-wearable-ack-only'
            elif verb == 'avatar-bookmark-choose':
                s.update(avatar='A',requestedAvatar='A',modelLoaded=True,loadFailed=False,scale=1.0,wearable=False)
                if self.fault=='avatar-bookmark-no-reload':s.update(avatar='unavailable',modelLoaded=False)
                if self.fault=='avatar-bookmark-leaks-owned-wearable':s['wearable']=True
                if self.fault=='avatar-bookmark-old-failure':s['loadFailed']=True
            elif verb == 'connection-request': s.update(connection='pending', dialog=True)
            elif verb in {'connection-cancel', 'peer-reject', 'connection-remove'}: s.update(connection='none', dialog=False)
            elif verb == 'peer-accept': s.update(connection='connected', dialog=False)
            elif verb == 'avatar-restore': s.update(avatar='original',requestedAvatar='original')
        elif a == 'create':
            if verb in {'open','close'}: s['editor'] = verb == 'open'
            elif verb == 'model-create':
                s.update(objects=['model'], selection=['model']); self.model_ticket=self.ticket
            elif verb == 'import-picker-open':s['picker']=True
            elif verb == 'import-picker-cancel':
                s['picker']=False
                if self.fault=='create-on-cancel':s.update(objects=['model'],selection=['model'])
            elif verb == 'import-picker-accept':
                s.update(picker=False,objects=['model'],selection=['model'])
                if self.fault=='picker-ack-only':s.update(objects=[],selection=[])
            elif verb == 'create-retry':s.update(objects=['cube'],selection=['cube'],error='permission-denied' if self.fault=='retry-retains-error' else 'none')
            elif verb == 'apply-texture':
                s['textured'] = True; self.texture_ticket=self.ticket
            elif verb == 'delete-owned': s.update(objects=[], selection=[], textured=False, voxelValue=0)
            elif verb == 'voxel-create': s.update(objects=['voxel'], selection=['voxel'])
            elif verb == 'voxel-edit': s['voxelValue'] = 1
            elif verb == 'set-rez-permission':
                s['canRez']=data['allowed']
                if data['allowed'] and self.fault=='permission-invents-ui-clear':s['error']='none'
            elif verb == 'create-denied': s['error'] = 'permission-denied'
        elif a == 'emotes':
            if verb in {'open','close'}: s['panel'] = verb == 'open'
            elif verb == 'play':
                s.update(animation=data['name'],sit='Sit1' if data['name']=='Sit' else 'none',poseProgress=.5,
                    override=self.fault!='ordinary-no-override')
                if self.fault=='chooser-hidden':s['panel']=False
                self.emote_started=self.clock;self.emote_restored=None;self.emote_final=False
                self.emote_due=self.clock+2 if data['name']!='Sit' else None
            elif verb == 'sit':
                self.sit_count += 1
                s.update(animation='Sit',override=True,sit='Sit1' if self.fault=='sit-variant-stuck' else 'Sit'+str((self.sit_count-1)%3+1),poseProgress=.5)
                self.emote_started=self.clock;self.emote_restored=self.emote_due=None;self.emote_final=False
            elif verb == 'override':
                s.update(animation=data['name'],override=True,sit='none')
                self.emote_started=self.clock;self.emote_restored=None;self.emote_due=self.clock+2;self.emote_final=True
            elif verb == 'cancel' and not (self.fault=='late-natural-cancel' and self.emote_final):
                if s['override']:self.emote_restored=self.clock
                s.update(animation='idle',sit='none',override=False,poseProgress=0.)
                self.emote_due=None
            # wait-complete delivers no input and changes no source state.
        elif a in {'world-web','tablet-web'}:
            def load(page,origin='primary',kind='http',status=200):
                s.update(page=page,origin=origin,documentKind=kind,httpStatus=status,text='',focused=False,
                    inlineLeases=1 if kind=='inline' else 0)
                if self.fault!='web-frozen-document':s['documentLoads']+=1
            if verb=='open':s['open']=True;load('reference')
            elif verb=='close':s.update(open=False,page='none',origin='none',documentKind='none',httpStatus=0,inlineLeases=0,focused=False,text='')
            elif verb == 'focus-type': s.update(text=data['text'], focused=True)
            elif verb=='clear-text':s.update(text='',focused=True)
            elif verb=='submit':
                s.update(bridgeMessages=s['bridgeMessages']+1,attemptedMessages=s['attemptedMessages']+1,focused=False)
                if self.fault!='web-echo-missing':s['bridgeEchoes']+=1
            elif verb in ('navigate','navigate-foreign'):
                self.web_history.append(s['page'])
                if verb=='navigate-foreign':load('foreign','foreign')
                elif data['resource']=='recovery.html':load('recovery',status=200 if self.web_ready else 404)
                else:load('B' if data['resource']=='page-b.html' else 'reference')
            elif verb=='back':load(self.web_history.pop())
            elif verb=='foreign-origin-message':
                if self.fault!='web-foreign-attempt-ignored':s['attemptedMessages']+=1
                if self.fault=='web-foreign-accepted':s['bridgeMessages']+=1
            elif verb=='restore-resource':
                if self.fault=='web-restore-forges-navigation':load('recovery')
            elif verb=='reload':load(s['page'],status=200 if s['page']!='recovery' or self.web_ready else 404)
            elif verb=='background-resume':load('reference')
            elif verb=='open-inline-app':
                load('inline','inline','inline',0)
                if self.fault=='web-http-inline':s.update(origin='primary',documentKind='http',httpStatus=200,inlineLeases=0)
            elif verb=='hold-inline-message':s.update(deferredMessages=1,attemptedMessages=s['attemptedMessages']+1,focused=False)
            elif verb=='return-from-inline':
                load('reference')
                if self.fault=='web-inline-lease-leak':s['inlineLeases']=1
            elif verb=='deliver-retired-inline-message':
                if self.fault!='web-deferred-leak':s['deferredMessages']=0
                if self.fault=='web-stale-delivery':self.web_late_at=self.clock+1
        elif a == 'graphics':
            if not hasattr(self,'graphics_original'): self.graphics_original = copy.deepcopy(s)
            if verb in ('open','close'): s['dialog'] = verb == 'open'
            elif verb == 'set-resolution': s.update(resolution=data['value'], renderScale=data['value'])
            elif verb == 'set-haze': s.update(haze=data['enabled'],hazePass=data['enabled'])
            elif verb == 'set-mirrors': s.update(mirror=data['enabled'],mirrorPass=data['enabled'])
            elif verb == 'restore-original':
                s.update({k:v for k,v in self.graphics_original.items() if k!='dialog'})
        elif a == 'audio':
            if verb in ('open', 'close'): s['open'] = verb == 'open'
            elif verb == 'record-start':
                if s['muted']:
                    s.update(phase='error', history=['error'], error='microphone-muted',
                             recordedFrames=0, playedFrames=0, bufferedFrames=0)
                else:
                    s.update(recording=True, preview=False, phase='capturing', history=['capturing'],
                             error='none', recordedFrames=24000, playedFrames=0, bufferedFrames=24000)
                    self.recorded_ticket = self.ticket
            elif verb == 'record-cancel':
                s.update(recording=False, phase='cancelled', history=['capturing', 'cancelled'], bufferedFrames=0)
            elif verb == 'await-completion':
                s.update(recording=False, preview=False, phase='completed',
                    history=['capturing', 'playing', 'draining', 'completed'],
                    recordedFrames=144000, playedFrames=144000, bufferedFrames=0)
            elif verb == 'mute':
                s['muted'] = data['enabled']
                if s['muted'] and s['recording']:
                    s.update(recording=False, phase='cancelled', history=['capturing', 'cancelled'],
                             bufferedFrames=0, error='microphone-muted')
        elif a == 'chat':
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close':s.update(draft='',channel='local' if self.fault=='chat-closed-default-channel' else 'none',focused=False,keyboard=False)
                else:s.update(channel='local')
            elif verb == 'type': s.update(draft=data['text'], focused=True, keyboard=True)
            elif verb == 'select-channel': s.update(channel=data['channel'],focused=False,keyboard=False)
            elif verb == 'send':
                text=s['draft']
                if text:
                    s[s['channel']+'Messages'].append(text)
                    if s['mixerConnected']:s['peerMessages'].append(text)
                    elif self.fault=='offline-delivery':s['peerMessages'].append(text)
                    if self.fault!='offline-draft-retained' or s['mixerConnected']:s['draft']=''
                    if self.fault=='duplicate-peer-delivery' and s['mixerConnected']:s['peerMessages'].append(text)
            elif verb == 'peer-send':
                if self.fault!='fake-peer-filter' or data['text']!=self.ctx['hidden']:
                    s[data['channel']+'Messages'].append(data['text'])
            elif verb == 'peer-send-distant':
                if self.fault=='distant-peer-accepted':s['localMessages'].append(data['text'])
            elif verb == 'network-remove-mixer': s['mixerConnected']=False
            elif verb == 'network-restore-mixer':
                s['mixerConnected']=True;self.chat_reconnect_at=self.clock
                if self.fault=='queued-replay':s['peerMessages'].append(self.ctx['retry'])
            s['messages']=list(s[s['channel']+'Messages']) if s['open'] else []
        elif a == 'snapshots':
            if verb in {'open','close'}:s['open']=verb=='open'
            elif verb=='capture-cancel':
                s['pending']=True;s['captureHistory'].append('pending')
                if self.fault!='snapshot-cancel-ignored':
                    s['pending']=False;s['captureHistory'].append('cancelled')
                if self.fault=='snapshot-idle-cancel-proof':s['captureHistory']=['cancelled']
                if self.fault=='snapshot-cancel-creates-file':s['files']=1
            elif verb=='set-save-permission':
                if self.fault!='snapshot-permission-ignored':s['savePermission']=data['state']
                if self.fault=='snapshot-permission-clears-error':s['error']='none'
            elif verb=='capture':
                if self.fault=='snapshot-capture-needs-photos' and s['savePermission']=='denied':s['error']='permission-denied'
                else:
                    s['files']=1;s['captureHistory']+=['pending','complete'];self.capture_ticket=self.ticket;self.snapshot_original=self.image(self.ticket)
            elif verb=='save-denied':
                if self.fault=='snapshot-denied-save-commits':s['saved']=1
                else:s['error']='permission-denied'
            elif verb=='save-picker-open':s.update(saveSheet=True,error='none')
            elif verb=='save-picker-cancel':
                s['saveSheet']=False
                if self.fault=='snapshot-picker-cancel-saves':s['saved']=1
            elif verb=='save':
                s.update(saveSheet=False,error='none')
                if self.fault!='snapshot-save-ack-only':s['saved']=1
            elif verb=='share-open':s['shareSheet']=True
            elif verb=='share-cancel':
                s['shareSheet']=False
                if self.fault=='snapshot-share-cancel-delivers':s['shares']=1
            elif verb=='share-select-owned':
                s['shareSheet']=False
                if self.fault!='snapshot-share-handoff-only':s['shares']=1
            elif verb=='upload-fail':s['error']='offline'
            elif verb=='upload':s.update(uploads=1,error='none')
        elif a == 'scripts':
            if verb in {'open','close'}:
                s['open'] = verb == 'open'
                if verb == 'close': s['error'] = 'none'
            elif verb == 'picker-open': s['picker'] = True
            elif verb == 'picker-cancel':
                s['picker'] = False
                if getattr(self,'script_restarted',False) and self.fault=='script-restart-cancel-executes':
                    s.update(running=['owned-script'],effects=4,companions=['companion.js'])
            elif verb == 'picker-accept':
                s['picker']=False
                if not (getattr(self,'script_restarted',False) and self.fault=='script-reimport-ignored'):
                    s.update(running=['owned-script'], effects=4, companions=['companion.js'])
            elif verb == 'load-url' and data['resource'] == 'missing.js': s['error'] = 'not-found'
            elif verb == 'stop-owned': s.update(running=[], effects=0, companions=[])
        elif a == 'assets':
            if verb in {'open','close'}:s['open']=verb=='open'
            elif verb=='upload-picker-open':s.update(picker=True,stagedAvailable=True)
            elif verb=='upload-picker-select':s['pickerFile']='main.gltf'
            elif verb=='retire-staged-primary':s['stagedAvailable']=self.fault=='assets-staged-retirement-ignored'
            elif verb=='upload-picker-accept-unavailable':
                if not s['stagedAvailable'] and self.fault!='assets-picker-no-file-error':s['error']='file-unavailable'
                if self.fault=='assets-picker-unavailable-publishes':s.update(mappings=[self.ctx['assetGltf']],selected=self.ctx['assetGltf'])
            elif verb=='upload-picker-cancel':s.update(picker=False,pickerFile='',error='none',stagedAvailable=False)
            elif verb=='upload':
                kind={'gltf-bundle/main.gltf':'gltf','obj-bundle/main.obj':'obj','asset-stand.fbx':'fbx'}[data['resource']]
                primary={'gltf':'assetGltf','obj':'assetObj','fbx':'assetFbx'}[kind]
                keys=[primary]+(['assetBin','assetTexture'] if kind=='gltf' else ['assetMtl','assetTexture'] if kind=='obj' else [])
                s.update(mappings=[self.ctx[k] for k in keys],selected=self.ctx[primary],
                    companions=['mesh/triangle.bin','textures/checker.png'] if kind=='gltf' else
                               ['materials/palette.mtl','textures/checker.png'] if kind=='obj' else [],
                    bakeState='ready' if kind=='fbx' else 'unsupported',bakeAvailable=kind=='fbx',deleteEnabled=True)
                if self.fault=='assets-flat-name':s.update(mappings=[self.ctx['name']],selected=self.ctx['name'])
                if self.fault=='assets-missing-companion' and kind!='fbx':s['mappings'].pop();s['companions'].pop()
                if self.fault=='assets-gltf-baked' and kind=='gltf':s.update(bakeState='ready',bakeAvailable=True)
            elif verb=='rename-folder':
                old=self.ctx['name']+'/';new=data['name']+'/'
                s['mappings']=[new+name[len(old):] for name in s['mappings']]
                s['selected']=new+s['selected'][len(old):]
                if self.fault=='assets-rename-breaks-bundle':s['mappings']=s['mappings'][:1];s['companions']=[]
            elif verb=='set-baking':
                s.update(bakeState='ready' if data['enabled'] else 'disabled',baking=False)
                if self.fault=='assets-no-real-bake' and data['enabled']:s['bakeState']='disabled'
                if self.fault=='assets-disable-unsettled-worker' and not data['enabled']:s.update(bakeState='baking',baking=True)
            elif verb=='import-selected':s['sceneModel']=True
            elif verb=='remove-owned-model':s['sceneModel']=False
            elif verb=='set-write-permission':
                s.update(canWrite=data['allowed'],deleteEnabled=data['allowed'] and bool(s['selected']))
                if self.fault=='assets-delete-enabled-when-denied':s['deleteEnabled']=True
            elif verb=='delete-denied':
                if self.fault=='assets-denied-deletes':s.update(mappings=[],selected='',companions=[],bakeState='none',bakeAvailable=False)
                if self.fault=='assets-invented-permission-error':s['error']='permission-denied'
            elif verb=='delete-owned':
                s.update(mappings=[],selected='',bakeState='none',baking=False,bakeAvailable=False,deleteEnabled=False)
                if self.fault!='leaked-companions':s['companions']=[]
        elif a == 'lifecycle-input':
            if verb=='open-editor':
                self.life_context=getattr(self,'life_context',0)+1
                s.update(editor=data['editor'],text='',focused=True,keyboard=True,generation=self.life_context)
                if self.fault=='life-inherited-editor-text' and data['editor']=='chat':s['text']=self.ctx['unicode']
            elif verb=='type':s['text']=data['text']
            elif verb=='back':
                s.update(editor='none',text='',keyboard=False,focused=False,generation=0)
                if self.fault=='life-back-only-hides-keyboard':s.update(editor='create',text=self.ctx['unicode'],generation=1)
            elif verb=='hold-editor-input':
                if self.fault!='life-hold-ignored':
                    self.life_pending=(s['generation'],data['text']);s['deferredInputs']=1
            elif verb=='replace-context':
                if self.fault!='life-context-replacement-ignored':
                    self.life_context+=1;s.update(generation=self.life_context,text='',focused=False,keyboard=False)
            elif verb=='deliver-stale-input':
                if not getattr(self,'life_pending',None):raise AssertionError('No original pending input to deliver')
                old_generation,text=self.life_pending
                if self.fault!='life-stale-attempt-ignored':s['staleAttempts']+=1
                if old_generation==s['generation'] or self.fault=='life-stale-input-adopted':s['text']=text
                if self.fault not in {'life-stale-input-not-released','life-cleanup-pending-leak'}:self.life_pending=None;s['deferredInputs']=0
            elif verb=='close-editor':s.update(editor='none',text='',generation=0,focused=False,keyboard=False)
            elif verb=='world-input':
                if self.fault!='life-world-event-not-dispatched':s['worldAttempts']+=1
                if s['editor']=='none':s.update(worldDisplacement=1.0,heldInputs=['forward'],positionDelta=dict(x=0.0,y=0.0,z=-1.0))
            elif verb=='release-input':
                if self.fault!='life-release-ignored':s['heldInputs']=[]
            elif verb=='restore' and self.fault!='life-restore-ignored':s.update(worldDisplacement=0.0,positionDelta=dict(x=0.0,y=0.0,z=0.0))

    def invoke(self, operation, fields):
        self.actions.append((operation, copy.deepcopy(fields)))
        kind = operation.rsplit('.', 1)[-1]
        if kind == 'observe': return self.observe(fields)
        if kind == 'cleanup':
            self.verb = 'cleanup'
            if self.fault != 'cleanup-ignored':
                input_history={k:self.state.get(k) for k in ('worldAttempts','staleAttempts')}
                self.state = copy.deepcopy(self.graphics_original if self.area=='graphics' and hasattr(self,'graphics_original')
                                           else self.snapshot_original_state if self.area=='snapshots' else SCENARIOS[self.area]['baseline'])
                if self.area=='lifecycle-input':
                    for key,original in input_history.items():self.state[key]=0 if self.fault=='life-cleanup-resets-history' else original
                    if self.fault!='life-cleanup-pending-leak':self.life_pending=None
                if self.area=='emotes':self.emote_started=self.emote_restored=self.emote_due=None
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
        if self.web_late_at is not None and self.clock>=self.web_late_at:
            self.state['bridgeMessages']+=1;self.web_late_at=None
        if self.area=='authentication':self.state['delayedGrantOutstanding']=self.auth_delayed_valid
        if (self.area=='chat' and self.fault=='late-queued-replay' and hasattr(self,'chat_reconnect_at')
                and self.clock-self.chat_reconnect_at>=1 and not getattr(self,'chat_late_replayed',False)):
            self.state['peerMessages'].append(self.ctx['retry']);self.chat_late_replayed=True
        if self.area=='emotes':
            if self.emote_due is not None and self.clock>=self.emote_due and self.fault!='emote-timer-ignored':
                self.state.update(animation='idle',sit='none',override=False,poseProgress=0.)
                self.emote_restored=self.clock;self.emote_due=None
            # Independently timed model source, never copied from a checkpoint.
            self.state['restoredBeforeNominalEnd']=(self.emote_started is not None and self.emote_restored is not None
                and 0<=(self.emote_restored-self.emote_started)*1000<1750)
        if (self.area=='scripts' and self.fault=='script-restart-late-replay'
                and getattr(self,'script_restarted',False) and not getattr(self,'script_late_replayed',False)
                and self.clock-self.script_restart_clock>=1):
            self.state.update(running=['owned-script'],effects=4,companions=['companion.js']);self.script_late_replayed=True
        if self.area=='scripts' and self.state['running'] and self.fault!='script-effects-stalled':
            self.state['effects'] += 1
        if self.area=='lifecycle-input':self.state['deferredInputs']=int(getattr(self,'life_pending',None) is not None)
        if self.area=='lifecycle-input' and self.fault=='life-release-still-moving' and self.verb=='release-input':
            self.state['worldDisplacement']+=0.02
            self.state['positionDelta']['z']=-self.state['worldDisplacement']
        if self.area=='lifecycle-input' and self.fault=='life-release-motion-constant-distance' and self.verb=='release-input':
            import math
            angle=0.04*math.sin(self.clock*2*math.pi)
            self.state['positionDelta']=dict(x=angle,y=0.0,z=-math.sqrt(1-angle*angle))
        state = copy.deepcopy(self.state)
        if self.area=='scripts' and self.fault=='script-restart-forged-absence' and self.verb=='restart-app':
            state.update(running=[],effects=0,companions=[])
        if self.area=='emotes' and getattr(self,'forge_restore_timing',False) and self.emote_final and self.verb=='cancel':
            state['restoredBeforeNominalEnd']=True # Only the adapter seam lies; the independent actor must disagree.
        if self.fault == 'product-echo-without-peer' and self.verb == self.target:
            # Deliberately forge only the product seam. The actor still sees the
            # unchanged real model; this must not satisfy the common journey.
            state.update(self.echo)
        if self.fault == 'script-effects-stalled' and self.verb=='picker-accept' and not getattr(self,'early_script_read',False):
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
                source = self.recorded_ticket if state['phase'] == 'completed' else self.ticket
                audible = state['phase'] == 'completed'
                audio = wav_bytes(RUN, source or self.ticket, profile='recorded-preview-v1')
                if not audible:
                    audio = audio[:44] + bytes(len(audio) - 44)
                values.update(audio=audio, file=wav_bytes(RUN, self.recorded_ticket or self.ticket, profile='recorded-preview-v1'))
            elif self.area=='snapshots':
                values['file']=self.snapshot_original if self.snapshot_original is not None else self.image(self.capture_ticket or self.ticket)
                if self.fault=='snapshot-destination-changed' and self.verb in {'save','share-select-owned','upload'}:values['file']=self.image(self.capture_ticket)
            elif self.area == 'create': values['file'] = json.dumps(document(RUN, model_ticket=self.model_ticket, texture_ticket=self.texture_ticket)).encode()
            elif self.area == 'assets': values['file'] = companion('gltf-bundle/main.gltf')
            for kind, content in values.items():
                name = f'{self.sequence}-{kind}.bin'
                self.files[name] = content
                artifacts.append(dict(kind=kind, name=name, sequence=self.sequence,
                    ticket=TICKET if self.fault == 'foreign-artifact' else self.ticket,
                    capturedEpochMs=self.epoch() - (2000 if self.fault == 'stale-artifact' else 0)))
                if kind == 'image': artifacts[-1]['source'] = 'world-render-target'
                if self.area=='snapshots' and kind=='file':
                    artifacts[-1]['source']={'capture':'snapshot-private-original','save':'snapshot-saved-original',
                        'share-select-owned':'snapshot-receiver-original','upload':'snapshot-upload-original'}.get(self.verb,'snapshot-private-original')
                    if self.fault=='snapshot-wrong-file-source' and self.verb!='capture':artifacts[-1]['source']='snapshot-private-original'
            if self.fault == 'missing-evidence' or self.ignored:
                artifacts = []
        return dict(schemaVersion=1, contractVersion=VERSION, runId='ff'*16 if self.fault == 'foreign-run' else RUN,
            sequence=1 if self.fault == 'replayed-sample' else self.sequence,
            capturedEpochMs=self.epoch() - (2000 if self.fault == 'stale-sample' else 0),
            state=state, artifacts=artifacts, resources=self.resources.copy(), lifecycle=self.lifecycle.copy())

    def witness(self):
        self.actor_sequence += 1
        if self.fault not in {'missing-witness','frozen-witness'} or self.actor_sequence == 1:
            facts = projection(self.area, self.state)
            if self.area=='chat':
                if self.fault=='chat-peer-draft':facts['draft']=''
                if self.fault=='chat-peer-focus':facts.update(focused=False,keyboard=False)
                if self.fault=='chat-peer-missing-keyboard':facts.pop('keyboard')
            if self.area=='scripts':
                if self.fault=='script-peer-open' and self.verb=='open':facts['open']=False
                if self.fault=='script-peer-picker' and self.verb=='picker-open':facts['picker']=False
                if self.fault=='script-peer-error' and self.verb=='load-url':facts['error']='none'
                if self.fault=='script-peer-missing-picker':facts.pop('picker')
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

    def navigation_response(self,kind):
        # An independent boundary reducer, never copied from a checkpoint.
        self.navigation_responses.append(dict(sequence=len(self.navigation_responses)+1,responseId=secrets.token_hex(16),
            ticket=TICKET if self.fault=='navigation-foreign-http-ticket' and kind=='missing-name' else self.ticket,
            kind=kind,status=200 if kind=='directory' else 404,bytes=100,sha256='a'*64,
            completedEpochMs=int(self.epoch())-(2000 if self.fault=='navigation-old-http-404' and kind=='missing-name' else 0)))

    def navigation_source(self):
        return dict(navigationProviderVersion=1,instance='f'*32,runId=RUN,inputs=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',
            sourceRevision='a'*40,sceneUrl='http://controlled.test/scene.json'),capturedEpochMs=int(self.epoch()),active=True,
            ticket=self.ticket,responses=copy.deepcopy(self.navigation_responses),failedResponses=0)

    def execute(self):
        return Journey(self.area, RUN, f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
            invoke=self.invoke, witness=self.witness, activate=self.activate,
            read_artifact=self.files.__getitem__, image_policy=POLICY, continuity=self.continuity,
            monotonic=lambda:self.clock, epoch_ms=self.epoch, sleep=self.sleep, report=self.reports.append, navigation_source=self.navigation_source).execute()


class FeatureJourneys(unittest.TestCase):
    def test_navigation_actual_empty_query_filtering_cancellation_and_reopen_have_independent_reads(self):
        boundary=Boundary('world-navigation');boundary.execute();samples=boundary.reports[0]['samples']
        query=[s['state'] for s in samples if s['phase'].endswith('-directory-search')]
        self.assertTrue(any(s['searchQuery']==context(RUN)['hidden'] and not s['searchResults'] for s in query))
        self.assertTrue(any(s['searchQuery']==context(RUN)['name'] and s['searchResults']==[context(RUN)['destination']] for s in query))
        opened=[s['state'] for s in samples if s['phase'].endswith('-open')]
        self.assertTrue(all(s['searchQuery']=='' and s['searchResults']==[context(RUN)['destination']] for s in opened))
        failed=[s for s in samples if s['phase'].endswith('-navigate-missing')]
        self.assertTrue(all(s['state']['error']=='not-found' and s['navigationHttp'][0]['status']==404 for s in failed))
        self.assertEqual(15,len(SCENARIOS['world-navigation']['steps']))

    def test_navigation_ignored_effects_cancelled_saves_and_retired_pages_cannot_pass(self):
        for fault in ('navigation-ignored-search','navigation-cancel-add-saved','navigation-cancel-rename-saved',
                      'navigation-reused-query','navigation-ack-without-arrival','navigation-old-model',
                      'navigation-no-native-error','navigation-missing-changes-location','navigation-unclosed-address-dialog'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('world-navigation',fault).execute()

    def test_navigation_requires_actual_owned_directory_and_current_named_404_receipts(self):
        for fault in ('navigation-no-http-directory','navigation-no-http-404','navigation-foreign-http-ticket','navigation-old-http-404'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('world-navigation',fault).execute()
        boundary=Boundary('world-navigation');boundary.navigation_source=None
        with self.assertRaisesRegex(ValueError,'navigation HTTP source'):boundary.execute()
        self.assertEqual([],boundary.actions)

    def test_navigation_final_http_source_read_cannot_finish_after_the_existing_deadline(self):
        boundary=Boundary('world-navigation');original=boundary.navigation_source;reads=[0]
        def late():
            if boundary.verb=='open':
                reads[0]+=1
                if reads[0]==3:boundary.clock+=21
            return original()
        boundary.navigation_source=late
        with self.assertRaisesRegex(AssertionError,'checkpoint deadline'):boundary.execute()

    def test_avatar_actual_unavailable_and_loaded_fallback_both_recover(self):
        for fault in ('', 'avatar-native-fallback'):
            with self.subTest(fault=fault):
                boundary=Boundary('avatar-people',fault);boundary.execute()
                samples=boundary.reports[0]['samples']
                failed=next(s['state'] for s in samples if s['phase'].endswith('-avatar-url') and s['state']['requestedAvatar']=='missing')
                self.assertEqual('fallback' if fault else 'unavailable',failed['avatar'])
                self.assertTrue(failed['loadFailed'])
                recovered=next(s['state'] for s in samples if s['phase'].endswith('-avatar-bookmark-choose'))
                self.assertEqual('A',recovered['avatar']);self.assertTrue(recovered['modelLoaded'])
                self.assertFalse(recovered['loadFailed']);self.assertFalse(recovered['wearable'])
                self.assertEqual(1.0,recovered['scale'])
                self.assertEqual(15,len(SCENARIOS['avatar-people']['steps']))

    def test_avatar_missing_original_failure_model_or_bookmark_effect_cannot_pass(self):
        for fault in ('avatar-retains-old-model','avatar-no-failure-event','avatar-wearable-ack-only',
                      'avatar-bookmark-no-reload','avatar-bookmark-leaks-owned-wearable','avatar-bookmark-old-failure'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('avatar-people',fault).execute()

    def test_avatar_independent_model_request_failure_and_dialog_facts_are_required(self):
        boundary=Boundary('avatar-people','product-echo-without-peer',target='avatar-url')
        original=boundary.reduce
        def ignored(verb,data):
            if verb!='avatar-url':original(verb,data)
        boundary.reduce=ignored
        boundary.echo={'avatar':'A','requestedAvatar':'A'}
        with self.assertRaises(AssertionError):boundary.execute()
        from feature_journeys.witness import WITNESS_KEYS
        self.assertEqual(set(SCENARIOS['avatar-people']['baseline']),set(WITNESS_KEYS['avatar-people']))
        from feature_journeys.contract import state
        baseline=SCENARIOS['avatar-people']['baseline']
        for change in ({'modelLoaded':False},{'loadFailed':True},{'avatar':'fallback'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                state('avatar-people',dict(baseline,**change),RUN)

    def test_avatar_wearable_uses_model_companions_and_rejects_legacy_entity_json(self):
        from feature_journeys.fixtures import payload
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
            verb='wearable-add',inputs={'resource':'gltf-bundle/main.gltf'})
        arguments('feature.avatar-people.act',request)
        for resource in ('wearable.json','missing.gltf'):
            with self.subTest(resource=resource),self.assertRaises(ValueError):
                arguments('feature.avatar-people.act',dict(request,inputs={'resource':resource}))
        self.assertIsNone(payload('wearable.json',RUN,TICKET))
        model=json.loads(companion('gltf-bundle/main.gltf'))
        for row in model['buffers']+model['images']:
            self.assertTrue(companion('gltf-bundle/'+row['uri']))

    def test_assets_actual_bundle_paths_fbx_bake_and_file_disappearance(self):
        boundary=Boundary('assets');boundary.execute();samples=boundary.reports[0]['samples']
        ready=next(s['state'] for s in samples if s['phase'].endswith('-set-baking') and s['state']['bakeState']=='ready')
        self.assertTrue(ready['selected'].endswith('/stand.fbx'));self.assertFalse(ready['baking'])
        denied=next(s['state'] for s in samples if s['phase'].endswith('-delete-denied'))
        self.assertFalse(denied['deleteEnabled']);self.assertEqual('none',denied['error']);self.assertEqual(3,len(denied['mappings']))
        renamed=next(s['state'] for s in samples if s['phase'].endswith('-rename-folder'))
        self.assertTrue(all(name.startswith(context(RUN)['renamed']+'/') for name in renamed['mappings']))
        self.assertTrue(renamed['selected'].endswith('/main.gltf'))
        missing=next(s['state'] for s in samples if s['phase'].endswith('-upload-picker-accept-unavailable'))
        self.assertEqual('file-unavailable',missing['error']);self.assertTrue(missing['picker'])
        self.assertEqual([],missing['mappings']);self.assertFalse(missing['stagedAvailable'])
        self.assertEqual(29,len(SCENARIOS['assets']['steps']))

    def test_assets_ignored_effects_invented_ui_errors_and_partial_bundles_cannot_pass(self):
        faults=('assets-flat-name','assets-missing-companion','assets-gltf-baked','assets-rename-breaks-bundle',
                'assets-no-real-bake','assets-disable-unsettled-worker','assets-delete-enabled-when-denied',
                'assets-denied-deletes','assets-invented-permission-error','assets-staged-retirement-ignored',
                'assets-picker-no-file-error','assets-picker-unavailable-publishes')
        for fault in faults:
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('assets',fault).execute()

    def test_assets_all_picker_permission_and_bake_facts_require_an_independent_reader(self):
        from feature_journeys.witness import WITNESS_KEYS
        self.assertEqual(set(SCENARIOS['assets']['baseline']),set(WITNESS_KEYS['assets']))
        from feature_journeys.contract import state
        baseline=SCENARIOS['assets']['baseline']
        for change in ({'baking':True},{'bakeAvailable':True},{'deleteEnabled':True},
                       {'selected':context(RUN)['assetGltf']},{'stagedAvailable':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):state('assets',dict(baseline,**change),RUN)

    def test_lifecycle_editor_pages_have_distinct_text_contexts_and_real_pending_input(self):
        boundary=Boundary('lifecycle-input');boundary.execute();samples=boundary.reports[0]['samples']
        opened=[s['state'] for s in samples if s['phase'].endswith('-open-editor')]
        self.assertEqual({('create',1),('chat',2),('scripts',3)},{(s['editor'],s['generation']) for s in opened})
        self.assertTrue(all(s['text']=='' for s in opened))
        held=next(s['state'] for s in samples if s['phase'].endswith('-hold-editor-input'))
        self.assertEqual(1,held['deferredInputs']);self.assertEqual(context(RUN)['retry'],held['text'])
        retired=next(s['state'] for s in samples if s['phase'].endswith('-deliver-stale-input'))
        self.assertEqual(4,retired['generation']);self.assertEqual('',retired['text'])
        self.assertEqual(1,retired['staleAttempts']);self.assertEqual(0,retired['deferredInputs'])
        cleanup=[s['state'] for s in samples if s['phase']=='cleanup-restored-baseline'][-1]
        self.assertEqual(2,cleanup['worldAttempts']);self.assertEqual(1,cleanup['staleAttempts'])
        self.assertEqual(0,cleanup['generation']);self.assertEqual(0,cleanup['deferredInputs'])
        self.assertEqual(16,len(SCENARIOS['lifecycle-input']['steps']))

    def test_lifecycle_ignored_events_stale_adoption_moving_release_and_wrong_back_cannot_pass(self):
        faults=('life-inherited-editor-text','life-back-only-hides-keyboard','life-hold-ignored',
                'life-context-replacement-ignored','life-stale-input-adopted','life-stale-input-not-released',
                'life-stale-attempt-ignored','life-world-event-not-dispatched','life-release-ignored',
                'life-release-still-moving','life-release-motion-constant-distance','life-restore-ignored')
        for fault in faults:
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('lifecycle-input',fault).execute()

    def test_lifecycle_cleanup_cannot_erase_original_history_or_hide_pending_native_input(self):
        for fault in ('life-cleanup-resets-history','life-cleanup-pending-leak'):
            boundary=Boundary('lifecycle-input',fault)
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):boundary.execute()
            self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

    def test_lifecycle_all_actual_ui_context_and_attempt_fields_are_independently_read(self):
        from feature_journeys.witness import WITNESS_KEYS
        self.assertEqual(set(SCENARIOS['lifecycle-input']['baseline']),set(WITNESS_KEYS['lifecycle-input']))
        from feature_journeys.contract import state
        baseline=SCENARIOS['lifecycle-input']['baseline']
        for change in ({'generation':1},{'text':context(RUN)['unicode']},{'deferredInputs':2},
                       {'worldAttempts':-1},{'staleAttempts':-1},{'positionDelta':{'x':0.0,'y':0.0,'z':1.0}}):
            with self.subTest(change=change),self.assertRaises(ValueError):state('lifecycle-input',dict(baseline,**change),RUN)

    def test_all14_complete_with_independent_boundary_model_and_observed_cleanup(self):
        self.assertEqual(14, len(SCENARIOS))
        for area in SCENARIOS:
            with self.subTest(area=area):
                boundary = Boundary(area)
                phases = boundary.execute()
                self.assertGreaterEqual(len(phases), len([s for s in SCENARIOS[area]['steps'] if 'backends' not in s or 'photos-add-only' in s['backends']]) + 2)
                self.assertTrue(boundary.reports[0]['sequenceCompleted'])
                self.assertTrue(boundary.reports[0]['cleanupSucceeded'])
                self.assertFalse(boundary.reports[0]['deviceAcceptance'])
                self.assertEqual(2, sum(op.endswith('.cleanup') for op,_ in boundary.actions))

    def test_ignored_effectful_actions_fail_in_each_area(self):
        targets = dict(zip(SCENARIOS, ['bookmark-add','login-submit','avatar-url','model-create','play','focus-type',
            'set-resolution','record-start','type','capture','picker-accept','upload','open-editor','focus-type']))
        for area, target in targets.items():
            with self.subTest(area=area):
                boundary = Boundary(area, 'input-ignored', target)
                with self.assertRaises((AssertionError, ValueError)):
                    boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_browser_actual_404_stays_loaded_until_normal_reload_after_server_restore(self):
        boundary=Boundary('world-web');boundary.execute();samples=boundary.reports[0]['samples']
        def last(verb):return next(s for s in reversed(samples) if s['phase'].endswith('-'+verb))
        restored=last('restore-resource')['state']
        self.assertEqual(404,restored['httpStatus']);self.assertEqual('none',restored['error'])
        self.assertEqual(200,last('reload')['state']['httpStatus'])
        self.assertGreater(last('reload')['state']['documentLoads'],restored['documentLoads'])
        self.assertEqual(19,len(SCENARIOS['world-web']['steps']))

    def test_browser_ignored_foreign_send_reload_restore_and_resume_cannot_pass(self):
        for area in ('world-web','tablet-web'):
            for fault in ('web-foreign-attempt-ignored','web-foreign-accepted','web-restore-ignored',
                          'web-restore-forges-navigation','web-resume-old-document'):
                with self.subTest(area=area,fault=fault),self.assertRaises((AssertionError,ValueError)):
                    Boundary(area,fault).execute()
            with self.assertRaises(AssertionError):Boundary(area,'input-ignored','reload').execute()

    def test_browser_forged_primary_document_load_cannot_use_an_old_independent_counter(self):
        boundary=Boundary('world-web','product-echo-without-peer',target='reload')
        original=boundary.reduce
        def ignored(verb,data):
            if verb!='reload':original(verb,data)
            else:boundary.echo={'documentLoads':boundary.state['documentLoads']+1}
        boundary.reduce=ignored
        with self.assertRaises(AssertionError):boundary.execute()

    def test_browser_forged_primary_foreign_attempt_is_not_an_independent_attempt(self):
        boundary=Boundary('world-web','product-echo-without-peer',target='foreign-origin-message')
        boundary.echo={'attemptedMessages':2};original=boundary.reduce
        def ignored(verb,data):
            if verb!='foreign-origin-message':original(verb,data)
        boundary.reduce=ignored
        with self.assertRaises(AssertionError):boundary.execute()

    def test_browser_native_request_acceptance_without_actual_page_echo_is_incomplete(self):
        for area in ('world-web','tablet-web'):
            with self.subTest(area=area),self.assertRaises(AssertionError):Boundary(area,'web-echo-missing').execute()
        boundary=Boundary('world-web','product-echo-without-peer',target='submit');boundary.echo={'bridgeEchoes':1}
        original=boundary.reduce
        def request_only(verb,data):
            original(verb,data)
            if verb=='submit':boundary.state['bridgeEchoes']=0
        boundary.reduce=request_only
        with self.assertRaises(AssertionError):boundary.execute()

    def test_tablet_inline_requires_actual_carrier_and_rejects_retired_or_leaked_callbacks(self):
        for fault in ('web-http-inline','web-inline-lease-leak','web-deferred-leak','web-stale-delivery'):
            with self.subTest(fault=fault),self.assertRaises((AssertionError,ValueError)):
                Boundary('tablet-web',fault).execute()
        boundary=Boundary('tablet-web');boundary.execute()
        self.assertEqual(26,len(SCENARIOS['tablet-web']['steps']))
        held=[s['state'] for s in boundary.reports[0]['samples'] if s['phase'].endswith('-hold-inline-message')]
        self.assertTrue(held);self.assertTrue(all(s['deferredMessages']==1 and s['inlineLeases']==1 for s in held))

    def test_browser_old_draft_version_and_http_inline_inputs_are_rejected(self):
        from feature_journeys.contract import arguments
        base=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/')
        for fields in (dict(base,contractVersion=10,verb='open',inputs={}),
                       dict(base,verb='open-inline-app',inputs={'resource':'inline.html'})):
            with self.assertRaises(ValueError):arguments('feature.tablet-web.act',fields)

    def test_create_picker_is_observed_before_cancel_and_accept_and_rez_retry_is_real(self):
        boundary=Boundary('create');boundary.execute()
        states=[row['state'] for row in boundary.reports[0]['samples']]
        self.assertTrue(any(row['picker'] and row['objects']==[] for row in states))
        self.assertTrue(any(not row['canRez'] and row['error']=='permission-denied' and row['objects']==[] for row in states))
        self.assertTrue(any(row['canRez'] and row['objects']==['cube'] for row in states))
        verbs=[value['verb'] for op,value in boundary.actions if op.endswith('.act')]
        self.assertEqual(2,verbs.count('model-create'));self.assertEqual(2,verbs.count('import-picker-open'))
        for verb in ('import-picker-open','import-picker-cancel','import-picker-accept','create-retry'):
            failed=Boundary('create','input-ignored',verb)
            with self.assertRaises((ValueError,AssertionError)):failed.execute()

    def test_snapshot_v9_executes_all_three_measured_save_profiles_without_fake_storage_permission(self):
        for backend,count in [('photos-add-only',15),('media-store',12),('document-picker',15)]:
            boundary=Boundary('snapshots',snapshot_backend=backend)
            with self.subTest(backend=backend):
                phases=boundary.execute();report=boundary.reports[-1]
                self.assertEqual(count+2,len(phases));self.assertEqual(backend,report['sourceProfile'])
                self.assertTrue(report['sequenceCompleted']);self.assertTrue(report['cleanupSucceeded'])
                verbs=[v['verb'] for operation,v in boundary.actions if operation.endswith('.act')]
                self.assertNotIn('set-storage-permission',verbs);self.assertNotIn('capture-start',verbs)
                self.assertEqual(backend=='photos-add-only','save-denied' in verbs)
                self.assertEqual(backend=='document-picker','save-picker-cancel' in verbs)
                self.assertIn('share-open',verbs);self.assertIn('share-select-owned',verbs)
                self.assertEqual(18-count,len(report['notApplicableSteps']))

    def test_snapshot_original_pending_cancellation_and_real_save_share_receipts_are_mandatory(self):
        for fault in ('snapshot-cancel-ignored','snapshot-cancel-creates-file','snapshot-idle-cancel-proof',
                      'snapshot-permission-ignored','snapshot-permission-clears-error','snapshot-capture-needs-photos',
                      'snapshot-denied-save-commits','snapshot-save-ack-only','snapshot-share-cancel-delivers',
                      'snapshot-share-handoff-only','snapshot-wrong-file-source','snapshot-destination-changed'):
            boundary=Boundary('snapshots',fault)
            with self.subTest(fault=fault),self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertFalse(boundary.reports[-1]['sequenceCompleted'])
            self.assertTrue(boundary.reports[-1]['cleanupSucceeded'])
        boundary=Boundary('snapshots','snapshot-picker-cancel-saves',snapshot_backend='document-picker')
        with self.assertRaises((ValueError,AssertionError)):boundary.execute()
        self.assertFalse(boundary.reports[-1]['sequenceCompleted'])

    def test_snapshot_missing_effects_or_system_sheets_cannot_pass_on_acknowledgments(self):
        for verb in ('capture-cancel','capture','save','share-open','share-select-owned'):
            boundary=Boundary('snapshots','input-ignored',verb)
            with self.subTest(verb=verb),self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertFalse(boundary.reports[-1]['sequenceCompleted'])

    def test_snapshot_unknown_backend_or_unowned_initial_authorization_refuses_before_input(self):
        for backend,permission in [('unsupported','not-required'),('photos-add-only','denied'),('media-store','granted')]:
            boundary=Boundary('snapshots',snapshot_backend=backend);boundary.state['savePermission']=permission
            with self.subTest(backend=backend),self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertFalse(any(op.endswith('.act') for op,_ in boundary.actions))
            self.assertFalse(boundary.reports[-1]['cleanupEnabled'])

    def test_snapshot_system_ui_uses_real_monotonic_settled_counters_without_restarts(self):
        boundary=Boundary('snapshots');original=boundary.reduce
        system={'set-save-permission','save-denied','save','share-open','share-cancel','share-select-owned'}
        def reduce(verb,data):
            original(verb,data)
            if verb in system:
                boundary.lifecycle['backgrounds']+=1;boundary.lifecycle['activations']+=1
        boundary.reduce=reduce;boundary.execute()
        self.assertGreater(boundary.lifecycle['backgrounds'],2)
        self.assertTrue(boundary.reports[-1]['sequenceCompleted'])
        for fault in ('regression','restart'):
            boundary=Boundary('snapshots');original=boundary.reduce
            def reduce(verb,data):
                original(verb,data)
                if verb=='set-save-permission':boundary.lifecycle['backgrounds']+=1;boundary.lifecycle['activations']+=1
                if verb=='share-open':
                    if fault=='regression':boundary.lifecycle['backgrounds']=0
                    else:boundary.lifecycle['launches']+=1
            boundary.reduce=reduce
            with self.subTest(fault=fault),self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertFalse(boundary.reports[-1]['sequenceCompleted'])

    def test_snapshot_backend_is_pinned_and_cleanup_cannot_leak_os_outputs(self):
        boundary=Boundary('snapshots');original=boundary.reduce
        def reduce(verb,data):
            original(verb,data)
            if verb=='share-open':boundary.state.update(saveBackend='media-store',savePermission='not-required')
        boundary.reduce=reduce
        with self.assertRaises((ValueError,AssertionError)):boundary.execute()
        self.assertFalse(boundary.reports[-1]['sequenceCompleted'])
        boundary=Boundary('snapshots');original=boundary.invoke
        def invoke(operation,values):
            result=original(operation,values)
            if operation.endswith('.cleanup'):boundary.state.update(files=1,saved=1)
            return result
        boundary.invoke=invoke
        with self.assertRaises((ValueError,AssertionError)):boundary.execute()
        self.assertFalse(boundary.reports[-1]['cleanupSucceeded'])

    def test_snapshot_v9_rejects_old_capture_permission_inputs_and_private_sink_substitution(self):
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',verb='capture',inputs={'mode':'still','format':'png'})
        self.assertEqual(request,arguments('feature.snapshots.act',request))
        for edit in ({'contractVersion':8},{'verb':'set-storage-permission','inputs':{'state':'denied'}},
                     {'verb':'capture-cancel','inputs':{}},{'verb':'share','inputs':{}}):
            with self.assertRaises(ValueError):arguments('feature.snapshots.act',request|edit)

    def test_create_cancel_side_effect_and_picker_ack_without_entities_fail(self):
        for fault in ('create-on-cancel','picker-ack-only'):
            boundary=Boundary('create',fault)
            with self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertTrue(boundary.reports[0]['cleanupSucceeded'])
            self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_create_primary_permission_error_without_independent_ui_effect_fails(self):
        boundary=Boundary('create','product-echo-without-peer','create-denied')
        original=boundary.reduce;boundary.echo={'error':'permission-denied'}
        boundary.reduce=lambda verb,data:None if verb=='create-denied' else original(verb,data)
        with self.assertRaises(AssertionError):boundary.execute()
        self.assertTrue(boundary.reports[0]['cleanupSucceeded'])

    def test_create_permission_restore_keeps_old_error_until_actual_successful_retry(self):
        for fault in ('permission-invents-ui-clear','retry-retains-error'):
            boundary=Boundary('create',fault)
            with self.assertRaises((ValueError,AssertionError)):boundary.execute()
            self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_create_v8_rejects_old_raw_model_picker_and_version(self):
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',verb='model-create',inputs={'resource':'gltf-bundle/main.gltf'})
        self.assertEqual(request,arguments('feature.create.act',request))
        for edit in ({'contractVersion':7},{'verb':'import-local','inputs':{'resource':'model.gltf'}},
                     {'verb':'import-cancel','inputs':{'resource':'model.gltf'}},
                     {'verb':'import-picker-open','inputs':{'resource':'model.obj'}}):
            with self.assertRaises(ValueError):arguments('feature.create.act',request|edit)

    def test_create_json_fixture_is_owned_input_and_not_an_export_measurement(self):
        from feature_journeys.fixtures import import_document,payload
        origin=f'https://controlled.invalid:4433/feature-fixture/v1/runs/{RUN}/'
        source=import_document(RUN,TICKET,origin)
        self.assertEqual(origin+'tickets/'+TICKET+'/gltf-bundle/main.gltf',source['Entities'][0]['modelURL'])
        self.assertEqual(3,source['DataVersion']);self.assertEqual(0,document(RUN)['DataVersion'])
        self.assertNotIn('textures',source['Entities'][0]);self.assertIsNone(payload('export.json',RUN,TICKET))
        for url in (origin.replace(RUN,'f'*32),'https://user:private@controlled.invalid/feature-fixture/v1/runs/'+RUN+'/',origin+'../'):
            with self.assertRaises(ValueError):import_document(RUN,TICKET,url)

    def test_chat_retyped_resend_distinguishes_local_echo_from_actual_peer_delivery(self):
        boundary=Boundary('chat');boundary.execute()
        samples=boundary.reports[0]['samples']
        offline=[row['state'] for row in samples if not row['state']['mixerConnected'] and row['state']['draft']=='']
        self.assertTrue(any(row['domainMessages'].count(context(RUN)['retry'])==1 and row['peerMessages']==[context(RUN)['unicode']] for row in offline))
        final=next(row['state'] for row in reversed(samples) if row['phase'].endswith('-send'))
        self.assertEqual(2,final['domainMessages'].count(context(RUN)['retry']))
        self.assertEqual(1,final['peerMessages'].count(context(RUN)['retry']))
        quiet=[phase for phase in boundary.reports[0]['phases'] if phase['phase'].endswith('await-no-replay')]
        self.assertEqual(1,len(quiet));self.assertGreaterEqual(quiet[0]['stableSeconds'],3)

    def test_chat_false_filter_distant_input_queued_replay_and_duplicate_delivery_fail(self):
        for fault in ('fake-peer-filter','distant-peer-accepted','offline-delivery','offline-draft-retained',
                      'queued-replay','late-queued-replay','duplicate-peer-delivery'):
            with self.subTest(fault=fault):
                boundary=Boundary('chat',fault)
                with self.assertRaises((AssertionError,ValueError)):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])
                self.assertTrue(boundary.reports[0]['cleanupSucceeded'])

    def test_chat_closed_channel_and_resume_use_actual_absence_history_and_lifecycle(self):
        boundary=Boundary('chat');boundary.execute();samples=boundary.reports[0]['samples']
        self.assertTrue(all(row['state']['channel']=='none' for row in samples if not row['state']['open']))
        phases=[p for p in boundary.reports[0]['phases'] if p['phase'].endswith('background-resume')]
        self.assertEqual(1,len(phases))
        resumed=[r for r in samples if r['phase'].endswith('background-resume')]
        self.assertTrue(resumed);self.assertTrue(all(r['state']['channel']=='domain' and r['state']['domainMessages'] for r in resumed))
        for fault in ('chat-closed-default-channel','background-ignored','chat-resume-loses-history',
                      'chat-resume-default-channel','chat-resume-ghost-keyboard'):
            with self.subTest(fault=fault):
                broken=Boundary('chat',fault)
                with self.assertRaises((AssertionError,ValueError)):broken.execute()
                self.assertFalse(broken.reports[0]['sequenceCompleted'])

    def test_chat_requires_fresh_independent_draft_focus_and_keyboard_facts(self):
        from feature_journeys.witness import WITNESS_KEYS
        self.assertEqual(set(SCENARIOS['chat']['baseline']),set(WITNESS_KEYS['chat']))
        for fault in ('chat-peer-draft','chat-peer-focus','chat-peer-missing-keyboard'):
            with self.subTest(fault=fault):
                broken=Boundary('chat',fault)
                with self.assertRaises((AssertionError,ValueError)):broken.execute()
                self.assertFalse(broken.reports[0]['sequenceCompleted'])

    def test_chat_rejects_invented_filter_error_contract_and_prior_version(self):
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',verb='select-channel',inputs={'channel':'domain'})
        self.assertEqual(request,arguments('feature.chat.act',request))
        for change in ({'contractVersion':9},{'contractVersion':6},{'verb':'filter-peer','inputs':{'enabled':True}},
                       {'verb':'network-disconnect','inputs':{}},{'verb':'back','inputs':{}},
                       {'inputs':{'channel':'peer'}}):
            with self.assertRaises(ValueError):arguments('feature.chat.act',request|change)
        boundary=Boundary('chat');value=boundary.observe({})
        for edit in ({'channel':'peer'},{'channel':'local'},{'channel':'domain'},{'draft':context(RUN)['unicode']},{'messages':['not rendered']},{'keyboard':True}, {'filtered':False}):
            changed=copy.deepcopy(value);changed['state'].update(edit)
            with self.assertRaises(ValueError):result('feature.chat.observe',changed)

    def test_audio_contract_rejects_invented_save_preview_commands_and_old_version(self):
        request = dict(contractVersion=VERSION, runId=RUN, ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/', verb='await-completion', inputs={})
        self.assertEqual(request, arguments('feature.audio.act', request))
        for change in ({'contractVersion':2}, *({'verb':verb} for verb in ('record-stop', 'preview-start', 'preview-stop', 'discard'))):
            with self.subTest(change=change), self.assertRaises(ValueError): arguments('feature.audio.act', request | change)

    def test_audio_completion_needs_whole_native_history_equal_played_frames_and_empty_buffers(self):
        boundary = Boundary('audio'); boundary.reduce('record-start', {}); boundary.reduce('await-completion', {})
        original = boundary.observe({'afterSequence':0})
        for change in ({'history':['completed']}, {'playedFrames':120000}, {'bufferedFrames':1},
                       {'recording':True}, {'preview':True}, {'error':'microphone-muted'}):
            value = copy.deepcopy(original); value['state'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): result('feature.audio.observe', value)
        value = copy.deepcopy(original); value['state']['phase'] = 'playing'
        with self.assertRaises(ValueError): result('feature.audio.observe', value)
        value = copy.deepcopy(original)
        value['state'].update(phase='playing', history=['capturing', 'playing'], preview=True,
                              playedFrames=120000, bufferedFrames=144000)
        self.assertEqual(value, result('feature.audio.observe', value))
        from feature_journeys.engine import matches
        completed = next(step['state'] for step in SCENARIOS['audio']['steps'] if step['verb'] == 'await-completion')
        self.assertFalse(matches(value['state'], completed))

    def test_audio_ignored_cancel_and_automatic_completion_do_not_pass_by_acknowledgment(self):
        for verb in ('record-cancel', 'await-completion'):
            with self.subTest(verb=verb):
                boundary = Boundary('audio', 'input-ignored', verb)
                with self.assertRaises((AssertionError, ValueError)): boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])
                self.assertTrue(boundary.reports[0]['cleanupSucceeded'])

    def test_audio_current_receipt_with_foreign_recording_or_acoustic_bytes_is_rejected(self):
        for kind in ('file', 'audio'):
            with self.subTest(kind=kind):
                boundary = Boundary('audio'); original = boundary.observe
                def observe(fields):
                    value = original(fields)
                    if boundary.state['phase'] == 'completed':
                        for artifact in value['artifacts']:
                            if artifact['kind'] == kind:
                                boundary.files[artifact['name']] = wav_bytes(RUN, TICKET, profile='recorded-preview-v1')
                    return value
                boundary.observe = observe
                with self.assertRaises(AssertionError): boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_emote_native_override_automatic_completion_and_early_restore_are_required(self):
        for fault in ('ordinary-no-override','emote-timer-ignored','late-natural-cancel'):
            with self.subTest(fault=fault):
                boundary=Boundary('emotes',fault)
                with self.assertRaises(AssertionError):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_emote_hidden_chooser_and_retained_chooser_share_effect_checks(self):
        for fault in ('','chooser-hidden'):
            boundary=Boundary('emotes',fault);boundary.execute()
            completions=[request for operation,request in boundary.actions if operation.endswith('.act') and request['verb']=='wait-complete']
            self.assertEqual(9,len(completions));self.assertTrue(all(r['inputs']=={} for r in completions))
            samples=boundary.reports[0]['samples']
            active=[s for s in samples if s['state']['override']]
            self.assertTrue(active)
            if fault:self.assertTrue(any(s['state']['panel'] is False for s in active))
            self.assertTrue(any(s['state']['restoredBeforeNominalEnd'] for s in samples))

    def test_emote_forged_early_restore_disagrees_with_independent_actual_timing(self):
        boundary=Boundary('emotes','late-natural-cancel');boundary.forge_restore_timing=True
        with self.assertRaises(AssertionError):boundary.execute()
        self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_current_emote_contract_rejects_prior_contract_and_accepts_only_closed_no_input_completion(self):
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',verb='wait-complete',inputs={})
        self.assertEqual(request,arguments('feature.emotes.act',request))
        for edit in ({'contractVersion':5},{'contractVersion':4},{'inputs':{'expected':'idle'}},{'inputs':{'restore':True}}):
            with self.assertRaises(ValueError):arguments('feature.emotes.act',request|edit)

    def test_script_mobile_restart_clears_execution_and_explicit_reimport_uses_normal_picker(self):
        boundary=Boundary('scripts');boundary.execute()
        steps=SCENARIOS['scripts']['steps'];index=next(n for n,step in enumerate(steps) if step['verb']=='restart-app')
        self.assertEqual(19,len(steps))
        self.assertEqual(['open','picker-open','picker-cancel','picker-open','picker-accept','stop-owned','load-url','close'],
                         [step['verb'] for step in steps[index+1:]])
        label=f'{index+1:02d}-restart-app';report=boundary.reports[0]
        phase=next(row for row in report['phases'] if row['phase']==label)
        self.assertGreaterEqual(phase['stableSeconds'],3)
        samples=[row['state'] for row in report['samples'] if row['phase']==label]
        self.assertTrue(samples)
        self.assertTrue(all(row==dict(running=[],effects=0,companions=[],picker=False,error='none',open=False) for row in samples))
        accepts=[request['inputs']['resource'] for operation,request in boundary.actions
                 if operation.endswith('.act') and request['verb']=='picker-accept']
        self.assertEqual(['script.js','script-bundle/main.js','script-bundle/main.js'],accepts)
        self.assertTrue(report['sequenceCompleted'])

    def test_script_restart_cannot_inherit_old_execution_effects_or_editor(self):
        for fault in ('restart-ignored','script-restart-keeps-running','script-restart-residual-effect',
                      'script-restart-keeps-editor','script-restart-forged-absence'):
            with self.subTest(fault=fault):
                boundary=Boundary('scripts',fault)
                with self.assertRaises(AssertionError):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_script_restart_retains_actual_mobile_stop_and_start_visibility_counts(self):
        boundary=Boundary('scripts');original=boundary.invoke
        def invoke(operation,fields):
            value=original(operation,fields)
            if operation.endswith('.act') and fields['verb']=='restart-app':
                boundary.lifecycle['backgrounds']+=1;boundary.lifecycle['activations']+=2
            return value
        boundary.invoke=invoke;boundary.execute()
        samples=[row for row in boundary.reports[0]['samples'] if row['phase']=='11-restart-app']
        self.assertTrue(samples)
        self.assertTrue(all(row['lifecycle']==dict(backgrounds=1,activations=4,launches=2) for row in samples))
        self.assertTrue(boundary.reports[0]['sequenceCompleted'])

    def test_script_restart_rejects_missing_launch_activation_regression_and_unsettled_visibility(self):
        for fault in ('launch','activation','regression','unsettled'):
            boundary=Boundary('scripts');original=boundary.invoke;observations=[0]
            def invoke(operation,fields):
                value=original(operation,fields)
                if operation.endswith('.observe') and boundary.verb=='restart-app':
                    observations[0]+=1
                    if fault=='launch':value['lifecycle']['launches']-=1
                    elif fault=='activation':value['lifecycle']['activations']-=1
                    elif fault=='regression':value['lifecycle']['activations']+=2 if observations[0]==1 else 0
                    else:value['lifecycle']['backgrounds']+=observations[0]
                return value
            boundary.invoke=invoke
            with self.subTest(fault=fault),self.assertRaises(AssertionError):boundary.execute()
            self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_script_restart_late_execution_is_rejected_before_any_reopen_input(self):
        boundary=Boundary('scripts','script-restart-late-replay')
        with self.assertRaisesRegex(AssertionError,'11-restart-app'):boundary.execute()
        actions=[request['verb'] for operation,request in boundary.actions if operation.endswith('.act')]
        self.assertEqual(1,actions.count('open'));self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_script_reimport_and_cancel_after_restart_require_real_independent_effects(self):
        for fault in ('script-reimport-ignored','script-restart-cancel-executes','script-peer-open',
                      'script-peer-picker','script-peer-error','script-peer-missing-picker'):
            with self.subTest(fault=fault):
                boundary=Boundary('scripts',fault)
                with self.assertRaises((AssertionError,ValueError)):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_script_picker_cancellation_and_real_companion_resolution_are_observed(self):
        for fault in ('execution-on-cancel', 'missing-relative-companion'):
            with self.subTest(fault=fault):
                boundary = Boundary('scripts')
                reduce = boundary.reduce
                def faulty(verb, data):
                    reduce(verb, data)
                    if verb == 'picker-cancel' and fault == 'execution-on-cancel':
                        boundary.state.update(running=['owned-script'], effects=4, companions=['companion.js'])
                    elif verb == 'picker-accept' and fault == 'missing-relative-companion':
                        boundary.state['companions'] = []
                boundary.reduce = faulty
                with self.assertRaises(AssertionError): boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_current_script_contract_rejects_old_consent_flow_and_prior_observations(self):
        request = dict(contractVersion=VERSION, runId=RUN, ticket=TICKET,
            fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/', verb='picker-open', inputs={})
        self.assertEqual(request, arguments('feature.scripts.act', request))
        for changed in ({'contractVersion':1}, {'contractVersion':2}, {'contractVersion':15}, {'verb':'consent-accept'}, {'verb':'load-folder', 'inputs':{'resource':'script-bundle'}}):
            with self.assertRaises(ValueError): arguments('feature.scripts.act', request | changed)
        boundary = Boundary('scripts'); sample = boundary.observe({'afterSequence':0})
        for prior in (1,15):
            sample['contractVersion'] = prior
            with self.assertRaises(ValueError): result('feature.scripts.observe', sample)

    def test_graphics_measures_nondefault_original_state_and_restores_it_without_sending_it(self):
        boundary=Boundary('graphics')
        boundary.state.update(resolution=0.65,renderScale=0.65,haze=True,hazePass=True,mirror=True,mirrorPass=True)
        original=copy.deepcopy(boundary.state);boundary.execute()
        self.assertEqual(original,boundary.state)
        self.assertEqual(original,next(s['state'] for s in boundary.reports[0]['samples']
                                     if s['phase']=='original-baseline-candidate'))
        for operation,request in boundary.actions:
            if operation.endswith('.act'):
                self.assertNotIn('initial',request);self.assertNotIn('expected',request)
                if request['verb']=='restore-original':self.assertEqual({},request['inputs'])

    def test_graphics_ignored_settings_and_native_settings_without_render_effects_fail(self):
        for verb in ('set-resolution','set-haze','set-mirrors'):
            with self.subTest(verb=verb):
                boundary=Boundary('graphics','input-ignored',verb)
                with self.assertRaises((AssertionError,ValueError)):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])
        for verb,field in (('set-resolution','renderScale'),('set-haze','hazePass'),('set-mirrors','mirrorPass')):
            with self.subTest(render=field):
                boundary=Boundary('graphics');original=boundary.reduce
                def settings_only(action,data):
                    measured=boundary.state[field];original(action,data)
                    if action==verb:boundary.state[field]=measured
                boundary.reduce=settings_only
                with self.assertRaises(AssertionError):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_graphics_close_and_restart_must_retain_immediately_changed_preferences(self):
        for action in ('close','restart-app'):
            with self.subTest(action=action):
                boundary=Boundary('graphics');original=boundary.reduce
                def lose_preferences(verb,data):
                    original(verb,data)
                    if verb==action:boundary.state.update(resolution=0.7,renderScale=0.7,haze=False,hazePass=False)
                boundary.reduce=lose_preferences
                with self.assertRaises(AssertionError):boundary.execute()
                self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_graphics_cleanup_cannot_substitute_default_preferences_for_actual_originals(self):
        boundary=Boundary('graphics');boundary.state.update(resolution=0.65,renderScale=0.65)
        original=boundary.invoke
        def wrong_restore(operation,request):
            value=original(operation,request)
            if operation.endswith('.cleanup'):boundary.state.update(resolution=0.6,renderScale=0.6)
            return value
        boundary.invoke=wrong_restore
        with self.assertRaises(AssertionError):boundary.execute()
        self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

    def test_graphics_unverified_or_foreign_open_baseline_cannot_enable_inputs(self):
        for fault in ('witness-disagreement','already-open'):
            with self.subTest(fault=fault):
                boundary=Boundary('graphics')
                if fault=='already-open':boundary.state['dialog']=True
                else:
                    original=boundary.observe
                    def forged(request):
                        value=original(request);value['state']['resolution']=0.7;return value
                    boundary.observe=forged
                with self.assertRaises(AssertionError):boundary.execute()
                self.assertFalse(any(op.endswith('.act') for op,_ in boundary.actions))
                self.assertFalse(boundary.reports[0]['cleanupEnabled'])

    def test_graphics_v4_rejects_fictitious_transactions_and_prior_semantics(self):
        from feature_journeys.scenarios import actions
        self.assertTrue({'preview-preset','apply','cancel','set-shadows'}.isdisjoint(actions('graphics')))
        request=dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,
            fixtureUrl='http://controlled.test/feature-fixture/v1/runs/'+RUN+'/',verb='set-resolution',inputs={'value':0.5})
        for version in (1,2,3):
            with self.assertRaises(ValueError):arguments('feature.graphics.act',request | {'contractVersion':version})

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
        request=dict(contractVersion=VERSION, runId=RUN, ticket=TICKET, fixtureUrl=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
                     verb='set-resolution',inputs={'value':0.5})
        op='feature.graphics.act'
        self.assertEqual(request,validate_operation_arguments(op,request))
        for change in ({'expected':{'renderScale':0.5}},{'contractVersion':1},{'verb':'unknown'},
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
        for change in ('geometry','source','owner','empty','foreign-extra','wrong-texture-slot','wrong-data-version','null-entity'):
            candidate=copy.deepcopy(good)
            if change=='geometry': candidate['Entities'][0]['dimensions']['x']=99
            elif change=='source': candidate['Entities'][0]['modelURL']='http://foreign.test/mesh.gltf'
            elif change=='owner': candidate['Entities'][0]['name']='someone-else'
            elif change=='empty': candidate['Entities']=[]
            elif change=='null-entity':candidate['Entities']=[None]
            elif change=='wrong-data-version':candidate['DataVersion']=3
            elif change=='wrong-texture-slot':candidate['Entities'][0]['textures']={'not-the-rendered-slot':next(iter(candidate['Entities'][0]['textures'].values()))}
            else: candidate['Entities'].append(copy.deepcopy(candidate['Entities'][0]))
            with self.subTest(change=change),self.assertRaises(AssertionError):
                file_observation(json.dumps(candidate).encode(),'create',RUN,TICKET,POLICY,fixture_url,TICKET)
        with self.assertRaises(AssertionError):
            file_observation(b'wrong mapping','assets',RUN,TICKET,POLICY)

    def test_create_export_rejects_duplicate_json_fields_and_accepts_actual_texture_json_string(self):
        from feature_journeys.evidence import file_observation
        value=document(RUN,model_ticket=TICKET)
        value['Entities'][0]['textures']=json.dumps(value['Entities'][0]['textures'])
        file_observation(json.dumps(value).encode(),'create',RUN,TICKET,POLICY,model_ticket=TICKET)
        for raw in (json.dumps(value).replace('"DataVersion": 0','"DataVersion": 3, "DataVersion": 0').encode(),
                    json.dumps({**value,'Entities':[{**value['Entities'][0],'textures':'{"checker.png":"foreign","checker.png":"'+document(RUN,model_ticket=TICKET)['Entities'][0]['textures']['checker.png']+'"}'}]}).encode()):
            with self.assertRaises(AssertionError):file_observation(raw,'create',RUN,TICKET,POLICY,model_ticket=TICKET)

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
            if area=='scripts': self.assertIn('05-picker-accept',str(error.exception))

    def test_auth_view_close_preserves_pending_and_real_restart_retires_its_consumer(self):
        boundary=Boundary('authentication');boundary.execute()
        self.assertEqual(4,boundary.lifecycle['launches'])
        samples=boundary.reports[0]['samples']
        self.assertTrue(any(s['state']['pending'] and not s['state']['dialog'] for s in samples))
        self.assertTrue(any(s['state']['pending'] and s['state']['dialog'] for s in samples))
        self.assertTrue(any(s['state']['delayedGrantOutstanding'] and s['state']['principal']=='anonymous' for s in samples))

    def test_auth_fake_network_cancel_missing_valid_old_grant_and_adopted_response_fail(self):
        for fault in ('cancel-invents-network-abort','delayed-grant-not-issued','old-response-adopted'):
            with self.subTest(fault=fault),self.assertRaises(AssertionError):Boundary('authentication',fault).execute()

    def test_auth_primary_error_echo_without_actual_independent_ui_error_cannot_pass(self):
        boundary=Boundary('authentication','product-echo-without-peer',target='login-submit')
        boundary.echo={'error':'invalid-credentials'};original=boundary.reduce
        def no_input(verb,data):
            if not (verb=='login-submit' and data['account']=='invalid'):original(verb,data)
        boundary.reduce=no_input
        with self.assertRaises(AssertionError):boundary.execute()
        self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_auth_startup_prompt_variant_is_closed_through_the_same_normal_action(self):
        Boundary('authentication','startup-login-open').execute()

    def test_auth_backend_revocation_is_separate_from_native_logout_and_required_for_cleanup(self):
        boundary=Boundary('authentication','backend-revocation-ignored')
        with self.assertRaises(AssertionError):boundary.execute()
        self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

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
        saved=json.loads((DEVICE/'feature_journeys/adapter-contract.v16.json').read_text())
        self.assertEqual(inventory(),saved)
        matrix=json.loads((DEVICE/'feature_journeys/coverage.v16.json').read_text())
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
