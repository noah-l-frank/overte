"""Explicit normal-upload diagnostic; original failure remains nonzero.

Requires a pre-existing private evidence root and the existing Qt host inputs.
No installation, service, physical device or Asset Server/oven is started.
The protocol/cache and fixture transport are declared host endpoints. The
Cancel input/file archive retains every exact command for this diagnosis; this
is not a complete durable Upload owner or v16 journey. Ending this owned host
process cannot qualify same-process product retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse,hashlib,json,os,stat,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(HERE),str(ROOT/'tests/device')]
from test_assets_native_ui import compile_ui
from test_assets_cancel_owner import OriginalPhaseClient,LIVE
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal
from urllib.parse import urlsplit,unquote
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-dir',type=Path,required=True)
parser.add_argument('--sanitize',action='store_true',help='Use only an already installed AddressSanitizer; never installs a runtime.')
options=parser.parse_args();evidence=options.evidence_dir
info=evidence.lstat()
assert stat.S_ISDIR(info.st_mode) and not evidence.is_symlink() and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700
stage=Path(tempfile.mkdtemp(prefix='assets-upload-worker-',dir=evidence))
print('Diagnostic retained evidence:',stage,flush=True)
binary,environment,args=compile_ui(stage,original_uploads=True,sanitize=options.sanitize)
if options.sanitize:environment['ASAN_OPTIONS']='detect_leaks=0'
hostdir=stage/'live';hostdir.mkdir(mode=0o700)
host=LIVE.AssetsLiveHost(binary,environment,args,hostdir)
try:
    current=host.navigation.snapshot()
    binding=dict(sourceRevision='f8cd43a02da492fc326f3f86ccebcfd223d3bacf',artifactSha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        processIdentity=host.identity,sessionId=current['bridgeId'],generation=0,targetFingerprint='d'*64)
    journal=Journal();run=journal.register('assets');ticket='1'*32
    journal.activate(run,ticket,'upload-picker-open',{'resource':'gltf-bundle/main.gltf'})
    client=OriginalPhaseClient(journal,run);url=client.url+'/runs/'+run+'/'
    files=OwnedAssetsFiles(host.files(),PrivateFeatureState(hostdir/'files.json'),binding,run,ticket,url)
    store=PrivateFeatureState(hostdir/'input-owner.json')
    owner=OwnedAssetsCancel(store,binding,run,url,files,host.mappings(),host.uploads(),host.io.original.capture,host.controls,
        PhaseFixtureReader(client,run,'assets'),host.guard,host.epoch_milliseconds)
    owner.open();journal.activate(run,'2'*32,'upload',{'resource':'gltf-bundle/main.gltf'})
    state=owner.state();state['phaseOriginal']=owner.admit('upload')['status'];owner.write(state)
    root=unquote(urlsplit(owner.state()['directory']).path)
    ui=owner.ui()
    for folder,name in [('mesh','triangle.bin'),('textures','checker.png')]:
        ui.navigate_files(root+'/gltf-bundle/'+folder);ui.select_file(owner.state()['directory']+'/gltf-bundle/'+folder+'/'+name)
    ui.review_bundle('main.gltf');ui.destination('/e2e-'+run+'/')
    observed=owner.sample();owner.check_sample(observed)
    result=hostdir/'observed.json';result.write_text(json.dumps(observed,sort_keys=True));os.chmod(result,0o600)
    print('Original worker/GUI callback diagnostic returned; original packet retained',flush=True)
    assert all(bundle['errorSha256']==hashlib.sha256(b'').hexdigest() for bundle in observed['uploads']['source']['bundles']),'Original normal upload failed; exact input/file/source ownership retained'
finally:
    host.close()
