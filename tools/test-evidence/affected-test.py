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
# 094277a83d1f039217dc812e7d7893f216837073 / tree 54cf72b98fbaf212fd7a2383c38dc43756968675.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'f62474ef32071bead3be0106e37c394f69559311776041f215c4fd04686bc65c'
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
    (
    (
    (
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TSs!Rj&#cXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO-_qR4XpQ|CoD<&(e5@^)ELInGnvWK)+fS-H%4'
    '?*GHfACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hm&%K3*xyYA1jcwO<O|$sDSv3}Q-IQHfrJ`)}=KaN=(&O>@@N#_m<J0stO}}ofSWi`3ES_tdcgsBYDW!g?t0k-E'
    '-Vg1&p)9I2R`0L)lAd2aJ-;4a(x*8+riVE_Ooz0&?mSj=GYw<bEJcxzRg+hK>^RI-J=b39P!xSJ6noa)TB{wWF(3Q3?Hm8?savML'
    'p8B%OrXnAPq3oNyue*ADf33Gy`RwIBrH7YK|9l<p56fX%-|Bz;@$LTo)%&iUyCs|RzDreB<hkFxlx5L1Lv7U}`MW7^t6i%<9e+vF'
    '%cuD5&zF~7s<x?@q4Ak4X-;)MEzR8K`CL>(Ul&t7XDKT$9i=~){m(;nap|I1QZ_ep+0S{AEnSvneV><>pZ)l{=(4%X#_A^@?D%9k'
    'kzu+&c*>ur!{=Yp!>@;j=g(h;c+Zc2yuYdkJ5}Q}6=PLZ?O0Tu^Ht<+o#wi$>U^nF-nLnB&8m-nxfgzU-D+veR1K-^$}yYT!jD_J'
    'ah!){T#9zd+Ad3Jnyy>-I9^_L8J0Gi%Bs!1-MYy7Arl$Ov6}kSRa3hR(@=NiRnPe8_2J^0Q+%S$ybS$Vb*-N_^ktLvT|Sm+Ohq-1'
    'S(}#Ssx{*z-%Veij^EPV^K^W?{HwdV$}&%OaGIK_OH=BHx*Xcfp%T05Y3}DPzwTMDJ9rqrrDuUV-94q@@$m5F;x^{4s+OrqbyJC&'
    'DX&tQ_eE6=)7WH9URM##TvgX^<MG?wbbMG2m)CEHJT+ZeH;p*CUW-jxWcAn#T|Li5W^-arRbIV*+{^Rb@4qeM#q~$$EUT)yu3MKx'
    'op}=V&<m$-NGG!N6f*boaP|65psVuY+G$$KZm5g7_TiO6dpqT0US@+^YZ{8Yo6D-ncKr5;DE}J%`23JwBGTPG9baG4-Fz6nJRF~2'
    '4%6jmQ})w12<Uk|)v5COMfWtgI<vZ|9l?1l1}RH_^)_DT$BPRWUEAa-FXq(x;O9P`zMZ&2mbvgDETfZ{+IIKCr-OH1eND{b2)?A>'
    'UoHor+Q;6ep(ty4Ntt3(b)VYN#Zni2n(|D1Xtu-c{U9%VIet4#pM<^N4$p2>AK>TVbw0e@oo~FjWiNh_b)AN4E`~9sauE&Zx$66>'
    '>LMoQO&u@8lWA|>&H7cw$8kTr$|WyHskSMnxtN>2@;;h*kli$WSM<v=w`C@yOPORVyL~gS(#gw_a-N2~n~Fx}QTy#fJr%91!Dk}f'
    'tGlI^Xq83EZ{EYN>FFWe->q-y;!gTv^g!mendWvZ+eHqvjC0Y{xqNJClDy3MEtZ>i@@;sKZqIjed`J1|kGrpj=g3tq?kbCmt68dU'
    '%+e%`w5fKPxkcp)d1;4PTX{;i@9H@E5B;_g%$g}Gm#H2_OF4eqI=w@g&E?dU$q5q2n)tW3@8a=Xc?|dKSN$|hFP8&bH&<QJR+7?U'
    'k)rllU6<`NcSBP+)<u=|vy64@Z{CueYPmmr`TDXu);4Xq$f&ZRsz+B#@}1{ht~^R@JfOME)ND&Teqc*m>6QmjD>bvWFSD{Ky1a<2'
    'tBw4+=)JwHE4!{N=9{-5?U)6-!*4$9yYG+aau(pMs3rPE{pJ~z%0+R1Yy{tBR5dR7B>rT#KbGeg-__;A(mNV$EIq2HrpYC=^v><%'
    'LAA=swyn#){=irCGCX}ryKjL-!kZ1#Ec;j*XC(Qs^Qx^Kk~W@DBR}Y~bo*O6Wvg#j!FYUqn1_u(<Cydgj`ZAX$zT^lqcm#jW~!9E'
    'O_dF~I-yE`)1G!*Pi0!vyZzYoWmTqLwVjR23|MiJyV)_0h%+tO2Y0mIQFpt-;8e@si`<3jV(f}E409SgCtH;>lx11h<08%a;Co9C'
    'za5^A58wO;Pp|HBSyu$k)5Dp{aUAQZaYc+nla$qI=*Ge`bED7Y$M&@Q7VU<r9ZFS2+l;A$(ae?VRsyEH9Ob@^58jTdzi&Ht2T9<U'
    ')9ta5365juK+SD2WdiZ&WsQ9^^_|P2bf=AJDQx#+Tf6C&A6tNygxDEh`Zmczrl=FUzQ`xJNVQbuF!$5nw6*E@ZN*8p9$2#ssq7{4'
    'Ri6u#@jg3Av+!-V&76;md$ud*zh_s^>9_Q-QB^Bhdx(%1sE8B*GS92aa@R*urVbif3gpAb_OmMzNDr&N42WS)OF#9^;Km)Y#>YPa'
    'Wb?)g&6T+y+{zDG(YM2%Gv33PhX5GLRI0h!d1~vi&&L5|V0UFPq<kK#<zxH0J~i^*200@fq#nzFxt0tLkvB!<hy#oZJFK#0{OG>q'
    'M|aZ`9P#1hFx)?HpaV*-sw!NxT|Y|Omc_%0oFE@1yLmam09CFZ-qW6xpmg~=IQ|D(G~{qrg;xdAhuoB1qd?7vb}ovKZRUpTO%6FO'
    'd6PGdFHG4y)QjxDt(PiKL+;8c+=F>BeQaaT$JZyI)^z-u;MUXSY|eUfrYIUbnLydn9ME`K^-%%<&1Vm70x^AXOOaLH?I>X(O!75g'
    'U(wbovt@M86i}DBEb0XJ6rQ@Q%d5X*JIipmf879jyQ-Vgkm@0;>S59_Y2~(qoMkFJrl~BuUIQin;JJSJ_P8AG)Awra^5@^W^qX=}'
    'oq>Zy%mysuv5fNFEFf8(ouY0&c)DMnUY}pwB)_IVp0=P--@N?N_g#%Cccy#qNV`RzJLV3R=1Vnq=_3`v6`P4HTaTlKi59)KPa2j&'
    '46mv&^My@gRn|Q$V&C<D2C2{g=JIVZm(W1R0y^5(?h6HdCX=o6v6jffXzOn3x_ue;m)AAirKfL)=jXMDcrh6p`(8gH8XZfQ#u=ue'
    'S*lDNtD&t@H)X>t=Ir~)Uyt$jkH@Wm9~ZQGq8s|QnksGCLTHQjr5k+C@);cGGugN1DQ&qNI`e)ie0Zhy#~fJ{;5+32F0jes&YAPl'
    '9_D@d(}T<Zw{$nm-wu~=5}ggnhxnI|MbqehKqcm78g#b&zY@SzDHwJZ1m{)vfQeb=5?7W*fz(cEY83XBFCGdK@X@4P69)F3r60ef'
    '-8sfo=BXGJ`Rc={T6KW5QME2LHM=q^=CKFD@2nSp?Dy>Xl-gNsQI+#tLiy{qiUL3NvggvL>{zR%)n;>h#p0*JbUHqzyI)+759x9Z'
    '5usHu)90wPkK3kcq0D_2m3yxl)u>a4Y1xU<{kVf~$KTRgjJkq0uEHEH*=nn1V^<CV<4S8JopCq9#d=kHtMSke`}c5NRGB7EJS%<H'
    'nbudS(N&N6QtF=j(vk}(p$bg>xPSefp(URewPQC#tqn(MJ6~KNZa(qOhgfyOyS%&Hzwjx(?0DvCAn#o>w{U$Gxv#L3OOK`IYT?EO'
    '5Q9$iKd)W-&l2|X9iow)NqYvVYhWR5A+zs1cz}N9b?0yr3E6V{^5<^f^!R%DIr#4KsVn@cw~iK~&Tx}8P-6F-enQu3wDdP@WZ(Mb'
    'QfqSNvOdjD$(Jm3@jaA<Kj;SNLQ{-$cKs2Mu&-PWpTh8T84DUmH)#=FR=3I|<khu3O{u6I!X!9$GL3m2Z{EVbC((NT*2^@#2V{fU'
    'U$G55{6T%3-0YI8TAp#kHvV||dVJUiXvX1JBmi}M59%irp;Wh;C>3Buk4bgxc~v(&jHmPkrlU}q@BZ~PJU(t^S<{#)e;0>BC<qM9'
    '<v7-Zp0J8M<!S?wVYuO70G2K{VH?yMJ-rdMJ<V0L7D0oHZd)-%hzy2WtxYoRUwVH+(6>WBltC_8G$YcSxsfX9RwX%@>rt06C@{+v'
    '_t8yRf&N0R>D_q#e)5PFr`w6o<+>j11b1$lnsP@qbo%9=4iAs7FQ2{j`!lQRlMMgUzmmiotfnHmxEsB?s8YT4_54jTd!-_1EdUX4'
    '_u{b>^^Pp*FT1h&r!)ug>Bo&l>2Wu_#G~5=js{htG))as;2;f7#pLT%mb8`HL!UUssoepNzPGV0($3-wi2TW8DFSP7h0geBs*hId'
    'vmU2K0PA*8X4cF4jof&7NvWE%8QH03uZR#G@KG(+rVgvoCyFQ14$ICZ-=MLGm3Q95@bvBYboc5%w~@8fg%80UspA3<o3IV#jG$JG'
    'ygXmf#B#-`Fur#mr^@rwnJe-6`Dyz9nmn?-vH#cTB=2wK#3_jaYt1w_@J#7#*WnF%MYyMxlxt|<8Gv%%uV*u${I=Z(w(|xctlPSr'
    '^;TnBpb}1#m@1_De$^Zm{=_03whzhYf^c->W>ymC>2xEL4$r%f&)oQ4rGcpcMHR_y9NbQCP3=9*wLg+2HaqB7oBJAH5BKv4|Je(;'
    'ifkPsP%-ovKzdZ!EC{r18wd!DOuMBFerEph&7Cp3A0FEV55;E}&r3*{@HHWIS#*On88C91A{Y;O>Z^}$?4S+w^!8HEr1Q(jf<9G&'
    'J=f`$=Xg1D9^H;o!??hw!!JZQ&%6F_*x7?S>t54ic+%>-e9DptJ;I`Ot)+UfbJ0_qAEY#*#;AF<jghA7kMHV~^oS8ZbZ9SMs^fs<'
    ')dCm2yG)>(eUNkSs5x=iwon16e>Z-7YuCiCS)SqSJNWqX;&;($`Xe|+DAhoYu7`SU_!~aUbGm-`wpOyQ<Kx%id4nB|G}#FAwl}F`'
    '15J=24FF>V041&qNBdzK|AsSmx(au}*R4LMC;{7<3IJl;t&r)G#wlxxDM)IC2bZOfZ|eE*Wo1VkNI_J-J3h)9u;?;W^Z~SK65z*U'
    '*ZCN<t|p1D2L@kF{~PwUW;#3C?p>lOi1r%tYwzr-hE+uLBdJy*Vk4y)`usP11aCrs%iCG>kFh{OvQit+PzM%jibh?~*LeWa`lW7!'
    '8@KbehtJntmHPdmpRu8N47jRuGvO#BN}z6yPz$JS-roEczwc_jC^uL)0bL<yyAKC(s`4pHyx~}I-LWV`sDRk~;pcM>@s}Z;vM3Zw'
    't{fLKDg=ZTpGAxZA&BZ|<vp~ssz17y9iLf&Q4^#-l#CY2h_|cLKFWuw8=#xhARE=sZa=)0bN%qwk8L9YWKk|Ht<K3Xg4oM4Ybj}v'
    'R$-uCSaehX;2+)E6<Y!d0(?Y8e631CH3n%_{+AbYOmk?)0v^vURFm`JDFj64ouwkZwIWtPc9>qavEW5FXUQhrP^E1*^^s5Y83dv!'
    'Vd8LdWzEo**X&`dh*hO2LW-_#l?Ms}io7zo%-TvbDTacw&1nI5|L&cQCjH)wnxUdlOXxx+(Mhj{N47|-QZ3ho$oroiPS@Y?uxz0g'
    'snFm@;u@kT*87Jh`e8&%)M;`YbgIUS{uzUFK2B<JS>|y6`3_b82Z`2Q{JV{Qon;;164N*Cvoyl5YKju4t0EW+rg+&7>GHBcIlPR?'
    '^z(vtt}oCfi4avK2Ca&F4DE_DQwn%`S>@$rP6^NY_Zz+5z8vd-S;nPqn*wE!7OGXWmAX_B{S(p5{F5IQ@K<^WRQ&Vs^m3q_k|?iC'
    'mzNC=x$Jz#yn_b2O2~1te9|kbBP|YEWf2-Y?XrtYt|vue?w>d5Y<biI8u|#o6OL4d&pKxyw<amvyQ!vc6a#*C$NtBHCt}Fub20?7'
    'SC<)<8o;;JW^53kocOX=4b-Q)c-r`V&*Smi-EVH~c{`;6WA<w5+NTX1f$^h$!D^NP(HhH8W;l-|vOoFEPua?xemlflRNp<m#Oiwz'
    'y)48DXe0qx`ruP6)=_mS^Iei7{(ClSdJbEQ&cowNXlK?4^B*gEdVfAwPc8EraicmY?l|Z&>0iSVgweLm=MHj;-M(+d=kKcOM@7N+'
    'KfWB;is-0LS?B2LX%OuouYk~VJ7_V0GmVvUoQ4~B@c4Lm{dTu!BU7-ob(2!NwsFfuZcL?GM{*Xi9xWJ!VW_X%$gYQgFVkqRjpA(;'
    'M9~%)P#{OhKZc?ir*5EjAT_*p?df>$emR~}_%rQs`|OuhAon9RTR-}=-7tmb1$aG}d;}?a%$+QMzIHb&V0`x_X}E8-91*=xjC~8b'
    '`NCQi`4~n+)um?Xs}_<BgHx65-okngcD)Off*IXx5zvBaR#(VY3yn?@?SGh&_W;u>cE5}Nf4l>oi*FlCBH4D*3XH^zyw>lWBLKES'
    't#-PqxWz8edM)=ZIj84eb+7J@)9d}=_g&8(tQt$}TY*j*DGwTtQe5Yxuh7eJnGl#{CpT{4%j4_aSNzEP^t=IU>M72OM@A3YC7S(t'
    'RZ2`iI%V|M3LHCcBV~WXK9Hha@2Kt@JR>a{Q2}ubhqPIiX#34kG6ff*A}6P=Da-ut+0Y6w?Px{^7+!~Nqnwsvnst7uC2A^UQiT++'
    'Fa__bY;N3@i~9*P;`#8ae|-C=i;0&i2sNdz<UouC79dlrBTJDvce-73$fC6niW~QHLLi1e?gg}{k<#J4EB3FDYKHhLJIa=ZbB6AG'
    'jY5*xcvO+Uw_5gjnd)0VtE=~u7o)&2(T)^dua>}~p_1^-W;M8wI!V6EpSp_td_Uig)33We?xBkwj-tBd^?<8`zvD^^A%AG1mS8Q&'
    '{FiC(!slvnJUq->>`RquD8mG^DW^+!Mv*`fmgXj~vs`c`LY<o3-}B>PI#!>T!|yMF`mf;U<+v7_9SNO0Lhmuk;-CviCj<3>9IHWO'
    '9c_2r`hQZUc3&&X^dab`nnze;(Wh1~S0ySDE|K178|*$n*>xLv3agc;{hJ_TQVNBQj)E3MH;lm5FuNg%A(F{E0#v}u-c9&#4Wh;s'
    'cYGBo)f_5hAXq=55V=&PpUx*)#gcFdra?)1;|@;w&hF<CiVjt7z+6PYig<l+#1T0$cNSu}vO;R<s@-?}Z%6-lw^|xSwYm|Vq*a;j'
    'T`2;LL1D`x<+rG?gicC<6Rg7Rwa1+c_C9`x4qdCE?L#1et${=9iY#lK5-ik(L2<LSAi>NZ|0C^^Ug^0*8RCO?U3t+<9~!3u=Fqs|'
    'WqLXETK{2d$yJK>R+n$+g!@oX^m@d3((kXbgfYbvAk3UP4P1YjFqF0e&OV*A&J)}z2e{)_6w$F(eG>u6S|<2=ebR1E)!xO{UwS;Z'
    'gX3@SPX7s+!TpZ5Yk;PX?yO>GgV7?sAa#_=bq^mm$zdxHKIZI}?HnGW@r!dYzVh9Ax_f*b-?%WB_ax-Ie1W*o3Gm$n?3s1$x~`?V'
    'p|1qvjkx(A+Eb|8=%v!VYiWzQ#<V1~2n~1vbO)B2(7E{pQQw1U$~xF<*u@{(&kyYz>A{j-4&N?cQ|>?vcKQ)zFLiL-RwRJF4jo?~'
    'P-x8Lzw>a*uI@b@-QKhnn!SZAn)FkyzGLL$LFHINiV&^15ZnPQ;34@fd-%4t1GOZ!_E5mFpf3;}0F(3)p69}LX6ionBNn6mj`J;h'
    '2zwuUc$#-Si{xf1L-EA*%t-;aW5?i}utXqbm>Y5ifW*|^vJb7%sKy^(_273M4mEeL5~eipX`>ioHcI(9d)Se7QMbgc)$}(VjuouA'
    'JKbBSFZ=TQ$=uD2dQkR?y)_0%2Fk@*LJ7bCoZ{4^+rA#y{P76@aNf;7zuj+;>LfGdB?yS_6NW(Qor?dLDh+8#$akA6+ULJvEAeNS'
    'F#{GWO{-s>R!$i|B9BFkL5#&5Z&M#QcQ-e;?<H87&x6CVf!+j)3H{DPlR^{%+w!KsxAGYoO~=;+y(FbuHu5}td!$Kw4u0^dwZBE&'
    '_Yd$y6&8<!eoA8@+h0^XT4-a96o^sn(4?DU|4S&-=N%P56*ULgsMQm19S!{zeTV^&fT>$SIUw{f!10z%oQ}tIuMoSu2mG;+iOjGg'
    '$Akbb1pF=J7v!T^4qV5(YxjRP)7RnUO-3`kY<?@j6NY35M_G4Ssts2Gbh}xQQGLIp%Zm1Ke>nSY@_4q60^xq$KnM^L09;AGr^UC5'
    'wt;pf_5w)@n<kGVAeC-^5Id1zPq)i)47H?YY7o_i$BiTj^%HGd`l;p4Wm2bx=Y`ZL8mMBbn!Kcd-@TED;nN?}eLClD)8q?@{O#rI'
    '>IQJ1w(GLcA)_QTnb763(@z9~A`8UrgT$d12pPzSziCf9jJ=RX_~;SghqIwDOZq>7y{h=rUIh*C!7%LpmJQ7Zu6r*VjQ4_sebP(Q'
    '=pDo6s|ljjv<M&ALyi{K)e>dg-?F2p^v~C=n2*dHM@NL?=f&hPl1h$1KBy|%w;jnXVNBJ2bVK*YFNcR+SWBZ#<_b)4L9@DavZ2+L'
    '>_6DD>?z%lRd8NDx+Cbvb7(XkrnKuYK{o=yUHgc-rQTSdHwqO!#Br8Hgn-$t^x-F^;rLxOy|pLr$J<epXgRe4p)Qk-PY^G&$nfxc'
    '7b!)WKf0&q^x~%a0^5BU9-qG+H+Ds|Tj2^qcJ(`(a8!x6ILkGwU|7sS5J%De+jjN(cz+x&L(NN|@CtZVqS(BAK$IegISb;mPIMsk'
    '2u)Q}d~{DQ$6wRKnKpYl*@EE)D|S+^47F^W@K7{D$02{}OM>?zwm06qp?Q7^H2x{2_)k1+as*vl%0}uJlox0o-f0(hcFaO>8oR1+'
    '#iFg;x*h)_8Wne6UtS(}1tuX;-?UhH6}%b*g9_^tA;JBEW66c8;oX`yAKlRN^mKUKbM@<LjSag{NJOo^q*0ap0bzNCD!;jdgo;$j'
    '`GE~>(@gb9@^BzfQO<?TSS72vW{*Ik#W&LBLPS-MH-GT+@!KFyuh++)Uf-AFb?%%FlrdPikrS;LIbkL44f?BuiOob9JAH6V_lJ<$'
    '?m+95DP5JQnn&S}LI#R8Lxvftb%j*13pJ03RQ(<MQPrfwmJv`m*v&O8&jle9A#KCHiVuy641!q^4MDBb?1LK$ITL@mT@jkN4^slc'
    'C-Y6iY?WK!O?)3j`EXC0W!12X^42Y#7)Rf~u^$v?mtS2SE@gbpIhD<WG@2%~jlR7ihxf)v=A}B#{;qAsUr`x%Sh7k<ytZ(%;^Bmu'
    'jI}tmkU+j*owo~_q~tEUziD5~w!KX_MJI@(=ong}3RgMI?q%MHIASF<lH>mL!41W&y2HwvF-wG_1?v?W>Ogne5q<RHl&R=BNJ-Hi'
    '%0IZ96U*_*NB4pOxv8wcaz!|lYE+c0bONMTdGNYbiyY>{I*G#trs)TFb-q7dA9g-09b34p{MOw*C}C^rrVdXea2^mmhCVofP3f)M'
    '`f_|Z2B%!YecszfwvEUhg4a|~Usu6$M5sid7!?3oi!GuY#^}w_JCKFo;|6Sb`5PN~Z^-zCW{uXMR%)!e+<a<^CSbDmrpEVj>qhR6'
    '^J-^xGLO29_*CIUPOFDP(ytl-mj+s$nn>Flw#)t|BKHUO62;K@C7r|fuB!y>kO!u%ctzDT$D<5HuF#0^s=}YFRV1lSKDMz{L_M!x'
    '+H~A(MMQ!oJw%w`XWOFyPeCllxFaf5#6>G~1&40k(-{`|^D%92$q)<`Y~BtbiGz|bTv&p-t1s&)i;;1t^V<s$tFqfWzrUT}NF{|0'
    '(~*GfG$%OQb82pbYD<2PnTF~cWb>QTl80k7jsnf2fA_?;7{9su4DWvmu3}n+3c)EzVOThUYx0mY@xr;e{y45V<f$COnSI@eiWD`B'
    '7!XPGFeVeF@y7#!h{j`zDGd|wG2MK_f)?XgtNDfOeMk++Y6z?3(0_{r+;KGh;}0nICLU0gL)NC{BRe`<L)^W54cEQP+hGQrMW4d5'
    'lErXI>#eWrhiMu;FYFkK#+y^4b4jKS5*-l^w@C+~&GoHg-@~kW2{#3UqeJd(<_{4b7Y9v^oA0spCY|@)9fg}+TYy;`$9(y#ToFjE'
    'C9j*!T1)4P*$LUp?R#18c+!r&UprA^CCB$}RE5<9``|xL^r5n*_0++Tf0*~td~ip<ecNI15#AwC7lWS+=z&vra%fELW@IZJ<5p&g'
    '^)TI>2mRJX;`&>lX<O-inFV{O56HTVu@{!^!XDC{71cF=X=PGBd|)T(_u$J%!+N*vsKxuX4}*shZ)ip?iR#eM9XG50D51i{?Cv9*'
    'I;>A8?R`vrPQE>bD>7mYYD;+FVO+6@tHK}#1`>uWW&g1q9e31Y#{EQA7R+6fNX$IK>j9Wi5rk0@zIjB%_IAiKcJdM!!|`c@a#%&O'
    'UWThfi@eP{lk8D^PD$QcL}j>y1n>j<IFkXVExjR{9cD3~G8jI~AQrxp<`4V0at>1zpFAb)m_D+V@As4lxRK{fDrUx%5Dq9W8B3Ef'
    '&EZ=q5IQBQdbhbx{O{Pzc6Sf}7HT1SbzgNG2#j_m)hhT0$Uxthc!H$y1DgqX;f8ifC=2;Zxa+a?tIIIkn_?22R2e%)0ygj<7^jcy'
    ';w9WV?}Eg&iA5=gqa~_YEuE5(+K;ZWa0jsqq9n*n#q*Ka`#pz9I3YCt8)i@ZHCXK#tA&f+YZ!Va-kPRLRmpS&Xn(ZaoM!!*d)}>$'
    '%?%+x7i@Y&&^vM&?9_{jxlh^_N=_#k=o9Yrw_K7QOlT%xDJPEYhWJhEjr(8~LlMXDV#73sKe-}(%Xm5vXBpQ1-0Jb370;W&!TR@`'
    'y=|G~5atxKya{xvHCTr?+Nh%HC3aaf#8?>br##@3o+Pk;?N7XcD7y_>aJ)5=Fz=u#Rf}~A&ctFuhhxz~qg!Y+)K|b2@9b+W5q9s2'
    '41S82#TuA<Bq_1ZE-Me#utgZzX*l;DU|Ze1t8?>Y?|!7hAj*+!L1!SobImu*1RQ<BN|%&ohCyF>e)E2QWKr(jl%y}ljYjo^qO5BW'
    '9)lrGkB?qA3~JBL=8AOdr<;m@w|`G->l+7vyc>O7VhT8fd1VnANz_H^EU4w#t$UiDhUc$rAs>z}!?yk#tb{w$hlYY>2mBO?JnUa*'
    '>@f8L0<MCuxPl+|Z@W2T7W;<-d1EoC)ciNo{~`>?LJhf;uNx?;)r5#^w8E|1`77+Sb5mg}G-FQ?)ZzWdq%@ZJnORC`-K<1q$|T9d'
    'Jb!FcQ4R05>*KRhE+^AK$#EEi8`H<qCsQQ1frE!`sBCWC(RU<e_l6j|7UM*CTBo>IV~kT~K$={T1QC<azn3N7{NCc>49~jVSHws4'
    'ZXr8V3)kUiU|gy6OTSc}S~KWZtGieFTX%FWKjl-eUt(Cm1{4ov!eux6D%?w0&>$x-F^ad0##f`-BC#TrY(Bi5Q#<Fl|9aDV3)fAD'
    '3GTGSHD}gjXeU)WphB2k!bKU=2Y0si2KMeLW)0S%@Y0(jbdZs0t)MKZMymkCWs+U{({Vjl?dkdJ>q{hz`|lIbseqJ+T`Ou=$z@5i'
    '$IXj4L<ObTp!ra|?%vmVBkR$Aev6pX>uMzZg0~=rJ6ujq++GRHq7E|1%-UQ-(M<?%^__t))e_!uegBai9miiJO{!F36Sw$b-Y~)l'
    'LnS&_dNk(zxNqS%CX~a&=Fq?rAG=$wNtk}Jr@#EsW@>4os5jMxi9IJH1{shRPD}WbjA~Z5Ur!N*b^neM+wb%#TJdtpf6p&3qfsg#'
    '6v_;!5IP?D$Pys|GS&gV$GHAjcl^|H<-N_E``za!bN;7uJ%4#Cp`TmaW#&<tIu{gDBS0&rED{h59Q|k1+AHYJ?`&l=^>;x)STL(Y'
    '=c7(G;#(6HF+W(~Mfj{?>{t80tCwK}QJx9L>)!{t_j!Za8sj5)EqWSFIOCz=LBy6I1TYB00n%2EX-Xg2#nzJ$QOqF-w>d|XxGu%G'
    'v?2zTFo<OKikiqLC)=M!pN{6kAwFPwI_TT|@W)EJ-q4r@k2nT!GnA`?(yL-_;7-U1N@&1)t#-eH40YNEDc|sPwz@m1NVe)@axVnT'
    'h#~-uB^+U3+6YjZ`}lKBjGS-#<+^RK=DvFxA`86x5`W$5qlf7&Ma>+kGP5Q^3B<J}3%u6Q0R0(bs%1aj^}F!jKW|vEg||o>a{+L6'
    '0T-AdW55)BTs8Q!WWPEML(^Qh_~{kIG1&DUuqxn;Oz4mnS)1@C)sDgf$7AH69@<<(2&*gfac7xT=x5F~-L{qoDVETf88-IoXj&$w'
    'x3>5saZ%^`Q|xyH!g{=J6KB}-?I3J8&?&T2AirVsY;?#Hv^)hjUzwm=0i|&V^6tv>sPDw-X`eJOkLf70RvgM5&n$H;0(BWpUfwg_'
    'QA>?(U|70t2M8s@I&pG8KY-X68Bl2UMTViG-n+Y<NJX5C0TYb<e`-2+aT}{7Wm^g|=Al2}VnL|W#5I9{tfm&cVIZXuAG|N;rM~ht'
    'oI~^vk6@RD8ZV11w4q&0){XFJMB6GXgL$BA20t1XX}t1{=xL2YWqhF<%hQ0P^0WSm3JXXF=rHq3hjt1|joXyz1-Gv2mVZ6S^j=;z'
    '4kIm_U&k{(?n^M3eo;;j%DDoCB}lzf0Cwek_1e$>I&5{PV?u6_K$QidjAaiIjNO>Zq|#$H0{YHF3%z^oaHl`fn!bf~Nz5%s;~vkc'
    'ipf%e`5NfD1O~ue>COznc?1lx+|FZ$LS1}tC!5+Jlhl|1bOi=(c#w0_jft=*L&ip}-dmJpOEq4<jadE6_1a0TFyyDFkfLsk3C|!K'
    '&UfyMFiHpuurlyv$kP=sCnQ0ig2(;GUs4G^c}etIA?8g!9KS!`M;Dul|CQ0qF-Z(nS0MG(;5kw1Hr4IB`sH|7brq||<8HYhzHHbs'
    'N9$ROJlI2XC<VeTDK7e)N?7g{b})uu6}Ru`qzlFNQ09Kwnv%m(Z;8RmT>gYC$P!PnB@{40`qov8nGD9h_qT5cYw<`ye13aoFDy@}'
    '4I5C7j$XLrm1XEm_=xH5x$Mkg>tb9+s90;>BwGbj3V?kb)ih{d{k}0Kig!gB0kk9!YI&@9Bgh=i40;YUDT^7a#TG1@epe^1z4%=g'
    'grUq1oN?_qvpnQ6Ex=~&ux8tq6=0zs<?dB|78}`wuW%lxJSHH`p<pb-0zVI4l)Kbds$}Ndzg4QATTK6E)Wxmy*DXVvC8)8HN^m}e'
    '5};xhd?jW>Gzkl^Gt96?d&+mNe?pr#3<6`is>T)&t_O^SyS;jbH`E-R3Xh${DrL*g70(KRH#O~^UYltMG6I(roe8r*TC=i=?2+y)'
    'x;9g>_M0|y>9-vmpU5_#ew$Or+88XLppJRTF?*AG68F7cg$i7RjH5CFcQa%AzU;qF>EcnEv}IS$gHA`&=n0bobY3~pjls4L=77#('
    'lCT+hi}|{9X^srOq(2{hFg1^tUpnW5E{ISu?t2O;L>VS{lp?TBOcUsoqI$k=1FMi{W7rj{6K({bmLUd$1dv*V>)ae3g*kSBq3A`n'
    '_mQs?mp6#0bd1We7;FUw6r}iW#?Uc+6kDi?LQH+#6g3=<ftW_1{{3;fdwG4>@>UDgjXMiki&##^m10OIjkN8sEsqgX)Irmx>^0V1'
    'k+pcb+vDV9`1LB02xY_)BPryg(5fk<>gYnuZ)18<wrABp9wwrLS?JnnPZNAP1i%S9N=4SiL~ZM7UB$<&ENa<q7n0*0i=X{ePxb_N'
    '+vekLAUA?O&kz%<i$KOue0@SXc=>_`s1*}JjXg^Pb(cS``{h=t13k@5JaTz}rxr;b-*a=js6W@&-&C9SBEO`EU)h^~#;SqCxHdL?'
    '^32RI!XoBCp&z9fL_0->&xZiPWi~_8hrB6idRz1~Cp<<*j=@P=4qrCP{yL`WfCEv>VLn72ascT^q}mZW$r)H~OgmS9voC*}F)bDP'
    'k~W??@BP))k=k{A#B{;XFuvJ!xI04W#7}C$e&-feBIn_vu`NKBuRVf2((w?4E|H8nLsfx)mz=yTijz(G;oFMmR_Csl&6!c7he$0('
    'L&Nwy?-Z~GY7E;UmV2yCf9n4H{>oRr@tpQS#tGmeELhgDs93#jilL57rCIO-Ik$AzY+=VUr>x*=;2@_p$8=@TIVk{wy~?7hGQ)cc'
    'zrT%TzZoYs>^4tRDSEZ8#fm?Hzu{z9&{N5Xbh^T-QxA2~G~HVCIKPIi$m`=zmA^m!%wEip;>omF$LXD!0lWkkE0RHkX&lR#HN9Ce'
    'pH_TcEux=y)uoIzHKU5a%QPB{Mac1ZTJIT`2D!*c>FCL}<KBfIL&<AI!-mpX(;%1vee^Y&a2-ODlnFS<F;RoKh|p)qH(3_nmt8yI'
    'n}TotHBfs!1LP&ql0q%eI?0F%rX2#BApcIAobd0fu4I>8elhIfaP-?08YYUEr41)$>{SFw_72(zY*=}R)jL;?vf{AKt!}~}!5{TF'
    'g(xe9OfS+QCcoi}=@aJqo9F%BMOPlpo7jfBE#yF(&s_GUR+HJW0K>U7hXZ?#Vw;*%QQdNFP($XMM7p<4oar-a$1R0z6~Lcc681{K'
    'LaeECu6^G`FW;c!`1y*-`nq*jJXW#%xS{Utv}AC+*e-SvyTcmD0b>^1h8QYbVkBtu&b8lEg;KK1%en}S9E!=MdX|2D@J>RjLgHu~'
    'A6-UH7&do1mtF4v*l^4;_YkHHV;7L2dvctHrLy+Fq<5r3CC-Hv>|E|JuNF+huNMR50#Mh+kD=LF;1PN(U6iODVAs<g!fsXyxc4}n'
    '8ZHm%Rk?UMqlc$M!@!u@zba;af8m!*y=_c3?u?Q`iro);7yjk-+vPJ<hpl1EzNS*oLyN#~lAyPVyfzFNd6C8ZmS*RAry*o_&)*;r'
    '7ay=L&Jfbi&^wk4of`9i`w%xtiE~g~#0@FHvUlA#`tA0s&5`T^2w-F>SUN<MF|ZaDj0hRDbyn?WTufK5yfaeyWOYuk4w4^TNio8x'
    'wAB7K(g@R*oSUj~+4RHyzW(v}>qZ}QZPvQrS<&~QzZr?9`D(DK#S9D1uhAaW-Y60C);APUKALbyCdhX25v%dpa|3|GMG7gb>KyO7'
    '+PmKC{mWsUQ+l~9G<qpKXoHp)0$#9MA1(ZtzX^<I+^k(w>^@I#gFlzS^81vZ0BxZug)ekK$}tKGlfWz$E_=MWU=XTiu+PpN{NRwh'
    'YkA|0q&K{H5PrF-h97Mpc)&cjUkVgPPs}8Soy(tnkvXg1zkJ<5148V<la`|*os6y|t0eWQ_^c1db-zYrCso<G@bd&-+5nYc_U_sl'
    '33CcBRGybrzz)g-3@jCDgw3|RW<k$*^TWkEhz=L_B13)Oj#iuDO+$G53tJ?0a5mRrzkA(aQo-_e0MuZ^Q0pp(LD6j>5aBc|f^n!I'
    'gQCW^^w{i;(%;>SelViC{L`r+rlyTq9zJC!nNS}(4mx$l9d*ta;RL()4nASFK=MEE9Dm)&-~~f|Wx>q?J;b~!Ii-2!iy&h=!JFj&'
    'us4@J_hZ)lDs9MKt1uLldo<zrr(vb`4m;PCph-k1iYge>-je0i<i7k{JyZ6e3)dkNk<^@lQyar61@Leq-v9vB&3x60cQ`W_??VVI'
    'Uque)F`d`Q3YUfDF=dOW{F&)B8h7Mn*R6WWcn;6U9eQ3vf~dd!#3H0qZ7_PGFVL%?Tqcp3xSEG@_wQz1c3S^(=EMC?3CN|4^wS5m'
    'epRc0gT7DW))6;7bJ`n5ULRK|@%1qXEgKyH#B7h1J#jekNpfmmwpu~|BYGr|)Fooe-kaj&p}DVQ@RgeDRicrt+2xE3&1ho|I!m|}'
    'l?LB&vh4SkD<{LqFcN(lcDQSsjub3n=Qw5wtVD5la}%>kLWGg8w9I)cGoT85`2FehhCko=D{J$+4bn^>+&%4Pdc~%NHZXH#<JHDU'
    'mME9hFw}$jH4DE@sydGxxqQ^>u<GVZ=cd9x_j4fu;dM~OAd4!-gNx%uan<@~r~ZA`^<k3b$%pt3lT3%RHKQk}uX#)tm6uKQ+4-hh'
    '-(PlcMkMaT%lwJ;3$$Rvqm%DVM_i^M!uk$R8j&iFL>{AiFohv*W3$Ok_{$!4E$lIC?~eht(bniWp=$ZCqs6L6#4#vrj?1aKdg1s_'
    'Z%{)RYrr#QELe<6WG18_UF|8-2o^v=Ff<ou>kc{1kJ)w9!aB#a-vv<WQ*z=6iO5jZJE;%P?FRcfsOuXmJ{}$kQMM8>rBh%oV@!>#'
    'VnD%K{u_=VFBwr4qm8_6bM&*Zl|Nok!5g7U&@`=vvJ7^{943!C=Bi;CHUJYez1ai^6!^-?grMNyWn(%)3$ZZ53}}i^Hs(qMX&Lov'
    '-27-x-VN)wvJwMM{iY3F4^)yBw^~uw>DL=aZ}x*2hWjW)1L;M|eA93ES&RDH@O>cTr?;Q|-S%(y&_vqqAuJMNv{w~lZJ{8XWC{}@'
    'V+27xle3K5Y}h>;+A~y<f|)}r0i9}|ny8JT4eCB=F+7<+NsK4JmnlB9oqdO7G%U(YW@0oPl4$Nj+-UdmkfoG16?aUzsk6SklXd*#'
    '<8auRN0`qhjcN2pAzDNvP#fTICo?<E#|bJL?$@So%y}#D^{9RK_~sfsXzl?QXdbnOJi1H>nzBF`#?V%wEsI0-Fzs9TB`RNHdqXMW'
    'DQuP|+P-7>1P>wl*OKl+^iQH^GK-_xhqPgCcdxxla8FlzdU{$%QD_!!S(viHMi?3qYS^m;xg%85%+*xE9ys7x(nSq>#U`$#F!exY'
    '_5(3*QgIe&H*2meDwjGSXnZ%Oo!j#ke%!$?uaQ~p`T0dMG_?u^YdBwFKH&E`_ksM+p@)o)xoHB|EPlo5(**8=RkU(IqlC#q2JI6J'
    'uRU0)Zeakp-4&}}cLd2$1tEn4F%i?ql0PF9%0p4m#JKATsAyEs)-8{RzTEvVFn<4FBCLFHZ5cvvv@&lzCiLhzWi;x22ssc1z<|@W'
    '8#t$!yJn#RBg{RXLi;wMgh=#FE9)XN!2Rj<p;Ye0=3uP%wy=L5l@Fi|n;J#528aX!rwzI*`x;}4LbZ+|$*<kU{#mR`sP4rZ|Cd@Z'
    'Oot%6ATsK%Il434e(LDa+_r-^md@pJ$ILCX2#h;PC+U<?w1JbMw^2#3vnitkJZz#h|FMOA-A@VuRwu=nusDrBbpZl?LC_Y4Kx<6~'
    'K{?-)lK=baf2BCC1}Gb;H`F8?dQ2Jx1S5)Qk;(m|ffPC(_?<hknm)9R9ZXAHsJx$4+j3#ec5feTiCCLAU>-v>OehA|cKL_)v3oSD'
    '@hYmXKCmkm2ppb@Fi7tsh1SGl6Q(X+%I@mT#DvzneIvi(a^TZuW-{$o2O1Z(#Y$G2TDO(zC_K5`*;nrYvF9Ou*%n{IYd!x^vlU@H'
    'V|a;aYVvqwSOyWa>SYHQ+9W~zbOX=fWw&)-=)y;eM0KeV(uW^%&|6ZN#Imk5*@f$0o6XmTh_~sQyQT<Qrdvf4S(x>vm433$Y=XGa'
    'voxXpoUT5VZ(G<strnAQLAI|#OQUXV>-8E}_k<;MjM3Hijd?pa?&JGl*j*0ixWGmsEk%scF2apxjC4{?fdr(>jPn*lK#Sqp&76Ar'
    '(u)Zv=`N;KJ#BOdTd9j;2J#JPhJES{P9XuvVx03ZpwLRJZrw)=cX(JcEEm=0_))#~Hf9^nc@{=z>d@7iwrL{8UD~z#K5h1g-`UG4'
    '!?vS`9SS_0tVLC$um}fyuSVsCb3u`a_=tw#B*6sQ{I;#^VUTk$oMH$fzk6PIt~pic6b9y~FXr{mF<l$1cx~u{&~x_M>VzO};g0Kq'
    'U{Oox)pHRlwO(9wy631yYOi{_HfsD;v~afz_!$Z3G1TCNSjGe^x+6TU$^Yv3UQx>haHv;(<yQ6?X1N_qiJ?cuNY$gE9PcBy4clMp'
    'ec#U9)aA9g_Huvt^3_>*JzuEbFhe&44e%GIu#UE>(FZU@%C{Uc)CMEl#0U+IAPirdWqk>-?;)&EBl*2so_wx{O*Mxgsne{{3|4QM'
    'ios$;u|gUsiWO0h%>H`qRzz{chT-A$(J@(T!Q*k+nB%68pqnJkLOwzsMb`FVaHqod$dF6)Ny}-z_Mw<j`|z`?<S%_JRKGf`SD}&~'
    'J#K@Z7E?K%=WuRq;^3zjn<($UFa1MvV|^jlm_cVTO)ez-G17z)t4<!J5BhFR!mp<$uJhO&ul-~Z$gg9LV|7Y+vRvU4Lqkf0y%?Y7'
    '&Zk?%Y7#br4pZO0k4@5;`5gYon0F>lQ0O8^uS@v2m|&(B2~H&1*wyz)Y~d=!L>WHMkaq^pc?>e(N$cqZC6sb^Ou$`?GS$%y`?x|u'
    'VG)Q7x3R#*DqMDiXETa2k+X|fQmyVk*>uA$c4`^)p7fLD!BmD?5QgpgKg!fTN>-)=rW5i0xVlO^N&N24lE1AI4F{?x-dCeS?S#|W'
    'u&v-eqnT?_kVNKnLSVdh57&{f6~a7ML<?W0n-%qq)G`}_BizJDA{20k<LU<?I;?I&=N9SqltqqsnAb292%=1w$|JyR#kAoJk=+d8'
    '4R`eia?PaqDOypOj^U*wIN+dxlPMK3w-w4Uak#37tJB}}4t%2#LU#?l)+i=ULrd49#4i!exp$f5K`9qDXS1qJ+oiZ|Bag>5q`TP;'
    ')2|z@695df+Bl^loAU+~sE}@~E=5z!oL_<j)7`d_m8Y=h#blC7z7I(z&Os?=zl}5rU7XC|<RqwjOkKP-T0F%1fh`7OgM5G=^796I'
    'ptG38)Ih97cb5%lr1Kv!t|AZJZqWS3t3Q=<U-i0%HuV*Ph+=huu0{(tsP<Ub_SM8_QjA9#QQq9Pmup+wj1oc4d5{e=HUuPh+8|_V'
    'DJ(I3(@pq#7wvf4Zcbd9T^qp(LrQX~;ex|7sucuY=c={gqpdfU2Os|GSG0;w&-wXI@hNmcp%~LiW4tn^>Dbi4g~S{m+`K%vJe_8|'
    'HWhq4Ovmp#*$%7W6)6p~P7rK~+32f1pgefLWk?lxxti-X+_H<)d-;-%EOfTWp#~Y_y)Za2c!O^eCRZrQ5N?8BF8>H6-S&`)pKjwE'
    'PPli(D2Kzt7Up8Ej=NPuN-8vkTEczf;2QlyhJ+qM%%P2!-}Fe{zU3>(F?tm|JLo8uEC!W{r;4X4509gKNd*pi20OnxZ(q0b1BrGw'
    'M2hpKm{e5Dfi%su@h117;Sw%i+DrSJ!glDU?YudfE3v=qkxjKhK?v%$dalL-Ffv6zQSL_t4kOax*4i6x`i9O7-@VTzkBKNl#z2n}'
    'LOauS3<8=%5UB`uXu{SvTduv7|Ga-fGO!P)V<o7bwU@9D1jP`c#DqxN>#)qgtpns@R$ZGndOKrUvFxbxjD_ATCgSP=2w}nS;=u)('
    'xRMb*p<*LF^Nv9KGFGRnuHVSaOZ5B0@T$HXR;PhY_Kz>7j%fv5h|uvTy)}ec`c<HW-ry7pw6?i+L;lMdd0x{613XA1G4P`giL?_N'
    'GYr<_z!;ulnkGXW@#fl%>?aP#NbEu1H>mf*9LHY#H?*47Dhc7TmS9sOTpQ)!bZ3|O$u#%DRDg|LL>TcE2cS;qL3jbA37d@ysg)cv'
    'f<Nu}mAkk=?fpxc>89!9maPNO*X(Gc#^|-?%dom83Jf=w<=PJ=>RX>jOrqSH%s?|fBQJ><Da=P>QU<^K82iR@Q%YinIA&gVEdp|8'
    '+1{O{ui^f)QQ9DFJBwZTV?ijZARywb<T02V2Ear)TE+d9+c>NE-*&S}(9uK4@z&}p_=ds9aHlX#kf99J)f$C>ZFqWl{Wdu0hQ3>V'
    'c&f85hb_W3ti6~eiTWDe>=-mn46ygjVlTnxe6-EAALogO{FpXE!)Oe<ZeN&UW#(&%o4CO2pW3+PybJK1zU*AxwE8|4bQgfB39*H|'
    'Bb*djX0&2~o;h?<7u5bbDg3qXVYMwgS(NO7vV)wnIEb8o_|BMFCu8qpQ);~;rhcNI2W?|(7uQ9kF)V;hQb^wL5ObBOf~hDgoEg;t'
    '5}VQ%UuA36@7@{TFRAl<p^cG8L$K|M`q@Sex=MOkTGBawN=U+p@29xC$K9*%aEbGAV+7$)wgxSO_Tt5p(0KYt;SC!NiPe%e**Slj'
    'h3t=h=4v*m4jC(bNmA?clKIyf-59O>Xo}!tw`tSn_Z(*4yLbQM9bv*B*k(q(Gxw!%!xDf^F(F=4nU0k*UH7@^_N}-(u(3hpgsmy2'
    '55w!oWi#`^Gb%&D<+7iGJS*&O{?PRs-j@TG=-fuMbX8>rZjb0p5429<aDI``42KI7w|>`(5wrFw2?*Tr%G@F&EM2xK>1(XSAT~xs'
    'VKWrkFZHGv`G;lqL<$37QusYKF~~=K!Xwy_)Hv1<Ad+{C8mPyn)#MMW;v`2OdV~J#QXGOjpNFNSp>2*6-IExR#atNHN@n+L)~r9Q'
    'y7PvhNy#goLPPju=`fQ8)Zk#sdN%7u96&RSSlPsd|6}1DGn{aB*~@T}ow}H`+F%c%WDJmkTA|!|1GN1Bg!h&{)#9IiOxQoYY|WdO'
    '7t4ZTL?@#P$Wak9x#3t-TmyW##pzmC`P~~)O}QMOzD3WFEM&O<<9}@EkH7@x$SdSBkzcnm2HTr-jp~p`&{&<{n)j`2e_Zd(nhXSF'
    '%fz2+XsAs1_;<i;o_nH#+*cYRN#-pa_4dM*?TTg3c>ng=(UCNlF~z4tN2vW0w*9r)%pA&=1Z%bn2kY9k-@xr1TYz)miKF4Eg7m$@'
    'BGn|#a7!S_P9e-lF{%39Q?2TGi9LK$9xlex{?{+h$A=5Q82*Wmi)j?YNeKG-@R=uK4B8psi;i%?6MZ+wvC1z<8K2fRCzS2y$N0y)'
    'CtE^Ig<WN!6-cRC?*x-K46H-3qIN3-B7L8eA9Fy@)3u*J#qiDldink3(u|>^hnQ*c&YmDKf|6T0-GrGTe=xctk)wED$|eMUdi#+-'
    '7i9d!5TXc|dX3x0&k%|0NZ0ys1ee0Wgka5DMybEFTJWjkpFXWv`$kuaRvgKL-L!f^r_u~Wv^|xBHerqH4rAaF|8Cv%EU)^6&k?<a'
    'bK&Yw?#_R5_uaJMa{5xo0ArLE_LsawjAz4fFoRL<5?lum3_gy3_ueMH|K6wQ%RX%fLh5Q2K?gX`L*OG>;hRUeUm0qlW*@?g%7DF}'
    'ouFvBejbNkozw4syAgE5QQq)a6@Y4JAi^ZsZ!wy<U`!%^9zxu{+OgJYxaQ0Mef+=D{TdJc&*A0k1_tY5#m|>;D}(}z9pkH<hjk!c'
    '0Oa0w`}2bIw7MqA^!3x3ok5IveB3PiILtDGL}$~i!APLjz(nn%<r-vpCXFt)0AY8odH(ALqfTs(fp#W088jb2Hx-(3j1lckv81sD'
    '#{4ud{Bg-smj8KW&}~fLHZ>Jz&IMP5&k=FsAZbArqg4uj6M__+(|O-|vn2TPfi2gsL#4>84Lwc!o+ls;H=QTh7~lRZs2@M2r2S;Q'
    'FR$h(ZamMjAEGM?Z**PC1j*2_&UF7sESOw~4Y;%YzV#TSy=)B~ZDLds!#_XBXmioe^Nleb5evsLtZQQ+?DXy@IUPQoj1HbZe?2VB'
    '&Ea;ZxowZfjcC9LjwF?@BHLIhWteyP!3jw)d6*)mvY-U5*s*l1watkz+TKh!#@*o$%Bq9IB2b1jSM#bILczo=wf?Do>OU5IT7l#('
    'W9$$YPRPeu_?9qJrp86XC5B}Vt8l}Lb+?pR+Ogv6<0dm-X;>nl13mkox@gOZ>s7S&ZGwjaTQZeYH@vsnoWfumz4;FbuCM<&+`2Zu'
    '$tv8x$RMOXW}*UC8Uhvf3aWP<QgaGmZ#KVbRbvwl8#U7yuIxGzB%_veYbe3Xu+fOwOn4n8$<=w5u3C2U0-Hj{uWyA^or1f<Kw%JQ'
    '!&V8<+6FT&rgr4lEPATNFW)BAMgjYWo3G&zK3E(U6(b~#@L1xDx2n&Xy|*mh(5LnD`1H?LFvoH@4QSr+a)+=}j^Z$=`*N_HQ6?@z'
    'R1!*Yazs!fM}zX(mG{s@2p728hzQ~=%RSr>#xK&q@JR{93)^MxRmIi6`s-F;!eWH$j{zHp1?jAc!84Qyjf_yu1EDS{gQR=y!aL^H'
    'LX4wC6{C=rC<Z)uU`G{BcTyR~q4NEph`+n^^Yd%^ga9LZS?wDiUxqEYLXGh31i4dXOh{TqI0!h}9=IF4=7N@m_i?{#&Fwo*yTC)N'
    'hL$k{VZacRcLL>5v$|SAI)w{JF1%~GJy%@3HYTqrrmcIUL1OVO(Ld;$Kmta6qL!;rw{yXlt<2MlqmJeAPmL3<{$`<imK@jOEA}+?'
    '5d(~UHz_(}45u7>M^0q#ZWR}dJA4Tna^@yL4rRXhuZxQxqSB~#E%)g9Rt#<oS14A!ADR}KyivX3aFO|EbE6o6NBGUdIJeui;?LXx'
    '{u1ZSdFlKDG;HGmf%u5{5qp?jg?kGn;u4thxNEV~D4-1z6sc4n!<v~sH<%RAY#6@UHcCXc0J<p7>$_jWIj+C`b<bSCAWhR)1eV$d'
    'XVxXIL&16h%Bm;}yw_fa?)@d@KZl5?pVs5@{AM1qVHJ~i(c1Rrv?Ux9577_zzZeK}m4$JPquXA+>W*<3G#wl|niz}#toM*P4CoUO'
    '^8px!AP>t6f6BqwSXxtmJ}%3ajGj{~FI<^|^e@_B`usys+dHk~ft)Xl`{(_ulL`LoIVgvZuNxdtL&ii}#6I5A6~C)lRp|91{z=d@'
    'gor?lEZ@KKc6c!6Oc1AeYj|t{#ITQzi}ZdCCq`Jp8XLo%>55-FS?8bk8;=+)1pqS&vJBURb;cgPZBP}$d(wOWD0^33yXaXqzA@w!'
    'TTrgV=Tgs=4~;2v{BqZ!2toyLKjtzw*%ePYGKQUF#BfBy&kLWGfToD)cHt<Zt_YJWrPaJD(Aq1$D%hjW(93WVcKyBqH3u-(#I21?'
    '9789&k|Pc4URfLBIm}6aFn_-U_|N4Z9>2xP&t|7?%(7$nGh{KkEr@uAbp;D;44Xvv0ven)gHtG@+Q0VsHabb`wj>ZpD2Ca_Fc&kD'
    ';;N6SD>1yw^mMnr;|DHS_AefPe)m0LKWuSl>%an}QfM$$JZe)%*fYr4iYWN_uaVc~b=tpv_){+T0?S))`?Rt&Kc7R~+n;_uiE}@n'
    '(}lxXta{kjW;5VVikXnR(471NG_({mu1Z8(-f)TAfj3&W|NFQ7XTy2t)*EOujVm+{$3m4d29yY+(ec1n=GGyTc8QfcwtjNKd?%Rx'
    '#YSGn=(5To-tl^QFqwEl+d*<3`ra6L#rJAgTnm*Eo#xtc*pA{w3a9Oe;+*QGM1H(h%Rr6htozOw`4&F2e#gSQ!8ZL0cTr}HuEZ<M'
    'u9Xupj!h;Oeu1o~Q&`--3k}5#&SU_?25JekOb|9n70)ApK?sHrR9hSsgtjTDyt09JBi6}H=+hX)kl|_1@8VUe(+H^?IzX%<M{XIt'
    'u{I_=L!N?+uY>Y#e*XOQWxU(^SxpQ{57vj#G+gmT0SS7hX~Q)L`0o~C;E>99Kdca3eL8{bi8=1)`LL|R6JHJ+9Zrd>E)y3t8lP~O'
    'l+c7R7(3N~5Da&f;DMowy$f$9bI@0n21c#?95%vh4+5lGb`4aaNF%;C{-|sAF8G(4`SN8q#n|c2PwSbL<9?8Hq!_&v;I}&m56V%U'
    'cCWk%|A6f&K#Op24A|RQ32B|~J#R&Ze<{Y+(j>lHi>zzCS<ZYO*5=8EOR39TZDl}PaOsPXWPoW?pu?gLx%&FFyY~<4UzZeH-@1#J'
    'C(&fo42%=H&}#WScseo?aEohiw&8ayajeU1-=g0Y$d`{1NoN*Q%;DXfWrBnqrj@XMU^ox5&{RU3hJ9=9fLdm=)1~1tfDRZNR*9}b'
    'K%!Z=;63xZWh`>^dEbJ8K!1y9cX`b@j44clqxGi>q>hZjPjQJC=z+>m!rW%*cCNYdi1#$!^ajnhc6gY$(IWIAs@H}Z<K=>2L<J|f'
    'Tk7l9-58ueV-WM3oZv*k4)EYe(ovH;Kh!iD8NE-Xxo$}u<-_F?i+6&aOiXN20~k&p^OcK`>x5ksxiTmXW}IKS>|0i|LC1xj357G~'
    'OYIt#aoh_zUP^{BOTzm?S2fRe9^p-3gzVcnVt-XeFC)~HFuW!FbT#1Wn1_afmXEtv+awGD2xwUI(Dg#1!Gz5udqfJu_Xz%147)Km'
    'xVmb^pH1%hE9A~zJO=d`D@dGH;`GI(LanG}Q=-~wZyGbR^MyW3KgZ+c8I>SALj${@m&E~I+X%STL2X6}i+e^&H1x|=E8cCQ&ICh7'
    'BPqzi55_}j;ZTNfN|ENW&;jLvW&58GsoYq07h6?v)I_Nq=@=fCPAecr217Lj0gsW>Oy8^bJJvs6e$`xTu+Y>S-~d3PP6H?r2D60I'
    'sFt~4)kcu=r_FWio)irm@qaNZLDIrU3)KU{k95b-FPG*<-?xtEQM{j_{oBH88j8bt)+23Dh3H;e{P;G8`jOm{?q#9>WzrOkr9`(z'
    '1G6(wY({?^H>dy<ALtcxbc83uO3Dqy8Xpyjf@WR)pIY$$^?&?7V=f$?'
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
