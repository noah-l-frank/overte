#!/usr/bin/env python3
"""Compile production Android Java/resources against real APIs, without devices.

The trusted preparation role fetches only checksum-pinned public dependencies.
The compile role is network-free and consumes no generated API stubs. This is
Java/resource acceptance; it does not attest an APK, Android C++ or device run.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

MAVEN = (
    ('webkit', 'https://dl.google.com/dl/android/maven2/androidx/webkit/webkit/1.12.1/webkit-1.12.1.aar',
     '18a0a51ad129e0c8563f031d46c8a7e61169f56ae84e562a0d75686941262111'),
    ('core', 'https://dl.google.com/dl/android/maven2/androidx/core/core/1.1.0/core-1.1.0.aar',
     '76c7cfbe596fe3c09a6983bf1c89e889299c08ac9a3b52ce5182a088d056647e'),
    ('guava', 'https://repo.maven.apache.org/maven2/com/google/guava/guava/23.0/guava-23.0.jar',
     '7baa80df284117e5b945b19b98d367a85ea7b7801bd358ff657946c3bd1b6596'),
)
QT_API_REFERENCE = 'qt/5.15.18-2026.01.04@overte/stable#4fc772a2dbcd84731eb6ff9904e6e358'
FIXED_JARS = {
    'QtAndroid.jar': 'a9f64f066766e3908d64183a49c0722aff09495c5f17768213a2989a73edf893',
    'webkit.jar': 'b03291b19348fdb4e7c5a97b316a19d71a583f45e68fd2b9ea2ea0a867e25cad',
    'core.jar': '6dad2c3643d2e11e8ccf63c9af57d3e36ed4cfa5caa1930f44f4f90f2990fd50',
    'guava.jar': '7baa80df284117e5b945b19b98d367a85ea7b7801bd358ff657946c3bd1b6596',
}
PRODUCTS = {
    'common': (None, 'org.overte.shared'),
    'phone': ('android/phone/apps/phoneInterface/src/main', 'org.overte.phone'),
    'pico': ('android/vr/pico/apps/picoInterface/src/main', 'org.overte.pico'),
}
COMMON = ('android/common/libraries/qt/src/main/java', 'android/common/web/java',
          'android/common/snapshot/java', 'android/common/documents/java', 'security/redaction/java')
RESOURCES = ('android/common/web/res', 'android/common/snapshot/res')
OPTIONAL_RESOURCES = ('android/common/documents/res',)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class DigestStream:
    def __init__(self, source):
        self.source, self.digest, self.size = source, hashlib.sha256(), 0

    def read(self, size=-1):
        data = self.source.read(size)
        self.size += len(data)
        require(self.size <= 900_000_000, 'Qt archive exceeds its fixed size bound')
        self.digest.update(data)
        return data


def qt_archive():
    # Resolve only from the trusted preparation checkout. The isolated compile
    # command embeds this module's source and does not load or fetch bundles.
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('android_dependency_policy',
        root / 'tools/dependency-releases/check.py')
    resolver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resolver)
    bundle = resolver.load((root / resolver.POLICY).read_text())['bundles']['pico']
    asset = 'pico4-qt-conan.tgz'
    return (f"https://github.com/{resolver.REPOSITORY}/releases/download/{bundle['tag']}/{asset}",
            bundle['assets'][asset])


def qt_jar():
    # Stream the 777 MB verified Conan archive; retain only its small Java API.
    # No archive paths, symlinks, executables or native packages are extracted.
    url, digest = qt_archive()
    jars = []
    with urllib.request.urlopen(url, timeout=60) as source:
        stream = DigestStream(source)
        with tarfile.open(fileobj=stream, mode='r|gz') as archive:
            count, unpacked = 0, 0
            for member in archive:
                count += 1
                unpacked += member.size
                require(count <= 300_000 and 0 <= member.size <= 2 * 1024 ** 3
                        and unpacked <= 16 * 1024 ** 3, 'Qt archive inventory exceeds bound')
                if member.name.endswith('/jar/QtAndroid.jar'):
                    require(member.isfile() and 0 < member.size <= 10_000_000,
                            'Qt Android API member is not a bounded regular file')
                    jars.append(archive.extractfile(member).read())
        while stream.read(1024 * 1024):
            pass
        require(stream.digest.hexdigest() == digest, 'Qt archive checksum mismatch')
    require(len(jars) == 1, 'Qt archive must contain exactly one Android API JAR')
    return jars[0]


def prepare(destination, sdk, qt_api_cache=None):
    destination, sdk = Path(destination).resolve(), Path(sdk).resolve(strict=True)
    destination.mkdir(parents=True, exist_ok=True)
    require(not (destination / 'runtime.json').exists(), 'runtime already prepared; verify/reuse it instead')
    properties = sdk / 'build-tools/36.0.0/source.properties'
    require('Pkg.Revision=36.0.0' in properties.read_text(), 'Android build-tools 36.0.0 required')
    for name, source in (('android.jar', sdk / 'platforms/android-36/android.jar'),
                         ('aapt2', sdk / 'build-tools/36.0.0/aapt2')):
        require(source.is_file(), 'actual SDK 36 input missing: ' + name)
        shutil.copyfile(source, destination / name)
    (destination / 'aapt2').chmod(0o755)
    cached = Path(qt_api_cache) if qt_api_cache else None
    payload = None
    if cached is not None:
        try:
            if cached.parent.resolve(strict=True) == cached.parent and cached.is_file() and not cached.is_symlink() \
                    and sha(cached) == FIXED_JARS['QtAndroid.jar']:
                payload = cached.read_bytes()
        except OSError:
            pass
    if payload is None:
        payload = qt_jar()
        require(hashlib.sha256(payload).hexdigest() == FIXED_JARS['QtAndroid.jar'],
                'extracted Qt Android API checksum mismatch')
        if cached is not None:
            # A dependency cache is optional acceleration, never authority or a
            # reason to reject a correctly fetched runtime. Replace only our
            # fixed cache leaf atomically; never follow a restored symlink.
            try:
                cached.parent.mkdir(parents=True, exist_ok=True)
                if cached.parent.resolve(strict=True) == cached.parent and not cached.is_dir():
                    with tempfile.NamedTemporaryFile(dir=cached.parent, prefix='.qt-api-', delete=False) as output:
                        temporary = Path(output.name)
                        output.write(payload)
                    try:
                        temporary.replace(cached)
                    finally:
                        temporary.unlink(missing_ok=True)
            except OSError:
                pass
    (destination / 'QtAndroid.jar').write_bytes(payload)
    for name, url, digest in MAVEN:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = response.read(20_000_001)
        require(len(payload) <= 20_000_000 and hashlib.sha256(payload).hexdigest() == digest,
                'Maven artifact size/checksum mismatch: ' + name)
        if url.endswith('.aar'):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = [entry for entry in archive.infolist() if entry.filename == 'classes.jar']
                require(len(members) == 1 and members[0].file_size <= 20_000_000,
                        'AndroidX classes.jar missing, duplicate or oversized')
                payload = archive.read(members[0])
        (destination / (name + '.jar')).write_bytes(payload)
    manifest = {name: sha(destination / name) for name in
                ('android.jar', 'aapt2', 'QtAndroid.jar', 'webkit.jar', 'core.jar', 'guava.jar')}
    (destination / 'runtime.json').write_text(json.dumps(manifest, sort_keys=True) + '\n')
    return manifest


def verify_runtime(runtime):
    runtime = Path(runtime).resolve(strict=True)
    names = {'android.jar', 'aapt2', 'QtAndroid.jar', 'webkit.jar', 'core.jar', 'guava.jar'}
    manifest = json.loads((runtime / 'runtime.json').read_text())
    require(type(manifest) is dict and set(manifest) == names, 'incomplete actual Android API runtime')
    for name in names:
        path = runtime / name
        require(path.is_file() and not path.is_symlink() and sha(path) == manifest[name],
                'prepared Android runtime checksum mismatch: ' + name)
        if name in FIXED_JARS:
            require(manifest[name] == FIXED_JARS[name], 'unreviewed Android API dependency: ' + name)
    return runtime


def verify_qt_api_reference(candidate):
    recipe = Path(candidate) / 'android/common/conan/conanfile-pico.py'
    require(recipe.is_file() and recipe.stat().st_size <= 1_000_000,
            'declared Android Qt API reference is missing or oversized')
    tree = ast.parse(recipe.read_text())
    values = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'qt_ref' for target in node.targets)]
    require(len(values) == 1 and isinstance(values[0], ast.Constant)
            and values[0].value == QT_API_REFERENCE,
            'Android Qt provider changed; review and qualify its actual Java API before compilation')


def resource_roots(candidate, main):
    """Include new Documents resources when present; existing trees may omit them."""
    roots = ([main / 'res'] if main else []) + [candidate / name for name in RESOURCES]
    for name in OPTIONAL_RESOURCES:
        path = candidate / name
        if path.exists():
            require(path.is_dir(), 'optional Android resource input is not a directory: ' + name)
            roots.append(path)
    return roots


def compile_product(candidate, runtime, product, run=subprocess.run):
    require(product in PRODUCTS, 'unknown Android product')
    candidate, runtime = Path(candidate).resolve(strict=True), verify_runtime(runtime)
    source, namespace = PRODUCTS[product]
    main = candidate / source if source else None
    require(main is None or (main / 'java').is_dir(), 'selected production Android Java is missing')
    source_roots = ([main / 'java', main / 'kotlin'] if main else [])
    source_roots += [root for relative in COMMON for root in
                     (candidate / relative, (candidate / relative).parent / 'kotlin')]
    require(not any(path for root in source_roots if root.is_dir() for path in root.rglob('*.kt')),
            'Kotlin production sources require an actual Kotlin compiler owner; javac does not qualify them')
    sources = sorted((main / 'java').rglob('*.java')) if main else []
    for relative in COMMON:
        root = candidate / relative
        require(root.is_dir(), 'production Android prerequisite is missing: ' + relative)
        sources += sorted(root.rglob('*.java'))
    require(bool(sources), 'selected Android product has no production Java')
    verify_qt_api_reference(candidate)
    with tempfile.TemporaryDirectory(prefix='overte-android-api-') as temporary:
        stage = Path(temporary)
        generated, classes = stage / 'generated', stage / 'classes'
        generated.mkdir(); classes.mkdir()
        manifest = ET.parse(main / 'AndroidManifest.xml') if main else ET.ElementTree(ET.Element('manifest'))
        manifest.getroot().set('package', namespace)
        manifest_path = stage / 'AndroidManifest.xml'
        manifest.write(manifest_path, encoding='utf-8')
        compiled = []
        resources = resource_roots(candidate, main)
        for index, resource in enumerate(resources):
            require(resource.is_dir(), 'production Android resources are missing')
            output = stage / (str(index) + '.zip')
            run([str(runtime / 'aapt2'), 'compile', '--dir', str(resource), '-o', str(output)],
                check=True, timeout=120)
            compiled.append(str(output))
        run([str(runtime / 'aapt2'), 'link', '-o', str(stage / 'resources.apk'),
             '-I', str(runtime / 'android.jar'), '--manifest', str(manifest_path),
             '--java', str(generated), '--custom-package', namespace, '--auto-add-overlay',
             *compiled], check=True, timeout=120)
        sources += sorted(generated.rglob('*.java'))
        classpath = ':'.join(str(runtime / name) for name in
                             ('android.jar', 'QtAndroid.jar', 'webkit.jar', 'core.jar', 'guava.jar'))
        run(['javac', '-encoding', 'UTF-8', '-source', '17', '-target', '17',
             '-classpath', classpath, '-d', str(classes), *map(str, sources)], check=True, timeout=180)
        require(any(classes.rglob('*.class')), 'compiler produced no production bytecode')
    return {'product': product, 'scope': 'production-java-and-resources', 'result': 'success',
            'source_files': len(sources), 'apk_or_android_native_build': False, 'device_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    setup = sub.add_parser('prepare'); setup.add_argument('--destination', required=True); setup.add_argument('--sdk', required=True)
    setup.add_argument('--qt-api-cache', help='Optional hash-verified small JAR cache; SDK tools are always copied fresh')
    verify = sub.add_parser('verify'); verify.add_argument('--runtime', required=True)
    compiler = sub.add_parser('compile'); compiler.add_argument('--candidate', default='/work')
    compiler.add_argument('--runtime', required=True); compiler.add_argument('--product', choices=PRODUCTS, required=True)
    args = parser.parse_args()
    if args.operation == 'prepare': result = prepare(args.destination, args.sdk, args.qt_api_cache)
    elif args.operation == 'verify': result = {'runtime': str(verify_runtime(args.runtime)), 'result': 'success'}
    else: result = compile_product(args.candidate, args.runtime, args.product)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
