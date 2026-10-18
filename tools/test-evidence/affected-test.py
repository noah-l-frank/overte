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
# d3b242c93e711caa988ac2152c4453a7b112beaf / tree 4aefdc4d3e1ce515ea6dadbfd4be39a5a5a5975a.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = 'bf677d4926f76f1ef0d5a99112d0a19e3ea69461a74e8da5165488397e4f4d77'
_MAIN_PROJECTION_B85 = (
    'c-qaK-Im+Pa;5L*G5Xqdgai^uz)vx2*4%UDA4+Uhk#$Ixx@9lF`+OT@sio6Z%mgXVj6HUrR`)oQ05URS$KE^s^S6IIZcm?I!zaH>'
    'hy6A^?El#1!^7#|cgHy&{_*>9zx(aq|MR!!eagT6`){Uc25W!&x8IJRJ%8J})MV2Pb4pX!^pi>1`)O$BxpB$Hkh68|X!QT#^zB9e'
    '2g1`n{Pth}_I=sFLh<v%%l>H_zZF&sp-aXLd6-<2e2(Mb9BVX<YvyhUshQnieKUT%+KZ20{9}IjV}JNEKkff`c+C7-f7<SM$HL<M'
    'Jo|PUd~hx_ZJ(PQQt0#44pVB|+%`@0L+sm+7eC~e{c(HRAHF@r&pCc6t{8cEb2QPJQ4cuhJk7nG8=EG6=rsDSwK-gQxTkzPJse-R'
    'r~HueOWviti`!gUw@uwV4)fHTwsn1Lrq-~qi$mA<voXE*+0C&rHS3nvN<$weeJ<VHhQYVq_t{Nz?(8@X$q$3E!SG%`UhC~u9(lQk'
    'ygNPo^VL6X=WSfx>Oa0cKVA8yv*j~#^I(T=Y>XdL=6TvK^wZ>A>pC;J?1!dm^~3)698VAW?Z@lOX2Ul-&HTjNhGg0yHN72X*RyDf'
    'u8V{1o0NRbvVZ@mt}g9n$GPcd)AysvAx<$3Q`hp_eKcu|i5*PV&VOGz99WLX5TCX@<xg?@>G!<*vfUj&J$k+8mv0}hYK)II#Mtt1'
    'tqZLk(-2$Z`keaF_Ga$0ajt3Ctop()=Y?Ni*UqlXykj?Zp^2_dV>6E-@L`3ybp)xg$vMV#>+Zw#RcAlDCU(}DncvqolW*G2b-~6d'
    'kCxBPN8gW~S+nZlb$4~mXzVZyY4%gFqvPlKsT-PUG@;8Ow>E{w<#}GUroQA&{CwCy=gl$hU#|b^vA0dbll7(>hB)S!C*OD8HGMl0'
    'yZV@>G@5nKdfCCwKj$NXJ8urzzifApSGSQyzTP<Gey~K%Y;5Kbx7PX?hGsCmwS*KC*FT8e%kw7gck}l8`p%m?j9otrqw%I4qZv3}'
    'J+W=<Q)(MF=h$PndVSr?Y4hjTIb2;o@SQc*roMMv5`Dvy=>62hmK%~Uvg0W<xeI>v`h0<0l~>o!aqdRnx2fmgbuL5~O)y>KxwWEi'
    '&6qknG!?&H5#<m6?b9xw6zMjH{p%@j($+uj_Q%sUUXM226oVhLHGS-}<@HZv&Yr8Y=?9`-OriCrH`D5Eyr!3{3%8>iOg3%Gjsu@2'
    'J$-gEL^G$BgD`W|+3Z~P!sid~vig#k=@UHVKTp>KP|soK;%d9T8@n!RQ~i`(=(%XxDM!-;WogBIJbCiM)BbrI9|(J2w?}SN4&W#M'
    'nzpCS<;K%3d-X*2efBoBo@}t2iH0fJi92RgOf*BUm%)>9H}7USl{y?x{*_$vdX#cQ7gNinXL%oF7=gGsjqNng$#o6sO>RiGn%g(?'
    'N;-KxQl{w57~5f-o1Wk9``9|J2962oUO&#gPqu5bxp@y?@?n>sHp^SOx|695JdorD?)}iY**5JQQakj<O~X87@)5q@cD{Kh&wfX`'
    'oi^n7e9DJ!o6p;$a+RyQYIJc8q(`C2kuc(N&t=9fO0Hl!cGx(}Q@VXu`@p~SwGhmP*v-krJ`gQ!Xr1Hh^<9%X(x=Q9L>wFRPjBDF'
    '%cb)0Ps^!3_;|V=*v4eX*4cKXz#0dldf#_0rqK^ApLJ`SDdlzy)6H8Vr<$L(kDpJ~v379XOh(ms+Xt?e%sDrsaU=0Z4=8mFHQVgM'
    '9a}1;TReciiDToaK)ZozvsKnbmc=8Pczey*jbqoQo3}vPkqCC%uN>^n_eXR+3*cMvfgGRujc3q}ZY1u9f#5p_LqTIA@u#`{u^dmF'
    'tLq=j#HZo3beOs^MlPY5N;O3ul%t$<uJ5M)j#G5<hsRuf3(O?EjgN`!V;=ZMG6&mO*YlA$Jt1m8Gd214w{*@{->!nNf88Zt2sC^q'
    '6CV!gIj^NLO99A#_d~R;34?9Cp-!;*7wxIydg}6QrhW?4WVXvw>SGh;6pi6a9uuFjB2Ju}J9o6)QJbnT7<=;f)^K5RF^(<pPRe2A'
    '%cjclT?Zr(X40%X-&@{&-5&P4Xa2?WtGiy-wZeIX5_BPiJ`P+F!4F_fL-u26d1l<`sk?7a)wk&At@9mKg&RU1fl894x+MXlybR>N'
    '0|%ZR*<ZJv&6Xta@qBv}GQki=KB(l{*bs;VFDpz#oJKB-jyo;nxn;ZeZSAI8J~#j^5@Npb8I*-AB&tpvL7O7Eh@EZc(-eQv*5dwo'
    '!AVLFY?yuSCK7o&83Lu==Sb2__-405GGXSP9lP{vc6H2O^R7@;Q?gF6*9)YGBmgu#FR&`EkG9JrXlO?u_xJ6mDiV+$+Nl%7kn%i5'
    'pipjH-wYi72q0?)UZ|nWy>lx+WJS;0ns0mpJoEw>y4+E72|)u>Gyy~_v%9YK*(7i0`}VayHR8Q_az=2FK6HY)<^~+X46Wr82XAcI'
    'p>5`H@4m>7Ht~?bc28UXbS$6)lw8)fT(sj9NZV#m$Do|R07OR9#X#zmrn~o4lM-}X{(Lz67if_;hBHrA4Wtip(~ScKs__nN{l3lI'
    'kiC&ZhS>~e7&u{+&AtaU&90xV$=-0~fcJy##QQdO+`k?Gwc`GB2DgsavpLpF4MmaX$p~f3shbAV*-0h99H+!Xi$F|wZb@0?rlN!e'
    'VIp4x?4v<IWi|)ynHJO~b#z9+Jqb@^^KRc~{dQ)*eR?eby`vpt_PO_s?R}(S;>c}1IZLEvV`A5h6Act|=XZU2ewnvV`Fpi?{rEdB'
    '{h{+zXTU*3%mG-2#}deQ8$q&kcG`Zp^XonxUXLekk}vt&p#+U`=E*NP-!^2!H$Cx=;sj9I1j9#_$JwSa-%}B+*o?C5rZWyqw4KJ8'
    'w>P)MaBD-u35&sY{R9?Kcl}>L>dQa5ep{ptG?32%bkz0S7ZmgjnQU)DPa+FO+mCS^>oV-e*CpKL!}IodTzZICld&+-M(fn*m`A#Y'
    'U>c4zIyAw0XY&{vpNKhiKl$@sZ-2ip1$<r5)DxqhoQ*copd_?WpO4(&sWAySj$=}{<~eP-9y-kwTMk}F`y(lf0{G4bfD71U=FUl`'
    'V-Kk=f7)^Rf6W`8p10R;5;_|sAH+Ws+F_vk0V<K^=qJ<h|2hCJOTkcC5L{NR0TY{sOPsPy1(J(74ixs56Aua^_$X4Y5eDkMr5{gH'
    'b&e4`Lkp22pZZW$D;=O@Y3-3~aM+tRg$WS8vR?eL-&1pxT%xwHT}mA&fA6dc{5+98)630#*3{C}X34Es{9KsE{UL9D=X%`b>otTz'
    'E5VFDhaD2t-{3%*r$&|gL^EojPW5rF#OQw9!SnuWUW!q!pu$yXz$IPV&P^CQFBq4!hNM$>Be>W^)$V9KOul{(>!M1GJn^RESU0r3'
    'IvQPlFmp#kmy?#cfHG8pIEDK4D?^J(GqvOBRcnKzxRDbl#Em09auDrEcqi}f>K8u8mx^aj4a9q=ncH%GwT4qTl1qn<=4#803qTBX'
    '(hbeprT;2nuiqgwvK!JKPwFZx#I<DhBM%-xzu|Qoa1s)-`S#^6-M;wpdi^<Y?o1rvo(PJD7DAoDO*ViMbI;LF7#)q4>4uHet>4W('
    'O-@7BN3)aUi!62KJajF8FnZ910e(ZX{u3Z!U$`6`1%J4X1%<#(+N#UStr7`&eb1g^ZhJn$OmG~@G*SvTZ=vo<IG#W2H8j0FWP`+C'
    'VH@!9J@s+sW+%Do$un-)#<$bw{jLts)W=Ve0H`xAG%P4WxrgvUosdU*OjO4_FMGqoIOIn#9SW7S`QzYUUP@V33=QS)%tt{e5C+EO'
    '7<x}nn2H?67~c!{&J7<1z|!?5>@ZNL4J<}Fm#kWgK!Y>gwl*k4g7T8~<;vpiLO`fZ2qxzz--%o@(~QWe;YPBcTbAS?^?@#<C@}Mi'
    '`{<^ufc^pmCOSkUm)uLR;^=lpFDTHn6S#8`GFL@4bpGWJ+uh6S=@W1L>B6ddAj5z7Ba?Uot5FeM-3`4uRjIu7<@<|d_LPc1YXU@o'
    'yJsFt+gD^sKkbIqA951$>Bo(!^w{{59$gtY@>GeWY1AMs93;<I5jnk-CC*ZN&?nCNYAe9ek2Y2!?aZ72<xf18R#*d9XiDQu^#R2&'
    '_aV*%u(5(Nvs~71<i_hulB)4-Dm$gwOGHoyJWz|dJO<$E-oq1dey&{d4H{Fd-0&X!;dy`9yz=iAvX;K(AaF<0aRCpDLsa<()H;pM'
    'm>HUwp%^8M*Y4w7c|KgY5}%HT`2U(bQr_7AH9E=1TRC$|RA4QcW&zJ6y&XsRio7DYr<Rn<58xR9<(yxh4NOVWz&p0{1|Tfkx}Npg'
    ';997JF%nY=shnSG4hw%`CLLxUB%d>cqZ>D~kT}m@H)K+Otp0q`z<DJN%q>t<o4Ji6EEC=uwYN__e?*ozRM4-A`wFkyr*y`DY5`Xw'
    '+XxY;^%D#rdQ?p!2sr12fPj(FZt29&H1}`rg4zA>*a|!pj-8$tAtA!o1gUG(4W`KeBWGyEcz}a!@88&#HqhbirCvzq*O3MKR4wee'
    'k#4zxmy?XT9UTqh7Cs&PLI~$(oPNR1cHCJ{G(G%*R^RonEEAyvSTtR0Qa!M9q9<*BAf*5`hMJeQ@z{s{{#~7u9%94~9op-cYVeS}'
    '9N;4Ft|3q*4rH46)cE3H+ky&!`j6rMt*wb&i9CaEpAR4YJn_37Y5GHOQYfW?tgZ+3n*RmI@{+D^pO;GZHN1TG#{xSV(&RvxXM2%4'
    'R%iklk_Rw`06>Y$g(K2-_yynC`6{e}uN{3(q6FAZYylA6xIm^el<{V0qeyBk53b4gZ|b;xT-Xs?q##tj6^F71SmZLK=mXHUfVkrv'
    '#*xE7>nf7y^1#4X^MAwMmQ1Ij?LOvYCbicfzfOF6RKrw687#D?M1+l$6X^3VI0SD(fa}|t=^w)a1(GGT0U8>Cg@$&ZE<ofVK$?Cj'
    'H^PnEdE3LMbyp?*eio(o*QFr1YUE~uqYP03>Q(@?0JSyl=C}BLSIb3NVBHA1f}G8L=!sL7qe$Wnjs>n8+D<|Rh|PCDpG%0p4(W7l'
    'OR>b2!-WhL0)!Pl3o#xDfv66xd;;yX{k?msIA$%38j<>-WH?Ypc)N7k1NkuO2GGsu$wujCySuk?sULnmY=sEWs9c&Iof8yUP1AJ<'
    '&LI6G<*^+vOdS;f@O!tmVoQL606s)T_*#~PDu}d7{%6oM(bvhr2_A2*RFi3Ykbvm2v)tylR>T6x`gkg1!86^QxruZ`DQ(9%DW94e'
    '5Qw1z69*@!tnsc}vxia<OO-|u(vH2OJfI*zk=KdKOj{`-#h{>crXT8mcV(lAes6=C!OryJp$m10P9|!2$QGn*5U34Z2s6F+adQ3n'
    '-CRN~a!Z3B5|>v|Oz$5wkspR=DMES)eEkwV#`hSUX&<S@$uj-Zrwvs7A0%2E{j);9j%E3P(Z992&vF32>QR*Nbs<s<Vv2Xp=j+Rg'
    'a(Eq+nbHjHoW8)ANrX^U!l0$%4$`jh&2$7jdRg7|WzGrD@}CR6-U&&aV3siVZfKzlqJ?r4Z5>@IMSm1=Xz%{Mn&7Xz6Dt16A5L48'
    'QzXg@)8$m)kdvJ!n0KJTTqVeH8WZUi^-7CHt3>(7Muv2C$>mESG3W1#bT*?}fQCMV-v~#lfzO&6Ah#h?xR0?%%}5M*?~eW3f@fmL'
    '_3y+B+3ULomf9%gAdeLS6kmKdQ4RFxx;Peo-!bf;H($B6Q#qvp#+<0B(Y<=W5iowJUtl$}hiDDUkjyZJG`-inK4&W_f8FXWQs2Ft'
    'w0cdV*GQZIjYNPY2R>`D5mgsuK9^*G|K22;p1!nb@-HW8XO;-_w-tGMe?3>8TElCE8#RLB22YoX{xw(vVbnQEB%yA(T({!!yQ=zy'
    'qTu@<Uk_}pI;yc5`E==NAliYv0)%eZfrA0u&{*k0^f&I{<z@T&ys6np6kD5aQg%xlx68<l6R}*$nPNS(U?>c}U%8R0hX7w@puHA|'
    'w^l?^2N=*ojv)W=?GWPVQ9B?tT)TGMKXJe8&nf(c_E`S*J1gWqpk|u_N1Gd_rFj9oE+!v>6ne}fS$<l(n*}i5JZ2j1rIsT^FDS;G'
    '1-ki!HLH9KMuQzQLT&3nlEL7p%Br`pd<RwU0!l%GZif0jiE7qc$W}8NomTCCFeBarm{wc;F8=>`2Xro;3rj+>9Z4%-BsR!v`JG7t'
    '&=G2Br&AR>*afs+yV@mFK7OHlwb{qlr|q9r&mLG+OVhUkIvGfLpz%<O(>a+e^m4dN5SYkLZrsA-%j@Pd{K%(#EWn!d6cMDuMn<&_'
    'E87{{k(dDKbn30OaO`*+x%mbAfE3O34%NNDGonR9RDd`Jhjf@{wf&MxCUFrga&pu)U1xsHh8BRSq8TkPyq9jHi*p+jonO=vJt}0R'
    '3R$l(i+9xxH|~my`v5cIxc$Q4zWv?R#EU8jYRY8EfhJNDKqf~=7DZ+n>2@W_qG=(tH}2<*K=^M@1T@u1dHc~7`!l49+W}We)67HP'
    't2^IAA<0-GSmp1Imc8k6f9tVYy&uyC0!KtU(qhOEI#@KQBzR_t8k~?CNxr*xT}9sC&+|ThsXE+#R1b%u8lQ;)t`7Vit~3exrHPuw'
    'S|IbEW9`D1YB6kgsl>jdQk61{U=|I!biPqYpb(bQAneQ#ToIwhq53?(Y~$X3nzw(Rg!(Vw=k>TI%?=42c?7*jmBpe9kWLEq06C@x'
    'A?tACy7m8}OjTbil<8h{Q<_Jx#?+^#Ud8}~MhH6qS`fPrplsbn4zgM~)NcYA6QvMsMX>{b=zIWNmDvrF7(_B=M1TtLQo9NMuZpO#'
    ';*PgUsghL4fM8RALd2!o%kL#1tC%xfg6JtpZ`{E-->H5cQgl$|3g$utOc75X9O4K$F+M+t;W`VcWwh0I{ntHzyICxaRIL`G6KPdL'
    '_pT!X1X0);rTi>PSb|Q90!OUE^4g(t!HL7qM+aRCD;y5Q1hxho+FN8<A!e{pE({bmr3DepeEW}FCB35O4$7bd&vnI%o+oLXS}=!!'
    '8=g$hfL_yoC@r~2(cbFvf=+mnf?}daY%=|R+hiD1cml}GX{3S6Um^^pQoyOxNz-`(cQOF(a4TAMtf{^c0g<&t@b~_#-Hx_)vE`TU'
    'FYRFc$IbcQATxNXXuAqD<<m`6?ATy9h%b;jI?8n(KHMZewid!iYHr!icBjTKoQv=}W7oBLc@1w|nCp8Y<a7A~;(|^9-$lTlMCWcC'
    '9jY7jmB4rbZvI_+lDZAORDR-GDlykEEs+*s0A2vP1D1-=x$y}?eGg32^<uBVF1~9&KeTU159WN@K3~74xC3FZqaUH{MIEf$3JD;m'
    'gN`o;NE$Qp-{f!E)e}#LZf`DyX5K=hCVe#2cNqEbpbRV_iV#|H65Ih;fQOh{_VB#418GT=_JB8+&=(LM04CB$@H{STzL|c~eu%};'
    'enYxt53=`R4~JCoEHXD!C&d#kU3@9P?XY9uoM4H7lpzhs82}`ryJa7=Mpcc!ywZcO`Z%b$Cn{l-1{`fDhA<mR`EmAON3@H^S+~|O'
    '-SlxRV9n-yZ=Fx}_4m_oHxJZ<WUsKdf<Q8$TsTWm0$>0}eKq;E(*riYKL7w+cJt5Yrvj;tWCnQ&1Vru=41uV3EdF0qX^@r(`P`-y'
    '?dcb6MSpf3Gr(eHaP+J5!YRX#h{r;Vffx&O+~r9)_n3y;_aav2(etqs&>Nwcpx;KC6ht9lTf8aYTk;t)nh{?U=p{MdvXP^IenFFV'
    '6hHXf+Ak6J`5W*=Dl9w>rkF!Zwm(zx&_WA6q(B(ed^Gu{*ng5TJylcyRy7B(k)tP$=Nx=-Lm$EeB*4_Qa^IUR7+|<%6X(w(K2eBW'
    '-vj(H$wU&^5uXVHI0^V2$S;r&&2qqXcz3S;*u>BN^d_V6r{Y-=PZ%Uy9A&!8q}t#r0NvaykWo3mNS7(vLwz{=Zt{4sjsn8{TtEmQ'
    'Bmi(_`aKT5mD&chD`77nX~Cw6$00~%tPf&m672bQ*$1g5X{L&(=3fd)64Xy<+oYeg-1|7vsloGt)JP3fVk$LxhXTHOBZ}eiTYSow'
    'ye&pfi1N47=fw@+DVOUq>5!o$3=N@+%Z`2`ASh%3-9C^w=mmld82^j*RAKA|X#^iVMEG(xB+MfHkHB75e>zb?1Ngu&9Dm7%(iYdf'
    'Q-Sf`B4Lm8(rEMs*?bKmT1EUkGwdNgEm&8x%D7*$qeK4ZYboYKX4a=egu~AZlSd_$I0A8?tlGCDl3Ro^*4?|Ir~Tu0SB13<w8^*v'
    'vo2_?F8Q)St1a2T*s|DDazk2iUhdry=*LkSja|%D9~0<?5ZtAYNVk+XHkpA!g&tx^BoPuYb1U8bq-Z#PS524p#QWjxP?OMdas)!U'
    'Omuuiylj-=!S9_(DRR1ZPse=Xrg{Y1-T9Z}=Y3&Uh;}VpL6BYgor4@z^cEAjrWL~?i69O|`<LzN_2p^ruS3nVP<RS>tVCh+;sZh{'
    '0x<_)Ub15&q#i<(9ol>MblQK(y9;ghda?zED^_fzUhzHIIKo4s5p*2nPg95Bz18-@%^OPTAT<7vv;K`;kt4{pMcIh@1<DI(9=y|0'
    'c6OMBz-b(9%M}Z4<<{-+57emGd_J9Cssa-sk-llW@G9_XAQ)I!pAZtbU*K5cLN(ysYKD6^bc~1XOU>0!S1SzIg@Q!%)R$;fN&Wy~'
    '@d~B<#vMc|QcBJ{HdLmW(jzf)AfTd5EtxTuEY&sk2uQT>jpTAcMAe6z4}97`d*bwRef;J1eLY?qzEh7f1{SVzq6H&ISPAzA`YQ<&'
    'HWM;-x^qiUTS;vz&^pSL(PmW5f$)by1{5oS3}d7=wxo)q)I3Ba`z!WCRg<?RBOp20CA{7v7X+CI(l*#vI%t^4Krn075Tte5+_@pi'
    'nedmZiqMGrU`jynX*knhwv=1IoA7-g%F8`1kyV3LbhmEl%sBdf#(q$oU4M1GT*@qcKuiccX*8Npr@lQ!4&EC9nHSY*^Q*R{zd~iK'
    'uw*4A;kC)h3J)ik$*>lq0|~?zY~<~NOrqrO#$U9rxomGEr|1mgNOY8z$ih{Y**%#zL>yuzXrx0+bLWP1t5#T9W6Yv(gylVYa(&Pv'
    '?TAUeILcJ$Igpan9x`|C=FD<DaOh4jAdAWhSgsHbNi{4=R&)YLuZ(!zREs#w$vO##3z(*N?&@-XyzVL=79Cq~S@K)%c25c0qi!1E'
    'i3sNbf`_3GoPbT~t=oFspZ4OElW<@5R>-y?vP<xqTh!N9EJp~H5GVo#0Ifv_Q4YrF&Cy%Pg7~<CEw7)kfcFL&KcSgMtEiPUR=M0b'
    'Y7|X?$+S0Ve9yOT<Y}K4JFByK)OEzi%84AU9u$&k(ExC1K&zuBqV27@3slxb?mPCPV(9XcF5$cCDgkyd!n7$~p=vV6qZ1<6(um+y'
    '$)C(oBvGB*x3NV;otBdp_r+F(5;W372ow0(PEdfOh~+Tu5EW9ysTI0_L$~hf0*n0hn95rk%tQrioR=gHlmx?tS=3$nvV6+KNPX1i'
    '_5y@evD>@6ze;e#lETV#M6eyr37qY5YIdU9BEN^32Gv(&^PAI>-Cm6&p?T=vd158Tui-v}_aDVo%!^P#oPsRF!U$YrBxk}4=jQrj'
    'zvPhTatO}sYauG4sKJN<BB_xvnTBpakph8G<1uSWLj-)xH{Y;8i~6jo`3c!|NDYvcmsPU#-$Vl3acKJM4^ZqyJfJKenalG%JGxjy'
    'Y)+r$x_5m$m;pEHQ?M+_qFmA@)~D+S(^Ne#*fA&?Z%&OaB^h-P(GkL7nRFm+E@vI~J($%*!i|D~PY1boOZT89n`A)Cbn`v7+@z`Q'
    '?r6E$X$xT1hGRbYE4d;dH7$9%*;s4Q`NHf3*~{&FS?+kG9kr(&QKBWs=iN{h+6eZ6|2U!#Dr>Z!bTG(2nD;T<xudVo6$T&j4gqyx'
    '@DpQ~z^O-aXqehVz*bu0RuYM|k2mK*Uq>abUxlWX(tAc;0isQUtUHapVChlzklb0SuJM<qOq%>1JIQ~FFRzAmwe2X2Pi~UILx4Aw'
    'AeX2*WathzEB`7&g^1bRJ)7DtPbb$trpX}Rj&enYSOc|19(XXWu!yrVhyeqUAxk&ix1)VUJ;t~nWo2USGKnO?pEVTH9V!AD6~Q-G'
    'M0B@9p4!Pt7{mThpd4By>z!O39OP}hGm$+KpP84I+g6p~ED7Kp`?!z+V@Yoa%?@TUK4oC|SO#I?8)^PvAJ-+BqHyF<(uRD`R=(d;'
    'M8HCx6RDUnrUc;t<weFaG??b#TS*|~E1|0AHs^@{ip`X}g8*Ps3!zu%R68Lsv@21q0{;Lqpzq6gg5+?=W+X2xXr~BelE27Z4_m*!'
    'li6O>BsfxK*fAtv9uI;L@7cvkZk-#ExQbX5<*-_!G^<IcNJ!ZaU1P!>h@FU%KxR}t_r%`sIYfpNg2umK_JqF%R(p)qf{Q-UFyxu='
    ')@Z6&OQu7B=8xu^)2zR8&&|@<EC~5=!A6e=^bWZU?35R!xlgn$C^`9(0e$37f6FDwgOO$eEal9xEr{P}z2QD+H54((iw&kR_!Czo'
    'XBnOjh%*^heQx#ggcZ-5!NKyMi@j|!NiTDXMBW5+No%l|H(H>gnn>&#HN>zmuBSY}Cp}AGf9_Abfhg4mEpWVPB*DA`O|cHvC2%Gz'
    'Cg^Zjw4l*#X*BdJ;EE6SwUh|eyFvyZ^|G8M0n*SR&Y-Eo3m2>DUSuA6yMUSY=3QNyC$;+_6$YXV$QI}f=$zAhgP8zFA7Lez6wM3<'
    'eHnA}etu+8)^3WV4>o{N^#nzku7NxTB~90%ryB-pkDbkmbnD$s>7Ui_X=#1K0YKgjeVoJ;;1JBKQD{V>PNZ(y_a{i!?I|Ao@iVrN'
    'yZy<R_20lsaAziID6s4RKZQgt`_}|JjCuhAE(Kq^f*<!UySZQ%^}~U9V;WS-{5PimDGZQ>wur>>Uct*8MAK4i-5djchMg)mC0n5c'
    'djdfnynjtf!xFz?mJ+mXtVGF_ktF++?%R~A;cB}+d{(;oY#K;%EMsuS^kM1KP$WCy;L;6s!>v2|j-*s?2xHeaM1-e(*1f7RP7MRn'
    '$OVxg!X)IMlO^B$-t=(%k#6^j_(;9mk{wbD_wqAvFx0tHp~7|;E5hy=bgxXe?&wl}l25%pYFI!4iU(za%g*d8xtCx;137utDBezu'
    'uYqa{i4{W0;qL96+d2FC>y6%<TsQfcz@27YbIh8Qc9Lobs1VGK(Yhw&J9oD925R@DS%bY4Ui9V=I*^gkT7j}aHEIQjlSz*5-Elpu'
    '_H_LGdQ!qzf1d!I5|E7STA_AzxGd4^;pT-ngbIpc1I-7;YxTY^8(BW><6FdxuZxlN3El!J-1d5M!tIrTS*U{;WX9UKhC(+%cuU_I'
    '@WsyZj+>@?cC-(_lQdDK5;ox$?^3}CLxxJ|T+yRp&JXuZeq)4k@USEeEaGGCmNf~}JA3-+kBX@!6GeGbqfG2^GQuDOqy?uX_>vga'
    'EN;I%MJTNGJIdI8=Lfao$tC|azr2n{Q2{}rYycIc;~^iJ6%s(kM!@f&>ksRWcP&>w+RUZjeR(pMzq{1)*S8}5+{|6ZJSwKni9*T<'
    'P>U%G2?z`v`p-~nSJ0h5*h(?==YjxXfmtn`4|Q@3YNA5S7Yn?V&l-$<TYs)jJ^)c(2*%5Q7P<FWV76*}1YV0gjX}<M(C|RSW)T83'
    'W}Na2Hvy(8-Ls3*lOUonhd^#~e42>svc{#g8dQQoBxbKr6Y<Gu>eJ}+r@7ne0Hdb^eS7lX7SeS=V<sN425@62*Nf6i#XNvJK~A8A'
    '26*qO-B*yI&ig>h=MNXFyR(X<R39Vvf`F+g0-!O=5e7^f0u;@C_;b*`8>UFj>$ZV4_vYZ01#TYo*HRx{rne|+l2T>Nnh;7rT$>x='
    'wG0iQKf{=6vY&DNF8IHn3RZ0L7IB&j0B0BA0%k}MOfl)Ifj^7vmrjEphINadUx7Y@s`mh^0-O;OI!KFHo8V1KI|>#!JVqSUrOjms'
    'p<SVmyU47hpSjd@Wi1b+ScJxyVZ(k6Ov{AnO<O#YxKQWvr?B545cXl+CN8k&+lNqaprg>vLVjiR%;=C=v^)xKd}Tzp0+fb3V8)f-'
    'BYh{Fp6aB5M$=IetvD!mcxF+@LZI%{<i&f2cjQo`GcYW#+W~|Uzf7F0=LaA*h73q(=0wU+k={FZJ0cb0qy|i2?EkLm+|_L?l9aL('
    'BpB%raIrwBGw7OtfJ{wI@CF0v81aGkWt#hyui+A+e|Q8{7HW7|G}4BSnyjnv$cVN@SO(?+WmEiUxJY5;8=<Ea2$edah2_zJL*>W%'
    'OBEI%9Y6;&zv$3LQEIqNF}=X8Yu)m%TQa@VsqitPW#iZ38L#^i7>s_AK@W;^1r!#MdZPflF0Ees_{X-?oz{e0kw7U6q>RNLLX2Ha'
    'Wunr<Yy{}rNDE!Pw%qB@w5DfSmuPN54mF-r7L%nG=Bv<k5*Pq(OLxYL^9V46<+jlbg}%LWCq-=#lhiN)7+V;)@*u}aR}*2O3^6up'
    '@!mp7Hrud%8(RIs^{S*+Fyv=KA%(h86P|%=aK7WdkWqpxz&hc}AWth^jwC@3;&FfbDV4w{FB82Mh`Gpz!|#vtF=|u#A2OPxNn%iS'
    '38b7FcupvF2YdUje&25wUB#mD*vwD<v0%%r)-x?~v4@hB0&+{zMQ>0ElY7Yyh9Ow(?K?W_LScJQ=029D<Y1{cYp^mde}pWMB|ODu'
    'DPTnUrmLoz42*rBZr={9#XSn*%iCl2!hC?*P=Ipi=*cCo>!dTmM~v<smmPE1MvcpminYg^q*O3v0qo1DCQtk7&%&4}yem2d&<=T!'
    '!()Xv0-1wv26_%?QllBGZ3!05e^Mtdz4$5%LMgL_GcFxxED!ORCcrk%FWENB5@10;y6ROq7KLnrQ<y?Dnt+s~VC-apZ^Vn@F6ER`'
    'GUMA{D%CG7rhhT&!maa5$<SsNHCCwv&WE4`P%&G4B@#n45f;GCV1_lcCsVop8Eq~Y1Zuh}jV(a931CF-_S7?YLnU=8c<e~5ax+)1'
    'cu@$vscCC^ZA?QTBjA!kXM$NETC;9Y_K5CGU7Of0{ib3r{kDVs0oewqUvcV~(_jG#YRya5>`l~@aNqkysDO(Q<ER*cTg=$LFZ;(i'
    'UEGr<mF&v#prfP7=m{nT(0Rp)E{JU}<^Y|=Ov1*<TbQqvOXJAEN&4&2i>bN4{?c(i7)6BAxbG+_L?;tGlp<iAFik+GD5}%C4J<;Q'
    '!mul-PH-deY4I8eA|TbubuP)H(7+C0D0<t}KJsPaa)F47j*)UqgROu82~zlOYUmh!6t>VK3SsJNQPi;A3o%uo{_`bnPOrO?x0+Np'
    '+*zQt5X+HqWew>>Bh7ZOE!T)C)IqT*d)2xNvZkk79w$eJ-!BpgDI;c$q#z#!t%{PWLl?sQR?~}`npMB;BBFyt=&H1*5uXkMV1yk-'
    'MK)@pHtW&4(qX17a@cOSB*zttU;I?h_5_=<`8YQaHv)YguZh*IkTEE}93eV*W`+hxD@H<%nxz4C=WpwNIji(SPa7s4ad`kw%_MpF'
    'o-?-#_2=^X2V1lk`91HxU~m2jRt-1|*G9o7kC_>au+SVR=to(DXrnTGd<Y=8BxY!Gkc*P0w?)r$!Zk87h?6#N9}8uFuc<n~fl$lA'
    'd=Pn%1CV|w)mG?4&Vc1ctX%!gzWi;*G^x;IE<AO-_ZL@3)UL}TMi&ekhHrK+cSle<;wNgssd5Vok#l?1*cLz*Uwa7lkdD0wT|_d}'
    '8B`VU?=oLrqvE6}KYUy9((0^w**G)O=s~2W(a>OgJnt-618NMmLs;%%ZThbJ^T#W%eB%b~0~sd(7s7&h8H)<5mz%=(%2b9KULejb'
    '<C-m0Jad#4xEk;w=OxGF%0TBt0U-7&7FCuR-cf#kg=L=^C+4fo)2I}AwOor9e**pkPKGUdDl#HEU9#$=hdR?VEiJlFud)?+eR)^;'
    '`{U1?h#91KWLj9q(K}-X@GLHtl0gX5a4a=zx>zxvS3E8j(Z{N~6k|=AQLXSY8V!s^Fz|RB?-?!)<RV5&t0(J1?ZPio@-m{Kpme5b'
    'Af~{izQ!QeAxM&B0({7tsDZc$p^rC3mc{pFmri(5@Qr^Bs69Oc$V)^^6ly~2NJgk&oEJ2K{5uyp;onzX$SzfWG1$Yw(RW!ICKNHV'
    'lM^%SRS1&UJJ3eJh86FyzH()i727hmdXPT?e>A}<gtF3-=_wt;<X66!9AR94jhSi}U3fHaVjI+Lk^>c=IoTJr8krpyU~n#(!vT8^'
    '#WreAifV^z12v>666xMHaiPypJC+o-R=^*(B-kqg7Q~u#&S~Ed>g6-&SU;a)vR}9Eg2z%UzZBHHBP|&?Uf3><irumX;se7h)=3N{'
    'mlzVXRJrz>s*sfI`m$Vvj2zPBQhJvBdht%ARYBs&I6ib424PqlE0>+0z7-s^n0pAO4aQDD2Hhja8L(8Q{ZG;xP@y8u1uLjrZkrYh'
    'CjaGXpqv5JY2#~Xb|XB39?Pf_bp+VuX?xktk^<I#PUnWpF27PPUeD;k(?P?4F=_u&G2{0qzhu<gjLC*OLrFo3J^9*&e}8?x{tflA'
    'HPq~DRO&`r1pFou^bX2vWx$9RndY|)mFt~{kZq37AP`p{FkKuk>8JFL9fnQ=^MEIbn@EWbP@LihDZpI2?i>BK{Avv(I{^V0SrRPy'
    'h)~9WwNSwjAw^rqs+}1ZarMfTk%}Wr=LFV4=0{sn3>lSnw7(f?1k)BdH>$?D=!gA%{r&z+p^v#VYq{XDqMxL{35cfg)xf3}W|%m?'
    'jP|g#Q9|?93yLTXjU18@WOMN$R>NnH8vr<*NI?oqbq?>^)~@&ZblNU+O0SoNj9!ult!Q}?@B*t%YT;}CCSW|q&9rOU>hI}o@aODV'
    'zE1fGpiOAX@`V<ptWi)f37DmV%O2ibU=UQzz&@2b_`xB$YI(*Pk>23N1K}4pRr%2h!2`_W_RB(H=!r3jp>p|)FEY;RPp8iXG(chx'
    'JZW)ML?=U6600QYQ{ppyI9&I8i0nvJDi=OR;H3hn1ZK}&n;>CEd7<KYX$3n_9>Bn&LRHvw-I@h?#>ImR??4?c*ozqIb9QL8F}%sk'
    '+n=z7qz;^o>u{=GS4=9fyb6FC*idR+%3+{rCj>%H!$dF~Dv&{;#%Ad-)JEy=?nOTsQC<J(s3GFuG|Pjd%$JN%A9Nh(ly96*9cK(V'
    '!PefvXUrCm{2M&SFNF-AV2EFtxLH6CnpZ_m$-MHJAj5XVo5cU2HkZEiW0w3X7i6zihJxfCgB<^8SW$b+&UGPZA|fP;QZVM)lI7gw'
    'zW!Tzrr3kdxDGK9iJDV5HDfqQ0eHB|HvoY8A+1_*183&yeFy@JuObfSn$F9}3N8zlhbh~t^2bbXpmB%1Y~8BojAwh?SLk^e5`_Aj'
    'pV&$|<;3VwUtpqw;xbWY!qx1%>feoZ*?IlznGf!Flz_ODA^qe)EvIS`aG>v_amy#p^vqZrMqXbQDDm}0gqA`_0Ae<e6?<Yi@sZ^8'
    'oNQ_Z`XB0%fTYffEwwkr*+a9gWZ;xC*Q<j@wq%zHGBidTNpu#u6?F{0!^v{0EmzKlkunlJ_zHJzrXz_(%y+C=0t-=`yLr%T5{WR('
    'Ld#60%m7v3?$5*d4S(A3SFFu91=7qU?jG%C^ooN6ZNSVG8!xAkEGn0%VNeg6H4DE@s=ACEx&Ep3vg*c{j++YpIX@R9Kwbw{gDkAZ'
    'gA>QwcGdb9r~W$YdYNSL<R!j?Nk)g$F{4M+SEK2o<Yf_kwkf*x{j`G%BJm_I^8?l|palhwPJC}h#AP%@u)c#Q4UtNpgwg08n8F}#'
    'VJLDFe%eFT!aQc$`$1qE+8TOJP_;PNYO&HI!ZAoT$6d6m7uLUBpoU<q0iH?50*jFn852?<UD{JfBd`Dx!H~H)r90$2Kc?zalXVW$'
    'erJGEjuKxSLLy|S)H`{S=k@^mS=9ByiZ9z2geav%jM7P%OVHFvs{sW|`Ok0+@{#~mQElY1&Cz>fD}TJ8#2Z1CK-1Lvt`j>W$>foa'
    'In^*3HUK8jbg>B_6nN!iLZD#rvSB)b7Q(`i8Bo-b)m#aYmZ5%y;-NWvH!NpmAqJfLO$A*Ks3cb0)QV)C{CdXGGy8!U2KSK=4M<O<'
    'G)2GRBQ5G@|9v3i!`sjPZu?g~G!bpLmqmg`ds&UO1qH!Lrez|eMiBG~IZG(BVQV&2GgJ`;GY+i?=&0sV6FCiSpzb3r22aMHMB@qI'
    '%d~fGr|u&O42xnWGh#G2Bx>%1xS`!MlBINPN_R|G)LCEO$uj=&#cvDq2u)(r7>#}vqOBqUwE-ON%*;;a<A{m|_p9g|bJ+^`x@zAV'
    '-&_U{GWP%%Xgq2e^2lX^ps5kU5TvbwwoDxAeXLvfq{<huJwqw<6pEz@ZQmfDU@y@>E$LCBe<XTLX5rJEByC8pdhJDmd%oK9;joON'
    'pjlY5FvSKN!cc%vgT0E#9a2qWu0|Ei0|$5}=|T;=ViPMVOcNk8_5+$XNpU8$8*8pcl}j%O8onE*o#lB8Kknf7S7lZ;KflckO|??6'
    '%J~ZB1N=U|dm;ZxdPsH5nI^Di@fBYmP2fqaqJ;yh5~h(1nj<K$J+M-`g#vKL6|1lN1d*W<geV*k6JZ+J;m-&P#Y3T>(YWgfsK}_G'
    '(k%}Uect>qFur~;5v+XR+D<}nXl1-{P3WQL)SywHB;<f701Oz{Zs3w)R?R{Mj9~6@l=dw`2_eyETG^<~0PfF3ABxJoEe^)|Xbbi8'
    's5k&lHZ>H{G(boY;Ix76l6?hDQLxJx60>$2^|M%KsqTq4{BP8XG93cp1tLS;mDHWV?Wb3d=C&QYv2?DNJIvgI76Idqq!Z~BqiBVb'
    'L2pAPft^jK4zMqxHGkVeUH21(09Ge$$gnsWf64_2@CyXZ!XVJJCPh#-MJf5euKqK{aWOzCq~4$=a_C{wC_peo5n5#A{%Rme#{+)H'
    'ooM4-+o)h#!i6$Zq}nDIrrFNhhqi=R8*f0PAsS352Cf~=UHhmW&B}Ncs;^1d6&46MJhd`NpOiw=#KR_xx_Iu!)tk|T)=k~WFI^7!'
    'v@tUo?bZl1PShq=Vzo)@)>0kGlZ!ih^&TMh?DAt-d<kC5^Ou^fmGKP2OPHoc9uFB7g9x<h-3TyLBtg8pfup?aO7{g_c%?|FE@^~J'
    '@<SHACCelh>q;iO;QHs9v^GS%P1mfNBFHl1B9dri)|(gl$uhGE#0@>mAoXWl{Z+ngp?X>^Otu-ay_J@Ry3zH^HBQ|lOK6SJrSGeG'
    'J2&p*`(W5AhjX~Vj6#}QjnQu9#uJoIl2bqeqRR~DO+!Fizjia{o<8YCgp;(<w5mg)L+D6dC}u#u0h+-+=?z9n02+;R_8tl?iPf$9'
    '&~S&{l3{UC6~~X#Yj>J$m`o$1GwRUAnsykJ;?8dAzQ<yJ_=CNiGi-LWt5D#<$(pHZC@kcF&#R&Gf^&f)5#l2>489~V0cUR8N)3Y?'
    '2g9f#i1^*(g~v5V6&ht=4)uk3y-Cxxffd(=E)aU0y-J-Bh+A;S>4LzbCZVUEQ>di%!bL~-9I6quS0C3#jh{sen=0TZAe@Jx23`ou'
    '7{LnN5j?Ju|MfbrP|FG6pkDpTt<)K2aXT<220bc_RC+Wh$0y~svi(K9&)G>s->uEH=cn!CXTF8k%Z2(3GqfOR0Ds{t?A2Cf^Z^(m'
    '$~OZt<iyBkVgwBh5r)@hS&stycCtcM^1GQ29M^48%|Vc)(@dioSlwYN1{OmUYe@r%Vy)_t#9!BLg(wcO!S7yQ_)L~saKE1mbKK}7'
    '&`l!Ef_wyd6tXr419vLe9u4FY`lMY<Yaa?TYIpBlB|r7Cp!)T)UImrp(Zg+^r-i8;p6B4)w28$}Z;L4Jzb^elb7OfSYs{b<O_P&^'
    'Un5O0Vx^OZ(g*r(kA$C|8gU(u&9L^!LLgtq9Ea6O!qXTE9}NxZAna*;8h1XrMOaOQ4bfrx+xJl<jWM5t|6<HLCQhKxtw^u4d|a4d'
    'MlB*vB($;B_lUNzN-@#N=NaT3gJ+{b26)o)bVLb7xf?RzE{rm&qZ{_ILP5bIATqd(2^X_)*&#eLqo^Trj*2CAasO%J4ZEn+GSGXX'
    'pG+Q%%8(WW!*=;!l&O<SR!j$&PK5Wz>MHFl@!MP^f29%)4%CErpBfd^j&Pb7wk7T}G;>-MNFq(2Auz7p!#WZ+g)p8gL<>$PH!IXP'
    'q?U~rM|jXkA}HW|9IGD$(P42Dy0l2kQx<W=gLw^R0)j{;jLJh`HpMi<8I;|4dBd$fAZsSgN4270I?79l-~a~=I2olP%xwx~O&qqp'
    'U!DG5cEA}`2(21=O`{lb8nkp;l<-T4=D2q;$pfXFY|au@8*P{NwvD{(mypiQwvAs3t`h(l&}#LSN;bzEpg;xbhSf#Uq?z-xNHF7V'
    '8(DY?H7}+isl@jolZoS?q}gu)O~R-zQ=FU(>aMAaYoo<Z>kC^HV*~jBe#plHdO&Bf(bPa#i`-pofJQq0BaEvs((Q`o7gisYOJ8+e'
    'LmTxK1QCkW2)e2kuBi5~uG!b1(WEdQ$%xEw+g{eTwlPWsayB9xHrNm#xuXq&OfAb2gEKwI*SmG$w%we$G*ugc69y@XOARhKn1)?I'
    ';AO6wlaDsNDI-4o>Q}UgPA~a+rT7$dfkIK!Ni|*>rfC>@aUo%jdv0DlxOh54SepvIY~%j>PRe0bUXi3>tRsRgVm9>EJRl?9Zzrh&'
    'Uarh_^SA8c{9YdO9t)ikIg~-h@Ln)DVekgNNieyjB!h4xemVJvlyv1G6Yp;05>9aM&?txPu7tTTSBJZmh7_q#lv;xOh7Xs~Kgf`v'
    'hal#ljc0CpByVSV1v!RZ1)d$~DCS0k%7~{FPu9re$jrHggWiChug=?-?fgKZt%gY9yirV2RFebIG^33dxepmG!R3qglKn;54&Ah!'
    'H%D_y?8h3}loJI()NSgy9u@#2QwS)O`>Mdfi0E+B+VeM^p$o&e_PH2MMDYy<dMF`iXL20_0VN3{DT4WEWb50^YcJ)$?jK18>To)&'
    '1gU4)i|hk|Vi2KdLL}O2S!Tek1IUG0wKi|$?S#Bw*{bsx3tcQGboBrT!Gghy2QEm&l?>q%RBTAkct=3{Vyw<+*KZ`@CHnng@TwlS'
    'i_<`n{lkgrHLYNj2p#?;Zw<mM`c*&)dV^64G&ii>5dX(9@?6se19%{jgn_R<B%~c}jA5`m4j98x(=;)}A>ORrNIh{_Be6YwUs3M~'
    'b2#?Ge}h)DSS3NY>`AauBdm>b;B*(4`N%YP&s2cIE)+&M#RAk3dLX<2q>;^rh17~1Q^6nY_{v>eq4xe%W^&U^x@CI-`ZPP7YK)22'
    'd?%}GM1gX1nb#f^)wdiEO`<GKW<WEZATJRyvdl*{DFeTIjeWy%laz!R;xO~ZwFt<CWxKgZU*-N&C~Y8Z^DU0@#{!|WA|S$9F&fMb'
    '27rmOTE)}KZCq6RZ@VcHbm$=%cx$~C-%xxE?i36Y$WT1$Y8r(A+u-Tl`fcE#D}6Wl;knMb9<~s+!P?U-NvN;#W`{vDXn;Lu7WNYO'
    '9EWyTdpOTL<d<9s4S_N2bo*qA)i7U+xCs{+`zNPcj&}ikM_)GCn^v!5L5~7VnGoBOcgRT*%M3>>pl1#`Nf(s;jim5v-@{^CcD5*~'
    'fwD!;nfVZL{=s*KnRR6BlQu=I*J|n~^mEZRO1oGWk%BCMnWT_;!(MZhQ3a!-v~Xsq4j{2n+QL^Ut@_<N<NGCbnJ-irdE~{mN7RpP'
    'l&7miFN>D6fuABt7~=b=yE{~`Uf~kQ;f4_ehte@<8E8*09tjOkA5!>$jRuL;oQv$7zsy4FqaSlM2dEAWR{A7Kj^jn<-_z)Z(TX2U'
    'D?YZ%MVsGCnEB}5{mDCm34g#g3F;klUs`Th1Yl7U;%O?QV?~)x_jwrWR;&(e*dXGBO;e0M3|>cEHVGd*MrBZNaoI<aX9>H-AG)03'
    'x*V{B&drFH(OPEUP7s~Z11(cH_<kXuF&s`NZd28Yidl6^0tD{x%D6=WSUTAzN#DRq7{qEs6l{i;_Df$BBmb~$O{8D|OqSo{pg}&='
    'CwK%iBvqd^2oREY7&V|CMXSjlR)v$SK6HWp%%$i>o;R|TWM~_o6S^m2M5DPdSSvBRr&zQ8uxjNEfhNURJcYb`vgj})3+RD^QPyL#'
    '&WHoh3`VRJapAu$TrtB5t}ga6ILXFQlU4`VLr^k2NI_4bJn{z6_5&b%wDh?afA}$Be>j!q&65|C1!+VlMin4Ot!8qAV?|v9_;3@a'
    'd%DUW-iXwc^ZxLxo*}Xj|McxY3i=~p0_Mn5$TdWMx|JGi&!lUp4n{#^aef;<wzB<ky$fqn2uR7qAJ<T+Oz`m^0kiSkBPx*ll7^5Z'
    '<1MUud&ZS*#j+Q?zr40OlFVhyIy&eGX}`#}zh^cx4rOx&Yi1XGSZmjQ1Gg)-0L}qV92y=~5PdIMq%uiUZV3povxFI0ld3=bs;PQT'
    '+QS3o;mlatfBb&j@2>n}@K5--FpV^v1VP^<pLs-#qMZSJp(C8(iGG;lu*&a{G9H#TCn($dpYe}(PcutR1-puYRzOO2xf7VY!N58w'
    'R;b-NL8KpZ@-+waGF|)lpy8YUIQ@CLHe;xrK+I_ICY~T-1WInw=|N_O_=BM<B674JOW6p44{ty6eL=>LKTd?nQB$CCap9<vrZU}u'
    '7fFu-TRX2Zu9sK$wbjI@*55rWSbL!>g;pGr2X@oc3v?=(fe3An%7Hdv57!-x0hjm>>!u@l)dPGE^%gFLD}S=N{K@9KX~FgMrPlys'
    'C@t7u;w8d(HaHH<U?g`D*8vCyJ`VrvqfLDOy$AJW59L6Jx|)h$1UNSm_>ipNn}=}UGSq@+?`1~CfW7y=AhldS1^<Qb^!tA-1YJ4G'
    'Gdz|GfNIDi!bGy~U^L-^5sCapLfpw#taTo)dHUb`|COJXc<?{{>2m>t<zj`O&-X(iBrG=QR3^U+#1lZy+jj34r03OXlElvs7j_0>'
    '#QjTIeu)JkJP{PN3JNWRgsACP_(c=%nZ|(-5#{T<<j?oky!^GK_)HS@dBF{|0(5A4n*EHJi7+3Tx6o<2c~e;OoaKL77<7f{+e}S`'
    'Gsgwj%I64iqbF&BDuz}`{w4@g;GCwq^%6<&^$)gNP6w4DUTx6RXy4-rh=v=TC$ceo`x{X|-le3yv)<z?a})~<#cuNIih?(CU6KhR'
    'LxXij_Ya8$CKtp8xU*B;dKjdgN<&8njY`7sj~~Qnb2!U9UybRYfFu)?b*%=%#t)BV+&-L*4vwEbZ)eQS!R^j-+g|pCXn+$Ol2m*Z'
    'v5iHg4CXCAI6@MbJeVR(Wr7lDMa9xutIUaDv^_K7Fz%K=C{`UfECR|P&82zOc`2AMOYPs)PyKDd!vZ9ijIkvyjF68T`Ica&j2agj'
    'E@D{BVJX~T#WqM=nq0Bs>r0WDPifdeKnL`kM0KGpM_jjR?Xw9y6tE?uk{bO-tEDW1ZRpM4NN_p*N4a$s&!m<67cvM^A7-KgtPBWL'
    'xL2Th_mY~U0Ork_RjV>KVOyw~f?V0@NFW(yNp1~F@J==wn#}~SgGq9|Y4WONix*gwjGw+0r0Oj03I+-u3Yct_09u`xahlp;)+~Ci'
    '#joEcsEq{s%gvYJ5FA)IEL4mjX$X%=eBrIq=ln3t!W(*6j>p44Ux7L1?Rh|R#mgm~hlYt;H$bnvP~?mXUjwxZ6{DOhrE`cMKjn{B'
    'uAzw_T)@?ah(Mgha*vw@;}_CE`J_nkg6%TyRqg6u{kasFxWHiiX2~7t`x{P9#Aujo34tBnomh2JzhWc5cHxS-wE`(+_M-W@Snh%5'
    'Q<8%6lLw;~9u2@AV~^j(49`m+kFWUw0u0&9V&C|3@+G+f7k0}R#GOjU1WBuvg8-j451hoT#|5pC_wiJ<X8DezT>zchdWSIs!T_(y'
    'J3=|AS-Dz)bXqPTa^b4wYOXjSSNNDraADf|jGZp=inE0NfxZbyK%h_La1|OW7d(|RPpEyUV|k6JapdaHEL5H)j%zx_JWcwD0%JdX'
    'hZl_DoMTtyMC_egg$sr|e3lJ4<|cp~l=;Mey14K|s5ETVaxYxp6oZA~3hkoz;}js1XH>5oE*k!xxltH_EBqQ6=Z;k?zUL0`Q=Dhc'
    '%g8T)hRt|D&Id$%BN)(%ODQGdEKE66Ep{FSR3Jeim6|lH8Pn$hCIx6V7(TTv%n3AQ%4+#uKRgYWxc>Innz?==O{1|8mO6<u%Oy^S'
    '0_z1(R*Ev=z3j!0A1_J%vsFBOSU#8In|VmVD#nazZS&@6OYoWS5c%Q!4-AB48yUy&>AKacmd9a0DkE<uo-weGgc`;S!Idz>ye%x4'
    'IWSzVAUf^(rD^J?{d}Fnj$%{;r{%0ghfssx@X+sw5WsSLXb26$qN=W69hu-CM^O%6UJD#hhKvzuA@<=dZSlKGRE4}=h<_w#G=voB'
    'yI8++MS3>i(kh&uYLLzdt%6y#rxXQPY%2z{g&3O^YqHKi3&aVk2r{FACMXC#v)yC_)Grf=(Twxo43cst<+Y1mWaEXwO|T$9lM!pE'
    'S|VWx>Ib376Zr`XRqhy)nQ5wDTp2^<7%_rB`BEcShyh50i6fw6_)aS#FG(pnRd{N)esQozPQ}Teg<XFZ5SBsOQ+(?Y=rA_PX?ht('
    'luXHOHDZ~n2X{Byta$LdmuIbfWOiy{mK}yazR~D55%Cz-B^FwcO(ORKG&tG}fDfFp`n4~&(OFton43o9jl>A=IJHbPOJ1EgLDDqJ'
    '=>8Jl*xj0tqCek!PuRC5?rbkCK-fp8<1G?qk39p<l&uOr{MV4znSRBCmp|qFL|}OfZVwAf^V227z5VH@vpDzDC0*EF#H!o6HX8%}'
    '=+0-zUC^9brT3t$%(&tsfx7^k5zzz}p8N0L_FoO>%B>He&1hUf^Wa#(KMH~p!D#4sz*oktgOZ6$tgG1i*#+~1VEU7dJQ*YXT*H~x'
    '>&1hKi6>|~keo~3tASTsAY;uZE|n2F&86c|QHNzYZF7F8Fu^RC&FN{ic+_Z!XE|rOM>%FSF|8VGqhG;Y)G$Vu#7kz^loJ}qMkXe|'
    'K&+>;EN(wMQkub;8NjeB<N_A8pOs`A&m#Z>35Fo3Iyfp2+M=kuw2nTkFwbs64?)Bbf2jFgc$Ly=guUiRfLMwga!d8boF+VjJc*1?'
    '2j#>3{CIc_o6^r3G$dWD4@T4Aicb_EL2tMbaSh`Bp~Z}WL+(C2SQ1=4oWb>sIqs*lotNQ>r){CbN#aVE2^TapK602uHYsB;+8BZm'
    '8171f2MpcTE?i9JxZ=nkNSXLG>P4yXG<1TVDRbZ_;8L_$_tq}>Q_Xz64v88&&2^e4%*x?@kalE^UW$_CISoPLQ;kFI%0>7GkWlgn'
    'N-WWIIg)_vNVy?HI(hsVm9g{t7QoAb%UW-iGoSp@JSn)8f~`|qF`!Lc`c{$*VA?Enn5d)tqSwrfk3ZI*mn62nbr-M0?1<taN<mG='
    'b8AGSrRk4YZD2to>IZd^nsBae(eDc6>!%XLqtO&|@NS%CM8cM7C0IXTI38ruRO0jG>(;D*S}3rn&oL1brA5sc050U-d_)WS4ZKDV'
    '4Z2v}f<mC573~T#0ZiVODF%G98m;OyS*n#=qsY88sL9da=fc0Y=E5VcX}r-Jq|D*t!Nd(M!X!~WZ79ATfFABFOmE>ay-QQQvTk8;'
    '0vZF&Z{iEiDA)l!a3mQ~lcNzqO+#uvQO6JKmV~3cy`Be3XNmbHwX~k*B#sNPDKD0+OlsIxLn>`vx$Ik3Q!uK6zmG>EMe``CI8MTt'
    'WD^x>0g!ytdhi;%U3qMZzzDK$<`iLn)v1>uH6<9{EI-{I@KW>8prDyhy;_kl1VDg>)kxRNBLyZLBH1IPF!&zge`(kabA#=w72liO'
    '^E2d*y|@PTFjf$8S_h}E5qFd6qKrz0Y6p<OBQ|x59!WpL{`!ncAUlQzj-r?8176w)aH~aah7zWGhLp%p^Qsj$MbsI=5TlVYoU4d^'
    'Dcot9`s0*Bnu~=FWgW2W^!|{_!m?FtReGr)ANZq?j={sC)9So37*s<{qteJ}OyBLt9qad(Uo;m578>;i5FbDyUXSWg<DV+0QCj8%'
    'E2kjEpAPHRJu4cnCrSW%6yne~9r1~&NRSQjIzb~v4X26MdLC_8d0NkDC>+j<9_e~E-}H;uxmRweVij&Ql3aiq026pZd~!erbLBxQ'
    'Mt@D-pm&fI2Z;y(F??Q3%;D<-b|>X^i<a<jAM}6ykN*R=a3BH'
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
        # tuple, exactly as shipping_context overlays the reviewed templates.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','android-owned-npm5-sync-ci-v1',
                  'protected-producer-original-default-v1'}
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
            'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','android-owned-npm5-sync-ci-v1'}]
        previous=next(row['workflows'] for row in generations if row['name']=='npm-consumers-sync-ci-v1')
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
        if future is None:
            future=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        endpoint='.github/workflows/pr-metadata-context.yml'
        approved=[future] if endpoint in tree else previous_rows
        matches=[row for row in approved if row is not None and all(tree.get(path)==entry for path,entry in row.items())]
        self.assertEqual(len(matches),1,'source must match one complete reviewed current or installed tuple')
        if endpoint not in tree:previous=matches[0]
        enrolled22=any(row['name']=='protected-producer-original-default-v1' for row in generations)
        codeql=blob((root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())['sha'] \
            if endpoint in tree and enrolled22 else '3a273057a38255ca368d3028594fb94227ba7c3b' if endpoint in tree \
            else '6d55d0fe4e9edc86204c66e1fa3967681793a2cd'
        self.assertEqual(tree['.github/workflows/codeql.yml']['sha'],codeql)
        tree.update(deepcopy(previous));tree.pop(endpoint,None)
        tree['.github/workflows/codeql.yml']=dict(mode='100644',type='blob',
            sha='6d55d0fe4e9edc86204c66e1fa3967681793a2cd')
        return root,registry,raw,tree

    def shipping_context(self):
        """Use the actual complete prospective installed S, not source-only B.

        The native inventory includes the new reusable workflow's membership.
        Its protected certificate must already name S; this fixture never
        rewrites that certificate to make the shipping positive pass.
        """
        root,registry,raw,tree=self.source_context()
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        historical=next(row['workflows'] for row in generations if row['name']=='protected-producer-seven-target-ci-v1')
        self.assertEqual(historical['.github/workflows/repository-checks.yml']['sha'],
            'd9fefd275d9e3c6977cf9350a1945a6bbe5051b4')
        future=next((row['workflows'] for row in generations
            if row['name']=='protected-producer-original-default-v1'),None)
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
            expected=blob((root/template).read_bytes())
            if future is not None:self.assertEqual(future[path],expected,path)
            tree[path]=dict(expected)
        tree['.github/workflows/codeql.yml']=blob(
            (root/'tools/repository-checks/workflows/metadata-edits/codeql-metadata.yml').read_bytes())
        if future is not None and tree['tests/platform-profile.json']!=inputs._AFFECTED_SHARED_PROFILE:
            # Source13 keeps all original owners. Only the installed Android S
            # fixture applies the separately reviewed exact six-file handoff.
            owner=json.loads((root/'.github/android-owner-transfer.json').read_bytes())
            targets={path for group in ('legacy_workflows','source_contracts') for path in owner[group]}
            self.assertEqual(targets,{'.github/workflows/android-tests.yml','.github/workflows/android-vr-tests.yml',
                'android/common/tests/android-workflow-contract-test.py',
                'android/common/tests/ci/validate_ci_contract.py','android/common/tests/ci/test_ci_contract.py',
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
