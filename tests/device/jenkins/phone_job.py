#!/usr/bin/env python3
"""Render the parameterized Pixel job without contacting Jenkins or a device."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET

JOB = 'overte-pixel6a'
AGENT = 'overte-device-pixel6a'
RESOURCE = 'android-device-01'
SCOPES = ['readiness', 'baseline', 'feature-area', 'single-test', 'all-features']
MAX_INDEX_BYTES = 2 * 1024 * 1024
CHUNK_BYTES = 12000
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,95}\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
DEFAULTS = dict(EXECUTION='plan', TEST_SCOPE='readiness', FEATURE_AREA='world-navigation',
                TEST_CASE='domain-enter', FAILURE_POLICY='debug-hold')


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def validate_index(index):
    """Admit a bounded, public selection index produced by phone_selection."""
    _need(type(index) is dict and set(index) == {'schemaVersion', 'catalogSha256', 'scopes',
        'featureAreas', 'singleTests', 'plans'} and type(index['schemaVersion']) is int
        and index['schemaVersion'] == 1, 'Invalid phone selection index schema')
    _need(type(index['catalogSha256']) is str and SHA256.fullmatch(index['catalogSha256'])
          and index['scopes'] == SCOPES, 'Invalid phone selection index identity')
    areas = index['featureAreas']
    _need(type(areas) is list and len(areas) == 14, 'Exactly fourteen registered feature areas are required')
    for row in areas:
        _need(type(row) is dict and set(row) == {'id', 'title', 'suite'} and
              all(type(row[k]) is str for k in row) and IDENTIFIER.fullmatch(row['id'])
              and row['suite'] == 'feature-' + row['id'] and 1 <= len(row['title']) <= 256,
              'Invalid registered feature area')
    ids = [row['id'] for row in areas]
    _need(len(set(ids)) == 14 and 'world-navigation' in ids, 'Invalid registered feature area membership')
    tests = index['singleTests']
    _need(type(tests) is list and 1 <= len(tests) <= 256 and len(set(tests)) == len(tests)
          and all(type(item) is str and IDENTIFIER.fullmatch(item) for item in tests)
          and 'domain-enter' in tests, 'Invalid registered single-test membership')
    expected = {'readiness', 'baseline', 'all-features'} | {'feature-area:' + v for v in ids} | {'single-test:' + v for v in tests}
    _need(type(index['plans']) is dict and set(index['plans']) == expected,
          'Incomplete or foreign precomputed selection plans')
    for key, plan in index['plans'].items():
        _need(type(plan) is dict and set(plan) == {'id', 'scope', 'featureArea', 'testCase',
            'moduleIds', 'setupModuleIds', 'modules', 'requiredCapabilities', 'qualification'},
            'Invalid public selection plan fields')
        _need(plan['id'] == key and plan['scope'] == key.split(':')[0], 'Invalid public selection key')
        area = key.split(':', 1)[1] if key.startswith('feature-area:') else None
        case = key.split(':', 1)[1] if key.startswith('single-test:') else None
        _need((plan['featureArea'] == area if not key.startswith('single-test:') else plan['featureArea'] in [None, *ids])
              and plan['testCase'] == case, 'Invalid public selection dimensions')
        modules, names, setup = plan['modules'], plan['moduleIds'], plan['setupModuleIds']
        _need(type(modules) is list and 1 <= len(modules) <= 128 and type(names) is list
              and len(set(names)) == len(names) and type(setup) is list
              and names[:len(setup)] == setup, 'Invalid public module sequence')
        for module in modules:
            _need(type(module) is dict and set(module) == {'id', 'description', 'timeoutSeconds', 'requires'}
                  and type(module['id']) is str and IDENTIFIER.fullmatch(module['id'])
                  and type(module['description']) is str and 1 <= len(module['description']) <= 2048
                  and type(module['timeoutSeconds']) is int and 1 <= module['timeoutSeconds'] <= 86400
                  and type(module['requires']) is list and len(module['requires']) <= 128
                  and all(type(v) is str and re.fullmatch(r'[a-z][a-z0-9.-]{0,127}', v) for v in module['requires']),
                  'Invalid public module metadata')
        _need([row['id'] for row in modules] == names and
              plan['requiredCapabilities'] == sorted({v for row in modules for v in row['requires']}),
              'Invalid public capability projection')
        _need(plan['qualification'] == {'source': 'registered', 'device': 'not-qualified-for-this-run'},
              'Source presence must never imply device acceptance')
    raw = _canonical(index)
    _need(len(raw) <= MAX_INDEX_BYTES, 'Phone selection index exceeds its fixed byte bound')
    # Catalog descriptions are public repository text; reject accidental private
    # locations and control data instead of embedding them in an artifact.
    _need(not any(marker in raw.decode('utf-8').lower() for marker in
                  ('/home/', '/data/user/', '/data/data/', '-----begin ', '\\u0000')),
          'Private location or control data in public selection index')
    return index


def parameter_choices(index):
    validate_index(index)
    areas = [row['id'] for row in index['featureAreas']]
    tests = index['singleTests']
    return dict(EXECUTION=['plan', 'live'], TEST_SCOPE=SCOPES.copy(),
        FEATURE_AREA=['world-navigation', *[v for v in areas if v != 'world-navigation']],
        TEST_CASE=['domain-enter', *[v for v in tests if v != 'domain-enter']], FAILURE_POLICY=['debug-hold'])


def normalize_request(index, request):
    """Resolve declared Jenkins defaults only; foreign values never fall back."""
    _need(type(request) is dict and not (set(request) - set(DEFAULTS)), 'Invalid phone job request fields')
    choices = parameter_choices(index)
    result = {key: DEFAULTS[key] if request.get(key) is None else request[key] for key in DEFAULTS}
    _need(all(type(value) is str and value in choices[key] for key, value in result.items()),
          'Invalid phone job parameter value')
    return result


def selection_key(index, request):
    row = normalize_request(index, request)
    key = row['TEST_SCOPE']
    if key == 'feature-area':
        key += ':' + row['FEATURE_AREA']
    elif key == 'single-test':
        key += ':' + row['TEST_CASE']
    _need(key in index['plans'], 'Missing precomputed phone selection plan')
    return key


def _descriptor(value):
    _need(type(value) is dict and set(value) == {'controllerRoot', 'controllerManifestSha256',
        'agentLabel', 'deviceResource', 'liveBindings'}, 'Invalid phone job deployment descriptor')
    root = value['controllerRoot']
    _need(type(root) is str and re.fullmatch(r'/[A-Za-z0-9_./-]+', root) is not None and root.startswith('/') and str(PurePosixPath(root)) == root
          and '..' not in PurePosixPath(root).parts and not any(ord(c) < 33 or c in "'\"\\" for c in root),
          'Invalid controller runtime root')
    _need(type(value['controllerManifestSha256']) is str and SHA256.fullmatch(value['controllerManifestSha256'])
          and value['agentLabel'] == AGENT and value['deviceResource'] == RESOURCE,
          'Invalid pinned Pixel deployment identity')
    _need(type(value['liveBindings']) is dict, 'Invalid live deployment bindings')
    return value


def _quote(value):
    # This is a Groovy string literal, not shell escaping.
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + "'"


def _live_bootstrap(descriptor):
    _descriptor(descriptor)
    bindings = descriptor['liveBindings']
    _need(set(bindings) == {'bridgeRelativePath', 'bridgeSha256', 'manifestRelativePath'},
          'The exact reviewed live bridge must be bound')
    for key in ('bridgeRelativePath', 'manifestRelativePath'):
        value = bindings[key]
        _need(type(value) is str and re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', value)
              and not value.startswith('/') and str(PurePosixPath(value)) == value
              and all(part not in ('', '.', '..') for part in PurePosixPath(value).parts),
              'Invalid live bridge relative path')
    _need(type(bindings['bridgeSha256']) is str and SHA256.fullmatch(bindings['bridgeSha256']),
          'Invalid live bridge source pin')
    _need(bindings['bridgeRelativePath'] != bindings['manifestRelativePath'],
          'Bridge and manifest must be separate files')
    root = descriptor['controllerRoot']
    bootstrap = """import hashlib,os,stat,sys
from pathlib import Path
def need(ok):
 if not ok:raise SystemExit('OVT_PHONE_PINNED_DEPLOYMENT_REQUIRED')
def stable(value):
 return tuple(getattr(value,key)for key in('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
root=Path(ROOT_LITERAL)
need(root.resolve(strict=True)==root and root.is_dir())
r=root.lstat();need(r.st_uid==os.geteuid() and not stat.S_IMODE(r.st_mode)&0o022)
expected=EXPECTED_LITERAL
for relative,pin in expected.items():
 path=root/relative;need(path.resolve(strict=True)==path)
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb')as stream:
  before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_uid==os.geteuid()and not stat.S_IMODE(before.st_mode)&0o022 and 0<before.st_size<=2097152)
  body=stream.read(2097153);after=os.fstat(stream.fileno())
 need(stable(before)==stable(after)==stable(path.lstat()) and hashlib.sha256(body).hexdigest()==pin)
bridge=str(root/BRIDGE_LITERAL);manifest=str(root/MANIFEST_LITERAL)
os.execv(sys.executable,[sys.executable,'-I','-B',bridge,'run','--manifest',manifest,'--manifest-sha256',MANIFEST_SHA_LITERAL])
""".replace('ROOT_LITERAL', repr(root)).replace('EXPECTED_LITERAL', repr({
        bindings['bridgeRelativePath']: bindings['bridgeSha256'],
        bindings['manifestRelativePath']: descriptor['controllerManifestSha256']})).replace(
        'BRIDGE_LITERAL', repr(bindings['bridgeRelativePath'])).replace(
        'MANIFEST_LITERAL', repr(bindings['manifestRelativePath'])).replace(
        'MANIFEST_SHA_LITERAL', repr(descriptor['controllerManifestSha256']))
    return bootstrap


def _live_script(descriptor):
    bootstrap = _live_bootstrap(descriptor)
    shell = "set +x\n/usr/bin/python3 -I -B - <<'OVT_PHONE_BOOTSTRAP'\n" + bootstrap + "OVT_PHONE_BOOTSTRAP\n"
    return 'sh(script: ' + _quote(shell) + ", label: 'Pinned Pixel feature bridge', returnStatus: true)"


def _public_export_probe():
    """Read only the sealed, audited public workspace projection, never a DUT."""
    return r"""import hashlib,json,os,re,stat,sys
from pathlib import Path
def need(ok):
 if not ok:raise ValueError('OVT_PHONE_PUBLIC_EXPORT_REJECTED')
def stable(value):
 return tuple(getattr(value,key)for key in('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
def unique(pairs):
 result={}
 for key,value in pairs:
  need(key not in result);result[key]=value
 return result
def relative(value):
 need(type(value)is str and 1<=len(value)<=512)
 if value=='EXPORT_READY':return value
 parts=value.split('/');need(len(parts)<=8 and all(re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,119}',part)and part not in('.','..')for part in parts))
 return value
def main():
 build=os.environ.get('BUILD_NUMBER','');need(re.fullmatch(r'[1-9][0-9]{0,9}',build)and os.environ.get('JOB_NAME')=='overte-pixel6a')
 workspace=Path(os.environ['WORKSPACE']);root=Path(os.environ['OVT_PHONE_PUBLIC_ROOT'])
 need(workspace.is_absolute()and workspace.resolve(strict=True)==workspace and root==workspace/'pixel-job-public'/build)
 if not root.exists():print('WAIT');return
 need(root.resolve(strict=True)==root and root.is_dir())
 initial=root.lstat();need(initial.st_uid==os.geteuid()and stat.S_IMODE(initial.st_mode)==0o700)
 if not(root/'EXPORT_READY').exists():print('WAIT');return
 def read(name,limit):
  path=root/relative(name);need(path.resolve(strict=True)==path)
  parent=path.parent
  while parent!=workspace:
   stamp=parent.lstat();need(stat.S_ISDIR(stamp.st_mode)and stamp.st_uid==os.geteuid()and not stat.S_IMODE(stamp.st_mode)&0o022)
   parent=parent.parent
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
  with os.fdopen(fd,'rb')as stream:
   before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()and stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1 and 0<before.st_size<=limit)
   raw=stream.read(limit+1);after=os.fstat(stream.fileno())
  need(len(raw)==before.st_size and stable(before)==stable(after)==stable(path.lstat()))
  return raw
 seal=read('EXPORT_READY',65);need(re.fullmatch(b'[0-9a-f]{64}\n',seal))
 raw=read('export-index.json',262144);need(hashlib.sha256(raw).hexdigest().encode()+b'\n'==seal)
 index=json.loads(raw,object_pairs_hook=unique)
 need(type(index)is dict and set(index)=={'schemaVersion','job','build','runNamespace','files'}and type(index['schemaVersion'])is int and index['schemaVersion']==1 and index['job']=='overte-pixel6a'and type(index['build'])is int and index['build']==int(build)and index['runNamespace']=='overte-pixel6a-'+build)
 files=index['files'];need(type(files)is dict and 5<=len(files)<=512 and {'artifact-index.json','debug-state.json','summary.json','junit.xml','diagnostic-events.safe.jsonl'}<=set(files))
 total=0
 for name,ref in files.items():
  relative(name);need(name not in('EXPORT_READY','export-index.json')and type(ref)is dict and set(ref)=={'sha256','bytes'}and type(ref['sha256'])is str and re.fullmatch('[0-9a-f]{64}',ref['sha256'])and type(ref['bytes'])is int and 0<ref['bytes']<=16777216)
  total+=ref['bytes'];need(total<=536870912)
  content=read(name,ref['bytes']);need(len(content)==ref['bytes']and hashlib.sha256(content).hexdigest()==ref['sha256'])
 artifact=json.loads(read('artifact-index.json',262144),object_pairs_hook=unique)
 need(type(artifact)is dict and set(artifact)=={'schemaVersion','runId','contextSha256','generation','files'}and type(artifact['schemaVersion'])is int and artifact['schemaVersion']==1 and type(artifact['files'])is list)
 allowed={}
 for row in artifact['files']:
  need(type(row)is dict and set(row)=={'path','sha256','bytes'});name=relative(row['path']);need(name not in allowed and name not in('artifact-index.json','debug-state.json','export-index.json','EXPORT_READY'))
  allowed[name]={'sha256':row['sha256'],'bytes':row['bytes']}
 need(set(files)==set(allowed)|{'artifact-index.json','debug-state.json'}and all(files[name]==ref for name,ref in allowed.items()))
 marker=json.loads(read('debug-state.json',262144),object_pairs_hook=unique)
 need(type(marker)is dict and marker.get('schemaVersion')==1 and all(marker.get(key)==artifact[key]for key in('runId','contextSha256','generation'))and type(marker.get('artifacts'))is dict)
 need(set(marker['artifacts'])=={'artifact-index.json','summary.json','junit.xml','diagnostic-events.safe.jsonl'}and all(marker['artifacts'][name]==files[name]for name in marker['artifacts']))
 expected=set(files)|{'export-index.json','EXPORT_READY'};actual=set()
 for parent,dirs,names in os.walk(root,followlinks=False):
  for name in dirs:
   path=Path(parent)/name;value=path.lstat();need(stat.S_ISDIR(value.st_mode)and value.st_uid==os.geteuid()and stat.S_IMODE(value.st_mode)==0o700 and path.resolve(strict=True)==path)
  for name in names:
   path=Path(parent)/name;need(stat.S_ISREG(path.lstat().st_mode)and not path.is_symlink());actual.add(str(path.relative_to(root)))
 need(actual==expected and read('EXPORT_READY',65)==seal and read('export-index.json',262144)==raw and stable(initial)==stable(root.lstat()))
 print(json.dumps({'state':'SEALED_PUBLIC_EXPORT_VERIFIED','build':int(build),'runNamespace':index['runNamespace'],'files':sorted(expected),'exportIndexSha256':hashlib.sha256(raw).hexdigest()},sort_keys=True))
try:main()
except BaseException:
 print('OVT_PHONE_PUBLIC_EXPORT_REJECTED',file=sys.stderr);raise SystemExit(2)
"""


def _public_probe_step():
    shell = "set +x\n/usr/bin/python3 -I -B - <<'OVT_PUBLIC_EXPORT'\n" + _public_export_probe() + "OVT_PUBLIC_EXPORT\n"
    return 'sh(script: ' + _quote(shell) + ", label: 'Verify sealed public evidence', returnStdout: true).trim()"


def render_pipeline(index, descriptor):
    validate_index(index)
    _descriptor(descriptor)
    choices = parameter_choices(index)
    encoded = base64.b64encode(_canonical(index)).decode('ascii')
    chunks = [encoded[i:i + CHUNK_BYTES] for i in range(0, len(encoded), CHUNK_BYTES)]
    chunk_source = ',\n        '.join(_quote(v) for v in chunks)
    index_sha = hashlib.sha256(_canonical(index)).hexdigest()
    enum_source = json.dumps(choices, separators=(',', ':'))
    default_source = json.dumps(DEFAULTS, separators=(',', ':'))
    parameters = '\n'.join("        choice(name: " + _quote(key) + ", choices: [" + ', '.join(_quote(v) for v in values)
        + "], description: " + _quote({'EXECUTION': 'Plan performs no agent or device access.',
        'TEST_SCOPE': 'One source-registered selection; all checks remain required.',
        'FEATURE_AREA': 'Used only for feature-area scope; source presence is not device acceptance.',
        'TEST_CASE': 'Used only for single-test scope.', 'FAILURE_POLICY': 'Preserve the first failed state and full logs.'}[key]) + ")"
        for key, values in choices.items())
    helpers = r'''import com.cloudbees.groovy.cps.NonCPS
import groovy.json.JsonOutput
import groovy.json.JsonSlurperClassic
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.StandardOpenOption
import java.security.MessageDigest

@NonCPS
Map normalizedPhoneRequest(Map supplied) {
    Map choices = new JsonSlurperClassic().parseText(ENUMS)
    Map defaults = new JsonSlurperClassic().parseText(DEFAULTS_JSON)
    if (!supplied.keySet().every { choices.containsKey(it) }) {
        throw new IllegalArgumentException('PHONE_UNKNOWN_PARAMETER')
    }
    Map result = new LinkedHashMap()
    defaults.each { key, fallback ->
        Object value = supplied[key] == null ? fallback : supplied[key]
        if (!(value instanceof String) || !choices[key].contains(value)) {
            throw new IllegalArgumentException('PHONE_INVALID_PARAMETER')
        }
        result[key] = value
    }
    return result
}

@NonCPS
String phoneSelectionJson(Map supplied) {
    Map request = normalizedPhoneRequest(supplied)
    String encoded = [CHUNKS].join('')
    byte[] raw = Base64.decoder.decode(encoded)
    String observed = MessageDigest.getInstance('SHA-256').digest(raw).encodeHex().toString()
    if (observed != INDEX_SHA) { throw new IllegalStateException('PHONE_SELECTION_INDEX_CHANGED') }
    Map index = new JsonSlurperClassic().parseText(new String(raw, StandardCharsets.UTF_8))
    String key = request.TEST_SCOPE
    if (key == 'feature-area') { key += ':' + request.FEATURE_AREA }
    else if (key == 'single-test') { key += ':' + request.TEST_CASE }
    if (!index.plans.containsKey(key)) { throw new IllegalArgumentException('PHONE_SELECTION_NOT_REGISTERED') }
    // Return a string across suspending Pipeline steps, never a parsed JSON map.
    return JsonOutput.prettyPrint(JsonOutput.toJson([schemaVersion: 1, job: 'overte-pixel6a',
        execution: request.EXECUTION, request: request, catalogSha256: index.catalogSha256,
        selectionIndexSha256: observed, selection: index.plans[key]]))
}

@NonCPS
String phonePublicArchivePattern(String receiptJson, int build) {
    Map receipt = new JsonSlurperClassic().parseText(receiptJson)
    if (receipt.keySet() != ['state','build','runNamespace','files','exportIndexSha256'].toSet()
            || receipt.state != 'SEALED_PUBLIC_EXPORT_VERIFIED' || receipt.build != build
            || receipt.runNamespace != 'overte-pixel6a-' + build || !(receipt.files instanceof List)
            || receipt.files.size() < 7 || receipt.files.size() > 514
            || receipt.files.toSet().size() != receipt.files.size()
            || !(receipt.exportIndexSha256 ==~ /[0-9a-f]{64}/)) {
        throw new IllegalStateException('PHONE_PUBLIC_EXPORT_RECEIPT_REJECTED')
    }
    List paths = []
    receipt.files.each { name ->
        if (!(name instanceof String) || name.length() > 512
                || (name != 'EXPORT_READY' && !(name ==~ '(?:[a-z0-9][a-z0-9._-]{0,119}/){0,7}[a-z0-9][a-z0-9._-]{0,119}'))
                || name.split('/').any { it in ['.','..'] }) {
            throw new IllegalStateException('PHONE_PUBLIC_EXPORT_PATH_REJECTED')
        }
        paths.add('pixel-job-public/' + build + '/' + name)
    }
    return paths.join(',')
}

@NonCPS
void publishPhonePlan(String content, int expectedBuild) {
    def run = currentBuild.rawBuild
    if (run.parent.fullName != 'overte-pixel6a' || run.number != expectedBuild || !run.isBuilding()) {
        throw new IllegalStateException('PHONE_PLAN_OWN_ACTIVE_BUILD_REQUIRED')
    }
    def manager = run.artifactManager
    if (manager.class.name != 'jenkins.model.StandardArtifactManager') {
        throw new IllegalStateException('PHONE_PLAN_STANDARD_ARTIFACT_MANAGER_REQUIRED')
    }
    def archive = run.artifactsDir.toPath().toAbsolutePath().normalize()
    def expected = run.rootDir.toPath().toAbsolutePath().normalize().resolve('archive')
    if (archive != expected || Files.isSymbolicLink(archive)) {
        throw new IllegalStateException('PHONE_PLAN_ARCHIVE_SCOPE_CHANGED')
    }
    if (!Files.exists(archive, LinkOption.NOFOLLOW_LINKS)) { Files.createDirectory(archive) }
    if (!Files.isDirectory(archive, LinkOption.NOFOLLOW_LINKS)) {
        throw new IllegalStateException('PHONE_PLAN_ARCHIVE_NOT_DIRECTORY')
    }
    def output = archive.resolve('selection-plan.json')
    byte[] body = content.getBytes(StandardCharsets.UTF_8)
    if (Files.exists(output, LinkOption.NOFOLLOW_LINKS)) {
        if (!Files.isRegularFile(output, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(output)
                || !Arrays.equals(Files.readAllBytes(output), body)) {
            throw new IllegalStateException('PHONE_PLAN_EXISTING_ARTIFACT_CONFLICT')
        }
    } else {
        def stream = Files.newOutputStream(output, StandardOpenOption.CREATE_NEW,
            StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)
        try { stream.write(body); stream.flush() } finally { stream.close() }
    }
    if (!Arrays.equals(Files.readAllBytes(output), body) || run.parent.fullName != 'overte-pixel6a'
            || run.number != expectedBuild || !run.isBuilding()
            || run.artifactManager.class.name != 'jenkins.model.StandardArtifactManager') {
        throw new IllegalStateException('PHONE_PLAN_PUBLICATION_READBACK_FAILED')
    }
}
'''.replace('ENUMS', _quote(enum_source)).replace('DEFAULTS_JSON', _quote(default_source)).replace(
        'CHUNKS', chunk_source).replace('INDEX_SHA', _quote(index_sha))
    # beforeAgent prevents plan builds from even allocating the Pixel executor.
    pipeline = '''
pipeline {
    agent none
    options { disableConcurrentBuilds(); skipDefaultCheckout(true) }
    parameters {
PARAMETERS
    }
    stages {
        stage('Selection plan') {
            steps {
                script {
                    String plan = phoneSelectionJson(params as Map)
                    publishPhonePlan(plan, currentBuild.number as int)
                    echo(plan)
                }
            }
        }
        stage('Live execution') {
            when { beforeAgent true; expression { normalizedPhoneRequest(params as Map).EXECUTION == 'live' } }
            agent { label 'overte-device-pixel6a' }
            steps {
                script {
                    Map request = normalizedPhoneRequest(params as Map)
                    lock(resource: 'android-device-01') {
                        withEnv(['OVT_PHONE_EXECUTION=' + request.EXECUTION,
                            'OVT_PHONE_SCOPE=' + request.TEST_SCOPE,
                            'OVT_PHONE_AREA=' + request.FEATURE_AREA,
                            'OVT_PHONE_CASE=' + request.TEST_CASE,
                            'OVT_PHONE_FAILURE_POLICY=' + request.FAILURE_POLICY,
                            'OVT_PHONE_RUN_NAMESPACE=' + env.JOB_NAME + '-' + env.BUILD_NUMBER,
                            'OVT_PHONE_PUBLIC_ROOT=' + env.WORKSPACE + '/pixel-job-public/' + currentBuild.number]) {
                            int bridgeStatus = -1
                            boolean bridgeFinished = false
                            boolean publicationFailed = false
                            parallel(
                                'Run selected tests': {
                                    try {
                                        bridgeStatus = __LIVE_CALL__
                                    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException interrupted) {
                                        currentBuild.result = 'FAILURE'
                                        throw interrupted
                                    } catch (Exception transportFailure) {
                                        currentBuild.result = 'FAILURE'
                                        echo('PHONE_BRIDGE_TRANSPORT_FAILED: resources remain held; no cleanup was requested.')
                                    } finally { bridgeFinished = true }
                                },
                                'Publish sealed public evidence': {
                                    try {
                                        String patterns = null
                                        waitUntil(initialRecurrencePeriod: 5000, quiet: true) {
                                            String receipt = __PUBLIC_PROBE__
                                            if (receipt == 'WAIT') {
                                                if (bridgeFinished) { error('PHONE_PUBLIC_EXPORT_MISSING') }
                                                return false
                                            }
                                            patterns = phonePublicArchivePattern(receipt, currentBuild.number as int)
                                            return true
                                        }
                                        archiveArtifacts(artifacts: patterns, allowEmptyArchive: false, followSymlinks: false)
                                    } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException interrupted) {
                                        currentBuild.result = 'FAILURE'
                                        throw interrupted
                                    } catch (Exception publicationFailure) {
                                        publicationFailed = true
                                        currentBuild.result = 'FAILURE'
                                        echo('PHONE_PUBLIC_EVIDENCE_ARCHIVE_FAILED: retain private evidence and inspect this build.')
                                    }
                                }
                            )
                            if (publicationFailed && bridgeStatus == 0) { bridgeStatus = -1 }
                            if (bridgeStatus != 0) {
                                currentBuild.result = 'FAILURE'
                                if (bridgeStatus != 77) {
                                    input(id: 'pixelBridgeFailureHold',
                                        message: 'The Pixel bridge failed. The original failed state and resource are retained. This action releases only this Jenkins hold and requests no device cleanup.',
                                        ok: 'Leave failed run and release resource')
                                }
                                error('PHONE_LIVE_FAILED_NO_CLEANUP_OR_NEXT_TEST')
                            }
                        }
                    }
                }
            }
        }
    }
}
'''.replace('PARAMETERS', parameters).replace('__LIVE_CALL__', _live_script(descriptor)).replace('__PUBLIC_PROBE__', _public_probe_step())
    return helpers + pipeline


def render_job_xml(index, descriptor):
    script = render_pipeline(index, descriptor)
    root = ET.Element('flow-definition', {'plugin': 'workflow-job'})
    ET.SubElement(root, 'description').text = 'Overte Pixel 6a: plan by default; one governed selection per live build.'
    ET.SubElement(root, 'keepDependencies').text = 'false'
    properties = ET.SubElement(root, 'properties')
    definitions = ET.SubElement(ET.SubElement(properties, 'hudson.model.ParametersDefinitionProperty'), 'parameterDefinitions')
    for name, values in parameter_choices(index).items():
        parameter = ET.SubElement(definitions, 'hudson.model.ChoiceParameterDefinition')
        ET.SubElement(parameter, 'name').text = name
        ET.SubElement(parameter, 'description').text = 'Source-registered Pixel selection: ' + name
        choice = ET.SubElement(parameter, 'choices', {'class': 'java.util.Arrays$ArrayList'})
        array = ET.SubElement(choice, 'a', {'class': 'string-array'})
        for value in values:
            ET.SubElement(array, 'string').text = value
    definition = ET.SubElement(root, 'definition', {'class': 'org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition', 'plugin': 'workflow-cps'})
    ET.SubElement(definition, 'script').text = script
    ET.SubElement(definition, 'sandbox').text = 'false'
    ET.SubElement(root, 'triggers')
    ET.SubElement(root, 'disabled').text = 'false'
    return ET.tostring(root, encoding='unicode') + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--deployment', type=Path, required=True)
    parser.add_argument('--format', choices=('pipeline', 'xml'), default='xml')
    args = parser.parse_args(argv)
    from phone_selection import build_index
    index = build_index(args.catalog)
    descriptor = json.loads(args.deployment.read_text())
    print((render_pipeline if args.format == 'pipeline' else render_job_xml)(index, descriptor), end='')


if __name__ == '__main__':
    main()
