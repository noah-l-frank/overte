#!/usr/bin/env python3
"""Compile the production mirror registration for each native product.

The original preprocessor guard, depth condition, loop, task names and arguments
execute unchanged. Task/GPU inputs are endpoint fixtures; this is not a renderer
build or evidence of reflected pixels, frame rate or hardware compatibility.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
PROFILES = {
    'desktop': (),
    'ios': ('Q_OS_IOS',),
    'legacy-android': ('Q_OS_ANDROID',),
    'phone': ('Q_OS_ANDROID', 'ANDROID_APP_PHONE_INTERFACE'),
    'pico': ('Q_OS_ANDROID', 'ANDROID_APP_PICO_INTERFACE'),
}


class AndroidMirrorRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = [ROOT / 'libraries/render-utils/src/RenderForwardTask.cpp',
                     ROOT / 'libraries/render-utils/src/RenderCommonTask.h']
        forward, header = (path.read_text() for path in cls.paths)
        start = forward.index('    if (depth < RenderMirrorTask::MAX_MIRROR_DEPTH)')
        start = forward.rfind('\n#', 0, start) + 1
        end = forward.index('\n#endif', start) + len('\n#endif')
        registration = forward[start:end]
        if 'Q_OS_ANDROID' not in registration.splitlines()[0]:
            raise AssertionError('Review changed production mirror capability guard')
        mirror_class = header[header.index('class RenderMirrorTask {'):]
        maximum = int(re.search(r'MAX_MIRRORS_PER_LEVEL\s*\{\s*(\d+)\s*\}', mirror_class)[1])
        cls.depth = int(re.search(r'MAX_MIRROR_DEPTH\s*\{\s*(\d+)\s*\}', mirror_class)[1])
        if maximum != 3 or cls.depth != 1:
            raise AssertionError('Review changed native mirror resource budget')
        template = r'''
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
struct MirrorInputs {
    int mirrors, framebuffer;
    MirrorInputs(int m, int f) : mirrors(m), framebuffer(f) {}
};
struct RenderMirrorTask {
    using Inputs = MirrorInputs;
    static constexpr size_t MAX_MIRRORS_PER_LEVEL = @MAX@;
    static constexpr size_t MAX_MIRROR_DEPTH = @DEPTH@;
};
struct Task {
    std::vector<std::string> names;
    template<class Job> void addJob(const std::string& name, const MirrorInputs& inputs,
                                    size_t index, int cull, int offset, int depth) {
        assert(inputs.mirrors == 7 && inputs.framebuffer == 11);
        assert(cull == 13 && offset == 17 && depth == 0);
        assert(index == names.size());
        names.push_back(name);
    }
};
int main(int argc, char** argv) {
    assert(argc == 2);
    int depth = std::atoi(argv[1]);
    int mirrors = 7, scaledPrimaryFramebuffer = 11, cullFunctor = 13, transformOffset = 17;
    Task task;
@REGISTRATION@
    std::cout << '[';
    for (size_t i = 0; i < task.names.size(); ++i) {
        if (i) { std::cout << ','; }
        std::cout << '"' << task.names[i] << '"';
    }
    std::cout << "]\n";
}
'''
        code = template.replace('@MAX@', str(maximum)).replace('@DEPTH@', str(cls.depth))
        code = code.replace('@REGISTRATION@', registration)
        cls.temporary = tempfile.TemporaryDirectory(prefix='overte-mirror-registration-')
        stage = Path(cls.temporary.name)
        source = stage / 'registration.cpp'
        source.write_text(code)
        cls.binaries = {}
        cls.observations = []
        for profile, defines in PROFILES.items():
            binary = stage / profile
            subprocess.run(['c++', '-std=c++17', '-UNDEBUG',
                            *['-D' + define for define in defines], str(source), '-o', str(binary)],
                           check=True, timeout=30)
            cls.binaries[profile] = binary
        cls.registration_sha256 = hashlib.sha256(registration.encode()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        if os.environ.get('OVERTE_ANDROID_MIRROR_REGISTRATION_EVIDENCE'):
            Path(os.environ['OVERTE_ANDROID_MIRROR_REGISTRATION_EVIDENCE']).write_text(json.dumps({
                'production_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in cls.paths},
                'actual_registration_sha256': cls.registration_sha256,
                'profiles': PROFILES, 'observations': cls.observations,
                'boundary': __doc__,
            }, indent=2) + '\n')
        cls.temporary.cleanup()

    def invoke(self, profile, depth):
        output = subprocess.check_output([str(self.binaries[profile]), str(depth)], text=True, timeout=5)
        names = json.loads(output)
        self.observations.append({'profile': profile, 'depth': depth, 'registered_jobs': names})
        return names

    def test_phone_pico_and_existing_native_products_register_the_bounded_jobs(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                expected = [] if profile == 'legacy-android' else [
                    'RenderMirrorTask' + str(index) + 'Depth0' for index in range(3)]
                self.assertEqual(self.invoke(profile, 0), expected)

    def test_recursion_depth_cap_remains_enforced_for_every_product(self):
        for profile in PROFILES:
            for depth in (self.depth, self.depth + 1):
                with self.subTest(profile=profile, depth=depth):
                    self.assertEqual(self.invoke(profile, depth), [])


if __name__ == '__main__':
    unittest.main()
