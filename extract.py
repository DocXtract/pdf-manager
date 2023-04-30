import copy
import json
import numpy as np
import cv2, os, random
import pytesseract
from pytesseract import Output 
from PIL import Image
import requests

# NOTE: the documents directory must contain one file for each page of the multi-page # document (1 image only if 1 page document). This is for multi-page conversion support.
# NOTE: if the api is called with fields that belong on x pages, the code will error if there are
# not the expected x pages in the documents folder.

debug = False

class extraction:
    dpi = 200

    # NOTE: the below are staging directories.
    # once a new api call is made to process a new form, all directory content will be unlinked to prepare for the next.
    # be sure to process all output files before making an additional api call.

    output_path = 'documents/cropped'
    input_path = 'documents/uncropped'
    signature_path = 'documents/signatures'

    # cuts out the border of the checkbox so it does not interfere with our check detection
    def zoom_img(img, scale=1.0):
        center_x, center_y = img.shape[1] / 2, img.shape[0] / 2
        width_scaled, height_scaled = img.shape[1] * scale, img.shape[0] * scale
        left_x, right_x = center_x - width_scaled / 2, center_x + width_scaled / 2
        top_y, bottom_y = center_y - height_scaled / 2, center_y + height_scaled / 2
        img_cropped = img[int(top_y):int(bottom_y), int(left_x):int(right_x)]
        return img_cropped

    # saves the given signature image to disk
    def process_signature(ROI, field_name):
        # ensure path exists
        if not os.path.exists(extraction.signature_path):
            os.mkdir(extraction.signature_path)

        cv2.imwrite(os.path.join(extraction.signature_path, field_name+'.png'), ROI)

    # Determines whether this image file is checked as yes
    def isChecked(ROI):
        
        THRESHOLD = 20 # Threshhold for stray marks, in pixels
        CROP = 0.6 # Percentage of image to scan
        PIX_RANGE = 100 # Pixel darkness to consider marked

        img_cropped = extraction.zoom_img(ROI, CROP)            # Crop to remove any border
        n_black_pix = np.sum(img_cropped < PIX_RANGE)

        if debug:
            ''' debug the checkboxes to test the tolerance variables'''
            cv2.imshow(str(random.randint(0,500))+' box.png', img_cropped)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            print(n_black_pix, THRESHOLD)

        if n_black_pix > THRESHOLD:
            return True
        return False

    def crop(path, width, height):
    
        # load and set dpi
        im = Image.open(path)

        # Set the DPI
        im.info['dpi'] = (extraction.dpi, extraction.dpi)

        # Save the image with the new DPI
        im.save(path)


        '''Load the image with the new dpi into opencv'''
        img = cv2.imread(path)

        # Make sure it is in portrait rotation
        h = img.shape[0]
        w = img.shape[1]

        if (w > h):
            img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            cv2.imwrite(path, img)

        # i want to be straight here!

        if debug:
            cv2.imshow('Original Image.jpg', img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        # Convert the image to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if debug:
            cv2.imshow('Grayscale Image.jpg', gray)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        # Apply adaptive thresholding to convert the image to a binary image
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 71, 25)

        if debug:
            cv2.imwrite('Binary threshold Image.jpg', thresh)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        # Find contours in the binary image
        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Initialize the maximum area and corresponding contour
        max_area = 0
        max_cnt = None

        # Loop through each contour
        for cnt in contours:
            # Calculate the area of the contour
            area = cv2.contourArea(cnt)

            # If the area is small, ignore the contour
            if area < 100:
                continue

            # Check if the contour is closed
            perimeter = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * perimeter, True)
            if len(approx) != 4:
                continue

            # Check if the area of the contour is the maximum so far
            if area > max_area:
                max_area = area
                max_cnt = approx

        # Extend the corners of the contour to align them along the horizontal and vertical axes
        max_cnt[0][0][1] -= 1 # Top corner
        max_cnt[1][0][0] += .01 # Right corner
        max_cnt[2][0][1] += 1 # Bottom corner
        max_cnt[3][0][0] -= 1 # Left corner

        a = max_cnt[0][0]
        b = max_cnt[1][0]
        c = max_cnt[2][0]
        d = max_cnt[3][0]
        coords = [a,b,c,d]
        # coords = [ [x,y], [x,y], [x,y], [c,y]]

        # Create a white mask of the same size as the input image
        mask = np.ones(img.shape[:2], dtype=np.uint8) * 255

        # Fill the mask with black inside the detected boundary
        cv2.drawContours(mask, [max_cnt], 0, 0, -1)

        # Copy the original image content inside the detected boundary onto the new image
        new_img = np.copy(img)
        new_img[np.where(mask==0)] = img[np.where(mask==0)]

        

        # Fill the area outside the detected boundary with white color
        new_img[np.where(mask==255)] = [255, 255, 255]

        if debug:
            cv2.imshow('Content in boundary', new_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        '''Fix the warping of the image by quadrant mapping'''

        # For each coordinate
        newCoords = copy.deepcopy(coords)
        # height and width in pixels at this dpi
        h = height/72 * extraction.dpi
        w = width/72 * extraction.dpi
        # possible error: where else do we use width and height? should they be adjusted, too?
        for coord in coords:
            
            x = coord[0]
            y = coord[1]
            

            if x < w/2 and y < h/2:
                newCoords[0] = coord
                continue
            if x < w/2 and y >= h/2:
                newCoords[1] = coord
                continue
            if x >= w/2 and y < h/2:
                newCoords[2] = coord
                continue
            if x >= w/2 and y >= h/2:
                newCoords[3] = coord
                continue


        # print(coords[0])
        x1 = newCoords[0][0]
        y1 = newCoords[0][1]

        x2 = newCoords[1][0]
        y2 = newCoords[1][1]

        x3 = newCoords[2][0]
        y3 = newCoords[2][1]

        x4 = newCoords[3][0]
        y4 = newCoords[3][1]

        src = np.array([[x1, y1], [x2,y2],[x3, y3], [x4,y4]])
        dest = np.array([[0,0],[0,h],[w,0],[w,h]])

        # Calculate the transformation matrix
        M, _ = cv2.findHomography(src, dest)

        # Apply perspective correction to the image
        img_corrected = cv2.warpPerspective(new_img, M, (round(w), round(h)))
        
        ''' Make sure the image is the right 90 degree orientation'''
        gray = cv2.cvtColor(img_corrected, cv2.COLOR_BGR2GRAY)
        cv2.imwrite('peter.png', gray)
        # Perform OCR on the image and get the OSD information
        osd = pytesseract.image_to_osd(gray, output_type=Output.DICT)

        # Extract the rotation angle from the OSD information
        angle = int(osd['orientation'])


        #Check if the image is rotated
        if debug:
            if angle == 0:
                print('The image is straight.')
            else:
                print(f'The image is rotated {angle} degrees.')

        # Rotate the image to the correct orientation
        if angle > 250 and angle < 290:
            img_corrected = cv2.rotate(img_corrected, cv2.ROTATE_90_CLOCKWISE)
        elif angle > 160 and angle < 200:
            img_corrected = cv2.rotate(img_corrected, cv2.ROTATE_180)
        elif angle > 70 and angle < 110:
            img_corrected = cv2.rotate(img_corrected, cv2.ROTATE_90_COUNTERCLOCKWISE)

        img_corrected = cv2.resize(img_corrected, (round(w), round(h)))

        ''' Show the results '''
        if debug:
            cv2.imshow('Corrected Image', img_corrected)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        
        return img_corrected


    def is_image_file(path):
        extension = os.path.splitext(path)[1].lower()
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        return extension in image_extensions

    def empty_dir(path):
        if os.path.exists(path):
            files = os.listdir(path)

            for file in files:
                img_path = os.path.join(path, file)
                if extraction.is_image_file(img_path):
                    os.unlink(img_path)
    
    def fill_fields(fields, api_key):
        # Clear output staging directories (input page is unlinked below after it's crop completes)
        extraction.empty_dir(extraction.output_path)
        extraction.empty_dir(extraction.signature_path)
        

        pageIndex = 0
        ''' Execute for each page '''
        # Ensure input directory exists
        if not os.path.exists(extraction.input_path):
            os.mkdir(extraction.input_path)
            print('ERROR: The stated input directory did not exist! It has been created for you, and program aborted: ', extraction.input_path)
            return None

        # file path to the image taken of this page
        for filename in os.listdir(extraction.input_path):
            f = os.path.join(extraction.input_path, filename)

        # proceed if it is a file (image)
            if extraction.is_image_file(f):
                path = f

                # Gather page-persistent data
                pageHeight = 0
                pageWidth = 0

                # Find a field on this page to set our data
                for key in fields.keys():
                    if (fields[key]['pageIndex'] == pageIndex):
                        # ensure these are the dimensions of the correct page
                        pageHeight = fields[key]["pageHeight"]
                        pageWidth = fields[key]["pageWidth"]
                        break
                
                ''' LOAD THE PAGE IMAGE AND CROP TO DESIRED SIZE '''

                # crop the portrait image
                
                img = extraction.crop(path, pageWidth, pageHeight)

                # update path to the cropped version
                path = os.path.join(extraction.output_path, filename)
                img = cv2.resize(img, (round(pageWidth), round(pageHeight)))


                if not os.path.exists(extraction.output_path):
                    os.mkdir(extraction.output_path)

                cv2.imwrite(path, img)
     

                ''' GET THE EXTRACTED DATA (lines)'''
                url = "https://trigger.extracttable.com"
                payload={'dup_check': 'False'}
                files=[
                ('input',('form.jpg',open(path,'rb'),'image/jpg'))
                ]
                headers = {
                'x-api-key': api_key
                }
                response = requests.request("POST", url, headers=headers, data=payload, files=files)
                #print(response.text)
                lines = json.loads(response.text)['Lines'][0]['LinesArray']

                ''' PREPARING CHECKBOX DETECTION '''
                gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # first the scanned and cropped page is to become grayscale

                thresh = 255 - cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1] # now we can binary it

                # iterate over each field in the document
                for key in fields.keys():

                    # procede only if this field is on the current page
                    if fields[key]['pageIndex'] == pageIndex:

                        # store important data for calculations of this field
                        rect = fields[key]["rect"]
                        is_text = (fields[key]["type"] == "text")

                        x1 = rect[0] / pageWidth
                        h = abs(rect[1] - rect[3]) / pageHeight
                        y2 = ((pageHeight - rect[1]) - h) / pageHeight
                        x2 = rect[2] / pageWidth
                        y1 = y2 - h
                        # y .9 - .11 x starts at .26
                        if is_text:
                            # If the name includes 'signature', save the image as signature.
                            if str(fields[key]['name']).casefold().find('signature') != -1:
                                ROI = thresh[round(y1 * pageHeight):round(y2 * pageHeight), round(x1 * pageWidth):round(x2 * pageWidth)] # set our region of interest to the signature
                                extraction.process_signature(ROI, fields[key]['name'])
                                # continue to extract and store the response after saving the image. DO not extract the signature?
                                continue

                            # set a tolerance threshold for text searching, then all coordinates
                            th = 2.5 / pageHeight
                            tw = 2.5 / pageWidth

                            result = ''
                            for line in lines:
                                for word in line["WordsArray"]:
                                    loc = word["Loc"]

                                    if (x1 - tw <= loc[0] and loc[0] <= x2 + tw and y1 - th <= loc[1] and loc[1] <= y2 + th):
                                        result += word["Word"]+' '

                        else: # checkbox
                            #print(y1,y2,x1,x2)
                            ROI = thresh[round(y1 * pageHeight):round(y2 * pageHeight), round(x1 * pageWidth):round(x2 * pageWidth)] # set our region of interest to the checkbox
                            result = 'Yes' if extraction.isChecked(ROI) else 'No'

                        # Set the result that we extracted from the page back into the json
                        fields[key]["value"] = result
                        #print(result)
                pageIndex += 1
        # Each file has been processed, fields is completely filled in
        # we can now empty the input directory!
        extraction.empty_dir(extraction.input_path)
        return fields

