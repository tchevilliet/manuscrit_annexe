import json
from scipy.interpolate import griddata
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from tqdm import tqdm
from matplotlib.ticker import ScalarFormatter
from archetypes_re2020.config import FIGURES_DIR

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

def emprise_projet(Slc,Sbur,param_dict) :
    a = (1/param_dict["Rlc"])+(param_dict["Eep_lc"]/param_dict["Rep"])+(param_dict["Eequip_lc"]/param_dict["Requip"])
    b= (1/param_dict["Rbur"])+(param_dict["Eep_bur"]/param_dict["Rep"])+(param_dict["Eequip_bur"]/param_dict["Requip"])
    return a*Slc + b*Sbur

def cout_projet(Slc,Sbur,param_dict):
    a= (
        param_dict["Ksol"]*(
            (1/param_dict["Rlc"])
            +param_dict["Eep_lc"]/param_dict["Rep"]
            +(param_dict["Eequip_lc"]/param_dict["Requip"])
            ) 
            + param_dict["Eep_lc"]*param_dict["Cep"]
            +param_dict["Eequip_lc"]*param_dict["Cequip"]
            -param_dict["Klc"]
    )
    b= (
        param_dict["Ksol"]*(
            (1/param_dict["Rbur"])
            +param_dict["Eep_bur"]/param_dict["Rep"]
            +(param_dict["Eequip_bur"]/param_dict["Requip"])
            ) 
            + param_dict["Eep_bur"]*param_dict["Cep"]
            +param_dict["Eequip_bur"]*param_dict["Cequip"]
            -param_dict["Kbur"]
    )

    return a*Slc+b*Sbur

def impact_projet(Slc,Sbur,param_dict,res_dict,ind="gwp",stat = "mu") :
    part_route = param_dict["part_route"]
    imp_EP = (
        res_dict[ind]["vegetation"][stat]*(1-part_route) 
        + res_dict[ind]["route"][stat]*part_route
        )
    a= (
    param_dict["Ksol"]*(
        (1/param_dict["Rlc"])
        +param_dict["Eep_lc"]/param_dict["Rep"]
        +(param_dict["Eequip_lc"]/param_dict["Requip"])
        ) 
        + param_dict["Eep_lc"]*param_dict["Cep"]
        +param_dict["Eequip_lc"]*param_dict["Cequip"]
        -param_dict["Klc"]
    )
    b= (
        param_dict["Ksol"]*(
            (1/param_dict["Rbur"])
            +param_dict["Eep_bur"]/param_dict["Rep"]
            +(param_dict["Eequip_bur"]/param_dict["Requip"])
            ) 
            + param_dict["Eep_bur"]*param_dict["Cep"]
            +param_dict["Eequip_bur"]*param_dict["Cequip"]
            -param_dict["Kbur"]
    )

    a = (
        res_dict[ind]["Logement collectif"][stat] 
        + param_dict["Eequip_lc"]*res_dict[ind]["Bureau"][stat] 
        + param_dict["Eep_lc"]*imp_EP
    )
    b = (
        res_dict[ind]["Bureau"][stat] 
        + param_dict["Eequip_bur"]*res_dict[ind]["Bureau"][stat] 
        + param_dict["Eep_bur"]*imp_EP
    )

    return a*Slc + b*Sbur

def xyz(res_discern,index_comp,ind,simplified = False, seuil_sup = 0.5, seuil_inf =0.3) :
    x_data = []
    y_data = []
    z_data = []
    tmp = res_discern[ind][index_comp]
    if index_comp =="K4" and simplified :
        for k, v in tmp.items():
            xy = eval(k)
            x_data.append(xy[0])
            y_data.append(xy[1])
            k4a = float(v[f"{index_comp}_A"])
            k4b = float(v[f"{index_comp}_B"])
            if k4a >= seuil_sup :
                if k4b<seuil_inf :
                    to_add = 1
                else :
                    to_add =0
            elif k4a >=seuil_inf :
                to_add = 0
            else : 
                if k4b >= seuil_sup :
                    to_add = -1
                else : 
                    to_add = 0

            z_data.append(to_add)
    
    else :
        for k, v in tmp.items():
            xy = eval(k)
            x_data.append(xy[0])
            y_data.append(xy[1])
            z_data.append(float(v[f"{index_comp}_A"]))
    
    return x_data,y_data,z_data

def plot_ki(
    res, # resultats analyse discern
    index_comp, # K,K2,K3 ou K4
    ind, #indicateur
    param_amenageur, # paramètres aménageur
    x_ref,y_ref, # point ref de l'analyse discern
    short_name_dict,
    input_folder,
    simplified=True, seuil_sup=0.75, seuil_inf =0.3 # option xyz
    ) :

    x_data,y_data,z_data = xyz(res,index_comp,ind,simplified=simplified, seuil_sup=seuil_sup, seuil_inf =seuil_inf)
    xi = np.linspace(np.min(x_data), np.max(x_data), 200)
    yi = np.linspace(np.min(y_data), np.max(y_data), 200)
    Xi, Yi = np.meshgrid(xi, yi)

    Zi = griddata((np.array(x_data), np.array(y_data)), z_data, (Xi, Yi), method='linear')

    x_annot_cout = 280000
    y_annot_cout = 760000

    x_annot_emp = 130000
    y_annot_emp = 950000

    N = 2000
    x = np.linspace(-5E4, 5E5, N)
    y = np.linspace(-2E5, 1.5E6, N)
    X, Y = np.meshgrid(x, y)

    cout = lambda x,y : cout_projet(x,y,param_amenageur)
    emprise = lambda x,y : emprise_projet(x,y,param_amenageur)

    mask = (
        (cout(X,Y) <= param_amenageur["subvention"])
        & (emprise(X,Y) <= param_amenageur["aire_projet"])
        & (X>=0) & (Y>=0)
        )


    fig, ax = plt.subplots(figsize=(10, 6))

    if index_comp == "K4":
        
        # surf = ax.tricontourf(x_data,y_data ,z_data ,levels = [-1.5, -0.5, 0.5, 1.5],cmap='coolwarm',extend="both")
        surf = ax.contourf(Xi,Yi ,Zi ,levels = [-1.5, -0.5, 0.5, 1.5],cmap='coolwarm')
        # surf = ax.tripcolor(x_data,y_data ,z_data,shading='flat',cmap="coolwarm")
        cbar = fig.colorbar(surf, ax=ax, label=index_comp)
        cbar.set_ticks([-1,0,1])
        cbar.set_ticklabels(["Inférieur Référence","Indiscernable","Supérieur Référence"])
    
    else :
        levels = np.linspace(np.min(z_data), np.max(z_data), 10)
        surf = ax.contourf(Xi,Yi ,Zi ,levels = levels,cmap='coolwarm')
        cbar = fig.colorbar(surf, ax=ax, label=index_comp)


    # ax.scatter(x_data,y_data,c=z_data,cmap= "coolwarm")
    # ax.scatter(x_data,y_data,marker="+",linewidths=0.5,color = "black")
    # ax.scatter(X_valid,Y_valid,marker="+",linewidths=0.5,color = "black")
    ax.scatter(x_ref,y_ref,color = "goldenrod")

    # droites espace conception
    ax.contour(X, Y, cout_projet(X, Y, param_amenageur),
                levels=[param_amenageur["subvention"]], colors='blue', linewidths=2, linestyles='--')
    ax.contour(X, Y, emprise_projet(X, Y, param_amenageur),
                levels=[param_amenageur["aire_projet"]], colors='black', linewidths=2, linestyles='-')
    ax.annotate(f'Contrainte de coût',
                xy=(x_annot_cout, y_annot_cout), fontsize=11, color='blue',
                xytext=(10, -20), textcoords='offset points')

    ax.annotate(f'Contrainte physique',
                xy=(x_annot_emp, y_annot_emp), fontsize=11, color='black',
                xytext=(10, -20), textcoords='offset points')


    ax.set_xlabel('Surfaces logements collectifs')
    ax.set_ylabel('Surfaces bureaux')

    # ax.grid(True, alpha=0.2, color='white')


    ax.set_xlim(-50000,550000)
    ax.set_ylim(-300000,1500000)

    ax.spines['left'].set_position('zero')
    ax.spines['bottom'].set_position('zero')

    ax.spines['right'].set_color('none')
    ax.spines['top'].set_color('none')



    formatter = ScalarFormatter(useMathText=True)
    formatter.set_scientific(True)
    formatter.set_powerlimits((-3, 3))
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    ind_short = short_name_dict[ind]
    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.set_title(safe_name)
    ref_name = input_folder.split("/")[-1]
    plt.savefig(f"{FIGURES_DIR}/Pb_amenageur/pb_amenageur_{ind_short}_{index_comp}_{ref_name}.pdf",dpi=300,bbox_inches = "tight")
    plt.close()


def main() : 
    short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())
    param_amenageur = {
        "Ksol" : 349, # prix du m2 sol en euros
        "Klc" : 332, # charge foncière logement collectif en euros/m2SDP
        "Kbur" : 239, # charge foncière bureau en euros/m2SDP
        "Cep" : 350, # cout de construction espace public en euros/m2
        "Cequip" : 2500, # cout de construction équipement public en euros/m2SDP
        "Eep_lc" : 0.36, # ratio de m2 d'espace public par m2 de logements
        "Eequip_lc" : 0.05, # ratio de m2 d'équipement public par m2 de logements
        "Eep_bur" : 0.1, # ratio de m2 d'espace public par m2 de bureaux
        "Eequip_bur" : 0, # ratio de m2 d'équipement public par m2 de bureaux
        "Rlc" : 3, # m2SDP par m2 emprise au sol logement collectif
        "Rbur" : 5, # m2SDP par m2 emprise au sol bureau
        "Rep" : 1, # m2 par m2 emprise au sol esapce public
        "Requip" : 3, # m2SDP par m2 emprise au sol équipement public
        "aire_projet" : 350000,
        "subvention": 16741000,
        "part_route" : 0.5 # part des voiries dans l'espace public
    }

    input_folders = [
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Pb_amenageur/discern_central",
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Pb_amenageur/discern_lower_right"
        ]

    for input_folder in tqdm(input_folders,desc = " Dossiers resultats") :
            f = open(f"{input_folder}/ref_key.md", 'r') 
            ref_key = eval(f.read())

            with open(f"{input_folder}/discern_pb_amenageur.json", 'r') as f:
                res = json.load(f)

            indicators = list(res.keys())


            xy_ref = eval(ref_key)
            x_ref = xy_ref[0]
            y_ref = xy_ref[1]

            for ind in tqdm(indicators, desc="Indicateurs",leave=False) :
                for k in tqdm(["K","K2","K3","K4"], leave=False,desc="Indice de comparaison"):
                    plot_ki(res,k,ind,param_amenageur,x_ref,y_ref,short_name,input_folder)

       

    # ind_short = 

if __name__ == "__main__":
    main()
