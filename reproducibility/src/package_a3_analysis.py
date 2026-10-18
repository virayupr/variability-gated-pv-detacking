from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('/mnt/data'); OUT=ROOT/'package_a3_outputs'; OUT.mkdir(exist_ok=True)
df=pd.read_csv(ROOT/'a2_daily_policy_metrics.csv')
assert len(df)==126 and df.groupby(['date','policy']).size().eq(1).all()
base=df.loc[df.policy=='always_available'].set_index(['split','date'])
rows=[];loo=[];paired=[]
rng=np.random.default_rng(20261013)
for split in ['train','test']:
 for policy in ['causal_15m_illustrative_0p09','causal_30m_illustrative_0p09','causal_60m_illustrative_0p09','retrospective_noncausal']:
  a=df[(df.split==split)&(df.policy==policy)].set_index(['split','date']).sort_index()
  b=base.loc[a.index]
  for metric in ['CSI2_reduction_pct','irradiance_penalty_pct','intervention_minutes','angle_changes']:
   delta=(a[metric]-b[metric]).to_numpy(dtype=float)
   valid=np.isfinite(delta);delta=delta[valid];n=len(delta)
   boot=rng.choice(delta,size=(20000,n),replace=True).mean(axis=1)
   lo,hi=np.percentile(boot,[2.5,97.5])
   rows.append(dict(split=split,policy=policy,metric=metric,n=n,mean_difference=float(delta.mean()),median_difference=float(np.median(delta)),ci95_boot_low=float(lo),ci95_boot_high=float(hi),positive_days=int((delta>1e-9).sum()),negative_days=int((delta< -1e-9).sum()),tied_days=int((abs(delta)<=1e-9).sum()),bootstrap_method='paired days, percentile, 20000 resamples; exploratory'))
   if metric=='CSI2_reduction_pct':
    for ix,idx in enumerate(a.index):
     paired.append(dict(split=split,date=idx[1],policy=policy,delta_CSI2_reduction_pp=float((a[metric]-b[metric]).iloc[ix])))
    for ix,idx in enumerate(a.index):
     loo.append(dict(split=split,policy=policy,omitted_date=idx[1],mean_delta_CSI2_pp_without_day=float(np.delete(delta,ix).mean())))
pd.DataFrame(rows).to_csv(OUT/'a3_paired_bootstrap.csv',index=False)
pd.DataFrame(paired).to_csv(OUT/'a3_daily_paired_csi2.csv',index=False)
pd.DataFrame(loo).to_csv(OUT/'a3_leave_one_day_out.csv',index=False)
print(pd.DataFrame(rows).query("split=='test' and metric=='CSI2_reduction_pct'").to_string(index=False))
print('\n30m LODO test:')
print(pd.DataFrame(loo).query("split=='test' and policy=='causal_30m_illustrative_0p09'").to_string(index=False))