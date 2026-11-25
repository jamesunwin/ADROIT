# The SHM++ authors' reference tables (validation only)

`gvmin_SHMpp.dat` (v_min in km/s, g(v_min) in s/km) and `hvmin_SHMpp.dat` (v_min, h(v_min) in km/s) from the authors' public
code, github.com/mccabech/SHMpp (master, fetched 2026-11-10; the archive's sha256 `0c03b807…6c9ff8`), under the MIT
licence in `LICENSE`. They are a Monte Carlo of 10⁶ samples (the authors' `SHMpp_gvmin.py` and `SHMpp_hvmin.py`) at
v₀ = 233, v_esc = 528 km/s, β = 0.9, η = 0.2, the Sun's peculiar velocity (11.1, 12.24, 7.25) km/s and the instant
7364.3 days after J2000.0. ADROIT neither copies nor runs the authors' code; the tables are an independent reference for
`tests/halo_models/test_shm_plus_plus.py`.

| file | sha256 |
|---|---|
| gvmin_SHMpp.dat | d636939ccf0c12ffda0f3d64ae06cef850db70ec744f66a44491814b739f39f8 |
| hvmin_SHMpp.dat | e8b6e5f02dc4fb77b6408811b9a7a386bf85bea264528410e749a44a1fda2c75 |
