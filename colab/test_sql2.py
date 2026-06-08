import sqlite3
import pandas as pd

conn = sqlite3.connect('sim_runs/job_20260608_175005/eplusout.sql')
query = """
SELECT t.Year, t.Month, t.Day, t.Hour, t.Minute
FROM ReportData r 
JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex 
JOIN Time t ON r.TimeIndex = t.TimeIndex 
WHERE d.Name = 'Zone Air Temperature' 
LIMIT 5
"""
df = pd.read_sql_query(query, conn)
print(df)
