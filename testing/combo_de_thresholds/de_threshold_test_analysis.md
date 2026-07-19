## 1> D , E threshold test

- E
    
    ## **Combo E — threshold cases & hit rates**
    
    Primary horizon: **12M** (252 trading days). Also **6M / 9M**.
    
    ### **1. CONFIG (current production)**
    
    CAPE  ≥ 28
    
    NFCI  ≤ −0.30
    
    CFTC  ≥ 80th percentile
    
    Rule: 2-of-3
    
    | **Episodes** | **6M bear** | **9M bear** | **12M bear** | **Avg SPX 12M** |
    | --- | --- | --- | --- | --- |
    | **22** | 9.1% | 18.2% | **9.1%** | **+15.96%** |
    
    → Structurally **bullish** under current gates (SPX up ~16% avg 12M post-trigger).
    
    ---
    
    ### **2. BEST IN TARGET N (n ≈ 20–50)**
    
    CAPE  ≥ 30
    
    NFCI  ≤ −0.20
    
    CFTC  ≥ 92
    
    Rule: 3-of-3
    
    | **Episodes** | **6M bear** | **9M bear** | **12M bear** | **Avg SPX 12M** |
    | --- | --- | --- | --- | --- |
    | **16** | 40.0% | 60.0% | **46.7%** | +0.41% |
    
    ---
    
    ### **3. BEST ANY N (max 12M hit, tiny n)**
    
    CAPE  ≥ 32
    
    NFCI  ≤ −0.20
    
    CFTC  ≥ 95
    
    Rule: 3-of-3
    
    | **Episodes** | **6M bear** | **9M bear** | **12M bear** | **Avg SPX 12M** |
    | --- | --- | --- | --- | --- |
    | **4** | 50.0% | 75.0% | **100%** | −5.96% |
    
    → Strong bear signal but **n=4 only** — not robust.
    
    ---
    
    ### **4. BEST PRODUCTION SCORE (n ≥ 10)**
    
    CAPE  ≥ 32
    
    NFCI  ≤ −0.15
    
    CFTC  ≥ 85
    
    Rule: 3-of-3
    
    | **Episodes** | **6M bear** | **9M bear** | **12M bear** | **Avg SPX 12M** |
    | --- | --- | --- | --- | --- |
    | **10** | 66.7% | 66.7% | **66.7%** | −6.54% |
- D
    
    ## **Combo D — threshold cases & hit rates**
    
    Primary horizon: **1W** (5 trading days). Also **2W / 3W / 4W**.
    
    ### **1. CONFIG (current production)**
    
    VXTS  ≥ 1.10
    
    CFTC  ≥ 85th percentile
    
    VIX   ≤ 18
    
    Rule: 3-of-3 (all legs required)
    
    | **Episodes** | **1W bear** | **2W bear** | **3W bear** | **4W bear** | **Avg SPX 1W** |
    | --- | --- | --- | --- | --- | --- |
    | **31** | **41.9%** | 35.5% | 38.7% | 25.8% | +0.22% |
    
    ---
    
    ### **2. BEST IN TARGET N (n ≈ 20–50)**
    
    VXTS  ≥ 1.25
    
    CFTC  ≥ 95
    
    VIX   ≤ 16
    
    Rule: 2-of-3
    
    | **Episodes** | **1W bear** | **2W bear** | **3W bear** | **4W bear** | **Avg SPX 1W** |
    | --- | --- | --- | --- | --- | --- |
    | **42** | **54.8%** | 38.1% | 31.0% | 38.1% | −0.11% |
    
    ---
    
    ### **3. BEST ANY N (max 1W hit rate, n larger)**
    
    VXTS  ≥ 1.18
    
    CFTC  ≥ 90
    
    VIX   ≤ 16
    
    Rule: 2-of-3
    
    | **Episodes** | **1W bear** | **2W bear** | **3W bear** | **4W bear** | **Avg SPX 1W** |
    | --- | --- | --- | --- | --- | --- |
    | **78** | **57.1%** | 39.0% | 44.2% | 44.7% | −0.36% |
    
    ---
    
    ### **4. BEST PRODUCTION SCORE (hit rate + negative avg SPX + n ≈ 30)**
    
    VXTS  ≥ 1.18
    
    CFTC  ≥ 95
    
    VIX   ≤ 13
    
    Rule: 2-of-3
    
    | **Episodes** | **1W bear** | **2W bear** | **3W bear** | **4W bear** | **Avg SPX 1W** |
    | --- | --- | --- | --- | --- | --- |
    | **46** | **56.5%** | 43.5% | 43.5% | 41.3% | −0.35% |