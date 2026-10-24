"""Real subprocess counter only: synthetic module, original frozen harness code."""
import argparse,hashlib,importlib.util,json,os,sys
from pathlib import Path
from debug_failure_hold import Policy,DebugCleanupRequested,install_run_hooks,install_admission_hooks
from debug_execute import preserving_execute
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--child',action='store_true');a=p.parse_args();policy=Policy(a.config,a.sha);c=policy.config
if a.child:
 sys.path.insert(0,str(Path(c['hostOriginalRun']).parent))
 spec=importlib.util.spec_from_file_location('host_original_harness',c['hostOriginalRun']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 install_run_hooks(module,policy);policy.native_metadata=lambda _g:{'nativeRunning':False,'nativeExitCode':2,'nativeStatus':'exited'}
 try:
  if c.get('hostAdmission'):
   from types import SimpleNamespace
   module.discover=lambda *_:{'selector':'host-only-selector','capabilities':[],'reservationKey':'host-only-reservation'}
   module.validate_capabilities=lambda _:None
   def adapter_call(_command,operation,*args,**kwargs):
    if operation=='cleanup':(Path(c['privateRoot'])/'ADAPTER_CLEANUP').write_text('explicit cleanup only')
    return {}
   module.adapter_call=adapter_call;install_admission_hooks(module,policy)
   class Identity:
    def verify_description(self,_):raise RuntimeError('actual host admission failure')
   output=Path(c['privateRoot'])/'actual';output.mkdir(mode=0o700)
   os.environ['OVERTE_DEVICE_LOCK_ROOT']=str(Path(c['privateRoot'])/'locks')
   module.execute_prepared(SimpleNamespace(target='host-only-selector',allow_virtual=False,require_complete=True,keep_running=False,suite='all'),{'id':'host-boundary'},Path(c['sourceRoot'])/'manifest.json',Path(c['sourceRoot'])/'catalog.json',[],[],output,Identity(),None,set(),SimpleNamespace(verify_unclaimed=lambda:None))
  else:module.run_module(dict(id='domain-enter',description='Explicit host-only subprocess seam',command=['module.py'],timeoutSeconds=c['hostModuleTimeout']),Path(c['sourceRoot'])/'catalog.json',dict(os.environ),Path(c['privateRoot'])/'module-artifacts','synthetic-host-only-selector',{'synthetic-host-only-selector'},[],set())
  (Path(c['privateRoot'])/'NEXT_TARGET').write_text('unexpected next target')
 except DebugCleanupRequested:pass
 finally:(Path(c['privateRoot'])/'CLEANUP').write_text('explicit cleanup reached')
else:
 spec=importlib.util.spec_from_file_location('host_original_supervisor',c['hostOriginalSupervisor']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 execute=preserving_execute(module.execute,policy)
 try:execute([sys.executable,'-B',str(Path(__file__)), '--config',str(a.config),'--sha',a.sha,'--child'],Path(c['sourceRoot']),dict(os.environ),.6,Path(c['privateRoot'])/'outer.private.log')
 except DebugCleanupRequested:pass
