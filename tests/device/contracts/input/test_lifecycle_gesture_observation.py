#!/usr/bin/env python3
"""Compile actual Pico axis hook/history; XR status/owner are explicit host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
with tempfile.TemporaryDirectory(prefix='lifecycle-gesture-') as directory:
    private=Path(directory);private.chmod(0o700)
    script=private/'overte_e2e_probe.js';script.write_text('// Explicit native host boundary, never executed.\n');script.chmod(0o600)
    inputs=private/'openxr-input';inputs.mkdir(mode=0o700)
    # Full original-format layer output is an explicit native producer seam.
    status=dict(schemaVersion=1,buildMarker='OVERTE_E2E_OPENXR_INPUT_V1',consumer='XR_APILAYER_OVERTE_e2e_input',
        profileId='overte-pico4-controller-v1',bindingProfileSha256='da7ef170275af8c058da53210c8a88aa6920e6315b5cdc0daaedf072dc1b3284',
        enabled=True,acceptedSequence=1,acceptedNonce='f'*64,activeCommandId='input-move-1',state='active',detail='vector-consumed',
        updatedEpochMs=1,viewAppliedSequence=0,viewAppliedYawDegrees=0,viewAppliedPitchDegrees=0,vectorAppliedSequence=1,
        leftThumbstickAppliedX=0,leftThumbstickAppliedY=.8,booleanAppliedSequence=0,leftSecondaryApplied=False,rightSecondaryApplied=False)
    status_file=inputs/'status.json';status_file.write_text(json.dumps(status)+'\n');status_file.chmod(0o600)
    source=(ROOT/'android/vr/pico/apps/picoInterface/openxr/src/OpenXrInputPlugin.cpp').read_text()
    start=source.index('    std::vector<std::tuple<std::string, StandardAxisChannel, StandardAxisChannel>> axesToUpdate = {')
    end=source.index('    std::vector<std::pair<std::string, StandardButtonChannel>> buttonsToUpdate = {',start)
    (private/'original-pico-gesture-axis.inc').write_text(source[start:end])
    begin=source.index('XrActionStateVector2f OpenXrInputPlugin::Action::getVector2f() {')
    end=source.index('XrActionStateBoolean OpenXrInputPlugin::Action::getBool()',begin)
    body=source[begin:end];body=body[body.index('{')+1:body.rfind('}')]
    (private/'original-pico-vector-query.inc').write_text(body)
    binary=private/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DOVERTE_E2E_OPENXR_INPUT_V1=1',
        '-I'+str(ROOT),'-I'+str(private),str(Path(__file__).with_name('lifecycle-gesture-observation-test.cpp')),
        str(ROOT/'libraries/controllers/src/controllers/AxisValue.cpp'),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    subprocess.run([str(binary)],check=True,timeout=10,env=environment)
    subprocess.run([str(binary),'--testScript',str(script),'--testResultsLocation',str(private)],check=True,timeout=10,env=environment)
