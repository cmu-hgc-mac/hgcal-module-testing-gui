import glob
import os

<<<<<<< HEAD
name = 'CMU-LM3'
=======
name = 'TWL_022'
>>>>>>> ad72641b8b7560c93ab0ab588fe3ea272b5531d7
dirs = glob.glob('../hexactrl_output/*'+name+'*')
print(dirs)

os.system('mkdir data/'+name)

for d in dirs:
    runs = glob.glob(d+'/pedestal_run/*')

    for i in range(len(runs)):
        
        f = runs[i]+'/pedestal_run0.root'

        label = d.split('/')[2]+'_run'+str(i)
        print(f,label)
    
        os.system('python3 plot_summary.py {} -d data/{} -t LD -l {}'.format(f, name, label))
    
