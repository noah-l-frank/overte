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
# 6612ab8c9ce10c4f6086bd5f90f30e8583a61bff / tree a1d572299404f51cf500119a3e5bdce4ad75e185.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '194301ccfbfdcd924f50ead49b872554400db1ac5f53be7cd58a6690f62c8a5d'
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
    'c-qa~+m;+h(jDmgd5pdme#H5pr<gTs?rX)t14yz^SzQM<DJ{MGd={Ang59W$$Si7Reo23mAl2>};bCsJZSQUW^B@29<?!<Lb^JU$'
    '%umO|{OS0whxGL6<!N|$UeeQl{qlT#_{V?$pa1xFoYO!4`#<t5YpUuW|Lq^oUk86%6j|<n>b&TteDYUW-Y!cj$9bxoZ0hnQE0;OX'
    '{eO7*<1zjV#{1*=kN@@GzArmkX!`o;@pylj{@7S;983RQO=|i!n};-YP1{am%Ca_F%4VFirERJq>)v1OahQG`zNAn8IzIin+#mn-'
    '=}Yo!hnK_g;dx{6)Tg|dv#u}uG#At2f2X#smwIUWswv8;DdIOT?=Sw89*@t5m*dkPpQf*A`gLo?daBxD@m$-yTjse>DfLTTEm<}9'
    'erVqfWl^QEdVj^2^!)Pa`StLUKF#SdJ<RE0I;5?2i>1lSswnfmj;B3U)6%wCF%5mz&2=%&bvBnvk@l>+wN^V$V?Oq6+c$Gnr*4`0'
    'dg{wAn~HoGhO%$$qN~UE*Lr)E&tC3RdU*Nt&)4DpupFlKt^U^^-|pXEz3<w&Te3OtyHsUGo)4pwR2E$`)K)E$znb#4+O_)A@s~8c'
    'e2U-xe0kZWYMXi)8lTDH6xI2(G;^Ehb5RYw2VBot%F4Xiv+RE!s*6k4!`LrNRrf_x*2CPi)7&~!#hm)4ZM@~Y%lyOnKbIb#EGIHd'
    '_Xkh;^K|(9OM3YA@bLWk%MkDR@sIac^<bxJoTg%|s;V7}s+$`xxUJJ%cU7G)b;{$2U9;+=U+#rpUbkA>GF3xryK>B?wwSwY>Bey$'
    'nsF)GC2PAZrD?iu-Q#$9)n!=PY$~fZ_jc<d>xZl;+j6X?K6Ta9F2gj`U726A>eK7P#WknAYMN$VhJLKN*3TRIvdQ``AImhRqMFC7'
    'P0MoCnsJivrms)OZ|UxNIzC?h)m>d>nI}8sWz$Suno>X1<<Mqz(TQF4H1~6tU-zun9Xt%*(zC#w?w-={czF17aT{}2Rm;?*x~W9X'
    'lvha{E2?Uk#wKg>x~iJIa#dZwjmK|y)A3<BTwcE&^3-%?-85Z3tk+^w7Fj(uLs!ppk=dM>Q<Yb*ANTTn_xo?lcyayFIm@bQuItt%'
    'QD>e+EpShT8`6m^J%!BuJY2oL6X>eExOSSBvK#7Ru6=l=(B4k@n3vfg!c2qEGM818?fC5xQT{dj@%bUWM5McWI=;T7yZJDDc{o15'
    '9Hz_BrtGJ25YY2_s#E3li|%P~b!K%_JA(6A3{sZ<>TSHvj~5p%y0*z9OGvE`e(vMx+leb=nF}AnGCGNphTRLF4&Hh7H8G1L_>z8q'
    'xg3CMAA6gIqO8lVEK_W%?o&IuSn8rrQ=W+r&33rGALNBE$8U$}ld$*O;n|Jq1N=O^&WD$~^Nkm`?8Ps#uG3J>#W1E+E~4Q)SAAbq'
    'UBtw^spDmMGVRT~S-;BoIPQm6x#Z<2)i&ic7qgtr`)KB26gT^>a4F7hnJsyqGRanU`(|FHlb0jqJPmm_6^+cJ_S=VgDq2^A&qTUc'
    'cQVSkDvOlgyoX=Y(?hzyTi?>fo%F@%fy`|q3mD6GkpnH`Tr_nqA6uFvFLQp2<>sAy8y=+F^PL>uQGWX4?(5+>a+Qm_%HrZ`mZ}@G'
    'GzlYZs$FJoQMp21+F{mKp3?2RI*$IO-!_6-GezYx)uU)xjYZo!y+bMUow`y1FpFbN{L|Za@p!I0hWquaej28i%Ym(%tFCA(Nolc2'
    'QTwc}O9@;zG=*bbR9QdESjYb6Ey<~t`@@&7FS}!H)0T^jDjTYLbhRYkdEVu1C;r3(n#)YhwzT61wzQRQc>uLiGi&=YE1ROri^#g#'
    '$ghju+snGL>&hJ|?R#60cFcm^;Wr=l-S<ayISX)B)Dr!oe)9~<uI<GAu@QWiQI)*pllYU}{#c%0d{>tbOCPy?EIq2HrpYC=^v><%'
    'LAA<BwQJeeANY!1hNmxS_bsqUc(Y-eWgko9j3gg+UbVGD(#8{N<OhA0ZhuRsZ1wFb7>}<H^RN+U9FyL`k)C@k8SG+cX8)&drmD!t'
    'rpks~olvE}X-_+@r!p<--F|HPvMN(Q*HbnwGhoF@?q<h0BF?mAAKcM;N8RlTgHtVkFLD>Ai?J)xFwAM}oNQIjP?lv~kBc<xgYPXp'
    '{C0RcK78{po?hMMvaSf6r-w6@<2cq+<BAxECMm1a(2a#>=0=~(kL_vqE!quLJCv%5wi#0gqnRt!tprSYIm&$-AG{q^f8TcQ4wAqx'
    'r`uyA6CB6RftuT5$^_!k%NqM;>N}T3=}sHdQrPatwszAkKehlZ39&Q2^lg%bOi?FxeUVRck!q>RVeY5DX=~H*+lrHHJ+NjOQrS!7'
    't3DSf<9&9LX5rgzn>imB_iR_rf6uO-({JfvqpDW2_7EX2P!TBrWS&=-<*tvSOdWi#6v&5<?PpgckRDcj84$yqmVWA+!Hqj)jgNl<'
    '$mWd~nk#cZxRoEWqHl*iXS|0o4*@WgsZ?{d^VHU3pN|8`!0yUoNclWe%g6S0eQM;r4RS^}NIjMTb1fMhB5#Vy5pT+_u)``_#*gkx'
    'esniI!4V%`4#WNP20EbRs;a_8+x4TgZCO05$O-aMvYVIFD0Q0q5ASJDN>IA|9UT7yEgEt-tHP@S=|gVHu2G=oLpvA6$2N0A_9llM'
    'm%PcF#uuh+9_mH*59_b;G~}+F!abN5)5kXUe0+TZYE8$l32r@I&gQJA_aHiXGJ&$CIiT^f>Z1ezn$I5E1Y-K&mLjXX+fl+onB;4~'
    'zM`#FX3OZFDWEQMS=0&cDLi#qmsfwsc9!9A|GEM6c2zf}A=N`x)x)G=(#mZ$X3|u6OjB8Qy#`AD!E^oc?QuEWr|;F;<<Gx$={Mz|'
    'Is*rZm<?FQV;SYUSwONnJ4M}m@N~aCy*|IVNq$X#JZ(XvzIpkj@4FgP?o4avWZEtA+!5;Us#~hLOCPBSuGmau*?Jr;Otk2=ebS(#'
    'q~leMnJ;V_tFrE45&N$HGe~{@Czo%Fxr7Ef7SPeQc3&vyGns6ikF`V=Mq77N*X_%&zr3#DE<JraJU_2J#EZ$;*!TJo(dbyZG|n&$'
    '%~ECJSPgBJx+xoGF=yXT{(6kJe>`pl{J5ai6W!3a)l_NA7DAi)ymN!kSw4f~d?x$WJf$s{LucMkg%7XP{+J_+0(_?&zy&s0+&Obz'
    '+QYmre|m8F|Ca8C`P<?0O`@|Q`4Io|v1l6I52(bvXjtZ@|62mMDh0#Ng5bRB9xyS>T;j^ID3IDIP1?VC<%@@c1bj3p*Mxz6XX(c;'
    'X?Kn>m3b;gMZWqls#YB!ZB(sGP0g;%ih1mT@H^|pANxIfKBab6TU6ydmr(w?t)jqB+T%quhaGFRwAyTLuUPz4m`=y1boYzv@gZHV'
    'AtJO2X8IhJ_Ho-ZEtI*>qH^ywqZ)PUFfBVVx*vD&?f6?-i&0n5##NZZCEKD{vau_NfN`ZYlFqmr;bOh2z14W=hy8oFE~-qEC!Uo)'
    '>rCsb)aa_md?|I$eQC)Blu!kxe%!zQ&d`$2i`uapqSl6^w4E<55I3KA=R>SI;a%Qc?qB#6Uv@lmHIVnNnOnHNiriP&$)(3qbG2~e'
    '0*FB;`k&V>{bvb#`3}*@&ZIqq)HSe>wvgF(9y~xl^SX05iG*yqefe{@Z+d*a{2Y9D`P3Eu)LTajQD?Zx8Yr=QPCub*HCp-`HnMO1'
    'a;Y^rb6KBer{qhPy7(T-!XI=4bfGE6IlKM{NZ3~{hfiU6x{L*lqnosdE~{H*67uTWo~BgP4q*};JDJ8jk2h~&-;-!Pf9qwM-UG4$'
    'I>mr(;NcJI<K$+ST-EZ78@BPs%h%(>K0q@Lzajys<9kp)p$MhA)kLWPD|$?-W6!I);bA<bFEAa2%6#{)r{VE&E6bY3O!>Pw6hc8@'
    'U@ph89`uA&<SADhhz!FG2LrHlxe42#*68VtpzUd{qO}MbTy)!tF+yZ8)M{;#Y5&su6N0`S`k@SR$)XvN=FE*$LANT&!Ca5Jj6s1}'
    'uDFkG$_n%sYEAFP^Y@cStT^4yX$UBAuoK+5X==(H)zImee>yxozP^0+*6+`(s!uZfPyb31Z?Kw*=;Chl>Y_^Z*4Ohl$?TPiptS%*'
    'z}<_-Qq()Lq`&OO>Yvga#HSxO7Ny7C@Dh)18#o$NiPAJRNP&YiI2DtxS6R~HM=9Oho=)u!aP+;6ZIN~sUqIwf9!n8egDZ5#M^k;Y'
    'TA%eeEdp4#gEF&T)^Fs-%S%etoXyBiHG4&b=zx!Eu{L!hxVj$jMA~85x#Sx(7P0cqdl;U+9iQ%A{d*f(OI`R7+>tsi@UW?wqWlB3'
    'V&vudf+m(LMuqXc`#4pepUzx~&(BZO|JUS^?T!7vMkjfHD<@7#6j*Dfxq)X&Z@X^ReaUm&(@M%UH1G^Sx$oDr8Bl)P?gQI-0}$42'
    'UCw%|u`N&ur%6l|QhmQ_jtYNbkq+C3<a0qdx^XiriSu;2kx7T=-N$Ece6P~LRDhz2<Teg&r?;l|9%e+#Bui{|(62W4HNGD1=M(<3'
    '7jPBXIz*si=rMrwsIplQXxlar5Ez+uOBwvk{NtNDV|G70whbPN&n}*qkTBtELh7>U25T~4<TOPv9`e*zAK%zP8|dlnrJhOWmyrd1'
    'sseki(=E^Oa^^g`9XQ}pimJsgL^#j8{%_dXgFEY9(_?tj>brc(k_bJ*qIIpMda!fRQ=1>8G@{0+d9{s^rt6RI>Xh_|5kGWjFJG$T'
    'faKKz7rnbopqhP<bML4*aoDy{0jPgBetc`!#I9MM;p{v3`19g-(P{c4I7KMcK#s15dTsa{KFf2ue)zUlvajRg*Wr1C9gQ^E2=lf#'
    'sbd38kRc5KV*~&tt_w%|VH*F2Gj_TPcfr@KKBp)F+nEXgV%x2d>5|4NBXkIoTH(QE>EoMvK73i(5eHHbmG6#^vIZ==3>AF<?Fxw7'
    'Eo0aD7__b?iLM6*UrqlT_O@m^JKFADqA7^>8uDxJ?5T!TL<tsJD-p4g66$^ZH+%$dLV(NLS@e&wKtZxn8_-Y(7HSHFe;IimfV6(8'
    '8{x+7yzSxhbyuZ+zeV-_%6Sa9s&g~pC?iUsZjDe2sBPZf{1(6OYP~2oST_M(A!oY}2XU(MDN4NISa98u5Qb0zvH8Q#=N#fMLpo(q'
    'D3)9~E@V^)2rE8|7!N`a)zQj(XlGS_bT2zTvjU?gNPQ?7EtC;&SEqfH4^uZlH>W{1s-N9{cq`}n;jbUtMg+*BTv}S4lVJq0mu1#c'
    '(jcwEK)tZ&r~tq}y0t5|1QZ1Lh>G}Hm4s>x(yII~FX))&JdJI@<JpC3ay~qTfatulRHV07#0tm`)5|s%yy)gE*`yn)wC$!o@~J+9'
    'Kr|&x98RvR8QSuiJ!}=Rsx(DN(bcW;KtVu}R|c0^TWKc6P*AoxUEJ>9y|dAz-<wf0REu6bx==}U(yQT-Eu?G+)VVH1-v8`yy8ecT'
    'Wec@Pg$6$o*APXq-aj<a4<lNlPLt!HQ#D@n&lsHZaZ-!RGKc%mcc}V5NVM+apKbK(Eb9Q5n7(nJr4fErQ<OMe6~S0A#mja`mzNF7'
    ';blywpBJ=qeSt1Xgs3VpXjR-}Xjhz>Qoz&8Dlac{N_f`4-stuA<yZ&IGA?!76exqVP;_USf!!MY6Vc54lOGlES9%Ck{PXbia-f`&'
    'D6dSHmkkcN?0m+&g9f`w$Z@iK(krSXEe={`5gI)0vWrWuCq-iJ?>FgedDH?L`Ut-hj#P%vI%goaCMn#zsitof1AcbL{>OqRV#wul'
    'G6b?$ml>8Cz_-<AY!INF__9|G)Tg?5+W39X<MG?wZ*J{*JEZ|*_G;?drwtr|@uPmhYL)@f8p}{-IFEDxv*z_FTba{uhj@$XyT_MU'
    'eNUp7g*X9?Bmheve2T?7sxD=|OLD}2&t^@}VQbNOczg-%%o<_-V?|Hz&*$o?WnLq0R0qW!2VExpYgmFX+P3-JK~AyT_pSK+T~+<4'
    'DER)zmjhc79n~r899=yPq8;QF5PEJ0Ee3F=u~LrHaN`ah9}lnJ?)GeC3bwXxQfk*WZkfo9sZ{Go&LY;M1*0$w^_3gh^$_r78tt`F'
    'ysd&L+5!U#<Ouo4P&DJz4b%>#hS#n=9q-*Q$5RS_raf+-ePZZ9nW)+N(WmW(DKsy@>%rtBNYP{NWcl;8yIBF_yDv$@eXHe&=!IhJ'
    'ThPrH)~d+IFdC{ZHA`Q$kYpH~s%-Zb)^o7yU7!@q=w^$67F4skLbh6Hbc$&I!;HKKm{zg-UHt#!9q3$q+gK9Gwv$$1BxdBbe&-wk'
    'uoY^x(^bVSc7fJwxp&DqJ^!kEb$6Uz?+?H4diG$|SX$o-bkaz9(0G*MIwyUFUXIIzz$81laSLA_U+=!+N8YFB4Oml8aaKGsdeAP>'
    '?9Z!GVgk}BqqkPz*m)Z%`y2Lw6zzIPb>H9_Y0-!Zh+{aU&9X$>Z;p~FxCj+FIdx50=6}zIR)A?oGdjTVI&>T5w1iKB8%t3_g-oiD'
    ';uWUgU6sv^yK-?qVMaV3e)YF+e|ItQQU#%=^pzZlvA_akYIS5OGUraWYYtho7D933eohF)@W;J?7Bx~jym!U^6;jO*e`QD6($sZy'
    '=W7&_#KxnF{Jqt(&&yQb`dMAQpS)m+z+|IQ^7m>9EE*~a&umtM3#pUjyZouE$j|rl?Ku6q>*F4}=;0`;TV4;iI`})Tv=H)#CTa=R'
    'g3N!J_AY#`7RSTGyv4p$sfIF4Fq?9^bY~O^6k%y@0z1nES0dD@+5J5~9;RdUc{%+45~%+QeqN4iq1lnp$s_b0qbv@(fOIlY56H0^'
    'MAp%E*RB62Woq}eqD&uxZmM~NH5Pqp^>S6B65$f*jkdw=1C(92k*Ba)dD_1TGA5-^*yt!|L3G0iTn)1uk{BYHydyvbyzJeC|JERC'
    'Tye)&ky6c}LI#5MBMOmARr=|Cl2t4TmtY!{q&M#1l<(|*9--(^<p#_}1gwbH2S*%{6LV)FhAS(imaf`;*Z+3(w|A?hQB<oN(MejB'
    '>E4whz!(&^EK+`p3QOpu6ga^u++KU!xnS?(cj(Zy8rnVt64)9zw64gq#wo!<T^JNMTMH7*{P921F6ot?JCq?lc-NH|z4W1RDqs$c'
    '8(yZDL$CE8ww7F_Xm54-hEBK-1x2q%oG1PMDoYqsJORSYsnfvq9}|YsR>0Y(lh%2HJLLd(+=?PP)~atJAX&=<f3Hv4?Wx+k*!oM4'
    '=XP-X<=yGukQv<XXuAez>gdiYb~YF-;tNtosa*H)ag!Xj0^wuMZrRS^AsW9p7vn46t*5)k*YS-Db9qlfzRNdEooawCKPv%9=dSBo'
    'svG)BFy4rp|DipFx{Y2c-Mf~ym}^W+LW|IV7eIGlsR^B%PZ0Gzn5L|Qy@p-<q5b^OzL6d*>E-b4@-^iS#9*f%QT9>?$8ALd=<Cq&'
    '^#O&(O#V9$x9sZP)6wlsTcO!o$f8L<<?1^|J|0w#C8P+^iVMLVzycnU-?E2qYdcU&Vrvft91Hpa;Q=s7AK`f}Y-gtKV?Sas+V42u'
    'vWKwuv4^L5$FoRorZN;yT+f^oaC=y?O<{>Z$}l(N3;>C#y=5O-qfw1NzUsm6Ivi^5UL{Ov;L}Di#B7xEbM~+!?V@gpTdV1BIvgul'
    'b9cJ8PG9!r_mjDs8}*><6?<z8kPMWIvxE|W0XW5}Nw<AHu=(Q?0N}ive}22)Ak|4`$V(6q-6srz)H@abFI5`Sl92B<RkY84!&c(Y'
    'E@K8PR(P5<yi|fy#*fHj5n~WzF~{4~2hQEi&Fy;$R_62Iuxy|=fnq|x^U$Oag}}DFDe$d)Mn==|H9;>)>6VQ=58obX(w>7Kd}{4)'
    '5%>KKJW++k<Dj3?SjhGl6^|C$SR(~uR68{3rr7@y%Jg|h1yDuJ0XAy&#9K#0e?=c+03=}QR!|NIJq&QXWfQ04G2JV~F7E+<EMy`x'
    '?8q@8fC~YC3;6~4XqE%l@$TCFpUw1jczKi23@@ACO7Mgs*}+lPU6yLYRRG;?7GzZ4FX^(PecT_;zMDLrt)oD=UpEi}gaiOr((h^U'
    't)gw9U5ULw(!!?6;|NHl+aJVEB-qpKavVb~shJu?wc&9iNkaWZ+m?Q6xz|&tQ^WH@Y7`ArF;z`oQo!%tNW}2zkLf<0^R{X7g+%`L'
    '@^y6sxKG=4S?G{a5}Hita@px80zr`l;`Tw}&<lhN<ip>zrya&#NF#joi15SNP?#nCpTJ&K{AsU(2KZnYc7Mx;<^$Kgmkq{yLBc-i'
    'rD^nzVe{1l(P~<R59}dF3+rl$GVX8L(Np^8>sHK1W{#sH!twKB@)$`aM<5?m746%O<d!g|YCpQ6`{S3x!!E3)(I#^RrnsP4T{_v&'
    '>Pq$>Y+3e{ZpbP)FCX0z^y4`+8V^(2b(o+Vf#9xvMBP$vtj`;TiXP%POCmzR>{j~llhSbfuA1K3llSB8s7bV(T7giPNyjIMmsw<Z'
    '_`QpiBF!J&({p-pQ+<K$J`9h~UymERBHFER1tGioolQ8Z#9N%@npH3?<{*fpX#Z`ydVRb<4ws?kB~W+;JS$ObUOpg75yYGY@mVK2'
    'ka~osswqCYr<dce>ETS9y_{^paDx>)saJ+tHcogb8lmHmKlLTSdlB0kZ{E;6KLr~9lv4Z~51Sl8*Os!8`UT|$numAVg`FL<5S+%Y'
    'DqOK>E4OaPKZr)f-Pf0w$6bL*NYpniR$c|K2Em}h`b0=@zu;JMp=x-y=FLYp^gKNs9`{`Rx>{qyE))_`t1oF(C4WFzUZKiw?jWHe'
    'RdRk{L)$b{J(4^e2vn3a4{hm=3Oi?yK%&Jr(&a)#RgX7+@bmH8AWpB>$Ddx`m*aKroDP&RSh$fBtr$6BCGHLStAvToL>N1La7*`x'
    'klOA*>y#;7m8hCW;g3QFiZw%q8L4%JRIv*+kBC(L9s5z$q{EgGP&nAlH7w5sArm2O!@i0Sjfo6`SrH9Et<&s-8wxoSf4N-|nz#>B'
    '0>LNqO~Y)JTi{K6A4K_ZPn%`cu!{25Eu9!g-@maR6la%TT^%lEe9bwP&4V<WCbW&dy&{MA#z^L+I?evBZN-10GVZWsm6CXE;bg_b'
    '2{RdMacUufe8D<z7cxo7U3P!dzLsr!n{bLw5J%B5v_uuIa+uxAyb*E4N@!$DOY^}E#jU!-%9=4tgrf!P6&mV5ciIts^x~AM=s8G9'
    '(H_b_xSJEp@ySQ`f&saytiW<bIFxEsl&o|Dq*r<Hx>buD=E6FO!v&`42X}S8KVBbpJ}ezuxUBrv-99K`YwD&BPb6?25IlxHIDt*+'
    't=sx?d^rZET*7_c+eWsH$R2{%R8U`6!E!{XM4%WI09uPJq8!HP&CxrMh2Y}`Y<c+`8+mWY_=RST)}U5uth(HMYKkUcvi7FN_j2n-'
    '?vL|oXLT}<x{UZ#;Y3cWheFb?8UU9DTAi9m+Z(pa{w5;#2lf)h(D@~u!}qSM1niIprmc8I)ilSW3`DNbi14bypR83RsZKt&u~kGp'
    'uV319+-yZef+jsgnBZsIqX17qEXTMbDpbTpD|7{iZr#%v7WwlrZEwjC3>9qN4k3wyk}zCYg1W0O>nMwnaj5g#3lOWa+dIF%o#03%'
    'g$>h@fbBFVINNh-Zi8w|evg@k>KkP9o70kqV>FHe&7*(!#I_i}x%&+7e+sT*T7?S1DM(>hIDu>OkTdbZxw-y0t~unX9KxA>-H3`5'
    'HH;V#N%Jr!6Q%LT1A&OfV~Qya6Yw$Je8Ykk<5;Wth3tJu4ajN;tK`ssiv-+pH2vcbDE1~EP?ba0rsX3$I$J~By?hPVz02ES2AoBo'
    '!m^UZa7pW}uj_|t8a*%U7>dT5Q=@Z9rVbJv5e~OW2cgaNtz+NAta=GI1%snQ?p^2}6tc-yQ{(1)Y`sb6eRoIUX4e*A*2Xbk{wh}l'
    'QftZUX0z7P`C@iL_Hz4P);pfGWAE2alvv5}y&F|wHNigkj}v{UtZ6-UFytTReKa53(Qn^&7<`0x2-L;kCj)xm)SVm}Q@a`2O2@dB'
    'Sz<j*H|IgWb&<IK7HHa5dS7P29_j<KE@SM4rMs|)bZ13%&0kuX)DIunN%}qb^3kx~Z98i5zU{-{VZ<AnkxQaFG<3(!>R%;Pn3&yt'
    'WK)Or>7>1nsn5x`r*K6^tU+xF4?K)37I9S=#K1tpkfrQDwxi>Ydd#?=$jXAbYZA$fKbtG0ODcjeD#AC9h}hl^dB#p&0%JHnZBP!Y'
    'NY=}6b!d^dd1sP6iq9#@TZ^a+myiH{U>|2P;IySTM6<&z=2Hg4XBou8chdY}A6L#{isF-}q#e^ow(|X+5&<{zoJqyZm=eMP<t1Zj'
    'GNw6vD+NNQL{;xL_lf@<o7wIT0>DBoM6d3vZUceQuB2K8{{R{2`w~x(G=5++Aurs}P6=fpe+hRzwtjUPW_wdif|Dv^$4I~i9t7j`'
    'kzKrmTjyPnxHhpU<#4n_HLIml5>oroH5Tq5c0rT`nW=a_5_`Yr5D6!Q#(%@?iN6M`J!7?S(R&R;&%|5PRH-VNjsWeCmYdV8KXcE!'
    'wXwM&<mZA-j|h54E`yzVQ8D*P+d|3dBm;fIo&J_f(t`=j1T5vmvE2~AX}xhDtYRqQ7+!3c#_%Usq;DBd2jVQl+MioJ-m~I)GdNiP'
    'db77JlN`dFVwN|7F0}^h@J1U|RK3J5i-s5r<NcHeeA1Hy_OJbkHxOmFK?{zzMiS;7G^J{>F2R{tOz3bdT4;0&jfVOPxZ<6CttG<l'
    'U6H|0@v>M0bB`n?*4bs{!5X#*BRdV}-UDo_n|F0?p6uO^R2W1#k}c>A#CNXwhM9n)Pgv=a(#$aEE6;D<&yOt1y_=Hs#kkR^o=}u^'
    '4Z>qEr0Ma|>xMz?+1Xr?ZvAvq@z3_}X>EPu0FZa1k4sDehcK@!LL-T~NSy_>JiB#I)6?+$l`Z7M@nzW7e}k29XZp}ku<U@JB9Vvv'
    '>x><yUO>QA@D*3^<Nj?oXUt;%a3F6i29=usX8K=*0a>Uam-6+7mpMeUQf%EE1O5s-?c7w@3eDIP1a)}-F)58DerA>uS~n|EnKDW8'
    'FwY;`R8+&e?fUqvl*`F9P;wl`;KuZ^^vM*-ZQ$Uc8!DSyck~@e*}WmguEjVJp4KVu)fnTH8IUFyBtgU^^v`9<H@~-dIK#7U_Z9I`'
    'y<5l*)xvf78MGMcu2fXmlCdIoM-%r-f9sCU<)?h=^-By3*nr}pOt|c3Uxj-K3mW9)B}Va<(fDdqTO?M5lFf&=b86=t_g`;%Z{fP>'
    'Fu|RcxaQ274DF<92UG~NOSmXw`ryvi-oV~H#jL?P6kd9Bgbp$?tre67)o2xfxJ<HZe>$$`sy#h_eSL|9asPb+Iu(%euxmx_D!D9a'
    '_PBWwhp3<w8#Et^*WLR%Z)82%&u<ZPdR>jAU+@;BaEHsuiQ6lIS=2!WnOU1_D7p#Zt-dqxrCP!}uJ1pxqvQCCq)C-3Y~mI_%o|1+'
    'VW>psN{_~zANMW%#)NWs*c=*I;$wHqH3`#C_VkxO+Dt7?6!oUMFtO)k#2^FG!f6R#l2Og-_UkF4u<qYcV*8ywMJrw|`S1DVWi(0!'
    'ghH7C6+*`&A6X(KK*l=Y_ZZh7>yDpVuDrLIbHDriWX^wguIDdrCG>NPyUaW)Q|E$0Y6NJ-ltlu9fusM7T6+cE`JJt7rv5Gn2n%L)'
    '=zP@4Mtp0cBIXARya=B)jQwi=cl9!iAj&hrc>U`j_dahhTVs3#uSHLz31>VsJc!s5ga8I%I6&IUF-_?syV!aXB8oW#;Wp=J64#{|'
    'msZ4}5(bgXUQrYI<YfEP=+n`BIK&4`PX~RwAO2WL*BctM;1S0FZiaGoP<mC&4crMiK?x0buhs5XkfBcdAmtmL&Q^CP70Fh8Ozwq%'
    '8BqkFv4kTGOdA18b02>W-8(ZyYPoJ3thw)=hR6c%zQliS_0hxhmZD~kRGC>5p#<XEk_BFCXn_8VG1ao4?)qK$@1HlU*uq<+jky3g'
    'yMPPKkTGD2KCT-4S+ZZ9hM{S$Tm1A2;u!3D4_Fm&MkaJfi>ys}lWIp{f#Wf9P!DacA%xWx`na>qD)ckwnr>UmgA_|>%nTd*bu=v#'
    '(_347lDMdI{VDc40%1K~w}~_C`F0RC9Ox9<DUjbVdNw*_30j_lo3BjJt$@<F19^AldDM5}^t4YJn8$RKSt}0Zj%SuS7J<5qCNJ+9'
    '@2I6lH!v(+w*!QdVVyX+pC3SMj0`9=`y#_oQSaT|PNX7E#()XN{y#OHySR;2lCmuY8S~H|aIqlNY2undKvq)=-Y}5Th!5VE^HN{='
    '8qOj5hexo>LXDS27TVA*ChJCcG@@-4mccwwHiI9Hi!@&OM)b5sp)$VEjpb>;QTbVaMTG^V19X`Ar9(RfrN(W_^nzR0b<4jVWO^?z'
    '8;6mW&9CDbANM5~Ous0n2jyIW!V;w3DFC~2zIyHFe;u~E(=j18NTAAsP{y){2*z$qWm4%e8v%Xip@rVPcDU1@XieY3x+LZnq;Zeu'
    'RK;Yez<dpKT>=B(u5@RH;5-6`SZ?PrL!mA{xRXt7kV$Gx0J;JLH$2EW>BdA@lp$lIR_`rJvZWfY-$tx{=6da<Rv7ZrQ%F%a#)M~('
    '4d*-eMHnT71y~vQGUVxsmlKkpPr>8<<1eWMpS&b`tq}7jACBLj@1u)N#s8Dh%rQv}RaYSO)!;c%>NeHwyZYsLSalVv#^Y|eAHHnZ'
    'GDquKi#*svb0`JEEh#SgoJv^k6?QO&U=_FT=%fq9_E6@2*_x8WQg4aD%3S`0EXWd1u_Y8RLHgEJi<u0@zW29p2W#<2L41CDW-lyH'
    's0|xXj*ecq<dtRUO!$cD?z!yDVe4XCMyOb8-XvQEQwo569n~~wU;Vx@CW?1O83D8;4{CX=cq7Oh&J21EG%1T2tHl;9ntoR&uD$qO'
    '7KEY94xDlAII}$DF)hGm?XYIsmK9*3ALZ^<eHI(pgs*TOr#vPg&7oi{!va4KUX;7kSE^*@+rL$+pIc1-X4J*4^Vcmyn<c2RkxFnr'
    'gc6`)7JMaULo^8surtiCMtjP4u75(CHw*$}x~j$&5UvM|guA_ZhBwq4oeGbg#42UW&K1uJfj2eno?e@22r>ef6rBmPKw7i1iR_W?'
    'EV?#RvG$ubbLqDo9G}QGpnjWE$J!VyprDR<$uWDAdJ^}&UWE!=gp8vy0(UcG`@ZbIPU+%NnzUtC&Vx=z)94A40(4$E(T%~j59WZ*'
    'Vv?{Kd5ihFb7_tYzN9}NeK0kTmtQ*PgD!|rG46W`DMT42c$6ZrPD~T%l%jgRZUd{3XJgnEsuOMmpOzs8f&`FSh3niL9)&q}fT8F`'
    'w)c^*6PGuLsC10Vu^4Ox1{9?DZpP3teH2@$i9$?$-4rz(j)9m)p#J@Fx_fzj*z#5j)r~s~T8mgt#+717Cyli2uq}@fQ`AAzrtCG='
    'U6HkTy4&OAWcc+ekqBkP5+f<(qtL1;r0VEG%x`0QQMPB*KOQEcgIVa>X-^Y;It0K8J4!{?#YAoEX<fy~tSoBTZWof{9gCm+R8RH<'
    'ciZOUZXh>;KF<&ntBXL!P<(wtI(Yel2B;MiLXAC319g`_uKVRysRKRDOgwUVfTtEo9^Z3wyQn|c*WXl|_9DNehhN#7f5xhT!?-p!'
    'eDci9Fv23{K%pO{7(_cohR=rp!DTi>(}%n%X?k1qG$%YpMvlQrTMl0~%Kkd0>VN}L%V9o59&!NbN2J;jI>{MWZcIB@f3q)tn=vgF'
    '`jR%DI`93})sfnDeZ+LZ&@jH)b+|i1>BLWJ!G7l!RwC!&qOmPNmajd6J<{<Igf5YcIzv@~f0vxREQ*s&`Qh7&=T_&gm(7_`qlZW>'
    'Mnl8+Jns~+25Jo3A(nfrO@HeC{Qk;UzVV#)LB<K-A}m<ev8Y(RZi=CfOr=@y0y(#I*KA?OGpDTJYTzKJHOF*i&^ajpg1yS3sxrfS'
    '3ctUNWxp9GHtaS}Qz?42uEmN!fxqBnSkP0+h;+Kbs#6bj(KOv!^f<qUt;p-+PnEwv{>)y?kmAX-SjXv|nE|{67b}uMglQbhm^Hmw'
    'F`rg^UM-@Zch#kgH8rD(z{@lmj77-tcv|lnmj=1WNa^Uww&UJ~A4AD&M8k&CS<@hx0)6x~ns6OLl9UNJ$T3laxQNha$TwLQ-<MrG'
    ';hTbQ{xwj0Jp<$=(UL+f&^pP83Z@+bnjrs9o1F0PtFC01U4Aj_;c)cZ6dERqn57LTX6#i2N%juf2y9q+ht)e*j<Vvg&8=?2AHg5>'
    'IE5%Hg-kEfAtt}!i|G^Q`kUwd-bGg)&70VUx-H~Do6lVKrB;*Ku>ixlG=~Fwj$)gdQ&HV=ZBRqzn?$;|O`Pd7YR4^wZ56<uTN3t4'
    'z(TC4bFO{gL@(c<<M{cC$@;o=S3Fj+{J5d+?X+ZYyx1;w5xc`0$N^&(+lCk_Tw)|>^Uk&3RE1Kq%gee5jU0-}rFxcreeg~~t3u*v'
    '93NdqP8c?KJC|MV|JZQMGWQUs4PzIOp?h+ihNZIhzod7hLM6_H73^H@Fs~L&!><<u<pNOG#*d-dS>O?REM1hS9bnhf9>Q)`3b^+;'
    'of<9==~cOSIirWCL&LzB+P^Ahet+SYOucPPHtvj)LW<oFdl&xY_1on$REMo$%)X{l&qIsAZ<3(5iM%!p7<rM!{FY|tdZ!^|chBD-'
    '5Emb?F3u3r&(J%T44oSDfcp?PNr`h%T*M72z_NGUH~Q`NtId(@0tjGaDOfs0lrgXt6^sZOv~^bPW?W2Hue>u-`DArYunv+RT}d&*'
    'sI=7nHqr>wmYkcaaoP04{=WY4`0GX=b8XhT;91f4p}!f4ruk~Hsl^Nn&acrP)!rx(^VT;MQ9hb*NG8a3@e!->*>eMc!$k@ytm+)^'
    'y4t(m>;21Nol|<bEHrv4JZOWK7Xn_eS|2U^n7;{(XWXn^Q|vxZZ-YOV!Sef*p8##4DTOa|K*})+3X{Mr6)t<cxnK~gX0XrB9sJ;s'
    'ylZ*mjHEZbco2TMsfHhIAb7w$w_gerMo-KnhMmiweUUk<-@km_Km$VT!IPGwBAtw`B&#I#sral9$92C(WG7YGx$yG@UfKYaVD|3X'
    '83}U=FI1kFRlp9)0}Lz`YJ|<Uyk<eqc=N->JBSV!_98=l-;P$B;Y~w$`wLqnb#OM<VZVFbU{b;Ib^z31!%*ughe6S8AQ0g+EP`>U'
    'AcLaDw)EKSjnd!Ui+(Voy8P3rA*QB{Ssp%RCz((mIu1H@#vOIe7~urF_YOW`wm|Yf@Em{L$lwJ-er3VU0zJgMDmkTj<%=L=JHeae'
    '|FAcgKKEnR{3>n8UaK$^lzTMc_@`l|_6|GOm7qyPD2gf=)83Nh)a1VWTRl_upbOU_6Oq)Mfm0j9DFyIwBi{f3)y;g>ig!3O7w<y|'
    'EMG+q<}sbu$O@N*<uPT8sQj7fH5zy1W!J5G%6JaX#~pfJLxQNk{lp@qQ*AJMqA$>^pj;-AnYfyVa`*3MU3Oaka^}PRP6^1RjP%n7'
    'wSHBrfP=nI<JJ*3J#*R{MqVFRDDm|%2rU~O0mN*Nl|6Ad@kw%OU$$C7|08-Nkkln&%if#f<e|B*Wbl=m>s6wWt=Z*_49#d`4mwM?'
    '6_p0xakA|9mMbU2$S@Lp8g{sAn~oGLV&^z!39LkMcXJc7NkW8?ue8j0D>I-9eE9w8^oBp*`A^p7cN?UcKDc|@&Gd>*3vFQL%EqgW'
    'kt|UzsbQ!G^J^A<n^bikIdb`^)nV1mm(ERvf9~f(0>bN{ia{1tj0YFTi{h&F&rbdOtn0%h%aafB9VVF$XKO}JP+#+yE-EjZ=(F=p'
    'x4ysZ;EYJzhnM*i>lbLjhDRsgn~u0lLxlAmo-`s=9Em(e_h1S`+{R{;oA8%C>{{4k*4`fjY@@Bwb3)bfVMmKqkBDPX*c_Krb@jsW'
    'Z*NdT7;C^YWh_{XN@OOaAYJV#(g+qnK`=BIXX_3*&5zl2)WSN)wBH3#>Qi#!2#Ls0)jO#V&+P{LIjHL!D?T0`2~oBZF{M*rE@MoM'
    'tYSdHTK*f3AukzG6{C&3ZFBUqv6VkwP{A9aO3*Z|hO!KH#vCS(I_9cj88!eDG`-mb2o(6r$%LTb;ALYvK?|`k!VGANPd4UC1Zf%d'
    'Yux;3PTmdcx3UrgPW`40T@O@}6}MVZ*6G(9M{o9n7>4^OL<8wX%6!vr_*skk+wgrL<EOWu{oVF&_s~Sz?jbA^VzgHkV{M@zoMZ|U'
    'A!7tVJ(IJH+ici98`?8ek%E~+D*>Hqo|>qQp$+OjX)!#RKS_)yz?UgLw4Hs2WHc<wOlD#<9Fl16L)>Wh@{pyJHWhbFxv8_hypwhO'
    '<KuAHm`9k;CXH$IM<H57Bv2dRa3?c6&BqBU8t&JoZ_Ifs@b##D_xR=-JZSC#7ib=}hCI4V2%54$7{<_6p)HF;^)T&Q_$4Y|VtYd='
    ';wfyFCfdGZ_yi9j`qz@~LiA6fXEKYU*@v`YZg;P}N^nnCdwP0WM^R`NZdsVJ!A2Mw5o*}01i2$r)6CUW!5%o^S<*!fd&MTMq%ieB'
    'X7&RyZ&Gm<Xg6!FEGm~eAZUCyrk&gK7Jl5pFRzhV?fLmdGBmXc1#388VLssZIroA5&!LBmj=5<9*DQX;>C*)6gH^P0K%<1oLI&*<'
    '46i*{scvBaxZM@2Uv~t_Pz51{12GZP$dW%J6v{(U(8Rdw38-jP(AF)FhrZnXFfe}qU?Qx1aBUevaI`XSJSOz$Ib}5JeF!-a1;BvQ'
    'wHr96n7d}70wc^lo<jRJp@c~EO)KjnGr;}n^`TVm#pYnF_qMQq9+eNE4VxN8v<8R-0jCYREBhK_ibA!HA<3`Z#{OBXOQ`O}8~>YH'
    'F-(UbydW~_t~t6h+<xll(cHF!H<r%ja>vXqv<QqlNhj%)QM7@Rp|?><u(K(n13YY^HUF`NecewA0aho)n6NmFKXm~DenHR{hCpjg'
    '20=OBl#>7Z>VKs;t_CO@sW;Rl9C}O|1q36CXpzbNqk$AU9{8O*v6?=#jU7x&T&TRCRNHc4&311eZHZW$H((w^G)yQ4*LL}b_OW|3'
    'tMMwTuRgFV76=@kiZDp;BZbz)V-uz>Udrz3&BTP(yL}_S;&R~AW@a+&RtFjvwZ%$Sn_9P(>L@(9+}T&}0kP*Hec2XY!fQSMP_q?b'
    'JY#r?X=?I#WLO3fwCZIC7}_L3{B#4);bpgVU+BU|ibQp(5z>bra?o2+n8dQKG}(pgUz^R>hKRT6n!Bb5TBch?5?Pq_rj>rO&TN9X'
    '(X%w6{+zBpm2X?vJ*^g#Z9%rLLQA7=Z0q$JSNDV^bd1r}_l<cwH}2#6VAx#_=eWQ|AuUCW(JsP`XN+`GPJslZ%Z&3DLqLn++RdDL'
    '`qGODC+RMxRXuHV2wSO(Vg~XJXoh|24Nf5e$YPxHFrd&%tZv;$40m`~Gb|U?=J-*)_BLi4&UqF_XX?<^nzm^o#a-I9`#x><hu_)D'
    'DZ{p-haCz$oUBDvqp%1Ee6L33g>ylXi1>(x;UvKX+WfYy>|u~|Fq~otBENfHc&<5B=oAL#s4wRA&M{pZtaxqcg3xpJ+UkTLZsCsW'
    'f?!cg=+$!(Dz#o*bh_uLMryBmx;AS3RkU!o3-}oc=P}gag;>S}E4m{*uF3!E_+C-V1#qZWedSj68D_a1Oo^dK#Yokop&aicw+-80'
    '>V4nN+|=c@x%P5@`0~|Rcs*aJ-!MZr1P$;Pr?8H;s?i59M9Q}uGSmhm+r$VBjUWtPn`M0ou<s$PP$T)hTb_KbhfOtyAgR-=(F|5^'
    'nTo+;M6p5|D2f$PkIeq_+O3G<hz-NT>!V|`)`G|5vN6X^A3--snuUCXJc_LC!{APZ?U5mu=#!SyeC<OqqxRuvSIJ-cSg3w=Sg%4Q'
    'J$l>*JuRkkJkR0W+Qh+6FE&x$e_#5C=EnL$t}%noVwzk?_+z9ABUYU}N+0yynuK3ZO<d=(IbQq8B9LFl9LMUE@MO8dCx(WU2zxO;'
    '&7DuTh}9%)1RbWneIJ{oG4nb6k1_8|oS@J}kY1PYaWTP6EfSnaw6Ux2k=Vjjiit9Oo+0lHp7R)Fz?0U~2}&sC?wEkP7-g!X8}@O9'
    'g2EyY8E#{Ni&ePn2+w8|Wg=%6v7}nvf3oR@UF_5{=soEt%Y&&5wIB@J^}m#<eUz+B2TUj8{c&}bc9Qtroh5%;B^nM?PrR>2h1v<H'
    'vte7oeMU3aq9BRP>x95~?H;ZpVJn1ru80=COgAg)8>wYB1V^}ukwhrq4#(9GLUdT&gw8F}?J0{K@i4DpCJ;oKFqKDu*@|hy86vwG'
    '!W-`D59FFj^Ha2<Fdf57NpQeH11D1|Vs0yxW8!dC4_BwZ=N<S)BZTf6daY4RoQ9UJMTuV`nse_m$%9fZY|ds?o3=}F+eRLbYe;vq'
    '9j0G5Tqgh+Xti-lLpJ9PC{Q8YSY3*ym^r@$38uSkBP&l~&x^?<m3$wPOq_#K%zhhb61q5<!O2Nb_n5kPZM1lZ^#fZB#s>KSKjh~P'
    '^gw4Zi>ZNFi|#HP&`9S$Vq8TYy4|4pjaPpv=f3K74Q=Wx1QEsR1YM05Zcy#9uI;Od(WDrUGNQb>Z7<ihwizXYobw<XW^4#Z?zBP3'
    ')KXYt_@<li^)A}+w%we#G`lu}6NZ%JQo{v@X;do+yv|i?!$(_hDi1#V)vst3ou2dao#IpIf<iH-lg4;uOw+NcgA0i{KDc>#aCth-'
    'cx@{9c$kjgcd{K;!z)r6W}P6|60^})dq8>ce#?+5@NzZRZMbC@r}y$D9a-pXkwXnK#(QCKV(<pvBuuVQk|Ep#zg+$iO1kYK6F=R?'
    'Ih=6sh*1uQhb_#-Tpf3-hLluj3blm$#=$lEhYSflgqTAcFTd%LynV}8kYn^Jcy`cHELjXH6HgUSRURHk`H~78^bB@>b>6;i=LZt)'
    'Zip1;O);scmIG;;Y2!`qL&GIpzO<M2H-+ucP1|{MG*@DO*&~~3gMtv$ZS`D@1z==~fTG-w3LHkH!>zS9-1H5d8NPd;OCA$ZhKzw8'
    'C4_dS>lg$yhagfB?9ha*Z?;@}DgSx@gk)eJPRB}6J!>yv9|(#eLWv2HwAW#ofm;X2#jLtEZ}fJ?v|`y&=NSvVSxm&$0}#T3;l+as'
    'GI1p%d_u)WdgdL0_GPS2S6#o6nV0DIhv8LyIjl|to9rK7OdZn-x)7n`PkL(zv-GP#3BAE76liU8?S}l9GxEHq3kG<QNMhhe9};ON'
    'Hf9*C$AK|C#WYQZIO5H<8`)1Bj*-}dzHd<Pg*lGB_-|-6t5p)hWi7#`Mz}W0!RgK}^OI@rgQ)-;yNEF2D-J-N(1Y*-NE0?26;dlX'
    'W(0rQ@hf+6f!h0*GSf}d$1Ph2ps(4{Mvc*H&6i<yO%xbzF3YtaO4PSLkC;TcHJO2Cd`4apF;bY1#-t2>_c8X3<))Ox3~|i7?pg%o'
    '%(A^ZOJBqNXQQ-1+IAMZ@W+BsRzX0-S;=ECHw=J@a<q#3E4Oi0@xSe6lc1xAkmIe@RqzdikKs;Xm>@$LsH-&!0o(BO^7?IX&<%aJ'
    '{P0v~T@G7>ZCHCTOA_@pyxB2mniyd3o5fy&&-rMZYd_8t5BV`|goe==cHO=(#mdar5;t*y**~>$%Xt^zJAK)?x@q-&Ea)x(Qxjqf'
    'c}F-Yvdn130zGr+q%NrabyE0i-@|HKcCskh17!y}XK@fY|L~nLvrfj|$EMVJMNIufKM&f*)-JA#NMl$4o1~Du;UVTKQw38|RyZ@N'
    '10*)3ExyXus^7gczF$)3`9d2bkA`5|6ZNx=8g!NPvb3ag{FIP{5#LX7caOVQ-{BJH<HiWWp==FW2JOX*C!z85k-{4`8WO7|ZL)Lz'
    'Gz-}u{mj*DP#rQ>`jVv9=Oy#6HM%ic`Oy@?$8OW6&F?wPym#;Z#XG`;Kd{Y=dS~uS;f5sun_@z|rZOEXWxDQj)9qVvcVJ_K$O&6h'
    'Odp2Vk;`W0gJ)ERg3Dz;1$kE3-Ta~JH@q(gEYZ1*Xz8lT4BQ^knI34J!r}ZPpBWApCT{(%6(eTtQxXuk<CVEZMp(LRQ_|O1i9u|P'
    'h{9$lv|s8?G4c<~?uirzz@+edY+{g)`h-WYA*pe!AwVSW7&TCjO{>WtR>et<KJ*6t*`+uHc|H$INkiKlC%PvwB8#~&td-2}*{oTA'
    'Sas(OL6eeKJcWkv$<kpa3#h@tl=W=ZjW~d27_qX63;)N$J7zfH>av&NBs+C6X|=%~Ldh5)1+_xC^9E@90SNCceX7Mj{g|+SdfA#c'
    'FE5q_#fVNu6_BGMW^%)^rnm<9aEsHmuJXG#qMC9!K7EUxAz8?9|HuE>&>w*b%#l~fWg@?BWem1A=^E7`kD#$Szcue$+5WiRnKc;*'
    '$d-ve*U(Uz@bT|}**y0|1-Y*@M3T%~IO^?%E87*zp7H+ewWA|xE@O&MhmKJDC2ad^vza-REeY0a7Y^37YrlcpJGKDlz!OKqQw8aJ'
    'g+;1Kn&Fl}kex!9kz!KyyQf;!^Adabq&!@VrTwp8o{tX~elh$L9~aXohLaHV_2Dy5#2B<Qz!x3if+zZJj$@TykTO24ZB8iL&yVqs'
    'cTcv2nhLwhKr4_^wcZIPZx~pIVnyv%21NQkCqL$Zo~LU+e~RIo|Ml|w%cU7ZMGrC4;+;J~Vgx0(bh-&ML;hfNMIuM>zLZS}{PgxC'
    'e=f-Qiy=f2F7+C>jh`VB*O9LE;Rr5;g9*W!wTx1KX|>=}$KQQgvG$Fw6s<Ut2fJzYf=;Cwh-iB%2W`R{*B!>dCH~#I=~-U&37;c+'
    '3+KYspWL1Q<nFs^!R7R&jseCfE$lCOi5Sm@<6s7(+$FdUAQ*fc|Lna@eE+>q(U*PN4usUzDuNDho`=9kvcflyaKAFtLd`ye8I=Kh'
    'KRZFua{W9GzdEPi|8gVfhNHaUu_^%7&_IMqvfpAfalx2G{yc=ZeYIn)({Rm~|NHoVrTaA={GY?i*9{ET#fqOV;Z_I*7CXjQIS=bV'
    'ya33(?e^yd>1lOMlIiQGGdqJA@%Xq|_HmeH28qt5S%Z;4uYrl$N6R(H@=O|CZUMsXT=V>&8;m-!JqFsD++@&v0Nqq*#xX{;H^q|1'
    '78vu>yzs{*Pg(xwl|i>LecRMjoH-X<5k5!6jf12GRg6|C{7nc_a8Boa>&=qj%LlexzYdimuQv2F?R%bpG~9HaWMh2$v!H(bl#=$7'
    '^}f8Cqqy-r%YKNiD7?{iDH9|^!#dObBe7s|AvWO7_WRajkoK}QbhL?4Neut|AfwGiKhHPDbVMv1$FQ!Afw0rNpX7A-bTT@4{`~c@'
    'FgJ(Wo#wVZ9yg)^CpeN+zKU#Psgz;f;Rh!q!Q^3zn970@v|`87vDP*x!f1Ol;TU&^KPamX4vRn;(p=4}atH+zv();h`l<g|@M#5-'
    'w~VnvTsR>gXW?7IOqm)N4VM^}Ijq7BE7sjoW@*QYuaBF|e5GNDfDZKRgX*F!C$3k~+P4WF3T(+#Qr+<0YI6#MZS>|pB)Go*=Wy%V'
    '{3fe#|008s`k09dSZN4U+$*Twbx6%AfW6uLs#T3mIBe8RW4N;GNRW(L(ygHcFT+M7W;5Y+m?T%{S-NW3%?oS_8Na?2QgsUM3Il~f'
    'pbc9kKx-S!xR~0JU$f|`7QcL(P#Xp8A8x*eL-=5ESX7LVG{R$vFW#y?XZGH*ctfAo&*RfSU%?#9;WVIm$IBhUPC1Ihpzh1Taz>fB'
    '2vJEW#mNyti5v~eYggVw6CqsSY9k_uvn=;;Lm0nE1H&gJ6fbO-xmOie|LU(>fvF~0(D>0eR-u7Zh8W1<+E%KrF9A0Ju2$yPF1%xI'
    'ZA79Voetr0BPoi}f7lMx>_#z%F>CNMvY+A)r=_2tU(+W97}?8e-}v}4Y{?b;+`<WRr^=X+w2E*LaI`&eH+anjEer4Ce%G4Ycbs+s'
    'I(0R)j2Q?6hM2q)D2JNW)e6!nTtIT+UCZsc;y|wWm?pTGw!W~_6|cNT`UiazNWiF1)N&Q-b}sm`m3gA}QOEN5r^X3af3r|MOO9*t'
    '6?>ZchyljFn-rZfhEtBcBPX(Vw~7nK9lnGOIdc;rhcaLM*TuyTQE61WmV0!4D+V`)D-^5V4^4|q-lq}{7n#2|H;NH>gx@@jbGuzD'
    '{>&ZVFLB<Sm(DLh!!{leh>wULv4`1Jd=`|5OJK_5uEkEHfHp`_q*8qhYi9b~U{XM{Vfbp>C=uBL=%P5U?|u#Exc>H^d*=EDX`03&'
    'u+%;{vo3KR3f2oyRz+Fhz4kJ6?=LC;IYd1Dv>un|H}jAUtC+lt*0wjNE#a7Wh<>>Lhk-CxSs2GSy6x4gZjZyL-Ia4NF(+UrKj2Zv'
    's0~k?0drT$*)WwOsV}czT2p^MF3XmTo>MC?T$zIOFWO=H{6kRNJFVn_oG*;~=l!db3I6LjD2I=)8yrwW#zb1gKHkz5zpGhQ==Hi<'
    'Bxo8!L?A|%?_YU4JjjwDVx3qgRSCOky(m*_jFTSBl2JIp%&MQO;oe)*I{&=ic*I~S0GLsbWw<7+GxqRpgQ^hTljZ|J*}Ll6MbEPF'
    'jUlJlg05*kmwK*zXiS;om%9!{5GsKCF_*c?u6W9kG3*>8Mh7fSDWd@^DOETocKI>>0m+BEw+@2qu9>p^i^CqhxR>E1?E3v>L;Hwm'
    '7Kb<sAv9au8p=ReBw6f3|LL`>oYNI&`{D6hto&?t>c%WPhCf3VquYXrXINLT(8jPybT6R6X){n>g1+~!eZGxO(z*=*SXN4;#QLa@'
    'cDumID>-!XF()hT#V~Dd@+)F!{Q2GYg#EC^ovi~4kV>J!_`HLJS+i&0Oj$(1$A68yF0a%6^~0ZXxffX8g4?H+rTO_B;@<xB^GTfh'
    '`J65s&SKTWzBZcye{%bT+=b@k7oee~m~mAi+VX}=+zvdvy8Yk3?LQmNJGb6In`vC3c{moTlrf-07>$kxzB0ECC6gnu=Mp)&V7?Pf'
    '|6(IAW7N;hA>Q$Nc`%uH;*%md4}EV8yyAPcE3Spgh)#3uIP8exDV(-_KPpU^h1r~gGGw4eBcAo0G4d^ZX8n$ZcY|$p+`?04jIP8h'
    '%&wIaF^)|p7Jh-Or&CzmzI$`T49;W#!v<>U_DK*nNfpl{fI$d`5L8<n6@<1asJy_$ckB3*o6x5*h#|w%p5Mi*RHqSAIdp(nMULDu'
    'dSh)&c!oR$8D9tG-TeId>C1Sx^|P87k{+xNqiML}ivkk#Ow)#I5b)nE#K1u`es>Xqt4}9zJu%1qJRg>Ic;d@pqr)k2)n(#>M&lC>'
    'lkS2r24klh5Q5>Z5<D<;v3KFkWDfIha?gZ0xW<qYy$M^Oz$6?Tsw2ZgOqiX9y$k-OX1-j9Ofh!4^V51}<+vZ@94SUG1^DgG!Gm&C'
    'r)KZUoA8gxAWi71C>(1j8&4Ql4XM3$kqK@tJKiY3%XcrCb*(qcna{)8JlSw5#oJO_8PFD7`XVG5VA>Suu&6_>PO-s%>HWj{*CoZ)'
    'x9;LaW&o#Qx*#Sm!^$ruD~uzIB&~q%4W;y2{q4AK(eDc6%g2bMGm9za@NUjBLBbBxN?1QIoCjHGDxpoozBPA1E#@bpF7l5W(7%B$'
    '>@w)n0PO2a1_9~L!6fQ^3kCxHEu!7!k8=)V3X|Yy{XI$Q$SC|2mw16lo5op%xy`ck0G)Wmdm3+ggXUX1JWSkZ5&96-YeP9bfF5@i'
    '(_1{IrM_<6jll^t1~I?MQ%n@>01u8NP&I`$iXh#c3NIU*>z2e(K5UGS!c|g4=2*BonME5Rmqm}ai+m;*jap!-(v{1;Wi^*COte=|'
    '8p>myj)%*X2QxO%T24hn5QumaReRs=CNM(w?HsYcDx;SXYDyU15`MZGaCOW>LqW^O-K%X9hNRFmta<2qA<<yMW|BQ3h2eVy|0{;w'
    'm>XPOwc^hv_xu%dXD=RudW;nWewH|WS#UQ^7ZsdP?X)+InaTGp`Yin%kC$gug6s?p?1Ekv2Y78G;8q8<86_<488_R|FITO2w~acB'
    'aNUxGBG)NqcNwPsoKmE@5sc~>5#IlNNae<|yV$CFsZEs1k&fYE>9n>(WH3}ircuSnX{PVh`yK0_FTZLoHdtut4RC;BS*HP%=*wBc'
    'X;jNxuxcYn`P1gQbx(?h%aH=0$I}gcvlX9!>d1z?PH3dma53>Zo=5S1hW2j@uW2X_=UI<*`B|I&h1(L^bYZuOjwC2ZyVo2tkwf~T'
    'kS*(J-_qM@i=X5o&7u()b95N<5>`@fAlCS(NE9^d>i^V&|F8e!{{fOT9G3'
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
