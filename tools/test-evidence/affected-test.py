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
# d9fdd783049ce4e2d73943c6ce812bd3710179c2 / tree 6ad030fd0f60b3917c02078217b4f9e791463c7e.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'fb546cadddc287b31f9458799cb9f051057541b07ab4ba81317f635cc9feaecf'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    (
    (
    (
    'c-qaK-F72MlAQ1L7=68*%E*lT+o#ac(LGN5vd~2m9008D+CBU3`YZvmS<@sU5~!85(yFJcTN8oI3=em6GxPua?H~8s<JTAe#XZIS'
    'ZX54*e>|oA-Er@p4ms`r@%v%-^xMDx=Wma@n11{B-%QgC*8cWyza73h{<du!!~gWAoq`Gcr^bvqr_RUF4^5a%Zn_+e;s3+&$Fu$m'
    '{KL-w_Fw<@wybBN@b&I__pl8=3afeF@!vJ1VIG_4QkaHu3_dl@*yL{TvB~3LT{C^Y+OrGa+<m(HW4Hg7A9jD--6wvnJ8pMRhr;4+'
    '?B=QMr*SlXGInn4Y`SQ>K0D{T(M{G5O|tFhi|^C(?yx=X_CM~z*A%{$R_ucv+stzv&6H!DQ%ZC0ZEkFw`JwaVy4EIdKVR{f4#&I0'
    '%l4S=VtP(bF+GKCDy{3IiIbn~5St<7(8Q2a?mEw(&ZY@{=jOS|!Pl%?S}P8{pWCd@r1gVqo$J#$^99*y9-<otW4+<Me!kZ0t32>>'
    '_vz_)_s<viu+7`Byw!jFczpPL_1Whz<Y{dAak-yuJ7iuePu-7G+YFPnZp?h*RjcoJzo&4#({DdqUY5hswXS#01|IF$dt-ZJqZyr<'
    'Lt}=>JI`&JYnJ`{M|E-O$@q}X+;u4izTK%EQX7*s#*Lh%5TcDKjNyal?e{E4WC#yip7NKl{qlQy`nG*Ke7Sde&(A+TUzPv*V0{R!'
    'x7LonwNo5IYsNmse&V<1KACZB+BK^_^UHbRm)Es<?2>h9oI2lxv5ixcC-3>Nd~V0wj8l_R2<z6}`OB+jm&YdX8JW!QYn$0MZ8vt_'
    'hB-|(jM)X(Pn}t_>i*^F;+nzOVHjd|v$xa8&vSD(G&8TeOFp$W`esZyuUb=I@+N%U?;g|U5O&X(fA!Scrs2st(+xwIQb@BSRE$mE'
    'PQ<Q0#5qo8-LqbH@Z=uTfxw+M`{bUtPxlwM5jnIR>eLUGsF{pSotaw>av(eprni=m!d10?8_$oMuzSke%j<K7(=c`YFigfR*W%E%'
    'O;2o_`WV}W&5i7_TfM&S<+%Ctd-fOC_k3rKwXyF<E{VS3N%U@RLdy-w7uoR?8t!MedVRh?uF8vRr;xkJ^=%}Y<!<x@65~zRIBu=r'
    'S~JDY4o$^xS48>4{rK{fj*4`f{qE(MHgW6jpLU1iHe8N2-5k7|2x@)kljZf#Q%a7jv+0MPPcZt{k+RIIxA796FD~3p<6x2@pmL*('
    'an{pkCqpnfwj6}aRcF&URxf<|@Xo6*iJ3mZWBT)WIRNz>_A$A(>${0iuTAxH8hsx*jdKd7AwCS{aQooM3y-_UZMY-secv9qQ8|EL'
    '+)LaZH|HBqx9r6e+4srW*gBt5mx+ck+IhBiQcN^Mub07-8L!^Waw>H=9^4DL<mD(e4qb?C9A?Y=Aj9y)P4c=q=QwsvHYPPBTg~;G'
    'c_E#=94TXPW(w^v<)-JiyFRodR|Cg{bg!Rs??@}#WUk)Bx3qss51ZvJUEImsdLBp|hY&|{*le3N``8Y>8RsDnX&y(u-!@;plSlVN'
    'x*a#<_<YLyADge+gL0LNyJ~cC4cSh<Nr5mjrk=};Ta;YEbnLJhEl=tCUF|&o()U6z8-gmA(0ih#_3b$F^}4Q!U6@Fo+DIH5^iQwf'
    '#q+uHa1YC=-n($T9N4C4r*^dMG_-jdi0XacjUi5MX!)#L+srYwlb^5N5;;|V*xr9VR>#_5>@pcu<81Gj`X>_R%{UQ%^nha5P_yOH'
    '->{`py2S(NDK(pM?wW3BC(|nHBFo~D%)Gs3>ZYk{<JDUr?T7@s?RO6L=Is$(&I0&WoNwk#{l+usrg0+f`+?w_Jymixf%wy0|5y%3'
    '&ei3QW#-cuwX~nRiPYZYJoDWK9@I!VIgWid_cxrPqubx7>RTX_@HQ?)vX4CQjU*1Xv189iGU^FY`<b~(*T1Dxw)%P%_}$A>bcH~}'
    'XEO8Qke>5e8n6pDME*}d1lt-v*v1*^1e<=*o+_@VE>WEIvmfTpc4>}%Xndv|G<?ZZ<TF;p3Awp(N6Q_xsS1OkCx34Z7bX|u)F$U*'
    '@)KV+RgUYruJ5U#`&-{zdiuWI@17p{7f-M5a#`03=MhTKdGGr$a7B1GBs&htO}^!saihoXwmntfqLZ_u>!>Qm!KVp~CR(an5-`e3'
    'PwqQ#;MtM=b=%o&NdoUrw?`op^nT)lienoZ0<q_1`FRNQ#AVTOr}>mywtL&wuDa#@2%tqm%r~CrF_DD?)rr&Gnm{gMv+Z1*!!O!e'
    '*gY;dN$G(N*`;nKkq6x)Q0je7B+Z0xb~{AlGxzM&#b2|lL;9Yc3RN{F>l}K$K#E8LK*RHz8pHL`c4-0)?Fi)Vw*6E^0@6b}cY+vV'
    '%5#_p$BpZnfx{mFWX-?}HI%tGZslE8^ti40#%I7oCxD?#9W~b&1BlveyaO^|cOY%aL}&AD`&yqG@!lLcBREL!JHcGJ0f#U{Yx%^7'
    'Zfe<~ZL+_0U*t!duuovS$E|xf6wm=mE^AvZ+G+NrZ8`I>loJ?G-(b4nNuA<+^PXx_f{x3d4~PE&Epo<i=E<soAwh1sX`ny_m5gnB'
    '+h(rF-pC<+HiH=kP8emg>oeK^*k@~!Gh8_>_n>LRZ5uo6UiN@mVfQtGTZhZp9P7n~qR8=NgtDdB%>z*NtP&uH88p`fAf_9)q^xpN'
    'QNn^Sk*@*vwPR0ZmOb}O3+fWP7X031!qe2yCHWQG$!`1bQUH1<JB8#@?;6{?K*NM)P4CEALd#<cT{q1%P|S_r_3`mJZy(ZIwRZXV'
    'k6ijg=cvwrgNT>|undpIlkYZyWa;d*{cz*gecZnsj@%^Q(vN)!8s*HBUvj>!Plj)L<{gC@ptSLZk19>s#wp!W5v<sZvh1caBbaDA'
    'Pnowz$AgZS^$jO1c$yP4SVZ0Re+H?~|K##*5j)U8J`2#%vFE;^pl`@zd*gc&Suomu3e!}VVc)+j;V$hTw}->hL%f)b`FW-vp+-lZ'
    'l8;~-G)pNHJ#8kNrqH-Z%&GgyUw3-@yIm>Z>w>19nA|+tU}?*?gf{B)i5omNCIZKCOzPG=r7f33CmpPogV)jih{~b>zLNpq0yfFq'
    'Igy?z*-Tyj^u*==J#Ack++My(=xmUD5dVyChk@<~s6@=c(ahujb^u(Kf}ye?IImg*CN>S1IAxg%q%ov0P}o~eJSd3Zqd>Vv7^wS}'
    '-k+rE93yllwVooM`cPFX9iV9Yej?Z4us3b=Ga!6rz4*T0Q*)HYNNr)e7&}n@ezYp^(@geEFE{a7Q%h5u#c{>rr@}Ps_G$Aw*W**V'
    'Ttg_d63pmx(5$BV8%9v(xl!dl(~KIZQ(efF7~T6FJnp`yr5NQ3DqMvITykvN-1w<;f^kV}NIG>lf{V>m?IVqc+12l1T~rByC*E`%'
    '>xR}>N27~=a_)?CoV3IRl%NWP+1IaM8Cp!t)Q*!=tqqPcPMkO)ZXEH6gJ>thJ9&3kzwjx(R6KKPAl^I8+?MOBHJrkUT-tXuS6gme'
    '0AipM`k!l;{;Pz&e237;Zb*9^sjIM%u_d#gc<=!F4X@jPlaP?*>z6-w`@-|f<>$b;GXbhXBPbeL2z3TG*#Jt+Jx4!b8fmo5S8Swi'
    '{Vw-3ISpAK%}$apvee9Z=vw|@a-a)C>tnP26Chz<xEve>x4(=9dCyJSs>{l)5(s&H&z?epsWX{GaGc0AV)R#Uq3%hHJb%_}XnH%y'
    '29dwQHsIkq>f^-CPIA?gXI!z3AIGn|r#e7WA3sF`pbqDO`U#3q>PMO=7GQ-Q6V)-#%U<y?_URr>he9Q8{@A<c=TepxJp3pS!d`c>'
    'FfcAh-#dE3ROHD}8xR@X6(0t`(&Z-XFi@urEJivPty+sfgPCqy>lGr!Q0r-vg!-lH6M}hkv+G1I$uuJp{HcMWmduOfAoiXvqbM+W'
    '#eH;DRzQEDr|CWL{Q1cqRvg{V-~<Iab^>=UgrTdbhEBiyZu|87a{R(ue>k(M?#S@({zxR=z-m-P7k5LiPE{&zefj=GJEBwsS`#1w'
    '+?{zWZC{Zk{j?iaze`cXr}rCE>9KJ~J-RY*<fsx!)2KmOI7p7KB5-;sOGZoWL7zD3tE~V>KigP|w39gj%Aa^Ft*{2J&={vo^)b@='
    '>|tsVz@`ey%yL=3k{d5CNvg)TsqB<yFA+f<a8E5ZrU}v;M--mO=yK(fuh5uc<%aj*_K&;$=7oQ+khSzJ2Z1}1jth8L7=p?_pw@XB'
    'jmgl&48<s6ymlX_%Jc5bmH2YlhyT~)k@Cj=uhB_9-^z(oq5^BlGz)kp>FqQ{x-Z7SJ+-7<ZUD~!DChk0Y#fx|ak^nUuK>cbt;<=j'
    '^<xW_Fa%;MA(it>&0*nBWYS^wLGqa)99_AYg~WOKx*?OgL-pqq2hJ;LU}}M)+Qe-fV43jNsJ&h6`6IH#p@M!@+?RjZKExCLQwz8f'
    '*(QiUt(##0(W7c2K>*&T5D+jj+AW><ndbJ*oiV$2kFCH%;n?YU5fTD?O^~`q-C&vwFmi@gj0clud;7+=w1M`oFZE11zl<!<r)pu('
    'O?1l*yd1dEbUQj4#w~n0_=OP8%{2dlojq}9J<#-Uds=;$zp_Mx_F&O;tx5I3&WWD1`GJ%?)EH`B+Qw7w``dSQN_vP9?>e-XFIDd#'
    'd5wUJyt{@#6*-V`=2PQ~gKY~c0O~*a+qbqRc17|GzI{G?`18c?cB1JI!AYT%2C}*y)NAe+9LsaMzI|LO*%$x()g21#Xh@R-VV>;;'
    '>R6!(WJnIc7y<w#E*B2%hv0v~H+H%TtKjRAJ||HEY$vn;h~u<CraAf03~dlet>wWr>Gn+>w)YD=Vv7`n%D3WBBEq1U;vS?Qnk*ph'
    'l>Ibu7-(Gu5?vk`_-guZ*xQonRJ7fv6wR#m8syiRZ;xu2iYS4F_LPXQkx~SG{so8NRS0l-JDL75EKnd>QX8P530P=o2kL^kHv**T'
    'mvSRqxt-TNd|7u@((h+cdVgK?f~zKOCOFCvC7^D3Pzz97GhY1`-*&ZJlm*s}pexAP+=q@hWjTr@-r!i^y1wlsRDjrg^Yb}}_{)$^'
    '*R~W(Tsd6GP$58A;j<9qfe?u5(8_1fPTSwQmx^PCHpGh52PFe(2<ZVayz}J4s2e~xgCiTIpFQ5Zm2>^@^I<DQfJWs~9_gGo55(Se'
    '%@`s5Xa22@7p9I10Qjw2Td^fTK>#13B77}NLghtTCI2&Mn&|5!KMEdiE>x3oyO)6IytCA%*H**=$hvSWW5JnjPHqC-P)ge=%*v<G'
    'YSHWJz{J7HDQgh2t=U7Vh^0!S2x+H&q&%P?K#|vp%S>A-BE_Jf91U8)>fc@2XrkZSpk}a{UOaT64$;X>4G-CZlnny4p$lQ=k3LSW'
    'KlhYNs6}dN@I&HqDvIg-gC_FB5G@5rFP^Wz8F<kjF*xHcP>Yjgx`!_tsQT|DS{wbdLcfk>`GC>CwYtxe2fyl3l<;-gq4Q#jBQ{Kz'
    'mlfskGA1*}4DFo0z?4XYP*uX9rQ-I|uJFxt1U!0K-Q{IY3D5GM3%%aC^SxjepZjrWp$wvh8Y$X3x>Sn(3DHda;71AmN>4(?zqtKz'
    'i*kxYd11O73mkH?^9b_}G?=RdIZk5&y`o-ev1pZTrd>q4?BbHkmqKFB-xuj@MzsJ9eF(n+j#LAmH8wzQL!xk>LXVn}81T^@`?m#8'
    '#E{G1i4(HdcMU8x0N;@|;{X9l%D$Oupg+~cq44_-e)qWf&aEBGDGe~@OikT$v;jxJ_@RD*)no*cz`LHzF#0%u)Vw}rD=~fF>Mc^='
    'Js-7tO`_LGoB)kPfF%b$X|V}a7iB(|q=*0BM4Fziv}knCM`>r42=liUd3t|6SDsqKYlIs$f#P~cmx=y0SOQ@b>2I7sPGPs#t$27-'
    'RX<Y{y#4Xzz}Bjx8k&hum!1Zq9mp#{=!PAPFn}8xE1eJS${jpEZ(klaH5&<HYtv0i<I=|M5_026ELU=-SPv~23WMucZlvlVz?T_l'
    'uX*CF6;X5q3}_)okbk&#@L_VO9grHXT|4X^xL<as6#h(mEPwl*6>{%UvmqF!K%@4jc>%mGCLe+nddw49eq6ho1u)*+CmQahmLo(j'
    'D8`%xy7`1Pt9%SbgPjtRWjlf-gTYaiRc~SW4yxV-l!6G|EECW~HR~;8tBgjcRr?>zi1z@d)mFcY|3BUVor}l9l8|gC(h3-fO_1Q<'
    'MFqf-P)j?Vs(6H5K<l-uT{5P_H@a7wU3hue{#o_xfmO9MeJh}ofs_Xt52ZMrli5Nqhsy+kiR|RcE!;o9Y`(&ed`O1^tVvHXQaobx'
    'K)Zxyzp)*O36M^w-dYRCj<=DTU$75I(OmCP-3vS;S~R0<2%u|^L(XdZMU_nAB3R_)sB5~;{F)6d08>RXT3~oD-A0FgKSVmes3m$-'
    '$Ve5EUSSgNsvEA{6&Lp&X2fCpjlX^UyNihzRS?va*^&dzq$Yq&BOO^3nQ@}q6(x(Nh0tEPpA!P%emoG+R3oMBXIJdckZJ?*m+Yv?'
    'L*J`A-$Nlu*mzjw@0c%8d8hu`W3_reru77lfOe#vW@-soG^iwaW|114kQzw7yANGOKHkscE_|yx+-_12hoXAy<oSTUhL(zvkYAdp'
    'EY<><e-5<^pQ}Z`eTpUaC6%g_VFa^a(53T@LIQ=b6bE5vhTw__H4N3~`FR_5_DkOWc@*lufS;G+nlw8kbmS5A9#s~LE<idd)C1(0'
    '8icH4oYt-X7iFsYTA@sLqMOn@f;FZ-HTAOXpc26)qBlB<-3L&%ZX<hHt?cVJfsBb#NH#hYv_N#u1Fp*K21yJe8H2YBA8GZ|;J;Nw'
    'jTLviRZ115LIwnzJrp7?RnkwsPh=H2!6gWelJv?QobsLO=OIN0RjyzzM8FjB^uZyHkQ3wcgBY%}kXj~Neb;~A@wc1B(n!^6Av%#('
    'HFWPfB7hf#tx?L)qJ$;rq$qI2DlD(<D;JzO{CsrKwXnkBK+Irkz@fcGmgPeN3+2K<aZ_3l!OV~UNLA7+dhVbMI`CXqyy!ej<J5vV'
    '4BYT!dIt2G{zGZWMT+)Xmlt%xvlJ9FJz|sS_uD4Hn8Fi4W=<0gT>cVZD3t<Eolct06S$KBaEDvbs$)&{jR=UWC4j&8C+&8ywTmsk'
    'ba!qC>pyNz{|1@CLq*$Fpedhjq+-VgV}$r310c$E9zNV8KDHLZM{KUy&h|--UpN>31>ddx=K00Ha$zp-iIC6b3y2Fk0epukP#5Xk'
    'O_(9kN*@K|dARvE?Mdo3^it`8YpKLs!?Z+NgaLQ~=nhyaK<CCM2=zTMP1lRP=037STCtyZ?HkgAoQ~Va%hwclAPjc&Bb2?UgLPXW'
    '0pxVh@#O$XV@CcP-8H*<;OWrqO{LJxTWHjz4~F^<BOe}=fh9x{LMu*!I{*vt5Od8Q9+!3?Es4?|@a7Ww0>T5pMEVGx$A!%|gJ~A~'
    'Ar?dX_3@fL$lixN>|@2VNZd@F6i>LG@udK_!;XP-f+Ye{hBzQ+0Fd~|y{fzqTBEAQpI_*~SA87R+%uIhN&}8I6hoMer2II0up`<<'
    'Q`W6D%vXIJ3s|!`-CL)Vefj+~+|2{^AlWPIEiaG^C>PEWlmHljL0?U}?(~4o@Ad!y=iU7C@u5JfBbh;70s)cx1VbR|9odUfr9oOE'
    '<a3)+w8vkt75&*|%m9m(VWeN37ET#{L_8K^48&NN<71kIb5C)&elKEW9vmM_0lg853HoiMNkJ4c$TAQ{2_;ZRMl<1S0=*=qYc_Il'
    'kI!h*4&n!&TKgs9K7RwANQH&R!5orr$@Vi94=ps`LkfgZ%}0~2iv33^(_=*iU{!Mf8;$hDM?MYuEA$~8Kmtr%3(5gP4+iM3*~IDd'
    '2oDrum-hgFOfnG+4ktbn1aK1Yk08H5J~Yb#*Wulb^~WZBb;nm3jXM_4ig>~x+2SbET_)8AR{`keW`T^#`ISi^b~p9m?9JryY#jxJ'
    '`?Y`&Ku7@KO7we1_*QBg(5{5NfTRVRCLV_%m8m|6ok*~!+hymamZX^~qMCayBuP*|p>30X(sJ(u29(fFz<C=rP>HG3<Q)q5>WwId'
    'hace~o%6O3I3dd4j$aoyfQMAB%cMhwk}x!cE-pLziGZMx1$6sB;-D7@GGN><+EazG7o-t<^bq08*^n@c^gjT5S^eou1r6W>!*Kc~'
    '8;V<8_l^a|dy9lU&`YDy>t*vbh-ek?^GvXZ__SbMWtDNiWJmk-&zDlnhs>-`hX{wC7bcHNDscqjKv}hKad3tE!iI0%(8KP2`&5Os'
    '47AC(0+TLitS<SoL8~p<zu2<aQ*uLEab9lS5$MN38jYursy-&r4I#KoACYb;Z)`RLg$g}HA4wu4VCGi3`AN}md{a%A_Qd<)?NF1@'
    'a>9a@aD+9h6Y;W9h6lellTxI3>z)qj$W3(*w)^Cs4_|kMT_M`Fa0Nkj>30rtRMA_E<eF9tiztFP6zyNOtC#18ox2P*XQA*E@K}k$'
    '=EVnuQUqcScD-cBMo2w`COfpZ?&-MumY&YE*~`fm7_L~cfqKRDWa9`AiAK<IkUz~Gg7<d(*fqFvLox1!#_v<ozwuP$2y$&vHlluk'
    '@&cL%?{t!#9cCeL8YkOw#X?)Tc02q7H7Yh=kH_b#z(h!-Z`v-r3cMN!1{T&QgaqyvIF`6j4S2Vj;nocu!hZW)bM@2J@&k6EAQ3(F'
    'B^p(dKR{T#LMgv-2a$@DlJkZQm1(B*NQ@i^s3>DgW=thZb?s$JjFK;LxgetI{nZCP?j9X+dbvLS^7_6UuMOWR7T16dt#YCTBS%;X'
    '_Xhea2@^IGGIqLgOAlK~Z7a|^%9P0_RL!37he8GvD}oGTq&Bsrij&klL?rtw_Cr;Zwk0DVIoQP>ERPF<Oay5g>?<8KOk^OKwQ2~`'
    'I&E&;kmOAG%T+~a#C<R&Aow(#X)s&LE#OV~J`m;Qo)*cf!793Iw{&70y`8alinGhFu9r)hr4NV+fg_DZ6FRDIPmzQ7hDYW_b=v%@'
    'ZRxL287nMVNlAEZa<an131%{^#V~>d;tMwMc0ndla(B}&+E*^y+sG+8fjAN!r6sa(m1TBM<_!^tSP2?AqNTZUL%LNftgJC+Q8>!5'
    'UO_|opeNc9vwCrqsnByEC8<4RZrsg@<+$h29brHgl@+jDAsmuwSd^^j1dv`C@w%xNahQ{J5)KzIO>f-Q`Tlr$s(e^<Y{6y8Z@JqY'
    'C2WtnX@VyroCgRVhCXltHl^2Y>wb6KiBnF(ecoFk+lI(4!E0(!Ut6&pAyh)3@Du>F7DtG3Fh;MA-a;0{#}#aO`HXqIH^}%2%`{p?'
    't)#Ka<;GE?XaY>8y-DLcU%QcqU0m#}PUcaU5g#ija<qC-NajTYz@-7Lj+%(Jx8^QTSrfT$*o%sx^GiC1@2aZ=*ue<Xrg(*_$sCVP'
    'h+In}f>$MfvXLT*>g2YKEh6f;oV2hjwjz|Eksd;rz|VGu0vtpvhjE9fkRnd4&;=a2c28$m<gdq6-qK)ZDp=-2ND>E1g5g3Ib(g*@'
    'pE5C0AGNu@0AW?^_RjCG5*)FlureJHY)5kfXM3EQM^SB&-@{CU>MOGO)oIDoPK_g>dFbDHVkO3};XZ@+AH-Emi%>zFf+WMj09<1v'
    'XTl5T>iT21<dCOw2+r(FAu6J%!H5AOsgW@mQ5ycZ5C}CMlcqETz{hm;4GXlW&zhQ_kX?t=09iR%B}@NJB)}bqroa9G#a_Sz%JPwo'
    'Dc`cAvo*x#_*JfZm$!o%aHBp2%aSb0C2eMXx_&TC)$@WKgQD^3)aYE2Q3nwnAsm)T2h!$p)?wd+S<NKeC>Z#3kbAdu4_dOxk*3Dg'
    '_t<ii#=5(s<z}ZXfLR-k`Q)$Uih$I#<mqN(twrYxvlC=5*Y9Py<B@jMo_0iumK>jVLse)4*a!aOh(4&S(R$LsApc<A$8h70zCTtN'
    'e8@Wl)P=!MZEC@(Cvs?*+JnbdTH{tCiM0z?=Rw~mC9dCvrj^qBt`U1^7G&LN>;+3tvWMi(Qgw~LG-cB4ZrDlsQ+#<ftgCHDS$rO6'
    '89Xq<2?xDysSX*s!_CUSicle7c6ZCBw#(B=wU22w$hU)Bks;PVZIK5aj4LeStPEnnKxD|$&A07nS5c2K?nhafn7d3OiSTC)g>;9C'
    'Kt@II%@q;H>mg6=<S2|`w=Yl*t&;Ult_~yQZM-v)JrbW&B5!R~8D>cUZ`j9~3>Zp!Luhs|i}5J~!^biR3*SKV2m3f?n_;TJkw;1E'
    '(=A(hyQheNg*+!vF=I>#!U4*QjAdvr&B3>lK*(1@RnKkC5&spNDR&0}z@!#Jug<9+g}~6RM70Y1qlsZmRKXJ@`5QJPd0|02MJSW}'
    'Mecgo`t_a6_JStCkt)NEApvuE5cqJ*E{<~R+=#?g#G)vN)e@yyO*%zF%6{k?6YfClM3e+FqvE+G_P*s12~G$a|AN^Q{u)^AF;)vM'
    '`b@)+XTn>fsbVde4gs1!%2%gZf90N=rLkEM^5cSy9ueprav9huFG_QtXj@Qn@+AZM$esS0OOgj8%>-D=iDO$3ztMWbeb8zsqL&vN'
    'Ok?mTu1L-@JRJ~cGOYUC>iGdHo>zl|<v$mD+hmeX<`j{<3Fwm6U@vbpPenD8*fna1VPRZPd4NxPlED7lpLhjPstsD;c+*INc?X(e'
    'M_8A@nXs6k!(q{aMz^KW(64|iKH1k&B2@1R8GO*o!WtO&NTkGccCqrn8n%^@9S!H12RPcRcXe)_)b58=7>Lp%Tc9(bb58ROW&#|2'
    'gq2)UG&30VWz5z4dC#J(-4scm#*M0af}%{<KpumVrt8qt4Fk2u&Spir_2H)U&+7NIw7%g0An%4gPGSmh2<Fu&G$K(aQa7TOH`ned'
    '?A_rjwvbP|qbuvbftBFS%+gR`*#UkEiCp%t5q22$0t8$NzIFva?q7Cu#w_ZG1M$W*sFe9{O#f3DAPa2~iQ~P3mpO>0rP#VU2K)>='
    'Rc=bQLJ{@^f;xErnv{kme#0y!Xx&(ek|`reb}`<zDOJPOc76D)bopc&NOCM=aK`ju>C;dokHW#F8|sE@cl3s&RBs4l*VZ%Wm5WsO'
    's>V1q3`ipvM1lyDkbh2=eD!<N!*K_?-7DfF^=?acNG;sU&tQb1&Xo!kw!>HvcE_N5WxjSt=kk+$>g8U;0t!$(C=*<EW?#v@1PdC-'
    '$yuX#J2k!rsx2f|2qlM`w{vRe?CP&KdT(;w<YNMN%DU#5H7V^R)ecZ0m>r{ajZZi3Z0QZu?n$!-dnvr=%^`FkBcrtfWr1qc3J@og'
    'oW>8w^{m>{;p@v$31j_z0(441GO}xh+STE*M6-vR7vc~qD2fd<9~7_E`#NuA`LqwO5i`6jM$$)k3#4${%gG71R|00C4q}iQYvURU'
    '-2~w+eP_TIo8=uh&$sMo=YJ<@qDm!f!YzJ^1tSa@Dxq^lkA^uv+&B4+5z4{CqBO9GkGWgcBupRd>8C#`rj|?;<xNd8vB${>gA9-s'
    'oR;8AVpOxZ{qhu{u-5M=Vf&r#)QTsU{MY>QG8#n%1ckBzRFIB`d?YI*fQ(Im-(J@r)*T;Ou6(wcbHDriWX^wguIDdrMf$nSUB)~r'
    'rp}2%$_P-4DGLb*3>^B;P-|Dvoj=)1G4<zy0AYbyEu9Z_a`0-RLd+Knyp_)yjD1^wu8z(FQJx9L%YPQR_fTNAYJ3D<i#&}%&Un!9'
    'K*X{L0U9$-d4`(+)0A%6Md?WpQJ6y@w>dsd#C1vI(pn8F!5|W|SEz~j<TUkZ^y$-l+UfwKrvrU^a6cB(bwOh$9<c^+V<^{)(o4lW'
    'fIC4>po9i^@2TBakfBcdK+5O#XREuDilkH@Blm)UsVD-Vk>v;jrVRl~^VU14;Ml5<b6&R%thqOPrz~)DufLZ1=rX-UQ4^IaW7dRF'
    '0^(Y3gx4}Ofc^|)s>yz)^}FD|KNhUm<SjC4E&!ZefD4!*UNFV1s|NlovR^t4ZWz`retHG^465D(tO{^OOz0pjVr_yqDeWj&;P4o6'
    'P?t8BA%u2?KJF~Dl78k~)0MS6kYW)UV}=d;)iW&<rZ;WzK;lB3%b&u2hd|i-b(=WDp06K5!GVrKI|=!f(KDk%vS@h}-1y3fZUra}'
    'cfd?5zeoB`I6c)#1C6GmL|SoB?(oc_j)g$osmY7?4DV<}jn2TZv~C9wO58GWvYsD+*cdV(p_vmYLq&S;-0g@|h?5#HfwBLGrgIm!'
    'u}D(NQV?&XKfuKTq0XRd0s=BMHNhJUq+`Sf-j^}=D__GoM8A6kRTgS^Sv1myPMWN%@W_a^MOX&r0cBJCXt+pz<r|@=<q4HKp@rqq'
    'fJ5cS`b!lSARRylGr#E222pCbO)<T|t!v%#FIzIb<FW8DqGjXP;Tf;{5*UnrkwFiNa|IL@k$QswyDqL?`|!uM)ScFZT#-O23#5$2'
    '9zu*=O=Y6e!)yfT+eiyty|&!xPqd~-S(j*TLGm@8Qx=n@7UrwabrKi=ZcBH@iSr0Bgypu;428bEaVJG>5R=p}0hn4Cxbh&!NmmnL'
    'p$suLYVqDeNtUf&zYVQ^=6Y39D;V-KqmV+~s0q(NHaOpLU&tsy7GRz5Wss*8FGrG~JMp-G{FF-Ilb48I3&dRH!{PVG`IxjR{Vy3!'
    ')Fd&ex&%^A4Lm25x`VxbSHJJJi>_kPcx>{6yD!)>tMyEaT<oDJrGVU$bkQ4B!sK4EgJB3(d;N}1x=`32l)3k%DLGi`Werxw<&TgB'
    'vV^BtmI6kkZ@Oxl$-vn6`TFg^THK)^KEFL?FXTPch60pBM^7$!T_>FhK4NtDxa^q2HfdajRIEMTB&C8W31DAFH96W>e-_3>;a$-w'
    'fOg1(Mm$z{Bak`xW}xSQCN-L|+LmC^^e1)V(u=RMAe1s&IOEcB#_|x4X##9Bx+U9YSpqERM_0Wn$D)u;a0;UjMiY>t6pWoL@Qrv;'
    '+@+jSN@jffOQrg`#q=*mUAT3AD;e5kQDc=#;Cu*502Q;vS0XY*6JY`D3}#qEdoq>lpU~!lL7=9q(%1ron*m1TZcjafH&j%og2#@;'
    'DmA%s#j`@-RZUydYhxM$83C6RIupzS(VBIGvPX1h>e_^M={FT~>DL|X_Q*Cs{fbk^MhzCApw_%(&E7;k3HQBUgbKI_F^-B6xW$a^'
    'ZP`Cg>Eezwsbp7<2OS+vMo%y)fX*vUbY5(GF$d@@CK5JA-okvXTpC9PPSRhGUQEs1<(H20!6YJ-#(f7#Av&4hp%ek@glPggMNu8s'
    'ZD0}d6oy?vb%Gm#Pm9w)5CN%Hu5(cyg$8y2L($u&_K`0WmkUHxbc~c^8f*m&NRYyJQ$xq-qp*b@Q3z9Ci=u|@PKc=j^`FmSb9{L!'
    'd8<iv!<_|M3$Yv-SJIG9G}3Gb+j5PVLLC%}vRAFUAZvQM<#BRk`28Z0kTN1`Bn9~>XjPC@9l8+ax0+tm)U5jBDIhwCgsw_^8u95M'
    '00!7mRAiGTYO@}#D;;Laq7mEemgKl%@w1=m$(~?SHXr8(;zpp)<213l6*30Jmm@?6&tzzTv|=RGs973NH~(1o%UPutdfG7Yh|2?b'
    'DwE{ld(PZ0)St`iA8gTH<oERS4SVx1uxh|zxHbwtdCbgUgoWlnK|e|wL>rXh<3j+!B{D;kgIts}y)Js16RwewUYxYNy)Tsgy{75_'
    '2SP0e^Fic64nX>$R9m4FIRlm(p>p+C`|{Tr)1*T8sqobC-d|iDQM)dW7+o-E7{1xP+#Nybh@Yqh=gKWCM9%F+V_N`OeC;9FLppXM'
    'bP>r=XHZqZze{|1jf#_^{P1<fbE~uJW#i09qX&_iMni+~@w}5@4X82L4q>^6wdsfM&!4Zn@{Jp`4`iGGTnG#DG8Pq9FE@qjm8lFF'
    'ULejb)0!<*Jad#4xEk;wrzOYa%0TBt0U-7&7FCuR-a&qUg=HTZC+4cn)2I}AwOor9e**pkPKGUdDl#HEU9#$=hni`cmKNQ`7ukxu'
    'Jb$SCeg89OVg@N5nHJV@^v;+8oW;dbG6-QBj-_Tz7c1t|iigD_`cPGuVysCssuf;Fqk*vq1|HAIdxlE`xrmX{>dB72cHw6!c^T1A'
    'P&(5z5K~}QUt^H#5F|-50X}3+)IeN>(8rk~%i?X>r4wEheB)mOYERDq@)FS!g__Vhk`XGH(FvMB{+)`P@V8YLvP+d;4EAtv^v5I('
    '6N;ET%842FDg;UF9cUw9!-{uUU%9f%ifx%&J;)z{KbqkbLRo3a^pp-^@+)6Vjxesj#>};gE<Bo7u?^}r$$^T`oa~EQjm!=UFgTaY'
    ';eb7dVjDFlMfHel12v>666szyai-5uJC+o-R=^*(B-kqg7Q~u#&S~Ed>g6-&SU;a)vR}9Eg2z%UKNr-!6D=7yUf3>9irumX;se7h'
    'c9a-OE-@r%v2yKKRUs+a<z=}D89AiMrSvTM_2QjKtAfOlaeU}948pKDRW6$!eiR(Dn0pAO4aQDD2Hhja8L(8Q{ZG>CQK2Hv1uLjr'
    'ZW|X1Cim@Ppv(a3wDC1GyAd8ik7ZJcIsxqRw4Ll`Ndap=r&Gh_DZNlGUe4&j(?P?4F=_u&G2{0qzhu<gjLC*OLrFo3J-gb4e}8$r'
    '{0;T8HPq~DRO&`r1pFou^bX2vWx$9RndY|)mFt~`kZlf+AP^THFkKuc>8JFL9fnQ=^MGfGn@EWbP@LihDL}4W_mzHIezgXYoqzz0'
    'ED4r;L?~mxTBu-%kfN<))y|BIuzKanNX3z*a{}ui@uMv%hKx!(+TV;cf@zDK8&zX2`eDDVzuSE)^f8xaEf+ji^t1Fg9?>+u8ramr'
    '3=`*<(H^!oN@(7CK@r8FkwY?qY%V^;YWVDN0|18;DM(?d&f#6#+Vx%@j@xBU>E*JJ(M$566)jH!USPFZEqu-21dPYHnRZQE{XM-7'
    '{>+Z$>y)1W+JvSgUuZ$f8U+QDfLSWI?BUG?20_&f>{GdecMi!_%QMc1^ad{;2*0?g%8ynE9$+4~UlIyKPmD<nmCK)fk#SakIDRdl'
    '0TO%QNsFT*IvKi>SS3-P5})bA;kw^LWJjt}x$q$XFBL!~FnjLW2njRD3l+~xE7*bZ00tHns>0^jtyz#~Ts*k&4%Fd-y@;VcXNOiB'
    '!<(GE{Rvx0>cH8!4(IB1#iRnus{p8h4W-tl90rOWg+Rz@m<WbL1u`hq*evab+9>_zUi8k0>he!V4H1S>vphJ;e8~v)LC1kk`NsLw'
    'amJ7nZ0#L<!fXM_f53D6R><H9hWM3<n+5csc~#_;%q!0X8MY(dB>oSzx%9aov*cH)AbYhk6eRZ;<oHL!irQOtt_wjE5g}2Of-%*W'
    'ET<;-<=@IP#U3={I>baIYEI$QjNv2&;NdFY008QTxN5}>oSBRFAqXtKia3~SIxizDxGY#6rfjRqA2Ypy#vSsqb*r8-p6y{*q32~t'
    '5bAG!Vk_y?C`OO^0y7m9mx(eHu4dO&|8A_yPU~OJd~m;`1jMBb=_dzjIaP~*1AQNjTRw57XNKA^^76bui7(G0v=ll55VLu#*b~c%'
    'k0ht(WK%29|4@$vBsD9x)ZP>)56!xgfm6y{uMQg7l3hl~&=_q*(OKkH)G_!DC(F6ETsav=%1CtYD%`c1jwBW_-?3&1EJShc=0USb'
    'B*HKYEi;xf15|-ef9_9j_{)aBVr{-DkY;9a_h>hxR~$yr2FzTs@ftOfMdcDT4C+C%X5rUKRp*f-mp`>$R^9m0aZ|xR=jVb1$m_sr'
    'kcHKFaN>B|u3G=>)L&;^FOw{uyu^1f$>?y7%;*vI)o8jXd09Z8ZHjJvKkeX*NIb~Pe2?`DXhFfF6W^N&aTyH}tnc7SL!{CtVKll2'
    'rZ9+`ABx<BpY~9-Fprt`z8BbrwuYV)R4op+TCDVla14^oaTo0Bh4pV2s390@fM=4iz+$9C#)K3|m-ZCW2rPg^Fk~)H=?*!~kE#09'
    'WSzsb-waU7QR0h3NQ4ZPdMC~D+#X;*i@IJ|@p=1<5T%reQ9228@tPWGHK1TA{~3-!UgDuDs*PN>Ir?a9<@*atyb)9hG)=ARI<YgN'
    'Odjc&Qw@`017HG87n=Y=fmco@1PT@}8>SOzAuJ4;0R<gd&6N;o8S0lW9-5PP!*W&@V!)~2RM7Q+N@B%Ltw`3%uV)-Rvmc0Ia32ZL'
    'fb>L4Q}i1?(4u~HZvz?cUVrwR?O*lKM6}&b76}^dWi{3o6a*)kmWhxWLC{C!EWXT!t=Uk`P(>8XIJ6?5qnbxeG-_xAbsuRlcryMZ'
    '8czUUroCx9bsvdmSQImv5u?E&QF9-}4eg$hETv;px?{Sc&ie9Bmhq3zZd;f~Xd;uwX!NTPZ50Wq4d8GmW_B_kM^rSpUq#=T^H#vu'
    'Rr}WX<}!GYxd*sF<5A0yM=lctO^px+FKrdHW#UlpLfyhgRlbPr8A_q2P%KSo`+E5VJBj{jNly~}Bhh0r3!mmJX+s>V*Ip#Jr>i~f'
    '_sb{>nuR3`Q*5vy40#AO*sF-#A=NbIYE;2IaDZo$F4V9qHnEbzGy^hYKcIP&6lX%avF2)2x%7gd;k#klS)RA>eh0t5D6^{h`E6oo'
    's+EFO&Q~xW;P>&}3;B=IL#kuWG=VjXulV|C0?%R<EgVplFpXr;96@>QftAuN6o5OeSbg0mhzyk=MB#v#2-C<8e@0L!9ts7G#$5+M'
    'MMedcZh3g<dGl^yeEnb|Soy%UorK`f%6Q|N&_mCuL8CrP$N^CR7%;5ez&XXNnuQ7&!QA5@?OT8nLZZ*KvPqc%+@F~~6qS2h9E|nZ'
    '7V76waR5fy)KEmz03ktu(+0Xr_T@E2!7gJ+%-U_#&tlC|-4k#4e^D#SbO?kOhzxaCRCflqpI$wh>vr(U(z#sjFmnr91dKb9PNY+e'
    'q7_aCy$zKFb~c?lz^;ha{A~+$-A@z(Se>*!!Qy26DHkBXFAy{fgFw@o6hYY(rR4v*`p*={#Q>#{dV`wCp@&JM0KpJNXpxcotAQjP'
    '5BME-q764~qk?G(7s||mYMWe`W;<^m+7e=IyaA1dXfUA|xOOr(?W1}$E8|tDzGh)pSRml=)XE@zRtilM51TOR;@nNEH=_xyo4S!-'
    'x*YInV`ehitqEwHs7<WIYLnKjr8<%)7kBpRJwWVvO7~^)C3r2*Uuw2i#xo2rVVW9wJY-l5BG9UL6TncB1o7bp4)U@q-4}G>l_H_K'
    'q!BX94_Wk<B$HUIE1B$q>)+VKwISklx@OfBL6(^okwhc2-n7t9mYGc;Zs=JCsXxQ&ukv*Z)zfNWvSrBjR$3bB#<5?naq1pfLTijJ'
    'eP7MnxpE(GgJG*2&fx+x3Msc5qut7l$19yAr+@@Rml@8RhJdzi?Pg9rebS2nCuyT;Rr^ARa3po1m;w0)Xa@VFHy9)VXf)2*IViLw'
    'R@d%B!yTTM42z4ZIDV8~`>5H5(KIqTqYhoHX@@~6ZXTEJdnopYKiSJE!)8ZM6$(5!S(&Pa!a@%Cyc#MmI2R}qAwELG;7bA%7|nHC'
    'sbP@gU>Gz65x;x9@VMrvLW2y<p}sJ$H)^^zu;SX#1wxOrSE&;MaSQG^T@YB*B=ppC3YD~8xajDfLp7rI>ciTo@v~@QQw98Zg!3@e'
    'zzbm+BUqt3g2y%Tzh37RYB>QM)T>{)l{&*LZU?5sphty~N{<HR_^jMkw!f(NIXiLayS2G?e%RiB<y&|;U#O2TLkofi@E5+qUTsxI'
    'AAljEd@~?JqZrvtjG&<*!tmNG>t0~rldMpc{BH7|<GL-XIS7(;nrSoxtB;t9fyEHTTGBwGSgU#@^4GOnA&Nt6a8EDKd?rgRxZCBz'
    '95?z1bdyN4ARj><g{;lNz?}-VM+3QpK4}-?+K0l7+NY1MlAromQ2lyYuYyYQ=;1cd)525^&vS5Y+Qj0gw?&lqUzdK@+*n@78Z+od'
    ')8r)K*GLnLSn1@U^nt$HBjKl~MqI~Z)2}_U5Xjdt$6<An@HB?PM?*t82zwfz#+{FD5mpmnLv)z_`h65hW6bB^e;D(Qi4!PvE7EJ0'
    'j|&sbs71tygf_PN9?=$7DJDAkJcGPr@N6{508d(;jwqohcYOlfg;7Rzbj3baC@5G2L<YAp;bImpJA`Lu6g5Q7NwLH(?mtbqVi%QK'
    '26|8QlgWco8PbAa*e?GMW$LVw71IHx6XE@_x=K4q{5EIFU#Ucc12rSwr$z;}Bb-KtZHfB~&72kml1S4h2#jm@u#SXHA&ln=(Sno7'
    '%?kAmsb%BD5gs&>2nskK$La?`bXeSk&MngNltmozU|xfnfFP0yqw)}#O)<@I24y!+-f*iA$eKy>L9Hm5j`C6>IKV*zPDZH+bDKh0'
    '6Nhc@R;Rz`9dJe!LaT;e(<nxq1}&WyCHxYiIqqFd@<1sko3lvOM%$&mZX?gTC8Tq+ZNs;M>jVG>v|4?olFji3C{RJVVRcb7Y36(u'
    '31+%(BMVQV=EXE5mH0j+GI1P~H2ck?NtpCyij$K--8FS_ZM1mO`ob2)*g!sjAM&Aq9?)5AG&K;`B6k-XpplOM2;(Y@bi1PY`PE0|'
    '+*e)K&_;a)L4;y8fUc^AE2=%LYxXs0G%1WnG9oivx0ki8ZHy9uoQ=qa4K@Tw?r4J`Q%kbM;7kwl^=?Oh-EK}?nyQV!34@fxr3M!q'
    'Ov5f9@G@6zl#e#ODI-4o>Q}UgPS5#yrT7$dfkIK!Ni|*>rl}u#aUo%jJ8oV)xOh5)Uz-X(Z^Q0wC*`mzuSn7`))B!LF&p}79*`05'
    'x06%>FIVQexodWDdN22BhlNgw9LgYLcrO^7Fn9ysB$!-Ml0mo;znuI-O1kopi4V7N4kx&GXq3bDsf4*OSBJZmh7_q#kXnNKh7Xs~'
    'Kgf`vhal#ljc2ZUB(G<A1v!RZ1)d$~C~~7gWyDj8Cu`(!WO8cZpf_OWtMm3{JMT!e)etG1H;PG$YH}c&X0-7F_aVb2xO~xGvcDkP'
    'p{us@>S#`heP1J+8bv`6b(?ywhXugM6aot6zAA7qB0Ai(_S{ux=*;k~eJ(~5QCx$89!dz>nOw&}Kv9B7ieNq(+4?ql?WO$J{Ugah'
    '9ZrXpAoVPJk$oUg3?dXwh(voW%M7@60J$)$*5-}89iJ8~TXh~|p^L?Yt{wm(STK0;zy%4ok|BJ8iVf)*?+9pLjMbU!`i(@qMBg3;'
    'uj+ogI1LopKb)9e(+Vbu(BV(=)*#HHUj>w)HyETq8;7+U;=ddt&ox~zfCmyu82IW#LfX;B7zWGZfH532O%p>L;?3HP)Dwp_65G-D'
    '74@Dlhhs1NH)u7BRT6~Do&*~;!rCYYPIq>h4@`4+Oa&<HLSckcEI=Kh2f_<L8rf`ENUg{*75veTuiV82YVS{FCO6HjTecUVPqSlG'
    'jWN@j?__n2C{S)LdF??_earFCB+Alc1~lUl@)8jv$$V6kGVr_C*f%UUNlBO?4l{3Bi-4S2wwtr`Rqj89(gxBt-{K^HED%a70wSCh'
    'qru!@0GKGNRXnfU##zPxx|<?FhaQ4~x7J(n4aLXcPQfsN48@_Yrcns64W8bu-v$o4(sz>|p6aa2VGCg!tUb+=g!(FPb{I5+2H10E'
    'VK0HtacGCNhx5ckeolqZ;2FbCw@;>64fC~#n{a`#e;Rem@h*Vx=*vcX)#`OD=t+Pn6JlHP4ml}enK2Rz=$V5~(gkII6Dj=K_psQO'
    'oh(Xfplp$IG9Mz&KlsitvyO~?)~2ZST21|gelFTZX&37vl9vTAlN1tf*lDgZs$f)<7S0US0VFm`TlgxaRo}cb-Y%*0e4)a~BPX^!'
    'qJC_n99<=PS+t}L{1i#T5Z?#g-M)JD3YRzzH;f=Slp}+df%f#`k<jq;A%zdvXpmUtRAlG;WfoE&{g|scKy_%a(kDq8IbLM`J&kS{'
    't@zQj;$x4gX!CmxGoRhNKY2$m;Sbm*LcL?|OUn(504!)iJWXYEtSHmzJ`Ypfiq(M)8$_J2X^PQ@!Rv_2CgOv~s0<1&F8d(zEMd3!'
    'LzgpLmjiatxf#(iS<4LE8KN_Kpk)dN-!J4dhQrCkZLV5TF{@5VfWRGI8MlZBODEeT=^I!HgIJA-g3Zv<e(8&1<af)~L<$DLB>6oK'
    '8stNLf=4hzQuSGb03msYQ3L8xw3>XkDx75Xp$qh9E=4Euypg3OL)-YA&^-|&8qI~lT8Y^`#hUfqs+BhcniOO46ms&(qQi_Vpa%{{'
    'S&z*+BMv|_7_m~sh5xp2#SAC7y4cI$BpW78S{+~yLCJ6+1wDoG#2Y}{4}kF5(x+Pd?tQ|3cP!1DCod)o(uhusDnO1}&Ey8h3c3dH'
    ';U-S^bd^875veKjZvUvBA+iwn@Z&!U`XgWh=EzgXHAH^8l^Sf%q-&@SMnPk7ej7fwvVFhanKdZ{q-5fcYp7Hv`1ntN*?8^|707)_'
    'Lr9YG7FNBTab;Vv>>2MbudR+Ga~YG44mv{GFS70LnazwtSx#Wh?1B$#?b@&4cEuLJIpB#y!=nnK?<I>=CTYqo0YP?>Fe7PF^`~Do'
    'RnJj-xT8GGjHUg@?}y#fg<lN*2_F}xk%p5X=$qv;kBCvUGk`C2gc+Xbr#TL*{0=GOZfSFZvVHs+zrTB$EHxGEDh65sDcR*tVDbh7'
    '>!4VncIyO@e$L6)9MJQ0?ZcghZ~o)>=kd~vp>_r_qs1F}f`}0)xk;x7nHk~_hOUUn(S9yvBLv>P{>YC789y09kf<?@nOCQQ3Q+@l'
    'h)O-+46b&>C?p4hBbrOAiBGM+yIZjKLRSi{I3y43rl}X`R5Ak*+8&hyZNeU|I~W5l@t@XB2lA>r_#EmjoC{a}WOM$L&6{b#<@BZ3'
    '0AnaE*k9r$!gw|~4$NRAcM;bC2nIe5|Ln6(y#3z2`m+0SAVghFMKA%J8wq?!R`AV3xNjM1LCx-DM#X@=kG>$aT)%ktjqmjBKNf<n'
    '9OW4vO9enR<Pc#Z*&ksv;eru}{6<3D*;cG|8m@W#-@E^n9+r6UKi%<b0fXgYg`ZEtO(7&K*6UP8w+zG+K+fA9KQ2g5tJ5S2U+>QB'
    '48(}L=d%0~3qp7zC~6fHS_lb2)35N0Cf+lR10f>H*AK~`AFX-*Yk^TmY}Y_LCO0u?UO+c0G{!M1+B3xxjV)lzhk4=qB~MxYmxV!B'
    'n7+-_R5){7aIJif5H~uK7N}xqmE>=NAO+58tXnUV1YiDOyXACHDdN=zJ&pD~o`7h$(Rm^p!?(W?_2WZI+6U|1zc5F!@I1TOsVfTJ'
    '$aP63hzt$Z8Qni57MNTR8{p2)b?ae}b}S7Y9W*Kl!#{oyqs`$g^L#a?g94IFP}a2?2pc{<l3{yyGCDYX`MS-Rn}ge(=C(cW3ef;3'
    'I3%g~Dq<UpN*T;sesF{&FnKUVn92kt(29zswN{xE!DxGC!eQJke^9JCa99MCL7GeRs&i5>VV2r|sGs`Vg8KzXE*WD>To@o9H}WmP'
    'Oc^yUG+e~6n8Q-I!HR8=wlt|?#h2$IGoRA1gMbd`Ig9E-TaLJH)!Jthcqm{?MkO`5&sK{`2HVh^e~{pE`VVsJDxOIz_b+4+q(00<'
    '1y~ulJGob&diRo=qX6d3npLYZHep++nY>)t=|~_MWl3%gO7KoL8k)@nuY*Z)y=l^_Ws4VBkc^+c6{PAU?uu2e0I3Em0f5#~%s5T$'
    'Fl!b))#8_L6Vyh6{pIG%a0m`892P1@kTitHB);%g>2o%pEemhxZaE%z|9k=F$lKF^=8Bg~Iu8vKw{C!5d7;P|6}|>)7b-?MS4!s)'
    'K7Y!etz1JBLAZdc4H1Dji{&2N5R6|)1Lcz<#S6B}xL38SfA!Z=V8X77+(Bv%FKOjKGn-Ti(G4npSgDpjhbH0swF_6wt>un}+W>J8'
    'f-RIn>?0%)hIC3#f#)9^y4*D8J`Kk-LtoMz1Q@cH#lG?R=t^>h9>OzU5O*rS8j@Bk2LV299ym96j|*BO@8h{@&GH>by8t@1b^IFa'
    '!Q`Gyai|%TloU*XW0pM^5V>&Gay3^RkSlylCb%$dJ!7X!yy7gOf1qyy65#0*jkpR;l?xtAnJ3gf)UkN{qsEb|KeJGImN>5I6!SFc'
    'BMOZDG$}e`45u8sA}3<++$vl!+~HX^<d~ZPa!}?I|M^(phfrzQs^y-!z9|L^!xh>^?*~l_nLML<<#5sP_sosL2wdUU$T)YZTJa-y'
    'fS=+#b6zHX0W@sJ0|Meh#5aNgt+<p@B4%OAzG|`4D4+rf3aQkrVa=F64=^b}v%&DGZDCHJDMN@0M{W4@G@Rr5>tAc;`iV4+#zI)?'
    'EY2*KI2{VC7eHAl%7pi_7dL&rB>B%)@$_!_Tn?}1AqA@#GpV)Bo1-nkXTn3|hx5NM5Tb2l9K)wOu3oh~4g;`&)EVj!Gq<==!AZbr'
    '0Kgb-GAZ=&tVtwnvwmrs`f-<YNk&hQ#S52Af%H%9F#7yX)b@#1vO~@%<NjE`Ix@jO4x$`BzZ5v2{9qz2#6G;GEq+&#s*u+U@s9*e'
    '=mUU97wT6ohX;5_*(B@>mI-q(Ou(oJdYU7PZWv)VIX=wne#M%s^Uup67h%;XtuWI7K;&S^&)_Pv{D>8K>Bv#@gXW~Qi=JiUh1%OL'
    'PVpd*l%>nWDEZRha2}N&1L(s=0>E1Few8s)ju8ux6elF<Iy@X9h^}~ft1Om<9A+le-*S2P^^1c&(iu9sld$X0f>K;F+voy$O?qb1'
    '4TvxOe>~;kATZK}gn1U}dBqp@^!%um56n(2%(BDq$2A(=CL$igy2L{BvPtA#fCfjKfgeu>RloN6Habb`3T#9YaTx>)^~Q1(1sxYK'
    'J(J*M=npTE`yVmliWsUt-@GO4+Y)!S7ZyM&1r3JdEfQvrJp;~^tqMN;*O1qle#I9rf6DwoV0jI0cMD7N%Q?io{^^&KIQPprUD%$*'
    's@u9Y8w396&L_xS(41PO_n@qV!49G=-f#)G1Kwyq{`YVDuZDBw)(6mLG_Ig|a4g^-c|nPsHaZ^gl?iW@Oq{^3V(TXt%uj;pPd4%d'
    'Q2MzB#9OZy4<;s_pzT0%E`6^CUg3K+)qLVo8KKi$It~?eSd!B==Z6Xt%!1jRj#i7~d+!ush~u=Cx^b>pxEgGuU%_3}Fh-ZeOJ>)U'
    '6B@@xCMLf?tf!MKZa=L>G=noSfZ=k$#FrPfpOs{rivqwvf*}a1BODb7Z9!CCz{F20%#)kYofk30?Q4D)UZr#z3CZC7PV{ziOZCP^'
    'O?U=*5*eQk%BT7HVSn#8rJpruNV-@bjHbaApC~|r-q5tcH3;yZ7BdD8sr&R`NpN*{0@oAfxL@KnFT)d$+d_wv#FZ`+E@)_c<S<D>'
    'BV#b^R0Sb0+?50m7`m-pxSY(<e?mY#gF!4fK7_os6$V6KgAvd{^JV23QM=$zHS^^<BxvmP#7~<sD~J1moFi%UQjjcf)DR>-)iBhq'
    'T!eox*Z>|xjtjvZ0FQMnn#6wbV54$vknb|D+<hA4m$hCkXTG?lc~WpGg||g*#eg<(>03!MfN7J^VWJK#Dij;|FMa;8{=6iy^|iZr'
    'xiK_bXb%em0I+?Tz7GD<@pCyD)CYW1l6BQB`ldj>d@7N2Hkx7%-i@=2NZ2y1WO=}FJjkS}#OKM?tyuxJI879wOeg1;bE9BWIw%k^'
    'XqNZ#ored)7#d%<pb+RsMZ3~jQT2*_6%$_3mkW<z7>p#OjP~quQi{^$${%^+5!W={=nXR8nvVw)H?#<|MD?_x_<8_(xU(?5g~ycp'
    'b?X)eCy;_`eiL6XKWhN+z>#D^O^!wcH4Tl7nL2)0w<H|pZNXTtl}L%cG=Q{3UBV}fS~l}?ez;4P$+jz(ea&i$({rgb;JdK|F_@q$'
    'x;VupwgPY<3>+V9vZlJVi@*r7Z{`$HYjo;mNKFZbm*uBR1FqLRG$?4sSFcti3;_^Os2k~eL85^Phd}lSDGa`c_+J`!!`xuIYQ>Kx'
    '_xudGV=t~jJ&Y9ub?xBvHR5hEU6fJDQ0>s^F=ocpEqWmR^t;P5DuL`68aRnwrVn^&Bk&eQZRYjqo*^Z2b6&OLrieNdjTnuT;9Ldl'
    'OW{t-)E}o5(p)TbfbxK4=Z}X}7M87ItI|sa*2W)&bPOIAoz~GQgF!X4RIqZS)Ud&I%P*RX0t=0L1BeeG5wAz}r~%*QG)l{yU^Oa8'
    '@u$PObx(?h%ZU<z9-eMS;5tK+a1wxYhoPS#%~jvG*YjvU&(Qv5;Ux`)!+F*t6$CDtM9C#1?Gpox__%?)03}G9U`{a;iVNP=KI>xi'
    '*W?W{6!2hB0h+5cR>)Y8(KwB&AmtqwE#coj=>Pg3{|CL^A!q'
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
