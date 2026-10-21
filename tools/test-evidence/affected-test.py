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
# 6229a7e0ac2b93927912d304835a38da2ea2e765 / tree b9311815cc4487b534cba821a1a7f7da291af0f4.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '5afa0e9ddd5c29abd1d6945a681aab57821dc3492a1559f4457672ca796fa8a6'
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
    (
    (
    (
    (
    'c-qa~TbCTiu_fsD`5Ag{9K`+7zhc&`d9M{04<N}xWvMO{*}eL|&u5WYASj_SBD2^tb50+L1l4lS2oH0!ZF_I~pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&(e4@^)ELInGnvWK)+fS-H%4'
    '?*GHfACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hmr#|JyoOONKr@5FG|C-viUh1LgtEMQYrikCXyubKUdOSWKUXD+He44(d>DR3l>#1ss#dB@*ZkgvkrPMEVwPe-Y'
    '`=Na|ltq=s>ird8((}uw=hwqa`ZTA<^f0G~>5#V8EtV!PtD?;NI-d4aO-tKm#WeI;H`m29*V$YyMcT9O)>`d2jrrKOZQsmQow{Y}'
    '>!~lhY%20$7|On}i>@BuU+e8vK6|-O>EY$mKVOIY!*ZC`xB6dye7k>t^}cK8Zpr4n?^2Z&c|MFzQdxA(P+PS~{%XqGYS-#d$6wO)'
    '@+p4%^W|lis%`3JXnZD%Q&i{E(#&n1&qX!#9&kNpDJ%14&$9n{s4gyD4`aV9Roxd&Sr2p5PIK!_6?5vFw(*wpF7prP|6F=}vYf~;'
    '-5)&V&(q=aFX`de!^89EFGIZN$3Na*)q|a?ahi&;s;YJ@s%~z);I>Y4-BoqI)G3c6cFn4fez_NZdEIJh%Tx`i?aDEm+G6gqr5ne2'
    'XvU>zm#powl&0yrb&uoaRhMCDv#G4w+}o{-tRJ$XY|F8l`qWiZyA0D%cV&Lfs!y*E7uTHfs%e^e8Tzs6T0d{-%O>l)d@R$LifSIS'
    'HZ99lYsN{wo4!6Bzoon9>G*j0S9f)lWuEMimrXNuX-fT2mqVM?MJIOE)7;Npe%-TPcknQLOV0v#x_e5)<Kf}U#cj-8RV`DK>ZTGk'
    'Q(h%;tf;DC8k?-i>#Az<%2jp!HXgs-O~;4jaC!Z9$Wzmmb<=eDuwIKzS!DIt3|&3XMP_qiPE}sLe%#CR-S59G<Hhwy=PawLxvpE6'
    'M4fpOwZJ_UZb&Dx^b|7p^KkY0PN1vu;@W9i%5JEOx%T0eLVG*qV_s&12r~^r%Uo7Xw&S-)METe7$LELi5|Qri>G=AR?&ibr<>C1J'
    'a+oeho3fwAK|s&zsZN#GFS@6})tS{z?Fi0eF-TeZtGDqwKVDq8=-MWaEFrZ%__>d#ZzryhWiEUO%jhIZ8g?&yI(X;R*TgK2;7j`b'
    '<#GV3ee7)-in1=dvP`k5x=-!sVyTNhO?f6hG~40!evlWw9KRi=Pr}}Bhi5mc5AgHwIv-x{&Np7%vKPO|x=uqi7sHrRxrm1IT=jib'
    'brBQurjD24$+S1`X8kJT<G3GQ<&u}9RNIu(T+DJd@1vQAQQYji!lgL3Wwzvb$|PIa?VEX(PF{|b^EBk$R5UV=+HW7~sc2mdJ`?F)'
    '-N`8Dsw`4|^B#UpPY>z-ZhcD^chVQ52Qs&fEMP3#MGmx#bJ5hfd~9iwyv+G6mYa9-ZFrDw&v$ZsNBQZGyRV1m$W<=xDvOJ&S*mW#'
    '(j<(usdkyUMdb>4X@^-`c}lnM>Nxrj{k9Rznkg!msUAhkYAo8;=^aX$@6?qFfLR=C;-B8Wi^p^2G2E|T_0urDTn=pATy;fTNlJ@F'
    'irQy&T}t4(p(z~eqRRSN#ya*lZ%IzI+#kMtec2sro3>nJRM}9~qpKzP&hsvBJMkwT&|GF}wxu0Eu%)eZ%LAyDnpxYIS=kg_UPRW_'
    'Mt)uN-d@&~U03c%Y2Vv|v||?R4!`-Z@4i2x%UOW4qL%0v^_yo<c5Nr_kB#8FjH=`%pTwW+_Q&%4;=8(hSo+BAW9d;nHBBy|rFU*8'
    '52{s8s$I*z{=irCGCX}ryKjL-!kZ1#Ec;j*XC(Qs^Qx^Kk~W@DBR}Y~bo*O6Wvg#j!FYUqn1_u(<Cydgj`ZAX$zT^lGyC7VnW`cm'
    'n<^V}bwZW?rakSrp31bScl)vF%c@NMTu<4!%zzaqxtks1h&a=deQ-zX9d)-W3{JKDy~tgdF2=4%!!W0@bFx)ALs^z}JucF$55Bkb'
    '@Y~_(`0&kt@bu~~mvu$pJUyJL9LKSq8dt<PG)Y;VhHfl8GdKENer!*>Z_#e3+M!fcw9S}07|mR%ZY5yK%Teyz_~7lR`unzXcaQ{r'
    'Io%!`ncz5f4%FNhQzj6PUe?$*Q{TBPN_X0rmcn*FwzZpX`LP9PNr;{CrEilgWQsbm>x+Dni&RTh4s$>KO<S9e-&UMt>wz`Pkjh>n'
    'U-h{_8Sk@`Gz;H$+syg6xM#a^{(E-yoPJ9W8&$QEwTB3Kfr>~0AoIMsEO&hrW$NH_r9eJ>Y(Kjqf%LHI%YYc>wDeQo3~t;ZYkd3@'
    'KsIl@&|I1O!L9s|6@5GGIpaNyc?f`^Or@Huou{@Q`+OWg26k5#L(1o&T0XX~>r*4|ZICm<LF%y#m}|-45P4Hnj(Agcg&kJeGJbSl'
    '@}s-y36A*iav1KPH_!nkS5*}*+O8j^ZOh_eMNW{9lHI(VMyb=>e|S%OQi9Uu@8I|!Xwi_vSruLtNFQ=jc8vlxAKJMnKDL<~vNt*8'
    'xa3XVG`=up^H49ce^`H&ry+Oc6z;*im_D|#=i}=WP-{AVO>pb!ayDl@y$8|BlL?e9%>j*<RUah)(0umLCJ@sHw-j0B-Hs9#!X#e<'
    '_7!cdGFwLXOaXP7%c4$jPvNP{y1e>3wzCX}`_~Pix2w7-4XGZosvaf{lU8o4F_WgkW17mc>orjF51#9nZ;#92K7Fs&E`R>5OTQ@x'
    ')fqTQ#B9Ja9?K}-%>t6u*(vJggQxrD>Gk==P4a8{<7o>T_07vKec#oXa%WmQC(~|`=Z;W+SKU(0UHV8xaK&aK%huy)VWLH^?UM!_'
    'B^|G7%zR<fSe11Ti`aMlpF!&LKe>Ec%q29?v4D=YwfjOrpUGtFe5@t1FxtACx^7>F{pEEHcj@Wd;rV&(Azn<z#=h5&h(^cKrE!L7'
    'XqGAy$7*P+)J@qii#hv#^4DX${o`>f;Kv26p6G_Yt)@y_wh-FX=bamT&hi-?=QG*2<|%Et96IxUDtvgQ_QxDq6yQ7M04}h};?9}#'
    '(jMl0`O|~T|F?8E%-;@|ZxWpi$%putk44kyen2JWMZ+>L{l5~xRVf&D76j*2_kf96<`P$yMS;{#Y1019D_=YmB;cb-xh4$kJ4-))'
    'NxO55smxO`D)QBbQMKv-X`^agYHD_6R?K4$gx^^&{@Cx?^C`8n+M+7wxrFl9Z50K6(jG6OIqX=grPXG0d&T0X!gM-5rMq8Tj}Pf`'
    '4H2PLFw^I#w2#}SX`#%07L|Li8P%v$hiTb~(fzoCZ^z%#T8z4aHm<@PF4-2vl8s$C1dJ=Kk#xr02p8*B?XAW`KkVPbbx~!SJn^jb'
    'S!Y^brAAjh=1Zx2?n_H9poA(g_2d5acZQaHUeu1=5VbZOrR{uifw=j^J0D`z3Gedma{t1o__E`ftAV_C&D_HERph?HPA)x`nyZBy'
    '7eEX;(f_=5=|4-@%Xf%Ib|&o^q^^O5w1v#R^WXvcnb)1eNhD;;?aQCLebeLX<>%nL%crjJr`|eRh&sbf)<B8fbNUHgtI^Wmu#tW1'
    'mrJe5nalb#J0)MT)W!Eu7XF|cpbJeg&e`=xK*GLqIeZGk(`77Z9NnZvbXnahlaN=}_B5rUb_kQ;*vT~JdAxZG`<_JW`CBj3^d686'
    '&?yFN0}p>tA161v<f@iu+^~&5UcMe5_5qr4_!S929p8ic2}LN?ttLtZSkYrr9eZBY4G-ffeSzsHROY*XJq?eKTUpjLX3F2ip%4lJ'
    '19Lf!^`IxLB2T&6Kx7zhI2eGX%T3q@wMI{G1Z_`q6|F_k;G)}Bj1eM(p;l{?O#7GKpAhuz&<|yhOBT(DG-qz43c6KE4(58)Wef_;'
    'a>adgQ&ynAP-}WOp1+?wV#VopPD4O}gPq{cO;c0usD@6z{L|s#@%81iw|;+SReh4-fBILFc!SkcL>G6XR~J>Px4xdgNoKE91g!-i'
    '0`6WsmZIK~CH-YLR{xadAU^%Lu_!(6hL?DB+rZJFN|dIlK?)qC!Ks*hy~>gnKT7H5_H=4@fTQniY>TwB_yQt-@>q(%8eE|>KAP&I'
    ')%vW*X%WD>9h8~%vVJ2sUS3kF=4?iGs@W?dL<f9Si?yj6!PWJEC(;hf&L!WVv51v--ox<p?f7)}>OZ%UwbX?V!5yjN0uP&-Dat=k'
    'D@I<PFKA-9VpJI4yN^@l`RUA+`274d{eMj!+1}XyYjl$Lw{qf?M1i$tnj3hg^tS6}-IqMaJ*}i%Lj%tMl>2@?n*rsw?LM%bHvnPX'
    '*5$0X8ruSuaGJzaA=US*=BV%|7U{5kNIn;YqZ>D~k~mMN8<})?-hF)L#`h`>Oa&;aNN(fcc6w`S?_ox?OtQpg2mNYuU*qfHem>zp'
    'djVIGtwRJVh8_b*k1Cr5fwpY}0fCWex0J!p%s;-lGiLY0W82`N`0V0&2?-OvCZsNlZm=c;Mov=%;~`Id_3@1zw1J-9Uh0{2ei>QN'
    'rz)`LI^FUdFK5o9+kpcvrKno`LWJ|Y>;HzGJ-D;(H9dwWt-i~rEQ!z~ELzuEss}q4J+=8kN+W8FnpfKxX}bRSu1-mh81X}g_VT4V'
    '4oF@taM8QV1ghBwIrom56NhaJ6@dD8<HxslP3)TG8P2|gk3TPd7oDa*f>VT24dm#0sMm(S;j=ua>xXY^CHp!)ejT1S*wILnjWBO}'
    'lR7rg1R2r*Fh&4S;<|9OAExndIAf=)a2I^t>T`+`u$`#@Ahz8KnJ#IZGD3$SsTCevmOj3z=fjtk9dRH9QTgupC~Lr?%TUn=(5`^E'
    '-7<Eak3s8dlIVJ1@YVFcVQ*`uv!m_aC7Ob0uOYwo&Yo&mMU-HnwGt5<DWTrif5S)cCIq;=okjl`3lt<PwE+!vV4<c!_?MCA0Z8kY'
    'x)E;N&f6Y7Uw2jN_ghr&ubjt#t2#FmjxwSI>edLgfZFEm&2RDhuGWikgLM<o6>_%wa1f^|pQ6MYjs@2p31J8o5Su^ze9j^MGNe-$'
    'g<{E-<3dJ-fUx4Ti18o<Q5~(khjv!=NB6ShGb=D^g4BnS(Lx#Vc6HiE`7m_@baNVHqx#wHhqrRBAO8BWZA5@9%B7{%IT=O}ds${J'
    'B@NOl4AcvYjtT($qg%UTOF%(@kEn>RRY|DEAg#*(@`8?O&ePZiJf2;sCg;Ob2#C%*OGSEXMXZ4AFuiPJ!HaIrl1;jyO51MgBcJLs'
    '2t-rD#Np)1nxQSP*~3;5t4dRZ6kXja4-^Cxd1Y{!wUuU43<YJI)5Y!n-8&mi`n?%7L$&C|qYITpC%qaT*+R;OK%MJC<o(YMr|WNc'
    'Shi4$RA}%caSc%v>-|F${V<{>>NGhHI#uIE|BS&oA1AfAEOWU3e21$4gGB2t{@F&q&aw`0iRl~nSsLM2HARWjRS}E@Q@m`4ba~mJ'
    '9A3s``guV+*B9uLM2M;qgI2{ohIYl7DFr;etn%_Qr-Wzy>y2J-UygOaEaOtQO@T5<3q^OP8Q87SKM~E$KlxDsf2D^&#Xk>EF9*sg'
    'iSo*HdD-BQ%g$%aJ7}=0gd8W!C%vLN(&C_17NNn@F1xtodQv3j{(h6rmPak1p^xx8;YelptaAo(Ym&mfn`-(-G2mx+?0+nHB8FT('
    'Cqp26b(vwQ0eo9+#s&e(i7$KAKz*u<r;XqDJRZN@{pQx5w^JH0X0N8MecHeg7(eP4tY#Syt+5PchVwZ0KWko}vXwdgc8IsAzI%L$'
    ')%PTNS%?$RNCL3*!KYZPqv}%TyCg^a_iWbm9JUsnhsT%D&a4sUKUVbg{(P>UTIMz4Ms-l!anNPbzlJ3Uqivhd9pn_decy`D-&NI*'
    'ih}Qdd^xZc(NUeU&e7G=AlgA*0iox1&|&~*8Y|^E4L9!K@$vBb?QYLTreJI9CZ%?5<Cclsm`b&d<Sb%6S}+R3P+z%`T@L|YrqNy-'
    '#oH=~qAf6>K#q`q3`H|e-9YU?YIyD1)A8Q@ay+H*XWHZT*(Zh$l!=<HAAQ<xm_qXcydF$Gf)qXGPL@AkyPFj-zWb6i+_zeeh+Zhh'
    'z6ITUVXcaM45OjyQnU0`3rU8-smgY5VLb=C-UUj*jBd6FXhAirD`cyMMyH7OKg`H`fN2%G-^Kqw-hs}=w~Zx{Y&&TMMq)-@>vzr('
    '09&C}J6%=WVi#z=mV1|+)AO&oS9izh_5Setu4fNcjivRiKqrlq2aQK5u5;2?=;gRf2u!k*8@KS~@%8R2e&l_6-hegr6lcXFqX+F0'
    '&HlV9B_<%9GJ0zTj-9uWvcF*;NYSo$RQC;@krs`pfH;Oj+AK@7{pKi{f{Rd*lT+7}W&ZbUXa$&dG@}CyuS2&{PD}VCxUm!^RLG<X'
    'DPCa;-c{M$xGNX;6K2Ho;a7kA_IDQ(FI5m~N?*x=7z->wrdCImB6IF^yXKHZYatXj?&pL+41e4UXi+1j!+TfkUm?{D@mF?~ElpiV'
    'cfLj;No+i-$lqHn`@Br`t)JD^`^gKI2uwB_C4aA$z@nj&@XTg4xR5$YzRRDwiu`;(-;UF-yFTuriyn@my5;qNtAoGeN(&)>Xrh*2'
    'Ey(<rY45`4YH>U~%v<bBm1-!%1hXlpOLs<*KoOSaCa|+ya3w;Wn%&>?<6$~hpO?e$FM;~6;OFJI7MdLiojgMCG0Nhg3rHse^?)3!'
    'L1Z0mcisAbQl@raE6VgC=%$)SSYy$rRxej2DiJP`-e?=_K0w)Z8+i(=m8boiAY)Prg^iAa7DP9Uz|}CjA&DW9$vXm6z{}oE_-_rO'
    '#uayb6)DvmDr6v7KcW!1RHdKJCt1aka0#YCNqXZBPWjI6=MjnyRc^psM8Jx8eQ?APIWcz@Vz{zGYU!%ocl~cie|xuD8b!6b5uKz}'
    'neJUF0*pan%Od5ssIY`iN`Vus!tJ%koeTCpeuoZStD)^fAc3ucL+gqxYn&1+)P+HDv$Y_>%pd<F?UG*UxkDM^gLhqd(Mum1rvm2C'
    'xZ!1bIrLipVQa}%iuP8QZ|H>kP*C)G#Cg*1ud;+O#S<XRoH`9$|2APLZ3UctI%%CJxKj>r$E_%$W3Boo0+O{%@b~(p-JYtwi><%('
    'cy0&BU*4Vm6EcJQ9c|YDO&#4?#m)w!MSMZ(D3$9TK5ml3Rv>)L*)7{SJVfIc=VE;2yY+PU_&UCEVJ`1U$andMsZ$Nm<!2=T>D+Z)'
    'OLaqE3C0_7^FOqwP`A-brF+-X7ITehNoWxo@B-)#EH$BX^9iE92h)^wu-CAQKeV48+BedJCA}QJUB0H=ff(%cBg$Ut;JB?w0DT=g'
    'zCNJPn8|<V;g((9dpf$kX)82)3t2Sjr(Au<$j5`qv4j*MT5%z`16aUA@>}-sZEXi?No?(*fMY>lAUpsj=_5SPh3(ALee6dpM*AJ-'
    'TlNt4KKAf5?|2r;%~XcsiR+n@0&WjWwka$TNEzmaoB<#)wYTg;Yc#6y$5%c0U57)>-K&Ht4Sd=thM0{~e$F0tq+Qf4acedGO^0Iz'
    'Ywk|>*6GW>{C+ZbbE6)Vy<%^T0g{1oah6a5FaW1GHR-mm2R46v0sx$M^UrVh8>BkP40#CxqWgp)kb0-$|D{SpS`zZzri%9YZ`exw'
    '*=5Xt#R^ZehL=ik%J>m^EMg2|EarHd`oOunxw(BW!ODCd9F`6ACQwZ1cOIG)q7c}YHwC_x&&X&xz9#4;Dc!P>=i%EUP1<wtgHNsf'
    'E#khvfhVf4cpUUo8VlL}qT<m)8*8LMjB1A_-4y#@LYY4Ar~s;{IlxA(o_OnM=&$HQ41feo-3rP9p@#vEw`}5cJf?ev*yTOokA+NR'
    'h8;O31aKkXZy~=RAI);$I^JEo|FfCC4li#qn&D;hTM3>pBs)0Dy30~+xC)@#&4P^T`z2jgw2%A4*>{u2vvm{*_v;2ifRF&-O8Px5'
    'zE!jhv@5X}NLtu5c^m<$bo+zYi3EGPU5;a@B{frns5U%qBuS{BXxq|HE%$orbZU5BNR6U_DyFK*OA7ei8;KY`{W0CAbKW*hzL3b@'
    'UcRnw0QYITE(;wpN<xzfT`oKQL?9@#K-@k^9D0F}fqeLz_O!#;3u%Op9ua;x8w#_e{}b4&ia+gD&;TC{!|rd{(0t&!_p-rwFG$!Y'
    'y)=#9F>Jn?AX-g}@PR$#XklF~QO5l(J9<k0eBFxq$jotcL^yt4Odcbt<Ot-0s-k_{k=zo-RP9GMbbtJEc-V!tG}>gYz!VoWt4k*v'
    'T3yNhgDuOR(hXS!=jEe2f_^-QM&n^hyABg{BM{uRkEmPfjrDn>P|-siXGuf|nB7Vreo`8a-&NCFd-8s~9W{xTQ!5baGU@mP@iL1H'
    '55ISjQl$B#dwNbUZmKV^-G|}v`Rj3GS46uNt{`Mrzq1KPm3WJ@T(b&>#T*226z#ulSFexv$Kf*6yaWobfM+F&&C3TwDT0`@AU^9v'
    '2U3sFR5is%_w;i7H9eeZvzL=C7;dm)C-uru%f<;0MI&?^@~6HecrRjm<INkI=chp9pHhnd#KR^>(6yy(q<%qpf#%_zc4247ECi>q'
    's|r^v+RCll@eiU=argD*<#AVF5)$=Ii<MWwt3fcRus#tI+%GtmT&Nn}t$Fj&4Lwg!hsQlvzpmEUunUDm)apwbRmmR^mRG3qn>$FT'
    'NR^x)*w8l3RF5PN2Lcu4%tKqcqr%SFBamqEjdZyXQPtzkAN+j$Hi*;f_3@|I_vLt<JEsF>3>I$WL@P#4Sc!Xs{wiT&GZDs4AKcRY'
    'A*8lD&^l#GS0$?EQTU^ffnv>&VMc0QAyw=`%_AaJf5(1QHR-Tr1QZT-a}CRLLC8c%+pw?VLt`R?U{*v!Q0p}N;D$oZ#9wY#geLC8'
    'ltA#weA6&n<ra7o-v?1X+|y=RHLRk%bxSA4(f4oc2gTXtS67Ei8DDcwW%D47rU`AMZ?DMVy)lw`sZO)MYg_T}sEj)-S*0XiTR2(q'
    'aKcQ+TAW%)AYZV~+l5S0a+lrTw6A5`-X@%)6U0$;3@uTGs~l$cGH*m2u@V~D($aizLvgF_u(D>%65(jUdWD8M(4BTfAH6tbDtZo5'
    'QnZKi5ANo~a(wd9y<k9YDl4#D5e}sq6(uX30O?g8yl&MZhq<s$;&6d!`oUeD?~m7qoexXL7A`Blb+->n*qXYj!xIUd2Lz9y4^CiH'
    'dh52n9AA#XDVK1c_qLI3BeI9!H5Js?Rj?cpDiJ6~1%TFKiztUNdUNy+WFh#t0b5@F#zx*7GJc_1qcy0N8mlfhpPHfxn5@02@x9!-'
    'k^AGk+F6~<qb?&pRXCB;>Y<SIs|LWOfmWv`()Nb!vcHMQ{eitiF?4=O=kUGjDgis>foUsVQ8mr+C<BozG$OpJ@F!~(Nve~NZEO`$'
    '&+C^q9XDGMk)TNr5hnQA_9(zp5X&*{hzb>P(F$F`p<DNKhDH8-Oxs&B1VaUzw?jzcpd<_zmZ0wH%R0(pWE|@J_5#GJ?Do#@ZzniX'
    'NnyiuBw#zu3C{MMn%kh-lHX&dq51~d{N}Xe;TVmhK=bI|J+UpuZ|*+B`=5fVm{y@ea0*fw7Ea)rJmgHgaBi+Yj%yBiDu-}pUpJy6'
    'MGYecMAAHr$wX=V@jxJ=@t9&t!vuUxH{Y<J#W>b#ej$4wQUkIY!YVoR-y#8b98LfD1B$(g2UO*dwQ2dtj?UH)cQ0SVb?@?am;q<e'
    'r?9MKF<jDm>+AYqnnuqHJBFh1=G5q1lBt74M})&|(m`l*ee2lwFsoj|O~K&kkb4)p2Ze01)zrB89$RnHdEebpxY@M@n6+`tm%qvt'
    'fz(>^y4kF?biSCKkiFc#m-UV(?b!RZ6D3x1eD6k8SWU1G{^LX+Dr;I#9Sr%0c^}OOcl6u09R?ra9RhVR_{o4CICUq7#?)>`w$d?f'
    'WtLbE)6IF%Z(Ss=zXh7MmEM<Gu!s79tjidCVd*aHA>CO~UGtY#CiTMyc9MP%zI-&SciWCyyl?w3co^}9X5^Bn4h`LLv-*z`Doo7o'
    'KC-F9`gGFX$JFQK+f%qABi5j{ga;nR6^pnk3}Rp)VaQVUAKTG!M?GfTPh@4m+%<`0#-Gg<(j^r^7!~20M?`FIhdg5^FM%-}pEf9m'
    'RV3?WxH`1R+q^T$9>wRB<gG<ihD%5QKd_H88F1Rt8=~1^7V{~C;j;{4;X7&mu#YR}Fh%jnQ__y<BU|}?Pl<pVdCsI_W=sj;fbx>D'
    'G#S$zzLf%@Q=+POoBPE7j?HX$2LWKA7NS@8Rkwk_Xjf9Lf`5Pv^nHmZNE$z|nUEK5Xs3j-kiUex9$UY<470r{Cc#OSv124)0}q06'
    '`p7O`!maZzNL-s(lyW#)qMFsxDG90l=o$-m5W65sg3MGrABnx+bBKf!LgT+-_QYR<)t<3hxahrxp=aW)X{uC}Oh<tBN6XD=)}OiO'
    '-P+jP5b|@urbh(5BbUKWy{MS`q-~+(bdrHS;ZA?cCF#M0W&)OS;@ED8-?ZMi4^}Z0aSSguOk?<yE7G@&rvq`8VeQYY9`9N4ycry<'
    'f4$k;mPrm_PBF`yK$lvBb$FwVDym*$mqkO2h4FsM13u|V0{hqg#2bjR+n@!<TO$ec4w_Q6SeM{TEGBd~7A-Wog+@bt1zhpYzSa_9'
    '_pZp`r+8Vcfw@PL66@@;@?Z^Hgpr+wbMFDR)y=y)H&6ENM=A`W9LW}R2I4!{e8Wt@(I>2QNoi&n^p)o~@8?Gr<=#z6`eNK@R8J_%'
    'x(4Af7}E6k=yk)O_Uvq~NVk5vsrYC6_q4XYaRA7>(Z?mGfJ2y97NL<uU8K%}TAtmyr|D^U{>m2e;rKFa>%YNDxHEldC|GvDPm##O'
    '{&mI<Q!gOkD)@>k_;LTXn=@vye>jjg7K2L7e>43r!hkH)kW2Y`!^<3^St+(|jsbs#opx?2Y=vg*34%Jj|Cp4<5<fFb39Xxzs7#q8'
    'd6?&qZ7Qna-FAI^R?6jM8YnpqV{l{oSo&m&<Th~d&<&N%tvmXTr0m`hW7lGw2v6%2_iBuB$_z-83z8sW68h(|<eT4HJe=WKxBH6t'
    'sNOAPhic(E{0v$Qbyq4XY{^&=yQ7JFrN4DY=kilN_4*}-1#Cd^P$pb<v#-Lvgar+9@)DzX%V>Nxsx1;LLdoXC+c~v!j{C1Sy|-}P'
    'beP~yOI&kiO@?+-wF4@I*(F?*F@11nYj0rho?_Nu9SSeKIYI{+nbr!*f@-u1KwKu-wLcx#bJd=nzrMai!nprF0i6m+dDyk0c9mR~'
    'G<)2<h(lCRiVd0%#p~{Uoj0-`?dP|MIlZn%(l2-mQn<tA<izcjz%1$@gUqbWH5A>1@K)a$_);z59oP3C+0k+QMbe~76*h5;ALb1s'
    'j4)K9bEQXP&X4;Req%y8JZugPEb+0s<(h=)CwuzKA8n?VCW?AfU6|N&GGdScY2mblFUhE8b^G-cQCRoyD6#!cpQ05nm;Cqq@-iBw'
    '0z#q8fC{1Gk&i495+Gw8@OzBwk9EgSEmz*#%(>rvelq93JJ<7<w-Wlf#a(6|m8o+<AvFTDV#*=`!NAdfMy<Vq?)=VHHdB8W1cU{%'
    'I&?njWFx*cQ4#Zl1zv>D8peLL|GRn_MiAwhV7&fykb9pun5{8Bg4d#_(S$P|8XiP!2|@saFdQIl<(Q`QkzH&(2@%B{f^eI2G>Pj{'
    'j7uwGPzi%bX0ND;d~&k=Y4qu6J{;l$rl*6x-4B1Pr0WfhS@4Ks05?OqIw-v=<_7MBoS=jTyw_^?E67l%eUS1EPiL#UlZs@kJ|_1<'
    'z>FvY&{)C|2BwVwrMZtkhwh!3BDGw%4c6RuPeWvZcVFV)xBBQ|dP`9=N2<)MiBJM@ZOH<!H8enf#+Yi^Pj~$;{P)irR&3!d(#Bi>'
    'oL#^LX2=*YMIToU{w&$APQ%bN*DZc}1#t{^y$7rcI3p7}q(#;yyh*jAu)y&cIjDy=*AT+$3VqyJW)=FGb4|Cc<w1%iG-ig4{W_YK'
    'iRrB^K1p2Ex&9RU9f7bOuiL~K_Ix`C8xC{|?G(sw7(E*uvIH$p!Od4D=vF{!+=0Bi@;vH0aeCS(4a{RY%B&TKa>p}E9g9F+Mw6HK'
    'jCa&hqZ=5OuG;}Z$*@kG+|LgnHbw>%nthRBsHpeuZYNR^Cu6__WB;F;&RyKbDoNRvf{c0S54czm>NIgpARw!$1#cKgX~YNb%Xz7<'
    'd=2Li{lg>JWueB)A`5M37n5}(JQ~rq3d>*~D4W5L#zh*hd?R{Vqfi-N=*IFi;HdnpzoNnd(g8Zm{L-PFf>Pr)WqQG_>$>G%4>G-%'
    'myN?n%jVbdjF0;g45nX{(}QxZKw$||?-YPtIbXf@^S=&T-RYQ+8zfL=K`3L{Lj+?trZTDYn2mtG^Uy-?UOU|BPqe0QVO<h)3(~m9'
    'bE;ypRA9aax-NkMa96rBLvS7eLoB!Rn4wS?AKb~NHpnD3CIDT5fg2v=oOEL%EXt6vQLFbBCD~Gq*KZ?MKXbiyQY#Gk=_#bB8)L#V'
    '$cFQs`yz}I!UC)ed>Qg|#mfmv(5K*W|M8bpf=^x&y;g{MlMl!5&-c;ArsDr(G;>T6L)8^XeKmMal)6oI`>uXD9#&n&s`0p6?uRcM'
    'w#?Cb)*=t~&>TvEa7&7dKBp3vdxag0Ay~!jJ38q?u|1TzU$&;?u+&>(urilFAq%p^Q)~$ZOpv~H)nX=tvG4uu+re5qQV^ftp4kh_'
    '6KcZ-l%t~;E_r1cIukx(x_d4=bJ)5Vmk}z~nm5T-!IT1EUq>|!+E>4CjEUl1QAPkQ$%9%RE8Yk)hckno15L_e#%i$zi>BYziEA%@'
    'mjz)cvjb;bJI*W*c}xqiSv#!Rwq*ra=tsGGRiDL1HsLFr$0?5qNOLF{%do)DgBRs4^_41_`Sx#>>gN{IzZrFL>-=@g&}Ip0Y@`yL'
    '51|C8m<3;n*$_>_0_+SktkItGo$H^_<_&|un69d^1%&GXBjIkZp5YBON2kJLC$UP|vUA0=Lf}nJyQkM?8iI_#B}He#ERfc$Y$AK4'
    'JBzN(RIL4`&0P9z2gfI}4XEGd)Uh@O3n-{#UUJOdq@KimuUDZ07a`-QjKJN@*uF3OuT#2slqPN2mGhv}(KLF(qyU{)PIP0i?Sna>'
    'vzR1oM&4q+?p&H9gD>gNM;}bh<K>sm`Jf9TRE+zcLJCoa2_B^gtP|4&I;E(duiL;X<k=W@h3bSG!KY=2fgk~-R^d7~heu(K9bhPW'
    'k?not>%`>^A}SrDax4a0fdK_6zMC<0OdrJ-YN8NRUpGY!hhre75vYHEobFy;AGW;JLUrTLg4QCIlX0aO(n%w2J8a8i#1wVVv?+Uy'
    'bys99p6>QIIT?PvN+d!VvBXFU`6#q%3aL7}5cAuZUX<-w^^b>%=wKGQcG}YfpAG?V!j4jrbum%fdRkZUF)NE&w%di|c*o*rKh={x'
    '!QHm`xEsigpwBbJ#OflDF%(~)kPcqHpaE*dgivG8(m>tikL!N9Rq8-bGZT+o9^k1(lE?Sl+%D?R_4PN^roG57>ET!Q=AW@@;4rR@'
    '4WB$SGmNl^IZ)_FDF)F_k>T?pKyaDO(DWg1N}AplJ<SP^k&$C?(w4)Qjk3RvsXE|5)N+^)k%t^W`Vpyigidk>mK)Q~)!*#P-)2lp'
    'g}$VXr_OtSb#<h6T^})BFf@#Bb{+1HP&)CGTCm@_g_X#8xM*w(kmYNSV2^Y>1ffeLqs~xO;NK-DFN@-2Q-1ii;<?qi>t%Ch)aW5n'
    'i_y?9KF>P^tbrQCc8KL3Ytx^)Kfk~7m2W(!eUNbixCjfDbu21YubX11BU5P>yg<$^-8Ea-@ysbJxEeUfY0WWR8FWqxfMBn(sH)8H'
    'p2F{MW7%)Ui4D8W(^QIHt!uI3Pv9>&85Z<ZG9sO>u<F!9T{KO%7Cp|dVJq_b_*3QYk3X{)Go*MjE!J^*XJ!B|!NrPX5Mdg}GG<M0'
    'R?MdrpI3|M=UsIvV@=JdBJeVe24fL&Jf7Bj#-%|nGEzEvvhBEc;m1(&8qu(!bk;Nora&KkjV4@&kR)XS4suM?ATA>G8S+h*#rI{`'
    'PWYzan|}?|Ue5q|NwlO;3$#u$qJn9MfF{Vl(<UeU`>HG1WtU$JdpI2ZHid?XB4%mBi5YtpL6W_LHUb+~-eL95m7}aUY;&ud@JH}R'
    'Jx(FYN+HvWbco4s_+t8mx&G#Pzjx7<NAo7Op>7K~(B?CjeW}%Cb}YbfF3sV<o}<{N=2TR-TpQGo`6iL>Z4+nujM{NaVOs_8=az)M'
    '60i_!>YQueH_^*C=s149VzRz&-4%~jEI)3jdpj)|951$uUBvFN26Did#kL`a3YQoO+Prh^H&vmO?DDcMLL-M_a;cuBUmv`a(5jF)'
    '8plVMkrRf^-Ogo~`#&}uv&=n&X~WnBWayq8r(vnA{V(YqsZfb?VFf#vJIt#E)9~xXK)C?awee$Ub{2Sq9!nP`Y6sZ$w1=>pl>+WP'
    'PN#;;LwZ#%Ue4&@>CiARruMIjncrXdB~x!3lZ`v0q>y6w!`_8|dHr_z4Ao(47_+ab)br3H@S7y)Z6dD?14dqCF~6nRx!!3A+1>Lu'
    '2*kw)tcx>*^fUC1B}1piJm5aWO;X|<6c=$r3b5>5_l<tL{c3Y0y8r?hSqhd85oHXlMFk^525p^HyBQbL)hq9eR6bdq6Rd;eM^{pe'
    'Fe)vzzl}7)v?b@JYFsw`u)nW=JpQ`T$6TAWE_hb-edupSqG`SwY-%yXg7a&%N3}Of#Ju$lMU;;w9FhsLU3|o9eD>S`;Bb*b3adKD'
    'yRP=G_j><wSm%^pE(?ub3J=<#<%NJ3tky>hKjv=&;~6(=*A%<Y)7#+BWw87{<tIQ}XiDJ=9guR2g2E&)ONGlGZ!Q>wsu}FFa|b^-'
    'B=1_@I3wu|FCK(nZmQu&8wegS&+V52h0zl;iDBpRXJ2H_>h~{SH_(6(d+?;?s7NQHE6FNJeJVcd!*SiO5!p#qb}sxpftNNwC78Xt'
    'c1FUS!V8t>Wfic4@&E%%g&JYAEw5S7Gv54g@eZQHg}um7-?yXHW_Z&O-u}WCNgbTcb=dD-H<(ngyd3~F*f7+(%3)A+8wf-=4U1qL'
    'D#)Oyu`N9|d!zJs_o5$+s4o9>YKW<6W0r?c*-0kUhmM0zopDE<Ge$VU?!ALgm@Sa}4?M?TH!^s^kY8DFvp^3quS!m7Uil)(*iP^!'
    '`9JK<rO*ACHNQ$5vezmM1?3)1IR0r^slCI_btPyL5sIP;#<aI&IW@U2|5neGJ?O%9$V4PHXW-Pva7qC@+{iZoKy@=;wc;Jl%*Fc<'
    '0?SvCgLzEnHL}8GVR=m1A}W7odX2^%dD(TVo-&@p^Kpls*N`CUZ$GgJ=~Nqxp6CnoDkzspWG1fWq1^quS(lyGznuASzf%HoDI@*#'
    'L9JiaD&U~+)3|lSP0yV6hLP9D6-s=43_{CBM*uO~V`WbqPJEJ_+Lx_X(Eo@Y2_$ui*s}MgIC*I9D;a#H=6aQAWNUUgBSSOVn1jv|'
    'ZbhZRcbqKyz2(ZuFfxoppN1Xo+NL7~i`Y4iSpq9j+}+&7Y?2UR<SQ+6-pUN90v~>VI=$h~cmAEV`P~L-rVs9(b~C+V(?T1Vxw7$U'
    'V<bzIOKKSE!Tg$q-zHU^M~+-RYIRt3^QCiB;h+1tkbv+ysA7;s730Ch@uIkD{j*d5KI{50$@1hwe1}P<!`YhA6V%r{ri;qUCi?7r'
    ')2;6>J2)c}_u*y!#QFtVu;J0k_ogE*(-2{OhbN6l6-OeE(LI>L5Vx_}<R<)O54#rjn6>xE0NZG5^qf$&eAv-q)g$5<6gJ1@R9(Gr'
    '{HHglA&fQPnKBkEMkO*6Qjo6p6lnwtpdc8Ui?elyoaV>uI%;8^W7_WmDD^2hafC!<sOp{6hv#;K{T$TwjTIjckAx^&iI~zUFqbi='
    'MpiMPU@iX*$B>tdsEW}>-nKdV+1Sb-FR0*+P$g)ZRzq0^J7W%$M;&w3unZf337Xz)0t5<t<zzxoaPYD*ouGwS7-0r9#U~qcC4#h!'
    '`ZaETG$-$d^;=nq0jGY`hOP%H$%<R8DC_j=jiWdFK@7uv6rzFjB4xhmH~g$c{cZR@knz*o&;D-vw|i(JZTAos2{GEMim|p(5Kc0M'
    'iI6dZpq|ND#%(t2o(=68sz|}ip_PD6HBU{{#?S_JpR^dB%%3F26X44fAKK2oLoyl`WhOH*8V*S`_aSbydwIxGN}Gy1rrgw7U*5?&'
    '{_$}*Y|JCfXOqS>`lApnA`++#aJZA1o#x{N6%F@m(>Lb475IA8zI%Lg4IVW2fD1H_T0<UPCIn4cAPi$@tI(Fkp?aA1E&LLdFR{I$'
    '6!8=`OA~G1F?@oD5dCXOcOm*G(KDIF(d<LoFt@wcUM0Avt35qEt)nP33%4vx*<d3KjR-aDRf60Rs%hqGs$dTs@GR+~hP`4FS5laI'
    'AT#@cm^Z073$&XxR~D5^9S}6W8`IA1c?&=8;Fs6PtoHo;A{m-mg@QGluP`6*`<(kg{^!s`M#tPVfom4O;`C_(_rWS!IiOL(WFdq0'
    '35M4mtW>u!0Nn11)vr5(WT=9W!hx8GX=KTt5ens@C}?8b^#oKjDroDL$3tK4ei#_Pe=reNKDf3FAvju@Hy#su^qevp^*)3ghyq~1'
    '>DmpPQ_NknP=OKV9#5ftn@~a|`lgk2ks09r^!iXL_hNG})_YsnKaa`>(1uNoB3c7Pf`HQo-IaZfF-4(T$B^XLZe#x})+JQ;;*Ec$'
    'Rt(c22rr0?x@(T^47Z;;dNjA~;Eknox!f^x3oQcUPSQy_WfX1TWaw>F66|cs=l~C!Xw83YVPE%?LV(ptF(xcd<4;|HfL{=_g(1*d'
    'lR;3<H>KqNzWQG&j;jI6M(PbU35On&MghTyB3fi}|7akEjt73{POPR6ZDR-15*I4(C)KuGShL;RM_VG+<_(y~5DgQG!L?ofp?&Ng'
    '&1$@g>Z=dziUk6Pry>l}`$(ZR@z{i^i<h#ydNVPh^={wDuecoew3(SqyVZflMQyQ?)uz^Mr8){vE_e3TdqC`YNME+am+)H8Kh$hR'
    '7|$49Vw##f9vPNF1g(160fsh75I^0(b9mWp-50v>ks?uDYJ~LRhaB{l6eh8(D@}Ic`qyUjwISkdy5_Daf|lu4kwg||y=kSNtTUS+'
    'ZuBfos6VHxPvzSdc2BFtWLuE!tI*P@8{2xl#??Jx2_0i}^?hUB&W-!{J{WeF!#OUnQAkS>W3-EK;~68Jlv5x9=`!QI#SqY9xOOwA'
    'p1$;A!b!S|X;n`f9l}=XqL_hv1Dau<dV^C)0J0e8JPatb602MH5yKrG)(p!<wK;xNuf2`ghI5{U(V04QwWe*FNO6~T?Y>W&{o!}^'
    'a>}sn=wXKf4<~C;)hH~&0pF`pdEs18BqBbdVK_-Jfi}NwD|;B^91N!zg2?Zl7oKZQ6*`51IqHjfy>m?01}k10x*+tNy|y|bh+DYh'
    'x*%B85_<Jqgi5U!7oF}os*&2Op014=e-$m<?E-#A!g&lecp;WC!HVt(k8AS3I=)xbaseFbRbRQ4eTG?X2UB9`Q87~WXeh_~$Zf;+'
    'mwMl~GdFd4ZLYoCAHIBb7GBR6>Nm{L4M79^#VM?#t!nfE43Y9JhYYpB$Tl%TLn8>o*JfE?0_=MTE7VAS@0KT@>tR#PAxP>pYczw^'
    'Tc%>L7*VW{28v=u)FZQhzjiC4IAX)_@cQVOthM0rxNOXE(?`%vl4c<vA&(+!`!KjuVS8lACHkc0G++Br%&2|%*;VqFJ{GE99oDN*'
    'Nsk`4K~IaR9M5w&w>EL`(~C`%_urTPp}DcXkZa7KvzR6q68;!z!iZHTkJ1Nyw<h7&Qxn&DY>wA{vIykYF~_kwB|KTK@QI-zCBj~e'
    'PjlzfEn+nZ8$pMuZ{NozY0P{M|6|NM6DKHi5v128d|XU0Q;P&A5^e12dnC4Sm13d{pJ&KBgXcU38Std_bb=B}xjQD{E=HN^=!Sh<'
    'p`fq`M26c~;9?anJHoRWMVZLiMJ%aS_n&OKVHZ2K40=!c$?{+-LoEoycKwSowU3gO>451(yg#n4(oPb;yR+nPt3<<r>WTN&s8BoM'
    'bT(`&xX)<jS`;Lad7Tg#uie9SBy5E+&lS<am+59jeIvEZhTsS{F_H)c+~K(TL5L2ko6xyMx;<r)BOc~8%mjic6Q=SAFk3NgI74JN'
    'LwLho{efIFX?}`U6sBW%DG3fZXy9Z@Ma*r5a!eeq>f!42_q+q&XoS#RL$5W8iPO;1wJ7mRM04(4CV5cGh0WQlYSVTpZrjM?aSiEi'
    'w!`%6hU)|X1FberX~^ch0R<|g8>>sv6f@_SAi;FEZDi#s?0GSnq>}GLl8JLrirH@?O+ptZGdMX3>K;=UuZ<QDv3_8S!Pp=l;D`LY'
    'fgb2AW-&DoYth|h0~+c4M~th;L$@0=zwzo%<=j`juAxnRg&?9>ouI4H!VRiD*0p^#F`5+PQAU(Ex9#QH);6O=kaHen!;B39$(=R`'
    'nOX`<4BvDUzTQPU-nN?)muA;SaKez1Txz)BFpX*jf!DceZTM*GP36IdzxoxeqSJGJzEgY(T~H{-bkZ2FjA=SHb#Ngu#|Jkr4=zuq'
    '8Lv$R9}m;<`%bpQYIsFT!>khoTVgi)Y7Zz6-ftOF1zxV^x(&DN;`Cm=q$3NREpn(q#&|CbP7L1Qn}o>~N-~6-;FrrkLP@thWa6jW'
    'IENGN9Wlz`@UVrsn5*M%)sT`3O`(=>-#EBN|BxY}hY)jU<K;I!lDBX93UZ8I1<wvTiY1FdW#XygsmjCSC|^>6gPy_8ug=@o?fgKZ'
    '-3^iAyeTFX)p8(BGi|)deQ3CZ%a``j{-&@Ux@kLaj^;}2FMDKDZBP(`x~-n8u>g!r5m1!-QGvsVbhx$lhMT^jGsAc9bID^O%8)V8'
    'qlD1TbRC0$<`6_Gf*qQ$_05)RFXcb)pO6gf!|7NFs%Pyb>;pkDL?|&KlJ+_*GjQtwxtLYg=8fLYm{u%1>O5niH;ak5dH_OLFuZth'
    'K_;$bgiom0NYA_@(7ue->8k5DGV>Ds{xH0%FNf7>V3Ymhi>YH;K^G!){7G*OVU~UsD4{nvg#xW@uHBITaz>ulbin`*5=jjF=tCmy'
    '#KsJR^*Atwr<kV65J$YZb|d?V!!Z(j(Dx1My)ehI7yk{dX0=K}xU41E)Cku`IXK<fWqvZveJ~YZV;2!de8mB%6M7I{0BOQzqe5yW'
    '$Bf`lJAUOZE>L^_Qf9ho`nYB50Q5CG+Nd#lt@$#nu89J}&1JdvLy7v<=Mj@Aw<a^tjL*nRB1Q`H(U_FM?>@%9vD}oBm?4gt*IkQ%'
    'oLRPaXX$IW|7?^tNZZb07yeif$|?wmI4gM!=7s?<QI1w|f8{pLD*m_KY!Y<z5OTb=x(dEw@G;ye3=?E119i1VAz&MxUS7Wq4!WW5'
    'mLHz#tjl4GunlW3W=W#HhBrF~O%ns`eY4n0@HroCbM41@;vqk#jnFU}!>-#GrdXNzTH+=yF#D%AZaMD)e5WrvS2wM`j|JTYU}{2a'
    'A@2w$MV1+@SfFPPozw-jzfKB&?R!{l%T5+0d!Xzf=PV8)=O4Z^X4c8r``DCPuZXFi=;uM(*xJQ)5ortyV3QP*H$22#WvXB*$_i&j'
    'b%4aCw8dB1TJ^hk#`jC=JYQ&I<k1jpd!l}}QG>3MUY3@0j-L{eFyi|u?(T8->N{NGeB2m8IFzkH%b>k@@gy{!K2mtYMnht?q)m3t'
    'pJpNZqo28&4XQ)NN?(%H`n+WRwMI8aD?ged_}FdQwD~=UnfLD9zj#NO@CUY;QSZ!sDcrCGU{g$p*HorsrA*g-Zn}Ld?hb5h5IJFM'
    'is{4fI&#^}eDI9QP;j~Iry$P?yPH3B{f77DfF(M&5iMO+nSt9QI@1HKQ#hPo<TJzJ!o;oLwPM7qeM$lXcf2yU$Ouc9ZA$tYD=~<T'
    '5mDF-h4xFmDMtQb**%fM0GJehk4+5nQJ?S#HY7EUH3W#{9is;7v1v8=!>TyR(TCokKf4r%AkXJvDQRe%<3#r)Mr1J;hP9H}J)1S_'
    '53BCHA!t(ail@*JK3O`<WC1len6jSDx)BG^3?o)HapC`1c*hJUTwV4uoMfjiCapHuLns*oq@Y$PcisSPKLFvqrBAi^rympcPcK{Z'
    '=H<n*pcv7~r~-0S#7u5D))dzOA8v8F)>VG@MpRQS$ER=6Gb9Tc?*I578~P(KfjRODxlH8Ot&G9;CS9XC<PkJh=eOp4E88E}JF_MO'
    '0ogL~=NcL+6F&YOFq`L|s37;1hDefm3rD@ZaAmt<*)!h1y>@gY&1FpS>Ch2szl3dnZ8kH9vL(Tq?ZUyjcI`KCd&d^w9C+erc&Z?M'
    'udqlpNi*CM2(nWMGg3^de)m+XdR}4=pOlA-v9$m7%k%N!!Y_t@;^Sf(#c&dWzCL{Bi5P=+2Kb^QT<}ES&2g;q3sT0Xwap1-`}r~c'
    '@$Si%P*Y)78E6Gks@6Nf<P8JsP^_rk%794U=j6v6(DQWd=T9+w^S@qxf4MYcsOTYPTD-F-NQ|K5mQFWeX2>6mu1Mr4-j}iofuG)f'
    '<j(~ee=&q8!lhp0w(&DW;yTi`J{-ZNa4;cQvzAfnFRd1Q>iD})E7rczm7*0#@?bZuUeKvD0}*Xc<)BSi<GRBbxWvC(H$BU%KH+mj'
    'Z{b|H`jfl!pWJ;nEx4S%)G@#qrG@<^FA?L}a2(8Fl)D7i0R)4O<Db2^iSNJnDf+Tc+kud}T1C(S&hrrXNLKjf5$;!pTBzBFFrzYH'
    '?`J0{TCShR;aBJM`(JJZ-EfpQJXQsu8XAZ&N%mWeCN3D0$e)K0x36}rbsDbu@_!%yuXMl0ga31Q`MQC@x>)h^CEN<3z+%VvD(7Jx'
    'h!+64x844{AU&<FNiu!?bY^D|BOV_&%RUaX%plR(G;1&t=ru4=`)IiaS)NIw%Pm0Iook-|eS=Xaw#Ps_lbZ~h51^Y0%{a!0_NG|U'
    '*aBmIniu}K<SEPlyfWxErf-{?iZkbeE5hf9xN(rQpo-Bdg}(_w3eM@gZ@pO(eEGnZ>(`-D<kg0rrhU&7kcOMilWdG{e-_k_pHk9('
    'vfh_ha}+n8XW0+Y6@@ptE@gsbXjo^ue<T)6F2n}h*?!-84ANe<hK@EdDv9BrA7r$-=;!&yn2v~r;~3VpF%Wio_mi9spH4;x&!4{@'
    '7Ut$~yVKmZ$Kysc-~>mK%2$zXER{0MJN)2;B$zx*5mQ-Ef>!KUI@a3eL>O&vCLH7L@CRkp!C?_7Lz=63RSuzGVwPI}R6q3}3qGwt'
    '@|H1nhzlp=<1Bnjm?=}^qTv$5GKW>TVa2*z$}H_z@%3?&nXfb~5zv92eNbJr<;3+WTKhJ^LxC-sN~#;)TWwBZu#MjQhXmKx{~T^z'
    'o8M#=?q6gOQXex>0V@rGihBjsyAG*21+X`pU$v^S35SiEX$)6(9SM?AOS(0b;APlo#B3(K4wK~SJWE$CyLo|4A>-G#LaI)|U16Xw'
    '2()3V1ZZu885dJK@@p17)#8_L6KbP?{lm@Ia0nkP4vUHrl16we@x@!!=gi()7H{a&`gwf%=PQ_FIh+PG?|8XG*eOSG7}R|^Sk5RD'
    '7a=MMr8qevD3PN<dF{%3Xd;9QTx~=IahByCZV2NSX<+!IgyMzmGWV+D>R<hJD=^h03mQNA#ws+B$`AuNT-!?3^(EjYz}3q9+J$$_'
    't&K<&q|+f>ZX`u9`VZTIn%yYoFlG&YM)p(u;k5Mg^K1Hq03&-@?HeCohAp{*pIbOV?o=5Ql2#E80*<x^?gp>9pk?8G-0xa*`;OBt'
    'K&P&TmN5fizz~yn0_9M%x>`Xxg$qb7ylc5VR~*O{AJYUE)7BSuy5g1BNdKU30tp!PiCV5g-OdGHwlYuDKI&K=|I|3)>TedRXUTCb'
    'zG6>PA2Gn#cax$s#&F89cjQF&?pATZxWkvQA!lv^<WS~||GK#NAu5e(*K&`pZ^huoaD`&k`=M!($@^5o;Ue?*=0-6BkMNs^ac;M3'
    '#h<wY{3Xtt^V0bRXxPRB0`U>?Bla-6iqC=)aS2R$+_l(g6wn3<id3qPVa-gR8%zplHVj{F8zmxJ09_R4_1&-G9M|9eea~FKAWhR)'
    '1eV$dXVxXIL&16h%Bm;}yw_fa?)@d@KZl5?pVs5@{AM1qVHJ~i(c1Rrv?Ux9577_ze;5dJm4$JPquXA+>h?H{K4?N_7}B%)7_yW9'
    'gIItgY@CbxW{3_|UtGVmrv7|fmMs}Qr&eCLG6m^hw8QlIhoH81TFC=BUl{k#`&TCu{MU0(4j*4PIG~1%iL{7)yrnCCSF@_n>vgqA'
    '&@_aIK#VNkzw&l?kR?IHI<Zcw5_Z#iQKr@yCq0-Yqi}+mRX<n5y|<=y{&~Ogh`~|-Fry&La7|ce?BUx6RUy15%?E(8ch$9vo@L`3'
    'Lr$>;UDJFn^<4STm@>yNcO8l#Q~>v5E_0Jz@suND*f~aw4p^E}Mgvw-s&Gu~@?-o1l8^JPgW$SrrfmP>utzWMWjG1Det+4}J|ddM'
    'A<jYw%@((YG7uI?7W>eDdhIIbbj8_zc>ESCKbxJpG0TqO&ydCFwjkme))g$YF>Dgu3utiK43w9k@BM3^Z=;j6ZUX?8l@ckjKI)_0'
    'E^zWn4xN0=$%=b1Oq-khiWnMye)m0LKWuSl>%an}QfM$f?;v5;>=`&y7E$o=Un8%}>$HFU@TXkv1(vtq_Gx8lem;k|w?F-S66bzC'
    'rwfO(SoN^4&1S%#+&&?9p*i^lXlN;BT$PBnyx|hJ0}rom|MzeE&xZ5PtvAqS8dqo@j)f{^3@8ysqvL_E%&kMo<Vch|wtjNKd?%Rx'
    '#YSGnsGpldyyNxqU^4N<Cq;4|`ra6L#rJAgTnm*Eo#xtc*b&83IBolWRG2UevpEN4$Uu!oJnK7S<Xia6`W*}J2HW&2+(nr&x)QH2'
    'yH-xbI5wGB_yw|_PGNET?#&T1IFkVk8>pq*CqdXGRXmRX1|b+iP;F%Z2yIhPd4Y-V*6}Adp-*EFLx!h4zl&F?P9vmp=m4>b9Jyum'
    '#@d+h40#GNz7EQ}`T6tHm+@}vXEiY-Jy;(`({RNX1tjR1rVZC1;J;glfrDuL?ji(NpHAR<VvhTHJ}m3-#FxWHhg0IJ%ftnZ#wQ#m'
    '-34I`#!fXL1jAh=cwp#a@4}nOoURZzZPd4@0Ms7~&;Ln#b@7n|+8qr}6EE_;3;v~MzFdb)F?PE1(|Ts*xF6&kDMl{^`0dWYgK|`-'
    'X79?I@DCFxzT|2xHMoCezGSeSk7EpU9W50FgdX$#ymejc&2r}Rur^ONTuSk_)K&(x1(&`ENd}lU1v)J1kgHQ{@LziWu>N&PvGuLH'
    'c##>vX_zjE$;+_vOUVl32qQ@=pnF3piOKx!xNp(#3gpYr))~rTiaETSvrLe%!?Y6C4-Dr)7Me<E)39&N9Z-w;iKvVGqXzVEhm>6g'
    'eHwt>h@lu29()#<M7?jpK%l=xw7dLq&S6Yp5*)3+CrKR{g`eUQFA!<dIIA$XS-PETt~}yBjW@kP^Q|2oCT_F{eTeF{p`0E-k2{O$'
    'EgsWSU$^eY-~<|jnBU|nCJJ_d2S*a9n!*}IknWCYS~fP<Es3Li*ccy$t3;BUW8vy#7Hx!F7CqiB@|j#TYJsInS1$XO)m*+X(Ox}i'
    'D35tM9xhWJ5irnNPDMiyh<FoKd*ALRFhch29I?MDqn8nCN*LY}e!3cPb<9IULCeS8t8Eg7q|h|1dFXl}(O|-6l071Y;d=!CD~8>e'
    '8(dwr;?E}c{1tL%FCK$>j1>famN<P`a5qgC6`WA*v^R~J$@eY#Ed3mhmuFOh><kU;f?gH}cx@x#RtL2iB`oe4Dbdg`SFL!rjXH~P'
    '-I9c&iG3;VbeQ^cN|EM9Fsfrjc>nVul^e_MVyo(<Hc=`^I);a()7lP^!B7pEMinEcnZ8%=cdUQD{HnRwV4<luzyXS7od!^%FJ}p-'
    'Q7v=9s*ND!Pn+x3Jt-P4M+$%*PdD_<R(t}gBOCHMp^;L<#l-7)9>x0^+P^KlrlB~TXFby8XKnTuZcAv>h21JTlAs{%UUSGq4(W?R'
    'wydXpOK(Ph95-|sD89rc=IAiyC9I^}K&<gmktk@^)&Hpl|6l*d{{w5?9GU'
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
            'protected-producer-optional-leaf-common-v1',
            'protected-producer-exact-parent-command-owners-v1'}
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
            'protected-producer-optional-leaf-common-v1',
            'protected-producer-exact-parent-command-owners-v1'}]
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
                'protected-producer-exact-parent-command-owners-v1':'b29e0558dc69bc9dd6fc6b47bd6024382be4079d',
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
            'protected-producer-optional-leaf-common-v1',
            'protected-producer-exact-parent-command-owners-v1'}
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
        if installed['name'] in {'protected-producer-optional-leaf-common-v1',
                'protected-producer-exact-parent-command-owners-v1'}:
            self.assertEqual(future['.github/workflows/project-tests.yml'],
                dict(mode='100644',type='blob',sha='f4765fa63bdfede51cf6d711d24a952c5d0e0316'))
            templates['.github/workflows/project-tests.yml']='tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml'
        if installed['name']=='protected-producer-exact-parent-command-owners-v1':
            templates['.github/workflows/repository-checks.yml']='tools/repository-checks/workflows/producers/repository-checks-parent-owners.yml'
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
                        'protected-producer-optional-leaf-common-v1',
            'protected-producer-exact-parent-command-owners-v1'}
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
                ('protected-producer-optional-leaf-common-v1','b29e0558dc69bc9dd6fc6b47bd6024382be4079d'),
                ('protected-producer-exact-parent-command-owners-v1','b29e0558dc69bc9dd6fc6b47bd6024382be4079d')):
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
