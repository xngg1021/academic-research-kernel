# Multi-Domain Scientific Computation Routing & Recipes

## 1. Task-to-Library Routing Table

| Mathematical / Domain Task | Primary Python Library | Key Entry Points & Notes |
| --- | --- | --- |
| Symbolic algebra, limits, exact integrals, Jacobians, LaTeX export | `sympy` | `symbols(..., real=True)`, `solve`, `integrate`, `simplify`, `Matrix.eigenvals`, `latex()` |
| Dense linear algebra, quadrature, root-finding, MILP/LP, ODE IVP/BVP, FFT | `numpy` + `scipy` | `linalg.solve` (prefer over `inv`), `integrate.quad`, `optimize.milp`, `integrate.solve_ivp(..., method='Radau')` for stiff ODEs |
| Arbitrary-precision arithmetic (catastrophic cancellation, extreme tails) | `mpmath` | `mp.dps = 50` (set precision *before* constructing `mpf` constants from strings: `mpf('0.1')`) |
| OLS/WLS/GLM, robust sandwich SEs (`HC3`), power, stationarity (`ADF`) | `statsmodels` + `scipy.stats` | `sm.OLS(y, sm.add_constant(X)).fit(cov_type='HC3')`, `adfuller`, `TTestIndPower` |
| Financial econometrics: GARCH volatility, VaR, Expected Shortfall (`CVaR`), Sharpe | `arch` + `scipy.stats` | `arch_model(returns, vol='Garch', p=1, q=1)` (rescale returns $\times 100$ for optimizer stability); historical & Student-$t$ parametric VaR/ES |
| Survival & time-to-event analysis: Kaplan-Meier, log-rank, Cox PH | `lifelines` | `KaplanMeierFitter`, `logrank_test`, `CoxPHFitter().fit(df, duration_col, event_col)` + `check_assumptions` (Schoenfeld residuals) |
| Psychometrics & inter-rater reliability: Cronbach's $\alpha$, ICC, Cohen/Fleiss $\kappa$ | `pingouin` / `statsmodels` | `pg.cronbach_alpha(data=items_df)` ($\alpha = \frac{k}{k-1}(1 - \frac{\sum \sigma_i^2}{\sigma_{\text{total}}^2})$), `pg.intraclass_corr`, `cohens_kappa` |
| Graph shortest paths, centrality, max-flow, DAG topological checks | `networkx` | `nx.DiGraph`, `nx.is_directed_acyclic_graph`, `nx.shortest_path`, `nx.maximum_flow` |
| Autograd, GPU tensor contractions, custom differentiable objectives | `torch` | `torch.DoubleTensor` (`float64`) when verifying analytical gradients via `torch.autograd.gradcheck` |

## 2. Numerical Conditioning & Reproducibility Rules

1. **Check condition numbers**: inspect `np.linalg.cond(A)` before solving $Ax = b$; switch to `scipy.linalg.lstsq` or QR/SVD when $\kappa(A) > 10^{10}$.
2. **Supported `compute-probe --receipt` operations**: `matmul_f64`, `matmul_f32`, `dot`, `svd`, `svd_f64`, and `fft_1d` across `small` / `medium` / `large` scales; unimplemented operation names raise `ValueError` rather than substituting another kernel.
3. **Cross-check symbolic vs numeric**: validate closed-form symbolic derivatives, survival hazards, or psychometric formulas at random interior test points using `mpmath` or `scipy` quadrature/finite differences.
