"""Historical context capacity, unchanged v1 and unresolved physical owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_archive_context import BrowserArchiveContext,read_context
from adapters.pico4.browser_evidence_archive import metadata_pngs
from adapters.chat_journey.source_chunks import digest,json_digest
from adapters.script_journey.history import canonical,pack,MAX_PACKED,MAX_RAW


class BrowserArchiveContextTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=PrivateFeatureState(self.root/'context.json');self.run='a'*32

    def data(self):
        return {'originals':[hashlib.sha256(str(index).encode()).hexdigest() for index in range(2200)]}

    def test_large_exact_original_uses_existing_parts_without_raising_limits(self):
        data=self.data()
        with self.assertRaises(NativeUIError):pack([data])
        owner=BrowserArchiveContext(self.store,self.run,data)
        self.assertGreater(len(owner.chunks.identities),1)
        self.assertEqual(data,read_context(self.store,self.run));owner.verify()
        self.assertEqual(MAX_RAW,16*1024*1024);self.assertEqual(MAX_PACKED,48*1024)
        self.assertEqual('ready',owner.previous['phase'])
        for store in owner.stores():self.assertLessEqual(store.path.stat().st_size,65536)
        for index in range(len(owner.chunks.identities)):
            self.assertLessEqual(len(owner.chunks.store(index).read()['transcript']['data']),MAX_PACKED)

    def test_original_v1_bytes_read_without_rewrite_or_migration(self):
        data={'originals':[{'nonce':'b'*32,'capturedEpochMs':20000}]}
        value=dict(picoBrowserArchiveContextVersion=1,runId=self.run,payload=pack([data]))
        self.store.write(value,None);raw=self.store.path.read_bytes();info=self.store.path.stat()
        self.assertEqual(data,read_context(self.store,self.run))
        after=self.store.path.stat();self.assertEqual(raw,self.store.path.read_bytes())
        self.assertEqual((info.st_ino,info.st_mtime_ns,info.st_ctime_ns),(after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        with self.assertRaises(NativeUIError):BrowserArchiveContext(self.store,self.run,data)

    def test_lost_landed_child_preserves_reading_and_orphan_without_cold_adoption(self):
        write=PrivateFeatureState.write;landed=[]
        def lost(store,value,previous):
            write(store,value,previous)
            if '.frame-' in store.path.name:
                landed.append(store.path);raise NativeUIError('Original child response lost after durable write')
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(NativeUIError):
            BrowserArchiveContext(self.store,self.run,self.data())
        self.assertEqual(1,len(landed));self.assertTrue(landed[0].exists())
        self.assertEqual('reading',self.store.read()['phase']);self.assertEqual([],self.store.read()['chunks'])
        before={path:path.read_bytes() for path in self.root.iterdir()}
        with self.assertRaises(NativeUIError):read_context(self.store,self.run)
        with self.assertRaises(NativeUIError):BrowserArchiveContext(self.store,self.run,self.data())
        self.assertEqual(before,{path:path.read_bytes() for path in self.root.iterdir()})

    def test_same_bytes_replacement_child_is_not_the_warm_original(self):
        owner=BrowserArchiveContext(self.store,self.run,self.data());path=owner.chunks.store(0).path
        original=path.read_bytes();inode=path.stat().st_ino;replacement=self.root/'replacement'
        replacement.write_bytes(original);replacement.chmod(0o600);replacement.replace(path)
        self.assertNotEqual(inode,path.stat().st_ino);self.assertEqual(original,path.read_bytes())
        with self.assertRaises(NativeUIError):owner.verify()
        with self.assertRaises(NativeUIError):owner.stores()
        self.assertEqual('ready',self.store.read()['phase'])

    def test_complete_png_inventory_reference_fits_root_without_omission_and_keeps_v1(self):
        pngs=[dict(role='primary',value=dict(name=f'capture-{index}.png',
            original=[hashlib.sha256(f'{index}:{part}'.encode()).hexdigest() for part in range(16)]),stamp=[index]*8)
            for index in range(80)]
        legacy=dict(picoBrowserEvidenceArchiveVersion=1,pngs=pngs)
        self.assertGreater(len(canonical(legacy)),65536)
        self.assertEqual(pngs,metadata_pngs(legacy,None))
        context=dict(source={'originals':self.data()},pngs=pngs)
        owner=BrowserArchiveContext(self.store,self.run,context);data=read_context(self.store,self.run)
        metadata=dict(picoBrowserEvidenceArchiveVersion=2,contextSha256=digest(data),
            pngCount=len(pngs),pngsSha256=json_digest(pngs))
        self.assertLess(len(canonical(metadata)),65536)
        self.assertEqual(pngs,metadata_pngs(metadata,data));owner.verify()
        for field,value in (('pngCount',79),('pngsSha256','0'*64),('contextSha256','f'*64)):
            with self.subTest(field=field),self.assertRaises(NativeUIError):
                metadata_pngs({**metadata,field:value},data)
        changed=deepcopy(data);changed['pngs'].pop()
        with self.assertRaises(NativeUIError):metadata_pngs(metadata,changed)
        changed=deepcopy(data);changed['pngs']=tuple(changed['pngs'])
        with self.assertRaises(NativeUIError):metadata_pngs(metadata,changed)
        single=dict(source={},pngs=pngs[:1])
        with self.assertRaises(NativeUIError):
            metadata_pngs(dict(picoBrowserEvidenceArchiveVersion=2,contextSha256=digest(single),
                pngCount=True,pngsSha256=json_digest(single['pngs'])),single)
        self.assertEqual(context,read_context(self.store,self.run))


class BrowserArchivePngWindowTests(unittest.TestCase):
    """Historical full-byte windows only; no live image/source is produced."""
    def setUp(self):
        import io
        import os
        from types import MethodType,SimpleNamespace
        from PIL import Image
        from adapters.chat_journey.archive_file import signature
        from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
        from adapters.native_fd_owner import OriginalDescriptor
        from adapters.pico4.browser_evidence_archive import PicoBrowserEvidenceArchive
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.parent=Path(temporary.name);self.root=self.parent/'originals';self.root.mkdir(mode=0o700)
        stream=io.BytesIO();Image.new('RGBA',(2,2),(17,33,55,255)).save(stream,format='PNG');self.raw=stream.getvalue()
        self.path=self.root/'original.png';self.path.write_bytes(self.raw);self.path.chmod(0o600)
        info=self.path.stat();value=dict(name=self.path.name,bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),
            file=dict(device=info.st_dev,inode=info.st_ino))
        rows=[dict(value=value,stamp=signature(info))]
        primary=SimpleNamespace(artifact_root=self.root)
        primary._original_image_bytes=MethodType(PicoTabletWebFeature._original_image_bytes,primary)
        self.plan=PicoBrowserEvidenceArchive.__new__(PicoBrowserEvidenceArchive)
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        captures=PicoBrowserCaptureRetirement.__new__(PicoBrowserCaptureRetirement)
        captures.admitted=captures.reader=captures.previous=None;captures.initialize_pngs()
        for row in rows:captures.append_png(row)
        self.plan.root=self.root;self.plan.primary=primary;self.plan.captures=captures
        self.plan.metadata=dict(pngsSha256=json_digest(rows),pngCount=len(rows))
        self.plan.catalog=ChatArchiveCatalog(hold_files=False)
        self.directory=OriginalDescriptor(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.addCleanup(self.directory.close);self.plan.catalog.parents[self.root]=self.directory

    def test_full_original_bytes_use_actual_owned_parent_then_independent_reader_after_close(self):
        reader=self.plan.primary._original_image_bytes
        with patch.object(self.plan.primary,'_original_image_bytes',wraps=reader) as reads:
            self.plan.pngs();self.assertIs(self.directory,reads.call_args.kwargs['directory'])
            self.assertEqual(self.raw,self.path.read_bytes())
            self.assertTrue(self.directory.close());self.plan.pngs()
            self.assertNotIn('directory',reads.call_args.kwargs)
        self.assertEqual(self.raw,self.path.read_bytes())

    def test_same_bytes_replaced_png_is_refused_without_removing_either_original(self):
        original=self.path.stat().st_ino;replacement=self.root/'replacement.png'
        replacement.write_bytes(self.raw);replacement.chmod(0o600);replacement.replace(self.path)
        self.assertNotEqual(original,self.path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.plan.pngs()
        self.assertEqual(self.raw,self.path.read_bytes());self.assertFalse(self.directory.closed)

    def test_parent_replacement_after_actual_full_read_cannot_pass_final_inventory(self):
        reader=self.plan.primary._original_image_bytes;retained=self.parent/'retained-originals'
        def moved(*args,**kwargs):
            value=reader(*args,**kwargs);self.root.rename(retained);self.root.mkdir(mode=0o700)
            replacement=self.root/self.path.name;replacement.write_bytes(self.raw);replacement.chmod(0o600)
            return value
        with patch.object(self.plan.primary,'_original_image_bytes',side_effect=moved),self.assertRaises(NativeUIError):
            self.plan.pngs()
        self.assertEqual(self.raw,(retained/self.path.name).read_bytes())
        self.assertEqual(self.raw,self.path.read_bytes());self.assertFalse(self.directory.closed)

    def test_inspection_cannot_change_original_png_scope_and_projected_windows_have_no_mutable_alias(self):
        captures=self.plan.captures;inspection=captures.pngs
        inspection[0]['value']['sha256']='f'*64;inspection[0]['stamp'][1]+=1
        original_sha,windows=captures.original_png_windows()
        self.assertEqual(self.plan.metadata['pngsSha256'],original_sha)
        windows[0][0]['sha256']='e'*64;windows[0][1][1]+=1
        self.plan.pngs();self.assertEqual(self.raw,self.path.read_bytes())
        self.assertNotEqual(inspection,captures.pngs)
        captures._png_windows=tuple([*captures._png_windows, captures._png_windows[0]])
        with self.assertRaises(NativeUIError):self.plan.pngs()

    def test_new_foreign_json_alias_or_late_capture_cannot_change_the_admitted_inventory(self):
        captures=self.plan.captures;original=captures.pngs;row=deepcopy(original[0])
        row['stamp']=tuple(row['stamp'])
        with self.assertRaises(NativeUIError):captures.append_png(row)
        self.assertEqual(original,captures.pngs);self.plan.pngs()
        captures.admitted=b'actual admitted original inventory'
        with self.assertRaises(NativeUIError):captures.append_png(original[0])
        self.assertEqual(original,captures.pngs);self.plan.pngs()


class BrowserArchiveNamespaceTests(unittest.TestCase):
    """Actual namespace/marker files; context/source/PNG producers are seams."""
    def make(self):
        from types import SimpleNamespace
        from adapters.observer_return import parent_node,state
        from adapters.pico4.browser_evidence_archive import PicoBrowserEvidenceArchive
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        parent=Path(temporary.name);root=parent/'artifacts';root.mkdir(mode=0o700)
        prefix='tablet-web-'+('a'*32)+'-'
        plan=PicoBrowserEvidenceArchive.__new__(PicoBrowserEvidenceArchive)
        plan.primary=SimpleNamespace(store=PrivateFeatureState(parent/'pico-tablet-web-primary.json'))
        plan.primary.store.write({'original':'primary'},None)
        plan.root=root;plan.prefix=prefix
        plan.sentry=PrivateFeatureState(parent/'pico-tablet-web-archive-owner.json')
        plan.sentry_value={'original':'sentry'};plan.sentry.write(plan.sentry_value,None)
        plan.sentry_parent=parent_node(plan.sentry)
        plan.context=PrivateFeatureState(root/(prefix+'archive-context.json'))
        plan.context_value={'original':'context'};plan.context.write(plan.context_value,None)
        plan.context_stamp=state(plan.context)[2]
        source=PrivateFeatureState(root/(prefix+'archive-release.json'));source.write({'original':'source'},None)
        plan.source=SimpleNamespace(store=source,chunks=SimpleNamespace(identities=[]))
        plan.context_owner=SimpleNamespace(stores=lambda:[])
        plan.store=PrivateFeatureState(root/(prefix+'archive-complete.json'));plan.parent=parent_node(plan.store)
        plan.marker=PrivateFeatureState(root/(prefix+'archive-intent.json'));plan.directory=root/(prefix+'source-archive')
        observed=[];plan.pngs=lambda:observed.append('full-original-PNG-boundary')
        artifact=PrivateFeatureState(root/(prefix+'known.json'));artifact.write({'original':'artifact'},None)
        return plan,{plan.primary.store.path,artifact.path},observed

    def test_matching_orphan_files_directories_and_symlinks_block_both_complete_namespace_scans(self):
        for where in ('state','artifacts'):
            for kind in ('file','directory','symlink'):
                with self.subTest(where=where,kind=kind):
                    plan,remaining,observed=self.make();plan.inventory(remaining)
                    parent=plan.primary.store.path.parent if where=='state' else plan.root
                    prefix='pico-tablet-web-' if where=='state' else plan.prefix
                    orphan=parent/(prefix+'unknown-pending')
                    if kind=='file':orphan.write_bytes(b'original foreign file')
                    elif kind=='directory':orphan.mkdir()
                    else:orphan.symlink_to('missing-foreign-target')
                    with self.assertRaises(NativeUIError):plan.inventory(remaining)
                    self.assertEqual(1,len(observed));self.assertTrue(all(path.exists() for path in remaining))
                    self.assertTrue(orphan.is_symlink() if kind=='symlink' else orphan.exists())

    def test_other_namespaces_remain_separate_and_same_name_in_foreign_parent_cannot_replace_original(self):
        plan,remaining,observed=self.make()
        (plan.root/'unrelated-other-feature').write_bytes(b'unrelated original')
        (plan.primary.store.path.parent/'other-namespace').mkdir()
        plan.inventory(remaining);self.assertEqual(1,len(observed))
        original=next(path for path in remaining if path.parent==plan.root)
        foreign=plan.primary.store.path.parent/original.name;original.rename(foreign)
        with self.assertRaises(NativeUIError):plan.inventory(remaining)
        self.assertEqual(1,len(observed));self.assertEqual(b'{"original":"artifact"}\n',foreign.read_bytes())
