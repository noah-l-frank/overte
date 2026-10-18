#!/usr/bin/env python3
"""Pico startup/presets and saved choices across independent Qt INI processes.

Executes the production Application graphics startup section, Render native
methods, complete Setting::Handle, PerformanceManager and LOD load/save/setter
bodies, plus Qt QAction and exact Menu load/save/checkbox methods. Android
properties, platform profiler/display data, async settings transport, GPU/jobs,
full menu construction/scanning/cross-thread dispatch, and refresh controller
services are bounded host fixtures.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import test_render_preferences as native
from test_render_preferences import block

ROOT=Path(__file__).resolve().parents[4]
EXTRA=r'''
constexpr int PROP_VALUE_MAX=92;
int __system_property_get(const char* key,char* output){auto value=qgetenv(key);if(value.isEmpty())return 0;qstrncpy(output,value.constData(),PROP_VALUE_MAX);return value.size();}
Q_LOGGING_CATEGORY(interfaceapp,"fixture.app")
namespace platform {
namespace keys {namespace display {const QString ppi="ppi";}}
inline int getPrimaryDisplay(){return 0;}
inline QMap<QString,float> getDisplay(int){return {};}
struct Profiler {enum {UNKNOWN,LOW_POWER,LOW,MID,HIGH,CUSTOM,NumTiers};static int profilePlatform(){return HIGH;}static bool isRenderMethodDeferredCapable(){return false;}};
}
struct RefreshRateManager {
    enum RefreshRateProfile {ECO,INTERACTIVE,REALTIME,CUSTOM};
    ReadWriteLockable _refreshRateProfileSettingLock;
    Setting::Handle<int> _refreshRateProfileSetting{"refreshRateProfile",INTERACTIVE};
    RefreshRateProfile _refreshRateProfile=RefreshRateProfile(_refreshRateProfileSetting.get());
    static bool isValidRefreshRateProfile(RefreshRateProfile v){return v>=ECO && v<=CUSTOM;}
    void updateRefreshRateController(){}void setRefreshRateProfile(RefreshRateProfile);
};
@LOD_CONSTANTS@
@LOD_HANDLES@
namespace hifi {namespace properties {const char* OCULUS_STORE="oculusStore";}}
class LODManager {
public:
    WorldDetailQuality _desktopWorldDetailQuality=DEFAULT_WORLD_DETAIL_QUALITY,_hmdWorldDetailQuality=DEFAULT_WORLD_DETAIL_QUALITY;
    bool _automaticLODAdjust=true;float _lodHalfAngle=0.25f;
    void setWorldDetailQuality(WorldDetailQuality,bool);void setWorldDetailQuality(WorldDetailQuality);
    void worldDetailQualityChanged(){}void setHMDLODTargetFPS(float){}void setDesktopLODTargetFPS(float){}
    void loadSettings();void saveSettings();
};
LODManager lod;
struct DependencyManager {template<class T>static T* get(){return &lod;}};
@PERFORMANCE_CLASS@

'''

class PicoStartup(native.RenderPreferences):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='overte-pico-startup-');cls.stage=Path(cls.temp.name);cls.observations=[]
        application_ref=os.environ.get('OVERTE_PICO_APPLICATION_REF')
        app=subprocess.check_output(['git','show',application_ref+':interface/src/Application.cpp'],cwd=ROOT,text=True) if application_ref else (ROOT/'interface/src/Application.cpp').read_text()
        cls.application_source=app
        cls.application_ref=application_ref
        start=app.index('    // Load settings of the RenderScritpingInterface')
        end=app.index('    // finish initializing the camera',start)
        startup=app[start:end]
        perf=(ROOT/'interface/src/PerformanceManager.cpp').read_text()
        perf_methods='\n'.join(native.block(perf,name) for name in ('PerformanceManager::PerformanceManager(', 'void PerformanceManager::setupPerformancePresetSettings(', 'void PerformanceManager::setPerformancePreset(', 'PerformanceManager::PerformancePreset PerformanceManager::getPerformancePreset(', 'void PerformanceManager::applyPerformancePreset('))
        header=(ROOT/'interface/src/PerformanceManager.h').read_text()
        perf_class=native.block(header,'class PerformanceManager')+';'
        lod=(ROOT/'interface/src/LODManager.cpp').read_text()
        lod_methods='\n'.join(native.block(lod,name) for name in ('void LODManager::setWorldDetailQuality(WorldDetailQuality quality, bool', 'void LODManager::setWorldDetailQuality(WorldDetailQuality quality)', 'void LODManager::loadSettings(', 'void LODManager::saveSettings('))
        refresh=block((ROOT/'interface/src/RefreshRateManager.cpp').read_text(),'void RefreshRateManager::setRefreshRateProfile(')
        lod_header=(ROOT/'interface/src/LODManager.h').read_text()
        constants=lod_header[lod_header.index('enum WorldDetailQuality {'):lod_header.index('const float LOD_OFFSET_FPS')]
        handles=lod[lod.index('const QString LOD_SETTINGS_PREFIX'):lod.index('Setting::Handle<int> hmdWorldDetailQuality')]
        handles+=lod[lod.index('Setting::Handle<int> hmdWorldDetailQuality'):lod.index(';',lod.index('Setting::Handle<int> hmdWorldDetailQuality'))+1]
        handles='constexpr float DEFAULT_VISIBILITY_DISTANCE_FOR_UNIT_ELEMENT=1;float getHalfAngleFromVisibilityDistance(float){return 0.25f;}\n'+handles
        # Keep the production Application startup block unchanged, inside a
        # minimal Application service wrapper. The first-run handle is actual.
        methods=refresh+'\n'+lod_methods+'\n'+perf_methods+'''\nvoid App::startup(){\n'''+startup+'\n}\n'
        extra=EXTRA.replace('@PERFORMANCE_CLASS@',perf_class).replace('@LOD_CONSTANTS@',constants).replace('@LOD_HANDLES@',handles)
        parts={'EXTRA_DECLARATIONS':extra,'APP_MEMBERS':'''PerformanceManager performance;RefreshRateManager refresh;
            Setting::Handle<bool> _firstRun{"firstRun",true};
            PerformanceManager& getPerformanceManager(){return performance;}
            RefreshRateManager& getRefreshRateManager(){return refresh;}
            QVariant property(const char*){return false;}
            bool isHMDMode(){return qEnvironmentVariable("fixture.hmd")!="0";}
            void startup();''', 'EXTRA_METHODS':methods,
            'STARTUP':'''lod.loadSettings();writes={};app.startup();''',
            'ACTION':'''if(action=="preset-low")app.performance.setPerformancePreset(PerformanceManager::LOW);if(action=="preset-high")app.performance.setPerformancePreset(PerformanceManager::HIGH);if(action=="true" || action=="false") {lod.setWorldDetailQuality(action=="true"?WORLD_DETAIL_HIGH:WORLD_DETAIL_MEDIUM);app.refresh.setRefreshRateProfile(RefreshRateManager::CUSTOM);app.performance.setPerformancePreset(PerformanceManager::CUSTOM);store->setValue("firstRun",false);} lod.saveSettings();if(action=="legacy"){choices(render,true);store->remove("performancePreset");store->setValue("firstRun",true);store->setValue("refreshRateProfile",RefreshRateManager::CUSTOM);}'''}
        cls.binary,cls.version=native.build(cls.stage,ROOT,parts,('-DQ_OS_ANDROID','-DANDROID_APP_PICO_INTERFACE'))
    def invoke(self,file,action,properties=None):
        result=subprocess.run([str(self.binary),str(file),action],env=os.environ|(properties or {}),capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        # qCInfo startup diagnostics are expected, warnings/errors are not.
        self.assertFalse(any(word in result.stderr for word in ('warning:','error:','ASSERT')),result.stderr)
        out=json.loads(result.stdout);self.assertEqual(out['qt_version'],self.version)
        # INI reload returns textual variants for unchanged values. Compare
        # canonical storage values, rather than transient QVariant type tags.
        out['saved']={key:str(value).lower() if isinstance(value,bool) else str(value) for key,value in out['saved'].items()}
        self.observations.append({'action':action,'properties':properties or {},'result':out,'diagnostics':result.stderr});return out
    def test_saved_false_true_survive_separate_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            for choice in (False,True,False,True):
                with self.subTest(choice=choice):
                    self.invoke(file,str(choice).lower())
                    out=self.invoke(file,'load')
                    for key in ('shadowsEnabled','hazeEnabled','bloomEnabled','ambientOcclusionEnabled','localLightingEnabled','proceduralMaterialsEnabled','mirrorsEnabled'):self.assertEqual(out[key],choice,key)
                    self.assertEqual(out['renderMethod'],0 if choice else 1)
                    self.assertEqual(out['antialiasingMode'],2 if choice else 1)
                    self.assertAlmostEqual(out['viewportResolutionScale'],.75 if choice else .5)
                    self.assertEqual(int(out['saved']['lodManager/hmdWorldDetailQuality']),2 if choice else 1)
                    self.assertEqual(int(out['saved']['refreshRateProfile']),3)
                    self.assertTrue(out['mirror_graph_matches'])
    def test_first_run_baseline_and_profile_does_not_replace_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            initial=self.invoke(file,'load')
            for key in ('shadowsEnabled','bloomEnabled','ambientOcclusionEnabled'):self.assertFalse(initial[key])
            for key in ('hazeEnabled','localLightingEnabled','proceduralMaterialsEnabled','mirrorsEnabled'):self.assertTrue(initial[key])
            self.assertEqual(initial['renderMethod'],1);self.assertEqual(initial['antialiasingMode'],0)
            for choice in (False,True):
                saved=self.invoke(file,str(choice).lower())['saved']
                profile=self.invoke(file,'load',{'debug.overte.power_profile':'1'})
                for key in ('shadowsEnabled','bloomEnabled','ambientOcclusionEnabled','hazeEnabled','localLightingEnabled','proceduralMaterialsEnabled','mirrorsEnabled'):self.assertFalse(profile[key],key)
                self.assertEqual(profile['saved'],saved)
                self.assertTrue(profile['mirror_graph_matches'])
                restored=self.invoke(file,'load',{'debug.overte.power_profile':'0'})
                self.assertEqual(restored['hazeEnabled'],choice);self.assertEqual(restored['saved'],saved)
                override=self.invoke(file,'load',{'debug.overte.power_profile':'on','debug.overte.shadows':'true','debug.overte.haze':'1','debug.overte.bloom':'enabled','debug.overte.ambient_occlusion':'on','debug.overte.local_lights':'true','debug.overte.procedural_materials':'1','debug.overte.mirror_views':'true'})
                self.assertTrue(override['shadowsEnabled']);self.assertTrue(override['hazeEnabled']);self.assertTrue(override['mirrorsEnabled'])
                self.assertEqual(override['saved'],saved);self.assertTrue(override['mirror_graph_matches'])
                individual=self.invoke(file,'load',{'debug.overte.power_profile':'off','debug.overte.shadows':'disabled' if choice else 'true','debug.overte.haze':'off' if choice else 'on','debug.overte.mirror_views':'false' if choice else '1'})
                self.assertEqual(individual['shadowsEnabled'],not choice);self.assertEqual(individual['hazeEnabled'],not choice);self.assertEqual(individual['mirrorsEnabled'],not choice)
                self.assertEqual(individual['saved'],saved);self.assertTrue(individual['mirror_graph_matches'])
                invalid=self.invoke(file,'load',{'debug.overte.haze':'invalid','debug.overte.mirror_views':'invalid'})
                self.assertEqual(invalid['hazeEnabled'],choice);self.assertEqual(invalid['mirrorsEnabled'],choice);self.assertEqual(invalid['saved'],saved)
    def test_partial_legacy_choices_and_explicit_presets(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            self.invoke(file,'legacy')
            restored=self.invoke(file,'load')
            self.assertTrue(restored['shadowsEnabled']);self.assertTrue(restored['hazeEnabled'])
            self.assertEqual(restored['antialiasingMode'],2)
            self.assertEqual(int(restored['saved']['performancePreset']),5)
            self.assertEqual(int(restored['saved']['refreshRateProfile']),3)
            for preset in ('low','high'):
                selected=self.invoke(file,'preset-'+preset)
                restored=self.invoke(file,'load')
                for key in ('shadowsEnabled','hazeEnabled','bloomEnabled','ambientOcclusionEnabled','renderMethod','viewportResolutionScale'):
                    self.assertEqual(restored[key],selected[key],key)
                self.assertEqual(restored['saved'],selected['saved'])

    def test_first_start_with_profile_and_desktop_detail_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'prefs.ini'
            profile=self.invoke(file,'load',{'debug.overte.power_profile':'enabled'})
            self.assertFalse(profile['hazeEnabled']);self.assertFalse(profile['mirrorsEnabled'])
            normal=self.invoke(file,'load')
            self.assertTrue(normal['hazeEnabled']);self.assertTrue(normal['mirrorsEnabled'])
            self.assertTrue(normal['mirror_graph_matches'])
            for choice in (False,True):
                self.invoke(file,str(choice).lower(),{'fixture.hmd':'0'})
                restored=self.invoke(file,'load',{'fixture.hmd':'0'})
                self.assertEqual(int(restored['saved']['lodManager/desktopWorldDetailQuality']),2 if choice else 1)

    @classmethod
    def tearDownClass(cls):
        path=os.environ.get('OVERTE_PICO_STARTUP_EVIDENCE')
        if path:
            files=['interface/src/Application.cpp','interface/src/PerformanceManager.cpp','interface/src/PerformanceManager.h','interface/src/LODManager.cpp','interface/src/LODManager.h','interface/src/RefreshRateManager.cpp','interface/src/scripting/RenderScriptingInterface.cpp','interface/src/scripting/RenderScriptingInterface.h','libraries/shared/src/SettingHandle.h','libraries/shared/src/SettingInterface.h','libraries/shared/src/shared/ReadWriteLockable.h','libraries/ui/src/ui/Menu.cpp']
            Path(path).write_text(json.dumps({'source_root':str(ROOT),'qt_version':cls.version,'application_ref':cls.application_ref,'production_sha256':{f:hashlib.sha256(cls.application_source.encode() if f=='interface/src/Application.cpp' else (ROOT/f).read_bytes()).hexdigest() for f in files},'generated_cpp_sha256':hashlib.sha256((cls.stage/'test.cpp').read_bytes()).hexdigest(),'observations':cls.observations,'boundary':__doc__},indent=2)+'\n')
        cls.temp.cleanup()

if __name__=='__main__':unittest.main()
