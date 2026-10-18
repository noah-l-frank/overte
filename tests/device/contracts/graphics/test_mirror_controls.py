#!/usr/bin/env python3
"""Production mirror setter/settings and task lookup with real Qt objects/INI.

The scene/GPU, async Setting::Manager and non-mirror graphics APIs are boundaries.
The graph fixture follows the checked production registration names/branches; it
is not a native render build or a claim about pixels on any device.
"""
from pathlib import Path
import json
import hashlib
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
RENDER_ROOT = Path(os.environ.get('OVERTE_MIRROR_RENDER_SOURCE_ROOT', ROOT))


def block(source, marker):
    start = source.index(marker)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


class MirrorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observations = []
        cls.temp = tempfile.TemporaryDirectory(prefix='overte-mirrors-')
        cls.stage = Path(cls.temp.name)
        source = (ROOT / 'interface/src/scripting/RenderScriptingInterface.cpp').read_text()
        header = (ROOT / 'interface/src/scripting/RenderScriptingInterface.h').read_text()
        task_header = (ROOT / 'libraries/task/src/task/Config.h').read_text()
        task_source = (ROOT / 'libraries/task/src/task/Config.cpp').read_text()
        # Keep production property/declarations/conditional settings, not a
        # hand-authored property which could hide a broken QML API spelling.
        prop = re.search(r'^    Q_PROPERTY\(bool mirrorsEnabled[^\n]+', header, re.M).group()
        settings = header[header.index('    Setting::Handle<int> _renderMethodSetting'):
                          header.index('    // Force assign both setting')]
        runtime_start = header.index('#if defined(ANDROID_APP_PHONE_INTERFACE)\n    bool _mirrorsEnabled')
        runtime = header[runtime_start:header.index('#endif', runtime_start) + len('#endif')]
        methods = '\n'.join(block(source, marker) for marker in (
            'void RenderScriptingInterface::loadSettings(', 'bool RenderScriptingInterface::getMirrorsEnabled(',
            'void RenderScriptingInterface::setMirrorsEnabled(', 'void RenderScriptingInterface::forceMirrorsEnabled('))
        job_class = task_header[task_header.index('class JobConfig : public QObject'):
                                task_header.index('using QConfigPointer')]
        job_methods = '\n'.join(block(task_source, marker) for marker in (
            'void JobConfig::setEnabled(', 'JobConfig* JobConfig::getRootConfig(',
            'JobConfig* JobConfig::getJobConfig('))
        count = re.search(r'MAX_MIRRORS_PER_LEVEL \{ (\d+) \}',
                          (RENDER_ROOT / 'libraries/render-utils/src/RenderCommonTask.h').read_text()).group(1)
        view = (RENDER_ROOT / 'libraries/render-utils/src/RenderViewTask.cpp').read_text()
        forward = (RENDER_ROOT / 'libraries/render-utils/src/RenderForwardTask.cpp').read_text()
        deferred = (RENDER_ROOT / 'libraries/render-utils/src/RenderDeferredTask.cpp').read_text()
        common = (RENDER_ROOT / 'libraries/render-utils/src/RenderCommonTask.cpp').read_text()
        # These are the real task registrations represented by the QObject
        # fixture below. Missing/renamed registration fails instead of silently
        # retaining an invented graph.
        for text, registration in ((view, 'task.addJob<DeferredForwardSwitchJob>("DeferredForwardSwitch"'),
                                   (view, 'task.addBranch<RenderForwardTask>("RenderForwardTask"'),
                                   (view, 'task.addJob<RenderForwardTask>("RenderForwardTask"'),
                                   (view, '"RenderShadowsAndDeferredTask"'),
                                   (deferred, '"RenderMirrorTask" + std::to_string(i) + "Depth"'),
                                   (forward, '"RenderMirrorTask" + std::to_string(i) + "Depth"'),
                                   (common, 'task.addJob<RenderViewTask>("RenderMirrorView"')):
            if registration not in text:
                raise AssertionError('Production render registration changed: ' + registration)
        if '"RenderDeferredTask"' not in view:
            raise AssertionError('Deferred nesting changed')
        cls.android_mirrors = not re.search(r'#ifndef Q_OS_ANDROID\s+if \(depth < RenderMirrorTask::MAX_MIRROR_DEPTH\)', forward)
        template = (HERE / 'mirror-controls.cpp').read_text()
        for key, value in {'PROPERTY': prop, 'SETTINGS': settings, 'RUNTIME': runtime,
                           'METHODS': methods, 'JOB_CLASS': job_class, 'JOB_METHODS': job_methods,
                           'MIRROR_COUNT': count}.items():
            template = template.replace('@' + key + '@', value)
        cpp = cls.stage / 'test.cpp'
        cpp.write_text(template)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Quick', 'Qt6Qml'], text=True))
        moc = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'
        subprocess.run([str(moc), str(cpp), '-o', str(cls.stage / 'test.moc')], check=True)
        cls.binaries = {}
        for product, define in [('desktop', None), ('ios', 'Q_OS_IOS'), ('phone', 'ANDROID_APP_PHONE_INTERFACE'), ('pico', 'ANDROID_APP_PICO_INTERFACE')]:
            binary = cls.stage / product
            defines = ([f'-D{define}'] if define else []) + (['-DHOST_ANDROID'] if product in ('phone', 'pico') else [])
            defines += [f'-DHOST_HAS_MIRRORS={int(cls.android_mirrors or product not in ("phone", "pico"))}']
            subprocess.run(['c++', '-std=c++17', '-fPIC', '-UNDEBUG', *defines, str(cpp), '-o', str(binary), *flags], check=True, timeout=60)
            cls.binaries[product] = binary

    @classmethod
    def tearDownClass(cls):
        evidence = os.environ.get('OVERTE_MIRROR_EVIDENCE')
        if evidence:
            Path(evidence).write_text(json.dumps({
                'source_root': str(ROOT), 'render_source_root': str(RENDER_ROOT),
                'android_render_mirrors_registered': cls.android_mirrors,
                'production_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (ROOT / 'interface/src/scripting/RenderScriptingInterface.cpp',
                                 ROOT / 'interface/src/scripting/RenderScriptingInterface.h',
                                 ROOT / 'scripts/system/settings/qml/pages/GraphicsSettingsBase.qml')},
                'boundary': 'Production native methods, JobConfig declaration/path lookup/enabled setter and shared QML; real Qt QObject/INI. Source-mapped scene graph, non-mirror APIs, async settings manager and GPU are boundaries.',
                'observations': cls.observations}, indent=2) + '\n')
        cls.temp.cleanup()

    def invoke(self, product, file, action):
        result = subprocess.run([str(self.binaries[product]), str(file), action, str(ROOT)],
                                env=os.environ | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'},
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=15)
        if result.stderr:
            self.fail(result.stderr)
        observation = json.loads(result.stdout)
        self.observations.append({'product': product, 'action': action, 'result': observation,
                                  'ini_sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        return observation

    def test_false_true_and_process_restart_reach_all_registered_passes(self):
        for product in self.binaries:
            with self.subTest(product=product), tempfile.TemporaryDirectory() as directory:
                file = Path(directory) / 'prefs.ini'
                initial = self.invoke(product, file, 'load')
                self.assertEqual(initial['value'], product != 'phone')
                expected = 0 if product in ('phone', 'pico') and not self.android_mirrors else 12 if product in ('phone', 'pico') else 24
                self.assertEqual(initial['configs'], expected)
                for value in (False, True, False, True):
                    selected = self.invoke(product, file, 'true' if value else 'false')
                    self.assertEqual(selected['value'], value)
                    self.assertTrue(selected['all_match'])
                    self.assertTrue(selected['unrelated_enabled'])
                    restored = self.invoke(product, file, 'load')
                    self.assertEqual(restored['value'], value)
                    self.assertTrue(restored['all_match'])
                self.assertEqual(self.invoke(product, file, 'legacy')['value'], False)

    def test_reapply_missing_bad_config_and_replaced_graph_do_not_retain_stale_targets(self):
        for product in self.binaries:
            with self.subTest(product=product), tempfile.TemporaryDirectory() as directory:
                file = Path(directory) / 'prefs.ini'
                for action in ('reapply', 'missing', 'replace', 'bad'):
                    result = self.invoke(product, file, action)
                    self.assertTrue(result['safe'])
                    self.assertTrue(result['all_match'])

    def test_real_shared_qml_control_toggles_the_production_native_property(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'prefs.ini'
            result = self.invoke('desktop', file, 'qml')
            self.assertEqual(result['qml_initial'], True)
            self.assertTrue(result['qml_false'])
            self.assertTrue(result['qml_true'])
            self.assertTrue(result['all_match'])
            self.assertTrue(self.invoke('desktop', file, 'load')['value'])


if __name__ == '__main__':
    unittest.main()
