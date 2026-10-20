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
# ca23646ef1b6b9a80dec2d45e3dc525972f128b8 / tree 58a0df502a61504c7f28a9a683e727e20142cbff.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '99c8dfff1ef1d51321cc66cf7984bcaf5661fa6f3a8b8807a258fe4e69639806'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j&vUuL7p-TcXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&*!E<?XVha-65S$)+w}vT~X8'
    '-2cJLACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hmr+LhpX6}l)>Z-C#Su^$h*pyklq`J(9Y)VUA`M-R3@u&27d_KG!pZ@qXeNEG^TPxO6)fS8A+UDId&wWa%x5ScF'
    'bMJ@t-B1=)8msqLd`ZtQpPpY2FX_{q9@E2|9;QRuT6gIEnpBT<F%;R*4aHE`V>y<2Tjo`lO?h3`T{+}?*4<jG9j7rL`?l?yxvEpQ'
    'Onp7|rB#Z27>2TM^1kls@%^>lUgfiw`;;DDKK=7`xIZk1X??5z^~bmS_gC+`cJ7vJ&igJ^S&`?%=p>az*Z9d@T_pc$%G+w!>QBdC'
    '()98ve*5#~WqmBAhdK<^G%cyE$GocZYR=ms@24zpX779{Qom=}|2$NemoAo+&COi)b6#Ximt|Ss=Vdduvmaj<T{d^wSpDSPj!%{o'
    '8K(P#r~G+3eEuap{CaqJ{`_T#_x$+B`>T4eQ#DRgF;-R8jz!hYjThY3X|6lJeW_F4wpnq_s*irT7k+u&YH7<<4XN$QF`L@Lk6XHN'
    'oQGyyigwA`E=y^eu3PswUS4$>mNuKps?8U_ugLl#E6TPUtEo?2HMPqy4L+c&p7GP`!^JhHylO<JW$4GMYyG^TFPp6I^07=~Dk{ON'
    'P0MoCnsJivrms)OZ|UxNIzC?h)m>d>nI}6qP0iG$DfL5L4sGU8iCy(H_j8wD_pH|)JPhB`v%sD1p3?Amc=&R08*^7x%haU0sYK0`'
    'SE<bVqN;{zY_cY=tE$N>SJm~~c>H!Z9Uqp%<@J5Tsp-nPX}Ww^uf?V;vU+TWuAb*2vpF%RDz9EY?&bOJ_urQB;`#!0l~vVT*R4yU'
    '&OC{F=!H`^q!U?s3Yq(PxO#mj&{cVH?KCZAH`K)}nk}W!-cI?Lm)YRfnua3p=CW$C9lt#y%D;v`K0l<Fh;(;P$Jdv1Hy?&C569=1'
    '!*n^?l>Iag0(xFgb*j96(LD{W&a7@~M{pjCLCVr!y^YuT@#4Zo*EV^|i#fGE__>d#ZzryhWiEUO%jhJgw%xt(>ENALUlX%9f-mX!'
    'm&*aD_OZ8VD9XC*q$;tgx=-y`&%VY!O?f6hG~40!evlWw9KRi=Pr}}Bhi5mc5AgHwIv-x{&Np7%vKPO|x=uqi7sHrRxrm1IT=jib'
    'brBQurjD24$+S1`X8kJT<G3GQ<&u}9RNIu(T+B^hc^}O@jN)eB75%czZJ8~3o-)Z+cKc>trIVK<<va~}Hx-S{qxRc}dMa91gU>{|'
    'S9eQ2%vD*W{N_FUnw}og{oVSOF7Bi+Mh|3en`v&xvR&jr%QzQJoy*6TCdtd3-(tCWC*Ot#>Gpgl$9I&U{<!;kc#d4<;;yo|xSFNv'
    '#w<<3NSkVxnOjt@ke7CtwUwuI`>u|of9bc4VAf1gxlHvaT2^DxwodO*W^*}pWpaYVu_pfM?Ynq9S02Ot`c*#-)63<+)+s%Twvv<<'
    'ixjob>bh*Fxf`0ou`a5tpJl9LfAf~)RLlM0%h#9Pv9@W;MMjkkRXw^|lJ7k4^0pIy;sMQNre<5(@dI1hO1C_KTB(_}eVLU_(d9*C'
    'U9v2Xr1$o+uI#$9m~Y;Kv||?R4!`-Z@4i2x%UOW4qL%0v^_yo<c5Nr_kB#8FjH=`%pTwW+_Q&%4;=8(hSb9gJjipER)HJz-mfpFY'
    'Jg8PV*|v4r*B|(bUWTVHY4<I#NO-ehnq?nL<BTL9c3!o$L(;|*YUBrfmTrGbr)>4@Dj1Ki5A(1QXdIK?!I7SOEg9@$Xp}}x-Aq-H'
    'k4=>gxjLarf770JTu)_M)VpAXzO2gB&-Ijzi*hh`lDpY4j)*fY*#~#D-cfhE!r)ZP-;3OZ>0<1PGz@bZJ11L}Gn8cs8d#)RAAE1='
    ';kU!n@!^|)@$~90mvu$pJUyJL9LKSq8dt<PG^uKvG<0L(nYq#D@?(42eT#NO)efMMyluwR!D!}6bt?f=UXF6##s_al)!(<ByMrX~'
    '%jx#m$OOl+bD-w7m@<KQ^s>eta@DykN_X0r7Jydsv8~;7%a1KUOG507FMXS2Ayd?eU0>vrT%=m6a+v$+Z`#^){I=pGTMw*RhE(<v'
    '`Kr$a%6Olhq*?g3+h)$k#XZ}V^WU?p=k!~8*r=+Nto>BS3sgi30Ga32Wx4C4C{qUwEd}!7WBb_^38aTrUk1c5r=_3zW^m&US>xlM'
    '0J3@Gh33lK4{qg$tmxZe&l&Gw%tHVSWh&KN?L0x$`g|Nf26hK&OZhxh%g6S0eQM;r4RS^}2=p{yt|fy*<V{gI;!W8Vc35T0_|bjI'
    'kM5?Y1lxT%4EN6)=zx-|stOlv*N@V+W$~~gC&)+1ZeC6>K$Yu<_p~P^C|&*zj{kuc4LO`u;Z=e3Ava~$C{XjEor~gQo4Fx-lS7V6'
    '-sDZ=3sW`^^&<Ok>!r%mkh^jU_h4R3AKTdT@%0I)H66buxb<{7o3q}WDT)S9CQ!CC2Q*$*eUtz|^Vvh2KujOpQe>5PJ4#pxlY9->'
    'SG2XtY#H4%1=M9Oi#owQg{Lm-^6Kx{&N3YCUpIi>uIi>Vq<YAzdYCj!TDk2YXPF9*X)4RE*FecXc&=Z*JuZj)^u1cU{Q0*o{if7E'
    'X~01uW&@V-SVsA77LcsYPEj`>Jl!u(ug@=Tl3&vwPg~HaZ(e@s`>w{6JJY>)q}?LV9dn0D^QD@*^pT3-ip@lpooOk-M2lYACk;9t'
    'I$qV7`NF2LD(fB=vG4jngVg7La{0EHOK6~D0Ud2?_l1H!lgZZkSW9GKv~@Ri-M$R_%j+8M($lxY^Yhw6yqJuQeXk!8jgF;D;|$Z#'
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
    'NQDMJ64ww#vEDy4(GMe9qE3_Jpi?zo^v@Wa^Knv(%QA=i&v&T$KS;Fh;-78w>n!U4mzchBpQRCgRa2BWT~$+#!4xmsAzfZJD2JCZ'
    'nSNf-&h-VlBoU&j#GqAikD*<0W=a81FRQ$~%qihn|MNz#w=c&!V3u*I+onJnq=jk~ZKW<%ME^uI^E2sWz+dShQ1Q>h)60Q!N}{|n'
    'U0yag<g)V_^9~y9Dj~<o@=33#j<h&vmBpf6q+ND#$@Qd2%>Df)oh^@AKtmtlcfyg%@LA^!<klpGdpFhejbgyh?%4lW@I(x`d`^Zy'
    '_UbajQUmz5+KdeXloMa}s)71c7f&0%?|D3ayZg<pJ#VKpV9Z`kUHi0wBQSo{FIdeoAX;M?$_(dm?tj+2K4mL&`t1;JQGNIL607e?'
    '^s*2qppgV%>4Q(PSVz^R%y&tS`0v@Q={amIIuDO8p`BSH%zv!t>HYa!J+;hh#Et5pxZ|M9q<;-d5JuZJpF7AYcKf~+pTDcB9~A}P'
    '|M+rXE25)1Wu2p|r$MxXyaGbc?V!Z~&NNoaaT;#i!Q<oM_1oQ^jZDGT)=f(7+Quytx$!KPM{*Xi9xWJ!VW_X%$gYQgFVkqRjpA(;'
    'M9~%)P#{OhKZc?iC!%Ec+0P`%m)D+-_wJYDDTP1N9=FeaSp{-GQnU4=PumSsXkLKVgULsbqQ~6H^5<)JvjWC<Uy_FVR?8953&q&C'
    'pqnqORgsTjG*n$`mcD8s$uKxo+3qc@=U~^nKq;8f%@zSIsAe_!JLOUn<N{EG(te1}XR-TT{Qu(}=v;i;SQ5#$lU86P(!5uG=NtjB'
    '6>7E9RmClKf!1recgZ<D|Eha+cbs1D55Mnv_F&amTHgwE(nxvGc$DHgCw+xpj?09=Bs;lr3tt{z@4n(k-lyjcSW{1NRy;C#&@R#J'
    '&#O{m0@5j?w^rcTc^fJF8}@+|?RrOb-{2W((TEC&V>qPEvP9c&j*=<32o*Uwbxm33f6s<ifN4iFI>7KcbQ>l8{xs|SQcLiMAOy!G'
    '4Xt_buFB@dUAefQFe9E1zxvy^zq^=tse({b`brMeOHF`Gt&S{3=G^Ia%^{1{LMU$B&k2DT{<s&=qDD%G_paE#LaG_!uk0vWn!1ke'
    'e2qeq*mzWtzqeZUdC5}a#!X$lpS&0aj)``p=z6sT77dkzXEv+Bh15y%UH;Tn<mdbOcAS3Q^>Ghf^l%i_d^LDJ(AQ|G<RRn_P1F*s'
    '1)2Xc?Opg>EslqWd5e9iQVnI8U^eA+>CPw;D8ka*1a_7Su0*I)v-^8~JWR*x^K$t8B~bqr{Jb33LbD^GlSk-1Mp+zm0qJC*9*|=-'
    'h^(XSu3P_4%GB;_MVUSX-Bj}kYb^TI>g9^rNrg+KH`)ff4^Vd9MxMfI<!S#W$e5HuVWXp<1<?&7a5c<sNMeX&@{Rx%@UnLk{#%2n'
    'am5{9MM^b?3K<C2k0?YgRq3bmNmj8WT!Lv(lHRz3Q@*qNd4!@vl^ZY@5wId&9~^N+PRyN!7_O|4TDofYUH{wB-`=g3Mp3P9L?>xg'
    'rh8Y40Ao<tvPk(YDlDOsQs4xuaC_}>=YqYD-=Ra-YH0fqNMLK=P*y^fL^r`gT^JNMTMH7*{P921F6ot?JCq?lc-NH|z4W1RDqs$c'
    '8(yZDL$CE8ww7F_Xm54-hEBK-1x2q%oG1PMDoYqsJORSYsnfvqmkC2@E8y(YN$WhpopOLXZbcCtYt=UqkgR2bzt<=2_Eha%Z2hIj'
    'b2~Wx<K5}skQv<XXuAez>gdiYb~YF-;!79+Dc3!G+@vgQmfCU7ZrRS^AsW9p7vn46t*5)k*YS-Db9qlfzRMSg3!MPpO~9U6=dSBo'
    'svG)BFy4rp|DipFx{Y2c-Mf~ym}^W+LW|IV7eIGlsR^B%PZ0Gzn5L|Qy*B*J66uQl{LsFU9xUnQ@a^(7<qpJPryo)FQU}LvMFQyS'
    '(DC&Fg~m+&I}f+)>fY1Q?M+*u*;~k>NzZnxQ}fIoRE{O22+@iQ!5zQ?9+Ka(hi_{;P)lNK4+R_x`U2qrFi9Wbc`j^crtV`uVlmq9'
    'IN!2|u=lZtr+LS-NN%Pw6i-~woD^_7b_~u5O9WDexglo&NKEZ5`_LMVYW(q44}RC-P;>VxVM+s^Hi{u;qm-YshaG7bbxYh@O@Gtj'
    'SizdR)4g^2vM;}%%-!6m2W79=TVsG^pj@0KlmHCCDNaqg?dyTfAD;jK=iU7C+x-TqPBKGYf`I5gVF;w&srY}X(vX&fe7C8hef}G^'
    '5`T6XGhngOwEER)<&^Ow@>s+e#8}MnHuZsXcXM<5UV@eRJUA>H=uM!Q(C<7nDMTT#EpG~ZE1!|kbbL+FOH#UJBhSOPN1C+f;0K>t'
    '`&-0)e*;ep(?Z8{N@F40UsOC=Xk(2Oh*9m(q?=;@ODNOl9Th+oH3!(J)e~<W4gD2;hyjp*sarugAoMW6@s>@Tj>mMb5WBnw{IQUU'
    '%&;TJga9rC{4L}c<fB;*T*td>_kT9i*Wu+&Ml-x@ek;KfhGYjvS$A2g4OanlyIGJ?eZOH6$nIu;IQwq$c(#rL;eOpf2oMqgTuHyD'
    '#kY#Kfp#VK0!a&-CXXW^m2Q6!JCR^dx65%1wWMZh5Y>jqjU);66Kz}ispVczolXtU3#m~wP{mX=c}W4kdm|CUr$46qbk5tR$rlp&'
    '+soJ04d6a)*JYtYMoDNgq042bp9lm+7Kqyii9;_CGLR2{)1G!1dm)YR(IdhSXG39@^nU_-Rq?023L4;pVc7jG8=4PX_g*#_?*$3_'
    'q?e}AJBH0y6GW?N5k9bo94)M?CCa$JWk*lxpRZdnADKChjtIxki^*dol^lV5P*t>VJCa+%n5zBghVGAF4iCGqmPVV*6`10JW_9Ug'
    'L#r#<f3RiQQ@SCm;JkcvN6?Sw&}ckNY1d(bZUln6_7QbUy|F%T6e@a%<1C2?0kd1_!%s@X@w;kzYfs*fx1%P}a%u%aT_zo$AYNvX'
    ';o<i#Qi?QxbWhLe#ZC1Ew)-$VK7T!K?22f&!WD$<>UTEbs1k2+mTOkQu$Y4&j-vgy?dtXM{y1EQnwLP~74WP?v3dD`C`Ax+7Q|<r'
    '=s@ZbnyRMw=$>AVzov&XZT51q1;Y(i?4({9YS}p9p=gATL;lp41n)&`Z@hU!^ZXQO{8LKtZ#-;r1YKLoM(P)o7ib>dX%}{O%tCM)'
    'yQ*--qOIJz9seL26?b1>ULJP^CLvMZv{-o+ycz_93hNUg!To|`$%U%n-I_Na-O%&&ba>oz_3LVlP53%fI;bycR3(2vSYDyZZ|)$W'
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
    '|9P{wEt4F=oMM(YfiATM>+nV!RaCviE{ld33*-Hi2Yk|#1op4}i8l~sw?PYzw?-1?9W<qCu`a=xSWM_}ELv!E3yp^Q3b^8(eXS+J'
    '?p=|=Pw}!?19OigCDz$x<-r=Z2qQZU=iUQstDARqZl3Jjk5m{$Ig%~t48(V?`G%Q*qfc1rlG4mD=qt}}-p`LL%DtPC^u@T*sGd-i'
    'bq&H}Fr?}6(d&jm?b+E}k#7BTQ}NIC?`ds);{cF%qmN5W0f#WJEJ7oRx=5V`wLH6ZPt()z{FN=_!|`R<)_;SQaA*3^P_XQPpCXZm'
    '{i~^^Oo+_n2|Lo_3Vz(b?dFVG>>m!~jm4nS7>vqoxCz_qx*!tgy~4{JqFE`nZjJ$eg`IY8Dr|*j><NN8y#JV##u7g>O9`!;m8eXa'
    'Bzc(Uk8LWd;oWw9d{)ZkWEv<r4r6d*`dIp8isUwM@X!sF&8<87j->3~5M$S3oCr_r6!&V3amoxxlM9j{ViNl2vgDiJTRfcMS-1O&'
    '_^943WQS_uI{XZbE0uofm&#LX2K{Pv_ey{3j?U$$eCqW}3=7zR;-O5q>}FqudkG5~<m4qr@s`o}YE)Y!R)mtxhqrTT=N$K6Z+dUx'
    'y6G^%otC)fVpwq%1o)Vd1G7uGC}aBI&eq<*-aW;v!8#OPdUJ#hGBT|dlm*pj6@a)*vTJ`juIH*fJ%4?DiG*?geF8cakn*r=MeQoN'
    'ENS+*c@c-GpcET4ABxxA`#NuAJ=)K25p#N7jig`j7Nl^8%gKq`D}h<mK?a#wn`<b#3E{22Gw`Ka!aJ_-KeD6a_=}`Tl`3rF7C+1z'
    'Mi^nJMCVG6#+)DbE&RrWa(LJr8d&0Ecgr;i(@*yFmp|G}Elm{lrn)e(=VZhn1Jc52315;?&Fc2+DWb6M-%(=wojye?UM~6X`Q>Fa'
    'N(F>MnE@3-$0HwEA|yb@I^g#h*B|SSpIWZGx0!Rl`}}0ie|N6uFK;FEbBnvoJStP?f<kHpXvLI80)l~~|BPCD1>O0bt!$?LE(iz<'
    'W_9R%)X7GCYoa3N2MfFipEZpAYX5ijGK?U~Gr@TM&q3~e-e9)I_y}H$o<<YScxZSKu_Xur48m}Lw3TC;(nof&^&~_Ta|pt1&e0^U'
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
    '4DTuY{x+8VW}Mit+dNIB=+(LwEB*xj11H0Ro=Qff(-l^odZ>%0>DHph`88}sULSv|{QdD~_F{$<Po~8>PVdYN;3c?NkqjbC<5<S5'
    '>CKAywBqw>5&gWYE@iB#8C3*crqN(5LXOANde68t$VEm<M^CmL_b&VxN?s!xHk8hq2Ei2Qqp#6~>kyKpOu#{oi5kR3gg!&Q$+Gyq'
    '?Ai(66nyiqf!gaCATNoQ6l#IiNk&vK?GVre`FGmngnwUkCA;kMi(wCkqu-{`Fj2%TZ8$MwuOdjYchE*)!^%6X-nnv=6^CtZbrb#w'
    '{;0<(L|G|hdXWw>`3+x8pD@?oJn#1|y7Fk=#5UAzAqU!g=CUufn#_&`7|x|R9N2Rd+ti$j>XvJR8ZzG`(!FisOrKFZZYgZ50RG&P'
    'uvY>WVojZM?fWKr`34=w&sR*=*R8wav5Mu#4Rvp)C4=L|cCm}t9o9e&7_-<m#8BZ9BSD*YuKlJel#*Ru)<tOKP)sh>v-InOcM@6^'
    '5=Z0s=rVG`u({j0>~jCdhGUkwhcImzyMPScljAfjm9_sRy(1MWaW1T2=W>U6wO|^4y%;DLfVwt*49(60kI-Z3qD1WgyPozCcC%8z'
    'y~pX)aCu0t%EikWJv<#62FBF>RWbAX3%_LQZDX==XOt9D?0(q0@Gr05E}x+~Yz<@fHI;fES_FQR1iek<wPC=>i!A21G&|Qj4I#UG'
    '{sw`#_<(hBhLC=S-mzrp)R+g{hqy^foP**bZb$)^z3aZwZ?|7<j${`=03%Dm(jlUZfwib$M9846vuZcvV!C?eosr5Xt8;>Nko@RM'
    'iV;SorS`XxMwqtb+*FOrrXTkA^^eD2H~N@sv(^RAioOs1%}6xOSA$J0W>|23jrOSaMv0iWzM+Wn(S$=XLAHyJSdGt~8vq<GQb=J{'
    '=XlrE-t}JZUk>Y>(#vI`(M#b$8??L-@PgI)XyM2FO<+9ZX6>3{_j!67{J9L4->3WpXbVj#e4ztUj!{sU1ZJsl+2hRxgHSbteRl5P'
    '2Z!Wc%Nu7Tz2U`!@XJj#{AdHg1LnE?QlKz;VkR-{T>k8f%vt^Z<?99-5MmFWv>X-bWOOB2C8<xvXMH%X`!ymvsmjiUpC|Cr2B-wH'
    'ch}BHm{WM6^1Q49c2FK*V5v|eY_{b!3wp+zA1>ZObhxk=8S49XwAu`B8p7LO*dnQev$+oY-RlOE3YND6pavU;T30y?if#je2&Z8Y'
    'j6($(6g9S`$7XMo{_bA%gAvu`pH2-iHEqoD@F_dVg!<5N(5W--sB^{$C)mAr@Cma8lK+9{`0GXnFBtMG3vL$ZA?8)dDa|Wi1R2{2'
    '-X#Bry}9(cAG79HX+!o}g`uF_qY1}94J);G*txC*O(H^3RKb|`mMo_x_vPQ}nX(66xDJ_!q~;8q+89nLfQK9T1^}pT=Brk`!<o5w'
    'A3|XHDsnK7>AXf(xGXG>DO*J4&rGk;xFavSZq-x9b9g@P(DND+ME&h279pK#gV7UxfnEjWGKtK@)jX8De>dy0)B2Y)AMSTbKrUsZ'
    'pFXJdt6Bvd^nDt)j=1TW)7~)h`nW=gua7}!+2{x$W_zsciNlFcl2iM#)e8C_(IbJRE)iSy-V`Sf&3z?<uhd+x5{+!lE@xzDMjLa`'
    'S;DQTH298_WxuyvIT=QVk?7N~!(H2Sq+k&{$1zJ_C5pS7o0v@!B8+^cWzJif0af6`?@y;U{Q1sbS)1Q&kY@Ve?rAsED>f~(ftf2C'
    'uQo=qM7gAfp&rbyS@>;I)p_K|<)c=IRX1NcHx>T5p9={HuY)QESyV9|TpTZotJXg|_3yK;50flUKE!vJWICL!89hOL&11T#ylkS+'
    '&Ntoq{<4EJB5@yH=1;6&pamNqoqTUP;xY{p)^~W)h*WVT@)+HNDGYHNn@w)QU-qzTVUJmRe+;mVwnonhRm+DREml1ujzM8_Tu#;1'
    '3&+2`K@DN70ne1NU@<C@nUI2XwWmlUSO5jV&|I9YJLEJ!X4g>*>m1X57eJ{`$%!K*B12X0q&_^i8|>$xu5YaPcz7g4*-FHePJy|M'
    'F*UM^0R?OMZ#ag$WJFbrHuAR3(a*+K{&+zJZ-gpA)3h4OGT0e&m^|v3tA=IR08G&IW)mP#;43E+f`WsWjp+m}#KH(Opea7tm@5&a'
    'Wz?^6^P@R=H>}^vN(?yln>KVkP)SzYYDHP6UvC_}*$-kE?xPS5q!%gkO~2u1E$VN>_koO`-hTFX+rQmI6KT7Lut<o}UR8{>g@SOB'
    'DNKZn5d`&2&N6PZVfSok&rn4QW)7_cbgFr3qBe#$sQaYF@MQiZF`fWlrufiy_8pSZuqZQ`iP3OKqPY)oqut9xmQvbO+%e^*&ie9B'
    '*71*z!(n3{VLqEQrqLgTXc3V>ZGgj_%<MEDC#Yz+Uz@%$=dHlkqxRk7n``i(xd&XJdDI&6=rSQ_$^u~+LtBNmEDqJfv~S^;sC<d-'
    '4W)>uuvwaD`;OrgJcQ_9OS%iuKZ%~nERJR$(uTR+z4j`>JzeeT>1iEBp;@?PVaf&@VQ56CVXqS8j!;cAS5pOh;DBdI7d7k^o4As~'
    ')B~B>55&Al#aW=;thutNT<U<J@!gnqZqHlzaR<M=MrO6==NHM))G8FL;e3VpfZylb2l79M9x^)SrU_iL_!Xy56Sxmn(aHgh5+(~7'
    'v`;X+_F$#Dg#qApSFC>B5hOzugcJ_ML`)+~{)|v44@E%}<E|&5qESIxw>%#Da`(f)`2B;4u=2sRWeCC1%DnNI(4*&+(Wv(!<UkYv'
    '15Vd&;GAOanuQ9CF!y*0?c0PBBGEUktc%P5_ovr~Qn?qKgR$P*!v1+wK7clCY825LAQA+eHt4SGYm6xh)jEbGzjhn@XR$7!x)*Q!'
    'Z)(Lb9fI(J$f&#K=+1EasiQ}8+Ya7XI+x2GGq=zpFzzIsq*F%G22O_FMkT?{ri>2ou!+|E#}@W=KPd!QofKoj;xzu$1qk>BL0cFC'
    'tu+}0<$P00{_m^*mEyP>plqbxP?K=zF=-SKj3}Z-Cijm9Qs{W#ckaY$`p`CZFfDPR@_tfn%Y`-Dy?wMLVr|}lc?{7op%`4-<saI|'
    '?$NBqtEj&Ez^+&zaCj=hAia+iS`&{=n7Vi=yQ?=76I$=~jr@wsflr&6$+TM?Xk645D_L!7-Bzlj@Z@r5U%dy!o`>{hTYL$x_54H4'
    'R)q14;U%W2$>Wh>8AQ;kmmOeelLYb84LpaJ-PV1f3m+*G)ul#AAAZO|Z%JVi%evBJ7p{M8HeVYe-ll8rnj&bKZWT#nVb+^g`pG)8'
    '3F1c2(uDeRy82YUZDIGcT1>VD*}e)bjk>X|*K1te6PD01MpxfA=Iz|LkMDzFcR8Hn0vm<26fs7-2sfTF(n&c55|A!4&RYxtErx41'
    'bL#0!FD9I%yO>t>w9z4Kr7nsY$Ty%F_Ng~Gg#;jran8elLMySlbssU@;bG0NTvVImNA=p<m~A-cSs0zELsx6srim1HY1i)iwAmki'
    'XD_D=+m0S~DDZHy7FCVHA{_9&8kHB$1w|s_BN~R21QTfU+qSZYLC(Q&iXn*n?s?(4=2W3m7?`8JnAbbUbZxNWwV?|_&)I9M6N0#f'
    'JFW|YMJ=IM&qb)zdU4U|o}(J6z3S=OsPR|P!rd<5XC$1*P=gm@856ANj_|l9|EuGBMJ*S=p<eZsTiIur<#sS7h8`6oRgZ>pypP;A'
    'Y=5cueLHhgm)GXn%l+ZYS7+h%e4&2B4BZekz+argI@+p6AHWbP-*U)M8;oodBQ!LEFnn#6^(DZ*hp<A8<o9lQ^0^*1)f|GPPP0Zc'
    'SiNN`28$8J3TdDyRzy8A`|Gt^5ycT3hKJWj$7HPqkH=+Wj+;J$Zjv+$`3QLwS=)!foeJ9{LoU%LEvNa~hhj$U!_Tggzx1(C{pzq@'
    'g-Uw#xD9$*Oyzi<!@0GIgP&e(qP+jU^bgIA^@Utx2A#z;xsdS3NE1e^I(d{n=({xuzn+@7&SP`D_LD^*zm7SM)hXf0a)nO}4Ji@!'
    'VtkrApKcMWN!SQFOnv)4Hc4aVbNC-)-kCT-p^G5BF5%;1f|*(*IFV>$SKlMCg{u@3W%xWp-WfdSG01=?t)~-|P|Dpg0e3OVR7W@L'
    ';|c|ZMIbWV#sU|saM=-_%_z!5&Msm}wYvXg(+#`Wsb$c6(odELQyFSO7`E$wDO39>S(y%)PQ?4;>MHFd@w+=q{<caq9H^dnUyTa2'
    '6HaHtwu1YNX0Am+5}DTtf$`csTt~uI2=iPKEqs}7R@66A%WMdaa1$emP{19Is~?2uu(}DITcq1l7CGW!Uc*cvh%#X+j{vh3(}pud'
    'b~A)G+|?h*HIwG2XhmT<hL@7yfP)53rc}h-Rw&2B;i?|4PJhok@Qp?Y-8J-DqnJ1iEnSNezeF_W-er;prCivY&8jwSm*TdKJRaAO'
    '?q)kozizlr05H&M<CKPM&KppmLb|cK6iqR6ehCsxciTo*p2D6NlSwN1J|vkq2c?+(Hqs<?aWaFGlc4S~b@AG0@eu0=wit{J@&SIx'
    '&l~80&SDl*1F;s}T{fVR&VR(Xiad0?LGv50{#4F=)$1DC)K>^1iq#3a8ZF$Q+GAbYR}-U2F&<?^d2`!du5E2IN(4FQK{m|T5Rlwy'
    'gOI7Eu*C39H{t7DwBv2NIdN%rZ3HI_DaoaV3l7t$RuFidtJa2(w%$}8eE6$h(JDGU=jS`cr_cq3VoWEE@yeK{V^aqg5_5cT^YY;G'
    'bei$nRPgaI9l!5nJFJFRq%_PrL9iueqp$XW^5FfJAywezYOdRG%Pvmu<x4uU(Agq~8f1+3!r;W<4Zca3T%jaGxCwr_{3Dcf+e0RP'
    'x{Y%<;ocFW91ag#n2WhO?p6&csn8T^3HObIYxEBp5_$+Rhc;e*(<6ENmaibk=vDCSprcr_7*r;nDxRu5JdW}u6*%Y_?ELDyecjFv'
    'B--5&DbAZ>Qc*1j(lpb?o7{(nOSpV#FYRv%+o7Ab^X6!-#Qw5JHq{0NA*kExxf%<=$P@uZxgQlcj7W!DYj3#e8#*(5_db_ACZY@('
    '13gLz?M&A(2xtyLq$1d%30vQ6x%N{2^Zp6Rz&@Ogm7sdoUcx>Q6hnj(6C!D^!!iT64v>pkb#310?Tl%~vZKy37J9Roh^q%6gayNk'
    '2Nz`GN=EpEijDNlI|A*?Se>rAej_t4(eDq#tNL<Sod!19KfahcrWJG{LdT!<)(~dtSAi0GgHtHb+UD8~`7dYWc}*7#@F0=Iz>hv8'
    '(oSs5Fj$WRV|a>bnhbHon`<|+pEw*Nu?KzMpxz5}9DDKK&}vqzB!tUaf=!KZZIpx4on7W9)7%GB0XB9KVZ>J)fI6WE;RTQ;Y&I&S'
    'R&vY;{<Py)?&1Qq_b+9po2HLjwhlmFv!jg~qt}`*!|IwSFx*_0Yd@5zZ+#vyiE?W)1I_r1yd+|zFdvOc8T{^J>>JBXDTx{4n0ei`'
    '2*{abdv}(;hWpP(X@j)wEOz0K1);2hfQYk_$6#(402AeC757(e<E-L;+s!6HM-L&#TdS+!8wMZ4ox(6dhB8oBYZL;u;pye|+u)!Z'
    '`fmB*sm{6_wg}s>_F|SK>T7tjW6(4)z}`2Dy#$~0(Kgq9oF^XgW7-G}qcQBdePN1~nXe^o;sUdOYU7skF2HyCvU7FQ>ibyGT>z#g'
    '#1`_7a8hKM(TW9n=Fmx9Q2Xno@YlYF)wb+pQL+ch4sy=oAaefUJ7Z>@jJ=Odsr8DO`iXuXw2iG@To;kXumCnmA$h|?%vGierlPEH'
    'W>g1AY)V^vm9163duM#Vq|Wn&Hbx!|!L}#rXB#!>D(PiuN$2<}AqgYCpW^Nwcdx#~CC<l<5rjk88ng`Bix*Eq<LM)XH*7Q{R!iDs'
    '=lp3FvOoHntJ$DBWUTZhNv+RI=3i@cW3=+4DT0sPrcImQbC`MW-u;Vrgb9COn;G@a+?T=)O8_>-gm_J5I#$Yb-RGv;x8m-=#s-lS'
    'wx*aq46h@X&CCbSs0;;{%YF*-tgyTJL)UM3Uk+HJa~sjpRh1dIJ)$!`&^m>~`9(f694<`U`duqV%-W|UAaKVkbBm0yblIk)udxz?'
    '*ccIo%}{8+)SF`DAC}z{DGY!~;rH0YARqM!k6=Sm<5)w0NZv7OpdOo6lRvDAlN^2M4f?Z7aR~B!9+r}ZwmD98PhvzCb75F3nccHl'
    'v;MH^&KrUzC9il24dIie!%P-XgM%sS*{mCJ0L?IBWfK?vkA-*4aKhDPFT+W8>SEGrgFS?jF+d7xg>vT&(Dnlm-dp-qi+}ntVgK~9'
    'HE&*CEDMSeos23VM@7u!hGR`}4e;R>r)yp1cW*>B<#K%b7Cl3<km3H1|FNMz0uz`cuaL_`e%;C#Y;V#vszV+@V|9LO-nX*-alJEZ'
    'G7yk06MwFup)%p)-vP6E?uiO=UulRWnYVD%+Y48=E0#Uu{o89tN77uz6rT<qq4rDI_Sa@Jb0}L9tl2IctZUbP1Gjf<0nULZj)tcS'
    '()S9BRFgErErB3Ag)k$<r0RE1wW{YO_V7u0xEM?OU%xybA1?f2_$NLtrcn$hA?WMFXP$^LXlH;gI>H4{^xYiCD!(9Qd|KO_P_~~R'
    ';~(#yYzZ|Lc9nrvAf;-(6HMMPunxtF+N}(T^nFf#%mF=5*M9yK!#Dry<@c9MGlq&DVy4AAdxFFWN^a?N6K00|!RU%aj^ceOn-KWv'
    '?MMDxkntBoh$39-HEtU}LnN*vUF*XUTnYyhf;DRyrT)@t!KaSD`?O;18(k?{aU>6R)9MACN;44A_EZkqgf*@^jDbu1yLHpEyy_D^'
    'NAwoXg{wcgJO9buchiE)=}R30j8R(HU-A+$o(;#r3`V(2a2-G}_&EOAdz<+Fd!M2&`?MVhsjF249pF3<fsbT`Zyw=(WvGRkeF!ru'
    '1NMG)f}-X6c^rOqPQU-hji4Kj@`lH%08~Q*5hlrgi_yddV-orE5aRaLj<rt1HDCVk<NuZJ*Ld)M4liFfFjyBWe!hfTArx5b7+>W)'
    'tOM}^AosT0pBJR3)ip_`ub<BB3}VFN<F@>g1tFdYMQsFy0wH0F=~w)s#e35@2oWh?e@g!R*_!9SZZPV^_84eqa+5*x0d!NL8OIpW'
    '-V{q3TVTvj^THpOJZ1TxR|eh2^lej9apqibMfe;MHx7~(R54nm@HZhy!8x7xtv5@8FCW-){W?^NyxP#ywC{NW(s0vxl8y20&w~2#'
    'Q%c%T*8B2mj^f7iEc+q4qVPu7rA&|v4eLzzkHmt>h1h^Q+wWVCLE6jK(9tGFB{BT-gN!y8{XE|o(-E<79K*Uc2EtD7ev;GS)5+-I'
    '`SaJq!rUBgcbePwc-)8voZv`O`6{xFrBa4@haa4f1e1p;Vk!$t(25;P$6DK*2&3)Igk#(t{-CTnI4lBXNOLu>${`d?%u?&0>Zkr='
    '!KW2S-ZI7xap8n~oP}=*Gi7RAG+bg>=CBGktXOwTnWY^ozCLa;^Oc4r0y@yM52}l{oVZ>^Yu_e#D6l0{Np-_}tIa74w$Ypakl_0I'
    'pTn(d^P8-~{fi7j>SHD<V5K2Yaj&3y*C92h0QP3{t5!8O;jmFNjp53!BSA81Nw<a)ybK$Sn9YROVUk>(XX&bCH!rX$Wc>P8NYyF0'
    'D-09{6tJ*W0<^ZljEkuq`8A84YVpgr3AItc{^90pID`)thegE*Nh3U#_~NbVb7t=?i#POX{X9PX^A*go98Lq8cf4HbJQ^mqZa{B%'
    'p@cIkz6Q06iZPrkL+3EP|CHZbc@Is5aDl6hh#=0g+`|oF{2~nupOjF%uwCX}Rb2h6zitI4#>M1?^b7n)!V6VH!OiBY9iye8&92#^'
    '(J^1U@Q%5)szgn=hJ8dYxiuI^S6|0cErsaWc78dL-||z-$kWo#&#&nd0*vfswQqcU8MfpKHNvwK<W7|_A!!xiAmC_w;BN4m3tAT5'
    '$NjD~x9>RZ0(9zXXc;pQ1`IKICr}PGtE&~HQ@DWS!n>B+bH#yN@i9$sF>QTerz>9hmgpb!O&|fIK2gh6sN1>V%U0%z+D9GB<DVKQ'
    'T>Z^L^(;BA#aHZU>LUgi`)*Qn#u!dH_Kuv$-rXuL7<c#*Hss7rfE>zv@n07gKSZTb?ON{9^{p7(7_LyPdOtKRGI^tV!{H+H_vS`1'
    '0*~;UhjDJVYsH_r1N<e<oAct_OMYTJAP^rBKMxqN3NB?R5tqP}$6bq^MgeV*ph%_q7}m`6xxu7>X2bB+woxLo1<*xtUf=y1&T;+i'
    'uY2bD1!<bbBCymxII}Ks9SYV9P*z1*;Jx-Tbnh=I|2afF{j?sJ=Qs0^4Xc>Ei`KR`r!C=_c!++u|Brz%S6LXxIJ)iCt8S0OSSgud'
    '`lP;xN$FPxhh0(zBY|e)LFkk%d4K)Vn)>r`S+->KoLYI|$`qu3(GJt+AA;K6X(bQjd|})_?_Zrv@L$hCIedKG;D8!3CekAI@s_Um'
    'UCpXOuNU!8g66jqff!l7f937)05%TOBi<T@H_?U~*r_iigFwh`!wS-ntB^EYv8HwYxy6@*qO;Fp>t%j52c($kfnbtY6kwjh@w+g`'
    '$*x`WEE|8`=*o~A(yi#oa9}J$SQSx1gUF`@^x;=PyHQ_px*}uPJ4Vb!xrCYL9M0Zj{A{$iHi)-Fm}o@D#y`2@m%|=)hF*q~u<Q2?'
    'ga!580_-YM+yxNrF5HP_6K)5!v4T~inhpDxe|Y>BD?gi^x-rX+;m?r8=(Zr@8P*jnv@vWF-3w@N+6=%4(D(ke&$rP@TDQSQl&n!s'
    'g@K&`L|_2vF|Ic*lW)5Z|Es|7#w!+&Kfn8)uphR#vvptrQYkbTpLdWjYxWGBDT^rh_^*-I<#pP>e)v-^_X5jXaQn2fG(Vq1+}odi'
    'K8bTbpVNiIS*&{4*Jd-|Pj@~cccD4O;gF5RjH?pSmN#7DcHoWH?f?F5|JiWfx%CFxOydg8!?D0W8Usp%(dc;KD|72mGP%Uc9a}%S'
    'V7?Pf|6(IAW7N;hA>Q$Nc`%uHLfb)d9{S!Gc;$QV_MEa%8PRF39fuutSPG|Y-;W9tW??qxpw%)^qY=;g&KUU?KC?YBZ8zBFes&jS'
    '#^_4C!t7c(5#!ioV&NCadOC&0?Yq!W%-~E0FkB9pe0iz;s*r5+JOUVmU<g6A#Zf_Mn}W&<Onf(Do!o>zjX?|<p7#7MUZpyXkjkM0'
    '#42*+meCt)W5P4!DaiObDDURy&re^*yRDzq#E|r0eHcv>_fHWCdZuaP{saDNF*9&T<+~qN2(CVz!1cr&_w#&M*5QdShm8)W#8sDx'
    '3mT12I7~`t!WfL5YCs5vyGroD(8b<`w`ZHx;SR>;fSDG6OYY=|=HU)YJ`Abt;+TvV9_PO;_?Mdb^2$?;o$ma!o>@8W2RTQI(Mwav'
    '^4b`J<fu-&SKfqwc%Z?z9avlwvC)r0YElMy*;(Yuj;(fX`)=mAuJvX)^LbdCCmSxMcw1^K1KNU1UxXwBOq&877InzgDK_LY??2tY'
    'E-ALYbr&y38_v7xE_Ix4jhqEB+3`c|tXGk;!3TbSG45ORy8`+0S4q;D#T0XRH)ok3VTWlYtREQeIEAK?&(pAP%^gsSp+am_NEOT%'
    'QZBPfbaT_#M!}o}SWu?Cwchz71A+b)(QYF>3u6kC;N;v?fz**v_$e;&0+BY2vkG&YrQ5mY$|K&>c+(p+-`e3};zo<mhp1i~%IN|0'
    'xU-nv;xR4tb?a^nPM|S}`Atr6qF@Jja3txd$-!vUG#VMbI=;DXNgU<F#uN4gV;rT=k;el7Uh3<^w39JL&;>xu0A;*#*|)6ba$yM!'
    'u0jw4DTHjb#OqT`d%=hZsR2Pd=yvSOeQR$5BT8oHi2YR=y^K&(!tj>x)75~hV;&j`T0ZVxZIdtrAfRE*L)Qz5R#7yQ>=7vp-y`^6'
    'G3>_N;OeRse>S=2uaG-?@fg%&tRQh(iPM(_cT*8(R5Gd^ot`l>`MyP;rJv*R@{CG_s-b~h(97ZguWba}>Yz5GgvC80B^vtWsuk}x'
    'QD=f7qme{j@Pq4A3x_g<Q;IZ~g$^iB@!0=-Nae<|yV$CFsVo-wqe#c_uyk76Au<@MA=9X0<TTUw>iv%O&zD~{7aJ@z^#)V`kjU#X'
    'der<=!)a8@T(D{*Ncq#|x^+*AhRcxxpvTh<eX|vxOhrOA<aI(LrG|@%*YP}x_cOGATX;=FaX8O<q|4zLcB+XGGr)+$G5+*lQ|OUH'
    'EKN10lBVz5`>HpiKaLx^3=|*e6?1eL^Ac84ZXniF(cCc-1KRi>wdw!*KmH${>L2$'
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
