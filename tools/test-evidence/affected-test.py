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
# 1d5db47c6e4f9b4a1b4cd1876bbd99f4d9268df0 / tree b5114871d3863a49ba1fbfdb73fb9f55a943c86e.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'f5ea3322941557d8c8542fb768a85c0c033849abbc1f82095134ad22adaf91c7'
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
    'c-qaK-F72MlAQ1L7=68*%E*lT+o#ac(LGN5vd~2m9008D+CBU3`YZvmS<@sU5~!85(yFJcTN8oI3=em6GxPua?H~8s<JTAe#XZIS'
    'ZX54*e>|oA-Er@p4ms`r@%v%-^xMDx=Wma@n11{B-%QgC*8cWyza73h{<du!!~gWAoq`Gcr^bvqr_RUF4^5a%Zn_+e;s3+&$Fu$m'
    '{KL-w_Fw<@wybBN@b&I__pl8=3afeF@!vJ1VIG_4QkaHu3_dl@*yL{TvB~3LT{C^Y+OrGa+<m(HW4Hg7A9jD--6wvnJ8pMRhr;4+'
    '?B=QMr*SlXGInn4Y`SQ>K0D{T(M{G5O|tFhi|^C(?yx=X_CM~z*A%{$R_ucv+stzv&6H!DQ%ZC0ZEkFw`JwaVy4EIdKVR{f4#&I0'
    '%l4S=VtP(bF+GKCDy{3Ab_k{)e2V<$aT<Kr<Z0@x>wWZ-HNNGA`=Mst(pquo{oH1KCj2+L*10~7GhdLM<{`RaFxDI1>*s5|zRCkH'
    'cb}e)cmI5G58J#A%Uk`&kH?44SD$?jL!QRA^CtJRZHLTD<*EB|YMWuQ){U7@ylVCR?)Maqclzyz%gb_Dy4Lm1*${FXdv9!SY&4@Y'
    'b7;&EdFQ!JbIr1U|EMl5ZTe{Z9NZkO?|G*t#6C}LJER<<9f!%p*rmz+eQCdEIU+-N*z%OWgzcB#)6=)@)8Wg#(|dmYabZ>Cg7qP^'
    '-da2Q)=qH<tr`0i`-$J4`((zkY1gd!%rEDKUtZVdu}jvaaq4^%#x_oT$=>r}`P`1V8K)+t5Z0}`^Osl6E{{#%GcuXq*EX|j+HUN;'
    '4Re}o7_$qm=h3fOb^r2oam`@tFbpxf+1qL4=efBXnt3w5OFp$W`esZyuUb=I@+N%U?;g|U5O&X(fA!Scrs2st(+xwIQb@DwJ2y6c'
    'I}yA35a&3Vb<cX)!IOJT2LgB6?2~)mKHXp3M&!_Ps8c^!qGmESb!Kik$bs-YnBH1K3Rl(oZ9G42!tN<=FR#xTPQ%po14qd%*W%E%'
    'O;2o_`WV}W&5i7_TfM&S<+%Ctd-fOC_k3rKwXyF<E{VS3N%U@RLdy-w7uoR?8t!MedVRh?uF8vRr;xkJ^=%}Y<!<z0491(Taok$L'
    'wPuQ)9h!>Yu88u7`|;%|9Tn*|``ybiZQ|D5KkW|3ZMYn5x;c0^C2RW7C(G-fr<5F5XVVWopJ4Q@BW0OaZ{sCCUtGAI#=#`h#>9;>'
    '##v9Fop71v*m4juSDj7cSiSJ+!#l6OBxd>qkLl0j<p9)k*vI7BuJ5L<OWIUFr_uM3(>SMK8sfuH4z~}Eyzsbt+=e^C-uLZ+8<hk2'
    '#l6JsadW=$bjw~mk$s<>jji)3b(v@wqn&4KC&ffF^m-XQnepn~ET>Y3<H5a<OJ0sr<IsiJ#$mR+4>Al-+$67?b0*novN5S4*=nxe'
    '%nRw{<wzNWGgD}XDK|a8-Swdzxf(boq<j68dq-N?CUf;3zNP(Bde|&)>Ecf2*7HE(ID|No!)DvG*~fP1%{UKvNb@-I{kHk)ojkfH'
    '((Sk*$LCYt|JZ!p9+azG+*PBCYshx;O$vmOG4)(#+@j<PrelZAXn9K4?`r4ym%bN**$`B@gx(V^t#8MXuh(@=?84L~z98b*pnrP('
    'E}qYohkIB~_1=Z!<-j&YJGG;2r=iW$KveJhZVYj9L(6B~+GdWao&0?DmdL5{!}k8`u{zccW0%RO8fSaI)IX6hZ^nuEqX!hbhMFyp'
    '{)R1;(k&i9PpR3AbJui3JDFBl7g-jMWajNPQ%9oP#;dnL+7StM+wUCg&D$fooCWZ$IN!{f`i*DMP2)t|_XEK<d#dDY0`aH0{;?d6'
    'oU6+p%gm=SYH2@rQwUr_dFHzfJgAX!avb|^?r%6nN4LLE)we(<;cZ-qWFL9p8%Z2&W5=G4WYiO)_A_&nu769XZ1wdj@Vl3%=n8>`'
    '&t&GqAwB1{G+-BQi2R>^2(~qTu#Gd+2{!$rJyl#!UCL(eXFtrH?b00k(D+O_X!w$+$Y-pG6LNFoj+Q%WQxyh7PyXH-E=(@QsZGws'
    '<R`vtsvOsKUEfnf_qV>c^z?nZ-#tC@FP>iA<+837&Lfnd^WOJi;EM2WNYt;%O}^!saihoXwmntfqLZ_u>!>P5Ad?A<CR(an5-`e3'
    'PwqQ#;MtM=b=%o&NdoUrw?`op^nT)lienoZ0<q_1`FRNQ#AVTOr}>mywtL&wuDa#@2%tqm%r~CrF_DD?)rr&Gnm{gMv+Z1*!!O!e'
    '*gY;dN$G(N*`;nKkq6x)Q0je7B+Z0xb~}KbWbWCii@#=9hx9!?6{>1V);aWgffSJhfQIKaHHPb>1*icH?Fi)Vw*6E^0@6b}cY+vV'
    '%5#_p$BpZnfx{mFWX-?}HI%tGZslE8^ti40#%I7oCxD?#9W~b&1BlveyaO^|cOY%aL}&AD`&yqG@!lLcBREL!JHcGJ0f#U{Yx%^7'
    'Zfe<~ZL+_0U*t!duuovS$E|xf6wm=mE^AvZ+G+NrZ8`I>loJ?FvTM5FNuA<+^PXx_f{x3d4~PE&Epo<i=E<so^g(XAX`nzgZj5bv'
    '+h(rF-pC<+HiH=kP8emg>oeK^*k@~!Gh8_>_n>LRZ5uo6UiN@mVfQtGTZhZp9P7n~qR8=NgtDdB%>z*NtP&uHIr7i~5YvrYQdYUC'
    'C}BaE$kzb-+OelH%bt6t1$BvC3x01h;c05<lKhJ8WVd~IDFD5bokDV{ca7~`pkYGeqIcvhq2)1!uA62WDCWlR`uO;qw-4#9TDyGw'
    'M=t%Lb5v)*K}5^}Scb>q$#)w;vUGOZez@`LKJH%*M{bgD>BqhVjdJG6FFD`VC&M>A^Nzv{P}+FIN0p{*<CJcx2v%%HS$5Nz5lpn5'
    'r_9@<<3Y#E`i2u0JdL#(ETZoEKZDfge{%V@h#hDkp9SdX*mGY{&^KhVz41MXEEsJ+g=wnGu<u`%aF_Ov+rwe$Azn<z{5;c-P@^MH'
    '$wx2^nx&M9o;H(BQ)pZy=G6V<uRFc{-L4eybwN{4Ol}@+u(V}cLL2q@#0?%B6M^G6CUt9`(w57ilMYtP!Ru&$L}gI`-^l=Q0h?s*'
    'oJh}<Y^E-MdgAi`o;EH%ZZF>?bT&vnh<~&uhk@<~s6@<kxlG6Z?Ette1w&;)a9*_rOl%r1amq3kNMlH0ps=@`cu)|*M}cyUFi`g`'
    'y+29SIY#JAYCT0h^`WX(IzZ9({Y0+8VQ<<<uWzia7vJ}LYL3!KGkCTg4MR}=ezYp^(@geEFE{a7Q%h5u#c{>rr@}Ps_G$Aw*W**V'
    'Ttg_d63pmx*g@UPVFYEK8&&Qz&8UGo)rDM%(Y@cn<L-M}iczkh!c}O%CC9eSjh{Lv7?-q$q*HezxY$h9KGJxYUHu-`MU@bE;!Ve~'
    'ZfJecq^C|Wxiijj(h?U?f+`SZU%!53XfZKUJ5EluHaN;SapHuyal|JMqMZou<lSBU!l(FB@yw}#c<(fGTduFxa0(}KY2VRYZMks)'
    'h=ES%f398nuM+n19YQ0!A?<ObuEIjbmdt+Q!2{?wylw+dLPD0WU;f<f3(qf?p9AO41gHv)plE0z)EV4l11K@~9Q}l8q|q{8v5~s<'
    'yWG>{G-Q1=J4wFCQZwhFYx#r8fi4WKkIni|fP{VFa&Q#f{xTNiJvV8qE-SZ6AmsHudkP7r&SVn7aU#=*(O<oVx+gL6{8_J|>FppJ'
    'ME(lffQRp>j}tdL$yHCDam6-%9KY_K>HtlB{1gd*I-CdUCn!RxA8DdkfE9X7RL49od&R@pr+Y9R3YEC|WAC1yOIcR%@S{Kod)>*x'
    'z_=WJ@8}6rktaiKKxA-Nd>8;rmz%J|K%F+QST9D4T8lt~nQmL_6(Yq@>uHmO`lag=f_Zea>qIWeG$T@MxREUAmL)ley{F443QS&c'
    'A6=Cd&|m0jdJjB*ezJ!ZN4GOLL4l5)z?}<W=qjqA(=Wf<K0Uu2zwp){&aA3CGW@$g5{Wmk8WqvS-O#I3mC9RRzP~_bPpJsBCO`zZ'
    'JM&oDz9LKdX*aBXm!gPI?>DB>W8;o`bY<YkQ6-Y5QG>K_kQ`q{;Pg_KjF#GiK5^1lTLF%Kwy_dvCvyUnKk-;vVGUfNF-}nJnvvFL'
    '?;(fL&#R!!ESL2wx$*Lnq-uPd%1&wa5)sq^_tauznjpP#MB#~yE>|x33XLgNZg>xF|G3+4UikM4Sxet?5V#}hxPXU+A*lQVYMrOi'
    'm<&zKP>d4BYxi-gJnzn2i7$tJ_<v0vDR1om8lB|xt(-U|DzKJJvw&xk-cD1b`(g~-Q%lO_2Jj4ka?UT$#zFZVryI8O3Lq@ox}5b|'
    'KekW_Lm;LSQaQiW92WjWCLLxUB%c|=(UqH7NSvpy8#1XoRDV8k;JlIsrWPowP29!-mI-f-+S|pRKO##UD(F|mefgK|Lp<R>wSX&;'
    'ZGs5Yx)}x#J*p-W1jca`0s=-xyQLF9)7-wfGiLYhu@!hI96LQPLPCJA2~yXn8%&b{M$XWR@nF(yZ{OIKHqid{rJhOWmyrefR4wee'
    'iEg=pmlKV;9UTqh7Cs&PLI~$(nt#F0p189fXnMFkt-i}&St3GvuxPs0q<UcIL{HlMKuR8J3^gxp<Ei)k?YlZ9J;aE29ooy6s&|mQ'
    'M!-ehT|=OX9LPBHsqw|ZwgnXc^`HFhTU!&mB6$YiJ|8~(dE$3F(e#Jlq)<u&SzQn6HTMgS<vCs7J}#B)i+}#=4h42Jq{)FW&-Ma!'
    'tk489BnMy&0e}*h3y1bY@W0?2J6(lU@byTalPCeU6IuYoaathLoP218Hi)Fw^5B|u`=$=t`-L5`MG8XYTX856VNgtQ57G}!77%yJ'
    'ewsK8w5|e)E)NWRHT^g2ZOL>h+U`?|W>$L*^6SjEM>R}El)yrJN<`R5DS|%#f<y2s1h~ANO#c`bD3C0v4bad8EHtzOb-~;l0n+qK'
    'xe>11&g&k&th*}d_p>Oyzb<;gRTDQ89A$_SP`5m&1*okVuYQYfyIL;F0_#T5736I0Lr0vl97Pgua4c|L-*yrzKy1GG`J6-iWk{!M'
    'TZ$#F94=(25Fo7ZS%~pK2t;*g<uhof?Qh*n#W6z^VnynMk}-lZ!rP_O?#YKyH-K&iM>a}7d%Sro=lbF2!&Zm@jmo7w(m8P+h`sBY'
    'F+%#!{97F_OdS;f@LRXGVoQL606s)T_*#~P%8Rs0{%6oM(bq|S6g=Kss3zlfF9FecXQ@rEt%wDXb>UdXf-~Km+yuIzl(titl~2tL'
    '2*l8ViG!0<)*xhCvxia<OO-|u(oX$Ic|bvcBCivdnYL0yia|j+q9v>U-Ia|d`n?Tm2Ak={Ll^20oy^qmkS$2rAW$2+5N7`9<K+5t'
    'Pq~Czq?QIhBrd0-nBG5VB0mh#Qh@a0`TCoI7yS`~GwuSlI9aB9__Bej|4yQ{(LXEn>sXc#82wwT`z(3zs~$xOUzZ&^FQzzR!*qFB'
    'Q4TL-GIPw(&glzGi9`rhB@9|BZZGW$-%LlqqnFiPUgnhWEdROC>zzB_3uf`TABPsoAX=!AqOGG#rRbj!&BPCWl;E%QBvky1+aI?m'
    'r%03+rpvLwAtyVJFz-Nvxk`}ZG$zn1>XjCYR@r9SMYPK<F1dUuB<B2mk<MmR3((Mq@EhPrHSk$u1LQU&3im1Ws2Pa?AKkHkTku2-'
    'x%{0tA$xt-z)}P79ceQT5TN+tyP0aBKh?#d@cRya_qh4atsToL4KU_RP2F>}0Y||2p?-nYWCW7HyPnK2`Z#~oygp?sF@4|aEmGe-'
    'AGLZ-qSr{A0F6X|B?mrfu?bZdWj>drhyUJ0nx3w-Xmrm<X=j!Q^S2dwdVf7vo?63egc~)1;(AAyiT*WM0$~*CZ=66*VYk<<cz9D)'
    'KT{OE{qg0%)~cf#nu$-Bo(7^F$SXkTh8>JBfEyYsoe%EH9Xvm8UmiC#8wp}-(@jd_(#Gu)a^pxWS8}FU4=or9gX>prr0OBSml<fU'
    'dE%`VQFH_hXdy?Cf4Fw=VREP)kQ%OCJM12~Uv{Sy{!Du;fBT&ka_>>IAsD7WqxPqH0lY3IAA%Hm%oACDT)UeEFy7oJ8t$c*BSbGK'
    '#+(JZ`GhsAd<;f|of48|JAx#G!BLe}Z(;cks@?^Zf(YF#6VOC8>n&ufj7Fzb`yb4R_W-8VR=<n?Ki&bIi^sx}kZdQ?3K)q^kl^1%'
    '1;CL|OFNyac!XU*>$R(0GN!{fx>uWBczM|VS@rCJRkbvIE1;8slm{9Qr8u3F*+MUe%LIXm?BvQV+&{l;zQT`uNQVNfNl!6SJfi!j'
    'T|%?p*p9>mNT*Y8t%YO9+epnX*axI&u6L;J1)dQt8lnQkF*u|{&T9Kbl}zFySmflWYr4+-nhh-gQ$;gcV0bUxMu&bMWj!|*MF}co'
    'qzXx|Fo}274Oi}pi+c|<;;{Y3-@g9c#l(v$2x`h~$$@546F{bsjx37IIMMBjl10-(Xs_JQ34w4w9tdcvk<#|FEB0qdwSo9ccGTpd'
    '@70}`13|*Z!zzEre1Xb4_17M&)%(H9g1`~bj<nNEEdh%Ll?2Z$QiBsx1Ic&yp{vNp`+3}jZ&ioeP3qxLRF9oJAJEs(QZW+pOB0pF'
    'S|Ib!p?2YOwdl7`vBbWlQk61{U=|FzbiPqYpb(bgAneQ#ToIv$q53>OZ^O=h$=g4VLj4!;^Kx91W`~51Jc8b%%3{$4NGFAQfE-hU'
    'kadjHy7m8}OjTbil<7`%Q<_Jx#?+^#UbY=nBDh5KMn|#x0Ls>FWG}0gef=hoF;NQ1Mu&nHh|YPyRhiu&i9sY|@Rs2tt$rH(w~DB-'
    ';*PgUsiIWKfMBzSLd2y?`pNf+tRg441i?{~Ub%x)zEk}?r0Af^70iVQm?EA&IK&ZhVtjrO!*v!?%VewX`tLjbcC%O-sah>WC(^2h'
    '?p;R&@S?CaO8HroumqhH1&&yS<+Xj~f-{Goj}E#PRyZ68%vs3vTyK$O`H;XuxiC=NlomuV^W#5KmGp|9J1Bz=Jl7R3I?vKLwO|ed'
    'H$0i10llXGP+D@4qP^DT1)cCL1;tE{*d+S>wn;Fi@C1;V(?kQ8zXTXcrGQhXlcw_o?qmSm;a0TjSW|r?0wQY(;P3rOyB%!pV#_bx'
    'o!i0skDJrKL1yq!(RLMR%BLHt*s;MFA->1}h;p5W4>yUAt%dLrn`^eSeNy8W&V_%$cWb|Se(|qdn9F-2<a7A~;(|^9-vz*)Nat?C'
    '42f3yC>YPf&A(|+Qn#U(N)KF1CFUBYCDI}czzaZkz)}G^H$FkA?}2H$UhFmZktNcK{k&`6kRIf8+&*5urnm!Pu%jQL>_r`{+X@LF'
    'r-P0!2S^$-^55vL+0_G2hi-2wg=XGDqb5C$ToW}<<U!%l1T`ekij&|DzydtPT(gJAr5#91qO=FRxrDxe@BlE8K7!|QVe`#kn#F#I'
    '#n66zyk-xw_hAqFSn(_pH&Z9Y6Ru}`DZuTpW8j=%iGY+L4#*h*B*J*jK4^`q8h?JF2VeDZP;<{z!YB<m+E5H(Hj?t=?7@y`7fo5W'
    ')-Yf7aV%iX=5%kJPWI*Z({MKr)PrQNu(!NGGN4>IOHcw}00w<E>AKScHow~g0GxO8&&P)Xsg7g@c?kqW?h_1wsCO*>UsP$3mI(RW'
    'rWEb*7i>j;b{R9kVr3ZVSEq$jh941+g%|@d7UuYvX5rjZ9IoGsSeXaM$5KFVgkpkz8);Gyg$%L`gi%5X)RECl_?kd3N$Hx69NgnG'
    'nzV!X!Kc=KiMY?-fG1L6;c+mB<Xf`+OvOVB&G(Q3VN~<cq^n~8QOfjKQ2|)h9Kc2+J@JuGgZ>JA2nUb=Q`drWfY5^h`fE0E`aHq|'
    'h1lgiz#o%LB!V6BnIM3ZfPVz}1@fU;4!92QZmd5x;j25o%4poNcvi#{2FVsjneH;FHn<8vH#ZApRL-wV0<pWP4`**Ck7w&BAl$D7'
    'gaASU09T^lGs3r0+kkc@>;)t(*fjAt1gT8*LF`0=J>4!lFSR7iR1wwOb0JBB`U!2D^plo*A0|3AcwUeisewvNr6%usUw>8=!^4m8'
    'kj{Bq2%He*Z^y5T8^A*<*JaWnLrEAKLKl}E{X{@e$O5{3AaT$O1Q{^y7wxIS*bCAKK6;4o<!nfpMfx9ry{!Iprh*3WfnhlPk`2Wz'
    'u6xG<<Gn?~9_Xdf==HMs8bq`T_<1JSLws7WuCmIwU$Ucp`sYh2=F8TSPlpJHpBE;NN-A*#;y_uoZ*g#i`@)8A-O$7Ce*08~wG6b$'
    'xB`<dXsj;zvO%jY*}vGb*i&*tT5(=(-4W==K^l#xkg7f=&<!EDOCOPLDQ|2x1BD7bL?1~aBw*%Ny7@`baC}oum-fW_;q6e9&~n0p'
    'm2iYLs}u3EQHBS<H<MDNc<Y`H>BvoW54QW{o)2Glg<T=qwQvPNcIkHxa#Yb<jO3bD42vj&I27$)wyT%thn>3&HD{sl6!2Jy!sf*X'
    'gi-`zPKNkQCt657geE(*x9;h<`<9;0wAsta78tHrv4MKU^<?7+4~a(5agaaF9fJ2(+w)g%D8{|e_<c(HH=c?dL9Q*zM$|7*UO@BU'
    'oldf|!z=_&<78W|SZFKPZij!MM#bjq@%UU7m<WmVP1}W6fmZ{;z{2{3kih){#}XH+0q<5b+`6Gd*l(X}u70{&9&2a3NkUJ3iAI&='
    '4-giwP|9!IL8Kz3<h)@+Wtu5H5+er!D$3ZB8B@tpU1N`cL<`?YE*C^py}$av$K9hNPA}KTUtZsr<F(;Cbtq$C;VLIuFmi;IaBrZ$'
    'k}zR2A!DZ-xAd@;)V2bxqfD7>Le=aEe<)-?u_DMYMr!yrgNaJbLqxK_Vn0+hX<IS^l7n6B!Sc8u$V8B~!M@T#!$byxS*wO1t<&bl'
    '4N1;~zg$&>M%)Ke0)kJ&nFh0^+ydT&?*ma@?rD*%8mywbc1tJ5(c2k&r#QR(>Uz19S^9vO5IE9kG@+yV_7pjIZ+K*0RHx0a+Lrzb'
    'm9fH-m6U|nCMPRAoM0xyS_~sdAiiJ|Zx>_|C3iRdqJ8DEy^Wlr6Nn?xQCcDkS6OEFWZn>Qh?Ss`7}19tH>6v&!pa(B7KNh>>lHMV'
    '4|<{<F{>9xnF>7zQj*$3=EmKeSdM!R-4O<4QCR`Y6~ZB@hDFJWP5|kZ5wDwS5r;WhC*g1b)AYt&o$rsAr^<&##}-_c{Fb}jQNl7e'
    'z)kQ(g!2Hw!_Ws#z^3%tZQbvVJ8{ZMxX*hlWZMwgC3sCO>T4^OBZNu_6rKWr*5U|J4#w!!(ObxZ__%^CFP|}w_XZh1p_xXjsFgHU'
    'x!gEv6itB1v^Qyd=W93eu#1bG)yX{SGU8+9M2=Pu3dy`^0Jt=u)ln1C_SW15Dr+M54SP{Bbbd+a@LhG406Q3A+7z!)HJRhl36X1Q'
    'MDVKQPc~8{QJvhju|-53my;HD#a4t8G}1!|6ZqNAP=JGo<uL9L6;i~h6}o^!*Y4>Ii~RMN%3B)DOa;q)2ub2VNibZ<qVCd{<x?g`'
    '>Z3N-7a**P-QM~ARe~dy6jr7qg6(Kd;B1dm^C+q<@_U$RP<=%<zd9{>+Np6QG!OkdPpriFHQZ<L{)4!RX%Q-jQ;=j>7=UYx<V<+s'
    'TwQ<cmK^d_4#AmyDMUpSH5f5KBsDT7BTB;`7XqQiW73p{0Qi`$zF~nD^;uK%6SC`&8Xzktt7PfFi3GUg(Dc_Ipx6s|Kv_PrG38r!'
    'bhd`r9KXtS@A7sq18&r(U|EtyxungkPuCBosd`?pV^B0+of@4>GU_0rBZR{;=|I|C&N}RSFsqq_8wCTO4s!37?m<g7Inva)`W{<u'
    '(pYzQwA}2p1u$#FF`xXEToI6(mOR~TthMNTVRnM-<@&uWcRbRL+S86G(URlyZm0@v0Q<my9MK1rHCj(P7~~(!`xtKA(f7v+gAaL!'
    'fVwdFsZA|7^+XO0Q+x2(N^9IoB(Zkk>OAQCq{Q{R(6mx|-!)<n&4R2ujlE#$N%oN3S*ot_m!?db-3>cQe~K@!hIO^=D2vbIEQ1GT'
    'HQ}JwE!81Iceq*kR}m@%%<gX4)OL9~srE6=2Kjc7D>B3ys4eoqgK>pLoRvWg7>Ep6y7{&p?JDXq#{DQO6LXhIBoY3sp^)xS5y+?r'
    'zPTdecs=B)og9TR?Dhr9p;fZp$<<+myp4AzvPa@`O60ArD#I)Z;0^mYlL13XZwSo}W-&fxVE9-DVc{ES{$L-+Y%@$1IPxfIeY#~U'
    'Z}$`tu#o2jDrSr+K{!Bpk+BR7raAal5(xQ9sOq`RIpV)!Gv)3e0GQN5=+!yZqYxO{m8e#Me>5?Si7I%4B!9zZBrhyzrwC<|zsOw='
    'Tfe@O*<R2jI8tTUF(hCP4+0-<*~L+Aog0z3idYoouv(%tt4XIwNZAivW5OMXorsb^W>h@4#NM|YBEbnk<6kg)!e0ZcJ;rLmMW1OH'
    '@=SPZG*zr6(;-0fNBQbB>#y8%votmfLVjGZ(IW!ALoNe5<wa@k6KxAhPQGM7AGy<Cb4l`Gq?rIqIdN<Y;x}4vxDQ$lMfCDwgJ}%@'
    '#1+X|hNlDKOommTTRlHu#q(-#u>9v@Z<|cg$($mRHvwJJ8tmnb=BcP=61zqXF)WPhDG%^TPZHRl`xCDqO0_`?9B&#)Fz-N9><H@;'
    'I1?5VbT}+p(CD@_8u}G*#V7k(N`&fNA%hQkSy%((9*LBg&MsCSSi`n5vZLWV^8iPC^{&p%liK}|3IkDkWD9f#bk1qM!AyXokFb(U'
    'ie?6bzKpqgKkr$TwVNX8)3{MpPf(QU8pvZ%(sUhqx?!O9*x9T|w?5pI{#pH=mew~M0OZ}!$4N{94#B({g+?UmMCwM=^5)t-g}pm`'
    '#TN2ucXVa_H?R`inOPbNEIYtYA(6}eHNp;~UVwm0!Pl<f$NkH0&X`60a3J2829+}Zjp=_117x8sB5}M|@G=L{v=m!c$AF(<r^-#q'
    'Rw%-rKu`zoUz5_X#BZ3T1g#q@Q8HyD$u7p*Hl=E~+O7|ul`fx514)i$49=K7EPWb^<WV@dbVJ>6?T+4%l<Ey(?ArQ(@U&05S2f0|'
    'VL%$WAQD8Fg#2@|<g4GC9*#TE?OqWdsdrnlLu%n(eg-29b*@yXupP#Vusa6bEAzEGI+vg1Q!n=#7EplVL7CvPGy6*JC0NivPR<&|'
    '+o|z2P;DWxLMS=hyq!}!XIFo{(R-8YCLa^HQ`R-dtVwAnsdj)0!R#2VYkazKXG?FOc2Al$*h}F>Zw{dY85yk=C<|1hR)9E}<TQRb'
    'u4mPr4qso6N*L?!6QEN9l9632)UFPfC7M0lyby;_K~Zd=`Ji~M-q(2}%cp&KjhNwOF_J#QTOftoUQSN9y%I1Bbr6HhSR2<+=q3nn'
    '={p0y*evh3dA?;wJO4XL6ICi<6K?TSEEr+PPzjwYdNj=W;l9alj8G097Nvnje9YalCSm$uPe1)pF|}l(C~s<#i9Jq67-WF7;Isr^'
    '5~G^M?U$zrg|&W13ES^<r&c_<<iF;Zm(eIHASjd#pn`Nf<Re)j0c30f{Pw#3u<rQKa^<tlocrD9Cv*P0b3K1~E7H$p?lR_4F?CK9'
    'QbvGUOj$@kVBpYyhFZIV?)=GCim5*r1PBYvYUzBalY>_i6=J?v;H`YtVC>uab9Hnci1JJ@UjDPly@vv`RpTS@TI6XAa>j#(2O^e5'
    '2+){u$}`*qn5J~gE=o^=h{7BKxy|uuBCbmsm)2@f2?mjvy+TdIC#R`Tqfeja(^dx<Jss%VgZr_Nt_vD7@rX5m8$-EXlwK<40o)04'
    '0wpxSdr$4Yf(&)q2U0$_KU>|MR3xSP7`Yb&Ohpj@jVwnPFl`7>nz!CT1;<u>ob$SEV9mYRJ7s~Jd;PW4N0;d>ikhfY8M7vY5)jvN'
    'BfOTO0rY1WQ%&|Wt=|Rz{jp%hCU22Za{=J&0$jih@q#I4T{ZA$k^RzXaKo@}@zX2NXHfMXU{!!KVnPRL5o;5?NohyH0*A+lgSxc2'
    '3?Z~D^l@jImGm>`ny#$nffS3-7&C0xubyd{FuiGu2ND<RT>cdHI|RbsuiL~K_I&*i3J!D>+DXW-jGh@Cl10m-;Ko-*bSpq<xC3Td'
    '`90Ei!s)3_8fY{fCDMw6a))OYbu0wxPEB6CXLv^=YIFvMrFA=iP~w(}llA-n#Kw>T3C)~H87k6y=Wa)&LY&lq35@+eG@ZM+jYX1D'
    'mV$UA{Q)i(2z3Ts6A+N8sR`a-ARQw<@V<<>U-=r&A^P1TsIpMQ%c7Asbkby9g-1rTEy6M|4=9`BN5e((E8hq`El;S_2`wy-1{^9s'
    ')?ccy0O<fanE6GAHi%NgZHnmyZe8n^f7z1h9gl^N5iJ|P4$pYqm%w23iwt^DoGYNPh}0Vd*mZIB+J`^3rS7yQ<cb7JSs-OB_7Gz1'
    'YAO?z9%dsz-$q*K>b2!gf1))#%DO~z3zDz#oU)iKwJ=|Wu9Lt3a9g@FPMk-8AuP9zW+?RSjXNo7gP5d-3Bc6Cz?BC%PP&>13uTD0'
    'QH%E$O0sPI`fX_SGuNw<TEUQ?8HE(;MooAIvcdU|`$9$uvH<IZFM~X-csY^;-HFHj<EK;tpS(o$S|H{k9}d4i&c~!p>3_*+q9%z!'
    ')g_Q}YT!Ac)E(^gyZU{%U33+T#$%Ho+<n28S*>SU<YEs+DFx(~q>J955+?VO9SlRT+Us|8(uKnIpv=85P07JhFKe(eE`Nk9kR?3D'
    'vJ@~PebZIbOa{ij&)07U*5VEY@%imBdm-<kHWZ*7I(l-+>pJO7@DZcC$7RPHwn^hMq+;#yCMgw6NdWsYs>#v5`m-=53h#<e0klIN'
    'G~%(s8-dKhHv>HfG^x>y)wTqSra!3@mtK681)-GL!Woy2GnR*VOcP+6(Jk3F%MxHgKf3BwITnR%f>RiMFq(iArC{u2fp5f%;x6Ts'
    'QZnP)Un<qlEvA1l>cXw_TglKSiyEs`0_Q_e0;rfRz7mlkng|PEXE4JW+LNhV|AaOd3<5P>mBtnz+zc=xcYEp?yrH5x6+Ct%R;kIA'
    'E1nesuWH(wUK`U8$OyQk(3xNsh}Ntdls%$5Q`aW6OTVd@OTX@5w@0=C>Q|gPHfpc{1-0fSYxXAUNx1L*B2>Udh;dYmz%6EMZ_EC1'
    'N*8yeNhP~-Jm~0XGJ1kZ0d!t*qVr<gi#b4NF_Ew_@)qW6<<dAZaFYId^kQo6F28h~4<-?zH10b{3em{~52XlLCrlI2DT?a2ZUc*u'
    'r!edasuSD@d|I3af(S^pa-ECvC^WDG7>eFDwU2z6xLhEjqGO~S(_kxLK!Oy$n;JSsAB8RSh(eh9S`;;GcS1}RsQ-Kpo8!w<$y-gT'
    '8}2O7T8QPyxRQo+qLF4h*p_R=6zZT*l)Y-*1zFS6Esv8U!|xY~gp?6kBPqy7L92qK>d=KSzt!}jre@V2PXW<EBy?5U(}+(80WiRh'
    'q9U6#QJeK>UFk4W7LC|$w<O0Ei=X{ePxb_xviUeS5H|vS9;b=bt&lM&z8oPscqT&wq!lBfM$OWIy7|YtU(PDM(9?#AM_eAjQ<)?W'
    '-*e`6q5fQ6|6q&uBEP4nZ`hlEfmH(z!?jWH$zx^)BP=ur3i?sfAlje|A0Gk;E|D3U9OR;;>2=Z5oN$ed^x~xD?R}x_?=@8iI1p+%'
    'm=7Wkasbi~rP>Oe$QiKQ2$ie9+Lyo1m?jmvPlczB_x|GQh}v~|#OQ)S!|=`S<?aYdNBl%BI9G0AA#!dn8ruTM;%g7V9@4QBp^Hd{'
    'I)kbL{$1kBYgC*R<%h2;o?D$&FB@k@8a;^AG#VO=kLR5PYe0>`b_mNotW7_3fBt;sm2cdjeIVlm;6hlCm$9g@dbufFuS{jg@B(pe'
    'nbvHf;+dnYz}0{cIW0LRR|YyK3IMTJv8b}l@DB3(D=hoSI5Agko<^m}tL0j>_!ICSa58MsQ;`wT>5^3^J=9Fow6y3hzQ|VO<@rP9'
    '@B5!Q6EjHh$h5GIqj$y(;4Chdl0gX5a4a=zx>zxvRy-^g(TA$K6k|=AQLXSY8V!s^Fz|Rr-ZNYp$VH5lR!?^HwF^H>$;*g_g3_6$'
    'ftUib`Wk~=hagFk3Gg9nq6Xq3gg(v`Sr%{0E}ihA;2ZxMP<wg?ke7&-DAa`3k&IBmj84!5^6ymSguku2kX@?$Vz7sUqdz8Tm{7#z'
    'QBKUTS0PAZ??4*?8&<r-`pT76R&2}M>OuYp{Lu`j5XwqRrl)iWlVAB_a)fdHHD<0|bm7swifvH0Ne)ze=44;gYGig;fWf(B4hQTx'
    '6x*mdDXK?Y8>k^okx2Kti8FnM+OedtwF3UQCBa@1upri?b58qyP%ocB$NKpcll{7N7d)0?`MIF(ooLCx@xpd-QtXyB5FZ$3v7^LL'
    'a)}{9i<N7?stQTTE-%YP$jBj0E~RJ5uNUt`S`{RYjN?O>VGxGJsdCx;@T1_E#oR+MZ7_BMGUy&T&VZ#d?SGP9j|vrWE?7b3a@)9A'
    'Fu89R17!wKr;V?n*^TfBdMuMl)Cpjhr|o1nOA1)~Ih`6VPw9nn@p48Fo(>uYj7j^KiW$E@`6Z*?W=uBR8A=LL?Ag^W{QJw}<!`8$'
    't)XULqf$50BH%ZPpm$JSD+5Nn$TYuYs9f(fgluzo1cA8tfa&5mNk64`>@aj1m<K#d+(b%jfZ`N4NC9%~y07%x@~btF>;wd0WJ$2('
    'BSIMi)<OkCgcNNZt9E8wgw-ooMk<ahofB9Gi63oAF=SNQ(f($n5lma;+^8CJ(GUA={oU?cp^v#VYq{XDqMxO|@rb7J)xf3}W|%m?'
    'jP|g#Q9|?93yLTXjU18@WOMN$R>NnH8vr<*NI?oqbq?>^)~@&RaNI6)N-vj%j9!ult!Q}?@B*vNYT;}CCSW|q&9rOU>hI}w@Mm@`'
    'U#I*8&?Yn``9cd))+i{L1k6&wWe;yIFbJw<V4unzymLsdTAp!6q&Il+K={Q?RerQW@Bs6;{gO}^dSXmss9gT+i;T1S!|`hY4UpIa'
    'Pg)!m(aF%2#43sUl=w^^4%hu2B0Ex*%7qUBc&Pv?f!TA{Mo5@JUZ{9pTEPyK2QaXxP!%@EZq0%`<Kn@Ecc2az>_rUqIXkr47~bUM'
    '?N8W3QU}h)bvReAD<&0KUIjo6Y$&xZ<uFk6C<H=I!$dF~Dv&{;#%5_h)JEwy_o8=3RF{7`YKSn5n&rV!=1WGX4>}HX$~VrZjx&aw'
    'U~BK-6J`rY{sW%lw?YO_FvPD++$^96&8s4(WL|kD$gmypCh>o$&85%%m?ghT1=*{Wp&+@(Ajdx%R@C0Ib6p6UhzN<I6pX31WH~jt'
    'FaK7aDfXZl*C8e%QF98XW(+4O01sFB1^`e$#8oS9;LKdS4?$q@Rm8zu(|H+L!DYenFlAd+{+Q_vH13d>ty}e!@oW#f3Oz4Ff>3|+'
    '6I)5AMlpKS7nrG_xJ;Cpa5cNG`gdbpc3S^(=7akkB_J+kNIyAH%c)uf9O(OK-13PtJu}pXk(cKMN_=@1p{39ffSAo=#hzGBd?YzN'
    'C!1P<{)c)bAgNigrS_&cd1%&^44hKtdUepqmh3V@hQ??kiq0apqK?6LI9blM<;ux0QbwYCSK+SBbR@Be`HnS9U?GZgHxHUkA`ymJ'
    'XqmB;8K4S$`g4DJ!(TT16>IZNfiyFVyGOejz2Y!}Helw8jn}A=EGn0%VNeg6H4DE^sydGxx%{d1vg*c{j++YpIX@R9Kwbw{gDkAZ'
    'gA>QwcGdc4r~W$YdYNSL<R!j?Nk)frWJZsuuSU~F$;$%zY*TdW`)LPfMB+hS=6kGPKnn^Uo%r5Nh|6e*V0{Nq8X}cG38T?HFoi+f'
    '{7~d3{IrLvg?Y@h_r1V2v^DgcplWfj)ncVbgkz9wj=Nx2FRXvNKn=lI13Z(A1r{SEGA5)zy0oW|MqmLXf+2HpN_WU<eoWP;ChHug'
    '{bqntjuKxSLLy|S)H`XG=k@^mS=9ByiqG3;geav%jM7P%i`Udhs{sW|`Ok0+@)8eKQElY1&Cy3=E8kyG;*Fq6plNDd*NL4GW%5YJ'
    'oNAa18vqk%y4VB|3cPYMAyBY**)W|z3t?f%3@GTxYOaJx%TT|3@z9*S8<w-O5CcyArh={qR1zz0YDKb6em&#pnf*WvgZoH`2Bara'
    'nxfzEffn_ndmG4j_xiKnZ2zi<CZg?jvPjTqFRQV(pddKOv`mE52!cK$XYpk=Y|VyhhAN_9#-SAf9o0N)qESN|sQXBZ!ISYP(Rc#*'
    'GVM*<sryJg!=jkUj2I0LiJJQ$ZfN(6WGNk+(jC(kb=H@6vW$OxcH6={LKB%ZMx$SaXsbv-Z2*TmF|(8TIHID#{VMv#oVNnLuG+W8'
    'H<!VK%ss#b8jo6rJaU;JXljHocxkJkEfa@&7wQ&1s`5o_&rk|Ig<@$!+t<q{*h%zHOL~&%ABi55S@<+(NgLu=z4ju(Jzec-zh6dC'
    '&@3!jm|}wsVaP+M!Cpn=4ymRwSECB%fdf2~bfJb_v5A!wrWueK`vJ|Hq&O4WjWt)J%B2?s4c`sZ&hos4_dEFgMVVF2&u<e$Q>_%N'
    'a=wE30Kbp#UdVrx9#S21rU|TBe8tyC6L=P@XyJgWglQy$<_OAb53H1Kp#a=z#p>%mL1d@|Aqoe?M3_c)_%nh+@lYseH10Y8Dl#gl'
    'bj!m-&zpAx<Ld_#!O91&?IZ+;R>m9GgdTcM4I1@XLJo)mz<^=x2F@vF)htxN2<9FKY2N~r5E6Z+l}*YF;Qq|?p{U&3;$W=LwopHh'
    'iUTmpriLP#1_%iPoHo#1vM;YG3U(PoV%Bb>eimz%>YjMR|BG5trb8gSKxC-9qPjD<{q*Y5T(^T)md@pJhnZW@B4FH+bRwN%6s>SF'
    '=xwMZu(RpZ0d_^S=5Jf5>wcmT!0M#+2^J^gPq_dAeu1D_7zCQuqzKBUC?)^b)qkcqE(R!t)Em@94n0g71qg;HLW_*tUkxPbc);(t'
    '6K%L@8x>4TxKL&eRNLgjG~0Rm(3TKu;|*vuM1u*%z_pXPX&=?2SsAZF^)(B-!U6$@r&b2(vr=f9c-Vwd7w2wTy%|kt-PDcz(&d0p'
    '8#9y9ZcRYrL~UXvR-3eLE!B}cxwx}e?*U@ZQ@SsUFTrbh{!+8GGM-_03DeZb;~~Rh5P?>`n*fH2B!~|;aFCZ>>As)~uM`Q@C5@0-'
    'e#oM?B$>owUCCq@T>r)<t_=~d(>1H62(rwyh$I@B^`?b>vdnA(aYN5CNc|aBf0eIWsGe2}lPyEGx6;y3H;(;sjZ^o?5?W()>HBKl'
    '&XxOk8w^|Ja1IxkQAoMf80}VWJYMM}IRzvjy3BCiGz7GDYd3T1>62arI7u5#tJ)Vjgd?d7#SF+dKr`4Uy}=*}K%;Ta&OxCivAT92'
    '8t(A4WLR8O#qp!`+DFYcjHZ#%8FlDlO*;%qar3xz-$SuK{K;NU88$n5s!-s;$;wnU6c%#8=haYo!MQ+@2=Ngb2451Gz-X@9N)3Y?'
    '2g9Hti1^*(g~v5V6&hq<4)uk3y;0M(ffd(=E)aU0y-J-Bh+A;S>4LzbCZVUEQ>di%!bL~-9I6quS0C0!jh{sen=0VPBb<k!23`ou'
    '7{LnN5j?Ju|MfbrP|FG6pkDpTt<)K2aXT<220bc_RC+Wh$7kiXvi(K9&)JDX->uEH^TYQ3E8oJ)`9gh!8CnoDfWPn+_G+s#`Tz_O'
    '<(mN+8pX(FVgwBh5r)@hS@#0_o@9lp<ad+z9M^48%|Vc)(@dioSbfA)3@nBy){+Ji#ah)Pk-x6p3Q-(lgL`^;<}+Dp!QCzw=D5*E'
    'pqoUR1^Ec_C}eF82JTd_JsQX*^hvuA*FF?x)INQ5mHgDlg6h}HdKFZXM-R7wo))HZc%FlE(<T-_y)B}=|GM<M=Em|u)|f#znkFX+'
    'zebv1#7ZX*r4RJo9tl4^HR3uRn||$)g+RWJIS#9ngr_kSJ{lU*LD<vyH12$Ki?Esq8=}MX*YBf98e={O|HGJfOq@WWTajL~d|a4d'
    'MlB*vB($;B_lUNzN-@#N=NaT3gJ+{b26)o)bVLb7x$6_)E{rm&qbv5YLP5bIATqd(2^X_)*&#eLqo^TrPKqUVasO$;6}za^GSGXX'
    'pG+Q%%8(WW!*=<9C{t&Zte6fkoe1xb)m7R_;<q_V{z@ep9H<%bJ~b++9pN-GY)jl{Xy&vikVKk3L10|Fhjk=u3Sm4~h!&hoZdRyo'
    'NG%&Dj_{z7L{Px_I95LhqQl}QbZ(KBr!3-#2lE=t1O$;x7?p>>Y>H`yGbp=p@`hV|K-Nr}4{Alhbd;A8!2u2$a573onA;S}nmBBG'
    'w>tej?|?I^5Lz|#nnp3=G-&CxDB+h7&2jHyk_SpT*_=hHHrg)jbsKr!Eg_woZ5zH7Tqgi9pw;Rtm28eTK!FO<4XcZyNi*lONHEiN'
    '8(DY?H7}+isl@jok%{A=q}gvCO~RxvQ=FUx>aMAaYoo=J))%%Y#s=~M{E!a?^nlJ{qp5+g7P-6F0F89~M;KROq}vtE&#yiz=f3K?'
    'hBoRe2qF}#0d!R@Tv6>|U9+!2qe)>rk`bBVy1lGzZDW)O<ZMJXY_K6faz`5knOc%124{MZuXj88>vnVE(o}5(P8g&lE;YE|U>bG-'
    'ftR^zqkOdKO&RgwSHGe~bb8LuE5)av3lxf)PO9<BFiri?iwg;J+;Q{b!Nt=V{MuCTc^h_bJ1K`%c}0?jv5p9~h}qCr^MH(azn!EC'
    'c)2py&0VvL(|fs3J1lfc<WL3~!+XKtguxs5Cc)&Ak_^I)_~qmuQqq-&OnkVFb2!1hL!%tFPbJKSxjNjfG^9v{g47b+H+;B^{y~NW'
    'Jp?faZ9H?;BY8c`E66eQD)8(;N0A#1DkGj!JXs@;Ba>4L2fYD1U!Auv+j&Q#t%gY9yirV2RFebIG^33dxDOdF!R3qglKlnQ4qdgK'
    'S4VS7?E4zo)F=vqsN2+YJuCo5rVvml_f>&|5z*nMwdbxnLuZC>?Q=1jh~gRy^iV?3&g41<0*VquQUvqS$kw;XYcJ)$?jK18>To)&'
    '1gU4)i|hk|Vi2KdLL}O2S!Tek1IUG0wKi|$?fA4{*{bsx3tcQGboBrT!Gghy2QEm!l?>q%RBTAkct=3{Vyw<&*KZ`^CHnR-cvbh?'
    '#c80({^7**npQALgbsg_w+3Mr{VJdYy}=*_+BmG;5dY;Ed9LY#0X&dM!oXJ_64H(~#xPhO2aMsMX_^?~5O3CQq@Fmek=TyDuc-Hg'
    'IUIZ8zd@^6tdbyH_9WP-5!OaIaJsY0d|;ZpV=6#l7YZYsVgc$1JrG_1(#U4RLTW{hso;-xeB~}KP<wwWGr4JI-Lky^eVQGkYK)oI'
    'd?%}GM1gX1$!iaa>RXP7CQ+6qGoTrdke7%UN#>)Pl!4#9#=c>>NlL;DahQ42S_I_GvfZ4euX6t>ls1sI`4%VnV}Vdw5fI_57!BqI'
    '1HeRCt>Ss*HqI*k*WDBeI`j|>ytUqnZzw(ncM66HWGD`GHH|`mZSeGN{WfsWmA;$&@Kk4A4qFJ@VC`v^B-B@Vv%{bnG{BxS3wsHC'
    'jzc@FJ)9>V@^dPL2G1CFx_vUmYM8G@+=L5^{nMyhj&}ikM_)GDt5&aLK~DlqnGoBOcgRT*%Z!m&K+ha>k}fFwn@Hi;zK6xO>|{|='
    '17(Yxllc&F{=s*KnRR6Bvo=Mo*J|n~^mEZRO1oGWk-RK`nWT_-!%lORQ3a!-v~Xsq4j{2n+QL^Ut@`Gj@peg_=L;1^9yzh?5%psm'
    '<>)HW%c3Q1;HO9uhWI|{?)KHISGdG+xM2jrp&S{s478^gkA#M&4=H@WMuWsEry@J&FSC&P=*L{m0jfiTl|D(*$nhfc?`d?yXvL4F'
    '6(4&{MVsGqnECA9{mDCm34g#g5$YXtUs`Th1YkiE;%O?QV?~)x_j#D=R;&(e*dXGBO;e0M3|>cEHW42@MrBZNaoGovX9>H-AG)03'
    'x*V{B&drFH$y#RM&Jdl^11(cH_<kXuF&s`NZgbU&idl6^0tD{x%D6>5SUTAzN#DRq7{qEs6l{i;_Df$BBfnd=CQ>i}Cduz{&>$b`'
    '6Fh<$lB&-d1PIAHj2cjnqSfTPRpBJ74_%-?b16EJ=Z!2S8QR9@gzkwL(P%CV)=JFoDb}p-R;|1t(4-iPr;w9R79D0}0X=Xq%6e?p'
    '8F2ub!HAV2F8sHJD`q&s)x};0C)qG*(&_+v2ug+nDd;JbC*A<segK5emOj<uckdJSyJKnIJb5u$kVbT3Q~`3-Y9=>0R?szo4>xhT'
    'r>p$wjYv(Icl$^643UMnhadk@&>sO4Fh`z3t|9W%t<+$9CS5~yFbW!r^V{&bmF@fW&a6oxASDxjTtlTY!N-3B%*Jz%s6g&Z8bXqc'
    'x3KE%j4RuUWzTqjd2Mwhnah}TbkGsfevxf|&unHK%5nm0W*2-|YuA1Sw=1>)&H+yx8Xi>;eJ@$0GD%Zz2?(;2gc(Vbsz3dzsd|pu'
    '!yV;eW-RSLen0G<F8pHfPx!bnjWnDDLEkK&c|?q&odJBIBh2tbKh1Gi<#$LKcT1ZSl<nis`2F3}WT~lOS255ENXagD0+TlwSO>)l'
    'wOc2M^m9(W=7653Yai}3eDfd2KaZDY47D?e87<z(6GV(a$xS*v$jlIbFmy#kj`njY8zJ!S^+$dz$oR<+f<%pJ%)B}cREQebLsaSk'
    'XK=M6Mj<&69MN1_O?+zo-Q9w<7rIht#UXiMH%+}jr;-_n(DtYtXcP8u-N6`eiT|{2I*?c0!RJtK;as@#C!6!1Y~D-@E~hWO1{gzW'
    '!Tu625yrE@abN}`xr?|CKrrxe_-CJO;_dhD)tB9u10m{aDuM~%+(_U<vVw0O!hOq73u<;JGb#q`ee?yX<@&|DZ+xe3|FIBs<tWea'
    'SSkRjA%_SP$^HnV2^Wk&<Tn!H&bDH$({Rn>|K9zt^svN(|LKlj3m7aHEBt&CZVDk`v0kS#x@91q0CL{;_;EpcTAe0I_<DC{XCOx0'
    'J(uN|SP;S!K~bxq&_YNEntp{}H1VEk90(CnzJ5sl{AkVdUki*nV!H;~F}aCB^8&h2p)rn8(Vi)mXlwyvKFkZ>FL}!Hzbp*8!t`yX'
    'rox%yf@|e-gt*a>v_KU@t0aFD1SxP%W8Hd@B>3_N+bySqN)fL%=xMa?@dQM}jm{I<7{2|Ds2?9v(mq)4{)IV;h3DDLPF+#(My^XT'
    'L1bvK&glLjvB2bl*Z_BSu3Ha-v}0-L=%7(a82<5t7;O$`ndhr99Tbpcg0imFK-lo<kqq0rlhMK9%hzqj+#KBQG`H<}SBM5U!68Y-'
    'R}tG-RLWr9@`EEJfysj@!c-<GfmT#3t+mRW2u9m86At5U`GaEBfx{x84ANYhSDllB3A5DxL;cj>7ThmDa>*E5;=%y=xRGxOX3D5>'
    'q2VHi#T=Hx4OVP}w53TEE51Aznfa849Rzeh&skI#+H%BotJXf7z(WCBGAgObeYRRmGT4UR{DTCS(|?d#SMf|*xql&pAoXD;D!|IX'
    '-O0TI)w`F}90f3M)~s5Uu?gEk&E)0EPDcXCC`)o{P=a@|(a>xrcpXfV>rInZEnB?6f@J*ktsqq=aaXKz1xPhm2>`T?V#aA|hgq}e'
    'sTRL{o1iul>@PQ8hC^^*;jmCKf}|llCh>*0N}sd&Y*~0icgyj(`{xTVN8X+WG*`S_(s^i@xOD^c$_qu#sPHvVyHGL8xl%fZ@cC2z'
    'Y~>o72*L$iZHNfOSuFS9hG6_c8YrI>DPFK$#=WXt{j0y00uy#s<PK7Ecu6Y<n%SgEh;C5%!%DUMIW!61uU)ueZY_5-+y;n)5Nx3o'
    'Vjm%aFr-s@3OxVV(B-Bv_h~q$8Tyj$Ai$8lEcT7hM^}<7^bnr;g1A%p)sVDWISBA+^T4^mdtA^Oc^}VJYnJag+6B<5t>f2V4<`3y'
    'ibKtyq@-X99JB1XfXIcbmaDnqfL!5YGQovu>lr&;;uU8J{R4dykN{7gXv9@$s$B3`$~>X=p^nAlA2p6#{h5Wzv&3;tr<kWnA5mcJ'
    'r%BNnV>sp56*&=m=T_l@;SSHTA;;VVkb^Rx_|L}zKZHudRxS6;^-VEY7_QJRdOv7d$mAK-D~F4Qzh`a~M&Js+M#i~Q)rudv1N;={'
    'ne#I73!q^$9uN>8BEAs}XvL+J5-|%?_En3WMgbK_P)Ma_4Qs~qd4Nd)nhl0eZ3}Y(O&LO5IBLVEr{NseU;kP&*H5HrG#0{AXK`k^'
    '#OY9Ay#UHeQ6{{Xy}0S~CCPubil=wW=W=*84=Gs1m`SZ|-W+WSJ`)}yKb-%Cfe>vY;}|~OarLU@aTtIFq|Q)>n7PG`3Qht}0|3Tw'
    'lS!eEXH6nuoApc6)Q`KIOEP+bEMB-|3Z#E(htcPEqP9=8k{xnB8TZHf)sYGQaS-M3`K7=C<p&dKA@<=dZSlK`RE4}=h<_w#LLUG;'
    'x=_DzIXu8a$|hl7uuPbPVFE@)(9;}Qbi)X{$?;)k_bb+9oqt{qx%ed@AVP2m>zLe-K7oc|^cw2r<wm5Z9ieNjUGyv)FVx<4af%0d'
    'q%2(~M#+~3hx4fP7(gE`5&+hU_p6Mda*UWIWssu>4uwHp*7Efv2?qP4;R??Q{h7lgxvO6s?2*pU(Vc`{e-@PDn%PDd$ZOIwlWstK'
    '>Hp&?4+nvfE+oveNY5+2u&3uot$bj1YGIZghCi;+=r$4Y7}g~gnwL!?_X0FH+6;gXWKi{MpKqg+w64HLBoUWEuuyL-M^Vsm0n;-H'
    'PKN&Q61o2oBd&;{`t!|O!oDqWXM14*q*BmeINl;*_SiGvOxdd7!+#BVo#|8k`tqmD4+NIi;C8pLG{2lf-0PoyIf-+>oYRHvS**IP'
    'YqK%nkM4Ye+y%|4ReBG~N*L@Q+TsnDa690Q_Tzv5w*P84S8ja(ZARk?ng_=M{*f1y2u4H41HLlhjgpB=tmdShTrfWgra#%p6F}+b'
    '8W3;2UObqXc!IVA$+`5s8hC~8)l~C|OJ#&kbLlu#)L}_Z+ngUNOfU;(b2?frj_)1uEawa(-<D%GS1eo&wh^<qiyFr0l6cANnsP$p'
    '*vQ1>7l`$AlEv+(wTNbLCI&EE4w(4zqV}_rY~y(ZU?9N|1l19a3WT;GDlcH-rxoVOP3X>x7~=LdzYDKYI*lNe;QdbYc5+Mg#zswe'
    '26+-0pAO2W`T1dg?>D8NHE2k>SRah0!4;n<K!V=Tw81q9@Shel1`etF^k7MFb$0^S6Xv*I;x;eC6OY?Mhm*vWE)y<jXnf=_NkSuI'
    'Fzi$XAu!yP1P>UxtzEdB%+Y^BKs|#&EI2-dytWkvL|=mu&_VNM<rz`C;7>L4<vJv2?DWJ>n=vbg`+=MzY4lQ%EN|2hBtF$J)UI5F'
    'e=yhp9z>1{!5sjPbu601e(_+Va&3_BGOyfy8swL?UM*+7xTSega4ChiMQz1^HgV}&Niu+Glh9$J4lODa8~87M{;~eNB(e3iyLh=V'
    'G+Ss73j+YKeVM)v{?hStIT_Rkd{dHj)h+s_K)!q`k#shiVh-Movy4dCGOc8Jz;Hasq^ZQ`$<?h{0ks6O{7GJoxQ7g~C`7l4IVvP<'
    'Ik3_31Bxeu%ykP2fqqo9E1eZpuh>^H;T3(k@Cb&%NJ7eJ&n_pWC|$1nktZH;P2-K;AoH#HcrbB8i!e)6PaBG_2cU;L3)5S8Ou1jT'
    'Zeef&DY)i0@dfj<1^^EnNhZ|fXhcxc(8!pn<A-%i!cpE9jP+WHl;}$XNK4cue8Q+@GcV_dyJVScyK>prtfn|Umr4V^8%q#_3A&<-'
    'Q(R&z00+Xr@xdl*s$07Vj3E1FP7(H3oq8EkQ-a}T`RUSt>opGz3YziNs}%`D00b23M!H^*XpYDb$Q~hu!S@jVOT%uM8*Ept_|fE^'
    'pCNbb#Wkphv4Wtk9h|;K+)bv7GAbFW9XdV6%$T}G52T-dcX>u7kR3w<C(+CF0WWO?-lC|@yguDCq(pAct5)0;QD+KuMk6ISR{{G{'
    'xYIKA$0>z07YiMrJYd=R;~|xWWvke#^iqMfsZUAA;9=2e9i1{5R6|Uo(#UB{-|goe>yMXTG#3RH8ubPcA3!2rkLpnazRPKpmN~&{'
    'RFL9Nhjr_o6b+XXB>+7<-HgC>h9u!60O<}xKSP?UzHhJR(SDwx{ma5j8VZN=tVb#cTr`Oi@rJZd3^3y32JQlsAZ>y<#Y`wJcvt(Z'
    'i_u?`H^@-HgFyvouF_Z`V?jpaG^&D>cU-iDfBT^S>wo+ofZZUb'
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
