#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Execute production hidden-avatar simulation, native override/cancel and outbound-cache path.

Actual Qt locks/threads, GLM and JointData are used. Rig/model animation math,
rendering, scene/camera and packet transport are explicit endpoint fixtures. The
complete actual AvatarManager update method drives the simulation slice and
copies the actual AvatarData outbound joint-cache section. This proves that
hiding the local mesh does not suppress required simulation/copy/send work; it
does not claim an actual animated peer, skeleton implementation or network codec.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=HERE.parents[3])
parser.add_argument('--output', type=Path)
parser.add_argument('--source-ref', help='Read production bodies at an exact local revision for a negative control')
args = parser.parse_args()
root = args.root.resolve()
major = os.environ.get('OVERTE_NATIVE_QT_MAJOR', '6')
if major not in ('5', '6'):
    raise RuntimeError('OVERTE_NATIVE_QT_MAJOR must be 5 or 6')

def block(source, marker):
    start = source.index(marker)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

paths = ['interface/src/avatar/MyAvatar.cpp', 'interface/src/avatar/MyAvatar.h',
         'interface/src/avatar/AvatarManager.cpp', 'libraries/avatars/src/AvatarData.cpp',
         'libraries/shared/src/JointData.h', 'libraries/avatars/src/AvatarHashMap.h',
         'libraries/shared/src/NumericalConstants.h', 'libraries/avatars/src/AvatarData.h']
sources = {path: (subprocess.check_output(['git', 'show', args.source_ref + ':' + path], cwd=root, text=True)
                  if args.source_ref else (root / path).read_text()) for path in paths}
my, header, manager, data = (sources[path] for path in paths[:4])
start = my.index('    updateSensorToWorldMatrix();', my.index('void MyAvatar::simulate('))
start += len('    updateSensorToWorldMatrix();')
end = my.index('    // Record avatars movements.', start)
simulation = my[start:end]
start = data.index('    QVector<JointData> jointData;', data.index('QByteArray AvatarData::toByteArray('))
end = data.index('    const int numJoints', start)
packet_cache = data[start:end]
methods = '\n'.join(block(my, marker) for marker in (
    'void MyAvatar::overrideAnimation(', 'void MyAvatar::restoreAnimation(', 'void MyAvatar::render('))
set_visibility = block(header, '    void setShouldRenderLocally(')
get_visibility = block(header, '    bool getShouldRenderLocally(')
send_rate='\n'.join(re.findall(r'^const (?:int CLIENT_TO_AVATAR_MIXER_BROADCAST_FRAMES_PER_SECOND|quint64 MIN_TIME_BETWEEN_MY_AVATAR_DATA_SENDS)[^;]+;', sources['libraries/avatars/src/AvatarHashMap.h'], re.M))
flags='\n'.join(re.findall(r'^    (?:using HasFlags[^;]+|const HasFlags PACKET_HAS_JOINT_(?:DATA|DEFAULT_POSE_FLAGS)[^;]+);', sources['libraries/avatars/src/AvatarData.h'], re.M))
cpp = (HERE / 'hidden-avatar-pose.cpp').read_text()
for name, value in {'SIMULATION': simulation, 'PACKET_CACHE': packet_cache,
                    'METHODS': methods, 'VISIBILITY': set_visibility + '\n' + get_visibility,
                    'SEND_RATE':send_rate, 'PACKET_FLAGS':flags,
                    'MANAGER': block(manager, 'void AvatarManager::updateMyAvatar(')}.items():
    cpp = cpp.replace('@' + name + '@', value)
module = 'Qt' + major + 'Core'
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', module], text=True))
libdir = subprocess.check_output(['pkg-config', '--variable=libdir', module], text=True).strip()
glm = ['-isystem', os.environ['OVERTE_TEST_GLM_INCLUDE']] if os.environ.get('OVERTE_TEST_GLM_INCLUDE') else []
with tempfile.TemporaryDirectory(prefix='overte-hidden-avatar-pose-') as temporary:
    stage = Path(temporary)
    (stage / 'test.cpp').write_text(cpp)
    binary = stage / 'test'
    subprocess.run(['c++', '-std=c++17', '-fPIC', '-UNDEBUG', '-I' + str(root / 'libraries/shared/src'),
                    *glm, str(stage / 'test.cpp'), '-o', str(binary), '-L' + libdir, *flags],
                   check=True, timeout=60)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    observations = json.loads(result.stdout)
    report = {'source_root': str(root), 'source_commit': subprocess.check_output(
        ['git', 'rev-parse', args.source_ref or 'HEAD'], cwd=root, text=True).strip(), 'source_ref': args.source_ref, 'qt_major': major,
        'production_sha256': {path: hashlib.sha256(source.encode()).hexdigest()
                              for path, source in sources.items()},
        'observations': observations, 'exit_code': result.returncode, 'stderr': result.stderr,
        'boundary': __doc__}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(observations, indent=2))
    raise SystemExit(result.returncode)
