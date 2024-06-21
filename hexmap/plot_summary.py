import os, sys, glob

import pandas as pd
import numpy as np
from argparse import ArgumentParser
import uproot3 as uproot
import math

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Rectangle
from matplotlib.collections import PatchCollection
from matplotlib.legend_handler import HandlerPatch
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)

try:
    from hexaboard_geometries import *
except ModuleNotFoundError:
    from hexmap.hexaboard_geometries import *

mpl.rcParams.update(mpl.rcParamsDefault)
font = {"size": 25}
mpl.rc("font", **font)
plt.rcParams['text.usetex'] = True

##### Mapping functions

# To get the pad number from the chip, channel number and channel type
# map_dict: a dictionary containing the pad - channel mapping from corresponding file
# chip: chip number
# chan: channel number
# chantype: channel type (0 for normal, 1 for calib or 100 for CM)
def get_pad_id(map_dict, chip, chan, chantype): 
    if (chip, chan, chantype) in map_dict["PAD"]:
        return map_dict["PAD"][(chip, chan, chantype)]
    else:
        return 0

##### Plotting functions

# To plot the patches
# df: pandas DataFrame with the data
# mask: a mask to select specific data from the dataframe (eg. df['channeltype'] == 0)
# data_type: the type of data corresponding to the mask ('norm' for normal, 'calib' for calib, 
#                                             'cm0' for CM of type 0, 'cm1' for CM of type 1 or 'nc' for not connected)
# hb_type: the type of the board ("LF" for low density or "HF" for high density)
def create_patches(df, mask, data_type, hb_type = "LF"):
    patches = []
    local_mask = mask.copy()
    r = 0.43
    if hb_type == "HF":
        r = 0.28
    for x, y in df.loc[local_mask, ["x", "y"]].values:
        angle = 0
        edgec = None
        if data_type == 'norm':
            ver = 6
            rad = r
        elif data_type == 'calib':
            ver = 6
            rad = 0.5 * r
            edgec = 'black'
        elif data_type == 'cm0':
            ver = 5
            rad = 0.75 * r
        elif data_type == 'cm1':
            ver = 4
            rad = 0.85 * r
            angle = np.radians(45)
        elif data_type == 'nc':
            ver = 100
            rad = 0.75 * r
        patch = RegularPolygon((x, y), numVertices = ver, radius = rad, orientation = angle, edgecolor = edgec, alpha = 0.9)
        patches.append(patch)
    return patches

# Classes to create the legend
class HandlerHexagon(HandlerPatch):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = RegularPolygon(xy=center, numVertices = 6, radius = 10, orientation=0, edgecolor = 'k')
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p]
class HandlerPentagon(HandlerPatch):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = RegularPolygon(xy=center, numVertices = 5, radius = 10, orientation=0)
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p] 
class HandlerSquare(HandlerPatch):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = RegularPolygon(xy=center, numVertices = 4, radius = 10, orientation=np.radians(45))
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p]
class HandlerCircle(HandlerPatch):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = RegularPolygon(xy=center, numVertices = 100, radius = 10, orientation=0)
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p]

# To add the channel type legend to the plot
# axes: the plt.Axes object with the plot
# hb_type: the type of the board ("LF" for low density or "HF" for high density)
def add_channel_legend(axes, hb_type = "LF"):
    hexagon = RegularPolygon((0.5, 0.5), numVertices = 6, radius = 10, orientation = 0, edgecolor = 'k')
    pentagon = RegularPolygon((0.5, 0.5), numVertices = 5, radius = 10, orientation = 0)
    square = RegularPolygon((0.5, 0.5), numVertices = 4, radius = 10, orientation = np.radians(45))
    circle = RegularPolygon((0.5, 0.5), numVertices = 100, radius = 10, orientation = 0)
    if hb_type == "LF" or hb_type == 'LR' or hb_type == 'LL':
        handles = [hexagon, pentagon, square, circle]
        labels = ['calib', 'CM0', 'CM1', 'NC']
    elif hb_type == "HF":
        handles = [hexagon, pentagon, square]
        labels = ['calib', 'CM0', 'CM1']
    
    patch_legend = axes.legend(handles, labels, loc = 'lower right', fontsize = 'small',
                               handler_map={hexagon: HandlerHexagon(), pentagon: HandlerPentagon(),
                                            square: HandlerSquare(), circle: HandlerCircle()})
    axes.add_artist(patch_legend)

def create_masks(df_data):

    # create the masks
    norm_mask = df_data["channeltype"] == 0
    norm_mask &= df_data["pad"] > 0

    calib_mask = df_data["channeltype"] == 1

    cm0_mask = df_data["channeltype"] == 100
    cm0_mask &= df_data["channel"] % 2 == 0

    cm1_mask = df_data["channeltype"] == 100
    cm1_mask &= df_data["channel"] % 2 == 1

    nc_mask = df_data["channeltype"] == 0
    nc_mask &= df_data["pad"] < 0

    return norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask
    
# To plot the ADC graphs from a pandas dataFrame containing the data
# # df: pandas DataFrame with the data
# figdir: the output directory for the plots
# hb_type: the type of the board ("LF" for low density or "HF" for high density)
# label: a label to put in the plot names
def plot_hexmaps(df, figdir = "./", hb_type = "LF", label = None, live = False):
    print(" >> Plotting hexmaps")
    df_data = df # create clone to avoid conflict

    # modify colormap to highlight extrema - red for top bin, gray for bottom
    try:
        cmap = mpl.colormaps['viridis']
    except AttributeError:
        cmap = mpl.cm.get_cmap('viridis', 400)
    try:
        red = np.array([[1., 0., 0., 1.]])
        gray = np.array([[0.35, 0.35, 0.35, 1.]])
        cmap.set_under(gray)
        cmap.set_over(red)
    except ValueError:
        red = np.array([1., 0., 0., 1.])
        gray = np.array([0.35, 0.35, 0.35, 1.])
        cmap.set_under(gray)
        cmap.set_over(red)

    norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask = create_masks(df_data)
    
    masks = [norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask]
    data_types = ['norm', 'calib', 'cm0', 'cm1', 'nc']

    #print(df_data.columns)
    for column in df_data.columns:
        
        if column != 'adc_mean' and column != 'adc_stdd':
            continue

        patches = []
        colors = np.array([])
        
        for mask, data_type in zip(masks, data_types):
            local_mask = mask.copy()
            local_mask &= df_data[column] >= 0
            patches += create_patches(df_data, local_mask, data_type, hb_type = hb_type)
            colors = np.concatenate((colors, df_data[local_mask][column].values))
            
        patch_col = PatchCollection(patches, cmap = cmap, match_original = True)
        patch_col.set_array(colors)

        upplim = 400. if column == 'adc_mean' or column == 'adc_median' else 8.
        patch_col.set_clim([0.001, upplim])

        # for live module if actual channels have same noise as disconnected channels, label
        med_nc = df_data[column][nc_mask].median()
        uncon = np.abs(df_data[column] - med_nc) < upplim/40.
        # not using for the moment because I'm unhappy with functionality
        # but will still print channel numbers
        
        # if actual channels have significantly higher noise than normal channels, label
        med_norm = df_data[column][norm_mask].median()
        mean_norm = df_data[column][norm_mask].mean()
        std_norm = df_data[column][norm_mask].std()
        noisy_limit = (2 if (column == 'adc_stdd' or column == 'adc_iqr') else 100)
        highval = (df_data[column] - med_norm) > noisy_limit
        # median + 2 adc counts as temporary check for high noise? we'll see how it goes

        # for all modules, label if zero or max value
        zeros = df_data[column] == 0
        maxes = df_data[column] >= upplim

        fig, ax = plt.subplots(figsize = (16,12))

        # label pads if on HB (pad is <0 if it's a common mode or non-connected channel)
        for x, y, pad in df.loc[(zeros | maxes) & (df_data['pad'] > 0), ["x", "y", "pad"]].values:
            ax.text(x-0.3, y-0.15, str(int(pad)), fontsize='small')
        if live and (column == 'adc_stdd' or column == 'adc_iqr'):

            for x, y, pad in df.loc[uncon & (df_data['pad'] > 0) & ~(calib_mask), ["x", "y", "pad"]].values:
                ax.text(x-0.3, y-0.15, str(int(pad)), fontsize='small')
            for x, y, pad in df.loc[highval & (df_data['pad'] > 0) & ~(calib_mask), ["x", "y", "pad"]].values:
                ax.text(x-0.3, y-0.15, str(int(pad)), fontsize='small')
            

        # mean noise information
        if (column == 'adc_stdd' or column == 'adc_iqr'):
            print(' >> Hexmap mean noise: col  norm  calib  cm0  cm1  nc')
            print('   ', column, np.mean(df_data[column][norm_mask]), np.mean(df_data[column][calib_mask]),
                  np.mean(df_data[column][cm0_mask]), np.mean(df_data[column][cm1_mask]), np.mean(df_data[column][nc_mask]))

        ax.add_collection(patch_col)
        ax.set_xlim([-7.274, +7.274])
        ax.set_ylim([-7.09, +7.09])

        # print summary info to plot
        ax.text(5, 6.5, r'$\mu = '+str(round(np.mean(df_data[column][norm_mask | calib_mask]), 2))+'$')
        ax.text(5, 6, r'$\sigma = '+str(round(np.std(df_data[column][norm_mask | calib_mask]), 2))+'$')            
        if (column == 'adc_stdd'):
            ax.text(-6.8, -5.8, 'Channels:')
            ax.text(-6.8, -6.3, f'{np.sum((zeros) & (df_data["pad"] > 0))} Dead')
            #ax.text(-6.8, -6.8, f'{np.sum(uncon & (df_data["pad"] > 0) & ~(calib_mask))} Unbonded')
            ax.text(-6.8, -6.8, f'{np.sum(highval & (df_data["pad"] > 0) & ~(calib_mask))} Noisy')
            
        zlab = 'Noise [ADC counts]' if column == 'adc_stdd' else 'Pedestal [ADC counts]'    
        cb = plt.colorbar(patch_col, label = zlab)#, extend='both', extendrect=True)

        # add red triangle to indicate values above max are red
        trixy = np.array([[0, 1], [1, 1], [0.5, 1.04]])
        pt = mpl.patches.Polygon(trixy, transform=cb.ax.transAxes, 
                             clip_on=False, edgecolor='k', linewidth=0.7, 
                             facecolor=red, zorder=4, snap=True)
        cb.ax.add_patch(pt)
        # add gray rectangle to indcate zero values are gray
        recty = np.array([[0, 0], [1, 0], [1, -0.04], [0, -0.04]])
        pr = mpl.patches.Polygon(recty, transform=cb.ax.transAxes, 
                             clip_on=False, edgecolor='k', linewidth=0.7, 
                             facecolor=gray, zorder=4, snap=True)
        cb.ax.add_patch(pr)
        cb.ax.text(11./8.*upplim, -0.18/8.*upplim, r'$0$', ha='center', va='center')
        
        # annotate chip positions on plot
        ad_chip_geo(ax, hb_type = hb_type)

        # add the legend
        add_channel_legend(ax, hb_type = hb_type)

        # add the title
        plt.title(label.replace('_', ' '))

        # save the figure
        figname = figdir + str(label) + "_" + column + ".png"
        plt.savefig(figname)
    return 1

def plot_channels(df, figdir = "./", hb_type = "LF", label = None, live = False):
    print(" >> Plotting channels in 1D")
    df_data = df # create clone to avoid conflict                                                                                                                                                       

    norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask = create_masks(df)
    cm_mask = cm0_mask | cm1_mask

    masks = [norm_mask, calib_mask, cm_mask, nc_mask]
    data_types = ['Si Pads', 'Calibration', 'Common Mode', 'Not Connected']
    colors = ['k', 'b', 'r', 'gray']

    for column in df_data.columns:

        if column != 'adc_mean' and column != 'adc_stdd':
            continue

        ylab = 'Noise [ADC counts]' if column == 'adc_stdd' else 'Pedestal [ADC counts]'
        upplim = 400. if column == 'adc_mean' or column == 'adc_median' else 8.

        chips = set(df_data.chip)
        nchips = len(chips)

        fig = plt.figure(figsize=(16, 4*nchips))
        gs = fig.add_gridspec(nchips, 1)

        ax = [fig.add_subplot(gs[0,0])]
        for i in range(1, nchips):
            ax.append(fig.add_subplot(gs[i,0], sharex=ax[0]))

        fig.subplots_adjust(hspace=0.)

        ax[0].set_xlim([np.min(df_data.channel), np.max(df_data.channel)])

        for i in range(nchips):
            ax[i].set_ylabel(ylab, fontsize=20)
            ax[i].set_ylim([0., upplim])
            ax[i].text(3, upplim*0.8, f'Chip {i}')
            ax[i].set_xticks(np.linspace(0, 70, 15))
            ax[i].grid(True)
            
            # print summary info to plot                                                                                                                                                    
            ax[i].text(60, upplim*0.8, r'$\mu = '+str(round(np.mean(df_data[column][norm_mask | calib_mask][df_data.chip == i]), 2))+'$')
            ax[i].text(60, upplim*0.7, r'$\sigma = '+str(round(np.std(df_data[column][norm_mask | calib_mask][df_data.chip == i]), 2))+'$')

            for mask, type, color in zip(masks, data_types, colors):
                ax[i].scatter(df_data.channel[df_data.chip == i][mask], df_data[column][df_data.chip == i][mask], color=color, label=type)

                above_plot = df_data[(df_data.chip == i) & (df_data[column] > upplim) & mask]
                ax[i].scatter(above_plot.channel, np.full_like(above_plot.channel, upplim*0.95, dtype=float), color=color, marker=r'$\uparrow$', s=160)

            if i != 0:
                yticks = ax[i].yaxis.get_major_ticks()
                yticks[-1].set_visible(False)
            if i != nchips - 1:
                ax[i].tick_params(labelbottom=False)

        try:
            ax[0].legend(loc=(0.16, 1.01), fontsize=20, ncols=4, columnspacing=0.3, handletextpad=0.1)
        except TypeError:
            ax[0].legend(loc=(0.16, 1.01), fontsize=20, ncol=4, columnspacing=0.3, handletextpad=0.1)
            
        ax[-1].set_xlabel('Channel Number')

        # add the title                                                                                                                                                                                     
        ax[0].set_title(label.replace('_', ' '), y=1.25)

        # save the figure                                                                                                                                                               
        figname = figdir + str(label) + "_" + column + "_channels.pdf"
        plt.savefig(figname)
    return 1

def plot_pads(df, figdir = "./", hb_type = "LF", label = None, live = False):
    print(" >> Plotting pads in 1D")
    df_data = df # create clone to avoid conflict                                                                                                                                                       

    norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask = create_masks(df)
    cm_mask = cm0_mask | cm1_mask

    masks = [norm_mask, calib_mask, cm_mask, nc_mask]
    data_types = ['Si Pads', 'Calibration', 'Common Mode', 'Not Connected']
    colors = ['k', 'b', 'r', 'gray']

    for column in df_data.columns:

        if column != 'adc_mean' and column != 'adc_stdd':
            continue

        ylab = 'Noise [ADC counts]' if column == 'adc_stdd' else 'Pedestal [ADC counts]'
        upplim = 400. if column == 'adc_mean' or column == 'adc_median' else 8.

        fig, ax = plt.subplots(figsize=(16, 12))
        
        ax.set_xlabel('Pad Number')
        ax.set_ylabel(ylab)
        ax.set_xlim([np.min(df_data['pad']), np.max(df_data['pad'])])
        ax.set_ylim([0., upplim])

        ax.xaxis.set_major_locator(MultipleLocator(50))
        ax.xaxis.set_minor_locator(MultipleLocator(5))
        ax.grid(which='both')
            
        # print summary info to plot                                                                                                                                                    
        xloc = (np.max(df_data['pad']) - np.min(df_data['pad']))*0.02 + np.min(df_data['pad'])
        ax.text(xloc, upplim*0.95, r'$\mu = '+str(round(np.mean(df_data[column][norm_mask | calib_mask]), 2))+'$')
        ax.text(xloc, upplim*0.9, r'$\sigma = '+str(round(np.std(df_data[column][norm_mask | calib_mask]), 2))+'$')

        for mask, type, color in zip(masks, data_types, colors):
            ax.scatter(df_data['pad'][mask], df_data[column][mask], color=color, label=type, s=10)

            above_plot = df_data[(df_data[column] > upplim) & mask]
            ax.scatter(above_plot['pad'], np.full_like(above_plot.channel, upplim*0.99, dtype=float), color=color, marker=r'$\uparrow$', s=160)

        ax.legend(loc='upper right')

        # add the title                                                                                                                                                                                     
        ax.set_title(label.replace('_', ' '))

        # save the figure                                                                                                                                                               
        figname = figdir + str(label) + "_" + column + "_pads.pdf"
        plt.savefig(figname)
    return 1

                
##### Main functions: read ROOT file, decode to pandas and pass to plotting

# To make the hexmap plots from summary file
# fname: summary file name (relative path) that contains the data
# figdir: the output directory for the plots
# hb_type: the type of the board ("LF" for low density or "HF" for high density)
# label: a label to put in the plot names
def make_hexmap_plots_from_file(fname, figdir = "./", hb_type = None, label = None):
    # fix label
    if label == None:
        label = os.path.basename(fname)
        label = label[:-5]

    if hb_type is None:
        moduleserial = fname.split('/')[-4]
        density = moduleserial.split('-')[1][1]
        shape = moduleserial.split('-')[2][0]
        hb_type = density+shape

        #print(moduleserial, hb_type)
    
    livemod = 'ML' in fname or 'MH' in fname
            
    # fix figdir
    if figdir == None:
        figdir = os.path.dirname(fname)
    if not figdir.endswith("/"):
        figdir += "/"
    
    print(">> Going to make plots for %s board from summary file %s into %s using label %s" %(hb_type, fname, figdir, label))

    # Open the hex data ".root" file and turn the contents into a pandas DataFrame.
    f = uproot.open(fname)
    try:
        tree = f["runsummary"]["summary"]
        df_data = tree.pandas.df()
    except:
        print(" -- No tree found!")
        return 0

    df_data = add_mapping(df_data, hb_type = hb_type)

    # do plots
    plot_hexmaps(df_data, figdir, hb_type, label, live=livemod)
    plot_channels(df_data, figdir, hb_type, label, live=livemod)
    plot_pads(df_data, figdir, hb_type, label, live=livemod)

    return 1

# simple function taking the dataFrame instead of filename to make the hexmap plots
# made for easier integration with pedestal_run_analysis
def make_hexmap_plots_from_df(df_data, figdir = "./", hb_type = "LF", label = None):
    # add mapping
    df_data = add_mapping(df_data, hb_type = hb_type)
    # do plots
    plot_hexmaps(df_data, figdir, hb_type, label)
    return 1

if __name__ == "__main__":

    parser = ArgumentParser()
    # parser arguments
    parser.add_argument("infname", type=str, help="Input summary file name")
    parser.add_argument("-d", "--figdir", type=str, default=None, help="Plot directory, if None (default), use same directory as input file")
    parser.add_argument("-t", "--hb_type", type=str, default=None, help="Hexaboard type", choices=["LF","LL","LR","HF"])
    parser.add_argument("-l", "--label", type=str, default=None, help="Label to use in plots")

    args = parser.parse_args()
    make_hexmap_plots_from_file(args.infname, args.figdir, args.hb_type, args.label)
