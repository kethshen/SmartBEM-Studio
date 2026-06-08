from eplus.sql_explorer import EPlusSqlExplorer

xp = EPlusSqlExplorer("sim_runs/job_20260608_175005/eplusout.sql", verbose=True)
df = xp.auto_extract_series("Zone Air Temperature", include_design_days=True)
print(df)
if df is not None:
    print("Is empty?", df.empty)
