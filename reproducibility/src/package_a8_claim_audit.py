"""A8 read-only consolidation of A5/A6/A7 frozen-policy evidence. No tuning."""
import argparse, io, json, zipfile, hashlib
from pathlib import Path
import pandas as pd
import numpy as np

def read_zip(z, suffix, kind='csv'):
    names=[n for n in z.namelist() if n.endswith(suffix)]
    if len(names)!=1: raise ValueError(f'Expected one {suffix}, got {names}')
    return json.loads(z.read(names[0])) if kind=='json' else pd.read_csv(io.BytesIO(z.read(names[0])))

def run(a):
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    sources={}
    for label,path in [('A5',a.a5zip),('A6',a.a6zip),('A7',a.a7zip)]:
        b=Path(path).read_bytes();sources[label]={'file':Path(path).name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    with zipfile.ZipFile(a.a5zip) as z:
        m5=read_zip(z,'a5_manifest.json','json');train=read_zip(z,'a5_training_candidate_grid.csv');external=read_zip(z,'a5_external_daily.csv'); ext_summary=read_zip(z,'a5_external_summary.csv')
    with zipfile.ZipFile(a.a6zip) as z:
        print('A6 archive members:',len(z.namelist()))
        m6=read_zip(z,'a6_manifest.json','json')
    with zipfile.ZipFile(a.a7zip) as z:
        m7=read_zip(z,'a7_manifest.json','json');robust=read_zip(z,'a7_block_bootstrap_sensitivity.csv');thermal=read_zip(z,'a7_thermal_transfer_summary.csv');repro=read_zip(z,'a7_a5_regeneration_checks.csv');sensitivity=read_zip(z,'a7_csi2_sensitivity_daily.csv')
    policy=m5['selected_policy']
    assert policy==m6['selected_policy']==m7['selected_policy'], 'FROZEN POLICY MISMATCH'
    assert m6['regeneration_pass'] and m7['regeneration_pass'], 'REGENERATION FAILED'
    assert len(repro)==78 and len(sensitivity)==624, 'Unexpected external cohort or sensitivity size'
    selected=str(tuple(policy))
    chosen=external[external.policy==selected].copy()
    assert len(chosen)==78 and chosen.groupby('dataset').size().eq(39).all(), 'External selected cohort mismatch'
    primary=robust[(robust.median_window==5)&(robust.include_half_cycles==False)].copy()
    half=robust[(robust.median_window==5)&(robust.include_half_cycles==True)].copy()
    assert len(primary)==len(half)==2
    joined=primary.merge(half,on='dataset',suffixes=('_closed','_with_half'),validate='one_to_one')
    assert np.allclose(joined.mean_daily_pct_closed.to_numpy(), chosen.assign(reduction_pct=100*(chosen.CSI2_base-chosen.CSI2_control)/chosen.CSI2_base).groupby('dataset').reduction_pct.mean().reindex(joined.dataset).to_numpy(),atol=1e-8), 'A5/A7 daily mean mismatch'
    joined['daily_vs_pooled_sign_disagree']=np.sign(joined.mean_daily_pct_closed)!=np.sign(joined.pooled_pct_closed)
    joined['closed_vs_half_sign_disagree']=np.sign(joined.mean_daily_pct_closed)!=np.sign(joined.mean_daily_pct_with_half)
    joined.to_csv(out/'a8_primary_and_sensitivity_reconciliation.csv',index=False)
    thermal.to_csv(out/'a8_thermal_transfer.csv',index=False)
    claims=[
      ('C01','The 30-minute 0.12 controller was selected from 2019 training days only','SUPPORTED_COMPUTATIONALLY','A5 manifest and candidate grid','Specify that earlier 2019 test days were previously inspected'),
      ('C02','A5 outcomes are computationally reproducible on 78 external system-days','SUPPORTED_COMPUTATIONALLY','A6 and A7 regeneration checks','Reproduction is not physical validation'),
      ('C03','Controller robustly reduces external closed-cycle CSI2','NOT_ESTABLISHED','A7 5-point closed-cycle block intervals span zero','Report both adverse mean-daily and positive pooled point estimates'),
      ('C04','Controller robustly reduces CSI2 under alternate cycle conventions','NOT_ESTABLISHED','A7 closed vs half cycle and smoothing sensitivity','No post hoc choice of favorable convention'),
      ('C05','Transferred thermal model accurately predicts one-minute temperature conditional on measured state','QUALIFIED','A7 one-step RMSE vs persistence','Report system-specific improvement and bias; no free-running validation'),
      ('C06','Controller reduces physical module fatigue or increases lifetime','UNSUPPORTED','CSI2 is uncalibrated squared-range proxy','Requires material-level fatigue model and empirical validation'),
      ('C07','Controller improves electrical yield or tracker energy economics','UNSUPPORTED','Optics use G*cos(angle) proxy','Requires measured/validated optical and electrical model'),
      ('C08','A5 external cohorts are independent policy-tuning holdouts','QUALIFIED','A5 selection fixed before 2018 evaluation','External data now inspected; prohibit subsequent retuning and fresh confirmatory claims'),
      ('C09','Controller is a forecast-based predictive or MPC controller','UNSUPPORTED','A3 source-code audit','Describe causal irradiance-ramp gate rather than MPC'),
      ('C10','The method is an exploratory computational feasibility and failure-analysis framework','SUPPORTED_WITH_LIMITATIONS','A1–A7 diagnostics','Use transparent exploratory framing')]
    c=pd.DataFrame(claims,columns=['claim_id','proposed_claim','classification','evidence','required_manuscript_action']);c.to_csv(out/'a8_claim_matrix.csv',index=False)
    audit={'status':'EXPLORATORY_ONLY_NOT_PHYSICALLY_VALIDATED','selected_policy':policy,'input_provenance':sources,'a6_regeneration_pass':m6['regeneration_pass'],'a7_regeneration_pass':m7['regeneration_pass'],'external_system_days':len(chosen),'claim_classifications':c.classification.value_counts().to_dict(),'no_external_retuning':True,'notes':['A8 is a read-only claim audit; not independent confirmation.','Primary estimand was not demonstrably prespecified before exploratory analyses.','External datasets are now inspected and cannot be reused as untouched holdouts.','No new scientific results were generated beyond reconciling archived A5-A7 metrics.']}
    (out/'a8_manifest.json').write_text(json.dumps(audit,indent=2))
    lines=['# A8 — Scientific consolidation and manuscript claim audit','','**Status:** exploratory computational feasibility; physical mitigation and lifetime extension are not validated.','','## Frozen analysis','- Selected policy: 30-minute causal NRI window, threshold 0.12.','- External evaluation: 39 days each in 2018 System 1 and System 2A.','- A6 and A7 numerical regeneration: PASS.','','## Pre-existing A5/A7 outcomes','', '| Dataset | Mean daily closed-cycle CSI2 reduction | 95% block CI | Pooled closed-cycle reduction | Mean daily with half cycles |','|---|---:|---:|---:|---:|']
    for _,r in joined.iterrows():lines.append(f"| {r.dataset} | {r.mean_daily_pct_closed:+.3f}% | [{r.mean_daily_CI_low_closed:+.3f}%, {r.mean_daily_CI_high_closed:+.3f}%] | {r.pooled_pct_closed:+.3f}% | {r.mean_daily_pct_with_half:+.3f}% |")
    lines+=['','Positive reduction means lower simulated CSI2; negative means higher. Mean-daily and pooled estimands differ. The closed/half-cycle convention changes the sign. These are uncalibrated thermal-cycle proxies.','','## Claim classification','']
    for _,r in c.iterrows():lines.append(f"- **{r.claim_id} {r.classification}:** {r.proposed_claim}. Evidence: {r.evidence}. Action: {r.required_manuscript_action}.")
    lines+=['','## Suggested manuscript framing','','> We present an exploratory computational audit of a causal irradiance-ramp-triggered detacking rule selected on 2019 training data and evaluated without retuning on two 2018 PV datasets. Although the implementation reproduces archived results, external changes in the squared-temperature-range cycle proxy are small and sensitive to aggregation, smoothing, and treatment of half cycles. The simplified optical and thermal counterfactual models have not been independently validated; hence the results do not establish reduced physical fatigue, lifetime extension, or electrical energy benefit.','','## Reporting guardrails','','- Retain all unfavorable and favorable results; do not replace the primary outcome post hoc.','- Describe the 2019 test period as previously inspected, not pristine confirmation.','- Do not call one-step prediction error free-running thermal validation.','- No further optimization against the 2018 external cohorts.','- Independent experimental/physical validation is required before lifetime or energy claims.']
    (out/'a8_manuscript_claim_audit.md').write_text('\n'.join(lines)+'\n')
    print('A8 RESULT',json.dumps(audit,indent=2));print('\nRECONCILIATION\n',joined[['dataset','mean_daily_pct_closed','pooled_pct_closed','mean_daily_pct_with_half','daily_vs_pooled_sign_disagree','closed_vs_half_sign_disagree']].to_string(index=False));return audit
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a5zip',required=True);p.add_argument('--a6zip',required=True);p.add_argument('--a7zip',required=True);p.add_argument('--out',default='package_a8_outputs');run(p.parse_args())