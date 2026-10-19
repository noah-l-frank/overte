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
# f8b80ee176d7a1ad2a36b8158bb7d33bc7a9331d / tree 8506490282f90f0c2d9f37b7b0e12eb363e4d917.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'f6ff5526bf6626609c54f37726dd9704f64b6e8ba620c558a75d195fa9a42778'
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
    'c-qaK>vkhYvYr3?G4$J<uB^(s`6;}-{2wc?Y^X_q1Avm+XPtNVw+kTEJwqb1fcE9s#~QWd$wXCFWW<iWcl^h1|9IS<zP|b|ZWj;x'
    'ZG71Oxl4zK)4}bIIUWA-`*FYf?Z5rUZ_oRfe*15~nWh=6{q4X0cKqu2+qP{C|I?dx3MTNM8Z+jcIv+znG+{Ei>2frN{|~3{FZwU='
    'PkaB{fBx6^WjzapuMaQ#r)~INSk3#6|E?ho^Vmd}!ZeIy@TqCWCU=96O&$m9n(6b^UR?O*9@E30`@^^VwEy$rG4X5NX}jMY3yX&^'
    '=VTl2rareRj?S8S9+UHC2<_C^JcMRy#{Tog59wup+@AJ_?+@W?3g1dA_Q8&A=DCh$$}!F<r8)ODH#W}v(0OuQYm>L1uXsww)5Gy~'
    'drA*6y`)`CyRc2Ab$!zg!SsXYS9bF_4ZdsgG<DYXKKjWT-}1u!P_u4ntvK|4ZnKUF|BbG7u1_Nmy0g<fL^lk^dc%ADe66=vdF16D'
    '((d%|&sX=f&D*fN)qi|{e)@d%+2=6iX>2=hazER4$g}Bq>VBNsW|*vXW9Eogt$x`5p2F!tzx{Z9Sw5Dob-i;ogq+6S8`~Qj&FIV='
    '8Z$)RIcIFHS@z!#)%B&@oSHbqZjPqqtu{?F^OJ`-M&o?XL5@@7?FYZuA6Sma5T3R?<u76T<@dDvw%r}SJUYGSm+zmiYK#lkhtPU!'
    '?dV%OMLrrc_9^xgzdiTKjAPTTS@nfq&I`Z3uFYeYtV`q6`6i4lKQ2$+bFh4F$J~rllTrxl*4_K-t7ezSCUA^Q=J&PD?3%V4J8#3B'
    'CL6}=g6pSl)iXZ4?yjyGj2(s{W;c5~jr=?}cSAEz#&^l5)<)lqDd$yd>LhQ%*TeofZH{68a{X6Ny=@wvtm8BdVM-y*uJ7E~aHxn~'
    'eTZ|M%(`d2>|p1f(~-cPHizV1w!6ox+lYL$eAKBQEKxHVn>sVMe8|BM&0u<K2`OAv>$mapyb1eV-d<myZ#WH8*AK&F+;S}rUEB1;'
    'wyBS?<(>#5d+b)PuX{Oe{`w>PtLuBtSz~SN`;kkcZ+H^Do14&bLvkWJo<hU@>{hSO3FNB0x^@b=n_S;UqFL@nAI4z3=^Dqa6<lkk'
    '*x8|}`0a`)f4c8qcIl)@w>j)zPiYgk?s2z2p0?q7wCU!+EuF0CL!T_Kf1XluT%Aon^c=zHTSv+=uinOMe7U-CJB@=$rj3akWsI|)'
    'K0Dzu&9UV}$Xs<cjbrt~=Yw}yeM!u81W)O&)Aaz<^Rbhfv|Zm#U6-_}eomwBBVXg3f+3BWhjO@ma^!`l{qr_F5cdAq9=TEZ0Kd4`'
    'xIJwyH=b_Ut6yZ_Cud{pd`ev=8pden+1g1l(G0y_22W<Zc{j^fsgL8yy^>2_k5c2%h1kYnw!9BA3{Tvgr*_VnWT(l-q=saxxqUOQ'
    'q?6YpWem<tp&h2&^!#?$hj!#@;4>lJ>!;kiXuCF<oA>Z79d_wyv%ICNJDFS01Bv4h;^@0E+osJvwnJ~mdB{VW$C2~f=9_o&>~^Hv'
    'aYK&JQ9gX%eBB<Et6bexql;_EcJfUMgpo1zTxQ&&<O-%^hs|htO1JN7@A;ShC<L=1sB#ItCt6zHjw7enbxrKT)Fn<3acs~(y?qxi'
    'm&(IEEnoG)h12!GHbpzNqiv_5&C@_s@B3~HadJb;v2JZM$J9=KzIjXJRQYN9`1MpBYlpGRWK@l_z2|C4eCK8|<3#+?1BzWk&6Y=h'
    '$CgUz77w7O)NIDNYr3JGOslMmEQ?1n^Y)slqj+iK&08Sthy=UsAAH!G_eXR+3*f9c-^`i%jc3qJ<3!x|1Hm_Ys^n|}@u#`{u^dl)'
    'SJw~A%+VONw4b{v1TLXGb8Z6<YNVVT$G)5UJHDcmJ3OZ9TOgD0HZDZ6k34Wj5+Am)W6vQO^@OPX%-p2g-_ki-eY*<${&g2!A<%G4'
    'W)2SNIj^MwyKn=g(a;aUw#E;(afUj<reCzDitDLM+06ayhq<#|nqwatpD70oCwYn-V?~^hn>%;3+)<mVFc^CB_ttP>axqSAaxNx6'
    'ak8m$T-SAdPYvDQ``*&-kL_W<d*)v}zq;#XT`QbNC_(4F@58_q;oXqzI3zdumS@I|9=rSYRDFw1&W^65su+PxCNP?4scuQYC@(#^'
    '@4yGoj_j}7&Spyz_;|iO3Ynny69+1eZD<I@o|on4A<Pq(MaP}yQ*PPreOtTfmiHro76~zDJcFZ=g#^`!)7+XsE@HFoT%5x%+FIB@'
    'FE~l*feqQEZYGhpvmsFGeNH6Jgl~2`MB_8}?9|0yv#VqJBkc-RH6`mDdc8o3NCH5^^O_pN_0e`|0uAj5<nF%xR7C>PLpyhZ7-GtE'
    'm<Pv=>zaX&KLE&@ffs5hbMM^B4_VRkw&sk_fQL>1Lzg;gt}zA>wb^(FWWeq~+LDRR=KJ=wJ~iUKIdVpDkluHKxpD&zVTRUn#D{Kb'
    '*`aN+zjt5cN1Jd+V7sTSdpZ`-0ZJ}wTQ1sZ_M~k&^RSc?7*Dcmx&Q`9<$Cv?YEpuZ%b$b8|9}=bWBBIDs)6)DZn|lpKs9cRZF}El'
    'ZphxqA$>N383w*E%4XMRvj4Hq)+A@Ra$4>|(}w#tcHF-n0JXyYYXY|p*Rwg+iw#AQ<H-nROCY!dQ1z@5Acr~f&;k(Com)~?xv3~&'
    'L72$b0Q=gpr!vc)d!_|-iCqhRZ!+O&Y9?cU#dfmWKD`!z-pNiOxzxMH_Abycp>feWa+c8Ym_pZ0GYu4T=ea&TzvS&xdau^5fBqwv'
    '{?Iw9GvFX1<^U|iWAWs>jUZV%J8eJQdAd)B*W-zs<XifFC_$rq^W>L&-_|F?nVxw^VFoB|yx~x#Dcd-udn$qzn^BhCbY=t-ZRaWT'
    '_UL%f@v^?*3k%+M{R|dScl}>L>dQa5ep|#2G>~HfIy&~;7ZmgjnQU)-Pa+FO+fQMd>N4!d*CpJg!}IodTzZIClQBQf^dr>h$W!tW'
    'OoL`AWum9eWYZKH7l}D_Kl$rkZ-2ip1$<r5)Dx4NM;k0{*_O~oeLiu6$Hqk9I6jlQHP30w_0UNNtL4M%Xn#ayQ2^h`0B`}DWbT}3'
    'I`$Cj@~0h_{~u}N;`8?UO+sgb<b(J}YjPOqet=5E92}i3{%;4sWhodc3xdn4HDF@XaEVivsX!V-3Im0`<%<Ue5quOV*9Zf3XX(c;'
    'sXE69ok^{y$frJ3)k+5_+P<enO&_mo+URFM_{w_m$9_-Er!>+Go^2On2g=`%Rt0{V$)4%u(ic~ok=iVdD;7T&reS|bo8P$}cj<Z!'
    'q0mY&qt9W7NcA_2pv-fl%6+C8HBhIzkSj5|A9wJ)|06BMC|6M7Dm37dBW=~jPn{EtOIkzHsk;$eY^G`-X*|rXeh=%SN(emhrsK12'
    'XnoP7r%o`rGtTj)B`%-@RUpj1e*MbOVq&ItoSbTHaFlW4ixc9;CqD5Z+KKQ^-rdzNe2y;_&zu^F_f9jn<@#z3U*SY9?K_&QEjKOz'
    'G0+M9&$UbcUBX_!Luh0-q&<$*RanT_lG#r@cmVx|*KNQ_NXYW-%U`;E;pO%EbKtu(0jfeHC>mM_bp|)t07}d~M?Ya2X|&8YY@}}e'
    'F84G!4Ot(}PLeOO)XewLwfw>4Ko^GA$7cNzAYos)9DEAya2*Tso}08)mz7&35c2w-J%!Zv9Ku9!oX9j{^fzyz?n#V1f7WYgdOOGl'
    'k-x$=;Nd&!<HXHQa@CV(+^~)Br?2~69iXYhPmutq!}mb_1Vt$IBTW<wutJZC>X_$cZ+IAo^a!Ryp%OQL9^A`IDa#7Jq5RDp3POP}'
    'FfK>mJ9@%Y<jGJQ5E<MJ2LoW~dJ}dSsM7`(Bb|#@two^0Ot-D|3Xx){^|VPs{nGUb!92Rzbt0E!nh_~B+(;I5%aR<#-qU3i1tzb!'
    'k8a8e=r8m%y$7B@KiR{IquUvrpg_k?;Le3GbQRUm`IkRzcQ3D}FTC}q3#;mZ4FBQJMB)vsMn!aWH}vXMrSjI7^B2hMDHVa%1c(54'
    'XC6!2S7b>)?S|DKQWWv&$Bn7<*tnA(T^TrXREeZ%)F3S!B*&=;e7%$<qowwsPn>jWE5OmuHdZ3-WWE69Pdt`ZSOZsRj1yG5W~BAm'
    'd&pt*^C~Da%VqsWZoIxEsTyZf*(uFlB7!>Lo?2{76QnmjQFtPw%au#ML1T)Q8{UIEJns*iSN^?1*3!3p2;7l$T)@M^5LEsFwa(LM'
    'Ook?AC`Jk6wfi_%o(~tU#FyhC{J$oTlsEQ&jZX6UR?eIf6<ABAS->+%Z>I^~Ag>7SsU_ud19%2NIo~hO#zFZVr#rUu1|Tfkx}Nn~'
    'KekW_#mWUNP#!|fVc}0?(qZ;N@|htV-ME>B#Cbm5kV)OK`uN0w@0Bz#wLnpA;x-PjOn7V5-Y)k15n19;LBA^Q%fD`);u-&`1zd@2'
    '6GWia%`kxIQ8keuFpi@T5HK>@EuHw8=KjrHFuNZfTY-ndXQ$^yNC@yXLFyWHgK09r$QfEO9!#3;{TtiT20FaG)C=kSI<i2Ys)ao_'
    '(JeRda-vbUqoZNm!l#2@2;tmJ^Do%hjyvm#riVMw>bri*5)s;iMbot=)dM>xdeY_xQu0t^sCj7{PrdK&-_<$kAx8Yrp}l^odI!mC'
    '1YG3ZH3X{22N`FM8Yd36EvNvf|K#uA+M3uE$ul_n9DMlm#P4>Z=?}q4p_B%)x*pVP?iYNPmvnvmyi~HU{^hGX7TD2{CI`Yi+Y8jO'
    'LKDc49Dp$d07_gg9NG`T|AI4iz6z`0>ybVuQ37lyv;c_Xv_Pgg`Opk)5J|1&!8PgrO&zz73p-+q6oksR;-l;V7P$;5`T(>oAnug?'
    'H1RRex(Xz^JTUOp^nYM)OQuuNcAru-v)XHrUuVu9)i4!N0t@Xa5n&^x2>SdBK7uzP!1e89`p2+9fn-T-fQBYup`jh93+CPkkfvYC'
    'jd0_3-uCci-Bn4ypGE2Yb<qp1nz)(ZC_|Khy5&JFKyA%<^ILr1)pAi5ST};MAZK$QI^vY&QzY>Q#{$>&Z6~1u#OAx7&n3iPhjhBO'
    'rC8$1;X;NA0m2HOg%}TnKvaiTK7)4J{@%S*d}b|-8j<>-WQ?GU@OJ66d-7q_4WOIBk&V*N9`D}DrGEJNV=F{}M&(i->6|zZ#NKty'
    '7$N;<{;iG|rj7~#_`O?Ou_Zu303V_vd@V~t<waU0|1)Ts=<6gu3LbB+RFiRgkbvm2v(%=yR>T6xx^OCE!I^GOZUWs<O4}*S%BSWA'
    '1Y+pG#KFlaYuwna*+Z#_rAng+X{UaqJfI*zk=KdKOj{`;#h{=Z(UR5w?#f0J{oV#OgU$5fp$m10PG)L&$QGn*5U34Z2s3|lIJy4Z'
    'E|*Y?)Y9OG#N|{J)B6Wa<cA?z3Xonrr@t9^(H}85<33P}lV!T6FB_=(KS;DT`e%iH9m{fn(Z992&yokf>QR(%y6n(-F~z&lrR&Rz'
    'a(Eq+nPY}_PG4Y3BtobvVbD@>dudlVGaUhsURHN~nRCLk{O3ZickX;In8oLQ99k%YXrV@mwvH~9qJKg(6F>M-g1^#EsQ4FmIBii*'
    'kti=rms5d5PIew)-hl>ll_1AyOrTfPD=ikSvdy%MXqR1Gaycm^=KOt;&Sq2#(9nnQ8{kMa@L6L6<TfM<_bK$K8HoWO-Le0+;F%b5'
    '{hT-<dwtiyQUmZEX)_KGpg8f}Of}G->*7%OeMi54-u%I>9m^>VFy>56-ScS!j)3t){Q|4W2qb}bJ(*$jasH@zea=>5`eUoNNPYKm'
    '(&{ydUL$b=G!g-peDFz&O{lsk^SLBF{P!l(^mL^~qkB0?JF`TXe_N5K_xE$<sWrStxKR@*u6J~q=wE{+5Jtz*#0lgSc6;55$9Glr'
    '3q`^EA72k_tvae`i8;FTG!X4TUI9Wk>|lfe+|XF*d~i4J;N@le`n;*xNDy0_Zc-YTHg1=Y8%JWfk~776Xu(hzT)%Q7RSyBa%s_k1'
    '6K}1Eq9b5H3ps-P!?lAClSA!*)Nt+EVgJPavOlNr7usX_>~~hky+_T4V3-1p+MnhH@Vc0M2vX=VPh|OV?QRypc=MQOxR+Xv5WS!n'
    '^DWTLC#+fJV=x-*l#ndj5hNK5j;gGB3(GmEdKXX%B6PD%Koixhw~(ze8l6_{e=sB71DIA@{Vx9hcn5SYo(oGtvYkjPU?eukYx$i~'
    '0dOSL(oUx;9$^>IdhKeLjOqA|?$u@=UZ1vqRXuxPRV_{53g~1Y<$=aSDNg5Pw$RJrGC^QUV}Iio9$#KJU*ShSrDFlsq^B4u9?|{N'
    'E}_|PY)4`Oq|>Rl*21ylZKUQG>;qCX*E>}A0?&vR4N(E&7#z|eXSMyJN+xj;EOK(xHC<<Z&4w0$siGMzFua#;qeH(RBAs8<5<Mzp'
    'qzXx|Fo}274L9zJi~9gG;<)|B-@g6b)x?V`2x`h~$$@546F{bsjx37IIMMBjl10-(Xm8xl8G&%$p9pBGk<#|FEB0qdwSo9ccGTpd'
    '@70~}p^zkOJgo9}%onJ<Q-AAcwR%5TSr9k^+L3mesU=|1ppxL3MQU(DY9RUUK6DlNct6kk@U80Oc9VKI6xCxV&j<81v{a0Q{L(~a'
    'u@=bubEsYTQZ4%JE|%DrRH{;j5zK-?m(CfLvk5}|LD-ogxFSLgL-qIkvJHFtC2#*a3H4vV&+BnbnjI24@(6m5DvL!IAe|KI0dh<Y'
    'Le?=(>(>99GF5%8P^LT4O=%v%8dIN|df9eRiQp2^8y&^&11MX!k%O#O4)vQr#zZM38yyN-AUfv(S7mmCBnFX;nGm1?ywq-j|5gz-'
    'R^0JcDOHpT84zstP>8rxNk2KC$SQJzOAs6->5V%$=R4KULy8WnT)|w3fGOhXgF_sVzfSHD!*v!?%VewX`akyk?PjqwQngx$PNY>0'
    '-Mfwm;6-6;l=8DEVF@}Z3LLQt%WM0}1!q2f4jptYtZ?`sX0SEj(B2};@*#nRa$%sjDJ_U#=KKFjRnjYZ?w}0%;JL1N(Rr4}sReTw'
    'xZ%n44CpoehtiUZ6z#1pFX)74DJW)o#3s@2w@rdEg(rZ_oF*E${3XCpDg~T6oiv>%a3=%c4!5FJ$C~OJ5fE8R0Dte#+U;O#7h8Vm'
    '{?ZQCf83n^4KjnLingmjQ;u$=V#fw!g!m!@Aj)+fKHMY@TMOYMHn(hNyHn#A&V_%)ck8fudG&8xnCp8Y<a7A~;(|^9-vz*)Nat?C'
    '42f3yC>YPf&A)3;Qn#U(N>5x%CFUBYCDI}czzaZkz)}G^H$FkA?}2H$UhFmZktNcK{ru3rAw9_Hw0*vQO>qapU`Ibf*^4?@w-pjV'
    'z79IRd_dBek^e?_%dVbyI&^zeDKzsI8a3&0<eI2?A`i;I5~2v96(_+RfCYGnxn&Q}OFNL3L}?Fra|wL`;Q?SGeFV?r!sg6in#F#I'
    '#n66zyk!rv_hAo*Sn(_pH&Z9Y6Ru~R6ySE)F>p?>L_o?A2jmO@5@Eb$AGAhQjlaCogReRq)Z8<bFiHbHZ77B?8%g<b_FzY}i>9nw'
    'YnX3391B>pIp167FZ=rYX}FsQ>Orzs*jrv88Bi{qB`5(f0E13Vy6x)$o8KP*04}@v=krs6R7Wy{yaWOw_X&nT)H@dcFRC<1ON4xG'
    'Q;PQZ3$~&^yN(%Pu`-PGtJA_M!;gr^LX3eJ3v+x-vvBSy4!7?`tjwe1uoTc6p_riGMw%2vAz)j)Dd1c388Vs)UlZshDc!P>qkDcq'
    'lXet8_}tnr5%>8U@I)#sJPziNd`q^Usd#9i`5sarjA{-|x+(Ubq)d+$6@XRE0c<qV6CXJm^jGLZIDiD0x)ziJgdPmg-?EAG@d!^8'
    'V%PToe@rrw2zJCVK>#NK{|NF6<U_L@a2?*=SpV6CukQ3Fqj9I=w<4Y}NVYi2beBoB!Bqgdxmh5i^8Lyr5WAcDaQ1HUc(ING!u?u6'
    '2p}W?a3%UZBYZ2h4QN-wUO>`<O%snpkjhja#Lgtx^X;<tQcKcI6;aK-6p|#UpU}2RKWVx5VWLxm=LM;e8mPonYVxl4_1~&uc=#Tk'
    '(j{*TfiFb)+v)4#2Jn>1b(wU?P!fiQ(8Xm(KM@cVvVd+MNF4M6K?aQbMSH3+_JTBmj~*g?IU5pYk^To@FRMSDsh|OTU>HunWJ7U_'
    '>)xrrcyE!g2YP8VdcADE1`(|Sex3>T5JwBvRaP1IOLlZf|9maQe8|i?Iz%}9yfArGQi&rFACy)5c0zKCFvgDeZs=+MxZPD@Edy;b'
    'uE3-V8mmiAHfXga`xjdldrEFdE6&TkI|BVUN~5t0sp>F+ZV16$`iOK(d1JE~C{*YndhBhz1kBt@cRwi_j_<1J(w=xfyd7#1T25H7'
    '5{|HDbs}Ci%JAU#W>Sh2@7>ceow%tU!FG4<<@j}9*cGB(3s(?imwx9UM-{!rNUmwcu!tgvL(%?ayLx?j+Pmvea~29u0gsg^Y+igo'
    'C`BOVWQfmnqJ`8$XtG0l@19QkZ)ta-&0bHoz;MNi4b&^HCmTn2NHl_ugZydk5WKhAp1*lRF&>1*A5zl4u`6-}xwa@9QNKWW0nLMV'
    'I?2usvk*9qlWn<Tp{?Ay9sYqD6`QZ8(@RxgA|%o`Z5LhzUJV2T3+od?0{06XOI)Z1yj#t1?}m=yuzjhy`sr$Utex>D2|e{C8dZ`%'
    'Kv=v&DZg<Ck&2X(^NtObX{Pi@j2sB4C}T@zOeITojXeSqEqo)nTo6(9{^k!p?w=iTdbvLS_WHgauMOwap^SlrtDI=T$Pre;y@CEp'
    '!i3F)jGgY>($iK_+X}RfGG(#}RkJ7jp^yQ^iXg)nsZA}Z;v_W>5y}3F{ZQ4UZOI5o4tB8z%j1F|6G7Sr`$``gCNdDrS~Ub|oi=xF'
    'NOC6p<*Fhy;y#!X5PTZGX)s&LE#OV~J`m;Qo)*cf!7932w{&J4y?<jrD9*0Gx?V12mOdaR1dcQsP3Wk;Jw*=Q8y=Y#)oJsqwxz#9'
    'WvsAdB_-jt$;k>2Cz#2w7Q+Y<h%ea0+Xb0K$=yxAXkWQ(ZzHGZ1mZ|^l$OZCRhHR3nKwinVkKxKM)cv%4e3^`u(HOOMd2vJdIb&T'
    'Ku@$IX7%DIQ=#WTN>Y2s+_{@G%kjWRcY*;~R93)pg>Xo!VNtT86F_=p#OtP7#9>a>NjO}<G`(|Im;2*&SNX8$*n-QF-*UG*N?7Iw'
    'xCx$!a2_Cd82Z2o*p%M7t;hXoFHSiL_hoN|Y#SoG1h1(@eQm{Zgir~A!czdyS{xzD!5F<cdJ9<)A6KyD^>57My+OuLXr|FBY9)<T'
    'E;l|kiYCBh+M6`K^Q{|s+Q-Gt>TDi$9r3YpB1fwSg=Ahd09+c->Zplmdu#3jl{Jz3j=iWDy1b-I_^!H2fE|o5ZHiZ@n#}R&gvhlt'
    'B6wBuCmSh}s7~(N*dn5i%a<1R#a4t8G}1!|6ZqNAP=JGo<uL9L6;i~h6}o^!x9;fzi~RkV%3B)DOa;q)2ub2VNibZ<qVCd{<tP&)'
    'b*Rnl1qiERw|9AemEedag_Y@uU^|)<INRgYJc??I{2pc+R9}(JZ%#{gdo_-P=AnP*iIo_?hWiZOe-KwOEkXrx3X%*918|LzoCz<S'
    'o9mDLl0%-$Avm+Ig{X+41|tTDq(;VML}~crLLk(5Oq$XV03XxMH!RSijx{wuA-fK#0kU$kN|yecNPs&IO@I9XioJjb6!UD@XTE1g'
    '7i);k>8o7#u5Sl3;6{B4mL*w~OWMr(bp2qOs^<ke21Vn|snMk*qYffELO3jw4y4WHTZerQW;K&=qhR3ZAop(R9<*eWBTbE)@3G}3'
    'jdgcN%gs((0JAn6^T}Vy6#=Pf$<xioT8qvXW+%vAZr{st$0O~i{n`;FT5^2e4OO8HU?2F8Bl@7SM(arjgZzVeAH$tH`s2C6;6vUa'
    'pe_u4YEuhNJ&{Ah)E+#x(i*oCNvvJCIS=|{QsVlD(6mx|-!)<n&4R2ujlE#$N%oN3S*ot_m!?db-5onge~B-zhIO^=D2vbIEQ1GT'
    'HQ}JwE!81Iceq*kR}m@%%<k^l)OL9~srE6=2Kjc7D>B3ys4eoqgK>pLoRvWg7>Ep6y7|5x?JMdr#{DQO6LXhIB+NX5*8^aNia<t1'
    '@XZww$J-%K?c^kkVSgx44y}^)POc6k<ZZk&kv$ThQzCC|RT*YU0Ponxg$x)<dP8V-FpKdi1H;EM2n*jp^9TF5F3J>zPaY+$Pxox)'
    '{hlHM7V?}x#f&i}2nQ%HGM1siGzZ^G0wJe_s-D}NPyAPGrraF_0Fzn>y*gj@C<KOfC8|~6A59Enq6(fM$=|UV$qNhGDMFd#FLKwz'
    '*01kmwih%Bj#L?T3<;RSgTRM-c5#wh=SC#1A{IqCtd=OvYSJkZQuagFm~aPTC!!>f85PexvG+ZPNN_^X_!rEc@Yld<kFi>C(PtWl'
    'JQLm;O%-d&bO_M=QNB6N`aAdBERD^AkRKOp^oT(3kjubMc~P4CMB9RrlambSBX{~+E=eAYG!tMcXO3+_{6^~y_d%<nh+bZ7Fpa^V'
    'xFY$M;pu=llVR28RxeLj@w^!vEdROK+a{BAGN*{-O+c5l277s<c`B-z#I8|83=89W$^(4Tvjq0%{=^%IQf<%z$D2kH%sbE&JHomI'
    '&V<DT9S(~YG`cN~hJFQH@yWiH5}|rm$l!xs7S_PHM<OMrvx}7n*08ON>}WX8JiyW3ysJy|q;@}~!a$TB*#eybedjdaU?#xPM_9=v'
    'MKgmzU&h?LpC4J2wVNX8)3{MpPf(QU8pvZ%(sX_Fbi+XHv9no`Zhg2Z{j>T#Ev;`j0LZ(ckCT`J9D;c@3XMqAiPVj#<;|^o3I})m'
    'iY?@Be{yC0H?R`inOPbNEIYtYA(6}eHNp;~UVwm0!Pl<f$NkH0E|^9Aa3J2829+}Zjp=_117x8sB5}M|@G=L{v=m!6$AF(<r^-#q'
    'Rw%-rKu`zoUz5_X#BZ3T1g#q@Q8HyD$u7qGHl=E~+O7|ul`fx614)i$49=K7EPWb^<WV@dbVJ>6>yF-$l<Ey(?ArQ(@U&05S2f0|'
    'VL%$WAQD8Fg#2@|<eT4{9*#TG?OqWdsdrnlLu%n(eg=#yCH<mbN}k$d&`+(-y)xgrqf7ZoKK1&jVF3jw9+U|#JF~CkUV;S;<m9YT'
    'yqy|f1JxE1D}<86-P<|0bN2Pu8@)HVZgQBwowBYuW=%>vNwou12xiA<UE|Z8J6n1KwR_U6!Cne4dUFUJ$jE4|Kv|#~wF1P+B&YGi'
    'aXqW{bo}~yQo>k&p8%Z_kc{kFp>}n+EYa-Y=7l(f3W{O_%?HJ6^}a3}S&sJcEn<e(#Yp-DZ-EqUdp$Yf_DaAk)Ikg~V{KeRp_?GQ'
    'rSA;*Vza#C=J}o-?fvg0O;o9bO}NFoSTMqnp%OY*^k|s#!+n$A7@-_IEJ_25_?Ww8O~UlSo__kHVrt1mQQp)f6MLMDFvtLD!D$J;'
    'Bt|uh+b>TM3Tyq261LyzL9KXl$$!l+ucJ{^Ku{<fKn3Y|$Vak50?60|`0aK5Vcqee<;rK9x%9g)Pv-J>mwNvCR-~WH+-1z8V(OeI'
    'q>KQyn6i+7z`&vZ47GLz-T9NP6jOgL2oM&S)zbM;CkL-4D#U!Tz+3sO!PvL;-_^-^Aj%8Dc=^vF_Z|z(R*jFqYmuih$QchB9*9^L'
    'AwXlsDbH{dV4BiByC^*gA_{W|<Tl6AL|m6NF0Iv|5)2|Sdxe^aPfk;xMxT%7ZmSO%Jss%Vll#7qt_vD7@rX5m8$-EXlwK<40o)04'
    '0wpxSdr$4Yf(&)u2U0$FxLDntRV1bQ7`Yb&Ohpj@jVwnPFl`7>nz!CT1;<u>ob$SEV9mWbIAwvGNBy<bN0;d>ikhfY8M7vY5)jvN'
    'BfOTO0rY1WQ%&|Wt=|Rz{jp%hCU22Za{=J&0$jih@q#I4T{ZA$k^RzXaKo@}@$)OtF{pYEuqwbAF`<LBh_wmcq_m@8fx~0OL0#Hh'
    'h7j5n`nZeCO8S{gO;^_PK#E0Zj2SlUSI@LenBKI-1BnZDE`JL99RgwR*KOhgd%hinf&(3eb`tU{qi05kWYO{{xbc+{-3m||?tqzA'
    'o=5slI6c)#1C6GmL|SoB?(oc_j)g$osmY7?4DV<}jn2TZv~C9wO58GWvYsD+*cdV(p_wmIhKlswx!Vz`5GOTY0%QLVP3Nv|W09nk'
    'r6Ar&e}IbxLY+a^1O#MiYJxWyNXLi|yf0(!SH6Zzi2mUbR9UFuWzk3*I%%@5!XqQv7GW8f2b4|mqv0a?m2ZTemM2u|3oR^<1{^9s'
    ')?ccy0O<fanE6GAHi%NgZHnmyZe8n^f8CPlolb?rh?b3ChiAO*OJFeiMFu@6&J|EtMCuI!?7Fym?c<-@Qg>Ptazz5AERZr5dk8Uh'
    'HI<1<53>=VZzC;q_1bc$Khv6?WnH4V1<BWVPFYNrT9~gw*GXUixGmioC(a|l5SH6UGZgyv&YcvsK}=G^1Yl}m;L3v>CtXd1g)+q0'
    'sKt8=C0Vw9{Wi4vh3i#GtzgK{j6w=^qb589+2DM~eIcU+S%7uImqDIZyc|h_9>nAR{!=P}PhKK=Ef8~&4~O3$-^Zj)>3_*+q9%z!'
    ')g_Sf)xdK?sXN%)clG;zyXYzwjmIWGxyOPnvs%xz$i*ItQVPf|Nf*6AB~0!mI~aywwYTr+tP6$hL7Dqlnv#R1Ue;h`T>c1IAWL|P'
    'Whr1p`lhR<nGB45pKsp|ti?SF;>+7(_Ch{DZ74uFboAts*LBjF;3GzNkIRlZY?H=iNX6RYO;ReDk^uH)RFk89^;cm`6y6n`0%(Uk'
    'XvAZMHv*Z1GXp&bG^x>y)wTqSroX5YmtK681)-GL!Woy2GnR*VOcP+6(Jk3F%MxHgKf3Bw`78?A1YcqF!Ds?fl!CF71-=n4io2Ar'
    'l#&_W{!*!aX)*naQ5SBV-%5ryS=3mi5;z}%5<tal@s)@S(L`7PJA)b4(4I`?`e(GcU=XP3sx-C$;bwplx!Y6E;0+bkso=3Au}V#@'
    'T=Ak1cvI8X^xBw)Kt{kNh0X-CK(uDvpzIOdnYuQiUHVPMT>5PX`vbBKP`~2Tu~CBsD5y0rS+h4$Pr`lg7oh?!LX4wg1a2{7dtdg?'
    'bGo=EO)A-y<3UG9lhG4Q3ZV0f6P*{^Ud#bHi;0Adk+(2kE0@NRfiLOrM=z%4{`yPD`Ct+eO5?tRq!67<@KB0?b;2|Ooua6Y>o%|m'
    'c?!d>pgO^gz^BD&Ac%leE7!Rwk3s`GfT8GZQ~Su5iOU5dDmq5WF%7l?1|&$~yQ!gL^ikMCk0^wxuSHSAb}z(Kf%>nPusOZ%O5SQx'
    '-Ee1t)<P^t#+5Xr6OA<6!M0o@rceikqU=@cF36gmZh4#>8GgS=B&3YU8c9Ju3R)E;RfjHw`K_iGH8rb#-vvYmk<e9XPa{4Z1i%10'
    'ii&K~L~Yiib)}D)vS`G1yCpfUSp4FrdbTInl+DMvfw&Rq^EgecZiS3N@#PbugJ&`{Kw2>pYSb(ZsGGm9`{k_C3q5U^c*NxaJe5iE'
    '@I7a47wXUD^$)gaFY<fZeZ$`T3#=M&7_N<iPaZQf7-69~P|%N(2GIs(`1lY&aEZ*&<U=k>n%)*Y&k5JaNH0!W-aZz}{$5jcfCHhH'
    'gZUuxAO|4*P^zuaiJSq;jZnGzn|=A)jA>G#$5eRgc<(Q+j;LLiM~p5QGz{PDUha;dbi_~8f^+2-79!{Ns<ADAEWY*->>(XH5xR(E'
    's57W4;NK-qUZdiqC_j8#@zUz7df7NL(&#~?rqR$~d_3<YSOaPdwnJF%VQu=M`}5~3uYBVM?E@Jn02ji7yo^PK)yqxcdSxm@h8Ku)'
    '%d}<-70(=H1+E4h<h10NTp8$`C;-G>#iGhG!#l|DudwVh<HTIGc^Z`>ua;}k;!nVTz{#*hPen#Vr%P6y^iVTR)6$~*_$phG*Ow2K'
    'zd!!WnV3O}N2Y~!9KADU0B3Qrlng?chGVH&)5VJUyy9`Oh(1=;r5J0{jB16K(P&^Sf`P{~@}A++KrUjWw0g3muU+^>N?t}Z6qL?1'
    '4a5|f)z=v0Is{3QOn`%|i5iHD5c)V%WLdl~yL7^ff^Yn5K<()nKwctRqEHiBM>0YMGde*N$iGvO6aK#HLUyV0i@_caj{caWVL}m;'
    'M>#RWUWFiuy#s9oY*_IQ>nm4QS+Om1s|Wcb@JBP8LMSUOnV!-iOn&8y$tR5KuQ7A&q6?4aO>Bd@O>&^(Gbj6^RwJ{+0u0V2b2wnn'
    'q1Z;vNl`uG+CU9yibT4%O<d?R)Q%;EtrhUcEeZCDfCaH8opajvgL?T4I@ZspnC#cByWp`D%P$3W??g)mju*CzlVZ25fjD58#f}m~'
    '$t8vaEmp4mrYa;QyS^+JAtQ%0xs;wIzh1l(X;qLoGL8>jhCvt>r^;pX)Axd77IP25w87X3$e?@VI0Kf-wEszZJt|bhxnKpA%WdOg'
    '!Q{SO4U`!`oi@IPW;enk=&?*HQ73?1p0<<SEGb~^aXL3#cIlOJ@p?uNo(>uYj7j^KiW$E@`6Z*?W=uBR8A=LL?Ag^W{QK+k^)uAV'
    ')=;yrQK=hg5%8Nt&^suvl>sAOWSZYHRIYa(Lbf?RgFsw;z;tn(q@U6|b{IMh%mbb!ZXzW%Kyiv2qyV{g-8cGe`PCXob^-!0vLsk?'
    'h)~9WwNSwjAw^rqs+}1ZVfD(Dk%~{2&Izo8#E-V57&0pDXn!-(2&OG^Zd8rA=!gBj{(k?h(8pYwwOsI6(a+M~ctq3qYG6|fGfbRc'
    'Mtj)WD4}`l1w|AejU18@WOMN$R>NnH8vr<*NI?oqbq?>^)~@&ZblNU+O0SoNj9!ult!Q}?@B*vNYT;}CCSW|q&9rOU>httA_%l0}'
    'uTy>kXcL-}e4zy?YZMer0%ob;vWGVp7z9-_uutU<esD;xTAp!6q&Il+K={Q?RerQW@Bs6;{gO}^dSXmss9gTyi;T1S)9Gsg4UpIa'
    'Pg)!m(aF%2#43sUl=w^^4%hu2B0Ex*%7u>sc&Pv?f!TA{Mo5@JUZ{9pTEPyK2QaXxP!%@EZq0%`<Kl-4??4?c*ozqI^X<@TV|bI3'
    'w?APENgX&F*Wp~fu9#F{c@+RPu%Xntl*2&LqYwx=4HLm|s6YmV8k?p4P#dM+-HU!OqPqUmQA31b)GQA^Wll0eeb8~BQ_eU?9cK(V'
    '!PefvXUrCm{5w3yZ-oq=V2EFtxLH6CnpZ_m$-MGRkYPLGP2&Ghn@eB%F-v}x3bI!#LqT$nL5_bktf;+Z=eiIy5fKtaDHv02$#QOT'
    'U;nK<Q|v)Au0u>jqUID%%@|Hn03NRL4FI5ih^toIz?r#vAA-Q*tB8ZSrt>ngg3E&CVam3u{4vuTXxt$$Tes>t<Jlhf6?$HV1fl-s'
    'C$^GKjbikuFECR<ahWJH;c9kW_3y^I?7aT<%m?>7N<du7kbd$(Enn3l;6UF;<CY`N^vqBjMqXbQDDm}0gqA`_0Ae<e6?<Yi@sZ^8'
    'eA(0r^gq-i0ZGk@Ewwkr*+a9gWZ)}hu2%<*Y{@PoWN3^wqUbDgE9w}0hm+-8Tdtf9BV{Cda24*_Oh*!nm~*UI0t-=`yLr%T5{WR('
    'Ld%S$%m7v3?ytl74S(72SFFu91=7qc?jG%C^oqj>+JKoWHeRDfvZ!35hCw}O)-3!ssp>Lv<oZ$TWz~%@9XA#HbAB#JfV>W@23c5*'
    '2PclV?W*-JPW^S(^)kug$xD0(lZ+1M$c!FQUyY`Vl9vVa*{0~$_tOq8h{Th;%nw+<fEE-yI`O@k5SP&q!TJuKG(;*L38T?HFoi+f'
    '{7~d3{IrLvg?Y@h_r1V2v^Dgcplb19tHnx>2*)7V9CyL4UReKjff|Cb26!eJ3oJ%TWK2kbbZJi^jlcp(1ViTHl<tu8{FthvChHug'
    '{bqntJ|#{ZLLy|S)H`XG=k@^mS=9ByiZ9z2geav%jM7P%i`Udhs{sW|`Ok0+@)8eKQElY1&Cy3=D}TJ8#2Z1CK-1K^t`j>W%H)xb'
    'In^*3HUK8jbg>B_6nN!iLZD#rvSB)b7Q(`i8BowCtGN;)EkphC#gFFf-LQNs3o+o_Zz|||Kqax_rdA~D<kvHfp4kt?Fu0F|Xh3=*'
    'r78LiA8AoPyZ3>N4{tyF-S)3~Xd>EfCyNA)_Ocpl3krghOv^+_jUebFau#1^!`5u5W~d?xW*k}(&{55!CK@%gfx3^h7(5w&5{)N-'
    'FVo(&ow`Hf85YG%X2fW4NYva1aYMUjBunYol<t_WsI$JllV$wli`y3F5t_)PF&h0UL|a7yY6CdjiJ6_u#}O3`?pM(_=CT#=b=AH#'
    'zPSt@WbOej(0J4`<dMq+K~p1y!An~OZJ9XKyHL0ANtG{RdxlczDHKZ++P+>s!A_!oTGEq5|48(h%)-%}C2fdf_1cRB_k6Xd!(kak'
    'L9?)AVTuhlgdq>12748eJEWS%T#YK22M+K|(uEp!#U@r#m}Wp`><2V&lHyEgH`ZK@DwkdmG<-KqJInJHe%!(Duga`yetw%6nrfwB'
    'mGc$M2l#!Qdm;Z(dPsH5nI^Di@fD|!Ch#m)(ZT^$3DZah%_k_YJ+M-`g#vJ=6|1j1g2+$_LKF^&i7<`q@Mi>t;-OH`Xxw!GRAf|8'
    '>6V9wo;N=XjISR|1S=o7wv!MXS{ZL#6ME=5HE7gl2{|AN00V}#8@QyHRkKh5Bba*}q<sreLP+$PRyHX!fcrDkhoW+Ci-WN~+d}<3'
    'Dn5WwHZ>H{G(boY;Ix76l6`qiQLxJx60>$2^|M&BRQJRi{$JFJG93cp1tLS;71f==?Wb3d=C&QYv2?DNJIvgI76Idqq!Z~BqiBVb'
    'L2pAPft^jK4zMetHUGASy6z_m0jy41pI~t^{*((4;1>v*g+ZWcO^Tpwic<1_UHxZ@<6?kPNWDQ#<j}*UQGj5GBDBcJ{nbE{jtBgX'
    'JJE)_wo$>fgbQWnK($RSOtYQ04{ZstHr{|nLo}FB3|u>zyY^8%nw9Y?R9~~OD=ZLjcxq*kJ}ZT$iHA)Xb#d;d)tk|T)=k~WFI^7!'
    'v@tUo?bZY|PShq=Vzo)@)>0kGlZ!ih^&TMh?9yXdd<kC5^Ou^fmGKP2OPHoc9uFB7g9x<h-2^aHBtd+*fup?aO7{g_c%?|FE@_0!'
    '@<SHACCMZf>q;iO;QBW<acziro32?kMUZ8tMI_P4tT!$6lVxTTh#PvALF&)2`c%Gcp?X>^OtuW!-bzbD-8lBkHBQ|lOK6SJrSGeG'
    'J2&p*eK2g5!#P}FMj_=^W3*ej@pz?^<P?yA=rY53(-6?st=-JIr%!qj;3RD{t?E$d5RRlS6f+>-0L@^Z^ag_@0FA~uI|qf9#Ol_4'
    'Xt={}$*{PnisMJ=wU3%@7)>LiGwRUAnsykJ;^uMbzK3Fe_>;YyGi-LWt5D#<$;wnU6c%#8=haYo!MQ+@2=Ngb1}6zjU^KUFrG`O{'
    'gJIARMEvgY!sD8w3Jo$ahx)?2-l*x?z=~@_7YIGhUZqY5#4WhvbU|QIlh9MoDOA#W;i98^4%LX-s}F0V#?PXKO%?Ft5zfO<122SS'
    'j9`WC2p-qS|9X9|P|FG6pkDpTt<)K2aXT<220bc_RC+Wh$7kiXvi(K9&$knYzFV7X=cn!CSI)xg<wAXi8CnoDfWL4Gd$m;=eE^1t'
    '^38w@jbdaoF@lDM2*Yc$tVe-;J6WMB`Q79LpX;`$<{(JYX{ON(tUh8Y1{OmUYe@r%Vy)_t$Y0lPg(wcO!R=mOI3`OixZmf(95?z1'
    'bdyN4ARj><g{;kofjbp!j|OrHebO$(wGV|EwY!h5lAromQ2lyYuYyYQ=;1cd)525^&vS5Y+Qj0gw?&lqUzh%&xv{*EHD=I_rpZad'
    'uaPDgvC_#y=>vVYN5W4}jku1-reFKXLLgtq9Ea6O!qXTE9}NxZAna*;8h1XrMOaOQ4bfrx+xJl<jWM5t|6$BKCQhKxtw^s~J}yi!'
    'qZSb-65816dqi7UrI_gC^9=Hi!L!jI13YPYI--Q4-1P}?7e*P?(GB}pp`c(95E<OYgo|0Y>=2%rQPdDQC&d!Gxc@ZahFw%@8R$LH'
    'PbLpWWk?HxVY~c4l&P~yR!j$&PK5Wz>MHFl@!MP^f29%)4%CczpBfd^j&K?owk7T}G;>-MNFq(2ATX}o!#WZ+g)p8gL<_!5ZdRyo'
    'NG%&Dj_{z7L{Pvv9IGD$(P42Dy0l2kQx<W=gLw^R0)j{;jLJh`HpMi<8I;{PdBd&#K-Nr}4{Alhbd;A8!2u2$a573onA;S}nmBBG'
    'w>tg3?0|1nA+&1fHH~7#Y0%PXQNk}Fn&aNZBoCBwvN?-XZM0q5+cxsDUqU)J+ctbFxK03IK&#a$m28eTK!FO<4XcZyNi*lONHEiF'
    '8(DY?H7}+isl@jok%{A=q}gvCO~Ry;DNarTb=TCzwb5dy^@S~pv4MO5KjdQpJ)pDLXlfv=MeZ&(KqDRh5yn**>2^i)^Q%9VOJ8+e'
    'LmTxK1QCkW0J^FcuBi5~uG!b1(WEdQ$%xEw+g{eTwlPWsayB9xHrNm#xuXq&OfAV0gKv6}uXj88+jev2(o}5(P8g&lE;YE|U>bG-'
    'ftR^zqkOdKO&RgwSHGe~bb86pE5)av3lxf)PO9<BFiri?iwg;J+;Q{b!Nt=V{MuCTWgGVIJ1K`%c}0?jv5p9~h}qCr^MH(azn!EC'
    'c)2py&E2w#^Lu$rdn|NH<WL3~!+XKtguxs5Cc)&Ak_^I)_~qmuQqq-&OnkVFOE|&3L!%tFyAtNYTpjLK8d9V}L23!^8xAg`e~=+T'
    '4?)a98_(SINZ!8X733It6?k@_qsWa0l@U)Vo~)6_k;$orgWiChug=?-?fgKZt%gY9yirV2RFebIG^33dxDOdF!R3qglKlnQ4&Ah!'
    'H%D_y?8h3})F=vqsN2+YJuCo5rVvml_f>&|5z*nMwdZd7hAs@>+UH_45ydqa=%Iw5oym0!1QaERqzLBF$kw;XYcJ)$?;lA9>To)&'
    '1gU4)i|hk|Vi2KdLL}O2S!Tek1IUG0wKi|$?fA4{*{bsx3tcQGboBrT!Gghy2QEm!l?>q%RBTAkct=3{Vyw<&*KZ`^CHnp_cvX+v'
    '#c80({^5)1HLYNh2p#?;Zw<mM`c*&)dV@g<v~gIwA^yuT@?6se19%{jgn_R<B%~c}jA5`m4j98h(=;)}A>ORrNIh{_Be5NQUs3M~'
    'b2#?Ge}h)DSS3NY>`AauBdm>b;B*(4`M@-H$5epAE)+)iiUp`6^gwt4NF$pK3#k=3rh-4(@s+!{Lhb#j%;ct-b<6ew^l5gCsxf9-'
    '^PQ}&5e3T4C9nNZRNwM>XcA><G6S0N2ziN!kz_uqNg4RvYwR1Ao1`Sn5QmvJtwlgCEZfaR`YQLILTLkOo3l8{9}9%iihu}b#b_`$'
    '7yu^9Y8B5bw{cPNzwM?-(4mK5;H~vmd_(auxKl7pAVYDet7#MhY=ftF>$ib}uJqmHhvz!$de}nP25V2VB%!{_n;iztpaJ%Lv#^)I'
    '=lE!cwIAo1hy0QXp}{kToo=5@u^Q%U5jWuiWB)Yjmg8Lj-_e(i_NLYASkRLIQzpc=<Q;NS#4=+f7SJ;XoumuO{w7lRweMlEEjwG3'
    ')IixH=VT5d&Oi9hFtd(~eb%O^^;%8+gnlmCMrjx8B9fN{Fq0G#Z`f(BGOA!ylorkm)d3_nN?Z6UrB&a(Gu|($%Y322$Rj7VJ)(YW'
    'qa0l&dRerj4g3^I!VupF-QB)=^$M3bK5iI6a41IxEd%Z8#Ur8N=|c)1u+bo~%BjfC`P(d{KKe0NbAam5V5LuzH1c_o`S&!sVYK2$'
    '(~6HhrlQU7CCq$w@BZW+!Gu3xn+Wxexi2j@ECR5g3Gp<Q(XpaTr~5oibt_f}Hf#`a!lo%k9|o@@E}MuC9-}fSxVY?t$g_mq;tyTE'
    ';kq2KgU-!}mdRRX;LZ@8(E}}0I5@wM&lnCT6Sui)Ma8T-B>@6=cxBuo9xR<~lcaB8B@ALUA__J`OZ%lSijjX<wkA?A04B-ranK+i'
    '>JvPI8Ir1F4FZJZ9YzhPN6~8XhgIPus}EhEKXWNMk>`ypB^lbraYFY*jA%3$25Ti|_Y`Z^A6BirA<(24i>Hv2PZk|!WC1;JFv@yt'
    ')){dCn!$*bA};)I3s=l=f~$+Y3{J9P(xlY^_7Ic|2U5^eC{MfrwEX}GpDlf^#UFl5*dI=%dGqAOWI-CyiBSc}QLCBU;8;P|06yHr'
    '>7K6gr#B)sW!@j2)iXpE;-0?$uY&#vn1DI*6mkubpKhfF+cW7Js)JF`Se)O6&#i2KT<^k~6arE*@y9h(DieJCC%|kx_lOGQzN8@}'
    '$#@H^-p;tPtyuPg_m|gJN0PaWNuLfnLfS8~?eCe*j6+#YV9o4;gSB?;H*mXR3*a2^#G&C)1=07CMJkgt<(7aTJ4u+4G^zU2Q%%)#'
    '(jFct4>MzF|MB~Azq|5_!9U^S!Zgxw5(Is-eC81`igpI@g^n=86a6&DVU^z@WjrixPEfXwkMWOpPm`slf?dTxD<CDi+zCwHU|<~-'
    'E7WeCAkxn{`I-ZInXY|&(D2QFoc=mpn=#bRAZE09BTo=90wp);^dK`s{K3!_5jon=rEG-2hqoX3u^{6oLkJQzrZMyCG*BUGU=LBL'
    '2b{sxju?gHKyXBJZ8h<!^>+^o)?VmJp%sVZf!#Fq0-Z``AVS-ta-dDv!*vH^z$O0Ey6H$>^#Gqky@gBR%Aag5f3kTuEx4Y(^cr9c'
    'r3L#-yhIq!2FHOJjN~rjIsn1I$KjuSwu$%Odr)8YP!5EstEmVkfO8{(56KF?c?kC{LoKM;oy@2hu=mjkQp@#=ci%Xt@Bgt7bmb_|'
    '@K`DUsv(C66UqJvqX`#`K;$<P;?A~Wt@Cir)BoK6kMy*}ga7VMUkey47c2aH5^f41VX<CcWpv9xJOSjq?eXJ+^t?JvlJNE6!p=a9'
    'xPK|jFR>tmCxW6@L7|0^5H$S?zi8q;(>M?!qI~_3{Q1$Em%kPmb;NcJv}1A;gXRTvqe5dGqoO@iEYa8k#(bC;{<!2h%m1=4=nB)f'
    'nVJe`jtj1p&k^EAN74dS46Ty<O%SBOIgNGeMUvp_2ew<j4k|^w+MuV=zQ+>~4L3SZWMlaDH==%gNJ;x(y~kJPC>EY)H#>Dj!5g_Q'
    '$pn$1!8)V+hr|Mt3t|J@*|}~#4AM@ep`(LFC1Lo-4`Q@AoMoP`#&l3Xk_pPXRs&(fr=MilKAepXj$giRGv?;tcIUZmFZ)6?zzGgX'
    'D!z)?#-dUN^OheRAqh+#OcACsK?$^?Vri{a=0q^so|$kMcgr6Xs}39%0cDWp(!A=N6ik?<_8;n}{%yg-0wkA=u_Z1HkdGVrmSCog'
    '8W$QaVpz;!DcoSiHb`5VRI%dgOOcsRY1lzP2lSjpb)hXsT(@fNvk5#DuqC6Cn%rlr#Uz7m=*{0raQXU=a_cI7lUD9u$RJ34n28Fo'
    'GH`ctuR!(gB{fF@%$qf<R%L9$woo&9xw6xdKr+gb+!~bNooqBTn+aYAljM5Sq*conFR&mPKYc4m)k)kHt6Tw64ORjGt)rN6n%ZI3'
    'EPAfRuiqx9jRgD4&6nX2e6Vm>s2D-g5FV5G!ds=!*?hJvyrGBX^LY5@D=<gio(D8nyj;?GXqdQl1N6!ZMb4=3HBh@yG0M48I*0K2'
    'Q~qq_8kz{g1zc^22*g<|_uz(L{6ZQipA;!xuwBNzs$Ko7zm@`1k7tC0>wxKu=xL)g$dpZ9?tY9LKz0J7iqc~3!WDCCm%cG(UC`ta'
    'n9dq$HKVh}2bV91uZXLa%szh_FldIprUwWxWG{<-<IBmF<O)56XHF1zDj5?btyT^K9Bm#rH+YW=S|jh{xoXYw9Y?zWI<<8p#taAp'
    'oF?xG<)CKeY6a41xq!%ptCp*|;(%P?V=}>oY3ms~UE&qr68Z=FCLjTxKGBG)&{VnLsg!v_?L!@l$3JQux%x8;m1l|Ln!aM5CVfPK'
    'v7aVI7mVSYV^`!v?44VM3x+#9%Z40t6F?5ieBwV{T=*eW8n$Y=7p`xL!NPEbcG3Gm(?TZCs9rf-H2ghtqc8$j_%$-lovK#+$Q|IP'
    'IM1AyiC+K>oAH2v_z>}pU_dJ_rId(Sn6j^0>^usnK!QRlHEUQirq2UR3eapYd}>>m6KKj1;=)lIKK&XlasBPDHFNz$nnq(GEOi!V'
    'mP?!t1=b6otQ2L!d)bSdK3|gjXRCPnupF1;n|VmVD#lD|ZS&@6OK?nhi2QK=7Y0JKjf`VBy5s6q%i}O`;$@%^a$?f>EMSVv77h=-'
    '$Ox+8<UxZVmHDtgQ&^g&e%$9=lF{STiWe@K0_mUHVf6W(sO=N2WQUwj#{IE=b!38n9z{8Pc`a~288Swsh1iF;w8if#QWf%gA^wq|'
    '34H+Y=tBL<<?xUZjgV{7@&QBUQfU%X$FY#7BK0uFnEgg}?{Z$TChPpO#Fqm_$36>NFXmU{fTWoo5KIyl1u##+@h6$%G;0^V$i|O_'
    't_*TRbSrdZaA52ttWuPqLByv7=!0JY+Kqm$UtAeO<rpzO9(nO->;=PvNB)nr0d%IM*I)SHRy4~MUlrIRouQLE3%mZh9=(uYs0haR'
    'xff`LcijNuz%VtU80|ld1N2?H6>od@@~oAQ%uX%LvcvGlH5%O}A|AuK#6t73N#tID21lC#@B!$%e(lR`be7f?*oepr79D(&dpp1u'
    'Nn=Yj%^(O|O^}Gt0+cCF{o?xb&3nSWEpcaiVF9F4&|vtyMZ)Z{XTX`VRl$e<8uB{Rr~38fPnn+xEN{W>VPR>0xrDg4KmBqR=YF}Q'
    '3)_oWbz9eFW56HX`2@KOnp3Ov9+Z_Z*g>?#8!q8?z#Cn2TyNd>-wo%=tq-8hXk0<_;8?&v@`4h<Xy|yrSH`V_l8M7!bBUZ?Fh2>V'
    'KiSBWG1AX9Al`btcrY>X1Z@YBbLo3E@Cx6nspg1FWrR+1={Qu>VM$Kgd_Po}U>3~gbhKI=YBa>Nd}kQ>wtQwaF|8VGqhG;Y)G$Vu'
    '#7kz^loJ}qMkXe|K&+>eEN(xAhBSjSF@WKEz{HmqwV#z_8_y#E0||y8sE%+{AhZQhc>xnYtuW7SLJwZV5O=8gT|{I$jUbia{Z90D'
    'a!d8bMooAIc@i0)4$7zb`SI}RH>IC7Xh^zPAB?8a{nIKzZ)n<Z|EYw-D}bxG`}D(-;OgNFt|!cKzr<}`h9{o3g$^f)D_tgB(9rnE'
    'VUmPK#$ec~3PNDGD+wMjbX&V{F`3i24)JI?otVTr1!1On<H;j2GkhN^N8plas9o@<n)!Mi5;S&t;-}4+m2<n1Iwp-?3X<iG8iK@8'
    '4b>|b;U9)@YG^OG5{VkLa@;RqT%e?ZFM!XrkSD6k@M)sHto3F&^TjRAlY&brye(=g2DFJw-%64JOq+xb6Ln}&q1Ygw`TVf{yd<&p'
    't-E;j!S)g+Wm${h_OUSf5aG@=uE||Mgkh4&C)U?3`mR8}{#7FBY&69jyc=g3k+5Z23Dyr7jt7}EmH0flx-~1H7SJWSZ(gI6dePG`'
    'GD`9_fpd%?i;ouVrnz!%e_l`s^s}Pf^)ODWYfwO?L(^&8o+g+=kD{E#^iBkMP?+w+!Brovx$uZ<8gKLlnQzVE!Nd(M!YoleZ75C;'
    'uai3q(_45<dF8r=x&w`Y<~MPI6AE?!5Av{y--|{BH4Tl7nL2)0w<H|pZ9&2xxSYW55SGng`(!gg21(1zJ<Zzz+JionS1$XO)f8}%'
    'K|`f+UV)|#e+A|t4J$;4nBIc`$ypD=pRWuLMPP(XpE*UG(N4V#sVTwmvix*G346^$gMwy!^=d`J5C8!hRwG?6NHj3v5Xc@Og~9g_'
    '|4YMem>X<Yt@zR8o}VFi?8P;xhp~c)(>gePjkuc>ag0i)u0^NEm>E;I=#li(@2}6Oq)=sO;3RsP4)D@OfLkqUGn6phGkn3W_6S{8'
    '+>}vgA{<o;oU4F+Dcot9`g3YXbFt6?$^(|2KORz9Shk9-N-q_Q1^iJ+$KYXca7U*M2GtPLs5EjK(|7xM$NJ;t7tKY1g+{#rDgclO'
    'IH4Xj=(?On0VoJoqk<HFI;>mwtZ2BNC;{l<=>~msBt9_}39=zxCupRo;WY7D&!hc3L;IJ7moyX(=S7cHC{{753bH&UV}M~uv}lv`'
    '$P!DV8l#d%-&gyp%UvrTV1`+N5?*c=q|<6L3)jcf6-H8&PxS|qr~mvf{~I)48_E'
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
