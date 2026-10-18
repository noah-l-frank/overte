#!/usr/bin/env python3
"""Real production Render setters/load/RAII and Setting::Handle with Qt INI.

Only Interface's async manager/storage transport and GPU/native services are
fixtures. Each invoke is a new process; no fake Render/Handle preference logic.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent

def block(source, marker):
    start=source.index(marker)
    end=source.index('{',start)+1
    depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}')
        end+=1
    return source[start:end]

def build(stage, root=ROOT, replacements=None, defines=()):
    major=os.environ.get('OVERTE_NATIVE_QT_MAJOR','5')
    if major not in ('5','6'): raise RuntimeError('OVERTE_NATIVE_QT_MAJOR must be 5 or 6')
    module='Qt'+major+'Core'
    modules=['Qt'+major+part for part in ('Core','Gui','Widgets')]
    version=subprocess.check_output(['pkg-config','--modversion',module],text=True).strip()
    if not version.startswith(major+'.'): raise RuntimeError('Wrong Qt development version')
    tool='host_bins' if major=='5' else 'libexecdir'
    moc=Path(subprocess.check_output(['pkg-config','--variable='+tool,module],text=True).strip())/'moc'
    result=subprocess.run([str(moc),'-v'],capture_output=True,text=True,check=True)
    if not re.search(r'\bmoc '+re.escape(version)+r'\b',result.stdout+result.stderr): raise RuntimeError('Wrong moc version')
    h=(root/'interface/src/scripting/RenderScriptingInterface.h').read_text()
    render_ref=os.environ.get('OVERTE_RENDER_PREFERENCES_REF')
    s=subprocess.check_output(['git','show',render_ref+':interface/src/scripting/RenderScriptingInterface.cpp'],cwd=root,text=True) if render_ref else (root/'interface/src/scripting/RenderScriptingInterface.cpp').read_text()
    handle=(root/'libraries/shared/src/SettingHandle.h').read_text()
    methods=[block(s,'void RenderScriptingInterface::loadSettings(')]
    declarations=[]
    for suffix in ('RenderMethod','ShadowsEnabled','HazeEnabled','BloomEnabled','AmbientOcclusionEnabled','LocalLightingEnabled','ProceduralMaterialsEnabled','MirrorsEnabled','AntialiasingMode','ViewportResolutionScale'):
        for prefix in ('get','set','force'):
            pattern=re.compile(r'^[\w:]+ RenderScriptingInterface::'+prefix+suffix+r'\([^\n]+',re.M)
            marker=pattern.search(s).group()
            method=block(s,marker)
            methods.append(method)
            declarations.append(method[:method.index('{')].replace('RenderScriptingInterface::','').strip()+';')
    for name in ('ScopedSettingsOverride::ScopedSettingsOverride','ScopedSettingsOverride::~ScopedSettingsOverride'):
        methods.append(block(s,'RenderScriptingInterface::'+name+'('))
    guard=block(h,'    class ScopedSettingsOverride')+';'
    runtime=h[h.index('    int  _renderMethod {'):h.index('    // Actual settings saved on disk')]
    settings=h[h.index('    Setting::Handle<int> _renderMethodSetting'):h.index('    // Force assign both setting')]
    interface=(root/'libraries/shared/src/SettingInterface.h').read_text()
    lock=(root/'libraries/shared/src/shared/ReadWriteLockable.h').read_text().replace('#pragma once', '')
    menu=(root/'libraries/ui/src/ui/Menu.cpp').read_text()
    menu_methods='\n'.join(block(menu,name) for name in ('void Menu::loadAction(', 'void Menu::saveAction(', 'void Menu::setIsOptionChecked('))
    parts={'MENU_METHODS':menu_methods,'SETTING_INTERFACE':interface,'HANDLE':handle[handle.index('    /**\n     * @brief Handle'):handle.rindex('\n}\n')], 'LOCK':lock,
           'GUARD_DECLARATION':guard,'RUNTIME':runtime,'SETTINGS':settings,'DECLARATIONS':'\n'.join(declarations),'METHODS':'\n'.join(methods),
           'EXTRA_DECLARATIONS':'','APP_MEMBERS':'','EXTRA_METHODS':'','STARTUP':'render.loadSettings();writes={};','ACTION':''}
    parts.update(replacements or {})
    cpp=(HERE/'render-preferences.cpp').read_text()
    for key,value in parts.items():cpp=cpp.replace('@'+key+'@',value)
    (stage/'test.cpp').write_text(cpp)
    subprocess.run([str(moc),str(stage/'test.cpp'),'-o',str(stage/'test.moc')],check=True)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*modules],text=True))
    libdir=subprocess.check_output(['pkg-config','--variable=libdir',module],text=True).strip()
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-I'+str(root/'libraries/shared/src/shared'),*defines,str(stage/'test.cpp'),'-o',str(stage/'probe'),'-L'+libdir,*flags],check=True,timeout=60)
    return stage/'probe',version

class RenderPreferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='overte-render-prefs-')
        cls.stage=Path(cls.temp.name)
        cls.binary,cls.version=build(cls.stage)
        cls.observations=[]
    @classmethod
    def tearDownClass(cls):
        if os.environ.get('OVERTE_RENDER_PREFS_EVIDENCE'):
            Path(os.environ['OVERTE_RENDER_PREFS_EVIDENCE']).write_text(json.dumps({'source_root':str(ROOT),'render_cpp_ref':os.environ.get('OVERTE_RENDER_PREFERENCES_REF'),'qt_version':cls.version,'production_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'interface/src/scripting/RenderScriptingInterface.cpp',ROOT/'interface/src/scripting/RenderScriptingInterface.h',ROOT/'libraries/shared/src/SettingHandle.h']},'observations':cls.observations,'boundary':__doc__},indent=2)+'\n')
        cls.temp.cleanup()
    def invoke(self,file,action):
        r=subprocess.run([str(self.binary),str(file),action],capture_output=True,text=True,timeout=15,env=os.environ|{'QT_QPA_PLATFORM':'offscreen'})
        self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertFalse(r.stderr,r.stderr)
        out=json.loads(r.stdout);self.assertEqual(out['qt_version'],self.version)
        self.observations.append({'action':action,'result':out});return out
    def test_saved_false_true_survive_separate_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            for choice in (False,True,False,True):
                self.invoke(file,str(choice).lower())
                out=self.invoke(file,'load')
                for key in ('shadowsEnabled','hazeEnabled','bloomEnabled','ambientOcclusionEnabled','localLightingEnabled','proceduralMaterialsEnabled','mirrorsEnabled'):self.assertEqual(out[key],choice,key)
                self.assertEqual(out['antialiasingMode'],2 if choice else 1)
                self.assertAlmostEqual(out['viewportResolutionScale'],.75 if choice else .5)
                self.assertTrue(out['mirror_graph_matches'])
    def test_menu_actions_cannot_save_transient_override_for_next_start(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            self.invoke(file,'menu-override')
            restored=self.invoke(file,'load')
            for key in ('shadowsEnabled','ambientOcclusionEnabled','localLightingEnabled','proceduralMaterialsEnabled'):
                self.assertTrue(restored[key],key)
                self.assertTrue(restored['saved'][key],key)

    def test_nested_exception_and_early_return_restore_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            self.invoke(file,'guard')
            out=self.invoke(file,'load')
            self.assertTrue(out['hazeEnabled'])
            self.assertEqual(out['antialiasingMode'],2)
            self.assertTrue(out['mirror_graph_matches'])

if __name__=='__main__':unittest.main()
