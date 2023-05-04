import sys, os
from time import time as get_time
from threading import Thread
import numpy as np
import flopy
import pymake
import umbridge as um 

def setup_mf_package(name : str, app="mf2005", workspace="mf", exedir="bin", clear=True, verbose=True):
    
    # Executable file path
    exe_nm = os.path.join(os.getcwd(), exedir, app)
    if sys.platform.startswith("win"): 
        exe_nm = exe_nm + ".exe"
    
    # Create empty model working space folder   
    if clear and os.path.isdir(workspace):
        for f in os.listdir(workspace):
            os.remove(os.path.join(workspace,f))
        os.rmdir(workspace)
    if not os.path.isdir(workspace): 
        os.mkdir(workspace)
    
    mf = flopy.modflow.Modflow(model_name=name, version=app, exe_name=exe_nm, model_ws=workspace)
    return mf



#==========================================================================================================#
# Entire input parameter configuration for simulation                        ### TODO: Move to YAML file 
config = dict(
    meta = dict(
        name = "layprops", # guessing layer properties
        params = [
            "layers.conductivity", 
            "layers.storage",
            "precipitation.avg_recharge"
        ]
        
        ## TODO: distribution of parameters 
    ),
    domain = dict(
        lengths   = [1000, 1000],  # in meters
        ztop      = 900,           # in meters (above sea level)

        divisions = [  32,   32],  # discretization (Finite Difference grid) 

    ), 
    timestepping = dict(
        # Time Stepping
        n_periods = 8,
        n_steps = 2,
        period_length = 365, # in days
        steady = False 
    ),
    layers = dict(
        material     = ["soil","saprolite","fractured bedrock"],
        thickness    = [   40,         30,                120 ],
        conductivity = [ 8.64,       0.864,            0.00864], #hk in meters per day
        storage      = [ 1E-1,        1E-3,               1E-4], 
        laytype      = [    1,           0,                  0]  #confined (0) / unconfined (1)
    ),
    precipitation = dict(
        avg_recharge = 120, # in mm per year
    )
)


#==========================================================================================================#


# Pick out optimization parameters from config file (eg. for estimation)
def pick_out_params(config):
    params = []; size = []
    param_names = config["meta"]["params"]
    for name in param_names:
        code = "config" + "".join([ f"['{key}']" for key in name.split(".") ])
        value = eval(code)
        params.append(value)
        size.append(len(value))
    return params, size
    


#----------------------------------------------------------------------------------------------------------#
# Generate input files for Modflow 
def write_inputs(params):
    mf = setup_mf_package(params["meta"]["name"])
   
    # DIS package (space and time discretization)
    L = params["domain"]["lengths"]
    n = params["domain"]["divisions"]
    thickness = np.asarray(params["layers"]["thickness"])
    zbot = params["domain"]["ztop"] - np.cumsum(thickness)
    mf_dis = flopy.modflow.ModflowDis(mf, 
        zbot.shape[0], n[0], n[1], 
        nper = params["timestepping"]["n_periods"], 
        nstp = params["timestepping"]["n_steps"], 
        perlen = params["timestepping"]["period_length"], 
        steady = [params["timestepping"]["steady"]],
        delr = L[0]/n[0], delc = L[1]/n[1], top = params["domain"]["ztop"], botm = zbot
    )

    # BAS package (basin definition)
    boundary = np.zeros(n, dtype=np.int32)
    initial = params["domain"]["ztop"] * np.ones((zbot.shape[0], *n))
    print(initial)
    mf_bas = flopy.modflow.ModflowBas(mf, ibound=boundary, strt=initial)


    # LPF package (layer property format)
    hk = np.asarray(params["layers"]["conductivity"])
    ss = np.asarray(params["layers"]["storage"])
    laytype = np.asarray(params["layers"]["laytype"])
    #hk = hk * (1 + np.random.normal(hk.shape)*1e-3 )
    mf_upw = flopy.modflow.ModflowLpf(mf, ipakcb = 1, laytyp = laytype, hk = hk , ss = ss)

    # PCG package (precondictioned conjugate gradient solver)
    mf_pcg = flopy.modflow.ModflowPcg(mf)

    # OC package (output control)
    spd = {}
    for i in range((params["timestepping"]["n_periods"])):
        for j in range((params["timestepping"]["n_steps"])):
            spd[(i,j)] = ['print head', 'print budget', 'save head', 'save budget']
    mf_oc = flopy.modflow.ModflowOc(mf, stress_period_data=spd, compact=True)

    # RCH package (
    recharge = {0: np.ones(n, dtype=np.float32) * params["precipitation"]["avg_recharge"]/365 }
    mf_rch = flopy.modflow.ModflowRch(mf, ipakcb=1, nrchop=3, rech = recharge)

    # Write to simulation folder
    mf.write_input() 
    print("Packages written : ", ", ".join([os.path.splitext(f)[-1] for f in os.listdir(mf.model_ws)]))
    
    return mf
#----------------------------------------------------------------------------------------------------------#




def run_models(models, verbose=True):
    
    # Wrapper for running model 
    def _run_model(i):
        mf = models[i]
        success, out = mf.run_model(silent=True, pause=False, report=False)
        if not success:
            print(out)
            raise Exception(f'MODFLOW instance of model "{mf.name}" did not terminate normally.') 
     
    # init threads
    threads = []
    for i in range(len(models)):
        thread = Thread(target=_run_model, args=(i,))
        threads.append(thread)
    
    # start and join threads
    t0 = get_time()
    if verbose: print("Starting threads.")
    for i in range(len(models)):
        threads[i].start()
    for i in range(len(models)):
        threads[i].join()
    t1 = get_time()
    if verbose: print("Finished ensemble simulation in ", t1-t0, " seconds.") 
    


def collect_outputs(model):
    heads = os.path.join( model.model_ws, model.name + ".hds" )
    heads = flopy.utils.binaryfile.HeadFile(heads)
    cbb = os.path.join( model.model_ws, model.name + ".cbc" )
    cbb = flopy.utils.binaryfile.CellBudgetFile(cbb)
    
    times = heads.get_times()
    end_time = times[-1]
    
    heads = heads.get_data(totim=end_time)
    budget = np.sum(heads)
    
    return budget
        
class Simulation(um.Model):
    def __init__(self):
        super().__init__("forward")
                
        # TODO: assert that modflow binary exists
    
    def get_input_sizes(self, config):
        _, size = pick_out_params(config)
        return size

    def get_output_sizes(self, config):
        return [1]

    def __call__(self, config):
        params, _ = pick_out_params(config)
        
        mf = write_inputs(config)
        run_models([mf])
        
        return collect_outputs(mf)
        
        
        
    def supports_evaluate(self):
        return True

    def supports_gradient(self):
        return False


if __name__ == "__main__":
   #testmodel = Simulation()
   #print("Inputs  ", testmodel.get_input_sizes(config))
   #print("Outputs ", testmodel.get_output_sizes(config))
   #out = testmodel(config)
   #print(out)
  

   model = Simulation()
   umbridge.serve_models([model], 4242)

