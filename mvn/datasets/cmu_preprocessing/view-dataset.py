#!/bin/python

"""
    A GUI script for inspecting Human3.6M and its wrappers, namely:
    - `CMUPanopticDataset`
    - `human36m-multiview-labels-**bboxes.npy`

    Usage: `python3 view-dataset.py <path/to/Human3.6M-root> <path/to/human36m-multiview-labels-*bboxes.npy> [<start-sample-number> [<samples-per-step>]]
"""
import torch
import numpy as np
import cv2

import os, sys
import math

cmu_root = sys.argv[1]
labels_path = sys.argv[2]

try:    sample_idx = int(sys.argv[3])
except: sample_idx = 0

try:    step = int(sys.argv[4])
except: step = 10

try:
    imgdir = "dataset_imgs"
    save_images_instead = (int(sys.argv[5]) == 1)
    print(f"Saving images to {imgdir} instead of displaying them...")
except: 
    save_images_instead = False

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../.."))

from mvn.datasets.cmupanoptic import CMUPanopticDataset
from mvn.utils.vis import draw_2d_pose_cv2

scale_bbox = 1.0
square_bbox = False
norm_image = False
image_shape = None # (384, 384)
crop = False

print(f"Scale bbox: {scale_bbox}")
print(f"Square bbox: {square_bbox}")
print(f"Image Shape: {image_shape}")
print(f"Norm Image: {norm_image}")
print(f"Crop: {crop}\n")

dataset = CMUPanopticDataset(
    cmu_root,
    labels_path,
    train=True,
    test=True,
    image_shape=image_shape,
    retain_every_n_frames_in_test=1,
    scale_bbox=scale_bbox,
    square_bbox=square_bbox,
    kind='cmu',
    norm_image=norm_image,
    ignore_cameras=[],
    choose_cameras=[],
    crop=crop)

print("Total Samples:", len(dataset))
print("Total Images Shown/Saved:", math.ceil((len(dataset) - sample_idx)/step))

prev_action = None
patience = 0

while sample_idx < len(dataset):
    sample = dataset[sample_idx]

    camera_idx = 9

    try:
        image = sample['images'][camera_idx]
        camera = sample['cameras'][camera_idx]
    except:
        print(f"Sample {sample_idx} does not have an associated image or camera {camera_idx}")
        sample_idx += step
        continue

    display = image.copy()

    from mvn.utils.multiview import project_3d_points_to_image_plane_without_distortion as project
    keypoints_2d = project(camera.projection, sample['keypoints_3d'][:, :3])
    
    # Draw visualisation using vis.py
    display = draw_2d_pose_cv2(
        keypoints=keypoints_2d, 
        canvas=display,
        kind='cmu',
        point_size=3,
        #hmm this point_color=(200, 20, 10),
        line_width=2
    )

    # Draw BBOX
    try:
        left, top, right, bottom = sample['detections'][camera_idx]
    except:
        raise Exception("Cannot get BBOX")

    # Resize image if image size has changed            if self.image_shape is not None:
    if image_shape is not None:
        img_height_before, img_width_before = sample['image_shapes_before_resize'][camera_idx]
        img_height_after, img_width_after = image_shape
        img_height_ratio = img_height_after / img_height_before
        img_width_ratio = img_width_after / img_width_before

        left = int(left * img_width_ratio)
        right = int(right * img_width_ratio)
        top = int(top * img_height_ratio)
        bottom = int(bottom * img_height_ratio)

    if top - bottom == 0:
        _msg = "No bbox data found"
        print(f"Sample {sample_idx}, Camera {camera_idx}: {_msg}")
        cv2.putText(display, _msg, (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.2, (0, 0, 255))
    else:
        img_height, img_width, _ = display.shape
        print(f"Sample {sample_idx}, Camera {camera_idx}: Drawing rectangle at ({left}, {top}), ({right}, {bottom}) for image of dimensions ({img_height}, {img_width})")
        if not crop:
            try:
                cv2.rectangle(display, (left, top), (right, bottom), (255, 0, 0), 2)
            except:
                raise Exception("Could not draw BBOX")
        
    # Get window name
    sample_info = dataset.labels['table'][sample_idx]
    person_id = sample_info['person_id']
    action_name = dataset.labels['action_names'][sample_info['action_idx']]
    camera_name = dataset.labels['camera_names'][camera_idx]
    frame_idx = sample_info['frame_name']

    if save_images_instead:
        img_path = os.path.join(imgdir, action_name, camera_name)
        if not os.path.exists(img_path):
            os.makedirs(img_path)

        img_path = os.path.join(img_path, f"{frame_idx:08}_p{person_id}.jpg")

        try: 
            print(f"Saving image to {img_path}")
            cv2.imwrite(img_path, display)
        except:
            print(f"Error: Cannot save to {img_path}")
    else:
        title = f"Person {person_id}: {action_name}/{camera_name}/{frame_idx}"

        cv2.imshow('w', display)
        cv2.setWindowTitle('w', title)
        c = cv2.waitKey(0) % 256

        if c == ord('q') or c == 27:
            print('Quitting...')
            cv2.destroyAllWindows()
            break

    action = sample_info['action_idx']
    if action != prev_action: # started a new action
        prev_action = action
        patience = 2000
        sample_idx += step
    elif patience == 0: # an action ended, jump to the start of new action
        while True:
            sample_idx += step
            action = dataset.labels['table'][sample_idx]['action_idx']
            if action != prev_action:
                break
    else: # in progess, just increment sample_idx
        patience -= 1
        sample_idx += step

print("Done.")
