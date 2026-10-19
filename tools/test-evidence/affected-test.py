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
# dad19710cc633cc1baf96eaab601da9f8e32c486 / tree 4fb8780cad7262b2e5022bec5a9a9d0d11c83891.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '8ad1f32510672e502b9b73dec0bd6209c3882ca473809062ea9d8d6219d68ed6'
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
    'c-qaK-F72MlAQ1L7=68*%E*lT+o#ac(LGN5vd~2m9008D+CBU3`YZvmS<@sU5~!85(yFJcTN8oI3=em6GxPua?H~8s<JTAe#XZIS'
    'ZX54*e>|oA-Er@p4ms`r@%v%-^xMDx=Wma@n11{B-%QgC*8cWyza73h{<du!!~gWAoq`Gcr^bvqr_RUF4^5a%Zn_+e;s3+&$Fu$m'
    '{KL-w_Fw<@wybBN@b&I__pl8=3afeF@!vJ1VIG_4QkaHu3_dl@*yL{TvB~3LT{C^Y+OrGa+<m(HW4Hg7A9jD--6wvnJ8pMRhr;3^'
    '%sJV{yQ$A@ileh;p2y_88A3ZXHV>hhnz8?U@qK#U9k$2a{>NSTn!>lzihZzSn|ZFInR1MCN@>o$&5eySKXjg4*V^Rm=PMr5;dpm='
    '*&fqfOwZ{lrl+t?rFDJN4#D(;=T~;~I1RpQ@-%hU^*;K^8sGB5{ZO-RX{|W)er~fq6aE`r>s+5k9&~4?d5CTpjP-{1`uSR~ukygl'
    '-KVGH-9KO4!!~cj@>c)x<MHA1)n}i>kf*WjyvhA++ab@U<Ei^`YMWuQ){U7@ylVCR?)Maqclzyz%gb_Dy4Lm1*${FXdv9!SY&4@Y'
    'b7;&EdFOm%bIr1U|EMl5ZTe{Z9NZkO?|G*t#6C}LJER<<9f!%p*rmz+eQCdEIU+-N*z%OWgzcB#)6=)@)8Wg#(|dmYabZ>Cg7qP^'
    '-da2Q)=rT_W5zzke&V<1KACZB+BK^_^UHbRm)Es<?2>h9oI2lxv5ga7viE#gKDT3T#;Hjugmvrg{N+`%%VQJxj7;YDwax6Bwi`Qd'
    '!<;4?#_WRYdGu>m-M>6tTr(Iu3`5Lr_I4Wid2a58W}b}il25ITz8O=_tJc()ya`|TyT`OSgx&MyUp@7<X?U{Ebi)v)6w>Va&W%mq'
    'PQ<Q0#5qo8-LqbH@Z=uTfxw+M`{bUtPxlwM5jnIR>eLUGsF{pSotaw>a_~blnBH1K3Rl(oZ9G42!tN<=FR#xTPQ%po14qd%*W%E%'
    'O;2o_`WRd8i7>LqZuR=Qm*eKo@7Z5m-}9X{*2cacxg`3AC(*mP2`x7yUu4HqXt<x<>h<{oxhgNNokH#=*SC>qmb=l1F&J;U#&K%}'
    '*P1DIc4#VoyCTXT?#Gv>bX26<>~}B6w251H|Fk<Cx8ZWM>E^&Kovi6YpDeF`o>FpLolQUVe1g%pj+A9yy^WXnd~xA+8V8e18xuFm'
    '7-v0wcEV+vW6MFvTy-{$WA(zP5AVGCl9=feJf=U7mjh7GVJ9_dyS|&cE@@N!oJQYAPUD<{A&r@ba=3kP<b}uG<2Kw8_P%cq+^8JD'
    'FYYC7kDK$2r(5>oiR}C2Y;2uRsmnye80|b;J1Hibq1Vgc$&6R;W;vBQ91re=T=H_18iy{#HV(7peUM>z;^sWHbIv3?O*SSqBwNk('
    'n|UFfyc{WGaApeaFy*G_x4S;HBUb~*gmkZ;a_^$;+GMWY!?(15N)MamEnVEn+<G2J9ET7`-;LQeZT7JpdNa;L9@0FHe7|kJdMA(W'
    'iF7+|$np7<_dhmYw+H1a7kAa@;u^A@e3JrUWK2Dm8Mi38g6Y^{Gg_X~^}E`6{-y7QU^WC*E}{2COY7Tl<m+`^6T2{Vi7$vaHt3&T'
    'zl-N{<>4NdQ@wZLcsa05(N67X+i7U?G!WJMz8gcF+|cq_x3-yMY9~Kmy(Mz0{II?MdaRDM!`Njqs>a#gbG0PSxtYv35r6c6V%Jc!'
    '<<Z};rBb@Z1L!F=n{n=%ZfGadD(fQ4;*rd}y=Ll2blZ6K7DziH!EXDVgS~lsM3=Jwz7^-2Ia9y!47zEYi2HsZ_-0R)oJ}D9G}k|t'
    '!;y1!`D2;+G)67$=WYstODNBLw}A&WQcjLz-_89Er|9VR_o@08$Rxat3z6(24}2qugKg~C^O1~tLezd{ZqoH{>6ER$UIl*l@)TVm'
    '(D0eed^n`%yp{&+!VQuC(+|P6#t*h}hC0EfU$m!+>#0lG%>C?#xwBoGV;>ryDF+Q-@)Y@u6>&mtZrsswM{TOYVCc!;Tf>FP#W=Oe'
    'xtRRKmra%9x~}VcYUuvf_m-Z%Z}+>WNB+grtGis*wZeIX5_I1CJ`7wD-VKTRHMz;RJTq?e*xk0L>RWVjc61$8#Rz0Ffzd=ubxQ(9'
    'dFjc02M#<tvcGOSn=MJ;{pt27WP;vLd{A+0Lqj0;yevNtVV<}wI_@-|a?5sa+uBvPydMFyNQn8yGdLPqNKl<P&8-RKA~xI3#X0<<'
    't%cp=f|HaU*pOZ7W)gWj8v>=?=S0#>_-3~Q*h%J|ox1pIc6CVK(^H|UrevK%uNO!WNdRbgUQ=VZK3aep(9n)R?rz&pRU{xiv~wqj'
    'A*MWsd2rmgt{FJ|0YKIayih}#d*fE#WkrwMns0mtJahsWy3|o~jWK|z&Bi+*19k_}mP~Xu-?p#ysS)qZku!pW^u80!l^bvfGqjdZ'
    'eCVc@9oi=QTlYnNv<dqJwtL*VheH7!pyaZ)<)WQtPui9<4@)_L@g%#Z3!c;|&NuI=CMD>&{P}SBAJ8Ia3}>FK8b}}Hrke%|RO80j'
    'wzqBOitLRX(q}W6Vc>*OHoHEP{f~XNCON~E({c}*Hr%$c!|r7ds1<f!6S#G_oXxRbY$%ExPev$PirqW_RnIB`a+o6zEdVjyxFuzk'
    'n~D+^go%6&u&*6^DzoglXIfB~*tOvICKH~fW-|6yY$v<z!%G3^o$M5nOTBAs?*a`I8W+7IX9+EjDRkX5(?Bsde%Hsx=e&JLZ`Io6'
    '<3Dog51per0}di$4!|-z7Eiw02$H3<)AqxSU-xnUayW96d`my}C1{j0PkzbywmuoY>6v#FW`NSh8$PNuWgDk-OGU6^Gs?1?&WvE9'
    '?L1}P9vu%lUe-69u;6Xi&tMUC*Z&!$KL3-;w?*tg1NkgKN5`J~f`YywlkJV~No2uj`zcIQU50)CvV^;|f7~7pOAqm4GUn%*euNqw'
    'c}hNlY0xaCO!TywY??yjA~C1#Cx6}P?eBJ_fUgUhdSY_(XoICK+Y;KS&nIs1*q8_$$1$l}^OUw+4xMzcS`J=E`y(og0{Bh_fD70p'
    'bLT|Uv4>cfKRt2ze@`11AGeop5;_|sAH+Xelfyvw15_erx?HB?|8@XemV%+OAULmD112^NmpEma3ZyZlFi_ZAPCO`x;G;mfMi{93'
    'mfoMF>Kr3<Cbga-pZZW$D;=O{`<@nc!(ngQNUv|Ktry?-duoo-NHci09SuWJ{(iJ7@Y788OfQ$dctb5sZ5GEBi=PV9u-m82?_7^h'
    '>2eLB&`L0)&tV63FNYD7d2Up>&orY3>QonUB}Vst2amh&X(>jzf(lom0hb)xHaC9ioM2qi8j?=kjo@N4Rr^TeVRrR<SQk}7;E6XK'
    '$GV~QMU$R7!Q{?3$4N_EKnbcqn0@{Fm7&GNOzk*1)!N`F<HU&*;>Ho5IEZ#4ypwl#^$VZkOT{y%2I9Tb%x$^8TEi)v$fbQpbG7Bh'
    '1t11Gq5rvd>Ay<Y%XbKk?1r?*k-7>C8Cx>@i3bm$-|)H(I0*?^zJB?0w=X=uTz(FmI}@NPG=id`g-~a3lMSH6+;j93rjbU=e8ooU'
    '*6(splhcs((d;DoB1_Gjhpy!hCI`AOv_3ZLKLHZ<h0DQFaQn+xkoVlAt-7q-DuIyK_v|U87IuS41jmU?BSwGq7V4hF$n$5thNicJ'
    'Y!LY?Yy%#?qdrdD>?Bt`dBzpn_;LKYd#VF8_3=|A0P1iasGpz+rGBJ|VgXj@F;N}!yzCVZW1sH9bSPBf=8wI5elBHM!8eq@nU8`{'
    'APkJl(f5v?Fco<+)CNQbcg2SRuynZzI}Frm1B>-yw5YWRG??kOwO%1o47Hv%NvL1CJ|UP#H@i;cl1wuq#fBTnf^J!ogV=kzjH1Bg'
    '75C9qSpofpo~HM}^XDgfSaEbagA)|!*a_UZ5QeUz8an;*yY18S%kc|u{o%~2x+BBC`y-Kf1FKOHUEB@5I#sE>_2v5uWcHMbKx+a-'
    'fV(q~rR^)Sq@Q-f>USxM`1F2bDm^yts7F@@jvQ4YX&N<13kS*ZRRm5iWyxr%J?IlBeYF+f=w}-%k#;gCK=~7or4`n|6&m9N)vg(7'
    'efA!582!8o%FJ?Ezmgj-FG;G#x2f!uW-k#z9dJ)AHl_*E8%GqL$mnwAlCRL1V&#VS;P#KZ{pN*#uaLF$EeC-+l8y^_SQvuJKcLom'
    '8jZ=&#0<qKVZ3%9r^@s0%$4|Z*oXhu<dO2m{;$zVKHtiTQ=$TE$utXiCh6@oMY=D>z&*93Ty6l*04V4D@@yQG-*LKOJFfu3vaQQm'
    'uk~XKl~Al)zyjqV)EpN6L?#_(A0(d{!qJtRSxB6xuNyL{J5+x@ap1g?2BsD$s!iO+0hS4GjoRDAo<AZ>94hEn#eMmg?L$1_Ked1>'
    'k!^wq)Vdi45Iw3U5(LI^6aoT9M!TgGKhxa4xie<>?y(hkC>%RIFG50quL)Aus2fa^0Y=Wyit%95Y;WJ#mNwA-^`)Lk=a-QM`cy6K'
    'xruJMftM4Fx*Z)2;}$+0{6YxlW}1J&&Yrll9%y>FJ*~dWUs)nTd$4G_)}(r1=R{B1{6I<`Y78|mZR4r;{q4ItB|XH5cOBZxm#TM='
    'yhgx9-d#hWiX6x|^QrO0!L|hz0QH~z?OR(DyCQi8-##Bc{CVPcJJIxq;G|GW16f@U>NWQZj^#OB-##vt?2CW?>J9~VG^ELaFwgb^'
    'b*#_?G9(9J3;}==mkWpXL-4=g8#`TvRq*vlpOYv7wi8+a#Bo|6)0}*0hBk<#*7D$*bo-_b+xvwbu|*0(<y&zmdw@kQLyA5CZ3~Dy'
    'Wj{?E23l8vM3)B!zMB3U_O@g?6>aw^MKi0t2Kja7+oKw$B1&MPJtZP+q!dA)f59Pm6#`t|PNshh3lvC})COp10u~zDfx2MsjR0x-'
    'rQ8TtZs&CmU)Eif^!r(q-d`8J;Hrt6363&E38-5h)B@Djj90(Kw_Pn4Wr1}g=n8T+_n{+BS&kx!H#io!u5UXD6(Ba>{Cv(K{xYP~'
    'wJpUGR}L34R0t4O_$<VDAOxa1wDK9W)AqOSrQ(<&3b7*fLCF|F8R6~HY4_yAs2e~xgCiTIpFQ5Zm2>^@^I<DQfJWs~9_gGo55(Se'
    '%@`s5Xa22@7p9I10Qjw2Td^fTK>#13B77}NLghtTCI2&Mn&|5!KMEdiE>x3oyO)6IytCA%*H**=$hvSWW5JnjPHqC-P)ge=%*v<c'
    '1_Wa0z{J7HDQn!=t=U7Vh^0!S2x+H&q&%P?K#|vp%S>A-BE_Jf9MO{1|L)306aC%>HG|Fc;-L$5h)!l|c*qu{Y!IjoT?jLO^l@_i'
    'xu;x0EmBK^9}<^SQB3b2G?5>MXemH?@qGQwz>EHf!5MdfTAVD?J$%_f)qf|^+UTDZ`gJVJ2aNu$)qR#c_*IXhgs;mEoflKQ8(q4*'
    'tSE<<F_}4LXy^0=rbHrysuBh*6}Ojmg>R-K;L*$KE-!ORc$WWM==IK>?*+5?+>b*GWe_dYNYU2OrBd`yh-TskKT7addJ-!B#qEz<'
    'lv5<i3)AIT;E<D@N0@h@!CWQCaT*io74=GsMXPKx?IPM`7nfYV6cTg(zDQ>?ss(81L--AFq#F3Fu>o=$5{3H|den@>fRFCjzb$wo'
    'hFtzmoRGb~YhbAX_>Qz02MADn@!d={(4Xq!Q22cZzkA$#=hlwplm-}crl#&W+JGZq{7}EZYBB;z;9XB<7=4^SYF?kRm6*P7^%kk`'
    'o{w6+CedpoPJl)tz>))>wAh5Ii!z@}(!+mmB27<MS~R-nqqH+ig!$WwJiWi3D^IQAHNuUWKykgJ%S8VgEP*gOjwVhZr?A`WRy@3^'
    's-Gze-v0P<U~AP;MN7=5OHTvQ4&)Uebi)ot7{CpUmCgru<qn>ow=a*InvDdpwdp3MacSdr3Au43mMb|^tcMm1g~9bJH&XQw;L8lO'
    '*F5poiYPh)2DFeP$Uj^=_%J!t4oD5xt{rv{+%LOR3V)_OmcRYZ3c2^F*$@m<pi%qNyZ~MolMg`(J?4olKd#-)0vK=Z6AkxL%Mqd%'
    '6l2Z;-F(8DRXzrz!A=RuvK>K^!QiOMs<*Iw2UYI^N<oBfmI-L0n)Md4RYs%Js{IdU#CrhKYOCMH{~zyw&c$P4Nl3O6X$6eL26-*N'
    'Gb#X%gj(9^RK+9g0$Q(K?UFGazR|tf?83{#_Rp$k53H)C>01Gv45U2Jcqql`oXi$_Ib0?POlj<|+`|3y%jPTm$cJ<&z?$?FBgG@S'
    'f7&H9`;F~LOn`Jc_10QAcD#+${DOTzispKU>R#X((V`(LKpcZZI^?XjUsTB?E`mi)j=HAn%&*zd0x(rHqXmZd(rt9;_fgh!V^Nf#'
    'LPn~P^a_)BSKV;suDH1OFe47zZ~X1+-(5_+sDhxT%$6KzCN%+M8tKTQ$cz)+t|(bFErj;U{hSa8_v3+prWz@2Kf7XohEyAfzhp;E'
    '9{OJ0c{vayY&@*;cgz>4yi<Sev0A+!tSkr|0qsaT&D0XGXi!P;%px^7AvKVEcOSZne7v8>UHDdYxZR{44n_6Y$@2ky4J{QTA-^<H'
    'S*!&z{~T%;K39u=`xHy;ODa_<!w6=<piAc)m9q&#{Xy87A-Ez!4MX*Le%^+i{gStT9)<cZ;OFJICe02B9eD)3N0r5*3y@9<^#D1h'
    '1|jPhr*-T9MVYF;Rw&b*=%zG}V2!CyO}%V8s6=py=#7qI_W_ix+sIy4EBpFQAY-Bwl8p`pEfAgafU7dQK@x*V#!LuM0bXi1!GEiW'
    '8Y}L2tCT8Ag$xKbdniO)s-&NMpU5h5f=dt_CFzwrIORLl&qIn1s$9Wbh=3{L>4QTYk-tvv5W{sAQp;qk@A~gM{&uri8mU?>L?_a!'
    'hVETQ1n{D;HA?wel&}Py6a|i0h2^z<<$^PZpN|f@7FIYM2+Uc?^jvR|W%-c6Lb)(d+>{nXF!SR-QkC?Io;xUm4m{TtFFMcCIJIC7'
    '12;UGo&mk4|4>?Tk)plU<prJaECt0(kJu#o{kBOkrtk!inbSlAm%juUN~M5Pr<11h1ny)2+~HQV>R3~KBLX683E=PjNxL0v?PAL>'
    '-JRRP`j4B_zd>g3P|<c3Xv(J>so1f>7$LsM0Elv(hYvT2kFAC95u0navwc$I7tV!$!FOxFd4BP)T$syyBII-V0^)*B0N(|`o=E3z'
    '!VHO4`Y0IB!_B{GPg1v`mr4&@OC{zSrX|uM48RLOcfe8sIyXK+sPBPkx?b!x_mL&iiv7H6-;f^Ublg5(zNWYXVX&hgq3lH+tlJ6+'
    'Ag6<lF9%2(GxFc)uG!TCPls-ADurg=LZc=<j$9KpPvk-2(F8Rl(2A4b4!{CD#9Xt7$E6)eOQN&~yt#zFfbak?kv@Xwabfe#V4B5#'
    'h{e!;eY|E5viD&R`&jWT5;s#P#S^Y)d?~=~uw&qyV2OZ~Ar8nH03^bA%|2+2sv3WOp$A{}aZq#5RKh3?INDGQVK$QT<LtqXXctXc'
    'x7ILU^>Hj<&E|A(olf@U_tS7U57dKXuduhgKr*0QI7?6hU;qYvHR-z312(_g0|1<N^UueJ0;!H<26+htMD7y|fv9&Z{$EsSkd_Gf'
    '+@=)m@fU1Ge|8x&z+z<>=~t(PQ-&WAkA)ZmF&5_dm}cSJQyi|}i&&Wl$H!7YZ-iokej9005QTtk@uq-p$!ExDCVWkxm!x#fMh@=r'
    '8BN+j{NPh-zeL>UZ@?3&u<$sTL-H-zex~A~h30!mfiSB1Xwp@&|0rd8tf&C2Y7Stdk)HU-r$K*(K7<2EfT?RiIY8*a0R1(aIDH=B'
    'fkN!^9^j8jCKADp_)HMMNx(mX`~vyVEC*bNcQ@7_oAA{gUu87zSUfA@34>&dqfB?1R2y6cpqrZoGAid+CV|-9)Q7V-lgG1l6cFy$'
    '0zv>G0e~yf?-}7+sck^J67~X;7Hpb$9D-D)`XF{9!JclHotIjYW~zv4?zxa8LH&fbP5Md8y$=(e8ayvZjnqITrc#r4y{|v3is9i$'
    'cu42GEd)-8^0(vH#SP#gmFqI;kf9_D4WWz6j(#E_C}aWMK9D%*1%eD1_lx#aVeAEI1Rp&__;NNR%p&~{z+P5=I#WRd_`oone#wU7'
    '7T3LFf$`oVVGs1uX!Ls7d<`O61^he{>>)laSXWtP+%MVDKK=8h6!T?k$)`hv!_NzoM<taw0&$?M+P4#uTZA!oymdnlyZh}^71lD)'
    'CgTcBx}dST<jV%Fwq*Ze%VJN-4Qa)BxphaN9|vhPo<genm_Rp#;4Xbcx~06a*$fma^bkGvwq62eZl#-_6b;8W)pTi3ydT~UH3=;z'
    'ELaIgShG42FB@fe@Ov{UMT)oX>5z`xRQF)JPwx5fbywIGqFoDD5M-Br=O9NFy~RkbX~nRJB8WrL{$;y*d4AZr%TRL`3Qqx#l_+dp'
    'd_X8gAm(I<&vc@N)I(^pLwoC<j=OK^=}eowoNR&NiWM8ES6ojvj_{CZ1RV$Y)7&9=Z?!#t^@d{H3yt5Wq<`b7$Pwh)qHIL{0_6oX'
    '58mk{J3Gum;51IQ<%)&2a_x5b2WnJoz8;UyRe_0+NZ+(wcoldx5DYA=PY4OzFK{ezp&IaRHN&kNI)wf9x#sGptL3qF#+xMc)R$;f'
    'N&Wy~@d~B<#vMc|QcBJnHdLmW(jzf)AfTd*EtxTuEY&sk2uQT>jpTAcMAiGN4}9D`I^y(lef;J1eK}qmzEg)X1{SVzq6H&ISPAzA'
    '`YQ<&HWM;-x^YVnTS;vz&^pSL$tG0Ip74i41{5oT3}d8*Z!?&v)I3Ba`z!WCRg<<QBOp20#U3n=3xZ4pX&dY-9W+d2Aegmk2+}%j'
    'ZrqUMO!&)HMQFr*FeM=PG@NNLTgolqP53?#<>j6h$*RFBx@)&|VjR7lv3H8I%df7NOPQq)hzWrsjYbnXs&7w`gZG9<=0$bd{Hkr~'
    'uTU8)ELllOcx`gB!ovw>GOWcgf&}6VHt}{rCQ)*C(=XarF5BD4DLR2T5*?)_vT&7Uc2DLF5r<d_8i^5oxN$?eRV%ElF=kOX%CKHR'
    'L;0X5+7YvQag?dhb08(DJ!Ed&&57l>=g=KtKo*r1uv{S=l4@9#tmp)gUK#PasTOgVlXVgf7cfn4+|~L1czLRPSafW`Wyx>3+Z`n='
    'a|7H2PeeEm5IhWh-~?<+uie)D?zj`DoP_(lw?eiJkzIn<)S|w&VmU&ngh1gb0B9|a5anQuULC!KEQpUQ*z)oj^LTHN@e`V9w2E3u'
    'W0lK|qejsLm`r<<#&^DUBM-Z{*jb&-qb?&pR!-z-^`MZ<iw1y816mz55p8eHU7)fia^J8Q6+`EjbPnHDR|&9#5vEP?3RROi9-R=m'
    'mPQ1xO8#UcMH1D?Z5vxe)Nwg!VOMNLC_y7VgfM}h?F<Dth*%Ee4pAXRoLZp^ICSlv&alW|kEy(+!OT>!%!iO94wMALg)HhWeOW$b'
    'Vx&H5bA18As@UzF-(Mv-Vo70TIwIJP<^<06I5m%=+9JP)nFiHYWb>=jlBb;-M?&+^zw^XOj9<fj2Jb(JtC$v{f;a_9hJ^vR#z@YD'
    '7tYo7$8O0XPvsDt*_T38L{Wng14L3IV=|&N{Ba==YCI-QX$XLi>FOI6Xi=XvH9sM{4yggMa<WR6{+mdEI}S~M{Q-)-fCm)wY}jYM'
    'Wk+Xgh|Te<T=y<-2Q%PCeF~N(S(HoK%=&cwV4AAu1v>^s<JGCrxg?_wB054iERznT&E>4az6Z0KNw`rk@aZ7;Zs{JhWRoLJjjQjm'
    '<tB}FcSp<3PFn!8HXQTGU&$2#scFg6&Bj`b&KG7U$X>4B%W}sf?WjHNh!QP1KJSLA&<3y%{KpY}P+6n(q=P~J!Mu;*#vOfstT6bH'
    'cL=BpgP+>ef>TfA&@i<JkFB)Etwa)Q7p~5OzE4VAzY9$(rT1MU_RuWIy3^PTmY!q}$(^O@8h>fZq}koDlk}(f@@iOD+m5pMJkBzB'
    'U{(_jdfieTGIWQVm46kXLcr|qmQ8J!r;}<Q(`=A$2e~3ctby7h4?GxGSj1Tw#DIawkfob%+tIF~9%I~(vNADunM4xd&l(Ep4i$ln'
    'ir||oB97NXp4!P#7{hK~pd4By>z!O3M#$TEXCiwfKBq+9+Nv_lk^tVYk24uCl=Ozs>|hq-QwD~QWe^s=f#whPab1)t3P&C#txvaX'
    '<?Ws#0v7U|K*fwPB?t#7FEW;)!88ZoN&+EY2~|C}IY<0gY^K~D1OSs-2)#O|dK3afyAstZ@Q)^jF;N9ikmPUJjO2v{?G&L*@)x=5'
    'Ve8j-GTRH91V^e2JB9?z;X&ZTExS0%t#cz1R}qV%99Bz|W;N*)2`T%bYfQKUu@g}e$c&2Tme~82LnJsMX#5LiPxxzKwZ~X3xaczt'
    'L!Jq5ji!pVWI6<B{wQCaX8o0WZkEPoLCB8_HhM&$cgSU6r@Sc5eWGna$;p=t=p%RfYc5G1j5HHqDJPC?LHtJR4fjE-p@?2yY%q<%'
    'pSU79%kXqSoXN22bF1eEtax4x4wnC1>}``tI+;^M@+P25T7$j3(L5E^Ok&rlA%=x<J>>yD=}7|nbARF$M5#7tf#Xdh3FaMWiXCBH'
    '0%yWvf)0m83mV;)Mnk^>uJ~kMONmguD`fCNFAHm6+#`_^)7iz!18dk;Ms_ruXCB~auin+Uc~ZL{QehxUk8FX?fX+G1H<$@<^buBa'
    'Nzu$;(3de+@8>;>vUXD>eHu5a>IsT6T?2UxN}8@iPd5zI9y^;A>DGsv(m$);)6)8e1Ax36`Z$Rxz#*7dqtJ*%ok-n?THai{r?7X2'
    'uh>F9?T)Uj{{~iqJ2Oi|fn^8yDI{{)zed<$)C&-BDfrqI{J4MF%^9<(9}dJD)1Xr3zcKw!VSp^OMI?^*3SQ<QnwDbg>KO1d>{Pia'
    '*$PG26A0?y{cBPhmiP^`l%REEB}%4@B-zDy+on_vSKIaBv(n|0X&}k5jKLYxhow(Lkvs|qmu{#VuHDfal2W}Pj9ptF5T5o)_o~J?'
    'H4I227es;xlaPN-mVEVl)5CEGy4@?{BlT`ec1SJU%g<nhq0W^G6}H1z5q8I*du6_MN9XdBeCp+1!vYFWJSY=fc4lA6y#xyy$jMow'
    'csn(|2C6M2RtP1Bo40dn=j`gQH+pY!-Q;5ecgnivm^CTwB-IX3A($Pbb&XFq?riA|)b2^M274*I=*=N?AS0u-0%d_})Cv$Mlbps6'
    '$Mvk*)8XsOQ3+%HeFAh!Kr*sxh1%8OvP83on-}5`DkzE#G#?bN)%!YcWcjoYuMso6EJo5tcnhR(+snxbw^ssYp$=k@8EfMj3f%<Z'
    'Eq!Oe7n|iBH_x~1Xy<<?X`)IcY{D&miUlJK87iT3MURF#KioI@jS<Sh!=f~>h>y8j)+9_H?CGaJDyEi96y;4#GO@?W2!jle7Mzyg'
    'OJY>Bxc%}Jp|IBPC}I1Z?$nAWm;BfK@-iAl1q6k%0aTEVhkPU}B!G-ffZtx%AJ!coTCRMynRCDU{AA95cdq9zZ$<jK%w5JjDyGhf'
    'LdpnGizy2U2n-zh&roYu(49ZoN-_24f&gKGSuLFpb#m}(qC(6U3%r%j8jO8gf3A+s15us{#>;;ex%W_DwrYF?UW+`9LC$#4@Ib_}'
    '2mu;1PI-o#0MnFi*+uC|5K)*zAh$U_O~iFc<I-9UD#0KUvsb8z_~bP8Y4qvSeA?;&qo)IXdvHG%(se;&CLXZ{aAPRfi_%NQJb*hv'
    'PN0Mac<-s*SCFAj`#{R)_GhcRlZvENA0zjIfT<_~ppoSW1EviDO7qq`sNmSDk8@tP4Xn90d#5aLbFaUa`sgyfMNt!#Dr44!Py*sw'
    'ZiLq|G=TmLW2(u1ruDnvzdshN*yJrTYAyhrU4RRiAzm=Wtg8n8EV5rZ4Q?3LEq;0h`V6Yx1FQ;gMoj1+En;ngH!1BXSm5v&aZr~w'
    'mm!39g+A^qvyy)1T+@}cJdk1$8e@hH`_(fo6Q(z9@j&82oy(uXeuqHV`*oW*!=A4nLcxKKLOTihmC-Y!L$YXj6x{gAh;9Wa4R^py'
    'E5AqjPB=Z)Ndt|hqeNP9Q10-|qK<_?-Koio_YCi7M2*hCu(WOm5K7!Kak8EtfY=x^AfcHPDMLki@7(Q(REU!rFoCiEho*BEx3Nf4'
    '%2E(-q(8vL0-?^JYXSl?H8sH-45VYk2i})4_bXq+IYhsE1XUJlcv&>khEAHStMJH(wnbP5<^g3>{AjpHe&rjXr{xKiI-!N-(SSqc'
    '$NEbZ79br!2Q$Cu&<0UzxJ@y=z^!ZD@-JI5z2mX)F`{MT*Wnqj`w|$8evv^BigN`N7Lj^`0J|=(Ui<LJw$z>0gj|t8DGQ{G#U4V8'
    'T}@@8(!*>7=-WsOUA?y4=})w#M_HF>Zb9-jo>LZ+r55I^&~*|R0B%cn#)<O?Fofl{(F}#Yy>TZ+Z4i^xFaela7`XBv$4OTcVWA8$'
    'Hfr(SLP?gbU%w5le&%{rQY#qpGoz3~-KYuAKsGqvabL(NK^9=0@MVyv6)#7UpgZxnfBck6;FFh#UJJxr<ip|j$N8AFDg7@QP1GbY'
    'sJaAFP7ORKl)8hxepkQmwu`P}(Rgg~gS#)-GOP7Wi(KrXD5Zehl627<RKnz5vV&m=R(t)9PP$Oo9+bKFr71aB>SYa9#^sNY1+s*v'
    'Se61tq;I-vn#sV}_xbwmz*^j)AU?l6W-sJD)P@3-Lq|_8d0i)+2|i+U_qgns!!~JLhE%LQ-Xx`hDG6X-Mm0IwSAQ19MB!c0DS&p!'
    'gGM}7cq5QG_-3HzfF?DXvD%hk(ex*E;?j$+vLKW)TR7v=amMlxk7)vIGrA?)W?2F(=toz*D#xObO>hdM4@MJ^q7;msEbxtZQQW1R'
    'Qc7lg`%9(zxyAG^MqRjdek&Q;WKm<4O5l75N&pqJ#aALSL=#~F><ngDLwhon>z~l(f<d6BtJ2s4gqs0I<Ze$rgEv%Er-H|h#40tp'
    'a>cVk;8jgq(`#cI0vQ396gm^k0@0dvgR)0-XX@I7cIh`2bLrO|?DohuK>dnS$3_hnprF>gWX;}0Jqh={UxW&{2r-U|5xB*S?QPjV'
    'PU+%~G^u1)jt3nbO-4^JDS*x^PIO*udoc&-EG7~*M&81Fty~&M22Rpnk6uj8-Q|~#^T8w{l*WArNg+C!;Gq-&>x5|nIz>?(*KJ@C'
    '@)U+$L3M%~flrImKo9|`R<3hV9)$*W07KE+ruLC96PF7_RCJ7#V;XD)3`mf|cT+>h=%cWO9#IHWUyGuK?M{fP0`;HIVRL+WDtW6('
    'b;F$nS_`op8CTMfPBhYN2itOum_i*Cin3R&yC7?Ny5(_lWcd9ek&rSXYa|8vC}>rXR2{ky=C_(&)YPo{<0&9Ih=i_6dm8cSAOHr~'
    'QB-7;CTg=Dtt%a7%Ayh5?Uv-YV)3(|>dBs9Q#K#x2I5Ab&*L<)x)m}8#g`*Q2hU_^fV5&H)Tmh+P&fZr_sdzO7kb(-@rcU<cq)_R'
    ';d{>9F4UjP>mO{<UgY=m^bLFSFR*IBVYoI5K6%W{V1$L{KtVrB8blkE;p0O9!6h<7lY?B8G`%i*niH;(kzSm%yuB}!{k^8@00%-X'
    '2lGMXK@LFrp;TL;6FCEx8=-RbSNrnU8PlXf_o?vI@!nrt9Z|b3j~HDrXc)fPz1$r^>4=}G1?S2wEJV)jMPpk4S$ypw*h4yYB6JbS'
    'P-jq8z`sj;d5wybqWti6#dE8(>Sg21NTUalnnpu|@$tNqU=64-*bZU2hqdX4?$4jEyz-43v=3yQ09*(Q@-h|`RxdY&>y@bt8D1dH'
    'Ez_DUR6KK(6}TGkA*UtB<jO$jL;)c7Di&3i8QwvDe}!cq87Jnd&C{q9d9_@N7JmZ%15So5dMYv^I$g5rq=%YmnwA#b#TVI%ygYxX'
    '{C)p3XJQ5^9+?)_arDlZ0i4CfQZfi(8jhuAO&2TX(~5`1BKlBOmtw3*GpZF{Mx%kT2nHU{$a{uM1G$Ki((1{MzINefDR~*uP*6J4'
    'G!Ro@R$pU~>kuSKG66nhP1HbKgwV&CBFo}!*`*U+6nx`f18Pst0P+&i5`~)3I+778n9&KEK>nSIobb0*7qUy0UkvteaP-F{4HJr('
    'Jj#g~_9_HP>>X$$V8e=cSYNra%8G57TRq4hfj^qz6hc{P$@G*CVe%_qOpY+FzsAh9i!MBxSFsK1HpzjC&z$UwT8+#O3otmB%;A7N'
    'hhiHwCq?y$YXdc;DH7>kH*u!VP&<|swpPF&w<Opr0v5!Ybk1qt59;MJ=vY6WVzOVi?t;fsEI$|2y%Q}NI9}K;PKw>K2I2$5EOwL_'
    'N-i-ZXt8qbS5+Y?+2v)q2pKt~$))rx`Ss$RNUMUxk#T(JG7Q47I8`p2AAS@ZvzU7brVYkUKnC3-#~H9xru|RS>rtU1&IK!|Ty7f|'
    '3nusNVxY_b>a_7SG`kTVL62opi8=x7^0b}oW=R2SKc`c}<te>TE?&;)!P7y*fH7(RQZeKAC%<IW+l<MEJ3~o9iaop9g@1o}y!;LI'
    'vNhD~YgFn+S_J$i5%dnqYh}QQ7n$a_43+DhhLCLzk01~iA23}UC+Vm3jva<h1M`4qiJM4?4N#oo1}Q+UUH6rKTYj|$lAVA6j4TP3'
    'd_*W?z*?wah>)VKW7W=#i?Dj-%1FhLrE>!7An~IuDTa(nJKEojG=gc1oEueRF8X1=t-srSEA%m!W-S*yR`j#<Hy+V6z8cun!VDAV'
    'm(d=!HcDvTdO;Dzp^-x}f^056#A^8LaRUH{6Ddexsm|eD+uHSB9*)~(PU+>ckkL!>pcO4o0$yOXSuK3c-vo@uxS4iMTm3z~4*txJ'
    '<?EE60NRA6BwuJj${Ga)lYm(&xa{H01qMOY4D3_6gLe+eRm(HZi1Y?89tgj<smhO52p(V_w_g$pLr;uJ43*2DeUWiie>i?EpaBwl'
    ';7N<4B03qml2|2CpAw(x!{NH$Lu5y)Qn~OU0526lB`|yL+6W0V$O{$EODouc@&E=F6{^DK*sWQRXIwnE@D9}Bg1v~LK4*tk8^fEN'
    'y!{DVNb11ZxDMy)b;YCt%c}sWfeoeBr5px|9)&>2X_yFxLj^J@)YvTThuSFp=3ey9i0blBM-35%QL{Wa%6!QP^+CshPWi_9)N#g;'
    '6Kw4re8Ox2$$!9e{8q@|35NKUiJJxVpm|l~l*}v71R1s?-X#7HwYl`UAG73FsUUl`G882D807dz!;0ElcCHIS6A>X%l!7tUmMo_x'
    '_vPQpGsPY><2uAdBx+9K)QsUI1>oT--v9vWhq!9R4V;;a_aO)@zKS@QYdS9@E4VCJ9;R%o${#bmfyN#3vURJTGM?>WSE1)+ND%68'
    'eqt->)F?)e`T{c*6qkuI6Ru|0RsU|R%TDWG&U|pcqXfjI4CyBaYB^PlfCGIWjaxo(re}uQF!J)eK#4EUBD54b0uZx#tk@IFiH{_w'
    '=VVhW(Em`61SB;pw$$DfClAfKl7UmoT(1rq*^*sG$j}&VMA2E~R@5>04kydGwp=+GM#@NZ?<(B2nT{kDG2gLf2`of$?&d+WNhHEB'
    '3oSF2G6PhBPk-)DZ}`iGzhZ5^DUfDnarbC9qgNb8&<4z0vGE!;l11ebH4N%Ovu5GfNmb{OBbPt5URK@s(s5J4Kj-Iy1jy^aYLJE1'
    'cyQu)+pb#w?9^XpT`!X?p1j0&Fv;j}j?Cy0_0?#)D0x{xpKXe6eLwBsj7U7l%Y2XZ3ur;XqZ8ko32_+>5v=dvNkgR4Ct)<Y2c|HH'
    'n;(kYgrD|MwJ?vF_P!U`hPH;D6I3k@wpy(8h;R&&&2bm(>V@@h7pNf^Yk+5xvA|-aM8<>^NSF2$(g-YoL@;D7PU#Lg&5x=2)MTB*'
    'wBHO+%2DErLr8=Sm3k-5^4uO^Ka09vSn+xLj1Z-ih*3HTbMcxQX*Hl=DgPOcL0;maDyofKwmJG}Y~}k4O1u$N2{cWu>pHPBqD&s?'
    'm{SdtVFO?SO&6O0LV;IKCIku=FB_&4Xdx^NnE?eIS<RIYX&LI5FCLnccf)d47Gl7u-&D}`fJ$P;O|3}Q$**S|J+mK(VQ?P_(SY<s'
    'N>lV3KG33mbZ-M0?_PiQo9$oq&_uM|P8JCo?PWFA78C?0nU;x=8bQ!U<Sf3-hOOC9%}_-Y%s8|npre{cO*Cp~19cy1F?cfmBpOcu'
    'U#7ijJ9Qt4XIK<7nGvJGAyIQ5#0~A9ku0TSQ@UfiqR#sAPL}bH&u&|oM`$9G#%T1b5N#C+s14w7CuVjsA4gO)xL-xznDbV^*H!!0'
    '_~tTrkhurAK;u!%kVh^P1Wk<)1}|+Dv}NK@??T<eM^(Ov?HNj;r%)_SX#0Bk1UrfTX-Q8K{Ugz1G7F#PENMd=tJhv6xTmW<?f1(l'
    '3Yvu_3sY>cAq;s4HQ1|&+#%I8=4w>IJaB+#k}lM+D>ku`!ZZUiV?UsIlN4t{yRqhKRJrtmpy9h=+F72r@O}rszbLb+`T1>PXsVTh'
    'RnAv1AK>@#-3$4T(nG3a&NP8Fi?8_lXadh-6)hZ4l`xHD&>TT|?SYljEfjz|tyq2CCx{G{AVlGSm<ZFz4u3{aC>{z0jmBLEKt)Cc'
    'm2P=>=y~&QV0`^xB3SvrwVj0E(8_q@n$SbfsX?PYOUMCH02nZ=-M~4;teS-i7{T1*AnjX#5<;TSw6aN=0o<RNJ`|OETO5q_*%s>O'
    'QE>o9+0;-((*PksfYS!LOZMe8MZqp(NX*)8)X!qgQr#18_<vC=%5(^X7l;gXS5$Wfx1U};n(KD(%F?-9?l5x;S_F(cl1`*kjG`4z'
    '2E7fH1a>x^I>4@o*8FV?b=^-C0$822KEdK-{3#b8z%LLq3xhz@niN6V6s6?<y86!)$Hf4pka~lf$f1WxqX5AWMQD+c`>TN@9S`^&'
    'ccKk9ZKHx|2^Y%Dfohvvm}Wa~AKDUPZM*@EhG;OM7`S#aH|?W(G%Mp(sJ>=lS6Cq6@YKp6eO3xh6Azm(>f+o@t2d(wt(&@$U%DLd'
    'X=7$G+N}v_oTyE##A=h)t))7WCl`12>ODa0c}n+X@g;aI&tGb`R>m_7FJYP*c|2rT3?k5~cN4%+kp%JK1`hJFE8Q1#;guqxx}*^@'
    '%MV%fmL!u{tSg!9g6rSd#I+&fb-HHN6hW4m7Li0Fv);7OPnMZYAa3Yc2B|;8>aX&33)RzVVX|e&_EuUN>c+8Ou5s!fSwd@!E`49k'
    '+qrTdZ-Zg09M0haGYToU8l&CHjmImUB&UD`M3))Pn}&e4ZtZ4HJ$=%P04HgqX;u3|hj1iyp_l>r251KRq&FBO0cbSN**Pe*Bv#k%'
    'L&F`OmJExFsyKd>Ui+xohS4-KI-?F<tZ9cqDQ+H@?t3Wqhd<fNDZ^$*PZbJ0I9ZvhhQdM)_`Dh_FE|${5+Oc9!{AE-6Bx~PTd84?'
    '<6syx1QEY`yzsc@s6vAb%%Q$8uQzJCHn8H_&;>$|vsbAT0&xrOI9(7})FkxOa|)HTUbyJ!o<lXF_UgmhsPVICVN(VCc!cvX)W8d2'
    '86#MsJA%hG^1oi^6>2#F9Mr2{xs^J@EN%y;#GprokxGvS<@l`JR<^&W_c=Rp=)1MKc7E92f8|?vIbW!cFhdK12JjcY!d`7vMjwD7'
    'qI@$TL!%hkOpKtRA;R$5EbCri-;=CRmHck<p5wYLsyPUfbed^21FMgiih;!t#ahxpqFAeXB=Xm_TOo==Y;aF6&wM6JEx6m|!W=jH'
    '2y~N3vmhTq9)+yU!N8pgwnqcGgg$8(;@XG8jM}G<u9BbnSWx|XS+9ah^623<(9^<H4$pINZra4+r?*9v_g|NO*W6fM$Qm=~M$_aZ'
    ';nzqLj9BU9q4a^i+auwpr$$`IW7DravJlAEF~?zblJGQ!!bd|xItY6jpT?b!ZV^@!VMBD7{`!3sNn_0C;C~qNj)@Z}bSu(pmX8Y)'
    '%&0}giG((``X131Rw*Vr`8<QXWAJP=$N*1To{lJ?D0h7V+=Wp_b#%o(RwyV~1Vje6G2vnsE<1#0W)w9<&PlPvF77`~xMCNTS_XPg'
    '^pnYhQ5n*LVAwAI4`u4Ck`>bdrW4`)vARk-N&Gfv$zQ2Ng99}q-ls+dwIiHHhHZ)a49%Pt1(Hb9CkTvd_ppwHO(Bfu3ekd-$;}G&'
    '4XI`0#1S4ek_ZYoAIItkL3CK$gw8F}@{~m!@nBwqnSdaY38V55m`yRwa0X>JPTp{<56GHH^FggBn2z#NA~?W715QS%2y>f4SrdnC'
    '?^dV3=N)iH6+)|qUehQ>oCYnO7A5==qB-teO!7b}C!4cK)kfQ;y>27VyCtM^vu(q-g6jkT2DDmzrIO9@1}IQLx?y!uG->91771p$'
    'ZX*j%q2|RjB$fC+Br<Uvlr;Ozqe+<bWr~xNK;1QUac#7C()z*{#n?bTfFJUqfF96UY&10x)*^Qo8=#Sn{|MtMjC8xA`T5mH<=j_Y'
    '*U(0N1wn*jHGr<Fg)6E(tZVi)Xf!E|M=~NaT(_6Ct!<1Fft-!Vh7C3ZNbYEZAX7`S#NbR1^7U><f8B0QT$-wlzzKtt#H9uo98AM5'
    'An-C*ZIq8Ty(uF;{OVV<h)&P>d8POibb&%q(@8a68K$WpdT}9PjyrB%Jh*r|gI}8pK5xVBZ71chDz8Y=FxC;l7BL(8Y95dg@3)gw'
    '0WVkPy18q1ae6QJX@`YQi5$uxV|XtZoG^F;-z1n^Qj$Tq5x<=LLrS{xkckhsaSkWAcW9Ku_Nj!qFjt4Wm4+0lP>@=J`-Tsf(LczL'
    'pobvlpp9p)dL*xBc?CI!UIm^V=qPfdL1n~KiYII2ab$98;h;BQ=d1JfWjpUkwABzPoHvR|ifVEonr5`|0{0=qCAfUiUb4R++o7wr'
    '^Xh0$iG5!qn;Jzy5Ote+u7?G{$P@w!<-RI#Fd{nKwD#OpXXwoEt$i*=6H#1)fgVZ-+L>I(KtNG~NQz)S8rk|bdF`eA*Zm{OKpjqp'
    'l_2#jdy#!0Pz)jzO^8H$Ez1nJbpW|AtJda?yd9qwEL(LRW1)-1gsvU{Ay_bY@xTQMxRN1!f{G348Se;aUyRk6?D~yFyhPs~2CwRV'
    'yEqLL**~0^UegLDiO}Is^41{CqF)7+pf?z#KpTg(8{)qlBhNKmFn|XVNf`L*Lqgio#ux_6<A5<7G))sj9OBK|jnor|H4@v=_Z9V?'
    'Fo$C={5NPdi&YYY%bo-qHNx5`2Tpf(nGZ~JcT5E+>_TCLQ!GFop$EbXKpNR>SV*nNF%|sLj<4Ls1#0h4WhOVxtXsAhpii@7RE;sy'
    'n(t(FjVMrVE_v-iQGLtt&?L&zWCk?j5%LldBguSJlQQtT*Vs2KH%UpDAr3QdT8n_3S+<+A^i}RZh0+GnHs9hTe=HD6D*_^%6{Er2'
    'U;vmXt5rO&+{RhO|GJwZL5CiKfw$IM@eRet;7-9Xfegi=uBK54unnHxt=|R?y3%)(AD-&0%V7&)8>~Iel7#vyZ*~|og9g}hW??UZ'
    '&v9snwTJV>Lw-($(BK)vPPb2{SPk>Fh?{VMv40wM%keIN@94`$d)4Z7Ea*vqDHCE_@(wvEVwo`#3+S1HPSOQse-kPE+V`;7mYpn0'
    'YM^Y9b21+y&Oi9hFtd(~eb%O^^;%8+gnlmCMrjx8B9fN{Fq0G#Z`f(BGOA!ylorkm)d3_nN?Z6UrB&a&Gu|$#^L(Mg$Rj7VJ)(YW'
    'qa0l&dRerj4g3^I!VupF-QB)=^$M3b4mXS-IFuuUmVx&4;*rqs^dW^0*l3Vg<y2(n{ACtWAN`oCIY4!2u+k?<8aZBM{ymLu7_Iox'
    'wBlorsc7?i4l|$KyFYnHFyRl_CPKYq?n}!JivTQWLOe}nbgU@T={^rr-HO$L4I4z9uxX0Xhr#QJ%O>K3$EXYnE-w2Z@+@Ju_(PX7'
    'T$clO(774WGFi(E+!>-XdZ1+r2j4H`Gls*-#BHuxQ8BAdNr1o|UKzKD2TLd0B<UMi34>UTh=R?~(thcSV&r$r)<g;hz$E!S4jSY`'
    'eS$|YLsIowg8(6UhfxFSQM8(Tw<?@u^`Q&&XD&r2^1P9yBtzTyoX|ZHBO1+x!CHygJ;j>!-Kv#01ez3M@f33M$)dxIET9JtMp=)|'
    'IwKB1GZ?W_#D)L1aK#KKxVqTO;3OL+O<Emb4?)RrAO$^z^28fJ+Yf;7+0v(4{O*0ies?U*n<p<O3(|;Aj4D8mTFvAJ#|pXz@Zly-'
    '_jHv%y%DJ?^KSpBo*}Xj_weIC3i=~p0_Mn5$TdWMx|JGi&!lUp4n{#^aef;<x3Yb|-kCKi1f*o*k87w@CiwVIfZ2HN5f#XNNkd4I'
    '@fKFSopEJbvFsV|FR!hRBy$;)jt)9P+Ap&0@0rbvLs?E>&Fq2?Ywg;v;C96pz&YTFL&KvAqVFY(R3>T4EdfDxk}xA_QuU`_HC4}1'
    'd$^-K%#5Y|$M1*T(}iCQ{s|u!rjdq|An2RrGmnT-v@?J&bc7k6=%+ajtNacr<8Enlg0g-58Na`Knk+RH>?#IY0V&z#PGIr|1M8qz'
    'p?2#8k$%p}*BsFEbnU~PhHw7k_~-G`jG=Z0F{8yBd4h-$D7i_e2bme-4~DLY$kBc-Wg`UMz5d9L1sOjXLXfC2jhR=cfeKLrdx%Os'
    ';0&&I#3&>Of+LzstBFsozq?zo_Ci+*tvDnP?53#~=u|QT5!xP=18u?{t~(e5F7cn%O$YL-JNO*xEu0Hi{$z9hlg*oH!R7R&*8pQE'
    'E!bb;CBk?%I1bEUBzF<l0SE>@4*%@4O}zcyz525Iav(%qO+_#PoEr&zNLKL8L%44lYC+BJWJbk+y^p>iwOqe=_l@uL?LQWRt{mkV'
    '9!mv4HRKRsBH15dG~t2~i2O!E+}T#FbsDaD{NKC(l^&LO@IT%0YXO7hVuhbi!c8G0EY|B(Mz;*a6F|<}9zQNfPpi`;319Ed><q++'
    'yXUg}5(`3jA}DGV6j}%gLDR4BizePPjRPSf%GVFcpC7Gx{%e6zM{L(XJ0>?VXkI`!Dm2D1D%vx}5{)fj%!hg5`z23V{+ES8SD3!d'
    ')KoZgTyU*?ju1CGk`}09XqDt|f*=LXX{=i>k_2D=V7ujXP$}Zo20e}TJ)VGQxY2nc8^gE15%uFkO4<kO-M=tLvG6>**{LfE-pF-H'
    'CWs6T)*0PDBo>%l5F6mm&UNcykajE$9UU|(3Bx~r5TniEEc1Ldrh@{KOi<Rf8VDOcJ(6L2cQQISeEGV~n45#!o#wVZ?+VcXCpaXj'
    '_$p!>i%J>HTYhkaBrtg}MVQJ2CD4kBrL|U>6TxVEX2N0IEq_p~I&fG7ltG$H^Qv=FFkzP3f2g1O+k*QANG=&;OI#QrA2;$X!Au!7'
    'E;L-ku$aSAxWS5TkhV0bV#Sx|A~T=Tu!DdO=sAn(LR*fwZq?dn6L=_KOGYI%xzARMNe0`{n}3kta{3Q)>nff}EB7yC5TriLL<LwG'
    'xI4L5pnCU`nxg>b&6-uKGB#mbsF}Q6+383i8D&Xs4NCA%HX54E1h0cha=mHNs%488SdfgLz7?eEB<_k;t^lb9D*=GkQOr0^?J#Q='
    'J=NluZxhr;g8k*@%Wwz|EF2apMvydw$0WY+R_Sv#pDhb-=x#Y4cmI3==E&RAfaZ#qOF9n?6Sr=FUU{L&85O<;Y8NU-Iaf;O5I%p('
    'pRHU&6G6Cus|^u>IE&>T+z^akNCV}QBE<`~%eYsytAF*^QeeWairhhJ4liltKr@?E3DFHIe^{xOKZhpa`?U*K%&p~)hT8yf5P~g~'
    'LhK_X5QcP0Pl4wj8@k*y<~|L_G(%s~9RwJ%m&LyE`RGb=g&x8)Ul4aHzZ#NOD+d8SZ5}u`c#jKOBk$w6YR&Q;N4o$zwRQX&?7`%o'
    'OmV0gl#~=qfn%0E7ZAB{)p9jg9FQw~OeVN6Z9QYBOT6MNp?{!n0utcq6OFhEO_d8COPMFsKGd;z{G-N^t3R_)d6qb?=@j!c=_3k^'
    '{WK{$V+^MpyCNrI@7yX}Fx=r;HsqL_0CG^~6aV>G;D=CY*sA58xxOg|3&R!KMeheq3z<BldgXA@@b}D(!U$a9*T^_`s#@_QcYvSb'
    'Jab+qegQOW#sdQ4L&P_N0j;={QX*zy%D!r`(<q<<2@0vytYOWVJ`XS{K(oQ{scm6SpeaL$3rB7E^fa8~`s-h7=K6^=jmAP)>MYJI'
    'mpB~?tQSC8DawTRvKKdfz9jk2R`K+1`CJaK<{<^E7&EE0&6}ew!Dqrl<cIUWFc6|`WE{h%JFZ@}JPrdVUIq#wCnk;00;b4p;qc&#'
    'jG!7$9yAD2nGgFjg{5ig$6d}P89hN3FI+MO(m%Ds=<_>K+b3Gd4mqEU`(yp;$OQj5h;sP+Qs96xWQ<4)u@7%)i{DkGD&+M-{3AgV'
    '`T*e3h5D7t;UOa$A=jkk1BMLarb$d4$3mWp)WaBK_8Zx~%X!6`tn<$jUk(%<`z&m|m|u+pl4g29FiBVxz&r)VpJa~HtX=dh8!v<>'
    'hKXiX-c(95dIs)fiWWn&XuP3F#GrSAWHYY#u$3`Xju8X3f$9te0Fy1MIeZ`m(q$>UREFcVPA=~9ieC=)NN4EiPQtD~3rg_>K@+kl'
    'jQa)%D99lf?u=kU(iyN>)I5aHxqkVl=SQu4V0LO@mK}yauF>c=5%Cz-B^H{OO(ORKG&tG}fDdF)^=qGRqm#6*z(zz~u;}2E+}i=R'
    'NE%zJX$C>yYJx<B7NA~4{o?xb&0E60EpcaiVF9F4&|o;;B4PH}GvG|ws^G(a4SAjEQ~mn#r_2uome=5Rx3Dz7oI~8}pME)sbHAL^'
    'h3#3ax~*%oG2oBxe1hBs&8by-56Vgy>^LoW!zJ7fc%%LJ-@om@8qSqlA3&Qq&7gU3EZ`q`L5ZApIv((qaqFOD;u5R5L{2W4p9IsN'
    'Y~;xp>E{{{Z@peTn3#Biwgbtz^t~E*h40l=^NCAkgidqmI8@YONlx3GA1X{R3ubdVS}l&k0P!s63?tu`V^(vntHCz<72HJ)V{}Qp'
    'WOhwCp>b?vV)6^bdOFGC_S0HKGdL3i7%m4)e0fp(SxL6>JOVI~U<iWh2uB4%TM(5OF!9q0^W-LU=S2*0`<mZ{S1FxF0wQ?76TO|>'
    'QoXTJ6P`hyM8>Cs@@am4*x&n2>1PcZk}lQ<qiJx(Ckl|DH#BXy{{a7KF=OD6x=#<51Xp(_a6Ms;`z3DkGCc9PEp#|ZT<J35f`-ON'
    '4wED_G6us=RS*KhT}kkOq1)Ppi^-hEb%;mH*NI82QxN6?#*;^4X81l-j=&|;P`ltyHS^_*K4|Rp#7~<sD~J0*>X<ZoDM*$#Y6uda'
    'YN%eh2>&pIQ$u^fl}OaMT5-RCae<Nsz5qVgLY}BD!>5V*vev8R%on#bPYN!j@V2O}7|<pzeJe=@Fl`b#Ow^%8g<=E$rO!XspO+-I'
    'zIGQcKG<Huq%3O@+&&gYA0phD#x-0^5Mh{P@`?3zi@qt4FP};zosFiLgLmUBBNDbuE5Z5!!|@=KrV^hgSGQ&b)Dp<@CwVpE9x}+H'
    'kh}?VR7luzV58#)6pzX_*DWXn`ccvDaskjv2iIU<#e`S%<-#Kv1|tb6qdmKv@JoO(TKOYSJmQ+h8@)m1Tl4W?;)WJsmZ+XK6kiXo'
    'lRFF3TX;;lU$<_d?m%Op`AvMm{Hy`MgFI{^|3o8#nubQkOdUV0TM~})wlGAAJZ4Y=K<k2Lyq-1<O)@a<WkzOtiR;I~uUz&ut0~|j'
    'gN91uyaG)f{tC=P8diu7F}()?lCvI!KVKOhiogi6Z{`$Xf7Pj%AvGl!UY4IO4Y*$O(4e3hU%gt9Fa$t=hSf;d3lhx{83NfOq%dkK'
    '@xL_ehPlCZ)rucY?)e#V$6j26dKfDR>e|8SYsB4Tx+tTPscX^cF=ocpEqWmR^t;P5Dk)SM8aRnwrVn^&BfzZ|wHZp7?io@dH|JF='
    'Zi=Wgf+0pDB{)|B`%<{mGWF-HA<e}?2Ph9%cK&!sWntMWwko|;U~T+SNXOt|@!^h684Ri+rcr6+G^XztD#wqPUo;m578>;ir~p7B'
    ';DmbAfbVh|1)v~UjS5oy>9B6ylcM2rq6DCar<)PD&X6RW1R&jkKN-?o^?iFikM{En?OzsN(oi^@XFXD(SjDI+$nuno0fr&bqD|5x'
    'ODv6Qj7l1PU+t?dMt@D-K=2D5jLSI9RT?WGBIGJgqbf*w$3;u{w-5Ti{>T3TmiHfc'
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
