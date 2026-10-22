"""Original source joins on synthetic native/QML/peer seams, without devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.samples import ChatSamples, compose
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack, unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.fixtures import context
from self_tests.test_native_chat_observation import Boundary, RUN, BINDING, SELF, PEER
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_pico_chat_keyboard import boundary as view_boundary, keyboard

TICKET = 'b' * 32


class ChatSamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.chmod(0o700)
        (self.root / 'peer').mkdir(mode=0o700)
        self.store = PrivateFeatureState(self.root / 'chat-primary.json')
        self.primary, self.peer = Boundary(), Boundary()
        self.primary.present = self.peer.present = True
        self.primary.opened = self.peer.opened = 20000
        self.peer_mixer = 'd' * 64
        def peer_source(value):
            value.update(instance='e' * 32, processId=456)
            value['source'].update(selfSha256=PEER, mixerSha256=self.peer_mixer if self.peer.mixer else '')
        self.peer.mutate = peer_source
        self.view = view_boundary(False); self.ui_template = deepcopy(self.view.source['ui'])
        self.view.source.update(ui={'present': False}, editorFocused=False, editorHasDraft=False)
        self.view.source['storage'].update(kind='unset', count=0, unowned=0, events=[])
        self.native = NativeBoundary(); self.clock = 0
        self.peer_binding = BINDING | dict(processIdentity='456', targetFingerprint='d' * 64)
        self.primary_lock = ScriptSourceLock(self.root / 'script-sources.lock')
        self.peer_lock = ScriptSourceLock(self.root / 'peer/script-sources.lock')
        self.samples = self.sampler()

    def sampler(self, *, role='primary', store=None):
        peer = self.peer.reader(); peer.pid = 456
        return ChatSamples(RUN, role, BINDING, self.peer_binding, self.primary.reader(), peer,
            self.view.reader(vr=True), self.native.reader(), store or self.store,
            self.primary_lock, self.peer_lock, vr=True, component_only=True, monotonic=lambda: self.clock)

    def read(self): return self.samples.read(TICKET, 20000)

    def open(self, channel='local', text=''):
        stored = self.view.source['storage']['events']
        local = [row['text'] for row in stored if row['channel'] == 'local']
        domain = [row['text'] for row in stored if row['channel'] == 'domain']
        self.view.source['ui'] = self.ui_template | dict(channel=channel, draft=text, keyboardRequested=bool(text),
            localMessages=local, domainMessages=domain, localRowCount=len(local), domainRowCount=len(domain),
            visibleMessages=local if channel == 'local' else domain, visibleRowCount=len(local if channel == 'local' else domain))
        self.view.source.update(editorFocused=bool(text), editorHasDraft=bool(text), keyboard=keyboard(bool(text)))

    def accept(self, text, *, sender=PEER, channel='domain', local=False):
        self.primary.event(text=text, sender=sender, channel=channel, local=local)
        storage = self.view.source['storage']; storage.update(kind='array', count=storage['count'] + 1)
        storage['events'].append(dict(channel=channel, text=text, timestamp=20000))
        if self.view.source['ui']['present']: self.open(self.view.source['ui']['channel'])

    def close(self):
        self.view.source.update(ui={'present': False}, editorFocused=False, editorHasDraft=False, keyboard=keyboard(False))

    def test_closed_open_typed_and_actual_remote_deliveries_use_distinct_original_sources(self):
        self.assertEqual(dict(draft='', messages=[], localMessages=[], domainMessages=[], peerMessages=[],
            channel='none', mixerConnected=True, focused=False, keyboard=False, open=False), self.read()['state'])
        self.open('domain', context(RUN)['unicode']); self.assertTrue(self.read()['state']['keyboard'])
        self.accept(context(RUN)['unicode'], sender=SELF); self.peer.event(sender=SELF)
        self.accept(context(RUN)['reply'])
        value = self.read()
        self.assertEqual([context(RUN)['unicode'], context(RUN)['reply']], value['state']['domainMessages'])
        self.assertEqual([context(RUN)['unicode']], value['state']['peerMessages'])
        self.close(); value = self.read()['state']
        self.assertFalse(value['open']); self.assertEqual([], value['messages'])
        self.assertEqual([context(RUN)['unicode'], context(RUN)['reply']], value['domainMessages'])
        for boundary in (self.primary, self.peer): self.assertTrue(all(c['operation'] == 'inspect' for c in boundary.commands))
        self.assertTrue(self.store.path.exists()); self.assertEqual(0, self.store.path.stat().st_mode & 0o177)

    def test_hidden_channel_and_rejected_local_packets_never_synthesize_visible_or_accepted_history(self):
        self.open(); self.accept(context(RUN)['hidden'])
        self.primary.event(text=context(RUN)['hidden'], sender=PEER, channel='local')
        value = self.read()['state']
        self.assertEqual([], value['messages']); self.assertEqual([], value['localMessages'])
        self.assertEqual([context(RUN)['hidden']], value['domainMessages'])
        self.assertEqual(2, len(self.samples.frames[-1]['primary']['source']['events']))

    def test_offline_echo_explicit_second_send_and_remote_order_multiplicity_are_preserved(self):
        self.read(); self.open('domain')
        self.primary.mixer = self.peer.mixer = False; self.read()
        self.accept(context(RUN)['retry'], sender=SELF, local=True)
        value = self.read()['state']; self.assertEqual([], value['peerMessages'])
        self.assertEqual([context(RUN)['retry']], value['domainMessages']); self.assertFalse(value['mixerConnected'])
        self.primary.mixer = self.peer.mixer = True; self.peer_mixer = 'f' * 64
        self.primary.mutate = lambda v: v['source'].update(mixerSha256='f' * 64)
        self.assertEqual([], self.read()['state']['peerMessages'])
        self.assertEqual([], self.read()['state']['peerMessages'])  # Reads cannot replay an offline input.
        self.accept(context(RUN)['retry'], sender=SELF)
        self.peer.event(sender=SELF, text=context(RUN)['retry'])
        self.peer.event(sender=SELF, text=context(RUN)['reply'], local=True)
        self.peer.event(sender=PEER, text=context(RUN)['reply'])
        self.peer.event(sender='f' * 64, text=context(RUN)['reply'])
        value = self.read()['state']
        self.assertEqual([context(RUN)['retry']] * 2, value['domainMessages'])
        self.assertEqual([context(RUN)['retry']], value['peerMessages'])

    def test_storage_and_visible_model_cannot_replace_missing_native_arrivals(self):
        self.read(); self.open('domain'); self.accept(context(RUN)['unicode'])
        self.primary.events = []
        with self.assertRaises(NativeUIError): self.read()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_wrong_view_binding_private_content_or_changed_config_remains_failure(self):
        for mutation in ('visible', 'local', 'count', 'unowned', 'config'):
            with self.subTest(mutation=mutation):
                self.setUp(); self.read(); self.open('domain'); self.accept(context(RUN)['unicode'])
                if mutation == 'visible': self.view.source['ui'].update(visibleMessages=[], visibleRowCount=0)
                elif mutation == 'local': self.view.source['ui'].update(localMessages=[context(RUN)['unicode']], localRowCount=1)
                elif mutation == 'count': self.view.source['ui']['domainRowCount'] = 2
                elif mutation == 'unowned': self.view.source['storage'].update(unowned=1, count=2)
                else: self.view.source['storage']['configSha256'] = 'f' * 64
                with self.assertRaises(NativeUIError): self.read()

    def test_old_mixer_reappearance_foreign_replacement_and_half_outage_fail(self):
        for fault in ('old-reappearance', 'unwitnessed', 'half'):
            with self.subTest(fault=fault):
                self.setUp(); self.read()
                if fault == 'half': self.peer.mixer = False
                elif fault == 'old-reappearance':
                    self.primary.mixer = self.peer.mixer = False; self.read()
                    self.primary.mixer = self.peer.mixer = True
                else:
                    self.peer_mixer = 'f' * 64
                    self.primary.mutate = lambda v: v['source'].update(mixerSha256='f' * 64)
                with self.assertRaises(NativeUIError): self.read()

    def test_reconstruction_restores_original_cursors_without_reading_then_acquires_new_sources(self):
        self.read(); before = [len(source.commands) for source in (self.primary, self.peer, self.view, self.native)]
        self.samples = self.sampler()
        self.assertEqual(before, [len(source.commands) for source in (self.primary, self.peer, self.view, self.native)])
        self.read()
        self.assertEqual([count + 1 for count in before], [len(source.commands) for source in (self.primary, self.peer, self.view, self.native)])
        self.assertEqual(2, len(unpack(self.store.read()['transcript'])))

    def test_interrupted_acquisition_is_never_replaced_by_stored_samples_or_new_object(self):
        self.read(); self.peer.ignored = True
        with self.assertRaises(NativeUIError): self.read()
        before = len(self.peer.commands)
        self.assertEqual('reading', self.store.read()['phase'])
        with self.assertRaises(NativeUIError): self.sampler()
        with self.assertRaises(NativeUIError): self.read()
        self.assertEqual(before, len(self.peer.commands))

    def test_failed_intent_write_blocks_all_source_dispatch(self):
        def failed(*args): raise NativeUIError('journal unavailable')
        self.store.write = failed
        with self.assertRaises(NativeUIError): self.read()
        self.assertFalse(any(source.commands for source in (self.primary, self.peer, self.view, self.native)))

    def test_role_or_candidate_replacement_and_rewritten_historical_queries_fail_before_live_read(self):
        self.read()
        with self.assertRaises(NativeUIError): self.sampler(role='actor')
        self.read(); state = self.store.read(); frames = unpack(state['transcript'])
        frames[-1]['peer']['commandId'] = frames[0]['peer']['commandId']
        self.store.write(state | dict(transcript=pack(frames)), state)
        with self.assertRaises(NativeUIError): self.sampler()

    def test_independent_roles_acquire_distinct_queries_and_keep_separate_private_transcripts(self):
        self.read(); actor_store = PrivateFeatureState(self.root / 'chat-actor.json')
        actor = self.sampler(role='actor', store=actor_store); actor.read(TICKET, 20000)
        for key in ('primary', 'peer', 'view'):
            self.assertNotEqual(self.samples.frames[-1][key]['commandId'], actor.frames[-1][key]['commandId'])
        self.assertEqual(self.samples.frames[-1]['peer']['source'], actor.frames[-1]['peer']['source'])
        self.assertTrue(self.store.path.exists()); self.assertTrue(actor_store.path.exists())

    def test_measured_lifecycle_advances_and_acquisition_age_cannot_be_retimed(self):
        self.read()
        self.native.mutate = lambda v: v['lifecycle'].update(backgrounds=1, activations=2)
        self.assertEqual(dict(backgrounds=1, activations=2, launches=1), self.read()['lifecycle'])
        original = self.peer.send
        def slow(request): original(request); self.clock += 1.6
        self.samples.peer.send = slow
        with self.assertRaises(NativeUIError): self.read()
        self.assertEqual('reading', self.store.read()['phase'])


if __name__ == '__main__': unittest.main()
