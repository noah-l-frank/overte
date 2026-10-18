#!/usr/bin/env python3
"""Execute unchanged production traversal bodies against source-derived native job paths.

Qt Core is real. Render-engine/GPU/config objects are fixture endpoints; the
fixture graph uses names and recursion budgets read from actual registrations.
No rendering or SDK/native application build is claimed. Exit 1 means a useful
behavior expectation failed, rather than counting reproduced defects as PASS.
"""
import argparse, hashlib, json, os, pathlib, re, shlex, subprocess, tempfile
P=pathlib.Path
ap=argparse.ArgumentParser(); ap.add_argument('--root',type=P,default=P(__file__).resolve().parents[4]); ap.add_argument('--output',type=P); args=ap.parse_args()
root=args.root.resolve()
def block(s, marker):
 a=s.index(marker); z=s.index('{',a)+1; depth=1
 while depth: depth+=(s[z]=='{')-(s[z]=='}'); z+=1
 return s[a:z]
paths=['interface/src/scripting/RenderScriptingInterface.cpp','interface/src/scripting/RenderScriptingInterface.h','libraries/render-utils/src/RenderForwardTask.cpp','libraries/render-utils/src/RenderDeferredTask.cpp','libraries/render-utils/src/RenderViewTask.cpp','libraries/render-utils/src/RenderCommonTask.cpp','libraries/render-utils/src/RenderCommonTask.h']
src={p:(root/p).read_text() for p in paths}; render=src[paths[0]]
header=src['interface/src/scripting/RenderScriptingInterface.h']
if ('Q_PROPERTY(bool deferredRenderingAvailable READ isDeferredRenderingAvailable CONSTANT)' not in header or 'bool isDeferredRenderingAvailable() const;' not in header): raise AssertionError('Native QML capability property or declaration changed')
# Fail closed if native names/capabilities have changed; no legacy alias is added.
registrations={
 'lighting': ('libraries/render-utils/src/RenderViewTask.cpp',r'addJob<MakeLightingModel>\("([^"]+)"'),
 'switch': ('libraries/render-utils/src/RenderViewTask.cpp',r'addJob<DeferredForwardSwitchJob>\("([^"]+)"'),
 'forward': ('libraries/render-utils/src/RenderViewTask.cpp',r'addBranch<RenderForwardTask>\("([^"]+)"'),
 'shadow': ('libraries/render-utils/src/RenderViewTask.cpp',r'addBranch<RenderShadowsAndDeferredTask>\("([^"]+)"'),
 'deferred': ('libraries/render-utils/src/RenderViewTask.cpp',r'addJob<RenderDeferredTask>\("([^"]+)"'),
 'mirror': ('libraries/render-utils/src/RenderForwardTask.cpp',r'addJob<RenderMirrorTask>\("([^"]+)"'),
 'mirrorview': ('libraries/render-utils/src/RenderCommonTask.cpp',r'addJob<RenderViewTask>\("([^"]+)"'),
 'aasetup': ('libraries/render-utils/src/RenderDeferredTask.cpp',r'addJob<AntialiasingSetup>\("([^"]+)"'),
 'aa': ('libraries/render-utils/src/RenderDeferredTask.cpp',r'addJob<Antialiasing>\("([^"]+)"'),
}
names={k:re.search(pattern,src[p])[1] for k,(p,pattern) in registrations.items()}
header=src['libraries/render-utils/src/RenderCommonTask.h']; names['depth']=re.search(r'MAX_MIRROR_DEPTH\s*\{\s*(\d+)',header)[1]; names['count']=re.search(r'MAX_MIRRORS_PER_LEVEL\s*\{\s*(\d+)',header)[1]
functions='\n\n'.join(block(render,m) for m in (['void forEachRenderViewConfiguration('] if 'void forEachRenderViewConfiguration(' in render else []) + ['void recursivelyUpdateMirrorRenderMethods(', 'void recursivelyUpdateLightingModel(', 'void setAntialiasingModeForView(', 'void recursivelyUpdateAntialiasingMode('])
cpp=(P(__file__).with_name('render-configuration-traversal.cpp')).read_text().replace('@FUNCTIONS@',functions).replace('@CAPABILITY@', block(render,'bool RenderScriptingInterface::isDeferredRenderingAvailable('))
for k,v in names.items(): cpp=cpp.replace('@'+k.upper()+'@',v)
with tempfile.TemporaryDirectory(prefix='overte-pico-render-traversal-') as t:
 p=P(t); (p/'probe.cpp').write_text(cpp)
 major=os.environ.get('OVERTE_NATIVE_QT_MAJOR','6')
 if major not in ('5','6'): raise RuntimeError('Qt major must be 5 or 6')
 libdir=subprocess.check_output(['pkg-config','--variable=libdir','Qt'+major+'Core'],text=True).strip()
 flags=['-L'+libdir,*shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True))]
 reports=[]
 for profile in ('desktop-ios','android'):
  binary=p/profile
  subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG',*(['-DHOST_ANDROID'] if profile=='android' else []),str(p/'probe.cpp'),'-o',str(binary),*flags],check=True,timeout=60)
  result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=15)
  report=json.loads(result.stdout); report.update({'profile':profile,'source_root':str(root),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'production_sha256':{path:hashlib.sha256(text.encode()).hexdigest() for path,text in src.items()},'source_derived_names':names,'boundary':__doc__,'stderr':result.stderr,'exit_code':result.returncode})
  reports.append(report)
 if args.output: args.output.write_text(json.dumps(reports,indent=2)+'\n')
 print(json.dumps([{'profile':r['profile'],'exit_code':r['exit_code'],'observations':r['observations']} for r in reports],indent=2)); raise SystemExit(max(r['exit_code'] for r in reports))
