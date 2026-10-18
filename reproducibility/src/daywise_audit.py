from pathlib import Path
import pandas as pd
p=Path(__file__).resolve().parent
d=pd.read_csv(p/'matched_free_running_persistence_segments.csv')
d['system']=d.dataset.str.extract(r'(System_1|System_2A)')
# Equal segment weighting within each day; no claims of independent within-day segments.
g=d.groupby(['system','date','horizon'],as_index=False).agg(n_segments=('segment_start','size'),dynamic_mean_segment_RMSE_C=('model_RMSE_C','mean'),persistence_mean_segment_RMSE_C=('persistence_RMSE_C','mean'),dynamic_mean_segment_bias_C=('model_bias_C','mean'),persistence_mean_segment_bias_C=('persistence_bias_C','mean'))
g['dynamic_minus_persistence_RMSE_C']=g.dynamic_mean_segment_RMSE_C-g.persistence_mean_segment_RMSE_C
g.to_csv(p/'daywise_matched_comparison.csv',index=False)
s=g.groupby(['system','horizon'],as_index=False).agg(n_days=('date','nunique'),mean_day_dynamic_RMSE_C=('dynamic_mean_segment_RMSE_C','mean'),mean_day_persistence_RMSE_C=('persistence_mean_segment_RMSE_C','mean'),median_day_dynamic_RMSE_C=('dynamic_mean_segment_RMSE_C','median'),median_day_persistence_RMSE_C=('persistence_mean_segment_RMSE_C','median'),days_dynamic_better=('dynamic_minus_persistence_RMSE_C',lambda x:int((x<0).sum())),mean_day_dynamic_bias_C=('dynamic_mean_segment_bias_C','mean'),mean_day_persistence_bias_C=('persistence_mean_segment_bias_C','mean'))
s.to_csv(p/'daywise_summary.csv',index=False)
print(s.round(4).to_string(index=False))