import sqlite3
import pandas as pd

conn = sqlite3.connect('sim_runs/job_20260608_175005/eplusout.sql')
query = """
SELECT t.TimeIndex, d.KeyValue AS zone, r.Value 
FROM ReportData r 
JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex 
JOIN Time t ON r.TimeIndex = t.TimeIndex 
WHERE d.Name = 'Zone Air Temperature' 
LIMIT 20
"""
df = pd.read_sql_query(query, conn)
print(df)

query2 = "SELECT DISTINCT d.ReportingFrequency FROM ReportDataDictionary d WHERE d.Name = 'Zone Air Temperature'"
df2 = pd.read_sql_query(query2, conn)
print("Frequencies in DB for Zone Air Temperature:", df2)
