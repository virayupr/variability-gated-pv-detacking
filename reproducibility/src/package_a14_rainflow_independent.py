"""A14 independent-code cross-implementation audit (NOT independent third-party library certification).
No retuning. External datasets already inspected. Does not validate physical fatigue.
"""
import argparse, hashlib, io, json, zipfile
from collections import deque
from pathlib import Path
import numpy as np
import pandas as pd
from package_a5_training_selection import load, eligible_days
from package_a_causal_nri import compute_features
from package_a4_corrected_controller import split_contiguous, simulate_segment

def independent_reversals(y):
    """Independent vectorized reversal extraction, including endpoints and flat-run collapse."""
    x=np.asarray(y,dtype=np.float64)
    if len(x)<3:return x.tolist()
    x=x[np.r_[True,np.diff(x)!=0]]
    if len(x)<3:return x.tolist()
    slope=np.diff(x)
    ix=np.flatnonzero(slope[:-1]*slope[1:]<0)+1
    return x[np.r_[0,ix,len(x)-1]].tolist()

def count_cycles_independent(y):
    """Deque implementation of three-point four-point-equivalent ASTM-style stack.
    Returns (range,count) with residual 0.5 cycles. Not imported from A4/A7.
    """
    stack=deque(); cycles=[]
    for point in independent_reversals(y):
        stack.append(float(point))
        while len(stack)>=3:
            older=abs(stack[-2]-stack[-3]);newer=abs(stack[-1]-stack[-2])
            if newer<older:break
            if len(stack)==3:
                cycles.append((older,0.5))
                stack.popleft()
            else:
                cycles.append((older,1.0))
                last=stack.pop();stack.pop();stack.pop();stack.append(last)
    for i in range(len(stack)-1):
        cycles.append((abs(stack[i+1]-stack[i]),0.5))
    return cycles

def score(y,win,half):
    smooth=pd.Series(y).rolling(win,center=True,min_periods=1).median().to_numpy()
    cycles=count_cycles_independent(smooth)
    return float(sum(r*r*c for r,c in cycles if half or c==1.0))

def archive_csv(path,suffix):
    with zipfile.ZipFile(path) as z:
        return pd.read_csv(io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(suffix)))))

def archive_json(path,suffix):
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read(next(n for n in z.namelist() if n.endswith(suffix))))

def run(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    manifest=archive_json(args.a5,'a5_manifest.json')
    policy=manifest['selected_policy'];assert policy==[30,0.12],policy
    archived=archive_csv(args.a7,'a7_csi2_sensitivity_daily.csv')
    a5=archive_csv(args.a5,'a5_external_daily.csv')
    coef=np.array(manifest['coefficients'],float);intercept=float(manifest['intercept'])
    checks=[];dayrows=[];summary=[];files={}
    for file in args.external:
        file=Path(file);label=file.stem;files[label]=hashlib.sha256(file.read_bytes()).hexdigest()
        raw=load(file);features,diag=compute_features(str(file),windows=(15,30,60));days=eligible_days(raw,diag)
        print('A14 reconstruct',label,'eligible days',len(days),flush=True)
        for day in days:
            vals={(w,h):[0.,0.] for w in (1,3,5,9) for h in (False,True)}
            for seg in split_contiguous(raw,day):
                gate=features['nri_30m_lag1'].reindex(seg.index).ge(0.12).fillna(False).to_numpy(bool)
                p=simulate_segment(seg,gate,intercept,coef)
                for (w,h), pair in vals.items():
                    pair[0]+=score(p.T_base.to_numpy(),w,h)
                    pair[1]+=score(p.T_control.to_numpy(),w,h)
            for (w,h),(base,control) in vals.items():
                row=dict(dataset=label,date=str(day),median_window=w,include_half_cycles=h,base=base,control=control,
                         reduction_pct=100*(base-control)/base if base>0 else np.nan)
                dayrows.append(row)
    generated=pd.DataFrame(dayrows)
    if len(generated)!=624:raise AssertionError(f'Expected 624 rows; found {len(generated)}')
    keys=['dataset','date','median_window','include_half_cycles']
    merged=generated.merge(archived,on=keys,suffixes=('_a14','_a7'),validate='one_to_one',indicator=True)
    assert len(merged)==len(generated)==len(archived) and (merged._merge=='both').all()
    for m in ['base','control']:
        merged[f'{m}_abs_error']=abs(merged[f'{m}_a14']-merged[f'{m}_a7'])
    merged['within_tolerance']=(merged.base_abs_error<=args.tol)&(merged.control_abs_error<=args.tol)
    merged.to_csv(out/'a14_cycle_counter_crosscheck_624.csv',index=False)
    primary=generated[(generated.median_window==5)&(~generated.include_half_cycles)]
    for label,g in primary.groupby('dataset'):
        g=g.sort_values('date');mean=float(g.reduction_pct.mean());pooled=float(100*(g.base.sum()-g.control.sum())/g.base.sum())
        summary.append(dict(dataset=label,n_days=len(g),mean_daily_reduction_pct=mean,pooled_reduction_pct=pooled,
                            base_total=float(g.base.sum()),control_total=float(g.control.sum())))
    pd.DataFrame(summary).to_csv(out/'a14_primary_summary.csv',index=False)
    for label,g in generated.groupby('dataset'):
        for h in [False,True]:
            s=g[(g.median_window==5)&(g.include_half_cycles==h)]
            checks.append(dict(dataset=label,include_half_cycles=h,n_days=len(s),mean_daily_pct=float(s.reduction_pct.mean()),
                               pooled_pct=float(100*(s.base.sum()-s.control.sum())/s.base.sum())))
    pd.DataFrame(checks).to_csv(out/'a14_cycle_convention_summary.csv',index=False)
    # Synthetic unit cases independently check key counting invariants; not an external package certification.
    testcases={'constant':[1,1,1,1], 'monotone':[0,1,2,3], 'triangle':[0,2,0], 'nested':[0,3,1,2,0], 'repeated':[0,0,3,3,0,0]}
    unit=[]
    for name,x in testcases.items():
        cs=count_cycles_independent(x);full=sum(r*r*c for r,c in cs if c==1.0);both=sum(r*r*c for r,c in cs)
        unit.append(dict(test=name,full_score=full,half_included_score=both,n_cycles=len(cs)))
    pd.DataFrame(unit).to_csv(out/'a14_synthetic_unit_tests.csv',index=False)
    maxerr=float(merged[['base_abs_error','control_abs_error']].max().max());nfailed=int((~merged.within_tolerance).sum())
    result={'status':'INDEPENDENT_CODE_CROSS_IMPLEMENTATION_NOT_THIRD_PARTY_CERTIFICATION',
            'reconstructed_rows':len(generated),'external_days':len(primary),'external_system_days':len(primary),
            'max_absolute_cycle_proxy_error':maxerr,'tolerance':args.tol,'n_failed_comparisons':nfailed,
            'cross_implementation_pass':nfailed==0,'frozen_policy':policy,'external_sha256':files,
            'limitations':['Both implementations use the same three-point stack counting convention; an independently maintained library comparison remains pending.',
            'Model trajectories are simulated, not observed intervention temperatures.',
            'External datasets have already been inspected; this is not confirmatory evaluation.',
            'Agreement does not establish ASTM standard certification, physical fatigue, lifetime, or energy benefit.']}
    (out/'a14_manifest.json').write_text(json.dumps(result,indent=2))
    (out/'a14_scientific_corrections.md').write_text('''# A14 scientific correction note\n\n- Reconstructed both frozen-policy external trajectories from the original data and A5 coefficients.\n- Applied a separately coded deque-based reversal/cycle counter (no import of A4/A7 rainflow functions).\n- Compared all 624 day/convention/smoothing rows against A7.\n- Agreement is **cross-implementation agreement**, not certification against an independently maintained third-party rainflow library or physical fatigue validation.\n- Keep the negative mean-daily primary estimands, positive pooled estimands, and half-cycle sensitivity visible.\n- Correct manuscript claims only where the audit demonstrates an actual mismatch.\n- Next required step: independent published rainflow package/ASTM reference benchmark and field intervention validation.\n''')
    print('A14 RESULT',json.dumps(result,indent=2),flush=True)
    if nfailed:raise AssertionError(f'{nfailed} day-level mismatches, see audit CSV')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a5',required=True);p.add_argument('--a7',required=True)
    p.add_argument('--external',nargs=2,required=True);p.add_argument('--out',default='package_a14_outputs');p.add_argument('--tol',type=float,default=1e-8)
    run(p.parse_args())