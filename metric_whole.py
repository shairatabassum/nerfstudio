#!/usr/bin/env python

from PIL import Image
import os.path
import subprocess
import argparse
import re

# argument parser
parser = argparse.ArgumentParser()
parser.add_argument("--input_dir", type=str)
parser.add_argument("--output_dir", type=str)

def call_ffmpeg(ref_image, ren_image, vmaf_scores):
    cmd = f"ffmpeg -i {ren_image} -i {ref_image} -lavfi libvmaf -f null -"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    vmaf_line = [line for line in result.stderr.split('\n') if 'VMAF score' in line]
    if vmaf_line:
        vmaf_score = float(vmaf_line[0].split()[-1])
        vmaf_scores.append(vmaf_score)
    print(f"VMAF: {vmaf_score}")
        
def call_psnr(ref_image, ren_image, psnr_scores):
    cmd = f"ffmpeg -i {ren_image} -i {ref_image} -lavfi psnr -f null -"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    psnr_match = re.search(r'average:([0-9.]+)', result.stderr)
    if psnr_match:
        psnr_average = float(psnr_match.group(1))
        #print(f"PSNR Average: {psnr_average}")
        psnr_scores.append(psnr_average)
    print(f"PSNR: {psnr_average}")
        
def call_fvvdp(ref_image, ren_image, fvvdp_scores):
    cmd = f"fvvdp --test {ren_image} --ref {ref_image} --display standard_fhd 2>&1 | grep -oP 'FovVideoVDP=\K[0-9.]+'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    fvvdp_score = result.stdout.strip()
    if fvvdp_score:
        print(f"FovVideoVDP Score: {fvvdp_score}")
        fvvdp_scores.append(float(fvvdp_score))
        
def split_image(image_path, output_path1, output_path2, vmaf_scores, fvvdp_scores, psnr_scores):
    # Open the image
    img = Image.open(image_path)

    # Get the width and height of the original image
    width, height = img.size

    # Calculate the width for each sub-image
    sub_image_width = width // 2

    # Create two new images with size sub_image_width x height
    img1 = img.crop((0, 0, sub_image_width, height))
    img2 = img.crop((sub_image_width, 0, width, height))

    # Save the new images
    img1.save(output_path1)
    img2.save(output_path2)
    
    call_ffmpeg(output_path1, output_path2, vmaf_scores)
    call_psnr(output_path1, output_path2, psnr_scores)
    call_fvvdp(output_path1, output_path2, fvvdp_scores)


def split_images_in_folder(folder_path, output_folder_path):
    # List all files in the folder
    files = os.listdir(folder_path)

    # Filter files based on the string 'frame'
    frame_files = [file for file in files if 'img' in file.lower()]
    
    vmaf_scores = []
    psnr_scores = []
    fvvdp_scores = []

    for frame_file in frame_files:
        # Build the full path for the input image
        input_image_path = os.path.join(folder_path, frame_file)

        # Build the output paths for the two sub-images
        output_image_path1 = os.path.join(output_folder_path, f"{frame_file.split('.')[0]}_org.jpg")
        output_image_path2 = os.path.join(output_folder_path, f"{frame_file.split('.')[0]}_ren.jpg")

        # Split the image and save the sub-images
        split_image(input_image_path, output_image_path1, output_image_path2, vmaf_scores, fvvdp_scores, psnr_scores)
        
    # Calculate and print the average VMAF score
    vmaf_scores = [score for score in vmaf_scores if score != 0]
    vmaf_scores = [score for score in vmaf_scores if score != 100]
    if vmaf_scores:
        average_vmaf = sum(vmaf_scores) / len(vmaf_scores)
        min_vmaf = min(vmaf_scores)
        max_vmaf = max(vmaf_scores)
        print(f"Average VMAF Score: {average_vmaf}")
        print(f"Minimum VMAF Score: {min_vmaf}")
        print(f"Maximum VMAF Score: {max_vmaf}")
        
    if psnr_scores:
        average_psnr = sum(psnr_scores) / len(psnr_scores)
        min_psnr = min(psnr_scores)
        max_psnr = max(psnr_scores)
        print(f"Average PSNR Score: {average_psnr}")
        print(f"Minimum PSNR Score: {min_psnr}")
        print(f"Maximum PSNR Score: {max_psnr}")
        
    # Calculate and print the average FVVDP score
    if fvvdp_scores:
        average_fvvdp = sum(fvvdp_scores) / len(fvvdp_scores)
        min_fvvdp = min(fvvdp_scores)
        max_fvvdp = max(fvvdp_scores)
        print(f"Average FVVDP Score: {average_fvvdp}")
        print(f"Minimum FVVDP Score: {min_fvvdp}")
        print(f"Maximum FVVDP Score: {max_fvvdp}")

if __name__ == "__main__":
    args = parser.parse_args()
    input_folder_path = args.input_dir
    output_folder_path = args.output_dir
    #input_folder_path = "scene1_original.jpg"  # Replace with the path to your folder
    #output_folder_path = "scene1_instant.jpg"  # Replace with the desired output folder

    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)

    split_images_in_folder(input_folder_path, output_folder_path)

