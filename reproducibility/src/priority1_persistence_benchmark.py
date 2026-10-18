from pathlib import Path
import numpy as np,pandas as pd
from package_a5_training_selection import load,eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous
root=Path('/mnt/data'); archived=pd.read_csv(root/'package_a9_outputs/a9_free_running_segments.csv');rows=[]
for file in [root/'PV_temperature_model_data_2018_System_1_1min.dat',root/'PV_temperature_model_data_2018_System_2A_1min.dat']:
 raw=load(file); _,diag=compute_features(str(file)); days=eligible_days(raw,diag)
 for day in days:
  for seg in split_contiguous(raw,day):
   obs=seg.T_module_C.to_numpy(float); start=str(seg.index[0]); label=file.stem
   for horizon in (30,60,120,'full_segment'):
    n=min(len(obs),horizon+1) if isinstance(horizon,int) else len(obs)
    if n<2:continue
    key=archived[(archived.dataset==label)&(archived.date==str(day))&(archived.segment_start==start)&(archived.horizon==str(horizon))]
    assert len(key)==1,(label,day,start,horizon)
    e=obs[0]-obs[:n]
    rows.append({'dataset':label,'date':str(day),'segment_start':start,'horizon':str(horizon),'n_points':n,'model_RMSE_C':float(key.RMSE_C.iloc[0]),'persistence_RMSE_C':float(np.sqrt(np.mean(e*e))),'model_bias_C':float(key.bias_C.iloc[0]),'persistence_bias_C':float(np.mean(e)),'model_MAE_C':float(key.MAE_C.iloc[0]),'persistence_MAE_C':float(np.mean(abs(e)))})
out=root/'priority1_thermal_benchmark';out.mkdir(exist_ok=True); d=pd.DataFrame(rows);assert len(d)==len(archived)
d.to_csv(out/'matched_free_running_persistence_segments.csv',index=False)
s=d.groupby(['dataset','horizon'],as_index=False).agg(evaluations=('model_RMSE_C','size'),model_mean_RMSE_C=('model_RMSE_C','mean'),persistence_mean_RMSE_C=('persistence_RMSE_C','mean'),model_mean_bias_C=('model_bias_C','mean'),persistence_mean_bias_C=('persistence_bias_C','mean'))
s['model_RMSE_improvement_pct']=100*(s.persistence_mean_RMSE_C-s.model_mean_RMSE_C)/s.persistence_mean_RMSE_C
s.to_csv(out/'matched_free_running_persistence_summary.csv',index=False)
print(s.round(4).to_string(index=False))