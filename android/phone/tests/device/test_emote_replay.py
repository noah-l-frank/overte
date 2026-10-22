"""Pure replay reuse never substitutes for reopening original source files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_emote_sources
from adapters.normal_ui import NativeUIError
from overte_phone_emote_sources import PhoneEmoteSources
import overte_phone_emote_replay as replay


class EmoteReplayTests(unittest.TestCase):
    setUp=test_emote_sources.PhoneEmoteSourcesTests.setUp

    def source(self):
        source=self.model.source();source.read();replay._verified.clear()
        return source

    def test_repeat_reopens_and_hashes_original_files_but_does_not_repeat_pure_history_validation(self):
        with self.model.lock.held():
            source=self.source();header=source.previous
            with patch.object(source,'validate_frame',wraps=source.validate_frame) as validate:
                first=source.decode(header);self.assertEqual(1,validate.call_count);validate.reset_mock()
                with patch.object(source.originals,'read',wraps=source.originals.read) as read:
                    second=source.decode(header);self.assertGreaterEqual(read.call_count,1)
                self.assertEqual(first,second);validate.assert_not_called()
            before=len(source.frames);calls=self.model.calls.count('native-read');source.read()
            self.assertGreater(self.model.calls.count('native-read'),calls);self.assertEqual(before+1,len(source.frames))

    def test_changed_original_cannot_borrow_a_previously_validated_history(self):
        with self.model.lock.held():
            source=self.source();source.decode(source.previous)
            ref=source.originals.manifest(source.state['manifests'][0])[0]
            path=source.originals.path(source.originals.expand(ref));raw=path.read_bytes()
            path.write_bytes(raw[:-1]+b' ')
            with self.assertRaises(NativeUIError):source.decode(source.previous)

    def test_missing_original_cannot_borrow_a_previously_validated_history(self):
        with self.model.lock.held():
            source=self.source();source.decode(source.previous)
            ref=source.originals.manifest(source.state['manifests'][0])[0]
            source.originals.path(source.originals.expand(ref)).unlink()
            with self.assertRaises((NativeUIError,OSError)):source.decode(source.previous)

    def test_failed_replay_never_enters_memo(self):
        with self.model.lock.held():
            source=self.source()
            with patch.object(source,'validate_frame',side_effect=NativeUIError('Synthetic rejected history')) as validate:
                for _ in range(2):
                    with self.assertRaises(NativeUIError):source.decode(source.previous)
                self.assertEqual(2,validate.call_count)

    def test_archive_results_have_independent_graphs_and_cannot_change_live_or_original_data(self):
        with self.model.lock.held():
            source=self.source()
            def archive():
                return PhoneEmoteSources.archive(source.previous,phase=source.phase,artifact_root=source.artifact_root,
                    binding=source.binding,guard=source.guard,monotonic=source.monotonic)
            first_state,first=archive();second_state,second=archive()
            first_state['revision']=999;first[0]['group']['native']['sequence']=999999
            self.assertEqual(1,second_state['revision']);self.assertNotEqual(999999,second[0]['group']['native']['sequence'])
            third_state,third=archive()
            self.assertEqual(second_state,third_state);self.assertEqual(second,third)
            self.assertNotEqual(999999,source.frames[0]['group']['native']['sequence'])

    def test_decode_results_cannot_mutate_header_live_frames_or_later_original_reads(self):
        with self.model.lock.held():
            source=self.source();state,frames=source.decode(source.previous)
            state['revision']=999;state['manifests'].clear()
            frames[0]['group']['native']['sequence']=999999
            frames[0]['group']['script']['source'].clear()
            actual_state,actual_frames=source.decode(source.previous)
            self.assertEqual(1,actual_state['revision']);self.assertTrue(actual_state['manifests'])
            self.assertEqual(source.frames,actual_frames)
            self.assertNotEqual(999999,actual_frames[0]['group']['native']['sequence'])
            self.assertTrue(actual_frames[0]['group']['script']['source'])

    def test_catalog_byte_change_invalidates_pure_validation_memo(self):
        with self.model.lock.held(),tempfile.TemporaryDirectory(prefix='overte-emote-pin-key-') as temporary:
            source=self.source();source.decode(source.previous)
            catalog=Path(temporary)/'pins.json';catalog.write_bytes(replay.ADMISSION_PINS.read_bytes()+b'\n')
            with patch.object(replay,'ADMISSION_PINS',catalog),patch.object(source,'validate_frame',wraps=source.validate_frame) as validate:
                source.decode(source.previous);self.assertEqual(1,validate.call_count)

    def test_pure_validation_memo_is_bounded_and_scoped_by_exact_immutable_context(self):
        with self.model.lock.held():
            first=self.model.source();second=self.model.source();calls=[];replay._verified.clear()
            state=dict(revision=0,manifests=[])
            for index in range(replay.LIMIT+1):replay.history(first.phase,dict(context=index),state,lambda:calls.append(1))
            self.assertEqual(replay.LIMIT,len(replay._verified))
            replay.history(first.phase,dict(context=0),state,lambda:calls.append(1))
            replay.history(second.phase,dict(context=0),state,lambda:calls.append(1))
            self.assertEqual(replay.LIMIT+2,len(calls))
            replay.history(second.phase,dict(context=0,binding=dict(processIdentity='foreign')),state,lambda:calls.append(1))
            self.assertEqual(replay.LIMIT+3,len(calls))

    def test_reconstruction_reuses_only_verified_pure_history_and_still_reopens_original_files(self):
        with self.model.lock.held():
            source=self.source();source.decode(source.previous)
            with patch.object(PhoneEmoteSources,'validate_frame',side_effect=NativeUIError('Pure replay should already be verified')) as validate:
                reconstructed=self.model.source();self.assertEqual(source.frames,reconstructed.frames);validate.assert_not_called()
            reference=source.originals.manifest(source.state['manifests'][0])[0]
            source.originals.path(source.originals.expand(reference)).unlink()
            with self.assertRaises((NativeUIError,OSError)):self.model.source()


if __name__=='__main__':unittest.main()
