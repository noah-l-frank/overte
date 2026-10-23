"""Strict original capture context at explicit native observation seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_context import validate
from adapters.pico4.snapshot_script_originals import validate as packet,accept
from self_tests.test_pico_snapshot_script_originals import history,RUN


def context(epoch=100):
    values=dict(previousSnapshotDomainID='{01234567-89ab-cdef-0123-456789abcdef}',
        previousSnapshotHref='hifi://original/place',previousStillSnapPath='/original/capture.png')
    return dict(snapshotCaptureContextVersion=1,instance='d'*32,capturedEpochMs=epoch,
        entries={key:dict(present=True,value=value) for key,value in values.items()},normalizedHref=values['previousSnapshotHref'])


def source():
    value=dict(snapshotScriptOriginalsVersion=3,activeUploads=0,commandId='a'*32,runId=RUN,pid=31,
        sequence=1,capturedEpochMs=100,history=history(),captureContext=context())
    value['history']['snapshotScriptHistoryVersion']=2
    for row in value['history']['events']:row['context']=context()
    return value


class SnapshotContextTests(unittest.TestCase):
    def test_presence_is_not_a_default_and_original_strings_are_typed(self):
        value=context();validate(value,100)
        value['entries']['previousSnapshotHref']=dict(present=False,value=None);value['normalizedHref']='';validate(value,100)
        for edit in (lambda v:v.update(snapshotCaptureContextVersion=True),lambda v:v.update(instance=''),
                lambda v:v.update(capturedEpochMs=101),lambda v:v['entries']['previousSnapshotDomainID'].update(value=True),
                lambda v:v['entries']['previousStillSnapPath'].update(value='a\0b'),lambda v:v['entries'].update(expectedDomain='fixture')):
            value=context();edit(value)
            with self.assertRaises(NativeUIError):validate(value,100)
        value['entries']['previousSnapshotHref']=dict(present=False,value='fallback')
        with self.assertRaises(NativeUIError):validate(value,100)

    def test_fresh_wrapper_cannot_retime_an_old_current_context(self):
        value=source();value['capturedEpochMs']=1601
        with self.assertRaises(NativeUIError):packet(value,RUN,'a'*32,31,1601)

    def test_history_and_current_context_require_one_original_manager_birth(self):
        value=source();packet(value,RUN,'a'*32,31,100)
        for where in ('current','event','old-wrapper'):
            changed=deepcopy(value)
            if where=='current':changed['captureContext']['instance']='b'*32
            elif where=='event':changed['history']['events'][1]['context']['instance']='b'*32
            else:changed['snapshotScriptOriginalsVersion']=2;changed.pop('captureContext')
            with self.subTest(where=where),self.assertRaises(NativeUIError):packet(changed,RUN,'a'*32,31,100)
        previous=source();previous['history']['events']=[];previous['history']['sequence']=0
        current=deepcopy(previous);current.update(sequence=2,commandId='b'*32);current['captureContext']['instance']='b'*32
        with self.assertRaises(NativeUIError):accept(previous,current)



if __name__=='__main__':unittest.main()
