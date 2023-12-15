#! /usr/bin/env python3

""" tiling_images.py
script created to tile big images into smaller ones with annotations that can then be trained on via a yolo model
"""

############## NOTE ##############################
# Has been superseeded by test_sahi.py which is a better way of doing this (see code in the splitting images sections)
# still works, but has a few bugs, and is not as good as the sahi code (though sahi code needs coco annotations not yolo annotations)

import os
import numpy as np
import cv2 as cv
import glob
from PIL import Image
from shapely.geometry import Polygon, box, MultiPolygon, GeometryCollection
from shapely.validation import explain_validity


classes = ["recruit_live_white", "recruit_cluster_live_white", "recruit_symbiotic", "recruit_symbiotic_cluster", "recruit_partial",
           "recruit_cluster_partial", "recruit_dead", "recruit_cluster_dead", "grazer_snail", "pest_tubeworm", "unknown"]
orange = [255, 128, 0] 
blue = [0, 212, 255] 
purple = [170, 0, 255] 
yellow = [255, 255, 0] 
brown = [144, 65, 2] 
green = [0, 255, 00] 
red = [255, 0, 0]
cyan = [0, 255, 255]
dark_purple =  [128, 0, 128]
light_grey =  [192, 192, 192] 
dark_green = [0, 100, 0] 
class_colours = {classes[0]: blue,
                classes[1]: green,
                classes[2]: purple,
                classes[3]: yellow,
                classes[4]: brown,
                classes[5]: cyan,
                classes[6]: orange,
                classes[7]: red,
                classes[8]: dark_purple,
                classes[9]: light_grey,
                classes[10]: dark_green}

TILE_WIDTH= 640
TILE_HEIGHT = 640
TRUNCATE_PERCENT = 0.1
TILE_OVERLAP = round((TILE_HEIGHT+TILE_WIDTH)/2 * TRUNCATE_PERCENT)

full_res_dir = '/home/java/Java/data/cgras_20230421/train'
save_path = '/home/java/Java/data/cgras_20230421/tilling'
save_train = os.path.join(save_path, 'train')
save_img = os.path.join(save_train, 'images')
save_labels = os.path.join(save_train, 'labels')
os.makedirs(save_path, exist_ok=True)
os.makedirs(save_train, exist_ok=True)
os.makedirs(save_img, exist_ok=True)
os.makedirs(save_labels, exist_ok=True)


def is_mostly_contained(polygon, x_start, x_end, y_start, y_end, threshold):
    """Returns true if a Shaply polygon has more then threshold percent in the area of a specified bounding box."""
    polygon_box = box(*polygon.bounds)
    tile_box = box(x_start, y_start, x_end, y_end)
    if not polygon.is_valid:
        explanation = explain_validity(polygon)
        print(f"Invalid Polygon: {explanation} at {x_start}_{y_start}")
        return False
    if not polygon_box.intersects(tile_box):
        return False
    intersection = polygon.intersection(tile_box)
    return intersection.area > (threshold * polygon.area)

def truncate_polygon(polygon, x_start, x_end, y_start, y_end):
    """Returns a polygon with points constrained to a specified bounding box."""
    tile_box = box(x_start, y_start, x_end, y_end)
    intersection = polygon.intersection(tile_box)
    return intersection

def create_polygon_unnormalised(parts, img_width, img_height):
    """Creates a Polygon from unnormalized part coordinates, as [class_ix, xn, yn ...]"""
    xy_coords = [round(float(p) * img_width) if i % 2 else round(float(p) * img_height) for i, p in enumerate(parts[1:], start=1)]
    polygon_coords = [(xy_coords[i], xy_coords[i + 1]) for i in range(0, len(xy_coords), 2)]
    polygon = Polygon(polygon_coords)
    return polygon

def normalise_polygon(truncated_polygon, class_number, x_start, x_end, y_start, y_end, width, height):
    """Normalize coordinates of a polygon with respect to a specified bounding box."""
    points = []
    if isinstance(truncated_polygon, Polygon):
        x_coords, y_coords = truncated_polygon.exterior.coords.xy
        xy = [class_number]

        for c, d in zip(x_coords, y_coords):
            x_val = 1.0 if c == x_end else (c - x_start) / width
            y_val = 1.0 if d == y_end else (d - y_start) / height
            xy.extend([x_val, y_val])

        points.append(xy)
        
    elif isinstance(truncated_polygon, (MultiPolygon, GeometryCollection)):
        for p in truncated_polygon.geoms:
            points.append(normalise_polygon(p, class_number, x_start, x_end, y_start, y_end, width, height))
    return points

def cut_n_save_img(x_start, x_end, y_start, y_end, np_img, img_save_path):
    """Save a tile section of an image given by a bounding box"""
    cut_tile = np.zeros(shape=(TILE_WIDTH, TILE_HEIGHT, 3), dtype=np.uint8)
    cut_tile[0:TILE_HEIGHT, 0:TILE_WIDTH, :] = np_img[y_start:y_end, x_start:x_end, :]
    cut_tile_img = Image.fromarray(cut_tile)
    cut_tile_img.save(img_save_path)

def cut_annotation(x_start, x_end, y_start, y_end, lines, imgw, imgh):
    """From lines in annotation file, find objects in the bounding box and return the renormalised xy points if there are any"""
    writeline = []
    for line in lines:
        parts = line.split()
        class_number = int(parts[0])
        polygon = create_polygon_unnormalised(parts, imgw, imgh)

        if is_mostly_contained(polygon, x_start, x_end, y_start, y_end, TRUNCATE_PERCENT):
            truncated_polygon = truncate_polygon(polygon, x_start, x_end, y_start, y_end)
            xyn = normalise_polygon(truncated_polygon, class_number, x_start, x_end, y_start, y_end, TILE_WIDTH, TILE_HEIGHT)
            writeline.append(xyn)
    return writeline


#cut the image
def cut(img_name, save_img, test_name, save_labels, txt_name):
    """Cut a image into tiles, save the annotations renormalised"""
    pil_img = Image.open(img_name, mode='r')
    np_img = np.array(pil_img, dtype=np.uint8)
    img = cv.imread(img_name)
    imgw, imgh = img.shape[1], img.shape[0]
    # Count number of sections to make
    x_tiles = (imgw + TILE_WIDTH - TILE_OVERLAP - 1) // (TILE_WIDTH - TILE_OVERLAP)
    y_tiles = (imgh + TILE_HEIGHT - TILE_OVERLAP - 1) // (TILE_HEIGHT - TILE_OVERLAP)
    for x in range(x_tiles):
        for y in range(y_tiles):
            x_end = min((x + 1) * TILE_WIDTH - TILE_OVERLAP * (x != 0), imgw)
            x_start = x_end - TILE_WIDTH
            y_end = min((y + 1) * TILE_HEIGHT - TILE_OVERLAP * (y != 0), imgh)
            y_start = y_end - TILE_HEIGHT

            img_save_path = os.path.join(save_img,test_name+'_'+str(x_start)+'_'+str(y_start)+'.jpg')
            txt_save_path = os.path.join(save_labels, test_name+'_'+str(x_start)+'_'+str(y_start)+'.txt')

            #make cut and save image
            cut_n_save_img(x_start, x_end, y_start, y_end, np_img, img_save_path)

            #cut annotaion and save
            with open(txt_name, 'r') as file:
                lines = file.readlines()
            try:
                writeline = cut_annotation(x_start, x_end, y_start, y_end, lines, imgw, imgh)
            except:
                import code
                code.interact(local=dict(globals(), **locals()))    

            with open(txt_save_path, 'w') as file:
                for line in writeline:
                    file.write(" ".join(map(str, line)).replace('[', '').replace(']', '').replace(',', '') + "\n")
            
            # import code
            # code.interact(local=dict(globals(), **locals()))        

def visualise(imgname):
    """Show all the annotations on to a set of cut images"""
    imglist = glob.glob(os.path.join(imgname, '*.jpg'))
    for i, imgname in enumerate(imglist):
        print(f'visulasing image {i+1}/{len(imglist)}')
        base_name = os.path.basename(imgname[:-4])
        img_name = os.path.join(save_img, base_name+'.jpg')
        txt_name = os.path.join(save_labels, base_name+'.txt')

        image = cv.imread(img_name)
        height, width, _ = image.shape
        #same code as annotation/view_predictions.py in the save_image_predictions_mask function, if groundtruth:
        points_normalised, points, class_idx = [], [], []
        with open(txt_name, "r") as file:
            lines = file.readlines()
        for line in lines:
            data = line.strip().split()
            class_idx.append(int(data[0]))
            points_normalised.append([float(val) for val in data[1:]])
        for data in points_normalised:
            values = []
            try:
                for i in range(0, len(data), 2):
                    x = round(data[i]*width)
                    y = round(data[i+1]*height)
                    values.extend([x,y])
                points.append(values)
            except:
                points.append(values)
                print(f'invalid line there is {len(data)} data, related to img {base_name}')
                # import code
                # code.interact(local=dict(globals(), **locals())) 
        for idx in range(len(class_idx)):
            pointers = np.array(points[idx], np.int32).reshape(-1,2)
            cv.polylines(image, [pointers], True, class_colours[classes[class_idx[idx]]], 2)
        imgsavename = os.path.basename(img_name)
        imgsave_path = os.path.join(save_path, imgsavename[:-4] + '_det.jpg')
        cv.imwrite(imgsave_path, image)
        # import code
        # code.interact(local=dict(globals(), **locals()))

# ######### With one image #############
# test_name = '00_20230116_MIS1_RC_Aspat_T04_08'
# img_name = os.path.join(full_res_dir,'images', test_name+'.jpg')
# txt_name = os.path.join(full_res_dir,'labels', test_name+'.txt')
# cut(img_name, save_img, test_name, save_labels)
# print("done cutting test image")

# visualise(save_img)
# print("done visualise")
# import code
# code.interact(local=dict(globals(), **locals())) 

imglist = sorted(glob.glob(os.path.join(full_res_dir, 'images', '*.jpg')))
# for i, img in enumerate(imglist):
#     print(f'cutting image {i+1}/{len(imglist)}')
#     # if i > 20:
#     #     break
#     #     import code
#     #     code.interact(local=dict(globals(), **locals())) 
#     name = os.path.basename(img)[:-4]
#     img_name = os.path.join(full_res_dir,'images', name+'.jpg')
#     txt_name = os.path.join(full_res_dir,'labels', name+'.txt')
#     cut(img_name, save_img, name, save_labels, txt_name)

visualise(save_img)
import code
code.interact(local=dict(globals(), **locals())) 