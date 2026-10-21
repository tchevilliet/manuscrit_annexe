import json

with open('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/HB programs/2019_data.json', 'r') as f:
	prog = json.load(f)



key = [k for k in prog.keys() if "MidriseApartment::Apartment" in k][0]

with open('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/HB programs/schedule.json', 'r') as f:
	occ = json.load(f)

occ_to_keep = {}

for k, v in prog[key].items():
	if not isinstance(v, dict):
		continue
	for a,b in v.items() :
		if "schedule" in a :
			occ_to_keep[(k,a)] = b

res = {}
for k,v in occ_to_keep.items() :
	res[k] = {k : occ[v]}
 


res_to_export = {"_".join([k[0],k[1]]) : list(v.values())[0] for k,v in res.items()}

with open("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/HB programs/export_prog_apartment.json","w") as f :
	json.dump(res_to_export,f)
