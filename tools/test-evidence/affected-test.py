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
# 4f890ff5615727cdc4d0064a732fa6cbec94413f / tree 1dbefdb6f8de05bb08e9a526972c93aeb624d7f2.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '870a1d560c2afad1ac41a113035034771044806af79f65543ba969038676472a'
_MAIN_PROJECTION_B85 = (
    'c-qaK-Et#IlAZ7M7=68*%82~mr;y2X4~t(Gx=4ZpfYn{Qw(qX*BtSN6nnXkbwUSo0+tbypi9lwChx_q!j{oOx|G3{CzrOe{?kVnf'
    '+jzJ8<0<X$j(hiX$Z7wN-w(T|-~RnSe|y};^xMDxW}0T`y5Iiox5HP*-`X)Y$uvWbac-M_HZeIj4>sp!j9u_4b)%h({y!XlJnO%}'
    'KkWQ(|MhQg%X$_HU+<oG58Lpgu$uR6G-gP{JT}p#Fb(6#8cj1cxgC6L@;G#^nLc0b*@bWJKHdGX+keXsyFc#k6Tj9Sx4Wl9Y4J3~'
    'ex7aD^?e*>_Ryt}vWsCf?aV)Nz8U+W`F!zxdfpwj$KC$NUHF>9x6+Dz;Nj(9SYXlvPASc~?{d?{nIAe&uC-nA7as009gcU0m+dj#'
    '#q^w>VtNYOR9e@@HcvyIdt>d`TQgh3!ebcPzR$+=&ZRMj#?-7^S}P8{pY^%4+4{j*=lV3xIknw1577;S>Ac~+e!kZ0t32>>_vz_)'
    '_s<viu+7`Byw!jFczn3<OLNC(H0Gfj+Nm*ah>7RfwVoF}j&^L#JSKPPoxWRrzxzFf<DGu{;qtP{@XgMdpO~zV#tyORyCIJ~i}E?O'
    'Vd(lMMpv`!-#@C0OOJWv+_c&B{bZ64bKqNUEx+9b6Q>Z_!Q6HE?@RkV%MlsE!<MJ~C2YU^o}RvKpAKK{o!;~FkIz>%#)Zy@V0pOR'
    '=xsN}Ay_l^DfUy>o7^Wej*VTj>NCHb7k+u&E{|>E9gkD%n=slqHF@%$56fpe5~QXkr4ZJwyYrV<%`T5kXuHv5exGe-*VuM!eHZ35'
    'b$o6vxPEHQnpO8NPZ!q=rW=MKW;gq88u@u{Zii-`jBk@qwu=O(l=G@J^(Ak@*ZuA>Z4P1geEC;Teb+QRS!dc|2ote!c75x{rneKZ'
    's}FIGlUetymmNI0$8;cYr_DaO=k3$|#cjliuQv>-A3CCDGF{>j6SQ6MLo=AZ>j)_(tbY(s&ySn1d&=9(>yOT)VQTwfn2a-a3TEJV'
    '^~AQRkI^=4Ze)+`>h*Om$IYMLv%k2$=R0e<F82M%CDAuLiQdgku-uS*ku6W5Nv(IQ*XIl5s=T;%3b~zJZ)4BFYeyf(V7zG?$E_8d'
    'HB)T6p{e-oiYR}$A77r*QIT%5-@P2uCT`vR)9!HGhRe~Wor8B%>P#Q{)baY~DJ93%+4KWZFGO#h>CL=)8!z$s;=*<s2a}AAY2?7i'
    'Sx=vx48i1RIS84nu1n)sz3}P7JFmVZX8Ht=>CfZk0Mv8XxwvfGw^Q3DZK|Ks=zA_2JEve8uPm*&j|WFyc-%d1!yRGo`}V+%$^rc1'
    'UgGw+Ip27?WiOt{zE7@;){zainP?beH*?2Kiiu|E^)h%e<JG%aPNfdVgL@&Dyd0&*p$*Y;>2<shG7L}LoF_Zy9LKgHy-5wpR&)Jk'
    'UPvb|N6HwSnSvdr-1Pi**9SXtHE>Kw_xdUKE_SU==IT9sOZ%tvuvy;H#huL7^FZP_aPRwe%w1!%k9O$II1hP9<Rg5)HebDyNB2a!'
    '9XI6oe9HSDo3Go0a+Qm_YIJc8q({C<fiN<rp396|lw85I?64U-p3?QZ+Ijw^?}cDCgf>SLdQY_Myd6irUe`9UC4EYKLBz2^|MdD@'
    'JfABM_pqGmy$i?7fo+Q2WXH}<6j;+hRPXzC3~_RU<+HY3Gsk2nKVQ8ia;p5Wz5jZwj<v(sW-_YAb-m|mNt|;tnQ<ci=mEvHp=QgY'
    'zhO(Ibc+YjH(_c<D$sVI+O*2L$g+4OGjFe%+G%QSym||y9g$$S{m#MOygj1JSpeS(_28VT-*^V?G)}~QKM;JgHxx7`5PzEMAIss$'
    'xw`zZ%zPT7miBWyg}^10XTICOgBmF($FXnc{)SU@bo={MeG6m~-o}MU_K^p^k;K6^-PrSyjCw-Uer9gc^>68vt-f9be)sYeT_Mo$'
    'naq4Rr02Yr#w-OO|F0iHXN@1a#u@5_F8!iCRa{SP%4Y6oPfgaf2~;68KF44TU-A_Bj1_T0Zf@Msaz|~d!eHph->u=o<YJsG@J>vA'
    ';>)JWacv7E;4^8~jqfczec$ePPmlbIr&o8mth2&-gc7vg`#ua@5#9}8O+#{%w>&d$^w{3Er|MgDa^2`!s)}*&X#y&V9n~!f80DoW'
    '_Z>L!?5O*7+u3YM0`E_^M<EmRe&U0QqYVv#*z>adJcN1TvS_)}e9D&X-nO-?Zh1cfXps=}jb~66vXG!UaRO}$<RV?}S{LW=i?$Ya'
    'j|)yxdSF9#shvsWyV(#Z^*$$(X2LhS9is7>dv<E$ui4cheNRt?s+y8@4!vF=MI-^B;dy~oaede}O`xGIf!y7;pQ=bedf3gaAcmOo'
    '9Ol7s<GN<x@CN`{Gw?zUW$ukzd6yMEZfm~r8Su~vU}#fI%_Rg4Owo7{t;FtH>ynAC%eU=oeQLyebL5QRAiZw|bL9pc!VI?K69;d!'
    '?67OHzja^aN1L!uV7teydpH!(0ZOi}vs|>(>`B`)sH0a-U;rY6X@e(qiu28Ts!0i2E`L58{s*+k8N-<;s|L~sxoIaLc5B=it-WnC'
    'S7dMGkUpEi3<D>Ovf1^ZrfKYRXOc5qIhK3S*l^p%4!f5<pjOy@P2kqyayG|$v7sn(JQ<;EDYo-q+HO_}ki#5#XaR`n#w{tU+*FjX'
    'AWY<IfPFLwsLZnGp0S`Vv9;j$CKH~f=EJ_v`t4-5eRwGVy;C=Z<WldNu6Kck$w+SN$XSBrF@?6BW*R8w#_#(0_?)*7>8)D3eEdf)'
    '{h@VKXTU*3%mG-2$KuI%8$q&kc5FY~_;nxmFNY&H$+z@lUxG$C^W>MD@6IQ~H$C%?!VFN_c*94PrrgCT-BJ;(*o?C5rZpp&sGX<G'
    '+sl?1-gUm=gazNV{R|dScm1D1>hnLjd|Sj8G?32%bad>wFDU36GTGkvo<tUmwx7Z@)n(ZCFH5*f`^W9!u=EfwCS!i4jn=Bsk*DM%'
    'n8rvN?Hk`Ynu$|rTqNey{p7DZz5U&;6!3LHQ%_8eer4!l=q;g*`h4OBkBy1IaU7GnHBV{F<<M#7U^#d#?T@G|3g9~#04`vY%$*ZW'
    '%N}A~{`AD<|2=J7eB55XN$6~ld=USPx5Gg915_gB;AT3rrfmVZItqr$g5bPr4Vc(8T;h~vDv-vI!a!l)apFNi1Rn*;HNrsMxAgub'
    'Rp%I?HM9^Z@~ID1wbB8K^rt6s4Gw!_qn`ocE9=Gg{hpemG)8KRu8pw;<?qK%1%8^zp6TT#K5J@eYO^@5So~C&hTT4Ge&>38N|$R0'
    'g;s(YeU5I3RDZ(=$~-r!+-I6m19hqkxe}v$zk|o!_p}tFTtS7a(11&h*5<}ftrLt(T0_#QyAfP$rfMH)Jj||s59^{z2t4to<ybeg'
    'zFHbxy*Ig~q0322TtEq`K$v~~`jw%@#7yltIn~<WDC5M56XM1ZpE!u!M0h9fZtE95#g~d_P7TC+r<rTHzO3OCPUO<QrMYUkaRG>d'
    'PTHYayYycr?BzRzMs`Em<49eFg^ZTWe&WFc=r_D>15QFhmakv_-0cg`FPEPK=gx%5@~6CYXd%=Y+++hNG4~w(glVMFGGDQgy7k-K'
    ')8sT{eKb2szQ|HD=b^Ry!Q?;}2KWul`cHs_ec^I&6x{wY7UVrQsa2PiTO|<k`kp<7WP3isL~xwQG-C8uZ=vo<j68qVYiN2q$Oe(W'
    '!ZzUHJL==a%}#RFlV@D9jUUIayQexpQy)J?0-(;c(6FEgr5?fubwZlxF;N}!yt*qM#y;JH=}@S|%^!RB{9MYif^R5)Gam(^Ko}U8'
    'qwgI(VJdPMV|*{*J6C)d085vfu){!|Hn14!T<p|Z1RBhA+pJfJ1mz{|OO?gjnSfB65X_^ST`O`)rWui9!;RE|ZgnIFvG;TtMS;mH'
    '?xU-+0{ROOnCK9ZTyihLilf^ZoS;C*PT<Z3$XpfG(CL@oZJ(ZBj$e4|4`)`@9U1=JABn^pSdEJ4;%?~GsY>OoFW+Avv!_%9S`#1w'
    '+?{zWwy(&Ne%cMI-=!$x)BBC7^w_wg9$gtYa#V?=Y1AMV4wB=m2%KKZlCh)qpii9i)mDI`pKYu}+R2;%<xe~oE3APlG{z}YeT=j|'
    'dml0ZY^tElESL2wx$*Lnq-uPd%1&wa5)sq^_tauznmllI@8F4yE>|x33XLgNZg>xF|G3+4UikM4Sxav@2;7l$T)@M^5LEsFwa(LM'
    'Ook?AC`Jk6wfi_#o_A-i#FxW9{J$oTlsEQ&jZX6UR!*D}6<ABAS->+%Z>I^qBCiPUX-CTC2Jj4ka?UT$2Bsuw;0@b(1rU~PUCw$t'
    'KU%1SArMmushnSGjt>4rCLLxUB%c|=(UqH7NSvpy8#1XoRDV8k;JlIsCJPj06Sr}IWx`vd_I9!7kH`{-3i?%XU;btL5Ks6|E#OLI'
    'n;-&NH^Ts;N7Y1vz&MUVK)}dox3uDCn%g&b#_ZlbwgL}@W2fguNC@yXLFyWHgK09r$Qi5{4{(sX+c&nQ4YYrKsb|vpWn_Uqm4!Vw'
    '(JeRda-vbUqorYN;nTq{gm7-A`4{Z$i973oria_p>bv}vB_gy3i>7N$st0yX^rX!Xq~xK-Q1j9@o_gQkzN=HxLyUOWp}l;mdI!mC'
    '1YG3ZH3X{2fs8Ys8ebf2TTlT||H<FJwKcITl4tPk^WnpvCw|+BrauHHg;E;G>UvPGxnFQB&*}R1aj9fq{PS0LD6pd;O%8;4wil>l'
    'g(i?8IRIk_0F<~~I3jKPU+|5cuEHw#dZf=ulmOca765Ua7RWS18E*y~L{hUnxF+4csl)buVMlC{f>8NZ9LgSGk;{;x4?w#E#GSIA'
    'CJqCwt3aa50|Q@8{|$RvGM$RH`;?-Y)n0@AI`i#O4O0;%u+W|o5jIkapwGYH5WETjE^jB(KZXSgBui=oG&BJV4R)X|K;$7nntmxa'
    '!j;>3-NTo4S0(*^7Nz&sMlZN(;%0)Q3{e8=mIt)}wKe0_Z}Dwc%SBmW-3YpZoXvgch*KR$k;EGu3tZRRRzd}c%{M=vbBMnT>9p2T'
    'EOF&<Awz`#VTI2^j0Zv>szWQEK|8zt*1c35GYg|eq&_GaBPb)hT{`Wad>C~D=w@(aqx7@Ko40bVAAUY;g$U57T*@Pz6X${0+ZMqY'
    'q<^G5UCRqoM+E@<)~&7B5}+V}4^a`mR!2hRMOr2QGiaLV>m)x49&avGlX1J3fatulWYcRaVgY1bIF_+s<Y?Twfo>?J?G$F^Q*#3X'
    'F|=Uf;N+AwZfw`=p;W|DrBQ^~sUIm1C<svGwc;|<R*Fb5C@4pREUx-@S2mjH_co{*x=b$~x=@SgWTu9PY(dHff!ff8F!M(rC)b~Q'
    '$|ckySsMJ1xSWb&djFt_{4hjI0n&@->zC*;e8k|4yFe{Ymgye8Y@q7DlW1-9&kFrImgNIR|7LZcB@cepqbT9)LZs%!6mLhDE-x#}'
    ';blx_jv3lHeSs;F2%)NkK}*H$rCs5hX$g4rvf9hboD!bpKNotvGm<*NEI#++V4)16g&HZ^TDnw<{wU(m-u-<w!C&b~sQ4GRKW<S@'
    'kti=rmt%oLPIew)-hl>ll_1AyOrTfPD=ikS66GHo8REqymoJ6HoWC#9*^Fud8u}1^101OaK5J}%+=fKqK7}4NBQfBkJN9o2o`@lr'
    'zY`~9uWuVzYLk?MJXQ!$eDUo}HPD~x;!yZ~2fusVeCO7V<&*{(bEc;5Iog0DVEj<Oz-qFCXbsDd%rN>mf7HA_Wh*g#-|8(=-#s6-'
    'dQGC&NSpwTM1Um+K54NDRTpJGm!yaP-b9+7uC!=$&qrxzmI(8=6?uApJy)Ju!)t^aHG$%KN0*8IHCO^+bQ~p-gt|4Rx)l#^s_JKo'
    'g10}u9N4Tns-c<qbm?gz+JU?Rgl^cu2m`pGvC{hBuH3=%^Y-O&Q?rpEwl>|QG%ju2HX%2T#BwEPiuKTfp)k09<wmL=0(_Z)_L?W&'
    'b|Q+7fB_bA1o?-vgAbEK?SRy9?b>1Y!2Pm2rSNCkWBJ=}J0bTTHQVet+T1Xf<^}M&n0yFQ=rK=Z`El)T7QlFOpJ=$3T8<FCpcr!&'
    '=;jmFI^|<98oDVV)b2)*WH30Yvg$1?-$B*8fKm{ln`Hu;sAhc!*(#&av1<Q=8Sx&#v~2ae`2XV_(7AXlED6bWBCUXt*dVXvcSZ%k'
    'kx)xJovL_*T|n!#tz9yv!#BEDn_YN$*#24d?15FaG<_?elYx{68V{v7os+qPUJjQD0u$NEm0P%fe%XA5ANi0D1z3}wB7$_-$f&kq'
    'Wsjz7NlburTJ_c}96R1dYJR~!AVqV%Lv=6kjA+pi6(EkmAsup7+b^nQ5*MLEPL8^!ZOyOQ&;l@3G@}KE_tI^&A=?n?{GyiVQ6VE$'
    'NP2}yysLJ&a#vj3dzcZ2?Kl4R_3thwUQ|I)Q|68wXeKoQWE$znqR5OB-L5EEG%W;s<$g{Gg!}P8KvRvBwx3<GKSQdx9dMO2O&<DQ'
    '-T590Nx~ALQ~o~EvNvt&uRT_)_hYOla0Ij?7DEQ#!lFSX!8420;Dppb^4)&uD)RAu9(Une)!}xNdN>r-_)H9Nb>Q!CrAf#yO;i?Z'
    'fy_UL+J(>6qTfEn68n-$Rmw1eSup6*`9>juLRgA}urot&MT8oL>ht`(4ZH43-u`(M>c4=Wm*bi=J0x`E5%eBa7K<)GIw{lx<d_<S'
    'tYe(kt^XHgs`^@?On0K2(maASram?GG6o<tLf8S&g4lfkW$QMwm(|L?eiO);D1~S%iX8w%=RDx5%x;jxAd)c?0#tyP+D-7^Dx$`U'
    'JHAs&6{SK31e-k+A}-ZlelH$bMNV)Df}<q8atEh;r}}wF(Lt3fm<tgwMLd0Qh$H00`1~M-Ydc6SQ&)Z0f8X)9o5j*d)oLL+kybTy'
    '?^+^&7lo}+%Fm*NCFrCmaKtJsuk9-roH_h_bkMc1!r?&7U~9mkeTOW|%V3CJJ+*NzEr?*|$A6?M=@mV9PzD`%t}9-2o~3cJU=9N}'
    'Jei&Wy{7+AT5^%1z1HOgo$xFL#Y~UbB>MeblVD8Y2_Q44i3Toz2{4pO0jEwUP3H;R$pE;+t+47?Q+*=>B5MiY@BK-;9lF}ZmS4I%'
    'w}bT`H>ZDt%;2G-?JCfePd8GrV}mh5e1X)_Qm*sx;U@91SqLAoxn?`tCpCWIT=<uaUDxLM#lLc4F7Jtu&*ck<3pxRO7XW)Aox5oo'
    'QQe@g1jh4l^KaUd)NSac(gW90iMfVpiL?j<@B+{suvCD~jZYBjdtjQj7kdqM@lE@A*S;Y=$mzI!ynIb@2f|=SKSJ4yI#{<A5<pG|'
    '9bXQRG-l+#(Ot8v2c8by-c$<ByoE+h`e3N<F!JF+8CXITA++KoxC5{N4>8y5;c;mP(vm3c0dFp$FCaX#yv~H@abfe#^t1LuEQa>$'
    '<28Gby$^fX$BJi>xS3iho^a{nO95_&9RueCO9Z40aX`)hAQ8rE_Cae@)%f!ZJ@~4RgPMD$5=Lpj(S~9Ovyqe^XAgEnyJ*U~wTAhs'
    'k7EIAHm7^*bh0nMpN6}6pdKW9g}vnkk^$wyS%MM(12E{TN!Ohou=(8{0N}ive?C4GNOdGL$V(s~a-U!bM7`7D|3#GsX^D`}ZA#G|'
    'f5BGtXO}SpELMh*esx+nW%v>CScowYV_}YuX%@~s#o_wBh?RM8d@Kd@Mkprew~;0VQ3%);ZwmO9e1?o>!q)_PNlMpj<lr8k(WD*3'
    '4?eZ_OT>Nt20W1p3y*_2ByY*~GZhalG~YuCgi*~$ldg*WM=8@|MFr5Q<^VPt>51bx2VdOKhj0K1Fm*e*@8u2*&|kBO)8`Q$D8w%B'
    '0sfd|A`$F}&jbOS1pFh&FOUz-a=>+XcVqpr318juRYv2E#j_%wFi5sI%5;}WwZT;Yy17{(qjG+cE>pDo`f&DU@_4q60>b@TKnNft'
    '0B|MxJtKT8wGC)j!d^hqf=v^TLy*c;AH+^1*wgK@^HNLFOchbhJr|NBsGrcbNk3`1_hF(_gXaaQks7GPRBG}T1$^~J6vM-h@Q}`V'
    'TL_#G<!{HYiyOd0D%WMwAwx+R8bTMB9sNW=P{;zheIRkr3j`T3?icN;!q^Ma2tIm<@a1esm__;@fW12X=}ZL;-~+>O`Xw8RTU_^!'
    '1;)EY!XD_Q(dhNE`5HvD3ix>@*h73;u&%PoxL>lPefsB1Ddt0F)~7>+!_NzoM<taw0&$=^wQnaRw+Lgp@zxDJ?C!TuRanbFn~W<k'
    '>4L`Uk}n&yx+D7+TNZmtZpcoYms@uP`f-p(<0+)7j|p@`2=3BHq+7}xo6SI>LJ!eLk_ZWyxs`5yQZyXjRMVwB@qTza)FiZ=Mgk#S'
    'COSSMUN*|`;P+-yiWG0%(;*$XsqVpcpWO4|>#ndXM7x;%f=Ut{F?j)W*ISI_nw=OHQ3P=)+P`d9FV7D<cNuEVLg6Xku@Z&Niw_8;'
    '2*ezGdC88Aka`GB-C%Fs({cALJ)LQ@my<0pT(M#U^@{7s#t|M8jiBQof0|na?^fIMS8piBz0ml5O8PgRiX1_%Ey_mJFHl}U^WdFM'
    'va`c11Wx1BS*}=UE7xv^f1pOi=IinJTosrIiS$kF!mGfmfnd<V`h<|c{Q}1l7pej8Rx{kXp+nejpKGpux>|m~E)*o9r@lm^O7aH?'
    'i&rS+H|`)(ky3Kru%R-|lpcwZ0|6Cfv}DFqvQ*dDBOuYjH<HT*5moQ6KJan(=!nzH_3@Y2_vLtP_)Z<l7+AQ<i583;VI|xf=&vM9'
    '*i6XS>BcQRY$dg=K<g+|rY@ms_JltaGN4!yWEdm0$&xBgQu7dzx?iy$s+zPd83D<`4!?6+CODDMIiWdB!@`RmL4D3Eq#;P_w7GFZ'
    'k~85iR~4ZV_ra8a;L~uX!E7nFfH&d$K$MqzS|qCmt7xy?(ur~OcE;W*&Mv>YUM^)FeLzeI9BDL~&{2JRiX6N*JTfn;)8<!gOMivR'
    'SYgRZO2TWClNBCLFq2^|h7lwXU$BX{3o?n4yPbZ~zH-^#Mo!TQ#F6MIEl~$oS!VZS-Vkw!m7tL$TACX-q+7MZ${J%9g(EEQ(Ua?g'
    'o@htR>cvr}LeGJer1p@xaW^NH<DNrzgaKJpR={$Fa7e1rp=3oTfb`0U*G;vE!<?*>aJYbJdgHFn_s7dq<-?+53oc83%iZoMVSCg~'
    '6Fd>&JV5X;^nnwwDZO@E_q*dxoN^NG^WF;CHbiy_UXw+A-HGK0p%MaxrvRX}I6{<zF?x0M7P25du3*c{XUyZhLB>yLrqL>DC5=@s'
    'H;x)b6JRp!O&Z_%+KoKy;$mlYGLO29_;hk2N2>>gWL`7?TpG~osEKHMYwiM-HIe&<y{H&Ezoc{cuDVKq9gHw-idU$b%<*W2$XOZ@'
    'yej#VjTA{#C%0{E5mCqGq=j9v6`=%;^bo=Xezr3d;2>f-j5|by6me>WF5u9$dpg4+e?6x1mIgCZ!J5%Y5(i3x;X)R5m%c2YGBHvg'
    'wYk0kVO8w*&hM`h9O+15WjZ3*j^+f;_Bb_<qS_+AhnWV|S7h_6(~_s18b?C&(7*G<N{nB_eFpD8h^v?up@KLCNrr_1xW-7%gcr`$'
    '^~Y|>Ay4HHoY|K`R76pO5d%b0BV#fR-GCwm0-?rZ(v*e(_?WJ~VSyI)SyS^9vg?o<AS)-UWa+<&1i0hS^w%Gt*b8_-b$n!F%D3$3'
    'Yz?tFewFLq<?Ubw+^A2%vLuUgNt;=pt{+TO^}JxmplG~0H9D7M)Imf?2#00TfwZ}tb=db{Rx=4V3I;wM<ldI<fhC({K+AmfJ+|DW'
    'vF`4$-0ZXkFl)mxpZt|v5s;deJl$-pwdj0dc7p8X`n@c7JkpNZ(~c;yBgg06P!)Co>;wOCL?2YvXg%p*kbf}mW4Lig-ybUsKI9z&'
    '>cZeBn=Cl>L=Fv8d+^vwYurjCv3B9=Jm~wR#Pz$-v{HJ{$SXj!S&((Bu@@{o$sUqBOVu_0(v(TFyJ08kPx0l|u&%ZpW$}5OW$@tP'
    '4MoT$sty^t!_CUSicle7c6ZCBw#(B=wU22w$hU)Bks;PVZIK5aj4LeSIvK=(fyj`hop0OGuA&}e+>f#{F?X3n65-Dp3h5RVfsBga'
    'n=2xY*F&D#$x#@?ZeO4rc1qS;xjKxHxAD$I_DFnYURttNm0^|y@P>Vy$$+7xH-u&fvlyQ;Fnlb7u<#8uf3S~hqfAja@+fJ2x@9YG'
    '_Y@JZkmm#{W{fF8I6!%ku?!8SIrvr*2>D8=>bcE1;=f`u<?bK=nAAe()j8Fp5E$B(s8)f002$EtB|JfrzhN_y7Z$Wrgfhur<gSOU'
    'U*F1XFK7}RsWR*s5-^7cfe*Lr;wZPyjYwQYEQ)eiEm4})q*ElM?1!!~;SR)3L`fhsDxO<n?^_O$;Dn&@FPJ^yuYuJbW3}L-&om5q'
    'CcHJ8DqTmWLxARw^3`e9U%BUIX>1mR{J3DFM+AC@Tn2W^i_+XD+7^_Ye93@5a;LxMlH|ciGXa)z;@B3%Z?xWUAM7*~(aVbsrZM;v'
    'S0rZ{o(_mJ8CHF6_56Sp&#S?~@}G;nZ8AwGbBajb1awJju$MQQr=prk>>4%1urRKtJisSCNnn5OPrQOC)dnqaylEuCyaP??Mp&1?'
    'nXs6k!(q{aM%U74=vTlMpX_TX5vq5E3_j>(jhX~VLx(tnrVcM$tfqUBdFbr|W_DNa>fAi3-4CfS5T!@9KxaVboaP(M1UUK#E4id-'
    'W-#c>n5*~mo<&)^DUv?e07lgl6lJ;w@)(pfU5B1-7^ppVHY?Jt4>zTMR==mE^$iCAc{lWN5>tRfFt0|T5s5mHy0ITmkgVHN*t^45'
    'Y$2a^M_1N=11rIunWdq?vIG1S61nVOBkVBh1qiqle0Bvt?q7Cu#w_ZG1M$W*sFe9{O#f3DAPcpK#PMFi%N#_rqu9DS2K)>=Rc=bQ'
    'LJ{@^f;xErnv{kme#0y!Xx&(ek|`reb}`<zDOJPOc76D)wE1KjNOCM=aK`ju>C;dokHW#F8)}DZcl3s&RBs4lSL*}9(?025)flIS'
    '0cqrdNDyHX^3TbVuYPZOIPO5VdqsSt-nC?h)WW^|3`Q90T&YlDTZ|Q*Ch~Hx%-8PdTz-;Iz1(Y9Kmm#eWrEAj>?^sKU_k>pIcpSe'
    'tH#$rwS~kAq2zG$c24b_UH$b&?@g|od`#d@S=Su1CZ(OE+5svAvtzWb@#)5$Exm!-J!#fpFNGJqIfM>mWVBYGEKrSh0>sHAr}4va'
    'J*)O~`1*2G!dQQw0G$$$jO<#WcD1-H(d^;og*b!?iedxJ2gPgkzRnw2KJCM6#0)Qsk@OMX0x8_~a&p4$m4I2OgBWDS+PH>7H$iwy'
    '-x=_w%kqw!=UaBP^S_fcQKb?#;TAu|f)R!cmC(7ON5h;S?wkC^2<6~mQ5smp$J{Mz5~dIK^wS>|Q%fd_@}?%4*yCh`K?X<*PD}75'
    'F{)YIetC*eSnGF`u>DSVYQ>XF{%d}D8I7U>f<oB<DoDpeK9Us@K*lD(Z?EeQ>y8gCS3cX!x!-+$GUvZL*YlURBK=(EE@K`QQ|Ck>'
    'Wdvx4DGLb*3>^B;P-|Dvoj=)1G4<zy0AYbyEu9Z_a`0-RLd+Kn+{$MS#(r0Su8z(FQJx9L%YPQR_fTNAYJ3D<i#&}%&Un!9K*X{L'
    '0U9$-d4`(+)0A%6Md?WpQJ6y@w>dsd#C1vI(yRuRU=WGfE7U}Ma+>-y`t)f&ZFPXr(}BJ{xE~AYx}Y%=k5~h^F_h~?>7`;Gz?~o`'
    'P(lN|_tfqy$WW(!AmwxWv(?>6MN+Ddk$XYFR1^Ww$Z~`M(}n;=b07X3bnk{KQhD7ru;$+EowC5qz5ZJ2qs#ObMNL$yj9C*x35aXC'
    '5njvC0QxhGsV4iG*6)J<{#dYLlefsIxd3o>0WM&Mc)=92t{V8W$bRWGxM5hg_~{ksGpKqGuqwbAF`<LBh_wmcq_m@8fx~0OL0#Hh'
    'h7fiu^l@jImGm>`ny#$nffS3-7&C0xubyd{FuiGu2ND<RT>cdHI|RbsuiL~K_I&*i3J!D>+DXW-jGh@Cl10m-;Ko-*bSpq<xC3Td'
    '`90Ei!s)3_8fY{fCDMw6a))OYbu0wxR!v^KXLv^=YIFvMrFA=iP~w(}llA-n#Kw>T3C)~H87k6y=Wa)&LY&lq35@+eG@ZM+jYX1D'
    'mV$UA{Q)i(2z3Ts6A+N8sR`a-AT1+4@V<<>U-=r&A^P1TsIpMQ%c7Asbkby9g-1rTEy6M|4=9`BN5e((E8hq`El;S_2`wy-1{^9s'
    ')?ccy0O<fanE6GAHi%NgZHnmyZe8n^f7z1h9gl^N5iJ|P4$pYqm%w23iwt^DoGYNPh}0Vd*tK!>+J`^3rS7yQ<cb7JSs-OB_7Gz1'
    'YAO?z9%dsz-$q*K>b2!gf1))#%DO~z3zDz#oa!)HvM^tTu9Lt3aCdZPoH&mFLs)Jb%~0s=jXNo7gP5d-3BY7w;L3v>CtXd1g)+q0'
    'sKt8=C0XwL`fX_SGuNw<TEUQ?8HE(;MooAIvcdU|`$9$uvH)v^FM~X-csY^;-HFHj<EK;tpS(o$S|H{k9}d4i&c~!p>3_*+q9%z!'
    ')g_Q}YT!Ac)E&C(clG;jyXYzwjmIWGxch=Fvs%xz$i*ItQVPf|Nf*6AB~0!mI~ayw+3R<7(uKnIpv=85P07JhFKe(eE`Nk9kR?3D'
    'vJ@~PebZIbOa{ij&)07U*5VEY@%imBdm-<kHWZ*7I(l-+Yg_3|@DZcC$7RPHwn^hMq+;#yCMgw6NdWsYs>#v5`m-=53h#<m0klOP'
    'G~%(s8-dKhHv>HfG^x>yRa=5Z)1TCdOE134f>6qA;fzbi8OuXFrU|gk=$34oWeKpLA8qxj9E(CW!6}SB7)?NmQZTl%z&GMWahGyR'
    'DVg!@FO}-&7Sq2Nb>Y_etz>AEMU7P|f%73K0aQ$juS8^sCc*;P8O*ST_GBv8KcUS9gFsDJrLhGFHv^2w-JW^|Z>XqF1&<wxRcdnO'
    'if4tutD3f^*TysiG6F6sbS9VuqBUy=Wsm62)U^qA={FT~>DL|X_Q*Cs{fbk^MhzCApw_%(&E7;k3HQBUgbKI_F^-B6xW$a^ZP`Cg'
    '>Eezwsbp7<2OS+vMo%y)fX*vUbY5(GF$d@@CK5JA-okvXTpC9PPSRhGUQEs1<(H20!6YJ-#(f7#AzGQ>p%ek@glPggMNu8sZD0}d'
    '6oy?vb%Gm#Pm9w)5CN&3T<4-Z3JvT4hN9c1_K`0WmkUHxbc~c^8f*m&NRYyJQ$xq-qp*b@Q3z9Ci=u|@PKc=j^`FmSb9{L!d8<iv'
    '!<_|M3$Yv-SJIG9G}3Gb+j5PVLLC%}vRAFUAZvQM<#BRk`28Z0kTN1`Bn9~>XjPC@9l8+ax0+tm)U5jBDIhwCgsw_^8u95M00!7m'
    'RAiGTYO@}#D;;Laq7mC|OLAPX_}NeOWKXaun~!q?aU;;@ahh0dg^WS*<p|NiGZ`8ntr!V4YL*7n%|F)ta#rbuo;FN8;_?8V$|QOC'
    'o-?-#_2=^XhpuQZ@_TyvhQ0Y0ST*1<TpI<SJZ5Gv!a{SPpdTd-q7BOM@gacV5}BdNK`u&~UKc&h3D?L-FHTzC-WSULUQ=~|1EH3K'
    '`5^Kj2O#}Ws;$t8oB_*?P`Uc6efjH*X;Pv4RCwxm?=P;7s9l#wj4l{74BzZt?v9{z#81?MbLAEmBIov^u`PfszV;C8Asssrx`<?`'
    'GpH)y-zC1hM#V`{e)ziLxz$<qvT<gl(St}$qoKk0c-~2{2GkgAhp^nk+Vn&B=g(JO`Nj>}2Qp3oE`$Yn8H)<5mz%=%%2b97FA(RJ'
    'Y0VZYo;k`2Tn+e;(~@IyWuSAS01$f>i>i(p-a&qUg=HTZC+4cn)2I}AwOorG{sjC7oD3~`Dl#HEU9#$=hni`cmKNQ`7ukxuJb$SC'
    'eg89OVg@N5nHJV@^v;+8oW;dbG6-QBj-_Tz7c1t|iigD_`cPGuVysCs$_g)|(ZE;)1CM9qJ;SAeT*OFe^<+n1yYRD=yo_ilD4l5<'
    'h$%3uuQAAV2$Ce303Wg@Y9KB`=;KV0W%0J`(g`mLzVWXCwWntQd5LI=LQQBL$p{t9=mbq5|4v0t_}i)r*`>-a275R-`eTxY2}MjE'
    '<-`no6@n!84zv-lVZ}SFuUuJW#kS0?9^{X}AI)$Ip{!UkJ*7jK{K^-TBaG{>F>~#r3y<biY=gQ@a-iZfC;OsSBeTN-49+EUIAG7A'
    '*hbAsQ9a_?Kn-b%M7q~aoar;vjwOX{C*Y4;66_TL3t~+==d|w!_3{~Xte;OY*{@r7!DA_wp9|{ViIxl;FKibl#co*x@qu9$J4y^C'
    'mlzVXSh@DAs*sfI^0Hinj2zPBQhJvBdht%ARYBs&I6ib424Ps7DwoX<KMIan%sm9t24g26gYJ>z3|K1D{wL}6s8A8-f)!LQw~dPh'
    'llyitP-Xyi+V~op-3X7M$1<rzod9-u+D>+}q=2=b)2ZR|lwK$oFK6`N>7Zf2n6!VXnDP6QUoz@##$>~tp`;+io?Y$2zrQ?Q{)T$l'
    '8fx}6Ds>|*0)CSSdI#mTGGN4uO!HfY%Joh|$To*Z5QvKpm@bZ!^iz7r7DK0jdBC&8O{ByIC{A&M6d>2G`%1qpzgh#yPCx)gmIO;a'
    'B9t*;EmSZ>NYU1@YG=kpSiN#(q~gfZIe~SM_|Y9HhKx#E+TV;cf@zDK8&zX2`eDDVzuSE)^f8xaEf+ji^t1Fg9?>+u8ramr3=`*<'
    '(H>oGl+e8Of+C7TBZp)J*<5^x)$rNl1^^BxQjo$@ox{8CYS(*tIBu6YrI*V>MlZ>OR<t|`c!AYsweU566EGg*X4*Bj`g?jE{Fxog'
    '*C{^%v<Xc~zR-e{H3|wQ0kc$a*~6O)41%f|*r##_?;Mh=mS>z1=?z{y5Poq}l^?ATJit6|za$ifo*0uDDwjX|BIB(7aQs?810?pq'
    'lNLusbTV`$u}Y#oB|g)K!*#!h$c|K{a^XV&UMhe}VD{X#5fWyQ7b>2YonQyb0~lCTs0y27yJkV2aq-~7J5YxU_9BM*oE=(i3~zGs'
    '_9tv1sRL)@I-IN56_W}quL7V3Hk4YIau_Ij6apcqVImj~7094aW3#j$YNPa<d(k^1s>?qeHAEOj&GO(V^CctH2OS4G<s0Wy#~DLT'
    'u(fya39|(x{{heOTOord7~)qZZWhpk=2ekXGOs)nWY~^)llVW>=F;bW%#vTFg6y@Ep&+@(Ajdx%R@C0Ib6p6UhzN<I6pX31WH~jt'
    'FaK7aDfXZl*C8e%QF98XW(+4O01sFB1^`e$#8oS9;LKdS4?$q@Rm8zu(|H+L!DYenFlDVOf6Vj-8h6Oc)~$NVc(#XKg`SroL8!m^'
    'iB{67QH&n-1!gKJE)!)YT+Obn{@qxYoz}mc`QUy>35ZJ>(oYW5a;g>q2l_r5w|wGE&kVI;<mGvR5?`K0Xeo3AAZGJeu_u-jA4yKn'
    '$);AI|DhfUNNQGWsl6#q9-4I}1E-X^UM)1TCA*A}p)uNsqO-`YsAcdSPL^|RxpFd$l#%G(Rk&+29Z4)=zGKZ2Scu}>&4Xr>NQ7Y)'
    'T4pR|2B-p`{@kD5@RtpL#oByRAkEC;?$K^WuQ-gL4VbxN<27m|i^?Tx7}SGi&BCvfs?H-vE`Mshth(`~<EDat&d&u2kk>({K^C3H'
    'gA>QCUA6w%slU#;UM5*Qd5P~}lF{KDnb9NatI>2(^0I(F+Z5gUe%iqqk$8}o`5x;R(1L<TC%!im;xZZ{Sl_{uhDfDP!f134Okof='
    'KNPtMKkcDvVIDK>eJ`*LZ4Esqs9GFswOHv9;TR;F<2H1w7uLUBpoU<q0iH?50*jFn852?<UD{JfBd`Dx!H~H)r90#_Kc?zalXVW$'
    'eltKRM~N>EArUfE>YX&pb9;dOEb4k;#pmraLX=V>M(HHX#cOJ0rvU{^`Ok0+@)8eKQElY1&Cy3=E8kyG;*Fq6plRB<wiP=g%H)xb'
    'In^*3HUK8jbg>B_6nN!iLZD#rvSB)b7Q(`i8BoxX)m#aYmZ5(6;-NWtH!NpmAqJfKO$A*Ks3cb0)QV)C{CdXGGy8!U2KSK=4M<O<'
    'G)2GR11;)D_coC6?)7KC+5S}zO+?%6WRalJUY*9;f`Z^AW0?r45d?ii&f?2#*qRO13{^zIj6*8|I;wfpM5Bf_Q1_7*gD2xpqVWXq'
    'W$aDcsryJg!=jkUj2I0LiJJQ$ZfN(6WGOA1(jC(lb=H@6vW$OxcH6={LKB%ZMx$Sas8uAOHh{yOnAypE98uBWeieOV&RYRrSM6Kl'
    'o6F!q<{sbzjYlm*9=S{qG&MpPytGx&mWe~X3v~-0Rrw;eXDEf9La{WV?d#<e>?Hc9B|S;>k3^5jEPR@?qz!SbUVD+?p04(^-!G#m'
    'Xcm?%OtHa+FytZBV6P%_hg8#;t5F5>zyY2~x=_Qe*u+W-(+tRr{eb38Qk)6x#+s{9<<bj+hVO=HXL;Vj`yKrLqRgu1=i9{4)J_Uk'
    'IbXqifZxY=FXTT;52=nh(*)KmzT)en2|SBcv~WOG!ZeaWa|GqJ2UbeAPyp_<V)b>OATm^f5QPI`B1|J&{24)^cqkM!8h0H46&V#&'
    'y5-@a=gqr;@%4j=VC4hXwi1FvE8~r8LJvKs295eGAqPYOV8F0;1LqX8Y8EPB1apsrv~K}Q2#G$^$|hw7aDQg{P*m==I2h}*E!5AW'
    ';sA`YsiBCb0YZWRrww$M?8|G4Lbr?|F>AL`KZ`X>bx*wE|Dslu=@1An5E<&OsO}7IKfQW1*X`hyrE|I5VdfUJ2pD%Hok*t`MJt>P'
    'dK)SU>}*<ffL#%-`P&xix}PWnusX3m!Qy26DHkBXFAy{fgFw@o6hYY(rR4v*`p*={#Q>#{dV`wCp@&JM0KpJNXpxcotAQjP5BME-'
    'Vi#`OMg`LnE|i%A)i${>&34{Cv?avacmo;@(O^O`aP4Gn+DG+hR>rGPea*tIut31!$;u#oRtilM51TOR;@nQFH=_xyo4S!-x*YIn'
    'V`ehitqEwHs7<WIYLnJ&M|C7mF7E8rdw|&Ul<v#oOYmBrztn72#xo2rVVW9wJY-l5BG9V06TncB1o7bp4)U@q-4}G>l_H_Kq!BX9'
    '4_Wk<B$HUIE1B$q>)+VKwISklx@OfBL6(^okwhc2-n7t9mYGc;Zs=JCsXxQ&ukv*Z)zfNWvSrBjowPL6jbp!D<J3K}gw_~c`o5aC'
    'bLBqX2E$f4oWliX6jHVtqiyBJ<CRX5Q$PZu%M9mDLqM%tyO~o@pY$TYN!n;y)xOXn97$a$W<b6Hn!!Hl4F*X78jW*y4hk)a)wTQ3'
    'aEGTQ!{VYUjvuAhK5DjMG>weTs6!WP+F?+No5!X59*X_pPxf-ku-Va5g#r&wR;H?<u#f{juZGGC&IO7@h>y@P_>#Z`MswX(Y8d1='
    '7zPbN#P1$2Jgzya&>#bIs4vXxjhe0vthhFGfzadZRqBL5+=4q!7X%hH2|e|kLM5#iE;_pBP>ra)`mi=?{4847Q~^I8;XDjA@IqL|'
    '2v+Eh;Bk%ouh)5nT2255_3Bq{rOq&m+kq)D=uu&$(xX8+J}bAC?Jw$m&Q2Wqc5SYmAGY^j`4(Qz7wRL-(1M@={DrTuS6h|Q2VjUO'
    '-wepmC`L9DBWP%dFuXR)x)<2@Br8-Uzni@0xNeJT4uT||W*W`F>LaFNU@=57OBzTNv#LiTe_gv3qBz6`_w@42XR_3SyIn5Kaifnw'
    'H;FV0@)6`w$l4qX+^JxDG>}W^leQtQeJISRefsDs`KgZu)vuTJDySrn9&Q6YEllO`JO}5dO)P%8Euy^ty7ar|#_~eem_aw1CMOBM'
    'Mw(#6N+%Dc5A@w02|qnG;yNCie(jNkK)#MS4y%)dr!f>h8XD3<*wgql?tFBMu$l-PqQmsp@1sZ>V?GD}!<ctWoIs(iNUvEwE=(|^'
    '77-^B+SuxQL|a&;m}uqm4Dyb_v(X>}JZX74qJ*N{^$BnnMj6%775iABpkNUY8QjK%i*<0>Av`mqs3CGriY49R{?mjjc2TKip!Y;S'
    'nLHSkAuR}o?ec#pQ)iW|m<}+V2=9;8RoY47w>eAxN+lW`s2TA-H7ckb;WRRAOWbE@=Cmk~M4CQ9U|hS0btG&GVLVre7Mx6OR;X`C'
    'EgL6}@Su@IP{8>(RzC=$!{R1%ZjqL!EaHd<^BT+q1d&V_m50D=ifM*3D7$g;hFg6=)=ZiYYDK|xl$R300S+2)GD=05+Z4*0INbGa'
    'b^3eW0cTVpv}))zjbg-U(9&s9!Y?73<KD$250rAUIg3<nv|a3V8+qO>A)T9T8@?4>Cjc;@)#@viY>qcTfeO+MtBayZGv~8NFw=D#'
    'S$GOHFQy@>#P=bQiQ}N8*>4_A!lW-#oSX#euBnS_qs5cf7q%$I2J!*?kPij)fX-s0se!N-xx3f^jdc7+7*}DW+ZD~vuRbd0zUsP$'
    'HtH(~A{46ubX6@}QSD(}v#&v;Nnt#a5t-q-y{v6*W0VNwY(zF}upvNlM;ip0T9PFOXL^vYw;la;yE$=bsx|^A3{n!88eDKNjcx&f'
    'm$_=Ae6;CJ8S&v)zoJESdd|-)#iyVP6pETos`1J&P5sb|3kh@Far5HA#nT!5+Enm)8+LCyDTh^gMUsZGjtI7h+0a+>fQ)#*t)vQg'
    'xiZ(yU9*eRd$~_LEObibPzD*pd%@s@!5jD{!Q_&X48o20<>Vhy(v^oye7KEsIKjO`qa3zRCCr7nI^3-^q)3H=)Dqk`e7KDML52i9'
    '1ThC~Jag3}c|FT3$T9RP@a#ZGksA#vBc4(`bw(aXCMOFAy#YI4owqOBc}JqHhDhPOQA|=)lLOH-qm3814;e1O<%{-`{RP<$UA3K8'
    'M{`Q-`x@EQC<=n8+thPCEC5EP5Kt)hRe^&M(cz}G=dL<KXNGU>b1|BT;u;L}P(sko<T?fdiV{Rp1oP3z*0;%PFXg}PA4vx4a5}66'
    'sb|@X>;r*f5TR&7B-(3PX27ij$c0(8HgDwZ__Sczs`D5NT`VSa^#BOLg29UiE=a(Y4B-=0Y)H>|M?m{xtj^S}-$=wu^zC8rs_wUo'
    '(?F5^!-?rNtzeP}9sVS54Z<w?RX_=PgFy<kaag+{{>w4)T+;;ucp#C4fv-L!q#bRHVX!<77{fu+G%>^>-mKk7J#kngu^oM1QSS+J'
    'IQGJSgI2RxB|*6CNw85Ptc`NubZ3|Oz%+NqRDi-R6h=730@M+DAiMyik<CU2sTDb<f<M~vmAkk=?ft3D<ffT*%k~2FX?BdNF=krx'
    't*ovQ1<K7OuRSQLZ#f>CL|K~5fMz^GULs;7nU88x27dP%`-bHvDG4*gVdhP15s)*>c5{}#%KfKM+CbXoTb$&N1wz@0fCy*BXfQVz'
    '04B<670)ZTaaQra?xsl4p@(4Lt@WMwhT>yzr(l>shT>3H(<lVk22XF-ZvzKi>AT4fPj%Miu!XP<)}CfbLVcAtI}DmZ1ME4ou$RE+'
    'IJCps!+GK%Kc_-y@Qh)n+b2`3hWT2=O}N0=KaINOco)ET^krjr)#`OD=t+Pn6JjlShny6#%ovFU^vppg>4LJqi4=bAdsuACP8KCK'
    'P`1c9nGX@?AADz+Sx3e`Yg5#ER#QKrpNqCp+Qqtv<YfWOB!$EqcABe<Di{@I2WN)r01_LeEqs;Is&C#IZ<o}0zEEN0krUe<Q9rg('
    'j;<2DELzeAeu^Yvi0^~$ZeP86g-aZV8%7Wu%8^0KKzn-eNN9NakirLSG)Sy+DzbC_G7G7Xe$3SzpgJ^I>60Xl94|8eo<=u}R{UtJ'
    '_}F7A+Welw%xCxRPu>ws_ye|yQ16)gV!2@vfCWv6r>TsN6=gcz=V7W_u{y9}gNPG0O)>f~cpY)sM11fVl|jM9WgkSICF~Y|=yHbZ'
    'a=;ckHzQi6u44x74AB`q&@zRC?-%kJ!{KD&Hdn2vm{q4FK;RCqj9bKmrIT%v^bM?pL99kZ!Dg_uU;3gL`Q5TLk%9p*Nq&!m2Ki8*'
    ';1SG_RDISUKuF$U)PQ;vttQ{C3MW~8=mPzjOVNouZ)7RS&^A6NbWg;HMss1XR$_Kfv1Wa@YUK@qCdG7k3OV^?(P2gw&;tjftjA`Z'
    '5eJ|dj94k+!hc)1Vull3UF>CWk`0q4tq!n<pkz3Zf}TQo;tinf2SE62=~FF!_da32JC^3nlNXZ(X+$SR6(C1eGr7UBg02C4xQWv}'
    'UFA=2L~6>s+dryjh%CfC{P>T8{s@?WIr0>84UwO2r3TwG=^CnoQP5bN--gevY~QbUW=#qKDVg}=8Y-0uKK>J6HlBM#1#(}~5RzoP'
    'g;j57T-jDEd&c|AYpWy4T*joMgN~5)i){OQW;5eZmJ?VryWqoGyY?%%U9kml4tV0w@Th|5d&we|Nt$v?K#-jz%t)G4{pnXt)pOJy'
    '?kEp4V`=~K`(gKV;TMB{!pDVaq~Rn8`eymeBVrWo4B!hLVTLFAX^z7xzeCEnTiTqUY#)Ed@9&-_OHBp4ih))@O5JiNFnNQ4bx^EO'
    'yS0KyKj-9Y4(NHh_Tf&$H~(?`^LS~-kexxyXz@m#AYuecZqn&NW`_8Kp(`SC*w3YGguuJkANjE$<Nc2lVRF(GXk1)4s-&q*ci=_R'
    'qrleAsf_F8)qQC-@u~H9cMH~D=t`j#hvb3XH1z_VN@gHJ+oN)zP1wVA2V=k`{?oeYKwfnRpF_QcbK%OLY|ekOc{44zoWArLU<{=N'
    '`%An;7|#aBff<bCF5)@>!NAAipMAE8x8J*0Uv^&(gs7{j2qu7YBY_Xe3ch&=_dAAK@a&z;s2H&K(HEqa>lg37@twZ?$3oDRqddc7'
    'sQ{>k93o64`y-4dTrdKW-$;l%cNJ@$hHD=G_wIkChb12TPj~!Uz+kyp;pg-HPzVW&^*WW&Ed%ickn^_3j|<Y%>NH8h*Sj-212N+6'
    'xh%iLf)JhvidqE)3n3wB`W1fB#CxW3AVfs@`XTxAqczWeEf9r}n?|Mp>HRS{05urAhdlIhFr%#n0^P~Mudw7P%m1=4=nB)fnVJe`'
    'jtkDp=Lm75BWZyuhE_@bCJ0jCoW{EKB1!P&54K%S2bCgTZP3$b-{T30h8vwHvN3%78&N+#q@;bY-u(-66blT+c6REDf;Vzqk_jS1'
    'gLOvt4~YdP7sLj*vvb{g7^EFbLq`XVO2Y7uAH-;LILka=jp?9(BomZ%tp>t|Pmg5S-kppN4qv`*Gv?;tcBi>*&$~i2zzGgXD!z)?'
    '#-dUN^OheRAqh+#OcACsK?$^?Vri{a=0q^so|$kMcgr6Xs}39%0cDWp(!6S&6ik?<_8;n}{<h$L0g_9`*b)~8$j6O*OE6PLjSCGI'
    'F)Ze=6mGC$8>B5ws#x*mxya0?G;ATD1A5M)y3m#*u6Jtfvk5#DuqC6Cnm#>^G09*Xdh-twTu%Q%Ze7JQ*~$G283d^hGf@Fn1_UbH'
    'D^R_ANzG9J^JdMeRT-PGE!0e2uIzLqkc_e<w+1D6D;o{XW`ftjB)Q%+Y1OjD3oJ;+Pu~hsbrN?40|f^KOtwk@t)rN6n%ZI3EPATN'
    'FW)ApjRgD4&6nX299TFkRE!{L2#-m8;jPl=Y(85S-q780JnsJa0?d)Orvc3sFPC&48YXVt0KM`;kuxfM4b(1FjB>7&&LMpMls{X!'
    'h9-h=fg6R0K%B*L4{iv?FQkF;Ns;0O+hyFV?CM|rwG^1Jt0H%hn!`(4Inc}|RYG)w${$v0$Dc!!@cr6_E9TY;q?Fl<=I3I$2bxbw'
    '3d&C&j9Pdy0DFu*{tz=fEqyq=q&o;OWG{<-<MYv#<O)56XTBirRDLxiEh`5BK5ZU2iCK>eS|jh{xoXYw9Y?zWI(6qpj2RFHI8ELW'
    '%0bP_)e59zxq!%ptCp*|;(%P?V=}>oY3ms~UE&pI3H<|o6OaH;pJ>EYXsTTBSjs%1_MwjDHKN9mt3R_)d6qb?=@j!c=_3k^{q!B4'
    'F@{r)U6B*9cWxCf81C>a8*<D|068f0iT`wQ;fGLZbXChebA3|`7KSU>Meheq3z<BldgXA@@b}D(!U$a9*T^_`s#@_QcYvSbJab+q'
    'egQOW#shLbAmSUrfStIMQX*zy%D!r`(<q<<2@0vytYOWVJ`XS{K(oQ{scm6SpeaL$3rB7E^fa8~`s-h7=K6^=jmAP)>MYJImpB~?'
    'tQSC8DawTRvKKdfz9jk2R`K+1`CJaK<{<^E7&EE0&6}ew!Dqrl<cIUWFc4zb$T)^icU-+{c^pR8JU-FIk#IsgAn{}>w-?$A947;2'
    'HE)|StY4a@e%$5D9Cj3=8aORyEjol6{Dy~qON1c0^Pv&k{i3R_Umcm?9|utmpI-_bP=<^VX(9IEE#2XF6{!k&y%7IM&}axL(6=jo'
    'cR4%|Zm>l~TO<lF_b3-89b4v6fQI30fbdBE3Sq^s4XpFef)xxLG^S=!N{B$wNgyhUC%y%MIE-Z`?;VMZs~0`X#tVa+U_pQ;Bi2y0'
    'M8e?J4?>YA@)H)S+%Y6G^IX5UGKR`AVl-Nj=ZZhWEk`2JYD!T;0og;$>le`~9ym7EFAnxdXXxlo!md9H2`b6hv@pAMjV~Tl2@Dju'
    'I#mIodC{Xze#LKpdVbW(2WF=hX4zr*;~I@_6A_PLU1Fhm*(7o=K!fA$13qxZ>eoKsMki@qA#suu0Z7Y?NCb~Dnqs54D5wpwAO)`E'
    'v4A_}712z8zIjX7w<YduFD!sm3K|T@TO`aLdj^~-tqMN;*O1qlKGm-;f6DwoV0jI0cMD7N%Q?io{^^&KIQPprUD%$*s@u9Y8w396'
    '&L_xS(44H&dk!cwu3Ew)-f%opYO36i|NYzktKnR^^#QaQjVov#91HkIUQi+!4IK~o%D8n<GI5Eu6<a^KV15!zf3lG$W2B#JK)m&O'
    '@nB-&3EB=M=hF9T;1w6hRP%{TWrR+1={Qu>VM$KgoF6JoFbigLI$A9bH5%es&KX9&mSa|PuB*W|`W4(o4P$gkykvGwIiYcEWMc9Q'
    '#Ckf(;`Y-Zt{I$(0SuP|CceC={W?ju0SW;OBp8CAI>J$b&=y4HrFHaag?Vxly7MB2xP8s<!mE@{BkVOd0mM?|kXx!ZHfq8%$dkzU'
    'bWlFc&ky^1zbXB!K||8T`d~B-uJ}X&67+_q4Ywlq4=rX498&w~!II$W?gXwU%yGZOZC-{a9=C-KCy6UvCS1_a_{d=r*`$oYXk!RM'
    '0HY<r1BSM>3m20)&6E&F6-OTMW$e#rX&UU(>33<YE#gUW7SmL_;7>L4<vJv2?DWJ>n=vbg`#~m|G<qpWmN#k$5}#@qYF948KX6cy'
    'P<a{9&_G3{N=YJXAo}NoenjQSLqUT-z1)|zUM*+7xTSega4ChiMQz1^HgV~#BpGDON$4<92e~?m4g8lr|5$%slGys%UAzplBZ`M8'
    '1vMGZtqF~mraxk}fd!4IAJj!^!i{x{zA2C|pGpvqMpMkeyK$Bg30tO>VEusMc#ug`iO-X(TeAjg0R<*j(-Hxwgzg+<mSJRznwCjB'
    '^p4@~c~iHb5a>rmyMjyrlecAx0iUc!tB#s1W#!f=GA}84o72Z!_>b0Hc*Hf0H+qAVIea{rxS>UuC90<l#n%JS!<~icEj*^&uUoe;'
    'I021;<~Q*LClu@e9ypRrJW(_vsA)*e2@`%;w<H|p?d1|nI!nwqsipNaXK`GBP0{g_l}Qb2HKejjE0=xEY6?bG@b~rkU}r0;I8MTt'
    'WHSSW7C>Nx6Kr;k-L5<~MPLNkH*<=xziQRXkeU(<FUwE2hnuc>Xi(6MuU@T47y=+b!)m1K<&jcf41w$sQW$&>@xL_ehPlDrsue$)'
    '-19T!j=i`B^)OZt)U}1v*ND5xbWuhnL$yPv$0M#hrU%kbzq>r6lERdsfs^QE`hb@<0^Dj*o1uj1o*^Z2b6&OLrieNt7-BRM<uPzO'
    '<DqEb5Poq=A<e}?2Ph9%cK&!sWntMWwkqWz$Orx?q+`TEI;|?AkWxb>k5MD1F@5ho?^u7l{Gz!iu+XSCfcO9s@p@E`8t`3CqqNKk'
    'R-=Lxe>$vN_oQgJoG1b4;pql_b0j`76$$tWuM;#<)Nq=3t><Ce%F}vEL*a0q^+=bq`KDjI&Yf~Yz&?T_vI(kG%0vuLnLTD0Rh26b'
    'QZf2#@&>(ws5nSOV895U7ZY>%x`5qDdB;Ud__q)Gzy8Pn0h}xyTm'
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
        # tuple, exactly as shipping_context overlays the reviewed templates.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1'}
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
        reviewed=bool(matches)
        if not reviewed:
            # This choice is only for testing refusal, never an alias proof.
            matches=[name for name,row in policy['targets'].items()
                     if row['profile']==source['tests/platform-profile.json']]
        self.assertTrue(matches,'actual source platform must match a protected target profile')
        target='main' if 'main' in matches else matches[0]
        # Equal namespace aliases (Android main/VR) must also share the complete
        # native reader proof, rather than choosing among incompatible variants.
        if reviewed:
            self.assertTrue(all(policy['targets'][name]==policy['targets'][target] for name in matches))
        else:
            self.assertNotEqual(lookup,policy['targets'][target]['lookup_digest'])
        return target,self.trusted_main_projection(root,raw,source)

    def assert_unreviewed_namespace_refused(self, registry, raw, base, candidate, trusted, target):
        # Choosing the owning profile does not certify a feature branch's new
        # import membership. Such a source must refuse dependency omissions.
        if inputs.affected_lookup_digest(base)==json.loads(raw)['targets'][target]['lookup_digest']:
            return False
        with self.assertRaisesRegex(inputs.InputError,'lookup membership is not reviewed'):
            inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        return True

    def test_shipping_manifest_is_complete_and_backward_compatible_registry_is_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        registry=inputs.load_registry(root/'.github/test-suites.json')
        raw=inputs.load_dependencies(root/inputs.AFFECTED_POLICY,registry)
        manifest=json.loads(raw)
        self.assertEqual(len(manifest['suites']),60)
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
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
        if future is None:
            future=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[future] if endpoint in tree else previous_rows
        matches=[row for row in approved if row is not None and all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:previous=matches[0]
        enrolled22=any(row['name']=='protected-producer-original-default-v1' for row in generations)
        codeql=blob((root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())['sha'] \
            if endpoint in tree and enrolled22 else '3a273057a38255ca368d3028594fb94227ba7c3b' if endpoint in tree \
            else '6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        self.assertEqual(tree['.github/workflows/codeql.yml']['sha'],codeql)
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete prospective installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
        templates={
            '.github/workflows/project-tests.yml':'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml':'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml':'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/pr-metadata-context.yml':'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml',
            '.github/workflows/sync-validation.yml':'tools/repository-checks/workflows/sync-ci-selection.yml',
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
        }
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            expected=blob((root/template).read_bytes())
            if future is not None:self.assertEqual(future[path],expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=blob(
            (root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())
        if future is not None and tree['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE:
            # Source13 keeps all original owners. Only the installed Android S
            # fixture applies the separately reviewed exact six-file handoff.
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            targets={path for group in ('legacy_workflows','source_contracts') for path in owner[group]}
            self.assertEqual(targets,{'.github/workflows/android-tests.yml','.github/workflows/android-vr-tests.yml',
                'android/common/tests/android-workflow-contract-test.py',
                'android/common/tests/ci/validate_ci_contract.py','android/common/tests/ci/test_ci_contract.py',
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

    def test_shipping_controller_delta_respects_device_certificate_without_running_any_suite(self):
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
        if self.assert_unreviewed_namespace_refused(registry,raw,base,candidate,trusted,target):
            return
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
        if inputs.device_reader_digest(base,native['native_independent_paths']) != json.loads(raw)['targets'][target]['reader_digest']:
            # Feature branches legitimately change native components before a
            # new reader certificate is reviewed. Test the required conservative
            # decision; never rewrite that certificate to make an omission pass.
            self.assertIn('device-control-plane-full',plan['required'])
            self.assertNotIn('device-control-plane-full',plan['omitted'])
            self.assertEqual(plan['reasons']['device-control-plane-full'],
                             'product-component-or-reader-not-reviewed')
            self.assertEqual(plan['required_setup'],['host-full'])
            self.assertFalse(plan['reusable'])
            return
        self.assertEqual(inputs.device_reader_digest(base,native['native_independent_paths']),
                         json.loads(raw)['targets'][target]['reader_digest'])
        self.assertIn('device-control-plane-full',plan['omitted'])
        self.assertLess(len(plan['required']),60)
        self.assertIn('attested-runtime',plan['required'])
        self.assertIn('test-evidence',plan['required'])
        self.assertEqual(plan['required_setup'],['host-full'])
        spec=importlib.util.spec_from_file_location('affected_host_policy',root/'tools/repository-checks/host_selection.py')
        host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
        selected=host.select(candidate,plan['paths'],True,trusted_tree=trusted,base_tree=base,target=target)
        self.assertEqual(selected['reason'],'protected-affected-dependencies')
        self.assertEqual(selected['suites'],plan['required'])
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['include_platform'],base['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE)
        self.assertFalse(selected['affected']['reusable'])

    def test_native_feature_source_cannot_inherit_shipping_device_omission(self):
        root,registry,raw,base=self.shipping_context()
        target,trusted=self.target_context(root,raw,base)
        path='libraries/shared/src/EmbeddedWebPolicy.h'
        self.assertIn(path,base)
        certificate=json.loads(raw)['targets'][target]['reader_digest']
        for already_in_base in (False,True):
            with self.subTest(native_feature_already_in_base=already_in_base):
                previous=deepcopy(base)
                candidate=deepcopy(base)
                changed=blob(b'changed native feature source for certificate regression')
                if already_in_base:
                    previous[path]=changed
                candidate[path]=changed
                for name in ('attested.py','postmerge.py','producer_workflow.py','sandbox.py','sandbox_host.py'):
                    candidate['tools/test-evidence/'+name]=blob(('changed '+name).encode())
                if self.assert_unreviewed_namespace_refused(registry,raw,previous,candidate,trusted,target):
                    continue
                plan=inputs.plan_affected(registry,raw,previous,candidate,trusted,target=target)
                self.assertIn('device-control-plane-full',plan['required'])
                self.assertNotIn('device-control-plane-full',plan['omitted'])
                self.assertEqual(plan['reasons']['device-control-plane-full'],
                                 'product-component-or-reader-not-reviewed')
                self.assertEqual(plan['required_setup'],['host-full'])
                self.assertFalse(plan['reusable'])
                self.assertEqual(json.loads(raw)['targets'][target]['reader_digest'],certificate)

    def test_preinstallation_source_cannot_inherit_the_prospective_native_omissions(self):
        root,registry,raw,base=self.source_context()
        self.assertNotIn('.github/workflows/pr-metadata-context.yml',base)
        candidate=deepcopy(base)
        candidate['tools/test-evidence/sandbox_host.py']=blob(b'changed preinstallation controller')
        target,trusted=self.target_context(root,raw,base)
        if self.assert_unreviewed_namespace_refused(registry,raw,base,candidate,trusted,target):
            return
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
        # Apple retains two additional audio Python readers and a changed mute
        # caller. Their genuine import variant must keep this extra owner.
        if 'recorded-voice-qml' in plan['required']:
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unreviewed-import-or-missing-required-input')
            self.assertEqual(len(plan['required']),33)
        else:
            self.assertIn('recorded-voice-qml',plan['omitted'])
            self.assertEqual(plan['reasons']['recorded-voice-qml'],'unchanged-reviewed-dependencies')
            self.assertEqual(len(plan['required']),32)
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
        before=SimpleNamespace(entries=tuple(entry for entry in snapshot.entries if entry.path not in paths))
        self.assertEqual(len(before.entries)+len(paths),len(snapshot.entries))
        app=ios._boundary(before)
        own_host=host.ci_host_boundary(before)
        self.assertIsNotNone(app)
        self.assertIsNotNone(own_host)
        self.assertEqual(ios._boundary(snapshot),app)
        self.assertEqual(host.ci_host_boundary(snapshot),own_host)
        changed=SimpleNamespace(entries=tuple(ios.Entry(entry.path,entry.mode,entry.object_type,'f'*40)
            if entry.path in paths else entry for entry in snapshot.entries))
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
