from pathlib import Path
import argparse
import subprocess,zipfile,os,secrets,hashlib,json
parser=argparse.ArgumentParser(description='Build the device-free public IME geometry probe. Device execution is Proxmox Jenkins only.')
parser.add_argument('--sdk',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=Path(__file__).resolve().parent
root=args.output.resolve();root.mkdir(mode=0o700,parents=True,exist_ok=False)
sdk=args.sdk;tools=sdk/'build-tools/36.0.0';android=sdk/'platforms/android-36/android.jar'
for d in ['classes','dex']: (root/d).mkdir()
def run(args,**kw):subprocess.run([str(x) for x in args],check=True,**kw)
run(['javac','-source','8','-target','8','-classpath',android,'-d',root/'classes',source/'ProbeActivity.java'])
run(['jar','cf',root/'classes.jar','-C',root/'classes','.'])
run([tools/'d8','--lib',android,'--min-api','30','--output',root/'dex',root/'classes.jar'])
run([tools/'aapt2','link','-I',android,'--manifest',source/'AndroidManifest.xml','-o',root/'unsigned.apk'])
with zipfile.ZipFile(root/'unsigned.apk','a') as z:z.write(root/'dex/classes.dex','classes.dex')
run([tools/'zipalign','-f','4',root/'unsigned.apk',root/'aligned.apk'])
env={**os.environ,'PROBE_KEYSTORE_PASSWORD':secrets.token_hex(32)}
run(['keytool','-genkeypair','-alias','probe','-keystore',root/'probe-keystore.private.p12','-storepass:env','PROBE_KEYSTORE_PASSWORD','-keypass:env','PROBE_KEYSTORE_PASSWORD','-dname','CN=Isolated geometry probe','-keyalg','RSA','-validity','30'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
os.chmod(root/'probe-keystore.private.p12',0o600)
run([tools/'apksigner','sign','--ks',root/'probe-keystore.private.p12','--ks-pass','env:PROBE_KEYSTORE_PASSWORD','--out',root/'probe.apk',root/'aligned.apk'],env=env)
run([tools/'apksigner','verify',root/'probe.apk'])
files=['ProbeActivity.java','AndroidManifest.xml']
r={'package':'org.overte.test.imegeometry','apkSha256':hashlib.sha256((root/'probe.apk').read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in files},'purpose':'Public app-window and IME-animation API geometry experiment; not an Overte fix candidate'}
(root/'probe.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
