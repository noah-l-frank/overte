"""Fresh-process parser baselines; empty actual IO scopes, no End authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from ios.self_tests.retained_host_roots import retain_owned_root


CHILD=r"""
import ast,hashlib,importlib.abc,importlib.machinery,json,os,sys
from pathlib import Path
repo=Path(sys.argv[3]).resolve(strict=True);root=Path(sys.argv[1]).resolve(strict=True)
expected=json.loads((root/'child-source-pins.json').read_text())
fields=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()
(root/'child-process.json').write_text(json.dumps(dict(pid=os.getpid(),parentPid=os.getppid(),
 processGroup=os.getpgrp(),session=os.getsid(0),startTicks=int(fields[19]))))
ordered=[str(repo/name) for name in ('tests/device','tests/device/self_tests','tests/device/ios/self_tests')]
remaining=[]
for value in sys.path:
 path=Path(value or os.getcwd()).resolve()
 if path==repo or repo in path.parents:continue
 if str(path) not in remaining:remaining.append(str(path))
sys.path[:]=ordered+remaining
for name,relative in {'ios':'tests/device/ios','adapters':'tests/device/adapters','feature_journeys':'tests/device/feature_journeys'}.items():
 spec=importlib.machinery.PathFinder._get_spec(name,list(sys.path))
 assert spec is not None and list(spec.submodule_search_locations or ())==[str(repo/relative)],name
parent=repo/'tests/device/ios/self_tests/test_ios_snapshot_photos_end_cold_parser_scope.py'
assert hashlib.sha256(parent.read_bytes()).hexdigest()==expected[str(parent.relative_to(repo))]
parent_tree=ast.parse(parent.read_text())
child_assignment=next(node for node in parent_tree.body if isinstance(node,ast.Assign)
 and any(isinstance(target,ast.Name) and target.id=='CHILD' for target in node.targets))
assert hashlib.sha256(ast.literal_eval(child_assignment.value).encode()).hexdigest()==sys.argv[4]
imported={}
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,name,path=None,target=None):
  assert name.split('.',1)[0] not in ('pymobiledevice3','pmd_pytcp','pmd_pytcpstack','pytcp'),'No SDK imports'
  spec=importlib.machinery.PathFinder.find_spec(name,path)
  if spec is not None and spec.origin and spec.origin not in ('built-in','frozen'):
   actual=Path(spec.origin).resolve()
   if actual.is_relative_to(repo):
    relative=str(actual.relative_to(repo));assert relative in expected and hashlib.sha256(actual.read_bytes()).hexdigest()==expected[relative],name
    imported[name]=relative
  return None
sys.meta_path.insert(0,Guard())
from contextlib import ExitStack
from types import ModuleType
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState as source_store
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.snapshot_photos_end_originals import SnapshotPhotosEndOriginals
from ios.adapters import snapshot_photos_end_read_area as source
from adapters.native_feature_observation import validate
from ios.adapters import assets_controls
# Importing this EXISTING explicit in-memory producer calls no test or SDK.
# Its historical sys.path helper is restored immediately, not a foreign root.
paths=list(sys.path)
from self_tests.test_native_feature_observation import Boundary
sys.path[:]=paths
lazy=('adapters.native_animation_history','adapters.native_animation_caller',
 'ios.adapters.assets_bundle_controls','ios.adapters.assets_tree_controls','ios.adapters.assets_usage_controls',
 'ios.adapters.snapshot_pending_runtime')
assert all(name not in sys.modules for name in lazy),'Process must actually start cold'
root=Path(sys.argv[1]);mode=sys.argv[2]
roots={name:root/name for name in ('main','photos','archive')};locks={}
for name,path in roots.items():path.mkdir(mode=0o700);locks[name]=ScriptSourceLock(path/'script-feature-sources.lock')
binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned-session',generation=0,targetFingerprint='c'*64)
packet=Boundary();request='ios-'+'1'*32;packet.send(dict(commandId=request))
with ExitStack() as held:
 for lock in locks.values():held.enter_context(lock.held())
 with source.scope(roots,locks,{name:dict(binding) for name in roots},'a'*32,
        'https://controlled.invalid/feature-fixture/v1/runs/'+'a'*32+'/') as area:
  assert all(name in sys.modules for name in lazy),'Known actual lazy definitions missing at baseline'
  baseline=area.parsers
  # Actual consumers from the failing Page original path; no decoder/pin swap.
  validate(packet.sample,request,123,20000)
  assert assets_controls.control_id('snapshot.capture') is False
  from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
  missing=roots['main']/'pending-snapshot-owner.json';assert not missing.exists()
  # Actual historical factory from JourneyFiles.setup: imports its real
  # Pending runtime before refusing this missing original. No SDK/query or
  # fabricated Pending proof is substituted for that mandatory refusal.
  refused=False
  try:IOSSnapshotPendingOwner.archive(source_store(missing),locks['main'],binding,'a'*32,
        'https://controlled.invalid/feature-fixture/v1/runs/'+'a'*32+'/',combined=True)
  except NativeUIError:refused=True
  assert refused and not missing.exists()
  area.check();assert baseline==area.parser_module.parser_identity()
  if mode!='known-consumers':
   animation=sys.modules[lazy[0]];controls=sys.modules[lazy[2]]
   old_code=animation.clip.__code__;old_ids=controls.IDS;added=None
   try:
    if mode=='changed-code':
     def changed(value):return value
     animation.clip.__code__=changed.__code__
    elif mode=='changed-constant':controls.IDS=controls.IDS|{'assets.unreviewed-control'}
    elif mode=='unknown-late-module':
     added='ios.adapters.snapshot_unreviewed_late';assert added not in sys.modules
     sys.modules[added]=ModuleType(added)
    else:raise AssertionError('Unknown test mode')
    refused=False
    try:area.check()
    except NativeUIError:refused=True
    assert refused,'Full original parser guard was weakened'
   finally:
    animation.clip.__code__=old_code;controls.IDS=old_ids
    if added is not None:del sys.modules[added]
  if mode=='changed-code':
   # Independent SINGLE fault: all earlier native/constant mutations have
   # been restored. Pin the actual historical runtime class's wrapped body.
   pending=sys.modules['ios.adapters.snapshot_pending_runtime'].IOSSnapshotPendingRuntime.pending_owner.__wrapped__
   old_pending=pending.__code__;assert not pending.__closure__
   try:
    def changed_pending(value):return value
    pending.__code__=changed_pending.__code__
    refused=False
    try:area.check()
    except NativeUIError:refused=True
    assert refused,'Preloaded Pending runtime implementation was not pinned'
   finally:pending.__code__=old_pending
(root/'child-provenance.json').write_text(json.dumps(dict(imported=imported,parentTestSha256=expected[str(parent.relative_to(repo))],childCodeSha256=sys.argv[4],canonicalRoots=ordered),sort_keys=True))
print('ACTUAL_COLD_SCOPE_PASS',mode)
"""


class PhotosEndColdParserScopeTests(unittest.TestCase):
    def run_mode(self,mode):
        temporary=tempfile.TemporaryDirectory(prefix='photos-cold-parser-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);retain_owned_root(temporary,expected_root=root)
        repo=Path(__file__).resolve().parents[4]
        environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join(str(repo/name) for name in
            ('tests/device','tests/device/self_tests','tests/device/ios/self_tests')))
        # Root's whole source snapshot independently guards these actual
        # current public files before/after imports. Child additionally verifies
        # each actual local module and its own literal parent/CHILD source.
        source_pins={str(path.relative_to(repo)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((repo/'tests/device').rglob('*.py')) if '__pycache__' not in path.parts}
        (root/'child-source-pins.json').write_text(json.dumps(source_pins,sort_keys=True))
        result=subprocess.run([sys.executable,'-B','-c',CHILD,str(root),mode,str(repo),hashlib.sha256(CHILD.encode()).hexdigest()],cwd=repo,env=environment,
            capture_output=True,text=True,timeout=20)
        (root/'child-stdout.txt').write_text(result.stdout);(root/'child-stderr.txt').write_text(result.stderr)
        self.assertEqual(0,result.returncode,result.stdout+'\n'+result.stderr)
        self.assertIn('ACTUAL_COLD_SCOPE_PASS '+mode,result.stdout)
        binding=json.loads((root/'child-process.json').read_text());current=Path('/proc',str(binding['pid']),'stat')
        if current.exists():
            fields=current.read_text().rsplit(') ',1)[1].split()
            self.assertNotEqual(binding['startTicks'],int(fields[19]),'Original child remained live after wait')
        self.assertTrue((root/'child-provenance.json').is_file())
    def test_fresh_minimal_imports_keep_actual_native_and_assets_consumers_inside_original_baseline(self):self.run_mode('known-consumers')
    def test_preloaded_native_validator_code_change_still_refuses_current_scope(self):self.run_mode('changed-code')
    def test_preloaded_assets_constant_change_still_refuses_current_scope(self):self.run_mode('changed-constant')
    def test_unknown_parser_module_loaded_after_baseline_still_refuses_current_scope(self):self.run_mode('unknown-late-module')


if __name__=='__main__':unittest.main()
