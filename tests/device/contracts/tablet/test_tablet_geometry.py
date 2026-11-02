"""Run the production touch presenter geometry against actual Qt Quick items."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


class TabletGeometry(unittest.TestCase):
    def test_presenter_centers_without_changing_platform_measurements(self):
        source = (ROOT / 'libraries/ui/src/ui/TabletScriptingInterface.cpp').read_text()
        start = source.index('void TabletProxy::resizeAndroidTablet(int width, int height) {')
        end = source.index('\n}\n', start) + 2
        method = source[start:end]
        header = (ROOT / 'libraries/ui/src/ui/TabletScriptingInterface.h').read_text()
        member = '_screenSpaceMode' if 'bool _screenSpaceMode' in header else '_androidScreenSpaceMode'
        platforms = ['ANDROID_APP_PHONE_INTERFACE']
        if 'defined(Q_OS_IOS)' in method:
            platforms.append('Q_OS_IOS')
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Quick'], text=True))
        libexec = subprocess.check_output(
            ['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()
        fixture = HERE / 'tablet-geometry-test.cpp'
        with tempfile.TemporaryDirectory(prefix='overte-tablet-geometry-') as scratch:
            scratch = Path(scratch)
            (scratch / 'production.inc').write_text(source[start:end])
            subprocess.run([str(Path(libexec) / 'moc'), str(fixture), '-o',
                            str(scratch / 'tablet-geometry-test.moc')], check=True, timeout=15)
            binary = scratch / 'geometry'
            for platform in platforms:
                with self.subTest(platform=platform):
                    subprocess.run(['c++', '-std=c++17', '-fPIC', f'-D{platform}',
                                    f'-DOVERTE_TABLET_SCREEN_SPACE_MEMBER={member}',
                                    '-I', str(scratch), str(fixture), '-o', str(binary),
                                    *flags], check=True, timeout=60)
                    subprocess.run([str(binary)], check=True, timeout=15,
                                   env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})


if __name__ == '__main__':
    unittest.main()
