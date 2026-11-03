"""Physical/cache policy counterexamples; no native/feature success is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib,tempfile,unittest,os
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import record,scope
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import emote_rooted_live as rooted
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
from ios.adapters.emote_callback_live_records import CallbackLiveRecords
from ios.adapters import emote_callback_live_records as record_policy
from ios.adapters.emote_archive_round import validation_batch


class CallbackLivePolicySmokeTests(unittest.TestCase):
    def test_actual_reviewed_parser_policy_supports_literal_admission_before_graph_work(self):
        history=CallbackLiveRecords()
        self.assertTrue(history.literal(),repr(history.unsupported_members()))
        self.assertEqual({},history.cache.rows)


class CallbackLiveHistoricalRowsTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.temporary=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.root=Path(self.temporary);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.stack.enter_context(self.lock.held())
        self.file=self.root/'actual-historical-input.json';self.file.write_bytes(b'{"historical":"one"}');self.file.chmod(0o600)
        self.reference=dict(index=1,sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.history=CallbackLiveRecords();self.assertTrue(self.history.literal(),repr(self.history.unsupported));self.calls=0
        self.owner=self.owner_shell()
    def owner_shell(self):
        # Explicit cache/controller MODEL. This is not a native record or
        # claimed feature measurement; actual cache, locks/files/censuses run.
        owner=object.__new__(IOSEmoteCallbackLive);owner._historical_rows=self.history
        owner.root=self.root;owner.run='a'*32;owner.role='primary';owner.lock=owner.primary_lock=self.lock
        owner.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,sessionId='cache-model',generation=1,targetFingerprint='c'*64,processIdentity='42')
        owner.primary_binding=dict(owner.binding);owner.fixture_url='http://127.0.0.1';owner.phase_instance='d'*32
        owner.policy=dict(source='world-render-target');owner.store=PrivateFeatureState(self.root/'model-live.json')
        owner.originals=OriginalFrameStore(self.root,owner.binding,owner.run,owner.role,owner.file_guard,owner.intent,
            namespace='emote-rooted-live',schema_prefix='iosEmoteRootedLive',kind='inputs')
        return owner
    def decode_model(self):
        self.calls+=1;rooted.sha(self.reference['sha256'])
        if rooted.LIMIT!=96:raise NativeUIError('Declared policy change reached literal decoder')
        record(self.file);raw=self.file.read_bytes()
        return dict(reference=dict(self.reference),mechanismOnlyOriginalBytes=raw.decode('ascii'))
    def read(self,owner=None):return self.history.read(self.owner if owner is None else owner,self.reference,self.decode_model)
    def test_cold_twice_then_reconstructed_owner_warm_keeps_original_bytes_and_actual_read_membership(self):
        with scope(fresh=True) as first:original=self.read()
        self.assertEqual(2,self.calls);self.assertEqual({self.file},first)
        before=self.history.cache.signatures({self.file});other=self.owner_shell()
        with scope(fresh=True) as second:again=self.read(other)
        self.assertEqual(original,again);self.assertEqual(2,self.calls);self.assertEqual(first,second)
        self.assertEqual(before,self.history.cache.signatures({self.file}))
    def test_samebyte_inode_replacement_cannot_reuse_previous_original(self):
        self.read();before=self.file.stat().st_ino;other=self.root/'declared-samebyte-replacement.json'
        other.write_bytes(self.file.read_bytes());other.chmod(0o600);os.replace(other,self.file)
        self.assertNotEqual(before,self.file.stat().st_ino)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,self.calls)
    def test_changed_original_body_cannot_reuse_previous_original(self):
        self.read();self.file.write_bytes(b'{"historical":"changed"}')
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,self.calls)
    def test_replaced_parser_function_forces_actual_literal_refusal(self):
        self.read()
        def refuse(value):raise NativeUIError('Declared changed parser')
        with patch.object(rooted,'sha',refuse),self.assertRaisesRegex(NativeUIError,'Declared changed parser'):self.read()
        self.assertEqual(3,self.calls)
    def test_replaced_parser_code_forces_actual_literal_refusal(self):
        self.read();before=rooted.sha.__code__
        self.assertTrue(any(value is before for value in self.history.references))
        def refuse(value):raise RuntimeError('Declared changed parser code')
        rooted.sha.__code__=refuse.__code__
        try:
            with self.assertRaisesRegex(RuntimeError,'Declared changed parser code'):self.read()
        finally:rooted.sha.__code__=before
        self.assertEqual(3,self.calls)
    def test_changed_policy_constant_forces_actual_literal_refusal(self):
        self.read()
        with patch.object(rooted,'LIMIT',97),self.assertRaisesRegex(NativeUIError,'Declared policy change'):self.read()
        self.assertEqual(3,self.calls)
    def test_complete_outer_immutable_inventory_rejects_inserted_orphan_during_historical_read(self):
        self.read()
        with self.assertRaises(NativeUIError):
            with validation_batch(dict(artifactRoot=str(self.root),stateRoot=str(self.root)),lock=self.lock,primary_lock=self.lock):
                orphan=self.root/'emote-rooted-live-frame-inputs-declared-orphan.json';orphan.write_text('{}');orphan.chmod(0o600)
                self.read()
    def test_changed_actual_owner_context_cannot_borrow_cached_role(self):
        self.read();other=self.owner_shell();other.role='actor'
        with self.assertRaises(NativeUIError):self.read(other)
        self.assertEqual(2,self.calls);self.assertEqual(1,len(self.history.cache.rows))
    def test_unsupported_parser_namespace_value_uses_literal_decoder_instead_of_cached_success(self):
        self.read()
        with patch.object(rooted,'declared_unsupported_policy',object(),create=True):self.read()
        self.assertEqual(3,self.calls)

    def test_changed_own_helper_policy_constant_forces_literal_decoder(self):
        self.read()
        with patch.object(record_policy,'PARSER_MODULES',record_policy.PARSER_MODULES+('declared-different-policy',)):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls)
    def test_changed_own_helper_parser_code_forces_literal_decoder(self):
        self.read();before=record_policy._token.__code__
        self.assertTrue(any(value is before for value in self.history.references))
        def refuse(value,refs,active,depth=0):raise _Unsupported
        record_policy._token.__code__=refuse.__code__
        try:
            self.assertFalse(self.history.literal());self.read()
        finally:record_policy._token.__code__=before
        self.assertEqual(3,self.calls)

    def test_foreign_original_codec_cannot_borrow_warm_owner_row(self):
        self.read();self.owner.originals=OriginalFrameStore(self.root,self.owner.binding,'b'*32,'actor',
            self.owner.file_guard,self.owner.intent,namespace='emote-rooted-live',schema_prefix='iosEmoteRootedLive',kind='inputs')
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,self.calls)
    def test_replaced_original_codec_guard_cannot_borrow_warm_owner_row(self):
        self.read();self.owner.originals.guard=lambda:True
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,self.calls)

    def test_changed_actual_partial_keyword_policy_cannot_reuse_warm_history(self):
        from functools import partial
        from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples
        compose=IOSEmoteCallbackSamples.ImageCompose;self.assertIs(type(compose),partial)
        self.assertEqual({'callback_only':True},compose.keywords);self.read()
        with patch.dict(compose.keywords,{'callback_only':False}):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_changed_actual_socket_timeout_singleton_binding_cannot_reuse_warm_history(self):
        import socket
        from urllib.request import urlopen
        original=socket._GLOBAL_DEFAULT_TIMEOUT
        self.assertIs(type(original),object);self.assertIs(urlopen.__defaults__[-1],original)
        self.assertTrue(any(value is original for value in self.history.references));self.read()
        with patch.object(socket,'_GLOBAL_DEFAULT_TIMEOUT',object()):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_changed_actual_integer_profile_policy_cannot_reuse_warm_history(self):
        from ios.adapters.normal_input import PLACES_PROFILES
        from ios.adapters.places_controls import PROFILES
        self.assertIs(PLACES_PROFILES,PROFILES);self.assertEqual({1:'qt-places-qml-v1',2:'qt-places-qml-v2'},PROFILES)
        self.read()
        with patch.dict(PROFILES,{1:'declared-different-profile'}):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_unsupported_actual_profile_mapping_object_key_uses_literal_decoder(self):
        from ios.adapters.normal_input import PLACES_PROFILES
        self.read()
        with patch.dict(PLACES_PROFILES,{object():'declared-unsupported-key'}):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_changed_actual_integer_version_set_cannot_reuse_warm_history(self):
        from ios.adapters import web_closures
        self.assertEqual({1,2,3,4,5},web_closures.READS);self.read()
        with patch.object(web_closures,'READS',web_closures.READS|{99}):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_unsupported_actual_version_set_object_member_uses_literal_decoder(self):
        from ios.adapters import web_closures
        self.read()
        with patch.object(web_closures,'READS',web_closures.READS|{object()}):
            self.assertFalse(self.history.literal());self.read()
            diagnostics=self.history.unsupported_members()
            self.assertIn(dict(module='ios.adapters.web_closures',member='READS',type=('builtins','object'),reason='set-member'),diagnostics)
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_changed_actual_immutable_source_metadata_bytes_binding_cannot_reuse_warm_history(self):
        from ios.adapters import world_web_keys
        metadata=world_web_keys._ORIGINAL_SOURCE_METADATA
        self.assertIs(type(metadata),tuple);self.assertEqual(2,len(metadata));self.assertIs(type(metadata[0]),tuple)
        self.assertIs(type(metadata[1]),bytes);self.read()
        with patch.object(world_web_keys,'_ORIGINAL_SOURCE_METADATA',(metadata[0],metadata[1]+b'changed')):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_mutable_bytearray_source_metadata_remains_unsupported_and_uses_literal_decoder(self):
        from ios.adapters import world_web_keys
        self.read()
        metadata=world_web_keys._ORIGINAL_SOURCE_METADATA;self.assertIs(type(metadata[1]),bytes)
        with patch.object(world_web_keys,'_ORIGINAL_SOURCE_METADATA',(metadata[0],bytearray(metadata[1]))):
            self.assertFalse(self.history.literal());self.read()
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())

    def test_actual_json_default_scanner_binding_change_cannot_borrow_warm_parsed_value(self):
        import json
        def parse():
            self.calls+=1;record(self.file);return json.loads(self.file.read_text())
        first=self.history.read(self.owner,self.reference,parse);self.assertEqual({'historical':'one'},first)
        self.assertEqual(2,self.calls)
        def changed(text,index):return {'declared':'changed-actual-json-parser'},len(text)
        with patch.object(json._default_decoder,'scan_once',new=changed):
            self.assertFalse(self.history.literal());actual=self.history.read(self.owner,self.reference,parse)
            self.assertEqual({'declared':'changed-actual-json-parser'},actual)
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
        self.assertEqual(first,self.history.read(self.owner,self.reference,parse));self.assertEqual(3,self.calls)

    def test_same_png_parser_function_code_change_cannot_borrow_warm_original_pixels(self):
        from PIL import Image,PngImagePlugin
        self.file=self.root/'actual-decoder-original.png';Image.new('RGBA',(2,2),(20,30,40,255)).save(self.file)
        self.file.chmod(0o600)
        with Image.open(self.file) as image:image.load()
        self.history=CallbackLiveRecords();self.owner._historical_rows=self.history
        self.assertTrue(self.history.literal(),repr(self.history.unsupported_members()))
        def parse():
            self.calls+=1;record(self.file)
            with Image.open(self.file) as image:image.load();return image.tobytes().hex()
        first=self.history.read(self.owner,self.reference,parse);self.assertEqual(2,self.calls)
        function=PngImagePlugin.PngImageFile._open;code=function.__code__
        def changed(self):raise RuntimeError('Declared changed actual PNG parser code')
        function.__code__=changed.__code__
        try:
            self.assertIs(PngImagePlugin.PngImageFile._open,function);self.assertFalse(self.history.literal())
            with self.assertRaisesRegex(RuntimeError,'Declared changed actual PNG parser code'):self.history.read(self.owner,self.reference,parse)
        finally:function.__code__=code
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
        self.assertEqual(first,self.history.read(self.owner,self.reference,parse));self.assertEqual(3,self.calls)

    def test_actual_image_stat_cached_property_code_change_cannot_borrow_warm_measurement(self):
        from PIL import Image,ImageStat
        self.file=self.root/'actual-stat-original.png';Image.new('L',(2,2),20).save(self.file);self.file.chmod(0o600)
        with Image.open(self.file) as image:image.load()
        self.history=CallbackLiveRecords();self.owner._historical_rows=self.history
        self.assertTrue(self.history.literal(),repr(self.history.unsupported_members()))
        def parse():
            self.calls+=1;record(self.file)
            with Image.open(self.file) as image:return ImageStat.Stat(image).mean
        first=self.history.read(self.owner,self.reference,parse);self.assertEqual([20.0],first);self.assertEqual(2,self.calls)
        descriptor=vars(ImageStat.Stat)['mean'];function=descriptor.func;code=function.__code__
        def changed(self):return [-123.0]
        function.__code__=changed.__code__
        try:
            self.assertIs(vars(ImageStat.Stat)['mean'].func,function);self.assertFalse(self.history.literal())
            self.assertEqual([-123.0],self.history.read(self.owner,self.reference,parse))
        finally:function.__code__=code
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
        self.assertEqual(first,self.history.read(self.owner,self.reference,parse));self.assertEqual(3,self.calls)

    def test_actual_raw_encoder_registry_change_cannot_borrow_warm_original_pixels(self):
        from PIL import Image
        self.file=self.root/'actual-encoder-original.png';Image.new('RGBA',(2,2),(20,30,40,255)).save(self.file);self.file.chmod(0o600)
        with Image.open(self.file) as image:image.load()
        self.history=CallbackLiveRecords();self.owner._historical_rows=self.history
        self.assertTrue(self.history.literal(),repr(self.history.unsupported_members()))
        def parse():
            self.calls+=1;record(self.file)
            with Image.open(self.file) as image:image.load();return image.tobytes().hex()
        first=self.history.read(self.owner,self.reference,parse);self.assertEqual(2,self.calls)
        def changed(*args):raise RuntimeError('Declared changed actual raw encoder dispatch')
        with patch.dict(Image.ENCODERS,{'raw':changed}):
            self.assertFalse(self.history.literal())
            with self.assertRaisesRegex(RuntimeError,'Declared changed actual raw encoder dispatch'):self.history.read(self.owner,self.reference,parse)
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
        self.assertEqual(first,self.history.read(self.owner,self.reference,parse));self.assertEqual(3,self.calls)

    def test_actual_json_regex_default_receiver_change_cannot_borrow_warm_parse(self):
        import json,re
        def parse():
            self.calls+=1;record(self.file);return json.loads(self.file.read_text())
        first=self.history.read(self.owner,self.reference,parse);self.assertEqual({'historical':'one'},first);self.assertEqual(2,self.calls)
        function=json.JSONDecoder.decode;defaults=function.__defaults__
        self.assertIs(type(defaults[0].__self__),re.Pattern);self.assertEqual('match',defaults[0].__name__)
        function.__defaults__=(re.compile(r'.*').match,)
        try:
            self.assertFalse(self.history.literal())
            with self.assertRaises(json.JSONDecodeError):self.history.read(self.owner,self.reference,parse)
        finally:function.__defaults__=defaults
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
        self.assertEqual(first,self.history.read(self.owner,self.reference,parse));self.assertEqual(3,self.calls)

    def test_unsupported_native_regex_search_method_default_remains_literal(self):
        import json,re
        self.read();function=json.decoder._decode_uXXXX;defaults=function.__defaults__
        function.__defaults__=(re.compile(r'[0-9A-Fa-f]{4}').search,)
        try:
            self.assertFalse(self.history.literal());self.read()
            self.assertTrue(any(row['type']==('builtins','builtin_method') and row['reason']=='regex-bound-method'
                for row in self.history.unsupported_members()))
        finally:function.__defaults__=defaults
        self.assertEqual(3,self.calls);self.assertTrue(self.history.literal())
