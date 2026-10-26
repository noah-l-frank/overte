"""Pure Share replay over retained host originals; native/OS producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain,RUN,SYSTEM_UI


class SnapshotShareHistoryTests(unittest.TestCase):
    def completed(self,cleanup=False):
        domain=SnapshotShareDomain(self);domain.activate('share-open','1'*32)
        with domain.owner() as owner:owner.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as owner:
            proof=owner.select('2'*32);retired=owner.cleanup() if cleanup else None
        return domain,proof,retired

    def reader(self,domain,**changes):
        args=dict(store=PrivateFeatureState(domain.main.ctx.root/'snapshot-share-owner.json'),lock=domain.main.ctx.lock,
            archive_lock=domain.archive.source_lock,binding=domain.main.ctx.binding,archive_binding=domain.archive.binding,
            run=RUN,fixture_url=domain.archive.fixture_url,system_ui=SYSTEM_UI,primary_bundle=domain.primary.target['appId'],
            artifact_path=domain.archive.ipa,admission_store=domain.archive.admission_store)
        args.update(changes);return IOSSnapshotShareOwner.history(**args)

    def snapshot(self,domain):
        return {path:(path.stat().st_ino,path.stat().st_mtime_ns,path.read_bytes())
            for root in (domain.main.ctx.root,domain.archive.session.path.parent) for path in root.iterdir() if path.is_file()}

    def test_complete_transfer_and_retirement_replay_without_any_live_source_or_write(self):
        domain,proof,retired=self.completed(cleanup=True)
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held(),ExitStack() as stack:
            before=self.snapshot(domain)
            for obj,name in ((domain.primary,'probe'),(domain.primary,'foreground_sources'),(domain.primary,'activate'),
                    (domain.runtime,'_sources'),(domain.primary_ui,'call'),(domain.archive,'call'),
                    (domain.archive.node,'call'),(SnapshotShareArchiveContext,'__init__'),(PrivateFeatureState,'write')):
                stack.enter_context(patch.object(obj,name,side_effect=AssertionError('Pure Share history reached live '+name)))
            owner=self.reader(domain);self.assertTrue(owner.historical);self.assertTrue(owner.guard())
            self.assertEqual(proof,owner.proof());self.assertEqual(retired,owner.cleanup_proof());state=deepcopy(owner.state)
            for operation in (lambda:owner.open('3'*32),lambda:owner.cancel('3'*32),lambda:owner.select('2'*32),owner.cleanup,
                    owner.save,owner.archive_runtime,lambda:owner.read_archive('new','snapshot-share-chunk.json',262144)):
                with self.subTest(operation=operation),self.assertRaises(NativeUIError):operation()
                self.assertEqual(state,owner.state)
            self.assertEqual(before,self.snapshot(domain))

    def test_wrong_outer_bindings_original_replacement_and_extra_source_are_not_adopted(self):
        domain,proof,_retired=self.completed()
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            before=self.snapshot(domain)
            for change in (dict(run='0'*32),dict(primary_bundle='org.foreign.client'),
                    dict(binding={**domain.main.ctx.binding,'processIdentity':'99'}),
                    dict(archive_binding={**domain.archive.binding,'processIdentity':'99'}),
                    dict(system_ui={**SYSTEM_UI,'cancel':dict(using='accessibility id',value='Foreign Cancel')})):
                with self.subTest(change=change),self.assertRaises(NativeUIError):self.reader(domain,**change)
                self.assertEqual(before,self.snapshot(domain))
            owner=self.reader(domain);self.assertEqual(proof,owner.proof())
            foreign=domain.archive.session.path.parent/'share-archive-source-unowned.json'
            foreign.write_bytes(b'An actual undeclared source file');foreign.chmod(0o600);changed=self.snapshot(domain)
            with self.assertRaises(NativeUIError):self.reader(domain)
            self.assertEqual(changed,self.snapshot(domain));foreign.unlink()
            row=owner.state['archiveSources'][0];path=owner.files.path(owner.files.expand(row['proof']))
            replacement=path.with_name('replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
            changed=self.snapshot(domain)
            with self.assertRaises(NativeUIError):self.reader(domain)
            with self.assertRaises(NativeUIError):owner.proof()
            self.assertEqual(changed,self.snapshot(domain))


if __name__=='__main__':unittest.main()
