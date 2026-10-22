#!/usr/bin/env python3
"""Build the standalone fixture with an existing SDK only; never install it."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[4]
FIXTURE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sdk',type=Path,required=True)
parser.add_argument('--build-dir',type=Path,required=True)
args=parser.parse_args()
build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=False)
platform=args.sdk/'platforms/android-34/android.jar';tools=args.sdk/'build-tools/36.0.0'
classes=build/'classes';classes.mkdir();dex=build/'dex';dex.mkdir()
sources=sorted((FIXTURE/'java').rglob('*.java'))+[ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotReadbackFiles.java']
def run(command):subprocess.run(list(map(str,command)),check=True,timeout=60)
run(['javac','--release','8','-classpath',platform,'-d',classes,*sources])
jar=build/'classes.jar'
with zipfile.ZipFile(jar,'w') as archive:
    for path in sorted(classes.rglob('*.class')):archive.write(path,path.relative_to(classes))
run([tools/'d8','--lib',platform,'--min-api','26','--output',dex,jar])
apk=build/'snapshot-receiver-unsigned.apk'
run([tools/'aapt2','link','-I',platform,'--manifest',FIXTURE/'AndroidManifest.xml','-o',apk])
with zipfile.ZipFile(apk,'a') as archive:archive.write(dex/'classes.dex','classes.dex')
report=dict(schemaVersion=1,apk=str(apk),apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
    sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources+[FIXTURE/'AndroidManifest.xml',Path(__file__).resolve()]},
    androidExecution=False,signed=False)
(build/'source-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(apk=str(apk),apkSha256=report['apkSha256'],signed=False,androidExecution=False)))
