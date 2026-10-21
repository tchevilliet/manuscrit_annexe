
import bw2data as bd
import bw2io as bi
import bw2calc as bc
import bw2analyzer as bwa

import numpy as np
import scipy.stats as stats

import pandas as pd

from datetime import datetime, date, time 

import os
import re

from tqdm import tqdm


import matplotlib.pyplot as plt
import seaborn as sns


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

# import bdd archetypes

perso.xlsx_import(fg_path,eidb_name,
                  biodb_name,
                  fields_to_match=('name','unit','location')
                  # ,parameters=True
                  )

ef31 = [m for m in bd.methods if (('EF v3.1' in str(m)) 
                                    & ('no LT' not in str(m))
                                    & ('EN15804' not in str(m)))]