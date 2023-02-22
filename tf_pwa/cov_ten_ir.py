import numpy as np
import tensorflow as tf


def _half2(s):
    return int(round(s * 2))


def _size(s):
    return _half2(s) + 1


def _srange(s):
    for i in range(_size(s)):
        yield i - s


def _srange_inv(s):
    for i in range(_size(s)):
        yield -(i - s)


def _S(s):
    from sympy import S

    return S(_half2(s)) / 2


def _dim(l, r):
    if l == r:
        return _size(l) ** 2
    return 2 * _size(l) * _size(r)


def DFunc(s, Psi, Theta, Phi):
    """维格纳 D - 矩阵"""
    from tf_pwa.dfun import D_matrix_conj

    return D_matrix_conj(-Psi, Theta, -Phi, _half2(s))


def CGlrs(l, r, s):
    """
    CG coeffs l + r -> s, order [l, r, s]
    """
    from sympy.physics.quantum.cg import CG

    ret = np.zeros((_size(l), _size(r), _size(s)))
    for i_l, li in enumerate(_srange(l)):  # -s + 02 s + 1
        for i_r, ri in enumerate(_srange(r)):
            for i_s, si in enumerate(_srange(s)):
                ret[i_l, i_r, i_s] = float(
                    CG(_S(l), _S(li), _S(r), _S(ri), _S(s), _S(si))
                    .doit()
                    .evalf()
                )
    return ret[::-1, ::-1, ::-1]


def CCGlrs(l1, l2, r1, r2, l, r, s):
    cg1 = CGlrs(l1, l2, l)
    cg2 = CGlrs(r1, r2, r)
    cg3 = CGlrs(l, r, s)
    return np.einsum("abc,def,cfg->abdeg", cg1, cg2, cg3)


_sqrt2 = np.sqrt(2)
# 洛伦兹群基本表示下手征表象 [m] 和时空表象 [\[Mu]] 之间的相似变换矩阵
X_mu_m = np.array(
    [
        [0 + 0j, 1 / _sqrt2, -1 / _sqrt2, 0],
        [1 / _sqrt2, 0, 0, -1 / _sqrt2],
        [1j / _sqrt2, 0, 0, 1j / _sqrt2],
        [0, -1 / _sqrt2, -1 / _sqrt2, 0],
    ]
)

X_m_mu = np.linalg.inv(X_mu_m)


def C_sigma_sigmabar(s, p):
    """SU2 群的从原表示的复共轭表示到原表示的相似变换矩阵"""
    from sympy import pi
    from sympy.physics.wigner import wigner_d_small

    ret = wigner_d_small(_S(s), p * pi)
    return np.array(ret.evalf(), dtype=np.float64)[::-1, ::-1]


def Metric(l, r):
    if l == r:
        C_sigma_sigmabar(l, 1)[:, None, :, None] * C_sigma_sigmabar(r, 1)[
            None, :, None, :
        ]
    else:
        a = (
            C_sigma_sigmabar(l, 1)[:, None, :, None]
            * C_sigma_sigmabar(r, 1)[None, :, None, :]
        )
        zeros = np.zeros_like(a)
        return np.concatenate(
            [
                np.concatenate([a, zeros], axis=0),
                np.concatenate([zeros, a], axis=0),
            ],
            axis=1,
        )


def u_m_sigma(l, r, s):
    ret = CGlrs(l, r, s)
    return np.reshape(ret, (-1, ret.shape[-1]))


def uu_m_sigma(l1, r1, l2, r2, l, r, s):
    ret = CCGlrs(l1, l2, r1, r2, l, r, s)
    ret = np.transpose(ret, (0, 2, 1, 3, 4))
    return np.reshape(ret, (-1, ret.shape[-1]))


def Uabba(A, B):
    delta = np.zeros((A * B, A * B, A, B))
    for m1 in range(A * B):
        for m2 in range(A * B):
            for a in range(A):
                for b in range(B):
                    if m1 == a * B + b and m2 == b * A + a:
                        delta[m1, m2, a, b] = 1
    delta = np.reshape(delta, (A * B, A * B, -1))
    return np.sum(delta, axis=-1)


def DirectSum(u1, u2, n=1):
    if n == 1:
        zeros = np.zeros((u2.shape[0], u1.shape[1]))
        return np.concatenate([u1, zeros], axis=0)
    elif n == 2:
        zeros = np.zeros((u1.shape[0], u2.shape[1]))
        return np.concatenate([zeros, u2], axis=0)
    else:
        raise ValueError("n not in 1,2")


def U_m_sigma(l, r, s, n=1):
    if l == r:
        return u_m_sigma(l, r, s)
    else:
        return DirectSum(u_m_sigma(l, r, s), u_m_sigma(r, l, s), n)


def Ubar_sigma_m(l, r, s, n):
    return U_m_sigma(l, r, s, (2 * n) % 3).T


def UU_m_sigma(l1, r1, l2, r2, l, r, s, n1, n2):
    if l1 == r1 and l2 == r2:
        return uu_m_sigma(l1, r1, l2, r2, l, r, s)
    elif l2 == r2:
        return DirectSum(
            uu_m_sigma(l1, r1, l2, r2, l, r, s),
            uu_m_sigma(r1, l1, l2, r2, r, l, s),
            n1,
        )
    elif l1 == r1:
        a = Uabba((2 * l1 + 1) * (2 * r1 + 1), 2 * (2 * l2 + 1) * (2 * r2 + 1))
        b = DirectSum(
            uu_m_sigma(l2, r2, l1, r1, l, r, s),
            uu_m_sigma(r2, l2, l1, r1, r, l, s),
            n2,
        )
        return np.dot(a, b)
    else:
        a = Uabba((2 * l1 + 1) * (2 * r1 + 1), 2 * (2 * l2 + 1) * (2 * r2 + 1))
        b = DirectSum(
            uu_m_sigma(l2, r2, l1, r1, l, r, s),
            uu_m_sigma(r2, l2, l1, r1, l, r, s),
            n2,
        )
        c = DirectSum(
            uu_m_sigma(l2, r2, r1, l1, r, l, s),
            uu_m_sigma(r2, l2, r1, l1, r, l, s),
            n2,
        )
        return DirectSum(np.dot(a, b), np.dot(a, c), n1)


def UUbar_sigma_m(l1, r1, l2, r2, l, r, s, n1, n2):
    ret = UU_m_sigma(l1, r1, l2, r2, l, r, s, (2 * n1) % 3, (2 * n2) % 3)
    return ret.T


def Pmm1m2(l, r, n, l1, r1, l2, r2, l12, r12, n1, n2, s):
    a = U_m_sigma(l, r, s, n1)
    b = UUbar_sigma_m(l1, r1, l2, r2, l12, r12, s, n1, n2)
    ret = np.dot(a, b)
    return np.reshape(ret, (_dim(l, r), _dim(l1, r1), _dim(l2, r2)))


def tLGen(q_mu, L, lib=np):
    p = Pmm1m2(
        L / 2,
        L / 2,
        1,
        (L - 1) / 2,
        (L - 1) / 2,
        1 / 2,
        1 / 2,
        L / 2,
        L / 2,
        1,
        1,
        L,
    )
    if hasattr(q_mu, "astype"):
        q_mu = q_mu.astype(X_m_mu.dtype)
    else:
        q_mu = tf.cast(q_mu, X_m_mu.dtype)
    return lib.einsum("abc,cd,...d->...ab", p, X_m_mu, q_mu)


def tmL(q_mu, L, lib=np):
    if L == 0:
        return np.array([1.0])
    res = tLGen(q_mu, 1)[..., :, 0]
    for i in range(2, L + 1):
        res = lib.einsum("...ab,...b->...a", tLGen(q_mu, i, lib=lib), res)
    return res


def _slr(s, m=1):
    if _half2(s) % 2 == 0:
        return [s, s / 2, s / 2]
    else:
        return [s, (2 * s + 1) / 4, (2 * s - 1) / 4]


def mass2(p_mu):
    return np.sum(p_mu**2 * np.array([1, -1, -1, -1]), axis=-1)


def LorentzTrans(p_mu):
    x0, x1, x2, x3 = np.moveaxis(p_mu / np.sqrt(mass2(p_mu)), -1, 0)
    res = np.stack(
        [
            x0,
            x1,
            x2,
            x3,
            x1,
            x1 * x1 / (1 + x0) + 1,
            x1 * x2 / (1 + x0),
            (x1 * x3) / (1 + x0),
            x2,
            (x1 * x2) / (1 + x0),
            x2**2 / (1 + x0) + 1,
            (x2 * x3) / (1 + x0),
            x3,
            (x1 * x3) / (1 + x0),
            (x2 * x3) / (1 + x0),
            1 + x3**2 / (1 + x0),
        ],
        axis=-1,
    ).reshape((-1, 4, 4))
    return res


def _decomp(l1, r1, l2, r2):
    for l in range(_half2(abs(l1 - l2)), _half2(l1 + l2 + 1), 2):
        for s in range(_half2(abs(r1 - r2)), _half2(r1 + r2 + 1), 2):
            yield l / 2, s / 2


def Flatten(a, idxs=None, keep=False):
    if idxs is None:
        if keep:
            return tf.reshape(a, (a.shape[0], -1))
        return tf.reshape(a, (-1,))
    else:
        new_idx = []
        sizes = []
        idx_bias = 1
        if keep:
            sizes.append(a.shape[0])
            idx_bias = 0
        for i in idxs:
            new_idx += [j - idx_bias for j in i]
            tmp = 1
            for j in i:
                tmp = tmp * a.shape[j - idx_bias]
            sizes.append(tmp)
        ret = tf.transpose(a, new_idx)
        ret = tf.reshape(a, sizes)


def U_zeta_sigma(H, nH):
    """
    螺旋度为 H 的无质量粒子的协变和逆变自旋波函数, 其中 nH=1,2 分别代表左旋和右旋
    """
    dim = 2 * H + 1
    a = np.zeros(dim)
    a[-1] = 1
    a = np.diag(a)
    b = np.zeros(dim)
    b[0] = 1
    b = np.diag(b)
    res = DirectSum(a, b, nH)
    # res = DirectSum(
    #        DiagonalMatrix(Table(KroneckerDelta(l, dim), [l, 1, dim])),
    #        DiagonalMatrix(Table(KroneckerDelta(r, 1), [r, 1, dim])), nH);
    return res


def Ubar_sigma_zeta(H, nH):
    return U_zeta_sigma(H, (2 * nH) % 3).T


def SCRep(s):
    if int(s * 2) % 2 == 0:
        return s / 2, s / 2
    else:
        return (2 * s + 1) / 4, (2 * s - 1) / 4


# (*根据质量 m , 自旋 s 和标记 id 输出相应的协变和逆变自旋波函数, 其中 id=1,-1 \
# 对于有质量粒子和无质量粒子分别代表宇称和螺旋度*)
def SWF(s, id_, m_zero=False):
    l, r = SCRep(s)
    if s == 0:
        return np.array([[1]])
    if m_zero:
        if id_ == 1:
            ret = U_zeta_sigma(s, 1)
        else:
            ret = U_zeta_sigma(s, 2)
    else:
        if s % 1 == 0:
            ret = u_m_sigma(l, r, s)
        else:
            ret = (
                1
                / _sqrt2
                * (U_m_sigma(l, r, s, 1) + id_ * U_m_sigma(l, r, s, 2))
            )
    return ret


def SWFbar(s, id_, m_zero=False):
    l, r = SCRep(s)
    if s == 0:
        return np.array([[1]])
    else:
        if m_zero:
            if id_ == 1:
                ret = Ubar_sigma_zeta(s, 2)
            else:
                ret = Ubar_sigma_zeta(s, 1)
        else:
            if s % 1 == 0:
                ret = u_m_sigma(l, r, s).T
            else:
                ret = (1 / _sqrt2) * (
                    id_ * Ubar_sigma_m(l, r, s, 1) + Ubar_sigma_m(l, r, s, 2)
                )
    return ret


def SPT(s, id0, s1, id1, s2, id2, m0_zero=False, m1_zero=False, m2_zero=False):
    # return Flatten(dyad(SWF(s, id0, m0_zero), SWFbar(s1, id1, m1_zero),
    #  SWFbar(s2, id2, m2_zero)), [[1], [4], [6], [3, 5, 2]]) @ Flatten(CGlrs(s1, s2, s));
    f0 = SWF(s, id0, m0_zero)
    f1 = SWFbar(s1, id1, m1_zero)
    f2 = SWFbar(s2, id2, m2_zero)
    cg = CGlrs(s1, s2, s)
    return np.einsum("ms,lrs,lp,rq->mpq", f0, cg, f1, f2)


# (*任意不可约表示 (l,r) 下的洛伦兹变换*)
def LorentzRotation(l, r, Theta, Phi):
    zeros = tf.zeros_like(Theta)
    a = DFunc(l, -Phi, -Theta, zeros)
    b = a if l == r else DFunc(r, -Phi, -Theta, zeros)
    return tf.reshape(
        a[..., :, None, :, None] * b[..., None, :, None, :],
        (*a.shape[:-2], a.shape[-2] * b.shape[-2], a.shape[-1] * b.shape[-1]),
    )


def LorentzBoost3(l, r, CurlyTheta):
    zeros = tf.zeros_like(CurlyTheta)
    i_curly_theta = tf.complex(zeros, CurlyTheta)
    a = DFunc(l, i_curly_theta, zeros, zeros)
    b = DFunc(r, -i_curly_theta, zeros, zeros)
    return tf.reshape(
        a[..., :, None, :, None] * b[..., None, :, None, :],
        (*a.shape[:-2], a.shape[-2] * b.shape[-2], a.shape[-1] * b.shape[-1]),
    )


def LorentzBoost(l, r, CurlyTheta, Theta, Phi):
    a = LorentzRotation(l, r, Theta, Phi)
    b = LorentzBoost3(l, r, CurlyTheta)
    c = LorentzRotation(l, r, Theta, -Phi)
    return tf.einsum("...ab,...bc,...dc->...ad", a, b, c)


# (*任意自共轭表示 [l,r] 下的洛伦兹 BOOST 和转动*)
def LorentzBoostSC(l, r, CurlyTheta, Theta, Phi):
    if l == r:
        return LorentzBoost(l, r, CurlyTheta, Theta, Phi)
    else:
        a = LorentzBoost(l, r, CurlyTheta, Theta, Phi)
        b = a if l == r else LorentzBoost(r, l, CurlyTheta, Theta, Phi)
        c1 = tf.zeros((*a.shape[:-2], b.shape[-2], a.shape[-1]), a.dtype)
        c2 = tf.zeros((*a.shape[:-2], a.shape[-2], b.shape[-1]), a.dtype)
        d1 = tf.concat([a, c1], axis=-2)
        d2 = tf.concat([c2, b], axis=-2)
        return tf.concat([d1, d2], axis=-1)


def LorentzRotationSC(l, r, Theta, Phi):
    if l == r:
        return LorentzRotation(l, r, Theta, Phi)
    else:
        a = LorentzRotation(l, r, Theta, Phi)
        b = LorentzRotation(r, l, Theta, Phi)
        c1 = tf.zeros((*a.shape[:-2], b.shape[-2], a.shape[-1]), a.dtype)
        c2 = tf.zeros((*a.shape[:-2], a.shape[-2], b.shape[-1]), a.dtype)
        d1 = tf.concat([a, c1], axis=-2)
        d2 = tf.concat([c2, b], axis=-2)
        return tf.concat([d1, d2], axis=-1)


def LorentzInvSC_m_zero(p_Mu, s):
    x = p_Mu / p_Mu[..., 0:1]
    x0, x1, x2, x3 = x[..., 0], x[..., 1], x[..., 2], x[..., 3]
    zeros = tf.zeros_like(x1)
    CurlyTheta = zeros
    Theta = tf.where((x1 == 0) & (x2 == 0), zeros, tf.math.acos(x3))
    Phi = tf.where(
        (x1 == 0) & (x2 == 0),
        zeros,
        tf.where(
            x2 >= 0,
            tf.math.acos(x1 / (tf.sqrt(1 - x3**2))),
            2 * np.pi - tf.math.acos(x1 / (tf.sqrt(1 - x3**2))),
        ),
    )
    l, r = s, 0
    return LorentzRotationSC(l, r, Theta, Phi)


def LorentzInvSC_m_nzero(p_Mu, s):
    _epsilon = 1e-10
    pp = tf.reduce_sum(p_Mu * p_Mu * np.array([1, -1, -1, -1]), axis=-1)
    x = p_Mu / tf.sqrt(pp[..., None])
    x0, x1, x2, x3 = x[..., 0], x[..., 1], x[..., 2], x[..., 3]

    zeros = tf.zeros_like(x1)
    cut2 = (tf.abs(x1) < _epsilon) & (tf.abs(x2) < _epsilon)
    cut1 = cut2 & (tf.abs(x3) < _epsilon)
    CurlyTheta = tf.where(cut1, zeros, tf.math.acosh(x0))
    Theta = tf.where(cut1, zeros, tf.math.acos(x3 / tf.sqrt(x0**2 - 1)))
    Phi = np.where(
        cut1,
        0,
        np.where(
            cut2,
            0,
            np.where(
                x2 > 0,
                tf.math.acos(x1 / (tf.sqrt(x0**2 - x3**2 - 1))),
                2 * np.pi
                - tf.math.acos(x1 / (tf.sqrt(x0**2 - x3**2 - 1))),
            ),
        ),
    )
    l, r = SCRep(s)
    # print(x0, x1, x2, x3)
    # print("theta: ", CurlyTheta, Theta, Phi)
    return LorentzBoostSC(l, r, CurlyTheta, Theta, Phi)


def LorentzInvSC(p_Mu, s, m_zero=True):
    if m_zero:
        return LorentzInvSC_m_zero(p_Mu, s)
    return LorentzInvSC_m_nzero(p_Mu, s)


def create_proj2(
    s, id0, s1, id1, s2, id2, S, L, m0_zero=False, m1_zero=False, m2_zero=False
):
    id0 = 1 if id0 is None else id0
    id1 = 1 if id1 is None else id1
    id2 = 1 if id2 is None else id2

    swf1 = SWF(s1, id1, m1_zero)
    swf2 = SWF(s2, id2, m2_zero)
    PsSL = SPT(s, id0, S, id1 * id2, L, 1, m0_zero=m0_zero)
    PSs1s2 = SPT(
        S, id1 * id2, s1, id1, s2, id2, m1_zero=m1_zero, m2_zero=m2_zero
    )
    CapitalGamma_L = np.einsum(
        "sSL,Spq->spqL", PsSL, PSs1s2
    )  # (PsSL @ tLq) @ PSs1s2;
    a0 = SWFbar(s, id0, m0_zero)
    # print((s, s1,s2), PsSL.shape,  PSs1s2.shape, CapitalGamma_L.shape,  swf1.shape, swf2.shape)
    if m1_zero:
        if m2_zero:
            Amp_L = np.einsum(
                "ms,spqL,Pi,Qj->LmijpPqQ", a0, CapitalGamma_L, swf1, swf2
            )
        else:
            Amp_L = np.einsum(
                "ms,spqL,Pi,qj->LmijpP", a0, CapitalGamma_L, swf1, swf2
            )
    else:
        if m2_zero:
            Amp_L = np.einsum(
                "ms,spqL,pi,Qj->LmijqQ", a0, CapitalGamma_L, swf1, swf2
            )
        else:
            Amp_L = np.einsum(
                "ms,spqL,pi,qj->Lmij", a0, CapitalGamma_L, swf1, swf2
            )
    return Amp_L


def create_proj3(
    s, id0, s1, id1, s2, id2, S, L, m0_zero=False, m1_zero=False, m2_zero=False
):
    id0 = 1 if id0 is None else id0
    id1 = 1 if id1 is None else id1
    id2 = 1 if id2 is None else id2

    swf1 = SWF(s1, id1, m1_zero)
    swf2 = SWF(s2, id2, m2_zero)
    PsSL = SPT(s, id0, S, id1 * id2, L, 1, m0_zero=m0_zero)
    PSs1s2 = SPT(
        S, id1 * id2, s1, id1, s2, id2, m1_zero=m1_zero, m2_zero=m2_zero
    )
    CapitalGamma_L = np.einsum(
        "sSL,Spq->spqL", PsSL, PSs1s2
    )  # (PsSL @ tLq) @ PSs1s2;
    a0 = SWFbar(s, id0, m0_zero)
    # print((s, s1,s2), PsSL.shape,  PSs1s2.shape, CapitalGamma_L.shape,  swf1.shape, swf2.shape)
    Amp_L = np.einsum(
        "ms,spqL,Pi,Qj->LmijpPqQ", a0, CapitalGamma_L, swf1, swf2
    )
    return Amp_L


def helicityPWA(
    s,
    id0,
    p1_Mu,
    s1,
    id1,
    p2_Mu,
    s2,
    id2,
    S,
    L,
    m0_zero=False,
    m1_zero=False,
    m2_zero=False,
):
    if m1_zero:
        swf1 = LorentzInvSC(p1_Mu, s1) @ SWF(s1, id1, m1_zero)
    else:
        swf1 = SWF(s1, id1, m1_zero)
    if m2_zero:
        swf2 = np.einsum(
            "...ab,bc->...ac", LorentzInvSC(p2_Mu, s2), SWF(s2, id2, m2_zero)
        )  # LorentzInvSC(p2_Mu, s2) @ SWF(s2, id2, m2_zero)
    else:
        swf2 = SWF(s2, id2, m2_zero)
    p = p1_Mu + p2_Mu
    from tf_pwa.angle import LorentzVector as lv

    p1s_Mu = lv.rest_vector(
        p, p1_Mu
    )  # LorentzTrans[g\[Mu]\[Nu] . p\[Mu]] . p1\[Mu];
    p2s_Mu = lv.rest_vector(
        p, p2_Mu
    )  # LorentzTrans[g\[Mu]\[Nu] . p\[Mu]] . p2\[Mu];
    qs_Mu = p1s_Mu - p2s_Mu
    PsSL = SPT(s, id0, S, id1 * id2, L, 1, m0_zero=m0_zero)
    tLq = tmL(qs_Mu, L)
    PSs1s2 = SPT(
        S, id1 * id2, s1, id1, s2, id2, m1_zero=m1_zero, m2_zero=m2_zero
    )
    CapitalGamma = np.einsum(
        "sSL,...L,Spq->...spq", PsSL, tLq, PSs1s2
    )  # (PsSL @ tLq) @ PSs1s2;
    a0 = SWFbar(s, id0, m0_zero)
    Amp = np.einsum(
        "ms,...spq,...pi,...qj->...mij", a0, CapitalGamma, swf1, swf2
    )  # SWFbar(m, s, id0) @ Flatten(CapitalGamma, [[1], [2, 3]]) @  Flatten(dyad(swf1, swf2), [[1, 3], [2], [4]]);
    # res = Amp // Simplify
    return Amp


def cal_amp(j0, j1, j2, l, s, p1, p2, coeff_s=[1], coeff_ls=[1]):
    slr0 = _slr(j0)
    slr1 = _slr(j1)
    slr2 = _slr(j2)

    Ubar0 = Ubar_sigma_m(slr0[1], slr0[2], slr0[0], 1)
    U1 = U_m_sigma(slr1[1], slr1[2], slr1[0], 1)
    U2 = U_m_sigma(slr2[1], slr2[2], slr2[0], 1)

    slrs = _slr(s)
    slrl = _slr(l)

    def Mstar_012(p1star, p2star):
        PS12 = 0
        for c, (chi_l, chi_r) in zip(
            coeff_s, _decomp(slr1[1], slr1[2], slr2[1], slr2[2])
        ):
            # print("s12", c, list(_decomp(slr1[1], slr1[2], slr2[1], slr2[2])), (chi_l, chi_r), Pmm1m2(slrs[1], slrs[2], 1, slr1[1], slr1[2], slr2[1], slr2[2], chi_l, chi_r, 1, 1, slrs[0]))
            PS12 = PS12 + c * Pmm1m2(
                slrs[1],
                slrs[2],
                1,
                slr1[1],
                slr1[2],
                slr2[1],
                slr2[2],
                chi_l,
                chi_r,
                1,
                1,
                slrs[0],
            )
        P0SL = 0
        for c, (chi_l, chi_r) in zip(
            coeff_ls, _decomp(slrs[1], slrs[2], slrl[1], slrl[2])
        ):
            # print("sl",c, list(_decomp(slrs[1], slrs[2], slrl[1], slrl[2])),  (chi_l, chi_r), Pmm1m2(slr0[1], slr0[2], 1, slrs[1], slrs[2], slrl[1], slrl[2], chi_l, chi_r, 1, 1, slr0[0]))
            P0SL = P0SL + c * Pmm1m2(
                slr0[1],
                slr0[2],
                1,
                slrs[1],
                slrs[2],
                slrl[1],
                slrl[2],
                chi_l,
                chi_r,
                1,
                1,
                slr0[0],
            )
        tL = tmL(p1star - p2star, l)
        # Gamma_012 = np.einsum("asl,...l,sbc->...abc", P0SL , tL ,PS12)
        # return np.einsum("ax,...xyz,yb,zc->...abc", Ubar0, Gamma_012, U1, U2)
        # return np.einsum("xa,asl,...l,sbc,by,cz->...xyz",Ubar0, P0SL , tL ,PS12, U1, U2 )
        proj = np.einsum("xa,asl,sbc,by,cz->lxyz", Ubar0, P0SL, PS12, U1, U2)
        return np.einsum("...l,lxyz->...xyz", tL, proj)

    g_munu = np.array([1, -1, -1, -1])
    p0 = p1 + p2
    trans = LorentzTrans(g_munu * p0)
    return Mstar_012(
        np.einsum("...ab,...b->...a", trans, p1),
        np.einsum("...ab,...b->...a", trans, p2),
    )


def create_proj(j0, j1, j2, l, s, coeff_s=[1], coeff_ls=[1]):
    slr0 = _slr(j0)
    slr1 = _slr(j1)
    slr2 = _slr(j2)

    Ubar0 = Ubar_sigma_m(slr0[1], slr0[2], slr0[0], 1)
    U1 = U_m_sigma(slr1[1], slr1[2], slr1[0], 1)
    U2 = U_m_sigma(slr2[1], slr2[2], slr2[0], 1)

    slrs = _slr(s)
    slrl = _slr(l)
    PS12 = 0
    for c, (chi_l, chi_r) in zip(
        coeff_s, _decomp(slr1[1], slr1[2], slr2[1], slr2[2])
    ):
        # print("s12", c, list(_decomp(slr1[1], slr1[2], slr2[1], slr2[2])), (chi_l, chi_r), Pmm1m2(slrs[1], slrs[2], 1, slr1[1], slr1[2], slr2[1], slr2[2], chi_l, chi_r, 1, 1, slrs[0]))
        PS12 = PS12 + c * Pmm1m2(
            slrs[1],
            slrs[2],
            1,
            slr1[1],
            slr1[2],
            slr2[1],
            slr2[2],
            chi_l,
            chi_r,
            1,
            1,
            slrs[0],
        )
    P0SL = 0
    for c, (chi_l, chi_r) in zip(
        coeff_ls, _decomp(slrs[1], slrs[2], slrl[1], slrl[2])
    ):
        # print("sl",c, list(_decomp(slrs[1], slrs[2], slrl[1], slrl[2])),  (chi_l, chi_r), Pmm1m2(slr0[1], slr0[2], 1, slrs[1], slrs[2], slrl[1], slrl[2], chi_l, chi_r, 1, 1, slr0[0]))
        P0SL = P0SL + c * Pmm1m2(
            slr0[1],
            slr0[2],
            1,
            slrs[1],
            slrs[2],
            slrl[1],
            slrl[2],
            chi_l,
            chi_r,
            1,
            1,
            slr0[0],
        )
    # Gamma_012 = np.einsum("asl,...l,sbc->...abc", P0SL , tL ,PS12)
    # return np.einsum("ax,...xyz,yb,zc->...abc", Ubar0, Gamma_012, U1, U2)
    # return np.einsum("xa,asl,...l,sbc,by,cz->...xyz",Ubar0, P0SL , tL ,PS12, U1, U2 )
    proj = np.einsum("xa,asl,sbc,by,cz->lxyz", Ubar0, P0SL, PS12, U1, U2)
    return proj