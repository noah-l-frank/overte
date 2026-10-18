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
# 4fb5f1fab0cd025f7e3a8a8b28e7b2dc001ce488 / tree 75b32b2a3a5acd8b3a090e75e5c9ff1930fde9a4.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '5dd54b15368d33ffb817d82c5074c4f31a48bff02b137a328ba658e2479ab4a3'
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
    'c-qaK-F72MlAQ1L7=68*%E*lT+o#ac(LGN5vd~2m9008D+CBU3`YZvmS<@sU5~!85(yFJcTN8oINDp^&GxPua?H~8s<JTAe#XZIS'
    'ZX54*e>|oA-Er@p4ms`r@%v%-^xMDx=Wma@n11{B-%QgC*8cWyza73h{<du!!~gWAoq`Gcr^bvqr_RUF4^5a%Zn_+e;s3+&$Fu$m'
    '{KL-w_Fw<@wybBN@b&I__pl8=3afeF@!vJ1VIG_4QkaHu3_dl@*yL{TvB~3LT{C^Y+OrGa+<m(HW4Hg7A9jD--6wvnJ8pMRhr;4+'
    '?B=QMr*SlXGInn4Y`SQ>K0D{T(M{G5O|tFhi|^C(?yx=X_CM~z*A%{$R_ucv+stzv&6H!DQ%ZC0ZEkFw`JwaVy4EIdKVR{f4#&I0'
    '%l4S=VtP(bF+GKCDy{3Ab_k{)e2V<$aT<Kr<Z0@x>wWZ-HNNGA`=Mst(pquo{oH096aE`r>s+74nG<BEd5CTpjP-{1`uSR~ukygl'
    '-KVGH-9KO4!!~cj@>c)x<MHA1)n}i>kf*WjyvhA++adE(dFp<g+Gd!nbz|m;SFOI^{hq?{PQU$dd09S|u64b0HiVqU-W%H+8_np<'
    '92zr3-g$1*T(j)o57ot`O&^V)gPWuEJ@3?n*ypKjhm=FK<1m>RyEM7KFYWg%M`Q>OTb}Zlu>JCTdiu6~I()fzde6^4F05)?us(#='
    'TWd$(+9?j9HDjM*Kk?ghpUgNm?V44e`Q^Ou%j?=acFDRlPMvSU*v5&I>^%p|=XT7^I5jDSux{O*zr1R8d29m5$Yg$B+sv+MyRq{&'
    '%xSV=%r3Z|N55v({mawEHG{FkFvRR;Z>N!;=jLu`=E?Xj`PACzn=$3QYE7NwP58RsJ*Lee?4B?G>Z!L)!;^KU8-_5YkY?9+ZfyE?'
    'B6js5&T%s9p7pYWC-;~R1n#uiC-=O4y1%%M$VbaZo%+ENHIuQaGjq#_90<>Y>8&NCa8<3}#`EJQ?4I)W^7?$kX_&fx;8SwTwK#Nb'
    '(-YgKKE}3Tb0d4~R<EynId1;^p8du3J?E^kHun9<CDAuLiQdgkXt^OdksVK=;eK|j*XIOsRbE^>h1^Z9ZzItxccTwuFy3^H<JJnU'
    'HB;>D&{X_(MU+3>k1tQ@s7SZj?_Q2+6SwaEX?Hko!{unx&B41VS<{C;SziA<rR2Cen||myg3-5*lx1GMjhFa*ap86v2a`-26F15j'
    'XFYv(!eyFc%ZHG;>TDXv>V;1S@4WhwnCS=})1Sx70jTF=ACqglzMHx(X;b~2M&C!i#yJJk5FdtexP5Tsg~#3FHrx^RzHblQsC<B5'
    '+)LaZH|HBqx9r6)vhS0#v2{MBE)xx7wDWB3q?l-iUN3_uGhV%$<*U@k@!(#_B`-&*ap*#9<1ky^2N{MZZj#r{Ig{)(*_hOjY&F+!'
    '=7n_fa-@vGnJKixl$)O4?)uP<Tn&6Cq<j68dq-N?CUf;3zNP(Bde|&)>Ecf2*7HE(ID|No!)DvG*~fP1%{UKvNb@*ye%pNYP9EJ8'
    '>2}<Z<8zevKQ>>t2jwakch%_P8nT^ylLBF6Og)zww<x)S>DXa2TAtGNyV`mFrSFAcHUw2Jq4z{f>)UbU^t!HzU6{JW2_lXS`lr|L'
    ';`v;8xQFGd-n($T9N4C4r*^dMG_-jdi0XacjUi5MXgSucZRVKT$<J4BiJU4wZ12Awt7GjjcA1Q-aklqM{SyiEW}JvWdO)#jsM+%9'
    'Z`e{P-QofCl$y;rcTG36lWCQ8k!A5nX5L;ibtJlNym||y9g$$S{mzHId3!{cvjEPD^Ua*8-*^VyG)}~QKM;Jgr%KKy5PzEMAIss$'
    'cXj!&%p8qTOZ&N-Lf{h0Gv_w&phn8caqPRfzu_x7y8V5sz6CM~Z{tEF`^W=lB=KPzJN6usQBR24&&*A_{w<xd)z_=Q?_QpwD+C&j'
    '$;`naJ?FJFU>9zP{GWaZwl#jRjWg5<HvOVKRa{S9%4Y6oKg^x&(j5EH_)IxyILTAw7%Sq0+}yaM<&N4^g~8C1zqf`9lZ$a`lXEfo'
    'iIYv0<GQZvdur(Z*7ug4zHj%tr$_$9)2q8&*0sWUgc5Y#`#ua@5#9}n`Zc-9w>&d$^w{0Dr|MgDa&~kbRmBKoGJ(-VOLa>EMtSMU'
    'eFr{xc4U9ub~am*!28qfQOE?npEyu)Y(qmJ_Pi`V4`H6TEIRHqpK{A~Z`;~cx4a(#v`C0K<9QwvSx8WwIL)mI<RUiP&c!+WqOFD9'
    '<ARfv9@vmw>Shvo&^-dB-seQpO!#KE1K3ICo}Ie*Yj$-=-_ui}s-|R}L$4P|5lH}OcwSRuxIS8d8qm;=K<;kaPgNu!J+yNth#{st'
    'hk0<^xUL!a_yd5f8F-<FGWW)<yvvFnw>4*c20U~E7`oI^bB!^8sLjSZAOm&>(w0ngHs7|d^{El>&5<*LgY>==%#|B(2s5;nBR+If'
    '%MNXm{jK{VKiY(S0^2=q-NT`P4p4Gg+j7xPvnOrKnTMsEz<82f(*;lJ6z7}wRFe{PT>cy!{s*+k8N)YERt=;Na??!%1*&mlY}?y5'
    'b4B(>4(YQQ%rNkUQ8v3ill_l<wkA2lmD6$$nl{|FvBU0V52zJ(UlX`>xSY+gUTi3e98X3lTZ-L009DT_0dkll4=n&O-MA%Xm79tZ'
    '7KDj>4Y02rdn&W+xo28Xm)N!7_a+mbriL!buh>p@+lQ9|&^y^FB$s;E*xm&iCNwU3N6r#j9#iPLX{Lc<Zamk=$LG9#NN?5J<<EcQ'
    '(jPiUbp{+n#2kQScr2cLw-F>uXQ%Cl8&CIf|8h8TlYC1*_9bYPZ=U>;@7wxhIMXxlD9iw*jW-;sG-Vs7bW26BVl&FJo6d}2qU}6o'
    '-X0wfI$qW{d||=USewBj>aPDYNPYe%mv4*Mfd+CcKu5=(`+|bLA(QQm?@46AX!|KlQ(cCA|FVR;w13<l4oeU5Vlw9EnSO*C9eGMV'
    'f@#n!rA+j+nQWRu<03Jq?k9iU>Fw`!rGT#sntEb#^Js&mE!z^>sLv;E@Yt9L9LHx;x8^Brxg0v_V6}XB9qo^(EDGQ|82~O|lgynH'
    '>6wzv)a6f4T>jtF#>L0&<(q`g2FVBUkJjWc(ER|Fh?y>z>G;1L0GFj;s4NK1tJZ*tO~WNlS*8MM3@Hp0_LeUm6h!b*pj;yi)SadG'
    'Us83B5jvAvPmxc3sH&9?P_%tNk!$d=H*KWXH`dmR@B2M9pVCM(c(xr4Ls0&Hv?}n^O!iDKH*u_~rK!#0xMJ~BVH$S(wE3Ou@hM%d'
    'Arx8(X7oAipzh@`f-=vID)*UY)Igo;LaxN<-tXXX_dPAeC|6M7Dm37dW83D&Pn{EtOIkzHsk;$eY^G`-X*|rXeh=%SN(emhrsK12'
    'XnoP7r%o`rGtTj)B`%-@RUpj1e*MbOVq&ItoSbTHaFlW4ixc9;CqD5Z+KKQ^-rdzNe2Om>&zu^F_f9jn<@#z3U*SY9?K_&QEjKOz'
    'G0+M9&$UbcRl;7rLuh0-q&<$*RanT_lG#r@cmVx|*KNQ_NXYW_%b&Y_;rZqAbKtu(0jfeHC>mM_bp|)t07}d~M?Ya2X|&8&Y@}}e'
    'F84G!4Ot(}PLeOO)XewLwfw>4Ko^GA$7cNzAYos)9DE9He;Et%o}08)mz7&35c2w-J%t2QXEKT4IFV_@=&#;F-IEx3{;b!~^mdR9'
    'B7cQ#z{7Xc$BCPr<f<pnxMCYWj$e0Ab%3T0KSctd4&MXy6BMD;k2Fy%zzRJks$-s)z2af)(><6Dg-YD~v3JkUr7SCW_)#E)z3yaT'
    'U|f#Acl3m*$djQqATqcs4hF!|<tFSfP^S$n){D`i)*{egrrXwfg-9{fdfFtRe(CyzU>@D<I+05<&4?5mZX^r3Wl0WV@98p%0+UzV'
    'M^|M9^cQ-X-UH8{pX_19(d`UQP@rQcaOXl8x{7M(^vmzIPtPyMFTC}KGpp*34FB$rMB)vsMn!aSH}vXMrSjI7^B2hMDHVa%1c(54'
    'XC6!2S7b>)?S|FwQWWv&{l-*!Y}`?gt_&PGszlN>YLFHVlH*hazFx|b(NcTRCr&!G72xP+8!M4^GGBo5Cmu^Htbr>u#tEujGt&C('
    'J>)R@c@>nI<+6SyH(p+nRE@K#?389N5kVbrPc1g43DO&%C_ItT<;o>rp)tkE4e!D2A9wrB3;$jrYw24)1nx*WF5qEd2rB=8TIXpr'
    'CPNc56r+Uk+I^fV&$}~M;>%$l{$G<v${YK?Mko1vD<@8g3alm5EZ~`>x6>5qz8C}d)RJ<!0XzesobQ)s<DmSG(+%5s1rU~PUCw%~'
    'A6uw|ArMmuseHfG92WjWCLLxUB%c|=(UqH7NSvqB4Vly(s*g_`_+Ci^QwtQ;CT`;Z%Y?T^?d@XEACV;v74)m(zWmGfA)fG`TELaa'
    'HbDex-3$YW9#s<w0^>Le0RbbU-O`DlX>Q-#8MAx$*a|!pK07@xLPCJA2~yXn8%&b{M$XWR@nF(yZ{OIKHqid{rJhOWmyrefR4wee'
    'iEg=pmlKV;9UTqh7Cs&PLI~$(nt#F0p189fXnMFkt-i~rED@nSSTtR0Qa!M9q9<*BASDkqhMJeQ@zneN_FbKl9%9714(;Vj)jLRD'
    'Bj6(Mt|3rGKFBz8)HrdlZ9xS<{U?9>*4D(XNS?vj=itMiCw{jRO@9bZ3Z*oV)%BoWbHCuTJg4j1$EA{e@y}n~p}>xYG&vCF*<PTI'
    '6`DYX<N%Bz08rv`;n02v{ui9F(^XgnUyt-Ti4tHtp#?x3rv)<2$%kfWgGg#E53WhKZ|bnUU)T{_q##tj6(1!c42mi4LHeP|0^&~D'
    'PZJ*lt*bzy%L4;nP5%vhTQZ%Bw)>Q#nblr{{5o^?sD`PC5?E+Yi3l4hMbPJ8@DaQU0WNPR(?5m<3M5Nv12i-N3k~f+T`>1XfHeJ5'
    'ZiFkh^SXyG>#j=r{VYoFuZv!A)x^yNM;W37)GZHc0cvZ;tKZ_=u9l0kz`7B11v#7h&=IFBpCXAjI2O3BZ#xMUAU5Cpe9j^MGNjYB'
    'EyWU74i_?12oP5IEW~&q1fn{$@)@+#_P6e(;xj`OVnynMk}-lZ!rP_O?#YKyH-K&iM>a}7d%Sro=lbF2kF5{^8kI|Vq;ujt5PR1('
    'V}$gd`L{Y=m^vx|;J0pV#g+gC0epyx@U<)nl^1E1{Li3iqOX(uD0sZNP))||UIL=?&QhCRTM-K&>%y^&1!uZBxe0VbDQ%}PE1#Mh'
    '5Qw1z69*@!tU<`OW)GzzmMV=Rq@DVa@_>Q>MP4T^Gi{}a6oZ0tL`zoxyDJ+_^m`lB3^vn?hc471I+>~AAzP5LL7+BtA<X>I;pF;r'
    'Pq~Czq?QIhBrd0-nBG5VB0mh#Qh@a0IsMJRi~fkg8FztNoGjBleAz(Ne<#t}=${q(bu7yPM*r68K1&|_sz*`6>9RxT#S}+um@Y3X'
    '%Hd^9W{w%!IemdCkqDuxgh5Ni?WJAe%ya}idRg7&Wljmt@}CR6-nsL=U>2YIacH3oqJ<hM+B&*aiv9`FO#I+S3I0k?LdCzh{c($O'
    'ibQ!~x*Q7}a<cOX^A0qas{}btV*<URUTLvtm2IY7M7!+blFLaUG3W1#bT*?}fQCMV-vCFdfzKKnAh#h=xKE)+%}5OR=#Kr{f+u3g'
    '<#XbM?Dbs(OAWwxq|G=$fa1h=Gu1$Us*6M6_Z|H1ar2#9JC;)#V9c4Cy64jd90B8p`UO^#5l8~>dNRZ4<NQ(c`joB2^nI(hNPYKw'
    ')ao^fUL$b=G!g-peDFz&O{lsk^SLBF{P!l(^mL^~qkBF|JF`TXzpcpA`|G*#)EZtR+^7i@*E_mQ^sm7Z2%|`U;{<XFyS;A3!<(x5'
    'nWEtBk1q$dRvp#QOdMT$8i;lvuK=MNb}+&KZfLA@KDaA)@cg`edEC@&B#5m|Hz|!v8@EfyjU%yK$(dq3v|uO<u3x#4s)qnyW}v<1'
    'iMLin(Gf79g&aZt;o8B6$)R>YYPfdouzTQs*_~4OGwrc__B$)&-lJwiFie3)?N9RpcwJ0B1S#~GC$jvwb~g)Pytz*_+)FJ-h+a^P'
    '`4;Hr6V|NqF&GVYN=TON2$Bp2M^#q6h2<Pny$dJ>5xQ9>powbMTgX-!jZUlfKbR5k0Zgl{ei#3LyaPHHkA)>6*-oStFcO;}!M}?N'
    'fFq%nb~;t@2)lsRYgfBuOowlDuQt2z^0580>e&OUYH9jbKqmt!4>TT1aXKfng<cMq2?7(@$(38Ue}36~g&+Bl4h2|~o?@hUME6g-'
    'gl5079f=8$PN&{l3&)PPk(yty4@l8m?@-+fJR@2(L<NXra7c%o)%J@jnZ!k~$jMRHbe;J%8(ILSie|LH@Lsx&4*fpLdTuO=5>&`Y'
    '6_Q?I67Q-TuG|$D_a0`%Vf&50ef_(Oi5FE6)Rfth1I?r+fJ`GDSrnOZqT3ZEi>8IpUb&wW0^xo<5YSX3rR`@|?9Y&D1M!#asL4a$'
    't2-|Tf`pBSRsN3o0+n~_ul=l6?*}Uj0!KhQ(oQqA1S}d<5<Ig=4Ngc6B;VbKt|A}r=W!RlRejuUQV)lsdhF!+fWC&7ijk0Cny4(+'
    '0-1jfwF{rCMZbNDCH5tis+3^_vtZDrb4DS7LRgA}urot&MT8oL>hJk^8+P_f-u`(M>c4=Wm*bi=J0x`E5%eBa7K<)GIw{lx<d_<S'
    'tYe(kt^XHgs`^@?On0K2(maASram?GvhAP}!6l+MI*Q!~P_}L(ds(gQ>o<XniBd>5Iux`(bj|~=%IpS73?dnWw+x50`f2drDx$`U'
    'JKid#ic%p1g3TTZ5tl0IC+8DcMNV)Df}<q8atEh;r}}wF(Lt3fm<tgwMLd0Qh$H00`1~M->nx;}$yVR>-*^1&X0bF<wOWWyq*V>w'
    'yN(FpMPX}{^0O#m2|6hX9I*<^Yx~LtXFh%o9ds?MaQGlFXCc#by+xMgLjnus!a#9TS`fj^kN-$j(kpuIpbYxpxvqH8d6veh1#=j<'
    ';mPz2=r#R^(vpi5?X@m1=!9n}C}w)ZCeiP=O@c9nCxFbHCK|Z>CBRTB1)MsaG@U1KCj;OPx1v?Yn(7-75LrtAfA3G)?O<ycTYl;8'
    '+z!@%+?@UmGJ}VTwyQu>j&7u4#|C4B_#y)!%5@$-+$0WL3*jR+*KB9|q{c6t3;%-e)_(K+;$OKim-j@-=kf)_1)TuC3xGY5&fSC='
    '60P)6FrJ5-f770%ZbL7X9=MiD%r#6)q(vBj7l7`7r2=$re1cHl1JiW9*lX@1OQaS1dDp%nJ;>>}eY|{4aR<U+M?XT@i#k}h6%s(c'
    '4m!SkK+>3z|3-Jst{!+gbbC`NH1if3HR*BWny7gq4+@Vas3Cz?oCJ3O7T_V~nms%&?Lb-*r9I%yCG-V^2Y`w65j>9zn=^xH7W*L<'
    'L;Lmdnmx$ghdu0L#j{A<Oq~=@xSnxRfZJimz&XJZ0VzWqkTU>Cgz=hv&>B@W{`^7@zUpvLbI(-5C=K|up%}t!B<081gB{T>nzC-K'
    'VZQ2cEMU#%bZ?!$?91<`;cgzN2gzPxZ+U@aK)G<1paj4G3_3OGx~~UpezykzIPd14j}HY>9mx#x5(tRgCl~@z?^yi5sL~)U5%RfB'
    'Dca*N*oyw_GG>6q$}rNeP79|DKO!CrF$Q8R%<(bJ!nvn7T)!8wG7pZ!Qb2EnVuF4fX;Kh{46+P_Q9=pSk<m=}nm{i}>6(ok+~YHv'
    'w1fD;r`CRnxX<5!CsJYIaWIGETeAI3#X}3t_mBc%RC8$3Rk8mlWqPcr0IX^bV55<q_{h<qzd|3v0VKfGwV)gz^k9JgnoXRJM|hwR'
    'ySxYZW0HwPup^EM0yqiyN0472ADZQW>+tTz`p+hOb;nm3jXM^<74d{Yvc*xRyG*JLt^&}_%>o&f?^h;)*xl5Jvp18+vvm{@?$-iB'
    '03iW@E79*6;ajO~K)Vw50+JSNns^+7RHphMb|S%^ZkL^xT9Rg}h-&V+kR(C<gtkrkNz1(t6P+47FG!8lKqaP9lXtzZ|5g>l!;kQg'
    '&Usr1d?Cu;j$aoyfQMAB%cMhwk}x!cE-pLziGZMx1$6sB;-D7@GGN><+EazG7o-t<^bq08*^n@c^gjT5S^eou1r6W>!*Kc~8;V<8'
    '_l^a|dy9lU&`YDy>t*vbh-ek?^GvXZI9jl-vdXw$vZH<a=SwN(%hr;kLxjW63zJ7Bl{f<NL0PqLad3tE!iI0%(8KP2`&5Os47AC('
    '0+TLitS&j(pw*V_Uu;?IDY+r7I4`&E2=wD1jmA?*Rfh?5LkRBDN2FWI8=K8Qp+XPQN0JB$n7Ng1eo{0X-&E73J@I~cJJck!oUmXe'
    '9AVAsM7(U2;lc0Cq!cOMx~D@ra#P)d?LN8Z!`EG5SBQ2kTtSds`kjLuRrD4kxuzAvB8ngmMf;cS>gD-i=PpCdStvXOJXWHxdGP_E'
    '6oHtNAwJWI7E%wP$qwzUdphpErKdA(_HwcXhAUQVpk8r3**L;Oq7if)<WF;l;JwxM{M8$ZaW6D}pOXHKry@s?Ym2fG^$V02&^&mj'
    'lkDs;3xU%(*_JC7+RC-t;UB0`vH5yDK34@MLLz<BcHvdv)j%+?us$IqaKFH@#D!|WyVVT0Zs-v9+vl3ApRSh2+8J+>&{JQcQ6>2U'
    'gvBeA@*8&$sYod~Z`e?oW=fC5$bo>0GPY#KRI*gp*drj(!Z(u31rb&6um0fU?$Hsam+Rv%ukXw8+Hg)C${1L<%83??9APEg8|bej'
    'OxR4w*y+YCJ!~bltw8H2Qzn~GHG9Gz3K>wW2r`V38ote7qEhn^k?gP74^>UtmW+VpU>AF^JT3?_5u|Ofuk@i|A_Kv!RYQ>0X>;R-'
    'Bxk~3t|~$!?t>`-!KdMy2D7Ey0^Wr015sY?X_2fNtfISiODD$B+c)-3ad!FD^>Qh*^Z_v;aHP>_LPz!ODRS`M@W{NVPMcq~E&UZL'
    'V}&IvDG9GlPF8q0!Ayp=7)Fple8DE(F32QG?r!=;`^sf|8#zTM5J#e;v_uxJvdr$uydmNcD?uYMq7OH2NVjT*l{LmJ3P%~%D`+SO'
    'dZHaMs~1O^3Oxr>lG;P&#@(D)j(a}3BMiu*vI3SXghNsdi;@+c0MaWXUN_Yu4s)_j!r=m@>5aQO-ybhel@E)KEx0WCEqA-4gk^4k'
    'o8XBE=K+F;p%0vZP3g7Uy5Ajl;*^tcpZ8YCwjr`h@S0lG*H$b?2$c{hJOu!)#Sx+$jM1y3w~z(#aRpmm{>D7s8)W>1W*V)cR?=AI'
    'a^q8@XaY>8y-DLcU%QcqU0m#}PUcaU5g#ija<qC-NajTYz@-7Lj+%(Jx8^QTSrfT$*o%sx^GiC1@2aZ=*ue<Xrg(*_$sCVPh+In}'
    'f>$MfvXLT*>g2YKEh6f;d}(1<Y(*$RBRzyLfuHRR1vrRU4&x3{Aw`^8p$j;4?VirC$X}1Cyrsd+RItp4kR%S21jB_a>Mng*jxsS)'
    'huU0UfUqidd*}C8365A&SecFpwxc<Lvpr7Dqo}sX?_s7v^%dFt>a^r(r^b=cJoN88u@d9gaG$~Z58^7OMW`T7L6Tu%0Io5TGvS4E'
    'b^Wnha>!FT1ZVc85EW6>V8j5C)X12OC=GvH2!tAsNmCjE;A6V_h6P&Gv8LuHWY-}zKvqsx$<lul32?`u>90RPu@~@wvK+E8<y&@i'
    'wuaaozshy*@^&x-Zq%n>S&~J$q|K~P*AJ$tdS0+&P&8hh8l6ir>L8*cgu^oFK-yfsb=db{Rx=4V3I>i2a_^SzK}$9{($u*69$RkG'
    'Sa)}{-0ZXkFl)mxpZt|v5s;deJl$-pwdj0dc7p8X`n@c7JkpNZuN_gMCCBI8P!-w$_JRL6q7N!-w4QV@$Um6(G2FPL?~fG*AMy?X'
    'bz$&Rn_6({i5wcH_TaIV*0_~OV(r4!dC>PsiR*WvX{GeOYs4O!1zC3*d%@C^>>;_cR9)jQO_?;i8+MZZ6klEq>uTFk7N5si1`o_?'
    '!a=WFszZkEaI^BSB2);N-QBXO?ecU|?PHn^^6em3WQa9TTjYTU;|hy7D}xv?5E-&`^KCoYRn%jQ`%zXV<}Q;+BK%oHA>E-OkWmqQ'
    'b4A4QddO2dISOOg?F*Dct7N^CtHTI+8}CeHkHqJc$Xi=ghFKE88}@M~1BQ~`5Sks#VtmTL@UaZS!Z*<T!9I@JW|%7Q$)lw8>6Wd$'
    '-BU!sLY@<-m@%dV;Q-}D#xgXR=HOdNAmo%#)pMKkiT{etl)HlfU{VXASLdr9g}~6RM70Y1qlsZmRKXJ@`5QJPd0|02MJSW}Mecgo'
    '`t_a6_JStCkt)NEApvuE5cqJ*E{<~R+=#?g#G)vN)e@yyO*%zF%6{k?6YfClM3e+FqvE+G_P*s12~G$a|AN^Q{u)^AF;)vM`b@)+'
    'XTn>fsbVde4gs1!%2%gZf90N=rLkEM^5cSy9ueprav9huFG_QtXj@Qna*_dk<W7IhCCP)4W&$kb#IY@i-)OzzK4>)*(aVbsrZM;v'
    'S0vvuJRJ~cGOYUC>iGdHo>zl|<v$mD+hmeX<`j{<3Fwm6U@vbpPenD8*fna1VPRZPd4NxPlED7lpLhjPstsD;c+*INc?X(eM_8A@'
    'nXs6k!(q{aMz^KW(64|iKH1k&B2@1R8GO*o!WtO&NTkGccCqrn8n%^@9S!H12RPcRcXe)_)b58=7>Lp%Tc9(b@0{iv%mg_42rIdy'
    'Xl5|z%b2V8^PWXnyD5@BjT=?<1Vx#yfjkB!P1i?HHw@GsJDU~h)`y$YKdax<()xx2fV>;}IEg91A(&UA(1=8xNZp89-dww<uy=>A'
    '*g`(-j;^f#23CSQGfP8(We4~vBy!omM%ZE03lMNA_}UfxxPRHr8MCM#4#XSNpi<_)G5t?rfGo5{B#!qAUgjX0mSXGb81OUfRJkeH'
    '3Psox2<qVdYf>7P_zkm^pmk#<N~Vk?*~NI<rc@1A+x6kI(&dwBAjz?e!5PzsrB6eVJPHSwZm1is-O(G8QoSLJU0WXzp7u%is>V1q'
    '3`ipvM1lyDkbh2=eD!<N!*K_?-7DfF^=?acNG;sU&tQb1&Xo!kw!>HvcE_N5WxjSt=kk+$>g8U;0t!$(C=*<EW?#v@1PdC-$yuX#'
    'J2k!rsx2f|2qlM`w{vRe?CP&KdT(;w<S>CdWnFX3nv`~uY6qwg%#P8z#-|&1w)6&S_oP{ay%b*b<`6oNk<nU#vOqOz1&EVLPUDB;'
    'dRFb}@b%@Wgt7iU0Xiih8QHZ$?dot@qS?dE3vmb)6vYOb4~p07eVsS59PPtv#0)Qsk@OMX0x8_~a&p4$m4I2OgBWDS+PH>7H$iwy'
    '-x=`5W_icW^DR5t`QJ&Js8R`=aEqT}!3aZ!O6XkCqhZbu_f39dgmUn(C=D#)WA2tU3DXCA`st5~sU;Idc~g^2>~S)}AOoZYrzQB3'
    '7}YFpzdS`Kto1ue*nX!wwc^Po|24n7j7CubL7{8_6{O=KAIS;{AY&8Yx7YQDb;pO6E1zxV-0wa=ne*SB>-o!Dk$x_7moblusdJ)`'
    'G6K|M%0dDH1Bd=I)Y=tv=TEj$O#QhaKv-Z_OXowK9K4#S5c9<XZ{@QFW8c<)S4Zc8D9;4r<v)wudnhnlH9i8bMV`hWXFO<lAYxgB'
    '0F4=^Ji|?ZX-c>3qVyz)D9j;{+Z;y|ab425v{r*kFo?wL6>1_rIZb^UeL9*?TYbRj=|JBe+>eEHUC@|`N2~$d7|Qjc^inYo;7*Ve'
    'D4_w~dusO;WT?|Vkn*|x+3N13A}Q6!$h{z7DvAJTWI4isX+wb0y!8$$IJWBJoY!pwYwpe7DGS`(>#wCgx=e3T)I_Dqm^C4kfVh?$'
    ';k676pg+TyYO<ec{Vw?Lj|D3>d5esi3jk*q-~wid7fdnhs)0X??3Yf18-{g@pI(8ELDhSJRRPY32_2+GtWEGHr5yze93CSM>eA*i'
    'gwU?g$DL(X($Ac0y0VrBQY=Da%&=j<dZuN<^rkHyNL;9M`BT{M5D0s}ZWCwN^YtJU9Ox*tlaOB-Ju^Bai<U>hjjxR8R)ErQ2h6nc'
    'Jkoc<>8VZ{Xfz!q(u#v}hi4XbEClLKO<ufbct;~@bOwf{bvuAi;+Bb%_51+D#*hIC&3utERHXOL-Hu3wIH>^>82f){I(Km!izKBi'
    '1@T7u16(W+>I}LjARtpy6THDdI!1ipeHnAV@->`8^t(q;Wub<bMI&wKq{+GpkBn$rgk@kJP&UPnhKuA^z7cv_o=~YTw6HuHaH#xP'
    'f2qO(qyy++<`*5>AW99lDW(^=b*)?eWlN@aJQfZkS~h+ip7FXbfx+k(8T6nyS3qGAsW%9)>*DIQ4}WY+-Dyq86$zBGK+0I`A;j3#'
    'R3<7t%tnB|jkM6!Ys;PfL~DAKb&2K{Bwyn>WieT5VZI7oCxHRrwsdElIFA5BSZ*85Q0UtmcT&^_F-Z**fT@LnD-Uv<bTttc$`E6t'
    '7Vj;TWZC-l+tBJ~u2&_sf+0UM3Mtf$n(z!{gYzBtg^Utp0oDm$26<ZXawG}56Oa4HPpJexd5P$?K+Hux9DaX%ACoqv|0Sb|nj{8Q'
    'mq5x_1J4Pi?qILq)$hCQqN`Xm9-I8&?hCfeYCY2;7kem5DIm8bUGxT(Fu9lPU>JhcUcaN0E)=#0W$t}xN)DEKS%Z~v`6Fb3Ea54Z'
    'rGOFXo35H>GBEaizJ5Ef7I!F!&u@>}3waN<p#bI3(UVJF*GXrBj~LxOE<5J1O&XUW6>E<-NvU8;0@#;PO^)`}pM^0|cvo}^pdIp{'
    '5sww#2xJb<4D=k(q((DV+Y&6A{-jP^dht~jgi>Y;XIwhYSRUdrO@M7iw`AKaOMnIa=&D!cvnXT}e1*{mqX|e+3dT+r_(r@a?oz%|'
    'N@jffOQrg`#q=*mUAT3AD;e5kQDc=#;Cu*502Q;vS0XY*6JY`D3}#qEdoq>lpU~!lL7=9q(%1ron*m1TZcjafH&j%og2#@;DmA%s'
    '#j`@-RZUydYhxM$83C6RIupzS(VBIGvPX1h>e_^M={FT~>DL|X_Q*Cs{fbk^MhzCApw_%(&E7;k3HQBUgbKI_F^-B6xW$a^ZP`Cg'
    '>Eezwsbp7<2OS+vMo%y)fX*vUbY5(GF$d@@CK5JA-okvXTpC9PzNEh%y_lN2%P$@0gGodvjr$IgLUc00Ln#8*3DX30ilREM+rT2^'
    'DGa-U>I63epBATqAOcdYT<4-Z3JvT4hN8Dk?IT|%E*FTX=ol%-G}sClkRXNcriPBuM_~&+q7bIO7DWx)oe)z6>OY^u=J@hd@>Y}T'
    'hC2(i7GgOvuB0KIXr$Q=w&fZzg*qq{Wv^OyLDuwi%j4w8@cTs~A!S6?NDA^%(5fJ*I&>k-Z#BKBsaf^MQ$TbO30;-;G~&}i01U9B'
    'sK_Qw)Mh<eSNfPKi$-j>Tax37#m|1KCwqcT*?gQEh#P@EkJH5JR>&9>Up^r^cqT&wq!lBfM$OWIy7|YtU(PDM(9?#AM_eAjQ<)?W'
    '-*e`6q5fQ6|6q&uBEP4nZ`hlEfmH(z!?jWH$zx^)BP=ur3i?sfAlje|A0Gk;E|D3Ue8@#f)9a$AIpG=^>BULQ+xtS<-)pK4a3Iuj'
    'Fdsx7<N%}}O0^X_kuzYq5h_=IwJ(32F-<CTp9)VM@BPKq5w+{`h|vXuhT)st%iR%_j`)dMaIW0KLgd_DG`0nh#n&E!J)~nNLKl$?'
    'bp}-h{JX@-YgC*R<%h2;o?D$&FB@k@8a;^AG#VO=kLR5PYe0>`b_mNotW7_3fBt;sm2cdjeIVlm;6hlCm$9g@dbufFuS{jg@B(pe'
    'nbvHf;+dnYz}0|*oR%DuD+8Sq1%TMASX5bNcnA6Y6_$NuoS3UNPoq-g)p9Lb{0aCEI2pF+smO@vbjhld9%`m(T3U1$Ut}xt^8BIl'
    '_x;bDi5aALWLj9q(K}-Xa26L!$smMjIF_0<U96Z-D;^e$=tEUqim@ims8)CxjRwXd7<fD*?-?!)<RV5&t0z19+J&E`<Yh!dLFr7>'
    'Kum#IeT_k`Ly#oN1USf=sDZc$p^q~~mc`q$ODDW2_{P5m)SjLJ<Rzjd3N@j1BqLNXqZ2fN{5usn;cu%hWS1(x80_KT=#NPnCKNGw'
    'loK=TRS1&UJJ3eJh86FyzH()i727hmdXPT?e>B4>gtF3-=_wt;<X66!e8RZ?8Z*}}y6|XT#WtwhBnK)!bFwdLH8MLaz~EdmhXeK;'
    'ifz=K6xAcH4b+gPNThq+#F;)r?O0OSS^<CDl3=e0SP*N{Ij4O;sF%;6WBq)J$$s6s3m!|c{9I7?PPAm;cwxIZDR#>mhy#XM>?kpm'
    'Tw+MjV&&SeszOq-%gb^RGIB_hOX*qi>%}{fRt1S8<M_~J7=&SQs$4cd{3tkPG4~Km8;qTR47x{-GhnGq`=6xOqe4ZT3sz9M+%_&2'
    'OzzvoK$!v5Y2#~Xb|XB39?PT>bpqJsX*=1?k^<Hqr&Gh_DZNlGUe4&j(?P?4F=_u&G2{0qzhu<gjLC*OLrFo3J-gb4e}8$re1>}2'
    '8fx}6Ds>|*0)CSSdI#mTGGN4uO!HfY%Joh|$To*Z5QvKpm@bZ!^iz7r4nwDbdBC&8O{ByIC{A&M6d>2G`%1qpzgh#yPCx)gmIO-<'
    '5y}{_7AhDbq-g6{wKL-)tX{b?Qt`>sIe~SM_|cXWLq????QcdJ!L&urjjAyh{jlHG-|fB?`j|_zmJ1#$`dRuLk7ycS4Qy&*hKcjb'
    'Xb)Q(B{Xlnporq5kwY?qY%V^;YWVDN0|18;DM(?d&f#6#+Vx%@j@xBU>E*JJ(M$566)jH!USPFZEqu-21dPYHnRZQEeV$$ie`d$>'
    'b;?fwZ9-F$FSH<Kje>$nz$_J9_VDHcgP>{#_Nm;#JBQ?|<r!y0dV?1agkRiL<wq+74=|70FA0UAC&na(%H_|#$T+J%9KROO0Es>D'
    'q{UGYoeW(`tdgitiO=-maNX}AvLjWgT=)=xmkOW~m_2uGgoGL7g^K5;73@HH00WB(Rbg}N)-1>~E`GT14%Fd-y@;Vc-wv%dhBrBR'
    '`xCa1)Pb{c9nRJ3ib(~QR{>B18%nK9ISdp%3W1Q*FcA!g3S>~Iv02&=wNd)bz3810)#aa#8X^p%W_j=_bCMD2gN_58a>hC8IAh2O'
    'w)PG_VYYzeKj1ljD`fBlL;T9b%>sJRyee`^=9OoH4BHWJ690$VT>9LPS@Nq?kiA+N3X*#aa{QxVMeQv+*M*>oh>$2s!I)}GmQ$1a'
    '@^9stVh@^e9bzI9HK%ZD#&D7X@NkuH008wvT(#l`&dkO85Cj%qMI6jEotKdnTox=3Q?^y*kD1;;;|_V*x>ZjZ&-SpZ(DO1R2=zBV'
    'v6Xac6r)Fdftd=5%S4$8SF`J?e>c`;r}ZyqKDgge0^(AJ^pg*2`KlHH2l_r5w;XY%XNKA^^76bui7(G0v=ll55VLu#*b~c%k0ht('
    '%cfSK|DhfUNNQGWsl6#q9-4I}179g~y*g-QOLiF{Lu0fNMQ4#)QODproGj<sa^++gDI?Lnt8mw5I+9q#oMX)rScu}>&4Xr>NQ7Y)'
    'T4pR|2B-p`{@kD5@RtpL#oByRAkEC;?$K^WuQ-gL4VbxN<27m|i^?Tx7}SGi&BCvfs?H-vE+4gCR^9m0aZ|xR=jVb1$m_srkcHKF'
    'aN>B|u3G=>)L&;^FOw{uyu^1f$>?y7%;*vI)o8jXd09Z8ZHjJvKkeX*NIb~Pe2?`DXhFfF6W^N&aTyH}tnc7SL!{D?FdE$hQy9d}'
    '4@GXmPkX3Zn8!?e-wSL*TSLzYsumx%TCDVla14^oaTo0Bh4pV2s390@fM=4iz+$9C#)K3|m-ZCW2rPg^Fk~)H=?*!~kEuFpvd&@J'
    'Zw4skQ{u!SBtnKty_05nZV#}ZMO`nf_`H2ah*C<#D4m44cukG88c?v5{|v_<FY!<n)kZGc9DOvl^8E!R-UzA$nx@uuo!A*sCXaN?'
    'sfNk00Wg84i%kHbz$+&c0tJhg4bus<5Eh2afPy|*&6N;o8S0lWel#cVhUHsXhyka5Q$g1QDv1?0wIW$3zn*dQ%zhw-!F?n|1JV;I'
    'P0?@oK#Tg(y$xi%d;QsOwtv+_6VY}%StMw*m(^HXP!ODCS|&nj1VJB>v-mO_wq`>$Llsdl<IswLj%pq?(Ws#f)P1DI;K}%tXgmRY'
    'nf9jb)EyGfuqb9SBSwQmqUJt`8`?c1SxU#IbjNf>o%Q9NEaM-a-L^1~&_pJU(dbtp+A0!I8^GaC%<N=7j;LsGzly#w=dFORtM;w&'
    '&1LW)a}RKV#-o-Yk6b1Qni?StUfL>X%fzAHg}Q~0s(caKGn7J4p;(&G_Vw}!b`t&5lAa{`N214M7LMjDX+s>V*Ip#Jr>i~f_sb{>'
    'nuR3`Q*5vy40#AO*sF-#A=NbIYE;2IaDZo$F4V9qHnEbzGy^hYKcIP&6lX%avF2)2x%7gd;k#klS)RA>eh0t5D6^{h`E6oos+EFO'
    '&Q~xW;P-Lvh5Se9A=NQwn!uXHSDZeYz_VCI3kOssOd}aIpP;<<z)I;B3c#IKtiJ9DB10tzQ8*wb!ZfnOpAi&_heAQ4an}J*kx@aV'
    'TOJ;I-n<(aUq6@#Rz7fTCm}erGTyi*^w4u^(5TN6azGRS1`KOAa85C+W}yN`F!wk}`xc;tkmxh5Y*J<b_h+ULMdjWW2V;G<h5C6^'
    'd;p_tYAB*<fRG@-X#?FQ`|_HiV3#o@X6-iWXR&6f?uj@2zo->uIt0QCM25O6syl<*Pp=-$bvt-v>0B;%n7IWl0>&LlC(<cK(F!Mn'
    '-iAs7JDW}&U{^$I{<ej>?k5TXtWH{=U~w}3lnW5x7YLe#L7-_(ilA(YQu2RY{b!2fVt`Uey+KXn(8HurfMAFsw8+T))j*Pt2mFpZ'
    '(T1D0QNgr?3uWd&wM{Nevz@mOZ3(e9-hf6!G?-8fTsxVY_E9~WmGLT6U$d|)ED&&bYGsf<D}|<shfNrDaqgzoo6&^UP2I>ZT@LuP'
    'F*6zM)&w+8)FxJ9wMpyNQXR>Yi#vPu9w7ESrTen@61<k@FEv{$;~9pRFinj-9x^Nj5op!B31Fy5g7|O)2YK0*?hCr`N|8`q(g>O5'
    'hb($al1VJql}vWQ^>1wA+7R(NU9)P6Aj?dPNTQKhZ(8Ul%giPaH}oun)SqGXseIi+^|V@;Y#Fk>m6nFOaqO3CoVrJr&>Evl-&gZ?'
    'uH47lVAv{$bGX2aLdvbiXt#3X@k%GjDIfvSWrp*nA)u{WyO~o@pY$TYN!n;y)xOXn97$a$W<b6Hn!!Hl4F*X78jW*y4hk)a)wTQ3'
    'aEGTQ!{VYUjvuAhK5DjMG>weTs6!WP+F?+No5!X59*X_pPxf-ku-Va5g#r&wR;H?<u#f{juZGGC&IO7@h>y@PI7wgvqq%M?H4Jhb'
    '41<Os;&+c19@iXIXpn(9)EDOUMorfSR$LppK<IJyDs@62ZowU=3j&Lpgr0g%p_0}M7aiSms7BOYeOMbceikiks(>Gla2|#lcp)rf'
    '1S@n$@VG|)*Xw(QT2255_3Bq{rOq&m+kq)D=uu&$(xX8+J}bAC?Jw$mzMVMq-P&9`KWy*6au#0B7wRL-(1M@={Do84tF6lD129CC'
    'Zw6#&6eF975i~SJ7+#xY-3#n{k`=0w-%Z~0xo(SU4uT||W*W`F>LaFNU@=6omNbwk)~X(f{B`YCh~f|%+|$c5$7HDmce`Ae<3=BW'
    'ZW3u0<Ri$VkhS?RaHoRp(LgStPuhjJ_MtGN_UWUm<flFsRKH%<tDurRdbkbrv@n&!^BkO;HnI5WZ4u@D*QMVzH<lN&#tgdAG&xE5'
    'HPQqlRyuhoeW365Ncicg5!dn9^lLv^2;}RS<FGnOcp5|DqoE-kgguQ<<IYF72&;*(Av#Qd{XUAMG3ImdKa6?D#0eC-73nq0$At-I'
    ')FR?ULK|Csk7x_46ce3%o<ZI*cs3ejfF~_aN0d;MyFLN#!YHFUx?&$I6cj81B7@tQa4`#)9l|p+iW(y4q*!7X_n#(Qv5QJA1HC8u'
    '$>hPP3~50yY?uFsGIdtTis=B;iSYhdU8S8Qew(x8uT-MJftnHTQ=@{~5l$n+w#0pgW=@L&Nu=o$1je;{SVzL95XN(bXu+4s%?kAm'
    'sb%BD5gs&>2nsldWA%d|IxKEN=N4&s$|8<<Ft5Q(KoH4<QF#c=rkG|pgR&bZZ@AST$eKy>L9Hm5j`C6>IKV*zPDZH+bDKh06Nhc@'
    'R;Rz`9q^4RgjNl`rcsPI4O%)aO86y2bKJX_<bhI7HfNEljkZgB-A0~wOGxKt+lFri*9ia&Xtg?}lFji3C{RJVVRcb7Y36(u31+%('
    'BMVQV=EXE5mH0j+GI1P~H2ck?Ntkpp#mPya?wY!|Hd;JsePN4YY#<-N5BX3)59lm5ni>dek-Lix&`8IBgmD!{x?R!y{OV8T+*e)K'
    '&_;a)L4;y8fUc^AE2=%LYxXs0G%1WnG9oivx0ki8ZHy9uoQ=qa4K@Tw?r4J`Q%kbM;F})g>)nq2y4{?(G*ugc69y@XOARhKn1)?I'
    ';AO7bC?9QlQ$~FF)vss~ou2daO7SV^0)?WclWM#&OjAGf;zGh4cig;qaPf2ozcv+o-iF=VPRe0bUXi3>tRsRgVm9>EJRl?9Zzrh&'
    'Uarh_bJy(R^j_}M4hx+UIg~-h@Ln)DVekgNNieyjB!h4xemVJvlyv1G6CZBl98PfW&?txPQweint`2uA4JlHgAhiVd4F{LeKgf`v'
    'hal#ljc2ZUB(LA{3UUm+3OqZ|QRGI0%7~{FPu9re$mG<*L2tm$SLf}^cHWU_t07W2ZxoXh)#N}l&1mBV?n8!4aQULWWPd@nLsxC*'
    ')zO?1`@TjtHHv~D>NfRU4-0^iDFhVCeO2IKM0B`m?YXPIp)<p`_PH2ML~#uUdMF`iXL20_0YwQSDS|mPvh{89+DrMb`$v+2I-CwG'
    'LF!rdBKts~7(^(V5Q+9$mKkvC0CHhgt<4*GJ3cK~w(2~_LKlk(T|EFouwd}wfeR9FB}4cG6&uns-VxBg7^^ec^&5$JiM~AyUe*0}'
    'aT+MHfB0g0O)HorLWe)eTZ1r*eicxH-e8adZ5-Bai2rhoJlAx=03JvrVc@F|328?gV;C%t1IBRBG))X~h&O9DQcoP#NNh*nSJZpL'
    '9FD#4-=NhjR!I;pdlGEa2y3GpINjN0J}}MQF%_V&3xyHBVgc$1JrG_1(#U4RLTW{hso;-xeB~}KP<wwWGr4JI-Lky^eVQGkYK)oI'
    'd?%}GM1gX1$!k9p)wg^ennYQe%z$P*LS7<bB$<zDQU-qa8vBOjCMgLs#9`)5YY~t$%XV{?zRLZlP})G+<}6O~#{!|WA|S$9F&fMb'
    '27rmOTE+9qZJbs7ue&J{bm$=%cx$~C-%xxE?i36Y$WR>WY8r(A+u-Tl`fcE#D}6Wl;i=BL9JUa)!P?U-NvN;#W`{vDXn;N6EbJxl'
    'IX>E9?Z<iIAwQ==Xz+|-r`sn}tcLko#7(%s*guWB<#-pscl2eWy=wJ37W5>*lnJpdd54@7vCJ5W1@z28C+UK+zljun?R!{k%T5+0'
    'HBh$5Ihliq^AEl=%&a40pS3A!y;f5{p`VMkQQF12h~#Af%p`@x8+Mwjj4BuvrG+y?bpVNt(iXl-Y1KFHjJHebJYT3V^2mv8kEkEp'
    'C`VU`UKTBB13yKQFvRykcek%zy}~7qj~hl19LkYF%Rqa2@knTR`jEm0Y&1x$aw@WO{xS=xkABS69H2ThSm~1_jeK5Y{ymLu7_Iox'
    'wBlorsc7?i4l|$KyFYnHFyRl_CPKYq?n}!JivTQWLOe}nbgU@T={^rr-HO$L4I4z9uxX0Xhr#QJ%O>K3$EXYnE-w2Z@+@Ju_(PX('
    'xGo3mpmQ^#WwMqTxHCj&^gzoL4$d#+Gls*-#BHuxQ8BAdNr1o|UKzKD2TLd0B<UMi34>UTh=R?~(thcSV&r$r)<g;hz$E!S4jSY`'
    'eS$|YLsE6DL4c6F!>9rEC|XUvTNO^S`p^aXGnb+hdEUrUlA&!JCv;E5h(>c^uvTJrPqAiww`%1LfhNURJcXQmvgj})3+RD^QPyL#'
    '&WHoh3`VRJapAu$TrtB5t}ga6ILU@dlU4`VLr^jtNI_4bJn;t5_5&b%w)CkMzk8ps-yKWy=E;l6f;6HNqY99tRx`Q5v4XAve7K3z'
    'JzeEbZ$xU!yxTvjXNWAsJ^c8Og8m4YfI0FMat)E6Zlwm>GwB+tgHg~}oZp7et!&?~cV<lr0V$dI;~FZJ2|oT4U^bq6L<MqR(h!nl'
    'yoFV7XI$A<EPKZL%WJD6$y~;yPX`?#?HAeh_snL-p)4n`W_H2BTD$fuxLvUYa1MCl(D0~&=zGZ`l}Va%OF)pFB+N*fRQ>6xrs_Fr'
    '4|kM@nX$D0`2DbZy6}s^KjGuTG}3Sq1bwr7<`FT9b_Vc;jxfU${WQm6mER#{+%0WRP_~bc@%y`{$x>6nu414Skdj^Q1SW4Vunvk9'
    'YPU`h>F1n$%>g}6*FM~7_~t*3e;zN*7;0w_Gg`cnCx{q<lACmTkeMO=VCag79PQ^)HbUUt>yP|cknxit1c@5cn0a*?s1P-<hp5y8'
    '&fscCj6!lCIHI|<n)uZEySoKzFLb5QibL|iZkl?5P9-xCq3uyQ&?fBRx`Q#`68~x4bRe&~gU_Mf!nttePd4X2*}Rz+Tuxtl4KRk%'
    'g8e04B8+E)<G>6?au;zOfMDR`@XtQm#M|%Pt1r7R2SU`<R0I>ixskw!WCh<mg!`7E7S!xcW>gH=`{)Fz<@&|DZ=BP&|5ymRa+GIy'
    'EENFNkVAxtWPgOwgbPL>@*4?pXIrt>X}IR`fA9WRdRXGY|8&Q%1q_yp6@ESmH-(U}Sg)@#x@91q0CL{;_;EpcTAe0I_<DC{XCOx0'
    'J(uN|SP;S!K~bxq&_YNEntp{}H1VEk90(CnzJ5sl{AkVdUki*nV!H;~F}aCB^8&h2p)rn8(Vi)mXlwyvKFkZ>FL}!Hzbp*8!t`yX'
    'rox%yf@|e-gt*a>v_KU@t0aFD1SxP%W8Hd@B>3`y?Ut{DN)fL%=xMa?@dQM}jm{I<7{2|Ds2?9v(mq)4{)IV;h3DDLPF+#(My^XT'
    'L1bvK&glLjvB2bl*Z_BSu3Ha-v}0-L=%7(a82<5t7;O$`ndhr99Tbpcg0imFK-lo<CmFVPC!>SIm#^E5xjDGqX>Qx|t`H4yf<uyu'
    'uOhawsFcCH<p)Pd0+R<*gsDtW0<EZ6T5FX#5sbEHCLG4y@(0DL1BXRG8Kk*1uR13M6K1LXhx)0%Ex2ER<dQMA#DxL!aU<Un%#=~%'
    'Lc>K2i#aTX8?4v{X-ktTR(yFbGV>`7I|%52p0lVfwB?BFR;_(DfrkRNWK>d<`)swCWUvjr`3DIuU;jaFUBz$G%KZx&1gQ@*Q2|y4'
    '?oRF%sNTJ#<|u%9vu4$*j7``UY9=pNb~+MBMp=?ugA%-xjfQ43!Rug>TyL7RYT4oi79``RZw0A3iMwKzD?qBjN&ujB6f;g!JItCz'
    'Pqp~v+XS_dV1K#!G8}>r77hy)BS;#;V-jC@tMoaW&z6NZbhmsScmI3==E&RAfaZ#qOF9n?6Sr=FUU{L&85O<;Y8NU-Iaf;O5I%p('
    'pRHU&6G6Cus|^u>IE&>T+z^akNCV}QBE<`~%eYsytAF*^QeeWairhhJ4liltKr@?E3DFHIe^{xOKZhpa`?U*K%&p~)hT8yf5P~g~'
    'LhK_X5QcP0Pl4wj8@k*y<~|L_G(%s~9RwJ%m&LyE`RGb=g&x8)Cx|<hUkypCm4g6Bn+MJf-s6JS$oqJ%TC;q|(Jp{aZ5_V`doZ~t'
    'QygjrB_#z@;Fx941w<}fwOq{=2jmJLlL;<NThG|(60i7{&_B>O0SWN*iAG$7rpg76rOXp*AL>{<{!!z|)t_0YJWCwc^cC|o=_3k^'
    '{WK{$V+^MpyCNrI@7yX}Fx=r;HsqL_0CG^~6aP6Z@I$CHY}InlT;CLfh2aYAqW6QQg-o7Ny>hr{_<QC?VFa%5Yh;`|Rjv4uJHStI'
    'o;fcQzW^FG;{gHjA>tdsfL2^eDG{?UWnZ<}X%tX_1cg*;*05$wp9h!}pxI#f)V44u(3By>g`+ln`Zb*6`s-h7=K6^=jmAP)>MYJI'
    'mpB~?tQSC8DawTRvKKdfz9jk2R`K+1IWC7+^N@m7jG5Hh=FQQT;F$0b`QiL841{PK8OLyR$JMKr$6){#kUB#hV&)b%DmV!^4FDL!'
    'O(umto;8VtZPqVMQ$Ox<F3IQ#vUuT=DUklD9Y&wuiP}EVN_NQkWZWO?S4SrJ$3c|C=a&Kplpjo_h1iF;w8if#QWf%gA^wq|34H+Y'
    '=tBL<<?sLxDVv0S!7^bEh6xxIK~HmJ(G4T)CdY@F-LF`ab^dud<l>irfC#}MtYdOR`UDz=(QBxemm86uc7(3AcG0tJyij}F#VH=-'
    'k+O7|7$sjC9L}TCV*q`)NB~$X-mfx-$}wWNXM^O66u``IMJG}6z5Jh*yg|k1@}qz>^^1c&(iu9sld$X0f>K;F+voy$O?qb14TvxO'
    'e>~;kATZK}gn1U}dBq8PdVbW(2WF=hX4zr*;~I@_6A_PLU1Fhm*(7o=K!c;r0Qf)#RloN6Habb`3T#9YaTx>)^~Q1(1sxYKJ(J*M'
    '=npTE`yVmliWsUt-@GO4+Y)!S7ZyM&1r3JJTO`aLdj^~-TNQlxuOY89eX3ty{*?KF!15a0?iQBjmve}F{nIZeaqgFMy0ATqRkw9*'
    'HU|9BollUvpgFZl??G7!gB?U$yx|gV2fWdK{O{lPUk&HVtq-8hXk0<_;8?&v@`4h<Xy|yrS0=nsGI5D@6<a^KV15!zf3lG$fYQ%3'
    'Al`btcrY>X1Z@YBbLo3E@Cx6nspg1FWrR+1={Qu>VM$Kgd_Po}U>3~gbhKI==N<7Z-x)@}EuYz3v2ZomM!$l)s9}sQiI>c-DJL|J'
    'jZ92_fmlx`S=@eFi)aRCVgSSCfQc_JYCkK<Hl9ZS1`-TGP#xi@Kxhl1@&YD)T4A2tgzmhEA#PvuyYMQd(+E-t-tR<jC%05@Y}ABj'
    'kSCGx>7aa?pC9)3epC8cgNCGw^}%QwT=9tlB<KxI8(f0`|7kH};E=jcKP(BZ?oQx(!W{QY+~#F?;&EH(aFV#vWx@pwjgK5ANoZsY'
    'hMlS)1ctkk-~mIowF{S%Ir>issAn*U1;>Yw*S5ld=xZ<nI%vMEJR@os{HbQXT!#dWou2q<GiK#*Kag`Ija~|p<&7GG#8C}H?aD>?'
    '2ZIgZLFBj)+yU@d$D&E>7Y{Zn*9Q46^UB?)L4H~5)pF*GTbd^Ymr{6J)K&~=6PLb~Bm<Z>2^}Wt(4s=If&bFyhxO+riLI~Q#mkMM'
    '*+P3*7yy9n%k*{dmyVyymqC5NnUbulZqYXd^5w4*NoS)e=HT5p%ZP+6(@K^H499~^no4}0T-}-#P)i`opXAkud&nS*LUgN`qe8-#'
    '0~;Mbpm;LKT(_VQ=to7n(zl}O75geCyrM4`9>FjeNk|#(+2y1ZrOTB+^28&qX}r-JWWF_r2NO562(v`>w4pdX06pAUnBKx;%Kf@^'
    '3xg9#!8N~$6U@&V06cIcnNX9X5kXBuBV(qHAJ#1iM|oQ?)@vnFqAv{~Em4>738R+HynH|0CCg;nmCL?nHO1+<R2uNzSb`W#&=p;r'
    ';u2c{I1q-)0Gq6-ZtWs4g6x|)Mc7|;>Sahx35J*Dr%MB_*E}>RXvSBsRwN7o5KyQa>3S(<_(X<4_6R8qzK8f<8g|3nV7qF?k0$s0'
    '47p=3u0cJF6$Ewd;Pf@(ZZchzQOQv4(CIN|#?&o(ApP{a%QGs0>=+t2iC(4yytEN`i=sC3`gG5b61h3AT5(fEohj5Ajg;VA1?)@V'
    'PRrCErxem$EOdbKfMw^8hg24ptzxUvO9j@(ABA)b9u}R}(J6yLHN-S3jhx2x-G1J&{&@LCb5UTSQEve80VLw}s2(-oyPQU8nG>u='
    '1u6b?Shwy;(Qr9Y0?@<L%?Mm)ND@v0knWaJof=LPuk}3I&oi`tS$Ii9;c%YyNCkn5CQ%~ZkoJiIMjUS7E<g#=CYV#qgyMpCwa>a3'
    '{WW=m3<W$GRDk9xjTJH$WHe5rDoA<9MN9a%1N~qB<Np8>X&|o'
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
                  'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}
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
        installed=[row for row in generations if row['name'] in {
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}]
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
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1'}
            and all(actual.get(path)==entry for path,entry in row['workflows'].items())]
        self.assertEqual(len(installed),1,'installed S must be its actual complete old or Boolean tuple')
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
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            if (installed['name']=='protected-producer-original-default-v1'
                    and path=='.github/workflows/repository-checks.yml'):
                expected=dict(mode='100644',type='blob',sha='81bcf1933edc435826e2de411a777cccd4dec7c7')
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
                ('protected-producer-original-default-boolean-v1','3b7a88765b7181a1bc7dd6f48b9b459e590055d3')):
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
        self.assertEqual(inputs.device_reader_digest(base,native['native_independent_paths']),
                         json.loads(raw)['targets'][target]['reader_digest'])
        plan=inputs.plan_affected(registry,raw,base,candidate,trusted,target=target)
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
