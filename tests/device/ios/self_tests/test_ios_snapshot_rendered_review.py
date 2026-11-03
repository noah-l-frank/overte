"""Original PNG/file proofs with declared QML/WDA producers, no native run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.graphics_images import IOSGraphicsImages
from ios.adapters.snapshot_review_images import SnapshotReviewImages
from ios.adapters import snapshot_review as review
from ios.self_tests.test_ios_graphics_images import SDK
from self_tests.test_completed_frame_lease import BINDING,RUN

NAME='parity-'+RUN[:16]+'-still-png-snap_1700000000000_1.png'


def png(image):
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def original_pattern():
    image=Image.new('RGB',(128,128));pixels=image.load()
    for y in range(128):
        for x in range(128):pixels[x,y]=((x*2)%256,(y*2)%256,((x//16+y//16)%2)*200+20)
    return png(image)


def screen_pattern(*,ignored=False):
    # Independent model producer renders its own scan, never the decoded
    # expected PNG or a caller's successful comparison result.
    image=Image.new('RGB',(320,320),(12,18,24));pixels=image.load()
    for y in range(128):
        for x in range(128):
            pixels[x+64,y+80]=((255-x*2)%256,(255-y*2)%256,40)if ignored else(
                (x*2)%256,(y*2)%256,((x//16+y//16)%2)*200+20)
    return png(image)


def ui(sdk):
    preview=dict(objectIdentity='22222222-2222-4222-8222-222222222222',row=0,fileOwned=True,fileName=NAME,
        status=1,visible=True,sourceSize=[128,128],paintedBounds=[64,80,128,128],centerAligned=True,
        preserveAspectFit=True,unclipped=True,axisAligned=True,systemBlocked=False,
        window=dict(width=320,height=320,x=0,y=0,devicePixelRatio=1))
    root=dict(rootIdentity='11111111-1111-4111-8111-111111111111',
        qmlSource='file:///declared/system/snapshot/NativeSnapshotReview.qml',visible=True,
        capturing=False,processing=False,statusError=False,imageCount=1,images=[preview])
    return dict(schemaVersion=1,instance='33333333-3333-4333-8333-333333333333',frameSpace='qt-window-logical',
        processId=42,sampleEpochMs=sdk.native(),elapsedMs=round(sdk.clock*1000),lastSequence=0,
        tabletShown=True,ready=True,controls=[],
        snapshotReviewInventory=dict(iosSnapshotReviewInventoryVersion=1,complete=True,roots=[root]))


class SnapshotRenderedReviewTests(unittest.TestCase):
    def acquire(self,*,ignored=False,kind=SnapshotReviewImages):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);sdk=SDK();sdk.raw=screen_pattern(ignored=ignored)
        owner=kind(PrivateFeatureState(root/'screen.json'),root,BINDING,RUN,'primary',0,sdk,sdk.native,
            lambda:sdk.valid,epoch_ms=sdk.host,monotonic=lambda:sdk.clock)
        before=ui(sdk);row,raw=owner.capture('e'*32);after=ui(sdk)
        return sdk,owner,before,after,row,raw

    def test_independent_actual_png_and_retained_screen_join_without_whole_or_scene_claim(self):
        sdk,owner,before,after,row,raw=self.acquire()
        result=review.joined(before,after,row['capture'],original_pattern(),raw,NAME,42)
        self.assertEqual([64,80,192,208],result['pixels']['screenBounds'])
        self.assertEqual(0,max(result['pixels']['meanChannelDifference']))
        self.assertEqual(1,result['pixels']['within24Fraction'])
        self.assertTrue(all(result[key]for key in ('originalUIAndScreenOwnershipRequired',
            'originalCaptureCompletionRequired','independentActorAndSceneRequired','wholeFeatureRequired')))
        self.assertEqual(raw,owner.archive(row['nonce']))
        self.assertEqual(1,owner.store.read()['snapshotReviewScreenImagesVersion'])
        self.assertTrue(row['name'].startswith('snapshot-review-'))
        self.assertEqual(1,len(sdk.calls))

    def test_ready_source_name_and_input_ack_cannot_hide_wrong_or_uniform_rendered_pixels(self):
        _sdk,_owner,before,after,row,raw=self.acquire(ignored=True)
        with self.assertRaises(NativeUIError):review.joined(before,after,row['capture'],original_pattern(),raw,NAME,42)
        with self.assertRaises(NativeUIError):review.joined(before,after,row['capture'],png(Image.new('RGB',(128,128),'black')),raw,NAME,42)

    def test_unavailable_ambiguous_occluded_loading_and_unmapped_preview_refuse(self):
        _sdk,_owner,before,after,row,raw=self.acquire()
        for change in ('missing','incomplete','loading','blocked','clipped','transformed','duplicate','offset'):
            with self.subTest(change=change):
                a,b=deepcopy(before),deepcopy(after)
                for value in (a,b):
                    inventory=value['snapshotReviewInventory'];root=inventory['roots'][0];image=root['images'][0]
                    if change=='missing':inventory['roots']=[]
                    elif change=='incomplete':inventory['complete']=False
                    elif change=='loading':image['status']=2
                    elif change=='blocked':image['systemBlocked']=True
                    elif change=='clipped':image['unclipped']=False
                    elif change=='transformed':image['axisAligned']=False
                    elif change=='duplicate':root['images'].append(deepcopy(image));root['imageCount']=2
                    elif change=='offset':image['window']['x']=10
                with self.assertRaises(NativeUIError):review.joined(a,b,row['capture'],original_pattern(),raw,NAME,42)

    def test_stale_native_brackets_or_different_process_are_not_rendered_review(self):
        _sdk,_owner,before,after,row,raw=self.acquire()
        for change in ('before','after','process','input'):
            with self.subTest(change=change):
                a,b=deepcopy(before),deepcopy(after)
                if change=='before':a['sampleEpochMs']+=1
                elif change=='after':b['sampleEpochMs']-=1
                elif change=='process':b['processId']=43
                else:b['lastSequence']+=1
                with self.assertRaises(NativeUIError):review.joined(a,b,row['capture'],original_pattern(),raw,NAME,42)

    def test_changed_object_or_file_cannot_borrow_an_earlier_visible_cut(self):
        _sdk,_owner,before,after,row,raw=self.acquire()
        for field,value in (('objectIdentity','44444444-4444-4444-8444-444444444444'),
                ('fileName',NAME.replace('_1.png','_2.png'))):
            b=deepcopy(after);b['snapshotReviewInventory']['roots'][0]['images'][0][field]=value
            with self.assertRaises(NativeUIError):review.joined(before,b,row['capture'],original_pattern(),raw,NAME,42)

    def test_same_byte_screen_inode_replacement_is_refused_by_original_owner(self):
        _sdk,owner,_before,_after,row,raw=self.acquire();path=owner.root/row['name']
        old=path.stat().st_ino;backup=path.with_suffix('.retained-original');path.rename(backup)
        path.write_bytes(raw);path.chmod(0o600);self.assertNotEqual(old,path.stat().st_ino)
        with self.assertRaises(NativeUIError):owner.archive(row['nonce'])
        self.assertEqual(raw,backup.read_bytes());self.assertEqual(raw,path.read_bytes())

    def test_lost_sdk_screen_return_keeps_open_file_responsibility_and_never_reissues(self):
        sdk,owner,_before,_after,_row,_raw=self.acquire();sdk.error=True
        with self.assertRaises(NativeUIError):owner.capture('f'*32)
        self.assertEqual(2,len(sdk.calls))
        with self.assertRaises(NativeUIError):owner.capture('f'*32)
        self.assertEqual(2,len(sdk.calls));rows=unpack(owner.store.read()['transcript'])
        self.assertEqual('opened',rows[-1]['phase']);self.assertIsNone(rows[-1]['capture'])

    def test_existing_graphics_profile_keeps_original_namespace_and_header_grammar(self):
        _sdk,owner,_before,_after,row,raw=self.acquire(kind=IOSGraphicsImages)
        self.assertTrue(row['name'].startswith('graphics-'));self.assertEqual(raw,owner.archive(row['nonce']))
        self.assertEqual(1,owner.store.read()['graphicsScreenImagesVersion'])
        self.assertNotIn('snapshotReviewScreenImagesVersion',owner.store.read())
