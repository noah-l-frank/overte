"""Local decode dataflow over actual private carriers; no native effect claim.

Only the measurement/qualification calls are explicit sentinels. The production
record grammar, bytes, digests, chronology and entry/exit inode guards are real.
The separate staged Node/PNG terminal-live case qualifies the composed path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.world_web_retirement import WorldWebRetirement


class WorldWebRetirementOnePassTests(unittest.TestCase):
    def owner(self,root):
        owner=object.__new__(WorldWebRetirement);owner.version=2
        owner.binding=dict(processIdentity='explicit-host-carrier-model');owner.run='a'*32;owner.role='primary'
        owner.store=PrivateFeatureState(root/'ios-world-web-primary-retirement.json')
        records=[]
        for index in range(1,4):
            frame=dict(index=index,before=dict(index=index*2),after=dict(index=index*2+1))
            value=dict(iosWorldWebRetirementRecordVersion=2,binding=owner.binding,runId=owner.run,payload=pack([frame]))
            owner.record_store(index).write(value,None);records.append(dict(index=index,sha256=digest(value)))
        state=dict(phase='retired',ticket='sentinel-ticket',baseline=None,barrier=records[0],images=['sentinel-image'],
            restoration='sentinel-image',records=records,pending=None,interrupted=[],quiet=records)
        owner.state=dict(original='unchanged');return owner,state

    def test_full_record_measurement_is_once_per_local_decode_and_results_do_not_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            owner,state=self.owner(Path(temporary));prior=deepcopy(owner.state)
            def qualify(current,checked):
                self.assertEqual(state,current);self.assertEqual(3,len(checked))
                for reference in current['records']:
                    frame,proof,signature=checked[(reference['index'],reference['sha256'])]
                    self.assertEqual(frame,owner.frame(reference));self.assertEqual(dict(measured=frame['index']),proof)
                    self.assertEqual(signature,owner.record_signature(owner.record_store(frame['index']).path))
                return dict(sentinelMeasurement=True)
            with patch.object(owner,'measure',create=True,side_effect=lambda frame:dict(measured=frame['index'])) as measured, patch.object(owner,'_qualification',side_effect=qualify):
                decoded,proof=owner._decode(owner.envelope(state),with_measurement=True)
                self.assertEqual(3,measured.call_count);self.assertEqual(dict(sentinelMeasurement=True),proof)
            decoded['records'].clear();self.assertEqual(3,len(state['records']));self.assertEqual(prior,owner.state)

    def test_changed_bytes_or_same_bytes_replaced_inode_after_measurement_fail_on_exit(self):
        for replacement in (False,True):
            with self.subTest(replacement=replacement),tempfile.TemporaryDirectory() as temporary:
                owner,state=self.owner(Path(temporary));prior=deepcopy(owner.state)
                def changed(_current,_checked):
                    path=owner.record_store(2).path;raw=path.read_bytes()
                    if replacement:
                        other=path.with_suffix('.replacement');other.write_bytes(raw);other.chmod(0o600);other.replace(path)
                    else:
                        with path.open('r+b') as stream:stream.seek(0);stream.write(b' ')
                    return dict(sentinelMeasurement=True)
                with patch.object(owner,'measure',create=True,return_value={}),patch.object(owner,'_qualification',side_effect=changed):
                    with self.assertRaises(NativeUIError):owner._decode(owner.envelope(state),with_measurement=True)
                self.assertEqual(prior,owner.state)


if __name__=='__main__':unittest.main()
