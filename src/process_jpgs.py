# -*- coding: utf-8 -*-
"""
Created on Tue Sep 10 22:19:23 2019

@author: phill
"""

from skimage import io
from skimage import color
from skimage import exposure
from skimage import feature
from skimage import restoration
from skimage import transform
from skimage import morphology

import numpy as np
import matplotlib.pyplot as plt
import os

def process_image(img_file):
    
    print("Process", img_file)
    
    img = io.imread(img_file)
    
    # Trim the edge of the page off
    img = img[100:-300, 30:-30, :]
    
    # Increase the contrast of the image to more easily find the black lines
    img = exposure.equalize_hist(img)

    cutoff = 0.18
    img[img < cutoff] = 0.0
    
    # If any channels are above zero, consider it a white pixel
    for i in range(img.shape[2]):
        img[:,:,i] = img[:,:,0] + img[:,:,1] + img[:,:,2]
    
    img[img > 0.0] = 1.0

    masked_img = np.ones((img.shape[0],img.shape[1]))
    avg_img = np.average(img, axis=2)
    masked_img[avg_img == 1.0] = 0.0
    
    # Rotate image
    lines = transform.probabilistic_hough_line(masked_img, threshold=100, 
                                               line_length=400, line_gap=1)
    
    angles = []
    for line in lines:
        p0, p1 = line
        next_angle = np.rad2deg(np.arctan2(p1[1] - p0[1], p1[0] - p0[0]))
        if abs(next_angle) < 15.0:
            angles.append(next_angle)
        
    if len(angles) > 0 and sum(angles) > 0:
        rotation_angle = sum(angles)/len(angles)
        img = transform.rotate(img, rotation_angle)
        img = img[5:-5, 5:-5, :]
    
    fpath, fname = os.path.split(img_file)
    fname = fname[:-4] + '.tif'
    img = img.astype('uint8')*255
    io.imsave(os.path.join(fpath, fname), img)
    
    fname = fname[:-4]+'_lav.tif'
    for i in range(img.shape[0]):
        for j in range(img.shape[1]):
            if img[i,j,0] == 0:
                img[i,j,0] = 115
                img[i,j,1] = 79
                img[i,j,2] = 150
    io.imsave(os.path.join(fpath, fname), img)                

    return

if __name__ == '__main__':
    
    directory = 'C:\\Users\\phill\\Dropbox\\Ziapelta Games\\Games\\Lavender Hack\\pg'
    
    for filename in os.listdir(directory):
        if filename.endswith(".jpg") or filename.endswith(".JPG"):
            process_image(os.path.join(directory, filename))
        else:
            continue