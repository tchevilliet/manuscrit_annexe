import bw2data as bd
import bw2io as bi

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

fg_path = "data/external/250422_fgdb.xlsx"

imp = bi.ExcelImporter(fg_path)

imp.apply_strategies()

imp.match_database(fields=["name","unit","location"])
imp.match_database("ecoinvent-3.11-cutoff",["name","unit","location"])
imp.match_database("ecoinvent-3.11-biosphere",["name","unit","categories"])
imp.statistics()
imp.write_excel()
imp.write_database()