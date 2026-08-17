# Analyze one (original, embedded) OM pair for the local real-OM non-destructive check ([OM-DoD-001]).
# Structure via pikepdf (pages / bookmark nodes / link annotations); visual via PyMuPDF render +
# a numpy SSIM (global, per page → min) plus the max per-page pixel diff (0 = bit-identical render).
# LOCAL ONLY: runs against the confidential OMs/ corpus, never committed data. Emits one JSON line.
import json
import sys

import numpy as np
import pikepdf
import pymupdf


def structure(path: str):
    pdf = pikepdf.open(path)
    links = sum(
        1
        for pg in pdf.pages
        for a in (pg.get("/Annots", []) or [])
        if str(a.get("/Subtype", "")) == "/Link"
    )

    def count(node) -> int:
        n, cur = 0, (node.get("/First") if node is not None else None)
        while cur is not None:
            n += 1
            if "/First" in cur:
                n += count(cur)
            cur = cur.get("/Next")
        return n

    outlines = count(pdf.Root.Outlines) if "/Outlines" in pdf.Root else 0
    return len(pdf.pages), outlines, links


def render_gray(path: str, dpi: int = 100):
    doc = pymupdf.open(path)
    out = []
    for pg in doc:
        pix = pg.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        out.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width))
    return out


def ssim_global(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mua, mub = a.mean(), b.mean()
    cov = ((a - mua) * (b - mub)).mean()
    return float(
        ((2 * mua * mub + c1) * (2 * cov + c2))
        / ((mua**2 + mub**2 + c1) * (a.var() + b.var() + c2))
    )


def main() -> None:
    orig, emb = sys.argv[1], sys.argv[2]
    so, se = structure(orig), structure(emb)
    ro, re = render_gray(orig), render_gray(emb)
    min_ssim, max_diff = 1.0, 0
    for i in range(min(len(ro), len(re))):
        if ro[i].shape == re[i].shape:
            min_ssim = min(min_ssim, ssim_global(ro[i], re[i]))
            max_diff = max(max_diff, int(np.abs(ro[i].astype(int) - re[i].astype(int)).max()))
        else:
            min_ssim, max_diff = 0.0, 255
    print(
        json.dumps(
            {
                "pages": [so[0], se[0]],
                "bookmarks": [so[1], se[1]],
                "links": [so[2], se[2]],
                "min_ssim": round(min_ssim, 6),
                "max_pixel_diff": max_diff,
            }
        )
    )


if __name__ == "__main__":
    main()
