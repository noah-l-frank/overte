"""Historical PNG decode reuse preserves every independent original file check."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import need
import overte_phone_snapshots_evidence as evidence
from overte_phone_snapshots_role import PhoneSnapshotsRole
from test_graphics_images import BINDING
from test_graphics_measurements import RUN,TICKET
from self_tests.test_snapshot_upload_service import png


class SnapshotHistoricalPngTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-history-png-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.raw=png();self.guard_calls=0;self.allowed=True
        self.role=SimpleNamespace(feature=SimpleNamespace(root=self.root,binding=BINDING,run=RUN),role='primary',history_authority=self.guard)

    def guard(self):
        self.guard_calls+=1;need(self.allowed);return True

    def binary(self,stage):
        return evidence.SnapshotsBinary(self.root,BINDING,RUN,'primary',stage,self.guard,lambda *_:True)

    def frame(self,stage,raw=None):
        raw=self.raw if raw is None else raw
        acquisition=dict(source='snapshot-capture-original',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),capturedEpochMs=20000+stage)
        return dict(image=None,binaries=[self.binary(stage).write(TICKET,acquisition,raw)])

    def validate(self,frames,*,historical=True):
        PhoneSnapshotsRole.validate_files(self.role,frames=frames,historical=historical)

    def test_145_actual_original_files_decode_once_per_pass_and_every_file_keeps_guards(self):
        frames=[self.frame(stage) for stage in range(1,146)];self.guard_calls=0
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            started=time.monotonic();self.validate(frames);elapsed=time.monotonic()-started
            self.assertEqual(1,decode.call_count);self.assertEqual(290,self.guard_calls)
            self.validate(frames);self.assertEqual(2,decode.call_count);self.assertEqual(580,self.guard_calls)
        print('Historical original files=145 unique full PNG decodes=1 per-pass seconds='+str(round(elapsed,3)),flush=True)

    def test_normal_current_binary_reads_still_decode_each_time(self):
        frame=self.frame(1);record=frame['binaries'][0]
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            self.binary(1).read(record);self.binary(1).read(record)
            self.assertEqual(2,decode.call_count)

    def test_actual_different_valid_png_bytes_require_their_own_full_decode(self):
        from PIL import Image,ImageDraw
        from io import BytesIO
        image=Image.new('RGB',(4,4),'black');ImageDraw.Draw(image).point((1,1),fill='white')
        output=BytesIO();image.save(output,format='PNG')
        frames=[self.frame(1),self.frame(2,output.getvalue())]
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            self.validate(frames);self.assertEqual(2,decode.call_count)

    def test_late_missing_changed_mode_link_or_inode_cannot_use_the_first_file_decode(self):
        for mutation in ('missing','bytes','mode','link','inode'):
            with self.subTest(mutation=mutation):
                frames=[self.frame(1),self.frame(2)];path=self.root/frames[1]['binaries'][0]['name']
                original=evidence.inspect_snapshot
                def decoded(*args,**kwargs):
                    result=original(*args,**kwargs)
                    if mutation=='missing':path.unlink()
                    elif mutation=='bytes':path.write_bytes(self.raw[:-1]+bytes([self.raw[-1]^1]))
                    elif mutation=='mode':path.chmod(0o644)
                    elif mutation=='link':os.link(path,self.root/'alias')
                    else:
                        replacement=self.root/'replacement';replacement.write_bytes(self.raw);replacement.chmod(0o600);os.replace(replacement,path)
                    return result
                with patch.object(evidence,'inspect_snapshot',side_effect=decoded) as decode:
                    with self.assertRaises((NativeUIError,FileNotFoundError)):self.validate(frames)
                    self.assertEqual(1,decode.call_count)
                for entry in self.root.iterdir():entry.unlink()

    def test_foreign_acquisition_hash_or_owner_record_is_rejected_after_a_valid_decode(self):
        for field in ('sha256','binding','stage'):
            with self.subTest(field=field):
                frames=[self.frame(1),self.frame(2)];record=frames[1]['binaries'][0]
                if field=='sha256':record['acquisition']['sha256']='f'*64
                elif field=='binding':record['binding']['sessionId']='foreign'
                else:record['stage']=1
                with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
                    with self.assertRaises(NativeUIError):self.validate(frames)
                    self.assertEqual(1,decode.call_count)
                for entry in self.root.iterdir():entry.unlink()

    def test_invalid_png_with_matching_actual_and_claimed_hash_still_requires_decode(self):
        frames=[self.frame(1)];raw=b'not an original PNG'
        acquisition=dict(source='snapshot-saved-original',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),capturedEpochMs=20002)
        record=self.binary(2).value(TICKET,acquisition);path=self.root/record['name']
        path.write_bytes(raw);path.chmod(0o600);info=path.stat();record.update(phase='saved',file=dict(device=info.st_dev,inode=info.st_ino))
        frames.append(dict(image=None,binaries=[record]))
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            with self.assertRaises(NativeUIError):self.validate(frames)
            self.assertEqual(2,decode.call_count)

    def test_valid_foreign_source_record_cannot_reuse_identical_actual_body(self):
        frames=[self.frame(1),self.frame(2)];original=frames[1]['binaries'][0]
        acquisition=dict(original['acquisition'],sha256='f'*64)
        foreign=self.binary(2).value(TICKET,acquisition)
        (self.root/original['name']).rename(self.root/foreign['name'])
        foreign.update(phase='saved',file=original['file']);frames[1]['binaries']=[foreign]
        evidence.SnapshotsBinary.record(foreign)
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            with self.assertRaises(NativeUIError):self.validate(frames)
            self.assertEqual(1,decode.call_count)

    def test_late_lost_authority_is_checked_even_for_identical_qualified_bytes(self):
        frames=[self.frame(1),self.frame(2)];original=evidence.inspect_snapshot
        def decoded(*args,**kwargs):
            result=original(*args,**kwargs);self.allowed=False;return result
        with patch.object(evidence,'inspect_snapshot',side_effect=decoded):
            with self.assertRaises(NativeUIError):self.validate(frames)

    def test_valid_body_over_memo_budget_is_fully_decoded_without_new_file_limit(self):
        from PIL import Image
        from io import BytesIO
        import random
        pixels=random.Random(9817).randbytes(2500*2250*3)
        image=Image.frombytes('RGB',(2500,2250),pixels);output=BytesIO();image.save(output,format='PNG')
        raw=output.getvalue();self.assertGreater(len(raw),16*1024*1024)
        frames=[self.frame(1,raw),self.frame(2,raw)]
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            self.validate(frames);self.assertEqual(2,decode.call_count)

    def test_full_optional_memo_keeps_decoding_new_valid_bodies(self):
        from PIL import Image,ImageDraw
        from io import BytesIO
        decoded_pngs=set()
        reader=evidence.HistoricalSnapshotsBinary(self.root,BINDING,RUN,'primary',1,self.guard,lambda *_:True,decoded_pngs=decoded_pngs)
        with patch.object(evidence,'inspect_snapshot',wraps=evidence.inspect_snapshot) as decode:
            for index in range(257):
                image=Image.new('RGB',(4,4),'black');ImageDraw.Draw(image).point((1,1),fill=(index%256,index//256,255))
                output=BytesIO();image.save(output,format='PNG');raw=output.getvalue()
                acquisition=dict(source='snapshot-capture-original',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),capturedEpochMs=20000)
                value=dict(acquisition=acquisition);reader.content(value,raw)
            self.assertEqual(256,len(decoded_pngs));self.assertEqual(257,decode.call_count)
            reader.content(value,raw);self.assertEqual(258,decode.call_count)


if __name__=='__main__':unittest.main()
