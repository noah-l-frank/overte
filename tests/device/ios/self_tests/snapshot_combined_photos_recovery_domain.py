"""Lost delivered Save return on the same whole-PNG Result2 owner graph."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.self_tests.snapshot_combined_photos_return_domain import CombinedPhotosReturnFlow


class LostSaveCombinedPhotosReturnFlow(CombinedPhotosReturnFlow):
    def finish_photos(self,case):
        photos=self.photos;host=self.main.f.f.h.path
        original=(host.stat().st_ino,host.read_bytes())
        capture=PrivateFeatureState(self.main.ctx.root/'ios-snapshot-primary-capture-owner.json')
        capture_original=deepcopy(capture.read());photos.lose_save=True
        with photos.owner() as failed:
            with case.assertRaises((NativeUIError,OSError)):failed.save('7'*32)
            case.assertIsNone(failed.state['saved']);case.assertIsNotNone(failed.state['input'])
            uncertain=failed.inputs(True);case.assertEqual(1,len(uncertain.state['events']))
            event=deepcopy(uncertain.state['events'][0]);case.assertEqual('issued',event['phase'])
            durable=failed.store.read();case.assertEqual(durable,failed.previous)
            case.assertEqual(uncertain.store.read(),uncertain.previous)
        case.assertEqual(1,photos.save_count);case.assertEqual(1,len(photos.library))
        case.assertEqual(original,(host.stat().st_ino,host.read_bytes()))
        # A newly constructed production owner decodes the existing WAL. No
        # second capture, helper admission, phase ticket or normal input occurs.
        with photos.owner() as resumed:
            case.assertIsNot(resumed,failed);case.assertEqual(durable,resumed.previous)
            self.photos_saved=resumed.save('7'*32)
            delivered=resumed.inputs(True);delivered.validate_original(1)
            current=delivered.state['events'][0]
            case.assertEqual(event['command'],current['command']);case.assertEqual(event['reference'],current['reference'])
            case.assertEqual('delivered',current['phase']);case.assertEqual(1,len(delivered.state['events']))
            self.photos_cleaned=resumed.cleanup()
        case.assertEqual(capture_original,capture.read())
        case.assertEqual(original,(host.stat().st_ino,host.read_bytes()))
        case.assertEqual((1,1,1,1),(photos.save_count,photos.helper.read_count,photos.helper.delete_count,photos.helper.retire_count))
        case.assertEqual(1,self.main.upload_count)
