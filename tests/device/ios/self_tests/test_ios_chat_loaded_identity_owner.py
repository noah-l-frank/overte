"""Actual Draft/JS/IPA originals; diagnostic Qt/load producers remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.chat_controls import IOSChatIO
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters import qt_image_bytes
from ios.self_tests import test_ios_chat_draft_owner as draft_fixture
from ios.self_tests import test_ios_qt_image_bytes as image_fixture
from ios.self_tests.chat_loaded_identity_owner_fixture import LoadedIdentityModel


class ChatLoadedIdentityOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f = draft_fixture.ChatDraftOwnerTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        images = image_fixture.QtImageBytesTests(); self.addCleanup(images.doCleanups)
        self.ipa, self.installed, sha, image = images.prepare()
        self.binding = dict(self.installed.scope, processIdentity='42'); self.artifact = (self.ipa.path, sha)
        self.m = LoadedIdentityModel(self, image); self.run = draft_fixture.RUN

    def bind_images(self, value):
        original = deepcopy(self.installed.binding.record())
        bound = qt_image_bytes.bind_many(self.installed.binding,
            [value['qtEntryImage'], value['qtDependencyEntryImage']], *self.artifact)
        self.assertEqual(original, self.installed.binding.record())
        return dict(bindingOriginal=original, entryBindings=bound)

    @contextmanager
    def owner(self):
        model = self.m
        with self.f.lock.held():
            roots, code = model.code_readers()
            owner = IOSChatDraftOwner(self.f.store, self.f.root, self.binding, self.run, self.f.lock, model.guard,
                native=model.native_reader(), io=IOSChatIO(SimpleNamespace(capture=model.capture, native=model)), view=model.view_reader(),
                phase=PhaseFixtureReader(model.client(), self.run, 'chat', epoch_ms=model.epoch, monotonic=lambda: model.widgets.clock),
                epoch_ms=model.epoch, monotonic=lambda: model.widgets.clock, sleep=model.sleep,
                source_bound=True, code_sources=code, code_roots=roots, qml_bound=True,
                qml_sources=model.qml_reader(), qml_artifact=self.artifact, qml_images=self.bind_images)
            model.owner = owner; yield owner

    @contextmanager
    def archive(self, **options):
        with self.f.lock.held():
            yield IOSChatDraftOwner.archive(self.f.store, self.f.root, self.binding, self.run, self.f.lock,
                self.m.owner.fixture_url, source_bound=True, qml_bound=True,
                qml_artifact=options.get('artifact', self.artifact))

    def action(self, verb, inputs=None, *, same=False):
        if not same: self.m.add_phase(verb, inputs or {}, format(len(self.m.activations) + 1, '032x'))
        with self.owner() as owner: return owner.act(self.m.ticket, self.m.verb, self.m.inputs)

    def census(self):
        output = {}
        for path in self.f.root.iterdir():
            if path.is_file():
                stat = path.lstat(); output[path.name] = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, path.read_bytes())
        return output

    def test_normal_production_script_send_cached_reopen_and_pure_original_ipa_archive(self):
        self.action('open'); self.action('type', dict(text=context(self.run)['unicode'])); self.action('send')
        self.action('close'); self.action('open'); self.action('close')
        calls = deepcopy(self.m.widgets.calls); queries = deepcopy(self.m.qml_queries); files = self.census()
        with patch.object(PrivateFeatureState, 'write', side_effect=AssertionError('No historical writes')), self.archive() as owner:
            self.assertEqual(8, owner.version); self.assertIsNone(owner.peer_receipts)
            raws = [owner.original(ref)['originals'] for ref in owner.state['records']]
            sources = [raw['qmlSources'] for raw in raws if raw['qmlSources'] is not None]
            self.assertTrue(sources); self.assertEqual(1, len({source['source']['objectId'] for source in sources}))
            self.assertEqual(1, len({raw['view']['loadedObjectIdentity']['objectLinks']['links'][0]['rootIdentity']
                for raw in raws if raw['view']['loadedObjectIdentity']['objectLinks']['links']}))
            self.assertEqual(1, len(raws[-1]['view']['source']['storage']['events']))
            self.assertIsNone(raws[-1]['qmlSources']); self.assertEqual([], raws[-1]['qmlEntryBindings'])
            for raw in raws:
                self.assertNotIn('peerReceipt', raw)
                for bound in raw['qmlEntryBindings']:
                    self.assertTrue(bound['imageBytesBound']); self.assertFalse(bound['qtSdkSourceAvailable'])
                    self.assertFalse(bound['importGraphAvailable']); self.assertFalse(bound['aotGraphAvailable'])
        self.assertEqual(files, self.census()); self.assertEqual(calls, self.m.widgets.calls); self.assertEqual(queries, self.m.qml_queries)
        self.assertEqual(1, self.m.command('read')['sent'])

    def test_existing_runtime_factory_registers_scope_and_journals_actual_qml_queries_before_send(self):
        from ios.adapters import chat_draft_runtime as runtime_module
        from adapters.native_script_roots import FILE as ROOTS_FILE
        model=self.m;selector='declared-host-primary'
        adapter=SimpleNamespace(state_path=lambda selected:self.f.store.path.with_name('session.json'),
            _candidate_guard=model.guard,_binding=lambda *_args:None,_session_recreation_forbidden=False,
            _chat_qml_owner_artifact=lambda selected:self.artifact,
            _chat_qml_owner_image_originals=lambda selected,value:self.bind_images(value))
        runtime=runtime_module.IOSChatDraftRuntime(adapter)
        roots,code=model.code_readers()
        observer=SimpleNamespace(remote='Documents/feature-native-observation.json',
            send=lambda query:model.send_roots(query),
            original=lambda *,remote,limit:model.roots_raw,
            chat_view=lambda *,loaded_object_identity:model.view_reader(),
            chat_script_sources=lambda *,clock_source:code,
            chat_qml_sources=lambda *,clock_source:model.qml_reader())
        self.assertTrue(ROOTS_FILE.endswith('.json'))
        source=dict(clock_source=model.native_reader(),native=model,binding=self.binding,check=model.guard,
            observer=observer,native_clock=model.native_epoch)
        runtime._sources=lambda selected:source
        runtime._existing=lambda selected:(None,'declared-existing-session',{},None,deepcopy(self.binding))
        # Only declared source clocks are selected before the first capture.
        # No actual SDK/process/session or native callback is claimed here.
        def query(command):
            if command['action']=='normal-ui-input':model.observe_intent(command)
            if command['action'] in ('normal-ui-input','feature-chat-view-observe'):model.command('read',apply=True)
        model.query=query
        actual_phase=PhaseFixtureReader
        times=SimpleNamespace(monotonic=lambda:model.widgets.clock,sleep=model.sleep,time=lambda:model.epoch()/1000)
        phase=lambda client,run,area:actual_phase(client,run,area,epoch_ms=model.epoch,monotonic=lambda:model.widgets.clock)
        with patch.object(runtime_module,'time',times),patch.object(runtime_module,'PhaseFixtureReader',side_effect=phase):
            with runtime.draft_owner(selector,self.run,self.f.root,model.client(),source_bound=True,qml_bound=True) as owner:
                model.owner=owner;owner.act(model.ticket,model.verb,model.inputs)
                self.assertEqual(8,owner.version)
                frame=owner.original(owner.state['records'][-1])
                self.assertTrue(any(query['action']=='feature-ios-chat-qml-sources' for query in frame['queries']))
                self.assertTrue(any(query['schemaVersion']==2 and query['action']=='feature-chat-view-observe' for query in frame['queries']))
                raw=frame['originals'];self.assertEqual(raw['qmlSources']['source']['objectId'],raw['view']['loadedObjectIdentity']['objectLinks']['links'][0]['atRead']['objectId'])
        self.assertFalse(adapter._session_recreation_forbidden);self.assertFalse(hasattr(model,'observe_intent'))
        scope=PrivateFeatureState(self.f.store.path.with_name('ios-chat-scope.json')).read()
        self.assertEqual(self.binding,scope['binding']);self.assertEqual(str(self.f.root),scope['artifactRoot'])

    def test_same_url_and_source_hash_foreign_loaded_object_refuses_before_next_normal_input(self):
        self.action('open'); calls = deepcopy(self.m.widgets.calls)
        self.m.qml_fault = lambda value: value['source'].update(objectId='0' * 32)
        with self.assertRaises((NativeUIError, ValueError)): self.action('type', dict(text=context(self.run)['unicode']))
        self.assertEqual(calls, self.m.widgets.calls)

    def test_replaced_weak_root_or_incomplete_census_cannot_reuse_old_code_association(self):
        self.action('open'); calls = deepcopy(self.m.widgets.calls)
        for fault in ('weak', 'incomplete', 'wrong-census'):
            def mutate(value):
                cut = value['loadedObjectIdentity']; owned = value['source']['rootOwnership']
                if fault == 'weak': owned['roots'][0]['weakAlive'] = False
                elif fault == 'incomplete': owned['complete'] = False
                else: cut['objectLinks']['rootSourceInstance'] = '0' * 32
            self.m.cut_fault = mutate
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, ValueError)):
                self.action('type', dict(text=context(self.run)['unicode']))
            self.assertEqual(calls, self.m.widgets.calls)

    def test_lost_passive_qml_return_retains_query_and_uses_a_fresh_read_without_replaying_input(self):
        self.action('open'); calls = deepcopy(self.m.widgets.calls); self.m.lose_qml_return = True
        with self.assertRaises((NativeUIError, ValueError)): self.action('type', dict(text=context(self.run)['unicode']))
        lost = deepcopy(self.m.qml_queries[-1]); self.assertEqual(calls, self.m.widgets.calls)
        self.m.lose_qml_return = False; self.action('type', same=True)
        with self.owner() as owner: self.assertTrue(any(lost in row['queries'] for row in owner.state['interrupted']))
        identifiers = [query['commandId'] for query in self.m.qml_queries]
        self.assertEqual(len(identifiers), len(set(identifiers))); self.assertEqual(1, sum(call[0] == 'chat.input' and call[1] == 'replace' for call in self.m.widgets.calls))

    def test_lost_normal_send_reopens_actual_source_and_never_delivers_twice(self):
        self.action('open'); self.action('type', dict(text=context(self.run)['unicode'])); self.m.lose_send = True
        with self.assertRaises((NativeUIError, ValueError)): self.action('send')
        calls = deepcopy(self.m.widgets.calls); self.m.lose_send = False; self.action('send', same=True)
        self.assertEqual(calls, self.m.widgets.calls); self.assertEqual(1, self.m.command('read')['sent'])

    def test_historical_selected_ipa_and_second_entry_cannot_be_replaced_by_saved_success_flags(self):
        self.action('open'); files = self.census()
        with self.archive() as owner:
            ref = next(ref for ref in owner.state['records'] if owner.original(ref)['originals']['qmlSources'] is not None)
            value = deepcopy(owner.original(ref)); raw = value['originals']
            raw['qmlSources']['qtDependencyEntryImage']['symbolFileOffset'] = '512'
            raw['qmlEntryBindings'][1]['original']['symbolFileOffset'] = '512'
            value['clockJoin']['originalsSha256'] = digest(raw)
            with self.assertRaises((NativeUIError, ValueError)): owner.frame(value)
        self.ipa.path.write_bytes(self.ipa.path.read_bytes() + b'changed selected IPA')
        with self.assertRaises((NativeUIError, ValueError)), self.archive(): pass
        self.assertEqual(files, self.census())

    def test_actual_frame_same_bytes_inode_replacement_cannot_replace_original_owner(self):
        self.action('open');calls=deepcopy(self.m.widgets.calls)
        with self.archive() as owner:
            ref=owner.state['records'][-1];path=owner.frames.path(owner.frames.expand(ref));body=path.read_bytes();original=path.stat().st_ino
            preserved=path.with_name('preserved-original-'+path.name);path.rename(preserved)
            path.write_bytes(body);path.chmod(0o600)
            self.assertNotEqual(original,path.stat().st_ino);self.assertEqual(body,path.read_bytes());self.assertEqual(body,preserved.read_bytes())
            with self.assertRaises((NativeUIError,ValueError)):owner.original(ref)
        self.assertEqual(calls,self.m.widgets.calls)

    def test_actual_frame_same_inode_changed_bytes_cannot_hide_in_historical_qml_originals(self):
        self.action('open');calls=deepcopy(self.m.widgets.calls)
        with self.archive() as owner:
            ref=owner.state['records'][-1];path=owner.frames.path(owner.frames.expand(ref));body=path.read_bytes();original=path.stat().st_ino
            preserved=path.with_name('preserved-before-byte-negative-'+path.name);preserved.write_bytes(body);preserved.chmod(0o600)
            with path.open('ab') as stream:stream.write(b' ')
            self.assertEqual(original,path.stat().st_ino);self.assertEqual(body,preserved.read_bytes())
            with self.assertRaises((NativeUIError,ValueError)):owner.original(ref)
        self.assertEqual(calls,self.m.widgets.calls)

    def test_old_weak_read_interval_after_original_load_cannot_replace_actual_capture_reads(self):
        from adapters.chat_root_loaded_identity import validate as cut_original,match
        self.action('open');calls=deepcopy(self.m.widgets.calls);queries=deepcopy(self.m.qml_queries)
        with self.archive() as owner:
            ref=next(ref for ref in reversed(owner.state['records']) if owner.original(ref)['originals']['qmlSources'] is not None)
            value=deepcopy(owner.original(ref));raw=value['originals'];loaded=raw['qmlSources']['source']
            clock={key:loaded['loadCompleted'][key]+1 for key in ('epochMs','monotonicMs')}
            self.assertLess(clock['epochMs'],value['clockJoin']['nativeBefore']['capturedEpochMs'])
            for row in raw['view']['loadedObjectIdentity']['objectLinks']['links']:
                for name in ('atWalk','atRead'):
                    row[name]['readBefore']=deepcopy(clock);row[name]['readAfter']=deepcopy(clock)
            # The old shape/birth checks still accept the unchanged same object,
            # and the real frame digest is recomputed: only capture admission
            # must reject these historical reads as newly acquired originals.
            cut=raw['view']['loadedObjectIdentity']
            cut_original(cut,raw['view']['source']['rootOwnership'],pid=42,captured=raw['view']['capturedEpochMs'])
            match(cut,loaded);value['clockJoin']['originalsSha256']=digest(raw)
            with self.assertRaises((NativeUIError,ValueError)):owner.frame(value)
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(queries,self.m.qml_queries)

    def test_profile8_is_explicit_and_old_source_bound_archive_cannot_adopt_it(self):
        self.assertEqual(3, IOSChatDraftOwner.read_version(None))
        self.assertEqual(4, IOSChatDraftOwner.read_version(None, source_bound=True))
        self.action('open'); files = self.census()
        with self.f.lock.held(), self.assertRaises((NativeUIError, ValueError)):
            IOSChatDraftOwner.archive(self.f.store, self.f.root, self.binding, self.run, self.f.lock,
                self.m.owner.fixture_url, source_bound=True)
        for options in (dict(qml_bound=True), dict(source_bound=True, qml_bound=True, peer_actor=True),
                dict(source_bound=True, qml_bound=True, peer_receipts=True)):
            with self.subTest(options=options), self.assertRaises((NativeUIError, ValueError)): IOSChatDraftOwner.read_version(None, **options)
        self.assertEqual(files, self.census())


if __name__ == '__main__': unittest.main()
