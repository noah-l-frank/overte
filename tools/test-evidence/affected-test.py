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
# 31ba7e9391ebab20d07fdd9b70b764fcadaf009c / tree 9f5c4b7bcc332a97975073ff0779365a1c35aa4f.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '5f85c0e1b50cfc884c11f863c13b7570cc60b4dadd97c9429756bb1c1e1b3636'
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
    'c-qa~+makdvL)E}`HXsQ9QggxUokQ=?<syU2ZBswWaWiLc1!>JEcJ*4!7609M<jb@j`TSs!Rj&#cXKt>t$T0%pa1x;FNc?}ujA+8'
    'VSYLu=1<3eJ*1~kFHgh6^OBza>zC)_!$1D}|NO_d<DCBS-~W+kSyNU2_;3Gs{yO-_qR4XpQ|CoD<&(e5@^)ELInGnvWK)+fS-H%4'
    '?*GHfACK{0Fy0@>fBdii_I=sWLetkzkH`DN^vA|(<5>FdYEsj;**v7FYua`iQ<k;aQa0n9Ep1Z`S@-^GkHhrq@Fjiv*YWAs<^K4u'
    'PhXN>JG>l@56>Hmr#|JyoOONKr@5FG|2MU5z0^a~S4~k)O%cC&d4KVz^mu$eyd0nY_%wY@)2~}A)>G9Mi|5+r-7?R8N~vG!YRRg('
    '_e1+`D2pnM)%z>Hr017U&##A<^l46y>0wR}(;;oGTP#gpRz;cjbv*5<nwGZBifQPxZmx@IuCuvZinM3lt+m>58uPJl+rF8rI(5s`'
    '*Hd41*;M4iFqC~`7hOHRzt-EUeD-pm(!<NAf4&a)hvhJ>Z}q?a_;&yP>V4PF-IC3D-=!)m@_ZPbq_XImp|)y~{N0qd)vnc_j=!Yo'
    '<x~9j=gZ43Rom3d(D+Oir>M@SrJ372pNnefJ>YuIQdZ{8o@M{@P+eTQD3+AX&0O|#USvy`Wm(_nrR8TozAn0K?y|A^$p<?=Sx#h_'
    '?hl^w=jrhIm-O)K;o<r7mm%Ks;~(#@>cLLcI8DV^RaH9{RW~<Ya9gLj?y5Rp>XgS3yJpo#zuXJIyl%C$WvYhMcIB8&ZQ;i)-8jxe'
    'GcHBDWNnwFG)>p7dmJyXx(rL3O=Z>Q-fmrF{g4%9TaMM#r>>gXWtfJ#E3bOSPp=Ob*PQaIX_|Q%`myR-KX2&EChNO=EYp~ZY96yT'
    'Ez4DF#!0@LzCInlrMu_p_;~qOcXgFzp6uW>HB*<S)DLwzw3$OCcGc6|&s~1qvtD=bFnmkT0(ZK5O2gyf;mgHs%w1J2Q<LhZ5;ap^'
    'C2_2%s$m+NtjX)DYVyieb^SITzuis8hvjg2{dUMx)0K78bosDei%nT%_1FwuJ<mmEb7D?aUcG+Y%k$muzb)g%^+)F{tE#!KTbD$g'
    'c@nk2Jr!<9C$jVuGWYXv_4-brtMcO7X<Eu|sEfJw;gv#rJLO|uW`kR68j8G|%c{wC{Pu__{~G@I{E%KE(%n5BUtiMQd>Fnw9G_nf'
    ')8%MW_R}~B=y^TWsq*?o_cXXVv%0Ar!FenODNBF#HeTn)iwhTB+vJfYq}B&N_wn@Y#1*p4g%4pFokU5)?uAbW@4Wh&n8gu%Nx#2b'
    '4nVb!y-h<=)@4_gDK=I2sU2M`b<w9O&%}pjJKWw6^1_$nx5M;F*!%79>_+tgejZ-u!^_?I#*16_;ul%hX{hF67*i@2(QuxtzOSk-'
    'Vq)IZ@iIJ__U7HJUuAq8_rt4P@^X}Fn{t|qS<dEtH1jZun|)XG%QClRw&Z!rBwN|-n|YN^UXGOWH00e>G%}CcZy)NZXk86H6X{;v'
    '$tdTlEK+{+9)3+v59$7HeM=X2(ifu#GPlh%w`18Za-e0Li>A)yV@s3dWzKK0+`N--!-I5tzLVoS%1?jXeLXx!u5xi#SzKJrQgvgN'
    'CSjyawad&cDp$x$JIvb3Q@VXu$I*Z2w~b)dOi{T^^(b0aW6`!w?@-Eor>;~0%;H!R|MvD>Jf16$;eP$9pN8q>a$xJ`sw>(`Qd%rh'
    ')IO{0vYqB`XbQ)=sIq>Rv5x)CTar^P_lGZEUv|gZrY#p4RW?-h=xRy6^SsO3PW*`nG?$s0ZE433Y-uaq@&Ib3X4dv)RyIYK7m;<f'
    'kzW_Rx0iKg*OkS5^A@BXvtW1l&4+#W{SjTx0-P1KM8BxtJcF`pJ8^$(1m9&;B`^6T{$#g5mgg7W)#by|I~r{)J*uas$tAS(&h6wu'
    'waQ7gYuVQy_=;YJr!Q&uEwD&<vtgQLA4}tmBp-HOwY5Xi#uIAf2Yr@qe@mxq_3bJckFO8&un}k+litCRo_j4B>|$t?MoryJRgsTP'
    'l?}N%p-O+#o_1VMWm?p`{n+$nRi=Kfr)*qiz>1UH&5m(IoN38ExTE!sy4w{7r&|7A<StAXV^^eMnA6xf*{YnOEX%qc7irc9-&=b4'
    '?eKJb_~t)&dUcn}x*~9%9?n#b<5*9PD`Fg)q^wRuHx{0m8+|T6wx`{<Xg5^tP^v20W=tK7X0BAX5-{cEDEDoA@OD)FecQP^NCLl{'
    'ZjX&ja2z`aYHo`u6NpDIYwVk;?_3t8J8eu$VY?sO+D*6o*aEa9#LoEAw@DT<MV;97MLx+zs--H2xu5=~txd;oD^9ZYz?x-9WiOGh'
    '`dpxl_t{CBg>SoU=6qb-vt2p=J-d2Nzomzbs#?j~Lxj9QMWg_bd0t(XyFQ9Cb?~`TARj)qpIwnadRX;kKn!zQ`l)XQH|~%%KK=<H'
    'n>Su)uFU=5R({Bez8&_Q@gBxJ1i(<HQq9%QQ(KRHJ`NxQyDN(!<?~Q2AKTaUsgd_K$Qj`v^;ibXwPbLJyeTS2yeYfF4y$Y#Ke{jZ'
    '(cSa}M|^lW4EN6)=zx-|stOlv*N@V+W$~~gC&)+1ZeC6>K$Yu<_p~P^C|&*zj{kuc4LO`u;Z=e3Ava~$C{XjEor~gQo4Fx-lS7V6'
    '-sDZ=3sW`^^&<O+^;dZsa#v2_9?XmBV;g%uzCHo9rsLNHx1KI%bJo*)5S=`kK-tn9(0Ez(Q33$XXAf-xF@11LkyYO9C}AN?@-<*z'
    '(bg)nWpvLJP?xzZ>IC-`p1Q2dtG{DA%W$}V-2i&Ks+-b~>LIJ@VbU;Z<+d6#X(~LXsVuu*11109xqkWfxE$`&_iF9(=ij>Yn{rT{'
    'frCWM1}x*TjPl(qAX%NAqHaETx?i4NpI_W0zotK)wxChpy!_JlU5zPsrnPf2?G}0Nm^)OOFV)<ok5mL#Y$md7J&qP8TJ+jJY0y#9'
    '@v6qm7dDMmS@*Dreb@gPq(1+f%eTc`LIWKO=xAHJFBJ5dOt#L)S|SUht-Gn~_GQ>#Ue|D!p1vKPpVuDZ#bj*kd;N%LbSzyOXPAa&'
    'sWNe_hPF!Glnt|(v+pN=J;vKV9=8I1T+r%?Zs^-;s<dSbp-p|>xxwcwpTTiHlYMKR(w57iGw-LuhgWKU%#lR_zEck10-G%EoH;M;'
    'VcwTNJ-GaTOLxQk?Qr=f(b<rEh=2K5G>z^DRAOE<Ec4R;D*;@Uf?;Pta9(u}n3!cQab;N)NbQs+?ccoe#X~^?KAMzk!oa?>^y8Pb'
    'JI9#HJQbrNUws%=s}7Jhs@A2ZW>;p#JoZ5No%Q06{hmFaQah_Hs&bx7D1Y5nQQ#--@gkbTj<s4^Z8o=8EPg6Xr{hz)`^EM6kS^B{'
    '5n2T^eU3`|xNVvi%G_sBx%Zk;jXHIhmYo>gk30Bw{4K4;s4HmWD$L=Mt+r}5cI6N-uCzwd8FwRGtXH+S8V~)je-GD1m1*+Cv(jgs'
    'X?>L%UG<nRrS7>eExCXas=(Bb``6zYTJm{OJ9b0V+HjP%^Th??<`eIHh*c-N%e%|{3!mc4j%Th0^4>Lb3)feX`wBa`^jK=H7H(Vs'
    'G3Z49^V+5VEMYI-AsX44v}cgI1{Ts5GW*Vh2k2*BcMd0!kS(__fA028kFS@XgYPb%y277&>u4eB3^!Q=C3es0Cv>ewOMk;g_N`wo'
    'wI*jS>(lI%e92N5-$PmWgKmH>G{rb)*B=21`^x3;DGX1Sv7m8ulNQlsb*oH5UR~SMl#1FROoC%4)0pS+<}K`d60PTNy-d@4KsK2D'
    '72CkWAJoUm%`UmB<rz0@<BylG$A^7@W*mM+0#L{IpngITN_DG=QUO-<m{iA}S9Qa~cuHSjItrEf?q5&C<KtGAHI13_cX23$g22FB'
    'j$=LO39HCct~L-Eh8qqBVCixbwn44Y(;GqC(_BSs5j42ywiRQ9$Y7||+9cEdrS~TUeLM6+8RU{hGa}8I8>xbBRg#0b9(5Um0<&Ck'
    'AKjD{=r7co-i_z)Cy!Whx}DPyP~c!ExO3Cglsl@S(=Y#YczAq$`RuLVpIKF(WcZ){l_cI^H5Jjt-RRXtmFlgp=WmkPD-}U&0f>OR'
    '7muZ=cVtO_*^Sjdr8$UCKW;2akGtU|9^E!@G^i4#X=;!H2WfCBCSR|zq^;B*`ot+t?GAACy^U>=b{1bi<WC+;5m<vObjC+heY9Gi'
    '^*Aj8Shs^RvtHJ3<i^WOO4Xdr$WAqTMTF>pk7}_tbtAaC9`HokVcEIl8#ETN^3Ho0p1vKQ?q2=pHnNtw@FBP(bzI<KQ!_>R2WrL0'
    '%ku?IELV&Q<9qjUsysiPxe}kBpQit>$s^kv`+tp2^8Qv%oRTQ8)=YB)&y?PF9p0c<gnL>^xrPRw0VwzVdNu>fZ`*xfJ8uBOx~<Du'
    'Z#A|BD&aJVsY0snSItr3Pb|`5`;dGt2uC+=W+ic+PB${?@Vxu@%#H6=8kh=DRFT}q!R_?c)ZW8f`y*Lmvx9!Mxv%l{a6g~$pS^&q'
    '$krhO6+@2!q(_y_f<W80fq=lsv|GyHXXYQ@+!?d`;jwM-P<(dryo7`aUlUT7MK@TJ0VAg=g7J{2zWVsa4%$FZZ!h&sI=_r8=u;Kg'
    'bDeH^j+Zm%(e1zimr_(Mej&nn-t~XO&K}%Z_nIEVlUCp5Q<g;N5f-g$E!Bgai=Nv2Af*vCM$M~jj5J+;d{?KWM~wKPLwosB9S0<@'
    '7P#o$WdhaggPeOu&56Udg$h9ZyYb^&yC!zc@(gF+!N;E$zl%=OAHgX?sRnX%J=AN%-|$(U)Ahr*wUT`uAHNRI8|-ML$wrvBy-6J#'
    'Xo3uB02m_xC~;jl+7HwCH=ME4Rk#bjZuL1u3E0k501(@5g-n+;P8p#?kkkqfE=wQZ)bruX%8odYf~b6Ve3Ug{(PgOU187%3+-@1W'
    '&c~p2HA!?mF!*Zv->|ne)7jB>?-ETxwAYYdduLBItRhOV&{~Ozjg)5S^WX3hya@p=Z)edz#sUS&N^L+x9ayL-8g&7QM*!0LrEY{9'
    'xAV4#&(~d*`u!Hw`zz-$;Hu8egrkfofx0z9Eugk}d-GfTzN_`3++f`VbcLMlJ{-iU%BLvthGW5XM?x4v1;pkLKc91mzYOV=MWI-7'
    '<+zYhAt0>yEMhzeK~zU8@1dPl{n5Sb_{<87njrO|WVBF5yj`94Q9exF0NtDh*{FVY`{Ave>xaL7Y#R|Ei*jjcbxwv6#9o$JOG$&Y'
    '3Ip}RqN4%;|LE4P*b-0>;3F#HYgH1eF-WWOzr3Jhn)5Wa0gq=Fs>%8A6au32&Qg)yS`jNCJ4`RzSn#5ovt*NQsM5BZ`pBpH3<A-V'
    'FmX7!vSw(@Yxb~J#H!L1Aw^fW$^!)fMP3<PW^JXJ6hlGT=5%qpfA`KtlYVbT%}_0R@#sP&(Mhj{N4Ai%AyDVK5PAQz!|D1P9+oZC'
    'A{83^NL)h{#d`nHL_dsZi8@V=gHF|W(LZBw&c{hDF3TM5Ki{G1{~*!2i+{J#ud}QJTw?mheU?V}RZUUibX5dn!4xmsAzfZJD2JCZ'
    'nSNf-&h-VlBoU&j#GqAikD*<0W=a81FRQ$~%qihn|9+#_+m~Y<Fw3~qZBw8O(n7V0wo;cWqJJWqnSb)50{%)5fr@_~o?Z@=QxfHs'
    '>GHC{A(x%cn0L@%R|z>zmQQ*`b)>~Xt1Lo;r(Je&$@Qd2%>DBwoh^@AKtmtlcfyg%@LA^!<klpGdpFhejbgyh?%4lW@I(x`d`^Zy'
    '_UbajQUmz5+KdeXloMa}s)71c7f&0%?|D3ayZg<pJ#VKpV9Z`kUHi0wBQSo{FIdeoAX;M?$_(dm?tj+2K4mL&`t1;JQGNIL607e?'
    '^s*2qppgV%>4Q(PSVz^R%y&tS`0v@Q={amIIuDO8p`BSH%zv!t>HYa!J+;hh#Et5pxZ|M9q<;-d5JuZJpF7AYcKf~+pTDcB9~A}P'
    '|M+rXE25)1Wu2p|r$MxXyaGbc?V!Z~&NNoaaT;#i!Q<oM_1oQ^jZDGT)=f(7+QuytxiOV$9m!e5dbD5^hM~T4BfA~~zD%RNHj1}Z'
    '5Jg*HK!F?~{}_s9oVtP9fz<HYwWs5~`{j5_;m@?k?Xyn|9VinuTR-}=-7tmb1$aG}d;}?a%$+QMzIHb&V0`x_X}E8-91*=xjC~8b'
    '`NCQi`4~n+)um?Xs}_<BgHx65-okngcD)Off*IXx5zvBaR#(VY3yn?@?SGh&_W;u>cE5}Nf4l>oi*FlCBH4D*3XH^zyw>lWBLKES'
    't#-PqxWz8edM)=ZIj84eb+7J@)9d}=_g&8(tQt$}TY*j*DGwTtQe5Yxuh7eJnGl#{CpT{4%j4_aSNzEP^t=IU>M72OM@A3YC7S(t'
    'RZ2`iI%V|M3LHCcBV~WXK9Hha@2Kt@JR>a{Q2}ubhqPIiX#34kG6ff*A}6P=Da-ut+0Y6w?Px{^7+!~NqnwuTNpNE+N~n-Y6;iyy'
    '6uhglxp7x6?kCKM=fki5@$H{3CSIx_)RexG12Gm@fK089EJfzr>2}Q_i`GIYZrslaff)X{7to?cN{9EZ*uO%m8RD<(C|jDkj_!Po'
    'LXy~cRFS{8TK0LF>RUgntM`)^qrfrIjuc(5mcXK+lJLxCHMo#ENxsXUx{CaKKi`hiue(0(p^F}lqPpevfUASQ<4Ox5e`unXU@ge}'
    'muc_9=W200Jj`3{OO<LU!vwP_r%QK6kw6ia<|eSSTyP~qotoX>^W$MUR-c!{?=OM+ui)q9xE7in37tGb?=i~apbJPR1NDF$t3hNP'
    'ZFk-Je^RD)Un|P=A?T)>M_6Ogr&cdlB`Ogvk=|$<>^?x*bsKpKtCgqyn;>IS3Wbf1f)+$KjKI|}yCI1olF2&)RKUyLP55sOqQ(_>'
    'd=)9x94cfWSU;i=xm2Z}&L>&Ll5h#8K}mY!4o>;b?&lGT4pnZzTtvW%cztlh5jin;7Gk)vLTc%%-FN+ONB?-YS{g;Qx)GhERhjNx'
    'DFTc^Vap=rx2Uj$PD+6jtitWJ$DIrIK7NM|U8|w(Lm+{zfkW$xENh$+EYyWTakI4`!OS23Bkhu2>A6E0;)8cxdC^NB8m9v0(754c'
    'dO7r3|6yy%Rf_gjmv88V`%qBydc=9s@2|3iF~t)g%$zz6Tz{D`l(quSKAp7A6Wl2WxZ_q7(Xm#269LIuCir`O(r!=H-o@5mdOWv-'
    '<8SXy{|TAF{f@S4fToV_tYT+_(IUPeb(G3=4<9$lVJi?m=Ioa393G<ai*qr)^4)s6dwd<=xG<OZB;>n%!_=t;=<>4?fOPJ<uBE!6'
    'uLR?bxcML2Q>feMrP94?X^XkWv?R0$4R`@`2bP-9x%mW9--Bt&I@oL2#UI+w5A7T2!IEAM-!5NM?m!H7`VnO>b#UBPB!IpS9bX?%'
    'Xw2ll^Ki?q?mZpd-n12(y@f2A^i!_BW8~vO<yb<B5Uscn+yN}$A^9zP__nqKwIsIoP{6UEFAyF8lk^du=fZYo>OS@(7Nh-+^DTP_'
    'dmnpvns+>l<Yp>E@x=AaNddQqCEFC12&4>iL(Tw@nA%(Rp*0%S_~WY{{I0{H=I&L(lm<R+6hq8LDL-cqJJK%dmbkT={-(pRf;D%i'
    'd+YRNUw%KCySY&h%3iUz#sJAcxj0KG0T_T&oSJmo*8`hBJ^=vEyZPt0`wdc^WQM#10nvTJ5J<gK@&8h#AuS2{Zc|13{5NbR{_HYl'
    'z+$Co^{dm$DdR`vv4}B<v6$m+>I3KQ=H~Xj1S|7-a9B3bn?Nz4-+5?Kh(cgn-W2#&J|m;)_?n=Xq;$(ho`-LbG-=Pl4?eZ_w}|`x'
    '0iLMB;&ISVX)I*>i;71JZLE<3F{&M!bW`kq31#}cqXMX+<^UVDdg864p}(RJF#r-Ubt@<bgdPSs-m;0)@tE!vVwd-TKNd2P8Fu8D'
    '5Wt0izlHpQd^F2}>v(tV{?BImI=sBeXoi=~ZzXubknG?n>n=;R;VOV`Hw!YV@0WC0(LU}EXWva8&(={O+^-u50YU<RE9v*N_*T(2'
    '(5}Q@AZcOK<Z%R~((MmoClc)Gb~%ormefoQqT2AdktCshqHRk*wcP8e)2ZQkAvKBys+g)KFDc-6ZzN*)^v86c&UxE3`9dOpd-=M$'
    '0o<qUx-4|aC<#p_bh+&G6M>+}0&)8wap(m?2J+!=+S3kWFQgGZdPMl)Y$(i<{!d`9D*m)rK?8g+47<N&L-T>_-pdB#y&z$q^wKnX'
    '$FTWof@n1@!Uy({qlI;~L>c$D?C2@|^K~ocBQwX*5#jiGF?o!nk|U50s*3h)M{-LTQ?(!6(Eaht;b9ln(rA;p0#jVjtS+5wXmus~'
    '54J3ON;hN`oR^R82>S6H8jXi3?K(`*jX-eMKB8`^H`eEkLPZa8oFx$<V0J5g_(^FvepgLz?aBM`cGM(VPOU(w%cSEI#LFx)JpA58'
    'N|EM|?&&$bxT(Itb{~ev=dZ_&T@me8xPp*f{mv#FRpKqqa?L6j7IP59QMCWIUA;cuABW3O^Aae$0-lv9HZLC#r3hlqg7~Zx9Y{Sw'
    'Q`Hn7-P6nQ*Yt3v&0bEnV7S4GozyEsEgL616phev$e;R>;Jt|LjW=&-o}U7Ze@ZF-6AzmlLD!bDk@^MY1)7I<+J&7Rvk;udt}0xy'
    'Xe+mF$G?b1#ogDJm&aX!Nl4T;EmmFyuLi-O!umu=aKGSKa-nK?x8}`9H}pI`9Uk{w{kmFX!!8sOQL8U$R3(2vSYDyZZ|)$WB2{vJ'
    'U_;w9Q$3PA90*jDGY@U)jtV<xk3gcuH`3)oL{*PBfAI71+aOM_*T<h;-<RWc?wk&kF<7{f6Rj9IVI}Sj`m2PA%|sYGeQ-<nhmhLt'
    'K<kt#U6rVsN8yh`28uO9h8d}Kg;cQ%HIIl?{T=&J)uh9g5l}eT%{45~1tAk5ZNt8b4~>Zof>{v_L9Ns5gBuDt6Mwl~5t_IUQv$&!'
    '^G(BSm0RFVd>=&la8H|M)v${4)-9bFN8i7(9~5VoUtJw8Wqi#!mCb`RnkKZ3zP%!c_r^%(r8>?2u5HC%Q5knwvPwz3ws5lI;e?rt'
    'wK%nqK)zs|w+or1<Sx6vX<y5>y-hepCy1ly7+RtVS2@h?W!{K5VkI=PrKS1chT>M;VP(yjCBo5y^$HDjpgZk|K6-J=RP-FAq-YQ2'
    'AKcA}<@n^Id%=L*R90ZQA{<IJDoR#50n)2Hc-^W+4s&6h#Nh(d^n<%P-yg3JJ0F&gEnHT9>uw*Eur+m4hbIy^4+tJZADqCZ^ww>C'
    'Ildf&Q!e2??`<R7Mr04cYbvO(t6(`IR3cD}3IMIe7Eumk^ycUt$U^XO1Gc>Ujg7oFWc)(2Mr%+jHCA12J~c%XFj;$3<9oSvBlpL7'
    'wX-^zM_opIs&FEw)k7iaR}Fwm1FcR?r0oscWq%Wq`vZH4V(9#m&f$C4RRVU%1JhQ#qH3DsQ3fJcXhe8b;ZN2ol2j)j+t@0ip4TsJ'
    'I&QWiB0-ZLB24hJ?NNZIAeLj?5fv)pq7}M=L$~hf42%5vn6|fM2!;waZ-<b?K}i@cEJ5AXmvxlI$T-yb?FEQc+3lU*-%fC(lEQ}R'
    'NWgZQ6P)ciHMc>vCBMf^L-h@^`ORs`!!a61f#%V_dtzIR-`stM_df+!F|9&{;1r}VES$hKdB~Y~;oMw*9M>H3R1V?HzHUTCiW)`?'
    'h@^QKlZn#!<AFd#<1xjQh6(tXZoXkbi*c;g{6h9Vqy}U)gjI6rzeNJ>IGX<P2NZh~52(r^Yt!<P9i6Qq?q0rz>)z$<Fayq_PhnZf'
    'Vz{LB*4OpJG>x7Yb__-1&8gA3BvS{8jtGa_q=V4r`qr`UVOG6_n}Wg7A@?qH4+`02tEqAGJ+|JY^S-;IaI<R*Fl*zOFMpLQ0;#p+'
    'b+cJ(>3lIeA$z%fFY6so+OhX*CrYg3_}-1Gu$o{W{KtttRMxbfIvDZ~^FEpn?&!B~I}AR;I|S-t@RI>OaOzGDjj7#?Y^7t|$}F)S'
    'rknGi-?~U#e+x8iE4?qXU=Q^HS(h>P!qQ#XL%Oq~y5=vfOzMXZ>?HjjeEDct@3tMac;EJ6@G#;H&B!HD9U8jhX7wK>RG66EePmOI'
    '_35O&kEzeex2JGLMyx??2@gDsD;9B87{tIp!jPrxKenUej(W_vpUBFBxoZ-MnMZg%05d9rFe<_~kBHdb4td5-UIJq{K5bAAt4P+%'
    'aCK;rw|QrhJ&MmM$y<x44404qeqbMGGT^kOH$=0;Eap=N!)F=9!gtdAVINn{VT$6Dr=%UzN4E0)o)Q5!@|;P<%$O3w0p%rQX)>lc'
    'd@BV)r$klnHus7D9h=$i4g$bJEkv*Gt8N2<(XOOg1^)mU==%~+kTiZ^Ga)bB&`t?uA%6*XJ+^*z8D@J^OoEdtW5-Cq1|9_C^pRb>'
    'gj?rbkhnInDCKapL^Z3WQxa19(KQzCAa+5N1evLLJ`#Js=MV`egvNiv?1{eyt36}2aM61WL(jxp(^RP{nT`PMkCvO$tUq(lyS1^o'
    'A>`+RO^*nAM=pb%dQma=N!von=_CVv!kzw>OVWc0%>*pv#IfBFziGX3AFN_1;uv0Rn8xrYSEO$lPY2>G!`h!)J>Ik8c{4az|9-Q#'
    'Et4F=oMM(YfiATM>+nV!RaCviE{ld33*-Hi2Yk|#1op4}i8l~sw?PYzw?-1?9W<qCu`a=xSWM_}ELv!E3yp^Q3b^8(eXS+J?p=|='
    'Pw}!?19OigCDz$x<-r=Z2qQZU=iUQstDARqZl3Jjk5m{$Ig%~t48(V?`G%Q*qfc1rlG4mD=qt}}-p`LL%DtPC^u@T*sGd-ibq&H}'
    'Fr?}6(d&jm?b+E}k#7BTQ}OTi?`ds);{cF%qmN5W0f#WJEJ7oRx=5V`wLH6ZPt()z{FN=_!|`R<)_;SQaA*3^P_XQPpCXZm{p*Y!'
    'rd~k6Rqz#8@Z<h%H)qUZ|8O90EC!XD|7QAMgaKKoA(!&?hL<@+vr=r`90UFeJMG+5*b2?q69jd5|1l|zC4Od>5?VJaQJFGH@-WXI'
    '+f-D;yY2e;tdz^iG*EIJ#^A>EvGmCl$!*}^p&KfjTX*ywN!h(2#;(OU5uVm5?$sFMlo^mF7bHQ%B=qlP$v3~ZcsRqeZub@OQN3Hp'
    '4%NbS_!$^iD*e(gm8aGW`qk?0mHyTpoy$-8)a#cR7O(-uLz!^d&Atlv5*9Sb$xDplEu-<(sJ2L~2ql{jZ|Bs`IqtvS^xndC(_w-;'
    'Epg46H5uAT)efi-W|weL#`M9Rt-XQ0dx}|ubtt^_<_H~RWLhgI3#!p70CAaQ*Zy=|&sBSR{`&e73FH3z1avAO<zd%~+EsE{((G~b'
    'A`VeODK=<66tBDYb>7H&w4dK1=JdK6Nx$GNNZ}5blM}aB0<)-t3^KDe*HCm5!drc3;7hfHcU<3pWJkyG7fF*URoKKWewa6mFv3uY'
    '&XpdGIX~`O_>BqW@US^Fu*ApimTMBGpX})`f3%renkec`bzx%9$%sJ)q=nNGz9gfX)$P|)L}A^(qr~<*eTr7RT=L)Z%gbn#3J8TV'
    '11f}$M?SJdNPvuW!0$1xKh_;TwOn~`Gv|Ky`N^FB>0HlW-b(1_7I&F>RHn`ah13YpiYbc(1OrF^8MXEby7N0**-ZUi5D*s3>d^V9'
    'la2V+L`BRG7I+apYZ&|0{_pB#7(tY0g7NzILGFFtV7A8i2wsbxMib6>Xm}8@B?tiw!f=4Jm1COHM|QFGBt#T*2*Pd7(Il=*F)po$'
    'K_v_#nZ2SW^2y2er_raQ`EZC2n4S*$c0c^FlCC#2X2Bzl0o)Ab>Y((hm>akga)J^X@LsFkuOLI6_Cd-wJe{rXPAZbE`k34c0W+cq'
    'Kw}9<7??H!l;%GE9J+UAiqvx5Hdu4tJq?is-hGL`ZuQZ_^p>J#j#Qah6QKm++L8rcYiNM}j4{=+pYHly`0t-Ltk}X^q>Z@%IJ<xg'
    '%#bl)iaxFy{8_SJora-lu3P-{3gQ^-dJk9?a7HF{NQ<mZc#~>JVS(c@a!?O#t|5fg75ccd%qsLV=bCO?%Yzh4Xv_>7`*k!e6VqE;'
    'e3H1RbNwmyI|5-nUbl%e?D=*OHXP^_+9{CVFnTsRWC>cHf}5{Q(5-;dxC422<$2V1;`Fpn8kom)lvyhd<&I~TIu?Ptj3zJd8Skj2'
    'MmI1lUAF^-l3|@Vxt||EY>W&jH2WgMP*LyQ-A<$;PR4)<#{NGwox8Y=Rg$tT1sU_uA8@fC)M?_HKtNVg3*Io0(ufb<m-A9z`5Mk4'
    '`iDob%R-HpMHbr7E+*?ncr>DI6_&v~P&R`fjf*s1`9}1#Mxipk(2eD3z)|^Ge?^4_qyu!A`K3cU1*OJq%JhO;*LBOk9%OniFB^xE'
    'md&r@86Wp07)-w?rw8R+fx;4`-YEdPa=v=)=YJixy3;WsH%Oq$f>6e?hX}@QOl4B(F&hDW=b?q(y>__MpJ+|r!n!2p7Nl{H=TyaH'
    'sla><bX@`i;I4FMhTuE`hFEUrF+-s)KDd)jZIDT7OaQt912;U#IqAkkSd<}SqgL-NO0uOIuir+je&%}Zq*fU6(^E)MH^zi#kPYWM'
    '_eB^bgaud`_%h__ikB0TpijZ${^KvH1fRSldaV%iCLfO9pYNlKO~wDpXy%wChN>%&`fBi;D0Q3a_FesQJgmBkRpW8D+z($iY?-6='
    'tVJH|p*fTS;g%E^eNH7T_X;~0L$He5cXZN)VtXiazids(VX3#oU}Y|ULKb9+r`Qq-m>_-Ys>MtOW8eGRw}Z8Kq#!=OJ+l{<C)9=w'
    'C`U&xT=L2?bS8YnboX3#=CE}!E+bT|HE)uwf++>SzK&`dw6A{O7!$?2qKp7qk_WXsR=g2p4rc~E2bz?{jMZWb7EQma6W3n+E(^j?'
    'W(Ur=cAQxr@|YH2vvydsZOaO<(2sKWsy>U2Y{FMKk5e8KkmgV@mSKUP2QSK9>MK<;^X=a%)z2-ae>3Xh*7@s}q0JK1*hnQfA3_OG'
    'F$=yDvmu&<1=ty8Sff4VJJ&y<%^L=RF<n(-3kcT(M#9}*J;NJnj!uQgPGXg^W#@`#g}|Gdc2BR(Gz1xeON!2fSs<-h*+lk8cNSfn'
    'saX3>o4NGc4vtS`8&JQ^sbg&n7En;fyyTd@Nj-`CUavw0E<(mp8G*Z*v3+0mU#E2OC{5b3E9XI{qiOVnNdY>qoan}2+Xr(%XE90G'
    'jJ(Bs-MKVJ24B*jk3N{1$ICCB^FbFxs2KM>g%qL;6Ff>0SSO|lbV^Y@U$=o($g?r*3e^cWf=|m313>~vt-^I~4v)edJHSx%BHR1O'
    '*NMv;L{vIP<yZ{10s{(Cd^cn0m_CXv)I=eszHW*d4#z-DBT)bTINiOxK5Tibh3dwg1+7IaC*w*nq?1P4cG#B3h$-rzX;bzZ>#oRJ'
    'Jl*Yaax(mSl}Lm#Vu_Iy@=<8j6jF6`A?CL+y(rtW>K_ji(ZMWq?X;%}J{<z!gdL?K>tdp|^|Y?yV^$WmY_|)^@s7pMeyS&Xg1c?='
    'aW{|~L7!)ciPc3QV<^5pAsxJYK?Br^38BWGrGdK3AJ_eItJHy>W+ooFJit?nB#-a8xn0zs>+5f-O?#1F(!;Op%|Bz+z+qe)8$Nkv'
    'W*A`+bD+?VQVgP<BE#oHfZ#Hlq3J{3lr+69dYTg+BO}M)q%DUp8)bhTQ+2?BsO2ypA`dx$^dnO32%Y2%EH|c|tH0Tozs;DI3Vlf%'
    'Po4Mv>gq`Cx;|pMU}zZM>^j^Xp>*OWwP3$<3oDWHaM9QnAj{Vt!5-;&2tt=gMxCLmz`sjQUKYj4ru^`2#dE83*URS2sL?~D7NenI'
    'e4cj-SOYbN?GVd7)}}voe|~@EE8lod`yk^4a1j<P>sVB*UN^;1N2by&c!8W-x@)$u<C#-da5Zp{)0$(tGU%KX0Kr~mQB|4YJ%!)j'
    '#<Jgx6B~A$r>PXZTGwL5pTOU6GA!t+WJEe$Vb!UJx@ekiEqa_^!&c<=@u$k)AAe>qW=Qd5TCC&r&ddN_f{PW&Ai^|`Wz3r1te8(L'
    'KCc$h&%5eU#+sT@Mc`!`4aOqmcs#B5j7x)DWTbTTWZQA?!jGZkHKJid>8xoGOo2Z78cnzkAxX*v9ORg&L0m-WGvu2ri|@;>o$yV;'
    'H~$)_y`BN`l4wbx7HFMhL<Q3h0Zov9r%g`y_f=Q2%Pzkd_Ha1*Z3+z&Ma<HM6EpTIf+TwfZ3H%~yu<39D@R#z*ydI@;g8^tdYnR('
    'l|rT$=@66O@Wu2AbN$Wpe($0ykLFEmL){i~pv`A4`%<gP>{x)|T$;myJx8%k&8etvxi+XF^Gzb%+a}KR8MWh<!nO+F&n*diC14@e'
    ')H&C_Z=#oP&~f~H#bkZmx+@;5Sbp44_jXz`I9_ZQyNKOk4dj3^i)}*;6)rInw0Y;+Z>mBm+2v(jghmd<<WfCLzdm>;p;aMqG>(rh'
    'BPR@-yPeA}_kV0SW|?~k(}uAN$k07GPQy}J`(M&KQlS#(!U}dScbHcTrs3C%fpP(;Yvaez>@4sIJ(ey?)DE!gX%AsHD+SzpoK6jw'
    'hxDpkyqwX))1hHtOzmG4Grzy^OQzm7CL4D~Ng>7VhrJ8`^7`%a8LGq9FlJv<spp|Z;5SLo+eBU)28_JOVtz}rbG_3Lvb*PR5QvKp'
    'SQlpq>1XI2ONLI3dBA;$o20}!C@$iL6kyrA?i>Af`_<-1b^!!1vJ@;GBFY$8iwZ`B4B9%Yb~7%ft5@C`seH0JCs+r`kFKN`VN_ab'
    'e;a9pX-m#c)wpc>VSiu$c>HyvkGVE$UGS{v`_SKvMALjV*wkW%1?Sgjk7{p}h<WQ9iYOmVI3yEfyZDIJ`0Tj>z~Lf=6jpVPcU|pW'
    '@AdxWu+AyHToxL=6dtre%L@T7Sgns1e$3wl#xri#t|@k(r?<hM%V7C^%1?l{(3HX#Iw0j31%*jqmI{|W-dr#URWsOU=MH{wNZz%)'
    'aYoV`UOWiD+*HGlHV`~up4%@43Zo}x62s2r&%Vf<)$d=vZlD1n_TWj&QISqYSCUnd`c!<@hvT|mBeIjK>|FSH0xxZVN-%qO?Tmyu'
    'g%>K%%PL?8<pBnk3N^xJTVAuEXT160;vGbX3wx2FzHdjX&G4ony#0kOk~%n>>#*OwZZN4}c{>1VuwkfmmBXOuHV}w#8WzDgRFFYY'
    'V_SM`_D1RN?nOTsQC<G&)DTnC#w-t?vXe}x4;=@cI^&KyXN+)y-FpY0Fk2w`A9#+xZe;L+A-}TVW`Q1JUX`5Eyz)hmv7O*e@_*Qy'
    'OP~8OYkrkBWUo~i3d%j2aQxG-QhSG;>q^ihA{0dxjA?Jla%ys4{;i%Vd(egJkcmiY&cLaS;gkY+xRGxFfa+$xYQ;O8nTz)!1eUKN'
    '2lJTDYh;DX!t$81MO6OG^csyj^0MnzJ!L$H=i?4NuOUIy-+p2d(y2BWJ<%8FRZuRI$V^<#L%I8Rvo1TWe>wBvey0TFQbzjegId3;'
    'Rlq^tr*Z3uo1QuC4I{6QE0p;97=)IMjsRk|$I6~KocJU;wJ%$(p#Kp)5=iP2v1RW~aq`gIS2FlY&GjnL$kyy~MuujzF$bL`+=@zr'
    '?>JfZd&`xRVPqJIJ`FqEwM|C~7O`_2vjkS6xVyQD*(4#t$X8nCyp<VH1wQ=#bb7;|@BEdu`P~L-rVs9(b~C+V(?T1Vxw7$UV<bzI'
    'OKKSE!Tg$q-zHU^M~+-RYIRt3^QCiB;h+1tkbv+ysA7;s730Ch@uIkD{j*d5KI{50$@1hwe1}P<!`YhA6V%r{ri;qUCi?7r)2;6>'
    'J2)c}_u*y!#QFtVu;J0k_ogE*(-2{OhbN6l6-OeE(LI>L5Vx_}<R<)O54#rjn6>xE0NZG5^qf$&eAv-q)g$5<6gJ1@R9(Gr{HHgl'
    'A&fQPnKBkEMkO*6Qjo6p6lnwtpdc8Ui?elyoaV>uI%;8^W7_WmDD^2hafC!<sOp{6hv#;K{T$TwjTIjckAx^&iI~zUFqbi=MpiMP'
    'U@iX*$B>tdsEW}>-nKdV+1Sb-FR0*+P$g)ZRzq0^J7W%$M;&w3unZf337Xz)0t5<t<zzxoaPYD*ouGwS7-0r9#U~qcC4#h!`ZaET'
    'G$-$d^;=nq0jGY`hOP%H$%<R8DC_j=jiWdFK@7uv6rzFjB4xhmH~g$c{cZR@knz*o&;D-vw|i(JZTAos2{GEMim|p(5Kc0MiI6dZ'
    'pq|ND#%(t2o(=68sz|}ip_PD6HBU{{#?S_JpR^dB%%3F26X44fAKK2oLoyl`WhOH*8V*S`_aSbydwIxGN}Gy1rrgw7U*5?&{_$}*'
    'Y|JCfXOqS>`lApnA`++#aJZA1o#x{N6%F@m(>Lb475IA8zI%Lg4IVW2fD1H_T0<UPCIn4cAPi$@tI(Fkp?aA1E&LLdFR{I$6!8=`'
    'OA~G1F?@oD5dCXOcOm*G(KDIF(d<LoFt@wcUM0Avt35qEt)nP33%4vx*<d3KjR-aDRf60Rs%hqGs$dTs@GR+~hP`4FS5laIAT#@c'
    'm^Z073$&XxR~D5^9S}6W8`IA1c?&=8;Fs6PtoHo;A{m-mg@QGluP`6*`<(kg{^!s`M#tPVfom4O;`C_(_rWS!IiOL(WFdq035M4m'
    'tW>u!0Nn11)vr5(WT=9W!hx8GX=KTt5ens@C}?8b^#oKjDroDL$3tK4ei#_Pe=reNKDf3FAvju@Hy#su^qevp^*)3ghyq~1>DmpP'
    'Q_NknP=OKV9#5ftn@~a|`lgk2ks09r^!iXL_hNG})_YsnKaa`>(1uNoB3c7Pf`HQo-IaZfF-4(T$B^XLZe#x})+JQ;;*I}Htr(_5'
    '5MB@&b=Mr-8E!vy^k{C|!5d5Ga=ByX7Fq<xourd=$|%~v$<W)VB-q)M(E%Pd(VG9*!oKb&g#fFQVoX?^#-F+X0ly$<3qzo_CWD}y'
    'Z%WDkef7Um99ILBjno@z5)M5kjRJxZMYPD|{?R}R9S{7@omfpD+Qts1B`#FnPpWOXux7irkG4dt%^NU}AsQwWgKN9|L;Ki0n$>s}'
    ')mI<b6$=CoPemA{_mM(t;;{)+7cXUZ^=4v1>)pPQUvW9`X)`mKcB=!8i`rr(t4*!jN_7;TT<+|v_kh^*kiKk-FX6SGf2i4tFrG2I'
    '#56T|JTfeU2wL^B0}O4FAbz@m=kT)Ix-WF$BSoUR)ClRr4>{;9DNJHnSDNg?^{>t5YeU4_bj@8;1TE98B8e=_decfjS!Xsu+~`@F'
    'P=8KWpUSr_?4DMO$+jTdSD~d*H@5Y9jjMaY5<14{>ifpLog4S@eK71UhjUzDqmY&&#%LGe#xq7bDW^aJ(q+bZiy@%JaP4MJJ$>oL'
    'gp+g^)2f~}I)ts%MKJ^U1~kJy^#-Sq0Aw-Fc^FV=C04iYBZfOXtQnSzYIFRkUV9s}4d*-yqce5rYE9cTk>W1x+I^ok`@`?-<&<ID'
    '(Zdb}9!}Pxs!>>k1HM<I^1`{GNJM-@!*G&d0&RZVR`xK+IT%hc1d-o8FFe<rDs&11bJQ2}dgqv~4OYB1bV2Ajdu??>5Vvs0bwRMG'
    'CG_gK2$fndE;`+FR3o)lJzX0${wi9y+XeiLg!33`@IowOf)(8n9@pf5b$qX=<pMa=tG;q8`wX+(4yMG=qhh4$(NK=}k=ustFZI4}'
    'XKw29+FX0NKYaP>EWDmC)Nh!f8-fP-i&I!fTh-_T7$W6c4jF2Lk!@mxhDH#Eug$W)1lacwR;ZEu-Yri)*TbfoLy**I)@TN+w@k%g'
    'F``%@4HU(Ss7Gdhy>=_2IAX)_@cQVOthM0rxNOXE(?`%vl4c<vA&(+!`!KjuVS8lACHkc0G++Br%&2|%*;VqFJ{GE99oDN*Nsk`4'
    'K~IaR9M5w&w>EL`(~C`%_urTPp}DcXkZa7KvzR6q68;!z!iZHTkJ1Nyw<h7&Qxn&DY>wA{vIykYF~_kwB|KTK@QI-zCBj~ePjlzf'
    'En+nZ8$pMuZ{NozY0P{M|6|NM6DKHi5v128d|XU0Q;P&A5^e12dnC4Sm13d{pJ&KBgXcU38Std_bb=B}xjQD{E=HN^=!Sh<p`fq`'
    'M26c~;9?anJHoRWMVZLiMJ%aS_n&OKVHZ2K40=!c$?{+-LoEoycKsh^Y9A#l(*e_ocz;}7rJW>xcW24pR*8lK)f4ZlQK5Fi>1^0m'
    'aG%l4wJ1m;^Ex3gUb~0uNZ1Nto-3k-FVoG6`bKJ*4Z#s^Vk8j?xWjSvgAg57H=%QjbbHDoM?B1Hm<a??CQRiKV76k~aE8ckhVX{F'
    '`UAOU()<*yC``xjQW6|+(7?%*ikRC9<(N2J)x*{4?|BEl(FmcthF)tF6Q`l2Yf<8ti00h8O!A<V3!Af9)u!!I+_sU&;~LW4Y=`OB'
    '4c7?(23l>L(vZ!00}50~H&&OTDQ3<uL4xUS+sMjO*z;mCNhRNhBopVL6tmw(nuIP+W^i&6)IFvyUK=eQV*S7tgRwzAzz_L(13l1L'
    '%wlRF)}p)11~k(7j~G{xhi*4$e&f}j%DJz4T|=At3PD7%Izd;Xg&S0RtZVyfVl*knql_qTZrjVXt!+k$Am=>Dh8Y_Ik~?h>GPM+z'
    '7{2Kye7%cyylpopF3qlu;DjM1xzupMVH(v60<Uw`+VIiVo63U^fAuR`MW^Tde5d#nx}Z>u>7+4U8PjxZ>fl0Rjt_2L9$cPIGhUkt'
    'J|3py_nmBq)$odxhFK>Fw#01o)gDkDyx%gU3cOs+bsKKk#p%6#Nk<ksTjWrKjPYI=oEW^pHwlv~lw=4u!7rD8gpzK1$iz>#aSkWk'
    'J7Sc>;b9ANF;~aksv#v6nnEq%zHxAk{vks`4<Y8z#>;PdByZpH733Jb3Z5Nw6iXI^%EVK}Q<aCuQNE-C2R(zGU!AwF+xdY+yBi|K'
    'c~eX(s^vhMX4-g@`_OO+moM$5{Y_yzbkla;9L<&3U-rnR+Mpl=bz41GV*wbMBA_VuqXLH!>2Pc94L5y5XNK?I=aR=nlp$lFM+u>w'
    '={g1h%^`?X1Uocg>zggtUdn&oKOq^|htshVRL|N=*aw1Qh)`leB<*!rX5iKVaxtr}%^SU)F|Am3)Op52Zx$1A^#FvhV0iK1f=pb='
    '2%k`~k)C-+pnVyu(^c1RWacIM{b6`jUk<C&z$W|07gNWyf-Xep_><lm!YutNP(p8T3I$r*T)QFv<%~S9>4E_sB$62T(T7CZiH#Ws'
    '>v3QVPccoCA&z)+?MC(!hhrr6pzj;hdtr`aFa8@^&1#i|a9K;RsS&P?a&Wq{%lu@T`(P@-#x5d^_=*EiC-fk^0MdlbMupT$jv2w9'
    'cKpg+T%h*;rOb5G^l{790qARXv{7U9TJvRCT@wX{o6B<ThZ6Oz&m$&LZcS#O8K04tM2r;XqcJIi-+hdIW4S3MF+&_Pue%ljIkRl<'
    '&eGR#|Jf*QkhY!0F8r||lvNNAaaQse%nbuzq8zQ_{>p8fRs3(e*(B)bA>?>#brpQW;A6N`7$(S22I^{!LclgWy}W)K9CSn9Ek8Wf'
    'S(n2WVH?(7%#uWX4R3Y~nkEL=`)0A1;B!9O=Gu?*#6x~e8=+w|hF!NWOtCWawZu(aVD?XK+;ZLp_)cGTu5Ma=9}Bt*z|@4;Lf#Qh'
    'iYzl)u|UrpI;jh4f1MQm+V`;9mYpn0_CVP|&RHBp&Odx-%&e2K_pvFpUJ+A2(a(dnv9*iqBGMQZz$PgqZ+M8g%2dHrloig5>HvvN'
    'X^XG2wd!~8jPIA!dA`ub$fF_H_C)<`qXu0iy(}&196u!_VZ`@S+}-2u)pxkW`M5EHa41`YmO*>*;z?*ceWdV)jfTW(Nt^7PKg~k+'
    'M?Z5l8&rpkmA)jY^?AwsYmIJ<R(>=^@Uh#pY4dvyGw<EIfANkm;SX#xqu!bOQn+CWz^0fGuc=JON|~<v+;sa^+#T51AacUi6w`;{'
    'b>y;{`QRCqq2O}aPeGm)b~k_M`VH^P0ZVjlBU-wuG6T0qbfyPdr*JsG$Y+Mbg^63gYsH9J`;-I(?s#Qxkr9?I+m!S*R$>qvBciYw'
    '3hkGAQ;ht>vU?(h0Wc~29-A2CqdwsgY)EPxYX}g@J4OxEW7BH#hgETsqYu47e|9MjL7vaUQqs^i$BFJqjL2dx3~ME`dp2v<A6DIY'
    'L(rt;6;Gide6n<y$pUI{Fl9ZPbt4X-8AhyZ;==#2@QxWyxVr3RILS_3Oj>QQhfp#GNI|Vo?z{ooegMLIOP^}-Pd_H?pI)}+&C82r'
    'K{29}Q3d3vh?(4QtSPPmKHTDTt*iX*ji{zvj!)mBXGj(@-2d@EHuOhe0(0aQa+%1lTN#7xO}a*P$RlX1&Tq~8R<=K`cV<ln0<vY|'
    '&owkuCVc!mU^dS^Q9<r24Ur`C7LIy*;mUT!vS+-1d+q2*n#-8t)1f2OehJ(D+H7VHWlMrJ+l7O5?b>hP_Kq#UIq<~M@KiziUSW}H'
    'l4iIi5M-wiW~7)@{qCt&^}NI$J}D0uV`=~Em*?Zdg<lN+#K*-nis2*#eSP@M6EOzu4DdxqxZsJto8wsJ7o?0&Ynv0w_VZ)><K2@j'
    'p{ByFGSCX7RIPV{$r}dNp;%G7l>w2y&&iKDpy%n@&!1xW=6}8X{&H!?P|-uow0LJvkQhP9EuC({%#c4AU6II9yf0-F0zbX|$e#-`'
    '{$dDGgiF1~ZR2N%#C4==eK>+k;b20rW-X)CUs^5r)bUTBR;+!aD@7}g<iT!Qy`WQR1|r&?%0Zj3#&w4=aEX7nZhDqieZuF6-om+X'
    '^(S}dKe_vET5vgisbhdKN(=i-ULwY`;W(JVD0d020|*8m$G>}T6W@RDQ}kt@wgVw`wThqvoaZ6%k*x5|BiyeHwNSGUVMb-Z-p@`@'
    'v|K-r!>`Wi_rKi;y5T5qc&rLQH8c=mlI*t_O<XW0kv|V1ZeQ(K>oi>R<^MkZU+I302mj~r@^u4)b+O{-OSlz6fyIvTRnEgY5HA37'
    'Z@c|@L3&zUlVtk(>CDa`Mm#=lmVF#%nL(nnY1UvQ&}(3#_R(?;vOJSUms^0aJJ&q_b%RkSw#Ps_lbZ~h51^Y0%{a!0_NG|U*aBmI'
    'niu}K<SEPlyfWxErf-{?iZkbeE5hf9xN(rQpo-Bdg}(_w3eM@gZ@pO(eEGnZ>(`-D<kg0rrhU&7kcOMilWdG{e-_k_pHk9(vfh_h'
    'a}+n8XW0+Y6@@ptE@gsbXjo^ue<T)6F2n}h*?!-84ANe<hK@EdDv9BrA7r$-=;!&yn2v~r;~3VpF%Wio_mi9spH4;x&!4{@7Ut$~'
    'yVKmZ$Kysc-~>mK%2$zXER{0MJN)2;B$zx*5mQ-Ef>!KUI@a3eL>O&vCLH7L@CRkp!C?_7Lz=63RSuzGVwPI}R6q3}3qGwt@|H1n'
    'hzlp=<1Bnjm?=}^qTv$5GKW>TVa2*z$}H_z@%3?&nXfb~5zv92eNbJr<;3+WTKhJ^LxC-sN~#;)TWwBZu#MjQhXmKx{~T^zo8M#='
    '?q6gOQXex>0V@rGihBjsyAG*21+X`pU$v^S35SiEX$)6(9SM?AOS(0b;APlo#B3(K4wK~SJWE$CyLo|4A>-G#LaI)|U16Xw2()3V'
    '1ZZu885dJK@@p17)#8_L6KbP?{lm@Ia0nkP4vUHrl16we@x@!!=gi()7H{a&`gwf%=PQ_FIh+PG?|8XG*eOSG7}R|^Sk5RD7a=MM'
    'r8qevD3PN<dF{%3Xd;9QTx~=IahByCZV2NSX<+!IgyMzmGWV+D>R<hJD=^h03mQNA#ws+B$`AuNT-!?3^(EjYz}3q9+J$$_t&K<&'
    'q|+f>ZX`u9`VZTIn%yYoFlG&YM)p(u;k5Mg^K1Hq03&-@?HeCohAp{*pIbOV?o=5Ql2#E80*<x^?gp>9pk?8G-0xa*`;OBtK&P&T'
    'mN5fizz~yn0_9M%x>`Xxg$qb7ylc5VR~*O{AJYUE)7BSuy5g1BNdKU30tp!PiCV5g-OdGHwlYuDKI&K=|I|3)>TedRXUTCbzG6>P'
    'A2Gn#cax$s#&F89cjQF&?pATZxWkvQA!lv^<WS~||GK#NAu5e(*K&`pZ^huoaD`&k`=M!($@^5o;Ue?T=0-6BkMNs^ac;M3#h<wY'
    '{3Xtt^V0bRXxPRB0`U>?Bla-6iqC=)aS2R$+_l(g6wn3<id3qPVa-gR8%zplHVj{F8zmxJ09_R4_1&-G9M|9ex@WFmkfv!Y0!!_K'
    'GwTx9p<ulLWmS{~-fJ&I_x_UdpF_mcPwR1celri*u!_mMXl;9Q+7gb5hv<j<Ukrq~%ECCt(QU6@b$c8}?XH}Ii8%o~`2mkQMs0ZF'
    '44Au0&W5QRNqu?!(wh47aap!x^qg9G;mQ=Gf6)%p=O2RF-f1Nd<a}Y=Kkr|iOz>aNK{<SU-Qa*4GA7a@_VJdk_+8DaLa*1=B0<v-'
    'A_6h8eE-VZ;X#%J5$nV{sY=*Q>qVJbW1RG0mW;v)W>)=N4fo!f*7@iC#v=wx0l<ucEW<Tnow0{+8&rkxo-`i-%HCDiE_#-YZwxub'
    '7IaPXxzuyzLu1Muzua{wf=~h6kGafEcEwYUjA7>(F@#?7EgIx8T3-+=1o~1oP96|5PGgFf(k8F>FAjV3;$DW6u<Q4i4ecYMSsdal'
    'gwSkpYbXO@kz}zC{ioNia!yyA?T5#2vGTLosT;HG82$`djBX1eo?%_VLL0*-(Y=5Mr_Dfl3Hsi@_W3qCN$WNMU|A`V66>Qr+U)`-'
    'ujJ6l$DFLV7sIr<$*+i^@#lBn6ZXRvceV~JKq`d><MR#@X3d^~Gi4D4AOAJ-y1Y*N*AIWn<z8TU3vQoQmgeVkh<p3f&nI#2=X1Jn'
    'IEz&e``T;<{K@STau=GDUx0>|V#Za8Xv-TeaXawv>h^#Cw*PE6@7#I=ZKiRB=HXbVQpSK1VKh1(_{!WmluVAqo=fE9g85D`{fmvf'
    'j8Q)~hj_>9<-ug)iBF2;JoLRW@QUx%uDBK|BRb8s<FF%&r*PW#{irZu7G`q}%8-E?jd<2~#>ltune{ss-VL_ZaSKnGF}f13FuPVx'
    '#5gvYSoj69o=#zL`|iyVGdPn03>&DW+b2QTBvm|*00to#LQrjSR1n&xpz;C}->u_MZbF~NAchQ2dwv(MQk_Of<<J3Q6*+Rt=#8~8'
    ';TiH2WPBZzck}b-r!V8(*3W8UNP4h7jHcm=FA7M|Gff+=LBM~v5CaF%_}xVau0EZ>^~4<a^L$v=;fXJYjSi>8RhNki8jVjlOu7rg'
    '7>u22KnRArO7OtY#omQClR3=4$vqS1;2J|p^d@Y90+VoXsE!N|F=2KZ_AdCBn)z}aGR4^G&QI%^mE(SpbEFu(6yUcz2M@|ootnKX'
    'Z^Az&gEXP5qHwICY&>CHHKg|1MJBkp?0BO9FW<dn*0tU&XFd;W^JK%N6mLsyWk6eS>5GtLfN4{p!=etkI>iS6rS}i(UzZeH-@1zz'
    'nE{-J>4KQN3@g8stT2u+lC%Q4H<Z$A^^fDeMZYVMFCQb4&Mc;w!@D`l1PMD#D`EY>a2{l#sf0ES`_|k6wV0oXy2w9jK>r51u*;xN'
    '1F)|z83d#|2a~AxEf@&&w}^I^Kh8OfDNKT+_4g#HBct$BT;c^HZ5n44<~GaD19ajM?`gbAMa{Q%c$m1+BJ?4u*M@R>06p$3rnh)Z'
    'OMTtC8-o*Q3}Swhr<f?%0UjJlplS+h6hXQ>6<#(r*DZ;oeApNtg{!29%&~BFGK)4sE{h&-7x_#s8nwVur7M?x%W5uPm}sw_G?d3Y'
    '9S@f&4`ytjwVaBEAP}hws=aS_6Br@;c8=IzmC?%xH6;vh2|ry8xH{&cp`hjC?$tI4LsDoO);x5*Q&cuZGszy2!tgzU{}sb-%nh!t'
    'TJdL-d;SW!vlov+J;n+GKTDjxEV!GdiwaJtcG{c9%;ftPeU^TX$ICM+L3V})c0n(T1H85oaI1sbj1m_2jGJxfm#bF1+eV#5xNb>8'
    'k?Rz*y9`r*PASsd2u5{`2=9MBq;g}~U2Ijo)Fw*hNXPK7bXwaXG8n2M)2L$PG}HI${f_m|mtQp(8!R;S1~>qasM7#S^yMt!G^%AT'
    'ShW$P{AqLDx+g`$<wyb0<LQRJ*@{m<b!0<cCp1!OxR`hy&!c!hL;JUd*EAG|^Q=d@{H)FX!fgp{y0BYCM-mjI-D?h+$RT}E$d>iA'
    'Z|Uu{#ZPjPX3+?YIXaAa2`ec#5Nmu?Bnp~!^?z!?|JVQV{{ViV9di'
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
