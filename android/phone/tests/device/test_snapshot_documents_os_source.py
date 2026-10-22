"""Closed native SAF identity grammar; observed packets here are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import source
import test_snapshot_os_retirement_source as original
import test_snapshot_readback_source as base


def document_boundary():
    value=original.boundary();value.component['sequence']=1;component=value.component;raw=component['destinations'][0];os=component['osDestinations'];row=os['rows'][0]
    id='doc-'+base.RUN+'-'+'c'*32+'-'+'d'*32;uri='content://org.overte.e2e.snapshotreceiver.documents/document/'+id
    raw.update(uri=uri,inserted=False);row.update(inserted=False);os['snapshotOsDestinationsVersion']=2
    row['identity']=dict(uri=uri,providerUid=1002,providerPackage='org.overte.e2e.snapshotreceiver',ownerPackage='org.overte.e2e.snapshotreceiver',
        displayName='e2e-'+base.RUN+'-save.png',device=1,inode=2,storage='documents',runId=base.RUN,armId='c'*32,providerInstance='e'*32,
        documentId=id,createUid=1000,createdEpochMs=value.epoch-2)
    return value


class SnapshotDocumentsOsSourceTests(unittest.TestCase):
    def test_real_callback_inserted_false_is_preserved_and_only_fixed_v2_creation_can_retire(self):
        value=document_boundary();source(dict(accepted=True,source=value.component));self.assertFalse(value.component['osDestinations']['rows'][0]['inserted'])
    def test_historical_mediastore_identity_and_version_are_unchanged(self):
        value=original.boundary();value.component['sequence']=1;source(dict(accepted=True,source=value.component))
        value.component['osDestinations']['snapshotOsDestinationsVersion']=2;source(dict(accepted=True,source=value.component))
    def test_other_saf_authorities_client_owner_claims_wrong_scope_and_unissued_delete_are_red(self):
        changes=[dict(providerPackage='org.foreign'),dict(ownerPackage='io.github.noah_be.overte.phone'),dict(storage='SAF'),dict(runId='f'*32),
            dict(documentId='old-document'),dict(displayName='foreign.png'),dict(createUid=0),dict(createdEpochMs=0),dict(expectedWriter=1001)]
        for change in changes:
            value=document_boundary();value.component['osDestinations']['rows'][0]['identity'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source(dict(accepted=True,source=value.component))
        for change in (dict(snapshotOsDestinationsVersion=1),dict(snapshotOsDestinationsVersion=True)):
            value=document_boundary();value.component['osDestinations'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source(dict(accepted=True,source=value.component))
    def test_document_bytes_above_32mib_and_missing_original_cannot_retire(self):
        for change in (dict(original=dict(bytes=32*1024*1024+1,sha256='1'*64)),dict(original=None),dict(deleteIssued=False)):
            value=document_boundary();value.component['osDestinations']['rows'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source(dict(accepted=True,source=value.component))


if __name__=='__main__':unittest.main()
