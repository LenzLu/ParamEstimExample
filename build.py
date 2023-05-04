import os, sys
import pymake 
import flopy
import gsflow

def build_all(apps = ["mf2005"], path="bin", rebuild=False, verbose=True):
    if not os.path.isdir(path):
        os.mkdir(path)
    
    for app in apps:
        app_path = os.path.join(path, app)
        if sys.platform.startswith("win"): 
            app_path += ".exe"
        
        # Build, clean and store binary
        if rebuild or not os.path.isfile(app_path):
            pymake.build_apps(app, verbose=verbose)
            os.rmdir("temp")
            os.rename(os.path.split(app_path)[-1], app_path)
        
        assert os.path.isfile(app_path), f"{app} was not found in '{app_path}'."
    
def print_version_info():    
    print(f'Kernel version: {sys.version}')
    print(f'numpy version: {np.__version__}')        
    print(f'flopy version: {flopy.__version__}')    
    print(f'gsflow version: {gsflow.__version__}')


if __name__ == "__main__":
    print_version_info()
    
    print("Building modflow...")
    build_all(["mf2005"], verbose=False)
