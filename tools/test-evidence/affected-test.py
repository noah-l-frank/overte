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
# 2de727b2b9e400d3b681fd8e70537e41c47723c9 / tree 93b11fd1e7151fcc0fad44fdd2787dd3ffc3db1c.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '28b9c9b81ec9f37bb7f4c59abe8d6a2fe70339a79539433d2e7145673cb76d8b'
_MAIN_PROJECTION_B85 = (
    (
    (
    (
    (
    (
    (
    (
    'c-qaK-F72MlAQ1L7=68*%E*lT+o#ac(LGN5vd~2m9008D+CBU3`YZvmS<@sU5~!85(yFJcTN8oI3=em6GxPua?H~8s<JTAe#XZIS'
    'ZX54*e>|oA-Er@p4ms`r@%v%-^xMDx=Wma@n11{B-%QgC*8cWyza73h{<du!!~gWAoq`Gcr^bvqr_RUF4^5a%Zn_+e;s3+&$Fu$m'
    '{KL-w_Fw<@wybBN@b&I__pl8=3afeF@!vJ1VIG_4QkaHu3_dl@*yL{TvB~3LT{C^Y+OrGa+<m(HW4Hg7A9jD--6wvnJ8pMRhtlF{'
    'i2Xdb*7kiIX7*rHNZG|Onr`MFIp2)@=+775r{~>ad))1R+=Z_xd@HTk2RpWz=Q^4x$2g~y=G@!d*f{e;=gD=gP2PUK;xQeLcZZkl'
    'G2O-VoStHO3foltrA<2o(+@tyv75(f@LiLqsk5&4(NEU+mKW}ansrNS#i93eoAsIS-{@NB`ZUgbL3Wyl=!U^qZ+Netul4#W54_xc'
    'dOF_y^Tj=E^ENDR^&dYTA3k4w_BjlB8r#mB+|RZh@@zVux*w;u876DpnEAx3R^RV_PvLl{-+s8fEQh6QUGJO?A*ZqT#`eZWGdeSe'
    '#te~np4&9nEc^G5>f+Lq@gbYJ>rxE1>!)@|ZA{h}H*%Ijh&HA$h7X>%-?JQ%Av|n(%3s3v%kSyw+xF@3<=*K%KmYiARsQRP^&zz0'
    'T08pIPH_mW8T%CbiQk_4WX7>+*R1-?FXx3{Uf1TaOV*`v>U<N%HcouW-t%Gk+>W^!rzWKk)~&nqmsia$k4@k+GMV4kHnVHmZtT1b'
    'bDC@zvkR`DI<scg{mawEHG{FkFvRR;Z>N!;=jLu`W?pxfd}?hZIHjCdt*I}06Ta?uk7;uVyXVWldg^V{@MN9oh9OME#@Y3q8=JnJ'
    'h+Tb%bDYe&XT9v;$vvh6fje#X$vtnM?k{d5a%ef!sUIv+GZ~vYqoD1AADY4R))G><s@8Ag`Ee6=PkDQJea>(irmi1`$++cO9J;pY'
    'iEUFKW81K~kv(>+*VnxqH-CQ5{^I(c@2s&l_Wj5u(KkGa-px&Dxgq%?JDx(r{p?n+&lkv5d2#I&ayPlYjYPBDjh;Yayy+Uptrc8r'
    'rr6n`src=RD1W#gU!KxYk#4i!y&TgfZr%OU?r_|O%h9HrgLe}_tq*;&y#9Gg$#Hcy{m}CXM&CM8mU;CyUgGn`h1+QyOfm#iZj>?3'
    'div~y%QVN9gOIuEY#PVvg-;*edG#eR(<gXLe;zLfpq|4%Cf9a-HxcT!seVqQ?<1#iPQf(9hoKy99~^n%ard|lcZ9v~+XFW$2k?t~'
    'iQD7meB<esy?7$~J~<m(=Tqu3(J)3k&(=<giDu~aGI%oM)w@|vr4Gk~dm)#+9Hqvg3$Z1Ev%C*73{Tvgr*_VnWT(l-q=saxxqdS*'
    'q?4B;Wem<tp&h2&^!#?$hj!#@;Fyr^^;7O$v|XFb)qD7s_D|_yv%IB?JDFS01Bv4h;^@0E+osJvwnJ~mdB{VW$C2;1%~$W_(LIrF'
    '#|=3?pYs04=Ii#LT;<}f8eLpNwv%sCAdHNu=Q86KC08&VJ8VYFQ@VavJI}xLy%5ZXpvoomo@i-(JC1z4u4`f!CX%N%62}Jp)9ZKf'
    'e6Bp)!*Z(kE*vihwkg`F9c?=eZJq|Adf#_rh?5&yKI_&tb4=~z=c~6wPL&_F_g|0Iv33}{Oh(l>+k38-#5p&U87Jb89#HHWYPLN3'
    '8@5zRw|D?OrDikEUDFNiWLjliWLZ3tnYY(W9mPu<uigS_M<m#7zjLrRZ;$A57QnYcJve9TH=aQ^jT3R-4+P)rsgkn^#GmH+$8tDw'
    't}cHpGoQw&rTyGZr1mD~neR66phn8caqPRfzu^=e-TppR-vXJ0w{anoedK{}Byq5f9eX~KQBR24&&*A_{w<xd)z_=Q?_QpwD+C%o'
    'lbH{P^qkkyfL*vD@_+gv*w*;LHqKBd*z}9`RB=6ZiQ=rE{V;d7OP~s&@tJba@Fh=?&sY&B<mSd5EqBzWDh!66{Jk|?m|Togo1BZu'
    'Pkh-_Ij-xvzNd!nZ+&m+>HBuSdwS$wJiWThWnC+rM<_w(z3;=o72(~G>^LMh`IcwKjUKz(_Edd~PR@?5qpBEzOeQdzXsK>Vz$h<0'
    'x$nS%XGiweZD+G33A{hu9)(QM`-u-Kj%{cN#GaSs=ON4!mqo{&=2LFj?rmGU>X!E-fEEcc-*}!!z_l@`PMqe}1ac9ZZRg?~e$m##'
    '?s36MN)K$vE_E}Byqyh!QtxvjX(oKL+aVgCxo4*?{+eAK()aXKsH!Ph=g{i~QbZB}8lKnG7_N`DOA}~lM<92%?WZadkRIB(6T}cx'
    'p2IviZd}(49R2_xYX)AZq0GH;EAO(R$8F6wJ_8;)0SsO0sJTV}SujQ89gqRL18GYpI-76X*ZS0m_vXkM!9jZ83FgWTID{Em%O^f`'
    'Q_Bu*ll`sxB0t)MeFED(Zr#J7fDTY{S=(~aPO~R%%bACzoWOXJUDE|m>J;aj_f(S-bX@*?IQ$Q2ku!!fPgV^K33Ag-K<q83WNh2p'
    'HgiSxMh@w-8O$(n!YG?vpUM8mK3kKV;mT>b2TdDp+t^|EvIo=(yRQk{I$X}?ST8mdMUE#Ulr6<>9)PN6l>j-+pt&XhG2OT&WtE$X'
    '5*CDsd=0R#rR6cZ?73%JP?y-X;P)mIo~C9p_E&5tyY0hE0qC9V6p~B5Yi#cV4HFs{y(4D{EsrU5-89ocF*knK$H(WqeMoQB+U4Uv'
    'a_JA9qdEf)B4Q4}GCUSfzS{_rrL)ua!;N3}asP5Sa+7>ZKlUYPlrv9$$@#WE8NTV6cNAuT(#9J;sx)OAr*un2uwpaHvYXC~V503j'
    'W!@eg4?14fH=MBGX->>w5p~!98Kge{lgqb7>_7wgEI>!cp8JA=z9EzCjqgch!D#y_OjBKkegCqAyR?7Y9u7+n@nSOO=b3(l8Xb8`'
    'K7wh`ETv5Jw3%$0LgOMar|u_z-RbS`cBO!?3z~Xja`Y>Mr7hbM+NjSbZt&Qc2pq>Tsax}uwp<RKbg)_uUPt>QDvJX6P6mJr*d%l3'
    'MANZ{SeHLNaru8w8y6q9mv0g}8zdjZKU$N+K=%VwBIe*|=J9_!04__xP+1V1SFHgPn}$oAvP=ci7*ZH0>@6oA6h!b*pj;yi)O}0u'
    'Pf~S`5jvAvPmxc3sH&9?P^3RSk!x_+n>P9x5WccreBbY>IZ7kV;MsODcA)(IXjR~+ne3TfZsN11mZmm~<BG*kg=yIB)8==s$ES3;'
    'hEQlFn9=93L!|l}Mo{LtQRP0<j2fs@UC5Of-TNIp?!Kp`8088oT!jW)a%|h&_^ES(aY<`PI(0XKi_KK+BaMgI)$d_lR0)A6-gF%6'
    'hSnENdg=s|JL4QDEpY)Qr~+a3_3KxL785hI<K$FpgQJWSCr*ePM||QS+KKQ^-rdzNe2Om>&zu^F_f9jn<@#z3r*I;d_8raDmKzs<'
    '80e%Mnzc*+Rl;7rLuh0-q&<$*RanT_lG#r@cmVx|*KNQ_NXYW_%b&Y_;rZqAbKu;W09Bz86b&teI)j^R043(0qn|L1G+O2>Hd42K'
    'mwTF=hOCcfC&?FCYUVt2Eq^dM(1oG(v048KkgzXY4vvD`U&eyG=O%5{W#v{0guK3IPa(BEA7LUmPGlM}`m484_asK1KkGF#y&YtO'
    '$X{U_@bDe=apGntx$4O?uGq$p<Ja9&9iXX?pCSQJhx0)F1Vt$IBTW<wutJZC>X_$cuXq^ybPuLOp%OQL?A`NoDa#7Jq5RE!6odj{'
    'U|f#Acl3m*$djQqATqcsJ`8}R%T3r}piUcDjC3wqwHAQ}Gu^h<D@2N+*3%{l^-I?$1oP--*NI$`X-1^ja3fjJElY9`dry~96qvl?'
    'KDsI^puYf9jSdmXCHE4nIJ%v|2?})V1nyi2LswA^oqqY<_UZZM_=UIraAsBAk>TI{kx0CO)u@Or?uK5Ss#M<k^8JZ+M5ze0CO`zZ'
    'JM&oDz9LKdX*aBXm!gPI?>DB>W8;o`bY<YkQ6-Y5QG>K_kQ`q{;Pg_KjF#GiK5^1lTLF%Kwy_dvCvyUnKk-;vVGUfNF-}nJnvvFL'
    '4^xW(HdRn&mdpB;+<19OQZ>F!Wv4WIi3sX|dup*UO_1I=qVPmUmn)Zig~k*sH@pY8f86aiFZ_Fjtfg-`2;7l$T)@M^5LEsFwa(LM'
    'Ook?AC`Jk6wfi_#o_A-i#FxW9{J$oTlsEQ&jZX6UR!*D}6<ABAS->+%Z>K5JeK7{^sU_ud19%2NIp>#W<DmSG(+%5s1rU~PUCw%~'
    'A6uw|ArMmushnSG4hw%GlMb^FlFtm`=*rD3B+k><4Vly(sz0ANa9&9RQwtQ;CT`;Z%Y?T^?d@XEACV;v74)m(zWmGfA)fG`TELaa'
    'HbDex-3$YW9#s<w0`NYCfPj(FZt29&G`DZ=jM=?=Yy}<)$4<|SkPzT&g48wY2GeAKku$VnJeV}w+c&nQ4YYrKsb|vpWn_UqRSSD='
    'qFZj@<wT=yM@PfBg--{+5W=~c=3lV0C+@5VnjUUXtMBqxmWa?EESj!0sUFxl(UUemkdlWQL(NOuc<OzB`>sw&4>96hhxYQN>K!Dn'
    '5pa=r*AS>82QtolYJ739Z9xS<{U?9>*4D(XNS?vB&xa3xp7`BPH2onsDU{McR@Z}i&HaL7c}~~2k4q){;-9~|LxCL)X>uUUv%Nqa'
    'D>Q)&$pIKc0HDO>!lC^T{4e;%PFG<Sd_B_VBuaqogcbmCoEFG5Cm))j4I-(vJh&#^zNy3Zeql#!k%Cb9RvgM6V3Es^q7OjZ0^&~D'
    'PZNiM)>R<U<$-~(rvHY$EtyV5+kHyW%xbSeex3RDsD`PC5?E+Yi3l4hMbPJ8a0p(70GGFu=^w)a1(GGT0UDZsg@$&ZE|_~GK$?Cj'
    'H^P<MdELX8byp?*eio(o*F`V5YT{;sqYP03>Xrw!0JSya)o<}_SIb3NVBHA1f}G8L=!jF6qe$Wnjs>pk+fG6Sh|M=YpL2-64C!=j'
    'OR>b2!-WhL0)!Pl3o#xDfv66xd<N~b{jGbcIA&-=tVn%OGLVLl9uUJjPd<#g0dzAsvQhfk<IP(+*AG7*wn7AGR4(O_&WZCt>|NK4'
    '5z>F=-|Bc_>ZkyK-@3IGTLKgW@F6O~*Rmv3UZhp>KZB-;zE1L^;PK`{H5s>i35d=+OKo~>MJ#}<3&%1Rj2w+yH_#2Gw4K7Nd}?k$'
    'AchW19Gsl8#*N*YJ(P-Asx*p_cIrpU0}28Zd7Ze-w3Q-K3<}B-Em{5Vu52{X?`=>s*i0`Tx=@GcWTu9PY(dHff!ff8F!M(rC)b~Q'
    '$|ckywKVu4aXA&m^!`B;`C*8b0;Ctu*WV1h=#LnjaTln?$uix;mkm_?cM`3Q{#l`4$Fh9D=-*o1XUT(K^(adCy6n(-F~z&lrOV5T'
    'a(Ee&nPY}_PG4Y3BtobvVbD@>dudnrW;y~My{zu?GN*)R`Ok%3@7(!bFpJOqIJ8g((L#+BZ5>@IMgN3oCVudv1b?L`q2gcM{<uXs'
    'MWVbgU5*6~IoWxHc?TNIRe~I+F@auDue4aS$~Mz3qFr`z$>mESG3W1#bT*?}fQCMV-vCFdfzKKnAh#h=xKE)+%}5OR=#Kr{f+u3g'
    '<?qA^+3ULomKuQXNSkqh03~JLOf}G->f%uNeFwjL+<fQOj^&gF7;~nk?m60kBVhbczrboT0!iRqPi7c>oIh$_pR$#hzHjvwsqdbT'
    'TD>OGYa~v9Mk2tH1D~|mgsO`&pG(rie{Uj9Pghzry62;`GfRZ|+loBBzn&{kt>HDojhaAly`#%S{~9cTFglJVP9UeS+v`?5ys4_6'
    'DGJ{H_;O%t)lm)2#HUM71JMrT6(DrO4n`Qj4ULt~2Y2NTo}afbkDHo}1hKX0CZ%y{<8}$TaU_;2Ia92M77T^K^(!}0^$_6847Arg'
    '@z#ncIsyi?kR!-HTs!zMIn)kF4cD$6b`RVyyHg5(rahLw{mu%x_o&$r3{#*{`_sGtUKf)OK?*(Qi7Y>^-OU0RZ|)Nf_fpFdq8Ain'
    '&H~+h!kSe+2BX1F3CXe@L6X7XsLHChuzUwq?*d9egl?7zXrh|+7P3`FqtmMW4`#%B0Mlx#-^KqQ?|{z5V_`{1wi9UujKl_cEx$7='
    '0FH!O+UZoqBkTfNuU+kuF&)0qz1r-;%ft51s%H<Zs-@{$0i6t_JkWS3#p#^P7J4~cCJ0PqCs%Ia{`qC|6@KJHIuu|{dWw<a5#2xS'
    '5}N(Sb|fZ1I-PoJEgU=EMrwY+J|IPNy+d^`@Qi5D5EUSf!66-TR@*PCWD*y_A}2>(({<+8Y-j<PDw@#(!+YsAI`sP?()mR#(W62}'
    's*v;wlXzF%aOJMJxc4w44%=`1?d#uNOuVRqpr*{09B3vr0c0BK$fC%M6Wy*TSu`z#_R9U75D53<fq<qODQ!QyVt<BI8;HMTM@=63'
    'UfuZ~3Q5Ao!zzEre1Xb4_17M&)%(H9g1`~bj<nNEEdh%Ll?2Z$QiBsx1Ic&yp{vNp`+3}jZ&ioeP3qxLRF9oJAJEs(QZW+pOB0pF'
    'S|Ib!p?2YOwdl7`vBbWlQk61{U=|FzbiPqYpb(bgAneQ#ToIv$q53>OZ^O=h$=g4VLj4!;^Kx91W`~51Jc8b%%3{$4NGFAQfE-hU'
    'kadjHy7m8}OjTbil<7`%Q<_Jx#?+^#UbY=nBDh5KMn|#x0Ls>FWG}0gef=hoF;NQ1Mu&nHh|YPyRhiu&i9sY|CIqMeFSVQCzg0wy'
    '6?eQ<N)@F-1_YZu6e2EF(oeomWEDBVB?yj^^vWHa@}27EAw>sOu3#=iz!dTH!6A;26XWxP7_PIBS|(e4*MHyfx0}V%NY!c~I+0d2'
    'bniMMfER_WQOeJvgeB;tC~(9oEU)b=7o0i#e00#Yu)^U$%wTK4p}j?x<z+BLub$dCmli}Y^W#5KmGp|9J1Bz=Jl7R3I?vKLwO|ed'
    'H$0i10llXGP+D@4qP^DT1)cCL1;tE{*d+S>wn;Fi@C1;V(?kQ8zXTXcrGQhXlcw_o?qmSm;a0TjSW|r?0wQY(;P3rOyB%!pV#_bx'
    'o!i0skDJrKL1yq!(RLMR%BLHt*s;MFA->1}h;p5W4>yUAt%dLrn`^eSeNy8W&V_%$cWb|Se(|qdn9F-2<a7A~;(|^9-(d>WMLKsA'
    'W=OQsN5Oa=ZvIVslDZAORC?fADlykEEs+*s0A2vP1C|QVx$y}?eGg32^<uBNk1UZ^?B`wkhV&q(<M#3LHN_nWgB|?{WiRSr-Bw5d'
    'IURI-IY82wk^e?_&8{AJI&^zeDKzsI8a3&0<eI2?A`i;I5~2v96(_+RfCYGnxn>WKOFNL3L}?Fra|wL`;hE)iCOnS|n{NiwEcQbz'
    'hW6{@HG7b~4|~|hif56ynK~(+a6RKo0d9vK1Lp)w1f&dcK+XUl@sWE~c^|Y!RgFKt(1Wk~IH<X2Dq)lc9Bn9uFdIqvarR(Gw2P*!'
    'TWgrF`ZyM_W^=l?PAB{F`)RnF2kJqxSJ+!#AQ@0DoFym$FaU$TnsnXi0h{0L0RYas`RC(9fmBB_gS-R+BKHY~K-4?37o$ppv_#0~'
    'Hl=8fzhEo+v&)zP7AwO@zd9|PGW>{mEW{Xyu`tKSGz;gR;&A<5#L7H4K9&M{BNP+#+enjwC<JVaHwAo4K0`(`;cEiDB&BOMa&V8&'
    'XwnYi2cKH|CE`AR1D;5Qg~!1hl5ffOGZhalG~YuCgi*~$ldg*WM=8@|MFn70a{wES^u$L#4f-qeAsj#gOkE4g0YVQ3=&#wt>GKE='
    '6k?b60Dnv}kqCCgXMzAu0{#)?7s!WZIp8|HyRrV*gs<-SDx-17;#m<-7$jR9WxC6x+Tbbx-P|mYQ8~Xd3B>NEKAgRoJf5wifN;MS'
    '5CRAZ09=WF&j{a2Z3EhsuosZDVAI6o5Tr8I2eA_g_H?`Kyws93Q$<vB&xIrj>L;{q(ob6MeVFLf;CVr6qy{Q6m72Wkef?Qg3=coT'
    'LptYeA#g&Jza76WZU7IdT$f3Q3?*S`2whxu^b-L=Aq(jCfy6;C5M;o(U$mzRV=qV}_~;?Rm$M;Z7U_Qg_OklZnF<=f2ZrJFOEwg@'
    'xb7VbjQ17^d!Uy_qu0ykYY@>Y;OCiO5AkWiy2>i!e#wsZ>7Os9m=Bp*pAHcYKQBxkl~m#g#DTJE-%dzw5ysf@)(t)E?zc}>Sj#}0'
    'j4Lqdg2w8SFB`PllKqP<i#;Vbq!s7o)*XR<9Hh~B3aRR20^JaTyYvz1mh#4CGf=3|L-dg(LIP%PrJJ7=4aYatbZJk#AKnf%2`wiq'
    'SP4g1vpNwk8)bO#dow9Tins3RkdE9`_h7qE?)mU_SJ)MzUCe$#C5euhya2lEEk<%pD~3fBK^%(qFWc42^TW<vhMKcbcnWx|L}Byd'
    '141bRF(*TOrV}ls9zv5H+FSQ@+<i+=XWH!LWD5*etk^)k;(D@igoi{U=s3uq<_^JotL^!#Hx%PuX#74U{Tok3jv&_-Wh3erC@-LS'
    '@J=V$*<ls}r*X0^S1h!ZYq!HcP@`h=^>}=)3QUAV`lju|tH7&)U|?Z=LP+3#fn$ja)qr=a8E)OsA?&x$HCI1fEswP`-Xx)?zC@!+'
    '@&^cuS19E-?jTZ;QgYs~p)$>s9*L0y0TpFz$&9IFsjj_DiBa+;E*C^py}$av$K9hNPA}KTUtZsr<F(;Cbtq$C;VLIuFmi;IaBrZ$'
    'k}zR2A!DZ-xAd@;)V2bxqfD7>Le=aEe<)-?u_DMYMru<_syIo_LqxK_Vn0+hX<IS^l7k(7=d?_4BB66abC`yO7d?XdoL5Lgkk)B)'
    '<Ax+>!e6c`LL=^jDFMN!;Y@?sQf>in!uNqFFZZ-aRt;9sUAv_d<LK>-y;GcBes#TE$}D|AOb8rlG@8&+eS3-=yf-{DFRIh#S8Ypw'
    'h00iA$x2GXYm<`|9!@ZmVJ(IcBoJS)iMI<fiITgUe$l>i+1^G@(Fw$n=qN3bg{v&Hdopi`IK)cONQ~&ijT_RfT4804F^j@chV=>>'
    '$_G8sj+oVpqfCXK11U-EA#>wyPAtbghwcaivZ$<p<qF}DRKucVMJIst%81uZwTQ!<tdnrKfN6T;uFm(z%TwjUqGJm#OMc7U?kHiI'
    '8{j5*BEorq;9=+kCty>0?Y8cB$DKIkB;4n{6|!xJ>=L}D7WK6i%Mn5)1PV_9Kx=V?C<kNo>gX+GL3~`nmY2_%$9sc}pU_OBRn$rv'
    't6XjzHHs#{WZIiFzVo#kdDz9p&gx_ybs6!oaw12o2Zdx_Gyq&0(CVm(XnSk!0+lt9`-Z)!7&^bCbNH^hN`M`VFl~xgsG7|2=!D3%'
    'G$MFa@+TW9lBiB@+t?zaj>}04yJ9Os2^#4kgbDm?XDGly#BvyShzcp<)Cyg|p=<YahDH8*Oyw;NW~PE=K7=H3pd=VBWKnnN%kn7`'
    'BlS_6>kAN8#cuEX{wl!{OA0H~5y5seCvdjMsd*ID7WqBQG^oBJn_r!lJnhst5}JqpohMde{2J~vc>h6M#k2?&#3@KJEDXRkMsg;+'
    'aIUUDc1sR<Du>|Az7(P&iW-a<Ad(sxlM$uij|+iN<1uMULjZhCSKqKei~6jo`3c!|NDYvclU1_x-$Vl3acKJM4^Zp{JfJKe*_iSz'
    'J33oKY>r>$x_5aym;pEHQ?M+_qFmBu)~D+S(^Ne#*fA&?uTG85B^h-P(GkL7nRFm+E@vI~J($%@!i|D~PY1boOZT89n;dCsTz!u%'
    'H)*W9J6djb+5(uh;h0bUO0Eb<O-r6`Hr85nzA!sM_HzARmOCD4N9}1xlxWHEc{fyrHh_KLKaS{w${MXF9Srgh=6wt|?&$ktg~5ls'
    'LqJ^^{M4ovoO&XMhN(SxY^61BC6ZXXaCIK^eNy83U1(Y<z3&>ahh{<6oyK0U^dx&o?krW;_)AkJ&F+Ssq(8-%SHrs6c9g~EahAaY'
    'vzl<w>z3+}p*!5H{Hq8R0%mu&Y-+naomBgnW`le?$Q2o44b&ES;K8`UBF@Sn1`I@oEZuzDj&>FG7~_7Fm5I5_B$5b!)=)@ys0d_K'
    '1m9c{al9V#)J~4V7<T&t<<Kfw@8s$*Lf*zZ6WJs2IVJMeR+V9v1n`D^oXLQpq&I|S2eTNTGBA8BgRt-oG=H#<>!M6iIPxfIeY#~U'
    'Z}$`tu#o2jDrSr+K{!Bpk+BR7raAal5(xQ9sOq`RIpV)!Gv)3e0GQN5=+!yZqYxO{m8e#Me>5?Si7I%4B!9zZBrhyzrwC<|zsOw='
    'Tfe@O*<R2jI8tTUF(hCP4+0-<*~L+Aog0z3idYoouv(%tt4XIwNZAivW5OMXorsb^W>h@4#NM|YBEbnk<6kg)!e0ZcJ;rLmMW1OH'
    '@=SPZG*zr6(;-0fNBQbB>#y8%votmfLVjGZ(IW!ALoNe5<wa@k6KxAhPQGM7AGy<Cb4l`Gq?rIqIdN<Y;x}4vxDQ$lMfCDwgJ}%@'
    '#1+X|hNlDKOommTTRlHu#q(-#u>9v@Z<|cg$($mRHvwJJ8tmnb=BcP=61zqXF)WPhDG%^TPZHRl`xCDqO0_`?9B&#)Fz-N9><H@;'
    'I1?5VbT}+p(CD@_8u}G*#V7k(N`&fNA%hQkSy%((9*LBg&MsCSSi`n5vZLWV^8iPC^{&p%liK}|3IkDkWD9f#bk1qM!AyXokFb(U'
    'ie?6bzKpqgKkr$TwVNX8)3{MpPf(QU8pvZ%(sUhqx?!O9*x9T|w?5pI{#pH=mew~M0OZ}!$4N{94#B({g+?UmMCwM=^5)t-g}pm`'
    '#TN2ucXVa_H?R`inOPbNEIYtYA(6}eHNp;~UVwm0!Pl<f$NkH0&X`60a3J2829+}Zjp=_117x8sB5}M|@G=L{v=m!c$AF(<r^-#q'
    'Rw%-rKu`zoUz5_X#BZ3T1g#q@Q8HyD$u7p*Hl=E~+O7|ul`fx514)i$49=K7EPWb^<WV@dbVJ>6?T+4%l<Ey(?ArQ(@U&05S2f0|'
    'VL%$WAQD8Fg#2@|<g4GC9*#TE?OqWdsdrnlLu%n(eg-29b*@yXupP#VP7`^#SLSPXbS^*1r(W(gET90zgEGNoXZDrcOR%7UoSZd^'
    'w^QS5pxQ!Wg-~+1c{`_e&aVD?qxUA)O+F@Yr>tv^S(DOEQtbd0g4r=z*Z6ef&X(Rl?VdDiu$RJ%-W);)GBR2#P!_00tpIT{$!Yv>'
    'T+gaK9lpLCl`z)dCqSnJBqO_4s9hZ{OEi19c_9v=f}+?!^Fi@iy|42|mQVZe8ZpDmVkCWpw?GQFy_}qIdnI5N>L3Q0u{N%u&`l8D'
    '(su@Yv02`6^L)#WcK&ygCaP4zCfwquSTMqnp%OY*^k|s#!+n$A7@-_IEJ_25_?Ww8O~UlSo__kHVrt1mQQp)f6MLMDFvtLD!D$J;'
    'Bt|uh+b>TM3Tyq261LyzPOW%y$$!l+FQZXZKu{<fKn3Y|$Vak50?60|`0aK5Vcqee<;rK9IrqEIPv-o0=X(C~R-~WH+-1z8V(OeI'
    'q>KQyn6i+7z`&vZ47GLz-T9NP6jOgL2oM&S)zbM;CkL-4D#U!Tz+3sO!PvL;=j!M@5apR*y!>a8dk+O>tHwv*waC*L<ctRm4@4}B'
    '5TG&RlxMgJFiq)}U6h^#5rsJfa+~ARL|m6NF0Iv|5)2|Sdxe^aPfk;xMxQ>-r>zb!dOFaz2lrzkT^BTF;t^{AH->V(D7{q71Gp39'
    '1WIUt_nz8)1sUqJ52So<f3~_isYpuoF>)^mn2I6*8d;7oVA>F%G;h6w3XZM%IOlcSz?yrrcgg}c_xfw8k1o?&6g5$)GG<K(B_OWl'
    'MtChl1L)5%rkd<$TE7ea`(we1P2M7-<^sUk1-O72;ssO8x@zFhBKxJ&;D%w{;-^=j&!Fl(z^VXe#DosgBGx8&lhTfY1rCo92X$$4'
    '8A51R=;O{ZE9qy>HC<WD11T1vF=p7XUp><@VS3XR4<s(sx%?^YcL;>NU$==f?D_g36ddR%w3Cou89g&PB#V|u!Huts=vIKza0kq^'
    '@_VH3gws=<G|*@|N~9GB<qpp*>R1TWotnIO&+v{$)aVQhOY3$3p~Ni{C+qnEh>alw5}G-YGE}7Z&fShkg*d4J6Bzq{XgYUs8;c~R'
    'ECumK`U6}n5b6xNCLkbFQxm+wKsrWz;C&f$zw$MlL-e~xP-UTpmqjCO=%mTI3XhCvTZCm`9#A&LkA{onSH2N?TAom;6Ixgv4LDSO'
    'tiM!Y0n!0<F!PHJZ4jk~+Z59a+`85+|FR|1J01%kBU(0o9iH*JFM+}67a8=RI9EVn5vex_u<PRLwGV%6OWkQr$Q22cvOvmM>><S1'
    ')l?=bJ<LXczKyid)oaV0{zPkfly!;b79?NeIb|_fYGJ+#T_=G7;I?#UoH&mFLs)Jb%~0su8+TIF1~Ewu6M(6Ofh!MkoOCr27RnG~'
    'qZaQilw{fZ_1n<uXRcQzwSpl(GYToxjhgTbWP|e^_l1lSWC7L*Uj}(v@p2>yx)YE4$4{vQK6#1gwLr{8J{*33oR3MH(*KgtL`@Qd'
    's!Jf{)WCB>sXN%~clG;jyXYzwjmIWGxch=Fvs%xz$i*ItQVPf|Nf*6AB~0!mI~aywwb$?Hqzi@ZL797Bnv#R1Ue;h`T>c1IAWL|P'
    'Whr1p`lhR<nGB45pReBzti>G);`7^M_Cnr6Z74uFboAts*LBjF;3GzNkIRlZY?H=iNX6RYO;ReDk^uH)RFk89^=DyB6y6n`0%(Uk'
    'XvAZMHv*Z1Zw7h}Xi}pYt8EDuO@C4+F1`3F3qmQgg)=T4XDko#m?pqBqg%3VmL<S~estBVax4nj1g9|iU^D?KO2OF40^f)i#a+rN'
    'rDVppzf`K9TTK6A)P-B;x00bv7ByC>1kQ(`1W++sd?g}7G!YiS&R~W$v?o)!{t0a^7zAp%Dvd2bxEWwX?)KC(ctb^XDtPQjtWuLJ'
    'S3D~OUe&ZUy*8#HkP&c6p)<iO5Up7^D0@VArmjtBmwr<*mww&BZjWpO)UP;oY}8-@3Tn+u*6dBxlW^brMW}#_5aXyAfm_Vj-j@C2'
    'lrHW_lS+2wc+k<&Wb_1+0_eQrMCZk}7juBlVj^K<<SoqC%B68+;3WO^=*86BU4H2}A50=bY20^^6rz&}9!e3gPM9X3Qxw&4-3AsR'
    'Phr><R42F*__R0;1QC#G<vJJTQD|TXFciIQY9IMBak)T5MaM`vromRgfCMRgH#KyOJ_=jt5rr`IwJ2)X?u3{sQ2+THHpiEzlDC>v'
    'H{4mEwGhjZaU~7uL?g|1ur1e!DbzusD0|hq3$muCTOKDzhTks|2`MA8MpBTEf>s4d)u9Vveyiz4P0gx5o&utSNa(7xrxBkH0$_k0'
    'MMXAgqBiT%y3%2$EE=)hZb^<S7C-x`p6m%WW%F@vAZ`TuJWdm<TOngmd^tjN@JxmVNGnD{jhdwab@PvPznoQip{ETKkGMR5r!q+%'
    'zUR#CLjAeC{=pXQMSf3D->^6T0;>ibhHInXlgG>qMp$SL6!fE{L9{^`K0X8xTp}|xImksx)9a$AIpG=^>BULQ+xtS<-)pK4a3Iuj'
    'Fdsx7<N%}}O0^X_kuzYq5h_=IwJ(32F-<CTp9)VM@BPKq5w+{`h|vXuhT)st%iR%_j`)dMaIW0KLgd_DG`0nh#n&E!J)~nNLKl$?'
    'bp}-h{JX@L*Qhut$`4;xJhwWlUN+8*G<p!JX*4t#AJ01p)_@v=?GToGSet(6{`~pME8n<5`#{DCz=g0NFJn<*^>S0VUYW{};RWK{'
    'GOgJ{#WP1)fvW)@a$0gst_*Ze6aZqcVo_z8;T`1nS6KFuabm98JdH|`SIf0%@h9Lv;AGgMry?Vw(<Q4;dZ?MEX=%}2e37ll%kziI'
    '-}gUrCT5W0k!fKaNAHXoz*$@@C4&&A;aF<cbg^PSt$0{0q7PMdDaM*Kqgvr*G#VI-VBqnLyl1#Hkc${8t)A@YYZrc&l9v$;1*J1h'
    '12F|=^)&{$4ndM66W~MEL=D762z{I>vMk<~T{_`K!8iUjp!W0(ATJRuQK$*6BN?HB8J(aB<lm{t34dF4A-h!h#b6HyM}JJxFrkRa'
    'qnwywuR@T--hnm(HmrDu^_45Dtk{;h)r0&I_@fz4A(WMtOi$?$CcpB<<Ot*XYs_4`=)$9U72BY0lN_k{%*no})yV9y0E2VM91hrX'
    'D7H~^QdEz)Hc&&FB9ZQO6KDDiwPQ(PYX$sqOM<;3U_q=&=bZNapk6+Mj`i~?Ci`{kE_f`(@^eAmJJFJX<Av?wq}VNMAU-h6Vn>Og'
    '<Pt-I7Ax0&RTYwwU0#-pkdZ^0TuRT9UoYN?v?@p(8OMh%!ypWcQ{}Sx;YYzSi@Aqj+F<MiWY9fwoB>N^+W#cI9u+F$T(E-5<+gFL'
    'U~=Cs2FeVeP8(lCvm4<N^jId9s1v|0Put0EmK3n|b2>F#p3)2D;^mAUJRLL)7?bud6*GQ+@=Hd&&6sSsGn5ph*t4r$`1hB`%imBh'
    'TSLvhMx}0~MZj+oLGPfvRtAiCk!gO*P`Tb|2-)WF2m*2O0n^2Cl733>*kR~2Fb{Z^xQUe50L3Y8kOJh|bzkYX<yUJU*$D{1$dX{m'
    'M}#s4tc41O2r1e+R_)BV2&-4Fj8q(1Iw!CW5<l9KV#uhpqy5cDBbc_xxluLdq969#`n%n?LLYN!)^fpPML$b_;}K2ctAR}|%rJ3&'
    '8SP<fqlD(I7Zgz(8aX5*$mZfhtcK4XHvn)rk%APK>Kxv+tzGZs;kaGqlwK|i8NDPATG8?(;00Ej)xy{OO~81Jn`zgy)!)<W;Lq$>'
    'zE1fGpiO8>@`V<ptWi)f37DmV%O2ibU=UQzz&@2bc;}E@wLIgDNN@1sf$)o)s{Ck$-~r}w`z4_;^u(CNP`Uis7a3>uhvU}*8X&O;'
    'p0qeBqLZO3iB%HyDe;*;9IpF4M0TVql?xvN@KOO(0<-6?jgT;dyioDHw1OQd4`5(Xp(<>S-I@h?#>ImR??4?c*ozqIb9QL8F}%si'
    '+n=z7qz;^o>u|1KS4=9fyb6FC*idR+%3+}BQ3!;bhKXP}R3L*wjm^@2sEyKZ?nUp6s4o9>)DU49HOqse%$JN%A9Nh(ly96*9cK(V'
    '!PefvC(IU*{0BV8Z-oq=V2EFtxLH6CnpZ_m$-MGRkYPLGP2&Ghn@gYjF-v}x3bI!#LqT$nL5_bktf;+Z=eiIy5fKtaDHv02$#QCP'
    'U;eE;Q|v)Au0u>jqUID%%@|Hn03NRL4FI5ih^toIz?r#tAA-Q*tB8ZSrt>ngg3E&CVam3u{4vuTXxt$$Tes>d<Jlf|6?$HV1fl-s'
    'C$^GKjbikuFECR<ahWJH;c9kW_3y^I?6m&n%m?>7N<du7kbZKYmQ%F|IMDaexaAXPdS<8%BQMVjl=$*2LQA0|05O}#iaoKM_(*bk'
    'PBygy{SWm>KvJ_}OYKc@^3bd+891fP_3EIJE!ky+42{u76rDwGMID3haI&0h%axO1q>M!OuEJfL=}2M`^BrrJz(N$~ZXPt7L?R5c'
    '&@y8wGe8yi^ymKchQDn1E7s<l0%>LzcaL^6dc|P`ZNSVG8?R9#SyV1j!=N5CYZiW;RCOLXa`{v1Wz~%@9XA#HbAB#JfV>W@23c5*'
    '2PclV?W*<9PW^S(^)kug$xD0(lZ+1M$c!FQUyY`Vl9vVa*{0~$_tOr}h{S`u%=cKofEE-yI`O@k5SP&q!TJuKG(;+W5=NtYU<!k{'
    '`Ju>7_-PMS3-g$1?|Xr5Xlv*>LDk}5tHnx>2*)7V9CyL4UReKjff|Cb26!eJ3oJ%TWK2kbbZJi^jlcp(1ViTHl<ttz{FtgwP1ZR~'
    '`^^BQ93{Rugha?tsdv&W&+P&Bv#9HZ6`!}y2vJIj7^Rai7q6+2Rs#x_@}J=t<Ru=eqT0x1o1>4$R=&TW#2Z1CK-1K^t`j>W%H)xb'
    'In^*3HUK8jbg>B_6nN!iLZD#rvSB)b7Q(`i8BoxX)m#aYmZ5(6;-NWtH!NpmAqJfKO$A*Ks3cb0)QV)C{CdXGGy8!U2KSK=4M<O<'
    'G)2GR11;)D_coC6?)7KC+5S}zO+?%6WRalJURGmmK|yemX_*MA5d?ii&f?2#*qRO13{^zIj6*8|I;wfpM5Bf_Q1_7*gD2xpqVWXq'
    'W!jszQ}>a0hD9-x88I3h5;gZh+|ceB$x=Etr8}l8>Z~vCWEubX?6!q@geEd+j7Gl-(N>Xw+5irBVrD1vaYRLf`&IOfId27gUA1qG'
    'Z!UuenR|c>G#<4KdE_!d(9{TF@X}U6TP6<mF4Qf2ROO4<o}m<a3dPcdwy&2@u#@PYmh>diKN3AAv+!xok~YM#dhJDmd%D`we!q;O'
    'pjlY5FvSKN!jOkhgT0E#9a2qWu0|Ei0|$5}=|T;=ViPMVOfw)e_5+$XNpU8$8*8pcl}j%O8onE*o#lB8?|1O~i!!U4pWh~irdlaj'
    '<$MM60e&Cfy^#MXJ)}D3OcPkM_=>NOCh#m)(ZT^$3DZah%@LH>9#|>eLIJqbiq+SBg2+$_LKF^&i7<`q@Mi>t;-OH`Xxw!GRAf|8'
    '>6V9wo;U9X#@7!ff|U<k+eruxt&BIW2|e_j8Z_#&gd7kBfC0nW4V+WVs#&Oj5zIXf(!K>KAtd@tE1Q%V!2Ox&Ls7Z6#lcvgZJ~Z1'
    '6$fCHO$|jf4G<CpIBlT2WM5uW6znpF#H`&${Vdij)jjcs{};8QOou>tfyhvIMRjLz`{~uAxo!uqES<~c4l}o)MZmZt=|nokC|coU'
    '(A!W+U}w{*1MG@u&EK|A*Zo8xfYnLs6D&@~pK<{L`~pF<FbFiQNfDGyQA+-=tN%=KTntbOsW+&J9D0~E3J?rYgccdOzZyu=@qpiP'
    'C)#k+HY%8waG}f`sJ6+4X}0tBp)DcS#v9ORhz1jifomso(>|(4voc<V>T4Eug#`i*Ppu5nXQj|I@vsS_F3#PwdNZ2Px~UuarON@I'
    'HfAQH-I{>LiQ2?UtTt)gTB;*?a&c#`-UGy*r*vNyUxL^2{H11VWjw?15~it<$3uq2AOfv=HvtS4Ne~}y;2<x%(tSY}UMUi)OBx}w'
    '{E$U&NivDWx{}E*xc-ezTpJ=@r)ySC5oDQZ5lJ*M>rD&&WSQ9n;)b4Okoq&M{wiO$P(7^{CR>JVZ>6Q7ZXEmN8mI1&CA7xq()ZQ8'
    'oh$e8HW;?b;T$e7qmXi|G1{%%c)Zd{atcU5beZA2X$WZR)^6t1(<i+MaFRBfR<$p52uD&EiW!h^fM&2ydV@g{fJWn-or6M4Vs-64'
    'G~D57$*{PnisMJ=wU3%@7)>LiGwRUAnsykJ;^uMbzK3Fe_>;YyGHiDARH49wla;AzC@kcF&#R&Gf^&f)5#l2>489~Vfze#Il^O;)'
    '4u(NP5b?Xm3y*7#Dm2Kz9O?`6dZVUm11qi#T_E&0dzCsN5Vzot(*=P=O+rsSr%*}jg^P~vIaDKRuRg4e8b6B`HdVlnM>r2d4ZIMR'
    'F@hDkBY0dR|Lb*Lp_UWCLB0BwTd6b5;&xz440==;sq|=2j?c<%W&4YIpR*H(zFV7X=ZEe6SH6Xp^M(2dGqfOR0Ds{t?A2Cf^Z^(m'
    '$~OZtG>VbU#0VN1A`Gw1vhD@;J;@4H$?qobIj-BHnu8!or<q1Gu=<Fp7+4HZtR)R3inXdoB7a@G6{0xA2KV&x%xALHg1cQV%yFZS'
    'KsSjr3-S@<QOMdH4BV+;do++s=#zFKu6-!XsD1kAD*3681=X*Y^(v?&j~;FVJuOV-@H_|SrcEq<dRs(!|8?ni&5h-StTBUbG)+zt'
    'evLH2h?PzrN+0OEJraI;YQ%LsHvQTo3xRwca~xJD2~T4vd^9wqgRrOZY25kf7GX6JHbjT%uir<JG{$@m{)aK|m^gt#w<5h}`M5B_'
    'j9NsTNN8iL?-6Zbm13fk&ojt72G2%=4Dh7o>4*}Fa@QxoT^MClM_24)g@S@bKxA+m6E0@qvO{=gMo~lLoD@s!;{MZwD|S(-WuW&&'
    'Kbbrjl_4z%hVAnIP^Qi*Suq`8IuYI<tE;q=#BXz!{FO>HI8Za<eQH!tJHlyX*p|4@(9CI3Ac-`6g21?T59>(S6vB9}5G^>F+^kUF'
    'kXklQ9N|GDiJ*Y<ajbq2M2E#q=-eVLPg%qf59T$P2?!#YFe(p$*%Z?ZXHa(I<PEp_fUKD`AJmG1=_oHHf&&~h;AE7FFt;g`HF4PX'
    'Zgu*5-T`M+A+&1fHH~7#Y0%PXQNk}Fn&aNZBoCBwvN?-XZM0q5>o)SdTS7WF+ctbFxK03IK&#bPD%l)wfC3ey8&(%ZlV;9mkzl6l'
    'HnQ*(YF<o3Qi<<FA`{0!NweQPnuJMTrZ_nX)Ll~-*G7vctuJg*j1A-i_#qz(=mDL@MpFY}Epm6U0UGJ}k1(#nNVhARpI?1c&VAK&'
    '4Q<p{5JV_e1L&$+xT4y_x@KR4Mw7yLBqK7zb$eOc+Qujm$k~W&*kD6|<c>B7GPNX249@f*U+;GG*X`!SrK#EooG?g9TxxK^!8Ggw'
    '0xxsbM)_#dn=<0VuYN^~==7YQSBg(T7bp}pomAtMVVe4(7Z(!dxZ~!<gNvs#__e9v^ET|>c2W+j@`@x4V;vD}5woGM<^dV;emhAO'
    '@N#9Yo4aNgr}uK7c39|?$e|1}hWCQO34=HAO@hfKB^iVp@yp3Sq@*hknfP!U=Wv31hekPUpGueub9J~|X-JU@1*s*tZ}@N-{euh%'
    'dI(|;+IZ%wNAh}>SCC`qRp8lyjv_Z2R7O0dc(O(wM<%Bh4tfK2zB+GTw)2ieTMd!Id83%5s3r%ZX+|3_a33;Ug3A}}CHo7q9lB~e'
    'ua4%F*!MNEsZkUJQMak*dRPFAOd+69?yCX^Bcj7iYtLPEhRzJ%+UH_45ydqa=%Iw5oym0!1QaERqzLAtk*#l&*Ivqh-9M5H)Zuhk'
    '2~y9p7ug2_#UMh_gh;g4vdn;62apT1YHi-g+wp0^vQ_6X7P?qW=;{Fwf(3&Y4_uIdD;dHksMwI6@s5D@#aNxmuHQ(+OZ4qw@T%^&'
    'i_<`n{lkgrHLYNh2p#?;Zw<mM`c*&)dV@g<v~gIwA^yuT@?6se19%{jgn_R<B%~c}jA5`m4j98h(=;)}A>ORrNIh{_Be5NQUs3M~'
    'b2#?Ge}h)DSS3NY>`AauBdm>b;B;q~`M@-H$5epAE)+&M#RAk3dLX<2q>;^rh17~1Q^6nY_{v>ep!WV$W^&Wax@CI-`ZPO6)fh9a'
    '`A$~Xhyvy2lGh#-)wdiEO`<GKW<WC@AukazlFUanDFeTIjeWy%laz!R;xO~3wFt<WWxF{`U*-N&C~Y8Z^DR#D#{!|WA|S$9F&fMb'
    '27rmOTE+9qZJbs7ue&J{bm$=%cx$~C-%xxE?i36Y$WR>WY8r(A+u-Tl`fcE#D}6Wl;i=BL9JUa)!P?U-NvN;#W`{vDXn;Lu7WNYO'
    '9EWyTdpJ)#<mXff4W2RVbo*qA)i7U+xCs{+`=?R29Pa}7j=pTPSFK*hf}RAJG9k7l?~s!smKh_lfSx(%BwbMUH<7}xeGiLm*~y}$'
    '2FeyWC-WiV{DbcdGwaCMXKjjFuhrB~=;xwsly<Q$B6(Q=Gf5%whMndrqY6evY2nOJ9YA8Ew1uxyTJ_C4<L#0<&lf6;JaS^&BkIRC'
    '%F$J#mqkn3z)z7R4Do%?-R-MauW*UuaKi|KLpd^N8E8*09tjOkA5!>$jRuKTPDOUkUuGfo(T};B15}3wD}9ork>f??-_z)Z(TX2U'
    'D?av^iZ;LJF!R~H`;&JB6aIj0BGfzPzO>x12*83S#M4wp$BHtY?(;C!tymq{utCHLo2D3j7`%?SY$85*jLM+k;<67S&k}ZvKXf_6'
    'bva-MotqIYleNsiogq4-2U@0Z@clwQV>p~l+~%qk6|?G;1PI*Wm2r!BuynFblD>hJFo@NNDA)`w?U%kNMt-+!O{8D|Op@Q@pg}&='
    'CwK%iBvqd^2oREY7&V|CMXSkotHMcEAG$z)=2CPb&l_1vGPI4)3EdMhqS0I!td*GEQ><Cvty+0Qph+<nPa!9tEIQ1{0(#(Jl=axG'
    'GvWX=gApr5T=;JbSIlsNtBbu1PO@Rrq}2iT5R?oDQqWT<PrL!N{QwA`Eq$uR@7^cucgNDadGcbiAdTq6r~>4u)l6=1te|TEA8z7w'
    'PgnWV8<Cna@Ai-C86pdD4?q5+pg#g8V2(V6TtnoiTdBeJOuB~ZU=%bK=eOZ=E8F+$omrDYKuRY5xQ0q)f{*_Mn2qNiQGwi-G=wA>'
    'Z(-Hj8CSLy%bxN6^4jW1GM6#w=%6E{{UY1`p4rSel;s50%r5w_)~@{uZdYspoCBUXG(4&x`d+d~Ws;`c5)fo32{V!=Re$<bQ}rCR'
    'hdau{%vjog{C?OyUHHY|pYU;E8fiEQg1%Wk^N1KlI|KMaN0{M>ewyR3%I}ae?v^$uDBH)M@%y`{$x>6nu414Skdj^Q1SW4Vunvk9'
    'YPU`h>F1n$%>g}6*FM~7_~t*3e;zN*7;0w_Gg`cnCx{q<lACmTkeMO=VCag79PQ^)HbUUt>yP|cknxit1c@5cn0a*?s1P-<hp5y8'
    '&fscCj6!lCIHI|<n)uZEySoKzFLb5QibL|iZkl?5P9-xCq3uyQ&?fBRx`Q#`68~x4bRe&~gU_Mf!nttePd4X2*}Rz+Tuxtl4KRk%'
    'g8e04B8+E)<G>6?au;zOfMDR`@XtQm#M|%Pt1r7R2SU`<R0I>ixskw!WCh<mg!`7E7S!xcW>gH=`{)Z&%k_(Q-}p}7{$nBN%2A%-'
    'u~Yz5Lk<xplKl}z6D}Bm$ZsUXoo&Thr{S8%|GoQP>0yZn|I;167BE;YR`~fO+!R8>V!cjfbjv_I0pz^x@#BK@v^q_a@b&J@&OnT~'
    'doIf_u^@yef}&PIp@onTH2n&{XyQH7I1nPDeEpF8`O%u^zZMvE#C8p|V{#LN<^^=4LSr1GqCHbA(bxjUe3%!$U-FdYe_0rGh3VT&'
    'O@%YZ1=q^w2yvq$X@M$+R!ROQ2vXpj#=7+)N$}+lwp&gIl_Fkk(9>w&;|Yj{8=WVzF?{<QQ9nMUq<yg7{R?vx3(vEgow}mnja-*x'
    'g2>QdozeY6Vu8s8u>tPvT(=$uX~)vg(Ltk<F#O{OG1?r?GS63IIw&B?1Z7>Tfw1AzBN?`LC!>SIm#^E5xjDGqX>Qx|t`H4yf<uyu'
    'uOhawsFcCH<p)Pd0+R<*gsDtW0<EZ6T5FX#5sbEHCLG4y@(0DL1BXRG8Kk*1uR13M6K1LXhx)0%Ex2ER<dQMA#DxL!aU<Un%#=~%'
    'Lc>K2i#aTX8?4v{X-ktTR(yFbGV>`7I|%52p0lVfwB?BFR;_(DfrkRNWK>d<`)swCWUvjr`3DIur~e?guHu=ra{odGLF&UyRDhL%'
    'yOVnbs&_A`ISOFjtXZ`xV-vQ8n#s$RosI;OQI_P^pakz^qoLVM@H&_z*PAA-TDEwB1<Cm7TS2N$;;vZb3Xp2B5&&o&#f;O`4zp&_'
    'Q!Re^HbHG9*k5kG42R&r!eOCe1W7}9OyUb~l|E<l*|PA4?v~?m_s<t#j=Vh$Xs&p<r1Q`)aq9-?l^2SfQQ>Q#cA;XFbER|+;q#~b'
    '*~&FE5rhl4+7J<lvsmuI4Z-+@G*CV%QoLZhjC)nP`d5D~1t#pO$Q`8S@RC*zG_y&S5Z$2ihm~sib7&I2U%PO{+*<BvxD5~oA=pAG'
    '#6Cg-VMwR+6nOrzq03EU?$dBgGxR0hL4YB9S?n91kFF$F=pj7w1#zeHt08H%auDFt=7DpA_qd=n@;;uc)-2y~v<sk9TgR`#9!&1Z'
    '6o;BYNlC#JIA+;%0g($=Emw2J0lC7*WP%IR)-!gx#4FAc`Um<ZAOW5}(TJ<iRJq`>lzBq!Lmi99KWZGg`ZEiaXNlvQPBBlDKBB<b'
    'Pm`iE#&F89D{><C&aJ`)!yTSwLyox#AO~eW@t=<ceh8I@ty=Dx>ziV*FkGQs^nTE^kjXQuR}L2qf6v?~jKCFsjf``rsue$S2ly$@'
    'Gv{UE7eK>iJRl%GM0_I{(27ebC1Mt)?5h?#jRGo=ppZ(<8rF>I^8k|qG#d<`+7{*nnlgmAaMXrRPs2H`zy7smuAfNLXe@-K&f?5+'
    'iPNFLdI6M`qD*)%dvVj}OOpR=6;JP$&*kuH9#XK1F_T)`ygAwud?q|ZemMUN10mW*#xZ=l<LXt*<1i+%{@^4t;;AE_1#YA(h7W?K'
    'EeXEiLYrl-zJ6(%`f-<YNk&hQ#S52Af%H%9F#7yX)b@#1vO~@%<NjE`Ix@jO4x$`BzZ5v23>hQRLhQp^+TwQ=sS0_$5dTQfggyXx'
    'bfJFba(F-(u1N%_Hu2Kp(dzdipeH;qIsk4XFPS7_TC*nW{Ig&M0|$+%nUoSDP*@2>Me)S901$_<%;dczk+EI7=vg*i7~BL40yG)1'
    'hN>kJ2Cse)iae2@uu$cWA(@%y`o)zoRE`njuH;Sw#^Fryvs=}r<cJB<E%hnwVLa{J$1R~x76*HzGjwz(Vb`Apr8u2t3K@b01T-?>'
    'NtW?eAG((;fg{a;gf6c5wx6CKweo@4sfAf~82-3MquWHpV_271XkIpn+zZg)c>914WKi{MpKqg+w5}jD#3qIh9d$bPp4ga(*2N%F'
    'Ff1M(R1nYt)MdffFRnk|yd~`05_h&27C<Tm4Tj?_5@wG*1J0DK3O=@lyw3Egetr2<<_7}HYjC?;SejqXA@220znsLmU(V^m_AFN2'
    '*0tFf@JDw(LGFU))GEE_fD#5fh_-mcCEN~pqy6~bzwN&o&XrpqK%3FHg66@ofPdr#C4$k=@qn+4TL&c*msnS^^^*(cC&Bb58+kHD'
    '4zB_6*6YQCiHRp@JCK}9->ZRF_+CvlpSV;;=ros(Lq#2y<h0HCp~3{SU^b_t)#4}&5YKYXi0&=NtR|*agKhLHxQiOb=#qHJ?3!{y'
    '<Jic=<QItbbdtsGr$JmZI1>XHE(c6}c~SdWNw)Dk0x*zZ2!iSeM+HJ#5S14&@zV<P<R*0IMGSHKn%{+2DV;`;O7MOsdONwLdSjy|'
    'JQK7<#;1ewX^1}T@BOCqvjz=G7wd!3G`Qju1xU~vnl{{u+&{FKF>pxTrw2=dtGg4po-oJ#61RC7o_O3AI-De~beV8LL*pZdNfH_v'
    'gJGvC2!Y|QBzVBkZSBIvWG-lUgM7l}k^+r(q->{E1a2sM7Je?pmE3V_7yPMazFda{jh&wOY23AVz>rX)Xz>aMGNsWFBtF$J)UI5F'
    'e+Z9QpJ9Y#1gX>8gjvO{BEx5VEwS<hwl&Fr8swL?UM*+7xTSega4ChiMQz1^HgV}&Niu+Glh9$J4lODa8~87M{;~eNB(e3iyLcI9'
    'M-&fHO5HC^rqF0<`Xg2w<m#e+P#38QH`Xosra-=YDv@+Hnqm&#jkAnM*fOmI>jw<SgG`!Ae4bq0niWt>Aj_ZR)rfn@Ad5nDtC*ug'
    '!j=OY9Y3IWRJOTpK_SqOigpE!H<AfO0V}QnBwnX6;h2b-WiFteDR4oGm1{0M;+n=Ay+P(%^YLKfh8AI#sGdFW^#Js6XJL8^k16--'
    ')-4Q9;DBg;6JKyb!4BYoBgw?iL?eQlhSYqfjvv-72}gN*87kHIIqD01;~>sQa1X|UQH#(qZh(ZN@^YqGtzGsttGQg>P2xYpu+YqP'
    '9w=HvjpJ0;ZMjI%y^TV>>eem-Bgnp)Q-u9hr(TBClwf#Se!4W^dd)+Ff@Xa6YDK~j00A0SBV8{@G)H6zWRHYI_#WbaY1j>OgYBvn'
    'KbqY0GvtoFxCZs`UO`<uIDL({n@ksFR5DaM-9F>zko(Vz9!Nj^?(&RE3R8v#PNJ9T176w)yg^Z$p@iw4X%+bMsuedy)EU7Lqmif&'
    'fgczTMGJ@Ui&F||E*3gKdBC#s$3rR$%T}>f>7@c|<Bvi*1`mr)>*$ohpc-Ntl}1iu`ffk(Sbx0yqPZxr(5N?n_y7_)v+7X;zRPKp'
    'mN~&{RFL9Nhjr_o6b+XXCB<H1l)!a{B;h0g=?+6bLz=6;Z?EUkc9oahDGi0gdDbJ9JfrBxk21NGV=gmwtcXgP`O<hOB)Ho!BtF*b'
    'f3S2h`fKtAf?x1pT*j%4X{^veK}O@0xsdXXi<a<jAM}6ykN*Qcbssn'
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
