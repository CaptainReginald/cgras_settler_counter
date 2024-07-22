#! /usr/bin/env python3

""" robolflow_sahi_test.py
trying to use roboflow to annotate images for sahi segemntation
following this blog https://blog.roboflow.com/how-to-use-sahi-to-detect-small-objects/ 
"""

##TODO add to yaml setup file
#pip install supervision <- actually needed

import supervision as sv
import numpy as np
import cv2
from ultralytics import YOLO
import matplotlib.pyplot as plt
import time
import numpy as np
import os
import glob
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, ElementTree
import zipfile
import torch
from Utils import classes, class_colours

weight_file = '/home/java/Java/ultralytics/runs/segment/train10/weights/best.pt'
base_img_location = '/media/java/CGRAS-SSD/cgras_data_copied_2240605/samples/cgras_data_copied_2240605_ultralytics_data/images'
save_dir = '/media/java/CGRAS-SSD/cgras_data_copied_2240605/samples/ultralytics_data_detections'
base_file = "/home/java/Downloads/cgras20240716/annotations.xml"
output_filename = "/home/java/Downloads/cgras_2024_1.xml"
#list of images that have already been labeled
labeled_images = [0, 1, 2, 3, 5, 100, 101, 102, 103, 104, 105, 106, 107, 108, 110, 112, 370, 371, 372, 373, 374, 375, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 
                  391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 
                  461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 550, 551, 552, 553, 554, 555, 556, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569, 570, 571,
                  572, 573, 574, 575, 576, 577, 578, 579, 580, 700, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715, 716, 717, 718, 719, 720, 721,
                  722, 723, 724, 750, 149, 650, 651, 652, 653, 658, 774] 
max_img = 1000
single_image = False #run roboflow sahi on one image and get detected segmentation results
visualise = True #visualise the detections on the images

## FUNCIONS
#quicker then the version in Utils.py #TODO probably update one in utils
def binary_mask_to_rle(binary_mask):
    """
    Convert a binary np array into a RLE format.
    Args:
        binary_mask (uint8 2D numpy array): binary mask
    Returns:
        rle: list of rle numbers
    """
    # Flatten the binary mask and append a zero at the end to handle edge case
    flat_mask = binary_mask.flatten()
    # Find the positions where the values change
    changes = np.diff(flat_mask)
    # Get the run lengths
    runs = np.where(changes != 0)[0] + 1
    # Get the lengths of each run
    run_lengths = np.diff(np.concatenate([[0], runs]))
    return run_lengths.tolist()

def rle_to_binary_mask(rle_list, 
                       width: int, 
                       height: int, 
                       SHOW_IMAGE: bool):
    """rle_to_binary_mask
    Converts a rle_list into a binary np array. Used to check the binary_mask_to_rle function

    Args:
        rle_list (list of strings): containing the rle information
        width (int): width of shape
        height (int): height of shape
        SHOW_IMAGE (bool): True if binary mask wants to be viewed

    Returns:
        mask: uint8 2D np array
    """
    mask = np.zeros((height, width), dtype=np.uint8) 
    current_pixel = 0
    
    for i in range(0, len(rle_list)):
        run_length = int(rle_list[i]) #find the length of current 0 or 1 run
        if (i % 2 == 0): #if an even number the pixel value will be 0
            run_value = 0
        else:
            run_value = 1

        for j in range(run_length): #fill the pixel with the correct value
            mask.flat[current_pixel] = run_value 
            current_pixel += 1

    if (SHOW_IMAGE):
        print("rle_list to binary mask")
        plt.imshow(mask, cmap='binary')
        plt.show()

    return mask

def callback(image_slice: np.ndarray) -> sv.Detections:
    results = model(image_slice)
    try:
        detections = sv.Detections.from_ultralytics(results[0])
    except:
        print("Error in callback")
        import code
        code.interact(local=dict(globals(), **locals()))
    return detections

## OBJECTS
model = YOLO(weight_file)
mask_annotator = sv.MaskAnnotator()
slicer = sv.InferenceSlicer(callback=callback, slice_wh=(640, 640), overlap_ratio_wh=(0.1, 0.1))

##predict and CVAT
class Predict2Cvat:
    BASE_FILE = "/home/java/Java/Cgras/cgras_settler_counter/annotations.xml"
    OUTPUT_FILE = "/home/java/Downloads/complete.xml"
    DEFAULT_WEIGHT_FILE = "/home/java/Java/ultralytics/runs/segment/train9/weights/cgras_yolov8n-seg_640p_20231209.pt"
    DEFAULT_SAVE_DIR = "/media/java/CGRAS-SSD/cgras_data_copied_2240605/samples/ultralytics_data_detections"
    DEFAULT_MAX_IMG = 10000
    DEFAULT_BATCH_SIZE = 3000
    
    def __init__(self, 
                 img_location: str, 
                 output_file: str = OUTPUT_FILE, 
                 weights_file: str = DEFAULT_WEIGHT_FILE,
                 base_file: str = BASE_FILE,
                 max_img: int = DEFAULT_MAX_IMG,
                 save_img: bool = False,
                 save_dir: str = DEFAULT_SAVE_DIR,
                 batch_height: int = DEFAULT_BATCH_SIZE,
                 batch_width: int = DEFAULT_BATCH_SIZE,
                 label_img_no: list = None):
        self.img_location = img_location
        self.base_file = base_file
        self.output_file = output_file
        self.device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        self.model = YOLO(weights_file).to(self.device)
        self.max_img = max_img
        self.save_img = save_img
        self.save_dir = save_dir
        self.batch_height = batch_height
        self.batch_width = batch_width
        self.label_img_no = label_img_no

    def tree_setup(self):
        tree = ET.parse(self.base_file)
        root = tree.getroot() 
        new_tree = ElementTree(Element("annotations"))
        # add version element
        version_element = ET.Element('version')
        version_element.text = '1.1'
        new_tree.getroot().append(version_element)
        # add Meta elements, (copy over from source_file)
        meta_element = root.find('.//meta')
        if meta_element is not None:
            new_meta_elem = ET.SubElement(new_tree.getroot(), 'meta')
            # copy all subelements of meta
            for sub_element in meta_element:
                new_meta_elem.append(sub_element)
        return new_tree, root

    #this is done so that the memory doesn't fill up straight away with the large images
    def batch_image(self, image_cv, image_height, image_width, slicer):
        data_dict = {'class_name': []}
        conf_list, cls_id_list, mask_list = [], [], []
        print("Batching image")
        for y in range(0, image_height, self.batch_height):
            for x in range(0, image_width, self.batch_width):
                y_end = min(y + self.batch_height, image_height)
                x_end = min(x + self.batch_width, image_width)
                img= image_cv[y:y_end, x:x_end]
                sliced_detections = slicer(image=img)
                for conf in sliced_detections.confidence:
                    conf_list.append(conf)
                for cls_id in sliced_detections.class_id:
                    cls_id_list.append(cls_id)
                for data in sliced_detections.data['class_name']:
                    data_dict['class_name'].append(data)
                for mask in sliced_detections.mask:
                    mask_resized = cv2.resize(mask.astype(np.uint8), (x_end - x, y_end - y))
                    rows, cols = np.where(mask_resized == 1)
                    if len(rows) > 0 and len(cols) > 0:
                        top_left_y = rows.min()
                        bottom_right_y = rows.max()
                        top_left_x = cols.min()
                        bottom_right_x = cols.max()
                        box_width = bottom_right_x - top_left_x + 1
                        box_height = bottom_right_y - top_left_y + 1
                        sub_mask = mask_resized[top_left_y:bottom_right_y + 1, top_left_x:bottom_right_x + 1]
                        mask_list.append((sub_mask, top_left_x + x, top_left_y + y, box_width, box_height))         
        return conf_list, cls_id_list, mask_list, data_dict, sliced_detections


    def run(self):
        new_tree, root = self.tree_setup()

        for i, image_element in enumerate(root.findall('.//image')):
            print(i+1,'images being processed')
            if i>self.max_img:
                print("Hit max img limit")
                break
            image_id = image_element.get('id')
            image_name = image_element.get('name')
            image_width = int(image_element.get('width'))
            image_height = int(image_element.get('height'))
            # create new image element in new XML
            new_elem = SubElement(new_tree.getroot(), 'image')
            new_elem.set('id', image_id)
            new_elem.set('name', image_name)
            new_elem.set('width', str(image_width))
            new_elem.set('height', str(image_height))
            
            if self.label_img_no is not None and i in self.label_img_no: #don't overwrite already labeled images
                print("skipping image, as already labeled")
                for mask in image_element.findall('.//mask'):
                    mask_elem = SubElement(new_elem, 'mask')
                    mask_elem.set('label', mask.get('label'))
                    mask_elem.set('source', mask.get('source'))
                    mask_elem.set('occluded', mask.get('occluded'))
                    mask_elem.set('rle', mask.get('rle'))
                    mask_elem.set('left', mask.get('left'))
                    mask_elem.set('top', mask.get('top'))
                    mask_elem.set('width', mask.get('width'))
                    mask_elem.set('height', mask.get('height'))
                    mask_elem.set('z_order', mask.get('z_order'))
                continue

            image_file = os.path.join(self.img_location, image_name)
            image_cv = cv2.imread(image_file)
            image_height, image_width = image_cv.shape[:2]
            conf_list, cls_id_list, mask_list, data_dict, sliced_detections = self.batch_image(image_cv, image_height, image_width, slicer)
            conf_array = np.array(conf_list)

            if self.save_img:
                print("Save img_not implemented")
                #self.save_img(image_cv, conf_list, cls_id_list, mask_list, data_dict, sliced_detections)

            if conf_array is None:
                print('No masks found in image',image_name)
                continue

            for j, detection in enumerate(conf_array):
                try:
                    sub_mask, top_left_x, top_left_y, box_width, box_height = mask_list[j]
                    rle = binary_mask_to_rle(sub_mask)
                    #rle_to_binary_mask(rle, box_width, box_height, True) #check rle, works
                    rle_string = ', '.join(map(str, rle))
                    label = data_dict['class_name'][j]
                    mask_elem = SubElement(new_elem, 'mask')
                    mask_elem.set('label', label)
                    mask_elem.set('source', 'semi-auto')
                    mask_elem.set('occluded', '0')
                    mask_elem.set('rle', rle_string)
                    mask_elem.set('left', str(int(top_left_x)))
                    mask_elem.set('top', str(int(top_left_y)))
                    mask_elem.set('width', str(int(box_width)))
                    mask_elem.set('height', str(int(box_height)))
                    mask_elem.set('z_order', '0')
                except:
                    print(f'detection {j} encountered problem')
                    import code
                    code.interact(local=dict(globals(), **locals()))
            
            new_tree.write(self.output_file, encoding='utf-8', xml_declaration=True) #save as progress incase of crash
            print(len(sliced_detections),'masks converted in image',image_name)

        new_tree.write(self.output_file, encoding='utf-8', xml_declaration=True)
        zip_filename = self.output_file.split('.')[0] + '.zip'
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(self.output_file, arcname='output_xml_file.xml')
        print('XML file zipped')


print("Detecting corals and saving to annotation format")
Det = Predict2Cvat(base_img_location, output_filename, weight_file, base_file, save_img=False, max_img=max_img, label_img_no=labeled_images)
Det.run()
print("Done detecting corals")

import code
code.interact(local=dict(globals(), **locals()))

import cv2 as cv
def save_image_predictions_mask(results, image, imgname, save_path, conf, class_list, classes, class_colours):
    """save_image_predictions_mask
    saves the predicted masks results onto an image and bbounding boxes, recoring confidence and class as well.
    """
    # ## to see image as 640 resolution
    # image = cv.imread(imgname)
    # image = cv.resize(image, (640, 488))
    height, width, _ = image.shape
    masked = image.copy()
    line_tickness = int(round(width)/600)
    font_size = 2#int(round(line_tickness/2))
    font_thickness = 5#3*(abs(line_tickness-font_size))+font_size
    if results:
        for j, m in enumerate(results):
            contours, _ = cv2.findContours(m[1], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE) #haven't shifted masks?
            for contour in contours:
                points = np.squeeze(contour)
                cls = classes[int(class_list[j])]
                desired_color = class_colours[cls]
                if points is None or not points.any() or len(points) == 0:
                    print(f'mask {j} encountered problem with points {points}, class is {cls}')
                else: 
                    cv.fillPoly(masked, [points], desired_color) #fixed!!!
        for t, b in enumerate(results.xyxy):
            cls = classes[int(class_list[t])]
            desired_color = class_colours[cls]
            cv2.rectangle(image, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), tuple(class_colours[cls]), line_tickness)
            cv.putText(image, f"{conf[t]:.2f}: {cls}", (int(b[0]-20), int(b[1] - 5)), cv.FONT_HERSHEY_SIMPLEX, font_size, desired_color, font_thickness)
    else:
        print(f'No masks found in {imgname}')

    alpha = 0.5
    semi_transparent_mask = cv.addWeighted(image, 1-alpha, masked, alpha, 0)
    imgsavename = os.path.basename(imgname)
    imgsave_path = os.path.join(save_path, imgsavename[:-4] + '_det_mask.jpg')
    cv.imwrite(imgsave_path, semi_transparent_mask)

batch_height, batch_width = 3000, 3000

## Visualise Detections on images
if visualise:
    print("visulising detections")
    os.makedirs(save_dir, exist_ok=True)
    imglist = sorted(glob.glob(os.path.join(base_img_location, '*.jpg')))
    for i, image_file in enumerate(imglist):
        print(f"processing image: {i+1} of {len(imglist)}")
        if i<6:
            continue
        if i>max_img:
            print("Hit max img limit")
            break
        image = cv2.imread(image_file)
        image_height, image_width = image.shape[:2]
        data_dict = {'class_name': []}
        box_list, conf_list, cls_id_list, mask_list = [], [], [], []
        #whole_image_mask = np.zeros((image_height, image_width), dtype=bool)
        print("Batching image")
        for y in range(0, image_height, batch_height):
            for x in range(0, image_width, batch_width):
                y_end = min(y + batch_height, image_height)
                x_end = min(x + batch_width, image_width)
                img= image[y:y_end, x:x_end]
                sliced_detections = slicer(image=img)
                for box in sliced_detections.xyxy:
                    box[0] += x
                    box[1] += y
                    box[2] += x
                    box[3] += y
                    box_list.append(box)
                for conf in sliced_detections.confidence:
                    conf_list.append(conf)
                for cls_id in sliced_detections.class_id:
                    cls_id_list.append(cls_id)
                for data in sliced_detections.data['class_name']:
                    data_dict['class_name'].append(data)
                for mask in sliced_detections.mask:
                    mask_resized = cv2.resize(mask.astype(np.uint8), (x_end - x, y_end - y))
                    full_image_mask = np.zeros((image_height, image_width), dtype=np.uint8)
                    full_image_mask[y:y_end, x:x_end] = mask_resized
                    mask_list.append(full_image_mask.copy())
        print("stiching batch back together")
        whole_image_detection = sv.Detections(xyxy=np.array(box_list), confidence=np.array(conf_list), class_id=np.array(cls_id_list), 
                                              mask=np.array(mask_list), data=data_dict)
        save_image_predictions_mask(whole_image_detection, image, image_file, save_dir, conf_list, cls_id_list, classes, class_colours)
        # import code
        # code.interact(local=dict(globals(), **locals()))


### Single image check and test
if single_image:
    image_file = "/home/java/Java/data/cgras_20231028/images/2712-4-1-1-0-231220-1249.jpg"
    image = cv2.imread(image_file)

    start_time = time.time()
    sliced_detections = slicer(image=image)
    end_time = time.time()

    annotated_image = mask_annotator.annotate(scene=image.copy(), detections=sliced_detections)

    sv.plot_image(annotated_image) #visualise all the detections

    duration = end_time - start_time
    print('slice run time: {} sec'.format(duration))
    print('slice run time: {} min'.format(duration / 60.0))

    # get detections in yolo format
    start_time = time.time()
    for i, detection in enumerate(sliced_detections):
        print(f"detection: {i+1} of {len(sliced_detections)}")
        xyxy = detection[0].tolist()
        mask_array = detection[1] #Bool array of img_h x img_w
        confidence = detection[2]
        class_id = detection[3]
        rle = binary_mask_to_rle(mask_array) 
        left, top, width, height = min(xyxy[0], xyxy[2]), min(xyxy[1], xyxy[3]), abs(xyxy[0] - xyxy[2]), abs(xyxy[1] - xyxy[3])
        label = detection[5]['class_name']
        #rle_to_binary_mask(rle, 5304, 7952, True) #check rle, works
    end_time = time.time()

    duration = end_time - start_time
    print('detction proecss total run time: {} sec'.format(duration))
    print('detction proecss total run time: {} min'.format(duration / 60.0))
    duration = (end_time - start_time)/len(sliced_detections)
    print('detction proecss average run time: {} sec'.format(duration))
    print('detction proecss average run time: {} min'.format(duration / 60.0))

    import code
    code.interact(local=dict(globals(), **locals()))

