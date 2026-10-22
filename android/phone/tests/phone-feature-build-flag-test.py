#!/usr/bin/env python3
"""Run original Phone Gradle flag logic with prepared Groovy/Android DSL seams.

No Gradle/AGP/SDK/device process or dependency resolution runs. Cached Gradle
JARs are read only; Java and the tiny CMake option contract use fresh own output.
This does not qualify a complete Phone APK or Android native instrumentation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'android/phone/apps/phoneInterface/build.gradle'
FLAG='-DOVERTE_E2E_FEATURE_TESTS='


def block(text,label):
    begin='// BEGIN PHONE_FEATURE_E2E_'+label
    end='// END PHONE_FEATURE_E2E_'+label
    if text.count(begin)!=1 or text.count(end)!=1:
        raise AssertionError('Missing or duplicate original Phone E2E build block')
    return text.split(begin,1)[1].split(end,1)[0]


HARNESS=r'''
import groovy.json.JsonSlurper
import groovy.json.JsonOutput
import org.gradle.api.GradleException
import org.gradle.initialization.Environment
import org.gradle.initialization.properties.DefaultProjectPropertiesLoader
class PropertyValue {
    boolean present; Object value
    Object getOrElse(Object fallback) { present ? value : fallback }
}
class PropertyEndpoint {
    Map values; List reads=[]
    Object gradleProperty(String name) {
        reads.add(name)
        new PropertyValue(present:values.containsKey(name),value:values[name])
    }
}
class FinalizeEndpoint {
    Closure original
    void finalizeDsl(Closure action) { assert original==null; original=action }
}
def requests=new JsonSlurper().parse(new File(args[0]))
def actual=new File(args[1]).text
def output=requests.collect { request ->
    def inherited=[:]
    if (request.projectEnvironment) {
        def variables=[byNamePrefix:{ String prefix -> System.getenv().findAll { key,value -> key.startsWith(prefix) } }] as Environment.Properties
        def empty=[byNamePrefix:{ String prefix -> [:] }] as Environment.Properties
        def environment=[getVariables:{ variables },getSystemProperties:{ empty },propertiesFile:{ File path -> [:] }] as Environment
        def loader=new DefaultProjectPropertiesLoader(null,environment)
        def method=DefaultProjectPropertiesLoader.getDeclaredMethod('projectPropertiesFromEnvironmentVariables')
        method.accessible=true
        inherited=method.invoke(loader)
    }
    def properties=new PropertyEndpoint(values:inherited+request.properties)
    def endpoint=new FinalizeEndpoint()
    def variants=request.variants.collect { name,values ->
        [name:name,externalNativeBuild:[cmake:[arguments:new ArrayList(values)]]]
    }
    def result=[accepted:false,propertyReads:properties.reads,finalizeRegistered:false]
    try {
        new GroovyShell(new Binding([providers:properties,androidComponents:endpoint])).evaluate(actual)
        result.finalizeRegistered=endpoint.original!=null
        assert endpoint.original!=null
        endpoint.original.call([buildTypes:variants])
        result.accepted=true
    } catch (GradleException error) {
        result.errorType=error.class.name;result.error=error.message
        result.finalizeRegistered=endpoint.original!=null
    }
    result.variants=variants.collectEntries { variant -> [(variant.name):variant.externalNativeBuild.cmake.arguments] }
    result
}
println JsonOutput.toJson(output)
'''


class PhoneFeatureBuildFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=SOURCE.read_text()
        cls.original='import org.gradle.api.GradleException\n'+block(source,'PROPERTY')+block(source,'FINALIZE')
        explicit=os.environ.get('PHONE_TEST_GRADLE_HOME')
        candidates=[Path(explicit)] if explicit else list((Path.home()/'.gradle/wrapper/dists/gradle-8.13-bin').glob('*/gradle-8.13'))
        candidates=[p for p in candidates if (p/'lib/groovy-3.0.22.jar').is_file()]
        if len(candidates)!=1:
            raise RuntimeError('Prepared Gradle8.13 Groovy runtime required; set PHONE_TEST_GRADLE_HOME (no download attempted)')
        cls.jars=[candidates[0]/'lib'/name for name in (
            'groovy-3.0.22.jar','groovy-json-3.0.22.jar','gradle-stdlib-java-extensions-8.13.jar',
            'gradle-core-8.13.jar','gradle-core-api-8.13.jar','slf4j-api-1.7.36.jar')]
        if not all(path.is_file() for path in cls.jars):
            raise RuntimeError('Prepared original Groovy/Gradle API JAR is missing')
        # The original project-property loader's reflected constructor types
        # need the core Gradle class closure. Only GroovyMain is executed.
        cls.jars=sorted((candidates[0]/'lib').glob('*.jar'))
        homes=[Path(os.environ['JAVA_HOME'])] if os.environ.get('JAVA_HOME') else [
            Path.home()/'Applications/android-studio/jbr',Path('/usr/lib/jvm/java-21-temurin-jdk')]
        cls.java=next((p/'bin/java' for p in homes if (p/'bin/java').is_file()),None)
        if cls.java is None:raise RuntimeError('Prepared JDK17–21 required; set JAVA_HOME')
        cls.build=ROOT/'build/phone-feature-build-flag-contract';cls.build.mkdir(parents=True,exist_ok=True)

    def run_original(self,properties,variants=None,*,environment=None,project_environment=False):
        requests=properties if isinstance(properties,list) else [properties]
        variants=variants or dict(debug=['-DKEEP=value'],emulator=['-DEMU=1'],release=['-DRELEASE=1'])
        with tempfile.TemporaryDirectory(prefix='check-',dir=self.build) as directory:
            stage=Path(directory);(stage/'tmp').mkdir()
            (stage/'original.groovy').write_text(self.original)
            (stage/'harness.groovy').write_text(HARNESS)
            (stage/'requests.json').write_text(json.dumps([dict(properties=value,variants=variants,projectEnvironment=project_environment) for value in requests]))
            env=os.environ.copy()
            for name in ('JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS'):env.pop(name,None)
            env.update(environment or {})
            result=subprocess.run([str(self.java),'-Dgroovy.grape.enable=false','-Djava.io.tmpdir='+str(stage/'tmp'),
                '-cp',os.pathsep.join(map(str,self.jars)),'groovy.ui.GroovyMain',str(stage/'harness.groovy'),
                str(stage/'requests.json'),str(stage/'original.groovy')],cwd=stage,env=env,text=True,capture_output=True,timeout=30)
            self.assertEqual(0,result.returncode,result.stderr)
            return json.loads(result.stdout)

    def test_original_gradle_environment_loader_exposes_exact_wrapper_property_and_rejects_bad_value(self):
        for value,accepted in [('ON',True),('OFF',True),('on',False),('',False)]:
            with self.subTest(value=value):
                result=self.run_original({},environment={'ORG_GRADLE_PROJECT_overteFeatureTests':value,
                    'OVERTE_E2E_FEATURE_TESTS':'ON'},project_environment=True)[0]
                self.assertEqual(accepted,result['accepted'])
                if accepted:
                    self.assertEqual(FLAG+value,result['variants']['debug'][-1])
                    self.assertEqual(FLAG+'OFF',result['variants']['release'][-1])
                else:self.assertFalse(result['finalizeRegistered'])

    def test_missing_and_explicit_off_remain_off_even_with_cmake_environment_on(self):
        results=self.run_original([{},dict(overteFeatureTests='OFF')],environment={'OVERTE_E2E_FEATURE_TESTS':'ON'})
        for result in results:
            self.assertTrue(result['accepted']);self.assertEqual(['overteFeatureTests'],result['propertyReads'])
            self.assertTrue(result['finalizeRegistered'])
            self.assertTrue(all([value for value in args if value.startswith(FLAG)]==[FLAG+'OFF'] for args in result['variants'].values()))

    def test_explicit_on_enables_only_debug_after_inherited_variant_arguments(self):
        variants=dict(debug=['-DKEEP=value',FLAG+'OFF'],emulator=[FLAG+'ON','-DEMU=1'],
            release=['-DOVERTE_E2E_FEATURE_TESTS:BOOL=ON','-DRELEASE=1'],future=[FLAG+'ON','-DFUTURE=1'])
        result=self.run_original(dict(overteFeatureTests='ON'),variants)[0]
        self.assertTrue(result['accepted'])
        for name,args in result['variants'].items():
            self.assertEqual(1,len([value for value in args if 'OVERTE_E2E_FEATURE_TESTS' in value]))
            self.assertEqual(FLAG+('ON' if name=='debug' else 'OFF'),args[-1])
            self.assertEqual([arg for arg in variants[name] if 'OVERTE_E2E_FEATURE_TESTS' not in arg],args[:-1])

    def test_invalid_empty_alias_case_whitespace_and_typed_values_fail_before_dsl(self):
        bad=['','true','false','on','off','1','0',' ON','OFF ','ON\n','ON;-DOTHER=ON',True,False,1,0]
        variants=dict(debug=['-DUNCHANGED=1'],release=[FLAG+'ON'])
        results=self.run_original([dict(overteFeatureTests=value) for value in bad],variants)
        self.assertEqual(len(bad),len(results))
        for value,result in zip(bad,results):
            with self.subTest(value=value):
                self.assertFalse(result['accepted']);self.assertFalse(result['finalizeRegistered'])
                self.assertEqual('org.gradle.api.GradleException',result['errorType'])
                self.assertIn('exactly ON or OFF',result['error']);self.assertEqual(variants,result['variants'])

    def test_unrelated_cmake_options_and_similar_variable_names_are_preserved(self):
        original=['-DOVERTE_E2E_FEATURE_TESTS_EXTRA=ON','-DOVERTE_E2E_VOICE_TESTS=ON','-DCMAKE_CXX_FLAGS=-O2 -fPIC',
            '-DOVERTE_E2E_FEATURE_TESTS:BOOL=ON',FLAG+'ON','-DOVERTE_E2E_FEATURE_TESTS']
        result=self.run_original({},dict(debug=original,release=original))[0]
        for args in result['variants'].values():
            self.assertEqual(original[:3]+[FLAG+'OFF'],args)

    def test_original_cmake_option_accepts_generated_flag_and_clears_own_old_on_cache(self):
        cmake=shutil.which('cmake');self.assertIsNotNone(cmake)
        source=(ROOT/'CMakeLists.txt').read_text()
        option=re.search(r'option\(OVERTE_E2E_FEATURE_TESTS[^\n]*\nif\(OVERTE_E2E_FEATURE_TESTS\).*?endif\(\)',source,re.S)
        self.assertIsNotNone(option)
        results=self.run_original([dict(overteFeatureTests='ON'),{}])
        with tempfile.TemporaryDirectory(prefix='cmake-',dir=self.build) as directory:
            stage=Path(directory);(stage/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(PhoneFlag NONE)\n'+option.group(0)+
                '\nget_directory_property(definitions COMPILE_DEFINITIONS)\nfile(WRITE "${CMAKE_BINARY_DIR}/actual.txt" "${OVERTE_E2E_FEATURE_TESTS}|${definitions}")\n')
            for result,expected in zip(results,['ON|OVERTE_E2E_FEATURE_TESTS','OFF|']):
                flag=next(value for value in result['variants']['debug'] if value.startswith(FLAG))
                process=subprocess.run([cmake,'-S',str(stage),'-B',str(stage/'output'),flag],text=True,capture_output=True,timeout=30)
                self.assertEqual(0,process.returncode,process.stderr)
                self.assertEqual(expected,(stage/'output/actual.txt').read_text())

    def test_forwarder_is_phone_module_only_and_keeps_root_cmake_default_off(self):
        self.assertIn('option(OVERTE_E2E_FEATURE_TESTS "Enable feature E2E instrumentation in dedicated test builds" OFF)',
            (ROOT/'CMakeLists.txt').read_text())
        self.assertEqual(1,SOURCE.read_text().count("gradleProperty('overteFeatureTests')"))
        source=SOURCE.read_text()
        self.assertLess(source.index('compileSdk 36'),source.index('BEGIN PHONE_FEATURE_E2E_PROPERTY'))
        self.assertLess(source.index('END PHONE_FEATURE_E2E_PROPERTY'),source.index('if (!usePhone16kDependencies'))
        for path in ('android/phone/apps/interface/build.gradle','android/common/build.gradle','android/vr/pico/apps/picoInterface/build.gradle'):
            target=ROOT/path
            if target.is_file():self.assertNotIn('overteFeatureTests',target.read_text())


if __name__=='__main__':unittest.main(verbosity=2)
