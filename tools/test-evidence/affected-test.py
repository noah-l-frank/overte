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
# fbfaf31d2ac822683eee58fef2cc3a4c86e6157c / tree f5dab8f6c1cb9979c2b9db52f4c81078caeec60f.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '15d990ae5508e960d14c043fcb2701bd96a2e2ffc005f0a498f0dbb4956acb69'
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
    'c-qaK-Et#IlAZ7M7=68*%E*lT+ozDpbPtPP7P?4+1Ax_CySDGH?<7DrYnntv0=1IXwA<6wt%*Qpq=)<QbB_P#Z~wU89>2c$FYYPs'
    'ciVWk`{OC??~Z%-bjWG{kKYfwr{DhlKYx4N#q`_1|7MzIu=clq`|a@6@waW;82+a>?G#MlKQ(5|IdwjUerUpEa?|B#4F4aFKc4kp'
    ';2(DWxBvRLw`DyGg|BzdyN7M~QCQ9Uj{mM94fEJUm%=oRWALeI#wK@zk4+v2>ze8F)t+7W=I+zoAG`gx{IL7u?mqEr-Eq5nIusTU'
    'Va~}m-c5aOQyiT&^E@W!%@EqDv3Us1)QtV-i|^C(?yx=X_CM~z*A%{$R_ucv+stzv&6H!DQ%ZC0ZEkFw`JwaVy4EIdKVR{f4#&I0'
    '%l4S=VtP(bF+GKCDy{3Ab_k{)JioG=$7%3glc%Y(uJ_ST*7%ke?uVLnOKZiU_j8+dO!#kft#f@EdC;Am<{`RaFxDI1>*s5|zRCkH'
    'cb}e)cmI5G58J#A%Uk`&kH?44SD$?jL!QRA^CtJRZHGLYj;HR&scnYIS~q5nc-89r-R~(J@ATUbmzU*Z=~~x2XG6$o?7gwQvC)jq'
    '%%L$u<ehWI=9*>yeyA=l-R9K9A$D^#EpN4Hnwg(G#4#G@dk%7(8gD=N#eUCnM27IN<tcv&+b_STr*GS*!<T!f_x$|h^Hq&;!TJzd'
    'Z>=4DYp2LZW5zzke&V<1KACZB+BK^_^UHbRm)Es<?2>h9oI2lxvE|3*$$Ji#&+V9-acWWuVcohre|gpH^4J89k;(kNwwYbic4Oyl'
    'nA2p#m|bxF)UA5P`<JJSYX)P7VTjqy-cBPw&&}P?%#-n5@~O4aH)G0q)tWlVoA7nNdrX@{*gaqV)l+Yqh9~PdO+%PcNVDrZH#Qt9'
    'VpkvH94E8xSuZ<ya*ydi;7*%;a?jhR`-|I%e6)PjsUIv+GZ~vYGq-%m!4J(~dTR+OTvhA0@%*?6yQjRpyguJ>8m6uvhRL|)S{%Bz'
    '>4|MqA7jfs5k~gdtzKXEa@_p+J^PF6d(K&7ZS4DzOQLUh61|(7&~ig^B0HW!!~N`5ug?kOs=T;%3b~tH-$tTY?nWQRV7%!X$E_7y'
    'Yo^%Qp{e-oiYR}$A77r*QIT%5-@P2uCT`vR)9!HGhRe~Wn*+CWvZfDxvb_FzO386`HvQ0Z1fy>qDa*Wi8!z$s;==7T4knp4CT^55'
    '&U*Ungv&I?mJcCw)!8(T)eD~v-g)&UG1Cz|razCD15nS$PHNJ2eK&Po(x&=3jlPe3jdKcyG-e*k;r79i7an(y+i*wN`@TJJqw)cM'
    'aW8Ru+?;Pb-Le<I$i7d`#@6|ix=b{T(ay8AlVYM7dc6#u%y{)~makGD$Afzzm%JRM#-R(bjl*ntA7mJwxH(VloHNNzlZ{CY$yRgy'
    'W?o1qFGtE4oS8y9Ou6a#?XC~)$ko7SLb}&axp&caZ8BHy;al22rH9S(mM-pOZaohqjzfr}@5XGKHv8BPy&2~r4{07p&TpHq-pQkT'
    'BHfM~a(s^R{>SF)_Mlwl;;tH9Ttl{#Z&DzPjH%}`;}#`XFdaK=M$1#Wepfrszx2Hj%!Z)KCG?(XX?;76oL<*8u?tg|I6=g*LI3pn'
    'T|A#F5BIQq)q59?mjl}r?bMF8orX3~15v&2yD`Mc4K2sIwapw;JNfzQEs;~@hwc5>V|A<@#x9dlHO}^)t0nQBo5_q5@kb9Rb`3RK'
    '9{mklDy3UIfSyvb8RxF)hITTovM#bL9?8txYo?CkrHxl_fwUtM?6%+eus3gy=yDdoS#iFZGxZzKpqs{txbFvoZ}wEl*#zQGbNypE'
    '9Qm#;AC{S;F=}Z)cT)&lLV4!g1|HN%IXRAfH}^MuMMt;4Pt~_TCgE*dh-4pm;EW_bY-7isLo(_KQTv&>N!P!nQ?~kg75LrDQ*?zu'
    '!!emTIHc#imImy?4U|ShKLpzvKiI|@>I9p9(Vi-<r!HkP_p=}7&UR^zeQ12995kHdDRPVzaYAlx+|hDJZK}dx=*iz(!-dJkIJL>S'
    'nEb@arpj?$*Y!O$bbsr6OHbdo``yzc|KjP@T`ucd;XFbKI`4fS2CfM2hGfSfxyiRYGj8<Q-L|LdTXb@EbRAX22xKyW(L_siO9DoD'
    '>B)TuK6rLyf8BOATav*0)9q2n1iha)P;qQSLm>9NEI$unp13SJ?lhlr%XV+u+Eur_9|5#Th&kgK9E~g_s7{>b)&z19n{DUf9DdQ('
    '!tQawNlFiF$S!p=iM*W+fl}{tB55Xkv)dsWpSfqJF8-Qb9n$yoRH&*cS?AE}1yV#302-dx)EKUhwo4OeXh$G-x9z7Y5|AF+xf8??'
    'Q=Y>-IBs0m41D|nK-LVrP(zt}<5u2fMUUH>Gd=?zIspt_>ZrNK7(mo!;~kIzy8~%UCOVsM+t>Qki1+5m8Noq%-wEc*4LF1uTFVh1'
    'x~XM{w#ok1eUTq+!ajlR9=Gn{P(TMLxvXuuXs6kew&l#jQchqz$*$=F7$BAF&3mdz2|6x+4i5hVTI7u3n<uLV(g(Terhx+0xG}cv'
    'ZJW6wdn1SR*$ieF_`)cgU7yMR$39z=oZ-r8xd%-fZrj*l_p%4n3cIff+&Wy&=2$N_6h)3FBa|(H;0{35vr2#*=Ey?}KukAoNm=El'
    'qJ#xuB3}dSYsa3-EPL*m7SttnE%?33gr}*QjQthc$!`1bQUH1<JB8#@?;6{?K*NN_MeoR2Ld#<cT{q1%P|S_z`uO;qw-4#9TD$!D'
    'k6ijg=cvwrgNT>|undpIlkYZyWa;d*{cz*yKJH%*M{bgD>BqhVjq=TtU-ErhpA2Vu<{gC@ptSLZLzSj%<CJcx2v%%HS$5Nz5lpn5'
    'r_9@<<3Y#E`i3toc-!?eSVZ0Re+H?~|K##*5j)U8js@uG*mGY{&^KhVz41MXEEsJ+g=wnGu<u`%aF_Ov+rwe$Azn<z{5;c-P@^MH'
    '$wx2^nx&M9o;H(BQ)pZy=G6V<uRFc{-L4eybwN{4Ol}@+u(V}cLL2q@#0?%B6M^ISOzPG=r7f33CmpPo53i&B5tT&&d?y3I1#FVJ'
    'bE4_kL#)f6p1AzKr;Uq`+siizoeh!?;vcQaVW9f~DiL#Vbhh|^9RQc5V5lqz&a2jdiA}>LPFbb`X$&b06!w-c9u!3IQJ`ES4Ah;a'
    '_g_+VjuASOT2GNreW<FH4p6jxPm7v9Ue~nI&w%ii_2T<}PtB(^(hQz$7h?y?-;Y)WewxXi>E+TFSDTUAERHJ{KNY57w@;hjxgMX='
    '<r+evm0(7n!w!+^Zx}(D=SG$LOfzbrPIVzyVs!6!@VNV)mSU7EsBje;aLJLjYU8KQ3C1O@A?eiJ2rf2LwU0C&W>>$5bx|b*o_N#o'
    'SvR!4Xwp+BnA{oX_|g&=P=YEDW?#R4WoR)mQ#(#hwKh1)IPt{^apM!8_z>+xcqi}f>K8u6mx^aj4a9q=ncH%GwT7>7BA50Z&DEA0'
    '7l0V(g#PE+rT;2nFW(_FvK!JKN9rmpWNgXoCmuY2e#7fF;3Onu`TFJ0-M;Yra``#%-I)MYp%D}fErdFQn`{6j=ANUUFpV@?<|{T*'
    'w|<v<nw*BLk7g&y7g=iNd+1vJU~-@fL+fL+{s@q;FI)~j1-HM91$oa++N#UStr7@%eb1gkYI_c0A~;TD8Zr8-w@~*aMxH<GH8i~)'
    'WP`|GVH@!99rbbIW+%Do$uq9l#*gFI-BTT)sl!i^0I0+FK>Y+oDD@*v6brCIkBRD-=Vh;W82fY&rbD3;H-GHi^K&W73cjKI%^V6s'
    'fiN&GN8dYo!c^qRP#X{#+!Y4{VCixbb{MGB1{Ncoi&m{gputSHt@R3#VyN}BNkaY7^$Ec|y4iIimt>j|DK^|l7Ie#!9K_z!WfTP_'
    'uegt{$_nT&^fbK(o<Bd?!-}KZ8JwU%$4=nRg)np#)zIme-)*0sUyfgR>knsE)g2lB-5-g>8(58s=;ChZ)u~G5tuN;<kl9lz0<8%U'
    '0q)K`mbS0Rl789^tKX$4;?w($sr1;mqaIxuIC4~pq-oS3EgU4rsR(?%lqI93_MlIkbZRTW(a$zkBJE_p0Oe0SmR48;S7?kARJ&%R'
    '_1SyKVf6DVC^O4t{Yq}Uyd<d_XH(fJ&0ZpcI^dpKY)liRH$G8#BBRTdOTI#5ij^DQgWEsu_L~>}y+YQ~w|ofPk#t<Z!@>|${sFbl'
    '(`ZbFCT1u`3FEc<I8~l^XRgGT!#@1KCXbXi_J55|^7&RyoDvmSOQu=CGf8i!3Em*D2=1vR<#Gdf20%IAFVDt7`5mVlw(|-gEZe%A'
    '^;$o+PzlA#1uRe=Ld{{}Ph`?z_CfNQAsk(~nT5o8I^B>--J$yU#DVXXG%&S5QElQj4zNskYt-H@_WTi9;!r`qD(=g_Y#-tY|EUFB'
    'iEI-@pw`VWfap;*ksvURqYw}<GTJSj_?hPR&7Cp3caN>WL*cX2^CBb!_?jSfjk>`!8DQiLtr!m`&Gz<<ZD|ATUtj8(bbc9GpikAp'
    'o}1{F8+bX<sN2!eFmB<~!7qexZl?Jc?Cgm<>w%_++tcd1e996L+Ji;YwI<aAJ12V5<_A*pP-CchX&X<y?{DALDd{0byz9_jzEr(~'
    '<TU~=^6nY}Rpf(=Ge?aR2iq1@0Mvi-w{LAt?26<WoP7>H{CVPcJJIxq;G|GW16f@U>NWQZKFf2uzI|LO*%$x()g21#Xh@R-VV>;;'
    '>R6!(WJnIc7y<w#E*B2%hv0v~89QBtRq*vlpOYv7wi8+a#Bo|6)0}*0hBk<#*7D$*bo-_b+xvwbu|*0(<y-Ml_5h1qh7^4O+7=LZ'
    '%6^*o7-(Gu5?vk`_-guZ*xQonRJ7fv6wR#m8syiRvqv>dMU=oodrCyuNGXCo|ALR;RS0l-JDL75EKnd>QX8P530P=o2kL^kHv**T'
    'mvSRqxt-TNd|7u@((h+cdVgK?f~zKOCOFCvC7^D3Pzz97GhY1`-*&ZJlm*s}pexAP+=q@hW%(3Iyuq=+b$#1Or~t9~=I3(`@s}Z;'
    'u5BrnxN^9Vp+bPL!e=4I10fLAp_R{|owmPqFBP9z3!_G)J}4O@C?mXGI_;i(7<B{aW^iPq^s~pCw{or@e*V}B5uj1Ilt(%z&I7S`'
    'T{A{V|CxWQ<AtfC0swyN)>do@P!Pa}s0d%nl2Cb(R>}VinkM=>$&Z4^n+w%s-0meHI`1sC>9rNH0J1I|%UE!xo0FSBH<Z$L3bXR5'
    'xdDL~Ixul?a>^Pvc5C)fDq^Y9C_>t)A1Mzg2vFp8;xf}#ibydiC`Ytp^}oBa(L}$uLCs(@y?E$C9io$&8XmF*DH{Z8Ll?r#A01Av'
    'KlhYNs6}dN@I&HqDvIg-gC_FB5G@5rFP_ui47})%7@TnzsKv=L-NTm+RQ-1nt&RR!p<l<c9ANZst?skr!LNE0C7dohbY4vHZglDL'
    'vZ5Sb#$@K0p`Ftgm=cK)s!ABNRNP+L70ygYz@wMdU0&vt@GSqi(CeK$-wS5(xgUoX${<>(k)o}mOQq<a5Y5C7ew5&^^dwaLi`yT!'
    'D5pr27pBXxz#%6)k1+2*gSkqO<1{AFE9#XNi&oiY+C{X>E-ty86cTg(zDQ>?ss(81L--AFq#F3Fu>o=$5{3H|den@>fRFCjzb$wo'
    'hFm@;PRL&0HL%nGd`H@h0|Y2ed^b}K^ryNw6n@{q?;bbbxwT_Cr2)pAsi}KDZNL#QeyCqyH5q{<@UAB_j6TjEHLp+EN=)CkdW+O|'
    '&qu9Zljt=PCqN?+V95ucwAh5Ii!z@}(!+mmB27<MS~R-nqqH+ig!$WwJiWi3D^IQAHNuUWKykgJ%S8VgEP*gOjwVhZr?A`WRy@3^'
    's-Gze-v0P<U~AP;MN7=lrKf>t2l5IKx?u++4B&>wO6P;SatF`P+n2{p%|?RQ+H{lBxU_M*gxok1%axod)<X-1!r=Oq8>xB-@MQ+t'
    'Yo2&(MHC$Y16s%t<R7jbe3%?+2c(8;*ABY}?w8#ug+J3C%V)o{Lhe0kHUz^IXw?2RFM!v@<U^1`k9i`?k85|c0LGj9M8mz*a)jsw'
    '#h7n_Za!hnDj$Q<V5fv+*^VH|U~p7r)mvE3LDjo}QV^k=WdfS0X1#@MmC@+5YX5^7@gBgm+Uj@l|HnI^bMaVM5|ZsiS^*=mL0-%6'
    'j0%7wp_X<!Rq+VBfYxhQyJSp<Z*;FVyYTX`{j=)X1FLFj`c^<E11S$Q9!haKC$oiK4wnf6QyTj#w{ZXbviS->@*y1xuqHjlNb!j7'
    'pLPk&eq%cl6Cj;Vy|osO9d9EwzhEDbqPgCox)*pxv}lM55Xaz<4mqps7gaKei(rwHqps;X^J_M=08AClXo2CqbQ>M|{SfK=qL%1U'
    'AtO~tdWA{6t8Tb*S6tkCm=TBVH~#kZ?=B`@R6$TvW=jq<lbQfBjdWyDWX6eZSClN87D9XFeohF4`|&_PQ;n3ipIxy(L#hqLU$Ubn'
    '4}Guhd=G^rVdG(yzhk~Y<(>L#KdaUI!ODWb5zvmb(@ZS^iw2bh&n!}d6H)`oclV*I$jAG6+=XvdAGe#-!=b1iJ9$2!uc4)4B;=PS'
    'DvPy1=AT3D!slwyZ=Yg`eMzM%Wf;LM7<B2JQ8}9+)E|VM8G<V!)G$<k&(GVivtRP|&!bTP1^m1m*QD7Yp(Br=_o%X1bOF*yp&lT|'
    ')F5OX<Fs!5zbI4H*9v926Wx^N5v(!wsi~K32bBme5xvn->^^|9bsO2sYGq%)31m!^LbB1Jpar6H9&lA=H%MX-$(RWND!@zaCirg^'
    'QDem&Z<SI-sgMD|W)FpkOO^DK^NFk?C%6Q`QIcM{gHyg!{XC@Tpvo1@g$S4;o<2Cl5&7%n4l!J3A+=1l`mX=J<8L>MrID)DLUban'
    'YUti|L;x=eTcebpMF~sLNm1a4RajozS1vg7@pI^)Yhi`M2Qh=K0f+V$S(Xn8ER+ia#Z75J1T#PWBUMSS=(&S3=!56F;zj3K8mAV_'
    'Vc>=*(=(vg^dCw~E>g7Dy1bwho~59e=@FYmzuz_q#uT0aGIN?};PRIML#Y&S>U7d{p1_?9fIHlZRvl}qZ$v<3Edl(!KWVpvtzB&S'
    'rMq)GSpRWz`Zvf79xB?d0!=x(k%}D~j1l6C41g%tdH8UXIBYG1kJwzZo$Zqvzi=-63%*<X&GU<Y<-%Ov6Ct0=7Z4Y80{AWf_Cz{&'
    '6J|)X(nrB~9&Y|kdy={hy;OSOS}HNuFfEZ5VE|qLx&xL9(7EvmLVXWR)AeGnxsNQ7R_y0p`-b!&r{nhV@-@XB2!kE{2xTwoVBJ<o'
    '0QoxT`0@csV@CcP-8H*<;OWrqO{LJxTWHjz$B}EI=7~Hg151b^gjSpccK{aPA?BJrJTC1(S`wu_;LRoU1%wBHiS!XXj|-bKgJ~A~'
    'Ar?dX_3@fL$lixN>|@2VNZd@F6i>LGaZ-TWVaLEZ!4d%}LmZGZ07!)Kntjk3RW<(nLJz*`a8Ps4RKh3?__U!I!fYhv$Jv7&(Jq>@'
    'ZmnUy>ToPz&E|A(oxbeL@2BBz9;gS&USV%}fn-3raF(D1zyJ(7HR-yq2W)<~2LL$l=AVxb1yUW!4Du2Ph}<U_0#WZ+{J*HuAT1H{'
    'xlJkB<1g5X{_HYlfW^u%(yvYnrwl(L9t$xBVl2$@G0nocr#M`{7qK!Aj>A$wZ-iokej9005QTtk@uq-p$!ExDCVWkxm!x#fMh@=r'
    '8BN+j{NPh-zeL>UZ@?3&u<$sTL-H-zex~A~h30!mfiS8$H0i3?f0QykR#X61H3zWKNKbs^XwYAw58(h3VCq^>4iI`UK!439PRAoW'
    'P>5aL1N<?`L?YM`#{>bK1pFh&FOUz-a=>+XcVqo$6TZ6RtBl4Si{FZP!XVk=DAQdg)dp7q=;mgDjLP>blR)fl>ciQa$>Z5N3JCXW'
    '0U>~p0Kk>#_l)qZ)Ha}933~xa3pPzW4nZnYeGog5U{ANp&Py#xGgU-2_gqMlpngKzCjF%4-iL`!4W1XIMrxoEQ>n?j-q(Mtis9i$'
    'cu42GEd;(0<!{HYiyOd0D%WMwAwx+R8bTMB9sNW=P{;zheIRkr3j`T3?icN;!q^Ma2tIm<@a1esm__;@fW55#bf$s^@PT1C{gMsE'
    'Ev|dV0^_|!!XD_Q(dhNE`5HvD3ix>@*h3sGSXWtP+%MVDKK=8h6!Rf7>*x^S@bkjtQAs6^KzvYE?b`{-Ey5T(-nyZO-Tn5d3Tqi?'
    'lW_$mUC>xva<W0IE!n@=ve;8{Lt1fOZru^+$3Ys6r;w@+6X=Ez+@+65x0E+Fn}I@w9-_zI)=R+5t#tE~qT%?anl9~$_ru$vCZXko'
    '1uNkQYgQ-XWupuaes3nFNb%M^9nz7T>K<(O$vq#w?h3m?v}@rCg6z`o9OS5?w;0Jatr!+j1aT<Zzid}8&ks9y8EVc#;VIy;5{1o+'
    '4+y0Q#GDNAnNGBjdI(K+Xm8!qarZ4fooTa|lPxe@v0?-DitEY75grnapyMEanmYvVt+wZ{-cXEtq4E2a^lv;BIf7hUl#QrgpuB+Q'
    '!8@H~XNOq`oW{wvT(QtruH6p*K#hvc*W>ZIDlice>6^9-uL7?If`Ntg2_b>|1&$>yR0H0vX1H}jhp^v1*IfN{wLI3&c$0*l`Vx&Q'
    '$sZsrUZIrVxPwSVO38V{hRQTkdL%{;1XPr<B{QayrMku*0f`pAkz6i_sCs|(2OoEjjySzsAAfm$Uyj#?bLvpWz`|8dv|!{2E8*Ti'
    'e<fkUW<thJH*V=+E2(V-T1S~O*@UXu6aG-hfMP|EVT{zKmQ-<)numyFf5m>NYSOl31SAK$*n{P9L6C_cZG(NK4-FF;2xhGsg0xPX'
    '8#g356aI2l5gKtHObG}+4c|1FE#(&QCVU@=@^Vj$WYu65-L+dfF^=B8v3H8I%df7NOPQq)hzWrsjYbnXs&7w`gZG9<=0$bd{Hkr~'
    'uTU8)ELllOcx`gB!ovw>GOWcgf&}6VHt}{rCQ)*C(=XarF5BD4DLR2T5*?)_vT&7Uc2DLF5r<d_8i^5oxN$?eRV%ElF=kOX%CKHR'
    'LpjhB?TA^uILcJ$Igpan9x^xX=EQQ`^U)n)Ko*r1uv{S=l4@9#tmp)gUK#PasTOgVlXVgf7cfn4+|~L1czLRPSafW`Wyx>3+Z`n='
    'a|7H2PeeEm5IhWh-~?<+uie)D?zj`DoP_(lw?eiJkzIn<)S|w&VmU&ngh1gb0B9|a5anQuULC!KEQpUQ*z)o>=JDPj<0mxJXce`R'
    '#wwQ^pBhCIU^4AZ8sGWajXdn)VrO+SkGhQbSUHiS)q_GZFB$+Y4QO@LM6|s%cY(^9$bG|JR1BS8(m8xrT_wN{Mwm9mD^yM9cyvPK'
    'S{f0&D*2O*6iHMkw{2_@QOD&=3%g<~LJ1n_A%qG1Y-cFILBw(xcZdop;?xRVz@cmRbcRL#dQ9al4Q8f-Wj=%?aiAm^E@V-6>C1AI'
    'iIF<g=K2DJRk7PUzrRXw#FE0wbVRTn%?X_CacUk#wMBjpGYzV*$mUn4B~Lpwj)dl+f9Hvn7{7-54BmebS1~O@1#t?J3=0Erjgg!Q'
    'FPy9EkKK|(p2{IOvoD3Hh@u7~28g6a#$-fk_~Sw#)Obvq(hvY2)73XD(4vktH9sM{4yggMa<WR6{+mdEI}S~M{Q-)-fCm)wY}jYM'
    'Wk+Xgh|Te<T=y<-2Q%PCeF~N(S(HoK%=&cwV4AAu1v>^s<JGCrxg?_wB054iERznT&E;E%eGg_elW?P8;OHRtZs{JhWRoLJjjQjm'
    '<tB}FcSp<3PFn!8HXQTGU&$2#scFg6&Bj`b&KG7U$X>4B%W}sf?Wq0Q5hYr3eBKRJp$%Xk_>Uv{pt45mNe6@cgLxmrjXV1OSYhxX'
    '?+{QI20yi_1*e|Kp<!wd9$RURTZtsrE?k`leV>%LeixcnO7FWy?4enZb*HfxEIr8{k~>S)HU83+Nwd3QC+Sb|<<+pRwjE{hd7NeN'
    'z^o=5^tz=wWathzEB`7&g@D=JEt}ddPbbwrrr99h4su0?SOc|19(XXWu!yrVhyeqUAxk&kwxeA|J;t~nWo2USGKqwlNAP+8%uo@?'
    's0hBfBI0;G<f)w;g)!{*1<IjSvfjznVT8PmcP6q&;&V#mt*t7<ED7KZ`#6&ULrHH4%?@TUK4oC|SO#I?8)*JuAJ;{hqVUP1r1j~R'
    't-Re+M8HCx6R4OmrUc;t<weFaG??b#TS*|~lu*@koAZhPip`X}g8*Ps3!zu%s~&~G(5^(a3jCvqVN6uP6D0W?HY0gqK|4h#ll(>Q'
    'df58)oy_)vCc%*^!;T>Vb9fN=aLX=^a_iiP#8t$iD2LS&rCCinMMBDc=o%C5K<q@61Tv%Ixh3|#<q!!@2pa!_*%SU6SnV-Z3oiOh'
    '!;ojfTcfFBEtw7hnm@`{r&)jHo|~nySrGE$f{h*#=pAwy*eNecbDwBiP;zpT0e$37f6XPygOO$eEak+pEr{P}z2QD+H5Adyiw&kR'
    '_!Czo-!eQM5N9&1`rPXI0V|$YgM;Ni7kk@el1}Cnk-Q1$lGb1^Z!}LuHIvviYKUQBTu*s`PkNHT{@kB<1yQOETHtuoNP>9>nqo&-'
    'm%y2@n4rU9(Sk;|rP0u@fGa-P*HR)>?+O`w(96Oa823n|#B_GC^1vFlm606{=a~mM+N*bUZl2Wchg2Ad(j!}-GobIB<{QieIQj@H'
    'xuj@jFzCyetM~JsMOnKkl0J<aRrLf#nXZ961|?0`M^85l)E+yV73tQ8o6<k4-_z3ih68}S8~QkjDZn9^SEJB~M4d?8h+5uUyQi>s'
    'hp*T|KJAXKtp5g9f;%%yLxE)n_$efE*}q2EVblu{a4GoO75un=+07ZVs2>i*8`Gdt=D#uhPho&8v_&M2_X=L-Aexq9>*^TrGwf8k'
    'DcK4|*b@lq;Qeb-8kYDCvy`B9V<k$aj3n8`c-y8_4OiRs;j_}^lW8Eyv5dhP(}$%`Ly<fR2bXTB8?N2a8<JAJA&gyH9}u4QN%yM8'
    'I5iANBNs%12$PV1PL_Q2d(*>l2fE!W;v@BLOLj;t+{@2^aiyeR^h?Q8dkp%i)wx&ZYj<=mKgp+F?lml+0L6nc!DVOmmE23Ppn;s6'
    'HHx=W<7=SWLSltba=3Xrr*_V+{(7VLCf7|46Sz~>HOH(;X(y?6fC|Cv7_Do3x^ZVqZ=iNhnl;!<;YDu_p#vEitraK>RHIgaIGN-$'
    'emJgY)t(MtUye!`>+chwQv#BaT`SbC4wogGJ>0wyhfqOLY@qp|c&*;oc_YiwKD<WE@Uj?5AK@*K!fh`nC){2Mn1wosL1wItYbbOR'
    'gtzpa0bgvEcicSRvZI~<our8>m9Po7_$d~QFl4BN&J{fx=KOHq<Tpkr2M>$Vz#=~8ZdsEseXysW{-~H*GEtN_HOa&tCnF3pKw5BG'
    'f-i|t&EodUQ-s1=zoUfhce+z6o?P-@^UKR<6crE@$_7wDIv(<otdIaQHUWNnU4K}2d}z7y*=ElD?(>s5|J}Kszq}Rc=Q4L0^Qf3Q'
    'CkiPeKrN;$Bp@(w=s!cPT|syLWGltgp9=zn1!lE$KGey<tBDFRUo7xeK5H=cZT)w3bRLNEOfX*lv&g-N0<%@)Bk)?}X$*44gN6qp'
    'mPH8Am~qN8+yt1WbjvPEPlAZT90Iw`aWoOvC5=mKHK+uGNX%ZLCgPLR)Thy>qxrPe2aKK$^zFg@SV-3ejhT4F8o-UATrWy574rb@'
    '1UZ2c8sNRBc3(k;I_(1~pWC0U?oKL_Qhkiv3j(I12!KYGBMg`}1Srj0@1TNXt3J+o-8Qi1-t3*Sz|Fn>TI!?A^cF=;RH}?w6G91y'
    'Yq=3#%g_M&GmNPw`<d47g8%+luws+9$f&shaCQMMV1{_X6tk`x__N4<=`^@uShx7;73dgLy$4to;Eb5iL0ZJx1aDH>QLw<_G2);u'
    'Z7xFy?FxO|S!N~u%(<p3Yk45WA~ePf8}_SbS|&_y+Twx4g*ul%h5ZhJu=ndWafUr#4?@9#jzT*L`IXT#qeHT2c@*6E%7|_SC=GYO'
    'Oe@bLeJ7lr>ZE~2(@`R=I4E~`W>LpNpzhS<#e0T#G@?dlU|3qW0|+H<nK)U`4?t`T8IaJ-7b!zUdhgurh*XG^8Zd#e|A(e?7q_uU'
    'Qp!>gZ=^rK#R8$uplbpGGBq{98w{jl#0TD&G50H9!#PC1djwS$YIs>R(uPi&tgG<Ih_*#o2Ic`}Q~YSSNPguTp{L~umHI*p%cB8@'
    '%8&JzDl9-cfDUGU(V-2Z)Nq?(dVyQly5(QCWO~PA;V`0Q<JaLCulo`hjDC?p4~laI6c&+sg8;iOu3r1_$F|g+)`VP<Kq(8PjKv;8'
    'j9pD-qSC``1nApH3thdo-04rWrbk(qXl_CBHJ(!zlcg5stI%~47yxcdcgBhH2rz`@w$TiQzP)iLMQsq1)Gz^<S{S(UAje5p6JenY'
    'F*a)P-a<*1tzW+lt$yZuRZ=S$@-w55Lfxnd&p<Xf-*I2aC_xrro$zIlrxh<plAt^BxPSbVO5l^1h+YfCT;#*y_s91!X;b=NGMcDK'
    'Vo-Gnq<l5-oKWfx_WE7@zS}OkibdnG$q(+nV9Tu5Gc9tlhoY1Ma!b-hZ%_%7d&v%lAz1D8J38q?VS7;K-j}B2V5yfiSQ(c;LKesp'
    'o?=-F7?Hl|s%a(zW8dfNw*zZ&hl2S0_L#kp_fQ)OP!1hEx#V@7bSC(S(cR;+V-DM-aT!vv_IQ(&3Z^80eHqo{XkYzV7!!qeMW+DT'
    'ArBhySmBL8=HSdg&jC$pG-I_b!J_F;>cpiNUu8ikWwvm}rQ?j{As*8N*k*J~w#~8xSkRBIdR0D)LN>uy7=19BfE1-*>|}v&#EarC'
    '<twFR#<#yzs-Ig-|6<gITj#fup-mPwR;dKehoA&dF<X2kB11G07QoJ6hBdS&Q@Q>LZ7vuDYPu?oEkL*#U_|cr)H8TPMRh88>`1Iq'
    'lPgy|D+FHEv^BjprXi3Ka7m#v!7LE1SvM$qM0cjHO=y>XQ!$r*-N9~;Yy;G<ICX5)U;zqh%}dtoP1KWc-}^<VfQu00s2G7;%-G(R'
    '{o|A_?nskLcI9}`(a~h|1d{^jyy8UX#kLo7fX-qfVPoVi%-71Lab)02`s>k)skyuS(s4eRM1<0~?;t5eClfrBB4C{`O+cq8s^hv1'
    'EJB{buq&uea3k<(aT*9BAl1rsF3O|Ozz$$2dfU`K@@3+3fryHZk#bCft$+auQuuCa=oozzw$LLAVd`s9)Ue$NF;$@c^EqseFHa?J'
    'HK}g6vp{PhmLuaz8q$eIn(bg)t`SqHgF;dEs&yA+O;5KxPL2$}UnCMzMr4hoARh&-3X-Zr7sC8j(~Fv#RewAML<f=3RcTKnJ{<(W'
    '06U6`Y|=z+)}wW$kD0P)#CE$SIj&gz?5BFNC)kwD$GL&H5$N+cO{{K(j6w0`6QYA>GBiM1F%oLjEDflef2{lEtkMfTZJ2n(<pDgE'
    'N%HVLXKokj&*k+GwrDT%dwTkYz4;edHQ+E@8wH;{W@a$LLUW*?A0-W<4a)HGA%Nf#nW4#tT$D7uE_#|1u91;moV2{XFO>bgrs@C('
    'LM;dLLF7RWK>DFnTcHy<1C|@1a`jjH^4A&Dq(b+p@YM0%UtAqgyDpCyT`*`EzS+Ip9YN`cpQr`r$}KEJ&h15GTL4*n?IGAhI(8y-'
    '5y?<zP*uRcOPst$#Ys_q_`2e`)minjab~2^gGf!Ip~3ig-bt_q)EI1su-wDi^h5XO&sSdg#tqsBGEM+4gavsSiwdiko5J<VRE7*M'
    '5a*U@%@!)2Im!xL4LHbY$uYSy&^b{6h`owMm1Tx^kl$Zn*+<5SxoYz?Dn(u`*P_Lrfd7D#VT+!MjEGK`tUBqTW}2p@MR)N<wjwXj'
    'A1Z&}|IC?~L5fGFg>@XgGiCs1aj}#PLYRhQsaey-iuttSVX=rlRMn*zYtoErg_qH2U@U@x$20Pt;nF}ZVx+WsvZJqE_*qI`Ml=+Z'
    '&NL0g6qwc5800zxNs>%}gRF@fh>H;VI8$U<ye+$Q!i$1${A)n%=@~#?B3hzQ6Iw?yLIpEAK@-ToQ;`$?w(3H5sq%}#9uAKFn51Ds'
    '5tBzbF~eSkAc?&LZ3Jvs@eb=NS5{fEEpw{}`6KX0Gn_&wD=nFx(jiQK<%`KDjO(v4bM2xFkLFcugSt&}pyD$p`=VAOv%>-m&Lwj='
    'V9%l0M$Ji4J>uFx4QYx*y4Ovd=`+-hC55dO@W(9)_KJW7u_m2!+V_Kc`3ySN&!?E|*R8wYu@uYC1$FO4O9qY?wu_Tux2%CUV3@^@'
    '5<|%)h6F8EuKlViBqh7NEEgdohcvmAo+ZCtyc20vkT^1q4_$^q7#63>W%I+2f@2nQ55cs-*a^s>d*nC+mddpMNqRjhRK&Sp1(nNf'
    '<6^<&zFiEI89<#jzJ_Ku!XxOhOe#?)fL)%plie&SVC``_HC&$33+3YFj2=84Gz=J%_AeDPet+^yM!n6LY`8O&6r|X*t6li_m&eOz'
    'sF$swW?!RHH_{^DH;JHkP+ltoM!d*0zh$Ug?=*yLb9e-SxcGqS;y6h^rFZNwbQ+ikJWJd}N^F4Q6gNl#a_zdW^xN{QHIVEC1Yl%I'
    'u;dV-i~(z*f+0eRwvJUhGcLmFl`A6^pDdjdSO<w8ZAmd?RNB%0W~32JTjboR8gtPP`)&Q*?pvXcxio9J;IX2grN8lrrt#IlrWR(H'
    'IKPbcu(eS_^VSQBC_WlFBqPY?;zO*4&mK1ba5#~I6qf27-nFe=@8#jRUFMWtE(;mGBoA8A@+9B|R-4tr*ZfVuc#NBA*R<8=>2>gD'
    'b}V0~`~=V@G$r{$3sTl7D3}DyQo&^pZ!Rzhs%BuH${oCONUmC*aYm#!c=15^#Z6Uyv_kLz^SJ$zP#Ah*Ok${9{_Km4v--pFYXJ?A'
    '*aJ^m92L>Y(3Qk0iTafIOdk%{{T?DaQkBYu4*__o04jmmbJs>lm_c5scwSn;4wMHlu&7WKHpgzwf;{8mhYRmO9WL0580z!w&}w6N'
    'laseUVGBteI2+gDT)nQCRA6}(05!0o)Vh?zK+&TR2ssTC!EmTR289}%rTtJFrQh6(-WgF{{^_V8!Z2!<2cI%08KFMtIM69)oTH92'
    'hMZt)@8A<=3rPM0p5wPd22U`=uT0!5pa;#XBBx|tc_zrP9q}gdf2hr+&;6Jsze)w!tCgW3xyK;KKN?ol-m-ID2%3lpiJ}yYskUS}'
    'HMuYUR-P&Lpc&U8CL&RD3a4faCn*3ASNR42P(Q>~D{kP-T)YoKVDVMN!CcdM8Ck()!SXO=TUGv;=?ygQke97n^_1~!54#FIFGGS*'
    'fAbStNvB3Jdej$~si3$_l$mffyRQ0oV_kMy|8nMo`yC}9E@enR`Jk4sY7uat@1t?c5oda4s0|}8&kL0J@+?A2p(6k>o5zYhv7Gow'
    'a(cdOY6bcq>XCq?X2q7;o8si5SywXfl`_|>gGRPwmk}~FMjKId7P%F548Ft3a;_~`PKJ>(65YEBcWtI4iABsg)+~XAD9+tHXf}yN'
    '7-pem#!_a0D)8yg{pk&V+3;7a%{K+o%q;F6?Pm0f!wA}dnJYG4qeil*T%v|SJ!sY}{5q-XJaXjnQR`*ZjV~QH75sC4E=Yj94y*=Q'
    'Sd9lKj<@Zq_0LZIb=LJV$>PaNd<T<^4(G^>9#LP7ri+r71@zgb=+^hs4$g?ggS^c5SigW46g)cdy_pb~(GbD<4xThbDjf-<(LFGQ'
    'LEQXM<R<*IhpL5n%(VBtz&5ls^qin-@nNgQN{<M~AlV#u!LD9d|8{{Ig0Tj8CK(GXMoMH%NP%=|Pa%!K0!Rcy=His@kkkB_s-q_B'
    '9H#wdfKomsP8>oaWT@0TX_n{q0Q*_g^}>qJ+h>F*r9_O<Ntlb*)JUrV1xxwQa18Pi4^>fZ<g(4tM`J7BUr^$Wph}==YF*cfoe^d7'
    'NXMLNm<$^L6KJ~F1P}_maxx)Muz1-poj?m=VaN<9=#$l436Ykee)-}@bMkIjzLkX-aOyV|bUmPwSaDM;l6CUy8As3T2Vxl9M?y3p'
    'J(1EB{e};;s2|<iK*qb*pZ#Y0S3NWlZMTy}f<}8;jkN^@!AYiNBBVwT^bt9WFSB85HdHfI5d||2tqAC-=1~)k8rneJM_LS?j6aFS'
    '6Tp{gZ`w}XA@K~0VkR?UG&m$`?t{3Y-7}J<bZkm@Ojp!dU*5?w{_)vu3-bs~WYQRoeifpvA_27l9PY%-PUho?iU#+q=o@q13i!He'
    '-x}Xs1`jg#02gRHY8mp#WrCoo5yIf5t%9~p9O_-DTllET7qLA<DfASIr3r0cFP~s1(LXKeNuqxwdQ4{FXwH&0#IbtqMS^>}+S7i&'
    'jG~}fSh6t11{=bVhfssPipU*OO=GS`70d$%cqZvW4ZC6!D=ADfAT#y@nm0*tCbS!Cu11whF9;gG8>XG*c?<7%@cWB0tD2wRCWfY3'
    'DOlxv1@i%ZALm}kf0Q0l9do7$tXX`;>7xlei&eC6Kvlvtl0owc%4-j-ly0E_+-b$?>y98YRDuwN17adfBRl*VL7{jk6f_!l9RL*>'
    '6;!(A;i2cvyMgibgNb0}1J`yEf<r6gjcY;=J*NhZ`Ya&_L;+yHuyzCI6tij;DqsY2kAt*t0ZIsoKGVu3Wd?A6X8KT6?rm`})@NI&'
    'pGU<9Fv_NeBANyW2?Crp&|R`GuPF+48AD>$Zlit{YnJMsc*FlittitW5MCfM)Ll{C8Qgw)^=Pi!!7EGWa=F9IEoc!i?npY3PBDsB'
    'I2rUdR1(<Pbm{=RB3kpeE!1^CQ3zml()t98lkulqfB?Th&@2oBO>0sFWmA-r|Lf{MQydoqltStaY9faoCXE6FLlmJ!M((c$l5{-a'
    'cif3K+_a4frX^e`GY6_|a$%b7ynSd(h_&$sG#aA8gks>@$=tM$>d~x>SE2fvg<WBRfWuQOgY;P`G)+8g!l;XLH?7``CbVwqMt<pX'
    'z^9Fw$!NDGpmCx$u@b9ITDO+!NS<8W*{k;evF9n>m&KRhwLE{R*;*OTFua6mYUJ^dVKIn6tKLljLq!tAhZ{J^%dT`^(1llugzAz;'
    '$Sgl((OZ&CVzI7dvJ0+%V-wegh}Y?wRZ|36W?DoNjm&z}LO)q%Hi5XIXBnja469G&>lUh~)xu=UknOFsG}Mh_zg*+gJ+g$>7+w0l'
    'nzwW1KHdhyRymx*1!fddZZ$@`l^c&&I!R6e35YH;oHq>tZQa_<oO=4C7XePvM$@YHg%06J>OwIC@(s`o_DOFrNCMDkoU?OKXi2QD'
    '-G_!dJS`a(7gcfmD82SkvkjwZWOPOyx>(Z=gHqf)F5UM~><@pkms5t#j-DzMcyO{ZRSkuO9PoKHR9<i{P$WWpgoeRM0uva`bz7-n'
    'kmFz&Gz1a9d%W<t=BPr049uavFt0aix;C)l+Rz0;kF!^)69RDy?l@f#Skxr+)N=}zv|hOA=$=D0qW0>;+NklfXkk+Y{CI@(Fx0>c'
    'VHqP>p*w=dHS)h+-z(H|0ywBwzj7;ehFRPWOo>5{3L}*s4a)IZxvgw}QSbBZ#G&uj=GysTd;gWQ@N&LTA7O?T1P$OXoWfphRYo6x'
    'A)<UUAVZ@V*-VU}p&`QX+AQl{VBeFhP?h{{@}AFiTU2upB<VEMXa-gvF%<)gA&Rx6fkd%Z^+@EeYqvrahuGkrUY<E7OD(wD<-!~{'
    '`UrHBNV6axK^}#y&4+<I6>N_NatVFXF2uDDg&DO^A6+Fs^|7G(^|D?CmE_UGZJ?)xsT`i?;M}x{#ZPaGDDS^6{jRyOypT0!(2b_a'
    'Ny4v@CK$2O$wTP_eYZ!#Pfv}wj>o27`^iEeU&kDW)k(tB7z!T^4e224X?z-YKDtF%O@s~6VfyR$Q6!BqpM(El%sVDdpwO*IuUS4W'
    'OfaJs5hoJb*y?*kTUe!-=;ZSZ@{Yl?(I5jnX?Z%LgreN_32+xi8P(Ah`&gl%U=a`*+{T29S-9*Fo|#e95IHBs61%wnG~tR}RB9RM'
    'J<(4l4@PB33xZ+0{2$8HStTo`1578v`(t&Lc9QsQ&XT`Ui3SI1M!Zjr3Tj6<jSSlo_ZgZwEea%&rcV$U*Y05*37bL~&lREtUnVyz'
    ')HkG-jT1+B&`2UE;2e(C4}$2hxCxzGq~$4#IO4&)1~UOcBojvEAuyX_n&Aw}Zk)W~R(~LCCd~)6qF_48ONrnB2MstGr6SC23S~_k'
    'w!K@O{+@ThH>wa?HT0TBG2%36>9i=}mk`Zy?_!b%N;%n_MXEO1F70(2dEPA{otteNz7<?205G7{>Xb@0#~YwP1?h&>MbV_0^I0UA'
    '>AH<9JcXJU(~wl+`;f@QaZu9iH;*P^(#aGjCxN<a>f+jH@uc;IEsC*$d;mY>LjgUYv)E{AAgo31E;c|T9sd!=RT$}ZMf3BkKb3P|'
    'bzMUn^%VpWiq!zRsur%O_OPzm*Pzj)FdoT>%y8Xa*0#1WN(6E?A{#c?5Foju4T4N9$r6KadXTSoJNoN(bK=reZ3Ipjq$DmixZq$K'
    'b^(ExxoV?)wCPP5@!?m$qD6Fi&d)2wr=SZIikeQU@yakw{m_dG33J?W^Wwq9(;58QRPcElc5gc=hgEq+l7_L42)2mX&{y+-jCjAD'
    'qzZVsGS|&rvy0PvxlcPRbV}q<1{uS9!Qh0!8~7%{<dTvM!j1Ul<R4Pfm4{4xxQ%l-!M#JH9JWs-%!Ro++^saENQHvb65KZ&Tt@#O'
    'LxLWHn1eQ+x$2R;e#<M!G4v|%>_A768x1NWo>DwnBab7KQws;Z0Xtuvw=dgyN20BUNa4IuOj1;n1JN|2jTg8N87{%)i}sTJ1=$W='
    'wVhW-b4u*{8rjq+3WBKH)N?&707j+|P$>6RfrAmz;ik3cuKI?~4By)4Vl)xOH5lljgrJ?tbqoX)C5WU5=FrI2x5;ZS<-hJ9Ne1e0'
    'I;;e#XW5JF1A$@?p=d%R+G|;6z^wzwg;}*WZ{+Rxv|!n)^B4<VEGBgI00_Z?!HWkjNWhg0;S*GBNY8jjK>K2>&SckbB;qCd_Aq!='
    '_uIv3pveB=i|IA3V3G(O{v>Y=!Yuk#KnZ$-K?<~SSi2$q%Q5m?(**-~Ad!TDuRbKC9c_$ZusjYJ!$H$DF~lL>tldaGaabd<9erO>'
    '?+J4__QHRIR<l?oLAdNmuu&tdjdI|0XP5cFG<U~TfWj^mM)-;as3Y`1cmYTwn+*%86*;DYKict?ySPB@{i)34rkQoi_5$>2c8sbq'
    'W?J)|tgaCS%FQLO{ZLfj@_A?yWoa@4n(+vEiHMP8KB`F>_}y#l8<v}-B+L+pnK!LPK+Y`N%~|>?_n$&(18JMHILRLigwl$D2xrA;'
    'FgF+gCdz6R&nvfaR`I{?rby7ChhX5X^;UdC@iDklFiapraj2_l6as96r+4eOfrGB}-Q<U-I_q-SLf8gtPqQSUzRH^&2F;)W_I$Ij'
    'm%!)vXos~Q=ZS~>oC=}AGlrdRpG>hD=4%l*;R0j-H0qY)T>#(FmyPzS)$3T$lK@jD#J1!ea#F-HV<Z;PGY6fd3(Ec`Quwv+VX-Yc'
    'S(Ma3*&^p;4kFG!_|7o1j*NZQrl|E=P5p#^F4{(E7waODmjy7B6cTUPX|6J=U{sVA&J5K7BsNN0_$sAU-@G&4E~)c;p~A=`C$>GJ'
    'er%&0T_t*1w4@FE6iLDm-v`~@zIycvmpDFd7(s9-M+Pke?dioMq2cL63Lmi1AhF7+$j<r8ETlgAF;{bd>d;`NPm(n9d6D_|G`eB5'
    ';z!epk3FWM&F?wPe0J~t<Q>6;KVX{(^^UnOEjKIzu%HR?G?me@qD-gzJWO>fRtGk05OKn$DMlX#uOlv-hz}m4GAOvX?1RX&gx%r~'
    'UB2PE9I%7V&4`xCT4vzR5S`HjEmJr+zmU%u4kr`0xoSnltU4tD0(W?2+#((<ooth&Z(t=1Vl^TPHbYDMr7wz+-z{4cDHs5g<o7se'
    'kPr0<9>EMr)v*QvLh=ry2GpZyHTiB;ILYcm7wFGiicaKtBTGq!wsD-$JrN@s&4s~QiP=5Hn)ThPl{W;M6l3uea`MTd!;CDT2M$JA'
    'kIgzG4nQ*)u~Ni^|F&?&3@5m{*vsG~8zxO!9bgYZ$#5VAJ%#eb8$jC+fbiMUr&|2(eZqcsEX|uIFD47ph)#?uK#p3?<OatIx(4v!'
    'CQkQsl|Q`^sVVbr|EQiJvJm(1<39@eBVYpN$WzEQM1H!J8f?#`Yp4!JL1S@#8$P$PeZStBH7Nw7Wa5u&s8lBS_)mb@c<vDu$bCse'
    'NRsguR=u5ZWm~cA8SgKzt&Svf8IwL8bcD2DWZT~}n;D0)oWPpd1qW;G+OObt#TLLh;E6-SqY9$$C5u!hY051DL3WZbBWY6gr>B~#'
    '=cqm0Q66T-(*EQ3!|v(AF9!dFj|<aC!$}bI&GMN?#3<Ssz!y5g3{Uja9EVkYhm>)*v^hc9K0e0p@17=0O$ED(fmT3DcDWOnyurXa'
    'C|0Q5IzgnLbMiF@^gLbraHrv$|2Y16yfkB|ok7fK@kX8?VgyQV(&<5FhWLY_D<X2VpG(;Yfp@Pz@?$~9PlgaAYD{D1)oGwY)W9C1'
    'QV%$Ts~s^4$${XA=F)27Q|s^U7OcI{l|m~H$pgD->IFKL%s_;;N9919u!rjo#(+!wr*+eTyy^}<hk6U=!j(VSod0C=W?FDLed#s8'
    '7)lHFmw1UVo(+xzGZ@KT#B~6IfseyK`)m_$zjv>`?7kcbQCCwDOaSLb0w0nUeDe_QTZURtvpbnlF<|eb6Qq{w7w^7tPT&4xA?V6c'
    'p5d`n08~Q`5hjxT5k?a(7=g%dB*dL<#agG~n#cdW`(No{i3k7F9lsVZST0uh`6S#FLc(IbzRKv9fp`MQdE4X11?g#Znk3=t-I<+%'
    '7;*PpmS18)2u}n>t%5=eAt7k`6@Jmgd!}(9L`3=eA^G#8HP3%7FzSfy8feGlCI-z5=thOcI7UT#rdXn}1&sMHFMPk`Da-$|Fz5=?'
    'x0#v>XO0W5mCq64Mn}>DRSd0?{7n#~z&VX|>qU~_%Llewz78ryyxO3r(Z0tM5DhmvPh?~G_BWz_d`L<AV7>bn<|r1PXE!@_MZp`n'
    'F3ALup}{(%`-j8=lM7-4+}XKqJq*&0rJ<vPMkQhR#}8t(Ih<vluf}vxK#~c{x>f^W!>6BQ*xsFt4h~<wZZqcQ;C83EZO^+xG{6ZC'
    'Nh-dI*v6t#2J@C593crz9!wFYGC>KnqGD;SRpvx6+Mbzk7<bDb6sry#76E0D=F+_CoD@u$rS>1{r~bC!egTq8#@G@U2FS;ad`mD>'
    'MvV&%7cng6uoP~vVjH9_O{!S&<+;err!?#!paXi&qPozQBd%Mu_Spm;3fPiSNlosv)nbytHuUBnB)EM22f1|>zey|iFJus;KFmY~'
    'SQ)rGxmTci_mY~U0Ork_RjV>KVOyw~yj<DoNFW(yNp1~F@J==wn#}~SgGq9|Y0|1?ix*gsjGw+0r0OK@idC)vsRk<nfYwpWI8E&^'
    'YZg7#;+Jm|)JB5+<>t$92tHUiEL4mjX$X%=eBrIq=WIS(7T(a^@_F3-^97hAZ%+f7D_$<?JTy$)x&eCSg(7EE_!_8Ps2Js3DV;<3'
    '{3(C7at%!c;R3EUL<Hh2mV0nRFn%EoluwEjFW4^QUe&Jt)n7}2smC)y!gauOM)b5%8f3~QFLyu24In##QAKI7cHxS-wM*X^vo2`z'
    '2ux><w3^Xb<Aci=#8<@CN@kxw4Hz^-U(y`}7_yhezVZ3!N^*rB!ZRm`JC%$Hl2$7R0gg5goEyBy1+9_y@m#fL`HrJq0G-;p5n~2~'
    '0Zx;5gmO@`a<u~Kv|K>s!d1)FTya3I@G+U-!nE~_oi6c;ZwdVaeG`xXPoHSSRcNYQ@L0+`q4uGU#p53}j$Hkjh03$UaZO(_Pm?~P'
    'z}QcdqBF*D%CReQBKFR$!Ue+}o@GOhxd|W#Wj^trE-w5KDh*q;+%wlV#b9B$Lc8ewplKnKXH>5oE*k!xxltH_EBqQ6=T22Ce&i1D'
    'Q=Dhc%fv5$hRt|DKzxY!Mlhfimr_c^EKJ!~Ep{3OR3Jeim6|oI8Pn$hCIx6V7(TTv%n3AQ2yx-44WE7u=eYj**P6M0B2A;Q5SBWN'
    'Gs`7ThXU&bP*#dE;l1p|O`k7G{<Bp)y<3jU;nh5(U=?E~wYGV4v?VwuJVbst{|f^l+D67P9NlsCs^xJQIPo%22strnd=@Z8W($W0'
    'Ut|Q;aPpu*kji}6pD8R&Q$Ox<F3IR|YQ+neOo8-I?J)ZMPSo~^R<c9RC*%HDzdAC(KMtZCKED(=pbQx!(n9RRTiW7x6{!k&y%7IM'
    '(1bn!cyytD<#Kq)h(^dYY59O5bE!0mspDA4Q;~WYW6XXdyLUOSSd(@BS>nrqqGO+htrzpFaX`{c4+tg+ivpOZ;P{iwahkP@o@L{Q'
    'LRSX4A-WYhGB_}H5>_cn&>-Sd0`$SJ0PRLU*DtP&p>m8E>S(VSI1)_((J?v{9~|+}@u8vfJJKhT3UkHb0(+!0baW?S*PoZ87ZMB='
    '!5BaH0?qKQ8$cWwrbZN_{fBXYzH7JQZ9hFfYUKm7Qwy`~^g|nsZW9rYVO?UOdD$d#FF=E%%>eiS^j*L9`8GO9>k4c{<OPckKFPfu'
    'V2h-&rJ80C1g<7XL}&rZl&5}i{rToCVc(Xxv%RnYQYmOKeBL5q_SiGvOxdd7!+#BVo#|8k`tqmD4+NIi;C8pLG{2lf-0PoyIf-+>'
    'oYRHvS**IPYqK%nkM4Ye+y%|4ReBG~N*L@Q+TsnDa690Q_Tzv5w*P84S8ja(ZARk?ng_=M{*f1y2u4H41HLkD9h6KQ_L@uN<bwH0'
    'F#X9!o{W)xt^x7Z>&1hKi6>|~keo~3tASVeUQIPeTq+}UnoGx_q7F-P+UEPA!UVHmHm9T2;!vX@p5;5k$hYM)tBGmVU>p4k?xKb<'
    'x+GpQyQZAbI5sjd`2}J<on&$QDKw-RoQVMpmjfogyr})GB-?l%0T@Uy1VMF#qXMBVh{_9?_-TcCaud4qB8Iqq&F{jilujc^C3wFR'
    'y`9`ry|Gafo<W{O#;1ewX?}j#-}_DJXAK&XF4hO5X>|XzO3)i_1nxhTaCil96?dP0SQ1>_oxt^kIqsLZ&CBq_<F?S@Bypw7gbNxP'
    'A302t(8w4JJ5@ml40k2L1BPyE7cM4q8rLBnEvFNcSf?P&G;ch4BxZ*1L*)ouG7Ys0{!}wxu0w*xPEY)_8MAV3H&Vx>(Mv(Hyir4t'
    'II5v~<s$sU5Kay41y>?bgI13F1&j-nH1GxRxfb$7bs0WQ)R(nhEoZ*CrFl|tDTTL1ZN-2#ap_x0GJt85&|#tuEh-cn<TIZi)}NOo'
    'w!U^3FFx2_!lW!~5!^l&Mjs;FnZ`BH2Z%6CGWo>%x<%g<$d|uLB%O_>n1grYEF%)OOe?|q0mJbilco}%Cs(&-1=P|EYIMmZ1K~Z='
    'QDiQ3r)ZGim_eq-WJka)=PRGA5a>rmyUSsmR@b0_N{6P?xIIlUg&svYi|L&R@}Mx?hl8s=T65tM*EHVf4Km-F!-I(%T7+4mdfHH&'
    '9$qJR7N)oGnDWYX3v~w?1I=&Z1Sb^i03JN+iQkJx1T_tfjF~!qShpk`<!wR2AGn;r?huyEVEbe<K?X_7%stK90osE;lvghMn$;9='
    'kwHVHabAI@4u1vaAq^`;hnU`j0LfVo!k@1U4@F>vOrJSL*k5((Wk^j4hL`213rg5)9vT!h<EvLI5{3W>(6AcmdO@Or35P)T2q_G{'
    'hxlI_cEj9YyK2RcCinadxnnP`K|PEWM4Z;a>1)K@q=;iwGIcFFJ;uzKx<wD9pMH0FMkR$RLjxz#%XEO3HUivgQJbNJ>7L;WcC|<7'
    'yyB*eIuqfjQs7(#>`UQJ%haD!Lz;_)4p1Jj?ELYN%EGc$Y*l)xSS;X=LOKQyi-S8lWiY6Qm`0_M)0n>7&pXy1FTZFm3M@404Nw7q'
    'M8FC4s6p4|GzvgLuo@Ml_|swCx+g`$<wOZU4^KDfn<MdwsYs9w@j5{xMGdEk*Loi9=Na0+EWD(la5&F;q(ZTZQB{!TDH#I{L!w2S'
    'q(_!m8r2w;H2S{US6z($+%nK*I^8)&b96A~MOcY)17eL;bBB=_ppAd4P5<kE{2v5G8^{'
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
            'protected-producer-original-default-required-context-v1'}
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
            'protected-producer-original-default-v1','protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1'}]
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
            'protected-producer-original-default-required-context-v1'}
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
        self.assertEqual(set(historical),set(templates))
        if future is not None:self.assertEqual(set(future),set(templates))
        for path,template in templates.items():
            prior_callers={'protected-producer-original-default-v1':'81bcf1933edc435826e2de411a777cccd4dec7c7',
                'protected-producer-original-default-boolean-v1':'15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
            if installed['name'] in prior_callers and path=='.github/workflows/repository-checks.yml':
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
                ('protected-producer-original-default-required-context-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
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
