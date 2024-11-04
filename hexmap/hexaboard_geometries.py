import os, sys, glob

import pandas as pd
import numpy as np
from argparse import ArgumentParser

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon, Rectangle
from matplotlib.collections import PatchCollection
from matplotlib.legend_handler import HandlerPatch

mpl.rcParams.update(mpl.rcParamsDefault)
font = {"size": 25}
mpl.rc("font", **font)
plt.rcParams['text.usetex'] = True

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

# To add the pad - channel and geometry mapping to the data DataFrame  
# df: pandas DataFrame with the data     
# hb_type: the type of the board ("LF" for LD Full, LR for LD Right, LL for LD Left, or "HF" for HD Full)    
def add_mapping(df, hb_type = "LF"):
    # create dataFrame clone to avoid conflict 
    df_data = df
    s = ""
    if not os.getcwd().endswith('hexmap'):
        s = 'hexmap/'
    # geometry mapping files' paths
    lf_board_geo = s + "geometries/hex_positions_HPK_198ch_8inch_edge_ring_testcap.txt" # full 
    lr_board_geo = s + "geometries/hex_positions_HPK_LR_8inch_edge_ring_testcap.txt" # right   
    ll_board_geo = s + "geometries/hex_positions_HPK_LL_8inch_edge_ring_testcap.txt" # left  
    l5_board_geo = s + "geometries/hex_positions_HPK_L5_8inch_edge_ring_testcap.txt" # five  
    hd_board_geo = s + "geometries/hex_positions_HPK_432ch_8inch_edge_ring_testcap.txt"
    hb_board_geo = s + "geometries/hex_positions_HPK_HB_8inch_edge_ring_testcap.txt"

    # pad - channel mapping files' paths 
    lf_board_chan = s + "channel_maps/ld_pad_to_channel_mapping_V3.csv" # full  
    lr_board_chan = s + "channel_maps/lr_pad_to_channel_mapping.csv" # right 
    ll_board_chan = s + "channel_maps/ll_pad_to_channel_mapping.csv" # left 
    l5_board_chan = s + "channel_maps/l5_pad_to_channel_mapping.csv" # five 
    hd_board_chan = s + "channel_maps/hd_pad_to_channel_mapping_V2p1.csv"
    hb_board_chan = s + "channel_maps/hb_pad_to_channel_mapping_Nov2024.csv"
    
    #import mapping files to pandas dataFrames and transform to python dicts
    if hb_type == "LF":
        chan_map_fname = lf_board_chan
        geo_fname = lf_board_geo
    elif hb_type == "HF":
        chan_map_fname = hd_board_chan
        geo_fname = hd_board_geo
    elif hb_type == "LR":
        chan_map_fname = lr_board_chan
        geo_fname = lr_board_geo
    elif hb_type == "LL":
        chan_map_fname = ll_board_chan
        geo_fname = ll_board_geo
    elif hb_type == "L5":
        chan_map_fname = l5_board_chan
        geo_fname = l5_board_geo
    elif hb_type == "HB":
        chan_map_fname = hb_board_chan
        geo_fname = hb_board_geo
        
    df_ch_map = pd.read_csv(chan_map_fname)
    d_ch_map = df_ch_map.set_index(["ASIC", "Channel", "Channeltype"]).to_dict()

    df_pad_map = pd.read_csv(geo_fname, skiprows= 7, delim_whitespace=True, names = ['padnumber', 'xposition', 'yposition', 'type', 'optional'])
    df_pad_map = df_pad_map[["padnumber","xposition","yposition"]].set_index("padnumber")
    d_pad_map = df_pad_map.to_dict()

    # add mapping to the data dataFrames 
    df_data["pad"] = df_data.apply(lambda x: get_pad_id(d_ch_map, x.chip, x.channel, x.channeltype), axis = 1)
    df_data["x"] = df_data["pad"].map(d_pad_map["xposition"])
    df_data["y"] = df_data["pad"].map(d_pad_map["yposition"])

    return df_data


# To mark asic (chip) places on the plot
# axes: the plt.Axes object with the plot
# hb_type: the type of the board ("LF" for low density or "HF" for high density)
def ad_chip_geo(ax, hb_type = "LF"):
    if hb_type == 'LR':
        #########################
        # LD Right board geometry and
        #    chip positions
        #           ____
        #           | 1 \
        #           |----\
        #           | 0  /
        #           |___/
        #
        ##########################

        # endpoints of line dividing chips 0 and 1
        x_01 = [-0.2, 5.3]
        y_01 = [1.3, 1.3]

        line_co = [(x_01, y_01)]

        # marker posisition, angle and annotation position, angle for chip0
        chip0_pos = (1.4, 2.3)      
        chip0_angle = 0.
        chip0_anno_pos = (5.0, -3.0)    
        chip0_anno_angle = 243

        # marker posisition, angle and annotation position, angle for chip1
        chip1_pos = (1.4, -3.25)
        chip1_angle = 0.
        chip1_anno_pos = (4.1, 2.95)
        chip1_anno_angle = -58

        # lists of chip positions, angles and annotation positions, angles
        chip_pos = [chip0_pos, chip1_pos]
        chip_angles = [chip0_angle, chip1_angle]
        chip_anno_pos = [chip0_anno_pos, chip1_anno_pos]
        chip_anno_angles = [chip0_anno_angle, chip1_anno_angle]

        # list of chip labels
        chip_labels = ['chip0', 'chip1']

    elif hb_type == 'LL':
        #########################
        # LD Left board geometry and
        #    chip positions
        #         ___   
        #        /   |  
        #       /  0 |    
        #       \----|    
        #        \_1_|   
        #
        ##########################

        # endpoints of line dividing chips 0 and 1
        x_01 = [-5.6, 0.2]
        y_01 = [-1.5, -1.5]

        line_co = [(x_01, y_01)]

        # marker posisition, angle and annotation position, angle for chip0
        chip0_pos = (-2.55, 1.05)      
        chip0_angle = 0.
        chip0_anno_pos = (-4.9, 2.8)
        chip0_anno_angle = 63
        # marker posisition, angle and annotation position, angle for chip1
        chip1_pos = (-2.95, -2.4)
        chip1_angle = 0.
        chip1_anno_pos = (-5.0, -4.1)
        chip1_anno_angle = -243

        # lists of chip positions, angles and annotation positions, angles
        chip_pos = [chip0_pos, chip1_pos]
        chip_angles = [chip0_angle, chip1_angle]
        chip_anno_pos = [chip0_anno_pos, chip1_anno_pos]
        chip_anno_angles = [chip0_anno_angle, chip1_anno_angle]

        # list of chip labels
        chip_labels = ['chip0', 'chip1']
        
    elif hb_type == "LF":
        #########################
        # LD Full board geometry and
        #    chip positions
        #         ______
        #        /  0  /\
        #       /_____/ 1\
        #       \  2  \  /
        #        \_____\/
        #
        ##########################

        # endpoints of line dividing chips 0 and 1
        x_01 = [0., 3.]     
        y_01 = [0., 5.]

        # endpoints of line dividing chips 0 and 2
        x_02 = [-5.5, 0.]
        y_02 = [0., 0.]

        # endpoints of line dividing chips 1 and 2
        x_12 = [0., 3.]     
        y_12 = [0., -5.6]

        # list of divider lines' endpoints
        line_co = [(x_01, y_01), (x_02, y_02), (x_12, y_12)]

        # marker posisition, angle and annotation position, angle for chip0
        chip0_pos = (-0.6, 2.45)      
        chip0_angle = 119.
        chip0_anno_pos = (-4.9, 2.8)    
        chip0_anno_angle = 63

        # marker posisition, angle and annotation position, angle for chip1
        chip1_pos = (2.6, -1.1)
        chip1_angle = 0.
        chip1_anno_pos = (4.15, 2.6)
        chip1_anno_angle = -58

        # marker posisition, angle and annotation position, angle for chip2
        chip2_pos = (-1.45, -3.8)
        chip2_angle = 59.
        chip2_anno_pos = (-0.7, -5.95)
        chip2_anno_angle = 0.0

        # lists of chip positions, angles and annotation positions, angles
        chip_pos = [chip0_pos, chip1_pos, chip2_pos]
        chip_angles = [chip0_angle, chip1_angle, chip2_angle]
        chip_anno_pos = [chip0_anno_pos, chip1_anno_pos, chip2_anno_pos]
        chip_anno_angles = [chip0_anno_angle, chip1_anno_angle, chip2_anno_angle]

        # list of chip labels
        chip_labels = ['chip0', 'chip1', 'chip2']

    elif hb_type == "HF":
        ########################
        # HF board geometry and
        #    chip positions
        #        ______
        #       / 0/ 1/\
        #      /__/__/\5\
        #      \__2__\4\/
        #       \__3__\/
        #
        #########################

        # endpoints of line dividing chips 1 and 4, 5
        x_145 = [0., 3.2]     
        y_145 = [0., 5.6]

        # endpoints of line dividing chips 2 and 0, 1
        x_201 = [-6.2, 0.]  
        y_201 = [0., 0.]

        # endpoints of line dividing chips 4 and 2, 3
        x_423 = [0., 3.]     
        y_423 = [0., -5.6]

        # endpoints of line dividing chips 0 and 1
        x_01 = [-3.1, 0.] 
        y_01 = [0., 5.6]

        # endpoints of line dividing chips 2 and 3
        x_23 = [-4.8, 1.5] 
        y_23 = [-2.9, -2.9]

        # endpoints of line dividing chips 4 and 5
        x_45 = [1.6, 4.8] 
        y_45 = [2.5, -3.1]

        # list of divider lines' endpoints
        line_co = [(x_145, y_145), (x_201, y_201), (x_423, y_423), (x_01, y_01), (x_23, y_23), (x_45, y_45)]

        # marker posisition, angle and annotation position, angle for chip0
        chip0_pos = (-3.2, 2.1)      
        chip0_angle = 60.
        chip0_anno_pos = (-1.9, 5.8)    
        chip0_anno_angle = 0.

        # marker posisition, angle and annotation position, angle for chip1
        chip1_pos = (-0.3, 1.8)      
        chip1_angle = 60.
        chip1_anno_pos = (1.2, 5.8)    
        chip1_anno_angle = 0.

        # marker posisition, angle and annotation position, angle for chip2
        chip2_pos = (-2.6, -1.6)      
        chip2_angle = 0.
        chip2_anno_pos = (-6.2, -2.1)    
        chip2_anno_angle = 120.

        # marker posisition, angle and annotation position, angle for chip3
        chip3_pos = (-1.5, -4.4)      
        chip3_angle = 0.
        chip3_anno_pos = (-4.55, -5.)    
        chip3_anno_angle = 120.

        # marker posisition, angle and annotation position, angle for chip4
        chip4_pos = (1.7, -0.8)      
        chip4_angle = -60.
        chip4_anno_pos = (3.8, -4.9)    
        chip4_anno_angle = -120.

        # marker posisition, angle and annotation position, angle for chip5
        chip5_pos = (3.4, 1.8)      
        chip5_angle = -60.
        chip5_anno_pos = (5.4, -2.1)    
        chip5_anno_angle = -120.

        # lists of chip positions, angles and annotation positions, angles
        chip_pos = [chip0_pos, chip1_pos, chip2_pos, chip3_pos, chip4_pos, chip5_pos]
        chip_angles = [chip0_angle, chip1_angle, chip2_angle, chip3_angle, chip4_angle, chip5_angle]
        chip_anno_pos = [chip0_anno_pos, chip1_anno_pos, chip2_anno_pos, chip3_anno_pos, chip4_anno_pos, 
                                                                                            chip5_anno_pos]
        chip_anno_angles = [chip0_anno_angle, chip1_anno_angle, chip2_anno_angle, chip3_anno_angle, 
                                                                        chip4_anno_angle, chip5_anno_angle]

        # list of chip labels 
        chip_labels = ['chip0', 'chip1', 'chip3', 'chip2', 'chip5', 'chip4']

    elif hb_type == "HB":
        ########################
        # HB board geometry and
        #    chip positions
        #       ________
        #      / 3 \ 1/ \
        #      \____\/ 0/
        #       \__2__\/
        #
        #########################

        # endpoints of line dividing chips 2 and 0
        x_20 = [1.5, 3.] 
        y_20 = [-2.9, -5.6]

        # endpoints of line dividing chips 3 and 1
        x_31 = [-1.65, -0.2]     
        y_31 = [-0.1, -2.9]

        # endpoints of line dividing chips 3 and 1
        x_31x = [-1.65, -1.05]     
        y_31x = [-0.1, 0.9]

        # endpoints of line dividing chips 2 and 3
        x_23 = [-4.8, 1.6] 
        y_23 = [-2.9, -2.9]

        # endpoints of line dividing chips 1 and 0
        x_10 = [1.6, 3.3] 
        y_10 = [-2.9, -0.2]

        # endpoints of line dividing chips 1 and 0
        x_10x = [3.3, 2.6] 
        y_10x = [-0.2, 1.]

        # list of divider lines' endpoints
        line_co = [(x_20, y_20), (x_31, y_31), (x_31x, y_31x), (x_23, y_23), (x_10, y_10), (x_10x, y_10x)]

        # marker posisition, angle and annotation position, angle for chip0
        chip0_pos = (4, -2.5)      
        chip0_angle = 60.
        chip0_anno_pos = (5.5, -2.)    
        chip0_anno_angle = 60.

        # marker posisition, angle and annotation position, angle for chip1
        chip1_pos = (0.3, -1.)      
        chip1_angle = 60.
        chip1_anno_pos = (0.4, 1.05)    
        chip1_anno_angle = 0.

        # marker posisition, angle and annotation position, angle for chip2
        chip2_pos = (-4., -0.8)      
        chip2_angle = 0.
        chip2_anno_pos = (-6.2, -2.1)    
        chip2_anno_angle = 120.

        # marker posisition, angle and annotation position, angle for chip3
        chip3_pos = (-2.0, -4.4)      
        chip3_angle = 0.
        chip3_anno_pos = (-4.55, -5.)    
        chip3_anno_angle = 120.

        # lists of chip positions, angles and annotation positions, angles
        chip_pos = [chip0_pos, chip1_pos, chip2_pos, chip3_pos]
        chip_angles = [chip0_angle, chip1_angle, chip2_angle, chip3_angle]
        chip_anno_pos = [chip0_anno_pos, chip1_anno_pos, chip2_anno_pos, chip3_anno_pos]
        chip_anno_angles = [chip0_anno_angle, chip1_anno_angle, chip2_anno_angle, chip3_anno_angle]

        # list of chip labels 
        chip_labels = ['chip0', 'chip1', 'chip2', 'chip3']

    # chip marker height/width
    if hb_type[0] == 'L':
        width = 1.2
        height = 1.4
    elif hb_type[0] == 'H':
        width = 1.1
        height = 0.5

    # divider line and chip marker, annotation color
    color = 'black'

    # plot the divider lines
    for co in line_co:
        x, y = co
        ax.plot(x, y, linestyle = 'dashed', linewidth = 4., color = color, alpha = 0.5)

    # plot the chip markers and annotation
    for chip_xy, chip_angle, chip_label, text_pos, text_angle in zip(chip_pos, chip_angles, 
                                                                    chip_labels, chip_anno_pos, chip_anno_angles):
        ax.add_patch(Rectangle(chip_xy, width = width, height = height, 
                    angle = chip_angle, fill = False, linewidth = 2, alpha = 0.8, color = color))
        ax.annotate(chip_label, text_pos, rotation = text_angle, fontsize = 18, alpha = 1., color = color)

    # create legend for chip position and add to plot
    chip_legend_handle = [Rectangle((0.,0.), width = 0.9, height = 0.6, fill = False, color = color, alpha = 1.)]
    chip_legend_label = ['chip position']
    chip_legend = ax.legend(chip_legend_handle, chip_legend_label, loc = 'upper left', fontsize = 'small')
    if len(chip_pos) != 0:
        ax.add_artist(chip_legend)
