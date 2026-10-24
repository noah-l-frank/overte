"""Opt-in, hash-bound bootstrap for the unchanged original focused harness."""
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
from debug_failure_hold import Policy,DebugCleanupRequested,install_run_hooks,install_admission_hooks

def main():
 p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--config',type=Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--run-source-sha256',required=True);a,argv=p.parse_known_args()
 if argv[:1]==['--']:argv=argv[1:]
 policy=Policy(a.config,a.config_sha256)
 try:
  policy.source_guard();path=policy.source/'tests/device/run.py';assert hashlib.sha256(path.read_bytes()).hexdigest()==a.run_source_sha256
  sys.path.insert(0,str(policy.source/'tests/device'));spec=importlib.util.spec_from_file_location('debug_original_run',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  install_run_hooks(module,policy);install_admission_hooks(module,policy)
  sys.argv=[str(path),*argv];result=module.main()
  if result!=0:policy.hold('ORIGINAL_HARNESS_NONZERO')
  return result
 except DebugCleanupRequested:return 75
 except BaseException as error:
  policy.record_exception(error,'HARNESS_ADMISSION_EXCEPTION');policy.hold('HARNESS_ADMISSION_EXCEPTION')
if __name__=='__main__':raise SystemExit(main())
