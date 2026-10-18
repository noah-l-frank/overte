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
# c33e9da0d8ef34fa6043fe1349a72f7d0f752ca6 / tree 2c16a407da4a55669a2c9fc7351c872844e9e8d0.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '00269d3578ca2383a1c659cd6c2aaae6dbbe44f619cb195ab6d31f1312fe06b0'
_MAIN_PROJECTION_B85 = (
    'c-qaK-In7>lAQ1L7=67tg#ZEwV4p%qNB2DOhb(qwk~t)^x@-6ByX!NMSzR@q$q10Ok|gc+baiVY2p~M%&CSgJ^S6IIZcm?I!zaH>'
    'hy6A^?El#1!^7#|cgHy&{_*>9zx(aq|MR!!eagT6`){Uc25W!&x8IJRJ%8J})MV2Pb4pX!^pi>1`)O$BxpB$Hkh68|X!QT#^zB9e'
    '1>tEQe*3R~`@U>oq4@dXW&gB|-wLaR&?RGrJWQ@hKF4uzjy0ObHFGzF)XZ+Mz8ODW?ZwA0{xLuNu|Is7pZ0$|JZ65aKW+EBV`1@r'
    'o_#wFJ~$Vew$DutDfD@2hbgsfZks0hA@=RZiy!jK{<uBu58oc*=N!KjSByNoIhyFqs0W;Lp61@pjZG6jbQ*ov+8nMt+*3ZD9*(cu'
    'Q+`PKCGS$+#ceLF+oo<Fhk5Ev+q%9rQ)^h*#i8r_*_ht@?B>{*nsrNSrJ)a#K9_E8!{A%*`|PGUcXphH<cGo7V0f<|ul4pSkG$MN'
    '-kl!)`Rbpx^ENJT^&j7!pRWAU+432=d9Xt_HpUMr^E_=A`e|~mb)A`9_Cr&(`eFZjj;9Cx_T%+sv*DYaW`1IBLo)4<n%)kx>sd5K'
    '*Tup1O-jCI*}s2OSC@9P<J@$!>HE>-5T}@iscZS|KAJSf#11BF=f5u<4lGAxh)-Ld@~61{^n2cY+3t>?9=+c4%eRkLHO5C9Vr+T1'
    ')`ixNX^5?HeNO#odo%ahIM=jmR(;`@^TMyMYiHMG-mx3I&_vg!v6;sZ_^`s<I)c>L<Q(I=b@$==s<WS66Fck7%<pTP$v181x?tm!'
    'N6Y8tqwmMgtXcK&y1Tk&G<Fz<H2W#o(ed;A)D6uvn$YEtTbn}T@;t9vQ(y8Xem?A<^X3@$FV}zd*xRPz$$HZbLmYF=lkYq4n!X*0'
    'U42Yb8qK<Az3gD;pYxHxoi~T<U$(o)tJ_E;UvC_8KUkt>Ha2sJTWfs`Lo=A(T0)A6>mS7K<#`kLyLo$kedkRc#;zZR(RkC2(F`1~'
    'p4c|_DYXrobL_EOy}s_{wE6Sv9Imb(_|6(@Q{Ou-iN4`U^nPk$%MHmF+3^&b+y%dSeZD}h%BySVICrD(+thRLIv1jgCYY}A+*;AM'
    'W=x$Onu_19i1LU3_Gy<-igcU9{`HhMY3m<%`{QXFuSc71iouWBnm+c~^7^MSXV2By^aD{ZrqFuRn`!knUen9fh1<~$CYv^8$AM3i'
    'o<2JnqM1|6L72JfY<8}C;q!-gS$#>&^a-BwpQq~qsOPYAakX9Fja`?useZ~X^jtLUl%r{avb5qpo;-QsY5%;94}`t1+aotB2k?`B'
    'P21Dva^vZiy?P@1K6{&5Pd3=iM8lNq#2qs#CYqtw%izhln|HIEN*#_T|4J@-JxaNui>c+(v%C*7j6mF+#&(+L<hq9RCO0Ho&F!0c'
    'C7rw;DO2=jjO{SaP0w%leQX_91IL7PuOH{$C)>5z+`NY``LN4Ro8>KC-O1Dj9!PQn_kQTyY@2otsU3RbrePj3`3T={JKwyMXTKxe'
    'P8)K3KIOx=&FAe=xysdDHM+P4(xcGiNEmUs=Q86KC08&VJ8YcgDc!!Sec)gES_o!C?B--*ABdJVw9fJM`mRYG=~LzlB90CEr?>Co'
    '<x+Y0r{z>1d^}wbY-6%x>uftxV2uM&z3)30)98nm&$_kElyW<U>E<nwQ_WA?$IqwgSUb3GCZlS+?E_a!=A4_+xRLmy2b8*onr(LB'
    'jxCkaEgnGM#IbQypxr>V*(&QI%i@ttyuD`Z#<6SD&08StNCdm>R}S{(`y;xZ1@Nu-K#ouS#xv+fHxl>5K=7S|p`bC5_|x3}SdJ&o'
    ')%A~M;?r<iI!xUdBbU%jrJ5oS%27@_*LPEY$0<7b!(*<#1!fZ7#>YhVF%NtrnS*Vt>-k8Wo)ER4nVNk2TRLZ}Z&yLszwVMR1R6e*'
    'i4TYLoY&Hrr2ypr_CvI-34?9Cp-!;*7wxIydg}6QrhW?4WVXvw>SGh;6pi6a9uuFjB2Ju}J9o6)QJbnT7<=;f)^K5RF^(<pPRe2A'
    '%cjclT?Zr(X40%X-&@{&-5&P4Xa2?WtGiy-wZeIX5_BPiJ`P+F!4F_fL-u26d1l<`sk?7a)wk&At@9mKg&RU1fl894x+MXlybR>N'
    '0|%ZR*<ZJv&6Xta@qBv}GQki=KB(l{*bs;VFDpz#oJKB-jyo;nxn;ZeZSAI8J~#j^5@Npb8I*-AB&tpvL7O7Eh@EZc(-eQv*5dwo'
    '!AVLFY?yuSCK7o&83Lu==Sb2__-405GGXSP9lP{vc6H2O^R7@;Q?gF6*9)YGBmgu#FR&`EkG9JrXlO?u_xJ6mDiV+$+Nl%7kn%i5'
    'pipjH-wYi72q0?)UZ|nWy>lx+WJS;0ns0mpJoEw>y4+E72|)u>Gyy~_v%9YK*(7i0`}VayHR8Q_az=2FK6HY)<^~+X46Wr82XAcI'
    'p>5`H@4m>7Ht~?bc28UXbS$6)lw8)fT(sj9NZV#m$Do|R07OR9#X#zmrn~o4lM-}X{(Lz6AJ8Ii3}>FK8b}}HrW*$eRO21k`hA<Z'
    'A$uc-46_-`FmS>sn|%*znq5CzlfB`}0q+OfiT7>nxPLtWYQ_EM3~n8-XLGEV8j2#%lM%|6Q#TE!vy)1IIZla(7J-=V+>)}&O+^U{'
    '!bH9X*hhna%4`nYGcBk~>gbGsdlH_;=H0%}`t8hq`}A4>dPh6P>~rrM+xtkv#F5*2a+XNT#>B20CmJZ`&hPs4{4#H!^7m@(`tf&M'
    '`a|cb&VYl6m;<m3k0p@rHiBg7?6m!G=huBYydF>7BwzBkLkSw?%#&YozHP{cZ+hY##R;Ia35Jg<kF!l<zNaEsu^DCAO=ldKXgiHF'
    'Z*Oji;ns$R6BdK*`Uxze?)txg)R%v9{kBLQXds^j=&0+tFDU36GTGjQo<tUmwjbj-)@9g_uS>Yghv)6_xbzUOCSzfujn=8rF^_Z)'
    '!89CcbZCP0&gL;TJ`r>3e)8wN-u`}H3i!I9sV7E1IU8-FK}l$%J|DTkQ)3cv9LJ<?&2!pvJ#?BWwj8{U_D50{1@N5>02i>y%$<`='
    '#~xB${<P!r|C%>GJ#VkyBy=`NK8SxNw8KF615_f-(NCu1|8)RdmV%+OAh@hr112^NmpEma3M3bE94PE9Cms|;@KK~(BMj7iOFy2Z'
    '>Kr3>h87}4KJ}rhRysh*(%K`};IKDs3KJlFWxe=gzo+IXxkPPYyOcUm{@z&?_<16Grk9)ftf{4`&5~QO__;8R`$OLR&h@y<*J}uc'
    'R)QIQ4m%{OzrlerPmL<~iDuM5o$BLUiP8PIgXjI%ycDBcL4~W(fJ?fzotrRrUNA0c4N0f&MsTr-s@>6en0);n)<u;VdE!mSv2JL6'
    'bu_yAVCIg7E+;K>0cEHHaSHY8SB4goW@^XLtJVfbaU&;Ah#N<I<RIFS@J`;{)h~RGFBQ+68i@B!Gq>gXY7M7wB$o~y&DEA07l0V('
    'q#K&GOaE2EUcW<VWH+Qep43%Xh-=C0M;<(Ye#7fF;3Onu^X<!Dx_$BG_4;$*+?hDSJrNWQErdFQn`{6j=ANUUFghA7(+wM`Tfduo'
    'nw*BLk7g&y7g_4edFWdHVDz911N??&{U<=ezHm7>3jS~%3krdov{jdtTO|_m`kp<--1dBgncz5*X`~cx-a_4za6Et3YiN3V$OehO'
    '!ZzUHd+OuN%}#RFlV{wpjc=#V`&}KNsgIu`0Z?aLXjo8$au4ByIw6nrn5d3<UiOBEambHgIut5t^T)xzyp*!67#hmonU8`{APkJl'
    'G4!6EFcmqBF}@e@of|$3fTinA*kPbf8(55VE?Kn}fd*%~ZEaA91mz{|%az63g@90-5KPWbz7x4*rWuh_!;NG?w=Bs)>H}RyQDEj3'
    '_t8yR0sRFCOmv7yF1eRr#nJ7IUQnQCCvfK?WUh*8=={qcw!4?t(<k2g(}h*_K!*SDM<($GR-+=ix*K|Rs#1CD%l8+_>?sw2)&z(E'
    'ch5YQwy(&Ne%cMIKjb9h(~lcd>9O%AJ-RY*<f#%#)2KmOI7ptaB64~uOPr<lpii9j)mDI`A8o8e+L<{4%Aa^Ft*{2J(3HlR>H~^l'
    '?n9gjU}FVkX1T22$c@*RBvs?vRCY?Umx!Pac%T+@c?`hSy@w~_{9L)@8#Ja^x#2zd!}I>IdF9_LWG#KmLEw(0;{qNQhp6%osC62h'
    'F*7tVLorGiuieMF@_e{(B|aSw@&7e>q`a~JYjl#2w{qr`sK8n>%>tfDdOMEr6?sK)Pc12zAHXvJ$~nJ08<>)$fp=`@4M147bv^5~'
    '!L?8cV<e^$QaQiW92Wk>OghXyNIqu>M>lR}A#t9+ZpftmSpE5=f%8flm|LKzHgg+CSSGwRYHy!<{)jAbsGwgJ_Z42ZPw9;R)B>(V'
    'wh<yw>n9jM^r)Id5OB^30RbbU-O`DlY3|?L1+)9%u@!hI96LQPLPCVE2~yXn8%&b{M$XWR@c;+e-oLReZJ@*3OTCcJuOkcesan``'
    'Bi(WXFDDswJ31Q1Eqprog%HloIQ@d1?YOg^XnObqt-kADStddUuxPs0q<UcIL{HlMKuQ5>3^gxp<FOC@{ku9RJ;aC~I<(g>)!-p{'
    'Ilx8UT|=Ns9LO~Bsqw|ZwgnXc^&i9iTU!&m5_tySJ|8~(dE$3F()5Smq)<u&SzQn6HUA5a<t1I;J};H*Yk2wWj|Fx#q{)FW&-Nm9'
    'tk489BoAN=0e}*h3rD2w@C&}N^Ho>{UpxAoL<z8+*a9HBae+){DC5o0Mv>H79$b^}-_&vYxUeI(NI|H4D-LB3u*hXd(FdSy0ddDU'
    'j3bAE)>S0Y<$-~(=KqGhEtyV5+kMQ*Olq$|ex3OCsD`PCGFWI&i3l4hC(!3#a0uRn0N1xO(?5m<3M5Nv12i-O3k~f+U4Y0#fHeJ5'
    'ZiE}R^R|ai>#j=r{VYoFuS-F2)yT~RM;W37)U5z&0cva9&2RDhu9l0kz`7B11v#7h&=aRDN0G!E91C1Gw4H<s5S#CQK9>-G9n$IA'
    'mSTx3hYJ}h1PCj97GgXQ0#O}W`2^Z&`+N6Nam-p6H6ryv$#9^I@OJ662l8Rm4WOIRla12Pc6V>(Qa}8B*a{J#QMoibIwvTynx^Xz'
    'oI(0W%40iTm^vx|;P-BA#g+gC0epyx@U<)nRS;>F{Li3iqOX&K6FlBrsV39*AOX>3XSvO9t%wDX_3>23f@iupa}()?QreDjQa&{`'
    'AP_?bCJs(cS>s)|W)GzzmMV=Rq#b)lc|bvcBCivdnYL0wia|l?Oh45B?#f0J{oV#OgPrNcLl^20olMm5kS$2rAW$2+5N3Ms<K+7D'
    'ySao~<dz0MBrdO_nBG5VB0mh#QiSvp`1&P!jPEfx(>_v*lV$p+PaCNEKS;DT`e%iH9n10oqkn64pXC64)uSlk>q4X!#1!wG&)1g~'
    '<?uQtGo=~YIemdKlL(=zgh5Ni9i(01o9PI6^s>6^%bXLQ<v$mCy%Ul;!7O3!-OxfAL<{98+B&*aivB3#(BA!hHNjtbCsh2CKb*EG'
    'r%03+rpu|oAtyUeFz-Nvxk`}ZG$zt3>XjCYR*CYDjST7PlFOGuV$R<e>1;-|01bTzzY&g91D`cDKyE{(a35ojnvodr-W~h51<%Bg'
    '>)(kNve$PFEVWU}K^`jvD8Be^q8jMWb#W~GzGK)wZ@zMCr*cXIj5$$LqkHv$BVhbczrbo{578QyA(>$cX?m}Dea==={<_s$q`rGO'
    'Y4w^!uaP(b8i@c)4t&;PBdRXSd@jiV|Gh~xJ$-4><X=wG&MXn;Z!7Zj{(7!FwT9OSH);gM4W2F&{cErU!l-kSNJ8Cmxo*YdcUAQZ'
    'MZxz!z8=_GbyQ<B^6ApkK(qsS1qj`+0|x`Rp|R41=x^M?%ggrlc~i5ID7H4;r0kY9ZkLf8Ct|shGsSvn!B7}{zj7m04*|Z+Kzl6^'
    'Z>@-;4ltmF96|o!+abi!qjo@QxOVNhf8u`GpHuh??XmprcUH)KK+QG<jy5+;OY;JFT}(a%DfE~}vi!7mHw$3AdCWB2OD#u;UQmoV'
    '3v}}dYgYLfj0QVqgxc1DB!j_Gl~r$H`3|by1(bpW-3;}664k7?kgaAkI<4COU`D(LFs-)wUHt#?4(MDw7nX!%JCatwNNkYT@;j3P'
    'pd-}MPNyn%unTCtcC|~UeEdT9YO{~8PuoAMo;|RtmZon7bTW|gK;xklr*kq{=;d&kATW`g+_;6um)Ff__>oWfSb#O@DI!RRjf`p='
    'R<<*?BQXKe>C{_m;n?vua`OxJ0V$g69jbeQXGDvJr~q*c4(Tw@YWpRXOyVL~<m9Mpy3YKX4J`muMKfApcrV>X7w0x6I=`qTdQ`|r'
    '6|!Do7VoMXZrl|Y_W@?aar=e8efztsi5FE6)Rf7R15KnRfJ}~#EQ-uD((Ou;MbkoPZ`{urf$-m+2xzL2^7f-E_Gd^Hw*#({rkRJn'
    'S9iXLLXxpWu*%;ZEql}D{?=o)dOxNO1dfPyq{WaSbg*bpN$|`PH8>$Pl6-gXx{AENpXYu2Qgyifs2&bQH9ivqTpjp3Txk;WOA|GV'
    'wLs=S$J&K2)neH0Qi**@r7C3@!7Lhd>3pM*Kp`xpLD-ogxFSN0L-l!n*~Y#7G;jYr3H4vV&+BnbnjI24@(6m5DvL!IAe|KI0dh<Y'
    'Le}BNb?g5{nX0~4DAT>@rZkUWjj2yfy^H|}jSzMKv><jLK-s#D9Avd}sNV!KCQ2dNied)<(fI(lDzh6TF^FW$hyWGfrFIkiw~DB-'
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
    'wG0iQKf{=6vY&DNF8J?H1uHgri#W{%fU^s50W%~BrkHfqz@J6-OQ*pP!@9-KuRxzc)q8+d0nUgC9i&C9P4FhA9R&*<9wQFw(&jRR'
    '(5}$OU1V0$&s=J{vX%!@EJ9<<uwlOjre(tPrY#;xT&Q#TQ`qki2>Y;Z6BpR??L#Oy&{1e-A-^(uW^~9bS{?;AzA~a)0ZPLiFyqSa'
    'k-ig7Pj%8jqv<G#RveT&JhP}{Ay9W}^5Q+iJ94Pe85ow=?EpfFUnWl0^8*kYLk1)?b0TG^NbjAy9gzxgQUfM1_J7xO?&>xcNlIA?'
    '5{&c*xL6?68FWoRK&GZ9c!Pm-jQGI&GR^(U*Ki5ZKRkje3pKnf8fimEP1aR-WJKE{ECcg^vMGKvT%@q_jnLBygi4*z!t!Xqq4Hz>'
    'r3wp>4xodXUvy}rC^g)sm|o!4wQl*>Et%fwRQMRtvhnNijMse$3`W1mpa;dd0t$;ry-|Q&msYQR{9{|{PHRH0NT8GjQpRErA;zwz'
    'GEwPaHUji*q=l|tTkiB{TGO+vOEkA2hZ@f*i^)<8^Hu0N2@C+Yr90!rc?1~3a@%NzLf_uGlcF|=Notq?j4cdYd646ztBJ5sh8P>Q'
    'cyFO3n{8OX4Xu9RdR0;@81gfrkV4(43C}<_INxz!$S6S;V4d(~kf#+dN0Oii@wmVJluF=}mx*2r#9ZXV;rGY+7_}+=4;f9;Br&ME'
    '1X4~7JSUX8gS~xMzwft;u42)6Z00BbSg>VQ>zNk0*h5K50l6jVqBp37$-QI;!w{_Y_8pydp|CwDb014na<J5!HCP#!KSCDB5}snS'
    '6fh!v(^b<<2FAWmw{Hj5;vNO@<?S(hVLm`@C_p)M^yHG)b<&yOBSv?R%Z@p0qsC=O#oFUdQYx6T0QO~6lc#<4XJJef-W8n!Xooz='
    ';jzLSfy}`-13d>csnLwpwgijjKdBR!UVN1Wp_JLe8JCVTmWOyu6JQ(Xmu#D539z6aUG=IQi$XTRDNG?6O+ZRgFm|%QH{wNcmvTxe'
    'nepu}mFkxk)4v#X;nw-3WN0&s8mm+S=R;5esF*Fj5{V(22n%3mFvA+!lc`+)j5Zex0ySNg#ugyl1TZ3Zd+Hgyp^`ckJa!~jxtS|h'
    'yeI_T)U-9dHl`tv5pYSNGr=qntywoHdqj7pu1##0ep4}*e%rzRfNTTQuQ+wgX|MnVwdN&j_9p5{xbOWURKP`uaa4@JEoN-rm;K|M'
    'F78Q_N_ORV(9zLk^aPUv=)B@Y7sR#~bAZlbCShabEzH--rEz57B>na1#njwif9W_Mj3Pp5+;@}|qLT?8N)fP5m?of86xC_n1{NVt'
    'Vb~Q^C%6&#w0I2!5s+%-I+x^8XkZ606uoU~ANewIxj;lk$4EJ*!B)V41SxzsHFS(V3R~zAg)sHCC~Da5g_tT(|M?O(r`KJ{TTQAP'
    '?kvz+h~>z*vW9e`k!CyCmTSZm>Y!MZy=vVBS<}-kkCP+A?-z-Llo7K=Qjm{=Rz*qGp$lPttLa5e&8pva5z#>+bXD5Zh))LrFv5<a'
    'A{#YPoAqd2=`d3kIc&FElH-cSFMg_LdxA~be4HDI8-YHL*Tm{p$QTq~ju0I@GeZNU6(gZW&C-Cn^S5=soK<?ErwtR2xIBQTW|BO7'
    '&zakW`g3{xgDu*N{GNATus8n%s|Fl~Yop+k$IJ{ySZEFu^rNgnv{4y8J_Hb45;HV8$VExh+oI<=;Tjnk#7UdCkA<?o*Hj(gK&a(l'
    'K8QTX0Z2cTYAbXiXTWkJR<8bLU;Z{@npEg97oIxa`-`h1YS-lvqYDNN!#BH^yCWza@e{S+RJnzP$hp00YzrWZuRR2NNXK4;E+QG~'
    '45|wFcbPA*QE^g~AHJ=4X?0e;Y@8Ws^dM5xXlO7#o_7|k0W}8OAuRW>HhtIq`Qw#WzHx*0fs7M?3t_>$j75dj%T3{XWh%oAFA(RJ'
    'am^Mgo;k`2Tn+e;^O9q7WuSAS01$f>iz>?u?<l{&!m`hd6Z6&PX;g~5TCPQlKLP&%C&Ly!6&VqoE?ITbL!D`wmKNQoSJ{fZzPzja'
    '{qbi`#0*kAGA*p*=$$bGcor8+$smMjIF_0<U96bTD;^h%=wnq~im@ims8)CxjRwXd7<fF6_Y9W?auFk?)suChcHtK(c^T1AP&(5z'
    '5K~}MUt^H#5F|-50X}3+)IeN>(8rr1%i{a8ODDW2_{P5m)SjLJ<Rzjd3N@j1BqLNX&I_7A{+)}Q@b9ZGWS1(x80_KT=({Wp6N;GG'
    '$%z^EDg;UF9cUw9!-{uUU%9f%ifx%&J;)z{KbqhaLRo3a^pp-^@+)6Vjxesj#!R(~E<Bnyu?^}r$$^T`oa~EQjm!=UFgTaY;eb7d'
    'VjDFlMYY4Vff~{jiF9w9xX@>)9ZL#ZE8ve?66_TL3t~+==d|w!_3{~Xte;OY*{@r7!DA_wUkd8pk(LY`FKib_#co*x@qu9$>m-Jf'
    'OAHBGs$Ba`RY*#9eOWF-Mh<CmDLqSmy?7_msvvP>93Q$2gD@<OmCMdg-wKXd%sm9t24g26gYJ>z3|K1D{wL`Ts8A8-f)!LQw@r%$'
    'lmBuxP|g7AwDC1GyAd8ik7ZPeIs)wSw7u+RNdap=r*p$)mtQFtuV?h&>7Zf2n6!VXnDP6QUoz@##$>~tp`;+io_y`XzrQ|T|Au<m'
    '8fx}6Ds>|*0)CSSdI#mTGGN4uO!HfY%Jt4e$Tr7k5QwV}m@bZ&^iz7r4nwDbdBBszO{ByIC{A&M6kx7h_l<sAezgXYoqzz0ED4r;'
    'L?~mxTBu-%kfN<))y|BIxO(NvNX3z*a{}ui^P?>(hKx!(+TV;cf@zDK8&%_6^uzwX{(k?Z(8pYwwOsI6(NEIf1Vq#LYG6|fGfbRc'
    'Mtj)WD4}`l1w|BxMh?jcvbp#WtKqZ94FDWYq#%W*I)`^{Yu9^yI&GIZrPs?sMlZ>OR<t|`c!AX>weU566EGg*X4*Av_4o8P_;dCw'
    'U#I*8&?Yox`9cd))+i{L1k6&wWe;yIFbJw<V4unz{NRvWwLIgDNN@1sf$)o)s{Ck$-~r}w`(>dp^u(CNP`UiY7a3>ur_<*G8X&O;'
    'p0qeBqLZO3iB%HyDe;*;9IpF4M0TVql?xvu@KOO(0<-6?O^`67yioDHw1OQd4`5(Xp(<>;Zq0%`<Kn@Ecc2az>_rUqIXkr47~bUN'
    '?N8W3QU}h)bvRY8D<&0KUIjo6Y$&xZ<uFjR69OTpVImj~7094aW3zM^YNPab_o5$+sILEX)DUrSn&rV!=1WGX4>}HX$~VrZjx&aw'
    'U~BK-GiD1&{tcevmqG?lFvPD++$^96&8s4(WM279kYPLGP2&Ghn@eB%F-v}x3$j-$LqT$nL5_bktf;+Z=eiIy5fKtaDHwBY$#QOT'
    'U;nK<Q|v)!T!)y5M9nFjnlYTD06bjf8vsE4kXEg@firXUJ_LcqR}lwuP3L7~1(yZO!<21R`D3Ox(6~chwr<sP#<M-{EA+e!2}1qN'
    'Pi!Tfa$@wTFECL-ahWJH;cE6>_3y^I?7aT<%m?>7N<du7kbZKYmQ%F|IMDaexaAXPdS<K*Bd;$Dl=%80LQA0|05O}#iaoKM_(*bk'
    'PBygy{SWm>KvHMLmfD-*?4em#GH^<n>(xOcTe8ap85*OFBsz=SiaG}0;bb}0mMdq&NEwM9e1*F<(~-m?<~!CbfrTi}-8^VEi9{G?'
    'p=G90W`HVi_vhjKhCgliE7s<l0%>LvcaL^6dd0zkHelw8jhE9%7L`lXFsKL3nuXscRb57oT>sR1S#{$}$4v$QoSzF4Ag=?fK^9iy'
    '!HMH-yK4Q5Q-7Uxy-c!r@)F;{B%{OWn9(EZtI>2(^0J6N+Z5gUe%iqWk$94q`2p(}(1L<TC%!i$;xZZ{Sl_{uhDfDP!f134OkohW'
    'Fci57KkcDvVIDK>{UERnZ4Esqs9GFswOHv9;TR;F<1X6O3+vx5P(v`*0M8_2fyGFPj0q`_F6}9#5m*3;V8~pY(j9W1A5-<I$vTH='
    'zcWB7M~N>EArUfE>YY5vb9;dOEb4k;#h2|1LX=V>M(HHXC1`4-)qsMf{AV}@c}ak(s5Wxh=IFh#l|Nok;*Fq6plND-*NL5xWb#PI'
    'oNAa18vqk%y4VB|3cPYMAyBY**)W|z3t?f%3@GZzYOaJx%TT{U@z9*T8<w-O5ChKrrh={qR1zz0YDKb6em&#pnf*WvgZoH`2Bara'
    'nxfzEkrwr{|2~lM;q7OCxBaUgnuxaB%OXLey{yLCf`Z^A(=riKBMAD0oF$amur(X18LEha8HZK`bX4=GiJXQuQ1_7*gD2xpqVWXq'
    'W!k&8Q}>YshD9-x88I3h5;gZh+|ceB$x=Etr8}l8>a4HtWEubX;<tr)geEa*j7Gl-(N>Xw+5irBW@abzaYRLf`&IOfxoib|UA1qG'
    'Z!UuenR|c>G#<4KdE_!d(9{TF2+~$TTP6<mKGrRKQss--o}m<a3dPcdwr`M6u$Sncmh>pmKN3AAv+!w7k~Sn)z4ju(Jzwqla9BoB'
    '&@3!jm|}wsVJJYT!Cpn=4ymRwSECB%fdf2~bfJb_v5A!wrU{T4`vJ|Hq&O4WjWt)J%B2?s4c`sZ&hos4A9wKkt1_#apWkMNrdlaj'
    '<$MM60e&Cfy^#MTJ)}D3OcPkM_=>NOCh#Oy(ZT^$3DZah%@LH>9#|>eLIJqriq+SBg2+$_LKF^&i7<`q@Mi>t;-OH`Xxw!KRAf|8'
    '>6V9wK5u>)7+*h_2v$CDZ6_f(v@+hfCiKvAYS5@p5^_Kk00xX}H*iTYt7f4BMlkm{O8XX}gplYnt!z|g0QYC24@KqP76)T}w1xV4'
    'R2%>&n;ME}8XzPHaN0n3$-aW7DA;8TiCMdi`dO^ARQJRi{x@nxnGS*Q0+FHaO6tzw_S36JbK4HySUT6s9cFGpi-2)Q(us76QMAIz'
    'ptqrtz|N*q2iO<Un!jzKuKS5X0IQQWWLTVxKji`h_yvMyVGw9qlOiaaqLln!SO1yfxEP=mQg2WbIrK1T6d)L)2rV*le>IS#;{m_p'
    'PPFl^ZB#HV;X;`yQf-q9(`@JMLt8?ujW?jt5Dg|21J{n`u6<OGW@Wqz)z>8K3JU}ro?02CPfDR_;$ag;T|9T=>dk0E>!xnxmo5i<'
    '+L)P)c54J0Cu$QbvD&0{YpIUp$;F+$dJhnLcKNX^z67u3`Af~#%6Nw1B}`KzkB1D4K?GX$ZUh)Ak|5sQz)@ayrTc;|yiz1omo!2q'
    '`5}wml4TN$btRKsaQ$;lS{owXrfXJB5oDQh5lJ*M>&*-OWSQ9n;)b4Okoq&O{wm+LP(7^{Cff|z-bzbD-RSz|8mI1&CA7xq()ZQ8'
    'og4S@eK2g5!#P}FMj_3u#%Q;4;|WS9$tfTK(Pf77rXirMU%Q!ePoMN6!b#d_TGgS@A#|iJ6f+>-0L@^Z^ai6O0FA~udk=+{#Ol_4'
    'Xt={}$*{PnisMJ=wL8r=Os0|18FlDlO*;%qac8%5-(#^q{J~z%88$oGRVeV_WX)7H6c%#8=haYo!MQ+@2=Ngb2451GfHSvkrG`O{'
    'gJIMVMEvgY!sD8w3XL)_hx)?2-lXZ;z=~@_7YIGhUZqY5#4WhvbU|QIlh9MoDOA#W;i98^4%LX-tB-4=#?PXKO%?DH5YEF;122SS'
    'j9`WC2p-qS|9YKQsO1E3P_KUFR_YA1xE+`hgB}$|Dm@yM<CAh*+5V#5=j^1R@7Ctp^V9b6GvC7N<wAXi8CnoDfWPn+_G+s#`Tz_O'
    '<(mN+a$;mNF@lDM2*Yc$tVe-;J6WMB`Q6M1j_bCl<{(JYX{ON(tnM%s1B)SwwWNVWu~zj+;;(DBLKKJC;CHVtd?rgRxZlr(Id1e3'
    '=q8b7K|X>!3R#<jfjbp!j|OrHebO$bwGV|EwY&GOlAromQ2lyYuYyYQ=;1cd)525^&vS5Y+Qj0gw?&lqUzh%&xv{*EHD=I_rpZad'
    'uaPDgvC_#y=>vVYN5W4}jku1-W>|Y<A&{?Qj>GCC;b{zokA{YH5cV`ajXNLRBCICDhUhT;?fWQ_#+c8+|6$BKCQhKxtw^u4d|a4d'
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
    'i_<`n{lkgrHLYNj2p#?;Zw<mM`c*&)dV^64G&ii>5dY;Ed9LY#0X&dM!oXJ_64H(~#xPhO2aMsUX_^?~5O3CQq@Fmek=UNTuc-Hg'
    'IUIZ8zd@^6tdbyH_9WP-5!OaIaJq}jd}NxtXDUEp7YZYsVgc$1JrG_1(#U4RLTW{hso;-xeB~~#P<wwWGr4Id-Lky^eVQFkHO541'
    'zLV88qCmO1%xe#d>RXP7CQ+6qGoTqyke7%US>~gfl!4#9#=c>>NlL;DahQ4IS_I_6vfW&yuX6t>ls1sI`4&g{V}Vdw5fI_57!BqI'
    '1HeRCt>S6rHZCgux7`#8I`j|>ytUqnZzw(ncM66HWGEhWHH|`mZSeGN{WfsWmA;$&@LXqI4_gS^VC`v^B-B@Vv%{bnG{BxS3wsHC'
    'jzc@FJ)CDA@=Gp+hQJthx_vUmYM8G@+=L5^{gcxz$GZT&qc5B6O{>?jphp3wOo(mCJLIH@Wriab&@%^}qzlUaMpF2-?_semJ6n|0'
    'K-nVa%zTJA|KK~r%sMjmNt>e9Yc=%~`nhNurCqFxNI@3BOj5|aVXwK$sDe>ZS~xRQ2awn(ZQ-kwR{ids@%@sz%oi$*Jn~}OBkIRC'
    '%F|V%mqkn3z)z7R4Do%`-5sh|uW*UuaKi|KL+Kc_478^gkA#M&4=H@WMuWs^&P8_4UuGfo(T};B15}3wD}9nA$MGWb?`d?yXvL4F'
    '6(8H>qRsCm%zSk3{^T9Ogg;=L1oe)&FD*AL0<fqF@idjuv7$_;`#g+wD^>?KY!Gq6rYS}r2CpM7n}iP@qcSMCxa_0IvxME^4_(f1'
    'T@Khm=VnC9Xe~2vCy37IftD#8e7}&-7!D^Bx2bAH#jH9d0Rne;W!xeGES+qVq;Fs)3}Q7R3N}Ma`=u|6k$+gWCQ>i}Cd=<}&>$b`'
    '6Fh<$lB&-d1PIAHj2cjnqSfRNtHMcEAG$z)=2G+`&l_1vGPI4)3EdMhqS0I!td*GEQ><BkShezoK$BuDo<d$eS#+3@1@yqdDC@CV'
    'XT$+$1|wFAxbWW=u9)EjR~LI3oMhvuNvi|wAt)Ihq@brz9(e<3`vDL>TKZgzKm3@mKb%VQ=E;l6f;6HNqY99tRx`Q5v7)X4e7K3z'
    'JzeDwZ$xU!d4G6T&k$LNfBN<x1^p2)0dwRj<QgJB-AWC%XVNuP2cw{|IKK@aTiO1&-i0+O1f*o*k87w@CiwV|fZ2HN5f#XNNkd4I'
    '@fKFSJ>$x@V%ZDcUtU`sN#-(U9UXLpv|nV~-!q#Thq5_?HM0vothH;uf!h^Z0Ox=w4h@egh`yIBQkkSFw*&;)S;CC0N!1^I)l@wv'
    '?css)aAqv+KYl;%cUOKf_$Pc^m_`~-f}n4b&paYV(ar$A&=Jn?L_f@NSmk#}84pXF6O`@!&-ll?r<tXuf?dTxD<CDi+zCwHU|<~-'
    'E7WeCAkvRH`I-ZInXY|&(D2QFoc=srn=#Z*AZE096HgE^0wp);^dK`s{K3!_5jonArEG-2hqoX3z98erA1A`(s4396xNuZSQ<?6-'
    'i=;<^t({jH*UPK>+G^rc>+c>Gti8~cLMsl*1G{PJ1v-_?K!mnO<v^RThwBc;fJ^*`b<>f&>H$87dJC7rl|R{B{$%srwBUOB(rbV*'
    'losqS@e*M?8yp8_Fp|57>i`4;ABTVT(I&qC-h=wGhjJi9T}?$W0-PHOd`MRC%|p0v8EV0^_cEhmz}|abkXo*vg8#yI`u#r^g039p'
    '86HaoKsDqMVItXgFq&||h(vxPA?{==);bT@JpJ$e|H@BGJoumf^tph+a<RhC=lh`$5*8bDDwAIZ;t3$<ZM*ji((~#xN#f^+3p)cb'
    ';{K&9zr=zNo(PIs1%(zuLe%st{Gy5XOyfX^i1PJa^5=VNUjABAd?tzdyx;~}0Xj52&3;DAM3|4vTj(_1yeTYs&hkGk47$SfZKkHe'
    'nd5?M<#U9%(UY`56+^2ee-i{La86U*dWj_X`Ul%Br-MonuQupuwD0i*M8l2F6WJKP{f(#}?^4p<S?}?cIf?~_VmEnpMZp`nF3ALu'
    'p}{(%`-j8=lM7-4+}WvaJq*%LrJ<vPMkQhR#}8t(Ih<vluf}vxK#~c{x>f^W<A+BwZXeD@2ggsJw=?GE;CAP^Z7=&mG{6ZCNh-dI'
    '*v6t#2J@C593crz9!wFYGC>KnqGD;SRpvx6+Mbzk7<bDb6sry#76E0D=F+_CycA5BrS|XYr~bC!VF8j$#@G@UM##sFd`mD>MvV&%'
    '7cng6uoP~vVjH9_O|Dq+^`*$nr!?#!paXhNqPozQBd%Mu_Spm;3fPiSNsa!a)l!zhHuUCiB)FXZqujcRXVS|33mF8d4>M5#Rt5wr'
    '+$&JMdr8ev0P|+es#O`Aur1U~L9Xm{B#?}<B)0}7cqbbT&1Qnv!6dofG<nss#S1J-#!uf0Qgs%01p@^S1x&U|0Ig2UI8E&^YZg7%'
    ';@58z)JB5+<>t$92o5Y97Ai)NG=#?_zVKG*bAA|R;SD`3$K&CjufQDh_B^1u;^mUgL&L<a8=zNSC~`)HuYuZyic!v$(mBMBpYlg5'
    '*U&@|F5qfIL?F&$xyQ|d@e667d{U%%!FCz<s&@6S{#*)7*j14`NX-!>tsH1(lPV#)LFErC)$-@iBtpM-;flGn0x4zoqWQU4?t$i0'
    'l7jM+2cs4q4Zt2_kKe@%&r2VVulWH24B5+K-}rL!CAk6@cFPyUoyxC<q}9qnfKQtTPGZ*Mg4W3Uc&b{ne8<r)fKF|_!<YeKfY;<5'
    'p&Zn#T&+MlEf)~EaMf}(R~(Qld`u>|Fl~LtPM3JaSwjCn-vlHe&?j=Z3XPQuo=TY~)IQX)yhhYGa`k5xD$f$fHJxIfCVfPKu^+y}'
    '3&wEHu`6;S_Rg)s1;ZUa%Z40t6F?5ieBwV{T=*eW8n$Y=7p`xL!NPEbcG3Gm(?TZCs9rf-H2ghtqc8$j_%$-l9jjJ+&mG{WIM1Ay'
    'kzW7}oAH304~Y0iFrXEeQcA>Gm~yCE>^usnK!QRlHECEgrq2UR3eapYd}>>m6KKkm)$+Z5cp5Ho{q3(cbNxh`Mq?o?brNTmOPme`'
    ')(fDl6lKDD*^3`PUXuK0t9bgbd@jc~^N@m7j2YG1=FQQT;4|SN^27Nb7zoKWGLGTXb*on`kHdgeM&3+3V_+W%HH;bJD`AFtTUao2'
    'V7OdCblUYx)6`G<`8tOk#i#~O%UO#Kp$5O<q2Cc9i0*u71oyD0s_R!rCiurul*5<T0tb{KV?<hreRxY-{H_vJA+HzW9|;-_AqDy_'
    ')~{R+4}=?RQPCEO0?a+ig-OSjc@&^wI2#~5lD|S+@oOXN{Ig&M0|$+%nUoSDP*@2>Me)S901$_<%;dd}$hdmZi)_3wxCs^nXfk3A'
    'RZAocLH!^Uc_Keyp~@XYGBZu}iz{QO93$3hs56#Z2~H8Q3AbJ<amcnX!)B34pan1$qR;h<gFSL8PW~+H`m=zr4AP$BTaQ48u}MzT'
    '%P^v3N^YwW%TztMyV+*N^1GL3t$bv5YGIZghCja1=r$4Y7}g~gT98d5_X0FHem~#?XRLnh%WZU)))nTa(Rd><!aGha6U~xWCr*$w'
    'jWW8w#5Z=gCZy=kH{TQXZHYVE3kwkT(dl@LgxO=yfHP&Qf)D>S<aK7vdzU}u{6t`R3vLe!OY_qu#J&CLr?WWs(<NQlUc{=~x;7gF'
    '{^-tU$X(E!TBY|KP-a~5k-%Mm&4_4%3(x)cZ~L!?bLG|t&}KBQpm}gC;2#A+iC{EzJm4$i)<Ma{CDv7J{p^DIK`{NvMxKn3ey#!W'
    '*6YQCiHRp@JCK}9->ZRFTp(l3CoYu{I?biyP*I0vIc;-(s4&4Sn9b>FwRqHMh-W!xx<@%?H8HIkY@=VnUDPl}m&8kE*OU_)$3`Y5'
    'zd)>~vn*~uJW`s$nHj*aE93$ewV#z_8_y#E0||y8s5&?*5Za=sytIx!tT4}RLJvX25PzuoU3it!X@tGzM}Sz09CAzb#+)WRgFK0h'
    'PY310{QP)$44cx=8Z;zbtPe)h;EGQaAVF_v+Hfm!|IlK_z#(@Z9xMs29?sx;#vJ!k+Rn@H#M8FW;UsaT%Y+LW8Xq}KBAb*k7;Owe'
    '2n=^6!2^bFYZopibDc(mf{7w`)9`NYT`Q)Ir<s7>-KvI#6PRu7f<M*F*Xxj|vC|_zZNjV^?gw&?tkFwRvOK3DNPMbss9m`T{~#S#'
    '%Q%bq&g+B@G0s#AnRYf3;Xx*Ij+Xt0h{Uqio8`<Wzcfz@E~Q}W)K&~=6PLb~Bm<Z>3mqovAXi7Rf&bFSAM4Lc5?kN8i`QXxMDY-%'
    'peEzFHKNhd^hc~Vu%Hq3gStpfI9IpmcLnnGQwieHXo@*_H_kF5Vav1<tRFBO4>D;g@p<xfYt}$5puogxS|R|I(4C{qGK_3d^D=3N'
    '-Z9+0VCohW0{yILSC9!{^0rJd;FHy8Rj0{Pt=t+#<|QTX=KMYv{=GF99&t_Mjou(-4j&IDZfFrEiRx)X@$~@oaA#q93y*2;*R5L^'
    'oPfqa^PBjBGYWP94;)EGo+ug-)HI~#6LtKsZb>-G+v|Ctbe5QJQcLS;PU5%#o1)_<E0Y?w)sRY?S1$XO)f9}X;P316!Om7xah!xP'
    '$z}!$EdY{lS`S`hw=0iL5g0-C&730auR8TIq^1PJo8_n5!%f#bG$?2$RIgSf3;__JVKvhA@<@RRhe-CQDCh;=WevMwZm?ao;(L>O'
    'eumt!7uTR3#tMSEc5wO{aW|PR%BW<hb^r-H;>u%sB>fEg>oY1TOc@$Die9D<cxfZRtroQzN|^2$QX)Uit5)0;QD+20Tql&r!0n8O'
    'qJ=~F#VLg}7YiNAI$+u9{UMcwWvke#^in}S@JAsXBM#DObzT_^sv)LPY2-Af@Al)4_4~^&nu`Jpjd}x!4<He*NA;)y-{mw)%bZ~4'
    '6r}jmVcoiCMZ@((2|y1|H|U!b=iGI414q10&`43kY2vk>N844N)^i#Phx4LGx}ME9{o-}*l^d#9g&U0|mvK6<#^DL^$uX*Gt~^M^'
    '=&#8e^bV5ZAQ6E9BYa*=%;D<-b|>X^i<a<jAM}6ykN*R|;2ty'
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
