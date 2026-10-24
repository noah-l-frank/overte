"""Run the reviewed focused entry with explicit first-failure preservation."""
import argparse,hashlib,importlib.util,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
from debug_failure_hold import Policy,DebugCleanupRequested

def main():
 p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--runner',type=Path,required=True);p.add_argument('--runner-sha256',required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256',required=True);a,argv=p.parse_known_args()
 if argv[:1]==['--']:argv=argv[1:]
 policy=Policy(a.config,a.config_sha256)
 os.environ['OVERTE_DEVICE_DEBUG_HOLD_CONFIG']=str(a.config);os.environ['OVERTE_DEVICE_DEBUG_HOLD_CONFIG_SHA256']=a.config_sha256
 try:
  policy.source_guard();policy.native_gate('launch-smoke');assert a.runner.resolve()==a.runner and hashlib.sha256(a.runner.read_bytes()).hexdigest()==a.runner_sha256
  sys.path.insert(0,str(a.runner.parent));spec=importlib.util.spec_from_file_location('debug_focused_original',a.runner);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);original=module.finalize_scene_service
  def final(scene,status):
   if policy.held():policy.wait_existing()
   if status.get('status')!='PASS_ORIGINAL_TARGETED_DIAGNOSTIC':policy.hold('FOCUSED_FAILURE_BEFORE_SCENE_STOP')
   return original(scene,status)
  module.finalize_scene_service=final;sys.argv=[str(a.runner),*argv];result=module.main()
  if result:policy.hold('FOCUSED_ADMISSION_NONZERO')
  policy.publish_terminal();return result
 except DebugCleanupRequested:return 75
 except BaseException as error:policy.record_exception(error,'FOCUSED_ADMISSION_EXCEPTION');policy.hold('FOCUSED_ADMISSION_EXCEPTION')
if __name__=='__main__':raise SystemExit(main())
