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
# 1aec5cd1adf68925a53b656725ed6002b134a517 / tree c8efd91b990e3b71e6c97c613846a3c707ae8594.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '65494f7b43c4dc4c8e804c3ec77ab87f0d6f72e443442041b9a59ae13c575c5f'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TSsQS34ccQ-ZFt$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO-_qR4XpQ|CoD<&(e5@^)ELInGnvWK)+fS-H%4'
    '?*GHfACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hm&%K3*xyYA1jcwO<O|$sDSv3}Q-IQHfrJ`)}=KaN=(&O>@@N#_m<J0stO}}ofSWi`3ES_tdcgsBYDW!g?t0k-E'
    '-Vg1&p)9I2R`0L)lAd2aJ-;4a(x*8+riVE_Ooz0!Zn<RM>NNFrK9qf3<YS#xOH<~<IF3a*H2su!#Zv59cWbS7oW^|Y+qQ4!s!rWv'
    ')u}JLY%20$uzZvEbytt?ul4pSpS|3t^zicOpRdFHVL43eTm7#;zTLmSdf&Bkw`6nPcd5#X+%NPcl||PKwN;Dc@20%1cCG$&{3T5<'
    'pW?SaUtZQ>DT|>VhH9FY)YfBO)p<4N?U46VmN&C^z7(n7v+RF<RF{`7mXyuST=sKbWJ{N2S>NYnGq<xJUl(0AciC9|<iL(kmJ=DK'
    '`-7+ac{+UlB|ZFlczFK&Wr+9u_{aOJdazS9PE#>fRn?9~)y<6;+}3HXJHLIYQ{J{&am}iaez_NZdEIJh%Tx`i?aDEm+QN@px^bL`'
    'W?YJP$=WVUX_~HE_c&f&bs3g6o64%q7r(E_`XLh;%CVaI)Kycv4AW3|<yFu4>Gk2_np0jiO*1b;KUQ7q=M8<?WPO*9Wg1ga&12T4'
    'Ww~n2_>%9YuTRHs>F#+tK3@LSU0r3FCp-9>nyE`u>W8`<+RR5KcGc6|&s~1qvtD=bFnmkT0(ZK5O2gyf;mgHs%w1J2Q<LhZ5;ap^'
    'r84h}sv4%T$(p>bswS^oRo8Fh@!Q>Wd{_>b*LQ|f)0K78bosDei%nT%_1FwuJ<o+eI*B<|dG-2nFVA<s|F(=5*B^anSyjz--MS>|'
    '%#)~xUO06_`XWnDA#*<uSFi62bX8tlJ55X34RtY#W=koww^KgmWj46ArlH8YxvZLO$8V2_@~`2K&kyM(BHi87@%1I$&4=O3!}0m$'
    'FkOx|Wj~FBfS%V=ohq+ibWek;Gpn20CpeGAAZ6*V-p1?vcyZyPYnwdf#hh9Pe(vMx+leb=nF|MD8GVVVZFetx`tZ)HuZdZFf-mX!'
    'm&*aDcG%lA6lE<hDN}5!?o&I~v(wn8DbK`*W;@*85Awp7<F~`~N!a`C@a#r)06!0}^Wo+0eB;F}d+|ipbsDO<7{-*O7X2{KRo_=t'
    '7cnt!>UbHROndWg)>9dW<9>LROJ0srZBtHjF*kkXeKhkhikp2`^vg20WhSFbnPe-weKW7p$;**)o`$@eibm#9`|U$L6|JkmF_G@o'
    '-BJ&8RTe3~c@Mv)r-yWZx4xx|JL!wj1DV@qn%l8#7dg-}&P7w_^0B2!@-p9VvE00qZ^MIhd%lz7`;?#lxcho|j$Gy9uClnenx*Q-'
    'EKR~ln`)PtTU4%)mv)%7m8W$3u8yOB>9>tw)=W{kO!X*Q%JJLQ*E^KiTuxn?d_m$^6aVS$yLdcT9>e{5s-K4G<#J%_=Bg{&N>W-Z'
    'Qq(@H>$08ZZfFXhbx~#gEMpz}o3|vVTJ8^DzP{{^wM|<tGOBE->e1Dbob$ZPl}D+K2Q-(Nnr&&v4{T{G-SPlxrDoRlWmYytmlu(B'
    '$+A3>-rLK%vg^uXzIhAMj#;of{N`ZaeSbukvjE?UTB2XnZ=OM^Tom`mM(|xmRpXLR;!k$_V|jjYt}cHpy-%Z!rAPJDG`WP9-gi5B'
    'P_1&ZZEMBd2Tsw;@bo3^z6BNuZ#GP`>|<$sBgw(etG4!$wDE)*`9Yth+uzbDTYb9<#^dY5JZuCSpGoh-k)C@k8SG+cltxY6OqHUy'
    'sj?wgCsgTg+S88fsZ5J{w;!9ntjg5S^^}c^axnKLceBqpBF?mAAKcM;N8RlTgHtVkFLD>Ai?J)xFwAM}eA%j;p)AX~9v5lW2j5$I'
    '`0em?eE8;HJiWThWnB?CPY-7*Arke}xFW`(NmbjVp&JX&%#A*mAKTOJTeKUhb|_U9Z8N40Ml)BcTM3x*a+Lcv4!j*zf8TcQ4wAqx'
    'r`uyA6CB6R2Q|0FlnKP6mo@gy)ORk6(w#P@rLf(PZSAI8ery3+5@O%@(zi(#GDV%(^+i6(MXIGLhq<5rrmaoKZ!1o+^}w2CNM$dP'
    'ulih|jQ80|nuTw>ZRUJj+_POd|2?~UPQRsxjjCG7+D~=7Kt-egka=ERmb*TRGIh|<QXn5bwx3;*Kzdm9Wk3vbTKcJP1~=}IH4gs-'
    'kj)z}G*{++a4SD#Mc)p4zVRN$JOsc{rc%w-&J#qf&&L5|V0VzVl+Q!8d~9FWr$*k}AZLVw)MFVi*OI{@@}{VK;sE2q4y$Y#Ke{jZ'
    '(cScvV7o7e;r@989Z+&rRpFxT`cc}pEFM<m1o<f0&C3Y}sB-=Ap7x{!rOV%k<A0z<Lk?$EcvT>M$W7Tb3e<dP=c4%7W^Tyd<dEZ%'
    'H+j=IVan#AUS$7my;OM`@&LizgLyH1Y-7*I*C(LXbo`p&*3;!|&U$mEC>lJOK-tn9(0Ez(Q33$XXAf-xF@11LkyYO9C}AN?@-<*z'
    '(bg)nWpvLJP?xzZ>IC-`p1Q2dtG{DA%W$}V-2i&Ks+-b~>LIJ@VbU;Z<+d6XX(~LXsVuu*11109cm4A1aXH+l@73Dn<KMdUn{rT{'
    'frCWM1}x*TjPl(qAX%NAqHaF;b-z5lKEJq0eocQoZ9${Xy!_JnuEv!6rhD&5yG5Qm<~}OTmul|PM=F9VHWOKPR^}~CwCJ^c(xBs^'
    '<5i8B6E=-iS@*Dreb@gPq(1*Amv4)?ga-O7prdW=zEIF-GTB;}OCk%St-Gn~_GQ>#Ue|D!p1vKPpVuDZ#bj*kd;N%LbSzyOXPAa&'
    'sWNe_hPF!Glnt|(v+pN=J;vKV9=8I1T+r%?Zs^-;s<dSbp)J~%ZtywFXK<WjvTw~(+HyH`>R=TPUa9>tM-~P6PC0-JY_hm>=Df6r'
    'd0+nY;PU@1-3{}%!{wVqXG8KK{^euQG`b&9iFug@oh|>b1aMUfhMfh$dDT5&VwSnYm1R*NwNsiJg?;73LqP&Qnv`q8z`k$k$CI=>'
    '$C%1I6{8|weHc}%4v;pg)}^LqS7yaL_CWZZ_2Q5Ho;^pYoz)gqInO1Oziz82@KY~)E*)i`wOU$jHn&$Sekx3-<5Rl(#r61*F4qtd'
    'S_LzGj!OHuZJHL!+-Fg__nJ|SI(3+qofzGZJNS0|Ev?0<D`?{?%;A!)wrVzZ<q$Bgv_{eycOzV^SGBhq5B;!z57$MNY4XIg(y`98'
    'zDkWQ{p3ZnesI!~3n-xqO#Qfj{hgsDpBJ@bH$<%sM`=4JE)X|IymJt%PI#Ahm-`n!#g`q=Tn*&CYvvZNuOfE}JGt~&YOdlZc<e3c'
    'ME~>JrT;8pFW(^=*_pIwkh%sI(iSrN&VvW&XI?jUgqmn)#qskB`qb^49$zm%2j?!Iy277&>u4eB3^!Q=C3es0Cv>ewOMk;g_N`wo'
    'C?a_->(lI%e92N5=b<e8K{r4bnqr)@>puYr`^x2T6o#kESkO4SNsH*Rx>Y72udeNBN=5A>OoC%4)0pS+<}K`d60PTNy-d@4KsK2D'
    '72CkWAJoUm%`UmB<rz0@<BylG$A^7@W_<jL1fY)dpngITN_DG=QUO-<m{iA}S9Qa~cuHSjItrEf?q5&C<KtGAHI13_ckxjO1%ZLN'
    '9LIXl6IPL@Tx}pS3^#ljfThb#*rrjZH5QZ3%~iA(L4%8KTQNq642D{*O)~9YdVfODw?jXaK`vP|Bhs9?kt*m`B{`VuQI|0&Fv}J9'
    '(M?%_{z9$k-FW_f@`x3u+c^yZ1rBzCJ2y?}T-(*q>6d>xJUqU>eD>Dw&#bCXGW<{fN)m6dnu_S+ZuIJ+O7+&)?{AXXD-}U&0f>OR'
    '7muZ=cVtO_*^Sjdr8$UCKW;2akGtU|9^E!@G^i4#X=;!H2WjwCOir(|q^;B*`ot-|+8yBNdmGy#?JQ0}<WC+;5m<vObjC+heY9Gi'
    '^@tp%pSOcDvtHJ3<i^WOO4WRuk)3MxiU`pGAJt-Q>aZFeQ9O}$SavS?28~6myz?H0r*FrnyI23-M%Gdn4uU&U#|0iXHB*#-pjM2$'
    'JYUena>b}HzIPv|%Jb8iEAjdHY5M<~JhHv9|JUdw?{DSADTxAW%``XgOzCac;SG94xTlqrYiQsZfO6;8vl&o++wKF~c>@sEZC%cK'
    'tFbLm39(dlG^)r$)EpK5#3CKG56S0(aCGBlRubpw>qaIWo_BvfbK|^915*KtDw5lH!ZPvJ)ZW8f`y*Lmvx9!Mxv%l{a6g~$pS^&q'
    '$krhO6$1iqrbm^{f<W80fq=lsv|GyHXXYQ@+!?d`;jwM-P#n8>UP8izuL-Hkq8qHqfRWP_!Fb41UwwRI2W_CIx0iY*onJ;4^r;H$'
    'xlXq{$IF@X=ysGE#sxkdej&nn-t~XO&K}%Z_nIEVlUCp5uPlksBP?3iTB-*-7d^H4K}sWPjG9;57-_ox_^wV#j~MYohxYQNIu1x)'
    'EpXAh%LJ;~ft-7vnlBF97AgSs@5YaB?V8v%%QJlYK79On@w@0W{SllZlxiSH*F(KF{0+zQoUR|ft(ENS`1o~r-e5-~O*X>3?M>>~'
    'Koew01Hc#oK#A+Z(SDf5zu_A@U4^^g>sFsrlz{C_1pu+_R>*Wo<CHbU6eP96gUiy#H}!n@va%x%q#!Ea9fz_8EV>L8eE{tWh}$h='
    '*EtMYSCd571B0)o{|$RvGo2l6_b$;CM0*YSwfF6*hE+uLBdJy*Vk4y)`usN>f;S<+<?Sr`$5@~sS*Z<Zr~?Z%MWZgD@d!X#ztoLz'
    '<96Qm@cFu{Qold+Gd47j0atZyCLCo%3Dm6-Y5}#)+ne9w_g$?Q<p%2}pey8T_u(K;RgR*>8;%9nrFaRU0%G%rpU*kOUxswbqEIZk'
    'a$Lx$5D->;7BL=#AgZI4_t4I&{^(wI9J2zWCP;lK87-6%Z&#;%ln+xkKsTpBHmaZ9et0YA`r)sKZ6g9?Q7$d5&dD%>*vm3&XQcnd'
    'zg2o+(NO__e{^eCYzZg`@DUa9wJHhK7^GGCUtZ8L&7m0!cs#pMP0oj>5D=YrmWuS&idX^JVS3rdf*0MKC7X0ZmA2i~M?TeO5QwIP'
    'iNnd2HA7oovxluBR+Xj*DZ08<9w-PX^2*>cYb(v97z)ZZrv=>oyLUF4^m{XEhHBA^M;9uIPI@&wvW1ilfjZZP$orptoUXs&Vc9}0'
    'QlY_*#5F`wtoIL1^uvgjsMF*)=v0jt{WAvVe4NzcvdrQB^Bt=G4-&1r_|G=_b(Zx3mzchBpQRCgRa2Dsx~iregDGCNL%O_dP!2C+'
    'GX1=uo$Cv9Ng_m5i9xI49z(n0n<)i6y{z)`GN*)R{rinxZ(ojez%1iZw@raENDI{}+Dcuji2jLaX8y^K3ivBM1S<Y{czQWdPDzwk'
    'rpwC)hg^0(W8Oi7T_xl=Sw86%)sYqlt+H6Oi?quwF1daw5_A8&NoUKW7SPZ~_?>X1GJMuK1GzOx;oeO(eWMugvpe=b7CaF{E`KLO'
    'AbWM0VW|OpTW!V$0m>I&_NsyUR2NShzwdcGe!Kh4tvzq2G+@kLO<g<Mz!4Zf>KCkL84#_p3}uG%NFw`_V}8n3=JeYk-lF>M@g-K@'
    'ljvn3PCz3Gz|w(Fu~<jdrObCpj`;7{tm!#yEjka6FQJ`TBg}uS=;{6WTs^hSYs8J}pt$3p%cOq|OAtoeHlI7lDR%q56`#MWsvi{v'
    '-~ae>U@M}dI%S<tS5Jdz2YCgAp4&l-0i0>9l;bqqxP!;X!|S)ZJsX*Vt*x7s+O>^aCUWChERW<YVm(?g3d2xexshED0bi!kUK_>R'
    'Du|*jFrYw=kbewCGfv$=?LcaH?b_4v-u-esrSNCk<My{-R)O4))NK9eXuDww%?t2)F!=~l^q4zY{(S9jR>1h~OVV)PYB?f$p%^<0'
    'y7|Id75NxOL)E2b>8lo!41-gZ?cT!r9qf7+C<QaR*&?6?)vT_Ntri-cBHI5jBkuvGRqTEj|NnRgIv3wImPE4cq!k#68F{VWIY$6&'
    'g<9=&RdI`5p!HhrU2;y(zv^Dy9jDj(!|%JEJy<oC*0%zkG*TWk9;LX>NnfFt<1!&I$xd$E!k5R_yRZ0>_vv{9*3?s+6_1P_v`aMm'
    '^Qx4XfON{}tra+S-bTv)hJ7GKyWUaVH+V)`G@=6H7!GN(EYbFxqhty$LPbtaT~n6%-?O0=VA|1)4luk9-9|~jKg~M7)DkrnGO0p}'
    'SD1o#RW>*7%EkSJ8S#Ah)jz)d)5XL~6@;47S8^am4hxW})sdyhoIBmFIb_jV2*r*2IUx|kANK-U)JW;@-WB^-NHs(Jl^tbE!#P8D'
    'zD6NQY&@#S-&-yFyiE12$Li|+<i#j(Otd3K*Q+J4Xs9GSvsn!;q)w9W@~5sMKi|){<MivU!##A-!%<YXWq3Z&*J!EaA><ED)Do-('
    'ng25FUHDurj)#YNi+!n54P}^M#>%6PZxjg>VQFpxJIe)EBGjqbeV!i=)3N%z9DaWZ)PDs(FUPge>`3V35qghN76)BGIvJ=3<X8<N'
    '>u9^{*8h_-wfkC8rVl|k)jYx)i$1k_xhheKaEbIr+hF$r%C6hUQ&_D$?cW3$lTs*bbQH88x?u#ahS?2C43SLU5ugHI_HM#|YY;WA'
    'xZ|rxspe221Ht+cg~+8U{q%j3RV)dYU>cO9H}2q+@9cgaq3BTM2FyhStcceKM;wt8b7vujD=VayuG)Rq|913`cdMmQRI3}&Nm`ZZ'
    '-jyQ27!<ZFQhtjHOX#E&IKe91UVGfRVDIqz=+Lzq+CBsl*cv#ruE?^+DZxTr7!)^K3lhxy@juco>6M;4lpzkh>&lB>`p`HPFo(ts'
    'FVoAR*ZL1zORiG1x4L{oC)|gEqSqtNlYW1dC5$Pa0Ac3TY2f<HgrT$*aQ5k>b)Mi(IlvvaqKJ;Q>YE5i)-u80>yvhSs`f6n{?g;Q'
    '9UOmqcltME2KPJKt^u0*bY~Si8;ln5B@BR+>mELCl8>!G_?WX>wsUxh#xKsr_{w+d>F)7$eB;7g-jk5;@&)2TC%|_TuxHk}>$;Ze'
    'hQ1PvH{#}hXiuSTqnAqeuB9#J8q<={A~fIy&>dK6Lg(faM12pYDeGXb4L`F)x?(>+v~Q#bOL{qcyL?T#12Nd?N0hzP!EsxW06HBy'
    'z79}m%;dlGaLcalJssWNv=y4Yg)Ex%Q?9;a<l{l*SVD>rt+)`}0W9Dl`7L|+wzdPcB)0ZYz_Fk&5FP-N^bwxt!uHM7ee6dpM*AJ-'
    'TlNt4KKAf5?|2r;%~XcsiR+m!1>BAugLA?Xfs|ox$Qb|<Q+vxkv__*Ee|*)0-}P~*xqFo`rGcZ3Vu;x&<>%~SN7_Z*61P^<-}G^;'
    'V9nj>-a4J^%kL+1H#h1**(>(e7$6xa7iS4200VG}uO{7gdSLU%Cjh{CH~;*0zd@>#%#fELAi7T&0;zYZJdEVvznGUoUli^0->{YV'
    'v&)zPi<PF;uTCqcj31H5BE}%bVve_|51hN3o7?vitjy=Z$FhOm1d0j$&O?(z6aw4wrogxI85vE-*95&JrCT=gJbZhkNqY`{@Ts-G'
    'Mcnrf@I)0BkAr?nBP+jpQSoS@ar(o}R0JWG+!Xs?LYY4Ar~s;{IlxA(o_Ooi&|lGq7yt>Fx)qcILJtERZ`s7@^O)`xVwd-TKNd2P'
    '8Fu6|A%F`3e+&5q`Dm5{*YWP!{l{kdI=sBeXoi=~vl2XENOo|Pb(f{ua1}ten*|xw`3;jmb~pRO*>{u2vvm{*_v;2ifRF&-O8Px5'
    'zE!jhv@5X}NLtu5c^m<$bo+zYi3EGPU5;a@B{frns5U%qBuS{BXxq|HE%$orbZU5BNR6U_DyFK*OA7ei8;KY`{W0CAbKW*hPDtc$'
    'FJD(TfcvyvmxT@)C85cLE|;BtA`lc=AZ{Nd4!uCgKtB9Ud)i^_g*3uPj|e}U4TV|K{|W3>#h>;nXn+rfVfVLeXg+Y=d)Z*T7bNVH'
    'UYbVl7&c!`5Ur*~_`n|WX<=P0QO5l(J9<k0eBFxq$jtHSh;aP8m^?;O$q~qbs-k_{k=zo-RP9GMbbtJEc-V!tG}>gYz!VoWt4m)t'
    'w7Qc02V0gsr5mye&dW!41pRmpjmE>2c7059*txQ=jXt7osW;Z=jY35aahxR)Az*eZefUXfIDS`6Z|%wZ@pjZCT28G%sLQ0|6U56b'
    'GCcg=MM{z8kM8L?y|}5qz;+*o$LFudja?D#R=9$YUH#4`997~i&T`Ev7#4F7#8I^Wwq3nG-XDj{Q1cQfyaJw;XxQ<p0|ty3c(^Nz'
    'x;yH4{r0B#=$>AVzov&XZT51q1;Y(i?4({9YS}p9p=gATL;lp41n)&`Z@hU!^ZXQO{8LKtZ#-;r1YKLoM(P)o7ib>dX%}{O%tCM)'
    'yQ*--qOIJz9sfZzD(=3%ygcp-OhTf*X|eJucr^$H71k$0g8K!>k_%PCyESh<x}oRk>F~Jc>etm88+M_Ph+2I~qbm6W!tx4Lesc#2'
    '6=}B=AK1_~%~X#h4+jDj<y^>&RkEsU_6Q_ed?Q^hL{#;7^MRj_-v)7dy*~c*`o0{mbKmJe8H0rzInj!d6ISBhpub9(*i3}6(+9V7'
    'e+a4V4zy00(p8D7c@+LAWT03xWSEg!S4b7RQ1ggL)!(rnRZTi<83BcZ-CV=+To5u5(l+d?IA}~{5X_2b2x^^XAKXyLnfS}?iqOP;'
    'm=Xv+nKKQuRc?Vd@qG~G!#!=5Rl_RETeoy#9DP4yKPb*Fzq&eH%J`adDw_vsG)-t5eS1X??~RenOLdz4UE7MkqB8EVWR;S5ZQ*3a'
    '!wEAPYjJ8JfqcO_Zx=F2$z67T)4rB%dz)~IP7p`YF|<S#u5y^&%e)bB#7bx+$NlMp8;V<Xhm|#BmIy}+)+;pB2i<8$^wEn`rlRK{'
    'B}IEE|KM&;EXOB@?gayKQ(1xKif|~^s3=+K1W2#);B~7OIn0H15{C;+(+}?Ie1E(??0i@{ws2Ybt-F0t!q(JH9iB+wJRo=seQ*Ms'
    '(p$In<@j<8PPv5pytj>P8<9N(uc@HEu7c%=P>Db>Dgd+=TSPgG(VL@pAPd3A4cPMX85?<T$oPe3jn<%6YOK2495qD~Fj;$3<9oSv'
    'BlpL7wX-^zM_opIs&FEw)k7iaR}Fwm1FcR?r0oscWq%Wq`vZH4V(9#m&f$C4RRVU%1JhQ#qH3DsQ3fJcXhe8b;ZN2ol2j)j+t@0i'
    'p4XE$9XDGMk)TNr5hnQA_9(zp5X&*{hzb>P(F$F`p<DNKhDH8-Oxs&B1VaUDK14|3pd<_zmZ0wH%leeX$oQ!9+Y1n@vfDeqzn$Pn'
    'C4~*sk$~+qCpg=4YHovSOMZ`;hUyz+^PAI>hhsF30?ng;_r$gszq$Ji?|%xeVp@d?!6`^#SU7=e@{lv}!nwKrIIcP5sT{(YecgzP'
    '6g7+(5J~eeCKILc#{+?g#$$>p4HNJ&-F(A>7UQ#4^9$MgkQ$KH5LU^d{}u_j<7oQFA5iQ~JfJEcS(}!R?C5L_arg2yT=y<-hZ%4d'
    'eG1D;7Q-d2x4y0)rfKxNuwy71Z%&QQC7C)%bVNAZCLM$}*ICEDhgtO!ZVCpU4!O6PKSX$395gj<zQ@*^bl!J&6mE8H0cLF+^X0E{'
    'MIg17ylysYEuAlBCuA?T?`6H?NjvtQcA~^ej_=*53abhB!GE0SLuF0tse>W^Fz=)J;EsO#w!`2fyhETa20t0l1E=of(3slI$W}VW'
    't;`bZVY)dF`mKw^^|wINw$l4D3-(YSkaZbjFD%`KJ)}D;s%!qz%A|hyz)sTd!IzJQ^={iyi}!6G1`i|N(2QIX)uEv~ZdU&)p~A%M'
    '?jxHztWPKHeN25$zCDF2GGYyCOL*X6T(O9&!XO3)5{4{g|FIn%chqCX{X|w4%w3a6%sj&D0hmz{gi#T`c|^qacE~e!@)8)s@o9r{'
    'SVgj4hO0x1yv;k4>`{D9N#0sSWw?X{@B{lelL4nKy&;+%W-*^K7(UA&7QU0_5Bs=s4pS6Io|1M<AKA+HdrAb{$a5wYGh<2!2b7nL'
    'rOBA)@U0XGeI=@Tx49$!cWh?6I|u*^wGh3!Q{4svqg_e03jP5y(Dx;tAZh%-W<p-Lp`8-SLjDr&dTjmbGR*d-m;@(P#*UGI4Lk_O'
    '=_9*%3AfI>AaQMCQOe<HiE36$rzE8IqiZbOLF|Gk2{Kdhd?faM&mj^{2#x=S*%N;aR(r;3;iC5%hMtMHrm0d@G93ZhA1ybhS%2o9'
    'cWYyFL&(nsn;sGLj$8&i^`c_#leUGD)0YhN33vKiE=dn2G!w9t6UTN#{HFEBeXxq5h+}xMVH(4qT#?Q)o({xWhP6Mpdc0@F^JZ|c'
    '{{3ceTP8V#ImIk*0$pki*5Qpds;GL2T^0>77RLK25BQ`f3G83{6K^2OZi5yaZ;d3(J7`MPVqJnWv6#@|ShUdS78(up6>!Bn`&vtc'
    '-Mb=#pW<b)2Id|~O02WX%7Zm*5k__z&b<fNRyXhJ+&tO4AE_{iawJ>O8HjVP`G%Q*qfc1rlG4mD=qt}}-p`LL%DtPC^u@T*sGd-i'
    'bq&H}Fr?{m=yk)O_Uvq~NVk5vsrb+K?`ds);{cF%qmN5W0f#WJEJ7oRx=5V`wLH6ZPt()z{FN=_!|`R<)_;SQaA*3^P_XQPpCXZm'
    '{p*Y!rd~k6Rqz#8@Z<h%H)qUZ|8O90EC!XD|7QAMgaKJ-K_t$5g_k)*vr=r`90UFeJMG+5*b2?q69jd5|1l|zC4Od>5?VJaQJFGH'
    '@-WXI+f-D;yY2e;tdz^iG*EIJ#^A>EvGmCl$!*}^p&KfjTX*ywN!h(2#;(OU5uVm5?$sFMlo^mF7bHQ%B=n!ll5c)*@o<J`-R>*m'
    'qk6ZH9jb-v@G~&3RQjb~Do?E$^sCj~EB&oII+vgFsn;(tEMNnQhce-^n|&4TB`j!=lb0C9TSnunQEib}5lS{6-p;9=bKHNu>Ai*P'
    'rjH5kw8S-M)?{cWRXd<Um|em}8Pf-Mw)O`0?kQ#s)}ipyn<I3Pk!h`<ET~4S0K{dIUHj8<Jy-4N`RnUTB#is-6VR!El!sj_YFEi+'
    'Nwdezi#S9DrP!ePP`vKm*LfrBr~UjEF{jtnNcshDK?--coSeA55|~9DWRRJ)xrU;f5Z>xL17E5oyyN=*BRe{dzet)?slq01@x#1f'
    'gb{{HbguMh%=vNO!f#9{hlkCffh9h6w_KAj{bWyn`J>I$(nL{jstXf)PDTteAT6Ah@Ff}5tZu)aA`0vN9VNEk=~J}g<&yuNUtUI|'
    'R6r<{8Bif~Jo1qxLIPy01AdQj{ju)&spZOhn>qKp&rjz3Pv?66@>W7Wx46s9qcU|aD5OS!R!mtWAQ(9M&#1Lm(4F7e%4X{Cf`G7K'
    'R)@|<oovLnCMsfnu)vG(S;N?`_MfYlVFXd03C8Q+2f6oogV`G6BX})(8cjIkq2WQqmLLQ$2*Ux=R*q>(AKAs$lMqqNAqclQpC)l#'
    'ig9U03@Tv|$?O$1kxx#xKaD<pnh%FK!1Q#`xBKCbm2|zKF$*4X4B%!cR|ln6#oWN1kQ0>9fcIMMegzrov=36g;puF3cT$mT)yL#s'
    '2$&H?02)g;!oai<pfvaK=g_?~Q>2#bw!xbF?rDfD@a{|eb*qmarneL|bEL}5ng}Hj*NnUuMGOtlpE0Id_S0Rz3;+G|h80_Qi?lHp'
    '0B09)ff+IeOwq?xgFj35tJ5$v&2@{PUO{{YyWRs<1)Pxy9nvCe6W*lSQCQ%3j2zTMn`;PRb%j3eEVByz%(<r9*76|55*jnZ#(o`5'
    '%f$577M~<8>Rf+{{f<CbkJoMD412zP2pbM`3hflgZx}rr9kK*1Pr=PsCg@f`Y21OlyYhR~cjEN4Pa2rVbd*^u4&{z#mO2)Jx{M|-'
    '?-}o?rA9X}EM2z)gpy&MIJuu6Kx~W*C^S2fVW_D0?rtYi5hr871Y`f7n$BI^#wtnKmV%6V=nuG95b88>O&}nvsReHsNNL0e@5_0q'
    'uY3*X5dFg=*kz%{%OVSHXcv=pBRm?>whGH&9w?i^kH$qBuY4nVTBA@ICv;<Z8gNv8)?ZO!0qFo8W`60=PC==0n=-xN)^*+TuLqgl'
    '%ge^cNXzEe@r;lA5)7tal+%N9u0UZ4QtuRiT{&O9_Vd3ETixlHkQ*dWWkD!o*+T?lH>NVF^q7r+zVpyR?_N9H=})w#Z(&^$a|_bA'
    '$8)M;vQ%Kc2D&bR0dQBkGedA50Yfae^O&Jf7a!corZ&hVH6{REfq@$y<eYS4A}q>~u~Dn{7A4tIjn{7@RzGvSc2X-0`ROU7s2gL#'
    'GsuSXo%<q;62bzk415{#bj8aFNzkX@asTm`RDw@l61`T4d6N&v@6Y+@VpH+IGMYIiiJ|HWq)rW<6Qyob-M*_|j)zrOv1&Z-miyt$'
    'hAnfnp0&t>Jv4_>Al#DTqR**><z8V2V+dAp`;Jb!P;3un?w748IV|;-7_7|YPsoBS@f2G^0TZNeUA36WVC;K;`*yGvj}*k`w`cak'
    '@`T#30p;lEg-c#phR%eKnC_m-&K$Nb#$|+xwdPH-RWPLh*w;}_gZ9<$8)Kq)SCkPzOY)$W$BH+C%;B3s&w(aoF=MsZf<@Es>cq7d'
    'zsrI!l-YqZt{rEVhdibQ*sLAaY}>K|EcBz?y{coekxe*-^El-(0cj2eV;L6sdGMm#rB11mnQ#AAseW!T{hLu2x6WU;3~iR6#zrc^'
    '`4CEgidpcLm<`b+EWpk%!y4@=-?{z?ZQd{ljOnTxTR^xTFcR+e>KWcpb95>^b`q<UEjw2{D+J!uw0nAOrXk1(TvBu<%mQi6$|kZ$'
    'y0hroOvT!7+RUZjc5r+m+kpCQP91Awuz-R(<|W7MP3lS9_j(m7a1k<&$_U)ejP3if|2n0MM`_ZQT{#ar9ZjPrObXC><wQ3I+dh~B'
    'I*UodX5=mA>&~S)GB`<pKKfv49xuOi&Ier(p<>+k6jF#XOz<d0V4avI&?!areBB0CA<xFJD^w@k2tF-C3<L=vwF=j{IXnt;>;Oa2'
    'i)`;BUneea5K-wEm18m33JfSn@!gD}WBMqzP!oli`noA<I2;2pjX?eT<8=4(`mp7#7OER}7PJ<zoQx~QkWLzD+hJQCBc`Z>rcK#v'
    'th*v>@pQMx$;t5RRU#3}h$Ti+$VZ`7Q%Kd(g_z&Q^rCFfs((C8L<h6bwbPy^_;d(>6Lyq}tc!`-*3-I*!>lZ7*=`q-;~k5i{Zvo('
    '1b5r!<8B}~f<Dg>6RV3r#!!46AsxJYK?Br^38BWGrGdK3AJ_eItJHy>W+ooFJit?nB#-a8xn0zs>+5f-O?#1F(!;Op%|Bz+z+qe)'
    '8$NkvW*A`+bD+?VQVgP<BE#oHfZ#Hlq3IxRN}AplJ<SP^k&$C?(w4)Qjk3RvsXE|5)N+^)k%t^W`Vpyigidk>mK)Q~)!*#P-)2lp'
    'g}$VXr_OtSb#<h6T^})BFf@#Bb{+1HP&)CGTCm@_g_X#8xM*w(kmYNSV2^Y>1ffeLqs~xO;NK-*UKYj4ru^`2#dE83*URS2sL?~D'
    '7NenIe4cj-SOYbN?GVd7)}}voe|~@EE8lod`yk^4a1j<P>sVB*UN^;1N2by&c!8W-x@)$u<C#-da5eBDr!~iPWzab(0D`^BqN*~('
    'dkVk5jb*<XCpPRhPg5y+wXVgAKY_pDWLVHs$%u5i!m3jbb<s54TJ$)-hONl!<4={pKmN>K%#h;Av{=XKotXi=1Q#okL4;`>%a}F2'
    'Suvkhd|oZ0pLf-zj5Rf*ionY>8jMBA@pxMA8J7mR$Vlnv$+qL(g&#x7Yed6_(pl3Wm;!zDHJWf8LXwmT_>g0w25}Lg&ya7jEWR(h'
    'cEUFW-~4N!_Id`$OQI!(TA+235fw~31T;bZoi;h)-&bA9F1!3<*u&xIw<$DC6fsL1PR!V=2$Jj_v=P{_@(!zat{i2>VVhgsgg=5m'
    '>TwEDRtlM3q(e-8!xz&L=K7oG{oX}a9?hHBhPo}}K%388_N7*n*|7k_xip6ZdyZn8np08Ta&1sU=9@&iw@sYsGit{zg>4nUpIZ|4'
    'O29&_sdKJ<-$XCppyT-Yipl!AbyqxAvHZB9?(MW>aJ<+qb`iV78psF6EVd0XRJg=Q(B_?Mzo`nPWS5t95gIuZlS}n1{rcdYgjR*b'
    '(KtT3jGQoR?shJ_-2buRm}TxEOdG~7AVc@$I1Ni>?SDz{NQFwA3oF>U++kiVn1)|32FeAXu8ki<v$Mb>^jNwmQ9Hn{r#*z-tQ2tX'
    '=X7egJfv6U;^mAUo(>HIV`~4ZnECyMUo!Q!G1<5?N(w1<KkQxjm)CEXzo9y84P*8-m3kgp1b&kQy-nn`VZg|XEatZ~JJ&l6A-jA2'
    '27$QvfOT<(kbZ{Vv1I7fm<Qa4xJgQ!gW@7?NCB3;>%P%%w_k0JWEVgHBTK>3M?@I|Yf-_7kU?8#)o#YcboI(RBb6hobAok{{OC%G'
    '5k{q@_P3Enn6~8HRE^7~ANKe4kH=p(`j~68)&<Xsz7PG)NHon?gH0`FSa5!g_NewoiI}&(p@?#5!XcR;+r>w$#%IqB01g)^q_C=U'
    'yz6T3daw5{hjmWr<+9M|rSPB)T3!fv!D@Z9@MHcaFrIO<c1^MSdwLuExeS)yr~CwH3r#6}p#xHmQBar!W~p%5<IM$wP&I>ncJAN@'
    'hvZ$$8)qcF;l+dS%S|=>Xam6m=DGb+pfGx3CNb<>{_Km)S^fUy>joMSVh^6Q92MzgbR}6OsZYgceK@ZBH6lBy%FczKC-Bk+s06cj'
    '*Um_oQ+T2BysQFtP#$1lsZb+qw&gVodd8av7w;fCT-b{Y^_?B9Hp82S@b(wBNb2BhuET!!y1}G^<?R5d!G@vMRStuq+dv?~X;=i~'
    'P(cPojcw_%*&C(5yBGanM0NS6Q$tKm8?!tdWnVI(K6D&(>Kpf|bH)fK*u8h~39|)~|AFWD>qZ7I81gF%ZWibv=2gil%`0C78QTfo'
    'B>#uKx%9aov*uT6L-tyQp`hHO3CBMTE46pnxvm6FB0^DA!I<`zET<;-<=^U=vIkwb4w;Cg<_w(L7)~jGha33@0H|)}t5&?jnYnl$'
    'LSXqSaxjnSyhc{IEG&;HTSVp0Os~<nBQLvd)l<fEcs}mX^BNLF{p}|fA)RW2(Gz`vUIpbciOj^+Je0eCH|w&~`j;~w?srN+E@h;j'
    '4%B+8RsjcnpT@0E-1N+8Zy0%fT%p9*#~`$9bOaEyJy!O_;lwA&shw=Kg8oPJNFb?8#Fo7`#mPf+U&-K<n(I}fk*(R~j10|aV-7k?'
    'xD}NK-*K|+_m(Rs!^kiaeHwPSYnzS~EMnhr%o13M;_l`qW|M>nBVTEm^Hyd+75MP`)9DR=zVlbs=64&UnLfCC+RgNeO$%*c=E}ya'
    'jgc%-E~#Ot2lHzdew$Qv9yxOPQ>(+On=hT43jf^Cg#?7xK^226su&M0ju*vM>z|$a_gUA6NtP!c;yX+-9nRK_o}j+wF<n$%HqmG2'
    'n{Iu7*})l+xDPM$C)O{}f(?&OzBe6lnT81KJ3MJbs`w=G7~O*@3~?KqO>V+p_ONSVk6C+v46u#1M$ZXV%fXHos~!=@ps+bEr|Rm3'
    '<KNz(hA`HEXUbTx7?sFONI|;VQ=}0rfP!FXF3#2+a+)8r>r)Hs9MgUmK&hkTiz6f=LsjpjK0LP@?B}4aZ>;!ucqByGO2m{-fw_z^'
    'HL{8U1#9_lIEK7rL{*G7^0v*<&&F2%ctHhkgepPPv>M7X*co$}JnERMhGp0QOwjaZ6ChCFD<>0zf`gZh=>#pr!U!{<DUNK+l?c)@'
    '>esk=XinY@>seWe0jGY`hOP%H$%<R8DC_j=jiWdFK@7uv6rzFjB4xhmH~g$c{cZR@knz*o&;D-vw|i(JZTAos2{GEMim|p(5Kc0M'
    'iI6dZpq|ND#%(t2o(=68sz|}ip_PD6HBU{{#?S_JpR^dB%%3F26X44fAKK2ok7P6~%1mZrG#rv>?nB&Y_wtaXlr|N2Ou4DEzPyul'
    '{Nv+r*qBF{&nAs&^hY6DL?lof;BY51JI%)lDjM$Brf<x7EAaKGefRk08a!z30T*Z<wT3*pObD8?Kp4i*R-rA6L-jE2Tlgg^Ut)Vh'
    'DdH(?mL}T1WB3FQA^O*n?n3lWqGvLTPqPnc!`$v(dzIjxuJ-iww2q?CEZnj%WrK|{G$PcnR|#@QsHT~#se(Olz_X-_8up4!TuEW-'
    'fz0d&V&0_UEYNP&Tv=2ubwJSgZcID3=PmrWgI``Fv)c3Xi)3hO6$;jHzQTOK@AKUU@;`?jGCJm_30$-I6<?nwa38Fql>-_jOcpX|'
    'M=-qhV5Pc+0pNC5tbW}mNQNp1DIAE2m`0ZT8KF=fih?G_T~9zoqk^_>c|7#x?uUW#`v((Y<%4U>5Q3wXdE+smN6#svQSU>@fhYh5'
    'oUYx#ImO&H3l$h)?(r1bw+SUgqHkJR7nuR>Pp=Q9axXRqW4*V9{qv|CfHrJu6ww+W5(Jz!=&tN*j42A$I))^_b{qR=u`Z#y7jOJu'
    'YQ-=eg7AXKsJrIq&T#vwqepYw4&GQgm&+Y9x6mRm?j)V0Q%2DSPKMq_CBe?7j1KUyiPrqb7WQ>NDFj%Z6l22TH2%~D2>1m-TNnbZ'
    'H5mlud{avP@2mfn;<y^1Y^2^$lW^!UX%rBQD56Cs_m2ir=y>3F?!;>P&^C53Epegpeo}4Ag*Dr~eY7QFZQg)+4AC&57+l-sAKJ(6'
    '(X7U+sJ{BZu2>*&cq+mmy^j=H6OT=px_BwOt2Yx9TJQFa{EEwgPn(&^v|Al$T+|jTS#4_FR;r`$<Z@?Uy$8gehxBDzd<n1h{6o!F'
    'gz=2wC8nv#<B?$*M9`|29bjma1o6`iJcpOv)_tK1A1M;mrA9~}e#k*@NnsMpy3%A9u77PdUmGIcrfcq+B50Xz6-i`a)|*!P$vU$M'
    ';zrNXg!*&3`m21~!tQCcm~0EOeHB_7bz@tv*SNYTETLnJuD)-~+qrQc-v`6)ayZ8YHVSDeVvKeXZaib8lX40qAYEphw-^Fi4A*Yv'
    ')YF$<OgKq*F|F!pqeIwAT@*8rZ$LBbQ*Uqz2|yO(oQDC0R$_JQK4Q4T!<u2as5Zxs>b18q+i=daFgjC*uGX|o6DjV}uHE-(vp@XK'
    'UQQXd9X;$&;NfH~sv3nwIN*CVDleQ1ibTXmGz?!7OrXtg+sYmWIS0cjh9L60=Y{8*Q-w}pV2=7?Uhf>!wZV$lhAs#_XRobJ2;vs*'
    'xGo45wS-<h7ok$?#YLxkj%uX#s;6tC#$QDXce{X}k#HVE4PJ<4Ot7Lm!sD9!ua5JIS}uS?z3MBsvd=Kf?O;j_Jt{`39u4JqAGvMV'
    '{!;HdJ9AT)*XG*G{o%`3-@@zpLj8srx*=$QzxWF4Xsa5107ImF%OOK;FtSaI(9j6N@U>aimjL@7!U{E#-@E0>aXoCRIRr_aW{qaB'
    'ddpM{79)xk(m+wHh<ar9*K4;TiX%1*53i3tleHE+9+!<dZu$tiNzyFjBjizJZ3lxp6}Cr)T%u1}PV==7#f;jApIs$?>0_b#)nUB~'
    'mGtOw8}zi8%JDphb88a^KfTyQdH;RsADSEM3%SM&I*Vy?A>ogaCX85h@+f`KcWV-UJvDKi$L4tLkwqZCjyaCiDdEX-g-;9(DG~N!'
    'e40C-ZV{_V*a$jIefvH(Nn_@7_#b25nK(hAiy*x&;p1Y0nOY<`k!WLA-y^Yws}vJu_&h`289e7P$bcuUrxTP=%H1&mcQMLTM>p)_'
    '3I&BlATr#>0vD@r*%6-2D9S|6E@DZwy8mR;4ZGN>Wzc)lPnHK$8EQcow(I{WQ~M}cnGTpv#QWpwD(xikyE{w%wn{V{sGfLVjS96B'
    'PG`fmg8PhSu0=r-nb!${@!CCHN5WPJ^IQ=voJ=<>>KmzLHUvkwiIGGo;69G4AB5<zx(S_Iq}x*#IpSen!%QHEGGQu@0J9a-hBHKV'
    'GlVzX)d%F7N%K>*qA(r9OG$9RK?5gKDq?Oclw;y>RS#FEzvmq|qY*-P4ZYSVCQd_3*P_HP5zV=GndCt!7dB_Js!iLaxNRek$2Fw8'
    '*$&gM8?F-o47A$#N<%j14Jc3{-B?|UrkFXu1PP|QZ6hmBVb6=nB$a$0l1!X~Qp|oEX%f2lGJ}(opzbks@!Dwd5bFoF7>o__0e;BO'
    '8|Z<~Vir>au@>E3HlUHtf5f<oJaoH3^Bb=|D(AlHbq#ImD+Ce6>I7Yl7H&}Ov99f_iP5AOk20dXxot1kwze51f}Hap8)j?>Nba;j'
    '$kb9;VmQ-H_<9%Zc-wAHT$)`Q!3jf3a;f2h!!)WD1YYN=wc(?!H<bq;{_0n>icZh@`A+dEbU~pQ(@A5zGN$R+)WL<s93R}gJh(ia'
    'X1q2Pd^}9Y?>pHJtKk(X4YN)VY>C<Et39ARc)w*x6?nOt>o(l7i_?4gl8!8Nw#cCd8RNY$I5BvGZxSX~D9I3Rf?qEG2qoS2kcppe'
    ';~Y-7cf=@%!^0NlVy=$6RYOWDG=*BiedEJ5`iBe&J%pG;8!x}<k-VMdE66c=6+AoWD3&Y+m5HZ{rz#JRqkKsP4tfSVzdCPUxAOyu'
    'b~i+d^QM?oRLg-h&9w0*_o3kuE??S9`<udc=%($wIhrf6zwD7swLw7$>b82W#sV-hML<#RM+FWe(&5(H8*Vy7XNK?I=aR=nlp$lF'
    'M+u>w={g1h%^`?X1p8>h);C+Oy_EmFe?l^_52s@#sGhZ#unz>q5TV3`NZRYL%)qS!<YHD`n>TtpV_LE7sPl}4-Yh2K>H!F0!SLe2'
    '1(~>#5k8?}BR%tuK>IRQr>m~t$jnRh`@`_6z8qGkflc<06H~{uf-Xep_><lm!YutNP(p8T3I$r*T)QFv<%~S9>4E_sB$62T(T7CZ'
    'iH#Ws>v3QVPccoCA&z)+?MC(!hhrr6pzj;hdtr`aFa8@^&1#i|a9K;RsS&P?a&Wq{%lu@T`(P@-#x5d^IK=^|6M7I{0BOQzqe5yW'
    '$Bf`lJAUOZE>L^_Qf9ho`nYB50Q5CG+Nd#lt@$#nu89J}&1JdvphSJ^c*G>it;q~D<1_M-h>^m4G$v*6yN|JNEH|YjW{6|vb=M*w'
    'XO`{VS^668KO3bD(zb803x6yKWfcTOoRvHVbHf0bC`YTfzj7OA7603AHVHa<2sz$bT?OAT_!#aKh6ys1fx23w5U>qTFR$MQ2i?$j'
    '%MVX=*5$B8*oL(ivm{Yp!<!w0rilUe&Mfv4e9ob5u05P59`a+_2o0k#?7Dqnij|qKC2ryZvwv#imh&#aclxq(b<^tmSkPSnrY6J|'
    '@{Vv)WSP;51$yStNnKF;>!k44zK7Me>|{~02g(j|&f-Jl{KI#~%sLr+ADdF^6*2V_{XA$JTf4X}B8_1IY?4CqhKHD|OchK;S>ep6'
    '4v^TCw)iSrtA6*+_<l*9=L>C&JQ{*+Pt?ygYS2~E%hHn0@l!$)MtncT-97GJeTPe&!;KMyL)jX%4BCqqPeSAABZW6?G$d9_+GOYa'
    'X%@0S`kAZQpgLr%^d(8H<0bR2HM%ic`Oy@?$8OW6&F?wPym#;Z#XG`;Kd{Y=dS~uS;f5sun_@z|rZOEXWxDQj)9qVvcVJ_K$O&6h'
    'Odp2Vk;`W0gJ)ERg3Dz;1$kE3-Ta~J8Qzxzmgw9@v~*Qv25yh&Ob@h9;qd(;pBWApCT{(%6(eTtQxXuk<CVEZMp(LRQ_|O1i9u|P'
    'h{9$lv|s8?G4c<~?uirzz@+edY+{g)`h-WYA*u0MLx4!$F>0V5n^u!QtcsHyedrDPvrBOZ@_Zhal7_bVoamm!h%Dy9uvRj=XR~Jg'
    'Vbz^C1Wig_@e~@uCrgK!ET9GlQ`WOtH{t-AVZ_QNF8m)0@0j6)tIJ-7lkC*Rq}2v{2qj~H6x0gk&KscZ2Ozw+^r;sA^kc&Q>1Au)'
    'yu4Tz6eBtrRX~o4n8^*tn&KMZ!!1tNy2|g~h-%8^`1CD$hGZeb{U85hLw^J&Fh^b?mx=tkl`+`fq-#`%Jc7pR{MNj0W&7iLXVzpO'
    'AX_H>Tth=;!pFY@X7k(=7399s5J@s`;i$J4u54E<d&c{>*N%>)xr`}}4jrNPOW5|;W;1grTN13<E__(muKfmX@7MyI15X?cPZgx^'
    '6&9%`X@*+@L3RpZMv6(*?|#*)o|o9eC*|Q{EbV{&@_c-_@QdM}__&xxF`R^;uMeMjBF3Pd0lw%67d+8-a~!Muf|T)TZF54|e*PK%'
    'c=u#WsHw244736%RqLH#@`izRC|1;NWk96wbMj*j=y|&K^QRcT`Cl);zg(IzRP+!tE#BD^Bt}qjOQ)MKGvp6OS0r*2?@QT)z)x>K'
    '^5=q#zZgOk;Zm=0+xQtGaUJPeACBNsIG7NuS<5K(msSftb^Oz(6>Hz<O3{iVd9a&SFX&X7frz%Ja?mEMaou4IT;kuYo1W!WpYS=N'
    'w{R|8{mI?=Pwu{(7F<qW>KI^*(!&0dmx%FfI1Xko%3Xr%0D{5C@t?i7iSNJnDf+Tc+kud}T1C(S&hrrXNLKjf5$;!pTBzBFFrzYH'
    '?`L07v|K-r!>_*6?|-`ybi+~J@K_aqYG@$BB-w8<nz&$0B7Yu2+`ihe)@iur%m01+zta605B|^L<?99p>te;vmvAeD0*f8vRL;XX'
    '5HA37Z@c|@L3&zUlVtk(>CDa`Mm#=lmVF#%nL(nnY1UvQ&}(3#_R(?;vOJSUms^0aJJ&q_b%RkSw#Ps_lbZ~h51^Y0%{a!0_NG|U'
    '*aBmIniu}K<SEPlyfWxErf-{?iZkbeE5hf9xN(rQpo-Bdg}(_w3eM@gZ@pO(eEEYd*VCa=<kg0rrhU&7kcOMilWdG{e-_k_pHk9('
    'vfh_ha}+n8XW0+Y6@@ptE@gsbXjo^ue<T)6F2n}h*?!-84ANe<hK@EdDv9BrA7r$-=;!&yn2v~r;~3VpF%Wio_ef5MPbZ^;=g(gc'
    '3v+Y0-Dz&y<8dPzaDpRA<*UdxmP#4s9e!{^5=<VZh^Z_nK`VAF9cyiKB8;{-6OM6r_=B?Q;IIgkA<fmiDu+-oF-xs~s-OCg1)o+R'
    'dCM3(#Dx>`aTdNM%#^8d(Qt`jnZqjFuwvaUWtMiV`1-iX%vTzg2<Sl1KBz9*a^iXwt$mx|p}>|*CDje@tv07H*hX*uLxSt{KZje_'
    '=9#R*{fi7j>SHD<V5K2Yaj&3y*C92h0QP3{t5!8O;jmFNjp53!BSA81Nw<a)ybK$Sn9YROVUk>(XX&bCH!rX$Wc>P8NYyF0D-09{'
    'fi`TF0Ih8><6>$@e$Aq%TKw{DLTwbVf4KP?4&lJ!u&5XzX@tiTU%XX)&g{Kq@rFLF$K%sKU%?#9;WVIm$IBhUPC1Ihpzh1Taz>fB'
    '2vJEW#mNyti5v~eYggVw6CqsSY9k_uvn=;;Lm0nE1H&gJ6fbO-xmOie|LU(>fhop5umCY`g0;;Yv|H?Tw}8)^_KqYPa)(;BT)Xg&'
    'xwUe6v6Fybp;U)ghG9wcmE3nQF<M`Cr2Oqq&7@CDKR>^wPY5uwm({-U@nzVOE7S<jz94t1j0s7r2nPY5wg>J8ueqRQ;eFiiT66o3'
    '(=I@#u7;K|17W}rlXn8;P_w#PK{|yCNG`l<xjk1L$Q2*c1Q*lR7k0Yhm9s?upl<>R81;!-u0q|;1z)x@Pt-o@SRVh>IN|DV7OH2-'
    'aV<`<r>Tz^VC=g|(HUbn<=8uNB71kMxM1AjOW2SzHvw`e^TmH%T>KD~Mzw3XN7uJvaAUYavFiQMw8-R*>J5jB%s-nO#RxpYZyv_E'
    '-L4gX<__?eIB(8N=NI_ujRyqcBjQKwVRjYnEtH5$V9MjJ#ZIGuHb_vUQhf|-X8PP<Qb4m|_-flI5!nLhqWE6lJq_o${`S{BbNzxe'
    'O=A&QY9E|gm$(jvI0I!>lm*^vFGKhKlJcKJ#M4jf=kok!9<pH-lXubD_U5!Dd?p^EAMSrK5auci;~1ZAd-bZ@<1p&5$EhTJT;tuK'
    '+5}BBtJ=uMScdTGaY%~y-|72HYwFL(W!aL^b86*<D^svww8QlIhoH81TFC=BUl{k#`&TCu{MU0(4j*4PIG~1%iL{7)yrnCCSF@_n'
    '>qY#Npt)9vK#VNkzw&l?Fy>4Ur+I65YyrfukBy7;ehnu^Si%|`!=34hUpranpIdx6D0;CjX@0f4D`t8im?Rbjn5S_3F3fSVYZpDs'
    '#-BI3GUSGID>^b97|Re=MU>DWa+H8R?o-;0y5GNeWDGmUh;>0)M2^6EHlbJCRbDYM2|Z7AL4ktmsl2=5RKXr~hF*q~u<Q2?sM)EW'
    'V}@RUWqI@~X#UV6&{nu!b>V;+es)*9?T5#2vGTLosT;HG82$`djBX1eo?%_VLL0*-(Y=5Mr_JCi1by#c`+OUnq;*>o2qYB4Y-5;<'
    '8A)-~$JCV=-er2aTVLJ`E?D+29)EuKJz+m=acAqm0;E!CFphVSFl+V<oGFVa_&jp*y1Y*N*AIWn<z8TU3vQoQmgeVkh<p3f&nI#2'
    '=X1JnIEz&e``T;<{K@STau=GDUx0>|V#Za8Xv-TeaXauv>-K;Dw*PE6@7#I=ZKiRB=HXbVQpSK1VKh1(_{!WmluRzMa>v$BE|~8G'
    ')4$lr%NX@@bBK4mULH&)p3ruXoQJ+Q243;K>h^r%p)#V=TssciQM^duv>j2LQ@xbPkJoA$9A@9TbH>QGaLo3^wB2BveucXzGe%e9'
    '6=v7Ui5SNg^+z7_KSJYdINEz_#thD60K*1q3A9WQHc1uFBY;5&h7eR+92JDNDX6@_#CPlXlbg_|F^D0<)1KeOt5l~EQaN;hSVfN9'
    'GJ0ceOn8Po1sPul<=y=J`RU7exAn7{7?K{W52I<~{wX3s&oph^f53k&W(E$aeD`35;Of%}Tu;n#KhK9{9iI4d*ywOdTy>e0tu#L2'
    'Fe#x4V=#8A0U;RfD!~Io7kd}pOy+d_>frObWe~ln0JVTTVe%F-E4ZQ=hVjKzdl&pm&3yT?n_}#A=co0|%5gu)IZ}*X3h>*Vg9l~d'
    'soA^oCj8@Mi#M97Tqp28;+E@!8|qGv!9zm7enZ{A8*<jQ-YjQ64{P&e!=)5&OKoL9TX5-%kYs>qQ=r454!JtThJ5DzkM*xhimh+m'
    '#mkduGHM3K30-Kl91ot3UZPuEd$SF{V~Jy3X8RWXu0XzgDoHxCm|_m^<}4E=>@cl_^#jB6^&{h%&<^|7+yS-3II;kiVuGT>+JuV3'
    '2q_MZ9ysRn5Q9dm_ZviiT`&;nZxQV-AI>?9DNKT+^`{D?j*P-jafuh`fyz+A+-B)^uDSAv_cY%02F<tj@i1|tMd(9RuMIWE%LT!R'
    '3VnRf^>yoR3{Idii1|&v;6%X=@Zd<&QIq?AsA)7ZdUbqr-I6%UhmDR+j1q#*wviE_qbe|=-WcVfI`h8qAQXN5mCL?mH5+7D!JSQ%'
    'hl;?Wh7I!q^#E0uampwP(LJAvonO=@Fhch2J7RxTMlU1OlrX#{{B$+o>X?Uyf|ifFSKA~E0SIVV^U(D|qQQjCBzr^(!}kdOR}8x`'
    'H@LcL#h*>?`77kkUOWc%7%NDeR^s$!!QE8E8I_D`r@d*+Oulc?XX)p7ygZ{)p=xMg7xc3DfY&wxZgo(bQNrS$krEC4a@C4=o2WCv'
    'kN~702R|4OrG-No!YM_X%R&c~2bS%BKBRJE*<EZ^#Sx1I{wUHhJS?5oc8CmyYRELI7&*=Ky(;?amR~g&8!R;S22=o$sM7#SguyJ~'
    'G^%ATShW$P{AqLDx+g`$<yZ{Ri-ReL7N1N-LN?@eLL;Syi;36qJc{=-w0~Q8O+#@w&w8W{su1043-4-Us2|BK>0TE4UnWh#SW21z'
    'BG%5kZZrDhxS`8H@qu13M~5*lVI}1TVvR#ZqM%t<|ECuGfBhf-561x;EC'
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
            'protected-producer-optional-parent-source-v1'}
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
            'protected-producer-optional-parent-source-v1'}]
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
            'protected-producer-optional-parent-source-v1'}
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
            if path=='.github/workflows/parent-qualification.yml':
                # Whole historical recipes retain their real Parent bytes when
                # the separately preregistered optional successor is installed.
                parent=('987d8f0d198e40211ab0f33286a55852e286c174'
                    if installed['name']=='protected-producer-optional-parent-source-v1'
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
                ('protected-producer-optional-parent-source-v1','7b0703d88d404f38c1b3dec92f77f03586c9144c')):
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
