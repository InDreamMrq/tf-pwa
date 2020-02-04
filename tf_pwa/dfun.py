import functools
import math
import numpy as np

from .tensorflow_wrapper import tf

@functools.lru_cache()
def _tuple_delta_D_trans(j, la, lb, lc):
    s = np.zeros(shape=((2*j+1), (2*j+1), len(la), len(lb), len(lc)))
    for i_a, la_i in enumerate(la):
        for i_b, lb_i in enumerate(lb):
            for i_c, lc_i in enumerate(lc):
                delta = lb_i - lc_i
                if abs(delta) <= j:
                    s[la_i+j][delta+j][i_a][i_b][i_c] = 1.0
    return s

def delta_D_trans(j, la, lb, lc):
    """
    (ja,ja) -> (ja,jb,jc)
    """
    la, lb, lc = map(tuple, (la, lb, lc))
    ret = _tuple_delta_D_trans(j, la, lb, lc)
    return ret

def Dfun_delta(d, ja, la, lb, lc = None):
    r"""
    D_{ma,mb-mc} = \delta[(m1,m2)->(ma, mb,mc))] D_{m1,m2}
    """
    ein_str = "ijd,jdabc->iabc"
    if lc is None:
        lc = (0,)
        ein_str = "ijd,jdabc->iab"
    t = delta_D_trans(ja, la, lb, lc)
    t_cast = tf.cast(t, d.dtype)
    ret = tf.einsum(ein_str, d, t_cast)
    return ret

@functools.lru_cache()
def small_d_weight(j):# the prefactor in the d-function of β
    r"""
    j means 2*j for half-integer

    if  :math:`k \in [max(0,n-m),min(j-m,j+n)], l = 2k + m - n`

    .. math::

      w^{(j,m1,m2)}_{l} = (-1)^{k+m-n}\frac{\sqrt{(j+m)!(j-m)!(j+n)!(j-n)!}}
                                           {(j-m-k)!(j+n-k)!(k+m-n)!k!}

    else

    .. math::
      w^{(j,m1,m2)}_{l} = 0
    """
    ret = np.zeros(shape=(j+1, j+1, j+1))
    def f(x):
        return math.factorial(x//2)
    for m in range(-j, j+1, 2):
        for n in range(-j, j+1, 2):
            for k in range(max(0, n-m), min(j-m, j+n)+1, 2):
                l = (2*k + (m - n))//2
                sign = (-1)**((k+m-n)//2)
                tmp = sign * math.sqrt(1.0*f(j+m)*f(j-m)*f(j+n)*f(j-n))
                tmp /= f(j-m-k)*f(j+n-k)*f(k+m-n)*f(k)
                ret[l][(m+j)//2][(n+j)//2] = tmp
    return ret


def small_d_matrix(theta, j):
    r"""
    d^{j}_{m1,m2}(\theta) = \sum_{l=0}^{2j} w_{l}^{(j,m1,m2)} sin(\theta/2)^{l} cos(\theta/2)^{2j-l}
    """
    a = tf.reshape(tf.range(0, j+1, 1), (1, -1))

    sintheta = tf.reshape(tf.sin(theta/2), (-1, 1))
    costheta = tf.reshape(tf.cos(theta/2), (-1, 1))

    a = tf.cast(a, dtype=sintheta.dtype)
    s = tf.pow(sintheta, a)
    c = tf.pow(costheta, j - a)
    sc = s*c
    w = small_d_weight(j)
    w = tf.cast(w, sc.dtype)
    ret = tf.einsum("il,lab->iab", sc, w)
    return ret


def exp_i(theta, mi):
    theta_i = tf.reshape(theta, (-1, 1))
    mi = tf.cast(mi, dtype=theta.dtype)
    m_theta = mi * theta_i
    im_theta = tf.complex(tf.zeros_like(m_theta), m_theta)
    exp_theta = tf.exp(im_theta)
    return exp_theta


def D_matrix_conj(alpha, beta, gamma, j):
    r"""
     D^{j}_{m_1,m_2}(\alpha, \beta, \gamma)^\star =
            e^{i m_1 \alpha} d^{j}_{m_1,m_2}(\beta) e^{i m_2 \gamma}
    """
    m = tf.reshape(np.arange(-j, j+1, 2), (1, -1))

    d = small_d_matrix(beta, j)
    expi_alpha = tf.reshape(exp_i(alpha, m), (-1, j+1, 1))
    expi_gamma = tf.reshape(exp_i(gamma, m), (-1, 1, j+1))
    expi_gamma = tf.cast(expi_gamma, dtype=expi_alpha.dtype)
    dc = tf.complex(d, tf.zeros_like(d))
    ret = tf.cast(expi_alpha*expi_gamma, dc.dtype) * dc
    return ret

def get_D_matrix_for_angle(angle, j, cached=True):
    alpha = angle["alpha"]
    beta = angle["beta"]
    gamma = angle["gamma"]
    name = "D_matrix_{}".format(j)
    if cached:
        if name not in angle:
            angle[name] = D_matrix_conj(alpha, beta, gamma, j)
        return angle[name]
    return D_matrix_conj(alpha, beta, gamma, j)

def get_D_matrix_lambda(angle, ja, la, lb, lc=None):
    d = get_D_matrix_for_angle(angle, 2*ja)
    return Dfun_delta(d, ja, la, lb, lc)
