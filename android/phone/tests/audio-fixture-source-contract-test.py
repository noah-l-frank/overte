#!/usr/bin/env python3
"""Compile the actual E2E PCM/HTTP headers in an owned host build directory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import shlex
import subprocess
import uuid


def method(source,signature):
    start=source.index(signature);opening=source.index('{',start);depth=1;end=opening+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build-dir',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[3];build=(args.build_dir or root/'build'/('audio-source-contract-'+uuid.uuid4().hex)).absolute()
    if not build.is_relative_to(root/'build') or build.resolve()!=build or build.exists():raise SystemExit('A NEW owned worktree build directory is required')
    build.mkdir(parents=True)
    audio=(root/'libraries/audio-client/src/AudioClient.cpp').read_text();test=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    signatures=['bool AudioClient::recordedVoiceTestInputAvailable() const',
        'QVariantMap AudioClient::phoneAudioFixtureObservation() const','bool AudioClient::armPhoneAudioFixture(',
        'void AudioClient::releasePhoneAudioFixture()']
    extracted='\n'.join(method(audio,signature) for signature in signatures)
    extracted+='\n'+method(test,'QVariantMap TestScriptingInterface::phoneAudioFixture(')
    (build/'original-entry.inc').write_text(extracted)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Network'],text=True))
    output=build/'phone-audio-source-contract'
    subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-DOVERTE_E2E_VOICE_TESTS=1',
        '-DAUDIO_ORIGINAL_ENTRY="'+str(build/'original-entry.inc')+'"',str(Path(__file__).with_suffix('').with_name('audio-fixture-source-contract.cpp')),'-o',str(output),*flags],check=True)
    subprocess.run([str(output)],check=True,timeout=15)
    subprocess.run([str(output),'--testScript'],check=True,timeout=15)


if __name__=='__main__':main()
