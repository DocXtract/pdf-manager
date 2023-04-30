from flask import Flask, current_app, request
from dotenv import load_dotenv
from digiFormClasses import Member, Server
from extract import extraction
import json, os
from flask_cors import CORS, cross_origin

class Api:
    load_dotenv('.env')
    EXTRACT_KEY = my_var = os.getenv('EXTRACT_KEY')
    AWS_ACCESS_KEY = my_var = os.getenv('AWS_ACCESS_KEY')
    AWS_SECRET_KEY = my_var = os.getenv('AWS_SECRET_KEY')


    app = Flask(__name__)
    CORS(app)
    cross_origin(origins="*")
    server = Server() # Make new static test server

    
    myOrg = server.createOrg("ABC Construction")
    myOrg.initializeBucket(AWS_ACCESS_KEY, AWS_SECRET_KEY)

    newForm = myOrg.generateNewForm("sample-clean.pdf", "My Form", "A basic sample form", "01/01/01")

    myMember = Member("Test", "Member")
    myOrg.addMember(myMember)

    myOrg.sendFormRequest(newForm, myMember)


    inspForm = myOrg.generateNewForm("inspection.pdf", "Inspection", "For residential home inspections", "01/01/01")
    myOrg.sendFormRequest(inspForm, myMember)

    dispForm = myOrg.generateNewForm("disburse.pdf", "Disbursement", "UAlbany Request for Disbursement", "01/01/01")
    myOrg.sendFormRequest(dispForm, myMember)

    @app.route('/getResponses/<id>', methods = ['POST', 'GET'])
    def getResponses(id):
        # return all responses to display
        
        # get the form & spreadsheet
        formObject = Api.myOrg.forms[int(id)]

        results = {-1: str(formObject.excel)}

        index = 0
        responses = Api.myOrg.responses
        
        for response in responses:
            if (int(response.formID) == int(id)):
                
                result = {
                    'date': response.completionDate,
                    'name': response.responderName,
                    'pdf': response.pdf # link to the resposnse to view it
                }
                
                results.update({index: result})
                index += 1


        return results

    @app.route('/extract', methods = ['POST'])
    def extract():
        # Save files to documents folder
        target=os.path.join('./','documents/uncropped')
        if not os.path.isdir(target):
            os.mkdir(target)
        files = request.files
        for i in files:
            file = request.files[i]
            destination = "/".join([target, i])
            file.save(destination)

        #Fetch fields from the formdata
        data = request.form.get('fields')
        fields = json.loads(data)

        updatedFields = extraction.fill_fields(fields, Api.EXTRACT_KEY)
        return updatedFields 

    # Member submits the form they are currently editing
    # TODO here we create the response through submitformresponse
    @app.route('/submitForm/', methods = ['GET','POST'])
    def submitCurrentForm():
        res = json.loads(request.data)
        fields = res['fields']

        for key in fields.keys():
            #print(fields[key])
            value = fields[key]['value'] # Dictionary of field name : field value, looking for key "value"
            Api.myMember.respondToField(int(key), value) # Respond to each field

        Api.myMember.submitFormResponse()
        # Create pdf response upload to s3 and store in database: s3 url, fields, form title, index of form, 
        return "Submitted "+Api.myMember.currentForm.name
    
    # Member saves current form
    @app.route('/saveForm/', methods = ['GET', 'POST'])
    def saveForm():
        res = request.body
        for key in res.keys():
            value = res[key]["value"] # Dictionary of field name : field value, looking for key "value"
            Api.myMember.respondToField(int(key), value) # Respond to each field

        # Same as above submit function but just stores and does not submit

    # This member updates a value for the active form
    # This is not used anymore because we instead want to just send all values at once
    @app.route('/updateField/<fieldIndex>/<newVal>/', methods = ['GET'])
    def updateField(fieldIndex, newVal):


        Api.myMember.respondToField(int(fieldIndex), newVal)
        return "Successfully set "+Api.myMember.currentForm.fields[int(fieldIndex)].name+" to "+newVal+"!"



    # This member will retrieve all its form requests
    
    @app.route('/getAllForms/', methods = ['GET'])
    def getAllForms():
        
        
        dict = {  }
        for form in Api.myMember.activeForms:
            formObject = Api.myOrg.forms[form.formID]
           
            dict.update( {form.formID: 
                          {"index": form.formID,
                           "complete": form.complete, 
                           "name": form.name,
                           "description": formObject.description,
                           "due": form.due,
                           "printable": form.printable,
                           "organizer": form.org.name}} )

        return dict
    
    # View this form that belongs to this member
    # Specific form details from id. This id is not index of activeForms. We must search active forms for this formID.
    # TODO add s3 link for printable
    @app.route('/getForm/<id>/', methods = ['GET'])
    def getForm(id):

        formObject = Api.myOrg.forms[int(id)]
        form = None
        for f in Api.myMember.activeForms:
            if f.formID == int(id):
                form = f
                Api.myMember.selectForm(Api.myOrg, f.formID)
                break
        if form:
            # We found the form! TODO: Also return the path so it can be printed
            #print(Api.myMember.currentForm.name)
             # add printable form link as above
            response = {"data": 
                        {"index": form.formID,
                         "complete": form.complete, 
                         "name": form.name, 
                         "description": formObject.description,
                         "due": form.due, 
                         "organizer": form.org.name,
                         "printable": form.printable,
                         }}

            # Now add the fields
            # NOTE: I included the height of the containing page for coordinate localization.
            fields = {}
            numPages = 0
            for field in form.fields:

                # Keep track of the total number of pages
                if field.pageIndex > numPages:
                    numPages += 1

                fields.update( 
                    { field.index: 
                     {"name": field.name, 
                      "index": field.index, 
                      "type": field.type,
                      "value": field.value,
                      "rect": field.rect,
                      "pageHeight": field.pageHeight,
                      "pageWidth": field.pageWidth,
                      "pageIndex": field.pageIndex,

                      "singleSelectionOnly": field.singleChoice,
                      "groupName": field.choiceGroup,
                      "choiceName": field.choiceValue,
                      } } )
                
            response.update( {"fields": fields} )
            
            response.update( { 'pages': numPages + 1 } )
            return response
        else:
            return "404 Form not found!"
    

    def __init__(self):
        
        {

            self.app.run(host="0.0.0.0", debug=True, port= 8000)
            
        }

Api()


