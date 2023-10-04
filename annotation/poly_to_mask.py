"""Converstions of polygons to masks for CVAT annotation.
    Download polygon annotations using CVAT1.1 format
    Upload mask annotations using CVAT1.1 format after zipping the outputed XML file
"""
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from xml.etree.ElementTree import Element, SubElement, ElementTree
import code
import matplotlib.pyplot as plt
import zipfile

def binary_mask_to_rle(binary_mask):
    """binary_mask_to_rle
    Convert a binary np array into a RLE format
    
    Args:
        binary_mask (uint8 2D numpy array): binary mask

    Returns:
        rle: list of rle numbers
    """
    rle = []
    current_pixel = 0
    run_length = 0

    for pixel in binary_mask.ravel(order='C'): #go through the flaterened binary mask
        if pixel == current_pixel:  #increase number if same pixel
            run_length += 1
        else: #else save run length and reset
            rle.append(run_length) 
            run_length = 1
            current_pixel = pixel
    return rle

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

def poly_2_rle(points, 
               SHOW_IMAGE: bool):
    """poly_2_rle
    Converts a set of points for a polygon into an rle string and saves the data

    Args:
        points (2D numpy array): points of polygon
        SHOW_IMAGE (bool): True if binary mask wants to be viewed
    
    Returns:
        rle_string: string of the rle numbers,
        left: (int) left positioning of the rle numbers in pixles,
        top: (int) top positioning of the rle numbers in pixles,
        width: (int) width of the bounding box of the rle numbers in pixels,
        height: (int) height of the bounding box of the rle numbers in pixles
    """
    # create bounding box
    left = int(np.min(points[:, 0]))
    top = int(np.min(points[:, 1]))
    right = int(np.max(points[:, 0]))
    bottom = int(np.max(points[:, 1]))
    width = right - left + 1
    height = bottom - top + 1

    # create mask size of bounding box
    mask = np.zeros((height, width), dtype=np.uint8)
    # points relative to bounding box
    points[:, 0] -= left
    points[:, 1] -= top
    # fill mask where points are
    cv2.fillPoly(mask, [points.astype(int)], color=1)

    # visual check of mask - looks good
    SHOW_IMAGE = False
    if (SHOW_IMAGE):
        plt.imshow(mask, cmap='binary')
        plt.show()

    # convert the mask into a rle
    mask_rle = binary_mask_to_rle(mask)

    # rle string
    rle_string = ",".join(map(str, mask_rle))
    
    return rle_string, left, top, width, height

def polyxml_to_maskxml(source_file: str, 
                       output_filename: str, 
                       SHOW_IMAGE: bool):
    '''polyxml_to_maskxml
    Converts a cvat1.1 source file annotation with polyshapes to an cvat1.1 outputfile with annontations as masks.
    NOTE: '.xml' must be included in both source_file and output_filename

    Args:
        source_file (str): name of source file with annontations
        output_filename (str): name of output file to save to.
        SHOW_IMAGE (bool): True if polygons and rle want to be viewed (to check process)
    '''
# load XML file with the polygons via a tree
    tree = ET.parse(source_file)
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

    # iterate through image elements
    i = 0
    for image_element in root.findall('.//image'):
        i += 1
        print(i,'images being processed')

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

        # acess polygon annotations in the image
        for polygon_element in image_element.findall('polygon'):
            polygon_points = polygon_element.get('points')
            polygon_label = polygon_element.get('label')
            polygon_z_order = polygon_element.get('z_order')
            # points into np array 
            points = np.array([list(map(float, point.split(',')))
                            for point in polygon_points.split(';')])

            # convert the points into rle format
            rle_string, left, top, width, height = poly_2_rle(points)

             # If converstion needs to be checked
            rle_list = list(map(str, rle_string.split(','))) #rle into list
            test_mask = rle_to_binary_mask(rle_list, width, height, SHOW_IMAGE)  # convert the rle into mask
            
            #XML mask element details
            mask_elem = SubElement(new_elem, 'mask')
            mask_elem.set('label', polygon_label)
            mask_elem.set('source', 'semi-auto')
            mask_elem.set('occluded', '0')
            mask_elem.set('rle', rle_string)
            mask_elem.set('left', str(left))
            mask_elem.set('top', str(top))
            mask_elem.set('width', str(width))
            mask_elem.set('height', str(height))
            mask_elem.set('z_order', polygon_z_order)

        print(len(image_element.findall('polygon')),'polgons converted in image',image_name)

    # Write modified XML to output file
    new_tree.write(output_filename, encoding='utf-8', xml_declaration=True)

    #Zip the file
    zip_filename = output_filename.split('.')[0] + '.zip'
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(output_filename, arcname='output_xml_file.xml')
    print('XML file zipped')

    code.interact(local=dict(globals(), **locals()))

def test_rle_to_mask(source_file: str):
    '''test_rle_to_mask
    Function to check that the rle_to_binary_mask function works

    Args:
        source_file (str): name of sourcefile
    '''
    # load XML file with the mask
    tree = ET.parse(source_file)
    root = tree.getroot() 

    for image_element in root.findall('.//image'):
        for mask_element in image_element.findall('mask'):
            mask_rle = mask_element.get('rle')
            mask_width = mask_element.get('width')
            mask_height = mask_element.get('height')
            # rle into list 
            rle_list = list(map(int, mask_rle.split(',')))
            # convert the rle into mask
            mask = rle_to_binary_mask(rle_list, int(mask_width), int(mask_height), SHOW_IMAGE=True)

#test_rle_to_mask(source_file='masks.xml')

polyxml_to_maskxml(source_file='annotations.xml', output_filename='ziptest.xml', SHOW_IMAGE=False)