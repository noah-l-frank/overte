# SPDX-License-Identifier: Apache-2.0
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[4]


class PhoneSpawnGateTests(unittest.TestCase):
    def test_production_support_query_only_runs_during_entry(self):
        source = (ROOT / 'interface/src/avatar/MyCharacterController.cpp').read_text()
        begin = source.index('    const bool wasHeld =', source.index('bool MyCharacterController::updateSpawnHold('))
        end = source.index('    static double lastGroundDiagnostic', begin)
        production = source[begin:end]
        fixture = r'''
#include "interface/src/avatar/PhoneSpawnGate.h"
#include <cassert>
constexpr double USECS_PER_SECOND = 1000000;
double usecTimestampNow() { return 100 * USECS_PER_SECOND; }
struct Controller {
    PhoneSpawnGate _spawnGate;
    int supportQueries = 0;
    bool supported = false;
    bool hasSpawnSupport() { ++supportQueries; return supported; }
    bool update(bool physicsReady, bool mayReport = true) {
''' + production + r'''
        (void)wasHeld;
        return notifyFailure;
    }
};
int main() {
    Controller controller;
    controller.update(true);
    assert(controller.supportQueries == 0);
    controller._spawnGate.begin(100);
    controller.update(false);
    assert(controller.supportQueries == 0);
    controller.update(true);
    assert(controller.supportQueries == 1);
    assert(controller._spawnGate.held());
    controller.supported = true;
    controller.update(true);
    assert(controller.supportQueries == 2);
    assert(!controller._spawnGate.held());
    controller.update(true);
    assert(controller.supportQueries == 2);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = pathlib.Path(directory) / 'production-support-query.cpp'
            binary = pathlib.Path(directory) / 'production-support-query'
            cpp.write_text(fixture)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-pthread', '-I', str(ROOT), str(cpp), '-o', str(binary)],
                           check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)

    def test_release_timeout_and_destination_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = pathlib.Path(directory) / 'phone-spawn-gate'
            subprocess.run([
                'c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                '-I', str(ROOT), str(pathlib.Path(__file__).with_name('phone-spawn-gate-test.cpp')),
                '-o', str(binary),
            ], check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
