# FM<5 SQUEEZE cells — out-of-sample checks

The re-run left FM<5 / RM>40, >45 and >50 above par at 100% excess-hit on four or five
episodes. Small n alone is not a reason to dismiss them — the 4 Aug spec explicitly asked for
high hit rates on few episodes over market-average results on many. These are the tests that
decide it.

## 1. Placebo — how often does a random set of the same size beat the market every time?

| episodes | draws | P(all beat market) by chance | odds |
|---------:|------:|-----------------------------:|------|
| 4 | 378 | 10.8% | 1 in 9 |
| 5 | 373 | 5.1% | 1 in 20 |

The bootstrap cannot answer this. It resamples the cell's own episodes, so it measures
sampling variability around a result it already assumes is real. This asks the different and
more important question: given 66 grid cells were searched, how surprising is the best one?

## 2. Percentile-window sensitivity

| window | first rank | RM>40 | RM>45 | RM>50 |
|-------|-----------|-------|-------|-------|
| 104w | 2008-06-03 | n=11 ex=0.0276% hit=70.0% | n=11 ex=-0.4464% hit=60.0% | n=10 ex=-0.2192% hit=66.67% |
| 156w | 2009-06-02 | n=5 ex=1.9096% hit=100.0% | n=5 ex=2.2544% hit=100.0% | n=4 ex=2.9453% hit=100.0% |
| 208w | 2010-06-01 | n=6 ex=4.3892% hit=100.0% | n=3 ex=1.2388% hit=100.0% | n=3 ex=1.1478% hit=100.0% |
| 260w | 2011-05-31 | n=3 ex=5.464% hit=100.0% | n=3 ex=5.464% hit=100.0% | n=2 ex=2.114% hit=100.0% |

## 3. Walk-forward halves

Split at **2018-01-09**.

| cell | first half | second half |
|------|-----------|-------------|
| FM<5 RM>40 | no fire | n=5 ex=1.9096% hit=100.0% |
| FM<5 RM>45 | no fire | n=5 ex=2.2544% hit=100.0% |
| FM<5 RM>50 | no fire | n=4 ex=2.9453% hit=100.0% |

## 4. Neighbour stability (RM>45 held fixed)

| FM cut | result |
|--------|--------|
| FM<2.5 | n=5 ex=1.3127% hit=66.67% |
| FM<5 | n=5 ex=2.2544% hit=100.0% |
| FM<6 | n=7 ex=2.1389% hit=85.71% |
| FM<7.5 | n=7 ex=-0.5709% hit=71.43% |
| FM<10 | n=9 ex=0.0787% hit=66.67% |
