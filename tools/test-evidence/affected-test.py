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
# 6aee967dc1373a3494b4358f436c213c409cf9f1 / tree 2e7e1eb961de38cfb4f74e6599331bf22f19587d.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '226bc1074d7c564cd0542893dd418db309acb047ea44f5c3d84dd4fc199cb28e'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TS!g6uL2cXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO;EqR4XpQ|CoD<&*!E<?XVha-65S$)+w}vT~X8'
    '-2aD{KOW=1V7xz$|M*}3?fbH$g{H5c9*_5j>5q-o#<BF@)ug6xvw28U*R<_4rYvi-rEJDITiT`?vhMxW9*61I;Y<4TujA9N%l+|R'
    'pS~o&c6d1)AD%ZBpQe6ERW=S?y%cF~hbr&;HVtFmOhuPfOEYC%*4FPY{*)e%&xe=e(;uIvuW9;qYsGr1+G6os+q_%mxlbweOI<Bl'
    'HTQmK-wkC^rLlT{#h3K_^6B~Y@RB~w=`lUb>0vsgt#!w&Xr{bwM!&M`+pZbQZ0WkP8tQQ#yDA?GFMMqFth=?=+|*-VEOAWyHx9)x'
    ')T#BL%c|>}d1#uv8guXU{k7g+<+GRjlpbC_{quFWKP-o7eXIZV$G7|USMSGVYL>1o$}wN+zABof&r45zY`Y?Bx~dx5#S!1N`qS~3'
    'G`)O^-~N1gSszPT4D~Qn)3l_v9`mZst2u9nyq~hXnZ0votlzWje;%sKOBYMZ=4LMYIWN4`EX#U7xtZHJAI922p1W+Ue)5aQC(DTp'
    ')BV9y{yZH%|B@blJv=;r{xZaSe*EM8Rr7q9s&Sf%v8t+eEUIqy(d2EN=DPFSmpbKbn-$lr`skN?;g{E~mbOgQklL;sv#BloxTPCM'
    '2Wwo4cFEc<OKF;}TlY9#UUeCkHk%xyeDV8=tRJ$XY|F8l`qWiZyA0D%cjZ;j`04fG;+j)lHBB=wLqAqs>*o!9*<^i}k7XKDQO#r4'
    're(Qm%{a+-)7Pitw{-VB9Um|M>aMP`%#$6Qre^BWl=`7Ahc<Jl#IAap`?<@nd)Dg?9)@q}S>R50Pic5OJbbyhjoC-*qfT{GiJB>|'
    'QknOK4|y7!tjX)D5>i}M*KgzT+ud}0SPqxh_YJ3}E9<7|@?pIeo3hAiv8}7;xo}TRtv!}kuOIjFeE0ir%Xo49(K*YiYOd?nB~fRd'
    'L_PG`RJb9X$kJ2D+|R?+>pOw2%8P5KX(_v*E@sheDcf;sr+m!IY;bE$Ly>oLSvA>?-yRX=U&9}tAJR)iy1S?2>r1+u55t#-<MYd5'
    'x*ToFesW8vDzB$HRbGGJr8KxYv%0Ar!FenODNBF#HeTn)iwhTB+vF)P=Hy0c=RTgkow!Vwx$q$@uDU9<?e2w72k*T4nwZ5Ad`Z8*'
    'Tn<3Bk6mg~ly%vaWr|JJeQL*g_BHlt%B3-VvmI{l2YKPk@!MhgB<%fmcy^=u06!0}^Wo+0eB;F}d-02`>oinzF^nmdi)c8{Ro_=t'
    '7cnt!>UbHROndWg)~_-?j{D(NE_pdhwM{wA#oY9j_aVa=#m&Ae`el*qWJ{i>OtO{TzL{6)<mE^?Pea~KMbj-=?Y9s0RJ5)JpNVv@'
    '?v{F(tFlP>&3pJYJw2rRyY($y+(}=I9?0A_)7*|_yHr`RjC0Y{dD}Njllr!Gev9SioqQV}q}%hI9N$rX`s42F;W=`Zi@VC=;%b(v'
    '8?!VCBW<c(W^PfrLSEWo)>fX<?YlaT{-xhGf>|>~<ucWyXjzR#+d92Nna$<YmB|Sb$C~)3x9{TdTzL%l>sS3WOfQ!MTQ^r-(N;y*'
    '6ie5L>UCYV)7%YB;aC?{*3YTv#{T9l$*Gq6!<VlwyJKzBmWzxk8>)JAwIttp-sNp4{=@^C%S_F-wBrZ1w3Tjo0JTyxYx^=Qo1)8$'
    '$hu@%9!c-*WnHOwDdwBEAnlk1yTflj?7Q!e=yDd|tPEq;FX}hXpzPXC+#egkcNta5OFoG|+3k<z`Nem2`LOhkMjK0yec4TuOK9nx'
    '+sT7!m6L5-mwo+#ujplX`jU3v0*iz<8>U(Iu{6#|@?qyyTRS9eJR!AT-e>9dw{*%@->!o3`1&vp8-d0#=^Y&Dx!01xE`~;F)YQ#X'
    '75Ugy*^sLfs`NMQX~*?crX}y|er)=(DpNn#Q#LNj!Q4siX2&=p&a`A7+|hbR-R%m4Q!Rflau=qHu`ALr%xUbLY*o%smStV5q3e&n'
    'xAgGa;pzDB&A)hhb(hP!B5<BS3CeLC>#1=?j6;*Ewn;-b7M__KeJ($?r`@+`H&pFVsw!HLNe82uE7h$8OnEuVeH$OV9aVqdcJ2<6'
    'z%QrUV<QtB$IgM8+hWQD;?c_*`)2ApmqqDL8`DzQ?#H%v(=9)?04)izGrqvlWFb@3iCtghlU$@)s&bh7>2KQFbo{pBBwG)xS%y^h'
    '68Wmn1<H7zoupa#w%caT$HhI{mGj@TtLOAvdf2F{m8|_##|u<M3ILhs)n&QsqbO4c4J`%o;bZ&R6$zw=RbK|gFsG%T`etzB4q4;l'
    'p8&FX<AvtR+z)Q$hpgz^Vb2-wfrmo?3}q_ST<ttT)cSlJKn8XPX-oM$RLjTqb$x2&y$y0kI7mH~0dp-G93pRu$`NnMuCT)@TgH#>'
    'OMY}WJtf%g%VD^G-arSGTvb)LXuE!twk?Z?6*)mZN_O*df&r>rKfI?sDM9J-cX0d<v}nk4-@L3Eqz}0%yGDVU5A9qOAKT0g*_#}4'
    'T=FJw8ef>Qd8ilJe_JnAo`&3&Q@987V*1#|o{z6jK&|QcHNmZ?%h{au=1fsEcrt;qB?xW<s_vr%Sf+mV&?XSm2e%Yi<=u`F7Q!T7'
    '1NIedtuk9i_e=qGnacuxpD)5wmvwpdcWh@F4)?DcKyO!dQyNk|WK}&(8YUVS^&n@N3Xf?j%dXcz$v=3mU%ovqhx_!sTD$!Dw=Vsr'
    '98_oEAQ7_x%XloKd^Zb7R%fTEn-8Aum#5d~7dOeT>5r!^Xw)|^zw~`qW6GWB-aDFlKxsDS4pr)wYVOiUDuOFE6Ipgv<}FOL=)1++'
    ')A7*ps>aM0HjPzT_ppe4*Z&!$KL3-;x5ZpS104(KXj{846!e))w$8^|A`7FfyQ%B;W!PU{*Kn7fz8#*Q*B;`<WNhqv{fKCEEL|FB'
    'n1*JlGI7*qs!}&)!z||P`^jIA@%E3$t$-gFw0fc&`nH-XZP`L-Q=fNk@Hxw8aGcL%-<qei<#OoM!76-srS``hSrp(q<p3_Q$>PqL'
    '^U@yXefiUa%m24@H_YD-mv0iC4atZ2r#0C$x*t%9d6@>CE&s0sa8(M1odv;p)jeQhmbt{0Wl<otQ<@ruedUXXf&_dtDc6L7eP`*%'
    'FKKs<F_n2LMn%5*FsfD^pt-7REoyzdGArh>2g2{H7k}*c?D>>h&EUQ&=edOP*KHLAe(Gh<db#@I(PmVe&FvM7p9<6I_>}H`aXmhy'
    '%QZxVR>4f4qiSZ=U(-UF`z$K=UNfpurw-Gy6Qlca2j7mrrL`D!1#Mh~Ib5>UR?Wt)90JCb)<`<zZiI{Vs`ggnp&$0|;ku|YO`dpG'
    '`m8gpFHL%NLcWywF!<7v3n-xqO#Qfj{hgsDpBJ@bH$<%sM`=4>Tp(^f@y>@>b;7&6yWGF<DZcD@=4v4CT{E|EeHFQ{u#-!VrRHkk'
    '#sv_APV_&oUHZ=w_VOK~k)26<2B~XcA#EYE?>u;be&%)Oa1sgGa{Kb<Zr}9ydigo{?(zv$AqyxPEkvE+CTpO??m7L0uGMJiZ`jDb'
    '^~<H!<jiG#nw^p_S?c0@C<}kk4bX+A80YNzBOqa4xg0));ps9KG>&f4BD$<@l}X5}YkQhfQ9Fc5aO`9n^E}?Xg?&$=_57`uX?hRH'
    '2D86n8+iDG`Z&4SC0DgP<A!bg@$&Wfun*9T!>>pH>i8biPbfmEZZ%OVz=|G|>e%zDZg?0^=?hFpp)%k7>uGp=+{&`1F;o674uwz<'
    '7?{g(tOq?|6?w|l1|q|7!@&S7U2eiQjXJHdm~?KgqO}MbTy)!tF+yZ8)M{;#Y5&su6N0`S`k@SR$)XvN=FE*$LANT&!Ca5Jj6s1}'
    'uDFkG$_n%sYEAFP^Y@cStT^4yX$UBAuoK+5X==(H)zImee>yxozP^0+*6+`(s!uZfPyb31Z?Kw*=;Chl>Y_^Z*4Ohl$?TPiptS%*'
    'z}<_-Qq()Lq`&OO>Yvga#HSxO7Ny7C@Dh)18#o$NiPAJRNP&YiI2DtxS6R|lY7c$l6sL9vIQrhkwn#gRFCg+KkEIB#!4*2s9jaZ{'
    'YJJuta+rSJ4$91WS-+7RFE1%ob2cM8)$A1!q60pv#oE*%z4=7(MA~85x#Sx(7P0cqdl;U+9iQ%A{d*f(OI`R7+>tsi@UW?wqWlB3'
    '_FbFj3z}H27!}6%?&DN>emZj{K0iNA|6h|wwm0_w8lB|*t(-U|QDCi^<_4ZAz3n=@L9Yn+w32cS4Lk!-?)&v@29)2n`@nYI0EBg0'
    'm$Tk#YztJvVC4b}A`ek>RQMB%bl5&5p9{j#jhk6XoTt-`OgcR8K0b5fdzA*J0u)swxABB!;;pH@hq?AgvczTw{c3Yx<LlvmKH)!m'
    '0auZ&Lj)>@9s@{^Dw_p?wrv9efstvql)=x;Kfbv$X7|Hm+u))2?BaO|2@}31q%MnYuqFdWPE!QqAy0kv@r@m{fu7!8>X~$Y8ClS$'
    'DzN7|-SQkSXU?PBQEC_$_;mP%2<Lg%{|!5PaA)0XdJIomeV0#J5}`*}w63*O4|XnkYV(7XM${NJueNblkM+lQbxL}~h#xw%moL?E'
    'K=NvVi{4!(P|ZHbxp&l@IBZ*}0Mx%5KfbkVV%IFsaP}R1{CV-a=rsKioFbHJAV=3jy*B&}pXE7SKYUv&+1K&$>+rn6jz*engn8SW'
    ')Ukmk$dCqrF#>=R*M+0~FpYo189QBtyWs0qpHq~8?Mwv#vF%pKbV=isHN_MpwZenT(#JRTeE71mBMzh>D&HL+Wer$#87le!+7%GD'
    'TgI;QF=$;)5?v1rzMB3w>}}0-cC_8QH0OP^*N|U(XHPY(B1*8(T8W5_lxFDj-|!K<2>~u|XVE{#0tLxRZ9qdESg0u)bwOX}0Z8kY'
    'x)E;N&f6Y7Uw2jN_ghr&ubjt#t2#FmjxwSI>edLgfZFEm&2RDhuGWikgLM<o6>_%wa1f^|pQ6MYjs@2pi!y`?h|M2<KIagB8PX|>'
    'Lb2q^aUr8ZKv?lv#CQ;bsE$_NLp!VbqkGx$nH3l{LFz-vXrYXFyE^Toe3-fcx;YK9QT^=p!&^Dm4}bmGHX=Y4<<ipXoD3s~y)3hK'
    'M*3g;TcsBk9TfohN4IvxmVkl)A5jrstCCQSL0Xmn<upzDI%#YJ9?vdRlk?#z1VrbZr6RqxB33|lm|nKA;6*oQ$tK-UrENF$kx%s*'
    '1fnTn;&5_h&Cr(D>|v{jRi!CHimq;z2MPj;yfV1V+DbDihJv!CCENeIcQ%^zdoyZ=YSD{F7b=NPdNn+<g_I3}I@g8B`=1?7*Wd84'
    'Y@rsZ(BMbn8louH`-dj_VMI$4(#z=dXN?#AGY02;oYdm7%;Em?9jg8h60N)VXB+)G%R0dHZ$;c^X@p<Z6eUhq)s$l}#mja`mzNF7'
    ';blywpBJ=qeSt1Xgs3VpXjR-}Xjhz>Qoz&8Dlac{N_f`)ywU6J%drlaWnAjEDNqJ!p;|>-sY?~nKM~E$KlxDsf2D^&#Xk>EF9*sg'
    'iSo*HdD-BQ%g$%aJ7}=0gd8W!C%vLN(&C_17K?U~cG<-x*OMYK_xGE0wmfP94Sj^)2}df!XPq;UTay&--BeREiUB{nWB+5p6EWoS'
    'IT-@ktIG^a4dB~qGd2iNPJG#`2I^B?JZ=2G=kfUM?l-sgyq(g3F?%(2?b8O1!1z(WU^NSYBzSj}8P4O}|Ezg^%2wv|+acbf`tI>1'
    'R^OB8Wg$*LBMHFL2cKfGj;c$U?~)wx-?LfMbJ$vR9v)vpJF`ZZ|5(w}`}4VaYMIxF8`VK^$3d4#{~DGcjJ9n)caT%;_I)cpe^*sM'
    'Dhj^;@#Vl)L`RjD*wNL~AlgA*0iox1&|&~*8Y|^E4L9!K@$vBb?QYLTreJI9CZ%?5<CclscoxeeIg4127L39$)K_j~*F(UUX|&fy'
    '@wN)0XbTJ|kR#+DL(z;=H&8o}8eY5hbi8-J98W3ynfADS_RA`e`;nTBU|4~s_Sd`suLqNlAVrV4ljYCX?q&sy@4h4r_pO#Aq8Ey>'
    'Z$UR-SgRr*!)U0wM6z79kYpH~s%-Zb)^o7yU7!@q=w^$67F4skLbh6Hbc$&I!;HKKm{zg-UHt#!9q3$q+gK9Gwv$$1BxdBbe&-wk'
    'uoY^x(^bVSc7fJwxp&DqJ^!kEb$6Uz?+?H4diG$|SX$o-bkaz9(0G*MIwyUFUXIIzz?9nh#w~n#e7*aMA9<giH(*UY#aZ!4_pe=|'
    '*`HUX!~~>MMsKaavGX=k_BZSUDcbdp>b}7<(xMR+5XW#xn`Mc%-y9`Va1knUa_XA0%>SMZtpL-GW^{nzb?7!q`u%Cv`K6YqsgOw('
    'QoO<xysNUgaaS(xC(MZF!>|7K?e8uoUaBC}l)jP!^->ccQ>!COkvVs|U318ywGfIM_j5uZhCl8Fw5XBN;k_&NuaIhn_$xcgmZq+w'
    'J71%aBsLyZ<nPQERNkq+^|QKqKddYSj)``p=z6sT77dkzXEv+Bh15y%UH;Tn<mdbOcAS3Q^>Ghf^l%i_Z5f^q^fg*4c?kJK6SV|u'
    'LFT_qdlx=ei{s&8-eO;>R6`jim`yodx-%NiCWQJ;U}w4DN`yK!yT9kh!*r}ZFNfb>0`*_P&&zQwG&>SHd4%3$l*K_8kWL2b0XbHK'
    '$U55Yy7m90Ozpl_l<7mzO*N0O#-dNHUam@1B3vT9(Kgt9fU@g0@)TApPy07P#-tPq8yy8Lh;A5xt6_FS5<?`DcLb<_m%W?t-x@@X'
    'EAIFzQmQ#r$Uv}uL?LpiN<W=XvWg|)5=?`V^u`^W@}1q!BNQE~+<>`=fEDrj;D{sPud|fIaAk$m(p9_f`rnTJ_HMN_ifVNuI!UWC'
    '-Mdl*7=yx=MapkcVF{g-0w-97+iQ<I7wmof4jsA{D;yt04_gC=))iUSI3-x93xncjYe9mUKmJGBCB4#fhcd(m@4E7$mp(L31<avw'
    '!^`w?=(YaC){?6f?X51~&<XdUpy>68^Q7NjWeH=7CqS4vbsD(-GGQof1)P04X`LsyQx0&)ttg^nt@<VclC@0m_xhyWo~pfzt-thm'
    'ZU@JIygU6HGK2daZPx%z9o<>Q&IY4Jd<g>}<+_KDo8+(+2p@BH%XSVA(fGx=7+?8rJ>5ONj&EF;%X<>?UA{nE=mhv~0`|;0cO5e%'
    't@Jivyb(A5LwgE!8@*JzcP(u(*O-=s7NG$zfbPIj6FN7aAnJQCO<4zfZTOib(iQvpp?xDgSklYk+vRJ@9f-kBKceiV4vyQ31kl%^'
    '<Ld(ojhXy+9&Xvyy{Dtwo3=u;w~$4Xo+DSM=9xXH97{+Mq7@f{JAef|B)?@3-_~}Zmc-T`cyk5%0^tELNgv^PE^KFpX_ozn#c03d'
    'e9Iof-p3xE<{i%>xtYpPJaIj9Qo!xlF*qkI5l9*4hMWN)F}1hsLu)ju@yAy^_+5uX&E2bnDGhwuD2AAgQhv@JcBEa@Epcl#{Y{5s'
    '1#9k3_txplzWjbNcXOj2l)YkajRBH@a&eYW0x$rlI5p|EuLm}Nd;$QRck|D0_Zy@-$qac30;2nbA&`2f;{T;eLs}B@-KL86`ES@t'
    '{Mlv9fW=DF>Q|?gQ^t?TV-aHzV=>3u)CbPp&CTt530CIw;IM3<H-Tb8zw^+f5QV_DyeaUld`3po@ijp&N$Hl2JP+R<Y0{p9AAD-<'
    'ZxQ$X4LnhW#p9r#(pbp$7Zr~d+E^n6VpKac>89BK63X;>M+Hzt%>g!Q^~768Lw`jdVgMvy>Q+z=2t5pNyk!%o<1yVU#4hgve=KAo'
    'GwjGQA%F`3e+&5q`Dm5{*YWP!{h!VBb$EG`(F`w}-%9X=A=$xE)?Jor!&Ly?ZWd%z-*1=%vb)(I&c2&Go~@%mxL-FA0)zwrSJLlk'
    '@vWk5pk0Z*K+?jd$>Rt}rQ09GP9)gV?Q$GLEvcCrM77~@BS}L2MBA2rYPr`_r&Gi8LTVHZR54XeUe@FOZ#820^v86c&UxE3`9dOp'
    'd-=M$0o<qUx-4|aC<#p_bh+&G6M>+}0&)8wap(m?2J+!=+S3kWFQgGZdPMl)Y$(i<{!d`9D*m)rK?8g+47<N&L-T>_-pdB#y&z$q'
    '^wKnX$FTWof@n4I^Gw)7juzI{5@p=qvZJT;&)2P(kIWoLM}*_&#pE%PN{&E2s4CjG9my?WOx1pLL-)rohlgEQOQTKZ3QTc9v$}M$'
    'q1Bb_KiIPDDcz7&a9%#TBk0F-Xfz(CwCgZIHv++3`-r-w-dLYE3Kc!Xk-hC00%o_;ho6*&<9F5c)}Fi{Z%0j{<-~$jIAYB@1o1M9'
    '3=h9|ky51jqkDQzFK((Yu-%8@@%ig<V^>7G6|Nv;SHH6fN0oSsvs|+ZhQ%BNaTM*pZC9_4_s8Kf)Vu@=uYhMIip|RhL@9!pvmid}'
    'L<drj&{Q?WNB8t{{53tCX|tD;Ef{XFVkh;=P|L;%4@Dz%9P+2WBzP}kd*jU;n&+oL<DXKBf8$}3Bk0;vHd4Q!yg>8tPP?$PV-|wb'
    '*j0rq7H#F$?f3`LsJQ$3^76PVFbRqJrp3yu;ME`)R9K$~3GNphOD<Fm@7BEe=!TxBr^Dl(t6x`ZWbMqGWUAGdG^&z6AS|y?<u`Yb'
    'P?0J*Kd_-~nyDU19u5R5%DIpkt7KKz>=8(`_(r;1h^XrE<_~^8ejCK;_4@eJ>-%!N&YjbNG6oAba-tO@C#=N1L4TDnv6%>Crw?xF'
    '{t!~z9cZ00rK=KE^C<jL$Uw1X$S@<du8=Brq2>{hs=s4Ds+x4zG6D(*ySawtxgcaBq;1$&@u4x1K`<+#A*gkleQ-k|XW}onD?$_Z'
    'VM-wQWWH&bt#S*ziSL6bAMR<htQuBP-nyj|<LLW0_JiW=@~f-ErL58iWI`}VqiI6h=-VrDcyEkkUaHgV@7h-U6_s&^C99OgYYQhU'
    '9!{9aSc_8&3FHgbdApEFO761zoA$MA+uMXwbb>gFj-e&0aFxUCUgnL6BUVBq8PQK4+)&)AJFKi3vqU&ruwJ2|4s@p-(MK;%nTno+'
    'loaiu{DZqWu^gX#bT1f?o5~6-SA;{UMn%a=CqR0Y2d`VT$YCz5lQ>*pntpIs=lkRJVdulrv4zXZZ{6*K64u;+p~DjioCgGtp$|@A'
    'Q+n&Rz8qhU!6}z;pZB(rZ6mUW;58N0*Hy3_5h@WVMg@S@Vv8t;F?w_K4rC$txB**U{>Db$8!~>OS)(<ml^UxqH=mlK37D+Csqwws'
    'x{>?iyxLiv%%d(NK2<o8)9Rs+^s5HIrGZwbCerqfxeF?5k^2LCiDKydlFs3K*Hr>`$OF?>yrOEF<5318S7=0dRpC$8Dw0$uAKTa}'
    'qMp|;Z8~nYA|gSP9wJQev+YrUry!PN+z}Nj;-VG0f<w3N=?shf`Ixr1)a1Pi)_jPN#6d|IE-XRa)t7aY#mG3+`RxUWRoU&G-``Gf'
    'q>{ph=}5qKniHJuIW@OIwI#pDOhfezviZ$v$-^-kM}g+izk6a^jNjaShW9@OS23+Zh2RvVFf5$FHF?OHc;Vb!e;n5w@>CAt%)V|!'
    'MT#0m42Yz87?X+8_~U^<MB_2Vl!giTm~OsdL5p#$)%-&CKBNX@HH1}i=)Xk*?l_wM@dp%p6Avi!Z0vLS$d1m|5O*(M!*%cSc9;QY'
    '(WkJiWHDUQdh6@@VVXwI3p<9Q@#fU%T#~7SL`Q_fZPGz#bA9XB_b{to!cD>8=#YCCx(9`9veneM`5s$u(s|$AQMlQ)1(>yQ%$L8)'
    '6@k=R^19iqwRFCioshlUzL)imC+*n#wG$;)a(wSbRai~15B}psA1Z5FPaO>Thj|~(2Y2+_w;cu_;T-~XG5D!S1)RE*Lt|<;BU|Yh'
    'w=zqthw0`#=(jEs*WUt7+e+`tEZ9SRK-Oi9y|8o__K@zZsIK`-E0g-+13O8-2VXuK*1K&-E#9|%7(AHO#6hoIt3yL~+^qgpLWPOh'
    '-A6WcSf5VX`<VKie0vI4WW*ZOmhiyCxMC4kg+UAqBn(-~{$o2j?x@F%`-!Y9n7byCn0bWP12Cf^2%{o=^N5J;?T}~e<RvhM<I@J^'
    'u!>~83|EI1d7F18*`xTJlDxHu%5Vt@;0N|`CIe1edP6ij%wj%eFnpFlEPN-;ANFzO9HuBfc}m(bePk=&?<o;*BhQ&s%#0}^98g{|'
    'mL_AG!?#i(bV^k9ZgZdb-?5qP?jQgx)I#*?zUnp*80|``Rq#(t3^P%MCrBDUu$hn-ZfK{3vXH-oyB=G=x(u_uDJH>5m9b+aU;__='
    'ar($EUc#;OE=XLPSd?-&TB4fO(kTh4{pcDCcM!WEN`lN(JRga@-*bqB6GG#^VfMsdgVmm~TDa)FhM{NTt!b)Ml}tx~_D9RjY1W^)'
    '=iS=a+z|3}!KOz9y(5>wPQ9p@`=o85<aCmOKH*M(%O&Z-gk}Pka^l!-h~Ko{xDQq_6mbkMHcVsqlPl7<jHd%}mSOGBtsd`L@w^!v'
    'tp9nlw=I(#!kl83H-Rp-2J7%f8&y=j#4d}57z^Y5lm~p$lLYp!{fRdaWw${Kj<-e<<{dPpYOyZCnOIEda4cGAbPJ7!`U<$>oqeq('
    '!tPy>!B6qBSOas9Bqi3_W#z#dwg@9T4d>niY^$4hb#9*Q-H%ilL^+Zz=nTYnuK9+UfTK@X>5|gSFz74KZ{E+3EXuu`lJv#6(WstK'
    'lywclV=$!Y@zLvsLG9VuT#;`5bW`!q_U~zJed7R-ccYI>OaX^5uPj0%iMmLg1+_f8bx+gN@cfl6<iqi0*w%l8m2hYJ&`_}KfS)3f'
    'hyCk}9j0DDz*X=SSMcNhZ8vAkV*hX;Z!89tn*V0{UxWc!Xh9^-dxe)dM6*(C-5dk{3OnuGRM-m5*b@YGc>ggejU|3&mJ(VwD^Zy;'
    'N%AnyAKO$^!@KSJ_^g!6$uv-M9LC_r^s)5G6v=Ji;Gr8Tn_GAE9ZA`}A;zx7I1!%KDel!6<CGbYCKn_@#3c03Wyv?cw|F?ivu^hl'
    '@lm~7$PU%Qb@&+=S1SF|FO{d(4EojT?v?)59i7Wh`PA!|7#6Sr#Y35J+0DKR_YxK~$jM8L;w_``)u^^etOzBW4{ztx&N=SC-t^wW'
    'b<<&jJ1ud|nKc>ON!1Rh5N2nzZa$_D?riN1?A=q$8mvR%r8h_DAS2USL0M3ZRso31B)j&f<9e>z)AQHYmq-}*-zT6`0Vxl=R@APN'
    '%aUe~n-_723QDm-^Pza%y|42|)}#IW7BQ#S)kyjUZ$S!oxSX80y%Ly39b}N1wYi3(n-JdWI|E;;CA{PM{v$g&j=xBnRH?!yZt=ss'
    'VT2KeN_4LDXw3O>-@<Q9D2Ip5p@AhncDG!UF#TjtfBB=$)Y3#zZ>kFudrn3SG9WFSmhdGR)vRv6o+1kC{v9Q@-|17d;^mV6o?l)@'
    'qf|gBlo?PVbUgBrB|-vZtOI_Jas9FG_^IW}dz(4;yU$PN{CDSi{_<8rKexEc%%d`OE-0i%fL2UdBp?_#`p>AfSJ0i`*~(_>?}C7^'
    'U{;6DN1Z&4(L_be4;FY4K5H2J)&B45Wf(z}XM*wipM%`{yuoaZ@e#ZhJ&h)u@zC%fVoMMLV$8VmjGKUIN*~$9){_uX%pnN3IY*PY'
    'F2%UCA_kQ(h-CJPn#d<7+n+|Cj^@K5K45w}=-d79$4a{1(3k~}I0kStl&gc%t72~8PRI#LXux}|cE5rQb=n6h-|%#{x;v>zw(4VY'
    'F9ghpA^?pg9ARME2v9L^y+j3PtKRm@b=zRgefKm(7I^n1{<_si57S$UnmJNsW=(_=h-*t0c&(uU`ZLB<%YM4+cj3Q(-mqc|Z;>|U'
    '0^sZdE-*vJfGPU8YVc>tesvm#rnzqM(<_K$u<JcwRlpgU&>=0dHsMXG9fbvs$H+lFw7G^5R#)ib&N8de&zx(zZ7mN{ETJ(oZ0y(3'
    'v`kEIZShIsqR#cF*zX90^?2PT&amg(LD+DhQ)s6^e#7Y5=#V97c?xd6GC{WjO5+aX-IeE2--*-HK51Yc(@|!vIFvh{S?X8>>N1+V'
    'yl1?lmKxo_uyoxH5K4x1;^cmQ0I@MLpwR4#3`0e|cXvCHiZ~eqCK&tw)O7CRHdaZ>wiIN{Lw~@<f>5W4YXSjTO)YrCKuRM%cwf#-'
    'edTL7hv*+3!7d9mUKUwsL%W!)8{yH2wpCaL^FY}Qel#x9c;y?>(;9`!_(C_9rvXRhXZ;lw7LX3mVdj?(?G%(6w<*&LZe7<c|9X(='
    'y}WE3Mp`z%j%R$_mtZjcqMRO-a|H@Zkb0*8?8^D-wV(fW*y>Klgxny3Dhomx%N`;ayD^nXrN?Xp^qq$mdiUDlPJf~`eGBW7m|Kv>'
    'J)Tn)lcfUlHPCel41l}Rof(4j2pD3yoyQD?y7=HuHnl+}sWAcQ3Jl!vAm^kT6Jb$?jE!2ow<yV$YP^0MvHF?owUb(5$WKopMco(^'
    'o<TO8@7xz*ln@qRW#G$@rz>7gNP<2EkNc0mq!N7clIXQU%$s~Tet*7?E;beaE2EiXk{GJ4K<cZ(bE4F3s@r$<%ki-4Dprlh-Eu#C'
    '*|24f*0UCQu!rVQ3WQryT=Y4Wu-q%`U<|=3Zr{;K7mDqn%>A-8C5NTn5`&ew{0Ui*C7xnSC}4v0t*aI@8H|1JZ{H5q;*o;*{PxUV'
    'Se{TDHlQ3Gy>Q7Z%g~wd5!2ms*_p%E#kh=6vDUmvwhE>c0Q)+sY0$p<ePc`%?}{=4Xh|N_@>uakkU5+g^c-kX7Bg0hEm$=Du1;Kg'
    '@w+StLzx{o<Jxg%dB|g0fX&)r&9*Hoz(POD-K+X6HnIs{;XF=xOhB4L!B~a`ejdCicd4&b$;`KZt5iR?nEuVEi(BWfTZT4EP-7#N'
    ';Cu)rK*cQhO3a365*A=*m|>0fl<!>sgf?#&1jck#jV&Nt4;Tq|d-V)&s5v?n9y^Iu%9fogo)rRbYT7-$Hq#Jf1THB$6J~+5W@QuE'
    'Bi&haZKh)FH*Mz9Z#y_Xk!?WzHm8oYF<3xB9rKc7_9pct?t8ro6}Si)M`Z-=X2$k?*?*nV#iKN7%dVUUosOo_6D9@dymF!&gKZzo'
    '0iDGpVKed;^L6La92tB`e?IzPY924Ybj}A|5TRn+_Y_iyGEDF&MPQwnCeSHG^?cn1Rw2*Euq#w2+z37`Lkt87AhinDxj8%vbL;>^'
    '(Ti;FBVQ*jZxB)G7?oo&*a{3NNb%i_p=0_ewons=nEJXYYB(GNF^xd|`{Q)?^7^pltrn^qcNVl3v7C%6#gI-KY1?629wVlxgQiW{'
    'YplB>Yw>iq$H~d?>s2BV%7`UKQpiW4RZ~dS(S?}b#`L0W&#HesOhgB>(6!T^Cirv+fD?9<imZ!?+Sb#$ijP@Y)Uw?!B*!}zKl`bk'
    '><R9+&Bxt9ZUlXvAtqKAfsCQ}`h;}w@&yf0D<*^*dzJ?3E`MD2%dJuedYYMd<njPdEs{LG=jL`%f3B~;sW$CJen}6%vN!*XRRf1{'
    'ZEX1DnVDgPMa+RhKT0u(c8Uz24*`P9Y=))}c~jE#w&-b2c#Mo3gOj!#zHF5JbxhR(2cnk4e26^c0Md_0wIg(rGqBv4cCP+rU;Z{@'
    'S}OD<Z9H|}`>U%Xwd?wb>4KqQe6#CtcZAZ3pVWf=&MmA&&cj7xTYxNIdjxx=;~@xLA{ljtssjHmIeA$WC!6xaw-wK=&Rs8?GowZi'
    'ky?y~hVgmcDPRrM7`8(!_gI_$)cyJWm9Ko`Iqidt6Tn4Su&iTIv3lJULmin)v)~1CZt1Ss!j5N7S;5u7K~8Iq>B^vUQUC;dl|@x$'
    'hW8YHe;dnwGfr&SZJwr5^lDv;6@LQ%fs<iDPbDML=?be(J=8_hbZgP${2I0*ua7@f{{Hwgdoe?bC(~jbr*~!s@Dg0CNCpw6aV%rj'
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
    'FSTNr4ncT9WYk@AbZ5Bz)X}54Z3k~Goy+BpnOkTP7<ZCR(kY{811Cdoqmp1}Q$`1P*hFjoV+;GbpA-VDPKq&MaT<T>0tEbmpe+o6'
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
    'afO1yA`lsFV}XlRxa<heW)x*2XBV-gTHSxL>4shG)H3Kj=_kvBsSLFs4BPd8l&O7`tV{<?C*u8ab(MCK_}!f)e_JIQ4pdLPuSSL1'
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
    '_9K5T$oPvPghb6WX0I*=D$FskM^vhTGhFS&D3XJKBeF}Y1)n<p?$e63Z*-+-#gRPNO{*7lD$PJd+fzAc6V|xyFa|F1@77Jv@~Thx'
    '9MM}i7q0%~?))cr-%SfHr!RF3Fh*%%f5}V4cs3jdGZ^JA!F2$^;N$pb?``7y?|q8C?9+B2q^?#Gbb#|b1U`}#zIlZEm7x}D_94uu'
    '4A}eG35u5M=W+PeIsN`0H-c_B${QZ50#FSNM3^M|Ek+X;j7j9rLx|f~JJvc4*L?ZEkN;P?U*p05IlO$`z+hdh`1ulUg-~FzV|<nK'
    'unxovfZW?|e_oKDR@Wq%zJ5BhGl&t7kK6J~7KC^r6txi)3WS6yreE=k7Vk~tAVj2m{VDnLXKSASy1}Ru+hd@e$xQ~$2hdH0W*lQg'
    'ds8fFY=JR9%?p2A@|5L&UKw;7)3;4c#hG)#72$J4+&D;DP{nAK!rz1-1?P0$x85uXzI<TI_3Kb6@@hj*)4t~kNW)F%NjAo}KMU%|'
    'Pbq0XS?|lMIf@(4v+RfHiozRRmoh;zG^{h-KN1Tj7h(hMY`<?k25B!_Lr0q!mBjGR4>H;uXW8?OF&zp>nP6Dg#z5HV-A{5ld^#B&'
    'Jb(UrSeTo`?M`#s9*-N*fD;@^Dqlsmu~f=1@9={Yl3?;MMNDNu30kpZ=~!!<6JfNynQ)A|!ylAY2Zu$V3~8?BRXK!$iCJp>Q~lI`'
    'Ecmnn$y>(QAugPdkF)SCVWv!ti-t=K%N$nWh83HUwq$9?im#8G%zUL`iGU9D?1So}Ehny5(b~5O9tv#9R8rmW-fD9SgKhNYKP0%m'
    '{^xM(+WaP~aQ`BMkouU33Rr2}o$eJ>?>eOB6u{nWe$}eRCLA_urZHUEbtFheE$P-!f|p^V5wn@_I!uzQ^DJGp?B)eFg^XX{3aL5;'
    'ccqG40jY+S0HC!EW?W3|$gf%SREuA}O{k3m_768-!y$aII4mkgNE+d>#20T>pEG-JS-hc7>*w+5pRZt!<!~C%yyN9c=g}~^bpv|C'
    '3niRU@inMjRE*(V89ImQ{ipoi%6n)cgbQ44L<Dh`<sNPb;}>aQ_@sp5h3zu;s^aQj{dFrav8$3hgqmXvX=S6CEmb1Aq4LK{t^7Hf'
    '#8_Xu@Q%5)?r7Ww#6bjGltT6qArMA7)l=~N=S-JdWA5E>tQq>6J|V!!URL|Y$CqJCu23U9J3;PLzZyxa2nPX2+XHul*IdxD@ILN$'
    't+{>2X&0bVSA$=}9xU9G6^Ai{Qb}P7oLTlRAi40a<@Q{0AXj`$6I@JNU)br2SH30s2YnMrz^G5uauw=!F8H#Qd7}1F$MX26#tBz{'
    'vrs)tj%)E1dz$))0mi<Y6rC}KQ;xkOC$e|9iVMaazJv`qa}ywkGGF|6Snxws8r81l9$nvx!HwYx#j5v1(;|~Msy7@iGJkJw6eI8m'
    'zj+wvcDq*mnLEH=;=DO8onL^4Z9E_l9}zzf7_bU1WhfDsz?8>bi=9RRZIGZyrTQ4w%=Edzq=06_@YS}M6EtOnxHxLfyI;dOuD|_t'
    '&s@JCP19Hemf8nr)+Me(!FmD8swfM**ItJ1{Uzl;hlr=2*5mU0W*)L(6_a<-+V<wOB^(nE(GT~(7zlHfg>j6d+g`ou_Baeqyao!9'
    '6HDWl0H$QNI6Qoj3951O&>*BTKkd(KEUl?OAD3lIMlZ<n!j&mV|DqkH&p!mUz0*n_$oay!f8M`3nc%;kgL3%zy1@Z8WK5(*?Bgw6'
    '@w=K;g<db>p9C$?2Y^R8?O%C2JS;>ba!oBC7&699mP{RIA+I7GF~-b(lid%?a>bg~`R5j24vNk`i>;UW)f|vwrU!yaVo`v33dirl'
    '94EVW(X(uPBRm-<x<uuzQVOGIaHlC+hGuEJQ6w_x?T~ERD-L#K3_Hh&^+u*i_s8Hsq*ckZ3P+qP*=RUnvXamhF7_`Dd(;_v8BW5k'
    '-#3)v2|*KC6yrVv0ZrkMi#roAp>zf|OU)yM_WPHAc>ESCKbxJpG0TqO&ydCFwjkme))g$YF>Dgu3utiK48R8&)c&>4x6w&jx4}jv'
    'FIaW(DcsuuTav~?HEj?CR}&HuEx<74*}r)F`Q7(~{jkNItpf{?N}<8{yn}>UvuEH;Swz9de~r8@uhahZ!=G}w7g*kc+ozSK`S~2;'
    '-v0FSNu2xnoGu*BV%5XGHk;F`JD-rd(42}$@1d;1VCie&4VSnbc%yauzkl0*Hk@~Ey@59SnxT0(7WhYFK#9I~9S?kEZXHS{m)M?5'
    '<m7_+PB8t8jl7IeKR1VX$Lr<6Wa0^J2g!Npdt=}g->YuV5f7CSo#xtc*inb2aN73$s4!s`W^)c&ErY^<c-D8u$hYvB?fI^EgKhd1'
    '?xM^XU5QtiT`MPI9Ggrm`~q1|r?9wvH<ZN;&SU_?<$%eTm)fri$u`d;fI$d`5L8<n6@<1asJy_$cPq@3o6x5*h#|w%p5Mi*RHsou'
    'g!d0YZ<kv}Z>)_8&yc4e<LjWjo1Z^FeHrhzepVAh(u4J3G!0jLQ9y#8Y1+8|fd5*|3>;GV?uQkEt4}9zJu%1qJRg>Ic;d@pqr)k2'
    ')n(#>M&lC>lM<RR24klh5Q5>Z5<D<;v3KFkWG=>a1drC~WD+|>5Ox9c<Owk|zK_ZgT+%gr7yL`jeEFiEV(fJ1r}fOraX+MvDMl|%'
    'A<JuH2$G{Z?Ou5k{xO6zhW5J2C2Fo#?iUyrlr;DPe69m|Qe95(ChF^2Z<aHkhqZaK;ZlmXrM5DlEx7bWNHV~*DbQh2M~jMLga6X|'
    'hxM;Zimh+m#fuNN4q?&~)*{?KRz@EYZm)5TYY7p?BnzL|ao?if708#rN|MejrkKOKIm-kIJ4`EK{lIV@WTC0#^EB*Ra|hG{UDACU'
    'W0X=I^fX3BDSS<EjtR1Sw6vS~g>(DY1p|Tp7SZl<0Z@bvE@NM1!Yh4w;1PzwgoM;+&vHrp5->)0{>T%Lcu(U^Z_s>ehlhz9EkYln'
    'dTl7D$Ln-wF}=lOTI%c8-KaZg3}Swh6YOU-01tUsC;y}op{CKu=+*JfbxYzXA2udrs2(wJRdR@y(tRVs#wc=lRq4hXB2|%cXVsO<'
    'zGXEVxJVO2r8%#lspGF;9%@(-9WuR#0EM$2!r!<vJZu6ZWZ&i#IiqFtGD1xW!&|~nR|Bq&d1xqT`M7(vO~Md>z@y7U*9(aT6E>6V'
    '5h+Yf75uLlc4KaEb=8VLo80qP$eq1-4C*mf5b9du^ku=_G+orFWOXf_o-s4|zD1v<pX2fJj7o*7p@Ch{%i;j9Z3Nuvpf;m~#XTb>'
    '8v5m`74J4tXJN=_q=a)du`k7)4pV=pMw-h)2b2ev?SDR`a%0(DY*oEfur_}b=@=fCgWC>~!B7pEMinEcnZ94B9Dlz2s=3%;p{X~Z'
    '0)Rx|MD(bE@8L8Gpb)Iu2vYvExo+K)qTzC)1kmH@mIt_QND?Ojq&xUiF3pX;ZynF0ct1n?w}sa<6o>PyN7^V>8C6YTc`9STFcd9{'
    '6nf+kOH+-hr0M(izUu9+l?S+BR#3u+n}u{bn#_Ug^K`{Xn!~61Cz7ZC^?&?7S@9f{'
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
