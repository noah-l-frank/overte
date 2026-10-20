#!/usr/bin/env python3
"""Pure protected affected-suite selection; no suite/build/runtime execution."""
from copy import deepcopy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch, Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inputs


def blob(raw=b'fixed', *, mode='100644'):
    return {'mode':mode,'type':'blob','sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}


def definition(scope='content'):
    return {'command':['python','contracts/test.py'],'layer':'host','scope':scope,'environment':'host-qt5-qt6',
        'closure':{'kind':'patterns','inputs':['contracts/**','source/**'],'required':['contracts/test.py']},
        'python_imports':{'roots':['contracts'],'reviewed':'sha256:'+'0'*64}}


class AffectedPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tree={p:blob(p.encode(),mode='100755' if p=='tests/run-project-tests.py' else '100644')
                   for p in inputs.AFFECTED_AUTHORITY}
        self.tree['tests/platform-profile.json']=deepcopy(inputs._AFFECTED_SHARED_PROFILE)
        self.tree.update({'contracts/test.py':blob(b'fixed test'),'source/input.qml':blob(b'fixed data'),
            'tools/test-evidence/sandbox_host.py':blob(b'old controller'),'unrelated/readme.md':blob(b'data')})
        finite=definition();finite['python_imports']['reviewed']=inputs.python_import_digest(self.tree,['contracts'])
        self.registry={'schema':1,'control_inputs':['tests/run-project-tests.py','tools/test-evidence/**','*.py'],
            'suites':{'finite':finite,'unproved':{'command':['python','unknown.py'],'layer':'quick','scope':'content',
                'environment':'host-qt5-qt6','closure':{'kind':'repository','inputs':[],'required':[]}},
                'candidate':definition('candidate')}}
        self.dependencies={'schema':1,'lookup_digest':inputs.affected_lookup_digest(self.tree),'registry_digest':inputs._suite_definition_digest(self.registry),'suites':{
            n:{'kind':'repository' if n=='unproved' else 'reviewed-patterns',
               'definition_digest':inputs._suite_definition_digest(s),'setup':['host-full'] if n=='unproved' else ['python']}
            for n,s in self.registry['suites'].items()}}
        self.seal()
        self.candidate=deepcopy(self.tree)
        self.candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed candidate controller')

    def seal(self):
        self.raw=json.dumps(self.dependencies,indent=2).encode()
        self.tree[inputs.AFFECTED_POLICY]=blob(self.raw)

    def plan(self,base=None,candidate=None,trusted=None,raw=None,registry=None):
        return inputs.plan_affected(registry or self.registry,self.raw if raw is None else raw,
            self.tree if base is None else base,self.candidate if candidate is None else candidate,
            self.tree if trusted is None else trusted)

    def test_changed_controller_selects_unproved_and_candidate_owners_individually(self):
        plan=self.plan()
        self.assertEqual(plan['required'],['unproved','candidate'])
        self.assertEqual(plan['omitted'],['finite'])
        self.assertFalse(plan['reusable'])
        self.assertEqual(plan['required_setup'],['host-full'])
        self.assertEqual(plan['paths'],['tools/test-evidence/sandbox_host.py'])

    def test_own_data_and_discovery_changes_select_their_suite(self):
        for path in ('source/input.qml','source/new.qml','contracts/data.json'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate);candidate[path]=blob(b'changed')
                self.assertIn('finite',self.plan(candidate=candidate)['required'])

    def test_lookup_shadows_native_modules_pth_and_deletions_are_not_hidden(self):
        for path in ('contracts/json.py','contracts/sitecustomize.py','contracts/module.so','contracts/path.pth','contracts/test.py'):
            with self.subTest(path=path):
                candidate=deepcopy(self.candidate)
                if path in candidate:del candidate[path]
                else:candidate[path]=blob(b'new lookup candidate')
                with self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_historical_unreviewed_module_on_both_sides_keeps_owner_required(self):
        base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
        for tree in (base,candidate):tree['contracts/historical.py']=blob(b'child variant')
        with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_nonregular_inventory_anywhere_declines_even_if_unchanged(self):
        for mode,kind in (('120000','blob'),('160000','commit')):
            with self.subTest(mode=mode):
                base=deepcopy(self.tree);candidate=deepcopy(self.candidate)
                for tree in (base,candidate):tree['other/entry']={'mode':mode,'type':kind,'sha':'a'*40}
                with self.assertRaises(inputs.InputError):self.plan(base=base,candidate=candidate)

    def test_candidate_cannot_add_replace_remove_or_enable_its_graph(self):
        for which in ('candidate','base','trusted'):
            for operation in ('remove','change','mode'):
                trees={n:deepcopy(t) for n,t in (('base',self.tree),('candidate',self.candidate),('trusted',self.tree))}
                if operation=='remove':del trees[which][inputs.AFFECTED_POLICY]
                elif operation=='mode':trees[which][inputs.AFFECTED_POLICY]['mode']='100755'
                else:trees[which][inputs.AFFECTED_POLICY]=blob(b'candidate narrowed graph')
                with self.subTest(which=which,operation=operation),self.assertRaises(inputs.InputError):self.plan(**trees)

    def test_every_authority_change_declines_before_selection(self):
        for path in inputs.AFFECTED_AUTHORITY:
            candidate=deepcopy(self.candidate);candidate[path]=blob(b'new authority')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):self.plan(candidate=candidate)

    def test_closed_policy_registry_definition_and_global_controls_are_bound(self):
        mutations=[]
        for change in ('schema','unknown','missing','definition','arbitrary-kind','setup','duplicate-setup'):
            value=deepcopy(self.dependencies)
            if change=='schema':value['schema']=True
            elif change=='unknown':value['force']=[]
            elif change=='missing':del value['suites']['unproved']
            elif change=='definition':value['suites']['finite']['definition_digest']='sha256:'+'f'*64
            elif change=='arbitrary-kind':value['suites']['finite']['kind']='caller-selected'
            elif change=='setup':value['suites']['unproved']['setup']=['python']
            else:value['suites']['finite']['setup']=['python','python']
            mutations.append((change,json.dumps(value).encode()))
        mutations += [('duplicate-key',self.raw.replace(b'"schema": 1',b'"schema":1,"schema":1')),
                      ('oversized',b' '*64001),('wrong-type','{}')]
        for change,raw in mutations:
            with self.subTest(change=change),self.assertRaises(inputs.InputError):self.plan(raw=raw)
        registry=deepcopy(self.registry);registry['control_inputs']=[]
        with self.assertRaises(inputs.InputError):self.plan(registry=registry)

    def test_missing_unknown_empty_and_wrong_policy_bytes_fail_closed(self):
        for tree in (None,{},[] ):
            with self.subTest(tree=tree),self.assertRaises(inputs.InputError):
                inputs.plan_affected(self.registry,self.raw,tree,self.candidate,self.tree)
        with self.assertRaises(inputs.InputError):self.plan(candidate=self.tree)
        with self.assertRaises(inputs.InputError):self.plan(raw=self.raw+b' ')


# Fixture-only projection of the REVIEWED PROPOSED SOURCE snapshot, not protected D.
# 7811163cf12c49516700b4eecf331689bf7b6c3d / tree 56235f604183c46fcd476f943c77c2b3173f9b8d.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '5ccd7a888e514ee8559d8ac2f2dfd6c32d582c1976b9bdef0e945a4387a69567'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TSs!Rj&#cQ-ZFt$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO-_qR4XpQ|CoD<&(e5@^)ELInGnvWK)+fS-H%4'
    '?*GHfACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hm&%K3*xyYA1jcwO<O|$sDSv3}Q-IQHfrJ`)}=KaN=(&O>@@N#_m<J0stO}}ofSWi`3ES_tdcgsBYDW!g?t0k-E'
    '-Vg1&p)9I2R`0L)lAd2aJ-;4a(x*8+riVE_Ooz0&?mSj=GYw<bEJcxzRg+hK>^RI-J=b39P!xSJ6noa)TB{wWF(3Q3?Hm8?savML'
    'p8B%OrXnAPq3oNyue*ADf33Gy`RwIBrH7YK|9l<p56fX%-|Bz;@$LTo)%&iUyCs|RzDreB<hkFxlx5L1Lv7U}`MW7^t6i%<9e+vF'
    '%cuD5&zF~7s<x?@p>a%>G^aYBmS%4Ad@ib?uZyXkvy_#WKBYgG{m+l;;?hO2q-<{HvY+!JTe>XE`aUl$Kl|}@(PeX&jnz*M?D%9k'
    'kzu+&c*>ur!{=Yp!>@;j=g(h;c+Zc2yuYdkJ5}Q}6=PLZ?O0Tu@2kk$I?Z)g)%jAVylu1MnpGeDaxeVyy4BK_sTxw-m18!wg&((c'
    '<2Vn^xD@S@wOy9dG+npualE|hGAwO2l~tR2yLFNELnbnmV>R`utEP4trlIc2tDf=G>%+x0r#Pa`ybS$Vb*-N_^ktLvT|Sm+Ohq-1'
    'S(}#Ssx{+FzMH;29lxc!=jr%(`B!&!m1Umn;A?88E={Q)>T+l^AC=fuPjf$a`E}2F-ND1~Ej<g|>Fy~FkB5gZ7q>BYRkch_s+&sG'
    'OnH^cyf3P1n8qe+^16y>=Bm1W8;{@arsKnMxV(Nl<f-Y(x@pA8^;&GoBCE${=<0bcGMf`~s`Bdf<6fTce*bM5FRnlO&a$eS>$-JG'
    ')R`wy54~{ehV(_2o<in+9<E;B7wD?IxOSSBvK#7Rt{uEmXm6){%*$+WYfVFucXL@a*^b{H5#?XQAD<u6OGLW6r{n8Ox|<Kfmxtr?'
    '%VD}4ZOVQc2LU~=r#e+$zv!L@S7%l?wNG#!i$TiLU%idj`SIeyMb|cY%8NO*4*cB5)3*~>$TAlW!ZP|2Q`_!d`1IkOS6>se_yk|l'
    '?=P1FQ0=g{X(-BCUQ(vmRNbd`bg|S$pQbz$ADZoOdq2nvUyk1n(<fo?x5Kj=)dBoGyv~Q0yYr0~x9r6eS=VW(=3*FADi_gko~ypE'
    'sxD$;-qi6jJel_9-K?iF4#)lQDwn(*rP`*P=3;L8%KK>ML3Y#hUC}Sg+?JV)E@hIf?DoyPN+&Nz%6S^{ZYmm?NA0%{^;ER32FFCY'
    'S9eP-(JG6S-@J!k)6+w`zgyqZ#hvuU=z+{_GtKQ-wu>BS8Rw#@bNSfPBzc+dw^(l8$+zJ_x;@{?@qNlqf82dNJV&l_aaUPfT+LE-'
    'W0odiq)oNU%q=Qc$V)rS+R9V9eOJfPf9SW3VAf1gxlHvaTFUX;*4I0f*<4OtnS4RwSQG#D_FX)lE05uRJ=IUc^l~|{b#v7fZ6zr!'
    '7Ab0<)pglUb2l`F&$_6xewMM0{momFQ!V$0FJE7F$J(YX7a3JHRQ2d;NzQrR<;tVf#siwmOwG2m;|I31m2P<ewNf){`!Xw=qRWfO'
    'y4uLEi{9JIy0YuaV!n9`(vDfMJN)Kg-+g~Xm$Lxhidv#y)Nh_asazEI$42m7MpfgIPvTE@`(t^2ajq_ZEWJ;ojipER)HJz-mfm+e'
    'c~Gr#vTf_KuRm~#UWTVHY4<I#NO-ehnq?nL;~Pm1c3!o$kED$!)W{F|EZzQ=PTA_)RWKf3ALd~r(D+PxACC0gYsp|2L!&fm>Sn5x'
    'y-k%3xjLarf770JTu)_M)VuxI^kr41UbUT#%M4iYC3myWI3mupWFOqodPm*u3WHNEe=l+uri-yF(lE?v?0ng(oS`hsx*iv4)(78P'
    'did?|bbR>cKX`g|m&>{$aGoB{RF30VPmL>L9Gax8PD3{qo|zkcE<d)X-M45rRP9izD%xgD9gJqKRJRf^<>e^%Z5((zs{X$1+#Mu='
    'Urx8jMkY9poeyemizyR`M=xvao2l<y7Nt9FOiN+AAKThZxBS=wv?Rp7@uhE*EM$s0vFnR`l8aPJRSt7M{Y_h&j^9?CWb1)7%aF=m'
    'B472nKpF3|lQaw8cH7MPxVUG#a{haE^_+f74;xjrlC_5jd4Y;Z0U-0dx-55n6lLn5p`}1Rd~83vB7yX<>dSx_=Ct%v-wbZtA!{7|'
    '2_Ty{UTCh&{oq!9$cnxl_I%?#jClxvp-iQktDUE|9{YS8Kn8YK7DLMCp;|t+uj^AI?`@DX!a?e>447-l;1GFJR6cQlabbs5wu~R$'
    'm;C5%dV(W9yc~x6=M8i~$yHT_i?-`WY1^`RSdkOtqhvQPCm5j0^}~DGlM<9Je;<zjfffxpoK@jff%G9aW!ETB^P!!K;$xe+A$yZU'
    'j!WL;P2+?qn}>Rl{kQc}<!Q)WIfZ*LFQ$)e?D_cm1k{?2UlZJVx}42fZ_X4&gC`RxTbctJFRMOE0HFEop-mvB4{j;4%DWvUEQCqE'
    '2J9=^T4lD3?wJDWGM7c2;GV)$mvwpdcWh@F4)?DcKyO!dQyNk|WK}&(8YZpWc9647g~v3NW!Gz<<RAR5U%ovqhx_!sTDyGwTbF)Q'
    '4yrS7kcioUWjvNqzMBOktFu$o%?H2km#5d~7dOeT>5r!^Xw;dPUpn8_m~!8A?;UBk$aBZsN2U2v&0YFPMR3JtBFom}Xkns7ukDkD'
    'r4YlbYRsIlX{^e+hehnW{?8!w`QKc=E#?v$=(B*1wzd00L7&NF>wK&wvM}1Zo4RgahW+Jr4R`73+u`|n?IB)F#>T$akBCOc(xq{R'
    'X=s)z6US<3tJF=|FpD|+e)892y#3>GE8xckt)A$HzOAN8Tec9|qJ8NGpR;@h$2lhZ);y&xmqTaXPlbb5YJbd;MFGB34&VZtEbg2+'
    'FYRI8mp?tY{C`V#!~E@V`6kiXkbH=L`B*fK?gvz2UZz23%l|6@T$O@hXF+gYbq|=BWiD}LSrka^l%_^uUpetmkbsXS<(e?C?_2uu'
    'B<;>IrZP{(sK{3zM%AhVq>ZX|sj1nOSuu}25PoO9_+!6k&rxb;wMA9Va|z|I+bRnD)XSbrN7-ksmR6h1?G=lk3e)NMl<t0UJwBw%'
    'HAI9~!Azf{(mrmRriC*1Syb-5W>lk29j0X`M)%_mz8!x{Ycc8y+PDgHxMZuXnvGpK1dJ=Kk#xr02p8*B?XAW`KkVPbbx~!SJn^h_'
    'tTU~zQlqOL^QF{1chZszD4_~W{kVVqouMV47qw$IM6C@+X*(w_5I0A>a}cXec$asV`xidNmmSYs4dlIR<`%B6B6kWqx%60St`=@w'
    '05Rx9|MS|V|14oI-ys^=nY3q+x&{`~7Bc(Jg9qqmUUv>Bk&rF7FMsa#O^>gapM!IkPhH_py>+w@b%vX)ffBpt^b@*Pqou!LBm34b'
    'ms*oEm-T6OO1@;Ni}O$x{-7J63r#W3+4Y}*gni|5I10nlWh`hM-K0fyS=}m=kXP6CG^L{U5hlU0lWENJc=HzaJ&D%yw_c{{Js=y*'
    '{)%nj;ScKL<Yt##)$)uRw(-Zy*W<%JKr=pmMFLRAc~C#02&KB!M5zEPdQ7Tg&#SuOVLYWTFdc=;eD|-X;qh@R%bLba`MdZigo41p'
    'T#jQs=n1RHQ?51;8HO7^48YRmCTxRRqo+55wx_v@)*@(d(QPZn2$8{1tF=j{{Y&pp2>N#Dhcd_|i)KWcGdEHN-Kr!9b3N)Z1_frh'
    ';y$`5E6`u4HN6|p-%lQ~;&eOlxm?$So#4(*Q&aA!hEBiy)8XOq_2sj-et%|FeUjmS`d5;8gVj_-7k8sq7gegazJ7m`%wDMoS_?n~'
    '+`V`#MZF_S`pa&t{wd8teEM-?QF`1BFY)NMfuli{C{0s?6gWtOuVQj~l_hPZ_RuFz@zw4CN8j7n7HMa30wRC%Sc<?JT%j{Qn(Cv~'
    '`mD!k5x}|~l$rIiej_(tUQ(*&+l=f~vsXlj4)~}RYg32S=!oKpw8OG<$v0>$V&$FpFg$%bKHa_g&uwHab>SemBXwNhVH38YoDtND'
    'k(cKSnpmzF6~_1O<5YQmI&&pHKR-?XUz10+H}?M;o#g$koH!*>V6B<v2A(Os?K-?cuL$?Fl5!0VJOfbf{CYM6%5U3!U^{OB!n&=?'
    'S#LGA1uEe*iK#-W^Q-2l@Fy1Ouzg5A7lfl5H?xvBPhU4O>F~V!^O+mxRT`KIP*joJ#=-6M*3{m^T>B$gVzYyOwYjhH^>9C*@SnYa'
    'tH{<N0u@7#0i;Kj&4NJNwt;}a$h2F^;AiF^-`p9q`{A)|@K7APcwR!ngs%yy%c2{s$$*j56v24NQ(t|2V+U=Zr?;1SCY@hK7WAnK'
    '?72?2JjctK^XPVz8pZ`a9eyFgdEWJZ!_FSuS@)VA!;@Cu<*zJ>&?78b*IKFvI~P5*`9Vq}YK)p!+ZbuO{`js=Nsk!uLx=YAr8*8s'
    'UM+CZyUPTs*@2vUpPDZY+ZHMS_3y@yZ|$1cHOn)6`#ya9dGWjGH2o2rB9v+%N7qBWHvA38@|><8zO9w)>-hL}c-~+~BTY8KyzNcu'
    '*gz9xNCUta0YHiC!qI-1#=qekJ6(ml;OkbOQ<Q-1Oa%b3?N-QiN#m3?#S|p9!h_4w$2awS__DGi4x}I|-yMgt1}wS^6@370ngsaq'
    '*mVwr*3~4@^}yh(>3_rC)=Xzd+r3LP1<_tZe(imGs$mro{Ya{nh}cMJhCcrdhu}>JaCtk6{xKFPNLFeC8tTA8P0^?e`Z^ClTEEnd'
    'aN~B~_VD?-t5Ux|^fNXzj{#S8ZYCUML<!Wb5o!Uo&D)#b;`d#x7v%=)CZH?iZ1>?HPF0Sg#2bzU*By&8gbIkwAAUaP5PuocDT_j}'
    '<jQd&qe4Jf@ma)p5Q3<VR^CH9tNNpR*>TJYjG7?zp=7jBM!a2}_EA1e-2mO32HB{7cKhM2oa=|b9=44LkVUz)v^pol2x2eGtfizu'
    'T7`jnVbM_mfPZvrS8NF=2=EaV@wF-m)fl8z`CnepG0mYF3wS)cP)*K<rw|aGcb1Cu){0mG*<pIw#)22!oF$udLzTAO)JHzmXAp>{'
    'go(q+l{G_KUbBa-B36~A2r0U{RURk^DDukSGHWZ%q!<dyHm3#L{kwNIn)G`!YKDqJEujmQL?^u(9@!$TO0`@UBJY3pak~D7hh+=3'
    'NQDMJ64ww#vEDy4(GMe9qE3_Jpi?zo^v@Wa^Knv(%QA=i&v&T$KS;Fh;@@rb>n!U7E-`)MK1(C~s-`IMbyWmo!4xmsAzfZJD2JCZ'
    'nSNf-&h-VlBoU&j#GqAikD*=h&6EP3URHT|nNz~E{{2R;w=c&!V3u*I+onJnq=jk~ZKW<%ME^uIGymjA1^ksB0u}!}JiQz!rzFZN'
    ')8%D@LoPd?G4G(kt`c&bET8m>>PU-&R#}7wPrK~mlIxcuG561#bhbQd0S$eG-w8)5!)Ki{kXw@!?%h<=H;Ms2yJP=j!4om$@^>->'
    'vR9WGmKwmf)n;rEpnUOVuNtUNb@8<E`<}<+x4Ylm+Vgfw1IFyt)U~4x9D(tpe!*&%0nr-EP-ZxfB(gs_=BI3BPQM-EEvoMxUt;w='
    'iCz}s1T>NWEFJh1i*;08%6ymPi2t6=nx4bfqVw?h655$H!u-dIp5C9&)l<v7M%<_liaQRvO#0Wb1Yxvo^SOhZVz=*G@%g)|`cYBv'
    '{f{pPwjw&JQ`Y%(^)!ffkXJzHxgE3^z?sHMIZnfkJ9vCNynegevymy-+PX=pUE8>2A~&W|ts^;$SdSKr!Z6fVZe-U(z?W&X*GBQS'
    '3ZiHW3@DHz<R3%Pj8ivIJCGV)yY_UvcfTA@Dg2rCxc%*yRUr2xHCsPA+HROa^8&mcOg@4XJ?2i9KVQ3>6)?X0k~G}6T8@ZbD8|l$'
    'ZoaTqMLvenP<5$U`l^K_!{Ah9ySK1@2fN+{O2Le7wg_lJHLELRtA$3Vi1t6s$a{ck6}#WX|3BV=&c(NlC6R19X$3}NMqcZ8&Jh4x'
    'p;kLxRor41XuXzumz>k{uew)v$LaO{@cXW34_1w(^{qfBjg$wCM=7pz(pTu^xJ(F4vXdLP@a6IK?kj%eeR|%2HT4u{#UrB!?GnxY'
    'yecIoAe}OLYXy#-w~?~HVIN4*u6I=T4W5w}ji`V)hC|vcOSJvwD4BwbP?3{U*OX=c_iShdn07Ry0}QW2w^2?@G0i%^)DkrnGO0p}'
    'SD1o#RW>*7%EkSJ8S#Ah)jz)d)5XL~6@;47S8^c60t=9-)sdyhoIBmFIb_jV2*r*2IUx|kANK-U)JW;@-WB^-NHs(Jl^tbE!#P8D'
    'zD6NQY&@#S-&-yFyiE12$Li|+<i#j(Otd3K*Q+J4Xs9GSvsn!;q)w9W@~5sMKi|){<MivU!##A-!%<YXydH3M@ONBkA><ED)Do-('
    'ng25FUHDurj)#YNi+!n54P}^MHsy5bzELDlgr&I&>?{{tiBP9z_j!IiOvmc;a`^ovQ2!PDyd2j;vm>FCN9a99SsZi$>13cDkYhE7'
    'tfTF&TmMhW)b49VnLY&FRPzXHEc(>y<*Gy_!X?rhZG+thD7$VWPhqw4w0{$1OiH1!(NWNX=!Oxv8fG^nF+?(XM}P`=*}Dn<twGed'
    ';*PH(rJ6&93<T>(6e5?Z^walAR<R^pf@x5a-nfHPzO(yzgrY;08!#6Uup(X`9C1WW%$<c8uB?z+x@z}b|J%_&-mR8KQLS!7Cuvot'
    'dsm78V^G+#Nck-)ETNN9-~_91d+l-Og1y7<qeItfX!{UIU~Ayex+2ROrvwXiVNl#`El4o)$NxyXq*r?GP=+}0t}8Ek=|kgGz#JMk'
    'yi6~LUh6+>ExAh3-s<uVop2utie8U6Px}2;mN2Gx0)&}Ur-AD)6Nb`Oz}csh)_H<E<p6iwiXuAJs&677S<3`}uTR?TsoJ~P`b&@J'
    'c5wXd-RVCeGq~T;b`8+fr#q|I*<iGYFGwAwa^1tnP4cl72p@BH%XSVA(fGx=7+?8rJ>5ONj&EF;%X<>?UA{nE=mhv~0`|;0cU{*~'
    '-OyKp@kZSI5A7+`ZS+#<-nF#FTw_`iT7(9?0J;N9P3YWwf~fDoG-Vy^HSFRK?dON~jr3qiFNbfJuPJvR20Q(TvX?qIZYvT%r$fir'
    '0Sb+o{C6I1+10(LquZOdLbJD!MU#HY)pv}1Jg6K?ND-nH7lJ#01w16bWe?xhcA%ET)*cEt7W4(e17MOq!t-3%zL~m@{fNbAzvFz%'
    '9>U(o9-ihM&my^*%1}IUJ@ci2+p%MCPFNz4GRzG*13+SGZ`p^|XjJ2muX^yiJ`Oc^uM(y-aI{ejF&m})oIUJFyQo{@)@u5jK8_Wv'
    'xjWrkr;~m8{bcUuMm;Ed#oihNBm?E*ETIHo08a7Mq}xspZ2tHJ066dFpWp5`NOh7K@)86@_X$HF^-jhAOO=MSB;>nI747riu$B0;'
    '%a{R+m8R9NPAjL3ACbo*#vsOGj<=}~oV%Nw+xHTz%;&+!vVq<NiV6MBLz6-j0^9PYz_;=l8BNF61id7sTQ>4Me0!uxdk%i^skOgF'
    '-1iUgL=_f~gMLb5A=_V6JX&aDjTDGc?W0LI#r~I2rq4SnfGTPZuu-cg-ug83SM(tUKmw+21?7Oy!vM!yHgWnqrhA3h<vrk!g-m3I'
    '9r;WM;6lLPLViI$n&rTCyt{V)v6;ROFK;rM;brrz1Wy=}9UNudWvMn?1<>tgK}L0cNtYGv<Nk2=-Q@9X9R<Sux`7ZNBmlUQeou>U'
    '6>S6UO6&!a7B)>DM?fmw{vdWD!JclH;}~j5&D0>O4UZd166z<~w)9iWoy(+74bKayQ8ZA+R5f`?0l#}A5yPiHru%fx+os70iTv&5'
    '>*@w@pSJ6=&>^EFG?~!lveQolf+7pV?SsUj7YG^1hrel0JB+=MM)>Fv;fJ%KFiZMBfxW8u(_RG)@WC+b{+12R2d;ZB8;tjYgniOW'
    ')94+;=Bo*!)wBp7*h4-otg9u;xW8pbPwAhpTQMJ*IX)c`j-MBk$4DwU0y$7sv~N3-Tf&&C{pg17k6#WCyReo<o6HrM;(}&%>C1*z'
    'SF-<L%d)3*Lsr3g`RI<IAJ3uDc$m_zj|sXF2=3ZP)GhVK`n*x7=pl}?Bq9XNZlw=DDGkT(s_Csgc|YEcnncT~6$o{ibbNw%nMH<&'
    '-@8aD()`gqJ*O8p)fd?A!|?e0^|-MsqTLEt5VEV^*@UA?yv13rSp~yl4uUv}_TRRv*T?(ga2aY|0)<z=vl7MT<pZJ=LCjeYpLL=G'
    'sYht4n&P8-dO7}@9?rDc%gGiDH(0TgdS$3(<AjHz5jqa}Q(qFi7qPwZ<_*pBQ=surDaC){VUr{1+EO-Bzo5K8^YBi)u(M+pg45Vl'
    'g)0_q<<{-^7tyG=`}*?oxGOLTiTb9+%B$ejAQ)6wp9l%=7aU72R1NRey!q&co~Nh7<DRQuS8Ht8g+d}~^(Bp}<PQkTD^&T-9VAqw'
    'O3n{#Xq#rLN0NsFfr@f2WX394)irwr5-q-wE*B!Idc66-&&O|rIK5sUe|mjij@P;GbfApE!i}70#mEUOac|IHB}{B4!r1A9Te?4l'
    ')OH72r%dUpMAbYBe-tuMtQj)QNUbZRie0FAM5OBP*pI3v9kz^s!ohB?VR<eHnFwhc_Ej7-CNc<SMKlDpPO}egDCA81<#t7A;yz3X'
    '1fR^AhS@5&z?=9!i1Oi{Hp{AE73Hm4Ix&vEpRpelXO~}H9WG^j%{i6LgEX2Zw2i*KB8T_JNam$F&Hk=!#a~ewcUZDYNxZgjvf|-{'
    'nT)kKwU9u*V4b%MnWW?{yT55)%eK8uI7KIjqv#k~q6$|z%<g60h&W;;G?L@~^uZ0qt-8a?nlVd+qXp{~8tQ}Yv?KcH#VJ$KbC8mv'
    'J(PcNHz$_klSB7{0lBHHz;Z=6lxkFztaJjTS9$QdRf`<v!a9k=1*Yi-cXhr$ULSToEFD|8to+v9J}6;p>ZT4)Byb)OJcd3vflcYH'
    '+xl{RIR>X(!hPP`Mz)Q}9)j0YP+wQUazv;^pcoYZT8k~B9LDI)(L0cZ;Nu2tdHIZuyf<Y0LbFC|P%AZ7U2cw=q6wI+y{YlN+`5tb'
    '<Gk8goy?;yBR*9)k<;p-ko2ntz@>p!rzX<&hV8PyiOBtdy+ko|eo5!>z3VCgJLG|BD_&7G&G9G$kt;MJysGdgYZXbVlaFm|6;aRY'
    'Nt=$Ft%yj_q=yI-{A_y^;3<gZ7<WX4inwTnuHewEdpg4+e?F$|Eg6ELg3a3@Byms@h6_tjclBj`%3@@E)cNfNh*jC`o!{S1aHNvL'
    'hUrMacA68M?Kw5KLA52n$4o=@4YK*oY01Me8b^WV(Z73QTa4e_eTMfx1y?bxLWSTIq%bU;z%_ZunRwycTz?$b9P(5S;mp2nL`8}k'
    'Mhu9gc^H$4()i<nKt$s)#gv8#_?T|KVL^-WS*!Vl?0rZL$Z80y<j{YM1l(~n{o@ZP_9h-sm5;1V%SU!}wuZQS`5LZ!m$$<VIEy}o'
    'WhIN@lGa;a*ALS)dS2Ku6pc5hM(2`D9V9v;9Bz{iLYwQXW8cH9dI>iLgHMOt+sq##JT4BJ8aLl#>rFcEyE_UuyS4zcHjer7SGgjP'
    'T1#Fxo3)nC7qb(xm)rNU-tnXzdrv!2VkO7-Zd8TU1pDAWPV}L&ruEdpkbju>(R^@6zkS<b@Dbi2P#1%r4CsMVcXDV<?Pg>v9phGJ'
    'iS;nuoCp2ZMdJEfplMs_eVGM&s1L}xjIkG%?!q3@ofXwJe`#e>KYU;(>G$BvN5guz?Wo23whx1c5pQTlE{W>U&>c6c|0tot#O&@P'
    'n>wsdC+&SqeNMhTg)1^*4Qfkx;9*>`h^xXN1_ly_EM@<(9UXVnW5)eNRu;@%lSs@w!s`K;Q4xeu5x#ju#P)W`Gj{S47{l>tgK}6!'
    'vR;O(LyNr4JCp2Dd`?N;T0~{Igaq&d`#6&Ur!Bo9njK~_pE4Le%ODoMljaZmxN;6t6i1$tc1$1H%J+Lp1l-7TCKWSdN(cv(myD&!'
    'nC9@U6bOAKs(QD%BmQ@6X1hBG01LGcy}DD~1_Gm9Nwo_80W#3{C7vK@{J>^HUbvy163RmU67G6z{pvEz_NJHwCsoFdk$??62*&9n'
    'yLbt=&buISZDLW%;b@6!R!gTOr1qn0EZjltf+z_xQ}KKx_I}SH5>5z>|AyHUe+^c9#%kfB_Zo(tiMOVyQdKe?0ooreH>X*D=AL(J'
    'V{=2u&jp(v5%i8+20QhlV(yc+g_6^k4D<<i`dcnZ4<<Adu#^+Wc0>H8^~Qa$ilK;Oc(Gv`!=GG{&N7}3#94;5Keu|kXT|eoaIpUU'
    'W^Y?2IfOaIEN=o`Y7N%mjW(*NdWl^Y4KWtR`za6jq$dgNU;7hpAj)oo794MlB+NT#O4VXrf-|w0(BW9L(C8K#4fPdp#XI|2ON8CK'
    'B7>jeWw8e49!W~9v&+hZHEa<^b{fvT2iR6O@9Nw<*}EU9Fo<#_ThJMZbFTS@nSi5DSm~0|%rNLH&u`w(k1Wc)o09a!xY4MdP?U8I'
    '!ecO`>2c_F!=U!;Y_3SRe!8jncl-CWw!U!y$h*<UC8mHwm{%5|kwjgj&VpK=-MXjgX?Xt17V_cvGHmO=!AiI@eP}3HcEC@O$ix11'
    '#tu_2AmA$aiYxeW|F)YmX0d-bkT({CO3i;W{V&3REYy%o`MQCkT1|+!Ml0O9oxj3PJ2w@!LNoRRK^@+IOiE*kpP8kE*3C*(rc9DN'
    '%=5=K71i)=yFNZE<#I9&lpKdKxG{Y!eKJLI8#s9AhRWvF9eqbqc5jHWYcWoQr*(>ZHO4q)2BgUaNf0p!{d-yR&F?K9&hV_;eMNj!'
    '?-sH{wQwDN2F8_2zw}GxsWpRswYqzyzja6F@>4$b`Xz=1Y(Vi)CR}#2ufn~A1r2iY5~Fy_XnZxQEfOn2$>zh`Ikj_+`>!{>w{YF`'
    'F~OadxaQ274DF<92UG~NOSmXw`ryvi-oV~H#jL?P6kd9Bgbp$?tre67)o2xfxJ<HZe>$$`sy#h_eSL|9asPb+Iu(%euxmx_D!D9a'
    '_PBWwhp3<w8#Et^*WLR%Z)E+npWh<p^tu{Jzu+xM;SQIR6Sr3av#5g%GP5?<P;?W*TYYEXOSOb|T;G3WN5}CONs}s7*u*V<m^X|t'
    '!cd9Ml^%^bKki%jjS1!OusJla#K-QIYZ9iP?CCFmw3%9(DC$jhVPen8h(QLVh0_wgB%_+u?blO8Vcox@#P&OVidMW_^565z%V?Ae'
    '2!%2ODuj+lKC(nefQ)s(?=h}F)*U~!TzPLZ=YIG3$(;Y`T+d(LO6cbncbR!qrp^V0)CkauDT@RI14sWEwe||S^E+GFO#NLD5Ejhp'
    '(D|s7jri6?Ma&Ntco9Bp82i=!bM-QeAj&hrc>Vhz_dahhTVs3#uSHLz31>VsJc!s5ga8I%I6&IUF-_?syV!aXB8oW#;Wp>fB(6&_'
    'F0F_`B@7~&y`m=a$;tMo(Wg)I;SdLyo(}qUKm4(ht~WGh!6S|V+zjRFp!BMk8@Lm4f)X0=UaQ@&AVZz@LCQBgovrRpDw3`GnA{5i'
    'GolDUV+ltXm^K2G=05&h6C>x_ez|TNthw)=hR6c%zQkX*`siVLOHngNs?4m3Py%sn$pWu6G(dmGm}=Qicl|E>_s<(vY~d}^##{iL'
    'UBCrq$QUq1A6E_jEZMJ4!_YL>Eq;0h@fqxT4_Fm&MkaJfi>ys}lWIp{f#Wf9P!DacA%xWx`na>qD)ckwnr>UmgA_|>%nTd*bu=v#'
    '(_347lDMdI{VDc40%1K~w}~_C`Su}fIM6AyQy{-#^lWs<60|%8H(!~cTLGnU2lDR9?@`~0)6+g_U>?&^X014sJDyqUSOn@an!LPc'
    'yrY&H-N3MP-3|~+hIQiPetrP4F*2ag>_mp4qTai^ok&HTi~$pj{eNmYcX1o5BxPF)GUlN_;9^0j)5JA_fUKq#ykQ`v5g)uS=cT^#'
    'HJn5A507A%g&Hr5EVQ9rOxBI?Xhhp8EQ5KVYz99X7iqlmjp%8OLS>xLjpb>;QTbVaMTG^V19X`Ar9(RfrN(W_^nzR0b<4jVWO^?z'
    '8y_Prn_tH>KJH5}n0`@C56Za$g(XP6Qvi15eD&JT|2k}Sr(;5HkU*6Mp^Rk@5sclK%B0d`HUj$2Lkqoo?Qo|*(VD)6bxF)ENaG&Q'
    'sfx)`f%zKfx&#KmUFpsY!FdD>vE0sMhC*F@a3`DEAd}RX0CWWgZg`M$(v69*C_~0Zt=?OdWJ@((zl~V^%=OwytuW-Lr;ws<j0w*m'
    '8_sv`i!e$E3$QZqWysSNFDE2HpMuBz$6rzjK6y#>S|R35J{-S4=c9{F#sA7^=9nagsw<E>HF!>xx=nTau6{WlR$axa@wi*=hc6qp'
    '%+Y$*A`kY^97=(3ONxs=rxKQXg&m9`SjFu-I_W~OJ(Rg$wx;B;)LUY(GM7Ig3$nyhYzYNSkiK=*VkU#J@BQuD!CE|05TD<k*$c}P'
    'YQqMUqoWrtd1V<o6Fy?PdoDY3*t!^(5h~W2H_2APlmcL1M>P%FSHEwJiQ-*RMgT3zgIXRd-Uu>>Zw5UFnv}(i)nW@4O~0!X*IxWC'
    '3&K!l2hO;5oLL_7m=<8Oc387*%L=g2k8<~_j>Sec;S|o}l*a_5ITVa#Sm5Wui*lDbrAlVL{adB_xyAHvMqS)Gf88>)S%MlHsRZXk'
    'C;=*F!B=87M3b-pJHrfXw5NRM`X{t`!yquGt7>ck;d;PGxZA5|ctg$6sqolItWvh@T=A?BcvI8v>9v`LAR}-|(U~v{q%|v>$R6p='
    'qH8l1YrknTmwwy9@ri5$>bE&{tc}3}3hJ1b9J4p6Cvo5FRj9y4$T%t^a5poy@5}z{lrA2nNn3X1Jm_>Zjh-+mK<AYc-56~9U=HXk'
    'CJCF7x0tUxm*&XeB>nm5gQ<DE{L(oebU}oQao<x&A<8hpqZEO4Vwymw6xH)}8(4)r8^f+pop2-gv<xv2B!JW^T<7NSD9o_~3`H-p'
    'y^nmIxV%9`rDIf%#b7HipdiI}Glq`oqu4@C6k_V@rl{d?48$}7_3w|<-OKC4mbY4{ZroYWTEucPt`tK$X{2q3ZF!8Cq7IriWv{XB'
    'imb)c-5w_=!>?C~L?|Pc7)c=?g;q@=RYw<MejC$^vOTN*@h}k`%tF^rdz#?WAplO;Q7W=7CTd$x>naYjvZ!UdT}Y01EPnP=J=qi7'
    'ZJUp~f!qlCJVQ*ZE&>@t@pXiB@bU!>P%9>c8he%o>Mnm=_sgwP2YQ;Bc;xZ`Pc4!>zUSt4QGc$lzo|CuMSe*Szp^*~j8y}Nacyk)'
    '<e8aaghkAOLO)6|h<1t$pAP|o%WQ_GgS;tedRz1~Cp<<*j=@P=4qrCP{yL`WfCEv>VLn72ascT^q}mZW$r)H~OgmS9voC*}F)bDP'
    'k~W??@BP))k=k{A#B{;XFuvJ!xI04W#7}C$e&-feBIn_vu`NKBuRVf2((w?4E|H8nLsfx)mwb6y6epYV!?zXBt<GI9n=_+E50P4o'
    'hKBKZ-YH-W)EKryEcaNO{?z^X{gtnL<2mhvj1#~`Sg@>PQL%d66hj@EO0(bva&GCa*}{%zPFca#z=xdH9MhFS=cE7#_9~02$_(!*'
    '{QfqU{brolu-iOMrRdeV7AyV){)UrbK~E(k(&-ATPCe8`({yXm<NO-7BCn4>RsR0?GkY;ZiYL=z9jA9@2JjMGtVjkCrg1D|*7Rn@'
    'd|L5&wTOP+RhKf>)Ql<uFVko+79q#uX}xD$8ss7)rK2a?j(Zn=3?;7-4I4^lO@m+x^wHO7!gUBqQYPR-j)@w?MT9;>zR9xqzU<lw'
    '-xPfFuYua@86Yo-mK17%)=5TGFzpb~1o?N`<b;1;btSv(@{3^)hoj%7&@fTNENwV3W3M7evUku%V8hBgtlqhDlof|<Zgms>2>z(Y'
    'DMVQ*WO|VfG5HN&Oh=gOZ=Uyi7hQQYZ(<wjwvYpDK6BZZT1{rh0u1NU91iR`ifw96MRm)yK@FL266xMHai-6x9k&#=RRDi(N!Tj^'
    '3$doox%Pb%y?ld?<L4_T>+9BC@mR(3<A%Do(~`mQV!PNy><()n9~iUPHpEcj5+gyIcdq@WDwL94Ue-lu<WNj5)wA^LgLe{I6%t3|'
    '_~<fn!mzp9x$JWP$A)8;xrZ=q7`uQB-IL=qES0tYCA}jRDse8XVCQm&d9`2~e!Und7l67pehkgd0*}yR>7qpK0K1;{5O%Xtz`dW-'
    'sp0aFUX_cNGkSPBGz^TX{i|Z;_ZNQ2)Z4~n<IX54q}ctici~@Nzg_-@>aaD8+1FI+d1w*%O%n7rk=KR+BQLU;-_q<{?=*z$?)e)8'
    ';^G6=#Ti2S8G6T(p;KcXa3A6(DRB;pi?|^LSoW^_M!(&DwK<Yq00E3F1xp_hWeluE1tUTRZJkxS85h&lEANa{j;ziJ)<N>4D=9`8'
    'm6qDyMjBz-l5<lvE}MSX-`77Lf8FR~uFYB(JS+M>^fx2XG+zxiwU}YS`8C?3+8ZTe-ui|j%ApB|WP)rLAF&#rJvRV2T%?e~s?PDQ'
    'tG(;J-oG5yIi;7&LZg?$gEnY+A>ak8_0htQ`J2Fa#?9I_#qRIvZSdzZSbm@K6QC_LrSOFgNI6D9VG@|7!ex&)7Ystx4EEW%gC87{'
    'cP($6k@SWa55g}u)$pSY1P_?!_Dg}n=!u!cuygsdFEVHK`<Jg9Xh4WPc+zrIq?6H=WR;{o6`%FtxbD}8?4&9?7k-|=OB<jP%-&r)'
    'BVkVAh061?3fMt;fPtk#jj-94*DUB6ZysE{gXnN!FEZ43cC^|IZyLheU)Un4gR{8~``zmXlM0r%1E2;QhFVuS42o_8fe5Ez5sX6x'
    '85A|PrN?G(l>Y8s^n(%A<)2OsF*R+>@^F-W$%OjQanPx6+^5bNBb;FO-oYo#7D)aFp5w0@8N6V~uPnG(pof@OC8sp6d=X@9CwP<m'
    'ANJ<b=YGtZU!@J%YZZoqa*rk)|1_-B-eKpu5;TbjMNtJ~+FP=mn%tLvt7pm{bm2N=B9fXjaB5>Xr2rmo<Qo8>x|y$9@eXI^;(Z8#'
    '<*UfSJf`y+S>dv<Jf>_Bl|M7RM&pjW?7CG?8PDPQxI@otND%e6pIC%+stra@^aXkql*=SC6Ib(4?*84Z%TDWG&V0DvDFL~Zk$yT*'
    '>#14=9Q1t}w?1*xGpD^_<n?id5?>#K(6Z4HK+N`7*%OBopCqStvegRuAJHR$q%IL#_TCgH56yiggHvj*SBXZpW|uQEG^33<=q%w@'
    'R2qE8$+F*DuAB@b!$|aL*x{~iI#RHReaA6NU?qyXo12(T5+aOzrDe`rnE_Sc!|zY0H~jg|Us;>qZIEXA;O=QR(<?SDw1Jr`8?QD-'
    'vP8M0hM^wJuUYtQQq_6n$mLJ14y$gybZ#pAb3Ydn5MBpW46>+VJh(Vs6j!Z(cIw|}T^}Y{o_vV!Fv)Z{TQhos`kKddQF+-!pPg^I'
    '_5EcBXGG#Yyv(0izd#E%JUaQ_bi`#EBCPN5q!Fp&lgMLq52i50ZEQBV34htcu7y2j?fo&pHrg6JCsZv5J6f!IL>z;{=D3`ys~3*{'
    '^aeGAu?9R-#)8GDL}o$?($$_KjbH&31VeLiw(gMA{Fq&zT3F|p_PYQ|9VK5JArTp>dMEYax!qtt2X%d8#mB=VA<9-FrgRF-WsIqj'
    'RSYOt%YVZ$<Rv4jVziOBZH|66w(`ddDtIGQ37V$WP?o{Yn8V~z$6Pfm!v<i2rZ<}afdXGSnGh5lylhM-XdxCxm;p_3WMi&Gkd{%u'
    '#?3=>@@`nq%1R74^_w<yJy1zj+-gNxr(bUzz1a_981ADG4Wt(-^G(0uXD#Y)!}o!VpWc4<ciX?+LlbGchp<S9(Oy-IwS|Ikk||7t'
    'j1dI&OwKZHvtjpaXwOhZ3T6(i1azu-YN9rVHmLig#qebQBr%=<U#9rbcJ_TFqhV2IG83cWkVJDI;zqldhb*PEskmdxO`Y}Sovh;@'
    'ABV%nJi>f7X-uO(3eh4Wf!Y9vJDJ&OK2A{4aKAQvW6oQFuSe~>$2ZsDL30ndK=Y_I<k4k9(3AzjFow1YZCM<uhiTu!FH!jt+Z##|'
    'Phqn((e@p~CwK_azm{|tqJI)SlUaP4eMlSTcK6z=1ow2cr>CcN6oqEtmW3%BY=of^p@zLmkUK&(&0I|t?12NGC0*38S8U=+3R4ec'
    'W<L<~CKYFacC+TnqH?JNg2s1a+POV%;l~~P@*0`do}XVNLsP3zu!i#$<^z78?>><KIrNaxF*i-%n#Hg9`ZR(2U=^(#&?sTDkU=|w'
    ';k5@V)h!GFx4UBX>pnp;R6$7LKup9mvgFSQh4N4oG%@aa0xB96v~|nlp)Yqo42<7Dm<TH$Tw8_^9Ieb7j|n|`P8p4QA3_d90Wjcn'
    '?FP;%=B`<&zzB1Xr_jDlC?OJk)5^NY3~+yXeJGWCu{jv)y)EpYN96#tVN;`s)&P+p;Iu(^WnW`VQK;52B>A=5*guPP3Dv!L<Ns1C'
    'hUpN57eq$gHAi=b+fN-mn%j2p#?rZ5?wGlS7J+dm=_H*piZ*aE^foF9b~a^nfQL=A=0CQuulq?M!0MzJ6BeiOr!GLiF9_Pg5NNH*'
    'ASmaXQu2Ra{jU_q)c|E9^@f^+Lyt+LfM7%sEi$=(G>}5a1HW@8R?~;Jv4d%e3zheiYFjR>+3xM5EfH(;2FzoKh6%;s+AjalK6a00'
    'HC{#a)dzOP0)fL*5eDgfq|lmpY{JyVOW9q$nV8Uew{PTETn>EN%uJ@;>OkY7wpht(Q|q=;9fc>CJNxQAAoe_@FWcfvc&+CjYPKSb'
    'XACbfO-&w;49g&bR=w;1Lz^UspKjneyzI8_3tjj~k*F>;Li+GS4th%plUUZ3CcAL`YqR;<5b-u$bJr9>%XF(qA`7$Lw9-%3nN1Kk'
    'dX^^CpVQS}<=Yl^PpidbTafLm(9)<I+j_mm)jeSe9b<I$ePiCvjr;gM7<QM#IWDkKNJ|l8w2N@#86%yPQy>B9GUL3(5YS?{b~C4*'
    'zVu?kNxF+^RZklo!dB{{n1Or)nqi-MgHuQVvKZ$)3@Ee`t6TRG!yO*h49i8eIet{Hy^Yz1bDo9KnL2c}rfr%?ahG=OzE7L|;dl0O'
    '%CPO|VTS?_Cu>pFC@jJO->Xr1;apH8B0i#F_>y1(ZGPKU_Atmf7)~(+k>5QpJlC8mbP5A=)ED!5=a{YyR=hTJLFhSqZFNErw{XXG'
    'L9nPL^y;|?m0B+@I^A<rBehpOT^lw2Dq6VP1^kSJ^B8LILM&r~72OdY*W`b7oLAIx0UYX8U%8cihFNY0Q)1{*F;ewtD98KAZNv7L'
    'df(ZZo4UL<*Iw=qU%vVlUe6cmH_XrtK?D57S6D||)#w8lBIR2S8ES)(ZDNFmMi7Rt&9c4(*!K`tsFD2MEl-Z?VN=Z^Na{3eG=tS!'
    'red%dQLK;#ieg37BeTC=yA@F!v0-?4ee{{Ewczo%Y|L@fN6<}@W+5LTk0NV37~H9_Ju>7HebRE8uYD+H)IR*|D)~zv3)Qa<>s6?v'
    'M~~Z}r^Qr`=Q*5Pn>hIC#U{%8?@RyC+*n`8HD=IROp^-<e~dI?#Hy1=>4Uyolkn@QiR(Nz$7_!)0{L~!ajZ@WPnIiuVrWQ-uovUg'
    '-1&5iSWUu4&|&J^_pwPDGoQo%81v4=2?|{V>2(Po7Zc3XBEgA78@u`*i7i~Em?*>N8S>8HIgddGJZU|hpoCKHjtRJnQKmY&VINm0'
    'C@cbz;WieyScS`u@N7m=CUSNWORClVC!22A#ZE1Q-jjZ^JebN*3&OBn|3{hHN6E@`z;q(sA6HjtCyC$PS@O44qTxXG#QSPgsGV>+'
    '8@3hPXEbvy3X;gYP6&+G?%_HTwnCWaifG|vx>-@*NG-D=IKoYgBtilAaa{c%M2FQ)=-eXRp0dah5Azyk0zs4sQ+WiKt(Z2PA+nnx'
    'yy31sAlFQqpQ06o=@?#0f&&g3IGIurb6cSt6NjsMxH|nk@4y+25V~vVwMH><8d|y*C4Px$&b`Yd4@$YPIh$2&+AhUy8+kmgA>GY('
    'n10=God95<)y7vEvN>-+fePuy>QXet%=slqFx_n%S$PV3UQ8yb<ol3h;vAG>_S;C4(8ZS-oSX!8kEx5-MvI47Kd{AMY>*G|Lw?>s'
    '4|Eo@m>P(+=<c!sjdcDa##Q8@+YOrEc=b^^_f@ZJXj5Myh$vPk=xVfZgKCd;ZC_1{CdGJ^5#`Nod%3o?%_tG%oCn!3V?#i4rwu};'
    'mckOlnQp?@yJ*MTc5~v=?Ai!U7*di;4Hq1yQLP~GI#;a?A8oy<JoxZezoJ!idd|;xicg^n3dNXC8sn8QO~<AVE+ppo;O6DQ<>@rz'
    'wW;9aVLE=_$#z%`uSjW_b%J0^%tl}B0p-E_Ekmln%hg=B;g(&T-piMCWTCS~4mHRa?}fpM!5e&&Fu6iWhHw-7a`{In>9&VV{B#@V'
    'aKgPKMmZcFwlEiSb=<8QQc|HQ)DrF+AFk0qWJu^C#2ngq`Av`H?JQqGj?t^&*+ECKWHG2rJXJhZd3YS<ODb^CGuZjndHcGZA4s&j'
    'AyS+-#iXKI4y0+OjW@Xu4VQ5F(q7u%6t+V*ZRgF=T#5Z<k8G+93PMn~)pIo#fRQNzigG_Ha2Syex7OZp(-}H5eD^+=JSL(H83R2^'
    '2<=SQF$ic5L8KzsM-#Tb*>dfr{OA1>l7W3V9V<cgti6PNASi|iB_>4DUWa7{ZXF;Ov+CNs(c2l*ie*QgXDsw)F%ee}KnM$l7Y{DT'
    '#FdQj2^AaZnRf)*m$5osb^S(WUZUS0hFA6FusRKFvVWYII;ItLAwtKW^wtn&=~sagdV^Ca(AwtO4f!u;<atdO4DcY4#K4a}B+^c7'
    '%rIDw17moKX_^di#G7k3vY$8{Be4g4-=N+La~yl|-_UASt0aWWT7pfDaBY->)16)BC)3;qQvo)15n;qB4nUpIgYW`K6E+(aQY$%T'
    '1b^D`D|c~$+WVI>(@oRIEn5emui4Q?jnQk(mtl2H6c}zU%e4n3>RZPnCQ)upW}q3Lk(We_6y~EbDTCjAjD2IdDJ3yO95b)G76Cc4'
    'Z12v}*Kq&YC~c6oeT!ZAV?ijZARywb<T02V2Ear)TE+d9+c>NE-*&S}(9uK4@z&}p_=ds9aHlX#kf99J)f$C>ZFqWl{Wdu0hQ3>V'
    'c&f85hb_W3ti6~eiTWDe>=-mn46t`*v6tX;4sCPo;XLt>AJax?7>!}q?F&<^%zQ0z6Bn5MQyaIOcLBcBmz}GdR^P{h?gB71A-0fr'
    'gp(r6j8-hrGlx#<g4$mvg}?SathQw*i;_K1c93%xA0p=;zB6Xl$=LhYlv=Ndsh{ZQLEG5c#dQ&B3=3eB6p}YQ#9U>nU@FQAXGV2^'
    '#HO^xSJ_(iyLZO-OX@sdXk+Bj5Nvy*ezsAAu99AsmUNDv5|S|D`zh}3arf#wT;d#Vj36A!)}Uq3Uc7h`8c!c7ykVmuv0Bn5JLgZc'
    'kp0omT+Ig6A!DU4NopN0nSZU(jnT@FrU*WEn>KBJ&tc}hd-pHi5hnbBZD!Ovb6*NKECJXQ6XG?M=~yY#b)TDV--^2f8yiGU*qUPc'
    'FuaajHZvbQqcRj+F8e9Sv%>D?4_(jjz8tVb=Qg6Ht12^adqih?pmhp|?-%*ZaJVpW>vydfF>9ZafWRHE%q=p)(q)^HzQ#%nVq-)U'
    'HbbHPQg4cpe^_=;q%Z&`h2LWngM8E{Jc12Ljn5haMDmVN1NGRnn*3o^oaE?3Z_uAzibIg+^RSdOw9V&4_asJSF&BollG#0*HR}(n'
    '?z|yrQu2zY&=5XZI?QANH8_~Ep3S-u2ha>7RyJ|r|5$j(3@2P&_A;Dgr!FR~HrPWb83UxCRw#Gg0Bt`2;k~6#wfLtW6ZTIpTl41S'
    '#j>Cn(aER+a#X}jZaCHy*8m@Gak|!3e)mRHQ!dA+Z_zU(3mNYJ_#YekBQSwE@(Q_3<kzi?!S*IyqdMdfG*;)g=6x&MAJ;pxCIbQ4'
    'GV$jc8Y&Y${v9xz=boq__mzf7l6eb9y}fW{yJFch-oL$ebR^AXOmTGR2(@3rw!b!;nM2u<V9j>n!@73uH*kB$7T_Fs;%IoPAbqc}'
    'NHs|_+!6?~QwTFsOsanOt5)^A#2!8=4;N!;|Ld3M<HLnt4FAN(#WafHBm{kZ_{<YA2JH;+MMt>ciN2fTSmhU_j8AKu6Uz4U&-ll?'
    'CtE^Ig<WN!6-cRC?*x-K46H-3qIN3-B7L8eA9Fy@)3u*J#qiDldink3(u|>^hnQ*c&YmDKf|6T0-GrGTe=xctk)wED$|eMUdi#+-'
    '7i9d!5TXc|dX3x0&k%|0NZ0ys1ee0Wgka5DMybEFTJWjkpFXWv`$kuaRvgKL-L!f^r_u~Wv^|xBHerqH4rAaF|8Cv%EU)^6&k?<a'
    'bK&Yw?#_R5_uaJMa{5xo0ArLE_LsawjAz4fFoRL<5?lum3_gy3_ueMH|K6wQ%RX%fLh5Q2K?gX`L*OG>;hRUeUm0qlW*@?g%7DF}'
    'eL>N3{X7o8`cA+9?MBcIM|s0zRRF4?fe4dizr|?cf-#Bwc?fa)YR6iq;hHc1_woNq_iH@(KZlpE8yKvM6+d6Xtq=+<c8pUw59>g@'
    '0LZ=V_U8rZX?0DK>FcL6JA)YU__$g2ahPQWiO!~3gONb5fr;8j%QeXIOd4Ho0mANF^ZeHhMxEFm1MN(1GH5=4ZYnh67$e%7Vo75Q'
    'jQMF^_~VkNEdTS$pxc<fZE7mcoC~f9pCjVNLDGUMMynM5CIl%sr}Mt`W=Zhn54K!Shf0xG8+w}dJx@RyZaPo0F~0p-P(OZ3N&Crq'
    'UtY~o+<2a4KSWm)-srlN36h~<o$3COSTMN|8*pd)ed{qud)XQ~+Qg_NhJSvL(dMF`=Nn@>A{LHgSl7lt*y-IPIUPQoj1HbZe?2VB'
    '&Ea;ZxowZfjcC9LjwF?@BHLIhWteyP!3jw)d6*)mvY-U5*s*l1watkz+TKh!#@*o$%Bq9IB2b1jSM#bILczo=wf?Do>OU5IT7l#('
    'W9$$YPRPeu_?9qJrp86XC5B}Vt8l}Lb+?pR+Ogv6<0dm-X;>nl13mkox@gOZ>s7S&ZGwjaTQZeYH@vsnoWfumz4;FbuG9Y<Ze5#a'
    'vI_SvG6<=UnW%u3hCs!=g6ds|)SLp?o6WCU)!2l?M$I&aE4z*a$*3jW8cOgoY&2pv6JCc&a&?}itCrooz^0J#>sujJr{JzIP#6T-'
    'uvG%Iw!w^xsU7(>i=Jxn%eM)&QNaG;=4&{F1B=6=VuYj-9!q@jR`ofv_m;&Q`m`R8Pyc)cb1a9`faV=9cL+P>C=P?VF9*vRW#S@4'
    'C7~22M+7BuG$^lKc@Is5aDl6hh#=0g+`|oF{2~nupOjF%uwCX}Rb2h6zitI4P|~;>Hei3mu%=L$sg?0&nlgT`EELzSpRQea$J|<o'
    'ag?ZH6w(sKfCmrksKV(^D#JKbz8@6vcb9&CeodbcU}P_=edFWHuq9Wh5uSZP?o=5Ql2#E80zPdI+znoHLCeDXxZkzr_8q5PfKFWv'
    'En^14fFUOD1j?aib+v+Y3Kx)Ec-L}!t~ih@KBfsSrmZjRbj2%YiT**~1QIan6SZ80x}6KYY-OHa9Ca*@e`=g?^*0OEv*frIr`Xff'
    'M+`9b-K6M@F`RPj9XXM`yH#8;?(ijS$eEh}Ih6V0zb-C*h)Sc{wcMlYTQRsXT%lO?esdfGE*En+Tx9;)+$cui5q|S9&h2)s_%nBa'
    'zr=ZSUOK-34cmA?AU+~~#2#i>;od@txCEv=?po|L3TT4_MJm<Dux6&u4JHLN8-}m8jS`V9fG&#f_1)8Oj_YrK-80uONYgYHfu;7r'
    'nRSWlP_SNrvMR~~@3ohqdw)s!&mrRJr}cArelri*u!_mMXl;9Q+7dn!577_zzZeK}m4$JPPq)2#)$MT@b=c!nl0L5SZcuH4CYn`k'
    'WMeEtc=b3W#ryB{{iQYa=i{<$$>=$?^1_uVSTNdQ`usys+dHk~ft)Xl`{(_ulL`LoIVgvZuNxdtL&ii}#6I5A6~C)lRp|A)Y9weH'
    'LPQ`&mhWGAJ3JV3CWzC#H9WQeV%W#VMS8!66C*5Pjg8^Xbj7cotn<(NjYkZY0)QC>S%z!EI%5ytHmC~WJ!w7wl)bC2UGyv)-xzX='
    'EhtywbE)UbhsKmSe!1&V1fc@BA9I<T?24xx8N<#oVpXIihN6a2B<Y7^7?H0yS&^E{-q;lzbJjKc7l%FS4805|Vb|{)P;&rdP2AeZ'
    '#4&WTD>>4{Sp!63({NIyNqD~m_|N4Z9>2xP&t|7?%(7$nGh{KkEr@uAbp;D;44Xvv0ven)gRc<uy?^cVZFG{>ZAl=IPz<w;VJ>DQ'
    '#Z@0uS7LaV>FI8LpC7nj*}r)F`Q7(~{jkNItpf{?N}<72@u*E5Vb36EE27}zzeZk{*J=Oy;ZM2T3oLKJ?bFKA{Co~^Z-4svB+mVO'
    'P8SYmvFc%8o6UefDQ1$)qB;2mXlN;BT$PBnyx|hJ18=l$|MzeE&xZ5PtvAqS8dqo@j)f{^3@8ysqvL_E%&kKv?Gh_@Z2jbd`A#tX'
    'i;cXDQ9n0_c*pDI!DQkIZ3oGD=zC+}72m5}aV=Cvbee0&VLOT!DV(+=igT)$68Z63Edw>0Z{0a#<Xbpq{f>oqgKhd1?xM^XU5Qti'
    'T`MPI9Ggrm`~q1|r?9wv7aEEgoXG%&4b&27nILSEDxOCGgAfcMsJ1vN2yIhPd4Y-VMy!*Y(5EqoA;Z(2-^Hs`rx8*)bbwezj@&YO'
    'V{J@$hCBrsUkByg5dHl0WxU(^SxpQ{57vj#G+gmT0SS7hX~Q)L`0o~C;E>994^{}SKAphz#2okYd|1}ui7$tZ4yVLbmx&7+jZZjC'
    'N@&6ujGbyg2!^{#@W9Z;-i5c5IcRM7l**sr%uCEhT=ZuGS_{iX#Ds1R=y~sgf2o--Uv^WBownxOGb_jaAm>OidMUtfcMcwuPjzbc'
    'uDsp9pa-oOOGqd%S=2t*Wt!!z1z9W?>`1EUskiSY>g!r>mNTD+wRy7PQtC2STN%(6T>2s;8DQEJ=&-0mu1>MRf9d^?^{-2ct#94M'
    '%adp_Y6iv$U1+r&51x*U1l;1<n{D_VOC0Mm+qdX<1@h%nNz$3c6mxhtXPF>jhiN6O9~jPqEHstSreWWjJD`@?>~!C144?zXhE<|#'
    '5RhmVE_l!UZW)WWJ?~pE5a@3a?Jlo5hcSgoaJ2qZfz**v_$e;&0zFU}N|@U$J3pWkk9bexO>fYAYab62H(G=~MD^NGW4v4tjHtjJ'
    'wEHPd^}@OvgA-^BVt$h^I8m?zJUEhc)a1S&Y8s7<ULD_Dw<M18VT0fSyQ6hvY74KN+A^ede1aHLa)ak3h=54?m|eN-TUN6{h85h|'
    'M0uz~1jHiD3y7Ggx{OnvBS0#>ifZ55o4^R!x9<ozSw=4-)RZv1CH!<X;Odx%hJu!lyI0#J3;_seSo6^JLZZQh%_Mt73d8pZ{#OjU'
    'F*mrnYQ>*T?)fX^&R#qQ^%yHioL1uWWx?GvUDT*#R6FfWV`lPwi#|&~$K&N0l^{Dq1G}J?#Rt5$5pb)6+Kdtw_l%Ti=$ETjyxT;b'
    '35JYDQjmimjEB;~p$q{)OLJN1fbzhy{m+L~ZY;Ztt*SU`qEwD_3=d1EwH+dZp&BxcDn?E-eXri{SpR(aRdcbyLQ`*m0|1FS4WL9A'
    '%o0wcTIPaP8$rsSHrK6tQZ#JD|D}k7DTfxHOhrOA<aI(LrG|@%*YP}x_cOGATX;=FaX8O<qz$SN-D~t1+8F9ba!b0Gh5naGQ!tj2'
    '7)1lK^RC;B{^B510E!Rvia9!rc?l~iHxO$aDiQ_Fy81u0;Q#CY_<sQ6=Nvo'
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)
)


class ShippingPolicyTests(unittest.TestCase):
    def trusted_main_projection(self, root, raw, source):
        """Authenticate fixture fields; never call this native D evidence."""
        payload=zlib.decompress(base64.b85decode(_MAIN_PROJECTION_B85))
        self.assertEqual(hashlib.sha256(payload).hexdigest(),_MAIN_PROJECTION_SHA256)
        tree=json.loads(payload)
        self.assertEqual(len(tree),502)
        self.assertEqual(tree[inputs.AFFECTED_POLICY],blob(raw))
        policy=json.loads(raw)
        self.assertEqual(inputs.affected_lookup_digest(tree),policy['targets']['main']['lookup_digest'])
        self.assertEqual(tree['tests/platform-profile.json'],policy['targets']['main']['profile'])
        self.assertTrue(inputs.AFFECTED_AUTHORITY <= tree.keys())
        for subjects in inputs._AFFECTED_SUBJECTS.values():self.assertTrue(set(subjects) <= tree.keys())
        # Installed workflow authority changes only through a complete enrolled
        # tuple, exactly as shipping_context restores the actual installed S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}
        matches=[row['workflows'] for row in generations if row['name'] in accepted
                 and all(source.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(matches),1)
        for path,entry in matches[0].items():
            if path in inputs.AFFECTED_AUTHORITY:tree[path]=dict(entry)
        return tree

    def target_context(self, root, raw, source):
        policy=json.loads(raw)
        lookup=inputs.affected_lookup_digest(source)
        matches=[name for name,row in policy['targets'].items()
                 if row['lookup_digest']==lookup and row['profile']==source['tests/platform-profile.json']]
        self.assertTrue(matches,'actual source namespace must match an unchanged protected target row')
        target='main' if 'main' in matches else matches[0]
        # Equal namespace aliases (Android main/VR) must also share the complete
        # native reader proof, rather than choosing among incompatible variants.
        self.assertTrue(all(policy['targets'][name]==policy['targets'][target] for name in matches))
        return target,self.trusted_main_projection(root,raw,source)

    def test_shipping_manifest_is_complete_and_backward_compatible_registry_is_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        manifest=json.loads(raw)
        self.assertEqual(len(manifest['suites']),61)
        self.assertIn('native-owner-lifecycle',manifest['suites'])
        finite=[n for n,r in manifest['suites'].items() if r['kind']=='reviewed-patterns']
        self.assertEqual(finite,['documentation-contracts','release-bundle','embedded-web-qml',
            'places-native-qml','recorded-voice-qml','snapshot-qml'])
        self.assertEqual(registry['schema'],1)

    def source_context(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        tree=inputs.full_tree(root,'HEAD')
        for path in ('tools/test-evidence/affected-test.py','tools/test-evidence/AFFECTED_SELECTION.md'):
            tree[path]=blob((root/path).read_bytes())
        tree[inputs.AFFECTED_POLICY]=blob(raw)
        # Both the source PR and its exact installed successor run this test.
        # Authenticate the actual complete deployed tuple before constructing
        # the distinct approved preinstallation B; do not bind R to B instead S.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        previous_rows=[row['workflows'] for row in generations if row['name'] in {
            'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1'}]
        previous=next(row['workflows'] for row in generations if row['name']=='npm-consumers-sync-ci-v1')
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}]
        if not installed:
            installed=[row for row in generations if row['name']=='protected-producer-seven-target-ci-v1']
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[row['workflows'] for row in installed] if endpoint in tree else previous_rows
        matches=[row for row in approved if all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:
            previous=matches[0]
            codeql='6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        else:
            actual=next(row for row in installed if row['workflows']==matches[0])
            codeql={'protected-producer-original-default-v1':'e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1',
                'protected-producer-original-default-boolean-v1':'3b7a88765b7181a1bc7dd6f48b9b459e590055d3',
                'protected-producer-original-default-required-context-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
                'protected-producer-optional-parent-source-v1':'7b0703d88d404f38c1b3dec92f77f03586c9144c',
                'protected-producer-optional-leaf-common-v1':'b29e0558dc69bc9dd6fc6b47bd6024382be4079d',
                'protected-producer-seven-target-ci-v1':'3a273057a38255ca368d3028594fb94227ba7c3b'}[actual['name']]
        self.assertEqual(tree['.github/workflows/codeql.yml'],dict(mode='100644',type='blob',sha=codeql))
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        actual=inputs.full_tree(root,'HEAD')
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1',
            'protected-producer-optional-leaf-common-v1'}
            and all(actual.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(installed),1,'installed S must be its actual complete old, Boolean or canonical-result tuple')
        installed=installed[0]
        future=installed['workflows']
        templates={
            '.github/workflows/project-tests.yml':'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml':'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/pr-metadata-context.yml':'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            '.github/workflows/sync-validation.yml':'tools/repository-checks/workflows/sync-ci-selection.yml',
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
        }
        if installed['name']=='protected-producer-optional-leaf-common-v1':
            self.assertEqual(future['.github/workflows/project-tests.yml'],
                dict(mode='100644',type='blob',sha='f4765fa63bdfede51cf6d711d24a952c5d0e0316'))
            templates['.github/workflows/project-tests.yml']='tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml'
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            prior_callers={'protected-producer-original-default-v1':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                'protected-producer-original-default-boolean-v1':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            if path=='.github/workflows/parent-qualification.yml':
                # Whole historical recipes retain their real Parent bytes when
                # the separately preregistered optional successor is installed.
                parent=('987d8f0d198e40211ab0f33286a55852e286c174'
                    if installed['name'] in {'protected-producer-optional-parent-source-v1',
                        'protected-producer-optional-leaf-common-v1'}
                    else '9bfc6f8723b1f59426f913472b78206844a7f201')
                expected=dict(mode='100644',type='blob',sha=parent)
            elif installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
                expected=dict(mode='100644',type='blob',sha=prior_callers[installed['name']])
            else:
                expected=blob((root/template).read_bytes())
            self.assertEqual(future[path],expected,path)
            self.assertEqual(actual.get(path),expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=dict(actual['.github/workflows/codeql.yml'])
        if future is not None and tree['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE:
            # Source13 keeps all original owners. Only the installed Android S
            # fixture applies the separately reviewed exact seven-file handoff.
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            targets={path for group in ('legacy_workflows','source_contracts') for path in owner[group]}
            self.assertEqual(targets,{'.github/workflows/android-tests.yml','.github/workflows/android-vr-tests.yml',
                'android/common/tests/android-workflow-contract-test.py',
                'android/common/tests/ci/validate_ci_contract.py','android/common/tests/ci/test_ci_contract.py',
                'android/common/tests/robolectric/build.gradle',
                'android/phone/tests/phone-release-metadata-test.py'})
            for group in ('legacy_workflows','source_contracts'):
                for path,item in owner[group].items():
                    self.assertEqual(item['source'],'tools/repository-checks/workflows/android-owned/handoff/'+path)
                    data=(root/item['source']).read_bytes()
                    self.assertEqual(tree[item['source']],blob(data))
                    expected=blob(data,mode=item['mode'])
                    previous={'mode':item['mode'],'type':'blob','sha':item['reviewed_blob']}
                    self.assertIn(tree.get(path),(previous,expected))
                    tree[path]=expected
        return root,registry,raw,tree

    def bounded_context(self):
        """Seal a small synthetic repository while preserving real definitions.

        Real whole-inventory shipping/legacy routing and protected iOS proofs
        remain separate. Repeated mutation cases need every actual authority,
        required subject, CI exception and currently reviewed import root, not
        thousands of unrelated application assets in every negative plan.
        """
        root,registry,raw,source=self.shipping_context()
        policy=json.loads(raw)
        required=set(inputs.AFFECTED_AUTHORITY)
        required.update(policy['suites']['device-control-plane-full']['native_independent_paths'])
        # These existing importable mutation subjects must remain edits, rather
        # than becoming new import names in the smaller synthetic inventory.
        required.update({'tests/device/self_tests/test_voice_roundtrip.py',
                         'provenance/artifact_identity.py'})
        for suite in registry['suites'].values():
            required.update(suite['closure']['required'])
            imports=suite.get('python_imports')
            if imports and inputs.python_import_digest(source,imports['roots'])==imports['reviewed']:
                required.update(entry['path'] for entry in inputs.selected_entries(
                    source,inputs._import_patterns(imports['roots'])))
        tree={path:dict(entry) for path,entry in source.items() if path in required}
        # This deliberately synthetic fixture exercises main's bounded parser.
        # Full source/shipping contexts above retain real Android13/19 profiles.
        self.assertEqual(inputs._AFFECTED_SHARED_PROFILE['sha'],'d63537504c20204de9d35d9be61da72a56df59c3')
        tree['tests/platform-profile.json']=dict(inputs._AFFECTED_SHARED_PROFILE)
        policy['lookup_digest']=inputs.affected_lookup_digest(tree)
        native=policy['suites']['device-control-plane-full']
        native['reviewed_reader_digest']=inputs.device_reader_digest(tree,native['native_independent_paths'])
        if policy['schema']==2:
            # Keep the versioned main aliases coherent in this smaller fixture;
            # shipping/all-seven source certificates above remain unmodified.
            policy['targets']['main']['lookup_digest']=policy['lookup_digest']
            policy['targets']['main']['reader_digest']=native['reviewed_reader_digest']
        sealed=(json.dumps(policy,indent=2)+'\n').encode()
        tree[inputs.AFFECTED_POLICY]=blob(sealed)
        return root,registry,sealed,tree

    def test_source_and_shipping_fixtures_bind_the_actual_deployed_boolean_variant(self):
        root=Path(__file__).resolve().parents[2]
        actual=inputs.full_tree(root,'HEAD')
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        for name,codeql in (
                ('protected-producer-original-default-v1','e9aaaed9693efc5ffb4701697ac2a4d51f5f5ba1'),
                ('protected-producer-original-default-boolean-v1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3'),
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
                ('protected-producer-optional-parent-source-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c'),
                ('protected-producer-optional-leaf-common-v1','b29e0558dc69bc9dd6fc6b47bd6024382be4079d')):
            variant=deepcopy(actual)
            row=next(row['workflows'] for row in generations if row['name']==name)
            variant.update(deepcopy(row))
            variant['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',sha=codeql)
            with self.subTest(name=name),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)):
                _,_,_,before=self.source_context()
                self.assertNotIn('.github/workflows/pr-metadata-context.yml',before)
                self.assertEqual(before['.github/workflows/codeql.yml']['sha'],
                    '6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
                _,_,_,installed=self.shipping_context()
                for path,entry in row.items():self.assertEqual(installed[path],entry)
                self.assertEqual(installed['.github/workflows/codeql.yml'],variant['.github/workflows/codeql.yml'])
            variant['.github/workflows/codeql.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='CodeQL'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()
            variant['.github/workflows/codeql.yml']['sha']=codeql
            variant['.github/workflows/browser-client.yml']['sha']='f'*40
            with self.subTest(name=name,invalid='mixed tuple'),patch.object(inputs,'full_tree',side_effect=lambda *_:deepcopy(variant)), \
                    self.assertRaises(AssertionError):self.source_context()

    def test_shipping_five_controller_case_omits_device_without_running_any_suite(self):
        root,registry,raw,base=self.shipping_context()
        _,_,_,source=self.source_context()
        self.assertEqual(inputs.affected_lookup_digest(source),inputs.affected_lookup_digest(base))
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',source)
        self.assertIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        for name in ('attested.py','postmerge.py','producer_workflow.py','sandbox.py','sandbox_host.py'):
            candidate['tools/test-evidence/'+name]=blob(('changed '+name).encode())
        target,trusted=self.target_context(root,raw,base)
        native=json.loads(raw)['suites']['device-control-plane-full']
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        actual_base,actual_candidate=base,candidate
        original_base,original_candidate=deepcopy(base),deepcopy(candidate)
        raw_readers=[inputs.device_reader_digest(tree,native['native_independent_paths'])
                     for tree in (base,candidate)]
        raw_programs=[host.program_digest(tree,root) for tree in (base,candidate)]
        routing=host._ios_routing_views(candidate,base,trusted,root,target)
        # This historical full-subset fixture uses the original reader family,
        # just like the protected finite routing comparison. Actual raw maps
        # and reader identities remain independently preserved below.
        if routing is not None:
            base,candidate=routing['base'],routing['candidate']
        # The installed compiler-data family has a separate complete raw
        # reader certificate; retain the original target certificate as well.
        reader=inputs.device_reader_digest(base,native['native_independent_paths'])
        if inputs.installed_compiler_profile(base,target=target):
            self.assertEqual(target,'apple-ios')
            self.assertEqual(reader,inputs.INSTALLED_COMPILER_READER)
        else:
            self.assertEqual(reader,json.loads(raw)['targets'][target]['reader_digest'])
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        self.assertIn('device-control-plane-full',plan['omitted'])
        self.assertLess(len(plan['required']),60)
        self.assertIn('attested-runtime',plan['required'])
        self.assertIn('test-evidence',plan['required'])
        self.assertEqual(plan['required_setup'],['host-full'])
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])
        self.assertEqual((actual_base,actual_candidate),(original_base,original_candidate))
        self.assertEqual([inputs.device_reader_digest(tree,native['native_independent_paths'])
                          for tree in (actual_base,actual_candidate)],raw_readers)
        self.assertEqual([host.program_digest(tree,root) for tree in (actual_base,actual_candidate)],raw_programs)
        if routing is not None:
            self.assertNotEqual(original_base,base)
            self.assertNotEqual(original_candidate,candidate)

    def test_preinstallation_source_cannot_inherit_the_prospective_native_omissions(self):
        root,registry,raw,base=self.source_context()
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed preinstallation controller')
        target,trusted=self.target_context(root,raw,base)
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertEqual(len(owners),23)
        self.assertTrue(owners.issubset(plan['required']))
        self.assertFalse(owners.intersection(plan['omitted']))
        for name in owners:
            self.assertEqual(plan['reasons'][name],
                'fixed-subject-or-reader-not-reviewed' if name in inputs._AFFECTED_SUBJECTS
                else 'product-component-or-reader-not-reviewed')
        if target.startswith('android-'):
            original=inputs.full_tree(root,'HEAD')
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            for group in ('legacy_workflows','source_contracts'):
                for path in owner[group]:
                    self.assertEqual(base[path],original[path],'preinstallation fixture must retain every actual legacy owner')

    def test_actual_child_namespace_cannot_be_claimed_as_main_or_trusted_default(self):
        root,registry,raw,base=self.shipping_context()
        target,trusted=self.target_context(root,raw,base)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        # A real child keeps its extra import membership and native readers.
        # On main, a synthetic neighboring import proves the same refusal.
        foreign=deepcopy(base)
        if target=='main':foreign['ios/fixture_namespace.py']=blob(b'new child import')
        self.assertNotEqual(inputs.affected_lookup_digest(foreign),json.loads(raw)['targets']['main']['lookup_digest'])
        for old,new,default,claimed in ((foreign,candidate,trusted,'main'),
                                        (base,candidate,foreign,target),
                                        (base,candidate,trusted,'unknown-child')):
            with self.subTest(claimed=claimed),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,old,new,default,target=claimed)

    def test_exact_metadata_and_source_reader_bytes_are_independent_but_membership_and_modes_are_bound(self):
        _,registry,raw,base=self.bounded_context()
        paths={
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            '.github/workflows/pr-metadata-context.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            '.github/workflows/documentation-checks.yml',
            '.github/workflows/workflow-security.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
        }
        self.assertTrue(paths <= set(json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']))
        candidate=deepcopy(base)
        for path in paths:
            self.assertEqual(base[path]['mode'],'100644')
            candidate[path]=blob(('changed reviewed bytes '+path).encode())
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        owners={'device-control-plane-full',*inputs._AFFECTED_PRODUCT_SUITES,*inputs._AFFECTED_SUBJECTS}
        self.assertTrue(owners <= set(plan['omitted']))
        for path in paths:
            for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                changed=deepcopy(candidate);changed[path]={'mode':mode,'type':kind,'sha':'f'*40}
                with self.subTest(path=path,mode=mode):
                    try: result=inputs.plan_affected(registry,raw,base,changed,base)
                    except inputs.InputError: continue
                    self.assertTrue(owners <= set(result['required']))
        candidate['.github/workflows/pr-metadata-context-extra.yml']=blob(b'unreviewed neighbor')
        self.assertTrue(owners <= set(inputs.plan_affected(registry,raw,base,candidate,base)['required']))

    def test_unavailable_graph_retains_the_independently_selected_legacy_gate(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_host_rollout',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'new')
        paths=['tools/test-evidence/sandbox_host.py']
        without=deepcopy(base);del without[inputs.AFFECTED_POLICY]
        for old,trusted,claimed in ((without,without,paths),(None,base,paths),(base,base,paths+['README.md'])):
            with self.subTest(old_missing=old is None,claimed=claimed):
                selected=host.select(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                legacy=host._select_legacy(candidate,claimed,True,trusted_tree=trusted,base_tree=old)
                self.assertEqual(selected,legacy)

    def test_changed_graph_cannot_expand_an_independently_reviewed_ci37_plan(self):
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_graph_preserves_legacy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        candidate=deepcopy(base);candidate[inputs.AFFECTED_POLICY]=blob(b'changed policy bytes')
        options={'base_tree':base,'trusted_tree':base}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base)):
            legacy=host._select_legacy(candidate,[inputs.AFFECTED_POLICY],True,**options)
            self.assertEqual(len(legacy['suites']),37)
            self.assertFalse(legacy['full_host'])
            self.assertEqual(host.select(candidate,[inputs.AFFECTED_POLICY],True,**options),legacy)
        with self.assertRaises(inputs.InputError):
            inputs.plan_affected(registry,raw,base,candidate,base)

    def test_each_device_component_reader_data_discovery_native_and_variant_keeps_device(self):
        _,registry,raw,base=self.bounded_context()
        paths=('tests/device/catalog.json','tests/device/self_tests/test_voice_roundtrip.py',
            'tests/device/fixture/new-resource.json','provenance/artifact_identity.py',
            'tools/sbom/verify-artifact-identity.py','libraries/audio-client/src/AudioClient.cpp',
            'libraries/shared/src/new-header.h','interface/resources/qml/new-component.qml',
            'scripts/system/settings/qml/new-data.json','android/phone/new-native-input.cpp')
        for path in paths:
            candidate=deepcopy(base);candidate[path]=blob(b'changed component')
            with self.subTest(path=path):
                plan=inputs.plan_affected(registry,raw,base,candidate,base)
                self.assertIn('device-control-plane-full',plan['required'])
        historical=deepcopy(base);historical['libraries/audio-client/src/AudioClient.cpp']=blob(b'child reader')
        candidate=deepcopy(historical);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        self.assertIn('device-control-plane-full',inputs.plan_affected(registry,raw,historical,candidate,base)['required'])

    def test_optional_ios_adapter_and_historical_native_root_headers_remain_bound(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('ios/audio/IOSAudioAdapter.cpp','ios/audio/IOSAudioAdapter.h',
                     'ios/audio/new-private-header.h','cassert','QtCore/QCoreApplication'):
            for shape in ('candidate-only','historical-both'):
                old=deepcopy(base);candidate=deepcopy(base)
                if shape=='historical-both':old[path]=blob(b'historical native lookup')
                candidate[path]=old[path] if shape=='historical-both' else blob(b'changed native lookup')
                candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated admitted CI')
                with self.subTest(path=path,shape=shape):
                    plan=inputs.plan_affected(registry,raw,old,candidate,base)
                    self.assertIn('device-control-plane-full',plan['required'])

    def test_native_independence_is_closed_bounded_and_cannot_exempt_unowned_headers(self):
        root,registry,raw,base=self.bounded_context()
        for paths in ([],['*'],['../cassert'],[inputs.AFFECTED_POLICY]*2,[f'leaf-{n}' for n in range(1001)]):
            value=json.loads(raw)
            value['suites']['device-control-plane-full']['native_independent_paths']=paths
            with self.subTest(paths=paths[:2]),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(value,registry)
        value=json.loads(raw)
        value['suites']['device-control-plane-full']['native_independent_paths'].append('cassert')
        forged=json.dumps(value).encode()
        for tree in (base,):tree[inputs.AFFECTED_POLICY]=blob(forged)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed')
        spec=importlib.util.spec_from_file_location('affected_native_policy_guard',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        with patch.object(inputs,'load_dependencies',return_value=forged):
            selected=host.select(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        legacy=host._select_legacy(candidate,['tools/test-evidence/sandbox_host.py'],True,base_tree=base,trusted_tree=base)
        self.assertEqual(selected,legacy)

    def test_reviewed_product_owners_share_only_the_fixed_complete_lookup_proof(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(plan['omitted']))
        self.assertIn('host-selection',plan['required'])
        for name in sorted(inputs._AFFECTED_PRODUCT_SUITES):
            subject=registry['suites'][name]['closure']['required'][0]
            changed=deepcopy(candidate);changed[subject]=blob(b'changed reviewed owner')
            with self.subTest(owner=name,subject=subject):
                if subject in inputs.AFFECTED_AUTHORITY:
                    with self.assertRaises(inputs.InputError):
                        inputs.plan_affected(registry,raw,base,changed,base)
                else:
                    self.assertIn(name,inputs.plan_affected(registry,raw,base,changed,base)['required'])
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','missing-fixed-inventory','extra-inventory'):
            changed=deepcopy(value);changed_registry=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-product-inventory'
            elif shape=='candidate-scope':
                changed_registry['suites']['device-jenkins']['scope']='candidate'
                changed['registry_digest']=inputs._suite_definition_digest(changed_registry)
                changed['suites']['device-jenkins']['definition_digest']=inputs._suite_definition_digest(changed_registry['suites']['device-jenkins'])
            elif shape=='missing-fixed-inventory':changed['suites']['device-control-plane-full']={
                'kind':'repository','setup':['host-full'],'definition_digest':changed['suites']['device-control-plane-full']['definition_digest']}
            elif shape=='extra-inventory':changed['suites']['device-jenkins']['native_independent_paths']=['ignored']
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,changed_registry)

    def test_javascript_and_performance_component_data_cannot_use_ci_byte_exemptions(self):
        _,_,raw,base=self.bounded_context()
        paths=json.loads(raw)['suites']['device-control-plane-full']['native_independent_paths']
        for path in ('tests/javascript/README.md','tests/performance/README.md',
                     'tests/safe-landing/README.md','tests/mocha/README.md','server-console/README.md',
                     'unpublishedScripts/README.md','tools/jsdoc/README.md'):
            old=deepcopy(base);old[path]=blob(b'old fixture contract')
            new=deepcopy(old);new[path]=blob(b'changed fixture contract')
            with self.subTest(path=path):
                self.assertNotEqual(inputs.device_reader_digest(old,[*paths,path]),
                                    inputs.device_reader_digest(new,[*paths,path]))

    def test_fixed_ci_subjects_bind_all_three_trees_without_coupling_product_owners(self):
        _,registry,raw,base=self.bounded_context()
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertTrue(set(inputs._AFFECTED_SUBJECTS).issubset(plan['omitted']))
        self.assertIn('documentation-contracts',plan['required'])
        self.assertEqual(plan['reasons']['documentation-contracts'],'unreviewed-import-or-missing-required-input')
        self.assertIn('native-owner-lifecycle',plan['required'])
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),34)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),33)
        for name,subjects in inputs._AFFECTED_SUBJECTS.items():
            for subject in subjects:
                for shape in ('changed','removed','historical','executable'):
                    old=deepcopy(base);new=deepcopy(candidate)
                    if shape=='removed':new.pop(subject)
                    elif shape=='executable':new[subject]=dict(new[subject],
                        mode='100644' if new[subject]['mode']=='100755' else '100755')
                    else:
                        new[subject]=blob(b'changed exact subject')
                        if shape=='historical':old[subject]=deepcopy(new[subject])
                    with self.subTest(owner=name,subject=subject,shape=shape):
                        lookup_change = subject=='tools/test-evidence/producer.py' and shape in {'removed','executable'}
                        if subject in inputs.AFFECTED_AUTHORITY or lookup_change:
                            with self.assertRaises(inputs.InputError):
                                inputs.plan_affected(registry,raw,old,new,base)
                        else:
                            selected=inputs.plan_affected(registry,raw,old,new,base)
                            self.assertIn(name,selected['required'])
        # This CI unit-test leaf is independent of the actual product tests.
        changed=deepcopy(candidate);changed['tests/unittest-runner-test.py']=blob(b'changed CI regression')
        selected=inputs.plan_affected(registry,raw,base,changed,base)
        self.assertIn('python-test-runner',selected['required'])
        self.assertIn('device-control-plane-full',selected['omitted'])
        self.assertTrue(inputs._AFFECTED_PRODUCT_SUITES.issubset(selected['omitted']))

    def test_fixed_ci_subject_policy_cannot_supply_unknown_owners_or_subject_maps(self):
        _,registry,raw,base=self.bounded_context()
        value=json.loads(raw)
        for shape in ('unknown-owner','candidate-scope','alternate-subjects','extra-map','missing-native'):
            changed=deepcopy(value);definitions=deepcopy(registry)
            if shape=='unknown-owner':changed['suites']['producer-api']['kind']='reviewed-subject-inventory'
            elif shape in {'candidate-scope','alternate-subjects'}:
                if shape=='candidate-scope':definitions['suites']['python-test-runner']['scope']='candidate'
                else:definitions['suites']['python-test-runner']['closure']['required']=['tests/unittest-runner-test.py']
                changed['registry_digest']=inputs._suite_definition_digest(definitions)
                changed['suites']['python-test-runner']['definition_digest']=inputs._suite_definition_digest(definitions['suites']['python-test-runner'])
            elif shape=='extra-map':changed['suites']['python-test-runner']['subjects']=['arbitrary.py']
            else:
                entry=changed['suites']['device-control-plane-full']
                changed['suites']['device-control-plane-full']={k:entry[k] for k in ('kind','definition_digest','setup')}
                changed['suites']['device-control-plane-full']['kind']='repository'
            with self.subTest(shape=shape),self.assertRaises(inputs.InputError):
                inputs._validate_dependencies(changed,definitions)
        candidate=deepcopy(base);candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed CI')
        candidate['tests/unittest-extra-runner-test.py']=blob(b'unknown neighbor')
        plan=inputs.plan_affected(registry,raw,base,candidate,base)
        self.assertIn('python-test-runner',plan['required'])

    def test_unknown_root_import_shadow_cannot_inherit_any_omission(self):
        _,registry,raw,base=self.bounded_context()
        for path in ('json.py','sitecustomize.py','tools/repository-checks/json.py','tests/device/new_module.py','namespace/__init__.py'):
            candidate=deepcopy(base);candidate[path]=blob(b'new shadow')
            with self.subTest(path=path),self.assertRaises(inputs.InputError):
                inputs.plan_affected(registry,raw,base,candidate,base)

    def test_existing_ci37_metadata_codeql_cleanup_and_lock_plans_never_expand(self):
        import ci_profile
        root,registry,raw,base=self.shipping_context()
        spec=importlib.util.spec_from_file_location('affected_preserve_proofs',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        ci37=[n for n,s in registry['suites'].items() if s['layer']=='quick' and n not in host.PRODUCT_QUICK_SUITES]
        paths=('.github/workflows/codeql.yml','.github/branch-cleanup.json',
               '.github/android-orchestration.json','tests/PROJECT_TESTING.md',*host.PACKAGE_LOCKS)
        # Preserve the exact legacy37 contract under its actual old namespace.
        # The new seven-target namespace deliberately permits smaller proved
        # Qt-free selections; SevenTargetProfileTests covers those separately.
        historical_policy={**ci_profile.load_policy(root),
            'generation_kind':ci_profile.CONTROLLER_KIND,'epoch':ci_profile.CONTROLLER_EPOCH}
        with patch.object(host,'REVIEWED_PROGRAMS',host.program_digest(base,root)), \
             patch.object(ci_profile,'load_policy',return_value=historical_policy):
            for path in paths:
                candidate=deepcopy(base);candidate[path]=blob(b'changed ordinary shipping leaf')
                package_paths=(path,) if path in host.PACKAGE_LOCKS else ()
                options={'base_tree':base,'trusted_tree':base,'package_paths':package_paths}
                with self.subTest(path=path):
                    legacy=host._select_legacy(candidate,[path],True,**options)
                    self.assertEqual(legacy['suites'],ci37)
                    self.assertEqual(len(legacy['suites']),37)
                    self.assertEqual(host.select(candidate,[path],True,**options),legacy)
            for unknown,regular,paths in ((False,True,[]),(True,True,['README.md']),(False,False,['README.md'])):
                options={'base_tree':base,'trusted_tree':base,'unknown':unknown}
                self.assertEqual(host.select(base,paths,regular,**options),host._select_legacy(base,paths,regular,**options))

    def test_fewer_groups_cannot_replace_an_existing_narrower_preparation_route(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_setup_dominance',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        for legacy_full,affected_full in ((False,True),(False,False),(True,True),(True,False)):
            legacy={'suites':['owner-a','owner-b'],'reason':'reviewed-ci-only-inputs',
                    'full_host':legacy_full,'include_platform':False}
            affected={'suites':['owner-a'],'reason':'protected-affected-dependencies',
                      'full_host':affected_full,'include_platform':False}
            with self.subTest(legacy_full=legacy_full,affected_full=affected_full), \
                    patch.object(host,'_select_legacy',return_value=legacy), \
                    patch.object(host,'affected_selection',return_value=affected):
                selected=host.select({},['reviewed-ci-leaf'],True)
                self.assertIs(selected,legacy if affected_full and not legacy_full else affected)

    def test_nonempty_or_changed_platform_cannot_enter_partial_route_even_on_both_sides(self):
        _,registry,raw,base=self.bounded_context()
        changed=deepcopy(base);changed['tests/platform-profile.json']=blob(b'{"schema":1,"platform":"android","suites":[{}]}')
        candidate=deepcopy(changed);candidate['tools/test-evidence/sandbox_host.py']=blob(b'unrelated')
        with self.assertRaises(inputs.InputError):inputs.plan_affected(registry,raw,changed,candidate,changed)

    def test_protected_producer_declines_dynamic_subset_before_any_runtime_preparation(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_producer',root/'tools/test-evidence/producer_workflow.py')
        producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
        registry={'schema':1,'control_inputs':['fixed'],'suites':{'finite':definition()}}
        tree={'fixed':blob()}
        policy=type('Policy',(),{'select':staticmethod(lambda *a,**k:{'reason':'protected-affected-dependencies','suites':['finite'],'full_host':True})})
        with patch.object(producer.shared,'prepared_tools') as tools,patch.object(producer.runtime_ci,'validate_environment') as admit:
            with self.assertRaises(producer.PreExecutionUnavailable):
                producer.selection_profile(policy,registry,tree,tree,tree)
            tools.assert_not_called();admit.assert_not_called()


class DependencyPolicyRoutingTests(unittest.TestCase):
    def module(self, name, relative):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location(name,root/relative)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module

    def test_only_exact_ordinary_new_leaves_are_ios_and_android_independent(self):
        ios=self.module('affected_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host','tools/ios-build-qualification/host.py')
        android=self.module('affected_android_inputs','tools/repository-checks/android-build-inputs.py')
        paths=(inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md')
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertEqual(android._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision="a"*40,tree="b"*40)
                new=SimpleNamespace(entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,new))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertEqual(android._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
        for path in ('.github/test-suite-dependencies-extra.json','tools/test-evidence/affected-extra-test.py',
                     'tools/test-evidence/AFFECTED_SELECTION-extra.md'):
            entry=ios.Entry(path,'100644','blob','a'*40)
            self.assertEqual(ios._kind(entry),'application-input')
            self.assertEqual(android._kind(entry),'application-input')
            self.assertNotIn(path,host.CI_HOST_INDEPENDENT_PATHS)

    def test_exact_metadata_and_security_guide_ios_exclusions_keep_neighbors_and_modes_conservative(self):
        ios=self.module('metadata_ios_inputs','tools/ios-build-qualification/inputs.py')
        host=self.module('metadata_ios_host','tools/ios-build-qualification/host.py')
        paths={'.github/dependency-security.md', '.github/workflows/pr-metadata-context.yml',
            '.github/workflows/documentation-checks.yml', '.github/workflows/workflow-security.yml',
            'tools/repository-checks/metadata_context.py',
            'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-protected-ci-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-postmerge-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-ci37-v1.yml',
            '.github/workflows/documentation-push-owner.yml',
            'tools/test-evidence/source_admission.py',
            'tools/test-evidence/source-admission-test.py',
            'tools/repository-checks/workflows/producers/legacy/parent-qualification-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/protected-project-tests-metadata-v1.yml',
            'tools/repository-checks/workflows/producers/legacy/repository-checks-metadata-v1.yml',}
        for path in paths:
            with self.subTest(path=path):
                entry=ios.Entry(path,'100644','blob','a'*40)
                self.assertEqual(ios._kind(entry),'independent-host')
                self.assertIn(path,host.CI_HOST_INDEPENDENT_PATHS)
                old=SimpleNamespace(entries=(entry,),revision='a'*40,tree='b'*40)
                with patch.object(host,'REVIEWED_CI_HOST_BOUNDARY',host.ci_host_boundary(old)):
                    self.assertIsNotNone(host.ci_host_omission(old,SimpleNamespace(
                        entries=(ios.Entry(path,'100644','blob','b'*40),),revision='c'*40,tree='d'*40)))
                    for mode,kind in (('100755','blob'),('120000','blob'),('160000','commit')):
                        altered=ios.Entry(path,mode,kind,'b'*40)
                        self.assertEqual(ios._kind(altered),'application-input')
                        self.assertIsNone(host.ci_host_omission(old,SimpleNamespace(entries=(altered,))))
                neighbor=path+'.extra'
                self.assertEqual(ios._kind(ios.Entry(neighbor,'100644','blob','a'*40)),'application-input')
                self.assertNotIn(neighbor,host.CI_HOST_INDEPENDENT_PATHS)

    def test_complete_source_reader_complements_exclude_only_exact_new_leaves(self):
        ios=self.module('affected_ios_reviewed','tools/ios-build-qualification/inputs.py')
        host=self.module('affected_ios_host_reviewed','tools/ios-build-qualification/host.py')
        root=Path(__file__).resolve().parents[2]
        revision=ios._git(root,'rev-parse','--verify','HEAD^{commit}').decode().strip()
        snapshot=ios.read_snapshot(root,revision)
        doctor='tools/repository-health/check.py'
        paths={inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md',doctor}
        self.assertIn(doctor,ios.INDEPENDENT_HOST_PATHS)
        self.assertIn(doctor,ios.INDEPENDENT_EXECUTABLE_HOST_PATHS)
        self.assertIn(doctor,host.CI_HOST_INDEPENDENT_PATHS)
        self.assertIn(doctor,host.CI_HOST_EXECUTABLE_PATHS)
        added={entry.path:entry for entry in snapshot.entries if entry.path in paths}
        self.assertEqual(set(added),paths)
        self.assertTrue(all(entry.mode==('100755' if entry.path==doctor else '100644')
            and entry.object_type=='blob' for entry in added.values()))
        # Exercise child routing families even when this test runs on main,
        # whose parent-owned bootstrap does not enter the child comparison.
        variants=[snapshot]
        routing_paths=tuple(ios.ROUTING_DATA)
        for stage_index,stage in enumerate(((0,0),(1,0),(1,1))):
            routing={entry.path:entry for entry in snapshot.entries}
            routing.update({path:ios.Entry(path,'100644','blob',ios.ROUTING_DATA[path][index])
                for path,index in zip(routing_paths,stage)})
            routed=ios.Snapshot(snapshot.revision,snapshot.tree,tuple(
                sorted(routing.values(),key=lambda entry:entry.path)))
            self.assertEqual(ios.routing_data_stage(routed),stage_index)
            variants.append(routed)
        for variant in variants:
            with self.subTest(routing=ios.routing_data_stage(variant)):
                before=ios.Snapshot(variant.revision,variant.tree,tuple(
                    entry for entry in variant.entries if entry.path not in paths))
                self.assertEqual(len(before.entries)+len(paths),len(variant.entries))
                app=ios._boundary(before)
                own_host=host.ci_host_boundary(before)
                self.assertIsNotNone(app)
                self.assertIsNotNone(own_host)
                self.assertEqual(ios._boundary(variant),app)
                self.assertEqual(host.ci_host_boundary(variant),own_host)
                changed=ios.Snapshot(variant.revision,variant.tree,tuple(
                    ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
                    if entry.path in paths else entry for entry in variant.entries))
                self.assertEqual(ios._boundary(changed),app)
                self.assertEqual(host.ci_host_boundary(changed),own_host)
        # The historical anchor is independently reconstructed by the complete
        # immutable reader audit; a shallow candidate need not fetch its commit.
        self.assertEqual(ios.REVIEWED_REVISION,'2fc894a0605103843b36653f250f854714a963ee')
        self.assertEqual(ios.REVIEWED_BOUNDARY,
            'sha256:8527f25d58c8ebf8eebab8a9e43517899b7afce2e511026d2873a69ab82f1794')
        self.assertEqual(host.REVIEWED_CI_HOST_BOUNDARY,
            '90da341e226f56b8dfb8b925af7c0273ecc41772ca424e3426b04c80acdb9a7b')

    def test_new_policy_uses_existing_native_browser_and_package_host_routes(self):
        native=self.module('affected_native_route','tools/native-tests/check.py')
        checks=self.module('affected_repository_route','tools/repository-checks/check.py')
        packages=self.module('affected_package_route','tools/repository-checks/package_checks.py')
        paths=[inputs.AFFECTED_POLICY,'tools/test-evidence/affected-test.py',
               'tools/test-evidence/AFFECTED_SELECTION.md']
        self.assertEqual(native.plan(paths)['mode'],'skip')
        direct=checks.direct_browser_plan(paths)
        self.assertFalse(direct['browser']);self.assertFalse(direct['native'])
        self.assertEqual(packages.select(paths)['package_set'],[])
        self.assertEqual(packages.select(paths)['tool_projects'],[])
        self.assertEqual(native.plan(paths,regular=False)['mode'],'full')
        self.assertTrue(checks.direct_browser_plan(paths,regular=False)['native'])

    def test_new_policy_is_python_only_only_for_existing_ordinary_pinned_leaves(self):
        codeql=self.module('affected_codeql_route','tools/repository-checks/codeql.py')
        before={p:{'mode':'100644','type':'blob','sha':sha} for p,sha in codeql._REVIEWED_CONTROLS.items()}
        before['.github/workflows/codeql.yml']['sha']=codeql._PINNED_RESULTS_WORKFLOW
        before[inputs.AFFECTED_POLICY]=blob(b'old')
        after=deepcopy(before);after[inputs.AFFECTED_POLICY]=blob(b'new')
        self.assertEqual(codeql.select_languages(before,after)['languages'],['python'])
        for shape in ('new','removed','executable','alias','neighbor','legacy','mixed','config'):
            old=deepcopy(before);new=deepcopy(after)
            if shape=='new':del old[inputs.AFFECTED_POLICY]
            elif shape=='removed':del new[inputs.AFFECTED_POLICY]
            elif shape=='executable':new[inputs.AFFECTED_POLICY]['mode']='100755'
            elif shape=='alias':new[inputs.AFFECTED_POLICY]['mode']='120000'
            elif shape=='neighbor':new['.github/test-suite-dependencies-extra.json']=blob(b'new')
            elif shape=='legacy':old['.github/workflows/codeql.yml']['sha']=codeql._RETARGET_RESULTS_WORKFLOW
            elif shape=='mixed':new['actual.js']=blob(b'new')
            elif shape=='config':new['.github/codeql/codeql-config.yml']=blob(b'new')
            with self.subTest(shape=shape):
                self.assertIn('javascript-typescript',codeql.select_languages(old,new)['languages'])


class NonreusableRouteTests(unittest.TestCase):
    def execute(self, status=0, product=(), include_platform=False):
        import execution
        registry={'schema':1,'control_inputs':['fixed'],'suites':{
            'selected':definition(),'omitted':definition()}}
        observations=[]
        def run(args,suites,cancelled,result_callback):
            observations.extend(suite.name for suite in suites)
            for suite in suites:
                result_callback({'name':suite.name,'status':'passed' if status==0 else 'failed'})
            return status
        controller=SimpleNamespace(ROOT=None,run_command=lambda *a:None,
            Suite=lambda name,layer,command:SimpleNamespace(name=name,layer=layer,command=command),run_suites=run)
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(execution,'checkout_identity',return_value=('a'*40,'b'*40)),
              patch.object(execution.inputs,'load_registry',return_value=registry),
              patch.object(execution.inputs,'full_tree',return_value={'fixed':blob()}),
              patch.object(execution,'platform_suites',return_value=list(product)),
              patch.object(execution,'capture_execution_environment') as capture,
              patch.object(execution,'_runner',return_value=controller),
              patch.object(execution,'_write_receipt') as write):
            value=execution.execute(Path(temporary),['selected'],include_platform=include_platform,
                receipt_path=Path('/fixed-receipt'),_impact_selection=True)
        capture.assert_not_called()
        self.assertEqual(observations,['selected'])
        self.assertEqual(write.call_count,1)
        return value

    def test_empty_platform_context_runs_exact_subset_without_runtime_or_reuse_claim(self):
        code,receipt=self.execute()
        self.assertEqual(code,0)
        self.assertEqual(receipt['requested_suites'],['selected'])
        self.assertFalse(receipt['reusable']);self.assertIsNone(receipt['environment'])
        self.assertEqual(receipt['results'],{'selected':{'status':'passed','fingerprint':None}})
        self.assertEqual(receipt['platform_results'],{})

    def test_started_failure_stays_failed_once_without_runtime_or_full_retry(self):
        code,receipt=self.execute(status=17)
        self.assertEqual(code,17)
        self.assertEqual(receipt['conclusion'],'failure')
        self.assertFalse(receipt['reusable'])

    def test_impact_execution_rejects_platform_inventory_flags(self):
        import execution
        with self.assertRaises(execution.ExecutionError):
            self.execute(product=[('actual-platform',['python','actual.py'])],include_platform=True)

    def test_legacy_owner_forwards_dynamic_selection_without_capture_and_never_retries_failure(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('affected_legacy_route',root/'tools/repository-checks/android_handoff.py')
        owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
        selected={'reason':'protected-affected-dependencies','suites':['selected'],
                  'include_platform':False,'full_host':True}
        proof={'reusable':False,'environment':None,'conclusion':'failure',
               'results':{'selected':{'status':'failed','fingerprint':None}}}
        shared=SimpleNamespace(execute=Mock(return_value=(17,proof)),digest=lambda value:'fixed',
            _write_receipt=Mock(),inputs=SimpleNamespace(load_registry=lambda path:{'suites':{'selected':{},'omitted':{}}}))
        controller=SimpleNamespace(android=lambda:SimpleNamespace(_shared=lambda:(shared,None)))
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(owner,'gate',return_value=controller),
              patch.object(owner,'host_selection',return_value=object()),
              patch.object(owner,'selected_host',return_value=selected),
              patch.object(owner,'platform_owner',return_value={} )):
            base=Path(temporary);candidate=base/'candidate';candidate.mkdir()
            status,observed=owner.project(candidate,{},'a'*40,'pull_request',
                junit=base/'results.xml',receipt_path=base/'receipt.json')
        self.assertEqual(status,17);self.assertEqual(observed['conclusion'],'failure')
        shared.execute.assert_called_once()
        self.assertIs(shared.execute.call_args.kwargs['_impact_selection'],True)
        self.assertEqual(shared.execute.call_args.kwargs['suite_names'],['selected'])
        self.assertFalse(observed['reusable']);self.assertIsNone(observed['environment'])


class InstalledCompilerReaderTests(unittest.TestCase):
    PROFILE_MODES = {
        '.github/workflows/ios-integrated.yml': '100644',
        'docs/ios/SIGNING_AND_DEVICE_TESTS.md': '100644',
        'ios/ci/qt-checkpoint-artifact.py': '100755',
        'ios/tests/ios-full-client-sccache-contract-test.py': '100644',
        'ios/tests/qt-checkpoint-artifact-test.py': '100755',
    }

    def private_git_context(self):
        """Real commits and immutable reads, with an explicitly synthetic policy.

        Fixture hashes never claim to be the seven-target shipping certificates.
        The exact production five/R constants are checked separately by host tests.
        """
        temporary=tempfile.TemporaryDirectory(prefix='overte-installed-compiler-readers-')
        self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        source=Path(__file__).resolve().parents[2]
        actual=inputs.load_registry(source/'.github/test-suites.json')
        names=('device-control-plane-full','shared-script-behavior','test-evidence')
        registry={'schema':1,'control_inputs':actual['control_inputs'],
            'suites':{name:deepcopy(actual['suites'][name]) for name in names}}
        def write(path,data,mode=0o644):
            leaf=root/path;leaf.parent.mkdir(parents=True,exist_ok=True)
            leaf.write_bytes(data);leaf.chmod(mode)
        def git(*args):
            return inputs.subprocess.check_output(['git','-c','core.hooksPath=/dev/null',
                '-c','commit.gpgsign=false','-c','user.name=Compiler reader fixture',
                '-c','user.email=fixture@example.invalid',*args],cwd=root).decode().strip()
        def snapshot():
            git('add','--','.');git('commit','-qm','Record private immutable reader fixture')
            return inputs.full_tree(root,git('rev-parse','HEAD'))
        git('init','-q','--initial-branch=main')
        required=set(inputs.AFFECTED_AUTHORITY)
        for suite in registry['suites'].values():required.update(suite['closure']['required'])
        for path in sorted(required):write(path,('fixed authority or required fixture '+path+'\n').encode(),
            0o755 if path=='tests/run-project-tests.py' else 0o644)
        write('.github/test-suites.json',(json.dumps(registry,indent=2)+'\n').encode())
        profile_raw=(json.dumps({'schema':1,'platform':'shared','suites':[]},indent=2)+'\n').encode()
        self.assertEqual(blob(profile_raw),inputs._AFFECTED_SHARED_PROFILE)
        write('tests/platform-profile.json',profile_raw)
        ci='tools/branch-cleanup/cleanup.py';write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('old '+path+'\n').encode(),int(mode,8)&0o777)
        provisional=snapshot()
        independent=[inputs.AFFECTED_POLICY,ci]
        reader=inputs.device_reader_digest(provisional,independent)
        lookup=inputs.affected_lookup_digest(provisional)
        policy={'schema':2,'registry_digest':inputs._suite_definition_digest(registry),
            'lookup_digest':lookup,'suites':{},'targets':{
                target:{'profile':{'mode':'100644','type':'blob','sha':sha},
                        'lookup_digest':lookup,'reader_digest':reader}
                for target,sha in inputs._AFFECTED_TARGET_PROFILES.items()}}
        for name,suite in registry['suites'].items():
            policy['suites'][name]={'kind':'device-control-plane' if name==names[0]
                else 'reviewed-product-inventory' if name==names[1] else 'repository',
                'definition_digest':inputs._suite_definition_digest(suite),'setup':['host-full']}
        policy['suites'][names[0]].update(reviewed_reader_digest=reader,native_independent_paths=independent)
        raw=(json.dumps(policy,indent=2)+'\n').encode();write(inputs.AFFECTED_POLICY,raw)
        old=snapshot()
        self.assertEqual(inputs.device_reader_digest(old,independent),reader)
        write(ci,b'new independent CI\n');old_ci=snapshot()
        write(ci,b'old independent CI\n')
        for path,mode in self.PROFILE_MODES.items():
            write(path,('installed '+path+'\n').encode(),int(mode,8)&0o777)
        new=snapshot()
        write(ci,b'new independent CI\n');new_ci=snapshot()
        installed={path:new[path].copy() for path in self.PROFILE_MODES}
        new_reader=inputs.device_reader_digest(new,independent)
        self.assertNotEqual(reader,new_reader)
        self.assertEqual(inputs.affected_lookup_digest(new),lookup)
        return registry,raw,old,old_ci,new,new_ci,installed,new_reader

    def test_equal_old_and_equal_installed_readers_omit_but_install_and_revert_keep_product_owners(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for base,candidate in ((old,old_ci),(new,new_ci)):
                with self.subTest(family='installed' if base is new else 'original'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['omitted'])
                    self.assertIn('shared-script-behavior',plan['omitted'])
                    self.assertIn('test-evidence',plan['required']);self.assertFalse(plan['reusable'])
            for base,candidate in ((old,new_ci),(new,old_ci)):
                with self.subTest(direction='install' if base is old else 'revert'):
                    plan=inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')
                    self.assertIn('device-control-plane-full',plan['required'])
                    self.assertIn('shared-script-behavior',plan['required'])

    def test_installed_reader_rejects_wrong_target_stale_hash_profile_and_neighbor_bytes(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            plan=inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-main')
            self.assertIn('device-control-plane-full',plan['required'])
            with patch.object(inputs,'INSTALLED_COMPILER_READER','sha256:'+'f'*64):
                self.assertIn('device-control-plane-full',
                    inputs.plan_affected(registry,raw,new,new_ci,old,target='apple-ios')['required'])
            for change in ('guide','helper','mode','missing','neighbor'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    helper='ios/ci/qt-checkpoint-artifact.py'
                    if change=='missing':del tree[helper]
                    elif change=='mode':tree[helper]['mode']='100644'
                    elif change=='neighbor':tree['ios/ci/unreviewed.hpp']=blob(b'new neighboring input')
                    else:tree['docs/ios/SIGNING_AND_DEVICE_TESTS.md' if change=='guide' else helper]=blob(b'changed bytes')
                with self.subTest(change=change):
                    self.assertIn('device-control-plane-full',
                        inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')['required'])
                    # Even falsely substituting this reader hash cannot bypass
                    # the independent exact-five profile check.
                    changed_reader=inputs.device_reader_digest(base,json.loads(raw)['suites'][
                        'device-control-plane-full']['native_independent_paths'])
                    if change!='neighbor':
                        with patch.object(inputs,'INSTALLED_COMPILER_READER',changed_reader):
                            self.assertIn('device-control-plane-full',inputs.plan_affected(
                                registry,raw,base,candidate,old,target='apple-ios')['required'])

    def test_installed_reader_keeps_lookup_authority_profile_and_nonordinary_failures_closed(self):
        registry,raw,old,old_ci,new,new_ci,profile,reader=self.private_git_context()
        with (patch.object(inputs,'INSTALLED_COMPILER_PROFILE',profile,create=True),
              patch.object(inputs,'INSTALLED_COMPILER_READER',reader,create=True)):
            for change in ('lookup','authority','graph','platform','symlink'):
                base,candidate=deepcopy(new),deepcopy(new_ci)
                for tree in (base,candidate):
                    if change=='lookup':tree['ios/ci/unreviewed_reader.py']=blob(b'new import candidate')
                    elif change=='authority':tree['tools/test-evidence/inputs.py']=blob(b'stale selector')
                    elif change=='graph':tree[inputs.AFFECTED_POLICY]=blob(b'foreign graph')
                    elif change=='platform':tree['tests/platform-profile.json']=blob(b'foreign target')
                    else:tree['ios/ci/qt-checkpoint-artifact.py']['mode']='120000'
                with self.subTest(change=change),self.assertRaises(inputs.InputError):
                    inputs.plan_affected(registry,raw,base,candidate,old,target='apple-ios')


if __name__=='__main__':unittest.main()
