# Statistical Recomputation Formulas and Mismatch Rules

Reference formulas and tolerance rules implemented in `academic_research_kernel.recompute`.

## 1. Core Recomputation Formulas

1. **Two-sample pooled effect sizes**:
   - $s_p = \sqrt{\frac{(n_1 - 1)s_1^2 + (n_2 - 1)s_2^2}{n_1 + n_2 - 2}}$, $d = \frac{m_1 - m_2}{s_p}$.
   - Small-sample correction ($df = n_1 + n_2 - 2$): $J = 1 - \frac{3}{4\,df - 1}$, Hedges' $g = J \cdot d$.
   - Verify whether source reports SD or SE ($\text{SD} = \text{SE}\sqrt{n}$) before flagging a discrepancy.
2. **Test statistics to $p$-values**:
   - Two-sided $t$: $p = 2\,\text{sf}_t(|t|, df)$.
   - Right-tail $F$ and $\chi^2$: $p = \text{sf}_F(F, df_1, df_2)$ and $p = \text{sf}_{\chi^2}(\chi^2, df)$. Note $F(1, df) = t_{df}^2$.
   - Wald $z$: $z = \beta / \text{SE}$, $p = 2(1 - \Phi(|z|))$.
3. **Confidence interval symmetry**:
   - Additive scale (mean difference, $\beta$): midpoint $(L + U)/2$, $\text{SE} = (U - L)/(2 z_{1-\alpha/2})$.
   - Multiplicative ratio scale (`OR`, `RR`, `HR`, `ci_log_scale=True`): geometric midpoint $\sqrt{L \cdot U}$, $\text{SE}(\ln \theta) = \ln(U/L)/(2 z_{1-\alpha/2})$.
4. **`2x2` contingency tables (`a, b, c, d`)**:
   - $\text{OR} = (a d)/(b c)$, $\text{SE}(\ln \text{OR}) = \sqrt{1/a + 1/b + 1/c + 1/d}$ (Haldane-Anscombe $+0.5$ when any cell is zero).
   - $\text{RR} = \frac{a/(a+b)}{c/(c+d)}$ (valid for cohort/trial designs, not case-control).

## 2. Eight Mismatch Categories

Report findings strictly as **inconsistent** (exceeds rounding tolerance) or **impossible** (violates mathematical bounds), never as intent accusations:

1. **`p`-value mismatch (`p_from_t` / `p_from_f` / `p_from_chi2`)**: Checked against half-open round-half-up interval $[p - 0.5 \times 10^{-k}, p + 0.5 \times 10^{-k})$ from `p_value_literal`. Check one-sided vs two-sided conventions first.
2. **CI midpoint mismatch (`check_ci_consistency`)**: Point estimate deviates from arithmetic or geometric midpoint beyond tolerance (check bootstrap/profile-likelihood asymmetry before flagging).
3. **Percentage denominator mismatch (`academic_check_percentage`)**: Verifies $100 \cdot \text{count} / N$ within reported decimal rounding bounds, or infers nearest integer $N$.
4. **Effect-size mismatch (`cohens_d`)**: Compare against Cohen's $d$, Hedges' $g$, and Glass's $\Delta$ (control-group SD).
5. **Cross-section / table-text discrepancy**: Same metric reported with conflicting values across abstract, body, and tables.
6. **Impossible bounded SD (`check_sd_possible`)**: For variable bounded in $[a, b]$, population SD cannot exceed $(b-a)/2$ and sample SD cannot exceed $\frac{b-a}{2}\sqrt{\frac{n}{n-1}}$. Often caused by reporting SE as SD or variance as SD.
7. **Degrees-of-freedom sample size mismatch (`check_sample_size_from_df`)**: Pooled two-sample $t$ requires $N = df + 2$; paired/one-sample requires $N = df + 1$; regression requires $N = df_{\text{resid}} + p$.
8. **Table forensics (`academic_table_forensics`)**:
   - Partition conservation (`sum(parts) == total` and share sum $\approx 100\%$).
   - Constant-offset ablation regularity (detecting synthetic uniform column deltas across $\ge 3$ rows).
   - Physical storage/bandwidth lower bounds (claimed throughput vs uncompressed tensor bytes / hardware bandwidth).
