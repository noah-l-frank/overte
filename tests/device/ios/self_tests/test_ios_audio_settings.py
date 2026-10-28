"""Explicit typed Audio/Qt model, actual normal codecs/WAL/original files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import audio_settings_source as source
from ios.self_tests.audio_settings_fixture import Fixture


class AudioSettingsTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='audio-settings-originals-'));self.root.chmod(0o700);print('retained settings root',self.root,flush=True)
        self.f=Fixture(self.root);self.addCleanup(self.f.close)
    def test_typed_baseline_precedes_normal_input_and_exact_selected_values_restore_with_all_guards(self):
        f=self.f;f.domain.muted=True;f.domain.echo=True;f.owner.baseline();self.assertEqual([],f.domain.actions)
        f.domain.muted=False;f.domain.echo=False;result=f.owner.restore()
        self.assertTrue(result['observedSelectedMuteEchoValuesRestored']);self.assertTrue(f.domain.muted);self.assertTrue(f.domain.echo)
        self.assertEqual(1,f.domain.actions.count('audio.mute'));self.assertEqual(1,f.domain.actions.count('audio.live-echo'))
        self.assertFalse(result['wholeSettingsRestorationAvailable']);self.assertFalse(result['independentAcousticsAvailable'])
        self.assertTrue(all(row['returned'] and row['after'] is not None for row in f.owner.state['operations']))
    def test_ignored_normal_input_stays_owned_even_when_returned_and_is_never_replayed(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;f.domain.ignore=True
        with self.assertRaises(NativeUIError):f.owner.restore()
        self.assertTrue(f.owner.state['pending']['returned']);self.assertEqual(1,f.domain.actions.count('audio.live-echo'))
        with self.assertRaises(NativeUIError):f.owner.restore()
        with self.assertRaises(NativeUIError):f.owner.resolve()
        self.assertEqual(1,f.domain.actions.count('audio.live-echo'))
    def test_lost_return_is_resolved_only_by_new_typed_original_without_another_click(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;f.domain.loss=True
        with self.assertRaises(NativeUIError):f.owner.restore()
        self.assertFalse(f.owner.state['pending']['returned']);f.domain.loss=False;f.owner.resolve();result=f.owner.restore()
        self.assertEqual(1,f.domain.actions.count('audio.live-echo'));self.assertFalse(f.owner.state['operations'][0]['returned'])
        self.assertTrue(result['observedSelectedMuteEchoValuesRestored'])
    def test_active_hidden_ptt_unloaded_settings_or_push_in_progress_refuse_before_any_input(self):
        for field in ('pttDesktop','pttHmd','pushingToTalk','settingsLoaded'):
            f=self.f;f.domain.script[field]=False if field=='settingsLoaded' else True
            with self.subTest(field=field),self.assertRaises(NativeUIError):f.owner.baseline()
            self.assertEqual([],f.domain.actions);self.assertIsNone(f.owner.state['baseline']);f.domain.script[field]=field=='settingsLoaded'
    def test_runtime_persisted_mixer_echo_stereo_or_mode_drift_cannot_be_repaired_by_hidden_setters(self):
        f=self.f;f.owner.baseline();f.domain.echo=True
        for fault in ('ptt','persisted','mixer','gain','serverEcho','stereo'):
            a,b,c=deepcopy((f.domain.script,f.domain.mixer,f.domain.client))
            if fault=='ptt':f.domain.script['pttDesktop']=True
            elif fault=='persisted':f.domain.script['persisted']['pttHmd']=True
            elif fault=='mixer':f.domain.mixer['avatarGain']=.25
            elif fault=='gain':f.domain.script['localInjectorGain']=.25
            elif fault=='serverEcho':f.domain.client['serverEcho']=True
            else:f.domain.client['stereoInput']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):f.owner.restore()
            self.assertEqual([],f.domain.actions);f.domain.script,f.domain.mixer,f.domain.client=a,b,c
    def test_unknown_field_boolean_number_and_unequal_double_reads_are_not_original_settings(self):
        f=self.f;ref=f.sources.capture('baseline');packet=f.sources.frame(ref)['originals']['settings']
        for fault in ('version','typed','mismatch','field','whole'):
            value=deepcopy(packet)
            if fault=='version':value['iosAudioSettingsVersion']=True
            elif fault=='typed':value['source']['scriptBefore']['inputVolume']=True;value['source']['scriptAfter']['inputVolume']=True
            elif fault=='mismatch':value['source']['clientAfter']['localEcho']=True
            elif fault=='field':value['source']['clientBefore']['expectedMuted']=True
            else:value['wholeSettingsRestorationAvailable']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_saved_source_body_lost_append_adopts_exact_original_without_query_or_click(self):
        f=self.f;intent=f.sources.frames.intent
        def lost(kind,ref):
            value=intent(kind,ref)
            if ref['phase']=='saved':raise RuntimeError('Declared saved settings append lost')
            return value
        f.sources.frames.intent=lost
        with self.assertRaises(RuntimeError):f.sources.capture('baseline')
        count=len(f.domain.queries);ref=f.sources.recover_capture()
        self.assertEqual(1,ref['index']);self.assertEqual(count,len(f.domain.queries));self.assertEqual([],f.domain.actions)
    def test_unknown_settings_query_intent_survives_and_cannot_be_replaced_by_empty_success(self):
        f=self.f
        def unknown(query):raise RuntimeError('Declared unknown readonly settings delivery')
        f.sources.settings.send=unknown
        with self.assertRaises(NativeUIError):f.sources.capture('baseline')
        self.assertIsNotNone(f.sources.state['pending']);before=deepcopy(f.sources.state['pending'])
        with self.assertRaises(NativeUIError):f.sources.capture('baseline')
        self.assertEqual(before,f.sources.state['pending']);self.assertEqual([],f.domain.actions)
    def test_replaced_original_inode_or_guard_loss_cannot_reuse_previous_success(self):
        f=self.f;f.owner.baseline();f.domain.changed=True
        with self.assertRaises(NativeUIError):f.owner.restore()
        f.domain.changed=False;ref=f.sources.frames.expand(f.sources.state['frames'][0]);path=f.sources.frames.path(ref);raw=path.read_bytes()
        path.rename(self.root/'retained-source-original');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):f.owner.verify()
        self.assertEqual([],f.domain.actions)
    def test_plain_verification_does_not_write_settings_or_issue_normal_input(self):
        f=self.f;f.owner.baseline();before=deepcopy(f.domain.actions)
        with patch.object(f.domain,'activate',side_effect=AssertionError('verification cannot mutate')):
            result=f.owner.verify()
        self.assertEqual(before,f.domain.actions);self.assertFalse(result['processSdkRetirementAvailable'])

    def test_other_selected_value_changed_during_one_click_cannot_be_laundered_as_the_owned_effect(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;original=f.domain.activate
        def changed(identifier,*,token):
            original(identifier,token=token);f.domain.muted=not f.domain.muted
        with patch.object(f.domain,'activate',side_effect=changed),self.assertRaises(NativeUIError):f.owner.restore()
        self.assertIsNotNone(f.owner.state['pending']);self.assertEqual(1,f.domain.actions.count('audio.live-echo'))
    def test_nonce_query_cannot_supply_settings_expected_result_or_direct_setter_fields(self):
        for field in ('muted','localEcho','pushToTalk','expectedSettings','setter','permissionGranted'):
            query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId='b'*32,**{field:True})
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(query)
