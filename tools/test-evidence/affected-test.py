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
# c3294f6fb00d2821db13d753b61cc9df4a7e908c / tree bb3d08382e85e64ee4ed0b445ad96c722f9c334c.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '7b85710e2fae077901abc892fb4ff0a493a1f7cfe2997eef54ff3307e1d0f1f1'
_MAIN_PROJECTION_B85 = (
    (
    'c-qa~+jbmR(jDsi{TO|1H1mA$Q+VvL?=kX7mIR>CI7p&B{O<dUtO7-L6P1|-`taMo)uQBHt1@%NikLCyjQ{bEe||o^e0l9Zbr0jy'
    '@i5*T|9qI9ZeE_chv#{E`sZ)Y$A^FX*Z=X4`{OwM<G=nRO_Hi8{_$V_@%*Lpw^^2?{-;c{W=IGBDM{;jp7MSi$|@O}bWZYlOjG|K'
    'UcNrYe?fnD?EmpU|I4>!dkYO;ZXS<!hvDnWYJH#k@2aM%t&_2vhNi0Pp`VhZPUgJo$7HUnqDz|hS9|P+-@DJ#&7a4o-{-sIpEsW;'
    'zqWfh93P(77N4rIY}>3T%5tn)dnl%1n!9nR)4cVMx<0A>==T?YnjVkOhnM5i*PG$XH2l7{VmTCbHhZph+RWqFPSe!RWicnk*!rPu'
    ')8$z)^~L)uzD&<AH_xw!m+5Al9;b(KdKeDV>Mu>QYDmkfpT;_G>!#}SWNw<g=*oWVn<DKqFTAg|th=_>Se1R7&GDJ|Z|t(JE2p~k'
    '1r<$Oja^lxMW1@F@2~atDxbaFr|IG4=3lSf-C;fq%Uk{D*ZaHoS8w}ysOF~5@;;r*w#cfvO><AZubV8Xnxg3H*(bhf^{3-+)9`W='
    'zy100vJOk0b!FET!!S>E*{4OB7Gqj>X*(ooHG1cBHnm%p{m+l;;?hmp4|Ce)`7{niUN%`ZW#d$&X;(W-!!Q=(G}OaSo_GIbIgw$w'
    'J9x^UhQp`drib4T56_=Ick!MdzrMe!|N5cmhau~WqNw|<XvS*D(z=|+vhmyJa!Ttu$@Z-J=$Cupm)9-kI-iPes++t|hB_M?Uvl63'
    'u=+Wx=cI0uX&Q!o>mK{dtIpkACxg!@o&CNnX}cuL>%1?9c4~^Dp1Ywdn>^jK>eK7P#WjbtsH$q5yS6Wy+Ry9Syh>WHJD>U~D@MU-'
    'n&(|>#+Q6Me0e(FPq)v*@$vGnZptD_JlQVIt7>S(#<nZ-u1?CV5xdG^Y{w?u_pFy4JaqTdv%o#wK26=@;o<YeZHx}BLp_yMA!<%('
    'G399l?QZC+q)N-85K>%K`?v9Ue>)r>=ELRno#Cl!^0KO$v|FylD$kNqY-`GK%o3Zc?J?iIe%#CB?O%V){l)cr-&s-=V_DWNi8Apd'
    '%C1d@%nj*_%sqv~{oL(d-xuhrytwu>%z4w5*(jRLdEE;nX`kjv=hhm!EN#ZTsFDr8JtE4V-PcbK(@R9U+o$8}%XB*)y3Y^C=a<89'
    'Iojmy(07fXRu1J<c>QfNO`WSVDXY>aIQCg5WodVB<8^$zxNz3gRXU{tsvD&q+j#nR;xe7b%t4r4b;VTIn-@NPc<0rZ#4J9+m+7yU'
    '%K@l#*z2jw@-lCP`q)(2PIX_7PGdU_X(B#U>*4mUlNY`m?+?R`u=mH|*^TM|e(GMw!^`dY#*16_;)yKFsVl~;>!&H7MZ<9{+O{Z~'
    'h>2-c#>?<z>Z^CNoXR*HcipR8@^X}_t9%$U30&cQ$S`_wvu(0=o+UfUoTgJE*-Eb8%&T<ra-<xGE^UUaYUZT$+q-heYFC3}BHb&S'
    'x$MRw&!+V1J^VgBJxq7E%Uim*lQ!!;kg=|YvF`JFE|P5S$E+&Tx~=AFYU|qfo6T46<i2~5ZjZNee4p~u*V`|L=g3tq?kb6ktD1|Z'
    'Po_Z_si)Fq<`$JJq`4g?b>S&pzpG>KU;1Mum{mhmE<@RimPMb{wXe6!lQAC}$x}9pV^#dq>v!>Zt~|QC<y1d)!^`Es){I4y)kW4+'
    '+1ym3dRgZ6Fg9J4`K+@dX~!vR`u6HA$*JbM!{;wAn`3QN=d+9|>58&<wM@==+N5<O{=@?s^F+-y*Zl{!w3cpp0HsnhsoOlstE@@0'
    '$hu@%9!cx%B~7k)$;PX<Anh0hyTcz2_U*SvbU6#~t*8gvS^ef2<W1d(`+X(&&b=ymP6zQPx&E;{zc^QyKbF>~QODAKn>SMXbe>z^'
    '?chPx%E`Je^S1oJDSGLiK2Mu(fmy<vbi*k7m@D7N<Y1>oUHVAsctUEwv`wb#-_j{teY*<!<LkrNtppmMN$bOro_j3`?4qki|EH{m'
    'B1`+KNV-&=P)xsQPaCeMd{Ug1ZC|x{kxx*CA?au3VCqY5MxSv+oMBErxTEEcy4@58hf@BYr7lbtW0Or?H%@)y%U0!dd7hW08oK=G'
    'dz&8qI6NI6?){6WS9iIr%L3;Klpyc>z8or7MBi0YQCCyf^qFVoMj!K!?P>EZ+H^(T<*JGrWYWNB#zJ)~0aIS~a^K2<x1-|MZRhqN'
    '3H*GzJytTozHfX`W1S6&K-_y-eOnD}<Fd%zY5g>3w)?TIU3JU%H9$*3>>Hok8n{*uQ71NSmJV`}VlMJ-Y=>X8wc&Wb;3R7gteU$i'
    'Zzb|Yn+lZiJ{w81@NKu%nD(=Kw#mm|v#aOnkLh8hs#dbLLm4kn5h(y9o>!Bku8%CA8fa)Pkar*3&!$KqJuKQhAck?8+o7#GH*S|y'
    '4*vj<O)D=nRpx$hE8k^B_lGUtcndu20$|9eT+LMjWMPVF-+>J54$?NIV^_={+t>co$b0MLjBt>$&jaR~6F5X#Wra_?%A3p%i)8LU'
    'x-a?B?eH|gc3%$N-SY}MpyVow%thO@y|itfJ*>zH(q6Kg=0h)a8ru)=X-i6wyZn7P{s&srrKvM7s|G_tZt@1io<SwYEc@7IuE^fx'
    'ko}xiX;nF4%I2<|W&d?K7wOccuAIz0m}bMrHuijceFAC?$1fAydbpg;S#L}fMV%)TDBCpVZ3U`sqXd|T7Mhz5Af^v)DYDAj4J9mu'
    'NxlZ`%d|Y&ZtmSP8PsLWGx&Wv3r|hbq{Xk;&fFdDURQwLrf7z#o60UJ%5Kmw(YPo(Im?iFOhcYGtp-Z^!SDLz{&7CsP2Z}u%g4WV'
    '=~sEDIs*rZm=##YW9j9)NkFnXJ6TzM@aukgdVPLzll(q?eOiM?oq74C^Ih~)>YHx8qoD<qCVlFonwq&7o9QDJ!H&&DmYw8j4HM1U'
    'X7=`UJaoK@K5@c^UUQ;_MQpqN&mi^rpIp8z#vB^xvw)7)rTaobpU7m(v@a#HFxs*inr2&u{rPnXchl4T;rV&#Azn<z`nJ`Nh(^cU'
    'O#KMc&@5FZ_S#Iv)C@^CiaFbU@|R=0{o`>h;Kv26o@hG#%AwGf&4f1fdE*8jlXL{fIVRiIJf$s{L#GZ_=HTVpA7f-ufbS^<aDh!`'
    'cg~pR_AqYCpB`NPe@wUCcz?Kjljv+nKEyw*$*R)*fJ%(>&}ruRzd3-bP%vyP2+pf+0TYwNC9W)s0;wLRp;FivPCOJO;G;pgCJb!*'
    'mcBnpn{$jIPp7O`<f{*(YSjT6^`{%ThQpp@W8VVdH`a^a_j|S+rCKw%E%I^9q5NfCM1eoGvS+>A$!D#WR-29Wj>S)f>2Q3SZhvz<'
    'K1`QuhzPBMnLbBRjjF$@hBCKFRPL>2RHaVshIu1K_x%p;kAF-{G3p9hxe8ObWSwPm(l>b*Fs`&l(iwLnT&z{K*BTFPw|x)$qRKFM'
    ';z{mUCt6>c^y-9k&eN`Q(k2(sgeow!{r2@YhL&`k)s9UUwKg23Zk)J4+#K=7K`a{KUEZB<U-%SXHav4RkoT^co4LNS)G2J_(tWPE'
    'nz?ZS#GsSBO7<@OcL{s>4$;U?q&=O~HL#F6li4>OJU~D3x>GobglxWk`E$2#cznJ59Gts!KvhTribe}jXSm5KD6xA^KcT5LTG}f%'
    'vTgl*E;Tt*S)XR7<V%)1I}ds051J0TP-Xp??EeHL><gE}QRtp7V?llICe5PD>Q)(qyt1^XVaiG$;UqXVGL3QUuinD8CsBL;)=M<K'
    'J7j~=U$G55{7!v5x!EOGr99(`ZG3(Ca(vhZXvW8{NC4_M59%irp{cAjQ3}9{9+T?W^D3@*7*Eq@n2thay#4d3dwg8WvW7lU{?0xM'
    'p&&3Ymt$XcdcrF5DODSY4BZtU24LxO6Sk_<X_dvKb7K*$MbO}^+m`haB7>n;YLg7xm)@Qbv~|~Zd5}wH&4_7C+(-p<tB@RwWv|N^'
    '6qtF(eRNe;pud2rrb8sTbT47W>2?lXK!Kf|;LZ(0m2aqqPQU!-@bLKh^2uAjJF}{8WcW9KP7-ghnu_S+ZuIJ+O7+&4?=NUaN=49G'
    '03zV-*<;Dd4O!9;yRrJsGzRhM`;A5EaofGbqgw}#I#r@HO%0OaAa%Zq!Rb|&)P>qZpLmL|b^|#2-p1BQJF^oI`IE<z1=ipS9mfXM'
    'E~&LXOH3^Rtl2=BSuX20a^vMCrE0#-$WAqTMTF>p_iC|vYLMO>Q9O~ln>Q}`28~6my!9Tsr~Bj6?W=!pC2J`&2f-bw;{p#Gsv*ih'
    'P;1-NX*#2crHWBueCs|=mFLZwEAi?1Y4|@)9$DYm|28_w`&&72N}|A8GR+k{Q+nGpqwY(Z;+_^#uC9V-0Lq<T&!$89t(y;Q=M6wu'
    'wskq{E&4h`B^(AZRY-My)f@%>#4H`Q56S0@aCGHn782*_>qaK+o;QC!W97U`1E&lWl}&Er0n5Z&Q+sz~>5pWI)du?2>c0Bd!`*no'
    'f3^ayB3pw9lyxlzkRDYs3Iceafq=lsv|IAvXQm(D+!?d`?y;@#P#n8>UP8ivuL-G3q8qHqfRR&W!FWigw)ptQ4%$FZZ!h&sI=_r8'
    '=u>6bbB%6!ikCB{(e21Jj5B;X{6d8Dv}u3A&K}%ZcbXpElUCp5uWS;bdswutwNwvwE_!P7gOqyI7&Wi9aZ~o?$9Hu~dc=tDI<%KB'
    ')xJaWs)38%T_RA84&>PS)O>N+won16f75?_YkOkXD9`Zi`|$DS#qX@q^ha=tP^y6(T@UqI_Y02YIbA>8FO}?T|M;bQUSUTgO;*CZ'
    '?G5VKKoew09l#g?K#A+Z(S8{EU+|5cuEI_5b*;}SO2Br841icS3uHP^{g71I5G1wCgG;85Z|eE*d0|H!NI_J-8xCa&SacaG`T*Jm'
    '5Vx88rg0dwt_F#&2L@lA{uk_R$#gcf-J5Al+i0&LzqY<T)v$_af`yh!L~NvKgg*a*L+~a9xV)WN{}>AtBrCN64K-k)Dy!55ZJ7oj'
    'tzYU!xN<vhd-$~Ps?_hdsNP>b_5oKlZYCUML<!Wb9%=!#P3x=Q;<sHb7v&1;CZH?iZ1-U&P8E)##2bzU*X^@BgbIkwAAUaP5Puoc'
    '$+Jwc<jQd&qe4Jf@ma)p5Q3<VR^CE8i}Is;*>KEgLy92vp=6MTNDsvDyq6DCH$XRsPByBaU4M8h=lbEt!?qFuk|>wvTIZzeLF{>+'
    ')FaaW?BB}0u;{1&z(2aR9a{nl0(?Y8e62!4)dy)+{+H4;>FZ2=9q@Q^p_&{IPaz;W?`+DZw^qag$acfaIu=Zh=GGl_LzTA8&_+Jh'
    'CJ=}!hl#_<l{H<R@7cpz5vxj5gk()wD-RR|6nS}YnYEQhQVa!UO-r`@cW-Po>Gvko48^P$k1muGowRCrWD6-90(Ghjk+whkI9-3;'
    '!@P!COqm8h5?2>RvEDy4(GMe98jxOkUw=}0(LZBwj>kbQF3arhKHZ|~e<#tpjeoY%ud}QVnEow``)umrS0zP>udAr?KA7Tp-A$L5'
    '4a(tVOr{-Yv~zudW|9a|RbtSpxcktq_-1kePcJLKyv!-#S^o1%ueZ(nGGLZ|F6$~o8Ki}(6>YgLRYd=ZXlDG$j|%u}dI(hfQ}^_8'
    'pq!E@FHD!06%M)Ve8jwi2D?hgagub<D=H%`4q9b4YZqykU0ibcQY7a7ewEIaMlGPBkMKL-NG15JV*+xkCWU)5l+=u3z|Zd3|5)%u'
    '47vQBbb;)Zd4i<|@U68OD+H)e_O+^k@>CZOE5Gl#Ki=Q|;np74QyMU4tEMg;ZQuxuAN31XGZRRHcYB%P*pKbcn%AdnWt{#v#9LI~'
    'J-)>1TN1q_#0h950a!ZlQ!Lg{bt&^*l0E)=GHQBuYm1KE<4b5~mI(77D|&i=KUYsJ@fvZX8Yphx=`!hG!xDtix=zOia*Ex)ZN=wr'
    's_I8Y!M8uY9N4nxs18Zv)78@;+Cg3cp{I6GV*n=_D|tV3SMK2P@$h<oyJaIou(frQrg~}P<`cQ`D3(WZ7O@^J7=@uLcWz|UL%^4*'
    'wAXs^wg{qV4GhSTBjg`lR`o;EQ9F<t?p=F0-nn0nrxgB7dtCqa^CFP@o|=tdSb?VY*Sr9)2a}H=MUT0W<&S%JvjE1opC=9XwU#5I'
    '7mBg7pqnqO6_Jl&G!)H5vRu@VWEh;PZ1WbD?_krrKq(l}&1L~DsAgq>Y&Fy9WYPYI8F>#dt!(qV_`l;F=v>^dEQw^>NGmWB6Y^TW'
    'bBq933$@zms^S{EK<hQ%y5u-L|E_y=dmLWx4u5TW_F&amTHgwEQb~Exc$DHgCvAaVj?09=Bs;ls3!fifZ@=J2-c8Rdu%@2ksCcCN'
    '*DlfQPm5e)0@BH&x0d19c^gym3-*B&?RrObU*Q>P(TEC&V>qPMJV)DajFKt12n9Jgbxoe9zh*-Vz_g(m9bkAFx{aKEe;9RssU=D('
    'WKxAGUf~qHtGv2$S1#@+%!ud1@Ba4f?=B`@svy*qwvYq0QWGFkts_g3IX1doW5}Yl5V9-xb3!1xuXh4k)JW6ey({)dNHszHl^rE>'
    'RhH46FHuM)HXcRf@5~oe-cxz)vD&>KRu%%sKs%B(ty%($hDyRS8`a=K>LB^ff9fjo^Znc(hu=3H?yiX*j-tBG!}Ec@MoT3PA%AG1'
    '=3p(z{O4io!slwSKRk?U>`RquD8mG^A*D<AjUs^}ER9uQXQ|*yggR84&-3G9I2NDg!(T6f`Y+(;<+v7_9SNO0Lhmuk;-CviCj<3>'
    '9IHWO9d)yB{l6(wo39mRdKYw4%_FR_=u@kgiyV~*mq>544t5`)Y~Mzn!fNGd`zFYkltN*nqo4)Rbv<x3%x*|xh-A`+02T1Ebrb$u'
    'gQ&6NjxQpm8bgH)1Z#T~BA2T4)AvbMF;BPzL#HIYatEh;XY=z2MTaUkU@jtHMZ7*Z;)tA>&kr$NULdtJ#pb*IkE6f6T`Y~FT3v}w'
    '(yB!FE*Am%ps*#8@>^6`LMNrb30C3y+Wp1_TZi9Ahpxp6$AM^JYv9nbAj|5*U`VfCZ9K0nNHFvDzfYT_S9<PHhB)x9D=&I(L*tae'
    '94a@wOfQ9A>p!e5xk%C8>hcwxa2pDWR*yKH^!tls!kFR-5N1w|2Clyh7)omaXPZu1=LznV0^D&cvglZ=zKMWjEd%_$JZZOwV(Vhd'
    'FFl^y!SNq&PydF@;BG_PH9%9J?x<pCgHa>CgaMFp-NVOC^08$IA7gUOb`B5G_{F*CU-@o5-9EndZ(NwmdlK?pzCc{)1o)0AP(JG1'
    'HO!E-((8cndffaE?J3l4^itEEYiW(S#<V1~2o-n%bO)9i(7E{pQQw1U@-o<K-OntMcI@Z7_Koylo?Z_3m#-;zAO<`Ah_aVDIBqKv'
    'K&L~;*8vKRnf!O`uG!U{r=#0Dt%YW9A&DkEN3KTAGkQ=dmXIPuD=q|g01J3Xdd(j0mv*3*#M&Nsa|QYW;c3I`Ebu%Rwr_@Mmi>su'
    'Xuth<%^t$u#~z->4bNh7Gv%Rp;(F#w0k>nv;GD2TAY~XUat46J&)lol_n|c!)%fG99{i?{L(Sc)geeUiZ4^VyMkzmM4?EH>YUa4L'
    's`jdnV*zV!Pxsd8WM6(iiMzQ{56WJ#xB39dK)E<eC;=FNLwq&Ub*Be5e|!P}oOkoD`@0oVon(f*1Od@~!VpNk6ZT@NG^8aV-)*XB'
    'AAiAC;?FK)1}s*pTEBW)IA#2ZJQgtqF&1;Yp4z~<o3XlnFTu)u?tCmO=uM!Q(C;)fDMTT#EpG~ZE1!|kG<;3aOQz|XjXZbvk2Gn|'
    '!4E#Q_ScB}{sx|?!s2nz4pX1W_GcB37Fu5-1!7eDXr`-T|4S&-#|;%g5j6+csMZs&eH!{J`Vbu;0aLetazN-|fc-U_IDH<&okHyL'
    '9`MIPCNjc~d?o~NA>gkezaSsYa^O1NUA_I-3}3pJHyKU$vU*m6Ck)9Bj<W8uR2!}W=ytOpqdLD~63FgmdpP@M@_4q60^xpHK?o2M'
    '09=!PPmOOCZ3FE}>;;k*HccK!Kq}4lAa)|bo^F?8A8JX>)F7&Lk1I(M>L=Q^^i#{d92%V(o)=Q1XrPLzYVy47x1ZIB;ltPAZaU{}'
    '!{CHO{`T@^aRa!U*6Xs+A)_QziO}V;(@z9~A`8UrgT$d12pLGbU$mzU#$HGxeDsL$!`V=nCH)`3UPb(AtAYmjU>G*PWJBYD>)y)>'
    '<2@r`AN0~Rdi${Xs)A@W@bjFohkROCS96qczhp;G)4yKVVm>l+d^#c=KQAVakyLU7a-fQ6-!>$-gfT_^(GA@lKOY`8VJ($5nJaLL'
    '3!2rXFB@82$o_*Z%bwB=Sp?_hqdS6rJcmZ(VVE|3Owf%$aF;%!ZmBocrj<fP53wI55g}l9D}DG$X*hmUO|R|A`|)<vBw9`^ScN0j'
    'tX&W<lgRM!duJ)dG=6kX&(n*W>N9Njp?iG(a$MOJ(Jr%JsHEt~<OS#+Z*i1s7QwI>gCLHg{mXXs`gnKjE<??8pzsQKR-)Lvd_a^U'
    'h&eOjvrcp%^$1Nxm3?$iFUQ}fhcj*Va<T=(4OZ-+Ug=8NIN_magpNc0)aC^5S!}PrdPC#*6lna@G{wL1u*wm1Z7Cb6Ur=74d3dKy'
    '*x4})!D(!Y%oU5aa_x5fgJ@LTetCI$+!UCEM19k2;Z^Wz5DW^ePlN>b3yvihs)~1OT77gw&%@K<am&@OtJSl1=1nq`>Ps3`$sZ7w'
    'SE%xvJ4mQVm7E{g&^pajk0cET0u|+$$&6L9s_Q;Xi7ELemkSY9*<XF&$K!n`PA}KT-(KIB<8|sg?I>fga3d#LFml35+#B>)2@{)%'
    'Fn0RjmhKKAwcUW$DN~waqH6AiKMENr)(9D9q}F6o#U|7|B2w`y_M@tq4r@k0;b6z_T+4(LiOz}Uu!cn+^a%C2SEwPVb((x|Lm_A4'
    'FSjW|6Zc_CAowKCG|X1H1>VH>L6i^ov{6<KtH`h2(ur~O?Tme=IJ^An%5W(w^Z}U=bkb;=&^r3|iX7e>J(-v4H2GEAioc>VZm?vP'
    'l6Y<5WW~b?GZ|}fs3C!T!5VKDGD*puH@|3K^SZrFI7LqoN6|5~L<O#LnBB{~5pl#yXe1;0;e#8BTXln#HDi_tM>EzdG}H&(Xh*cs'
    'i&Lhe=O86Tdno<jZcZ%6Cx`9@19DYaf#r&DDAgz^S?L5wuhQUks}?!Tg>@2#3ry1w?&^GhygqDvSUR?FS^2HIy;H)P8_+d)B7yUO'
    ';4$>U32aKQ-PY&h%P~0R67KWfR<dnG_7J>I8TEA$EJuV&1d3h(ptV>d%3+LN9lZlt2tIDWmY2_1&wE40FEnek2DMUS)#c`>DVl)E'
    '+M62R^R*kfJC2K;)yX{SGU8K&6FIFO3Q4<Y09+bqb!sAQ@0h!wvKF~Nu$L%?&M)a4zBgSZV23m?ZN)39ra2yYAaa>TgjW^*WVIqm'
    'b@H)|Eh6f1IcdXjwG|Nwn)DE1f}d@R0z3q<9OI6tP!Sic&;=a2c28$m<nPC{zNIQ{Rj}qmgd`41!f;^@>aM=5Pg#tNk2<}+0I@2&'
    'z4QCq2#yp|*f1Rl*iLhTvpuKgI;ghf_n2v@zCkv>IxTrPM&l^ZJo<M}Y>n}oy3g?bhu|tsi%=mr1ydLn4&a(J<V?J9uC70hOAdJ|'
    'hj3<JSE3?C4I>6b(lm_8L}~o-Kp>*=IK`BP0r)sweZztl<Fi)t3)$O{8jw{NR>`6N774iHX!^$=Q0xsnpb8&ZJ<T84(b*c}_T@{s'
    '?p@vvGvFlp6qc1NhD%y&eO*6H)986&$51q0of@4>GIfyXh;X=0ItXp9vyOcavuY*W6bwEca_>y{Ad^kjni^N%W6MoCZo4}&H@mg~'
    'vo?<T@>jVckXlP#H=DJV&KI*2vX|@kvfS~c9a~R3QDPy-_ij{$#Q^)@KTh<avZnRa!H|EL_fdUtM}ORJF!%`X5U7j6PuY~gsT(;o'
    'rgqh{m5y;Mqr|!!uFix0Xd-d_Bha+9^gd65J=6wdoyXV<OE+N;>CTGkn!mI%sqH?nlj*PE%SXd{v+bzG+qw;d2eX<u=;cdwXy}fc'
    ')xS!pFfhCO$fgd<)0wtDrZy$t9>NtFu?DpzJn%5CSi}`!5Ca1VLzcY#*p7}H>M`SfA}b5#u1O>#{%op{&Z!8(s0iOYB4T|#<QY48'
    '35?<Rv_d&7B3aMF)uBe-=AB9QC_Yb<yfur;a1IIJ2ljC$0}g9?Lo_?gVm@Use3n5hd<V@R_Hp?brYMd)C2c=_WGmn9DG_ib&lyzA'
    'j42@;P+l^YDq)(#w^AVVm8k07=8pKU*vxu&5C9fxA$oPEx()<JyOL@Z{1X$yOjO|sGW8$WOvnpYv{OP^$X~);kF8&shuPi`li;Mv'
    '*fA2Yjt4<Md}J3d;nsN@B(7B~N;w=YQO#=Ul!VlNbd7~Oh+PmRL1rqRkHp?@ImCn$LgT+;_QYR<)t<3hxah5hp=aW)X{r>3Oh<tB'
    'NAuNb*5A43?b6s>5%P1vrbh(5BbUKWy{MS`q-~+(^d$p*!kzw_OVWc0%>*pv#IaowziGX3A1q=hVjo^?n8xrYSERFyrvq`8VQtT?'
    '9`9K3ycrxU|9Q2yEtBlRoMMzWfiATM%kW0)RaC9SE{TR13*+sS2Yk|#1op@N#2bjR*`Ni-TO$ec4w_QbSeM{TEGBd~7A-WonMOmo'
    '1Fm>yUrULwc~@lcL%b~3z}zEAiFI~ad9a4f!pKg;x%B|+;_6+Un<rcMBNYZw_GAk>198qZ-!Kz!^a(3nQkoeCeWmHu`}v+lxph;L'
    'z8E(e)f0-cu0ePVhBQ46y>1xPo}JB(bnB;^ihs6!PfP0?2Y|dAeOzJ+ID~m65gJL<Md~D|<;k^s8lJl6FKi(njxXK1{u``>JJW`S'
    'f@KH%6p1|SUq|dP^#TH}f-l>_kNdaXoH2{-!-2f97*uNho9TZM24tZbkvQ)aUgi+ZLa}vq4EPat+PJB(6&kT82<q_uV^SJR{KPCJ'
    'v~E_SGG&tFZX7?hsi=lG+x78T$>)=4pyW7=!Hwx->60ju>%hT7H<VY`?&uqmvUx*{U9)~5JT0fVS7VG*VnCW)kOUEv&_9<YU;W<V'
    ';dIZs-8<r=dN-3Ds)ft&GpI4tU8$(BIb+2xCi1#h+G}@oE<fc{ub*RBzzP%(Wx{1Q`zqW^SkNFR&oPQOkH%M}+9I(cl&n6yol`sK'
    'xcz$5dkfc19~0bZj%&`W$<R)!c0h$NJEL{ee){0fmfpbDJ;kiSG8A5VbA%2uGOZPq1=VN~fVfPused}IXV;#dzr4Og!nplD0i6m+'
    'Y1p-*cI8}_G<)2<h(lCRiVd0%#p~vMoj0<4+Rtwhb9h~hq+jqBq;QAJ$%)%*0<)-t3^KDe*HCm5!drc3;7c)wcU;?kWJkyTH%XH!'
    'RoKKWei&DbFv3uY&XpdGIX~`O_>BqW@USs7u*ApimOTm6Pxkb~AFZaACW?AfO_<noGGdScY2mblFUhE8ar^ZYQCPR{Xkz<4-9#&1'
    'F8S~I<z+NV1%yJG02M;VBOjR~BtXU*;CCO_AM1{vTCTjenRCDU{AA95cdq9zZzc3|v%AbZDpTizLTUtP!IVV;f`Oy|j9R;c?)=VH'
    'R#Sf$1cU{%I&?nj<e`ryDq?=Hz_ajK!`LsjpR1Ry2T`60#>;;Wa_{pBvo*#?@LKdVs&K|b!-I&;K?sO3<H|E`0;VZ_WEX2sLPRl#'
    'Al&ABn#6Tej7!U6Pzi%bX0ND;d~%ZQY4qvSd^p4brl*6x-F06V()EhQEO^8*fSaLQ8I)cXa|L%oPEbMv-b=On4l>kfAEbQU)7k3o'
    'q#{|XkIB6dFe8cpH0E%GfoUT^#k}<#6`ZYl-Ol^A!J7N_sf#S|_H+Dot&bk2w-hyFq{_^i2qh5L<|Oc1Lj&|@jH#CWH2Zhqzkgh@'
    'VheAPI_3i4>;f(@L;8Rz+PG@)XUTqb8oH|5xA^H5#AmSSJz!P98JW-_EwVP@O{yJ*1&+taK|Qp&h7cAz^l@jIRp@8VHQl<F2Pu}&'
    'm>D+qYj0X6rnk2EAaPOW`cv$81j4f4w}~_C`Su~KIM6Ayr$Bzg=-KFyIcRwbZoV=>w*pGz4y4V_?@`~0)6+I-U>eg=My)uMJDyqU'
    'SOn@kn!LPcyrY^L-N3ME-wqH;x@F?zc76b{F*2ag>_mp4qTai^ok&HTi~$pj{eNmYcX1nwBxPL+(x;(6;9^0jQ^hrbfUKq#ykQ`@'
    '5g)uS$GP138qOj5yGO9eLXDS2657xvChJCcG@@-0mccwwHiI9Hi`4IYBYIlBP#Gt5WqBHKRDRZ9QDFh;03Bw2>Cg^Asd1Y!z2Mfh'
    'Z~51QOz-7o<zu8}^XquV$9)L~(=STtK{;2Tumq`h2*55Mcdz~Y=V7fo9TRec1gb0uWh{G$VC=?JCY2tu5zu!UTIkJdhdcd=)^s1%'
    'B{8>P>bH1K6-<^g%-2BIB`^T)LU*PM&Ld!m<#rk~6w2&_J6Y8RnWV-9pvf?B!-JfYZcKzl88S9%@!p~&n~Q$`He&TN*J~rS!jPYq'
    'LW;UECOm^|IN!N1!YCmu!1BPCAx}GAPDp}og2(;!hg5=3-XwZ05c4V@j^Cg2(Zr_We`PddOcF!Y6-b>LJSR%ss<?hvza0;Yu42)6'
    '+|GC1=M`J#XgzC@2YYA?r9ikP#YLY|3Cq304#p6y?D`#@bfMTD%G}RuQ*v19%`sS+%b$=1S>h=+hXN)@-@0lslfl^c_WJE$EgmU|'
    '&u`D{h4~4!VFk+3(F>QnJP(}-A2HoMmz_CmO^nM36>G_xWUXMD0$^W8HFerof31v(;$4wP0L{sRY91@z2r`Fn20aIwl*EkHYz-Ej'
    '{!%9{z4%QQgrUq1oN?(mvpnQ6Ex;yqw`ALv6=0zs`Q}v}i<NA`DIEJDjR{C&C>Zmwz)yo0<t}wfmCStm*Glzsi|OBty0~@zzGi4M'
    '2Q@ZQ3C@R50#wY5uf%AGCSd_~h8fmqPwB?>PiXUsL10W*)z|{UwSbXuw^z^bh8m+&;jxogP074*#j`@-O-;L{*Jc`mjKC#DXTmIy'
    ')-10gd!##yuFa4w{ifAi`fUftC$bHw-|Ez{ItB|UsAFDo%-*D)#C<Opp#m2n<EV_lUCr3OE&JywT|7#Y*6hl8(CKIzJz-LS&MPOn'
    'KG^ob9MD;uBy2|BV!m!%nj?dg^!K9=rsnbTOXqyh1Q9C6eGegp$ioDWQUunCX#$;6RFC^Mun2iphFzgL;YRRj>0%&A0I5Z|&W+(w'
    'm|_PQik>A~ANewId4-5d$EX~O!B${EL5lBY3?0))v4xT-#MIYSQN!UFh-n1szaEF%m)D0iZ?#a}xU-<Oh~;ElQw-^(k+vPS<uPK4'
    'I%rsxy~er=vKCKweVm*Ozg#2|p^TVgB!zqwS~Y}J9bJg|ZA>ppwygT~VIVpfg|3bEG{L7s035KRRAfy|)V7}1RUBqzQO$NclN@hY'
    '{OqTCvM0D*Hy?Kcxe@evx|mp<1u}->>j>%Kr863!R!j&rwk!?Qoxkq;<yI*JJxxqJa(RHKW=S63b91|>KbO~E6|43lzfBLnvp4^Q'
    'RRf1{ZLIj@nVDgPMa+RhKbm3??GPD09|8oI(F{!oc~#Q%w&-b2c#MqfgOfHNKChJhWlYrp2cnk4e26^c0Md_0wIg(rGqBtkHm?3='
    'U;Z{@S}OE;T6yZc_ZL@3YS-lv(*;Ar_-2>k?g*t5KdA-VjayiVoQI3Xwg6ea_6YV!$6XM*L^A3ORR#Xt<jYH<I9Zh+zO8s}b#8ju'
    'oEbHGh}2><G>p&lo&wfDjbS^)a*ws?Pu-v2UwP*nPiY@yoB%Guf_WK>iq-3;=*q}csu?ekb4#;l3mcv}Wd&CQAM&*1n63;uCj~&T'
    'S6NgQW_S<b_qVd_y>VjQX7e<aqF3u$Ecg@n51b4$dMX)_PFGlU>Y>h>rfZ8H$JekGd42q;^7s3n*@_ubJed~jIK4A7fal<1MKXvm'
    'jbj<JrdKQG(~8fFMfCHgx|Fe|W>gk<nMQ-L2q_*<?LFhtAQu@a9X;8)-@5Q)D0z)&SW!A_8U$0IjlM<|u0u$YG65fQOw=GQBJ}Cf'
    'RhGrKWtUF)s^FV{4b)!G0C`EYq)-dAPBNl`sk?wC$iJsmPWZP~7qZJHzZmv#IQsPz8YYUExeh00>{SFw_72(zY*=}Rl^a)%vf{AL'
    't**i!!5_6ag(xeTOfS+QCcoi}=?HWEP1APkq6?4aO>9Hm7IL7~XD<6vtI6zGfZ<%4!+||Vu}#gXsIIv-s3Fr;BHi02&h#0z<C?;@'
    '2;k2x340}AA=cD6*S@c!mv7K<{Cve^xo_PCk5w!`uBdw(Eg2jywu?=~?yv^(fia7%LktxzF%q<K<JxbkLMhqhWnF|u4#nhBJxjkn'
    'cqgG%A#pU0k1iu63>%w`%g%RSR~)m<J%nk)*ac+ho*buQsjU4k>FuddiF08E8<#tbiv?5n`^7*x1Jt$gV`z2~c!VBH6D4W`*!8r#'
    'u$z?vZvC824VQ=MRk?UMqlc$M!@!u@zba;af8m!*y=_c3?u?Q`irscw7yj+_{_;0ehOJ@DzNS)7LyN#~lAyPWyfzFNd6C8ZmTKdA'
    'ry*pw&-W0Biw{^Arwi$4=pA#0PL+AUZHSws#3?8);)WDp-n#A^{dWD;rbu=H1TeA`EPX_jF|ZaDj0hRDbyn?WTnxKc-WaJIS)CKC'
    'gUOFBq!?jTnrnX>X@qG@&P~-guliwsTmN|ceWj1NG;3Y(tmxa&-}FS&d^OnAVul6h*JzJoYm|t2>nn;VhbA1739?;$#A<x@+yLNk'
    'kwOZqI>);%wyyVj_i|X~lwK|ija~{5+MwlyfETRRMhidYZvx{PH*42qo4=>G!Jl(y`EANifVR*yg)ekK$}tKGlfWz$E_=MWU=XTi'
    'u+PRFeCLq7X?f#}q&K{H5PrF-h97Mpc)&cj-xMf}o|s7t8<#)(B6C*1d-<}0287syCoM-sIvHI_R!Qnp@mU{^>wbyIPO7qT;pYLo'
    'v;r!@?A^5^66O$Is5~!=fE|<v7+5OQ2%B}jXF<<+_2A+iM28D|k)gh`qt#}3Qy1R;!WKy#oXvIEZeBN-RIt1a05#Y!)Vj)HP;?y#'
    'L^utLU>qvQps2Ae-B(+q^f&jS?~JG}|8#1Ip{iq+hokIECe(+HgHC<pK6TC*;RL(&4nASFK=QA6j=!&D@PZ+~vfyTc9%5dVoYK7V'
    'S&*@v;7#&>*qTe9`!P#?HLb{Ai!c<FdsN~0r(vb`4m;O{ph-k1iYgeVttHE;$$j~^dZz3_XRbpgBB?n8r#6OD3gF>Jz5xI#t8v$g'
    'w>UEw??VVIUque)F`d`Q3YUfDF=ex;{F&)h8h7Mn`&K<=JcsAw20gDKLDb)VViwY=Iv73C7id*bE|bViT+Lm+`FFD}JFR~?^WlD{'
    '1msdi`sqL|r)m*!(D!NF`ovAo9JYp$*T)4)e0>Z;%SuN8G23HhPaIBslAO}XRx9X#M2`fLI!A2TdQ+S{G`E!uPN}(GIU3oLU5?1m'
    'j5fxgvxHkwZtxu^%XVwIax#nzBhjaBgS)orNWmiZ9mgzzg(&WBu3|Pxh%nNHmN~9v22_C$e?6Vv@TXgUWo>@DLYirVyQkeuuUOU4'
    '24=2oyy_Uq66KN_hI%mFv+&!bs`JQ^%b!{qR^5E*+*J7Iel8>+ybg*OWKqO;aB)1#cCCMQ>fdHvA0}Cze2DKb$#ghtGkSvhn#Ocd'
    'dD%dpovym|{jh^GB5@a9=1;6&pam-)oqTT^;xY{p)^~W)h*a@Oq%pb&QyAjbSF7BFANH_mVUJmRzYnmDwnonhRm;JS7ONf+$Dpt|'
    '&WB?6!trmfP(v7Nz%ykmSd2<!CZr%;?J3d-7C=ETG#6*>4mr(_+4QM}b&hGjGoaK_^2HGnk)f)0rZzmcE9~c>uCJ{4cz7g4Sxdx}'
    'PJy}fF*UM?0R>C>Z#ag$q(@bZHuAd7(a*+Ket$s)Z-gpA)3oUFJlGjym^|v3tA=IR08G&IY7-z(;GL5RLBYYx#&m)fVqt_C&=5y9'
    '=1K%<8TG4QJv1lphUKg*#DG)3X+_rqm1M=OR+M%6^~TYg{UC<nJ_^x5dXX|+^&5WHqQ39G4P?A|``O=Y|27Xzr0wp)A|Xb56*1Np'
    '3c^VyGZ8XI5R@Z1OTW&B-Lj!ALlr5QIkXbcsphGP>KNLf?vob7llhaxcmjNx>_gkx_L204MVZM=jD|xJ&3%X)?OqzPl-#D`j>%Vb'
    ')|Yp(jDLLW4lDBr)6t|cjs7S^vxo$0103$j%ue%hf{KRwwdxyl-U@s@YTqrsxdsoKd%y*nN39``E)#;LBoKx^v{h)!;!xQQ+ZKL_'
    '%9q&QP>Og8tEGvyZy!FvU5Ng*q?-`^ljxbu;?rzH+A!9e*Ip#Jr>lK>dRj(NXcn$nn6kk}80ryf*sBD&BUIDO)l|VAIN({*MGd=S'
    '6FVtPEs&Z0K+Ky|oCVs=nk$LQr3?rf-;HVK`n-kjcktV5WL8^#el{7JT7-f%oUbq+@cVrCf&7o5hm4N7X##r|-|_Wn0=K~`S~#Fl'
    '!XzPsb_By~4_2yM7yxdwWA%NXAQ`G4q;Mc6Vj7wAXM{p|C<>YwcRc_VjS5=3<?+zx+wTU(Zy!vAl@G4XLkNym=8eaM9zCaoM!gLo'
    '2ciHNaM-(nbBeiX7Ai2p+~Xm%Zv#q*MBlWsCNcxupH?4A<({n$#(HlH+via^0Cm{ZD55n$BnUWd&|TSAA5#>HWeiEWcN^PhvCg5o'
    '7jOK()QVv`1mOjdQFo2eo#FOVMvvyY9lWu0E|)uIZlOhB+(|k~r;MTvoD98<N`jqD9v$Fr6|MP?Eo|$4QV6g*$@&S4)A&;tAmA4S'
    'ZD9zs)?^Tr(^V<?zpwry#c?q}SxLR2CgIRy(kLJpQACSO?jH@L(DA_U+=<2Tp>1qnTH->b?V#G03v0G}`)EtV+PneN7@}c9F}Su#'
    'KeUg{qgjntQGK<6U9mvm@RWr?dK)RUCLWtGb@7}xyEhXPT5q?F{EEwgPn(&^v|9~mT+|jTS#4_F7OJE0<Z@^4-UDLK!}NJwd<n1h'
    '{6o!_h4GBxC8nv#<B?$*M9`||4Pa=M1o6`iJcpOv+I^u5A1M;mrA9~_e#k*@nZhKNb*0HJT>t81+#4d^rfY7RB50Xr5lJLr);lfq'
    'lVxTT#EqV%3iao(`>TB0!scnUm~1n$eGyt3bz@yF*SNYTETLnJuD)-~+qrTd-v+~OayZ8YHVSFZVvKecZajUYlX40qAYEphw-^GN'
    'b$d5+>gh`_2ArhZm{#?)(jly+E{Yk*H=r5zsW&);1R#lV&RvH>E3vwEA2HnFVac#uRIB4h_1f#0Z8)Y$7@es@7i-$8iWGOQm+t$p'
    '+8=&rFQ*LKjvh8B@NlwbRgJ<T9Pqswl^4zhMIz!O8ip?kCQzr>ZDk9CoP*&ILlF7h^TKn@sX~V^Fh_kcuXl{;+F-@Kp$kIK*=wy6'
    'g1Ch{t_y-iEumM>MX1zzanb3XqZ+Bb%3*KR_))ZQy9xN|3Fk4?;DuPm1S`5DJg&+A$~dp6<pMa=tK7MjZH8HH2UB9`Q87~WXeh_q'
    '$Zf;+mwMmX8LKkin`_T^htFSp3$N!3^&T^HMbH3$@fDWQRyFznhDiCALWb&KWSbbFp%H}Py;;`h0Q(-o3N@17+xf|HJ*=uZ1WBD{'
    'jb^ZV%~T8)BZ_6xKv67<dSvw1y;~8*5gWRP*GHepQVSlB^U54IeFWVkX%_Mk@+h*lgTb8&+ap0P(I?G^aqmMhqxRuvSIG~3EL6WT'
    'tXH9u9zAY@o)%L%p676GZQ|gkXR9dhzc2k=b7OfSd(5Ddm?jqz{upV(h*c+#(g%IFB;nUn6W4ic_Ir;k0{K4XI98{GCrK4PF*GDc'
    '*o*OL?tHpMtR`V2=rHB=`&cE7na|;WjCp6`1clCm^g4%+iwS0Gk>Et4jqSciVhg(z6M6VNL*5xYr!mNYC#|Owlu*juegf`dl&Oxc'
    '*vAe9g+(AT+{OYID{$Enp3NvqM9wB+NwK*9B*PWE*r;XDd(uyq2U8hpK^V5{|52v4QL-`}FrA3^$L=caB=NgFOa9hMG#sdwcwdbQ'
    'wG&Q9!?uF^jApJyK@ypk69VJjJ?tZ4D};Hjh!#$!n-%qq)H3OUBV5HuA{1~R$L<FqIxKEN=N9SultqqsnAb292%=1w$|JyR#kAoJ'
    'k==CR4Y&J%?3pw_L@Nr@F}#!n2OKnTGNmHswn8~34i{y&JN-THz!{AYx@qXOMlo?3TDle`eu-$#y~`vIO1ZE(8&z%EF4=V(c|0y5'
    '-OY9weqV8&0AQfi##b7$Id4FL3hBn`QZ&WP`8h~1&2<}DcnVuyOd_e|`!LDGIVi>Kx1J`Ui7zuaITO@9rY`P{77ww0V2i=nARpj|'
    '{Jer5=qx5NH4tmj-DLwB>HJ5Gt4Kq)8#KRu_fa|bRrfWtsjm=36srStHCnhqwa2=)uPR29Vm!)-((1as>}_o`N(4ElK{ia-5Rlwy'
    'gOI6BVTs{PSK;fO)%|t5IdN$=Z3HI_DaoaV3l7sL77%!ut5%1Pw%$}4eE8k3Xc3*B^Ye}3Q|N+1F{YEocx6n}zAA$Yi8<c6d3kVo'
    'I#s_n6?{Al$8S4X53Au7DGjqu5NwIr=&L=TG<d&xNELXwn(NkGvy0Pv`8*w2=&X@L4Kl`iVQ^yb2Hzx1u27O8+yuW|{t-&L^&t~K'
    '-NrebaPNpw4u^*|%*9+CcdLe!RA>mbg!{&aYxEBp5_$+Rhc;e%)gyU3%R9(1dKEl7=qTnS29=4Yil-tCkE3*+G92^-cD_4rU$*ld'
    'iFPwYiu0zJR8-4>G|jZ}2KS-i5-wlbOZywbcIc|@yg8aHu|IE-P1Qj`2<o<auEYW`GDSd9?nea<Bhum4+Uu@5LuZEX*5{JOM3gRJ'
    'phpRzo#{FT0gWMuR0R8I!qzvL_g>0>-#;N4*oM=w5>(IHOV|g3Vu(;;LL}{VSZ3hX0dg^`_U4V=PCqSJcGP*sLa!DRarFR%uwZ!c'
    ';DQWX$q1iNv5}s6N1%NftJ4(wH!|`P{q``ts?UeTX<(K8<HVFPt)K}JI{u`$hA>ON3Y5?r972IsS9>?)znqcho-P>RK_ZEPAALxq'
    'o!FRRupS4-@DS598RCdHdpEM3I2<FfJAL1v-V1Xad-31UY8I;`gv(NbO^vWO%E9T*F7tzF?wzRsE4zp=;uHs<PUt~+0i+3=jRL8a'
    '95aGH?fA}JT%h*;P-ePm+PG!Q0Q5CG>ZmbVt@%8xu89J}&1K$uP@=wdJYo{%+GGZr@ez4R#F)Z-G$v*6yN|JNEH|YjW{6|vHG2_|'
    'Gt2h&EPW04pOw-EY1_Bhgg+L9vIqhq&Pp1CxnTfIl%rML?%c*%#s9XORf3KlLW;Lm7Qr_RK88DmVS)^$qpsE{1Z>08^Znc4pd0#b'
    '`QfR~x*WC$+pzXxmL%$Hc(Y^BR58HbnZ;g$&pEW!-ots~AwNzlp`ka1UAHexu@dvO#7$ga_D^-(a^3~_PG5E`u3CK?3%Uuw)P&ef'
    '-VsiUEHi4cK+haHsS9d<jTC<GdsuACP8KCwpzI*$%sxcUKYVA*tdp^~u_?7)7E?db&x5wHwu^lcsSgWalN2UzxQn^URKZk~1<s7>'
    '0Eta$i?6b_>NoF<Z<o}0zR=3Zqb}I?MEz`|I$b5bEG_92KP4n##P>to-Tmg(H@L((+!#SPl(j+2puKqUBs88rQh3EiLt-^gtL&V='
    '%|f<EKXWxJRELC>z9gx3yk!2RMmI()KbkD~*!8q(^Lq|6@7=pUct@D<2euhe@63J4+^_^-LrjR*RHkF4OxJy`nr$m?4s2`?Ibmyx'
    '>BI0ka@mZ0@Qlh(aJlS<AkPZBt3Px(!`pJe9G%;UmZm7oz-<wo>4BCh9KK)VGsEG+#I4=5V#KU%N&*6RyfU{)4@;MAO8P1*F^G*3'
    'QP>Qb_Di`cM*eQuEs??im?``os~F^?KH(8;NNRl65FnCwj2fuNs@3FotKuX_A9{uU>{9H4JfDW8q@is-C%PvwB8j;$td-2}S*=;W'
    'TXo|NL6edeJcYXO$<kpa3n;<Cl=W=ZjW~d27_qX73;)N$8)i7+>av&NBs(-QX|=*0LdobL1*Jl{@djx70SNCceX7N8zE9Y1Ue@N#'
    '%Zp_}F`|=E1>`7;ncQ%!A+7;F+~RbptNiYbsHU8cPxsL?Bn#>8zW(<W{SlbJ9C?LYBJ%52#$bDsu2CJ*2pWs?TlKz`?f2`QS(AZ)'
    'teN<84GonEAO8lJ&2vvwko!tQB+0ymqu!pmvh7&*jQ6jv9UVz?8K*cpbcEV3VcTDt&CH=}o?y*(;ltXy_8YjpVGD2$JaIHURgk_{'
    'SfrYy8Ey##*;5EJrkGUy?pLkqd5JyTC=X|2Y5)1#^YP)rFNS~O<6;`ca1w&PHhkuZ7=v~O_@X16@kHOvajfziQpU~F=7h5S{4@Uk'
    '?n&lQQ(;#bXa!O#mOH`Z4Fl^?tf<}cfJoox<i{M)^K|X!n;5?N&zHYmF3lLqT8Nnz@8}5<BPhA0(^Z%m@&}_U5;?N>rEEgr&D)Rs'
    'xgg^QLkNkQY0O?-3{)6nV2`L&0%y3|iBTj60Y@a4Rtr9L{N2rhwXbxgXvL8{*iEY!bSlk2MB7t2XcLyW?l1-}@$c46&+@7pe2(ZX'
    'oC{Zfa(n)h+i#`?m(!Or1{kBXu)pLbVmup;gBgr+m*6^pVDNGLv-dXf?e{)KU-oG|5K>pG2pYh78Ui253g0}!{lZWSHG3CkR0iz*'
    '><fyP>!-f^-FN!!KduDbaFjPZRt2CM>WDB&_G^qLE*OKzpN0^(EjFxm8m{^B{~iC|>28S!|E+uZvVy_7Sn=~E+zO$<V*5CiW48>%'
    '3xM3)u76&To>tc+8NS?{*%`!$$H#T~B@0445sKOf3K>Ge5Yw;tMT_^QaS$R>zW$W_`Li|8e_dhJiS04a&g3S8<^$-aLNksrqP;1W'
    'G`7H)pXP<%FL}!HKP?QpmFe52rsB-G;Ii;JB5v#?EvRC&O5txpkb-kMZd-4Z1YiDO^W}7?6nV9wr)l5w1f=1n^CTPN+n)sW<ENCg'
    'pRD)!)f~l@=b5)%bVcEfu1lF985-7^?jMN-lMAr{cedTO9)q-(wV|U`j7nno=LZ>Wj<f9f#+VKTq)afZYhxhn@a~Zu4mT&GgXd3Q'
    '4l{FexZP=P+v9O18gPOmN#(1^HkL{m<{f@;LJ~|KriiI5C_yVWEFEjDb0UnkHxrI=cld*{>fo>llp)R4yvn;!FfmIlf2yDQj|HC='
    'AbHIgJH&+p@^KQrCCrqmanW#zVVT1!+^}L3(w1b}u;T0EDl=bcm?NMAJ=>tVXv>M~MYQ&9f`<ZIGL=-*y|>ypg~2v@^H&M3)BhZ9'
    'U8`rZ2=^~C2&s>msDPEq-RWLI^)5qdP66!Arn^=(HsP>RGxg!ht|LJ*YDu?-5<CwZjhM}Z*I|-enI_Y&Wmhk-A!PjeR!G%Ta94`R'
    '6_9FJ2>@E_V8+GNj&#qWr&|2-Z9;7nuz$Gu8V=#W;;^U~A!&ri5?{Pkea_^)W$}h?mg8~ruU9a~d^ing-tcmz^Jtjdx&gi6g%ZxF'
    '_!`tMD#mcG44uR9{!@N$<t;Q3!Ue82B7!)}at}9z@ryJtd{RR3!giT^Rkr(Ae_0Dm?5gArq2}mAT3KmkOO=RjsQj@~3xAF#(U*G{'
    '-Y~b;9gW+7IEY}2Qpi3c1j0zCdJ3NZnCNnA%)J|qHA7#g8w42H%VOX7_|mP(6-tC>UywW1uSU|!!a=~N?SZ?&OD<?hcptZ$)?B~i'
    'v<uLwi_WiM4;Jppio=*esiZIk&MbQukX(4va$BxAkSji>2`;9s&+K%?D`$!RLEi)t(CZV`T!osA3%;yno~V7)u{{2%al+N#EL6{u'
    '<64|zPg5T;z}R<_qBF*D%CR@(ME34halyF5=ddAXZUW>`=8OM67W@#EMzLwRN7uJvaAmkcw&?xPw8-R*>J5jB#NV46#RxpYZyLtA'
    '&88K9<__>foHysC@e9zfjRyqcBjTq40~W!h3?<?mm~y{qvC}A^6%rJwR2##ZnLbyT6wquKzS<UZf~JfR7e}pn_cWa2`rBW(%=HV>'
    'G>t`Iscmp(UE(?vtQVlHin73a?WJqpUsC>ah<JLld@j##<{>LqF=-R6ZEsFn!e`<k`r-Z;17R$ZFplx**1K0-ABQo=JiefdlW?LP'
    'NIXsD?gQ-w$AtlNG;fo7*uS)<{&<|{H5t7i%L`YgApMJWm_C0O)b>Uzxg+Nb<Nk5`>STg{J_qIS@pXj*YRH&Ki`d6oy5M&;stUbc'
    '#6JmIpbr3#e8=xz4-bUlF^Pa`lb4o4IDRhyz3^ak0B)m~EQx6LtZAKptysa}pqZMfln4Sv5dzVmc=9a(;uy;;@2y3~Z119H+4#!f'
    'CM*bOGO<QfOA>}Y`au+VL4IPP>W-1jwC(oABV*V&MohH`ETa0uq-4%uO(3KkRdz~&2)-)t#FA{sFNZzq483$GVb@<P394kQS(x2%'
    'jV~Tl6AYAGT~#17FM8Cb-|^cY9`9r2XR}jRX4x_P>5>@T7DPP5x`Kt)hfSh;0S(UE2R_K4wy%A@jZV_K6`>)U7#})yI(ttxCPC{m'
    'h!lq9;fW^D0_w7%-@bVK`R%ua{jkQJEdvXXN}<6x-a*1F*)wpa%%b44E%LgwoVKqY{*?2b!15N{ZWfm2r*nvV`_oS+aqg#cx^Os)'
    'RS(<RYzF-4&QHi)XiizA_YSBqm?PTqhMTw@c%x<gzkb_)H=H+ay@EE=xI*)AES$PNphOsrjt9Onw+<zfODx~8^^*(cJHhk^8+jR{'
    'er^i!j@QeB$;1=d4wCcG_r}00zE{nbPdrpcbec=YVM84@h10h4qr!w)n9bQ~wR8#t;#ucRbk7{KE$4bO*rs3ME=r8im3W2OwQ?fH'
    'vB|{3FOc>06c)GdhO(H!IT^rkIbibT6)%gBZ1X$<7=&O5LAAzFL1-I-$_q?<x57NR3ElKT4C$V>{4QRlI*pJ@cz+l4cDZHr#_E{x'
    '40#GNz7EQ}`T6tH=l*u>XH_vIJy;(`({RNX1tjQ+rj1+C{iDUqz`=#^?ji(NHz#m?VvhT1Jj~1R#FxWLhg0IJ%ftnZ#wQ#mB{X3S'
    '#!fXL1jAh=cwp#k>%yza9O|`f8EMui0~r<VYLst&Kb<>vx;)zPR0(Ze@Q0fDavd_n*y+YkYnhefe#j)J7`-%vEU%6sNIun}+Pd;8'
    '{KJpb2~-6jG7Fj$x4$IV0Qm0hV)Iu<_ac4w6fSGMS<ZawmgdQdODW!#+RA{o;L>Ly$&f8ifewp0R`hWBFTMY<{<x&r`qo{%46_r('
    'BT7a0i^&v?R!o0nwZVcWs2}R0Xu{Ro7X79`zI-Z4I+K`U4)5kH6C~^~t%UUh!+DT}rcy@LZCi5#)H2BOoA7Gn9#VxxA>Ar-R3z+h'
    'V3Wjw;;C%sZ3_kheIL<oWnMbMQ25J2)U~8>IvU0`DnIN|*n1m>GBIF&<C+VPcuV6=Z_s>e9}g2ZT7))4_1aLr9zc&fi|H*M(_HRb'
    'cV%z_jX}(B@&!*6>;MmrBn>q=jfmeYHE-4N)xIThln<9ntk799-&9MFF(oxPE?`qSepy+lVY3)gS?qkmw{Ka^3IiaC_K@B`k9+;L'
    'p!k6eK|Wr2$PB{qqJ1A1`El)4V1(@3oFbo49=(iEQ^N4(@YB_RD`OrS3R>E4UTu{y1R$VcO+(k~kvbyPAbUg#Q{e>vD~8>e8(i#K'
    '@n@5JeuUiFi^rfIV+EnEIZj^^+)dL(jY>wfQ_dPQlWtq|S^C)@FVCn{m>L?`1idUi;H8a#TOHJ9l(4vGq(ogi?^^M86?G;UG8##F'
    '41O>kN()E$b+1TsS?GZBz_RVnhg7aCyNRu;JOpd=N0E-<Vd=EiU1Ts+L#9#1$Z4kUMb_?He$ia4u+Y>SAU;4MugB<71K-1GRLfkj'
    'sv}7G(`w(kCq={ML<ykB(=82f-H;?s0!ViZ{o-nmzHb@NBg;2la;G#Dhx4pQx}41e1;XpRi`=k^J3&W-1GxMNc}QQ0!>V}-8xPWI'
    '^pD9K1ixd%K@q`#5ucZdIleBiyOg(Hw1ofhLI2PH=l=)URv}d'
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
        # tuple, exactly as shipping_context overlays the reviewed templates.
        generations=json.loads((root/'.github/package-workflow-generations.json').read_bytes())['generations']
        accepted={'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1',
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
            'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','android-owned-npm5-sync-ci-v1'}]
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
