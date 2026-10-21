import polars as pl

import bw2data as bd

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

archdb = bd.Database("2026-10-2-17h34_archetypes_RE2020_PRB")
res = {a["code"] : {"total" : 0, "fondation" : 0} for a in archdb}
for a in archdb :
    phi = list(a.production())[0]["amount"]
    for e in a.technosphere() : 
        tmp = e["input"]
        amount = e["amount"]
        input_node = bd.get_node(database = tmp[0], code = tmp[1])
        unit = input_node["unit"]
        if "béton" in str(input_node).lower() and "waste" not in str(input_node).lower() :
            if unit == "cubic meter" :
                to_add = amount*2500
            elif unit == "square meter" :
                to_add = 0.2*2500*amount
            elif unit == "kilogram":
                to_add = amount
            else :
                print(unit)
            
            res[a["code"]]["total"]+=to_add
            if "fondation" in str(input_node["lot"]).lower

                

