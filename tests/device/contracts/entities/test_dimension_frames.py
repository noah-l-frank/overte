"""Host regression: complete native property converters and dimension accessors.

The parent lookup is a fixed boundary. No device runner, server or GPU is used.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class DimensionFrames(unittest.TestCase):
    def test_native_world_and_local_edits_and_snapshots(self):
        source = (ROOT / 'libraries/entities/src/EntityScriptingInterface.cpp').read_text()
        entity = (ROOT / 'libraries/entities/src/EntityItem.cpp.in').read_text()
        properties = (ROOT / 'libraries/entities/src/EntityItemProperties.cpp.in').read_text()
        bodies = '\n'.join([
            function(entity, 'glm::vec3 EntityItem::getScaledDimensions() const'),
            function(entity, 'void EntityItem::setScaledDimensions('),
            function(properties, 'void EntityItemProperties::copySimulationRestrictedProperties('),
            function(source, 'EntityItemProperties convertPropertiesToScriptSemantics('),
            function(source, 'EntityItemProperties convertPropertiesFromScriptSemantics('),
        ])
        with tempfile.TemporaryDirectory(prefix='overte-dimension-frames-') as temporary:
            scratch = Path(temporary)
            (scratch / 'native-dimensions.inc').write_text(bodies)
            binary = scratch / 'frames'
            subprocess.run(['c++', '-std=c++17', '-I', str(scratch),
                str(Path(__file__).with_name('dimension-frames.cpp')), '-o', str(binary)],
                check=True, timeout=30)
            for mode in ('world', 'local', 'snapshot', 'unrelated-edit'):
                result = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=5)
                with self.subTest(mode=mode):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
