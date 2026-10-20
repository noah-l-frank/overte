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
# 7ac434eda9088e57ed329e8c76ce93ef59bf7d57 / tree 350cf3b3cb2650087d960023c17abbfe1b31c3b8.
# It contains complete import membership/root module identities, every affected
# authority and every fixed CI subject read from trusted_tree by plan_affected.
# It is not a complete source tree or native execution/provenance evidence.
_MAIN_PROJECTION_SHA256 = '9f50726170c5b51c6bdf7ae3f3267899b360072911be65bd5efebcd3745f0db2'
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
    'c-qZ<*>)UBlHI#Lqo2j5?~A@dM@R2C=I-WX76BwWk*F%p9R0iQjZCn}E+Qi`K`lMgQzXbKv+%|2UUOUi^B@2Gv^#!&X&>cr9QM2M'
    'VgJXY9zGlo^7uUU@Xz0#_mBVhZ~ys^hyBoh{I`EtV^RqJ_^<zX{w(;dbH?I7(Yn%Y$FGddbE<En$7Fi3)A%{8#s9<c>l6P4?S9|>'
    '@xT7-H?a+Z`sWW%`}<x0x+1MLkAGLvRI?ePy`-FbQ)9B3KDA+HPC-n0TiTQKFY-x0{INfLnfLoYK73MqtsHmz$LAH{qe8F@XQ$Pc'
    'OD-u*e6I=3#h85YL7mSwy)FEpPy6THaew&wp?}u?Wldu2A-jon&9=-js;br*!!%)3d}uA=UC<WZmUz_X<A>*$-BCXbebUFFkA0`B'
    'az_gzb!jF|=WGkf27GLj5#os0RB^64aa-iB$;z!a+iK1=;oq)h_8NQj#dK#y#MfkNEU~>U>vb!ivAG9*Jbw7si`?(#t}na#&#w>n'
    'Z%eNwk21}$wP-NTT72{L-jyT~Qk~*g-R7`K`eFZ@_TvYB`}1Y7GvpMfBwUlJL!<38jco03L27h84x`3jI!b?u{rjQ1DB8KHW~AZk'
    'u+Ge4jH%Unh#&a)=!zM|wD6M)+YS&1%h2z4Smlp>_whG<{IYv|{`g6_&re_9mWqY#q4n-s2q8BY3eK0aIqHZdL_4F}oQ=Ci>Jz>k'
    '8-7`CnAvL(&BZs<v%|;D(%O*JrpwdhVpMy-PVT;4mO5o-(|yPmyBnRUVqh733%zOyJx}Qpi@$1(4=;}wWp-ZCG^W%RO2+3&^~uy?'
    'o7bi;jApXVd6i6_<h%a)uz%3I=e~cs{M97}W3aM<)0BGAu2rI!Y;dSxyJ8=86nouTFB&|`gFeG>>)k=+Y4`Z)q8g)wFniLN0<5Om'
    'px#y&g7lV5vN6z_!Bt(a#?!-H-#^aXW%*gGrs88tu#<~hOx~H;l9V`xGf)mTC-|%7(=U&^KYyR?qWp$)W<nS-W;lsxuo6)!%qcu1'
    'PNc^w82D$oT0Tx7T;)aC+NUoP-H5n&9;Q8a+pISNuhqrbGJHs8!?)9-{2^aIKI)N{?(VREIqKcm$*0Ht^KsWNTN__{6Bu+Gd(?pK'
    'hjmwh>ohS%9Kq3?0J7Ap)p!|C7X`bLlU3`6W?cADx%$uqE@Tdei!d8bqUO9=@af>4r7ysYNAReB9xof9h|8W;oR7dIUa3^9nj0KT'
    'bXB`Gun%e7+};at;c@@4>mOkDe&0RAqv8U7l$WtP-km)jz3jys8KX)VPMWHpu!duVT0<zbi8e)U2398Dtj%&Oc{%Ro1z7U3mCDKY'
    ';YO+f`;mqK-K1JvopWSwfauf!Y?<4Yc>$cfY$-<<Te?d?9ueOzvAYb{fNKJ{7t4$QTHdL>S%)urc+~s5WtT2$QeDG>jGX$&&F2XW'
    'G}~|~THvvn6u1oM*Ug(Xd5}lI?QsW;kE49}diQzvOssNID?`VXW+=^QhZ)Hl;mqJgffcNWh9(EB((PL98~)PoE5<B!GM643tR*mh'
    '&N#i|&G5Z=#R-BPOZ?N@wRk!+54m4%^+EdavSBMD6qf@)shfbP)x_v?A4QVGv39}K0mRzs%_;#?&HLS_&&SQSHf2A7sEmZz;93;-'
    '+!hOZq?rpeya8vMxxGWBHMoTZh@hG#S8sfB#X6#{OnmJscFz=Fig)8?6#zR1jNR^cT<p7VOLQ3p;H-d4)CvBEHSnN|u=_2+_|68_'
    'IBkdhF}E+v^AY#z@?ohs8kwRS_*Cz3LbKxBb}Uo|oy<A<8sBk?j&k^<o4vpU;5E_*(8o+TBZ`Y{LykBknJbil5314Icj<&yUtK}l'
    'zdR0EF*G<P6$c0K9NS{7v64WIQcOL7_NHLOf+qz1MLKP8PhKbZZf&Xh;I)Enn>I(c7ALt39AjFXKFvEdT71;qCNtP0@Vm2cm~f26'
    'smRb)aI(R2#CsoOn}AvG+&6vveRtSDKHx8&w(c^mbBy!UsouBNVoz`pO_G9EtCZ%jX7K34zfY&lUbINa;=w9%YFf0;5x{N%z(6k>'
    'uy4YJheqMosdKjj2>f*N9xF(&wSogRvg-zhxM8zeO}!R43lE>xbULW}KGkmW@-0_Y0Aif+S+fF#bn?Vfo$bIPVFoXw_Ftr0-#;vI'
    'lC=d(Q`A=g`A{tkCHJ!cG{byD+ca#O@Uz8_U!&Et{;rQJtQwTH_Q(wciG%?#Sg&F%+=ug8Y=R*L&3>Ogn=Ap~VW^%VhM}|engkwK'
    'Ov2^wH5;3-p%ygvovM6?iXL`b&Ul^13j+*ZJvdh$J;zpU6X^==yc4xU!hD}z*Fz)hn*cL*t+9EAxu$U;*yI9^c=E+T!(e86uU^1M'
    'cm1FPe|0DK&nwXZP_7Uh9Bru$ux(B(7BPWs0K3-r2Iw^EyLH+E2|S!X4i5fP6qLx~&I48F+=B&VOCYFL@^J2b%G`k7fFawo$)<!G'
    '2HGrf0{!PWgH^F`ISzi%y8b@Jp7$?@j;-5&)`P-wUJk8@9R{RGuriFY>0oHwhe`@CdmUJ`E+xKGC8El^4HVXd0K7ItT#jI7v%$}}'
    '-eh<eHQNdER7|nqSEw^(cmJ{y=q;gi6^&v-l-{$=z_tR+(jAtmdtd4p)xPswA0M9P?q0vKwaeE(!|5k4U}u^gEM}U~U|AaQu3<=a'
    'cI#q#=jlEkUY?KeBwzIFVJ$R@I}dz``yHBEoau@^>NNuAHj6{0Wrk7oJ&fQAWr(tkw|U@#*D|qt)4_&^&<t)^Z^6ep+t}v*&q3<*'
    'pIr79!x!bTs5#{be*r>ofMla>5kNMM5lb&+8^ZqdvY0zPJnWvImp8<VV64?Tv*$y{EZT-oAYv0Vu?5LNOE)rLbGCi*=RJ3Szh5)>'
    'bkN`vMQRQ`j2<0K8=o)X!H2P<3ZeZrnJ3tC*>u|49WI{tArGRcmf(K7%f6QhpEIn74r3dBdW7@;UGHQ(>@Ir}g&V_N7uao=l7J8R'
    'IcAq?J^t4Z&;<~NjfCJVbxSbO7&vjzG7_ZRwI>k!fEyo%WB90puE7j!J4@f+q|F$kd#kR2<bxlQwWa~`!Kce<aM_I;t@gZ?FMj{t'
    'v*jw~0d5ie7~VD;b0ERj3iRx8m2s@WrNPZczC!qknD+fa?|y@OeALSvf~FP5ET<UK0Q*bXNvnp;y&8j4Z>sdUF-G^j1`qq+bs?j0'
    'K`XA%3h04z)3oA+VO+o(fKK|x(o6+w&(Xvx+jY3ks`QQ(Hy+p8ln{In@B}-(6~RqYI3P_R5VdWWztObVF~J>+kZU^}vw|DPh#RhW'
    '!9@%O<{h}(Zx?*BFB{ez90>b9ig9pX&f*ppVCm*V&ki29fw_(7let#(UljJT59zpbfIR}}%2-HtK=uU-KTR~)Zd)8U(MHDca|V5S'
    '?dwl3m)8OJ&i3N)Q|x*e6+8o;EER_Z@G@cND@fZ7ifohbXS4wBKz#*(LJUyq#C`A%KPZy5CD(?z{s;iDFS#7J3Uas{3u+CX)bW)S'
    'UZun2#R#3cx`;!lFpdRCV~lpQ3fop9WBnn|C{9H#e&C<k4J^KZA1gdNz*Pj!xIvAt$Itu6Z2?UlevpKw6ZZl9sTN@3tQ|Z-OYRly'
    '80!^oSd4>y+5y{vX5RgAkf*0Ll+~L7{hc@zFa?Z(!8x`lxpgpdwcrM@406N4cs}kgKf<O2o|YgCaBc)XEjCHh;Z8J~NM@+Tp&QBD'
    'IRRlSAgEcYcqW(3>cO!MJW`lIUH}IpHdiN8VCEJ6=q6NP&5X5{g!RWKx0(6c*@dA%fhJ~vA|=0p4V}LH!|w6v<@gc1et*uY`T&Ig'
    ';SUAy-akBn5na?Klu4F~U0=>$2eJoMtW6mZnYK<Wi;Ejj(hu4|`Uf3MeEME7Qja@1a_QCsM*@}zm<A5w0&E6OMaS(0Ey)4gBYAjF'
    'oZ1b+(YF*^OWK*Z0mM&O7ROivT<92Of_>y>G`2orz{-Y{nZ;SZCO2Ld38;p%Npu>FgGJyAcmo&9T3Rl+qSL1=bEC-D&=_sy9ri&E'
    '5BtO23;x~;YKaaP0X|X^7Qgn?N&mErTC%mXg<wHOVaB)Wablhy&bbmFpAY^2b@Ir%V*l6DN#0iFlv6^2wII!vcqZU&DZ@H!QNhUt'
    '<dRfcvL@sHVr?WDz`%E?^BO={)Vhp%L(49}nsnGym{i<faE{<+oPfj71K@MoGHz66N#Z=6Zn@vd^XB6-67DNtpgJ+ZDZDXrJF#ov'
    '-ZCP71eBOIq+hM-)n0b@;}rkd8gPYWD>haqwObQl=mv~H&Y2OA?)lu}nV)IjuiQCi_uaCs<e}i&alK#?x(4v}YWN!5D|4)qW5$Ek'
    '8s4wi?%`>Fc-_=<()s1cLd(^4H%s)@4p?i;*A8D5kRoKYKzPQM`U^CBgwMLa2hcfu(Zl6arm)b>s^~O;dR;86XNF51zU2TX-#d6o'
    'Z1MeCoj?z4#CI>Wmz`=8KTV$1VDAhJ)xd=u6-Nyxt{5gC2VYBjziQXmt^u5ZvyX!x!-V~IMSwlv-eF2x?0oeAUz1;OEzfX$_pmV8'
    'm-h5oo>#J?r!NU+9_n@QSVj|okYv`Rl@u2aX9B~wUvS1wu5eTMI(rvjC5E@%#R_P!giNQlZj$RvQgc{1qwiPhdG~3_j@Y#W_|29}'
    '84C~^C@+Yv*AM|3W-A4k!R65bbg^JXoBkirZ9zI4p52QMTlu`^4X}fS+r-`)O`v0-h{Zb{DaT)M30?~UE~_)+$eL`(1JK4>U<i;D'
    'm%s~Zv<yhMYT*%XROeNPkJq`%+zabxpwMUxR~2|BpTaD-h^d9jVji1s-o<ZPEsk;}>xQAL;ph(qb}Ha10(e``xNdWvg$lmNyVvJz'
    ';xC7EymKH+a5-?u&h}D+gE8-7fFVpvsnirhi0{>9!!>hB1C#nnb-8!I1K4oifQK{gn7A%Lqrs;9ZdK0w;m6CiVgU^4(#%1!v}}y`'
    'CJ&8i;%|9u7++M1H}6&L3YBViZd6#s30ea{)tIyj{AZnr4AzV>JZ>(q$+0`Ifat85I(>bLSOT)rkL$7EDFa@&htff9ORvOJ)y$fc'
    '4@Po|pf!^HH9D-3Sg<sZ5LaRbJpdudy?N#`k5oqhFo*N9F>U|ujSo$wtFa!)-#KkQd!JGThu0c)sZ_Jh!|wj<aKin`<6MhcsI!hq'
    'TtZT;nbAaiSjUa59vH{L4Pv8zmccpp9b6nJQ|>?B>7U2%O0@3yXDjb@5Q_usLvi$H+Gc}%?4@%d`Nm9fpG7Z=Wy;~@m`oir!lQ%G'
    'DS*&`A?|$sZLD3vnei}qW?Fw)%n9%;zg~Ikt-eKuS=x*_x!7g^hz4o%qb$~6t)}slk7D>s9~l+@D2L;2;u75LmQ0u9N)9>D`H0EJ'
    '7~x7h4xsG{)IeCwv`WVsJeS5rk;_Q|Fvss#)7dP!fOXN$-p3S^#0?`bp9<n$daQ{y;AcMeZvsz=A(zjIFtQiDsg_wGIbvC3=ZW_f'
    'Y#^R^abNkq=eB>i`yF0;tV5bGYXzr{xY`;R<M(1pwo~$y85@w{Xrun@@%n^ThW@_eE`r}Z9VvYa&@(JfD3+0+jtj38R?1Y+d^pKw'
    'Vl*STBx^#4JRMm(vsjqFNyO^?wXRq-gKcchlr~{W+9+y46F^62&UTcZe95{^;`6tv>L-wbZ$G|l*c@L}yD2!j9=NSVUuqNZ;0pQ<'
    'pH^VNTbCO(czW8sJlt(jq%&LFN2_^x#`P-R4cKymGunDr-0(@_m5OXy1gA5Jm<D?rm?)a7Q8#P?{t%a1FXG_O#9k}A@9*JX_9qB`'
    'PJ3KG`#vyo-*N}0$JK_1aRC5YCNufGgH@UZD1Th5%@Q!a`=t8^U3+p2H40!&vAHv$I1rBoxVfTf){v){>{vRqS%u{sY}$)4$I#&?'
    '3>s6-Vkn_ZlbBpks({)HUq0RDz4-rQ5BmP$VMU~|fRHH#@S|=6zH`t3W|-PuaWZ2zfO~+RTSX3i{&L(u-R=9!{qE0AYadOa=xIs;'
    'dj#Z>nnA_mG&Lv?FHA!mKqoh<@agI0?z76c*XNb6=4?7Z9;0<OkJ_^h9>Bx^lJITKCEKwZYJPzpch7Y1k9xn7XB0sYVUxRhpxZh5'
    '>^Df6n2Qh;l+85n?XOX22{3JVjAk%AvTnoo>H3K9SRf@+?NqPaLS^2SPd91>$9*{JKc9DB@Y~nlT?AfWLC(QI00UJ(6YENjQbvrU'
    '4DEwu(JrXFQJ+%;LcZR^pphf#?kyMlV@TD+09RtnOfm9xKF;D)jS0l>*)=e4jkjK_tM#$2!Ep4PK=~`UL<xYYpfYWMgTthDfN%fP'
    't|C9z=V9N!Y`WZ1_=W>goxM#1m%9YGG#2u+CTcQk0my&$t%A>NvF#qmTJ|NFDl5Za%(^X+XEYdi)-n=fXBNga%IInHeSX^YefT(c'
    'e;yh2UxJ^P?HX%#0O)`tV(O&DOcwy0WYojd1P%h!k;`@R|4NzK>{dY2h3TeFB?ZHGYVhUYn-2jRNXyLbOF3Pq$bqd^4%?ORt$_-$'
    'jSdK{6qV*$WV4%&YpTtbfFIP&tAT$j6E&{z@qv(PunO6kQCqYLP8IMI=d*jAT9R}DCB0FD6W-ap9<1m9%Vn4=lm-$%u?Rf@6PxL~'
    '1v!pcOW5q|f8XP`cS}nnvegyq1XyJp2o5YjV+xxg<cCn0CF^VPomqwJvfD<16_+1}ZUD^0h6_=<0O?5#BLL{?lmv${bgl_}l>4v$'
    'p_@vt(qM3d7ar~k8$By)oSY9O!NUXT*<tIftA~CmMSJDtD|Nz^6%^HWu^Ql@jpiPQ6E<@yy#@TEm)zG3&bB(~3Oo?SHUrE8nlh{d'
    '`&J9`5_&WmPqo`UY!$YA>Hhp2%wOJ}{sxf2{f1{(22F8v2N-+klAA^cj{>@m#cu*24HTK%Ft@0)d*s9K{&3e`=7h<4dTFn@Fqd_L'
    '$%pfGU1}_vU7s*O;%6z@S#g<Ryf%h=mrks1J7TTw;g;4i*8<k2#*~bxb+~5QyMSm6_055NMrN;x)_3Xi-SZ9L!PMjK;j){84-B>0'
    '?m>Hv6?&^-8*Ya!6&Hv#X28EgZqe!<t8;$`=C@*+u?vQe^xcBrIamb~>=*?kq;<oByWWkP(cYrN!}1&`_xEc$xRw}wX`@zO0UxVp'
    'ejm<Etkeg#xM5+&EjqBh4|F(;4QrwBOr8}_+5%3>sA7R5J6j?cEK0JYCW$@YqR0N_NH+fTa(}<=aDa1HFkwFjuC@TDr3lDxONU14'
    'OPTaqsor!rmSD}@$#0!*_T~LC@XZN)5a=~!X$+DzP0_>#;%-{!snOeR&q4eCFyPEj+WhO`ekG|6V5Z~}aZ*C*(}V8>YXvNAxD1mI'
    'Zwk^ret|0d+2xo)Dl=u1oGv+Kt!FF?Y)o?1I5?!rICmN8c3qg2`7AgrE72Q9F<oeuH7OpDR|Gp1Jt&X|qA4YSHdfVJ6nU11r+a14'
    '_;H+`_SX{k@tX#nqqjJoU7G{ipI|&5UML#Z8%WSJdXw!xvNC;aU;u%fBTjf4(Tt-}ut2b+$%1aVP;+)O%p~m=B~Hhq--C!<)*-`$'
    'ng;GQ3yz86v^2%9O3T@VJgPN5kG%cb^v`m9Eu)d+>Rn-;@B{z@$}SQBwR^U`7kCzle2Vc-K-$}ObM~#t<GFQIm;QMrLZFc)w;I)F'
    '1E1UL6cHUZJ2wLB-x*RV+l|;M3HIb&_Knq&f9wxTRFkI_kW}H*5_r%Y&Bb0CObC|689t!Grh=3E*tXwQ+VK9h-|HE-^^O}t{C51j'
    'bOX58bza6gWS`(_V7lP!Y~`ztj!ExRJl_Jl7c0L=rwxt0Qf41LKPEdH!pvsy)j7b2@Y4zgog_Q$<(DWlcF#|8T*-KM5=@^VhZ!5&'
    'd?hAY^$GJ409b$#U~)<0eu+j0{nyKy%?~Z|=)l5_?Avq%l@{zij=<;J;$rgfKl!~1-S0o`9yi5WQpsSfR_UN4JV1fLl>qe5Y}xD;'
    '9x^cJ<-Hm`f$FkG<FV_e!!)EZg1fvUx&%fRs!bp&7T|6GM6iGvUg_N{^>o;OtD0WZ3HyWH0Vf$iaWI6vI^Tqemxc&0IQXgQb-Y)n'
    'XFbAGeR{roew3%@&-)dvvd=-g^$P2l6FaJK7YDFrV1~tDg1GbfmudC#bibF&q2|dbJP3T3Si3FY0pc~A+2OL(GE(n{3(37#r{n&M'
    'KAzKNFN3Y(lv%MId_^MAxG1er2wuCXUR`ihuidQB7zak<532kdkE=O?a9f~_ZNg+q2z{hb*v`&)@wS)X;9|48*;L{W_)u~8`FMQV'
    'WSC$QTYz<DUPS=PF*zi)u@(3i+no`UY6~{KSE1*A*gb7={n_-Enr}Y#2!3f|1^BCiA7kaTwxx;`l=B@5t*4oeh&6!m0izra$QVo('
    '?7Au3tcy|MT!u-p-F)H4{y|`;7x(d3ukXwD+Txr_t;0u0Oti$vJ-muz`YQmFMkWQxJ5{>hvD9`$v<@_-1g$1Dn7=Y=wqXnl;Ht#|'
    'Di&7rz#@fTp$}M%?$#Osv4h=+)pj@tAd#-a`^1ZuE%-UM&?RR>G4E7}<xG0qW}%CN%W9f~!JYP&bjvi!A!eEEo;HB0J<iyzDxETp'
    'zTL6!D$Xu%U1XQC5LLY&0vMegJZs?7N-4O0x#90S^Q+Y2KaYo(4J}y#Nw96~WR<~3n{hzbxyDjUDA-*OI_jz~zeumS-rk0tqP4XF'
    '>&RN7U_)lJdm!&-3T$O>Etk~asSv&DhE~?yI+~-ILC72rbn(?!zQuv2IzQ6Ld>*pz)aI1sc)+DQ?hd+IS&@wy-2iF?*H|Zzuv5(I'
    '23t(lvUQRSFXO#ho&Cql<Hp6(nnf${EquFx!p793WWd~>7=kZewRxX!-nviw<DNO?0NiKYR?xNup-nZYtAY8a9Y)emaC#5`F*WBD'
    'o!)M}8ChUHF2k0W?^tWK1M$N&mmHZ|IScm7;;Ml(S;;Y%ILo|Mk^B8v+F6~NM_rEi1a=~qR5bOv)BwO~6dS;adQPq-0kekXeupk3'
    'L+4F8o9|7oB&xTJX@k7l7)>^w5jiJ*VyoDnEQ2J0oxD%6rHFbgH?8kipCSm*01qpOqtWU#cP5s%E(W*HB|e2N!J%7qI)_F6TBdcC'
    'lC5B{HVaGQa!SLy$<$pftO$jT<e|2=6A(z1``7*37#s<JuxvWQuw915#G166nQA*jlEGA8CY#?3OCI-pIASz!_q@Z3t!4aL_%oYB'
    'XRe|yg$m3mP&O>=AwkW+Nh-JVkNtunPju*axqn%)iVb9XHW!;^V=`FjVml)ce0Wq&Y3R9iz1hS5>*1cq8k`>{dt0O?nIdeJ%=&Lw'
    'f(HN53xCkW_f$3DkY%0k(dgV7;_mpFUH2}lV}xBX%7j>eMRrN6kl#C;nDWg_ifOgo42{l|3_J+d@&0~8(gAC8ao0PXRhbold!&k^'
    '<6t{2b`oeZ$69apV~Zyp+kA(EXZOA6gncA_1y)R>*IBEB<@QEK9Juu6c3l=9e|UM^dfOwIJTN}?2COi2H&PNP6Tz(W1VLfX{3<cM'
    'Q={J>HZ=HP?~u_s_{piu&J|$j*(5b*3&*Vt0Bh+t<DlOQf$Q&#rmewyZ<sw)8M5{qdjZjf?IGc_$gW3pph;EUp^5&<e0e@tZ*DsZ'
    ';Wbw_cxWZGk^I6Ao8x#T{8bBE6m5HtQoCh!bn7xzTaxSSiaZR+nXm_5Z_azbGvNe;#)d4uzE7k520oTyQ-I2tx$6UG9(fBQ?IW%_'
    '2&CW-VG;A~Ax~;@WQ<{dSV=hy1nZt%9de$&VR=e`eO3i-b!3K<C4leH<D3lG*Xj-Ph(<YZA><$xZou|o^EAT`Hbude*TxA#?@;BN'
    'pMnKk!8sj_IZil)F+C7ZOQyN1qred2lz`R4o8yZA3T4(`2b-O&7D@p(sAWcArpvj*=;iEui&aeo{(6TpEH7NCoq{Q2`3t-2#S)`u'
    'v%StqaDd7MdozvL5L$na7DsmLykipAYAgzLm`|d<@_h$@6#5td8K2b+CQ3#}#`7NA`wc^=9LD~Sl~`R$Ff1Y^0F$R$Tfv%O*VKdj'
    '0qMX%<45ymnDrO-yjvbNR|@$vL^>C(?;ZOEe5IWGG=c-=#7R!2usi)NP7({lnu+7xImdRT_{~P+N(&r{*w~A$m^h@uMdB`7FyUl@'
    'u(o5Xr+Wd#Jg25Czg~UY29gvurx?IZCN&kfpDNP8s49S+;e(j3X?x1ULC2{C_Q&^$*C5K~1}z094yMgDGkVBgfYNQOA<o#t$ksR+'
    'BVG}%ctfv+B5c;mn9{jfd6*bt?XWYk<<M|w*vM|SP_ckH+^p64@now$fWjU8V5-kK^PU?E#8uQ7;}V?IG+IDN?algppGCP<DS$qX'
    '8zp<HEyhIFkXf3}OJ6&q_QB*U;MPx-;-78TX?gng!t(B5Du8MA!xV358jV+2YQxlWbE{7MAkUxg<neKTl=b@WV8w-6Swm4<t~18w'
    '+5UADm%tY^vmL3sB0uimv^mEtwhsrwj&V@wjA7J4GXNCof&j0lG$k7oK(=nS0Y8SFHY&xoLL<yv0o{A!q%_~GsU{XvoyGNQ#Sa<d'
    'eM*rHZ*JGut?~2JG!WpJjln(q#&iZGIWrE<x*?x#)#zI!WwSyPUaa-#;YjIMImXFMkes0w5IQLS94PtbedFTD^RphWu#e!o4(JeE'
    'II^EX9v1Mc1q+-Sn?!JR_?3FAMrZm7JoWO4!va=9@c|T~+LS%Jmv{{s+?=C$Js-Xj*j5>_$B^Ew&gnU4zumn}$F7eNhsk!GbaN$m'
    ')=q-$Xp^3d`e2*BQ?uo5V5?4?H5ggp)w1gq+g04mwpg&yz<@ZAWXV4r*K?Il&!1n81dQALNdrQ095#V-U6Y?#ZKUVTzR4^g8@>U{'
    'ZU>KNMV6!e{Aw}#%hE{tcu)m|+g%1H@Lrm70}o0-ZPn_)R<h2zB{qx?lfC0=eUC=__8UMGSSrlsU3+;PD~&MNP^pR=GxZR3O!gat'
    'DR)BSj%yGye9JX}=_fk<@S{~|X+b#@M+W~R1t%S5d<ghr^3~;~+b>qJ`R$R+XYGL0ANUjxEcx&F@^Ul^3`nCf71q)wR$)(?1Xn=T'
    'Ivfn#U+M0rEmz)B=KS7$UYYan&V2r|Dy*NI@MQvnG(1yC#raT!0Dx4l70czq73t1zsIm(E;UKc9S_bQUz>|C9BdTCQJfI2ttmWXs'
    '_Iq`dcCTkGPQPYy@AFD#E5}E~nXnp(o$*r1GqlNs0C6m_D#>t~(tEU6TM1Z{IVQW!;b``%%5iCqgG!>hGT5MGj%2pO=+n`B-0=dB'
    'J3buU%hx68dZosUdBhyRJ-`H+(hJ6%rU$_1*yvg{g1cXl40Y1ucR9-8-0JRBMY6_^6YN?{v?4jc-VVpMA}OSni}N{g<b1C4IyL&!'
    '%iTeU0`ETYpKI^vY<g=<9)!wmva;O)Vj0G3t1&+HQ7q6;xn2wW`^QQvHue_DoD1N=IEO?yMTRLVT}@QjRK7GwO4kWLZ2^zLrhQ0e'
    'Xi)ETI^Qh}dT0S$I1iQX4Qq2PFw7P8apy8C*3X<d-Fhugw!T;}N$sIDFCqZD!FB)_@Lc>fLBAxiU8lr3?D={SRyxpuXe%SXZ1ij!'
    'Y$x9|T{JN=-D;?F4%p<%^Z2h9J$&6*8fZBkWwgX(MFY$MO{VpH<efN|L9@p_bwRJw;GjoYCQfe84`?1*u=p4^k_{DGGw|)r7uZP-'
    'm=HUE+H~%s8cRvadMQY=tUu5k6Ly1cqQWqFf$@$l`=q%ywyU~w8_p*ByCvAvLM^#uSQ}b6S(oN9n7I^|1(=8&m>=C+Ygg{basSj{'
    'DtSX!#7FB!g*kF$SYwzLqrhPM-kDMZZ<?#I)?6q4We22pJgywZGQnr;ltzE)u>J~+Ub0uFurR5&GhpY()v}-e*sZ-zb3!hYKtT&w'
    '8SC9(#xAEaf$7-*CK@ekp*PEBcluLW(*s+VaBhLNEj_0~F5oBLGP(``<AJ(e$D&xve&nq>%NYvMy;GCb+92;h-awnmbnHPs;VTK@'
    ';`FI5y|<+DiSK$fDE*x4wK27#2482vePBjR2tLn&8<N>5fi1v1<I7gA$kJI#f<7>h`|A%-;t8M*)@unduja$0${=>3Qv5Fv&EO=l'
    ';v)<xZp{!dIGe)lTK%@)Ep-)3jmO=*mrpBgnfdfQa9_Z;2P*~GEs2iadi>H2wu70YxZ5>4)rCGk325%8wJAB8*swE6?LgpQwAtYF'
    'umXlj-xbu-d(G{Nch|qEbI^zVQD1lOi+-I4d06o^e9>c<Jnva&BE60>;q2n@h2t_<#TpI#&Wcvb0Q)kkNsfozpDSac1ooT;)CU+)'
    'u@*a$;p3$=%jvU*GgjSNSXBQ6Ph8&OH?<&SWj5oC%ZqaaO~qGx_z+ppHpIff4(t48skjy^Xacuzv~D>8X|RIPvjx6oUKD&OZYe0U'
    '_^?LR&reMM)~Kr;_FvW-+DxX#5=t0QUjdFb&P1I1qOOXwrGXOWW;e<|MVnU|1ai7+mE<*4sg>RB!DnKfgD(|W_MWqvxl!V|Lg2NU'
    'cFS9vbs2~NPHN^T4M@THMD*Be<f~10%X`x*mVVV>f9RhX^;?}fmN{4egqrh`IeW8~Y+8;>p@N7FMXGJ9i0zx$KTdFQ516#puDsYh'
    'VBj1l1&Ea1*%`$&W)8FgS^+Gr%zWJ_`biGBNq;RpGd1^@H@$<MF%gR6zB@}HJe%NkID_DmW5oza^|(%frI2T3*j0ezvsqFU4g_H!'
    'HL&a4V2?s;pu?QbY+dqY;_^x&YKZ}KjDxLW0w8DKO%5GPz#k$pV3~tmEo#{988M}y{`0Bd9bX>TdaJSO20p80Cjh<zWIl!)eL@`_'
    'oM_7GpuSr6O1Vp9jjOvpP7Vk^E+rDIjF=or0X!N8C&Os$%_ZMBy~u2l`t`BjO&u^@8{5+`pRNMuCChsB!in0DmqO)b1}(}7_YB~8'
    'gYa`d)l++dyY=Sd@IdeglG(OF;DiFJ-xID-#i5$fcjp=lHMWS>!)|`P?#m%1GJ0z2OmH3%EEpiqSr~6te=ggf!fJbw-}Ldz?(zBK'
    '{l3fn9o)uBpFCrWOpXk$(Wr6|Z70Hya}IAu0Od(;wWR4)=xI(kM@Ba0q|M!@71|#;RVUBTJsY9*?0^9PKM1vHIu&GZYTqdRwSD>P'
    'jA=ljPr9<|F6E`Gqw}&XakO)0AV*G`@9>xf_Opf6&I7M1EQy@Ei;ZowsUg5e_^w5m&;?7@fSz5ju_;cTAvswsKYW#Ve(Kz`*(pvF'
    'V(NvXp%aincFM3ug7cWRg42rsY4_*1C11JYR#E}t%tQT@xr{{>>)<IQ5~-wFz_Y=1uTf#cn!A>KEjY-!U`)6SjUEJm*{f;JFnsOo'
    '_qQVULB~!uH%|jo#MZ(s24_2d(P7sL+{7Hg7Pjh)fWLmMxhee1U)WaU<>{xDzu$jmh0OrO1JW9>CcZfcV=flKV6EL-%URQ_jQJ$-'
    'd1(>-yor}iwWW(=yet?^@Q*dbjD7B~9$+{!`6ip&R>4oK<bB5dT?rtY$V`FCca6lZL%CtKI}S1@YB+7PSh1^F7T?4!FX5{N-z_vJ'
    'd@~p!!dklO8La~t0fWiH(1d2At2yD{q%O%WoBGAfT5PphS;J(s&dg5C!-Gq4s7{)`nmNSBjgm<#cI&y-iTx4qqnaabDzHc&ghK@f'
    '8Ey(!*m`Ge-70j+qj@d1xqDgqGp?>V&=<HGke%&b;iek+VrwONKR~K;2{_kcR}<-8l{lx*fIF^L*aimv;3W%a@|YQi$zg*f@hyLZ'
    '%+CjzjMvFs;;|shPb<~ErB>#6r92C5H(LYYfQ`WFbpSB!9RO`?l>J&&2uOBWEF7VCfs;#}5BPfKov>CVj$9PrzFRGDj2p$y`>!h<'
    'v!rpxphDs(f{P3f71TK3uw<K=uI1L^);qi#OA99Xa?w!E+F0Adq1lG<h#24#K~YQTiq#gjn*{{idYn!VE|2;Gx_BAU`-TfzTxb6{'
    'FlNonzlx>}scba_N&$#nWvk%dULG!=p~$v|oPFJmv8+XK)`g63WP&$j1>7aCt6f!J<(-C*-910-zv#sUR<IJ5ezM-to21Db*vXzM'
    'AhC_X({2C)%&l@?({I<e)=tBs^By$8SmF>x30XWC3@jwm)<-B-R|}Z`E_tJ+!j+v8ODu|y4uBYJRO;hQV=~h=dS@p4Ic$}`-+x(o'
    '$6Ow3;ot)h2J3H{b=CILYN?rp_-Pa$wpt0!TVJV&!lhw{<m@aQp9c2Xg9nJPf`$+l>^$O6w#s|CKkk+}rI%@;GmSlHnU==_-ex#r'
    'J2uYW^jb~!5ioM|d3qiEIR)akReshoVVabEp&3%<D5&as1XpP6&80qoHRrh1EPmG^d6Rengta;LJPlm`U_V+$@Txd?KV=lg<PeN('
    '6o2lE{8{Dx_<1E7z+#W+0938_a11kN4}J>!JdJS%j=5Rex1O)(u8%7@^FUMszIIF)4E928t_6l2Ko430_ct_~*<T|NYrJ}KjbZT6'
    'R@kY@yHg{)K^FG*huNwUUBCjjx>+tWsdU_J2vE1?Sgi{>Tu01|K(Ny=ESP|Qk8HAm=$5ux>2KYOzH3Bv`O{0m;%3hBz*WXcc7X0u'
    'Q^zu}CvI|vonW{6;8V=@>0Z7zSt;%5G=?oIbF+%+oL2=*Sp}TTE7W1$<ZyE<mOj77Eci-S%3cE-3Icm1cKjQzf_t-_>yn_^e1sJR'
    'VbraZ<@CsX`CGB3CX_jC2qS`XGES`qpGR^^ypiLGX<Q}oPTgfsoJMNk2*YwZZ^j-s9HyZ#-(>z7My(8%mt80Igm`w(`wjKH>Sk4s'
    'PjoDu%FO8DyFdklf-@m9fom4O`MdScv;51*r{)d{I03crOX<t4S_(J{Tw?V&;;sYLZ<PA-w1g60o|w?G@*+@7z_QxLdP;(vh?@<r'
    'khAiQB#bm^Tef<NQxDB;lmWMN#_Vg=1znChovC>+orT?syfq-Iv2LX+r-qSiBzlky-L*??%p%4)<}86FQ5?QGaW)ByFzk|+Io6QD'
    '{z)JIJe+p;;~oCFJKo)`B+XRj?)fOyf-EVlho1(Pn<H6Bm%w3KP4*hWuam0IBS$VDwa8Z8LE)rYuM?kZ`_k(maF9jdcyQQp=dO}}'
    '?$p1nbv>J8VdYtTHyt=e%MM!)5NbJH6u7Lb%XYO}-wzs`BNF%QWq#Nn_kF*TVrdP&GDJY6Xnbx-ixD0P%h5d^MhSj3t>z~Dpu;A?'
    'SmxPdW3VlaHcavb?!@zn)n+NavdyvY;cCJB+bgLdHuf?Z1Ij}{k-HbsHbahP4lhhFoPE`YoaV=DI%;g4(_)_q>^u*gxLk{EY-ypD'
    'J-1Vjo~i3A5}$TYdcRu(VxUfpxin6V3>;9f(0?1jI6~{8@fmr&&C$=sR(|iGm^YFlA5DXJ&+LrBCXaqvuwfwVRI9DJ`Ut=%@RgGZ'
    'Yc|Zwwgm@=Sr}{v)Olq&SAt2)&gHgxX->Txmb<bf2AtlTR_c1hc588KLC!nAJ_hF}eq(KOFwrKk3zuE(H~ic`>w|n7$oS#)v%j_d'
    '+dMSURjfp;mZQA_$J!<!1E9X<Ek_W<F@e9=vthR=v}LH`C?!W5u=CS6usaTI0Ph1V_OKwjj3;Qmx_7Cw?U1x$aJ6h`r3be9$$gG8'
    'ie*`fhf?%0eznf}vL?&;$0ymX%p<fzO%_>*sG}tSH;749txC&GMYG~o`^KDAIp{OF@0Px~RzX47NZy1NT!J&v84M!~jkQ&?bl9ON'
    'eVgDTneU_A-zgIe)~QLXOqmK<SoB{Cr!E3R0!4$7;oh>eVdTxSmlE8QYuCeJ8AY-CUDjHdy4bxjt@%;rU~&hmrln-CU@W*;1JI>X'
    'uTbL36sGE?m%v8K9psGBZYLZ-8D?Y%TH*ddA$z_;gWq0=thRi<(^ykr1uHvWiGd;x=bn-O!Fou(n7eY7@GDMVQJ6`uVaWj{g)uCH'
    '#ua3*y<WwFrq8%q#PYrL>yBV63|@jbc!vuozQe&z?0W>E;kfH=$LzA&ApcqK=iPS$<F^kcD$S>^o`v96n4Q51Jz<I&1{<TS;Wfst'
    'hBW`Cz!_q0nuQu5#^L6-;k)k!K)>LBi3~FAu^Sf5-K`GBdP{}v^QdqEGTYREM0cYA2t&agC(u{p6os&iA+gu0v3(ZnWYs<F4gPQO'
    'gH4A@s1uhUz!H&XdJr&Kol5nF2CrE<m+4N-8s;=v0XmcMr7Ur>QduPt0HXK;EUVF)zp1e8^)qX1aLP^l?8&nI-t;j^gW!tu5e5^K'
    '?P@9czf1oy#c^qXvI4y)jDlk@efSu)hEfu+KOc}-$5U#BPYnHCYHY}~^bP2=gKYx~SEw|x78<bui5XkTmdtQ%vG3Aj^JrEDs06=f'
    '?5bK0FLP{=UJ0Q?O4Swc;_1uP%5XyK-L{cmbPm>W+_!bDGzDz(u$9vR^7;UF#GYL6*;ngu(7Q+dv|fCfaUO6u;WQi@&&)7GNx<=b'
    'v@m^DT$o<nY7)dx6?kSZyET8|EBQ9;1N$~r_CscRi?T^<7fyDm9&Be^Ya(8!Yi^n%2r*?Tk}z!6t4sRHGPB9G>M{;QhB3eTRKBXP'
    'd0OoR^&YB$wKU+3IWBG-yoW8JIYxH|<-DC6_4qazc2kG*YH$zybR47Y*o~(VP6AVm-luC;Ib?A-xmKCen?B%0|AK#VTGe6Yg)jrU'
    'fXvtlL>Y6DG?;}Cl+AI@BC`ent6TNpaEHeQVZl+YjvtLFWX?7m*09kTc<9oaHYGybnU~l1zWP4=hAt<B4UHZ*RNzIh3a}aw3wFTA'
    ')_{3=Tw2e>$1n^|lAku)+f><-L7tuK9D?W~d*Q*&frWN9Fb}vc1<sb^p2b{iy41mN9M@h#rWV(krEa?cpa-9$sWi#K(Isy}G~iyb'
    'Uu!jfELynR6!>XHy)Dk_(2;uMBdbXzDXuT`xJG~hFSExhRoT`s3*NyxFxt>zsX}f8v=i8tZGW9)+?|o4zZPrH``xF{I14Xlhx#Cg'
    'Pb&otk}XbQ<g=>joMz_>tT}$mjO-ke_nb#4*P^UX4E8;;6)M5+-8|sB?pCWgU?gK6t>JE(Y@AI^V8t9@Agq`p9~t=PwW`31_j{Gc'
    'mnR&Pg$wTYb7hX3!Zr*Kn5DftxVTYqF{XM+)p%!T1wR_sF3M*)JpRm;{P2zy;k4O$Ria?&OU)iOE4D0JA{zxUKi#cHdH-GXcaIy('
    'hFsGO+Hjg2OZYj`#EmrE4B4BeF=ZEl#L}=b+qGAAw|~AabKJ%Wz+)_k4~K^MWE01y!RNcitR|QZro+VB^;k_BbJ^fO-rKCcrsSCP'
    'I@!lXK$e8%vcMpEwI87hS5-`S_IVy&0@xr2893O}IGGaa#Wz(~nwelnH|TLi1qFm?g$GZJi-qZ`&toL;bzm;qlCX6DG5rQDHr6tP'
    '#DVg_!LD$kM34CD4w_m?S<TSdjYz(lrJYLr?#?BDYZNUOt*Mct76VQghlI}D=N6^nT;Rk;HGN*I!*xm6Ai~MOZFt;FcvelI&CLjN'
    'gcC;+g~7vd^+LcpEZv08Po(Qp79|)HVZqp-8A#YvLcRntox~E|2z$d_eL=37G~f9Y6$7ipDvZPQR!z2sncE=BoH!h!Tn&HE8sLu7'
    'gl-yoZ3<SLrR~!(zXaCY6qpHC%CXJa0BdVH+--_H?H7{{&$jDdR=Q4fSjsqgN?A6C9RNW!86KXbi8JRXlVHkiiY$2wTQ<f3R0cRy'
    'Ao1BcXTP;HXW_|YPL7(;ICb$_Yw<|=j4d)_<L>!ocU*aN0pN_?aBAQv0lo_gOc3T6Qc=sgU8ec9tFOxWUG=&LZI{EWz%;dYJNSgl'
    'RC~eSkd!!@w3!4%WYcZBT>G@`0$-9XlMRg@zIAxFG%9?m!pFvu*w@?TcAGY*T$)XajG!esIJG%v$}KEG;AO5_W*_a`r)56;)myX_'
    'ou2Xe#^O`yB#N9)%JIrI!=6UwLb{*=&+Bc%>ZEop6nxtC{Wne4%_@6E0){~j6KtDdeKi)yGVj;3RKX|Cb(34PIPJ?P-9PAYEjcu~'
    '>VSu*=3H}~4pb@H82~~|@xULfq+1^{@l!R<=Hz8}$59Tu$F-PC&TQ)xGoestwFLYP4sP=tlWL|*hFym2O-u56m#;{Usi2C|CTxk}'
    'pfcD~kf&hT<H$~RMx*heUX9xqb-qiY-5erK4rafBR09Kz0g@{n{xCR!^Ys7<iC`(lo78#jXby_~X-nBuW(opRx54LPim}HIg95rw'
    '2A-_-)iteh(;Yfz_-<Vn%ZVsrqA|VT`!n2eDu7GMs2xX|v#qb0*E;3D{0~b8w#DhBFlq>0*gi0V?FGXLkz*`FV@;R?hELtKxDmV4'
    'bctn?=k?FBN+#%fda6-ymBr!QR6w|3#5EJOD$~9?{9?FXk@3?18q0{S`m|d*4XkGW;KoEwD<~{NAHb1~BS`9GnRv0%S%H?*wF=>1'
    'et`YI;uTB-OJ=H%e24UYQZWz6)}@x(IZbndfw^mAbyp+~b0oI(8JT(yGdF=2tg~X5R!I>q5db^bc&(Lt#%VouneX!OB)d;*=~y%)'
    'xWx>p*Wz8Z4bWAK1`~2^d~gYNUTaM*r1t(mGvR3}y=-JaKfw8sW7JWjXRGUGE4#VOYcC4<Ev^SAQLas9sL_lV11yHJ`6wr4M8g48'
    'sRKP%xIbp*m1`p)=PcX1bLlI)|Ey4(3b<NwVSlWkEieHwgWPa1w*sL!$EV_Yr5fid{#R{Q6Leg&Ry}S8^9`Ag0iO~9RjZL{YXevU'
    '18l363qMigxLfMGfe%kS>$2HugIRl=B^lu93usjX%j87YfSWS<;H6F1Ud~e<@{_KZh9*`b0FYGhZ57zfm|#fZ@GHBHJBfUk9pNVF'
    '+p?ew1Ey1(1MXlaMK^#sYz&jp$ppp;V+ja<?LI7R%T6sywuG{ooHKC{rv-h2JL^E~l}dr@IZpj_y)bQKO^fR+Qez9?1pbU27S2^p'
    ';Q7r2iw)?rl@4la$6S;8t#`&ZCv~1Lv@-HYm~B5=^~H-$5$uGub|%A;FrBs2cel;bH*|@^<<3~e6my3^=$RXz1-v=bky48dz-sDh'
    'cFteTLbhAK4l0^$F)k1!Wn3>H|LDYym_moqDWPXwZS#9JGjI9bA9_d30cNG6v|2Sdc-Sg%x-I5dz3*_k&R3JlHi?@JTZJP@Jqq7p'
    'CjMLVC_0T{_YgSy&g5B`-PI3W?(jAY=*O@H{xbyYZPng_*JTO^&aWGFbk8Pkb(2KetZkJ9(YaB`=9}pjXcM3>K~kK{h^PYlWnjZs'
    'i;=$*yTwur!-7iO5)SeKKk?C(##n<LAOmn6v!o=ettP*ddU$!{JM>EWGn}F@dET<6WNJK4J~r40!?`d53tq!2XZ=p<Mh`Kav0)ZY'
    'ooG2v=Ydj0VWWYbG{Js#kq}qo!haLIVTMy2Y~<Q)>4lS4lbN=Q5uaTIQ7+g4Z8FoFEa$|<KYS0^KOEQQ%>x$$1#v`Yt&AKw&g7Pq'
    'I^BQ=c9aptm^VElIOW_Q9{6VXQSgOd|6`^8NbxTO{DFIc<&W?`iE}`^2{0Wn8cXN5^mZ%T@8zAdCK&-)YvNx_WR;0Je4Lmhv<kq!'
    'fFS_M+F7Ilzhm7MV$bpZb=iE8OatT@SH~68jIwQiEW!?DQ&XiDI9S)pehqGKP@(psm1%fjK{G2`q)JkDOK6S9x<}=t>Nig{SkI9<'
    'd;mS1yL<iTZ_oS33tyak^qG}C98MC3R`!{%O__F<0ddlpvA$j21}VR3KYm!AIpvf7{1|`ld(31tRUY0rK4FB#C#38vY&1wtvz{T+'
    'w{!A22lPB$`}qThZ~pW6=kd~vAy+%d9C$8Pa9Rh-4LF_H%rF4(H-Jp=tv9I^OyGytkNkN-#t#i49J|zOObMR>OB@N;Dm#J$!c}Zu'
    'wo+B=C27p3=I=f%vG$c$sVKQA+f9QnST6x)51$ld0H}uy*xXusJK5tIxaz~bEN=^E;)<W#oquxot!cq!_!2q5I8IPFHSn+?3ceUm'
    '?801!IRNGc{_HI!zJ2e3@3Mz=LpUr)@Rm`7Wq}XCisFPu8w6fAPGK`DfgAXVKt8#CZ1M%?^xH32j4nIMSFK<GU_&x-T;Ogd{-^d1'
    '%WqkTTf+ufr{S8%|GEDkdcW9%|1QVRD=}C&RssK+F!91zY~!sQvJAvyfE>G>e@;kG(ho32pFf<lGd{}LKdsWfX*gXb_@-6_9Ir4F'
    'werc8$?~N#hnzv!jWW;wT*;_|ZRbEc^;lXCI_(wUw=UK`V_UnoCH@o_elPNb@;@#abSu-hO@cA-aBz-&jwCq&Xep&xxAZru4afMW'
    '2^T++Hvob!A6UQK4lqUE*%y6;9$XNEgA1?(s?X8MBmFcb?I-d+y~tsucZl&-_$q2A*i#1*lscuyfs-rE;J1;5jCGs5-6Oc;%Fxlo'
    'QAs^Ud{D9#)(`8;F&(spt+9122g3F@uVmkSI5j$W{`h$}cXy22o#wVZ?N_XUq>`=92pm?OslFBVgM&$O_$lBv_=PfBu|YItt>;A4'
    '%9(H#_hMpIGY5cF@Ted)s~1)<)o$WX>!<!E@UR4u*BWE9xUiR$4f~diXsmGNcnV<05yUOx)YjyUZjku$w3?X@YUq=n7T>{CmpO4}'
    'P2kf$lyK8D&0tbR-jX(y4Yu{Me+9tB?SE#suGKpk*!@d@ad27um<0?m!i|m~oFH3csbCb-UM2OQ$K48NYV69M4X``#JisPPlRVpK'
    'a5ht$K)5DaqgRPtbzq%k{6nqDMVY%2V1Hm}*;c8=k(n9CsU7wjp(ieW*_%x8lR+cI_({Tr&6>d&qu>N*0AJ_$&S~BfyW2m1Sgyy1'
    'f4vB>!R|DmdBf%k+bNSAGIbvq%$mZkzGM=h;zP~IA-11J(k@Egk|q*+DWKp3m(#V-qymU3U?BUXu;L~48C2cXU;TN_Fr}E=(y(Dl'
    '<*+7Jn1L&IkEQ4L0)-lDYQI+ShPky7MqzL`B%qnm(y;IjaEYDn0A)-K!23)Qe^d1H^NW7iJsyExmiCQLM_DUZhy^m7gHHuwvJqs}'
    '`G%v71&0TZ-Fd^_$90p;bsraF2o=~M%Lp3SJsISXGblkR1Q)hCI3Qr*P2#q=IBhsHz?+=5KAmL}3+_^O%!ur^v^qm}=BMpAekSm^'
    'hCH!xGnko;SIe&cQ@EBXC*ESLrppZT<TpXlImU3p*c&hrbca`ggMkm9Y(t)^&+ssVm?eW)OfrqIN!%0MH^|`1a0R#2`wd<K>0z+L'
    'g~9I~#O6fvYuPxrY?Ao1?f^g7`HHQ<7nscPfHnpP)W9%cU@j#q5hr8HZIiImD4>-jsA@yyu;!L+N;>Lj#!qltQpAemIU~;No44U?'
    '*I)m+Wv(BSrd!X9rB>$5!ih^{54k)FNEze3&_&AIB7uK)w5K1I<MRC4JY=O+j4gcH#?IxcI3`#`d^rA_JG{4H;}{&>e6`f|aTt;9'
    'aRNYJQX=>%lK5DaiN=f+=>YY(pY3|lpYe<RoNHzD(XtmVkOBnqIm`}F-=wu@>tbtX<NmQ-dOPg@cxKAs)5}T@sKOXI4Fg9vhGO~v'
    'E5!D~)c~NW>r;#MeY@m!^I)ul5jVah4Gf5l%2~kJ-&#3yt6~k<o#~3N?U3`Y`;{dQ9kwV<uby2KmKl33C8jE{_vFBxPNjrvg`UgC'
    'SB9K=U~1q47i?wE;SPvDPD2r3DpIMO%bd&=t4zeOag10SQ#e(1nKJ@{Azm4U8$4E%4ROR+U&0l_AM_|gj&dsO`g0}J%)nTp*B-@j'
    '=w$I8w+nZzW7DhT*3z(VQ-HsVe|&nN<mZ=%wOMuzx7l!X8x!$TFw8=0Y?BDTU_o-G#VK_5icLRzqf=?!S_y=oKrWfXT!OE3^_;rG'
    ';a#aTczqndhy%G@IDdZk4Y2Rla%UrB0f18KdA*s08BGyjHb=rY{4f*VOSj8sf693e!}4m}J}g<9AI~Q4^`{?C#kn8PaA9{YR^4rT'
    'W{a8a;1ystRenJO8sm&B9{~OG)GXjsGv@#EYX9}%yixU(#kL~3g8Fr^l*Uk^!d04>@BzjENyCZx4XU5IV7_5Ye`q5Q#Hb_L0tk!k'
    'op4nKP;%I0Sl`QmSGlE4c8yg=M_mfRHdt||?6gfQK0Lgn!N;r1QcT8K$30WvB3!e&LGb2aTU1c{Zrm&YUTk&^I>B*lKw|6{*bQr('
    'lYcWb#2K7=_@paQOCOxtz>@9gS-Z}Hp&nY!0103)Oyvza-?Uh#ZbBa#6GP;%<-05#zN?{EDJo2F2e#zfSmuOhou0|~lHHs5{Q2;y'
    '-K~9A;*fM^efYpBlCS~*=w>8eidFFGQs*@4-@I5XxcYDkuImfn<k-z+c;a!l^1=z=+OutgH9qVx2|&ZfU<1}M;`i_hp~@_7tKd~I'
    '=Rz#gz|&az*k}VAH{md{6$JJb-f%F5b#4{-182VM>^jFz7kpaPS^DffS>@;@2EXBRdLvu!X{+Sb@Q*mrUK5~9Hn?;J_}Gq~XU@4a'
    'J8>bFqUkrU|03(P<;+J}9#2-fl){;VTlwmlOYc~cku1Jebi(Sy*;?exjJFT#k0N1PUtbq5Pogma)<5v(w}|Uu0V_;~7x$xN_B#e}'
    'jNWV$`mF-_@~y0`7)~*t(n}mn!sfwg9*B5amswM3MwV?dH-uV-3<DU>0dziAwn~H>OwxT}c+XA;!~%>ywh3ee`hnK&vdqE86t)bn'
    'dAgcaNc=!9O>|gLAQU#YnPsEQC69Q^!<ztgTYSxMsfBJUi|T#Q#?1}zSp~Y-^3ycc3vyQmC$wNWzX>N;XG%Gz3J%*Fh;<X2BTyQ6'
    'e7a8LojmPU5<D_4=j^zoGHuVErFBL*ld{+vQ*{nLTg;VWUs26UGAxYyYypcZ@FCu@c|jexNmz<LaD@fb%WX6dtAP=hE6$O?IrA-p'
    ')s#+UvY&3OzyqBo(b=|H+G@g33)o9YnSOSyZo1Tg9>u024Bjb+-8fC*Dv3Xv-1B3|U7O{g9u2j_5{?Aw2EQ`#**L|pze9X}JLLYO'
    '&}YEUw!b{1GB<BhFHA4v0bZUFf?-?RXdQcvf!Y?S^D2pVt5N3&3s)uxdF?o>xq3GBms$aHOAi`3BE0^5Nac#yP1&j-M~PIKaLiSk'
    'U<8E-#(QAT!I9HmIBf7b@k`CcN){UUhABYO@SLUsOel!61A=cB#wycD;iu_3xu=ST75hIOFD5WF>{B%$>!oE-MZjFX`$n#ZdmEws'
    'o8Se8-pM%EBdw$gxl;MYkU7*3sKSS2SpRE7V#bofMwKKRech_{haK#2q=pZHoTHNzD6p0ce8#z$1<W}}{Ch3<|N1Zg8|yh8$N'
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
            'protected-producer-optional-leaf-common-v1'}
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
            'protected-producer-optional-leaf-common-v1'}]
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
            'protected-producer-optional-leaf-common-v1'}
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
        if installed['name']=='protected-producer-optional-leaf-common-v1':
            self.assertEqual(future['.github/workflows/project-tests.yml'],
                dict(mode='100644',type='blob',sha='f4765fa63bdfede51cf6d711d24a952c5d0e0316'))
            templates['.github/workflows/project-tests.yml']='tools/repository-checks/workflows/producers/protected-project-tests-optional-leaf.yml'
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
                        'protected-producer-optional-leaf-common-v1'}
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
                ('protected-producer-optional-leaf-common-v1','b29e0558dc69bc9dd6fc6b47bd6024382be4079d')):
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
