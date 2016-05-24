import os
import h5py
import bisect
import numpy as np
import pandas as pd

def iter_loadtxt(filename, delimiter='\t', skiprows=0, dtype=float):
    def iter_func():
        with open(filename, 'r') as infile:
            for _ in range(skiprows):
                next(infile)
            for line in infile:
                line = line.rstrip().split(delimiter)
                for item in line:
                    yield dtype(item)
        iter_loadtxt.rowlength = len(line)
    data = np.fromiter(iter_func(), dtype=dtype)
    data = data.reshape((-1, iter_loadtxt.rowlength))
    return data

def tie_data_map(d_set, m_set, name, axis=0):
    d_set.dims[axis].label = name
    d_set.dims.create_scale(m_set, name)
    d_set.dims[axis].attach_scale(m_set)

def read_analog(full_path, field_name, end_time, all_pops, h):
    print 'Assumes recording at every 0.1ms'
    cell_range = [0,1000,1050,1140,1230,1320,1560,2360,2560,3060,3160,3260,3360,3460,3560]
    pop_names = ['pyrRS23','pyrFRB23','bask23','axax23','LTS23', 
                 'spinste14', 'tuftIB5', 'tuftRS5', 'nontuftRS6', 
                 'bask56', 'axax56', 'LTS56', 'TCR', 'nRT']
    num_cmpts = [74, 74, 59, 59, 59, 59, 61, 61, 50, 59, 59, 59, 137, 59]
    for pop_idx in all_pops: #each population do
        num_cells = cell_range[pop_idx+1] - cell_range[pop_idx] 
        cmpts_per_cell = num_cmpts[pop_idx]
        duh_ = 0 #counter to keep track of cells
        unique_names = []
        d_set = h.create_dataset('/data/uniform/'+ pop_names[pop_idx]+ '/'+field_name, 
                                 shape=(num_cells*cmpts_per_cell,int(end_time*10)), dtype=np.float32)
        for cell_idx in range(cell_range[pop_idx], cell_range[pop_idx+1]): #each cell do
            filename = os.path.join(full_path, str(cell_idx)+'.dat')
            print cell_idx , ' of population ', pop_names[pop_idx] 
            #arr = pd.read_csv(filename, sep='\t',names=[field_name], usecols=[4],nrows=cmpts_per_cell*int(end_time*10))
            arr = pd.read_csv(filename, sep='\t',names=[field_name], nrows=cmpts_per_cell*int(end_time*10))
            d_set[duh_*cmpts_per_cell:(duh_+1)*cmpts_per_cell, :] = arr.values.reshape(int(end_time*10), cmpts_per_cell).T
            for compt_n in range(cmpts_per_cell): #generating names for compartments
               unique_names.append(str(cell_idx)+'/'+str(compt_n+1))
            duh_ += 1
        if field_name == 'i':
            m_dset = h.create_dataset('/map/uniform/'+ pop_names[pop_idx]+ '_names', data=unique_names)
            tie_data_map(d_set, m_dset, 'source', 0) #adding DS attributes
        elif field_name == 'v':
            m_dset = h['/map/uniform/'+pop_names[pop_idx]+'_names'] #Always currents  are added first
            tie_data_map(d_set, m_dset, 'source', 0) #adding DS attributes
        print 'Done population : ', pop_idx
    print 'Done analog reading', filename
    return h

def read_digital(filename, fieldname, tmax, all_pops, h):
    cell_range = [0,1000,1050,1140,1230,1320,1560,2360,2560,3060,3160,3260,3360,3460,3560]
    pop_names = ['pyrRS23','pyrFRB23','bask23','axax23','LTS23', 
                 'spinste14', 'tuftIB5', 'tuftRS5', 'nontuftRS6', 
                 'bask56', 'axax56', 'LTS56', 'TCR', 'nRT']
    arr = pd.read_csv(filename, sep='\t', names=['times','cells'])
    u_cells = arr.cells.unique()  #get names of cells that fired
    pop_cell_dict = {} #dict of dict
    for cell_name in u_cells:
        pop_idx = bisect.bisect(cell_range, cell_name) - 1
        if pop_idx in all_pops: #only those populations of interest
            pop_name = pop_names[pop_idx]
            try:
                pop_cell_dict[pop_name][cell_name] = arr[(arr.cells == cell_name) & (arr.times <= tmax)].times.values
            except KeyError:
                pop_cell_dict[pop_name] = {cell_name:arr[(arr.cells == cell_name) & (arr.times <= tmax)].times.values}
    if fieldname.find('output') != -1: 
        var_name = 'spikes'
    else:
        var_name = 'spikes_in'
    for pop_name,cell_dicts in pop_cell_dict.iteritems(): #flush them into hdf5
        ii = '/data/event/'+pop_name+'/'+var_name
        e_dset = h.create_dataset(ii, dtype=h5py.special_dtype(vlen='float32'), shape=(len(cell_dicts),))
        e_dset[:] = data=cell_dicts.values() #h5py BUG! here, let people know!
        jj = '/map/event/'+pop_name+'_'+var_name
        m_dset = h.create_dataset(jj, data=cell_dicts.keys())
        tie_data_map(e_dset, m_dset, 'source', 0) #adding DS attributes
    print 'Done', filename
    return h

def attach_to_all_under(h, variable_name, mset):
    for pop_ii in h['/data/'+variable_name].values():
        for d_set in pop_ii.values():
            tie_data_map(d_set, mset, 'time', axis=1)

def add_time(h, t_max, t_step):
    #time = np.arange(0, t_max, t_step)
    time = np.linspace(0, t_max, t_max/t_step, endpoint=False)
    dset_time = h.create_dataset('/map/common/time', data=time)
    attach_to_all_under(h, 'uniform', dset_time)
    print 'Attached time DS'

if __name__ == '__main__':
    h = h5py.File('traub_50_common.h5', 'a')
    t_max = 50.0 #total_time
    t_step = 0.1 #ms
    #all_pops = range(14) #list of populations to consider [1,2] if only population 1_out, and 2_out
    all_pops = [0,2,8]
    path_folder = '/home/cchintaluri/hela_data'
    log_filename = 'log2014042810:46:30.txt'

    #processing currents
    currents_path = os.path.join(path_folder, 'i','tmp')
    currents_name = 'i'
    h = read_analog(currents_path, currents_name, t_max, all_pops, h)
    print 'Done processing all currents'

    #processing potentials
    voltage_path = os.path.join(path_folder, 'v','tmp')
    voltage_name = 'v'
    h = read_analog(voltage_path, voltage_name, t_max, all_pops, h)
    print 'Done processing all voltages'

    #processing input spike data
    spike_path = os.path.join(path_folder, 'input.dat')
    spike_name = 'input_spikes'
    h = read_digital(spike_path, spike_name, t_max, all_pops, h)
    print 'Done processing all input spikes'
    
    #processing output spike data
    spike_path = os.path.join(path_folder, 'output.dat')
    spike_name = 'output_spikes'
    h = read_digital(spike_path, spike_name, t_max, all_pops, h)
    print 'Done processing all output spikes'

    #processing log information
    log_file = os.path.join(path_folder, log_filename)
    f = open(log_file, 'r')
    str_type = h5py.new_vlen(str)
    ds = h.create_dataset('/model/filecontents/log.txt', data=f.readlines(), dtype=str_type)
    f.close()

    # #process time data
    add_time(h, t_max, t_step)

    h.close()