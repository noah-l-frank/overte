"""One-send normal missing-name/OK inputs with independently owned originals.

The original 404/modal proof is retained before dismissal. Delivery, hidden
widgets, and scheduled deletion cannot replace actual OK and lifetime drainage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from urllib.parse import urlsplit

from adapters.native_clock_join import NativeClockAcquisition, digest, validate_join
from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI, NativeUIError
from adapters.script_feature.history import pack, unpack, same
from feature_journeys.contract import arguments
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import validate_status
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path
from ios.adapters.navigation_observation_owner import fixture_original
from ios.adapters.navigation_surface_actions import _SurfaceUI
from ios.adapters.normal_input import NativeInput, observation
from ios.adapters.normal_navigation import IOSNavigation, PROFILE
from ios.adapters.graphics_history import follow_native
from ios.adapters import navigation_error_state as errors, navigation_dialog_controls as controls, navigation_ui

VERSION = 1


class _LookupNative:
    def __init__(self, owner): self.owner = owner
    def capture(self): return self.owner.capture()
    def edit(self, operation, text):
        owner = self.owner
        need(operation == 'replace' and text == 'hifi://'+context(owner.run)['hidden'])
        owner.input_intent('QT', 'address.field', dict(operation=operation, text=text))
        return owner.native.edit(operation, text)


class NavigationMissingActions:
    def __init__(self, store, admission, ui, native, *, epoch_ms=lambda:time.time()*1000,
                 monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and isinstance(admission, (NavigationAdmissionOwner,NavigationProcessScope))
             and not admission.historical and isinstance(ui, NativeUI) and isinstance(native, NativeInput)
             and callable(epoch_ms) and callable(monotonic)
             and store.path == owner_path(admission,'ios-navigation-missing-actions.json'))
        self.store, self.admission, self.ui, self.native = store, admission, ui, native
        self.binding, self.run, self.lock = admission.binding, admission.run, admission.lock
        need(native.session == self.binding['sessionId'])
        self.epoch_ms, self.monotonic = epoch_ms, monotonic
        self.started = self.last_clock = self.active = None
        self.lock.assert_held(); self.previous = store.read()
        self.state = None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self, state):
        return dict(iosNavigationMissingActionsVersion=VERSION, binding=self.binding, runId=self.run, payload=pack([state]))

    def call(self, value, verb):
        arguments('feature.world-navigation.act', value)
        need(value['runId'] == self.run and value['fixtureUrl'] == self.admission.fixture.fixture_url and value['verb'] == verb)
        return value

    def decode(self, value):
        exact(value, {'iosNavigationMissingActionsVersion','binding','runId','payload'})
        rows = unpack(value['payload']); need(type(value['iosNavigationMissingActionsVersion']) is int
            and value['iosNavigationMissingActionsVersion'] == VERSION and len(rows) == 1 and same(value,self.envelope(rows[0])))
        state = rows[0]; exact(state, {'missing','dismiss','component','admission','frames','proof','cleared'})
        need(type(state['component']) is dict and set(state['component']) <= {'iosNormalNavigation'}
             and type(state['frames']) is list and len(state['frames']) <= 32)
        previous_ui = None
        for key, verb in (('missing','navigate-missing'),('dismiss','dismiss-error')):
            row = state[key]
            if row is None: need(key == 'dismiss'); continue
            exact(row, {'call','phase','fixture','intents','returnedUi'})
            self.call(row['call'],verb); need(row['phase'] in ('checking','issued','delivered')
                and type(row['intents']) is list and len(row['intents']) <= 32)
            if row['fixture'] is not None:
                fixture_original(row['fixture'],self.run,self.admission.fixture.inputs,self.admission.fixture.instance)
                if row['phase'] != 'checking': need(row['fixture']['ticket'] == row['call']['ticket']
                    and row['fixture']['verb'] == verb and row['fixture']['inputs'] == {})
            if row['phase'] != 'checking': need(row['fixture'] is not None)
            for intent in row['intents']:
                exact(intent, {'method','path','body','original'})
                self.packet(intent['original'])
                if previous_ui is not None: self.follow_ui(previous_ui,intent['original'])
                previous_ui = intent['original']
                need(intent['method'] in ('POST','DELETE','QT','ERROR-OK'))
                if intent['method'] == 'QT': need(intent['path'] == 'address.field'
                    and intent['body'] == dict(operation='replace',text='hifi://'+context(self.run)['hidden']))
                elif intent['method'] == 'ERROR-OK':
                    need(intent['path'] == 'navigation.error.ok' and same(intent['body'],controls.reference(controls.project(intent['original']))))
            if row['phase'] == 'delivered': need(row['intents'] and row['returnedUi'] is not None)
            else: need(row['returnedUi'] is None)
            if row['returnedUi'] is not None:
                self.packet(row['returnedUi'])
                if previous_ui is not None: self.follow_ui(previous_ui,row['returnedUi'])
                previous_ui = row['returnedUi']
        previous = None
        for index, frame in enumerate(state['frames']):
            exact(frame, {'kind','hostBarrier','provider','nativeStart','originals','nativeEnd','clockJoin'})
            need(frame['kind'] in ('baseline','missing','dismiss','cleared') and number(frame['hostBarrier'],1,1e15)
                 and type(frame['originals']) is dict and set(frame['originals']) <= errors.ORIGINALS
                 and (index == len(state['frames'])-1 or frame['clockJoin'] is not None))
            if frame['clockJoin'] is not None:
                self.validate_frame(frame,previous,state); previous = frame
        if state['admission'] is not None:
            first = state['frames'][0]; need(first['kind'] == 'baseline' and first['clockJoin'] is not None)
            need(same(state['admission'],self.lookup_admission(state,first)))
        if state['proof'] is not None:
            errors.validate_proof(state['proof'],self.binding,self.run)
            need(same(state['proof']['admission'],state['admission']))
            need(any(frame['kind'] == 'missing' and same(frame['originals'],state['proof']['originals'])
                     and same(frame['clockJoin'],state['proof']['clockJoin']) for frame in state['frames']))
        if state['dismiss'] is not None: need(state['proof'] is not None)
        if state['cleared'] is not None:
            need(state['proof'] is not None and state['dismiss'] is not None)
            need(state['cleared']['fields']['error'] == 'none' and state['cleared']['ownedDialogDrained'] is True)
            frame = state['frames'][-1]; need(frame['kind'] == 'cleared' and frame['clockJoin'] is not None)
            measured = errors.compose(self.run,self.binding,frame['originals'],frame['clockJoin'],missing=state['proof'])
            need(same(measured,state['cleared']))
        return state

    def packet(self, value):
        if isinstance(self.admission,NavigationProcessScope):self.admission.ui_original(value)
        observation(value,int(self.binding['processIdentity']),value.get('sampleEpochMs'))
        original = self.admission.archive()['originals']['ui']
        need(value['instance'] == original['instance'] and value['lastSequence'] >= original['lastSequence']
             and value['sampleEpochMs'] >= original['sampleEpochMs'])
        return value

    @staticmethod
    def follow_ui(before,after):
        need(before['instance'] == after['instance'] and before['processId'] == after['processId']
             and before['lastSequence'] <= after['lastSequence'] and before['elapsedMs'] <= after['elapsedMs']
             and before['sampleEpochMs'] <= after['sampleEpochMs']
             and before['navigationDialogSourceSequence'] < after['navigationDialogSourceSequence'])

    def bound(self):
        self.admission.bound(); need(same(self.store.read(),self.previous))
        now = self.monotonic(); need(number(now,0,1e15) and (self.last_clock is None or now >= self.last_clock))
        self.last_clock = now
        if self.started is not None: need(now-self.started < 30)
        return now

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value,self.previous); need(same(self.store.read(),value)); self.previous = deepcopy(value); self.bound()

    def capture(self):
        self.bound(); value = self.native.capture(); self.packet(value); self.bound(); return value

    def input_intent(self, method, path, body):
        self.bound(); need(self.active in ('missing','dismiss'))
        row = self.state[self.active]; need(row['phase'] == 'issued' and len(row['intents']) < 32)
        row['intents'].append(dict(method=method,path=path,body=deepcopy(body),original=self.capture())); self.save()

    def validate_frame(self, frame, previous=None, state=None):
        state = self.state if state is None else state
        clock = validate_join(frame['clockJoin'],frame['originals'])
        need(same(frame['nativeStart'],{key:clock[key] for key in
            ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
            and same(frame['nativeEnd'],{key:clock[key] for key in
            ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        errors.validate_originals(self.run,self.binding,frame['originals'],clock)
        validate_status(frame['provider'],instance=self.admission.fixture.instance,run=self.run,inputs=self.admission.fixture.inputs)
        owner = 'missing' if frame['kind'] in ('baseline','missing') else 'dismiss'
        need(frame['provider']['active'] and state[owner] is not None and frame['provider']['ticket'] == state[owner]['call']['ticket'])
        if previous is not None:
            follow_native(previous['clockJoin']['nativeAfter'],clock['nativeBefore'])
            errors.continuation(frame['originals'],previous['originals'],self.run,int(self.binding['processIdentity']),clock['nativeAfter']['capturedEpochMs'])
        else:
            proof = self.admission.archive(); follow_native(proof['clockJoin']['nativeAfter'],clock['nativeBefore'])
            errors.continuation(frame['originals'],proof['originals'],self.run,int(self.binding['processIdentity']),clock['nativeAfter']['capturedEpochMs'])
        return frame

    def frame(self, kind):
        self.bound(); frames = self.state['frames']
        need(len(frames) < 32 and (not frames or frames[-1]['clockJoin'] is not None))
        row = dict(kind=kind,hostBarrier=self.epoch_ms(),provider=None,nativeStart=None,originals={},nativeEnd=None,clockJoin=None)
        frames.append(row); self.save()
        row['provider'] = self.admission.fixture.status(); self.save()
        window = NativeClockAcquisition(self.admission.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(row['hostBarrier']); row['nativeStart'] = deepcopy(window.started); self.save()
        for name in ('dialogs','replies','ui'):
            reader = self.admission.sources[name]
            row['originals'][name] = reader.capture() if name == 'ui' else reader.read(self.run); self.save()
        row['nativeEnd'] = dict(nativeAfter=self.admission.native.read(self.admission.native.sequence),
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic()); self.save()
        row['clockJoin'] = dict(window.started,**row['nativeEnd'],originalsSha256=digest(row['originals']),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in row['originals'].items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]); self.save()
        self.validate_frame(row,frames[-2] if len(frames)>1 else None); return row

    def lookup_admission(self, state, frame):
        source = urlsplit(self.admission.fixture.inputs['sceneUrl'])
        return dict(runId=self.run,ticket=state['missing']['call']['ticket'],inputs=deepcopy(self.admission.fixture.inputs),
            origin=source.scheme+'://'+source.netloc,nativeAfterEpochMs=frame['clockJoin']['nativeAfter']['capturedEpochMs'],
            providerAfterEpochMs=frame['provider']['capturedEpochMs'],afterEvent=0)

    def action(self, call, key, verb):
        call = deepcopy(self.call(call,verb)); self.bound(); need(self.started is None)
        if self.state is not None and self.state[key] is not None:
            old = self.state[key]; need(old['phase'] == 'delivered' and same(old['call'],call)); return False
        self.started = self.bound(); self.active = key
        if self.state is None: self.state = dict(missing=None,dismiss=None,component={},admission=None,frames=[],proof=None,cleared=None)
        self.state[key] = dict(call=call,phase='checking',fixture=None,intents=[],returnedUi=None); self.save()
        row = self.state[key]; row['fixture'] = self.admission.fixture.read(); self.save()
        need(row['fixture']['ticket'] == call['ticket'] and row['fixture']['verb'] == verb and row['fixture']['inputs'] == {})
        return True

    def navigate(self, call):
        try:
            if not self.action(call,'missing','navigate-missing'): return {'performed':True}
            frame = self.frame('baseline'); originals = frame['originals']
            errors.compose(self.run,self.binding,originals,frame['clockJoin'])
            need(not originals['ui']['tabletShown'] and not navigation_ui.project(originals['ui'])['addressDialog'])
            self.state['admission'] = self.lookup_admission(self.state,frame); self.save()
            row = self.state['missing']; row['phase'] = 'issued'; self.save()
            flow = IOSNavigation(_SurfaceUI(self),_LookupNative(self),
                dict(contractVersion=1,profile=PROFILE,sceneUrl=self.admission.fixture.inputs['sceneUrl']),self.state['component'],self.save)
            flow.open_address(); flow.ui.click(flow.address)
            flow.native.edit('replace','hifi://'+context(self.run)['hidden'])
            flow.ui.click(flow.go); flow.ui.wait_absent(flow.address); flow.mark('addressOwned',False)
            row.update(phase='delivered',returnedUi=self.capture()); self.save(); return {'performed':True}
        finally: self.active = self.started = None

    def observe_missing(self):
        self.bound(); need(self.state is not None and self.state['admission'] is not None
            and self.state['missing']['phase'] in ('issued','delivered') and self.state['dismiss'] is None)
        if self.state['proof'] is not None: return deepcopy(self.state['proof'])
        frame = self.frame('missing'); originals = frame['originals']
        # A complete no-error frame can be read again. Foreign/partial error
        # ownership fails validation rather than becoming a pending success.
        if not originals['dialogs']['events'] and not originals['replies']['events']:
            errors.compose(self.run,self.binding,originals,frame['clockJoin']); return None
        proof = errors.missing_proof(self.binding,originals,frame['clockJoin'],frame['provider'],self.state['admission'])
        self.state['proof'] = proof; self.save(); return deepcopy(proof)

    def recover_missing(self):
        """Recover a fully retained lost proof result without any source read."""
        self.bound(); need(self.state is not None and self.state['proof'] is None and self.state['dismiss'] is None
            and self.state['admission'] is not None and self.state['frames'])
        frame = self.state['frames'][-1]; need(frame['kind'] == 'missing' and frame['clockJoin'] is not None)
        proof = errors.missing_proof(self.binding,frame['originals'],frame['clockJoin'],frame['provider'],self.state['admission'])
        self.state['proof'] = proof; self.save(); return deepcopy(proof)

    def dismiss(self, call):
        self.bound(); need(self.state is not None and self.state['proof'] is not None)
        try:
            if not self.action(call,'dismiss','dismiss-error'): return {'performed':True}
            frame = self.frame('dismiss'); originals = frame['originals']
            current = errors.compose(self.run,self.binding,originals,frame['clockJoin'],missing=self.state['proof'])
            need(current['fields']['error'] == 'not-found')
            reference = controls.join_observation(controls.project(originals['ui']),originals['dialogs'],self.state['proof']['joined']['dialogId'])
            row = self.state['dismiss']; row['phase'] = 'issued'; self.save()
            # Retain the exact source reference before normal pointer delivery.
            row['intents'].append(dict(method='ERROR-OK',path='navigation.error.ok',body=deepcopy(reference),original=deepcopy(originals['ui']))); self.save()
            self.native.navigation_error_input(reference=reference)
            row.update(phase='delivered',returnedUi=self.capture()); self.save(); return {'performed':True}
        finally: self.active = self.started = None

    def observe_cleared(self):
        self.bound(); need(self.state is not None and self.state['dismiss'] is not None
            and self.state['dismiss']['phase'] in ('issued','delivered'))
        if self.state['cleared'] is not None: return deepcopy(self.state['cleared'])
        frame = self.frame('cleared')
        current = errors.compose(self.run,self.binding,frame['originals'],frame['clockJoin'],missing=self.state['proof'])
        if current['ownedDialogDrained'] is not True: return None
        # This is modal/listener drainage only. A still open address editor is
        # retained and must be closed by its ordinary original-root owner.
        self.state['cleared'] = current; self.save(); return deepcopy(current)
