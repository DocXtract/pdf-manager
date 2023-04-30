import numpy as np
import cv2

def zoom_img(img, scale=1.0):
    center_x, center_y = img.shape[1] / 2, img.shape[0] / 2
    width_scaled, height_scaled = img.shape[1] * scale, img.shape[0] * scale
    left_x, right_x = center_x - width_scaled / 2, center_x + width_scaled / 2
    top_y, bottom_y = center_y - height_scaled / 2, center_y + height_scaled / 2
    img_cropped = img[int(top_y):int(bottom_y), int(left_x):int(right_x)]
    return img_cropped


# Determines whether this image file is checked as yes
def isChecked(path):
    THRESHOLD = 100 # Threshhold for stray marks, in pixels
    CROP = 0.85 # Percentage of image to scan
    PIX_RANGE = 100 # Pixel darkness to consider marked

    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE) # Load image as grayscale
    img_cropped = zoom_img(img, CROP)            # Crop to remove any border

    n_black_pix = np.sum(img_cropped < PIX_RANGE)
    if n_black_pix > THRESHOLD:
        return True
    return False

print("Not selected: ", isChecked("Check/no.png"))
print("Select Line: ", isChecked("Check/yes.png"))
print("Check: ", isChecked("Check/check.png"))
print("Tick: ", isChecked("Check/tick.png"))
print("Dot: ", isChecked("Check/dot.png"))