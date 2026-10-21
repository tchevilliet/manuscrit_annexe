#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 16 14:50:04 2024

@author: thibault.chevilliet

ensemble de fonctions pour bw25 
"""
import pandas as pd
import numpy as np
from datetime import datetime, date, time 
import seaborn as sns
import matplotlib.pyplot as plt
import os
import re
# BW25 packages
import bw2data as bd
import bw2io as bi
import bw2calc as bc

def all_equal(iterator):
    """
    Return True if all the elements in the iterator are equals, False if not.

    Parameters
    ----------
    iterator : any iterator

    Returns
    -------
    True or False.

    """
    it = iter(iterator)
    try:
        first = next(it)
    except StopIteration:
        return True
    return all(first == x for x in it)

def unique_list(l):
    res=[]
    for e in l :
        if e in res:
            pass
        else :
            res.append(e)
    return res
    

def import_bdd(project_name,db_path,db_name) :
    """
    Made for bw2.5 
    import the database located at db_path in the project "project_name", with
    the name "db_name"

    Parameters
    ----------
    project_name : string
        name of the project where the database is needed.
    db_path : TYPE
        path of the database to import.
    db_name : TYPE
        name of the database in the project's databases dictionary.

    Returns
    -------
    None.

    """
    # BW25 packages
    import bw2data as bd
    import bw2io as bi

    # set the project as current, or create it if it doesn't exist
    bd.projects.set_current(project_name)

    # Biosphere matrix import
    bi.bw2setup()

    #Import database if its names doesn't belong already to bd.databases
    if db_name in bd.databases:
        print("Database has already been imported.")
    else:
    # Go ahead and import:
        ei_importer = bi.SingleOutputEcospold2Importer(db_path, db_name)
        # Apply stragegies 
        ei_importer.apply_strategies()
        # We can get some statistics
        ei_importer.statistics()
        # Now we will write the database into our project. 
        ei_importer.write_database()

def exchanges_df(act, cond_name =None):
    """
    Create a pandas dataframe that contains the exchanges of an activity.
    Exchanges can be filtered by name.
    
    Parameters
    ----------
    act : brightway activity
        Activity for which you want to consider the exchanges
    cond_name : string, optional
        Condition on the name of the exchanges you want to consider. 
        The default is None.

    Returns
    -------
    Pandas dataframe
        Contains values of the usual exchange dictionnary, 
        with its keys as columns.

    """
    import pandas as pd
    if cond_name == None :
        tmp = [exc for exc in act.exchanges()]
    else :
        tmp = [exc for exc in act.exchanges() if cond_name.lower() in str(exc).lower()]
    
    return pd.DataFrame(tmp[i].as_dict() for i in range(len(tmp)))


def lcas_static_df(process, list_demand, list_meth):
    """
    Does impacts assessments of a process for different amounts and methods,
    and return the scores in a pandas dataframe.

    Parameters
    ----------
    process : Brightway activity
        process to assess.
    list_demand : list of floats/integers
        different demand to assess
    list_meth : list of Brightway method
        different method to use

    Returns
    -------
    res : Pandas dataframe
        Contains the lca scores. Demands are lines, methods are columns.

    """
    import pandas as pd
    import bw2calc as bc
    res = pd.DataFrame()
        
    FU = {process : list_demand[0]}
    m = list_meth[0]
    lca = bc.LCA(FU,m)
    lca.lci()
    lca.lcia()
    res.loc[f"{list_demand[0]}",f"{list_meth[0]}"] = lca.score
    
    for i in range(len(list_meth)) :
        lca.switch_method(list_meth[i])
        for j in range(len(list_demand)) :
            FU = {process.id : list_demand[j]}
            print(FU)
            lca.redo_lcia(FU)
            res.loc[f"{list_demand[j]}",f"{list_meth[i]}"] = lca.score
            
    return res
    
    
def method_cfs(method_name,db):
    """
    Create a dataframe with the names 
    
    Parameters
    ----------
    method_name : tuple
        name of the method for which we want characterisation factors.
    
    db : brightway database
        Biosphere database the method apply on.

    Returns
    -------
    res : pandas Dataframe
        First column : name of flow, second column : Characterisation factor.

    """

    #Source is already what we want, just not in a dataframe, and with non-explicit flow identifier
    #source = [x for x in bd.Method(method_name).load()] 
    flows = [x for x in bd.Method(method_name).load()]  # list of tuples such as (flow's id, flow's cf)
    fl_names = []
    for flow in flows :
        tmp = [(f['name'],f['categories']) for f in db if f['id']==flow[0]] #name of the flow is obtained...
        fl_names.append(tmp[0])#...and added to the result list
    
    #we create the result dataframe
    res= pd.DataFrame()
    res['Elementary flow'] = fl_names 
    res['CF'] = [elm[1] for elm in flows]
    
    return res
 
 
def search_and(meths,*keywords):
    """
    Search the elements into the list "meths" that contain all the keywords

    Parameters
    ----------
    meths : list
        list of methods or activities.
    *keywords : string
        keywords to search.

    Returns
    -------
    res : list
        results of the research.

    """
    res=[]
    for meth in meths :
        cond = True
        for keyword in keywords :
            cond = cond and (keyword in str(meth))
        if cond:
            res.append(meth)
    
    return res
 
def search_or(meths,*keywords):
    """
    Search the elements into the list "meths" that contain one of the keywords

    Parameters
    ----------
    meths : list
        list of methods or activities.
    *keywords : string
        keywords to search.

    Returns
    -------
    res : list
        results of the research.

    """
    res=[]
    for meth in meths :
        cond = False
        for keyword in keywords :
            cond = cond or (keyword in str(meth))
        if cond:
            res.append(meth)
    
    return res


def xlsx_import(fg_path,*db_to_match,fields_to_match=None,parameters=False):
    """
    import a dataset in excel, apply strategies, match itself and
    given database on the given fields, create an excel file of the import and
    write the database.

    Parameters
    ----------
    fg_path : str
        path to xlsx file.
    db_to_match : str
        name of an already imported database.
    fields_to_match : tuple of str
        tuple that contains the fields to match.
    parameters : boolean
    	True if there are projects or database parameters, False by default

    Returns
    -------
    None.

    """
    
    imp = bi.ExcelImporter(fg_path) # import of the xlsx file

    # if not hasattr(imp, 'data') or len(imp.data) == 0:
    #     print(f"Erreur: Aucune donnée trouvée dans {fg_path}")
    #     print("Vérifiez que le fichier Excel contient bien des données au bon format.")
    #     return None


    # # apply strategies - Brightway 2.5 compatible
    # try:
    #     imp.apply_strategies()
    #     print("apply_strategies worked directly")
    # except AttributeError:
    #     # Application manuelle avec l'attribut correct
    #     print("Application manuelle des stratégies...")
    #     data_attr = 'db' if hasattr(imp, 'db') else 'data'
    #     if hasattr(imp, 'strategies'):
    #         for strategy in imp.strategies:
    #             setattr(imp, data_attr, strategy(getattr(imp, data_attr)))

    # apply strategies
    imp.apply_strategies()
    # match fg_db to itself
    imp.match_database(fields=fields_to_match)
    # match fg_db to db_to_match
    for db in db_to_match :
    	imp.match_database(db,fields=fields_to_match) 
    # print stats on the import
    imp.statistics()
    # create the excel_file with the matched fg_db
    imp.write_excel()
    #write project parameters if needed and write the database in bd.Database:
    if parameters :
        imp.write_project_parameters()
        imp.write_database(activate_parameters=True)
    else :
        imp.write_database(activate_parameters=False)
    return None

def mc_lcas(list_demand, list_meth, nb_mc):
    
    """
    Do nb_mc runs of Monte-Carlo for each chosen method in list_meth and each
    demand in list_demand, returns a dataframe with organized results.

    Parameters
    ----------
    list_demand : list
        list of dictionaries {process : amount}.
    list_meth : tuple
        methods as used in brightway.
    nb_mc : int
        number of Monte-Carlo runs.

    Returns
    -------
    res : dataframe
        Dataframe of lists, index = demands, columns = methods.

    """
    res = pd.DataFrame(
        index=[f"{dem}" for dem in list_demand],columns=list_meth)
    res = res.astype('object') #to allow elements to be lists
    for m in list_meth :
        for d in list_demand :
            tmp = bc.LCA(d,m,use_distributions=True)
            tmp.lci()
            tmp.lcia()
            res.at[f"{d}",m] = [tmp.score for _ in zip(tmp, range(nb_mc))]
    
    return res 


def mc_lcasx(list_demand, list_meth, nb_mc):
    
    """
    Do nb_mc runs of Monte-Carlo for each chosen method in list_meth and each
    demand in list_demand, returns a dataframe with organized results.

    Parameters
    ----------
    list_demand : list
        list of dictionaries {process : amount}.
    list_meth : tuple
        methods as used in brightway.
    nb_mc : int
        number of Monte-Carlo runs.

    Returns
    -------
    res : dataframe
        Dataframe of lists, index = demands, columns = methods.

    """
    res = pd.DataFrame(
        index=[f"{dem}" for dem in list_demand],columns=list_meth)
    res = res.astype('object') #to allow elements to be lists
    list_demand_id = [{list(d.keys())[0].id : list(d.values())[0]} for d in list_demand]
    print(list_demand_id)
    for m in list_meth :
        tmp = bc.LCA(list_demand[0],m,use_distributions=True)
        tmp.lci()
        tmp.lcia()   	
        for d in list_demand :
            ind = list_demand.index(d)
            tmp.redo_lcia(list_demand_id[ind])
            res.at[f"{d}",m] = [tmp.score for _ in zip(tmp, range(nb_mc))]
    return res 


 
### Fonctions pour analyse de discernabilité selon Heijungs 2021


def K(A_mc,B_mc) :
    """
    Comparison index according to Heijungs 2021 
    https://doi.org/10.1007/s11367-020-01851-4
    
    Parameters
    ----------
    A_mc : list of floats
        Results of Monte-carlo runs for product A.
    B_mc : list of floats
        Results of Monte-carlo runs for product B.

    Returns
    -------
    dict
        Both K_A et K_B index.

    """
   
    assert len(A_mc) == len(B_mc) , 'Same number of Monte-Carlo runs needed'
    n=len(A_mc)

    A = np.asarray(A_mc)
    B = np.asarray(B_mc)

    ka = np.heaviside(B - A, 0).mean()
    kb = np.heaviside(A - B, 0).mean()

    # ka = (1/n)*sum([
    #     np.heaviside((B_mc[i]-A_mc[i]),0) for i in range(n)
    #     ])
    # kb = (1/n)*sum([
    #     np.heaviside((A_mc[i]-B_mc[i]),0) for i in range(n)
    #     ])
    return {'K_A': ka , 'K_B': kb}


def K2(A_mc,B_mc):
    """
    Comparison index according to Heijungs 2021 
    https://doi.org/10.1007/s11367-020-01851-4
    
    Parameters
    ----------
    A_mc : list of floats
        Results of Monte-carlo runs for product A.
    B_mc : list of floats
        Results of Monte-carlo runs for product B.

    Returns
    -------
    dict
        Both K2,A et K2,B index.

    """
    assert len(A_mc) == len(B_mc) , 'Same number of Monte-Carlo runs needed'

    A = np.asarray(A_mc)
    B = np.asarray(B_mc)

    
    n=len(A)
    ka = np.heaviside(B[:, None] - A[None, :], 0).mean()
    # ka = (1/n)*sum([
    #     (1/n)*sum([
    #     np.heaviside((B_mc[i]-A_mc[j]),0) for j in range(n)
    #     ]) for i in range(n)
    #     ])
    kb = np.heaviside(A[:, None] - B[None, :], 0).mean()
    # kb = (1/n)*sum([
    #     (1/n)*sum([
    #     np.heaviside((A_mc[i]-B_mc[j]),0) for j in range(n)
    #     ]) for i in range(n)
    #     ])
    return {'K2_A': ka , 'K2_B': kb}
    

def K3(A_mc,B_mc):
    """
    Comparison index according to Heijungs 2021 
    https://doi.org/10.1007/s11367-020-01851-4
    
    Parameters
    ----------
    A_mc : list of floats
        Results of Monte-carlo runs for product A.
    B_mc : list of floats
        Results of Monte-carlo runs for product B.

    Returns
    -------
    dict
        Both K3,A et K3,B index.

    """
    assert len(A_mc) == len(B_mc) , 'Same number of Monte-Carlo runs needed'
    n=len(A_mc)
    ka = (1/n)*sum([
        np.heaviside((B_mc[i]-np.median(A_mc)),0) for i in range(n)])
    kb = (1/n)*sum([
        np.heaviside((A_mc[i]-np.median(B_mc)),0) for i in range(n)])
    return {'K3_A': ka , 'K3_B': kb}

def K4(A_mc,B_mc,threshold=1.2):
    """
    Modified comparison index according to Heijungs 2021 
    https://doi.org/10.1007/s11367-020-01851-4
    
    Parameters
    ----------
    A_mc : list of floats
        Results of Monte-carlo runs for product A.
    B_mc : list of floats
        Results of Monte-carlo runs for product B.
    threshold : float, optional
        Arbitrary minimum threshold value. The default is 1.2.

    Returns
    -------
    dict
        threshold considered for the comparison and both K4,A et K4,B index.

    """
    import numpy as np
    
    assert len(A_mc) == len(B_mc) , 'Same number of Monte-Carlo runs needed'
    n=len(A_mc)
    if sum(A_mc)==0 or sum(B_mc)==0 :
        ka , kb = 1000 , 1000
    else :
        ka = (1/n)*sum([
            np.heaviside((B_mc[i]/A_mc[i])-threshold,0) for i in range(n)])
        kb = (1/n)*sum([
            np.heaviside((A_mc[i]/B_mc[i])-threshold,0) for i in range(n)])
        
    return {'gamma_0' : threshold, 'K4_A': ka , 'K4_B': kb}


from cmcrameri import cm
cmap = cm.berlin
palette = list(cmap(np.linspace(0.1, 0.9, 2)))

def discern_1_meth(thresholds,l_mc,out_folder,out_path,param = None):
    """
    For one method, ie one column from dataframe out of the mc_lcas function,
    and a list of thresholds, do a discernibility analysis (K,K2,K3,K4)
    on the products contained in mc_lcas otuput index.
    It creates an xlsx file and graphs.
    
    Comparisons indexes according to Heijungs 2021
    https://doi.org/10.1007/s11367-020-01851-4

    Parameters
    ----------
    thresholds : list
        list of thresholds to consider for K4.
    l_mc : panda serie
        column of a mc_lcas output (monte-carlo runs on each product for a 
                                    given method)
    out_folder : string
        path to the output folder.
    out_path : string
        path to the xlsx file.
    param : dictionary of dictionaries
        dictionary of Activity, Databse and Project parameters dictionaries. 
        Default None.

    Returns
    -------
    res : dict
        dictionary with all the comparison index.

    """
    #Building the results dictionary
    res1=pd.DataFrame(index=l_mc.index,columns=l_mc.index)
    res2=pd.DataFrame(index=l_mc.index,columns=l_mc.index)
    res3=pd.DataFrame(index=l_mc.index,columns=l_mc.index)
    res4={gamma : pd.DataFrame(index=l_mc.index,columns=l_mc.index) for gamma in thresholds}
    
    # #début de code pour pouvoir ne pas tout tracer
    # l_graph=['distrib','K','K2','K3','K4']
    # if graphs == all
    
    tmp = l_mc.copy()
    for i in l_mc.index:
        tmp=tmp.drop(i)
        for j in tmp.index:
            li, lj =l_mc.at[i], l_mc.at[j]
            tmp1 = K(li,lj)
            res1.at[i,j],res1.at[j,i] = tmp1['K_A'],tmp1['K_B']
            tmp2 = K2(li,lj)
            res2.at[i,j],res2.at[j,i] = tmp2['K2_A'],tmp2['K2_B']
            tmp3 = K3(li,lj)
            res3.at[i,j],res3.at[j,i] = tmp3['K3_A'],tmp3['K3_B']
            for gam in thresholds :
                tmp4 = K4(li,lj,gam)
                res4[gam].loc[i,j],res4[gam].loc[j,i] = tmp4['K4_A'],tmp4['K4_B']
    res = {'K' : res1,'K2' : res2,'K3' : res3,'K4' : res4} 
    #Creates excel file
    with pd.ExcelWriter(out_path) as writer :
        com = 'Probability of (Impact(line)<Impact(column)) ie Line better than column ?'
        info = pd.DataFrame({'location' : out_path
                             ,'Number of Monte-Carlo runs' : [len(x) 
                                                              for x in l_mc]
                             ,'Number of assessed products': len(l_mc)
                             , 'HOW TO READ RESULTS' : com 
                                 })
        info.to_excel(writer,sheet_name='INFO')
        for k in res.keys():
            if type(res[k])== dict :               
                for j in res[k].keys():
                    res[k][j].to_excel(writer,sheet_name=f"{k}_{j}")
            else :
                res[k].to_excel(writer,sheet_name=k)
        if param==None:
            pass
        else :
            df_param=pd.DataFrame(param)
            df_param.to_excel(writer,sheet_name='PARAM')
    # Graphs
    # Distributions
    #   a graph for each, and one for all at once
    to_g=pd.DataFrame(index = l_mc.index
                      ,columns=[i for i in range(len(l_mc.at[l_mc.index[0]]))]
                      )
    for i in l_mc.index :
        tmp = l_mc.at[i]
        g=sns.histplot(l_mc.at[i],kde=True,stat='probability')
        g.set(title=f"Demand : {str(i)[:7]} , Impact : {l_mc.name}")
        g.get_figure().savefig(
            f"{out_folder}/{i}_distribution.pdf"
            ,dpi = 200
            #,bbox_extra_artist = (g.get_legend())
            ,bbox_inches='tight'
            )
        g.get_figure().clf()
        for j in range(len(tmp)) :
            to_g.at[i,j] = tmp[j]
    
    g = sns.histplot(to_g.T,kde=True,stat='probability')
    sns.move_legend(g, loc='upper center', bbox_to_anchor=(0.5,-0.2))
    g.get_figure().savefig(
        f"{out_folder}/0_All_distributions.pdf"
        ,dpi = 200
        #,bbox_extra_artist = (g.get_legend())
        ,bbox_inches='tight'
        )
    g.get_figure().clf()

    # K, K2, K3
    for ke in res.keys() :
        if ke=='K4' :
            pass
        else :
            index_tmp = l_mc.index.copy()
            for i in l_mc.index :
                index_tmp=index_tmp.drop(i)
                for j in index_tmp :
                    x, y, h= [], [], []
                    x=x+[1,1]
                    y=y+[res[ke].loc[i,j],-res[ke].loc[j,i]]
                    h=h+[f"Impact of {re.search("'(.*?)'",i).group(0)} < Impact of {re.search("'(.*?)'",j).group(0)}",
                         f"Impact of {re.search("'(.*?)'",i).group(0)} > Impact of {re.search("'(.*?)'",j).group(0)}"]
                    to_graph = pd.DataFrame(
                    {'Position' : x, 'Probability' : y,'Condition' : h})
                    sns.set_style("whitegrid")
                    g = sns.barplot(to_graph, x="Probability", y="Position"
                    , orient="h"
                    , width = 0.2
                    , hue='Condition'
                    , dodge = False
                    , legend=True
                    ,palette= palette
                    )
                    g.set(title=f"Comparison index {ke}"
                      ,xlim=(-1,1)
                      ,ylabel=None
                      ,yticklabels=()
                      )
                    g.set()
                    g.set_xticks((-1,-0.75,-0.5,-0.25,0,0.25,0.5,0.75,1)
                     ,labels=(1,0.75,0.5,0.25,0,0.25,0.5,0.75,1))
                    g.get_legend().set_title("")
                    sns.move_legend(g, loc='upper center', bbox_to_anchor=(0.5,-0.2))
                    g.get_figure().savefig(
                        f"{out_folder}/{i}vs{j}_{ke}.pdf"
                        ,dpi = 200
                        #,bbox_extra_artist = (g.get_legend())
                        ,bbox_inches='tight'
                        )
                    g.get_figure().clf()
	# K4
    index_tmp = l_mc.index.copy()
    for i in l_mc.index :
        index_tmp=index_tmp.drop(i)
        for j in index_tmp :
            x, y, h= [], [], []
            for k in res4.keys() :
                x=x+[k,k]
                y=y+[res4[k].loc[i,j],-res4[k].loc[j,i]]
                h=h+[f"Impact of {re.search("'(.*?)'",i).group(0)} < Impact of {re.search("'(.*?)'",j).group(0)}",
                     f"Impact of {re.search("'(.*?)'",i).group(0)} > Impact of {re.search("'(.*?)'",j).group(0)}"]
                to_graph = pd.DataFrame(
                {'Threshold' : x, 'Probability' : y,'Condition' : h})
            sns.set_style("whitegrid")
            g = sns.barplot(to_graph, x="Probability", y="Threshold"
            , order= list(reversed(thresholds))
            , orient="h"
            , width = 0.4
            , hue='Condition'
            , dodge = False
            , legend=True
            ,palette= palette
            )
            g.set(title="Modified comparison index $K_{4}$"
              ,xlim=(-1,1))
            g.set_xticks((-1,-0.75,-0.5,-0.25,0,0.25,0.5,0.75,1)
             ,labels=(1,0.75,0.5,0.25,0,0.25,0.5,0.75,1))
            g.get_legend().set_title("")
            sns.move_legend(g, loc='upper center', bbox_to_anchor=(0.5,-0.2))
            g.get_figure().savefig(
                f"{out_folder}/{i}vs{j}_K4.pdf"
                ,dpi = 200
                #,bbox_extra_artist = (g.get_legend())
                ,bbox_inches='tight'
                )
            g.get_figure().clf()
    return res
    

def discern(thresholds,mcs_res,met = 'all',out_folder='OUT',param=None):
    #if len(l_mc.index)<2 or not(all_equal([len(l) for l in l_mc])) :
    if len(mcs_res.index)<2 :
        raise ValueError('At least two lists of the same lengths are needed.')
    else :
        t = date.today()
        n = datetime.now()
        folder_name=f"{out_folder}/{t}_{n.hour}h{n.minute}"
        os.makedirs(folder_name,exist_ok=True)
        meths = [m for m in mcs_res.columns] if met=='all' else met
        res = {}
        for meth in meths :
            os.makedirs(f"{folder_name}/{meth}")
            res[meth] = discern_1_meth(thresholds,mcs_res[meth],
                                       f"{folder_name}/{meth}",
                                       f"{folder_name}/{meth}/discernability_results_{meth}.xlsx",
                                       param)
        return res     


def graph_all(mcs_res,met = 'all',out_folder='OUT') :
    
    t = date.today()
    n = datetime.now()
    folder_name=f"{out_folder}/{t}_{n.hour}h{n.minute}_distrib"
    os.makedirs(folder_name,exist_ok=True)
    meths = [m for m in mcs_res.columns] if met=='all' else met
    for meth in meths :
        graph_one_meth(mcs_res[meth], f"{folder_name}/{meth}_distrib.pdf")
    return f"All graphs saved in {folder_name}"


def graph_one_meth(l_mc,out_path,l_col=False,xlabel=None) :
    if l_col :
        pal = sns.color_palette(l_col)
    else : 
        pal ='coolwarm'
    to_g=pd.DataFrame(index = [f"{re.search("'(.*?)'",i).group(0)}" 
                               for i in l_mc.index]
                      ,columns=[i for i in range(len(l_mc.at[l_mc.index[0]]))]
                      )
    for i in l_mc.index :
        tmp = l_mc.at[i]
        for j in range(len(tmp)) :
            to_g.at[f"{re.search("'(.*?)'",i).group(0)}",j] = tmp[j]
    g = sns.histplot(to_g.T,kde=False,stat='probability'
                      ,element='step'
                     ,palette= pal
                     )
    sns.move_legend(g, loc='upper center', bbox_to_anchor=(0.5,-0.3))
    g.set_xlabel(xlabel)
    plt.axvline(0,0,max(to_g.T[to_g.T.columns[0]]),linestyle='solid')
    sns.despine()
    plt.savefig(
        f"{out_path}"
        ,dpi = 200
        #,bbox_extra_artist = (g.get_legend())
        ,bbox_inches='tight'
        )    
    # g.get_figure().savefig(
    #     f"{out_path}"
    #     ,dpi = 200
    #     #,bbox_extra_artist = (g.get_legend())
    #     ,bbox_inches='tight'
    #     )
    g.get_figure().clf()
    plt.clf()
    
    return f"{out_path} saved"

def barplot_static_one_meth(l_mc,out_path) :
    to_g=pd.DataFrame(index = l_mc.index
                      ,columns=[i for i in range(len(l_mc.at[l_mc.index[0]]))]
                      )
    for i in l_mc.index :
        tmp = l_mc.at[i]
        for j in range(len(tmp)) :
            to_g.at[i,j] = tmp[j]
    g = sns.barplot(to_g.T
                    ,stat='probability'
                      ,element='step'
                     ,palette='coolwarm'
                     )
    sns.move_legend(g, loc='upper center', bbox_to_anchor=(0.5,-0.2))
    g.get_figure().savefig(
        f"{out_path}"
        ,dpi = 200
        #,bbox_extra_artist = (g.get_legend())
        ,bbox_inches='tight'
        )
    g.get_figure().clf()
    
    return f"{out_path} saved"


def uncertainty_parameters_to_float(db) :
    """
    make sure that scales are floats for all exchanges of all activities in the
    database

    Parameters
    ----------
    db : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """
    i = 0
    for act in db : 
        for exc in list(act.exchanges()) :
            if len(exc.uncertainty)>1 :
                for key in [k for k in exc.uncertainty.keys() if k !='uncertainty type'] :
                    exc.uncertainty[key] = float(exc.uncertainty[key])
                i +=1
    
    return f"{i} edges done"
                    

def act_delta (db,act1,act2) :
    """
    Create and save an activity in db which is the difference between act1 and 
    act2.
    Parameters
    ----------
    db : Brightway database
        An existing database in the project.
    act1 : Brightway activity
        An activity in db.
    act2 : Brightway activity
        An activity in db.

    Returns
    -------
    None.

    """
    attributes ={
        'name' : f"delta_{act1['code']}-{act2['code']}",
        'categories': ('custom process',),
         'code': f"delta_{act1['code']}-{act2['code']}",
         'comment': 'un commentaire',
         'location': 'FR',
         'production amount': 1,
         'type': 'process',
         'unit': 'unit',
         'database': db.name,
         'reference product': f"delta_{act1['code']}-{act2['code']}"
        }
    res = db.new_node(**attributes)
    res.save() #create and save delta new node
    # exchange with the node itself
    tmp_attri = {'name': res['name'],
     'amount': 1,
     'unit': 'unit',
     'database': db.name,
     'location': 'FR',
     'type': 'production',
     'input': res,
     }
    res.new_edge(**tmp_attri).save() #save the production "chimmera" exchange

    l_edges1 = [e for e in act1.edges() if e not in act1.production()]
    l_edges2 = [e for e in act2.edges() if e not in act2.production()]
    
    for exc1 in l_edges1 :
        unc1 = exc1.uncertainty
        if exc1['name'] not in [e['name'] for e in l_edges2] :
            #if exc1 not in act2 exchanges, we just copy the exchange
            tmp_attri = {key : value for key, value in exc1.items()
                         if key != 'output'}
        else :
            #if exc1  in act2 exchanges, we just copy the exc1 attributes, except for the amount
            exc2 = [e for e in l_edges2 if e['name'] == exc1['name']][0]
            tmp_attri = {key : value for key, value in exc1.items() 
                         if key != 'output'}
            tmp_attri['amount']= exc1['amount']-exc2['amount']
            unc2 = exc2.uncertainty
            tmp_unc = unc1
            if len(unc1) > 0 :
                if unc1['uncertainty type'] == 2 : # for lognormal distribution
                    med = np.exp(unc1['loc'])-np.exp(unc2['loc']) # delta of medians
                    tmp_loc = np.log(med) # mu for underlying delta distrib
                elif unc1['uncertainty type'] == 3 : # for normal distributions
                    tmp_loc = unc1['loc']-unc2['loc']
                else :
                    print('Unsupported uncertainty type')
                    break
                tmp_unc = {'uncertainty type': unc1['uncertainty type'],
                             'loc': tmp_loc,
                             'scale': unc1['scale'] #same scale (delta should only translate the distrib)
                             }
                
            l_edges2.remove(exc2) #we reduce the act2 exchanges list to consider (exchanges should be used only once)
        tmp = res.new_edge(**tmp_attri)
        tmp.save() 
        if len(tmp_unc)>0 :
            for k in tmp_unc.keys() :
                tmp.uncertainty[k] = tmp_unc[k]
                tmp.save()
    

    #We then add the exchanges of act2 that didn't exist in act1
    for exc2 in l_edges2 :
        tmp_attri = {key : value for key, value in exc2.items()}
        unc2 = exc2.uncertainty
        tmp_unc = unc2
        tmp = res.new_edge(**tmp_attri)
        tmp.save()
        if len(tmp_unc)>0 :
            for k in tmp_unc.keys() :
                tmp.uncertainty[k] = tmp_unc[k]
                tmp.save()
        
    return res.as_dict()



def moments_mcs(mcs_res) :
    """
    Create a multiindex dataframe with the mean and standard deviation of the 
    scores list for each demand and indicator

    Parameters
    ----------
    mcs_res : DataFrame
        Dataframe with indicators as columns and demands as rows. Each cell
        contains a list of scores.

    Returns
    -------
    res : DataFrame
        Table with moments on scores lists.

    """
    arrays = [list(mcs_res.columns),['mean','std']]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples,names=['indicator','stat'])
    res = pd.DataFrame(index=index,columns=mcs_res.index)
    for meth in mcs_res.columns :
        for dem in mcs_res.index :
            tmp = mcs_res.at[dem,meth]
            res.loc[(meth,'mean'),dem] = np.mean(tmp)
            res.loc[(meth,'std'),dem] = np.std(tmp)
    return res

"""
def redefine_uncertainty(act,exc = 'all' values_dict) :
    tmp = bd.get_node(**{k:v for k,v in act.items()})# node to modify
    for key in values_dict.keys() :
        tmp.uncertainty[key] = values_dict[key]
    return None
    

def explore_scales(db,scales,force = False) :
    if (("ecoinvent" in db.name) or ("biosphere" in db.name)) and not force :
        print("Don't mess with ecoinvent or the biosphere")
    else :
        for s in scales :
            for exc in [e for node in db for e in node.exchanges()] :
                if len(exc.uncertainty)>0:
                    exc.uncertainty['scale'] = s
            
"""





