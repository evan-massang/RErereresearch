"""Front-running KOL followers: price path after a tracked KOL's first curve buy, from a 1 s-late entry.

For every (KOL wallet, token) first buy in [A, B): entry price = first curve trade >= KOL buy + 1 s; returns to
+5/10/20/30/60 s after the KOL buy; gap_pre_to_entry = how far the price already moved from just before the KOL.
No costs. Output parquet is used to pick KOLs on train and check them on validation.

    python scripts/research/kol_frontrun.py <A_unix> <B_unix> <out.parquet>
"""
import duckdb,pandas as pd,numpy as np,bisect,sys
c=duckdb.connect('data/market.duckdb',read_only=True)
U=lambda h,m,d=1:pd.Timestamp(2026,10,d,h,m,tz='UTC').timestamp()
A,B=float(sys.argv[1]),float(sys.argv[2])
# first curve buy per (kol wallet, mint) in window
fb=c.execute('''select t.usr,k.name,t.mint,min(t.recv) t0 from curve_trades t join kol_wallets k on k.wallet=t.usr
 where t.buy and t.recv>=? and t.recv<? group by 1,2,3''',[A,B]).df()
rows=[]
for r in fb.itertuples():
    x=c.execute('select recv,vsol/vtok from curve_trades where mint=? and recv between ? and ? order by recv,rowid',[r.mint,r.t0-5,r.t0+65]).fetchall()
    ts=[a for a,_ in x]; i=bisect.bisect_left(ts,r.t0+1.0)
    if i>=len(x) or i==0: continue
    p_in=x[i][1]; pre=x[bisect.bisect_left(ts,r.t0-1e-6)-1][1]
    d={'usr':r.usr,'name':r.name,'mint':r.mint,'t0':r.t0,'gap_pre_to_entry':p_in/pre-1}
    for h in (5,10,20,30,60):
        j=bisect.bisect_right(ts,r.t0+h)-1
        d[f'r{h}']=x[j][1]/p_in-1 if j>=i else np.nan
    rows.append(d)
df=pd.DataFrame(rows)
df.to_parquet(sys.argv[3])
print(len(df),'entries',df.usr.nunique(),'kols')
print(df[['gap_pre_to_entry','r5','r10','r20','r30','r60']].median().round(4))
print(df[['r5','r10','r20','r30','r60']].mean().round(4))
