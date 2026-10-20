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
# 7b83924c8485868476b822698df60011d322c180 / tree 7d06f1df9b47dc0ade495ca82eec087176766cbd.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'd004947ad1a98072b2dfee19cf4466de4c9cd2ed457df22962196366e3deb0d6'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j&vWAD4sG4cXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO-_qR4XpQ|CoD<&(e5@^)ELInGnvWK)+fS-H%4'
    '?*HKBkH`2g81IkcKmON$`@ZaGq3P?V$K(BB`eS3YaV-6JHL2;_Y#!3oHElbMDa+byDVuT5mbR&etb2d8$6@+)_>w;T>-hBRa)12S'
    'r!UE`9bOK{hv$vO(>!KPGk3*YbyZoWteN_LY|5-&QeEalHl?Mm{9nGi_)~g3J|A9=Pk(%xzNYEdtrhF3YKz5lZS!uK=RT#>TVlzo'
    'x%Wf+ZYYZ?jn(@rzNF`uPtUK1m-J~)kLh7f57QxStvmF7O{&Mb7>aD@hGMAeu^h|1E%U0&ro1let{n0`>u#;pj?<WrecSfUT-B*t'
    'roNu~(kewh3`5yBd0%(+`2JdNukzW;eM%26pZ@te+#i<1w7%8<`s3UE`>Xd|J9kSq=Y5x|tjP0Wbdt)VYy9M{E|R~S^0wNw`qS~3'
    'G`)O^-~N1gSszR3p$<beO-pL)F|X>pn)7zZ`zgzt**jl~)bCmLKM&RArHdtHb2FFyoEO>BWm(qudD+bE?8nzdm(5)^RzG>S<CEn?'
    'hUxy`DSw_0pMOaYzaAc*KYtnGJwN{O{;D4ARE^VAj8#>&V^MW;;{~^Mn(NMQU+R>%ZB|^f>Z4!og<oE`TG}#ILu$Kn%%-;R<Cbn5'
    '=b;&wqFu7K%Tk)A>()JvmseeerOl?YYV*bKE3$sbin1-oYU)#0P3<yFgAeGcXZ-Z~aB<BkuNu*58Tzs6T0d{-%O>l)d@R$Lic0Wm'
    ')3RK(W}M`^>Fd++Te^Fmj*pjrbyrte=E)9DQ!{mGO8romLz_8NVpl!Q{oLi(J?nJ`55u?gEO4j0r!+hs9==@M#@toaGBv4gDp51#'
    'RVwqosH$Nao2<#}s%rAeRdxL~9>3j9$A{%`d41n-YPzy+nl2yKYq2SdtR9=8tLM4MY);In%B$CpdwIV5{kLVjxV}JLWmPrTb?cI-'
    'Gf$!(dg0U!=|q;ELgs!Ru3p~>bX8tlJ55X34RtY#W=koww^KgmWj46ArlH8YxvZLO$8V2_@~`2K&kyM(BHi87@%1I$&4=O3!}0m$'
    'FkOx|Wj~FBfS%V=ohq+ibWek;Gpn205uC?jkh1hwZ{u}-ytr`DwN0M#Vot3Oe(vMx+leb=nF}AnGCGN=ZFetxI(X;R*TgK2;7j`b'
    '<#GV3ee7)-in1;{sY-0B?o&I~v#+sFQ=W+r&33rGALNBE$8U$}ld$*O;n|Jq1N=O^&WD$~^Nkm`?8Ps#uG3J>#W1E+E~4Q)SAAbq'
    'UBtw^spDmMGVRT~S-;BoIPQm6x#Z<2)i&ic7jx5B-bXVJqqy03MZYX_TV_k1r%bYy-M*Pu>Ez`|IZs30O+_Q~sQvb#o{HAh;4_i#'
    ')!kALb5#~8zj+V8rl*H=f49D+i#zFy(F2*=W}4fvY!^AuGR{R)=kl?oN%Au1w^(l8$+zJ_x;@{?@g3!-KkmLBo+DSexT`EKu4bva'
    'F-wy$(x%#F<`$JJ<fR>EZRIK5zN_QtU;1q$m^D*WE>k^<mep9at<yV{*<4OtnVcYTtcm~h_FX)lE05uR{i>ga>E&`@>y#cvTS-cb'
    'MT**IbzQd8+zn0PSQk~+&ob7rzj;e?s^$Lh<?GAtSlhJaBBRQNsvcb}$#<T2dE1FU@qp$sQ?o7Y_<=2LrCT0At<=ogzRb#|=<*`6'
    'E?JgG(tCSZS9V=l%r|dA+A#}uhu?hIci$h;<t)HiQA_lT`pq*ayS5Ye$42m7Mpg2XPvTE@`(t^2@m*a$EWM-A#?qsDYMNX^OYhuH'
    '9#pHGY}>l*>koWIFT>N9wEGrVB)r)$&9aZBaYm94JFnW>A!*|YHS&W#OSiwJQ?~kc6^zH%hk4itG>%E{;7HHCmJD_=G)kkUZl<cp'
    '$EM1LT%Ay*ziCf9uBS3B>RqrxUsh%6=X%P<MLC!|$=&Q2N5q+y?1MX6@2I<7VQ{MD??vvybTM{C8iqNIos+G~8OpK*4J^{E55Bkb'
    '@Y~_(`0&lYczSi0%eo?Po*vFrj^kKQjVodtnpCw-8oIIY%-ra6`LR9izD2vCY6s9r-Zo?EU^H{3x|M(_FGsm=<Ab-O>hIgm-9Zxg'
    '<#c;&WP;<^IZ$(3OqoDDdRb!+x$0aNr8{j*3qY&+*w${k<;NDFB_Vdkm%dH1kSXfKt}pUQE>bO3In4d^H*IY?ep_*ptq0aDLn?cT'
    'eAVXyWxUT$(ky)2Z8PWN;-2lw`S01)bNVekY*f`s)_$tv1u7y1fXwsivfTAil&OP;mIC?kvHk3d1k%H*F9Twj)6!3UGq`bwtnu+r'
    '0NK3pLUU#A2e<M=R`l(#=ZyC-<{<!vGL>qscAg+=eLfB#1G|H?rF<T$<zxH0J~i^*200@f1bP}U*OI{@@}{U9@uutwJFK#0{OG>q'
    'M|aaxg6+N>hWqCYbU?{fRfUVT>qlwZvUpgL6Xc_0H!mj`pvv{bd)ku{lrDb<$NxZ!h8)hS@Tx%ikejk=6sY;o&PDOD&D@Z^$sxxj'
    'Z}O(`g(;hddXfFN^-|?&$Xz*wdoVAik8SMv`1%CYnvP!++<Lm4%~@~G6h(t46DV7n0~#-@K1u+f`Rt)hAf^v)DYDAD9VIM;NxlZ`'
    'E81FRwv6tX0_rlCMV;WD!c&)ZdG&W}XBiInuNy#bS9MbwQaxl<Jxm%Vt=x8yvrL7@G?iu7YoO#GJl8MZ9+$&?`d+PF{`^~)epBk7'
    'G~gf+vjNL^ETeok3rJRHr>L6`p6-{Y*XI{E$*<{;r!8pIH!r{ReOF`3o$1~?(r%IGj=4jn`BKeY`bb4^#bzSQ&a{+ZqD8OmlLj3R'
    '9j|K4d|}gAm30q`*mwP(LF)5=a{0EHOK6~D0Ud2?_l1H!lgZZkSW9GKv~@Ri-M$R_%j+8M($lxY^Yhw6yqJuQeXk!8jgF;D;|$Z#'
    'ELA3s)zDU{o3ddRbN2n@ug7@%$KzJOj|*Bo(G7iDO_jE6A+)K_J2&{8<uf?WXR>e2Q`&Mlbn0LgKD<)<V~#8e@SSo17uaNR=gfI&'
    '5A(kK>A~gyTe=(OZ->h_iOz=PL;TCfqG@zLpc3;kX=IlEUkTu<6bw5Hg7d0-z{D(bi7U&ZKx(HnH46L67Y_vq_-InD2?P7i(vM%#'
    '?i^z(^HhwAeDz^etvW#3s9Kkrnq8R{^VkF7ch-wP_IvhxO6{z+sLFXRq5O4QMS-7s*>mYrcC6LXYO}e$V)0X9Ivt<V-7l`khjh7y'
    'h|nsS>2p-t$8FQJQ06|1%DvZ&YSgL2wCu#_e%!&g<8Ns#MqNQ0SD{{c-D<05qn>!cxY8O)XWWf&v0l~QYCQDA{ykh5Ri?=k&q|+l'
    'ru9{7bm=EA2nmBPExCXas=(Bb``6zYTJm{OJ9b0V+HjP%^Th??<`eIHh?oLp<lW`|g-`Ki$1_(0dGDIJh3l)xeTAJ|dMq_p3pXx+'
    '7<8ildF|4Fmav!a5RL3i+A~O90}E*jnSJNM1N1YmJBO1<$d=oeKX?14$Jfix!FQKWUExo?b+nKmX4H8DC3es0Cv>ewOMk;g_N`wo'
    'wI*jS>(lI%e92N5-$PmWgKmH>G{rb)*B=21`^x3;DGX1Sv7m8ulNQlsb*oH5UR~SMl#1FROoC%4)0pS+<}K`d60PTNy-d@4KsK2D'
    '72CkWAJoUm%`UmB<rz0@<BylG$A^7@W*mM+0#L{IpngITN_DG=QUO-<m{iA}S9Qa~cuHSjItrEf?q5&C<KtGAHI13_cX23$g22FB'
    'j$=LO39HCct~L-Eh8qqBVCixbwrSL9jm4yMa}}*c(BPumR*VrMgP~SylT7=U-k%Wk?a&WpkV_WLh%_UNDQab2l7qP(bs2*Kvs`f>'
    '-INvRFVvdejpy$tk63ZKozoCd;9w`XbJNt6JF216FaLCSczk{N?5*FQSyi88_@DljB;H^(7171r=+#A)>aDNmZ<5(76+vqOh=98n'
    'kEN)0WJ!P7jnzM;Ifzd`ZY)ZVyWu4s-8OJEs1l`VYLEg4X>ckgU$3&Ht<)a+#3@eg4si6njct*37GFT*PaaDVSc5Bc#z#|qv||wP'
    'ki+!zc2H*4%leJnczH>wnzI?%sb;T;5FPMQE!L)P1XtGso=7_^JC}Te#v)eUc@M+Wx8u{@tAB4JYpDw#f;&>j1s*mvQ<Q(8R*bwn'
    'U(m#I#i%g8cOR$9^V69t@%i~_`v00dvc0kY*XShgZ{@@(i2`fQG&k@}>225H4SGemr<IgzXy6%ua^J6KGobvo-3PYw1|Y24x}5b^'
    'V_TpSPLr4_r22l<92Ne=A|195$>)M_bmL}L66fi3Ba;r#yN}P@_+F)fsQ^V4$!$DgnRshz?_sX}ku0&<LBHDE*Z6w4pHKMDUcgmk'
    '>kxs8p~nEyqsnGMpl#bgKwxCrEoJaC^N(-tjM@G0*fw}5KD&5cLc)Zv38~AX8?4EIk<%2xc*s*<eSBjFZJ?*OmwG0hUq%-6sS515'
    'PPaVA%bD}&c9a^%1wI{qA;Njy^?$?89^6^?njXWGR^R1QmPF_g7OiV7)q|ajp4$8%r4cno&8uyUG+lpuSEr;$jQF8Ld-+lw2PCf+'
    'xai$w0@dt;oO?&jiNm&q3PAn4@#9;&CU(v83}@fL$DbF!i%!!Y!6`zi26A*g)N8}v@L8VI^~1Ndl6@T?zYfnE>}aIPMwqv~NgW$#'
    'f(&T@7$X2Eaa}mt57YQJoUzkYxC_2+^*Kce*v?b{5Zi8rOqVoHSyN0wQY$>TEPZ@a&xbE7JK{hJqVnDGQPzM(m!YB$pj`oRyJhS;'
    'AA{D_B+>Q2;H&9>!`{|RXGhz;OEd-1UPFHEojujCiYUQCYb7E!QktR9f5S)cCIq;=okjl`3lt<PwE+!vV4<dH)CGN=2OzCq>PEP6'
    'J8ygVeBD*4-)~X9zj7V}uIk)OILe3;s9Ph{0&1JLH^0U2yIL>G4c1LSSIF7!!$F*?e2NlpI2K%YEXoinAU1#a`J6-iWk{zi3dNEu'
    '$Aydv0b#{w5#vD!qB>f65ACe#kM3p1XI5a;1gQ@tqlGf!?dr6T@?q)*=;k!YM)kAX4{zmMKm7G$+lT;JluJvib25w|_Oi^{8R>uV'
    'Z<StHbW{M~AKls&TLKCKd_+Zjtx7^Q25D9Pmlt$QbDqXF;PLE2H8~%iLO^uhSt`<7D`Ev?hv{V-3tn_{mTb}uRoZq_ANf?DK_HqE'
    'CJrZ8)(mZV%^tRjSXG)Lr0D8ad7vPm$SZ@(tgSSYVkjuvoEC8R@7~#H((lcv8LCAu9$ly;Iw4!Dku9Wb2-LYQMBe}GaJv46hh+=3'
    'NQDMJ64ww#vEDy4(GMe9qE3_Jpi?zo^v@Wa^Knv(%QA=i&v&T$KS;Fh;y>Hy*ICv9E-`)MK1(C~s-`G$x~iregDGCNL%O_dP!2C+'
    'GX1=uo$Cv9Ng_m5i9xI49z(n0%#;G2URHT|nNz~E{{2R;w=c&!V3u*I+onJnq=jk~ZKW<%ME^uI^E2sWz+dShQ1Q>h)60Q!N}{|n'
    'U0yag<g)V_^9~y9Dj~<o@=33#j<h&vmBpf6q+ND#$@Qd2%>DBwoh^@AKtmtlcfyg%@LA^!<klpGdpFhejbgyh?%4lW@I(x`d`^Zy'
    '_UbajQUmz5+KdeXloMa}s)71c7f&0%?|D3ayZg<pJ#VKpV9Z`kUHi0wBQSo{FIdeoAX;M?$_(dm?tj+2K4mL&`t1;JQGNIL607e?'
    '^s*2qppgV%>4Q(PSVz^R%y&tS`0v@Q={amIIuDO8p`BSH%zv!t>HYa!J+;hh#Et5pxZ|M9q<;-d5JuZJpF7AYcKf~+pTDcB9~A}P'
    '|M+rXE25)1Wu2p|r$MxXyaGbc?V!Z~&NNoaaT;#i!Q<oM_1oQ^jZDGT)=f(7+Quytx$!KPM{*Xi9xWJ!VW_X%$gYQgFVkqRjpA(;'
    'M9~%)P#{OhKZc?iC!%Ec+0P`%m)D+-_wJYDDTP1N9=FeaSp{-GQnU4=PumSsXkLKVgULsbqQ~6H^5<)JvjWC<Uy_FVR?8953&q&C'
    'pqnqORgsTjG*n$`mcD8s$uKxo+3qc@=U~^nKq;8f%@zSIsAe_!JLOUn<N{EG(te1}XR-TT{Qu(}=v;i;SQ5#$lU86P(!5uG=NtjB'
    '6>7E9RmClKf!1recgZ<D|Eha+cbs1D55Mnv_F&amTHgwE(nxvGc$DHgCw+xpj?09=Bs;lr3tt{z@4n(k-lyjcSW{1NRy;C#&@R#J'
    '&#O{m0@5j?w^rcTc^fJF8}@+|?RrOb-{2W((TEC&V>qPEvP9c&j*=<32o*Uwbxm33f6s<ifN4iFI>7KcbQ>l8{xs|SQcLiMAOy!G'
    '4Xt_buFB@dUAefQFe9E1zxv0wf4Z1>se({b`brMeOHF`Gt&S{3=G^Ia%^{1{LMU$B&k2DT{<s&=qDD%G_paE#LaG_!uk0vWn!1ke'
    'e2qeq*mzWtzqeZUdC5}a#!X$lpS&0aj)``p=z6sT77dkzXEv+Bh15y%UH;Tn<mdbOcAS3Q^>Ghf^l%i_d^LDJ(AQ|G<RRn_P1F*s'
    '1)2Xc?Opg>EslqWd5e9iQVnI8U^eA+>CPw;D8ka*1a_7Su0*I)v-^8~JWR*x^K$t8B~bqr{Jb33LbD^GlSk-1Mp+zm0qJC*9*|=-'
    'h^(XSu3P_4%GB;_MVUSX-Bj}kYb^TI>g9^rNrg+KH`)ff4^Vd9MxMfI<!S#W$e5HuVWXp<1<?&7a5c<sNMeX&@{Rx%@UnLk{#%2n'
    'am5{9MM^b?3K<C2k0?YgRq3bmNmj8WT!Lv(lHRz3Q@*qNd4!@vl^ZY@5wId&9~^N+PRyN!7_O|4TDofYUH{wBKi;jDMp3P9L?>xg'
    'rh8Y40Ao<tvPk(YDlDOsQs4xuaC_}>=YqYD-=Ra-YH0fqNMLK=P*y^fL^r`gT^JNMTMH7*{P921F6ot?JCq?lc-NH|z4W1RDqs$c'
    '8(yZDL$CE8ww7F_Xm54-hEBK-1x2q%oG1PMDoYqsJORSYsnfvqmkC2@E8y(YN$WhpopOLXZbcCtYt=UqkgR2bzt<=2_Eha%Z2hIj'
    'b2~Wx_U`m=$PDgxv|R%<b#!MHI~$A^@g)p^l<OWoZc-LDOYJykw`}L|5RG4)i}983*3;eN>-ffnxx6PK-{lL$g-(F)CScF3bJuk('
    ')eU_m7;nVQ|InU7-9|5!?p;e;%r&MZp+#uG3!po&)P&B>Cy4qUOjFjuUK@U9iFCz&erVrF50><D_;&f4atC6t(~l^7se|LTA_4Su'
    '==l18LSrWXorha?b?@ou_NJ}S>@8%`q-VR;sd;7(D#sF1glNTu;0|B`56N%Y!?(2^s3ozrhXRfTeSz=*n52*JJQubzQ}?kSu^8=l'
    'oNw7f*!$SS)4bzZBsWtTiYKmTP71gkI|k>3B?2kK+>kQ>B&PP3eQ1qFHU9Xj2fyoZsJVNUFr|S{8^sW_QOeKR!;Z9zx+QL{roZWM'
    'tYFRE>E1eh*_Yo>=5B7(gR)obtua6{P%h3AN&p7n6sIQL_VvK#k52%A^KSn6?S6w)Cz&BHK|pk$Fa%QXRQ$hGX-G>#zS~sMKK~6{'
    'i9frH8L(JsTK(#@a?1D-c`RZKVl3u(oBF`HyScf2FTu)u9vqep^d?YD=yx8P6rvE=mNx~ymCwj%I=&|8B`Mvqk>}ytBTd?K@PkjS'
    '{Vn3Ye}E^3X`$merLmChFDf1_w6R7C#He;?(oM1dC6wv&jtZcPngeXq>WR0GhW?5^!~jUZ)UBW#5PBHkc*`bE$78xzh+W<T{#eLF'
    'X4sKqLI4*6{uc5J^3f~@uH)Uc`#+oM>+td>qZwW{zm?z#L$ZUTth+4LhN}R&-7LtczTYqjWOuVaoP9TWJX=SBaKCOK1PBQLuB6}7'
    ';#)=AK)Vuqfuw~^lgAN|O1D3Vok*~!+vPZhT2eDLh-$;*Mv{d3iMB2M)N-$<PN#<Fh14h-sA8&`yrh8Ny^)CF(;w4)I_GWE<O_-X'
    '?d9w025_IY>$1=xqa-w$(B-nzPXvM@3&ib%#Gw}m8OVpfX-_+hy^u!u=n>(Ev!O6c`aglas`%4h1r6}QFzo)84b2CxdoLS|_kx6d'
    '(o56m9mD3U38K}s2p`x(juzI{5@p=qvZJT;&)2P(kIWoLM}*_&#pE%PN{&E2s4CjG9my?WOx1pLL-)rohlgEQOQTKZ3QTc9v$}M$'
    'q1Bb_KiIPDDcz7&a9%#TBk0F-Xfz(CwCgZIHv++3`-r-w-dLYE3Kc!Xah61cfZ46|;U}fx_+2%<wI}b#+fkEfIkf_zE|ZQ=5HGXH'
    '@bG&VDMgw;x~J##;->ln+kF@wpT8bAc15&X;R-@_^*ftzREf7Z%QdTDSj<5XN74S<cJ=yre;h7D%}b#03V2qc*t~o|lp=^Z3*xg*'
    'bRhKzO;uBTbWbnGU(>^xHhVeQg5d@$c2chlwQQX5P&7ivA%E&ig7+e}H{QIVd438s{wbySHy$=Qg03xPBlQc)3p5Y!v<o{sW+6C@'
    'T~)YZ(N=EVj{hJU6?b1>ULJP^CLvMZv{-o+ycz_93hNUg!To|`$%U%n-I_Na-O%&&ba>oz_3LVlP53%fI;bycR3(2vSYDyZZ|)$W'
    'B2{vJU_;w9Q$3PA90*jDb0ITU$*Qi|BamqEjdZyXQPtzkAN+j$Hi*;f_3@|I_vLt<JEsF>3>I$WL@P#4Sc!Xs{wiT&GZDs4AKcRY'
    'A*8lD&^l#GS0$?EQTU^ffnv>&VMc0QAyw=`%_AaJf5(1QHR-Tr1QZT-a}CRLLC8c%+pw?VLt`R?U{*v!FpR=KxS^0U@t4~bp^5u2'
    'B@lcv-!#ltxdq<D_d%2o_q1774XY?`-O`D1^!*$AL2-8Z)z#rr#@C!v**r+2X+qoR+beQ-Z;WJKs?+T6+E)A(m2rn9tCYlR3nwcc'
    'PMFD9i&F~;<O|k$yO2pr?y~!v_O)!=+k{hef;ftfp(UztmBZ{_=8cFWRzf3NTAB}TC~nmqR@RJJA{;GPuh38jy3>y6qZg-4MbAM>'
    'iuO?c!QGr#j!!<i7YxWvWd)Wi!l6{7qGY8LAic_i*R5LQFc;QI94;_TKe(&&{qg#+^I_@O!e!;R?)E_mTT?f6cp`!GfZ#Fo!3k_i'
    'Z{60H<I6EP<r41m-ZrvrMD`H8rh@vq3YH^6B?85$0MJ@&5#=yOZ;sx9ECe4nV9U$j*vNZB#xFE$v<9_OW7Xy6Q&ThnleITBzL#4!'
    'a(|pxJFAm<)Mdn{3MX<}Jrt6D)d09O(CXAg+TO5T_BRo^Kd_f5hR!eP9KLs5C18g<Fm1&vs-`&}Wgv2eMub-t{$#BpNp<qEjjbZ;'
    'dHvF+<7O)&5;W-{!UR9t9tC&`VmZbgQK2F(TA?dAbnBkZu*jc}X?shCV5nfthX_d=l!W2J64YINSw~rnj6<E@UVvDY-QM~A?F2_E'
    'DQuXI1Z<}{!P%Zua~o7!@_WoQRNo+*-<*~_9HVg*XdeB$C$`1-&E02s|5I=k(<)R5PC*L8!U<fHhn$HQ&dv45am^u5<q*#7>qb<h'
    'sA0r_NScQ+nJA4v9tcD<9#c$dn1GMz<{K8Y7{^-8FJ$jSYCu*)SS5%4TO{C)qv;=iK(RORfT|p_HZ337(b*c}?&WK^?p@vvGvF-x'
    '6qc1NhD%y+eO*6H)986&$51rhoEn`=GIfyXh;X<~ItXp9Zyoy{X4Ol$DHt3ba_>U-ppZ?rni@CXW9v;i@4Gt+H@mg~vo?<T@>jVc'
    'kXlP#H=DJV&KI*2vX|TUvflBe9eclaqQpv$@7<^hs|ohOf1Kz;Wlig;gCYMg@1yzPj(+>L!{8&lL!d4OKN-*ir|#s?nA*+ARyxM5'
    '%o6Kix;YQ}t&7C<w?Naj(tE?7fM|U{)@6*nuyhypknXIguK7zVlltKUJ4wF>Up^YvyKP4;-nV@iJdAilGjd5(hlcLBS^cYo3KO%t'
    'k8J9&KAp7pG4(n5_7twjh&8A!;em&7#Uic>gBTb{7_yZ8$98nwQI8q-6Iod>cTFNO^9Zj8U`9m{Mn(AM5fR(lA<x*!OJEGgrwz(s'
    '70G%Tt`05oHt$TbNAWo&d211s;Sv(S5A5Si2AsC^hG=$}#eB+O_$-51_)eNX?BmKgOi_IDl(b{|$X34JQzGC-o-?VK8B;<ypuA)('
    'O~y2bZ>2!!l&I?6=05SiV>8>`K>%2&h3M6N)oma!+LctR;2$6ZeP7}UlEx2gCgg=1+9{zd<S*f_$JVbd!)$MgNpMnS>=+5yz=L3%'
    'KC+9KaO=Da64xdcr5uiysAjcvN<wNsy2ipC#4d=EATt%uM`G{y93tU_(D-kdJ@MCIwP&mrF1mSq{7KYVu1&?COh<tBN6XD=)}OiO'
    '-P+jP5b|@urbh(5BbUKWy{MS`q-~+(bdrHS;ZA?cCF#M0W&)OS;@ED8-?ZMi4^}Z0aSSguOk?<yE7G@&rvq`8VeQYY9`9N4ycry<'
    'f4|w=mPrm_PBF`yK$lvBb$FwVDym*$mqkO2h4FsM13u|V0{hqg#2bjR+n@!<TO$ec4w_Q6SeM{TEGBd~7A-Wog+@bt1zhpYzSa_9'
    '_pZp`r+8Vcfw@PL66@@;@?Z^Hgpr+wbMFDR)y=y)H&6ENM=A`W9LW}R2I4!{e8Wt@(I>2QNoi&n^p)o~@8?Gr<=#z6`eNK@R8J_%'
    'x(4Af7}E6k=yk)O_Uvq~NVk5vsrb+K?`ds);{cF%qmN5W0f#WJEJ7oRx=5V`wLH6ZPt()z{FN=_!|`R<)_;SQaA*3^P_XQPpCXZm'
    '{i~^^Oo+_n2|Lo_3Vz(b?dFVG>>m!~jm4nS7>vqoxCz_qx*!tgy~4{JqFE`nZjJ$eg`IY8Dr|*j><NN8y#JV##u7g>O9`!;m8eXa'
    'Bzc(Uk8LWd;oWw9d{)ZkWEv<r4r6d*`dIp8isUwM@X!sF&8<87j->3~5M$S3oCr_r6!&V3amoxxlM9j{ViNk#Wyv?cw|F?ivu^hl'
    '@lm~7$PU%Qb@&+=S1SF|FO{d(4EojT?v?)59i7Wh`PA!|7#6Sr#Y35J+0DKR_YxK~$jM8L;w_``)u^^etOzBW4{ztx&N=SC-t^wW'
    'b<<&jJ1ud|#jxTk2=Fl@2WFRWQO5Maovpory?csTgLNpp^yUa1WMo<^C=065DgberWY_+5T+dZ|dj9(Q5((q}`vi0<Amw4#irQ6j'
    'S<>ur^CAvWK`Az9J`}IJ_jTULdbFS4BIfkE8cDz4ElA-Gmy;8>R|2!BgA6jWHrG&e6T(}4XW&b<gm+xue`H6;@fS&xDplCTEq<6c'
    'j4;AbiO!WCjX6K=TlkF$<?ygMG_b_S?v`s3rl0KTFMqU|TAC>8O?6>n&&h~E2Bd}4622s(n$_*sQ$%6izoW$VJAH~)yj=3%^UKR<'
    'lnMxiG6O1vjz>PSL`Z;)b-?d2u0PftKeb$WZ!_n9_xZ`3|LI)MU*1aS=N5OFc~qv(1%=cI(26OG1Ox*|{~5LR3cB+<TiHzgT@Vl!'
    '%<9njsFRKO)<i|j4;FY4K5H2J)&B45Wf(z}XM*wi_d)J`-e9)I_y}H$o<<YScxZSKu_Xur48m}Lw3TC;(nof&^&~_Ta|pt1&e0^U'
    'OEE63h(RR`BALCSCi2P2_NUROqxo=%515_~`gTA3v68MgG-kmgjse^Z<zjYwp<-^}PRI#LXux}|cE5rQb=n6h-|%#{x;v>zw(4VY'
    'F9ghpA^?pg9ARME2vC~)_;cvqnJH4sb=zRgefKm(7I^n1{<_si57S$UnmJNsW=(_=h-*t0c&(uU`ZLB<%YM4+cj3Q(-mqc|Z;>|U'
    '0^sZdE-*vJfGPU8YVc>tesvm#rnzqM(<_K$u<JcwRlpgU&>=0dHsMXG9fbvs$H+lFw7G^5R#)ib&N8de&zx(zZ7mN{ETJ(oZ0y(3'
    'v`kEIZShIsqR#cF*zX90^?2PT&amg(LD+DhQ)s6^e#7Y5=#V97c?xd6GC{WjO5+aX-IeE2--*-HK51Yc(@|!vIFvh{S?X8>>N1+V'
    'yl1?lmKxo_uyoxH5K4x1;^cmQ0I@MLpwR4#3`0e|cXvCHiZ~eqCK&tw)O7CRHdaZ>wiIN{Lw~@<f>5W4YXSjTO)YrCKuRM%cwf#-'
    'edTL7hv*+3!7d9mUKUwsL%W!)8{yH2wpCaL^FY}Qel#x9c;y?>(;9`!_(C_9rvXRhXZ;lw7LX3mVdj?(?G%(6w<*&LZe7<c|9X(='
    'y}WE3Mp`z%j%R$_mtZjcqMRO-a|H@Zkb0*8?8^D-wV(fW*y>Klgxny3Dhomx%N`;ayD^nXrN?Xp^qq$mdiUDlPJf~`eGBW7m|Kv>'
    'J)Tn)lcfUlHPCel41l}Rof(4j2pD3yoyQD?y7=HuHnl+}sWAcQ3Jl!vAm^kT6Jb$?jE!2ow<yV$YP^0MvHF?owUb(5$WKopMco(^'
    'o<TO8@7xz*ln@qRW#G$@rz>7gNP<2EkNc0mq!N7clIXQU%$s~Tet*7?E;beaUq&;>Br#N7fz(%n=R~R7RJZTym*Zj8RjeA1yXAiP'
    'vSG^{t!FLrU=Piq6bQGZxae~#VYye>!5D&7+`gleE)?5CnfqmHN)AiCB?c>V`4h4rOFYGvP{0J~TURY+G8p^b-@YBJ#Ulmr`R$p#'
    'usoqQY(P0Wdf}2+mZ3A@Bc{9OvNMORi*XsDVy$_TY!yr?0QPlM)1ZCz`^K0k-W6p8(2_i;<+0+8Aagh~=sD1&EM}}0Td-*QU7fi0'
    ';&)jPhB7;F#<k<j@{q^00GqYLnr&NFfQ5dPyI1vDY-AI@!g-wXn1D2gg0Tz>{5*J3?owZ=l9_M+R;hk&G5woS7q`w|w+wBTpvFcj'
    '!TAtMfQni0m6#3DBrL$rFvA+{Dc`yN32ojm2#o2f8e2fP9xxK__UaklP;+!DJa!VRlr1|~JSzm=)U<ngZKff}2wYNhCd>k9&B`XS'
    'N4m4<+DygTZ`#bI-*#|(BHMuaZB89)W3YgNI_4$E>`m%P-1mAFDsT}pj>-t!&5Z5)vi~}zi$`hFmR&gyIvq`;Crk>^dF4bm2HQTE'
    '13HUI!e-<x=IhR-IWqW?{(SVo)I45(>6{O`AVS5s?<u4ZWtiYmioiNCO`ubX>iN12tU{iRVOOY5xDk9>h8PGEKx!4Pb8~nU=GXy-'
    'q8HiTN4`#6-XNmVF)GJmuoW0kkm9=;L&x+{Y@sF!G4*v*)NnWkVj6+^_s8k(<@I69TP;*K?ks36VmTRCiXoje(ze64JVs1W2Thx@'
    '*I0K&*5c`IkCT((*Q-P#lo3meq>zt7tEP~uqYE*=jp;?%o>l*Nn1~K$p=+l-P4MXu04MAy6<HS(wXLUh6(6&*sAaodNRD?be)dy6'
    '*%RDtn~%GJ+z9$SLrknL0vSW`^$F?V<qI01R!j&r_ACw5UH-W4ms_O{^fWW^$mIc^S|oXV&&}<k{#;*wQ*GLd{E{AiWpDl&s|F6^'
    '+Su^PGc&^oi<kq2ew1Pm?Gzb49|8oI*$hn|@}{KeZPC-5@E9361}AMfeAy`b>zJwo4n!@7`4D-?0i++1YDefKXJEN8?OgrMzWi;*'
    'v{dLz+IZ@`_g7a(YS;A<(*;Ar_-5DP?g*t5KdA-#om*ImoQI3Xwg6ea_6YV!$3qahL^A3ORR#WCa`Lh$PB!I-Z!4Z#ox5H(XGV=4'
    'BDEL|4de5?Q@|RiF>Hre?y)xgsr&Q$D_{A>bJ_<PCxDBvU|GkaV)eQyhB`8pX2A>O+|pgMg&ohFvVyCDgPhhJ)0IKzqyPx^DvPSh'
    '4DTuY{x+8VW}Mit+dNIB=+(LwEB*xjhLd4IPbDML=?be(J=8_hbZgP${2I0*ua7@f{{Hwgdoe?bC(~jbr*~!s@Dg0CNCpw6aV%rj'
    '^k&6;TJd?ch<@HxmonDWj4A>z(`YajA;;rsy=Pn+<RT-bqbJ*rdl!BTC9e?;8%k$QgJ25u(bs6gbqGmPCg32)L=EC1LZ2buWLbP)'
    'cI||33cmT*K<)Jmke5VD3bjD%BqJ)Ab_i&K{5x%O!oRP&l3jNB#juCN(Qi{|m?&bFHk_ETR}m!HJ7^=YVdWiG?_4>`io-Uyx(R;-'
    'f7Ig?qO24$y-0_c{Dv>4Pnhd(p7(nfU3oNbVjJqVkOOT#bJ>?#O=iae4Cm4u4(vIKZE8+Mb<4Fu4ViBe>E1SRrq8Gyw-mNj0Do>t'
    '*ed}Gv8K+s_I(q*e1neT=PM@b>(*WISjF<=hPt=YlELv}yVynS4r?F>j9F|OVyJM5k)X{x*M3tKO35xS>moFAC?=QcS^D+CI|;1{'
    'iKB6RbQw8e*xc=0cDes!!!gU;Lzp&<T|kEJ$#EK%%G&>u-jNEGI2Ts1bGgI3S}+a2UJR5AKwTR@hGu7hN9eJ1QKEK$T~B)myICpV'
    '-s5y?xICm+<>KXx9-a;j17m9cs+jrxg<mrDwlUebGfE06c0cT0_?Opjm(NfgwuUkLno2znEdswug5D<b+Av_`MHcg0nw{&NhLGJo'
    'e}h0=e89RmLr6bE?^rT)YRm)fL);`K&OvbzH>3c|-gV#Tx7)8aN3shbfRUwO=@3!Iz*<x=B4p6kS+$#SF<rg#&Pe5x)j7dBNPcuB'
    '#R#L)Qv2ITBTQRzZmPy*(+~Um`p4t18-2{RS?hvlMc;@1W+a;CtHGugGb}j2Mtf9yqeRSG-%v#PXu=_xAlt=9tj1^04FC=oDWtHf'
    'bG++n?|QHIFNbwb>E*J}=%w(W4O(6Zc)@CYwD4p8CNQ3Hvvy6f`#il3{#*vj?^AvPw1uV=zR&?F$0#UF0<%=O?D6J;L8zL+K09~t'
    'gG2JJ<&86v-tgi<_~oV=ezbw$0rT8`DNq<aF_Rc}E`Rn#=B$4I@^u3Z2(brGT8@fzGP;tilGLZ-vpyWx{Th*-RAuMF&l7lQ15|?9'
    'yK848%qhH3d0tilJ17q@uvDlKHrw)=1wG@<4;SwsI$YR`4E23GT5X0m4dLxCY?0K#*<6SH?sbDn1<Tt3P=gIat*aacMYn-KgwwDH'
    '#-V}?iW=L}W3x9(e|InX!HDYePp5{Mnl@&6_>`SwLVf5s=+qf^)H!2>6YSnQ_=MR4$^XD}{B<LP7YzB81vd-y5c8_!l;)K$f{g71'
    'Z<7DR-dy_Jk6H7pv>|(~!cb7|(S+llhLzeo>|9rZCJ~`1s$fieOO{iU`|@w~Oxc4jT!&0VQga4QZ49Rrz{8Dv0{~Pv^HnR};mlmT'
    '4<WF86*-v4bY3GXTo#tclr5t2XQtO^+>w`Ex9Tb5IXoYC=y?qZqW<<1i;zyW!RU#;K(B&wnM7vdY97knzngX0Y5mKY5BEDIAeS=I'
    'Pao9!RjmRJ`aX?YN8I$xX>S;LeO#f$*T*2VY;*(=vprV!#Nosz$*FzWY6bm|=#fBDmxwKUZ;F$L=Dw1_S8A?TiAJ_&moqXnqm4P}'
    'Ea6sE8hppevfo>-oD3twNc3sg;jV2uQm}}f<CrC|62;xkP0S_<5k|h!GUu(#fGY6e_ovev{(R@Jtj+H>NHcwK_q3bo6`K~?z|576'
    'R~sW)qFhqLP!HzUEc`a9>O6Af@=>e9s+%vJn+pHj&xHhp*FhD7EUFj}E{+$)RqLOf`uADahe?(vAL2VqG9Av=jGmyr<}qDVUN+HZ'
    '=bLVQf7!tqk+=^p^C#9X(1Hz*PQEuCahZk)>pMJYM5;Ivd5rGC6o$Bs%_cYDFMHUvu*a;uKL*%FTchWMs^!Cu7ONf+$Dpt|E~o11'
    'h2!7epoTEkfM?2Buo#udOh`ex+Eb(vEP#SwXfDpy9deo<v+JmZb&hGj3!v1e<irsYk)f)0QXih%4fb<T*Ed#tJUkMjY$ak!r@&ms'
    'm>OBdfP%IBHylG=GNLL*8+qI2=x1Xqf4rcAH$s)5X<7|s8SIQXOdfU2Rl_oD048X9vk4F=@RgGZLBYYx#&m)fVqt_C&=j9+%#{ez'
    'GV0g3`O%!b8`f`SB?g@OO&hu%s3a?HwW6%kuQ!g~><2Ln_fd!j(u<V&rr+?h7WKE``#{D|Z$JCH?ceU9iL~8ASR}+~uPVmcLP0pm'
    '6edE(2!eVhXBoHIuzNPNXQ(0tGly0JI@LTiQ5!=W)P2%ocrt&I7*BvNQ+#MU`wq!ySd^K}#ArAq(cFi)(eC9TODSzC?wE2@XMK4m'
    '>-fjV;jl4}FrQ5t)98;vw1`NcHo)OdW_Fs76I3+ZuT9^W^H$*NQTy)k%{6$?+ygGqJZcSjbeRw|Wq~k^p{+t&7KiF#+PCmaRKCRa'
    'hEl{+*ep%7eaG+#9zyi5CEbPSpG41O7DuxWX~W#^UVD|`p04)v^t6tm&@9}tFlB>{Ff=06uvZCkN2sQmtEqxLaKN*qiyHQdO<YM~'
    '>VeGc2V&l&;w;c^)?8UsE_FcA_-;%)x92VVxPxC_BeUA`^NVC?Y849BaK6HP!0&VJ1Nomr4;dYE(*&+r{EE}33ET&(Xyt%L36q5k'
    '+9w!Zd$3a7!T@l)D^|bm2$G=+LJ9|BBBqfge?};jhoYc~an}=2(Ws!UTOJR6x%**Y{Qkj2Soz@EGKAo0W!`v9=+Se^Xw>@<av%zT'
    '0jFy>a85CI%|Zo6n0q{h_H9B5k?5ON)<tH3`_t<~soaar!C3EYVgEcTA3z&6HHv5r5D5ZK8+2FpHO3T$Y8^w8U%QR{vsjl<-HSK='
    'H??Az4ncT9WYk@AbZ5Bz)X}54Z3k~Goy+BpnOkTP7<ZCR(kY{811Cdoqmp1}Q$`1P*hFjoV+;GbpA-VDPKq&MaT<T>0tEbmpe+o6'
    ')|w20a=s}g|M%7ZN^x8bP&QI;s7W~Vm^2CqMikK^llw;lDReyWJ9lC=eP|myn3lLuc|WPP<-(fn-agtAu{LkOJcekPPz<i^@(=A}'
    '_h?q*Ra9SnU{@><I6M_$klsfMt%=7bOkKQ`-PN0k39WbgMt;TRz^Bd3WZJC`G%jk3m8>?kZY$MMcyhV3uigV<&qMmMExv@;dj6qi'
    'E5dlj@DkJ1<nhR`3?gXN%MLKKNrL$42A;#qZtK3#g^v`8>QW=54?pCfx1=zMWnF2q3)jCko39NKZ__n*O%b$Aw~8dPFzZb#{bZfl'
    '1aYHhX+r%uU41Iwwy=9zEhgK7Y+r?zM%~!f>ou<K2}|f0qpR;5^LB3B$M?aoyByAOfsI01iWs9^gd5Ko>7<+j2}qY2=PibS7Q?lh'
    'Ira3V7ZXm>T}-Qb+UO9rQWwPx<Qvco`_vnpLIRM*IOkzNp_N$Ox{ny{@UUiBE~?G(qk8Ra%r>0!ER4?7p{q4*(?p89v}^Z$+UyU%'
    'vzJqbZAT9~6nHpUi>gLp5f1oXjmit>f+7*|5e>shf(f+wZClyHAm?B>#Slb(_q_02bE?oO49rnq%<G+Fx;9wx+Rz1|=j^rB2|?V#'
    '9oGfHqL$FB=OR>Uy}0Of&ryxkUiEZs)cC7t;cgf3GZM~YsKE=dj0skBM|fP5|JCumqLvHbP_O#Rt?V<*ayyt3LywA)sz*aP-bZd5'
    'w!hT-zMZ+L%WHG(<^J&HtF!QWzEHnmhHeNN;4e;L9c@*k4`7ItZ#iVB4Mw(!5gHmn7``^k`VwH@Ls+3k@_V;D`CJd1Y7RkCr&*&J'
    'tllyegT;tqg)~qUE218m{q@?dh~kJ1!^7*NW3twQ$K$dw$4wtWH%Xd>e1trTtnI_#PKE7}A(!ZrmeYLgLouWF;b&LLU;0?6esx%{'
    'LM1(V+y*@@rgA*b;oRE9!A~zXQQm)F`iJJm`a-TTgU(`_TuAt1qzNNdojgh(^xc|-Ur$Y3=dn3n`^h4ZU&kEB>Xh(gxxy!ghLi|<'
    'F+R<mPq&EGBy0p7roMe2o1`)GIsA_??@XMa&_$45m+)~h!Ava@oJh2>tM8H6!c~fiGJKvP?+l*v7-Ybc*3$_}DCO>$fV&uFs-qkB'
    'afO1yA`lsFV}XlRxa<heW)x*2XBV-gTHSxL>4shG)H3Kj=_kvBsSLFs4BPd;l&O7`tV{<?C*u8ab(MCK_}!f)e_JIQ4pdLPuSSL1'
    '38%ARTfu!sGuNUZiOlPSz<BK*t|MV9gn6!r7QRe3E9x7mWi|vyxQUTODBupq)ek~+SlxuqEz<2NiyZMVuVE$-M42#^M}XOiX~P*J'
    'yBWe8?&=TZno09hw4yK_!%InUz(E5iQz~L^E0km6a8(air@!YN_(mgy?izZnQB0hMmaavKUm}`w?=s1QQZ8)HW>uTEOL5yq9*=8C'
    'ce5R)UpHJQ02pYsaY{or=M5-OA>CMAil&%3zXS=UyKN&YPhroC$t0D0ACgR*gHp_X8)*`{IGMr8Nl^Egx_E80c!>1_TMWhq`2auU'
    '=MD5gXEBSZfmn;~E*sED=RaaxMIO4{p!tnge=6s`>U9lm>MH~h#p(oIjTUZD?Xj-ytBKL17>_cdyt!>J*S5A9C4!vuARA_E2uSX<'
    'LCDlnSYr65oAC86+VQsCoVYZ*Hi8p|l;l#w1&3)=D+s*KRcpgXTW=~4KK#|MXce8F^YfkJQ|N+1F{YEocx6n}v8jU#i8(&Fd3kVo'
    'I?Z@(D)@Mqj^B5(9ah6DQW|ERAlMSK(N}vwdGLPAkSg$UHP>ypWf!OS@+BQv=xmWg4Kl`iVQ^yb2Hzx1u27O8+yuW|{t-&L?I9CC'
    '-NrebaPNpw4u^*=%*9+CcdLe!RA>sdg!{(9HTs7P2|a|ELmMx@>5;sB%U6(N^eT9E&`~T|3@Q^(6;D+j9!L3-3LNwdc7Ao<zHa9S'
    '676n?6z5Gbsi>9%X_{%{P3}X(C0xF=m-aV>?a)ozd2=*ZVt?5qn`(oC5Y%n;T#W@_WQu^I+>Z(zMx?{7wKv@K4V@Xjd!I`l6H$hY'
    'fgUA<cBbnX1T=>rQW5OXgspG3Tze`1dH;lDU>{D$N>Dv(FJT`DiXlRY36ZqdVVQwj2gt>&x;Ah0cE+?~*-_^i3%yxP#MJ{3!h+$&'
    'g9|coB_n)7#YTGO9f9^`tWH;5zmb`j==X==Red?EP6M0lA74xz(+au}q2o__YY4OSt3V08!6_7IZFB90{FgKGyrv5Vc#ue9;71=4'
    'X(u*j7_7&EF+9aIO@=t)&9xiZPaKYs*n_@rQ168~j=lJAXf>-<62fII!KOyIHp;>2&MxzlY3_rm02{lAFybo?K%LNo@B&B^HX9XE'
    'D>-Haf7<aYcX5H*`<F7)P1DCMTL+-8+0jOg(QD0@VRcOu7;Y}hwI52<w?2=UM7cGYfo6P0UJ@}<n2*M!41V`9_KoGHl*9~i%)IVe'
    '1mw)Jy*o=^!~JKYv_aZ-7Q67rf>2gLK*U+eV=y-ifQfRniu)_KaaQra?Pimpqlb{=t<_cV4TF#2PGOiJLm8;6H3|XS@bvQfZE(;H'
    'eYgDZRA*fdTZC;`dofEA^)<ZNF=(0?VDFp7UV_j0Xq#(4&Jz#$F>Qo~(HM5!zA(kg%-0e(ae>)CwQ<XN7vMX6*}1xD^?fYpE&x*#'
    'VhedkI4QEsXvG3ObLgZlsQq<P_-o(8YFl=)DA@yL2RUbP5IO(woiVdc#@@%K)Otls{X{<x+Q!x{u8T-xSOA-(ki6j`<|<PKQ&Cnp'
    'GpYk5Hl;1T%GRpiy)(XFQs?<X8zYZ~VA~V*vyB>bmGrW-q;vd~kc1K6PjPpTyI0@g66fQ_2*ROk4O#~6#fvAQ@$`|x8#Wpet0ir+'
    'bN)07*&qGP)of55GFJMMq}Jyp^RG3!F<SZ26v4-C)27YuIn2Cw@BYO*!h}Dt&5U|y?n~i@B><aZLcFFj9V=zJ?sL=aTXA<_V}r;E'
    'TT@IQhS!nHX6A!uREC1fWj_UZR@mMAq3buiF9$5qxs7P)s>%%99?_W|Xr030{34$j4i_eF{jL=wX6;iF5V+%&xkW};x@=R@*I0=`'
    'Y>bG)W+=2@>P<2756kX}6b8Vg@Ox}xkdOL=N3bEOajYRgB<~nCP>)Tk$sbn5Nsd1B2L0KkI0Sh<4@*fy+Z-plCov+6xiGAi%<kE&'
    'S$|k{=M6!Vl2<&1hVaSKVI~Wx!NHXEY}So9fMyu6vWW}-$HF^iIN|EDm*FHkbunqR!5%`%7$60;Lb>w>X!`*O?=5|*#XtR+uzz~l'
    'nl~>mmIcL#PDT}wqatQ<!?C8g2KaD`)3vVhyEmemaydSIi=H7_$Z-G1|JcwUfeFl!SIA`|ziwp=wm0b-)gh0du{yss?_1gaxZasH'
    '83@Rhi9grSP?_-Y?||7n_e2G`uQWuG%v(6>?S(7b70aIS{_VA+BWW&Uicg1*Q2Qlp`)jkAIg~94)@&CJ*0pQDf!jN_0O!CHN5fME'
    '>3fAms!5vRmOzl5LYR?aQuVv1TGjIsd-$Y0T#TjtuV0>z4;Owh{1YD+(<p|M5cKuoGf%`Av@^gL9pQo}`fiS6m0yrDKCNv|DBI7E'
    '@sD>;wuG7ryUIW-kW#hY2_|nCSchUo?N$av`aUN==7653Yd?RA;hX>U^83rB8AC-6G1KCmJwajwCAW0C2{S|fV01+yNAbRtO$hw-'
    '_9K5T$oPvPL=i6a8n=y~ArjY-uJz#vE`@^$!J4&<Qh#Z+;8VvxeOj^hjjj}}IFbjuY4w6mr5T85dnyNQ!W!2d#=s^1-MZ;nUiAr|'
    'BYF$x!quPLo&V(SyJ^AY^remg#wac9FL{X=&xYe*2BX|1xDFr~d>sGTdz<+Fd!M2&`?MVhsjF249pF3<fsbT`Zyw=(WvGRkeF!ru'
    '1NMG)f}-X6c^rOqPQU-{M$ipMdBbB>0IH#Z2$N*L#c1M!F^T+n2yy#r$6BZ1nlJzN@&8KqYdrWrhnKG#7_5sGKVQPF5DF}IjIVMY'
    ')`55dkbB$h&kNGi>Y60e*H3451~KCCaa(@Lf)G!HqBep;fsio8^ecYR;=O4cgou={KP7+uY|ZmuHyCwddknNQxyhjU0J^ErjAM*w'
    'Z;B<2EimS%dEt*sp0fPUD}!!h`nIX5ICCzzB7BaB8wW`Xsu-<O_?r-<;GE9;)|(~4mk(^YejO@BUTx@U+V?yGX}IY;$;SBhXF>h='
    'DJAVE>wS4OM{(nMmi-W2QFx>4QYJ`-hIOX<M`FR`LTtdD?f0$6Anj#q=x7t8k{JH^K}MU4ex7fP>4;c3j$vIJ17W9kKgsFv>11^9'
    '{Q2u)VQvn$JI!r-JZ?k-PH-ftd==ToQYpi{!w*hKg2}@aF_i@+XvL1DW36pYgwgh9!ZGd+e^6E(92S8xq`8_`<q!%cW~ud0^;7?`'
    ';L{2uZy95UxNt%~&ce5ZnKCsl8ZI#`b6ABNR;;_F%+ih(UmrJ_`AWkQ0UhYs2h~MePF$~|wQmzV6xfofq`Kj~)#eli+vv@INN|1q'
    '&*9d!`At^g{zV2M^)V9_u+k8yxK~iU>yVmL0DH6fRjV4CaM-As#&BiVksukhq+3G?UWScE%x1#tFiEb?vvk$6n-|y=GJbt4r0Nvh'
    '6$T0e3Ru`G0b1K&#>Lc*{F+5iwfN=RgxV-z|8Vm)9Kr{S!=hq@q!AuVeDPNGIkWec#T)vxejcCx`3mM(4yOUlJ6^7I9u1RQH=sAX'
    'P{J7%UxV63#Td?&p>vqtf6DKzyoV-2xWLs$L=b0L?%{?oevt--Pf93W*e-LgDz5(3U$+7i<6`nc`UU<Y;f1Q9;AZpHj?vQ4X4h=d'
    '=$Nlvc*opYRiY+b!#<*y+!~CdtFL3JmO}JwJHMRBZ~3WZ<Z0>W=hyTJ0Y>(++BZJF3|n%A8sXUqa;M6ekhF?$5OB0Ta5s3(1uYBj'
    '<9^qg+jpFH0XlUxw2T=D1BRHq6DWt8)zu2pDO^Bu;a$t^x#B>s_?RZRn6|#K(-p6LOY{%=CXj$ppQz<3)a_jGWh?VU?W2z6@lTBt'
    'uKs4BdX^m5;w$zv^$`P%eK#pOV+^Mpdq+-W?`{<rj5~Y@8*=6*Kn`WT_^*qLAEMHzb}jel`c@2X3|A;ty&swunY>ZG;c$`pXLF+%'
    'fk*hw!#KCwwc^j*0sa!_&3SR|B|kA95QvY6p9c(B1(!0Eh)ZC~<F3U{qkuL@P^40Q3~Ofk++b2bvtjsZ+b9v)0_dVRukU^h=eYj%'
    '*FAInf;3HI5m;&;oLQH+4h8E4D666@@Lqcvy7!lq{~RKoep-*q^P73dhE+`7MQhue)0S{dJVZa-|HnX>t1OIT9NqTnRkz1stdz_!'
    'eNx}Ur1UF;!!9X<kwCNYAau%>yuW^FP5t?}EL$>qPOZFfWeU>2Xou<Z4?%73w2}vMzA)~e_peSS_^;=n96r8oa6k<i6KN6qcuQCO'
    'u4YxC*NgZkLG#;*K#VNkzw&l?02_zt5pNB{n`lD~?9`W%K_FzeVFhW(RY)4HSkpTH+~UhY(b;FQ^)kPj15(WNKrl%x3NTOM_+6Oe'
    'WY;cwmW@AebY;j5=~i@PI53tWtcob1LF7{c`tU2D-KeiPU6C>D93#e=FsupbAA`e#%gP5QrmB*j;U=gqtgkC|#p19>ouQZEB<%Wq'
    '17SgZm*camNO2cHw7YO8mQA=F)W!-{iE1|NU;g3oTde$ScIw6~JBB|)7NgsOh-X+=u+YY^Npvru!D%x9A3)#x*FN7yCu!XV8&R@G'
    'ITZ$W1`vS(q{q14xJ<t7KK!o&zZ<VuJpTOdd%}L$;?CBA1xTgPV0_*|!mQadaHcGx;N!nWUYFNt|N7xix!emZZ^7-;%F_IN4smaP'
    '`uQZz{d`Ur4rj6IVPBigfIr>&gxrPZ6o*4L7Bj9&L|fi)iQ9oUTDSlExBX|sdFR#}Xfur~G!MrD|7Z*-5k{lqfv?Q1L&@Y4D|c-D'
    '<bwH5F#U^-yo^ylH-~t~>*c{@;t6dB$$98|W8jtVz1wrjLS;m!xpo|O)L|){wtYV;Oqhk)oP$=&K#fK`>pNrQTlmcOgq7W3oBP>a'
    'lo_Kd@d~qR<wT5QlZl02AnWNA7Ps$0LotIh8NhHkVDjaq_Nzj&&GQIg5P~5D)fPtup=}B(FEH`lh;?!k`ZNYHWO&;1yLgrAG(swe'
    '4iKxzky}P@tc?lJkf$Ky>!7@wpFcl+8Sl1!Rue<ggY{uFP24|4B<Pu@jr$Myuf@#3A(iibSRuIjbOP5CbKKAKVOfVKz8p3>oDx@E'
    'CN5|+KH)Gap$TI!cB%m(815>;149>k7v7$2R);$nn*(NA04}+cBbtXhEcq~`wu@sjUU;1Uw%}iC=F2NjF?PE1(|Ts*xF6&kDMl|%'
    'A<JuH2$G{Z?Ou5k{^5ZJ-*#YeO~gh&3aLpM<Yi}(D?7H@x$V1|<GR+H<;>?{ZJunnl;Ulvtqf=jE`1S_3@~j9bXe3OSEtyJ&%FP1'
    '|GK2u`qo{%9Bnx7s=L&2x-}|R#AL@0wX<GD$_5|!{l&O%(eDc6%U>l)XBJb;;oY2Nf`lEWm9TzbxZ@O>O4-z~Z_OQ0i=jenR7e%f'
    '7g8>>N_2D6*haye1Xxg}ytUr>BLji{7SV1aJqu$Bli=jsRDslyQTQn?@dA-Hjk5}Ko2A>i=E@`9(|FSxG~e3cVd5qm?L$<r4dwIz'
    'dfZt|Z}FIx`nq*D1}D%M#QY{FI8m?zJUEhc)Z}0^Y8s7<ULD_Dw<M18VdDvVf-#QL=g8v$05A3RVcN+UBj^GkW`HtYx$Ik3bGfht'
    '23H}7ffPcvTH^I7roCW9gw%kb9dtYP<-WByfe|IMbHx6tj9x~lDPed^_~~lE)iDnZ1uY+UueM1T0ua!!=Ar9_M5`#8N%n{ohVK#l'
    'uNZb?Zg6$gia(p&^H<27y?6}jF;<W`t;Ffeg1f1RGb$O?j!w^*nS9@(&(hEFczH&pLe<c~F6d=(fY&wxZgo(bQNrS$krEC4a@C4='
    'o2WCvkkLpYFZjWAs)a)t!YM_X%R&c~2bS%BKBRJE*<EZ^y;K$p{86N1cvw2E?GPCZ)sSgaF>;#ed-Z<D`sd59nu`q<ntB5&07&HZ'
    '7(HtKso^xLWiD8?5v2TSbKSZpMZ@Jt0np>=rZjKGCsUD-4SAi=NU7ms;&nWa;{6Qm-xgleP#n&)9_ey8hMj66#0)UvaEw3w*A#l>'
    '5KB{ysif)q_P*-P=#S%uE(65}dc_<a#=L};lpBaORWx^u#DF&bM{WAQ{*V6$YK9)N'
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
