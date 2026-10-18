"""Package A4 verification: independent rainflow comparison, synthetic controls, paired uncertainty.
Requires pip install rainflow and the original A4/A1 scripts for full verification.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from package_a4_corrected_controller import (extract_closed_cycle_ranges, severity,simulate_segment,split_contiguous)

def test_controller():
    ix=pd.date_range('2020-01-01 12:00',periods=20,freq='min')
    # 100 -> 1000 jump triggers detack; gate goes off before dwell expires.
    g=np.array([100.,1000.,1000.,1000.,1000.,1000.,1000.,1000.,1000.,1000.,100.,100.,100.,100.,100.,100.,100.,100.,100.,100.])
    seg=pd.DataFrame({'T_module_C':30.,'T_ambient_C':25.,'Gtotpoa_Wm2':g,'v_wind_ms':2.},index=ix)
    gate=np.zeros(20,bool);gate[1]=True
    p=simulate_segment(seg,gate,0.,np.array([.001,-.04,-.005]),ramp_limit=400,theta_max=45,dwell_minutes=5)
    a=p.angle.to_numpy()
    assert a[1]>0, 'Initial detack missing'
    assert np.allclose(a[2:6],a[1]), 'Dwell did not retain angle for five minutes'
    assert a[6]==0, 'Gate-off return not executed after dwell'
    changes=np.where(abs(np.diff(a))>1e-8)[0]+1
    assert all(np.diff(changes)>=5), 'Angle changes violate dwell'
    assert np.allclose(p.T_base,p.T_control) is False, 'Temperature trajectories unexpectedly identical'
    # No gap bridging: one missing timestamp produces two segments.
    broken=seg.drop(ix[10]);segs=split_contiguous(broken,ix[0].date())
    assert len(segs)==2 and [len(s) for s in segs]==[10,9], 'Gap segmentation failed'
    assert severity(np.zeros(50))==0, 'Constant temperature must have zero CSI2'
    return {'first_angle_deg':float(a[1]),'return_to_zero_minute':6,'angle_change_indices':changes.tolist(),'gap_segment_lengths':[len(s) for s in segs]}

def test_rainflow():
    import rainflow
    rng=np.random.default_rng(20261013)
    cases={'flat':np.zeros(100),'sine':np.sin(np.linspace(0,18*np.pi,1000)),
           'plateaus':np.array([0,0,4,4,1,1,5,5,0,0,3,3,0,0],float),
           'random_walk':np.cumsum(rng.normal(size=1500)),
           'alternating':np.tile([0,10,0,-10],80).astype(float)}
    rows=[]
    for name,values in cases.items():
        expected=sorted(float(r)**2 for r,mean,count,*_ in rainflow.extract_cycles(values) if np.isclose(count,1.0))
        actual=sorted(float(r)**2 for r in extract_closed_cycle_ranges(values))
        ok=len(expected)==len(actual) and np.allclose(expected,actual,atol=1e-10,rtol=1e-10)
        rows.append({'case':name,'reference_full_cycles':len(expected),'custom_full_cycles':len(actual),
                     'reference_CSI2':sum(expected),'custom_CSI2':sum(actual),'match':bool(ok)})
    return pd.DataFrame(rows)

def uncertainty(csv,out,bootstrap=20000):
    data=pd.read_csv(csv); d=data.loc[data.split.eq('test')]
    baseline=d.loc[d.policy.eq('always_available')].set_index('date')
    target=d.loc[d.policy.eq('causal_30m_illustrative_0p09')].set_index('date')
    common=sorted(set(baseline.index)&set(target.index))
    metrics={'CSI2_advantage_pp':('CSI2_reduction_pct',1),
             'irradiance_penalty_reduction_pp':('irradiance_penalty_pct',-1),
             'intervention_minutes_saved':('intervention_minutes',-1),
             'angle_changes_saved':('angle_changes',-1)}
    rng=np.random.default_rng(20261013)
    ix=rng.integers(0,len(common),size=(bootstrap,len(common)))
    rows=[];paired=[]
    for name,(field,sign) in metrics.items():
        diff=sign*(target.loc[common,field].to_numpy()-baseline.loc[common,field].to_numpy())
        boots=diff[ix].mean(axis=1)
        rows.append({'metric':name,'n_days':len(common),'mean':float(diff.mean()),'CI_low':float(np.quantile(boots,.025)),
                     'CI_high':float(np.quantile(boots,.975)),'days_better':int((diff>1e-9).sum()),
                     'days_worse':int((diff< -1e-9).sum()),'days_tied':int((abs(diff)<=1e-9).sum())})
        paired.extend({'date':day,'metric':name,'paired_advantage':float(value)} for day,value in zip(common,diff))
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'a4v_bootstrap.csv',index=False)
    pd.DataFrame(paired).to_csv(out/'a4v_paired_days.csv',index=False)
    return pd.DataFrame(rows)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--daily',default='a4_daily_policy_metrics.csv');ap.add_argument('--out',default='a4_verification_outputs');args=ap.parse_args()
    print('SYNTHETIC CONTROLLER:',test_controller())
    print('RAINFLOW COMPARISON:'); rf=test_rainflow();print(rf.to_string(index=False))
    Path(args.out).mkdir(exist_ok=True,parents=True);rf.to_csv(Path(args.out)/'a4v_rainflow_checks.csv',index=False)
    print('PAIRED UNCERTAINTY:');print(uncertainty(args.daily,args.out).to_string(index=False))
    if not rf['match'].all():print('BLOCKER: custom rainflow differs from reference; CSI2 must be recomputed.')
    else:print('Rainflow synthetic checks pass; still requires real trajectory crosscheck.')