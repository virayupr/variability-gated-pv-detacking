"""Package A1: causal NRI feature audit, not controller performance validation.
Run: python package_a_causal_nri.py --data PV_temperature_model_data_2019_System_2B_1min.dat
No threshold is trained here. A 0.09 threshold is used only as a non-transferable illustration.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def compute_features(path, windows=(15,30,60), threshold=0.09):
    df=pd.read_csv(path,sep=';',comment='#',parse_dates=['Timestamp_UTC'])
    df=df.sort_values('Timestamp_UTC').drop_duplicates('Timestamp_UTC').set_index('Timestamp_UTC')
    g=pd.to_numeric(df['Gtotpoa_Wm2'],errors='coerce')
    g=g.where(g.between(0,1400))
    # full minute grid: missing samples never bridged for ramp computation
    g=g.asfreq('min')
    date=g.index.date
    daylight=g.gt(50)
    adjacent=(g.notna() & g.shift(1).notna() & (pd.Series(date,index=g.index)==pd.Series(date,index=g.index).shift(1)))
    ramp=g.diff().abs().where(adjacent & daylight & daylight.shift(1).fillna(False))
    out=pd.DataFrame({'irradiance':g,'daylight':daylight,'valid_ramp':ramp.notna()},index=g.index)
    for w in windows:
        # Features computed through t-1, so action at t cannot use irradiance sampled at t.
        # Use min_periods=w for uninterrupted daylight observations.
        gg=g.where(daylight)
        valid=(ramp.notna()).astype(int)
        numer=ramp.fillna(0).rolling(w,min_periods=w).sum()
        denom=gg.fillna(0).rolling(w,min_periods=w).sum()
        complete=valid.rolling(w,min_periods=w).sum().eq(w)
        feature=(numer/denom).where(complete & denom.gt(0)).shift(1)
        out[f'nri_{w}m_lag1']=feature
        out[f'gate_illustrative_{w}m']=feature.ge(threshold).where(feature.notna())
    # Diagnostic full-day retrospective index (not a causal feature)
    rows=[]
    for d,part in out.groupby(out.index.date):
        gd=part['irradiance'].where(part['daylight']).dropna()
        if len(gd)<300: continue
        r=part['valid_ramp']
        # Day-level retrospective calculation deliberately matches original notebook's
        # dropna/diff convention; discontinuities are NOT corrected in this reference.
        full_nri=gd.diff().abs().sum()/gd.sum()
        row={'date':str(d),'valid_daylight_minutes':len(gd),'retrospective_daily_nri':full_nri,
             'retrospective_gate_at_0p09':bool(full_nri>=threshold)}
        for w in windows:
            f=part[f'nri_{w}m_lag1']
            row[f'{w}m_feature_minutes']=int(f.notna().sum())
            row[f'{w}m_gate_enabled_minutes_at_0p09']=int((f>=threshold).sum())
        rows.append(row)
    return out,pd.DataFrame(rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--output',default='package_a_outputs');a=p.parse_args()
    out,summary=compute_features(a.data)
    target=Path(a.output);target.mkdir(parents=True,exist_ok=True)
    summary.to_csv(target/'causal_nri_daily_diagnostics.csv',index=False)
    out[['irradiance','nri_15m_lag1','nri_30m_lag1','nri_60m_lag1']].to_csv(target/'causal_nri_minute_features.csv')
    print('Daily diagnostics:',len(summary),'days')
    print(summary[['valid_daylight_minutes','retrospective_gate_at_0p09','15m_feature_minutes','30m_feature_minutes','60m_feature_minutes']].sum(numeric_only=True).to_string())
    print('WARNING: No thermal/controller outcomes have been calculated. 0.09 is illustrative only.')