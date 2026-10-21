import bw2data as bd

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

db1_name = "2026-8-9-22h39_processes_RE2020"
db2_name = "2026-8-9_consumptions_processes"
new_db_name = "2026-8-9_composants_yc_consos"

# Extract data into memory
data_1 = bd.Database(db1_name).load()
data_2 = bd.Database(db2_name).load()

# Prevent merge conflicts by checking for duplicate activity codes
codes_1 = set(code for db, code in data_1.keys())
codes_2 = set(code for db, code in data_2.keys())

if codes_1.intersection(codes_2):
    raise ValueError("Duplicate activity codes detected. Resolve conflicts before merging.")

# Combine the unrolled database dictionaries
combined_data = {**data_1, **data_2}

new_data = {}
for (old_db, code), activity in combined_data.items():
    # Update the primary database label
    activity['database'] = new_db_name
    new_key = (new_db_name, code)
    
    # Update exchanges to point to the new merged database
    for exc in activity.get('exchanges', []):
        if exc['input'][0] in (db1_name, db2_name):
            exc['input'] = (new_db_name, exc['input'][1])
        if 'output' in exc and exc['output'][0] in (db1_name, db2_name):
            exc['output'] = (new_db_name, exc['output'][1])
            
    new_data[new_key] = activity

# Register and write the new database
if new_db_name in bd.databases:
    del bd.databases[new_db_name]

new_db = bd.Database(new_db_name)
new_db.write(new_data)