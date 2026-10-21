"""
K4 on a grid of the (x, y) plane, then interpolation + classification.

A = fixed reference programme (REF_KEY), B = programme at the plane point (x, y)
  K4_A = P(B > gamma * A)      (same as K4_pmf in your discern script)
  K4_B = P(A > gamma * B)
x = collective housing surface, y = office surface (adapt programme_from_xy).

Tip: with n_jobs > 1, set POLARS_MAX_THREADS=1 in your shell to avoid
oversubscribing the CPU (each worker also uses polars).
"""
import os
import numpy as np
import polars as pl
from tqdm import tqdm
from joblib import Parallel, delayed          # joblib >= 1.3 for return_as="generator"
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import binary_dilation

from archetypes_re2020.config import PROCESSED_DATA_DIR

from archetypes_re2020.compute.pu.discern_pu_weighted import (
    build_Hb_filtered, prepare, run_variant, K4_pmf,
    dict_w, df_open_scores, Hbs_folder, f_tilde_from_var,open_by_iter
)


param_amenageur = {
    "Ksol" : 349, # prix du m2 sol en euros
    "Klc" : 332, # charge foncière logement collectif en euros/m2SDP
    "Kbur" : 239, # charge foncière bureau en euros/m2SDP
    "Cep" : 350, # cout de construction espace public en euros/m2
    "Cequip" : 2500, # cout de construction équipement public en euros/m2SDP
    "Eep_lc" : 0.36, # ratio de m2 d'espace public par m2 de logements
    "Eequip_lc" : 0.05, # ratio de m2 d'équipement public par m2 de logements
    "Eep_bur" : 0.1, # ratio de m2 d'espace public par m2 de bureaux
    "Eequip_bur" : 0, # ratio de m2 d'équipement public par m2 de bureaux
    "Rlc" : 3, # m2SDP par m2 emprise au sol logement collectif
    "Rbur" : 5, # m2SDP par m2 emprise au sol bureau
    "Rep" : 1, # m2 par m2 emprise au sol esapce public
    "Requip" : 3, # m2SDP par m2 emprise au sol équipement public
    "aire_projet" : 350000,
    "subvention": 16741000,
    "part_route" : 0.5 # part des voiries dans l'espace public
}


GAMMA = 1.05

EPS = 0.01                                    # same validity threshold as in your script
GRID_DIR = f"{PROCESSED_DATA_DIR}/Pb_amenageur/ponderees/"
COLS = ("K_A", "K_B", "K4_A", "K4_B", "neg_mass")


# ---------- 1. plane point -> programme --------------------------------------
def programme_from_xy(s_lc,s_bur,param_amenageur):
    s_ep = param_amenageur["Eep_lc"]*s_lc + param_amenageur["Eep_bur"]*s_bur
    s_route = param_amenageur["part_route"]*s_ep
    s_vege = s_ep-s_route
    return  {
        "individual_housing" : 0,
        "collective_housing" : s_lc,
        "office_building" : s_bur,
        "education_building" : param_amenageur["Eequip_bur"]*s_bur + param_amenageur["Eequip_lc"]*s_lc ,
        "roads" : s_route,
        "vegetation" : s_vege,
        }



REF_centrale_KEY=(100_000,500_000)
REF_lc_plus_KEY = (275_000,425_000)
REF_bur_plus_KEY = (40_000,1_000_000)

REF_centrale = programme_from_xy(REF_centrale_KEY[0],REF_centrale_KEY[1],param_amenageur)
REF_lc_plus = programme_from_xy(REF_lc_plus_KEY[0],REF_lc_plus_KEY[1],param_amenageur)
REF_bur_plus = programme_from_xy(REF_bur_plus_KEY[0],REF_bur_plus_KEY[1],param_amenageur)


REFS = {"centrale": REF_centrale, "lc_plus": REF_lc_plus, "bur_plus": REF_bur_plus}

def emprise_projet(Slc,Sbur,param_dict) :
    a = (1/param_dict["Rlc"])+(param_dict["Eep_lc"]/param_dict["Rep"])+(param_dict["Eequip_lc"]/param_dict["Requip"])
    b= (1/param_dict["Rbur"])+(param_dict["Eep_bur"]/param_dict["Rep"])+(param_dict["Eequip_bur"]/param_dict["Requip"])
    return a*Slc + b*Sbur

def cout_projet(Slc,Sbur,param_dict):
    a= (
        param_dict["Ksol"]*(
            (1/param_dict["Rlc"])
            +param_dict["Eep_lc"]/param_dict["Rep"]
            +(param_dict["Eequip_lc"]/param_dict["Requip"])
            ) 
            + param_dict["Eep_lc"]*param_dict["Cep"]
            +param_dict["Eequip_lc"]*param_dict["Cequip"]
            -param_dict["Klc"]
    )
    b= (
        param_dict["Ksol"]*(
            (1/param_dict["Rbur"])
            +param_dict["Eep_bur"]/param_dict["Rep"]
            +(param_dict["Eequip_bur"]/param_dict["Requip"])
            ) 
            + param_dict["Eep_bur"]*param_dict["Cep"]
            +param_dict["Eequip_bur"]*param_dict["Cequip"]
            -param_dict["Kbur"]
    )

    return a*Slc+b*Sbur


# ---------- 2. exact P(total > 0) --------------------------------------------
def p_positive(prep, prog, indicator):
    """Exact P(total > 0) averaged over iterations, where total is the demand
    `prog` (a dict of surfaces, possibly a difference of programmes) evaluated
    with building scores + open-space scores. Returns None if more than 2
    archetypes are involved."""
    groups, usage_ranges = prep
    f_tilde = f_tilde_from_var(prog, set(usage_ranges))
    if len(f_tilde) > 2:
        return None
    open_it = open_by_iter(df_open_scores, prog, indicator)
    items = list(f_tilde.items())
    its = sorted({it for it, _ in groups})
    its = [it for it in its if all((it, u) in groups for u in f_tilde)]
 
    p = np.empty(len(its))
    for n, it in enumerate(its):
        const = open_it.get(it, 0.0)
        if not items:
            p[n] = float(const > 0)
            continue
        u1, c1 = items[0]
        s1, w1 = groups[(it, u1)]
        a = c1 * s1
        if len(items) == 1:
            p[n] = w1[a + const > 0].sum()
            continue
        u2, c2 = items[1]
        s2, w2 = groups[(it, u2)]
        b = c2 * s2 + const
        order = np.argsort(b)
        cw = np.concatenate(([0.0], np.cumsum(w2[order])))
        idx = np.searchsorted(b[order], -a, side="right")   # strict ">"
        p[n] = (w1 * (1.0 - cw[idx])).sum()
    return p.mean()
 
 
# ---------- 3. indices at one point ------------------------------------------
def indices_point(x, y, param_amenageur, ref, prep, indicator, gamma=GAMMA, check_neg=True):
    """Returns (K_A, K_B, K4_A, K4_B, neg_mass) with A = ref, B = point (x, y)."""
    prog = programme_from_xy(x, y, param_amenageur)
 
    def diff(g, X, Y):                                       # X - g * Y
        return {k: X[k] - g * Y[k] for k in X}
 
    vals = [
        p_positive(prep, diff(1.0, prog, ref), indicator),    # K_A  = P(B > A)
        p_positive(prep, diff(1.0, ref, prog), indicator),    # K_B  = P(A > B)
        p_positive(prep, diff(gamma, prog, ref), indicator),  # K4_A = P(B > gamma A)
        p_positive(prep, diff(gamma, ref, prog), indicator),  # K4_B = P(A > gamma B)
    ]
    if any(v is None for v in vals):
        raise ValueError("more than 2 archetypes involved: p_positive does not apply")
    neg_pt = np.nan
    if check_neg:                                             # P(total of the point <= 0)
        neg_pt = 1.0 - p_positive(prep, prog, indicator)
    return (*vals, neg_pt)
 
 
def _row(x, ys, param_amenageur, ref, mask_row, prep, indicator, check_neg):
    out = np.full((len(ys), len(COLS)), np.nan)
    for j, y in enumerate(ys):
        if mask_row[j]:
            out[j] = indices_point(x, y, param_amenageur, ref, prep, indicator,
                                   check_neg=check_neg)
    return out
 

def region_mask(X, Y, p=param_amenageur):
    """Above the cost line, below the footprint line, in the positive quadrant."""
    return (
        (X >= 0) & (Y >= 0)
        & (cout_projet(X, Y, p) <= p["subvention"])
        & (emprise_projet(X, Y, p) <= p["aire_projet"])
    )


def feasible(X, Y):
    """Region + one cell of margin (8 neighbours), so that every interpolated
    point inside the region has all its surrounding grid points computed."""
    return binary_dilation(region_mask(X, Y), structure=np.ones((3, 3), bool))


def bounding_box(xmax=6e5, ymax=2e6, n=2000):
    """Extent of the region, to restrict the grid to where it matters."""
    x = np.linspace(0, xmax, n)
    y = np.linspace(0, ymax, n)
    m = region_mask(*np.meshgrid(x, y, indexing="ij"))
    xr, yr = x[m.any(axis=1)], y[m.any(axis=0)]
    return (xr[0], xr[-1]), (yr[0], yr[-1])
# ---------- 4. grid computation ----------------------------------------------
def compute_grid(prep, indicator, xs, ys, param_amenageur, ref,
                 feasible=None, check_neg=True, n_jobs=1):
    """Returns array (nx, ny, len(COLS)).
    feasible(X, Y) -> bool array lets you skip points you don't need."""
    if feasible is None:
        mask = np.ones((len(xs), len(ys)), bool)
    else:
        mask = feasible(*np.meshgrid(xs, ys, indexing="ij"))
    gen = Parallel(n_jobs=n_jobs, return_as="generator")(
        delayed(_row)(x, ys, param_amenageur, ref, mask[i], prep, indicator, check_neg)
        for i, x in enumerate(xs)
    )
    rows = list(tqdm(gen, total=len(xs), desc="Lignes", leave=False))
    return np.stack(rows)
 
 
def main(xs, ys, refs, param_amenageur, out_dir=GRID_DIR, feasible=None,
         n_jobs=4, check_neg=True):
    os.makedirs(out_dir, exist_ok=True)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
 
    for file in tqdm(sorted(os.listdir(Hbs_folder)), desc="Indicateurs"):
        full = os.path.join(Hbs_folder, file)
        if not os.path.isfile(full):
            continue
 
        Hb = build_Hb_filtered(full, dict_w)
        indicator = Hb["indicator"].unique()[0]
        prep = prepare(Hb)
        del Hb
        ind_name = "_".join(file.split("_")[1:-1])
 
        for ref_name, ref in refs.items():
            ref_neg = 1.0 - p_positive(prep, ref, indicator)   # P(ref total <= 0)
            out = compute_grid(prep, indicator, xs, ys, param_amenageur, ref,
                               feasible, check_neg, n_jobs)
            pl.DataFrame({
                "x": gx.ravel(), "y": gy.ravel(), "indicator": indicator,
                "ref_neg_mass": ref_neg,
                **{c: out[..., i].ravel() for i, c in enumerate(COLS)},
            }).write_parquet(f"{out_dir}/k4_grid_{ref_name}_{ind_name}.parquet")
 
 
# ---------- 5. loading, interpolation, classification -------------------------
def load_grid(parquet_file, eps=EPS):
    """Returns xs, ys and a dict of (nx, ny) arrays. K4 is set to NaN where the
    point's or the reference's P(total <= 0) exceeds eps; K is never masked."""
    df = pl.read_parquet(parquet_file).sort(["x", "y"])
    xs = df["x"].unique(maintain_order=True).to_numpy()
    ys = df["y"].unique(maintain_order=True).to_numpy()
    shape = (len(xs), len(ys))
    G = {c: df[c].to_numpy().reshape(shape) for c in COLS}
    bad = (G["neg_mass"] > eps) | (df["ref_neg_mass"].to_numpy().reshape(shape) > eps)
    for c in ("K4_A", "K4_B"):
        G[c] = np.where(bad, np.nan, G[c])
    return xs, ys, G
 
 
def interpolate(xs, ys, Z, xi, yi, method="linear"):
    """Interpolate a continuous field (K_A, K4_A, ...) on a fine grid.
    NaNs propagate, so invalid zones stay blank. Use 'cubic' only without NaN."""
    f = RegularGridInterpolator((xs, ys), Z, method=method,
                                bounds_error=False, fill_value=np.nan)
    Xi, Yi = np.meshgrid(xi, yi)               # shape (len(yi), len(xi)) for contourf
    Zi = f(np.column_stack([Xi.ravel(), Yi.ravel()])).reshape(Xi.shape)
    return Xi, Yi, np.clip(Zi, 0, 1)
 
 
def classify(k4a, k4b, seuil_sup=0.75, seuil_inf=0.3):
    """Vectorised version of xyz(simplified=True): +1 / 0 / -1 (NaN kept)."""
    z = np.zeros_like(k4a)
    z[(k4a >= seuil_sup) & (k4b < seuil_inf)] = 1
    z[(k4a < seuil_inf) & (k4b >= seuil_sup)] = -1
    z[np.isnan(k4a) | np.isnan(k4b)] = np.nan
    return z
 
 
if __name__ == "__main__":
    (x0, x1), (y0, y1) = bounding_box()
    nx, ny = 40, 40                    # was 21 x 21
    xs = np.linspace(x0, x1, nx)
    ys = np.linspace(y0, y1, ny)

    m = feasible(*np.meshgrid(xs, ys, indexing="ij"))
    print(f"{m.sum()} points to compute out of {m.size} ({m.mean():.0%})")

    main(xs, ys, REFS, param_amenageur, feasible=feasible, n_jobs=4)