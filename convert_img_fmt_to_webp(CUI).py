import json
import glob
import os
from PIL import Image

with open("input_data.json","r") as f:
    json_data =json.load(f)
img_file_path = json_data["img_file_path"]
os.makedirs(img_file_path,exist_ok=True)

# confirm img files(.png,.ipg,.jpeg,.gif,.svg) in Image Folder AND make Lists
def confirm_files(img_file_path):
    img_file_list = []
    for f in glob.glob(r'{}/*.*'.format(img_file_path)): #LIST
        if os.path.splitext(f)[1] in (".jpg", ".png", ".jpeg",".gif",".svg"):
            img_file_list.append(f)
    return img_file_list #LIST

# convert img file to .webp file
def convert_file(img):
    w = r"{}".format(os.path.splitext(img)[0]) #filename without extension
    webp_img = r"{}".format(w+".webp")
    with Image.open(img) as i:
        i.save(webp_img,quality=50,format="webp",optimize=True)

img_file_list  = confirm_files(img_file_path) #LIST
total = str(len(img_file_list))
for idx,img in enumerate(img_file_list ,start = 1):
    convert_file(img)
    print("===============continue("+str(idx)+"/"+total+")==============") 
print("All Completed!")
