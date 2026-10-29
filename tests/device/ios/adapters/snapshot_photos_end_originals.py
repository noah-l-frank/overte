"""Original-only factory from independently selected recorded scope/config.

No SDK/runtime/context object is accepted. Raw owner headers are not used as
expected bindings; callers must supply their independently selected scopes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,nullcontext
from copy import deepcopy
from pathlib import Path
import stat
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney
from ios.adapters.snapshot_combined_photos_journey import SnapshotCombinedPhotosJourney
from ios.adapters.snapshot_photos_end_owner import SnapshotPhotosEndOwner


class SnapshotPhotosEndOriginals:
    def __init__(self,main,photos,archive,*,run,fixture_url,primary_bundle,system_ui,domain_policy,reuse_originals=False):
        need(type(reuse_originals) is bool);self.reuse_originals=reuse_originals;self.last_read_counts=None
        exact(main,{'root','binding'})
        for value in (photos,archive):exact(value,{'root','binding','artifactPath','sessionPath','admissionPath','target'})
        self.main,self.photos,self.archive=deepcopy(main),deepcopy(photos),deepcopy(archive)
        self.run,self.fixture_url=identifier(run),fixture_url;self.primary_bundle=primary_bundle
        self.system_ui,self.domain_policy=deepcopy(system_ui),deepcopy(domain_policy)
        self.roots={key:Path(value['root']) for key,value in (('main',self.main),('photos',self.photos),('archive',self.archive))}
        need(len(set(self.roots.values()))==3)
        self.locks={};self.lock_pins={}
        for key,value in (('main',self.main),('photos',self.photos),('archive',self.archive)):
            context(value['binding']);root=self.roots[key];PrivateFeatureState(root/'original-only-boundary')._parent()
            path=root/'script-feature-sources.lock';row=path.lstat()
            # Reject before ScriptSourceLock can create a missing lock. This
            # factory reuses only the existing original private inode.
            need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_size==0 and stat.S_IMODE(row.st_mode)==0o600)
            self.lock_pins[key]=(row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink,row.st_size)
            self.locks[key]=ScriptSourceLock(path)
        for key,value in (('photos',self.photos),('archive',self.archive)):
            need(Path(value['sessionPath']).parent==self.roots[key] and Path(value['admissionPath']).parent==self.roots[key]
                and digest(value['target'])==value['binding']['targetFingerprint'])
    def helper(self,value):
        return dict(client=None,sessionStore=PrivateFeatureState(Path(value['sessionPath'])),target=deepcopy(value['target']),
            binding=deepcopy(value['binding']),artifactPath=Path(value['artifactPath']),admissionStore=PrivateFeatureState(Path(value['admissionPath'])))
    def check_locks(self):
        for key,lock in self.locks.items():
            row=lock.path.lstat();need((row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink,row.st_size)==self.lock_pins[key])
    @contextmanager
    def read_journey(self):
        locks=self.locks
        self.check_locks()
        with locks['main'].held(),locks['archive'].held(),locks['photos'].held():
            self.check_locks()
            with self.read_area() as area:
                with self._journey() as journey:yield journey
            self.last_read_counts=None if area is None else dict(area.counts)
            self.check_locks()
    def read_area(self):
        if not self.reuse_originals:return nullcontext()
        from ios.adapters.snapshot_photos_end_read_area import scope
        return scope(self.roots,self.locks,{name:value['binding'] for name,value in
            (('main',self.main),('photos',self.photos),('archive',self.archive))},self.run,self.fixture_url)
    @contextmanager
    def _journey(self):
        roots=self.roots;locks=self.locks;binding=self.main['binding'];run=self.run;url=self.fixture_url
        page=IOSSnapshotPageOwner.archive(PrivateFeatureState(roots['main']/'ios-snapshot-page-owner.json'),locks['main'],binding,run,url,combined=True)
        files=IOSSnapshotJourneyFilesOwner.archive(PrivateFeatureState(roots['main']/'ios-snapshot-journey-files-owner.json'),locks['main'],binding,run,url,combined=True)
        share=IOSSnapshotShareOwner.history(PrivateFeatureState(roots['main']/'snapshot-share-owner.json'),locks['main'],locks['archive'],binding,self.archive['binding'],
            run,url,self.system_ui,self.primary_bundle,Path(self.archive['artifactPath']),PrivateFeatureState(Path(self.archive['admissionPath'])),combined=True)
        archive_end=SnapshotShareArchiveEndOwner.history(share,self.helper(self.archive))
        returned=SnapshotPageReturnOwner.history(page,files,archive_end,combined=True)
        native=IOSSnapshotUploadOwner.history(PrivateFeatureState(roots['main']/'snapshot-upload-owner.json'),locks['main'],binding,run,url,
            combined=True,frontend_http=True,frontend_caller=True)
        backend=IOSSnapshotUploadBackendOwner.history(native,domain_policy=self.domain_policy)
        photo=SnapshotPhotosArchive.history(PrivateFeatureState(roots['main']/'photos-save-owner.json'),locks['main'],locks['photos'],binding,self.photos['binding'],
            run,url,Path(self.photos['artifactPath']),PrivateFeatureState(Path(self.photos['admissionPath'])),self.primary_bundle)
        journey=SnapshotCombinedPhotosJourney(SnapshotCombinedJourney(returned,backend),photo)
        yield journey
    @contextmanager
    def read(self):
        with self.read_journey() as journey:
            ended=SnapshotPhotosEndOwner.history(journey,self.helper(self.photos))
            yield ended
