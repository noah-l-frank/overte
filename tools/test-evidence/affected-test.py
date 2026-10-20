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
# ec26d4765b48c2085ea86c64fcd3d79bb29ec4df / tree 46da9b71440a75d6e6959cf63094fe174722c10b.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '5fabe5e9d55ca9501781bbb78249e188e1430e36a92cd2084631e66b46a91eb4'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TS!g6uL2cXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&*!E<?XVha-65S$)+w}vT~X8'
    '-2aD{KOW=1V7xz$|M*}3?fbH$g{H5c9*_5j>5q-o#<BF@)ug6xvw28U*R<_4rYvi-rEJDITiT`?vhMxW9*61I;Y<4TujA9N%l+|R'
    'pS~o&c6d1)AD%ZBpQe6ERW=S?y%cF~hbr&;HVtFmOhuPfOEYC%*4FPY{*)e%&xe=e(;uIvuW9;qYsGr1+G6os+q_%mxlbweOI<Bl'
    'HTQmK-wkC^rLlT{#h3K_^6B~Y@RB~w=`lUb>0vsgt#yY!AF@=Bbukp#&<({<*JC-Bd0XaHmrZ$H)?GQ|d)D1rs~x8?AN#iLo4Kk}'
    'w@iIK^`%vcd>DqZZ}PtG>hb-x-d^Rim;00+UOxTvb+|t)hiQGQ|MkbW`}bGx$7O1kt}V(jU+TUpnx)T6Pkn5=B5S&;8rsDX-?jSF'
    '@s~8ce2U-xe0f<POX;BwLp4oHYU?qt>b#oscF6lF%bVFdcgFfX%l_w~y1aC;q-<{HvY+!JTe>XEdOx|D+c_V+@h+RYY^;9ri^nI+'
    'i44>I!BhS`9X|h(9)3MMJb(T&#Cv}H<Na0he3+_nnu@Wis&*`@ZuZgSZJp-2^V^p?<!zf4*R1;JmwVxt*R7VeOx2Lut{k(eE&RBp'
    '8^?KQ#-(VNtnIRtrs=wMkK^T4mtkqM$uY_ozpu#pAuGzZ9IL5MT{X4KFbzJStDf=G>%+x0r@U&KW?qJVth(0E8~U=z`Ys>KG^V1O'
    '$E;1ua@Cq~lJBOkPseZR?s+;sUjEfxU1gakJ2*|v)TJr)LtPGS=1_@U^)&Z$mtXg+*Bv|z-_o<do$j8}@OXIma&a58kJd+>>ZTGk'
    'Q(mPq?+YLDG&Wh2*HzWzm8<IdZ9IOvn~o35;qv;v;nZ|x-85Z3tk+^w7Fj(u?u~ga+!Ir4kLA_t$Gtq?{r=lBUR+<GuCl6{>$-JG'
    ')R`wy54~{ehIArJPa$(Z4_B}61iC6OuAQc(?1s9SMYE+8+S@4~^D-OUTGLSE-CR~pw&S-)METe7$LELi5|Qri>G=AR?&ibr<>C1J'
    'a+oeho3fwW(y7YpsZN#G-*+huuFkA(YDaJ$i$TiLU%idj`SIeyMb|cY%8NO<QQEnWr*9|ClrMAPLs&*9F}3aPg--|Xy!x7$#Swf-'
    'zrS1#K(&uuYEqPS*_CCAP1SvB$9ncP_G!wcF@3WgZtn+q;mh&cVfrNO{dRbEqxt|p53lp#<?ejr#VvdBi>&K3RC6(mDV2+8IL}qz'
    'S5+4=F>mU48J<jg^KRC!GCq#`;Z-hqIZCxnInBk~^p*F~%)=;d_Fd60%iNaPlIJOtY-P7^=2bd*Ia1EkkattjbW2wI?L$2kt*gOj'
    'BHgRIr5@(0EK+{+9)3+v59$7HeM=X2(ifu#GPlh%w`18ZRaPwHTr_nqA6uFvFLQp2<>sAy8y=+F^PL>uQGWX4?(5+>a+Qm_%HrZ`'
    'mZ}@GGzlYZs$FJoQMp21+F{mKp3?2RI*$IO-!_6-GezYx)uU)xjYZo!y+fJJ<<ynQ2@=Pe_@}q;;_+O04EO6-{WMH3mjhcjS6$Io'
    'Mb{Kd*NEzMUAEKQ4Nc)#7gg5Jsp!W3<}Jyomixn(uP?h}ZPS*Ej4B(ddUUlU-+A8UZ72T31DeZB&9=1T2e!18Zg~K;QZsA&GAo;+'
    '%ZtdmWLX|b@9kw>*>z<x-@FBB$1K<#e)D19eSbukvjAsh7_)v+zj+2_*LLFm*a*JMs7hY)N&Lxfe=N^0zN^cJrFS&iSb9`XO_NJ#'
    '>7CojgKCwNZCjUp{eiFOWqA6McHaVvgf|<eS@y9s&PeiM=T%!fByBvQMt;y|>GrpD%2wa5g7NtJFb^An#xdy~9O=2&lEE&9MrqX4'
    '%~Tcn*i_k&s}rj9H|=T1^;D)sz1xpXUsh%6=X%P<MLC!|$=&Q2N5q+y?1MX6@2I<7VQ{MD??vvybTM{C8iqNIos+G~8OpK*4J^{E'
    '55Bkb@Y~_(`0&lYczSi0%eo?P9&k)qj^kKQjVodtnpCw-8oIIY%-ra6`LR9izD2vCY6s9r-Zo?EU^H{3x|M(_FGsm=<Ab-O>hIgm'
    '-9Zxg<#c;&WP;<^IZ$(3OqoDDdRb%NOnv9FDBWpeS_<3!*w${k<;NDFB_Vdk7dV<MWQsbm>x+Dni&RTh4s$>KO<S9e-&UMt>wz`P'
    'kjh>nU-h{_8Sk@`Gz;H$+syg6xM#a^{(E-yoPJ9W8&$QEwV&#Efr>~0AoIMsEO&hrW$K`zr9eJ>Y(Kjqf%LHI%YYc>wDeQo3~t;Z'
    'Ykd3@KsIl@&|I1O!L9s|6@5GGIpaNyc?f`^Or@HuohOJ|pN|8`!0sSzDW8XG`Pja$PmR2{LCy#Vfu07;wPbLJyeTS2yeYfF4y$Y#'
    'Ke{jZ(cScvV7o7e;r@989Z+&rRpFxT`cc}pEFM<m1o<f0&C3Y}sB-=Ap7x{!rOV&J@juX_A<upDvTBe%<fiNz1!_LDb5VS3GdE;!'
    'a>#MXo4jd!Van#AUS$7my;OM`a#v2_9?XmBV;g%uzCHo9rsLNHx1KI%bJm+PMbY5N1j?4?fX2(Jj}icAK6_{ri0Ok{imdW(M+pmI'
    'lCJ^#indmnEu(v;fV#|OQ75>k@YH2pUi}^0S%$;?>ju!<Ro#?^R1aBI50i#TE4LlwEK}hzO=a2j8YuY(&-Kf<$K`OJzE^9PKmXRH'
    '-<0|%4LC@|Y``)e%P8N?0+Q9)DeC5fr~BpU_4&n3@@x9zX$u<l&C4%+-_@9MXS(-}v|Hr4WA0FCzEpFUK2i}}v6;xSGc6^UXwhr?'
    'q(R3+$EzAMU)VHOW!=Lf_FeyHkox>jF5eb&2@P~CprdW=zEIF-GTAyGYl$q3w(h2`+m~T~d0oR@dir*FeqMWs7n8BE@AV_1(Xn)C'
    'oM9T8rOL!no2g3Olnt|(v+pN=J;vKV9=8I1T+r%?Zs^-;s<dSbp-p|>xxwcwpTTiHlYMKR(w57iQwOW?;g#ASb7WC~@00_$z$S}3'
    'XU<D|nD^yR4=(@T(%mqBJ6yg=bT%X(;$J=%O{4n(m6(@FBeV4XN&r`-VAxp@oLAigCT5vSTv-+cQah!oQP@|$cqmA~N0V|*7}$4~'
    'e*BVl=NMC&r(#s(s}G}U)dA8*)i7Q3@ye{2#~uj3vtInM-?QgaYG<`YRnBt><*(Z+3jEZ|o=cyyW384}o6YSNi=PV9>G+iHesMiM'
    'q{}r#gjT^!pQF+~ZkwisGWS_j?!9JIqfQ;BWhX}W;|{(Ze@kmI>I&Mp3iZnCR$Db2^~3|lmDWf)<8FkD^{Vz(<Dnn+@8P<rGEJU%'
    'R{E?nt*=s}OFwxjb<cfi$pw^91*U%7zy8k9lFy6Uu^Xb+hNHBdFD?)_pLpj(#1tqa?=JT*e2OnSp1B&xd)Le@Twg`*E9~UbW2w1X'
    'xN!l*pcDPiYnT4BguQ%+Xk=&7o<ZswSV&vQ>^l!0pr3i&Ih;g7w%oq_x!X5AzFvL~zPo%vRmcL0MhgjIMx8fMV)vYWLf2}v^fzo|'
    '-}>cJYjWnYKFv<amn?PhJ(Pt%=mzLQQ;c(V{SlC`uUrnF!tit%3mQi^X%Sskx5^~s)wMlMsi+;oBsg|5jd>n#-om~o(R%*Y%QU?Q'
    'WP{mXu?;-@L4BOu?2@Zmo^iuA{&@L%eAowQ#^F~a0Cjv1>L(PTRJWQa6<|e=Np<XbRX040r}PD;qfnXe{`E9GK5k`M)0ioL7l%S9'
    '2n@{SIM#!nu!=n8Y6FpBxZz*`mM%A8n?{}1SWG%MSJ7Go4KBKE#TX$n7;3dP$+Umz{Ru(e4*gIDxn$9dNOR^!s-Rny<Y2BxUB;lm'
    'ELYq|H)RF-3$><q<N5o^BUYSl=QIQqIM@m9+%z@ij%w)i%Re0+9$#NRd+YaSR@EmN{-=K>i8okHMRajDdUa8ydh6@?n`HJ%MbKIR'
    'BH-@DV=3w#S<+v2WA#sI4&u{~8;jE8Zg`1Dw+$Q(szhm;8l=EM8k~yB*Q+dPE47C{af(yB0~~#CV_T%1#TO9ylgCm7*5C@A=WbDb'
    'v||wPki+!zc2H*4%leJnczH>wnzI?%sb;T;5FPMQE!L(E>CGpKC(;hf&L!WVv51v--ox<p?f7)}>fhVQTI#}w;EvRBfrm}a6y+bN'
    'weQ+IU(m#I#i%g8cOR$9^V69t@%i~_`v00dvc0kY*XShgZ{@@(i2`fQG&k@}>225H4SGemr<IgzXy6%ua^J6KGobvo-3PYw1|Y24'
    'x}5b^V_TpS1}hg>5P682qr#t9q{H?h`CJf=ZrsdD;yj&hWYXbz_wkt<->Wn*6`-ghxs4|*6K_rJJ<PQ~k|j1f=vSNj8eb3h^9ldi'
    '3%H7G9U@RM^cX;TRM{*Dv~3#*2#id-r3`*%{_)M7F}oig+XfHCXBW>)NSN?7A$3`FgEbj2a+)F-4|(dVk8kXt4fOQ(QqQFG%gBO0'
    'Re?R%>6YhsIddM}j#9(8z^B76L^#j8{%_dXgFEY9(_?tj>brc(k_bJ*qIIpMda!fRQ=1>8G@{0+d9{s^rt6RI>Xh_|5kGWjFJG$T'
    'faKKz7rnbopqhP<bML4*aoDy{0jPgBetc`!#I9MM;p{v3`19g-(P{c4I7KMcK#s15dTsa{KFf2ue)zUlvajRg*Wr1C9gQ^E2=lf#'
    'sbd38kRc5KV*~&tt_w%|VH*F2Gj_TPcfr@KKBp)F+nEXgV%x2d>5|4NYl<mIYJ~@vrH^mw`S4|BM;u5&RK7bt${MifGF0>dv@0NP'
    'w~SrqW6-*qB)T3Ld^P=V*xQ=v>}b1pY0mp-uOYwo&Yo&mMU-HnwGt5<Db3L5zu_Zz69Qb`&Z2*e1qzat+JJ^SuuxMp>Vm$`1CZ7)'
    'btBxkowq%FzV52j@3*MlUpbEfS9NYC9A!ia)U6R}0kzHBo8RL1U9A`82J0rEE97kV;UG>`K1GQ)91E^H7G($(5Su^ze9j^MGNe-$'
    'g<{E-<3dJ-fUx4Ti18o<Q5~(khjv!=NB6ShGb=D^g4BnS(Lx#Vc6HiE`7m_@baNVHqx#wHhqrRBAO8BWZA5@9%B7{%IT=O}ds$}f'
    'jP$?ww@NQ8Iw}D0k8bUXEdd1qKB6MNRwbbtgS0CD%L_WDIZtC7@OXBinw$?$As{;MEEVak6|n-c!}PL^1uwceOE&3-Ds8)|k9?}n'
    'AP`Ln6Ni&4YlgPGW)E9MtSU_rQgn5zJWvo&<dwl?)>fKHF%*<-P7ApEckgU8>Gx*T4Ar6+k1kXaosg~7$QDvI1nOKDBJY28I9-3k'
    '!?J~1q(XxqiED_WSnnU2=!X$4QK!jq(5V_P`ezKz`8cV?WtqeM=Q~vWA0%3L@y|B;b(VF2OHALm&(a9LswqmGuBs`=V2YRRkS;G9'
    'l*7xIOg}GZ=lTL&k_b^%V$iC%$Iz}gGo^s1msMU~=9KWP|9PX=+m~Y<Fw3~qZBw8O(n7V0wo;cWqJJWqnSb)50{%)5fr@_~o?Z@='
    'QxfHs>GHC{A(x%cn0L@%R|z>zmQQ*`b)>~Xt1K4nBJHw^ORgtHV(#xZ>1=t_0vh@VzY~sBhR-@@Ah#wd+`Fl!ZxjQ5cE|q5f+u3g'
    '<#RFwvR9WGmKwmf)n;rEpq%)!R}Ivsx_H|7eb3|Z+ud(&?Rh(;0b}-R>e{Cb9D(tpe!*%M0!i@hC^MYLx&K-7`joBA>9<3?MfKg|'
    'ORT;p(aS=dfJPF4r4K&EVjWeNGT$XR;=gCJrsuG==sY~Wgmz|)F#oZlr}yV`_0%%25jU!X;*NtZlm0a<K^Se@eC{Bp*zNmPeEzPg'
    'epD2E|KrPnt%!~)EwQ7kr$MxXyaGbc?V!Z~&NNoaaT;#i!Q<oM_1oQ^jZDGT)=f(7+Quytx$!KPM{*Xi9xWJ!VW_X%$gYQgFVkqR'
    'jpA(;M9~%)P#{OhKZc?iC!%Ec+0P`%m)D+-_wJYDDTP1N9=FeaSp{-GQnL{ZE6~*bnit^pVDb^9=rMP){Q275tbp;|m!#po)pA7i'
    'LNWF&=;jM+RpetB4ON#&ma7($41-gZ?cTzA4tBi@l!6)EY!T3cYF1asRtt?z5$%7Nk@o=8Dt5n%|9`v#or`Z9OCs5J(h7`3n)k}@'
    'oFf3XLalbXs<_22(0VQRE;*;?Uv;nUj??S?;rCt79;_Nm>sx_N8YvGNk5XLcq_5D+ahVX9Qd{4+g)fh<cVF=%@6+=Jtf{9sD;^m='
    'XqRaA=T#{&0qK;{TPtwvyp5Fo4f{ZfcD<vzZ}5z?Xha3XF&xrnS)%PXN68digo>P;x~44izh^@$z_g<o9bkAJx{Z>4f0}iEsU>PE'
    'WKx9`uP_Dgs%&oDm5cicGvfL1tG|8wyNijJDhM^DujD|z)C9=X>c~=L&Yf=89I|LFgyP2ioDhiNk9z?vYNT{{?~45^q?#fA%8s(7'
    'sq5&@*C-^3jYk#vJM#sVcdBpwtghZqUW@|AL_1P+y;=f`hDyRSo7Lb#>LmFtf9fjo^Zk4~PQUK@xQ8x!IEre%8ayB9YqV7I5b}p6'
    'Y6;eY%zv5oE_|*Q$HT+C#lBRjhB8brn{v8zXEdBm2=$x5&T_$(2z6?9f6tGH=~#VU4!^$y>c4`Ym*ZM!b|iH22))NBi-Rs8oeb0i'
    'a;yfCb+p}e>;Fla+I_7k(}$p&Y93*YMW0%|TroSTaEbIr+hF$r%C6hUQ&_D$?cW3$lTs*bbQH88x?u#ahS?2C43SLU5ugHI_HM#|'
    'YY;WAxZ|rxspe221Ht+cg~+8U{d7LbDwc#xFbzu58+UNZcXmIIP;{tr1Lh(ER>bRrBaVc>&QcP?l@(G;SM9#*e>?iyyVcSts@09?'
    'B(2JH?@AG13<_HoDZfR9C3I2>oM07huRZQuu=nvhbm&?QZ65*&Yz-V*S7ce^lwhGQ42qkr1qo*U_#bJP^h(bi$`BvC>&lB>`p`HP'
    'Fo(tsFVoAR*ZL1zORiG1x4L{oC)|gEqSqtNlYW1dC5$Pa0Ac3TY2f<HgrT$*aQ5k>b)Mi(IlvvaqKJ;Q>YE5i)-u80>yvhSs`f6n'
    '{?g;Q9UTAh?(}cS4DNTdT>~_AbY~Si8;ln5B@BR+>mELCQWiE#?Ko$*Z0GP0jbEIL@s;n^)7|6i_{N2~yeA>w<qO1xPJr(wV9%^`'
    '*D*uVN^b+k8*%eLw5L$F(MzR!*U}bqjcG|}5gPCU=ngD3p>y*IqP_>yly$JzhM!p?U9q1Z+BedJCA}QJUB0H=ff(%cBg$Ut;JB?w'
    '0DT=gzCNJPn8|<V;g((9dpf$kX)82)3t2Sj*=}`ep4o%Sv4j*MT5%z`16aUA@>}-sZEXi?No?(*fMY>lAUpsj=_5SPh3(8R&9Wb{'
    '80~kQZ`niG``E+NyyICUH&YpkC$48s3b-9R2Iqt&0x84XkTU=zruLS7XpKfS{`jf~zw2<QxqFo`rGZZy#SpVm%Fo%uj<k!qC2p;z'
    'zv*zSV9nj>-a38Rm)}q3Zf?|rvRCY_F+eg<F3u8400!U`rzYL@^}yzjPXK`PZvOf0euGpenISJhKy;rl1XAx*{J&IbNJ~P#+f>m$'
    '{|#G-Kf8<>uvlqY{pz%G%J>m^EMg2|EarHd`oOunxw(BW!ODCd9F`6ACQwZ1cOIG)q7c}YHwC_x&&X&xz9#4;Dc!P>=i%EUP1<wt'
    'gHNsfE#khvfhVf4cpUUo8VlL}qT<m)8*8LMjB1A_-4y#@LYY4Ar~s;{IlxA(o_OnM=&$HQ41feo-3rP9p@#vEw`}5cJf?ev*yTOo'
    'kA+NRh8;O31aKkXZy~=RAI);$I^JEo|FfCC4li#qn&D;hTM3>pBs)0Dy30~+xC)@#&4P^T`wf#ob~pRO*>{u2vvm{*_v;2ifRF&-'
    'O8Px5zE!jhv@5X}NLtu5c^m<$bo+zYi3EGPU5;a@B{frns5U%qBuS{BXxq|HE%$orbZU5BNR6U_DyFK*OA7ei8;KY`{W0CAbKW*h'
    'zL3b@UcRnw0QYITE(;wpN<xzfT`oKQL?9@#K-@k^9D0F}fqeLz_O!#;3u%Op9ua;x8w#_e{}b4&ia+gD&;TC{!|rd{(0t&!_p-rw'
    'FG$!Yy)=#9F>Jn?AX-g}@PR$#XklF~QO5l(J9<k0eBFxq$jotcL^yt4Odcbt<Ot-0s-k_{k=zo-RP9GMbbtJEc-V!tG}>gYz!VoW'
    't4k*vT3yNhgDuOR(hXS!=jEe2f_^-QM&n^hyABg{BM{uRkEmPfjrDn>P|-si+1rjGV0J5g_(^FvepgLz?aBM`cGM(VPApi3Bi5`#'
    '5HGXH@bG&VDMgw;x~J##;->ln+kF@wpT8bAc15&X;R-@_^*ftzREf7Z%QdTDSj<5XN74S<cJ=yre;h7D%}b#03V2qc*t~o|lp=^Z'
    '3*xg*bRhKzO;uBTbWbnGU(>^xHhVeQg5d@$c2chlwQQX5P&7ivA%E&ig7+e}H{QIVd438s{wbySHy$=Qg03xPBlQc)3p5Y!v<o{s'
    'W+6C@T~)YZ(N=EVj(-r1io35bFORzdlaQ!yTCBVZUJZglh4qP$;C{ie<U-Z(Zq1vIZs>V>Iy~;V`gOI&CVZVK9n_aJs**n-EU!@I'
    'H+PUwkt#Vqu%T_5sUArl4g@O7xsVyFWL4Mf5lFQ7M!H;xsOs_N4}Ly=8^r1L`uNl9`*OU_ozsCb1`9WGq7@@2ti-)Rf0Zz?nFwR2'
    '4{quH5K`M6Xq_^ps}fc7DEv{#K(S`XFeA0DkScbe<`I#qzhghDnsnGQ0tyGaxrXJrAY>w>ZP-`wp)rv`Fe{=V7)IeA+)&7w_{;5z'
    '(8PV15(qw-ZyIK++yZan`yk4Pd)h3khE<feZt280`u>gmpg6ny>gsSQ<7>{TY#yZ1G@)(u?G-t^H%2lq)oJ#3Z7cqY%DBUlRZ8Nu'
    'g_9KzC(LB5#i@k^@&)U>UC1OQciH_-`&zc`ZNe!!K^#TL&=OU+%3*dd^G3uGE1{7sEzJiv6u0UQD{ICq5sntDS7@jM-DyYk(Th{2'
    'qURtbMSCd!;BHPV$0r}%3kKw-vI5H$;ZUkkQL@qrkY44%>sBptm<#J94i}iFAKcaX{&;=Z`LJ|s;j;2ucl)4(t*M(jJdwb8K=2s)'
    '-~=|Mw{Gjp@#PqtatZf&ZyVV*B6|p4Q$c-Q1<Mhk5`kh=0B9|?h;kUCH%IS47J`o(u;t}%Y~;Nm;}@DWT7z1tvFdX3sVSO($=aJ5'
    '-^;BVxj)XUoz=-a>N4U}g%dfg9tugnY5-gsXmx5LZEx5v`<sZ|AJ|J2L+6)t4&S@360k!an6}~-Rnr`gG7z~!Bf_f+f3jAQq&oT7'
    '##RyaynboZakCW>37Yf}VS=A+j{-aeu^i)$s8A6Xt<V)5x^+)ySme*gw7n%mFjTPSLxdy_O2Tkq3F@xCtfMSO#-Yw{FF>ryZtwj5'
    'c7h|76gEsp0=Cnf;B3#Sxecl<`8{SDs&A0ZZ%#`dj?p*@G>`t>6We0^=I%4R|0%eNX%#92ryzx4;RLS9L(aqt=jQt3xaN?jatLSk'
    'bt5WL)G%T|B+bK^Oq9kS4+J6_k13`!Ou)x<^9>7HjAO0l7qa&uH6W`Ytdc|jEfR3Y(e#f$pxB#uK$&M_pUX#fbhd`Ld-)o!dzZJv'
    '3^<EEg=Hm+;gZ%{U)K-QG<sgxF%*qAr$*<JOdTXTA{=g$4nmvjTgSeKS@jZb3I<1q+`G^{C}fkZrpC?p*m{%B`|ggy&8{uLtc_#7'
    '{8g?9q}Gzx&1S8o^Tq6h?B({otam(V$KJ1<D6x{`dpD}WYJz?6A1C@yS<`yzV8}nr`)EG6qu;*mF!%`X5U7j6Pem%=)SVm}Q@a`2'
    'O2@dBSz<j*H|IgWb&<IK7HHa5dS7P29_j<KE@SM4rMs|)bZ13%&0kuX)DIunN%}qb^3kx~Z98i5zU{-{VZ<AnkxQaFG<3(!>R%;P'
    'n3&ytWK)Or>7>1nsn5x`r*K6^tU+xF4?K)37I9S=#K1tpkfrQDwxi>Ydd#?=$jXAbYZ8f>M|eE|Gb(~GD#AC9h}hl^dB#p&0%JHn'
    'ZBP!YNY=}6b!d^dd1sP6iq9#@TZ^a+myiH{U>|2P;IySTM6<&z=2Hg4XBou8chdY}A6L#{isF-}q#e^ow(|X+5&<{zoJqyZm=eMP'
    '<t1ZjGNw6vD+NNQL{;xL_lf@<o7wIT0>DBoM6d3vZUceQuB2K8|HQ;F6IFPEr11lr33=g$c1kD<`AfL#vGuFVFx#7A5}Z^SJ4OOF'
    '@E{nckL=<l+&b@q#I=b<DTkvas#z_al91YuuCZ_ju?wOk$V|oak=Xk^he$XfH2xcAPy97l?HQ|ui{5J(dM4hQrb<=GbOdOBwA`F#'
    '{h52-t&PnMAwL&vdPLAWavAK@i;B5V+7?PqCmHAy?)0}@k{(QGCSWNij_ro{P3w*OU=>3V$M9mqG=@L9B7MtvIuK_W*8be;@tzgW'
    'o58{QpErBkGRYy#DQ0;S=u&I24sWzkMb%5}vS^60Fy2pjz$ZOPVE@{mcmq*(8?@kfYb0UbK~t(0>k^!a#e@#WqJ>7c&}gWyfGghF'
    '*IFX%-W3`A6fcW4F!xAOVx3)99;{)DFtXEd?mfV^x_MXU=E>guNQFU^BiVw^Kz!$#Z<q-<`h=A(Da{OnzViI${rt$H+`B1BUyK`#'
    '>Ip?z*C0FwLz*5Ry>1xPo}JAV>DEs-75{Aip4Qek4gh&K`nbdta0v6tA~ceyi_}?A%d=beG(8Q^U)e%F9AAcQ{Wn+%ccu>w1<MZj'
    'DH3_uzs}fU>IDQ`1z&LmKknalbH*(84+rwbVo<61Z>Il67?6b)MB=<xc$q^qE5+8$G2pMT)6PwWt<a1;K~RVHACuBp;%8<lp>?wo'
    'l_`@X5A*!7O+_`l+pdq#O1Yd&10}~{3~o#xOP@@U+y)LFx}mbUbw}Tkl-(O*>{^Ty;c1=XUX3wMnE`2XK@vnvLjPQreDiyYhci6u'
    'c3%-6)w_l4P%T`CpMi0u(l7l|d1}p|U#;$5>2KZ9x%`w*y?%*d0UJ;}lnIyJ?5l7uVL^kOyu>KpG8$ivYKz2*P_p^(c24b_<NoVS'
    '?=4(69VWQb64#trlcAkd?SKklb_o|{Ods6Y+8fxrr<gTZhr&y5j?h6yrnQ2ypc<_L5SK}I?N7(`T(zg?udgqWFz&xkK&Jvy9(Jv$'
    'T_u+#%^o)|;t&;-VuR*G@w$6o=Z&mK`}r+mPOqzx^b6jC6z*_2IdOX>FpE0KATw)o4MjI0yw!IGzEn$i$MyY3c61znku<4Ng-zVz'
    'hk3&YBMg=3T<Ou6^W(mS-<VJi51T^+OML8Zxh7%y$)5i5N1LgoiK5<A7bf<cj2L7<S~xA?OERii-F`hq6xRJaN^HN=r)b5?CI3CY'
    'yo^SvfKVtiphD<)<ReRj1jtwi{2t@_W8Lvn%a!*wbMAMapUnC1&h`A|t%QDVahI7#W$Ii|NR0rkn6gMfFmUvrQERWDJHNA)&D7ro'
    '0b#+c4xNuW*@$mVRK)yXffwPkhOuAm|E^w!5kz?=7_a|1$i2@S%+?qm!E4deXu=r}4G$u=1R;Py7!HuOa!gbD$S$^?got7eLAcF1'
    'n#6S}#-$Z8sDwczvsctaJ~`R`H2QQj9}e*W)6+rU?uS2C()EVMEO^8*fSaLQ%x*7K%njTLIY9{xc(2v&SCFAj`yk~Tp3YWxCl$$7'
    'eN66!fEiH)ps|D_3``pVD(0=1sNihX+kUxj8?3qSo`%Q*@4m!exBBQ|dP`9=N2<)MiBJM@ZOH<!H8enf#+Yi^Pj~$;{P)irR&3!d'
    '(#Bi>oL#^LX2=*YMIToU{w&$APQ%bN*DZc}1#t{^y$7rcI3p7}q(#;yyh*jAu)y&cIjDy=*AT+$3VqyJW)=FGb4|Cc<w1%iG-ig4'
    '{W_YKiRrB^K1p2Ex&9RU9f7bOuiL~K_Ix`C8xC{|?G(sw7(E*uvIH$p!Od4D=vF{!+=0Bi@;vH0aeCS(4a{RY%B&TKa>p}E9g9F+'
    'Mw6HKjCa&hqZ=5OuG;}Z$*@kG+|LgnHbw>%nthRBsHpeuZYNR^Cu6__WB;F;&RyKbDoNRvf{c0S54czm>NIgpARw!$1#cKgX~YNb'
    '%Xz7<d=2Li{lg>JWueB)A`5M37n5}(JQ~rq3d>*~D4W5L#zh*hd?R{Vqfi-N=*IFi;HdnpzoNnd(g8Zm{L-PFf>Pr)WqQG_>$>G%'
    '4>G-%myN?n%jVbdjF0;g45nX{(}QxZKw$||?-YPtIbXf@^S=&T-RYQ+8zfL=K`3L{Lj+?trZTDYn2mtG^Uy-?UOU|BPqe0QVO<h)'
    '3(~m9bE;ypRA9aax-NkMa96rBLvS7eLoB!Rn4wS?AKb~NHpnD3CIDT5fg2v=oOEL%EXt6vQLFbBCD~Gq*KZ?MKXbiyQY#Gk=_#bB'
    '8)L#V$cFQs`yz}I!UC)ed>Qg|#mfmv(5K*W|M8bpf=^x&y;g{MlMl!5&-c;Ars98PG;>T6L)8^XeKmMal)6oI`>uXD9#&n&s`0p6'
    '?uRcMw#?Cb)*=t~&>TvEa7&7dKBp3vdxag0Ay~!jJ38q?u|1TzU$&;?u+&>(urilFAq%p^Q)~$ZOpv~H)nX=tvG4uu+re5qQV^ft'
    'p4kh_6KcZ-l%t~;E_r1cIukx(x_d4=bJ)5Vmk}z~nm5T-!IT1EUq>|!+E>4CjEUl1QAPkQ$%9%RE8Yk)hckno15L_e#%i$zi>BYz'
    'iEA%@mjz)cvjb;bJI*W*c}xqiSv#!Rwq*ra=tsGGRiDL1HsLFr$0?5qNOLF{%do)DgBRs4^_41_`Sx#>>gN{IzZrFL>-=@g&}Ip0'
    'Y@`yL51|C8m<3;n*$_>_0_+SktkItGo$H^_<_&|un69d^1%&GXBjIkZp5YBON2kJLC$UP|vUA0=Lf}nJyQkM?8iI_#B}He#ERfc$'
    'Y$AK4JBzN(RIL4`&0P9z2gfI}4XEGd)Uh@O3n-{#UUJOdq@KimuUDZ07a`-QjKJN@*uF3OuT#2slqPN2mGhv}(KLF(qyU{)PIP0i'
    '?Sna>vzR1oM&4q+?p&H9gD>gNM;}bh<K>sm`Jf9TRE+zcLJCoa2_B^gtP|4&I;E(duiL;X<k=W@h3bSG!KY=2fgk~-R^d7~heu(K'
    '9bhPWk?not>%`>^A}SrDax4a0fdK_6zMC<0OdrJ-YN8NRUpGY!hhre75vYHEobFy;AGW;JLUrTLg4QCIlX0aO(n%w2J8a8i#1wVV'
    'v?+Uybys99p6>QIIT?PvN+d!VvBXFU`6#q%3aL7}5cAuZUX<-w^^b>%=wKGQcG}YfpAG?V!j4jrbum%fdRkZUF)NE&w%di|c*o*r'
    'Kh={x!QHm`xEsigpwBbJ#OflDF%(~)kPcqHpaE*dgivG8(m>tikL!N9Rq8-bGZT+o9^k1(lE?Sl+%D?R_4PN^roG57>ET!Q=AW@@'
    ';4rR@4WB$SGmNl^IZ)_FDF)F_k>T?pKyaDO(DWg1N}AplJ<SP^k&$C?(w4)Qjk3RvsXE|5)N+^)k%t^W`Vpyigidk>mK)Q~)!*#P'
    '-)2lpg}$VXr_OtSb#<h6T^})BFf@#Bb{+1HP&)CGTCm@_g_X#8xM*w(kmYNSV2^Y>1ffeLqs~xO;NK-DFN@-2Q-1ii;<?qi>t%Ch'
    ')aW5ni_y?9KF>P^tbrQCc8KL3Ytx^)Kfk~7m2W(!eUNbixCjfDbu21YubX11BU5P>yg<$^-8Ea-@ysbJxEeUfY0WWR8FWqxfMBn('
    'sH)8Hp2F{MW7%)Ui4D8W(^QIHt!uI3PvAdrGA!t+WJEe$Vb!UJx@ekiEqa_^!&c<=@u$k)AAe>qW=Qd5TCC&r&ddN_f{PW&Ai^|`'
    'Wz3r1te8(LKCc$h&%5eU#+sT@Mc`!`4aOqmcs#B5j7x)DWTbTTWZQA?!jGZkHKJid>8xoGOo2Z78cnzkAxX*v9ORg&L0m-WGvu2r'
    'i|@;>o$yV;H~$)_y`BN`l4wbx7HFMhL<Q3h0Zov9r%g`y_f=Q2%Pzkd_Ha1*Z3+z&Ma<HM6EpTIf+TwfZ3H%~yu<39D@R#z*ydI@'
    ';g8^tdYnR(l|rT$=@66O@Wu2AbN$Wpe($0ykLFEmL){i~pv`A4`%<gP>{x)|T$;myJx8%k&8etvxi+XF^Gzb%+a}KR8MWh<!nO+F'
    '&n*diC14@e)H&C_Z=#oP&~f~H#bkZmx+@;5Sbp44_jXz`I9_ZQyNKOk4dj3^i)}*;6)rInw0Y;+Z>mBm+2v(jghmd<<WfCLzdm>;'
    'p;aMqG>(rhBPR@-yPeA}_kV0SW|?~k(}uAN$k07GPQy}J`(M&KQlS#(!U}dScbHcTrs3C%fpP(;Yvaez>@4sIJ(ey?)DE!gX%AsH'
    'D+SzpoK6jwhxDpkyqwX))1hHtOzmG4Grzy^OQzm7CL4D~Ng>7VhrJ8`^7`%a8LGq9FlJv<spp|Z;5SLo+eBU)28_JOVtz}rbG_3L'
    'vb*PR5QvKpSQlpq>1XI2ONLI3dBA;$o20}!C@$iL6kyrA?i>Af`_<-1b^!!1vJ@;GBFY$8iwZ`B4B9%Yb~7%ft5@C`seH0JCs+r`'
    'kFKN`VN_abe;a9pX-m#c)wpc>VSiu$c>HyvkGVE$UGS{v`_SKvMALjV*wkW%1?Sgjk7{p}h<WQ9iYOmVI3yEfyZDIJ`0Tj>z~Lf='
    '6jpVPcU|pW@AdxWu+AyHToxL=6dtre%L@T7Sgns1e$3wl#xri#t|@k(r?<hM%V7C^%1?l{(3HX#Iw0j31%*jqmI{|W-dr#URWsOU'
    '=MH{wNZz%)aYoV`UOWiD+*HGlHV`~up4%@43Zo}x62s2r&%Vf<)$d=vZlD1n_TWj&QISqYSCUnd`c!<@hvT|mBeIjK>|FSH0xxZV'
    'N-%qO?Tmyug%>K%%PL?8<pBnk3N^xJTVAuEXT160;vGbX3wx2FzHdjX&G4ony#0kOk~%n>>#*OwZZN4}c{>1VuwkfmmBXOuHV}w#'
    '8WzDgRFFYYV_SM`_D1RN?nOTsQC<G&)DTnC#w-t?vXe}x4;=@cI^&KyXN+)y-FpY0Fk2w`A9#+xZe;L+A-}TVW`Q1JUX`5Eyz)hm'
    'v7O*e@_*QyOP~8OYkrkBWUo~i3d%j2aQxG-QhSG;>q^ihA{0dxjA?Jla%ys4{;i%Vd(egJkcmiY&cLaS;gkY+xRGxFfa+$xYQ;O8'
    'nTz)!1eUKN2lJTDYh;DX!t$81MO6OG^csyj^0MnzJ!L$H=i?4NuOUIy-+p2d(y2BWJ<%8FRZuRI$V^<#L%I8Rvo1TWe>wBvey0TF'
    'QbzjegId3;Rlq^tr*Z3uo1QuC4I{6QE0p;97=)IMjsRk|$I6~KocJU;wJ%$(p#Kp)5=iP2v1RW~aq`gIS2FlY&GjnL$kyy~Muujz'
    'F$bL`+=@zr?>JfZd&`xRVPqJIJ`FqEwM|C~7O`_2vjkS6xVyQD*(4#t$X8nCyp<VH1wQ=#bb7;|@BEdu`P~L-rVs9(b~C+V(?T1V'
    'xw7$UV<bzIOKKSE!Tg$q-zHU^M~+-RYIRt3^QCiB;h+1tkbv+ysA7;s730Ch@uIkD{j*d5KI{50$@1hwe1}P<!`YhA6V%r{ri;qU'
    'Ci?7r)2;6>J2)c}_u*y!#QFtVu;J0k_ogE*(-2{OhbN6l6-OeE(LI>L5Vx_}<R<)O54#rjn6>xE0NZG5^qf$&eAv-q)g$5<6gJ1@'
    'R9(Gr{M#GU5XKttOc@InqY{}3DM(j)iZp@+P!J5w#o4+;PV-}S9ksB|G3|E&l=_sMI6@*aRP|2k!*jdAeh%vT#)^-JM?#dXL`>-v'
    'n9CSbBdZutu$KRZW5`QJRK;i`Z`&OGY;5I^7gX>@s1h_ytD!7|oiT^WqmH?1ScVP21Wj)?0RjcSaxx((IC$BZPS8Ruj4%V5;**WJ'
    '5<yx<{Teqvnv-|K`mL<QfK$I|L)Qb9WW}vkly&;`#?hPoAco;S3eiA%kuu-(8-CWJ{x*Cc$oT2)XMeZ-+dVXqwtEPRgc$8r#aLS?'
    '2q&4sM93IHP|xHn<2D<1&xZC4Rit3%&`Ln3nx`geV`ziAPg)F5=1&si3Gii#4{c}PAsG#eGLxAY4TmI}`w%zUy*y+orA@^hQ*P?4'
    'FYja>|M)l@Hs%rLvq@tb{ZWV(5ed`=INZt1PV;esiiZ2O=^Jz23Vc0k-#xy$1`nEhzy+E|ts##t6N08J5QZ_dRcOoNP(4ih7JiA!'
    'm)PD=ig*f}rHQuh7(T&6i2k*tyAb`8=$XvoX!ap(nA_cJuM*tT)t;W7)=?Cig<BS;Y_JiAMuZynDnafD)iiT8Rj>yRc$Rcg!(Oq8'
    'D=ADpkeU5J%$ro41=`J;D~rmd4hS0GjcMohyoDck@XKptR(pPakqk|(Lcto&SC|j@ea?L#|8wXeqhoHGz%`3sar!iY`(PEV9MC9X'
    'vXDXh1jB0&R;pVV0B(21>en4XGE_lG;Xq8pG_vH+2!--c6f`mJdIBmM6|{BB<DoBiKMaiDKbQzBA6#385FD+{8;=P+dQKUQdLKd#'
    'L;*11bnOPtDdw(OsK5wwkEhVSO(-D}ebdUi$P93QdVMIBd$Bnf>%A@PpGV~bXv3yP5v>6tLBMH)?#jN#n4(avV@UFAx3PZ~>k_Ja'
    '@y7q9Rt(c22rr0?x@(T^47Z;;dNjA~;Eknox!f^x3oQcUPSQy_WfX1TWaw>F66|cs=l~C!Xw83YVPE%?LV(ptF(xcd<4;|HfL{=_'
    'g(1*dlR;3<H>KqNzWQG&j;jI6M(PbU35On&MghTyB3fi}|7akEjt73{POPR6ZDR-15*I4(C)KuGShL;RM_VG+<_(y~5DgQG!L?of'
    'p?&Ng&1$@g>Z=dziUk6Pry>l}`$(ZR@z{i^i<h#ydNVPh^={wDuecoew3(SqyVZflMQyQ?)uz^Mr8){vE_e3TdqC`YNME+am+)H8'
    'Kh$hR7|$49Vw##f9vPNF1g(160fsh75I^0(b9mWp-50v>ks?uDYJ~LRhaB{l6eh8(D@}Ic`qyUjwISkdy5_Daf|lu4kwg||y=kSN'
    'tTUS+ZuBfos6VHxPvzSdc2BFtWLuE!tI*P@8{2xl#??Jx2_0i}^?hUB&W-!{J{WeF!#OUnQAkS>W3-EK;~68Jlv5x9=`!QI#SqY9'
    'xOOwAp1$;A!b!S|X;n`f9l}=XqL_hv1Dau<dV^C)0J0e8JPatb602MH5yKrG)(p!<wK;xNuf2`ghI5{U(V04QwWe*FNO6~T?Y>W&'
    '{o!}^a>}sn=wXKf4<~C;)hH~&0pF`pdEs18BqBbdVK_-Jfi}NwD|;B^91N!zg2?Zl7oKZQ6*`51IqHjfy>m?01}k10x*+tNy|y|b'
    'h+DYhx*%B85_<Jqgi5U!7oF}os*&2Op014=e-$m<?E-#A!g&lecp;WC!HVt(k8AS3I=)xbaseFbRbRQ4eTG?X2UB9`Q87~WXeh_~'
    '$Zf;+mwMl~GdFd4ZLYoCAHIBb7GBR6>Nm{L4M79^#VM?#t!nfE43Y9JhYYpB$Tl%TLn8>o*JfE?0_=MTE7VAS@0KT@>tR#PAxP>p'
    'Yczw^Tc%>L7*VW{28v=u)FZRMUb_`h9I;_|cztwC)>`m*TsG#o=_BYSNwbiTkVlcVeHh%Sust&55`EHgny-B*X4F3X>?-+79}Cs5'
    '4(nB@q(_h2pr^%Dj^{a?Tbnre>BT0>`|nHt(A-#G$TeorSxl1)34e?<VZ^GFN9lvUTa)nXsfp`6Hpgo}Sp@RynB!QT5}qtq_{7kV'
    '5@9dKr@8a#7O|RyjiAHSx9?+<G-f`B|1svBi4zpM2-52kJ}xGhsYQYli8gliJrY~EN-<G}&oktm!E+vi40zIdIzb7g+#M5e7o$vd'
    'bi+QbP*7L|BExMgaIp%P9pTxGqD<uMB9>IE`%gCAu#25q2E8Z!WO*=^p%#Q;yZ(<dwU3gO>451(yg#n4(oPb;yR+nPt3<<r>WTN&'
    's8BoMbT(`&xX)<jS`;Lad7Tg#uie9SBy5E+&lS<am+59jeIvEZhTsS{F_H)c+~K(TL5L2ko6xyMx;<r)BOc~8%mjic6Q=SAFk3Ng'
    'I74JNLwLho{efIFX?}`U6sBW%DG3fZXy9Z@Ma*r5a!eeq>f!42_q+q&XoS#RL$5W8iPO;1wJ7mRM04(4CV5cGh0WQlYSVTpZrjM?'
    'aSiEiw!`%6hU)|X1FberX~^ch0R<|g8>>sv6f@_SAi;FEZDi#s?0GSnq>}GLl8JLrirH@?O+ptZGdMX3>K;=UuZ<QDv3_8S!Pp=l'
    ';D`LYfgb2AW-&DoYth|h0~+c4M~th;L$@0=zwzo%<=j`juAxnRg&?9>ouI4H!VRiD*0p^#F`5+PQAU(Ex9#QH);6O=kaHen!;B39'
    '$(=R`nOX`<4BvDUzTQPU-nN?)muA;SaKez1Txz)BFpX*jf!DceZTM*GP36IdzxoxeqSJGJzEgY(T~H{-bkZ2FjA=SHb#Ngu#|Jkr'
    '4=zuq8Lv$R9}m;<`%bpQYIsFT!>khoTVgi)Y7Zz6-ftOF1zxV^x(&DN;`Cm=q$3NREpn(q#&|CbP7L1Qn}o>~N-~6-;FrrkLP@th'
    'Wa6jWIENGN9Wlz`@UVrsn5*M%)sT`3O`(=>-#EBN|BxY}hY)jU<K;I!lDBX93UZ8I1<wvTiY1FdW#XygsmjCSC|^>6gPy_8ug=@o'
    '?fgKZ-3^iAyeTFX)p8(BGi|)deQ3CZ%a``j{-&@Ux@kLaj^;}2FMDKDZBP(`x~-n8u>g!r5m1!-QGvsVbhx$lhMT^jGsAc9bID^O'
    '%8)V8qlD1TbRC0$<`6_Gf*qQ$_05)RFXcb)pO6gf!|7NFs%Pyb>;pkDL?|&KlJ+_*GjQtwxtLYg=8fLYm{u%1>O5niH;ak5dH_OL'
    'FuZthK_;$bgiom0NYA_@(7ue->8k5DGV>Ds{xH0%FNf7>V3Ymhi>YH;K^G!){7G*OVU~UsD4{nvg#xW@uHBITaz>ulbin`*5=jjF'
    '=tCmy#KsJR^*Atwr<kV65J$YZb|d?V!!Z(j(Dx1My)ehI7yk{dX0=K}xU41E)Cku`IXK<fWqvZveJ~YZV;2!de8mB%6M7I{0BOQz'
    'qe5yW$Bf`lJAUOZE>L^_Qf9ho`nYB50Q5CG+Nd#lt@$#nu89J}&1JdvLy7v<=Mj@Aw<a^tjL*nRB1Q`H(U_FM?>@%9vD}oBm?4gt'
    '*IkQ%oLRPaXX$IW|7?^tNZZb07yeif$|?wmI4gM!=7s?<QI1w|f8{pLD*m_KY!Y<z5OTb=x(dEw@G;ye3=?E119i1VAz&MxUS7Wq'
    '4!WW5mLHz#tjl4GunlW3W=W#HhBrF~O%ns`eY4n0@HroCbM41@;vqk#jnFU}!>-#GrdXNzTH+=yF#D%AZaMD)e5WrvS2wM`j|JTY'
    'U}{2aA@2w$MV1+@SfFPPozw-jzfKB&?R!{l%T5+0d!Xzf=PV8)=O4Z^X4c8r``DCPuZXFi=;uM(*xJQ)5ortyV3QP*H$22#WvXB*'
    '$_i&jb%4aCw8dB1TJ^hk#`jC=JYQ&I<k1jpd!l}}QG>3MUY3@0j-L{eFyi|u?(T8->N{NGeB2m8IFzkH%b>k@@gy{!K2mtYMnht?'
    'q)m3tpJpNZqo28&4XQ)NN?(%H`n+WRwMI8aD?ged_}FdQwD~=UnfLD9zj#NO@CUY;QSZ!sDcrCGU{g$p*HorsrA*g-Zn}Ld?hb5h'
    '5IJFMis{4fI&#^}eDI9QP;j~Iry$P?yPH3B{f77DfF(M&5iMO+nSt9QI@1HKQ#hPo<TJzJ!o;oLwPM7qeM$lXcf2yU$Ouc9ZA$tY'
    'D=~<T5mDF-h4xFmDMtQb**%fM0GJehk4+5nQJ?S#HY7EUH3W#{9is;7v1v8=!>TyR(TCokKf4r%AkXJvDQRe%<3#r)Mr1J;hP9H}'
    'J)1S_53BCHA!t(ail@*JK3O`<WC1len6jSDx)BG^3?o)HapC`1c*hJUTwV4uoMfjiCapHuLns*oq@Y$PcisSPKLFvqrBAi^rympc'
    'PcK{Z=H<n*pcv7~r~-0S#7u5D))dzOA8v8F)>VG@MpRQS$ER=6Gb9Tc?*I578~P(KfjRODxlH8Ot&G9;CS9XC<PkJh=eOp4E88E}'
    'JF_MO0ogL~=NcL+6F&YOFq`L|s37;1hDefm3rD@ZaAmt<*)!h1y>@gY&1FpS>Ch2szl3dnZ8kH9vL(Tq?ZUyjcI`KCd&d^w9C+er'
    'c&Z?MudqlpNi*CM2(nWMGg3^de)m+XdR}4=pOlA-v9$m7%k%N!!Y_t@;^Sf(#c&dWzCL{Bi5P=+2Kb^QT<}ES&2g;q3sT0Xwap1-'
    '`}r~c@$Si%P*Y)78E6Gks@6Nf<P8JsP^_rk%794U=j6v6(DQWd=T9+w^S@qxf4MYcsOTYPTD-F-NQ|K5mQFWeX2>6mu1Mr4-j}io'
    'fuG)f<j(~ee=&q8!lhp0w(&DW;yTi`J{-ZNa4;cQvzAfnFRd1Q>iD})E7rczm7*0#@?bZuUeKvD0}*Xc<)BSi<GRBbxWvC(H$BU%'
    'KH+mjZ{b|H`jfl!pWJ;nEx4S%)G@#qrG@<^FA?L}a2(8Fl)D7i0R)4O<Db2^iSNJnDf+Tc+kud}T1C(S&hrrXNLKjf5$;!pTBzBF'
    'FrzYH?`J0{TCShR;aBJM`+wXBy5T5qc&rLQH8c=mlI*t_O<XW0kv|V1ZeQ(K>oi>R<^MkZU+I302mj~r@^u4)b+O{-OSlz6fyIvT'
    'RnEgY5HA37Z@c|@L3&zUlVtk(>CDa`Mm#=l%P(0F;)zhyMo=ga5~i4b#V=aCH;sc3k@EGY<j<e2dH(ALqfTs(fp#W088jb2Hx-(3'
    'j1lckv81sD#{4ud{Bg-smj8KW&}~fLHZ>Jz&IMP5&k=FsAZbArqg4uj6M__+(|O-|vn2TPfi2gsL#4>84Lwc!o+ls;H=QTh7~lRZ'
    's2@M2r2S;QFR$h(ZamMjAEGM?Z**PC1j*2_&UF7sESOw~4Y;%YzV#TSy=)B~ZDLds!#_XBXmioe^Nleb5evsLtZQQ+?DXy@IUPQo'
    'j1HbZe?2VB&Ea;ZxowZfjcC9LjwF?@BHLIhWteyP!3jw)d6*)mvY-U5*s*l1watkz+TKh!#@*o$%Bq9IB2b1jSM#bILczo=wf?Do'
    '>OU5IT7l#(W9$$YPRPeu_?9qJrp86XC5B}Vt8l}Lb+?pR+Ogv6<0dm-X;>nl13mkox@gOZ>s7S&ZGwjaTQZeYH@vsnoWfumz4;Fb'
    'uCM<&+`2Zu$tv8x$RMOXW}*UC8Uhvf3aWP<QgaGmZ#KVbRbvwl8#U7yuIxGzB%_veYbe3Xu+fOwOn4n8$<=w5u3C2U0-Hj{uWyA^'
    'or1f<Kw&@u3tJ^XYa7hCnA(wFv*@W7zkHie8wKniZoY;?_+W8ZRE&@`!efaq-l{%l_TI91L!Z{q<I_K1!5qusG@yCM%azWfVRGvR'
    '^oAEoIHTfgP`juY!?`ka4%7Qj`Ms6*&_oCqxY~#a;w;NO+z`eu(!lUZ3B?QBW$snQ)xY}dR$yXWOkPO8z<(sXP&E|XY`)qtS{mBy'
    'nk^a~^R)}_m|Lq#)P!r;NA!|ggK>2Abu86Vh@NfdmlOFdKedcJE&crbnm!@G$X-_a#>baoORi8OJUc<|R2dVJRuK*Yj<yHx2CuoG'
    'W#N6??^<*Fj?*qcr>=&UF#}=15R-QT<xsP_T0uI63rH@!Yq>pF9LN<P(*zgO))#iV;+1cS{z2aa5-{o$wOoa|oeREfWuB;g)UiDN'
    'sd2*9-z-$mlH*!@#h#`<Vt}#lCPinA;gn<V$cgOTt>S`lhc976&fEmZq0ATmb#d`SR2tQ;<sMz%iouQH3dO4TL(?LYH>x)rE;4^_'
    'ZWJT%2)}t4=XSeR{FytzU*fzuFV4N>C&mK;@e%R!fB~!EQic+72~2t1wb*GC&;|*LRH~0*%}k#gObTc=3}0;<B_dk@T@>f_-LK&s'
    '*WdoSXRcq6rfDn!OYMU*>k`+YV7&lkRg?wZYcE6h{*v;aL&Vch>v4I0GY{FYipjfZZF_Ut5{`+7=!g4X41~GL!Z^m!ZLeN+dmIKQ'
    'UIT^5iKX#N08=ts93H;N1l2fsXb@7FpY~@qme$mtkIS+pqvzDh3s<Hf{fl;(KK~HZ_D(B#Am<C?{(1lEWP<;C4$9%<>jnqZkTH=K'
    'v5&WO#qVlX6?(mhe-bneAtDeX%lEIm9Uc~<5xJ(84-6UOCQGJ{vyfMjj%8eG4Bm@jS*}>qI{)0_%R$lEXR-A%znTM5%=ADoNh}I5'
    'PvQ7onB!#EE_#-YKW}tp$PMXMbYwU%mLaT)D4{{*Qv&+%E1=z|`~8bY#;|jY7_<nPXl&yiH+Mpw*hU;K!pU6{Udh43P&Mse9QLR)'
    '^fH`;UB6$BUL+V%1T%iF12p4Z*FYQ$QxnCs{}>0vcRgJ3wjUn9#mdiSr*6!$WB4;<F}f{?c!qTa3vCRWME3$3oHhgS0rb6p?elGP'
    'lGbgo5y=Zy9efJ+cEFaTu~1DL1i{sWL_`ZPOnLS%9)EuKJz+m=acAqm0;E!CFh1`fVLAx|XUZZ9KK^Uub$NZodk=rg<z8TU3vQoQ'
    'mgeVkh<p3f&nI#2=X1JnIEz&e``T;<{OQgo<SsO)BGP*(t1wt1+VX}=+z!0ay8Yk3?LQmNJGb6In`vC3c{mpMM`J*VFd7{Xd}VGO'
    'N+ySW&n0ql!F(r}{>4UK#;Bj0L%iel@?bLYgtmj^JoLRW@QUwMx95n5%7{*L?KteH!%{eH`+iiIFblIe2d$QY8jX0?cgD!K@R{w2'
    'X}iHT{R($cW{j@HE6lEy6ETiWCKi5ytfy00+`bD9#SG450K-PWG}J9Y*d$dvj{pWC7(!5Oaa0i6rl9fy6W^^cPi{h=#vq0aPkVkB'
    'uTq^xNafH0Vih@Z%jk`@G2t2V6l8oIly~#<=cg~@-PX@)Vn}+hK8&V``=^KmJ=3&t{{jECm>D>v^4$+B1XrI<;Cf<?`*}Vr>+r;v'
    '!$yZw;;PHU1&zih93~|+VGPDjH6R4TT_t#6=wk1}+q2E;a0g>^z)TCkC3kW}^KgeHABNO+aZJVwkMrLa{7cPzdF3g_PIrD<&#c_-'
    'CUs0PdT9z-UK>M@9Mx&}%A4>H4>b6;1B+`SHu_OWP0AoIJBwV|vDMCP-_0D?wcadeJ`Zd2WW%KtZ%b`uKwEI>i;!f1X;YxXq7Jz_'
    '#fE(5{iplaCB@da?&4){4XC6uG$iREqa6%?&Kg0l3_jQTJ))a5`MyQJE08aLl_Z^6OfiRdbCwAbc9>Se`hnq&Q)nvrJPrHS+yS*1'
    'D#S*GRKa{9<ua>8H#d!K6wFD0l`zX&>v7+Lfk1zYXm|PJoWq#HBsf}sszB<<DEt(cc!5Zp##x2A&C=~$bLA25X}swTns4p!Fma<r'
    '=tESm4dwIzdfZt|Z}FIx`nq*D>JA!%nBU|CCkl3ehdivKCI_QY(`aP$>iFimC2^Dw8?LWX%plH4H%&W<)+U?)>mi2kMUZC)0>Qm@'
    '*|)4_1FF!U21v_u4MDLFKMxE}#2({*vM>mvc<lOpYi|N0GJWTW{Z$#gj8Id;@Rsn?)qtyG9vTW-KJH#^lQ0Azpkd8J*9(aT6E>6V'
    '5h)DcBlur2?8e;S>Z%ogHo51okUM+v7}R5|AaPoW)0YKzQxRuWvbvT|&zPB=vFKU)IUX<1s8pyL8rTKBEDrG6M!>BOYBNe$+%r<5'
    'p<k|A@op1!CKxgrDdAjA>`MW?Vd~E*MViY(2b2ev?SDR`a%0(DY*oEf77P4Qq+@tkI<4&x84T5sX;d+Cn(2F0^w%xFYA!ZdXzC59'
    '03Z=K5j|@Dso^vVpb)Iu2vYvExo+K)qTzBZ2I%p0L*H!0CsUD-4SAi=NU7ms;&nWa;{6Qm-xgleP#n&)9%-Xkb)8OOc?vAWFoe()'
    'DfGx8mZln0Nz?c3ebt-MAIA+{28s{#ia9!rc?l~iHxO&8Xzmz^0d4$`+Vp?@AO8=dW*Q>'
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
