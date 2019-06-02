from __future__ import division

from models import *
from utils.utils import *
from utils.datasets import *

import os
import sys
import time
import datetime
import argparse

from PIL import Image

import torch
from torch.utils.data import DataLoader
from torchvision import datasets
from torch.autograd import Variable

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.ticker import NullLocator
import urllib.request
import zipfile
import random
import matplotlib.image as mpimg

if __name__ == "__main__":
    print('Downloading images...')
    
    url = 'https://www.dropbox.com/s/yj942v71dtqg1ua/val2019p.zip?dl=1'  
    urllib.request.urlretrieve(url, 'val2019p.zip')

    zip_ref = zipfile.ZipFile('val2019p.zip', 'r')
    os.mkdir('val2019p')
    zip_ref.extractall('val2019p')
    zip_ref.close()
    print('Done!')
    
    print('Downloading models...')
    
    url = 'https://www.dropbox.com/s/wveb53yauo63qzg/yolov3_ckpt_6.pth?dl=1'  
    urllib.request.urlretrieve(url,'domain_translated_model.pth') 
    url2 = 'https://www.dropbox.com/s/4culeqpjhthj5x7/checkpointmodel2.pth?dl=1'
    urllib.request.urlretrieve(url2,'non_domain_translated_model.pth')
    print('Done!')
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--image_folder", type=str, default="val2019p", help="path to dataset")
    parser.add_argument("--model_def", type=str, default="config/yolov3-custom.cfg", help="path to model definition file")
    parser.add_argument("--class_path", type=str, default="data/custom/classes.names", help="path to class label file")
    parser.add_argument("--conf_thres", type=float, default=0.6, help="object confidence threshold")
    parser.add_argument("--nms_thres", type=float, default=0.4, help="iou thresshold for non-maximum suppression")
    parser.add_argument("--batch_size", type=int, default=1, help="size of the batches")
    parser.add_argument("--n_cpu", type=int, default=0, help="number of cpu threads to use during batch generation")
    parser.add_argument("--img_size", type=int, default=416, help="size of each image dimension")
    parser.add_argument("--domain_translated_model", default=True, help="if False will load model trained without domain translation")
    opt = parser.parse_args()
    print(opt)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    os.makedirs("output", exist_ok=True)

    # Set up model
    model = Darknet(opt.model_def, img_size=opt.img_size).to(device)
    if opt.domain_translated_model == True :
        # Load checkpoint weights
        model.load_state_dict(torch.load('domain_translated_model.pth'))
    if opt.domain_translated_model == False :
        # Load checkpoint weights
        model.load_state_dict(torch.load('non_domain_translated_model.pth'))

    model.eval()  # Set in evaluation mode

    dataloader = DataLoader(
        ImageFolder(opt.image_folder, img_size=opt.img_size),
        batch_size=opt.batch_size,
        shuffle=False,
        num_workers=opt.n_cpu,
    )

    classes = load_classes(opt.class_path)  # Extracts class labels from file

    Tensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor

    imgs = []  # Stores image paths
    img_detections = []  # Stores detections for each image index

    print("\nPerforming object detection:")
    prev_time = time.time()
    for batch_i, (img_paths, input_imgs) in enumerate(dataloader):
        # Configure input
        input_imgs = Variable(input_imgs.type(Tensor))

        # Get detections
        with torch.no_grad():
            detections = model(input_imgs)
            detections = non_max_suppression(detections, opt.conf_thres, opt.nms_thres)

        # Log progress
        current_time = time.time()
        inference_time = datetime.timedelta(seconds=current_time - prev_time)
        prev_time = current_time
        print("\t+ Batch %d, Inference Time: %s" % (batch_i, inference_time))

        # Save image and detections
        imgs.extend(img_paths)
        img_detections.extend(detections)

    # Bounding-box colors
    cmap = plt.get_cmap("tab20b")
    colors = [cmap(i) for i in np.linspace(0, 1, 20)]

    print("\nSaving images:")
    # Iterate through images and save plot of detections
    open("Results.txt","w")
    file = open("Results.txt","a")
    for img_i, (path, detections) in enumerate(zip(imgs, img_detections)):

        print("(%d) Image: '%s'" % (img_i, path))

        # Create plot
        img = np.array(Image.open(path))
        plt.figure()
        fig, ax = plt.subplots(1)
        ax.imshow(img)

        # Draw bounding boxes and labels of detections
        if detections is not None:
            # Rescale boxes to original image
            detections = rescale_boxes(detections, opt.img_size, img.shape[:2])
            unique_labels = detections[:, -1].cpu().unique()
            n_cls_preds = len(unique_labels)
            bbox_colors = random.sample(colors, n_cls_preds)
            filename=path
            import re
            #filename = 'abcdc.com'
            filename = re.sub('\../retail-product-checkout-dataset/val2019/$', '', filename)
            file.write(filename+";")
            for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:

                print("\t+ Label: %s, Conf: %.5f" % (classes[int(cls_pred)], cls_conf.item()))
                box_w = x2 - x1
                box_h = y2 - y1

                color = bbox_colors[int(np.where(unique_labels == int(cls_pred))[0])]
                # Create a Rectangle patch
                bbox = patches.Rectangle((x1, y1), box_w, box_h, linewidth=2, edgecolor=color, facecolor="none")
                # Add the bbox to the plot
                ax.add_patch(bbox)
                # Add label
                plt.text(
                    x1,
                    y1,
                    s=classes[int(cls_pred)],
                    color="white",
                    verticalalignment="top",
                    bbox={"color": color, "pad": 0},
                )
                file.write(str(classes[int(cls_pred)])+",")
            file.write(": \n") 

        # Save generated image with detections
        plt.axis("off")
        plt.gca().xaxis.set_major_locator(NullLocator())
        plt.gca().yaxis.set_major_locator(NullLocator())
        filename = path.split("/")[-1].split(".")[0]
        plt.savefig(f"output/{filename}.png", bbox_inches="tight", pad_inches=0.0)
        plt.close()
    file.close()
    
    path = "output"
    random_filename = random.choice([
        x for x in os.listdir(path)
        if os.path.isfile(os.path.join(path, x))
    ])

    print('domain translated model = ',opt.domain_translated_model)
    print('Showing detections for:',random_filename)
    image = Image.open("output" + "/" +str(random_filename))
    image.show()
