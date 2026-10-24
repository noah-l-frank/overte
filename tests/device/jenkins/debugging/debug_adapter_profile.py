"""Only enrich closed request categories; preserve the original CLI JSON protocol."""
import argparse,hashlib,importlib.util,sys
from pathlib import Path
sys.dont_write_bytecode=True

def main():
 p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--profile',type=Path,required=True);p.add_argument('--profile-sha256',required=True);a,argv=p.parse_known_args()
 if argv[:1]==['--']:argv=argv[1:]
 assert a.profile.resolve()==a.profile and hashlib.sha256(a.profile.read_bytes()).hexdigest()==a.profile_sha256
 sys.path.insert(0,str(a.profile.parent));spec=importlib.util.spec_from_file_location('original_debug_profile',a.profile);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);original=module.webdriver_category
 def category(args,kwargs):
  method=args[1]if len(args)>1 else'';path=args[2]if len(args)>2 else'';body=args[3]if len(args)>3 else None
  if method=='GET'and path.endswith('/attribute/focused'):return'normal-focus-observe'
  if method=='POST'and path.endswith('/clear'):return'normal-text-clear'
  if method=='POST'and path.endswith('/value'):return'normal-text-write'
  if method=='POST'and path.endswith('/appium/device/press_keycode')and body=={'keycode':61}:return'normal-focus-tab-request'
  if method=='DELETE'and path.endswith('/actions'):return'normal-input-release'
  if method=='POST'and path.endswith('/actions')and type(body)is dict and type(body.get('actions'))is list and len(body['actions'])==1 and type(body['actions'][0])is dict and body['actions'][0].get('id')=='overte-phone-go-touch':return'normal-go-touch-request'
  return original(args,kwargs)
 module.webdriver_category=category;sys.argv=[str(a.profile),*argv];return module.main()
if __name__=='__main__':raise SystemExit(main())
