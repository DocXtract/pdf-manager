const cv = require('opencv4nodejs');

function cropImg(img, scale=1.0) {
    const center_x = img.shape[1] / 2;
    const center_y = img.shape[0] / 2;
    const width_scaled = img.shape[1] * scale;
    const height_scaled = img.shape[0] * scale;
    const left_x = center_x - width_scaled / 2;
    const right_x = center_x + width_scaled / 2;
    const top_y = center_y - height_scaled / 2;
    const bottom_y = center_y + height_scaled / 2;
    const img_cropped = img.subarray(top_y, bottom_y, left_x, right_x);
    return img_cropped;
  }

  // Determines whether this image file is checked as yes
  function isChecked(path) {
    const THRESHOLD = 100; // Threshhold for stray marks, in pixels
    const CROP = 0.85; // Percentage of image to scan
    const PIX_RANGE = 100; // Pixel darkness to consider marked
  
    const img = cv.imread(path, cv.IMREAD_GRAYSCALE); // Load image as grayscale
    const img_cropped = cropImg(img, CROP); // Crop to remove any border
  
    const mask = img_cropped.threshold(PIX_RANGE, 255, cv.THRESH_BINARY_INV);
    const numPixels = cv.countNonZero(mask);

    if (numPixels > THRESHOLD) {
      return true;
    }
    return false;
}

console.log("Not selected: ", isChecked("Check/no.png"))
console.log("Select Line: ", isChecked("Check/yes.png"))
console.log("Check: ", isChecked("Check/check.png"))
console.log("Tick: ", isChecked("Check/tick.png"))
console.log("Dot: ", isChecked("Check/dot.png"))