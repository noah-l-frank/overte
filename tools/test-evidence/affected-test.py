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
# f5cad14aff3a4606b8154ed0366b265518a9e99a / tree 81b732ddfe027f38aa1d03dcadf325aaa606390b.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'a31650ecede743dae5dc2861010714e53900fa532b63a381572afd6429141a2f'
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
    'c-qa~+j1OPk{!@@eMUbInsL9(SIA^~hsBl5B7j5#iK^m^&A)4TWP(L@0~wJCj-)ZoR2Qq%=VZhQKknQ2-u|C|`}^nJ;mb?^se2fo'
    '_Pg<B|Hs4hbaQy>9-imv>F>Wi?;rm5@BjI?`~5im?ce{FCP`HkfBUz;J%8!^ZI&ge|0&a~8PdUjO453sr@SABvPy;~os)bX)71Zm'
    '!?(xyFX->~{onrU-@Y%~TWI)l^SHm;4c}H)>-*e)S2a~_os8WyG*w*>{gfniGUru4CUadCUDCY2+G96-?LJR8f9#*W&UgDiZaz<b'
    'ZFku1AD&khABJ|GilpzFa?Yl)?uxW+>#6J0YRH<Tn5!XalDd3<@u%r=|GYcwpT6A;U#8*f+KS~+)Y<I0)@d`3V>?Y#JD0_r6l3d$'
    'woR93#ncz?uXvcA4>!**yTf!dPLI>WI6VxzX>Hv;$*LhOtKP57+q$XxJeiv&FS@cH`=&_y%nR?UE$gnWHCAQcW^)`9|BYSNb>&oh'
    '(0S3c)!0>4TJ)*+`u<w4ukzW;eVQH)H~)C)?soHTSl;U2zun)xzk1uxLp3*bmiOsgwnbLWZJK-Pecfb9)f7cn&yM(})t~miO~c_P'
    'e*5$JWqmAp)|FjX48uItWuF#hT8wGkrR|WU)##l&W9^n@|MgIvUpkwoWUR)#9n;KPO_HSbldG{F)2=Ta<grQm;*DS2KUq#>818nS'
    '@~2_<>9^_O>+a$C)8{VU^W(SoS54DyDEeW@`l2Z6J}a8hN0Zj&G?tCuK9^Hk*GYECs*irT7k+--Vy^S4=%%{K`(&syKW=XN-ofhU'
    'te%s)Nv3HSE?alspI>$E<~kW1qjdKBvZU>jEU)vv7}}{RhI;OXu59v)p7GPm!`U^5w5Y0ToV&I!n%d9n+Pq5IChha7pR!`?lX{xx'
    'i`I;jd^>!3+TTyN&%^%l{I71xB1t^i&S|QKW*VlpEAy^S94fJ^9L9ER(#xLpvV({2etH(Tr`xBgd)z&IKD&+4N9&`W%Bm1Gr?i;z'
    'w9S0TLtiCTS{8+n;;OoQ8;|$5!~S93onPNKJXK9zR#lUB%e7eLSyGB^O*xL4dt#{VF~4~IxR=M<KYyS5v+MWHSyB{ZS=KIzGVvtJ'
    'u1$u_4e3PYo<ib&?k-;633OGSU3(hlyy?np6wT(m?uU9v`!r8Fx7N^QX*1?Um2CL!5mEl=zI}R_4iV{YpY|_@>2}<8pC9(mhuv^K'
    '+T`uvmY#~V9LlNi`rBrjI#*{>R;432_E{%oX)oT!%lLS9;jF2vbV{>va--B^8&BU(T&DAw`4DDTT`|@5=7o<3@3i`on8gu1On)BE'
    '2cXi&E;Y&WGH>#HicOX6RQKiRYiy?>mBzHydbqvo<b{X*{cgAs_I}?zyHS0BpSqWEcep*>cyY^~{UXb9>WVSz`f18%(Qq7#wk?V#'
    'Vq#jA@iIJ_`s&>*UuAq8cioFz@_dx4t9%%<v1$wNLx$0dn{AV|^DNm(<}{rW$yRdxW?rO|=Og7fbZIkWRWm20-`<r&R=XN}CeppK'
    'nagf0@@z`4-ow}F>0!FNUEb2!owQl+fsA!EjCG&abCG0oKW0^#)@?OcQ(M>0Z#G}Oll$&Lx;@^?@g3!-Z?|7|&ylN~-Bl77S2Y(+'
    'pG<==QctDJ%q=QcNOL<(>cUgHepmb6zx4Y`Fsp{BT!yk2EsH*@Yp1u%lQAEfd~$-su`2%Q^}BdHRUX~l@>M@|!{K~jYsR9<>LP2Z'
    'Y;G!1y)5&37@Mxj9P6w|+HuO7zP)-&a;o`m_xa0VbF8iEe3nrqT~YR~mdSUXHfi06Kk<OZJW;dFb^n1at)*KYK&jMB>NZdEDr?d#'
    'vMyPcN78zGNs}vHvhnIINIOQsZuh$n`}X@II-dnND_x(ov--_5$eX$m_xnoloqJXCoDSkoa{Xg@KKQQAAC}h9sAK8A&6{Cx3C*o@'
    'J9tpFa<Z<=ye&WQ6&<>#&(r2xV3zPE-7v~N=E@nFeAsDGmkvoCPe|>Tw#jt;TRLW|uUA38e|Z?Yl|bW|v<{B++-pf-7hR<^s>*68'
    'vb3*?q)XKa#q^8zwBdTnr#WrQwy)Z}$ftHJhoqmCgQ=6;jE-?coMBErxTEEcy4@58hf@BYr7lbtW0Or?H%@)yWUF$zJkQHg4PAcp'
    'y-g3l@1FJ#_x{D>t2<xTWr6bqN|5(`Uk;TkqVKAysH>@K`ph$PqmTK=_O$sHZMvfFa#ckQGHGBmW1+g0fGIC~xo_ozx1-|MZRd6;'
    '3H*G#JytTozHc0;vCf7>Anv`azO9C~aarW<w0@d1+x^(quDa#>8lWX1cE)Eonk;09I<aZ9bdZY_bCGvrJN%-p4g32ACs})7)!a>a'
    'E0HhSRG^Ia*+`m&Z@aC=w4dFxO+NmbT|G~~PY)|qwUV_R%6Nf_NC6=6yqY9+ePsF6KtpqZy!+UGHbnyIVbSIRF^tpP4sF%Bal54Q'
    '@ecsmwDLkzW$p*J@<Ud1zuR)gTi{_A07E|IYOZ=5AZl&ecOV11gS1WQ*cJ1~_H}t`<h^xrMmR{>=K*ug2^=D=vceIs@+PyxBANS-'
    '?n{1jJ3LLW-NUZCdtN~Ylw3uTxoDfVm$uEbhZQ+N+DmrRe1HL}TtB?0Eh$0n@^^6j545ODQ{TL-8l(@o$(u@nns)V=Wgpwj71^5{'
    'vY*o`ttwxbvbif~*?(QmMLKn<D<^XgrrGeZjXm#Qo`71z{>ucn9?oZT)*BN=QRm47$~Hl8D^PVCCBQtiqlY$tm_E3r$SQ9)l&}yc'
    '`5Le<t4o#H+`DHosLPmV@cVQYo|>ddi(j#wx!c{ntN^`D(F{{Jm0ePl-JoHjaZz@1mLc<)hCFXt4V3hQ=lXE}IPdPJ@73D*&%bu*'
    'S9zy80|$wi6<Ee&>E*jgK(abJSy_GXbRV8xo)2!4uhX}uHE7f~FTeDC7yXnv)2(+jw1Cp2PaUeMnTxTRK2i}}u$joRlRT|qqFLL_'
    '-ky$!j#tqqzObP$^0I|RY`gwXAob~=oWCu`92)3YKu7D+eW9RFWU^)2ml9bRZP^S>vn|8^{IZ0*>FIv={JiuK&n9Di+v-O|qhoHS'
    'euQagmMRl_ZKh&shNK(CoNYh(%Rb)ze!mv*<APRCG+kR4L!m9332o~0#tl9u=?ISVnQUA0n6{h`ojO>V4=>mL7$b`Ud`~HW3v4pG'
    'bH+5chjCl}^x*RUeY)+&``!7QL}x?tA^vGiR+a7tRAQWmPG`&i%K==4f?;Dpa9VW>n3yCkab;N)NcAucmBPO8#X~^?J{pv3!oaq('
    '^y8PbIma0Cbjo@~zWOk#Rvn<RC`&DBeY`x$#=Zr@Z>$%8?DuT>lxof3w#dgZhw_(o5e5F#%AWOd^~Iyjs5Tqx3l={Xro;Yey8X@d'
    '_%NNXAtJO2X8IgOHLCuq8p_-zQMtF8QI$Hi8|IA|-H$uC-~T=>#i%Q2<tj|!lC`#K(l>b*Fs`&l(iwLnT&z{K*BTFPw|x(nMU`Rj'
    '#FN}-ooIb&(yJ5FIZwOJmo~Y8CRBl;?YFPLF|?%Ptafa=sI}oJb>oW*#LXw(_z;Umc$atQ+ZR5@mkrNc4dlIR=4P(1EcF#Oa_K(T'
    'T+Q6L0AkRI{^zAj|5d`Cze6;#6KPK;bqy?}&SdtD2M^FsyzUfEA|acvU;fnX8y;WIKL_7kI-n{f0Y#&Qs59JT6_nULr=QT&8ZGS='
    '8`-vgK9`!DsjN@4Q}QKCoqZ2^<`0?<x=>~Pm|T7YB<u^9!>7<aoyUUu-c6cCm({H@2zg~`Ps5az4&fv?HZqNI?62O!wkJ`0{?<!0'
    'y*p%s(O<C*Jp4|5Jh|B=SEW4Tifw#5eAz#212p6CD-wV@z6bRaiqKTnnkWTeMUP2!?0FSeJdCI5GfYRJGT#32)IC0~Wm!X?D1T>%'
    'LMR9f%;ngZou06Yd`i^@B13n@!2m3sZ^BlUI<2ypbZ#u7wFnxVb=$H&LS!)1N^O#1`_kJJg0}A3E)R0atQj$li5sbaZWWS)vFvpj'
    'g90;Oa35Wj73eRNn%<S??<e<Iak`yD7f@hlC%ALNP~{t{q2n*V**!eI96ovLcPCcWjST<hk4fSUR#Oq3-Hl#dRH@$ja{dOHy;2dh'
    '7Jvx2d-hneazmE%({8MOGmSxf`f+1Xdfax0cy#N)QKw3jrl~<P9Hh>v7<|3TlDbfP=o3$IYBzwR?`>?2v@`nxB7gE&vcMW#q2t(~'
    '+9kEtXW1i%>E~^r%q*AnE4lIfl2SEiGqO|7UJ)TW;JsR`o*JY#pD3P4-OU@9e1*m$R^ECK-P8U4>Gs9Hx01D#nGeAospA3<8>%77'
    'KTvDi)M+}SiKU8BVSMX8j+N)li7WBx`DyrnO&(d_*#9*;$@^P5a!R7WS~ATQJX3nxG<btv5$<Ur<?1SU2B6&c>)CWDzjgD0?YsgA'
    '%eKyEy+vPVsD#1F1r|geqUI>@CuZreeMmlMgrh4rvyeECryH5Hd)|C}#>)394V*GiR5rPd2P_kBP3_%{r9YA-RvYM7tNZF-c6Z|u'
    '|Je$-ifj!cP}a2=KzdZkC<xSb9S8`FOuHoyerEdd&7Cm2A0FEZ55;E}&r3)c@HHWINpyoX88C9HEEo^z)D|D#*iIYh>Gh?aNayE~'
    '1%0Xvd#=$fPw{fbG`bzRhH-{ZhhK<ro;K|-*x7?S>rT_7d(!GVf668ix`##UT1)j{=c1=JKS-%ZjZyPz8#iTNetcKQq(_YSp+kHA'
    'Qtdk=uNt`M-6aCm=z|<vN6m@DwuK5n{hR*dTe~E7jq(g<-@(V97r(Pc(;vYpLa7FFbUoB--7okoPwD#ZeyL<%`o}Nb^9nl}X|fXL'
    'ZEsM=2AUv4>Hx+F07_gJj`qXQ|AI4iyb3qL*R?*UC;{6UG5})TERg9u^+Qr+Ly*)m4=$NLzNzQk=Y<`yBLz|UZulrmz@p1g(Ff2j'
    'fVj=vH;s=$>uQkbdSLL?>AzubOQy4-?cPjd+D3Z~`L%WSRKqHw2^Lx^5wVe`5&HZKK7v;v!1?XW`o~zHAX%vmXs7`TRavDjXv;JJ'
    'Y5h_+!j;>3-NUELu1fuWi|YO5V;^u;<7UE9MwCF^>Y)};+qAy=Eq>qCa#60ZZUVYO&UPPm;#A>Nlz79j;JSU5hfo2r`NPlW6yncA'
    'I(e2UmRvb5WK;+UD?W=D4?+;t(aKwBXHkB1FB?9y45KDUeJB|<lo4-Nr@faCQ#U|2hfX%CpIv`=E2sM5=Z|eA0whr`&9%-+*Mr#e'
    'JgG;d|JlEldtuR00f2vWYZq(@C<yQo74fwS2~{7YRry~^)1<F6^>x7G$(d?$+&zVW=(Mvbn_gQH3n1GKhjlD?*3FrdK{r%s+YD{w'
    'Q*8o)sB)M%oLpJc)%hiRSSw;xX^N1nDQo3{f`B3~4=%H|(nyM-psZ=hw*T&pjVArxgqoq4_2SWma-x$~4UcRgWkaA&bs^IBt;6a1'
    '>mKGc)MCms_>s7}D2ny|p^1JN(b9nQ(mVZ0<wd{6;2igZT3nXd-F>=6)&D`FbsPU|rC(=R2blgXi~DTq;a4R^iPKe7c^^#iyzZv+'
    '%Le7}JSNkQGupYnKr=~%s46jNRos1OSDcw#z|+gh&o6UKc$WXX((7&Wz6_Y9pUb++PzGtCYDHVFOBK<7BAOZB_)!6WO%H*Jf9jqN'
    'JIX1E^1^gEtZ>L>=OgAFG}u)_j+3N=UQrooanLHWS-VKP?Cg@uNs*ZQ`&Bwy8nu9iKEm&SBbDH@jtR)EniTHMP*O9B0dL*0|FYnb'
    '7;^rcbb;)Zd4i<|@U68OD+DMfK5tb6<*_avR({`ezrVlz-K{;Yr!-*9R!v>{w1Fcqe$+2m%}gK(-tA?EV?VZUHLs7^$~gVLi?^u0'
    'dpyMITN1q_#0h950a*Irr&z3^>Qd&rBzye#WYqNR))pPR$3tjmmI(7ND|&i=Jy%aH@fvZX8Yphx=`!hG!xDtix=zOia*Ex)ZN=yB'
    's_I8Y!S_EtAK0?!sL~QUx_TN!JIE^_^wbV&4B$j#CGUss${jpD?q2S1w`^nxwzh84R4;AZd?Gg<#qvnbBG#h?qcC*kg&W!Q5b$Lx'
    '?X_OKErKXo0|PST2>C~sRsGO()DEPEm##hR@7yo@V+wzwJ+7bqya?pJr)DD<R-mc<H7~&H!Q>-I(PM68`QxR#SpehP&y$AxTFVj9'
    '3&q&CpqnqO6_Jl&G!)H5vRu@VWEh;PZ1WbDbFk@MpcIVgX0w16RI{=`wwh^lvS|OqjJyY!R<`+F{QvO|bS~~!mPE2`q!k#633;vG'
    'IYt1ig<9=&RdJ17p!J$>U2>eBzv^Dy?uVDV-JhGDJy<oC*0%zkR8k%^9;LX>Nn4<o<1!&IO?7$Y7Ct||+<w82yqlg^U`;*6QSnIk'
    'uU(?qpBA~q1f-KkZ!N>I^ERgB7wiKm+Vzg=zQQxoq7fAk$8boid5*T<7$sA15ejm0>Y6-Hf6ay#fN4WBI>7KUbQ?MS{xItNQcILn'
    '$fOEWyuvAXS9x{iu3X$tm=Vvrum1M+@6IM(svy*qwvYq0QWGFkts_g3IX1doW5}Yl5V9-xb3`DzZ+8M()JW6ry({)-NHszHl^rE>'
    'RhH46FHuM)HXcRf@5~oe-cxz)XLa#@SXl@h1MNuGv}y?~8Y&6TY*d2_se|M@f74au?fu;Ehp(GH?yiX*j-tBG!}Ec@MoT3PA%AG1'
    '=3p(z{O4io!l!Dn-#v_L>`RquD8mG^A*D-qM#I^JP`?W7EEQadP={*s_x!jU_Qj`p_vax{{{{R!AJ;;&BcYQ==siYR9CQKcWS}09'
    'V>O7Zqi!x+|1Zka=4(Zn-UZ!M^9XA!`qb*>B1a{{CDI$MgWU%xyKEy*VYTwKeG_C%N};gPQP6_ux*oV1W;Y};L^5eZfC_lox(WZS'
    'LDab5jxQpm8bgH)1Z#T~BA2T4)A=N;m?vC<p;MAxxr1ZAv-x?1qC=G%Fc%T9B3>UHaU}e8=A0NVFOXWAV)I@9``+K)E|x}7t*%5T'
    'X;q?omx};>P}q`4`7J6ep_5YJ1gmg;?SA8et&iWKL)T)3<AZ2nYv9nbAj|592^Q+YptxCEkYMK9e@vUCS9<PHhWOxJS6=kohQ=v_'
    'IaF?VnO+LL)_+)Aa*?9F*5xZY;WiW$tsZeY>Gv1OgfYbvAk3T^4P1X2FqGB;&NiL2&J)}z1-Ro@WYMu!eG>u6S_b%gdDLzX#n#1^'
    'U%EfFgX2Hm9{&xQ!QF<oYk;PX?x<pCgHa>CgaMFp-NVOCa@aD2k1@GsJG+Ny{Nh~nFMPM2ZXaLzS1!!?Jqh_PUmz}Y0(>_Bdq$nR'
    'h8dDpdL1xckDLFYJ%zfBUTV5?Ev+%vn3jYVp#m>}?!Zz5Iyavn>U%IvUIu%ud&?5(g8lr^zL6fx(_wdi{+e<JVzASXD0``c<F+CJ'
    '^mXX?`hY@XCjT9~Yj$<#>FD-OYoXa&NTNy4k*iVjj2={qC8P+^iVMLVzycnUUbBb$r5&gxv9<@^T!FqocmPb&M|hqK+nHgSWj|su'
    '+HXHzvxl(vv4^K|!?T#&OnE4txSlyF;CAd7oD-G^qzq$4&H#`Y>TC9)H5%3U<BJ~rro*A;ZdJmR20m>RL(E1gKW7g+(k^P|xV5VG'
    's>88>HMhrm>-c4#e?N)4xl#|xUa`0O0LehPI7=u27=S~Zn(4Z)2R6Td0sx$L^N;(x6;hpKhP(s;(S5=YNWD|=|5BwPEeZK<Q$_pu'
    '3$_w}b{;ceu~OCg)ziW$<45GNh%tz<nB(=-2F~4#)%AM`R_1f(u&kgrfnq|x)6k?4g}}DFDe$d)Mn=={H9;?#rfW9x+}%IYq&){e'
    '_}JQCBkubfc%ll6$3Z(xeJ0zVRXkc~eTfu^QSH!7SH=EADAUIc6+jU+2iU0A6R#Z&{S|$P4v>JUTR=G=^f18wnoS&!$8e_*JHH3~'
    'v5<+3up`HW04@alHRKoMqgf7I$GfYye>TIH?(iz3=?<&kO7Mgs*}+lPU6yLYRRG;?7GzZ4Z<qwKyV)MjzMDLrtfN4<UsezTgaiQB'
    'q~BBHTSePIyApeWq=ikB#}SZ9vpt9%NwCM;W#5NdQZqG(YTe^Xl7#w+wk`eCaxaHQr-tW+)F>LLVyc=vFZ=D^YQ*s2+i*9X^0r~{'
    'g+%^#__DYG+)e9sS?G{a5~@V#a@px80zr`l;`Tw}&<lhNq}?yt(*|QNq!B)PMEK!sD9n=n4`8n%{<Kv=1AH(Hn_se_amRJ<u)=uH'
    'NZ1FxG>zUqY`&@>S`GX>C+s0d3+rl*GVYh`=xO@L%UaAwW{#sH!twKB@)$`aM<5?m5$)TC<d!g|s6V=)yZz_g!zQey(k62SPH{oA'
    'x^%Lk)rIUo*s|;?-H=6aUOu`b=*M$tG#-X&(_w;c1cJNt5p_$wu{Ny~Dtd@Ld)qz)%x<L*KPe5z@2cswJ$XOgj+#Wvi3O{0#G17W'
    ';$;#U9)9mErI^N#?&*0txT!wFb|1RO=P&z}T@mdTxPp*f{mv>JRpKp<a?K(b7Gn^^QM7;Au3jGR_T71?c@7j_0nbVlo0kuWQUoz)'
    'Mts(Z4x}ETsi?A#?&+}qIz60dv*(j77;dm)2lYx<%Ek!~MI&?^@~1W@c+X;c{nZ;9$EQH!pQb7PjfYi^pleInNd1EH0?oraZNkou'
    'SqM&JQ)I4Kw3TbO;~zw$;`Yno@VF^335oiq*}|*f)gTxYSf2<9?iU<OE>soo*0lQQhMtF~-Q$+4UstPV?aZ5GDAkuVs**n-EU!@I'
    'H+PUwkt#Vqu%UIDsUArh4g@O7F_RgqWL4Mf5lFQ7M!H;xsLKB84}RR=cjEMNef;J1eLh~N&S^&(gM}M8(Snf^R^r~Eze<?cOoXx1'
    '2e)*$3#sh}v`(4Q6cbf*FZ@x+K(R*1Fe9}llPWf$<`I#KU$Gxm&9qxH0tyGav4rKhAY>w>ZP-`wp)rv`Fw3GLsCAlra6=(y;xD%;'
    'LKF94N+9?ozG;}PatpkP?}I2G?rEc}8di~CyQL%J==(SJgW~M`t1H8$tk4H!LeNR0X+rDh+beQ-Z}ends?+3GZ7cqY%DBOjRZ8Nu'
    'g_9KzC(LB5#i51-@&#+WUC1OQci#M>ea-9kHsKUKK^#TL&=M86%3*dd^G3uGE1{8$=!Xw(C~nmaR@RJJA{@<Fuh38jy3vkkqZg-4'
    'MbAM>iuO?Y!QC8Lj!!<i0|w-(vI5H$;ZUkkP_ohqkY1(1>sBptm<#J94i}iFAKcaH{&;!V_^@<r;j;2ucYCLVH8-GZ@I(UV0l{PF'
    'gA>@4Uc0T&`@=ps<r41G-d3`0MD`H8P8s!e5iCc9N(72t0id;5Bg$cnULCyySqMIEz?SE~v7Yyaj9+NhXbozm#;VKBr>1BECTnkM'
    'e9zZz<ZeGMc2-C8sPl+V5l-Z^dMG6Aq5*Jepw+2~w7p~Qg34Ot{=i<M7&^VAQ~2I=m4F@6z_b;wsG8<@<blX#8WCPq_><L&B-P2s'
    'HnxbU$K^{K_N%RkNYJE*2owBlTNL0Sh~*e}M1_jDXoW7|(6xIy!6JV>ru8jVX{&-YA0i}iP!fg<b5M8nWgTTPG7fcmeF0)sc6+Dy'
    'w-FpEq_AN+60n`-1ZR6r&2><1$?q}KP<?}Jesx;%u#d)3pn3G~p4b}WH+7%k{SU!aoED)%a0;d{EF8c!X~>y);apvR?3Wz!SPtRL'
    'zN|z=iW)`?h@@#4lZn#!<AFd#<8g{94Fm9Ty84C%Eyl4{^9$MAkQ$Ix7gouk{}u_j<7oQFA5iQKJfO_8vCsJ<J33iI+#bG!>)!e8'
    'Fau7aPhnZfVz{KW*4OpJG>x7Yb__-1)v3{`BvS{8jtGbAq=V4r`qr`UVOFh#n}Wg7A@|O74>H+gt*LSKJ+|DW<F>mabF*s;Fl*zO'
    'FMpLQ0;#p+b+cJ(>3lIeA$z%gFUuWI+OhR(CrT{j_}-1Guoz$;{KtttRMxbfIvDZ~^FFE%?&$aX4F(_K9RhVR_$iw*ICUe3#?-EQ'
    'w$d?fWt3QV!_|4v?@c7GzXzJOmfq({u!q`!tn(OqVd*C9A>CO~UGtY#CbiuMb~61LeEDctZ?+w^cw4t&@L*OG2fci$4h`LLv-(#F'
    '6$WN^AKBDyc{<b9$JD0e+e5e_Bi5j{ga;nR6^pnc3}Rp)VaSrVAKTG>Lp^5PPh@4m+%<{B%p<%WfEg7*7!~20M?|czhdg5^hrk&2'
    'Pb-weB9iqyTpeoUZQhw=kK*$*$y>9i4CjyleqbLbGT^YLH$=0;Eap=N!)F=9!gtX8VIP-|VT$6Dr=;ztk8I`pJtYFJ<T-<inK31V'
    '1IkOrQYB1t_*M#pPKm1CZSE8Q6`NV_4g$bJEkv*GtF8lq(XOOg1^>jvFcVdHf=vAfHWTu~744Kz7V?*H*JJBf=3%xs#3VSWGIopv'
    'tm8q@4<FgZA>2A|gT%FpMJb1)C8}91osy8+kFK$B2eAvHB*;v~^O4y5J%^ZZLTLO~%%1pbu-Y?L3m3iBF!W5kHBFVGkm(4}{%F2B'
    '&H5|%yj>cbD?)xQ*z|~?cjPkIsTUP<pR_HMoK7;(C*0|;xg<T9&`iKmjvU(+@tf8g_rW5DBKG0MhG`6caz*-<@pK^0GOX>n)#Dv2'
    'o>zl|<v*|Xwq=rCm{W}MCeWqUU>V+My^5-p*d@^rV`03V@_<izl)(PnpLhjPHXF3ycxxnK-a%7}8tW3AiN%Bt$D)NsH`8b+FMuoF'
    '+1FAcY~B?a{17jTH8A%`QevH5RvxTjvoNyLaBe-oy105*r{>Al{YZsDls(yk&Om(Uns1m1IQoQ@E-B3ngTB)A>izu4qTISENneZ`'
    'jp_+SS=S&u21A-2AH8lE)SjKq1?kqCn~Hz7eNRj48wY^A8+}}23OIy$B@r4))J5tfsO8DEdm5g)=Pzs_ANGfCUH=VM!kuYDL&35G'
    'eu_jM_OBy$n0f&LSHYKEz>oW<-JCFs?Zbh*u^3cp{+sE45e8(T8Id^e6<+2L%|fwtbqx3!cG|e9uoW7yCkX2B{$o-aOZ>zvCA4l<'
    'qB3QY<Zc{4wyCIwH{12`S;^<4X`tjdjKPiRW9gG9lIy_1LpPLH*Y4;$lCpV2j9s&SAUrLnxL0G0Q({1xT#y72lh8kxC13sC;^B19'
    'y4@GVNA+$dJ5&po;b&l6sq{;~RGwNg=vS+|SK4cLbSgjPQ!k%mSilMt4`sq-H~T8wOIXk#C(kj8H;=|wrP?B~B9yE?yq#k^XTSY='
    '(|ZfoO@|5YG{-e()?{cWRXd<Un4QtOX+M2%XG?Ej>z-oPU>OQ8y*WY$8JX4!%7SXN2tZsW+0<{2>$zx8&tF~+kuYw*Pe7*vQW|!x'
    's9iaiCCwf;FX9jtlwyPCL-D$KU#E>MNBj9TVh%5hk@Nv?K?=7!pPab8CNPUS$RIOoa}7l|A-vUh2EG(?c*nKvM|QODf0Hz+QiV<2'
    ';)ij?2qO%Y=v?X1nDgVlh2NM^4i6hc1514DZn-33dSg#N{n2V_X`-k%)r5&XCnE+KkQPo$_>zoj7Pntd5ruX8jwZI>(@nJE<&yuL'
    'U!F&!R6r<{2~Z()Jo1q_LIPy00e<&!{ju(N({km#&7At(rzdmzyHh=Xek-A$o84vRQJFdy6jCEV3#Kd*5DXmsXVlsY=+5tKWi|D8'
    'K|okAt3&6bP9FMbq9W!83p@*-HH`gY`*(HddJyG_V7&b2Aoo76Fk54M1g}L;qY7s{G(3pd9E5-vGp;=2CSaP<M|QFHBt#T*2*Pd7'
    '(Il>$Vq97lgGv}gGJ8c$<dc(ZPos}V^I;bsFg+dg?XLT_kgiuWX2Bzl0o)Ab%AoYBm@Bvwa)J^X@LsCjFCar5_d&|nJ)NxXjw+J1'
    '`k34c0W+cqKw}O^7??H!RLon?QNh`&*X?}SHdu4tK6Q}=-hPh1uJzHw^p>J#j8vIf6QKm++MEPlYiNM}j4{=+pXTyi`0pQAtk}X^'
    'q>i}&IJ<xg%#c1{iZ-qq{8_SJorbQeE?fNg3gQ@SdJk9?a7HF{NQ<mZc#~>JVS(c@a!?O#t|5fQ1^T#?%qsLVr<!hE%Yzh4Xv_>7'
    '`?WVM6VqE;e2}=PbNwmyI|5<ZU$%)8?D={SRvhRQ+EXCEVf1Wt$Q-mh1vg)rpj!c@aR<`o!t<!_#OZ09G%$_nD5F*!${o)vbu0pP'
    '9!*}}Gu}~6jc#DrblDCNO1fp@<aT}lu`x2B(Cmv0Lq)xJcRP`aI2i*b82i6zI(K#(izH=T3eu;cKj30Ps8hu?fq<;07QA5~xe*_{'
    'FUPsO@HL!5^be0<lZ6^DizKw6O-$B}@MuKaA}oV>plk*|8W*X*@Qvtc^+IKQp)1SNfTQxW{)!3<NC)UJ^Gk<z2uh9Hl<5VxuFIBx'
    '*~#<{hn2%f%jVbdjF0;g45nX{(t~oYKw$||?+}1pK3=@`^B=pl?sQDZ4HBrbAe6D}A%d|RQ<+qH%tk=pX=tH0uO066M_SW;SeL}y'
    'f~nu)IaM%O$}nF8U6;TBxC`BxE;x^XA(q=|%upz^5AI}D8)T9i6M!bezzq*_PP#D>7G=oTsKtAWl58&e%eN7$pSWHdsTGF&v=ma*'
    'jWOXFWW)K+eGx_pVF8v0z6^P~;N^rQ=q7mF-+oFZ_~cEZ*8(xG^5OXX`97N1RQ#`uW{gQ<sJa5FuLjSFQnxCu-_>vX-J+{lG#<C}'
    'UH5s#mN{C_TI9hV8bc`%Zb@;`r&PjnudstL1S`9KM@L;KwudtJ^V*agmU?pxR_5|2WI>jAip`;b3DUQ&TFhiH_PxD+J6MZ*3gXk-'
    'GkalvLTy-qa&+{<B`?oIXTnEJch6;K4qFrBGD5{#@+Mg;n5F>Omr+ff_SK&&W1@Ih<Pkt~@}Qc>iZ_DH;mn}tK$DV~v6`*HqSK%1'
    '#HAO%$$~JH*?}`I9cPw@Jf;QMr0$k%+p+>I^dsNAs?TC2oA4Em{gB24q%jnXd0615!HaU2`bw3|eEZi*^;3)KpNzV=b$(qlw3&k%'
    '8>s~6Lnr|%X2w@yG(?lI06W7BYqY0y<N8OmdBq?wrmJdf0pVJ}NVwapXLv)6(W&s*Nvx)1-nimPA@HiE-O_6_4M9fWlA<$V7D#KB'
    'SCKu^okiDX$d-Q7YA*e{gZ&fP2GnnL>R26v1r*dVFF9s!QcvQ(my1w=i;!_tM&PbyY~Ppt<Cre)rAcdc<vi$gG>x7xDM06y6I~x{'
    '`(O^}EKU+OBX2QZH!jVQ!I$*cqYtL${`^ble9#0DD#m>eA%)1p1dmb#)`@8Xol;bfmu+AX@~jNILUqE8;M3B@K#%}Zi*TJA!=o_8'
    '4loowOSV4pW#aM*5tWWnITnMhz<`1j-_000rjKF^B~gf}udAYl-98Z02-JT*4!4Jwhc$1tP~Et*ptXqQWL#4W>7<di9k%5$Vv0Iw'
    'Se3oTx(l)vPj`KsoD9EQBod*Fm}4Y`d=y$Wgj5|}i1}?yFG{wo`t4yLIv9nnjrKIbr$Yc7u%lFDO-$6bp4L@-%*vvg?RF+P-mv(|'
    'PxWX|aJz0k?gnxr=<{?ju{sN648_+cq=T2vXn<NVA=KEiG*EZ`cG)ktN*U;BV&aj@13WcL^7x*c+eQ7ky#A_KwHNtqdicuT{1a9U'
    '9LBY=;*)1)h7lGq2MYaYib1qPWcYjt5L`wxG=0dclBU;1k8{FfWMm(lw0ZY=rR*<bst!01wH)R{<RJ%;enhGrp_80}<;Jja^;i4y'
    '*BR4Nq0iIGQ|G<ExH?k1E{~Wl7#hYmy9{?nD4qC8E!b|{!b0TSoi(-v$nv#Eutz%Xg3u+BQD>+s@b4xkFNxx0Ret!o;;GfS>1A_f'
    ')aW5ni_y?9KF@m!SOYbN?GVd7)~0W|Kfk~7g>O8ieUNbixCjg8Wh^RIubZMPBU7nnyg<$^%_Upd@XRSIxEeUf(~@JlGU%KX0Kr~m'
    'QB|1XJ%r!i%Ch&yiFKRJ(^QIHt!uI1PvAdrGR)|yWJEe$Vb!UJI%}G)ExI3H!dB$v@lECLk3X{&Go*MjE!J^*XJ!D;!NrPX5Mdg}'
    'GG<M$R?Np0pBIbh=S_7fV@=JdEbuao24fLYJf7Nn#-%|nGEzEvvUR_8;m1(&8qu(#bk;Nora&8gjVfG+kR)XS4suM?ATA>G>C#n}'
    '#rI{GPWY<en|}?|Ue5q|NwlO;3$#u$qJpWrfF{Vlr&Uh)_f;3N%O<}V_Ha1*^%NQ=ikP_$CuZzb1WEP|+6Zh|d54u7SB|n`x6ZAu'
    '!XLpOwK#<+E166$(jg|l;fv`L=K7na?bbyX9?h%RhPo}}K&#JO_N7*n*|7k_xip6ZdyZn8np06-b8S#VrmIA{*G-)0Git{*g>4bQ'
    'pIZ|4O29&_sdKJ<Uqvt9pyT-Yiplb_br(EVvHZBA?rpSWaJ<+qHW9nS8pr`-7F&lHDqLbDXyeAUUsZ)tvh&Nj2#p+y$)$Rhetqyx'
    'LaRdJXdEA1MoJhqHXE0n@4l@#W|?~k(}uAN$k07GPQ_AL`(M)AQ=t;)!U{Gnw;LA=rta(6Ksf`{wee$Ub`p4m9!nD?Y6IByw7amI'
    'l>%-(PREAJ!}OwDJfG3S)1hHtOzmG4Grzy^OQzm7CL4D~Ng>5<yR8fV_Huvz43%MP7_+ab)YH%+@S7y)ts<`t14dqCF~6nSxZZIH'
    '+3oW^1mf%i*2U>U`Wbr1oS{=?9&j7tCMj_Wii@}*1(>(4`%1rEf3+!+T>t@$ECox4h%yG&qJj}2gSO79-HeOj;*~c>Dxa**3D&{n'
    'M;B6zFe=Tpzl}7)v?b@JYMfX7u)nXr-+x`{V=m2F7d$KaHuN_=(KKHTHno^x!TB}Xqu3fHV&3|SBFaY-4#@=BE<R#4K6`EeaJWbz'
    'g;ky7T^C!|d$~L8mN}*8%R-}<!h<$wc_H8htF_U>kNKOxc*f1zHQDC#^g8%+?kvAe`3cY#nx^oD4oEphL17Y@rNU*8Hx~>-)eQF8'
    'xPu=Yk~b}HoRRc~7Z1WOH`VZ?4FnIE=k}Wdh0zl;iDBdNCtqaF>UW1PD`-H7J$TY`RHT#9m1LEqJ{6z!;kfRXi0q^)8y9{az)LHj'
    '63pIRJ0f8Y;f2ccvIy8gd4PeXLXEIl=a($#8Lxi0cn8tp!d_&k@7vL8GrXw_Z+~Hnqz=yJI&3$u8%!!#-UfggY#3@?<uE9^4g?~c'
    'hD9(A6=YD<*p}|Atx@{Bd(jU@ROf#>HN;TWG0VfJ>?9NFL&rg<&bXt_86%uvx8A`=%oa%g4bSoGN(L_&@+%8&7U&`7RmmyME1v}!'
    '+X>zz|A(!)^r;`S<X6**?6n9(LAgg2j(-|fYVWXfT?m>)grcZ|aoSq49Gl$df2(K89(3k9WFnH9GjM8SIHdp{ZsZ#Ppt2e-TJaWV'
    '=Inh4f#s{n!91q(8d>48uso)07L`9Uy-MSbyzH`7j~UPIdA~u=Ye*3Fx1X4WbgB+UPxJ*^6_m>)G80#Gmv8>vtjmt;pU-@_-zfpP'
    'l#zb=pq8&{5pdA=Y1}&Ere_XY!^q3y0wumY2BBr8BY>Fgv9c!)Cq79|>C09t=zm0y1d=*OY}tBK96dC*l?=X8bG>pjvL(A5k)auF'
    'j6r7!x1!wOJ5HAE)^g=&7#T*QPu&K0ZPSs0MeH2MEP;h6?ryGPHc5yu(uI~eu4M*Pfe(K^9pCV$TYqJ3e!D`NX@k3`-Au1o)zAiJ'
    'u57&O7|9alk{X73Fui2q*GW~Ukt64iS{YW|eCga&_~(8uBp|#FiWp>3#CULVJj*Ux|K!xa&AL8JvOM_^-(iyJaMot@1obtI>7w$o'
    'fj&E3b?f_S2PZ`0F1*a2Sie9ERy;cS-ZaEz8X~Ok@T3u`;z*=1x(8Dj;?`HI+=QR@uxVkBS$n?^u#L7x&k0q_haD|eJtB@lVRM`h'
    '#l;K9zr8{YVXOhql(AqjDv_Cxf^@Z~NF!JP1;Nl<oV7dTI6r37Q48xF(|%__sZYs?BP1e2Rqsq~cy3qN&p};ZS@CiANQknQh$)={'
    'bLnGhWDx@jmh#_l40%b9su*qLb(^EN##a7#K?QGwDnZk<=<+<+8Dp3{>X@sBW!L~r(DZ5(AW+~7Cli8#gO`oz1TDnE2s5A|KG~Qn'
    '5u|0*uYUETIeIrN-^xM^IQE-XbUjc>R@`buS*Krb9KG2OVi@kD5DlakDbrQI;b$%C`|kTd#+%ol{oVF&^Uy@v?k+46VzgHgV{M@z'
    'oMbW+A!7tVIg+#V>ulI98`?5dk%E~+D*>Hqo|>qRp$+OjX)!#RKS_)yz?aEBw4H5-q&F<eOlD#<9Fl16L)>Wh(vYR(HWhbFzN)i6'
    'zmsMB<72m5nMat8CXH$IM<JR;Bv2dRa8G7-nvWAyG~BOM-<Z=@;OkNQZt=}Ec+lJfF3>z`4S95#5Hux$F!Z6VLR%Jx%5K=U@F6N+'
    'VtYd=;wh|_CfdGz_yl($`qz?fLiA6fXEKYU*@m=XtT(T{NN|r=`}Fj*jH1viT(dA`gN-oMBh;{0335lMrkSg$f<17+v!sg}_JU1Z'
    'NMUM$%<KnZ-lXCz&~DaTNmMRnK+yPZOgq=-E&RBH-(DiK+Vb<W$<Wjy6s+NVh53Nr=iCSKKZYJMI_9PcT(bBDr%w~O4OY>@0gVzS'
    '2^q9cFue9)rMiUy;5HYme%TQuLluM+4#Y%EBXj<YP$&;YK@;Py2cV)+L2I`>9{POy!@&6MgNd;6!L@k^!O_aR@tDw~=akT>w;|*}'
    '6aWJbmu}#cVs4s+3XCxKcnIy=fD$6nH?6FR%mDYN)rV5KXRCv;-rK_Vc~m}tI&5kb(HbBU1e`YLuI#IiDGJ3hh9tdo8{22G&Y`*&'
    'Z~R|s#V{R$@Pf#wyT<6waQi8vM|0f{URgTl%N;Yf&>}GIB%P#FM$raNhTcXc!OkX+4sf@M*8IyBwsk)#1X!J9{e;D7{HY5N@C$;r'
    'Fa%m_G6>4)s+9bnSO1yfxEP?Uq~1`IaOg2<6cCIkqD3b6j|Nicc;I*L#A5i+Ha0LVaiP+7P;JYFHQT*?v?XF~-hgQg(J-MHT-&4{'
    '+Q;V6tj4RTzS_X9SRinC%EBPMjTBlFk4>1mc+Q)PHxm<DZ?}#7ipzmdo0-Y9TMcMj)D|mQZED>Xs-y7aa%W$>2gII->GQhy5?<^1'
    'hng)5;~B$COjDD`Bf~O?pjFQsz|blQ;>`^_hnL;jeW42<DH7GCMo1fe$U$$J!X%b;rO7T_|LSDCG(@~k*W5Hk&@#;;l1Rd=cUtHt'
    '%giQ-8$C-E>d)cgQ~A1u&C_Zz*=A(>BD6H>#=2atadl5vLdO_geczb3bLBq14~E_3aE=RX6w;i<80{?Fc=|{u<rGLjy39ClF$6U0'
    'F5S$rr!T!2aFT9gTGi7^hp?8qC}tqvfM(dI-rx`tfF#B_cO43?#Om68#Bhg)CBt%2t&ShnYp-Lr;g}|2bfykntZAz%Qrx*-y6?kk'
    'fB2of95ZY?df1@A!^xUeH42Mx!1roYUN{#NiHMJA7)}yQpiZyb$`%GW2g4zTAo9ECh3A@6g$`k0j{0I=?-<jy!HSoLE(kqmueDAH'
    ';uh|>E(jL2gkC)tp;GI`MW=g?YNYlmhfAZz&!UCfO~6l2IFF$QFT^q?SkWEfaZUbL#`lU^E`US5$_ux$%`nUDU`h-<Dn_av4dr+n'
    'xoz0~Qt$hA#;VLO&9&#d-RCdP!prGGy~hk)5j4PGoWe5Nszx8c5GmhM$WR@OY!f3iG=eaEX_oalz`lpDLXG72c7F1??pD<tf}~Ef'
    'Ml)EwW-11Y5ydiTpeU9_Ju>?1rCSlj5gWRPmq*8BsRj4@d1a29K7wwNGz<9%c@$aOhryi++ap0P(I?G^@zRH4M(x8}SIJL(EL6WT'
    'tXH9u9zAY@o)%L%p676GZQ|gkXR9dhKQH}5b7OfSmzY5(F-<Nc{4vsm5vxufr4RaUNy4wECa&|?>@WRf5y&rNj$?I7c#>4%6GKCC'
    'guNJ_=FX>E#A*^Yf(}z&zmHYYnE4$3$C!5}PEhD9NUwAFxR_w3770!y+StYSNNnLE#Y7%H&yaTp&uI)Y;7RN01SOPmx1WH!7-g!X'
    'EB0}Lg2EyY8E#{Nixs%+2+w8|B_d}Nv7}hsf0E&fU2N1c=soEt%Y&&5wIB@J^?#J9ZIrA`2TUj8{c&-Xc9i(to+N*3B^nM?OT4c}'
    'h1v<HqhVXYeMU3aq9BP(%L#$;(mh;8!d3|LToEmNnQm6pH&V-_3yyFVBZ*MJ9gd41gy^ui37uM`>r)mv;$dFHOdyCdVJeRRvlY{Z'
    'GemaNg*V*AAIK$>=7(rSVLFDFlHh=Y22Q3_#N1XW$Hd{H>@H4!Pdo69MhM+B^jf2sI1MdbixR&?H0R!Bk_V++*qn{3Hf@*ex{W;U'
    'myqse+YMh=Tqgh+Xti-lLpJ9PC{Q8YSY3*ym^nWO38uMjBMVPq%Zo`Qm3$v2nK%cfnElq%Bs6g{gOf8s-DB$FrP1Oc)(>nk7#rjR'
    '{E(kl&;y;tB&G&pExNmGKqH<1h;bEZ=yrqV*I)dpocgMlHMFU(5JVKK19UZ7xIwkYy0)(>Mw4PZ%81hHy1iW5+Gdmpa!!M6n6M!r'
    'xzh$AQ=7sP!#7=puXk4W*X`!WrP;I*oG_#$ml`fOOruyp;AO5_9X{H6Q)%$wFMdUf==7AIZxo+G7Zi#yoixTPW199=8C*!r@y^Z5'
    'gUi#Y`b$&6$KA01zLWK^8eWmoFzW=tmY9vc+5<|1_nU`QftRbfZrwGzIKG$9)1HOS8adP;W4spzCkAiuO~T{~B^km^@XO^Np`=?M'
    'GV$g%PT_=mM~rgVJ*;6a=IXdxHKe3ML#QR(Hx91RKV(SgA;cWoc<EJ-<n>#=fE=S&!Lx&oVoqXEnRu#rD$?*cO6MuVK~G@k7w7HE'
    'c77nyZiYy4-V~FHYB`XmnKs_wJ~Ujy<x6{Me?!;~UA3K8M{_0i=Pk0SIw%N1-B!<)SO7+*2q?<^sK8-FI^0@&-BsVviQ&8Txuh`>'
    'rArv-Q9@{Ex{g6WV+bM@!46H>`X=+Gm-1itPe=x~;dHD7)wA{z_JN=nB9xdANqZfZ8Mt+TT+FIV^G0u{pB5}T>O5niSBr_bdH_OL'
    'FuZthK?bg5giom0NYA_@(7ue-X^P7?GV&7r{xH0%&%4EGV3qyjiz#DTK@%c${7G*OVU~UsD4{nvgaWOuF5Qs-az>t)bin`*5=jjF'
    '=tCmy#KsJR^*AtwhnS|x5J$YZbR*k|!!Z)O)AtSPy)ehI7yk{dX0b{_xGW{u)CiYGIXK<PWqvTty)zYHWfu`fe8mB%6M7I{0BOQz'
    'qd;mU$Bf`lJAUCV&QN=QDl^?QZQQbD0Q#C8b<`NG)_fjT*F=Hg<}zRUp+tS_^N2~5Ym*sh#z*8O5n~GT(U_FM?>@%9vD}oBm?4gt'
    '*IbH#oLIKEC+Tar|E!cYNZZb06aH8b$|4AeI4fxk=7s?<QI1w|d*L=tD*o5qtP*te5K_FgvIxFm@G;ye3=?E19d)%vAz&Mxo?pHV'
    '4!WW5mLDGLtn*=uunlW3W=W#HhBrF~O%(&|eY4n0@HroCb?L`><RL#!E1{t`hF!NWOtBL4wZu(aVD?XS+;ZLp_)cGTEUsF88w<J#'
    'z|@4;Ox_VriYzl~u|UrpI;jh4e~lFW()X~~mK`lhwm{iI&Y2xV&Odx-%&e2Kx3MX;UKUe7(a(dnv9^oLB2pg~z$Ph7-f$Olm8pWM'
    'C<~k!)d3Ql(iUH3ZPoAI8Q(9d(|n<okw;yy?TPx?Ms>PMdRbc1DSk>w!ievOxV!t!t8Z|L^KoMY;ZW8FEra&r#gou@`bgmw8x4uo'
    'Jgu^G{xS>M9{tSKtWX^iR{D~p+UF(nFEzR`TKUmr!N;zrRh!>an0fEs{mDDRgg>y&h<a!4OXh|p02^XLyrwc8D`mRwbJc8HadTi}'
    'gUAV6Q%oO**OAL+<b!8ahJwpwKLmMJ*j@dh%Qw6&2h7pAjc93#!VKIN(U~4-nZn`xBA*!!7bb4)rWGS*ZBr5uxZ{<%MS57eY*W%#'
    'S&2bxjEKT!$h2R|RWb4p%WjDj2Ea_=_gKXsAN2{3U_(;lSVMqF-Z5&R9;;T9Kdg$A9DV2&`m;;13-Wv#mXe0HIZkv>Vnh;iVOT4f'
    '-LqP={;=xC8-gY!EqDrb;ghAqOcqdrgDLCTtQ&Cv%`jqR6&L=Og*VJ_!qsIj!%22%V$y1bJ%p0cK?+KRa^nrq_5%>!Tl!dw-~5=c'
    '-yGKF&C82rK{29}Q3d2Ei<#VTtRb!eKHTDTsjK|%ji{!a_fPlHGb9V??!NuUiv9>pV2->(E)n^4D`T*|N!O?jX#|bM`K@~2%J#?g'
    'POQm5K-NtBxrT<ygpYp%%;vc#D#(4MA(CX?!clL}T-h#I_JsGZuN@spa~Y@jbm$1RU&6M(G@F@2**w9T?ZUyjbnRDgd&3ss9C+er'
    'c&Z?MudqlpNi*CM2(qUTW=t`u`rT8l>N&(7Zj^_!v9y2x?Ro!j<`=_1@o_PYVmJvwUmHI2M2tZ@1ANgD&Um8l<~UaQ4JqShX>&r^'
    '-af`Z-aW}2YAWn11Fb+x#d0T@ykTG+iWRk69uVpKocx#rdYZ2Nd=tYr|9<%MaBjv>)<Vp*ct=l=7(vM`ovy;nkUtn*k;sv~FJ%(~'
    'Z(e`o+k%Xr3?U?HrZIbUF;HQQfjy#937p|-Cq|JR1RRl^TP^t1@pm^1*1pn}q7_H-U^lH^(5W;75p7T9piNlfy2BW_#J^iNJ<F?Z'
    '@HwKla4KB=$?fS+ZoiuroKIiM7+{Rj!v2z%i1BPV4rVaQU4rWXg2Bh}&)(a__uu;zec7k=KuBG!B4_~TX$X8ID}3_^_X|TU)a+fD'
    'Q5mrJ)(MK1>!-f^>YRT6k1Ihp9OVs<RRO4mIwDMx{Tic*3&tSwry;~`iw$cXhie}G_x^uPcS}6@pWWfh3I^+9#m|>;D}(}z?c=K)'
    'yJa9=0Oa0w{dPfmTwRl7_;Pb%XAmRqAJ^rVEC}&LC~6}pWC#gEOuyn6E#8~PL5N8C`X>4Ftu;@7U18LT?J>~K<R*jW1L&qgGmbH$'
    'y(yM7w!oM-^THpOJZAZy76#qQ^lej9apqibS@;|gH+GU1R54nm@HZhy!8skbtv5=7&mY))`8rgJyxP#ywC{NW(s0vxl8y20PlEdK'
    'CME5S^*+Ctqqy=s^R|nwD7?{iDH9|^!#dObBe7s|AvWO7w%gWYkak!bI$Fi3B!+)}kkRHi%bstH=}<t*1jD*E2Eq>Sev-rP=4f>A'
    '{OQYXW^N9*JI-x;+^<9fPH-ftd==ToQYpi{!w*hKg2}@aF_i@+XvK!5W36>ggwgh9!ZGd+e^6E(92S8xq`8_`c^3*MW~t?y`l)|e'
    '@M!^(*Nm}4TsR;fC*fPdOqm)N4VM^}Ijq7BD>fl*Nu~`ezC5ln^Oc4<0y@yM4XTT_oVZ>@Yu_e#D6l0{Nj2SjtBq3_Y@;`Sli>RL'
    'pTn(d^_wih{fi7j>SHD<V5M?*x>r!W%aEE=0DH6PMXMT{uv@8_`fz2}ksukhq+3G?o`;P_%x1#tFiEaVlj)*mS1+(3Wc>P8NYztt'
    'SBl6LkZM>709xx{#>Lc*^pZu7wfOnlgxV-z|8Vm)9Kr{S!=hq@q!AuVeDPNGIg|I6#T&X=K98G!yns38-ElzkhL<ayN5kaS4d@Lo'
    'lyFAH*PwP$F@|$x=p2UkpYnSvZ=s10E^xIG5yV-Rd$=KtU!;NIlM;#-w#(eBvWtK9m$krD@{9=KIxyXco@@*ava+cUcR%9>$WAb-'
    'loppRykTzb(l=(-g(gp6+Qvw$md=_Ft}n<}<Z6}K&+i5d&Cr+W1_4I)ve-919=bKTLW%I~1i4dXOh{T;I0!h}9=IF4<bsxj_i?*v'
    '&GkD@y8xZK=xW9cgaKVl-U*aL&FX3e>0~Y-x$vgtwp?)_SA0wpTufV^+3AW`z9sqxeG^DPuTNBS6>2svcv#CkQTwQ4dHhr3gsZ<<'
    'sGcRqwfKrXO?|`wW8Y1RP8h>6$KH?=*}GfC1>+8%!-kx>36MjXFaGP|;)kd-icQNsy1o^IE5jACMem2EMJ8`lZ#Y~e{@&auM&J>C'
    '(=g6$Hm&%UJHStI-kg`lFF?aK9uSC+h@S=wSOk|cl!$X+%KfIrj-!B9NKm9wZ47H>`dndBK(k@^YFo?+nleIM9JT7*ui+HeU;nyg'
    'u3wO*X)FRuZG$uG64#+%y#QrZlm*^vFJ1HglJcKj#M7JQxIDj_hpbq|q)oK8y*X_O$HYVQ!~HJ?!dN6>9OLNL7q7ZL4ucb~fkNcO'
    '()c-mDVZ$}4_{=0YMeYY2&v4Q{h5`eHTB2+Jg>><Ikob_l_^O7q8+Bs-vzb3(Ms;f`NFt=+`c-Q;2+OHIedIs;eZ-4CekAI@s=+5'
    'U5%<juNU!8f)?llz#|{Fue=@}W}*?frj`#3*`<<9rjE0aSCRG@V`jg}?z?%uU`^}%V~sBdMQ5MI*30~A4oET61HoisQGj_0$8W+M'
    'C%JUdlWhEXr7J^jNVlRR!+|jmVO2y44I-Zs(1%|E?MB&dUpz8~jbp?jJurAu`i(GCgowp&g`4r4LipwOg<mPDx!@JU9(9He-BH-}'
    '=lSSGf)Pb9<L5F!Gv0L-#KAB%QB3=faX@_6-34#^;qg9Jel|OGWtJVopDu~fZ9&8{tSeY(eb^+r7tr9e8GsL<@9k@!Zlj~LZiS6V'
    'Ua;ukr*LlvY)Kk3)wDqnTun$sv;f1DXZzyu=eOSz_T3tHwhSylDuo8)^9~Yb$)15TWflb=|26Wuw4AoDAO4i{oxt)M+-??@=BHDL'
    'd;QZ-M{(|_Q@XG_iB)&o+H3~=>CVSlMRUp`y@#?2gE^utZ@7uufj3&#|NYzktKqzH>lL(_#ub`}V}XCv2b2h-(ec1n=GLKPa@e<A'
    'B1ad@cY^6pHu5q?{oEAd9j})MlZhv^9VF+W?~Q?1e6N}<M?6$Ubec=YVM84@h10h0M}-NqFq^Z}YU!xah-ZCgjC?bn*_N2L8En(9'
    'a2F+_nZzs1u9Xupj!h;Oeu1o~r?9wv7aEEgoRa|z=L05RUTVK0B-=cX00to#LQt)7R1n&Rpz;C}->oo@ZbCPG5JS4BEx(IbsZJxL'
    '65ihhy<Kh@y|FqbJVTy>jIV?8Zhrp!^tr!X`&m^CNe|YC(KK=YWRajJnl|pgDB*YoxQg?4Kdca3-5kO7i8=14aW^l+6A!zU4yVLb'
    'mx&7+jZZjCN@&6ujGbyg2!^{#@W9a7)`eG-xfs_GJX)udNo*HE*fejRJRxSr_fa{5OPXryf<M*F=j)Im#!feWTFb25?Iv}cV)W7w'
    'vb;KmAUUeT=9O3BA451}XfIqzqJ~z^{Q~2Hk_KOZ&vhVAs>|WsM15K7)pF)jw=_>yTuSk_)K&(x1(!YxNd}m93UpZ1(W0W*kk7n-'
    'SbttpY<=x6o_(-o2$SZp7UA}>F#3paTa9bb2SgZ?EPP`7ZHs<aAfNv#Njj65Vh-<?Fa-%aOe<miz;GU9p{eBa)NNaH1JnXt(tV5U'
    '48<8ejgiq5z9u-w1X(^>+RgOLx&3*;K%nm<+MN&MT3uBHR2`Z;#_h!fQ}ih1EYrIn$U|ZBHwRa}wdTSj-qLu}8#LeA;bG!Ni_nIs'
    'UK`5k@jBgEOmFd+<_p(dsXJ&4Vt$hoJW;R%Jmg`G-%BGxO{0;~s^hE6mc&usoxilOXc)4X*nnH%qK*b5-LT->BchSmIYtnY<icfN'
    'vzirLq>7=^oLA7)@mDYpHLQpZnchQy!dVaDuiqFRR)G<jzBxtCXdb<cP*cM2=J3;n5|%L!4FxUjH?Ouz7y=N`u%@Bwg+zl1t3mdN'
    '6o&5+{I3{xV{UM9(TZ<P?)e#VXD=RudW;n$PRnunlHhJC;*3gG*V5@3Gm~yx^jZ4Z@6XSuRHzyn*aW>S4)D@Oz^x8yGfG(8Grr)i'
    'oiAGPb{%yV;Z!L&R|ES}-03j&cWR`$EObD5VA=NVA(bo3ZepwIrLtJyk0Kqz!*X!zE;1OZA=9X0<TTUw;{A^G+siMSixn1{dIKr|'
    'NCZwqj~cojPNM({!K#iR<xi{2);%g3&L>I$J)Umpo3;34DiX3GuM-+6HC#-*j^~lRpP~KJ!b=*8!+FvptrV+_s)n#Ul`&u#iWb=v'
    'dgKsGQ;n&l>HD_6>h-Rb2RLI^P{N0sg>*Wa%z^9kbj3&-!>9TU$<u%RkN*QF<QgX'
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
