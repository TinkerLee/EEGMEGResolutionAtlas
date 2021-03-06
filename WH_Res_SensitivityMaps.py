"""
=========================================================
Compute whole-brain sensitivity maps for WH data set.
E.g.: run WH_Res_SensitivityMaps.py WH_Res_config 13 RMS
=========================================================

"""
# OH, July 2018

print __doc__

import os
import os.path as op

import sys
sys.path = [
 '/home/olaf/MEG/WakemanHensonEMEG/ScriptsResolution', # following list created by trial and error
 '/imaging/local/software/mne_python/latest_v0.16',
 '/imaging/local/software/anaconda/2.4.1/2/bin',
 '/imaging/local/software/anaconda/2.4.1/2/lib/python2.7/',
 '/imaging/local/software/anaconda/2.4.1/2/envs/mayavi_env/lib/python2.7/site-packages',
 '/imaging/local/software/anaconda/2.4.1/2/envs/mayavi_env/lib/python2.7/site-packages/pysurfer-0.8.dev0-py2.7.egg',
 '/imaging/local/software/anaconda/2.4.1/2/lib/python2.7/site-packages/h5io-0.1.dev0-py2.7.egg',
 '/imaging/local/software/anaconda/2.4.1/2/lib/python2.7/lib-dynload',
 '/imaging/local/software/anaconda/2.4.1/2/lib/python2.7/site-packages'
 ]

import importlib
import glob

import numpy as np

import mne
print('MNE Version: %s\n\n' % mne.__version__) # just in case

## get analysis parameters from config file

module_name = sys.argv[1]

C = importlib.import_module(module_name)
reload(C)

# get functions for metrics etc.
R = importlib.import_module('WH_Resolution_Functions')
reload(R)

# get subject ID to process
# qsub start at 0, thus +1 here
sbj_ids = [int(sys.argv[2]) + 1]

# for filenames
st_duration = C.res_st_duration
origin = C.res_origin

# read variables specified via qsub
if len(sys.argv)>3: # if additional variable specified

    metric = sys.argv[3] # (e.g. 'RMS', 'SNR')

else:

    metric = 'RMS'

print('Metric: %s.\n' % metric)


for sbj in sbj_ids:

    subject = 'Sub%02d' % sbj

    print('###\nWorking hard on %s.\n###' % (subject))

    fname_stc = C.fname_STC(C, 'SensitivityMaps', subject, '')

    # create output path if necessary
    if not os.path.exists(fname_stc):

        os.mkdir(fname_stc)


    fwd_fname = C.fname_ForwardSolution(C, subject, 'EEGMEG')

    print('###\nReading EEGMEG forward solutions: %s .\n###' % (fwd_fname))

    fwd = mne.read_forward_solution(fwd_fname)

    fwd = mne.convert_forward_solution(fwd, surf_ori=True, force_fixed=True)

    # covariance matrix (filter with wildcard)
    fname_cov = C.fname_cov(C, subject, st_duration, origin, C.res_cov_latwin, C.inv_cov_method, '*')

    # method may be underspecified, since it may be ranked differently for different subjects
    fname_cov = glob.glob(fname_cov)[0] # be careful if multiple options present

    print('###\nReading noise covariance matrix from: %s.\n###' % (fname_cov))

    noise_cov = mne.read_cov(fname_cov)

    stcs = {} # will contain metric distribution as STC

    # iterate over different combinations of sensors
    for (eeg,meg,modal) in [(True,True,'EEGMEG'), (False,True,'MEG'), (True,False,'EEG')]:

        fwd_use = mne.pick_types_forward(fwd, meg=meg, eeg=eeg)

        info = fwd_use['info']
        ch_names = info['ch_names']

        # restrict to channels in forward solution
        noise_cov_use = mne.cov.pick_channels_cov(noise_cov, ch_names)

        # fwd doesn't have projs, add from noise_cov
        info['projs'] = noise_cov_use['projs']
        info['comps'] = '' # dummy to avoid crash

        if C.inv_cov_method == 'empirical': # if unregularised

            noise_cov_use = mne.cov.regularize(noise_cov_use, info, mag=C.res_lambda_empirical['mag'],
                                                    grad=C.res_lambda_empirical['grad'], eeg=C.res_lambda_empirical['eeg'])
        
        # Sensitivity maps with diagnonal noise covariance matrix
        stc = R.sensitivity_map(fwd_use, noise_cov_use, diag=True, metric=metric, maxnorm=True)

        stcs[modal] = stc

        fname_stc = C.fname_STC(C, 'SensitivityMaps', subject, 'SensMap_' + modal + '_' + metric)

        print('###\nWriting STC file to: %s.\n###' % (fname_stc))

        stc.save(fname_stc)

    print('###\nContrasting modalities.\n###')

    for (modal1,modal2) in [('EEGMEG', 'MEG'), ('EEGMEG', 'EEG'), ('MEG','EEG')]:

        if metric == 'RMS':
            
            print('Ratio for RMS.')
            stc_contr = stcs[modal1] / stcs[modal2]

        elif metric == 'SNR':

            print('Difference for SNR.')
            stc_contr = stcs[modal1] - stcs[modal2]

        # stc_diff = R.normalise_stc(stc_diff)

        mytext = modal1 + '-' + modal2 + '_' + metric

        stcs[mytext] = stc_contr

        fname_stc = C.fname_STC(C, 'SensitivityMaps', subject, 'SensMap_' + mytext)

        print('Saving STC to: %s.' % fname_stc)

        stc_contr.save(fname_stc)


    ### Visualisation:

    # clim = {'kind': 'value', 'pos_lims': (0, 0.5, 1)}

    # stc_norm['EEGMEG-MEG'].plot(subject=subject, subjects_dir=C.subjects_dir, hemi='both',
    #                         time_viewer=True, transparent=False, colormap='mne', clim=clim)


# Done