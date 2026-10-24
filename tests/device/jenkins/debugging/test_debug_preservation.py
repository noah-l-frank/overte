"""Genuine host subprocess/FS boundaries, no lab, SDK, network or device calls."""
import hashlib,json,os,signal,subprocess,sys,tempfile,time,unittest,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from debug_failure_hold import identity
SOURCE=next((p for p in(ROOT,*ROOT.parents)if(p/'tests/device/run.py').is_file()),None)
if SOURCE is None:
 SOURCE=Path(os.environ['OVERTE_DEBUG_TEST_SOURCE_ROOT']).resolve()
PUBLISHER=SOURCE/'tests/device/jenkins/diagnostic_logs.py'
class HoldTests(unittest.TestCase):
 def scenario(self,kind):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);base=Path(temporary.name);base.chmod(0o700);source=base/'source';source.mkdir(mode=0o700);private=base/'private';public=base/'public'
  input_marker=base/'INPUT';secret='synthetic-secret-host-token'
  module=source/'module.py';module.write_text('from pathlib import Path\nimport time\nPath('+repr(str(input_marker))+').write_text("actual host child started")\nprint('+repr('actual host assertion '+secret+' hifi://private.invalid:40102/')+',flush=True)\n'+('time.sleep(30)\n'if kind=='timeout'else'raise SystemExit(1)\n'))
  owner=source/'tests/device/run_control_plane_tests.py';owner.parent.mkdir(mode=0o700,parents=True);owner.write_bytes((SOURCE/'tests/device/run_control_plane_tests.py').read_bytes())
  inventory=base/'inventory.json';inventory.write_text(json.dumps({'module.py':hashlib.sha256(module.read_bytes()).hexdigest(),'tests/device/run_control_plane_tests.py':hashlib.sha256(owner.read_bytes()).hexdigest()}));inventory.chmod(0o600)
  launcher=base/'native_verify.py';launcher.write_text('print("EXACT_LIVE_CONTROLLER_REQUIRED")\nraise SystemExit(75)\n');launcher.chmod(0o600)
  active=base/'active.json';active.write_text('{}');active.chmod(0o600);start=base/'start.json';start.write_text(json.dumps({'containerId':'c'*64}));start.chmod(0o600)
  policy=base/'policy.json';policy.write_text(json.dumps({'schemaVersion':1,'literalFiles':{n:{'maxBytes':16*1024*1024,'required':True}for n in ('summary.json','junit.xml','diagnostic-events.safe.jsonl')},'logDirectories':[dict(path='logs/module-domain',required=False,maxParts=128,maxPartBytes=1048576,indexMaxBytes=262144)],'maxFiles':200,'maxTotalBytes':64*1024*1024}));policy.chmod(0o600)
  config=dict(schemaVersion=1,enabled=True,runId='host-debug-counter',nonce='d'*32,sourceRoot=str(source),privateRoot=str(private),publicStage=str(public),inventory={'path':str(inventory),'sha256':hashlib.sha256(inventory.read_bytes()).hexdigest()},moduleIds=['domain-enter'],domainRequiredModules=['domain-enter']if kind=='native'else[],nativeGate=dict(launcher=str(launcher),launcherSha256=hashlib.sha256(launcher.read_bytes()).hexdigest(),activeConfig=str(active),activeConfigSha256=hashlib.sha256(active.read_bytes()).hexdigest(),startResult=str(start),startResultSha256=hashlib.sha256(start.read_bytes()).hexdigest()),diagnosticPublisher={'path':str(PUBLISHER),'sha256':hashlib.sha256(PUBLISHER.read_bytes()).hexdigest()},publicLogStreams={'module-domain':'module-domain-enter.stdout-stderr.private.log'},privateValues=[secret],publicationPolicy={'path':str(policy),'sha256':hashlib.sha256(policy.read_bytes()).hexdigest()},hostOriginalRun=str(SOURCE/'tests/device/run.py'),hostOriginalSupervisor=str(SOURCE/'tests/device/jenkins/sequential_campaign.py'),hostModuleTimeout=.2 if kind=='timeout' else 3,hostAdmission=kind=='admission')
  path=base/'config.json';path.write_text(json.dumps(config));path.chmod(0o600);digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if kind=='drift':module.write_text('raise AssertionError("source was changed")')
  log=(base/'worker.raw').open('wb');self.addCleanup(log.close);process=subprocess.Popen([sys.executable,'-B',str(ROOT/'host_hold_worker.py'),'--config',str(path),'--sha',digest],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  def finish():
   release=private/'RELEASE_REQUEST.private.json'
   if private.exists():release.write_text(json.dumps(dict(schemaVersion=1,action='cleanup',contextSha256=digest,nonce=config['nonce'])));release.chmod(0o600)
   try:process.wait(timeout=7)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
  self.addCleanup(finish)
  deadline=time.monotonic()+12
  while time.monotonic()<deadline and not(public/'debug-state.json').exists()and process.poll()is None:time.sleep(.03)
  self.assertIsNone(process.poll(),(base/'worker.raw').read_text());self.assertTrue((public/'debug-state.json').exists(),(base/'worker.raw').read_text())
  hold=json.loads((private/'HOLD.private.json').read_text());self.assertFalse((private/'CLEANUP').exists());self.assertFalse((private/'NEXT_TARGET').exists())
  # The outer supervisor has a .6s deadline; the published hold must survive it.
  time.sleep(.85);self.assertIsNone(process.poll());self.assertFalse((private/'CLEANUP').exists())
  if os.environ.get('OVERTE_DEBUG_TEST_ARTIFACT_ROOT'):
   archive=Path(os.environ['OVERTE_DEBUG_TEST_ARTIFACT_ROOT']);archive.mkdir(mode=0o700,exist_ok=True);destination=archive/(kind+'-'+str(time.time_ns()));shutil.copytree(base,destination)
  return base,config,hold
 def test_first_nonpass_preserves_full_raw_and_no_cleanup_or_next_target(self):
  base,c,h=self.scenario('failure');self.assertEqual('MODULE_NONPASS',h['reason']);self.assertTrue((base/'INPUT').exists());raw=(Path(c['privateRoot'])/'module-domain-enter.stdout-stderr.private.log').read_bytes();self.assertIn(b'synthetic-secret-host-token',raw)
  public=b''.join(p.read_bytes()for p in Path(c['publicStage']).rglob('*')if p.is_file());self.assertNotIn(b'synthetic-secret-host-token',public);self.assertNotIn(b'private.invalid',public);self.assertIn(b'actual host assertion',public);self.assertIn(b'DEBUG_HOLD',public)
 def test_timeout_stops_only_owned_child_and_outer_deadline_does_not_kill(self):
  base,c,h=self.scenario('timeout');self.assertEqual('MODULE_TIMEOUT',h['reason']);self.assertTrue(h['ownedProcessGroupStopped']);current=identity(h['child']['pid']);self.assertEqual(h['child']['birth'],current['birth']);self.assertEqual('T',current['state']);self.assertTrue((base/'INPUT').exists())
 def test_native_gate_failure_holds_before_module_input_with_actual_private_log(self):
  base,c,h=self.scenario('native');self.assertEqual('EXACT_LIVE_CONTROLLER_REQUIRED',h['reason']);self.assertFalse((base/'INPUT').exists());private=Path(c['privateRoot']);self.assertIn('EXACT_LIVE_CONTROLLER_REQUIRED',next(private.glob('native-before-domain-enter-*.private.log')).read_text());events=(private/'events.private.jsonl').read_text();self.assertIn('"nativeRunning": false',events);self.assertIn('"nativeExitCode": 2',events)
 def test_admission_failure_holds_before_original_finally_cleanup(self):
  base,c,h=self.scenario('admission');self.assertEqual('RUNNER_FAILURE_BEFORE_CLEANUP',h['reason']);private=Path(c['privateRoot']);self.assertFalse((private/'ADAPTER_CLEANUP').exists());self.assertFalse((base/'INPUT').exists());self.assertIn('actual host admission failure',(private/'caught-runner-results.private.json').read_text())
 def test_source_drift_holds_before_any_process_input(self):
  base,c,h=self.scenario('drift');self.assertEqual('EXECUTOR_SOURCE_ADMISSION_FAILED',h['reason']);self.assertFalse((base/'INPUT').exists())
if __name__=='__main__':unittest.main()
