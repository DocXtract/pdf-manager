# pdf-manager
Functions for pdf conversion and extraction
*Can test all functionality using the local file system by drunning driver.py which clearly tests all pdfGenerator functions.
*Or, run api.py to start the extraction server which will listen for submissions through the mobile app and pass the output to the web server.

1. Download required dependencies: `pip3 install -r requirements.txt`
2. Run `api.py`
3. Make sure the mobile and web apps target the displayed server ip addres for api access

Alternatively, play around with driver.py to test offline in the local file system with provided input and output folders.
