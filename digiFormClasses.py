import copy
from pdf_simulator import PdfGenerator, PdfReader
from pdfStructure import *
from datetime import datetime
import os, time, shutil
import boto3



# Server class 
class Server:
    orgs = [] # A list of all organizations 
    
    # NOTE: Is this necessary? Can we just pass Organization object around?
    def getOrgByID(self, id):
        return self.orgs[id]

    # Create, return and store a new organization
    def createOrg(self, name):
        newOrg = Organization(name)
        self.orgs.append(newOrg)
        return newOrg


# Member class
class Member:
    def __init__(self, firstName, lastName):
        self.firstName = firstName
        self.lastName = lastName
        self.currentForm = None # The request we are viewing / modifying
        self.activeForms = [] # Requests that are in progress

    # Member selects this form. A request object exists already if we can see it. When we click it this happens.
    def selectForm(self, org, formID):
        # iterate over active forms to see if we already have data for this request
        for req in self.activeForms:
            # print(req.formID, " is the id of ", req.name)
            if ((req.org == org) and (req.formID == formID)):
                # This requests matches our selection (org and ID match) so we already started it
                self.currentForm = req
                
                
                return self.currentForm

            # id 2 is what i want. form id is org based, so our request are only id 0, single form, and id 2, multi form.
            # id 1 is reserved for the web generated form (devin's form).


        print(self.firstName+ " could not select form ID "+str(formID)+". They were not sent this form! Do you have the wrong formID?")
        print("    - The org of form @ id "+str(formID)+" is "+self.activeForms[formID].org.name+" .")

    # This member has been sent a form to complete, this is the request object
    def receiveFormRequest(self, req):
        self.activeForms.append(req)
        # TODO: UI updates and creates a visual form button for each req object, incl new one

    # This member wants to submit the form they currently are editing.
    def submitFormResponse(self):
        # No need to check currentForm is valid here, because submit button will only appear if it is.
        # We must call a recieveFormResponse in the Organization.
        # In that function, it will be appended to the list of responses. 
        # Then it can be clicked on, at which point the generatePDf(from response) will occur.
        
        # mark complete 
        self.currentForm.complete = True
        org = self.currentForm.org
        fields = self.currentForm.fields

        # STORE THE GIVEN NAME SO WE CAN RETURN IT TO THE WEBSITE
        name = PdfGenerator.getNameByFields(fields)
        # self.firstName = name[0]
        # self.lastName = name[1]
        # name = name[0] + ' ' + name[1]

        formID = self.currentForm.formID
        # We need the responder's ID.. or can we just pass the responder object themself?
        # I will try to pass responder but I'm wondering how passing objects over the network will be
        # as opposed to passing the ID and then finding the object at the other end.

        now = datetime.now()
        # if > 12 subtract 12 and set pm
        if now.hour > 12:
            hour = now.hour - 12
            suffix = "PM"
        else:
            hour = now.hour
            suffix = "AM"

        if len(str(now.minute)) == 1:
            minute = '0'+ str(now.minute)
        else:
            minute = now.minute
        
        response = pdfResponse(self, str(now.month) +"/"+str(now.day)+"/"+str(now.year)+" @ "+str(hour)+":"+str(minute)+' '+suffix, fields, formID, org, name)
        org.receiveFormResponse(response)




    # Member updates a field in the currently selected response
    # We need to look at the fields and see if this one exists 
    # to know whether to create a new object or update existing.
    # NOTE: the fieldIndex will be the ChildIndex of this button in the scroll box
    # when the client is looking at all fields.

    # TODO: When responding to radio button, set all others to no.
    def respondToField(self, fieldIndex, fieldValue):
        response = self.getFieldByIndex(fieldIndex)

        # NOTE: This will always be true, because we add all fields by default!
        if (response != None):
           
            # Field says firstname, so store the first name
            if response.name in Consts.firstNameFields:
                response.value = fieldValue.capitalize()

            # Field says name so its probably first and last
            elif response.name in Consts.nameFields:

                response.value = fieldValue
                splitName = fieldValue.split(" ")
                
                # Store first and maybe last name
                firstName = splitName[0].capitalize()
                if len(splitName) >= 2:
                    lastName = splitName[1].capitalize()
                    response.value = firstName+" "+lastName
                else: # Only have first name
                    response.value = firstName
                

                # We are given last name so store last name
            elif response.name in Consts.lastNameFields:
                response.value = fieldValue.capitalize()
            
            else: # Any non-name field need not be capitalized
                response.value = fieldValue


            # print("UPDATED VALUE FOR "+self.name+" TO "+ fieldValue)
        

            # Check if its a radio button (checkbox w $ prefix to denote single choice)
            if ((response.type == Consts.mcDisplay) and (response.singleChoice == True)):
                
                # It is! Set them all to no, then this one to yes, if we're choosing yes
                if (response.value == Consts.checkBoxDisplayYes or response.value in Consts.checkBoxYesState):
                    
                    # We said yes to this, so first say no to all others.
                    for field in self.currentForm.fields:

                        # Is this field in the group we're targetting?
                        if (field.choiceGroup == response.choiceGroup):
                            field.value = Consts.checkBoxDisplayNo
                    # All have been set to no, so set the desired to yes
                    response.value = fieldValue


    # Return field with this index (NOT "at this index", not necessarily ordered by index, but probably is.)
    def getFieldByIndex(self, index):
        
        fields = self.currentForm.fields
        for field in fields:
            if (field.index == index):
                return field
        print("ERROR finding index "+ str(index)+" in form "+ self.currentForm.name+" (id: "+str(self.currentForm.formID)+").")
        return None # Error field not here! Every field in the form shold be copied!
    


# Organization class
class Organization:

    AWS_SECRET_KEY = ""
    AWS_ACCESS_KEY = ""
    bucket_name = ""
    s3 = None
    

    # A new organization is formed
    # Begin with a name and an empty list of forms.
    def __init__(self, name):
        self.name = name
        self.forms = []
        self.responses = [] # Must be filtered by FormID
        self.members = []
        self.currentForm = None

    # SET ACCESS KEYS
    def initializeBucket(self, access, secret):
        Organization.AWS_ACCESS_KEY = access
        Organization.AWS_SECRET_KEY = secret

        # Initialize the S3 client
        Organization.s3 = boto3.client('s3', aws_access_key_id=access, aws_secret_access_key=secret)

        # Set the S3 bucket and key for the image
        Organization.bucket_name = 'ms-inventory-management'

        # Delete all objects from the bucket
        # List all objects in the bucket

        try:
            response = Organization.s3.list_objects(Bucket=Organization.bucket_name)
            if 'Contents' in response:
                objects = response['Contents']
                # Delete all objects from the bucket
                for obj in objects:
                    Organization.s3.delete_object(Bucket=Organization.bucket_name, Key=obj['Key'])
        except:
            pass


    def uploadS3(path, old_key):
        # delete old link, if exists
        if old_key:
            try:
                Organization.s3.delete_object(Bucket=Organization.bucket_name, Key=old_key)
            except:
                pass

        # upload new file
        image_key = str(datetime.now())

        for char in [' ', ':', '.', '-']:
            image_key = image_key.replace(char, "")

        image_key += os.path.splitext(path)[1]
        with open(path, 'rb') as f:
            Organization.s3.upload_fileobj(f, Organization.bucket_name, image_key)
        
        url = Organization.s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': Organization.bucket_name,
            'Key': image_key
        },

        ExpiresIn=12000
    )

        return url
            # generated at 11:42
        # return new link
        


    # NOTE: This should probably add a Member object. at a minimum, it needs to take more info
    # so that we can properly manage and reference the member
    def addMember(self, member):
        self.members.append(member)
        return member


    # Return form object by ID
    def getFormByID(self, id):
        return self.forms[id]

    # Set the currnt form by ID. ID is same as child index in UI when listing all forms.
    # Current form is used when we want to "Add Existing Responses" we know which form its referred to.
    def setCurrentForm(self, id):
        self.currentForm = self.forms[id]

    # Create pdf from desktop site using json data
    def createPdfFromDesktop(self, fields, title, due):
        newForm = PdfGenerator.createPdf(fields, title, due, self)
        self.forms.append(newForm) # Add the new form
        return newForm

        

    # Organization wants to create a new form using the button. 
    # It must be given a new formID, the number of created forms.
    # returns the form object
    def generateNewForm(self, path, title, desc, due):

        formID = len(self.forms)
        newForm = PdfGenerator.generateForm(path, title, desc, formID, due, self)

        # Create, upload and store the path of the printable in s3
        printablePath = PdfGenerator.printForm(newForm)
        newForm.printable = Organization.uploadS3(printablePath, "")

        self.forms.append(newForm)
        self.currentForm = newForm
        return newForm

    # Send a request of this form to this target. Can be a list, or singleton
    # NOTE: Called from: UI "Send Form" button from desktop by organization
    def sendFormRequest(self, form, targets):

        try:
            some_object_iterator = iter(targets)
        except TypeError as te:
            # Not iterable (singleton)
            fields = []
            for field in form.fields[:]:
                newField = pdfElement(field.name, field.type, field.value, field.index, field.rect, field.generated, field.pageHeight, field.pageWidth, field.pageIndex)
                fields.append(newField)

            newReq = pdfRequest(form.name, form.due, self, fields, form.formID, form.printable)
            targets.receiveFormRequest(newReq)
            return

        for target in targets:
            # Create the request and call recieve in member
            fields = []
            for field in form.fields[:]:
                newField = pdfElement(field.name, field.type, field.value, field.index, field.rect, field.generated, field.pageHeight, field.pageWidth, field.pageIndex)
                fields.append(newField)
                
            newReq = pdfRequest(form.name, form.due, self, fields, form.formID, form.printable)
            target.receiveFormRequest(newReq)

    # We have recieved a member's response! Append it and refresh our view list.
    # We must store this updated list to save the responses on the server
    def receiveFormResponse(self, response):
        new_response = copy.deepcopy(response)

        # RETURN AND STORE THE s3 BUCKET LINK HERE
        new_response.pdf = self.saveResponseAsPdf(new_response)
        
        id = new_response.formID
        form = self.forms[id]
        
        self.responses.append(new_response) # Cool, but we want to rather store this in the form's response list, not orgs
        form.responses.append(new_response)
        # UPDATE THE s3 EXCEL SHEET AND STORE IT
        excelPath = PdfGenerator.generateExcel(form)
        form.excel = Organization.uploadS3(excelPath, form.excel)

        # TODO: Here we will refresh the UI on desktop to show the new response, and store the new result (database?)
         # Creates a pdf with the responses and saves it to pc
        # TODO: Send email to organization that member has submitted!
        # TODO: Send confirmation email to member that their response was recieved



    # Store the response as a pdf
    # enters the necessary directory, or creates it
    # then, calls generatePdf which implicitly then populates the pdf with our responses
    #TODO upload to s3 here and return the link

    def saveResponseAsPdf(self, response):

        formID = response.formID
        form = self.getFormByID(formID)
        formName = form.name
        
        try: 
            os.mkdir("responses") 
        except OSError as error: 
            pass # Directory exists

        try: 
            os.mkdir("responses/" + formName) 
        except OSError as error: 
            pass # Directory exists

        path = "responses/"+formName+"/"

        pdf = PdfGenerator.generatePdf(response, path)
        # TODO upload to s3 here. Then, return the s3 link.
        return Organization.uploadS3(pdf, "") # pass the new file and the old version which we will unlink.


    # I uploaded a form on behalf of members. 
    # Turn each pdf into a form object
    # We have a reference to the current form, where we can gather most fields.
    # NOTE: This function has to rely on databse info so im not sure it can be autonomous.
    # Can we access db through the lambda? I need to iterate over every form the organization has to see if there's
    # a response for this form, also need to iterate over members to see if their na

    def addExisitngResponses(self):
        # For each form look for a folder of its name
        for form in self.forms:
            # Set currentForm so we add responses to the correct form folder
            self.currentForm = form
            title = form.name
    
            # Must only continue if responses in input/title/

            # If this file has an input folder: NOTE: If it doesnt, was it deleted? One should be made when the form is created
            if os.path.isdir("input/"+title):

                for file in os.listdir("input/"+title):
                    matches = [] # Each file will have a new member list, found below:
                    member = None
                    firstName = ""
                    lastName = ""

                    if file.endswith(".pdf"):
                        path = os.path.join("input/"+title, file)
                        # First we must convert to a response object
                        # I will first gather the fields by converting to form object
                        complete = PdfGenerator.generateForm(path, self.currentForm.name, self.currentForm.formID, self.currentForm.due, self.currentForm.org)
                        # I will now use complete.fields to gather the person who responded.

                        
                        
                        for field in complete.fields:
                            # Field says firstname, so store the first name
                            if field.name in Consts.firstNameFields:
                                firstName = field.value.capitalize()

                            # Field says name so its probably first and last
                            if field.name in Consts.nameFields:
                                splitName = field.value.split(" ")
                                
                                # Store first and maybe last name
                                firstName = splitName[0].capitalize()
                                if len(splitName) == 2:
                                    lastName = splitName[1].capitalize()

                            # We are given last name so store last name
                            if field.name in Consts.lastNameFields:
                                lastName = field.value.capitalize()

                            """ We have all possible info about the name, now try to find the member(s) matching the criteria """
                            if lastName:
                                # We have a last name so find all members with the last name AND first because we will always have first
                                for m in self.members:
                                    if (m.lastName == lastName):
                                        # Now check first name
                                        if (m.firstName == firstName):
                                            matches.append(m)
                                # Here our matches must have at least one because we had a last name given.
                                # If we don't have any matches, it may be because last name not stored in system.
                                """ Widen search to just look for first names since we found none with last name"""
                                if len(matches) == 0:
                                    for m in self.members:
                                        if (m.firstName == firstName):
                                            matches.append(m)

                            # Try just searching first names if we got no matches
                            else: # We only have first name data
                                for m in self.members:
                                    if (m.firstName == firstName):
                                        matches.append(m)

                            """ We're ready to parse results. If one is found, perfect! it is our member. """
                            if len(matches) == 1:
                                member = matches[0]
                            
                            """ We're finished gathering results. If multiple, show UI to select or create new. """
                            if len(matches) == 0: # No matches found! Must select from all, or add new!
                                print(firstName + " "+ lastName +" was not a member so we have added them. This should prompt org, not just do it by auto!")
                                member = Member(firstName, lastName)
                                self.members.append(member)

                            # If we have multiple members with this name, present UI to choose which one
                            elif (len(matches) > 1):
                                #TODO: UI will determine which member (auto - detect halts)
                                # When response comes, we continue
                                # NOTE: at this point, member is set to the first occurance of the member that we found w this name
                                print("Multiple members found with name "+firstName+" "+lastName+"! Add UI to prompt which one in digiFormClasses.addExistingResponse().")
                            # Here we successfully have set the value of member (after UI prompt)


                            break # We already found the member so no need to keep looking


                        if (member == None):
                            # We failed to set the member because we could not find the name!
                            # TODO: Present UI with option to select member from list where we can search for a member,
                            # OR we have option to add a new member as a button at the bottom of the widget.
                            print("No field 'name' found! Add UI to prompt member selection / addition in digiFormClasses.addExistingResponse().")
                            return # FOR NOW WE FAIL TO ADD THIS FORM UNTIL WE LEARN HOW TO CHOOSE MEMBER FROM UI AS ABOVE
                        # Member is found!
                                
                        # Gather time of last modification
                        ti_m = os.path.getmtime(path)
                        m_ti = time.ctime(ti_m)

                        # Create and add the complete response to the array of responses
                        # This is like how in the DB responses will be added and associated with the form, the member who responded
                        # and all other details
                        response = pdfResponse(member, m_ti, complete.fields, self.currentForm.formID, self.currentForm.org, member.firstName+' '+member.lastName)
                        self.currentForm.responses.append(response) 

                        # Add the form file to folder of complete PDF documents
                        self.saveResponseAsPdf(response)
            else:
                # Make the directory because it mustve been deleted
                os.mkdir("input/"+title)