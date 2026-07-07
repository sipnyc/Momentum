# Review: `claude/loop2-performance-analyzer-r505nm`

Branch under review: `origin/claude/loop2-performance-analyzer-r505nm`
(`loop1_replay.py` + `loop2_analyzer.py`, no PR opened).

Note: trunk (`claude/data-ingestion-parser-replay-lwd72w`) already has an
independent Loop 2 implementation merged (commit `176bd06`, linear
interpolation over a 9x13 breakpoint table). This branch is a separate,
unmerged implementation of the same component using SciPy bicubic splines
over an 11x4 grid. This review evaluates it on its own merits.

## Critical: cubic-spline overshoot produces physically impossible target speeds

`SecondStormMatrix` fits a bicubic tensor-product spline
(`RectBivariateSpline(..., kx=3, ky=3)`, default `s=0` exact interpolation)
through only **4 points** on the TWS axis (12/14/16/20 kt). Two of the eleven
TWA rows are non-monotonic across those 4 points:

```
150°: [7.04, 6.38, 8.11, 8.67]   # dips at 14kt
165°: [6.37, 5.67, 7.26, 8.13]   # dips at 14kt
```

A degree-3 interpolant forced through a dip-then-rise shape with so few
points overshoots well beyond the input data whenever you query a
non-grid point nearby. Verified by scanning `evaluate_performance` over a
fine TWA/TWS grid:

```
grid min/max target speed across all 44 input points: 5.33 / 9.29 kt
worst overshoot found:  TWA=150°, TWS=18.4kt -> target = 9.80 kt
```

9.80 kt is faster than *any* value in the actual polar table, including the
fastest reaching angles (110-135°) at the top wind speed (20kt, max 9.29kt).
Physically, a boat cannot sail faster running dead downwind (150-165°) than
it does on a reach — this is a data-fidelity bug, not a quirk of the input.

**Downstream impact:** `loop3_router.py` (already in trunk) flags
`🚨 SPEED LOSS` whenever `polar_eff < 92%`, where
`polar_eff = stw / target_btv * 100`. An inflated target from this overshoot
directly lowers the computed efficiency, so a boat sailing perfectly well at
TWA≈150-165°, TWS≈17-19kt would get a false "check trim/sail selection"
alert. This band (dead-run angles, mid-teens-to-20kt breeze) is a completely
ordinary distance-race condition, not an edge case.

**Suggested fix:** drop to a monotone/linear interpolation (as trunk's
merged implementation already does, or `kx=1, ky=1` on the existing grid),
or add enough TWS breakpoints that a cubic fit stays well-conditioned. Given
trunk already ships a working linear-interpolation version of this exact
component, replacing this bicubic-spline approach is probably lower effort
than fixing it in place.

## Minor

- `loop2_analyzer.py:1` — `import pandas as pd` is unused (`pd` never
  referenced in the file).
- Neither `scipy` nor `pandas` is declared anywhere in the repo (no
  `requirements.txt`/`pyproject.toml`), so the module doesn't run out of the
  box (`ModuleNotFoundError: scipy`) for anyone who doesn't already have it
  installed — confirmed by running against a clean interpreter.
- No test coverage; `__main__` only exercises exact grid points (12/14/16/20
  x the row values), which never surfaces the overshoot above since it never
  queries an interpolated point.

## Verdict

Do not merge as-is. The core numerical approach (unconstrained bicubic
spline on a 4-point axis with non-monotonic rows) produces target speeds
that exceed the input data's own range and would cause false tactical
alerts in `loop3_router.py`. Trunk's existing linear-interpolation Loop 2
implementation does not have this problem and is already in place.

## Addendum: `SecondStormCompleteMatrix` (heel/reef/flat upgrade)

`loop2_analyzer.py` was subsequently upgraded to `SecondStormCompleteMatrix`,
adding three more `RectBivariateSpline(kx=3, ky=3)` fits (heel, reef,
flattening) on the same sparse 11x4 axis. Re-ran the same overshoot scan
against all four splines:

```
heel: data range [1.0, 27.2]   overshoot -> 27.401   undershoot -> 0.647
reef: data range [0.85, 1.0]   overshoot -> 1.028     undershoot -> 0.739
flat: data range [0.61, 1.0]   overshoot -> 1.008     undershoot -> 0.610
btv:  data range [5.33, 9.29]  overshoot -> 9.805     undershoot -> 5.330
```

`reef` is the clearest case: it's a sail-area fraction bounded at 1.0 (full
main), and the spline reports 1.028 at TWA≈74.5°, TWS≈12.9kt — a
physically meaningless "more than full sail" target — plus an undershoot to
0.739 at TWA≈73.5°, TWS≈18.3kt, well below the row's actual minimum of
0.85, i.e. a spurious over-reef recommendation with no basis in the source
data. `heel` and `flat` show the same class of artifact. This confirms the
BTV finding above generalizes to all four target-state dimensions and gets
worse for grids with a real physical bound (reef, flat ∈ [0, 1]).

Implemented as requested with a compatibility `evaluate_performance()` shim
so `loop3_router.py` keeps working (updated its import/instantiation from
`SecondStormMatrix` to `SecondStormCompleteMatrix`), but the interpolation
method itself still needs the same fix recommended above before the heel/
reef/flat outputs can be trusted operationally.
