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
# 874a83becd5f3a6af6e5badcba6045708c239c75 / tree 386f7a2d0c98871a2ad0cdce0a43dbf755f54239.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '8c4415ab43030f6cb7cca883079351858a5de13f01bfe44353ca3760d651b530'
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
    'c-qaK-Et#IlAZ7M7<0Xx%E*lT+ozDpbPtPP7P?4)1AyIKySDGH?<7EW)eMP<1ZpL%X}71VTN8oI3=j9?=N$jfzy1Ajd;0q7zqnmI'
    '?6>h@|Hm#J9!>|hJLYuw`)|kn?r;D8pMQJa$Mm;<|C?!=!P>w5+ux2~9e>-ljp2WK(@wzz{!?SdoKxpx=!YguCO2J<#_<2)^!-Ku'
    '1^#L8|Mp-1_P(rVq44$LW&gAd-wUgG-|^oyq+uSL=u()5aST2+&Di8_@Uh9`U|lnPzS@fm-`rz*_+x+gmY?>2JUk|TtvhY^yJKPT'
    '5ayh0<K5KfHpS6dGtXmk-VC9g8k>jEOwHJTzW5=%?2p^i{_y=Fd`;n7X~jO+vCTZ!(M&nUIi)n`-sZ-}nIAe&u4`@b_VX1_>3DiL'
    'zHU$HA*PqKi)k0OskE+d+98;J@chbd9;d-~O`fLCy52`WS>sz?xF2fPEv*%Y-p_5;XTpD@Yn|)U$b;_eG!M}YgR$Q5UO!*!?NuIm'
    'xreknJ^bU<J#F(gEN}Ji-=Cj8Uw!sD40#&c&YRrNwjJ_pI-a^8r?wd;Yu%Xn#H&_6?0-w)^q}8<yuK`lrE6X9oDCtTvG>OI#zr$b'
    'Gl#|uk$28FHrFisuOHR*rQ4jEIK*y_rsb_RO*8Y8hd4&#e9wm*r^ee4ez8BW9FZYBZF$OH!uHE=Y4>frJAQd|de1N4KVQ`t7pxDV'
    '_14<aw|0sg8Z-7O_7lH7_sNW7)2><dg<sAKzrL=`W0$N;<J9>kj4eMdPu}xk`P`1V8K)+t5Z0}`_t#g=E{{#%GcuXq*EX|j+HUN;'
    '4Re}o7_$qmpSo4g`0%>Bx@ItT7>1bL?Cmu2^W5AG%{&?3C7)UweKV$<SFNcpc@w@K_Rnc^4EvYszk2Fz)9_>+U(*n#6w>Va&W#Np'
    '6|t)iagLK&_pFy4?A&uY61damklf35_jq+1kweR&PW@nsn#tJInYra42R}4}>8&NCa8<3}#>?|2?00#4eSOYw8m6uvhRL|)S{%Bz'
    '>4|MqA7jfs5k~gdtzKXEa@_p+d-hk?_k3rKwXyF<E{VS3N%U@RLdy-w7uoR?8t!MedVRh?uF9)xr;xkJ^=%}Y<!<z0491(Taok$L'
    'wPuQ)9h!>Yu88u7`~GE@PKtD!!~XS@HgW47cl+aM8?Hy2ZVuei$(la&$@2Q=DJ93%+4MutCm4O}NLl99+jxyHR~K%laWKiWF>#}e'
    'an{pkCtRjEwj6}aRcF&URxf=1@Gh$_iJ3mZQ~L9CJplC_c2bkJ>$|Dzk~Y=PY4m;MG|nj)(wKQDhubGdUU=F+Z^Hv&@AvJI8<hk2'
    '#l6PuX>+;pbjw~nk$s<>jji)3b(v@wqn&4KC&ffF^m-XQnepb`ET>Y3<H@~}OJ0vs<IsiJ#$mR+4>Al-+?=O&&Y5JV$;PCHWUIM-'
    'Gq0qR*CS;N&P<^lrrh-WcGrh?<Z9rUknZ(U?p?H9o6OC7_?8a4^t4&t($$^Jt>=NnaR_nr-I#6DW*^(3H{(3yA<g5+_uJ;1ck=9Z'
    'q}y>rj?brj_`dnNJt|kZx~oPP*O2Yxn-mBmW9qrgxJAhoOvetJ(ejjT-__ppFa2H!W<yZr5_(Uxw7wljzFyZgu?tg|_=1RIgZ}C5'
    'yLh=&9`0#5)dv?&*8|%W?bMF8orX3~15v&2yD`Mc4K1H_YnwTycJlMhTOy~*Pus_@r|MWcj9n(9YMkvoS4-lYo5_q5@kb9Rb`3RK'
    '9{n9#Dy3UIfSyvb8RxF)hITTovM#bL9?8txYo?CkrHwalfwUtM?6$vius83I=z12wx8i&=XX-beK{t&Pao-OF-|VT9vkAnX=Jv;O'
    'JaMkBe=IYf#;B$J+)W{H3FVpZHt?WE%E@u;yScyP6rJ4RF;(9JnS{4-A(DOMfo~*nu#FviK9W&Sh}zH0O}hOpowL=qtHAGHchMCB'
    '4WG%(heLYKYiYnP+(2nG^h2<%@q=xgp-!;r7wxIydg@X(b3glG?rfLl*oVev%0a`IJVicZMVyeEJ9o6)QJbnT7<%&e)^K5RF-~oA'
    'E+#+mWmDz2uIu`q8oIyty`|mn+rxhM%)fYkb=S+fRydDPg3f#2hk+}?yCK<eNN(~i&x{*AcK7Y6`WBs>9bHFNF#?%PU^LNE-I9P&'
    'UV3uhfdkKu?62F-W=j(Ic)mRfnV|O*A5<LM&=80{FU!wEm?tiajyuh#+_K&KwszAk??(VF5@Npb430(?5>zKnb87;*h|RWhaSp#|'
    'YhnMq;3TC7He{E&nMB^shCr$JIgvCIzS->%jnCY(Qx|{Du8!&Vv@2BAl&o{;^#Um(2>=bxYibPFN86<dG_)g-yZiQ26$wZW?c51s'
    'h$+uu9vnBWYX%N~0FX5UFVs-x-no?@vZCj0%{M*+9y$RGUFxX0#uz}<X5$@@0lNcfOC~y-@7ve<)QI=y$Qi*wdfy4=$_+S#8CuIH'
    'K6F#d4sDbDz560R+Jr*_+dXaF)3JaKP;yz@a?wt+CvD4_hozjrc#>Vy1u#G=*Sq&rlM-}X{(Lz64``7yhBHrA4Wtip(@g^fs&Qj%'
    '+xs?iL-s}v>9ZNkFmS>sn_ZvD{>MIBlbqqoX}JeY8}8fKasPS%)C&8r3EVnd&*oS!HWWpUCnJ<Cf#426)w4=~9OlSF3qVYFZb@0?'
    'rlN!eVIp4x>}$uK$}D^CnHJO~b}jh5$%Ln=nT-7v+sSVG^jZLVCp(4YQtukuyFkN)#zpVQSwhQW3SBqNG*HZ)-}UMFC2yb7d$o4`'
    '_>WxrL+7Z@fP;vb1F#H_#gp$gf@JCJwEb}B*L^y?9#7mP-_rL(2^!_hlV5Vatxtw;dgdL48KAWBhL0*u*~Tf|QxUA#jI!*eGb5O2'
    'J5QOnN5_MXm-P)NEO^`XGgw63^?w1WFaPBFZ4o=rKt2o5(Xr>gprCKaWP9U#5?L_XehSl6mtjA?F5xa6p0~&2(nGwOjQM${AE8D^'
    'o|2DX8Z=8O6FqGvo2JmXNX)7G$zS(+`}=(<;Ol~>o|xP`+F)tRwuCn7^NAZgHYNhcaZKvgJf|(!Lnj@qmV?*P{)oz=0KSs}-~u+u'
    '+&R&7>><|WPdhIE-_yp$=k4{Igw6)Z2l0>A<S@|v0F{V2I67PWzYc)QQZQ5&1eaB7z{IBE5~nOvfi#8`1`2!2i3bG{d=x0x2m^KB'
    '(vK&pI>!i|Nv)^Ir#@8GN(U&~zNbY^AFpfL=x0Fq%6jp~eoxI&8fga4wu`X?<?lzU0zb`U&-8NXi>u8@Z5GEBi=PYAus@{DZ(NVN'
    'biIa9XeF4@=deSh`Wr@2=DAVjKGTdEs8e0Yl^ETRJ9yszo|a;iE2wZ48gR*xwrb<2&I!gPts&{u-3Tr=Q?-vY9%fg+hjmdU1fF=)'
    'ajY9!Uo`2d6HM-mbDXrq1(cu)gxS}xUm03V%+!vPQ>_h-GESU0A#NP;iGye-!aI3)SHJK%zEnJOY9QV_&D@sjt2La$iCo%uG*?@0'
    'TmWLA6Z)TPm;S4Sy?%$#$Zkk`9I30Ykg+ARpLp;9`VFt!fRm7r<=dCPbo;`~>-FcrxibN(LL(>|S_pLpH`xG6%sodxVH#<)%r|VL'
    'Zv8IzG&v1fAI(mZFS69kdFWdHU~-@fL+fL+{u3Z!U$`6`1$VfP1$oa++N#UStr7@%eb1gkYI{DyL~xwQG-C8OZ=vo<j68qVYiN2q'
    '$Oe(W!ZzUHJL==a%}#RFlV{wpjqj(g`&}KNsgIu`0Z@nYK>Y+oDD@*v6brCIkBRD-=Vfnr7>D!-rbD3;H-8-5%S$QC3cjKI&3qJu'
    '0%2fWj=p#FgsI4rp*A2gxEnqUfTinA*kPbf8(55VE?Tt~fd(_(w$>{|ilNriCJFUR*Czz?=w{c6T#{)<q}XsHS<o#@au9n@mr)d$'
    'yy8B(DJ!7A(9`rDc>erk4=avtXK;c79Xo+L7sAk0R72-q{;=J>yq>=B)}Jn{ss}Rshd&aDH?SHN(be71t5cQATVKAvKxR*=2(%_Z'
    '1h_l%SlYfKOZsUytp1Rqh)+LmOr^)ho%HC+z>%X$Bu%3RY2hF_zKX!<r7RgOwFiCTq_4ID9Q|x#CDKmj1So&vv9!V(xI$x`pxQMf'
    't<T;=4x^t}L77=D>o;=a^(9Hw_%@ZD((EN7r~~e)#l|#2dgF+~6B%8uT=ESXQ>@(Z9^B!1f7rb8?-jC^zU3frN78Wt4+}$3`3KZG'
    'PopsznwX&&C5+eZ<6L<@T(}Znj)(C7nmkh8*#9*;$>&=+b4pZTEtzHk&m_H_CU}FqBDklPl*<j^835&+U!IMF@;gp<Z08L?ShjUN'
    '>$QGtp%RLf3s|5$gqp*`pU9-c?1SVpLpZu|GYg6H{B=Vnb;s(@Ck~uf(!kULMYW0BIKVRDtx<cs*z-qZi9-ebs<<!zx_ydg{HGRh'
    'C9+Krfm%1i0HR0LM1sILjzU1d$Y{58;%A!sH+RA8et2vJ9ty`!&x?={;A?`^HR=Y_WPp(~v|>D%G~4?(wxtbpczdZA()o2{fj(6W'
    'dv2mzZs6raqi#n>!?=Y{2fq-)xtZo)u(KU^))P$+cc9gG{VPjEXb%=m*P2uh?40OHn;%HYLye*4rENU*zQ2E0=cI=i@k599`lad}'
    'B(D*0k$2Y+s3He4&U|Woaj<Pc1wj2LfB)9j#I8u5!MD$c4}YHc-A*+9Avh_N(m+<%gL=*Vf@66}*SF70CHv}MzPe+99Sv!6Ak4G9'
    'KpiVIfegt37()P{#O1=F{Sf>w_{PpxVHJEm(&r>ffbE190CAia$TTM(nxPFMskJ<~Cf&cO<Mwf3M{JRTQ2ACI${t{m%aEcEK-&W1'
    'PT5Zrhk@2rAkpQ4fv=|jhP^GBPDR^&O3}<}uR(sD`Sz%WsfZF-Xitd<8!1K5=U;FL-h=?xx0C4~!vY18CA9$>nt+9dcAzepdm})a'
    'eknJ?joW$K!<TheCH;ODrT5oGFSu&rW`d&(Q3C3g2ekmTHRH{1@qJgzMOk3o2)crt&3)*IQ<kGh;th@kuIt-QLIsG;cR!y?h`$c$'
    'bZtwq#FfK^3>5-|6+R0w9teS`4y}9!?X>;9d#N~PEsPqG`k-Wtpp5W#>9l+DVbl$vo57Kd($606-pZwZ`1!CEB0!^ZDUWncoCjj>'
    'x@L@!{xknp#|u+O1pxfst*zJ+pdf$`Q4zkDC86>nt&;y4G)?q%k{<<+H&?33xIIWfblF*I(_1TI0c2e`m9gMVHzzlNZYZVg6lUd9'
    'a{~e~bYSA(<dijT?AGj|RK!xHQG~QpKT;l05TMBG#AT+f6p><3P>yKH>VJ1-qltcRgPOr+dhyVOIz%TkH9TYsQZ@+GhAxDeKl(Vi'
    '{@gB?P>a;k;D^NJR20+u2TkOMAzBKMUOZoaGw`B6VsOTNpcW^~bWdM4Q1yS1Xl?Y*3jI2k<pW0l*6Kb>9{j3DQNq_{ht7*B-i<C@'
    'UsjaE>zK?OGqiL10#hOpLRATamWta;yTUiq5%B0`b=Q|UCp^o4F7$fm&i8^@eD24gg))d1YNTlE=u#>ACqy&xgC8aMEA51ee{qM?'
    '7UdL)^1^gE6*%N%=Mm-|XfRg^a-7BldPTj`V$mwwOuLA7+0`YNFNMUMzc13+jA{WI`Vf8t9H|CAYixkrhD6~$g&s8{G2o*+_Fon}'
    '6GN_lCr-#--!-t*0DMQ<i~|HHzW8pY8tBh;aVY%0qu)Poe&^PX<&*{(bEc;5Iog0DVEj<Oz-lrAN#I>iW*B{(KWbi|vz3^B-|8(='
    '-@Tl)dQGC&NSpwTM1Um+K54NDRTpJGm!yaP-b9+7uC!=$FDGedmI(7NEAsUIdagXRhSvx;Y68XejxH1ZYp?{u=s21<ft<o_uUql>'
    'uBv{aD0u(l>w&FRM-?qGpDsNOL_3gIfY1#)7-0Z6G*&tv+>JYUdD*@`Z)!FY#MY*pl*Xlv+a=`2kyx(eOtBtXFcb#YuiQx0Lx3+c'
    '&|dSzTPvdI2pG^pjv)VV?cl@YP&*(sT)TGIKXJe8&nf(c_E`S*J1gYgqh>=eOo2x2PxAtJT}(a%DfE~pvi!JqHw$3Ac}z6iOD#u;'
    'UQmoV3v}}dYgYLfj0QU;B+GULNd|+XDy!bY@*PyY3n&E<x>+WmiE7qc$W|GRPOJ7mm=W&*OslPa7yo~}13DMag(V@`PNWqu5*y^T'
    '{LZKVI1*}Ur&AS=unTCtcC|~!bo@s5YO@coPuoAMo;|RtmZon7bTW|gK;xklr*kq}=;d&kATXt|zi|tXFRz=g@FSnnu>fn*Q;Zak'
    '=>BP!(Cjz1BQXKe>C{_m;n?vuQu7P;0V$g69jbeQXGDvJr~q*c4(X7y+I~?bleh>LIXUW@t~0-8LkqxE(To-t-b=U9q2CXY&M#_-'
    '9u+cDg``)Q#JlQ-8+XOUeSjHp+<xP4-~R4u;zbn%HD$KsKr^WcAk#=k7DZ;9=ypZPqG=(tH}2<*K)CNu1T@u1Y5Um~`!l54K>Q^;'
    'YVy$c>dyC2ND?+4R{1;T3sl~zzx7zH-Vat51df1qq@8AJ30O3!BzR_#8k~?CNWQxdT}3|L&+|Tft2*3nQV)lsdhF!+fWC&7ijk0C'
    'ny4(+0-1jfwF_UWMZev}68n-$Rmw1eSup6*`9|ezf>3`Dc4i2!h)}~&eV$*oVQ;_W?Vl&1{tNhdJ+4W!LqbO$LGMvzvFHM%lR`Z}'
    'j;TS&I>u?;`hQWTs;?EwbSJtg%_CT2>QhrM+YTxbTq1g-qu6}_W$QL_kk!heeiO);D1~IBLqQ8f=RDx5%x;jxAd)c?0#tyP+D-7^'
    'Dx$`UJKid#ic%p1g3TTZ5tl0IC*LQsik#pQ1V>4F;||XGPWAJUqJt_|Fc%_Vig^0q5J%*%lRLz4orTmg+3LIg_dS2RSuBlItrnsa'
    'X;nk_t|J0?QP>)#{47dXf=-G8N36o~+P-qZnZwUV2VDy*91g?`wgw#9TVz>2B(P8}3=}t|1rf}A|BqB9y`tw1%Af<!b;XO$vouaE'
    'n8UygPo`%;ujxOOmRzK0Z*_S=Cp=3*G1DV9iGIIr5{xN40c7Sh(ZJ;|0ftg3;MD1)={$iu831><6|FkfRNshz$XWvUdw<q$2V1+?'
    '@=N!ZcCh~A=KODv89Y_AT?Lx*=|(DcY%oTMFERk4T<77#P2yu~A$-K<mhEhJYW%{v@UQr89X2no{*4QBeNTjZE?+=g&<WtX0N4}h'
    '+)bDv(Mlf$<9WFGckM~)HuO^IiEF9ET*I_PT7&_30q71`DnRGPCkXXDFiqEsz2-i$L|U<*AKEvh2RWU#&)2Uh?m!sq=tn4fQ3va`'
    'LITL?pySH{lE#euH@aJP^~BSm+nY+EnYYlWNslAfM9mX<PzII|MF_1p3GM(az(dR}dw5>jfwUw_d%&AZ=nDuB02ApWcpeuv-wdW%'
    '?1xwk?bpX!_8@y7_Hc+5&mwU%by7Uxdd8Om+zvYi&Iy(XNEzaQoB=>0jJNEA)~KrSmsfi5RUZd6_e>>>(tx84#SmsADL>90?1*;J'
    'lyz$j^GzSe0@iHK_tyDjUw=Ohck@6!NcIYQ%L^m}%7wE8B>)Cs&{vagJ3V0Y`vU;LWjFtLekzdaNM?|iKtSX^!4Qag$KwA*l?G{v'
    'kk4&O(H?)nR`h4rF#{}ChLL`CS~z9+5%E}vF%V;6j*n>;&OOE9_PvOed31a%1@uNJCg``3CIwLl*cNXJ_?CQzjAp{u1bRtIw`}C-'
    'o?p<U9mNkmxAsfKef|bKkqQfsgE=JMlI>?I9$IL=hZG2-nvW*k6#Gw7rpJm3z^di|HX7-Pk9->RSLj1HfCQMj7L)^o9t_amvWfHO'
    '5uPZ-uI~Z<m}DXm?1;|<0h|Q<Bgik156yDGb$EAU{jmvO-RVt6<4(o1BAzfvwm8akmr1q3RRFrVSs<fweq|Df-A#QsdpCK!SVsZj'
    'ek~vb5E1~m68)YLzLnYrv@2mRAZfv-iN_&GWvUNiXA<oBcG-KWC26LLsODY@NfOjgXxpTpwA}kJ(W$}ng49S2RAMSMdDr{;v#J;#'
    'zK5rD$=gEUgeZSIeO=rDo>I9klMWe5!q5=9xa{aB0)j#o(Cq_>gI*xWfN{TQPZh>qkVf#)LxeA9L&7Z5{{ZY|^`|oxG=L8b!|9i7'
    'C~k4xI~5r3EfV%XFO5d8m(AB8qE*1pGr=C>(}H!CRmT029Uam?UQ00_GP6D%A{>5Rm^><}#1V)CW!1i&klZ4SvE#iPdfGp3cU4%+'
    'K%0y!FzJHE>XI)TwAzyWi!F;iB{!rM=jGlVfqopN(b$Dl^)Z2N2*F+Yh;&PNW3w43ROlgk>}|aS%-l+MKPeiH@2ct2o_IgJ9cmI<'
    'PFS!Kj<9BRB3?Gi@Zk4mQi>Gs-P19hxTzk&c6aXO_;p{{6{1}WR}f^Ee&--Z6}`nsu4%=vh$4tX(f(z-dVP7?yX#PM779-RkCiBF'
    'UVK0(MIh#6h|hGQh15f6vO|0Co=*F3X?LN`UQf2baK(xZ)GMwh8%KCZG=h$U{AunGytmq(zj;G39)!jpQqsS%D{=(6wkR7>zd(5b'
    '&4YJ3$<7Y55IBvKZMkBht=zgD{(%}5o3E$SOI2VZB+@r+7hVNk4Fm%V>k~o(_X`|LT&M=TTg`CqhK}K|eW|(n>1uhbo$)3KJ@q9T'
    'RgynISiC|hzi|hVij<P`jt!M*ru0aR90;f=V@qaCB};XUJpvLfd?UGB5K;C1<^v!1&yF~~TpxdVeP55)hVRs&jDdx#oM^$w5mv&z'
    'f&NOugw2GEo$lPy(^gX33bc+gWwHrXvnTwakO9StAj24`O)aV7BsC8a$^MG{P}QVu$p}aecCiP`<ANX)LD~lUN(T)S83<;r8iKS='
    'n>#loITQYJRS_C-A4~}dJ`HCY%$9NscoV)4M0vTVMY3wJitg4eof${(XY2>X+4Wb~%cacH2gHQHkw&8l9o4s|$iaKVBlDs<ZGP3Z'
    '^jD~i6_%`|B)m2`S>fRXGa1%m7(oK@1)F%gAd@J$yXhD0E0^tU<P@Di9Epz75?Q#)GP@`9hKNI~1dYUqKHRw>-KrH<))=!W9A#Lq'
    'prL%w6YYpuy*SEL=sA#*)E+W-?&i#LJaFhvFd&P{3RtcX4oNjEN>+3NNUw}|-BgP>%*i?lhYOgdckb$Pf4uH09~K>3a9Q$O?si8B'
    '%iI7r!4nbA0|XC4A2<P<(p$InxIgX1DJS8+?5&V(Lu8lWHMOX(tyqo_Dj`sK3IJM*BSbkEqc=xyAq(Q;3bwp{#ys8|Wc-9?8m*#M'
    '(pcqk<ET+I0VdPlr170^-N@5EE_POD^Qh~HkChWST0JNv^P&OZ(tuV+O+?#Ua~G(riQISWMa9tNC0)XI)l~xQV1#K?yh7Dvjz=d%'
    'uB8#dtCBz2NRdQ!a^J=l5p`TnTG$s`5lYZV4<St8XFEdy4kDJrxI<J(5vNw@0uJ4}rwc6d*JCPgX)rStEb}2Gi326Ua3PDjOJ9~x'
    'nHZ^$+T31%uqt+Ym-kl*j#yGynT`myqd9@IJx<M|sJ6)OVWvU#71{jev}Cte<49;8`gfjKiScW=&*1$BaTU`dR1l{i$*?d0*BHr}'
    '@WQ#d{@5=$<hdMzGy7VIiYRI@Vt`0$WK2eshCeO@LXF3yDGdSeG2MK_0xjyZrsgMP*C91PR!&yQ(ti^PaL1wPuRlPs7w~{$o(=oV'
    '_w49m4Y4_WmFwR1?O+Dns87MNB#UxMn^~W(A52sAykN(mXuLT!x|C$pK}1Ighh@@%w7Hyh*!N&oGYK~e20k6+-YwmOmTYpQsd4i?'
    'w%nw#?(S&0*=Y-4)`nv~`7601AT=#{y4hH3(fPvc1lh~&ds*&yq#d=V9Z{ks$LHNp71{vyf&Vz74=QW4o^&wCKbZG1+_|IQpDPSL'
    '<Q)R)!r-SiwcykfIW$b|!DB0}aVwF;+J&3*px-AYuD=USE2Z~cBlgfN$hy<m3znW_56PXS>KcD(%B0!dv6J+t`0{F4SKE%V_&m-s'
    'cwkl&4tm{E9Wr!>o0WeRp+dmy?w(C;m#33zAJc4*ZwI*|L#%<?A`d(mS6IYZ8N`5r$dIL*@7vM7q8?-1kFqi`cbP=O%p-U`0A{EN'
    'WK;y-ToG}+9rDypPQn=WhXUo$Dp~L3>M%my#yb<)Bk?&U^43<BVU`5&j(uFnfT5%}gk}e`7@smQd@O^o@C`J7u#fAaOi?)UC~1AV'
    'XDjdb6cMnH=L9Ndj444lKzWg|3=O6^_*N1K`AVqjxy?D^zhX1x?jQh|)I#XhIn|>O7}}MnR)K#sF^q{Sc!DH<$7UoiENG_)Ws<+h'
    'T@PEozLVKr&?GogW!Nz!U=9xgAMV-3Np77Rk+_Oj6y>m5qBN^Xr$|WI4_#xz9f+NXl0aruJom)j_Z%X@2|?puFnhvZ1FJp8YQaUH'
    'X&CZMcxyCOtR>SSK=ViW<}~ZC+;g)uHVZ<2T(Hq20=+{n13TqKY3>tk3rbGDWI!Le)8BGQ@?fNy082S@YzyKyT5q@yS`9_?@?wK&'
    '4F1Fw$ytV{1L91ERi9hEJYmK2W^l0l=VEW0Ow!4mB9b=&UD6ut<&Ea4sAdwoMh!76jO!^6@JY`S*q{3oZy-vwK?@vj8c8tkKvV1p'
    '>k>E<787(hELza$wlo_06>!BT`&vqb>Rlm&4|-Wx1LGcvl$g#gRvuWxwlcD#;XLyIM|<<GF3pqL{g4U+QF>$xbOv<JX}-ZsfTNGF'
    'l1qwa27|tgxp_Z7vM6geMbf8nqpF^uDAP5N$DpL?I`nkIK<%-!S&?pixGDX!`aLbJZ#V$RyP=Phm;xMvc{K`+NYshcji}|#t$PXw'
    'cl?Si<Zgd*W&Jm>65N?t8VW2sz)vBO%l<XO4x?UxfJ?#GuHeW0({3)9Mg4Ff-k1iJGXIU~e+mO+p)DeDyjSot2hp??TQ|pmpJAuU'
    'P03a$!k$1-2k&2#(y+vDn56`*8!J&VWhBWi#``v<YPj0251*ATpG^Zvj%5tam_96h8j9pmIJk5}-EixU-jS5*4Pors`hf7XPr6q%'
    '#;IXI8o3}6M3{v9bF$={-<uweJJRi55g(~{Te3rH;a+|Qj4LJmqF+j$+GEg9t<JqN-@2nq`AI(Y`lw+61t=br2`)RcujF2W1r6ln'
    'tWmt38eap|77{CjlEdBGIk$86_17D{H@R-|F@ZZ}U31Kuly;J82dEItj?uctr#pAH^ag78q*;T#6khb^5IT^N(OQABKs9Owh?7Z9'
    '<A>vVR_*Ed_4TBLvHm^*Iwc?(*|kFL>Tp@2*~85XaR?O@#Ri%Wir4CWT{g0O+Q+wu8D1A7=@YyKQn>B)<b>NR0kcpCG02RyaSerT'
    'g7B8UGvJHO@{XJ5dv>(<zmYUir4lyb7Vl!g2t$TS=v>jGVa^ZtO@3p9a`3Py4J_hg?v^zP(+7L{>5q!3B@;z?Q<F^WaWcXn1Ed9~'
    'CHRsU)huqmJVhw1^*c(~ey0bu;>jidIlsJ)Mo|Glp=<yZq~jqU$qES|V-w)F*Y$^W$A^|HpKa#S@4h^l%imq<`RiMeelByDF^`I='
    'bE1$k0@Py4LIMH<hyF9v+7)!?PqtD_{kb4OSYTF5=R=(wyqc&G^Th&h<+BE3-`1b2lk-577lQHfpGEFH7MQIXAA#2*Ph*fX9yB}<'
    'u`EJ>#*9;*;U>T|rF(W!dJ;qw<`Bqjj!zSDUDCL;R)b0~h{Ws_Y9c;4O??`D{xo-69boiypl?s^`$D=dXw1YT)&On{<$6(ish9_F'
    'C&&qu&;ai}wfhP()OjCB`P|`Rb$3>gl<H&TUJx)9MF2Fi9AUt;AwX%~dIuF8TlI0y>$ZV4_vYY~1#TYo*HRx{rne|+qEcndnh;7r'
    'T+5B{T80MDpJ7Zj+0V3o7yS3ff)$&*MMlj9fU^s50W-u4rkHirz@J6-OQ*pN!@9-KuRxzc)q8+d0nUgC9i&C9P4FhA9R&*<9wQFw'
    '(&jRR(5}$OU1V0$&s=J{vX%!@EJ9<<uwlP?re(tPrY#;wT&Q#TQ`qki2z$S76BpR??L#Oy&{1e7A-^(uW^_mvEsug5Um4M@0Hxs$'
    'm}%wrNZ$#kr#fk%(R7qZD-OyXo>|nf5U4vfdGVg%9gV2b85ow<?EpfFTP9A{^8*kYLk1)?b0TG^NbjAy9gzxgQUfM1_W#gy?&>xc'
    'NlIA?;*InNxL6?68FWoRK&GZ9c!Pm-jQGI&GUk5eYq*5yA09!Kg&JNKjkKYYChICZGNNq}mVtRd*%Ut-E|OpQM(AmILZwb<VR<y*'
    'Q2DX`QiTOb2hhRHFFLeAlp1bROfPWjTDSb`mQ3$-DtwG++4yyM#_PTW2BTkO(1YS!0fj}R-XOrPi>uc@{;@4}r!^s0Bv8r%DPysR'
    '5Mx(UnW*$I8v*(@(n43SEqD4et?60TC7N51e2wRn#bl|4`6_gs1O|ZH(w%YQJOT`1xotE<p>OZpNl_cbBsEL`rWOXSJjij<)kIh*'
    'LyV1Dyth!2W$V{(L#to7UX|1ehWyMZq)<0%!ZVN!&Uf4wGD?sISSNfL<Y~prktFCrJnrv5r4sn$C8E~?F&Fu8`2BG{CT&XpOGXnl'
    'Nerqkfs|7N&k3dOU~k{mZ~N_{t5`H1oBZS+3%1N^J<}o=dnigNAh#r4^ahnMxtHu<7=qQ_zN51)6t)Lt?qg|64wiaZgOzdlBV>Ur'
    ';VG7-fD!4Nu9{{tF!p`EeLJug_b7-jZ;#mv`2e+{0OioplS^LLNoRtO7~MTCJLa%W8kZpzYmYZcsbES1*q2dFj`r1`g)vchS9A)X'
    '9rB<Nj}_hsWDdR==sBQCjb^O2C0I25Nu9X#;;SqOrOX!2xOAMcJj7#~0Nadi$+lUR01NujRj<miC}b0y!svt11f(bhV<!uIBVH7D'
    'DW{Z@8Q=a=seWlO{gY7_Zk^vshBjH$Sfvs;AA%A<#cc7Fhz!w0SO7bN8P?FAOy&A#w7FmqsOhRSwgBN~fDyUdQ_tWH71gQWu_Lic'
    'O|D$=q7Zmf)7JFbn1(<`z$Jyw1hYW2X5FCd5#5=(HlbbmO~qXLZ3p`UvJFtb;?%KGg9Rw4H7{ASH&IW*eeV~c0xm*~qhbVZF=KmQ'
    '_K$PAxF=02*_Go#M@N&<6HE%A^NJIl7u#OU0XmC`gpHB6FkdT|#*u-O^w*;oQ*(d)rQ>`si3p`}-$7D{P9}ILMZh{?nt)DGRL6B2'
    'ScE)<VOLO{;6~un;xrIMK&qANT$D$lfgQk5^tP#e<jch60udD*BjuO|TLA+Sr10I;&@uWbY@tUK!qnHIsA0PoVyZy>=S$d}UUwyL'
    'HK}g6vp{PhmLuaz8q$eIn(bg)t`SqHgF;dEs&yA+O;5KxPL2$}UnCMzMr4hoARh&-3X-Zr7sC8j(~Fv#Rln~7qJv22s<fvOpAG_G'
    'fE`6eHff?Z>(RQ>VWun^vE6P-jw=?w_^F=l2{vW(ac&@P1o}Kq6RTSxV^DlKLUiy<h6YG0Mna96r2%#G_jSLVReGVP4HJ*JJb<S%'
    'NglrE%<V$`xxD_t7VSlTOS^B_n}2~-0}jKrQSixQW(FfHGzSX$QPLpVpbQ@$0thaV8JZmAqNM3<(es>ejg0i-q~+~nq3rK9RR=f_'
    'YB`t>A`fx^(hsHD3Z2Lqu-pihtH0Tozs;B?6?#mCr;hjj;_8Unb$P_-f<eRZ&F<yy2uer%L@hX1ZebyEZm$~K0?6WP55XSNu@j+-'
    'NQOFtssjF9;>&APoD}7UZ!2C}omDRzXGR)5h}1M18jO$Uodjz@jlp&Z%RQ`3KXiZoeC3sI+@O6R;{@PBSdf>osIYpuDO|5iWytUX'
    'ac-H`Y@y<rqpZNyfDbt>IVM*IIwuMMu~)IEvdr)f^7|_+`^-2oS8bj~rO2!0TD15R@E>q8Y|&GZ5z*<ARVO{vOw+Wq=sv#6R^;{N'
    'L*?&}KXWE#km8YPVI4>Bj2XaLTr4Gn5T@Z+YSwhIVm_~UTr8rGRdp%Gnlz(Y;bk-$7>i)w@r=A@xHOQ97%8ou?C5J3evy)w5e)^U'
    'Gfe|A1!na%2DuJFk|Y!0L)JtM#6<{woGG#_-j`iE;YGnW{xzWX^b8;`5iL=u39Ta;p@JEmpb6yPsmKX`Uv(k7RQbhV4+lqoOwur+'
    'h{>azm|?F%ki_1BHUc)Rc!%|sE32&7mbuk~{1N!08BQUTm6l9T=@2Hr^2Ou`<N9mNT)XJPqj?kCpl*{KsQApuzNpp6?63fXbIBYI'
    '*mEehQFBsMkGM8aLz*Iy?rjqn`V6&WNnvXR{BcWyy&_;itV!pb_Wht<K7)?+^C>3#b?Yv8EXDFmLESsil7Zue?c$`^Eo&e?Fw9~{'
    'iJ{~YLxL77*M3tKl9F9tmWz;)Lz-Ml&yrs+-ifp-NE{i*hc3e)42x6cvia$I!7+=uhhW-Z>;z=cJ#w4@OJ&;sB)uLLD&kzQg39H#'
    'aj{@>->wGA44_UMUqiDS;Suy$CY7iYz%EbQ$!?Yuu=aC0H(Yk<m2&ZVMh~728U~C>`<IFtzd!jUquyprHryFX3R3LZ)h_(o>+|(*'
    'sF$swW?!RHH_{^DH;JHkP+ltoM!d*0zh$Ug?>vNTb9@GYxcY$U;y6h^rFZNwbQ+ikJWJd}N^F4Q6gNl#a_zcr^xN{QHIVEC1Yl%I'
    'u;e2`83Wcr1w(`sZ5^w2W?Y2TD_2G;jx3!MSO<w8ZAmd?RNB%0W~32JTjboR8gtPP`+fcW{#&7sxio9J;IX2grN8lrrt#IlrWR(H'
    'IKPbcu(eS_^VSQBC=QJrk`ZKc@gY{jXO9~IIGjj93QKhk@7mU`_xg0&E^|t+mxYX8k_WA5c@ppftIcZRYyKu+JjTtmYuf7X>22_5'
    'b}V0~`~=V@G$r{$3sTl7D3}DyQo&^pZ!Rzhs%BuH${qaRkX*Gq<BUje@Zy2+i<_$aXocVb=5hNap)mBsn8Z-I{KXd;XZ5Gk*8&<K'
    'u?L>CI4Yu(p(}}167?zZnLZq@`#nT<q$-sQ9|Q1G0aOCB=dO*AFoV2M@w~Kx9VicAU{RqeY>wTU1$oBBgA4CK9WL0580vF&XtgoC'
    '$;sQFu!W=!oQ>;nu3lG6DzLl?fEw6PYF)}<py*Kugq((nU^rADgF=nX(tfCo((mp?KNwM6|LLe9!Z2!<2S=GN8KFMtIM6BIIG;Ms'
    '7;=KGy@St~Eg<=Kc#hu+89c!dzcO*NfF3ljiky;p<(VMEcEp>+|DiUQzVu_3{3;b>uU3YF<Q{_@|7ciId&|ysA!s5ZB#KfnrrMI_'
    '+~mIgTY09~gJxWZn21EpDV&-yoTLCeT;&@8K>ZL`t+;_RbM-z1fyGx52Xjs5Wn=}H1<S*fZB_YWrZ>>ILteIS)pN$PJ?<;?ybK9K'
    '{moBoC7l|@=uux_rh?)!QD(x`?7HgTjdj_1{p*<z?st@cxRfFN<UlQ_Y7uat@1t?cC(iWDP#Z>GUlu6w^+kl1LPr2%Hjfp1Vma}V'
    '<n)|uY6bcq>XCq?X2q7;o8s)DSywV}N}21`K_gqT%Lo}7qm3v!i`<Gj2H)XiIoFmeXTwMti5^^qyEfC2#3JT9)+~XAD9+tHXf}yN'
    '7-pem#!_a0DscDb;rxcbZ1^kI=9>a(W)^pkb~Ad#VFYc!%oQ82Q6pJYE>Xjv9yDtfew$Qv898$OQ|o2bjV~QH75sC4E=Yj94y*=Q'
    'Sd9lKj<@Zq^)F8Sb=LJV$>PaNd<T<^4(G^>9#LP7ri+r71@zgb=+^hs4lanqlf29iSigW46g)cdy_pb~(GbD<4xThbDt!`0qkCWq'
    'gSh#j$W8cZ4^<2Em}&2Ofo*7O=s7{v;$W-AN{<M~AlV#u!LD9d|8{{Ig0Tj8CK(GXMoMH%NP%=|Pa%!K0!Rcy=His@kn{YQs!vVU'
    'IZXS_0HquyzBq(L$WW<w(k##I0rs<~>xC6xwl4@#N{JYylQ0*rsgYI#3YPMp;TYs49;%|+$Yq<OkH%L1ctMFbf+~TgsdZf^c1D!R'
    'BOP<9VKQt0OrYsv6F?~N%E^R4!Qy4ZbOJ4eg&{Mbpd+if5+W@_{qn^_bM|gn&dNdzIQN?hx*kwTthlKa$vXM<jH74v12GKlBOw})'
    'o=9nme#1vv)X(mHAmhW^&wjW4s~(z&w%f@fL8HB_#@d2{;3U&B5mF-v`iPvxm)Wp28>$(qh=Li1Rs?iZ^QehN4Q-(ABP|9`#-Bvv'
    '3E<1LcWtNcBk>H2VkR?UG&m$`?t{3Y-7}J<bZkm@Ojp!dU*E|x{_(|a3-bs~WYQRoeifpvA_27l9PY%-PUho?iU#+q=o@p{3i!He'
    '-x}Xs1`jg#02gRHY8mp#WrCoo5yIf5t%9~p9O_-DTll2P7qLA<DfASIr3r0cFP~s1(LXKeNuqxwdQ4{F)0`!3h-3BIiv;(4wWq^j'
    '8AU;}uw-G14K{=!51|Ho6_Gonn#Np>Dwqcj@J!N$8g|7dR#KQ|KxXU*G;fmPOlUXOT#YK1UJx{VH%vRr^A>*G!Edk1tZIIKn;4pE'
    'rC^ow70d_teSG&q{-gAe>X<W4V9nwyzCN13vsgt72UI0YBN;SDP+ogrrF07g;7%)6U-t<jLnR1NI3Om%G_u2=5fqAtLP4W(*8xzG'
    'Q9-3!9v*t${4g-SelQWNeBjznLU3qhym3wFq36_~QJ*E`fG7YA7}jp!l44fPLIsRq?s1UzEkFq&(PvuOq|5;B&rBbR%DpWP#`<gv'
    '_4BAW0HbVbD57bAkRZTm1KlP2@|vPxmoX$}?KbLXv1Y06i8uUT)QU140^tQBL){hCox$y=SC8hl9lWu0u9rK^+=3PX<Bp^g=@g@A'
    'g_A*VLnVQoO{Wg9E21_3vW2?tCkg?qPFkN}aWejt3lQKJ2%3dKplMBtplpg#@_%0aXNu!ufKo`kK~3b)!=zDwV2C2L$jJTGK$4CJ'
    '{Ej=(hP$>=!L)=6W#&M&O)gBcowpBd39&ZbfJQ?!m{1H{JDI!oQ9YWK@hVhbv#={H5O8>EWsp8Ag{FyzO&E1??xxk7(S+7b-N-Lp'
    '4*0Y&Ga2pH1T;?6CRSp#N$b{99m$i6JA3sWAolFiV_AF&Ud!{Bnyr=b48u#9rbZqQ85V;GwCddiFjOQ#e7J$5yzEN%1zmWhNT@Dp'
    'gv|0o7QH3OBo^yRCcEJJH#Tu?h<KZ>Sv5tFWu`?W(a5YfE%cLRW)p}TdX_=z&#?NdeA`0xv|5;K8M3{VmWH}<?3Zhtx<{7K8ly|!'
    'SMzpm+{gQ1*eZu}xWJ4;%B{v|w{qk0N+-!FAOX>3hV!N&psicGnR8E{^di7X+GtwUq0k{5NnI#rK)wN*!9M8?21x)KjdOMm3N4A%'
    't^3e$huxB4aZwe=kJ4)&HQO+nMn-4Up^G)`Fet^%<I;T(#s2UodpT#=>}Xe^z=M;OscI-J<bcnsq4I)rfg%y&BQy-YBrt)|+_se('
    '200FfK|>JnyT=QUYmO>3$iN)x3-fxTrfUN$t_@uv^f-H!Iw26Z;EvM;fkjP1Pd%qlN$Z7+j_x^BBWkZctc@B!ixxIjz>h~b4?_*S'
    '5SB556}lsMTqFPMbzY&C6Tm^e`juO$GtA<4U`h;nR2ZrBXi$#N%57!)i+Z246NkQAn``H%?c-Ozh1bi4`V2F)AZP%8;VbObR%P@7'
    '7$V9y12Qy<k<G*i8X6)Dug$U^1@`S^g{tItlMfu%ZBflZkfhU0qZwFz#8eC{hA7sO1`@?u)gzI=uH6bz9Abmpy}t07EVbZ%p9^!`'
    '=p)cgBF%z)1bGy)HU|TDD%c(k<P!R%U5INR3NvbVA6+Fs^|7G(^|D?CmE_UGZJ?)xsT`i?;M}x{#ZPaGDDOWn{X=tOc_C}epc_q-'
    'lZ0O*O)z4mlZVm=`fiVepPm|V9gj`F_Q*mYU&kDW)k(tB7z!T^4e224X?z-YKDtF%O@s~6Vfx$mQ6!BqpM(El%sVDdpwO*IuUS4W'
    'OfaJs5hoJb*y?*kTUe!-=;ZSZ@{Yl?(I5jnX?Z%LgreN_32+xi8P(AZ`&gl%U=a`*+{T29S-9*Fo|#e95IHBs61%wnG~tF_RB9RM'
    'J<(4l4@PB33xZ+0{2$8HStTo`1578v`(t&Lc9!^UE|R}ei3SI1M!Zjr3Tj6<jSSlo_ZgZwEea%&rcV$U*Y05*37bL~&lREtCzG2M'
    '>Kjta#)%_5Xe1F7a6XRJ4}$2hxCvcaq~$4#IO4&)1~UOcBojvEAuyX_n&Aw}Zk)W~Rv(Zxljeh3Q7|3lr9^Omg9e<8QW54hg|a3N'
    '+up5Ce=j@Wj4Fgy4ZWsOj5rNiIxR~0B}8-FyO`vGQcgB!k*bZhOMBZ!UiM2!=Vsf6Zw1#001Rlg`bs66;|)-tf^@^`qG;00`79F5'
    'blXN2o<hxwX-F#ZeMn^DI4EiMn@5u{>B|%+CxN<a>f+jHvD5m(7RA^=K7b$cv49@XS!^^l5Y{4h7aO3Fj{gYbDvWfyqWSsNN9EF2'
    'UDwb?eFZ^;Vl{xSs)Z}6J*;c?HE1*`j7KseGu*b9wXJQ85`mnJ$c7Cz1W4{^gCJ8&vc%v_5AyYHM}OOH&Rm+Rjlc<ml*FY57aUB('
    'E+FtSS8bG!HoYk$KK$xew1`eG`FW-I6m)??QPW8^UKysTA9`^iVU9a)UOc#XI)h)E3chT^{(UFquqv-e(lFK$!4@$a`f47K5%0H?'
    'Q~@tn=DN9Cc5!|$k7<vEPKg}KAY*th7@RP81K%W=TvC!jxDmgc{6k8*@{oxSw{Zz4xOZrj!**A~T$roF-AY4>R47O-!F|Jr%jh3u'
    'NYFzNbI`^!H$9TKv%G>FL$3nQ4s;Z`(V#NoDaDgD@;EX%wQ$fIu=CY<`?8%MNVL@uDV#ToNs4N6Aev^h@dEcD!zH+U(O$B@Alspv'
    'w)5s_PKo_kBbypUK@fGDdaj2Bz{nH=3gx~ka4;e|+_d)GO=sxB@U49=MiWt7gMl7O2-=xk$3Q?)f=G&BJ{sBjHhJx({MY>>$v_=W'
    'hm|1pEPIiCAW#e<6itXkdo9ZhxOD)zFss()jl3P77A#wJ9%G@4#e}XN03lc~c=5mm3AmCWe1eJ%=^5_`XkU!gne6(FM7%`b9|o`L'
    'al1GT6xlzVm|oKgCW+ADPx96v%%Wcfl%O{lq(B>owHxBU93#&)T`+(L5=j{N>O(@>(Z(1C%j1AC95hW6LmcAG+Kto`hcy!0(f1Yg'
    'o-l`FFZ?%XHH%degv*`;8#Th(C<jh=ahVTHb9YPyDC|OEgi|a)9ia!p3qTs#Y*<LG$T1cC(T=a&#T9DrPh}=I&8%Ct7obnGV^obX'
    ')0*#Ob&V)cZZ3K4K~a6n@z5m7(qslS;}P-_5hKZbRFg9ByVuw^EH_C>m>~``Z(56hTv)c7i}Y3QKZVi;(l+1XB!4UrN-F{)oE4+N'
    '++YBhD63UGuiVB(#s9XOB0+~9f`PZzTk#FW$KX!EFo6ukp{}M;2(S&F-mTvT4!Y8JlOLYztm|P5VH>PH&60%rDsOfeG=m1%b7o;L'
    'fzNShhqZ_E%tL-jh0x#`!%nwPrdSR0wTPQ=fw6xYb<6QCfbZzbMtjrhbu8#ffGHDVTk;M$DPoy15)0^=gHF-~Wq%VX{Mz@h*p{6w'
    'N@}2Nk#jO1BF;bf&M>o%jD6OosP$S+{e*rl+D2&?>mrhu1u&Bo5^vaPt}?1%RFoFZ4AlW7HcDIgDy3E5y))h~smpw!!pI{hwmqVL'
    'Y@-}qC3;!3qz(KONx~4{2i@Jidi4sII1V?AAUKpGgO-8z^x~1w@bn>t57=msSmjh?=lo?BQXl=8t2sb*Xt2^JNg6p`Wd1#kZWyij'
    '(X`@YkEv+$dkHh2-Mc?|M=;?J*d{`~WA01K4T}IQXhJ+qWpu14)9F4BQ{9Tyfejl(oUmz%(TBn7h|4D8gU6^03N9}DAo46>xA;Ss'
    'GhCMgcF?&Q(K1=f4BQ!_GkTz93J2dW<THlD$;550T2V2pPDy~k9bOr?hzCn2+a&25SP6qzjfjHH(9(YCi(=#-maT~t41h`UdmJ>#'
    'hx!DMV1}gXvjzb|@(!a0)T3xM`NOJklGTSU(4V;!oyhY>mXZu@<8wmyM2u)O7Y1u3X7?0p)*n`_ydlt}7>lQnlTQ{MW@G_9a4^bx'
    'Y}OfZ0Gh#wl_D<uFAG=9aDuCgy$nvWVbY}40rn7-3<pxsQz%co0kr)92%jx|uEigIOxPbzrFrw@#biMm(TPz7$Wg1A+~8P2*8o1;'
    '#Oa={@~1Z<HD%r(p4Br%7UG`1|3^W81Wdpjc?!9P$WOOYgYB7g4b{OYXe`ce!{=7EKdyISO$q@infT)xDwPR7{u5v}o_j<Ea$nLA'
    'l4QJvRc~ip*;Xuj!TZZ=t0T!=#-yWzj*#|?Z2Nm=GviQ}6Ie65;KN$G_8Yieu?27rc;e9TsDkKw$s(0WnsQ4(kewvVNSajr=~qqF'
    'bJ89jC=WAZY5)G)algCri@`tP<H9u3a1sQ4vwY?eF^YBu@P&>r!xQ~9$6=M<AZ0u(ZB9_Ok3Zud@17=0O$ED(fmT3DcDWOnyurXa'
    'C|0Q5IzgnLbMiF@^fF!h_@LpNe?R?sx;A5|ok7fK@kX8?VgyQV(&<5FhWLY_D<X2VpG(;Yfe&v#@?$~9PlgaAYD{D1)oGwY)W9C1'
    'QV%$Ts~s^4$${XA=GtoFQ|s>@7OcI{l|m~H$pgD->IFKL%s_;;N9919u!rjo#(+!wr*+ejyy^iyhk6T_!j(VST>fP9Zd!0Xed#s8'
    '7)lHFmw1UVo(+xzGZ@KT#B~6IfseyK`)m{MzxSZN?4cY8QCCwDOaSLb0w0nUeDe_QTZURtvpbnlF<|ebFGwxdFW!CQJAMC;g`g`('
    'd4|VQ0Z<J&M3_kSM;J}GU<4w+kq~#b6>FV`Yo7l1{(q&XB_8}wcluhuV7XY~=aX<#2nmbzI+f8a1Mviq^R~y23)1uIG)cnOhYLFc'
    'G2;HEEWgBp5S|E%S_Op`LPF5=EBvB~_e|qJh=}s_L-OZGYhM0ZVAK)YHPDX9O$?eB(2WX>ag2)gOtC~`3mEfZUijmZ=Pdur!k{Zm'
    '-)3qmoH;JIRz63F8y!gtR57$l@;5<{0_QZ=trtmxuYa)JayqCK@oIyfM*AL5Ks4OwJdusz+uw-#@gXJcgY_O?nWI>Ep55%!6$NkP'
    'x+D`sh6d}5?jI5hOfHBGaA)Vb^)N^~m4=QE8kL0MA3uoE=5UsIz8cd(0ZAq(>sk$j4WAy#uzffi9UQ-W-Db?q!R^j-+g|pCXn+$O'
    'l2m*Zv5iHg4CXCAI6@MbJeVR(Wr7lDMa9xutIUaDv^_K7Fz%K=C{`UfECR|P&82zOIVqShOYJ|@PyNe+hXqJ38DmRa7$6@v@-4wk'
    '88t36T*R=L!&11xifxd#G^t|6*OwwQpVF{{fDY(6i|RsKj<{~s+Gi7ZC}2xQB{jLvR*Ojn+t8c8li+gtk8<lOo=GeBFJus;KFmY~'
    'SQ)rGxmTci_mY~U0Ork_RjV>KVOyw~yj<DoNFW(yNp1~F@J==wn#}~SgGq9|Y0|1?ix*gsjGw+0r0OK@idC)vsRk<nfYwpWI8E&^'
    'YZg7%;@58z)JB5+<>t$92o5Y97Ai)NG=#?_zVKG*b2gtX3vcLQIUW!Hcm?Lj+w*|tikC||4-FHyZh&5Sp~x8(z6NR+Dn>b1O6L$h'
    'f6AY&TtgE<xPYq-5rH_1<sRG+j9*9t<&z@C3%1L+SGB8u_198h;?R=&X^Nd>Etq!08siq@6k+jeR8A2zV{6tfTrsy+-RnWN6zbUm'
    'E|CywsyU`4xK=f!^;zoE>C>!*X6S2rfB-}Gve-AioLot+&_j6U3*t^CV}hjB%0Ylnn+MJf-s6JS$oqJ%TC;q|(Jp{aZQY151Hu5O'
    '$vZ+hs9CvMfpl6fAadcV<!Y`tAXoU9OmJb^dd5zdc*R*l|3KdaB*4=r8gUhxDi=JJGEb;|sAKW?M~x#_e`cZbEOA`ZDduU?M-&+Q'
    'X;O5-7|uC%MNY)txmCDexWlt-$T2qo<e<za{?o;UA3~*JtCoA=`lc8x3|D9uy&p6!Wb%yamBU5D-!nG~BXEUZBjenuYQ>M-0e*_}'
    '%z2sk1<<e=4+w}45#I;~wBk}qiI{~c`>Msxqksw|D5O%ehBagQJiw#?%?87#wuL!?rVJr29JS%o({PFFZ-1?s>nGAQ8Vg~mvpBO{'
    ';&dpmUI1mKC==exUflHglH@;I#nXr7b2+}5hm@k+q}DcXj<y7!2@jDU&i}$dh_;b&44>|}de!nc44ilwD1@AtG(HQMBD00VgD*0I'
    'YB+h&AV_6C?9UXIrl}wIIhSPgIJM%1OQt~jr*;^9ekW@CL@U`L=aX@NtY00O;2%d(4qsji98iXg5osaz;Vn%-hk)W_%L4I_1Wo7z'
    'fJYbVS1yN#jA(>hla>z{GK`xhF?AdZc`8y5V~p8vWcM!T6>GB2KT3Q#P;~6Gu=QeoH4aFc=>fqcVNn3{6dZq&IZm^7(Ti;SSm??i'
    'H$=BWM+OJRPQofh2^vHkB|sni3eax!bN%AV7%InzVc)K<7gl1B&mn)2w}3a$3LR9M62fTCFj~vkFAnxdXXxb4!mdBBM=vB8DuOY7'
    '?gg6RT{nO@FiedoM*9!r0G(^M;%)C<p0)Ck*{OwDb{PJ+Mx)zA#A8^OSZH20iQEf33EB*R4?y4bYhP}ov$U?jMnqn)=-`vw+X1#n'
    '8e6Jq20`Fzf<%NCpiFt{7uTO}-V^q1i96d13m}z(2E*|d3A4wZ0cXlq1t0!v$m>j>>erV)Wqu;Cyal(1g{ArB65`(e^vhYC`{j}@'
    'Y%gNfZC#s<0e^Jo6XY&vPOZ{=P*%cV2hkR9xP;pQZ?qr(`?vj9!?|+n186fES56lk3;0J~P$C!&9S@EeZXJ|NeC#!s$k_$+lVJLj'
    'jXW76{agd$t=EeO6BAF+b|5*IzE=aU@V%O9K5?mx&}l9mhl)BZ$!VMOLxl-u!E8=PtHn_gAfDx%VdUF#%xYp<HP}YKg1e|;j4p|n'
    '%&sXXG>(l-On!k_PbXR2ehLj~24`XbLn&Zd)P7cyZ9I<v3?vwWpgO`)fzTF2<poUqw8A{Q2|aibL)@X}ci~k^rxBzQyx)o5PHw5*'
    '*r*B5AWtIW(?R((KR+HG{igJ@1`SCU>x0oWx_??F=nYL9?mxhPTFe+Yr0&y$CBfCh8C*}8<9><TybMn~Z3`Vv5?8uRxS*l&k;5bj'
    'jf}ytQx$~3a90vMVCc4X;bJnUaUJ5(@^xYo>lB2U=8Y$h#LV!0s2qVyrlEGhpK9jobx6?I>4~2<V^+@XM(UU}dMQYjH);qHpK7RH'
    'xd{I-gi}L%!IenVpq1l(0pkKC4SWH7u7x~NU4~B+^<}L$%b723X`U2ZO5tr$TQQ(bT>4g$3}D(MbeO0^iweaC`ON1Z>(5IPTi?2i'
    'S08LIVN#a02yPz>qYn}8Oye4^C5SLgGWo>%x<%g=$k$ILlFmj`%)z^HmJtbCrj=m*fZ=$MNmGf>ldD^^0%`$WqWk7GN~sq;4I`r@'
    'UlTaT2(mb|XgAH3@Al^fg+M<m+FcLhw7LcbR5~=B#_ef>DfB4HSxoOlkOzh7J{(;2(V7d7xTf(&Z;<)cd_0)Ap+%S_s;3Rb*Td`N'
    '&H`V8$COvDTc|t8b~V3=FE{~e0eFyyP5fRoBB*I-WX#m@!@4EmC~pe}L7F{J9D>1;rBLDC%=jnKprRz{xlLMi9OsqGzGXE9Tx8Ht'
    'X`EM}sl#7^c}T+w(IKYyAV6}~gYf4o!$T1mA=7705#MO1UWU|^V0c-6x-{T=%|nBNW_<N(MZypO0UA~#T`x#9FyRo$9wCLn_YnU}'
    '!)}-xY*(%L(d3?=A$RP>HK>QNf{4>PIDL({n-p=3N~W$wr^lEXQ@7}m^waOJ&#0tOWoY0edYL}prHuf$TGVDJVY+8H!EVm0R@@X('
    'XTlJpkrJG%fPE?4X_@--)sW_5p#zi$EIWTZq_VJV6<d{FDi#a)qmYil!{WmooiZ3yLrkO6$Z1U9Z9A`9e$iYMSZLH6paKAifD`Ib'
    '<DV+0Q2+{p)u<rFpAPHRJu4cnCrSW%d8x=p;uBMmARFR!f<}rOP7|;7JlfAQw0~N7NkidqUi3(XVilvRAj?xS1{j7!i#AD*EU`4I'
    'F)C^FeYLN;+_mBXW|$Qy;pJvQI;|$NaD6;oVI)QQRDU3O`mg`-e*oy48Z-'
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
