import shutil
from bson import ObjectId
import certifi
from flask import Flask, current_app, request, make_response, send_file
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from pdf_manager import PdfGenerator
from extract import extraction
import json, os
from flask_cors import CORS, cross_origin

class Api:
    load_dotenv('.env')
    EXTRACT_KEY = os.getenv('EXTRACT_KEY')
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
    MONGO_URI = os.getenv('mongo')

    def now():
        current_datetime = datetime.now()
        formatted_string = str(current_datetime).replace('-', '').replace(' ', '').replace(':', '')
        return formatted_string.split('.')[0][:-2] # ignores seconds




    app = Flask(__name__)
    CORS(app)
    cross_origin(origins="*")

        # Connect to MongoDB
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['docxtract']

    db_forms = db['forms']
    db_requests = db['requests']
    db_responses = db['responses']
    db_users = db['users']


    # send a form to users
    @app.route('/sendFormRequest', methods = ['POST'])
    def sendFormRequest():
        users_param = request.form.get('users')

        # If no users provided, set all of them
        if users_param:
            users = json.loads(users_param)['users']
        else:
            users = []
            user_items = Api.db_users.find()

            # Add the id of each user if none were specified
            for u in user_items:
                users.append(str(u['_id']))

        target_form = request.form.get('form')

        # for each id, add the form id to their user entry in the database
        for user in users:

            # Only send the request if the user does not have an active request for this form
            if Api.db_requests.find_one({'user': user, 'form': target_form}):
                continue

            # Add a new request object - can reference each response.
            form = Api.db_forms.find_one({'_id': ObjectId(target_form)})

            req = Api.db_requests.insert_one({'user': user, 'form': target_form, 'submissions_remaining': form['num_submissions']})
            req_id = req.inserted_id

            # This request is now associated with the user
            Api.db_users.find_one_and_update({'_id': ObjectId(user)}, {"$push": {'requests': str(req_id)} })

            # Store the user in the list of recipients of the form, if and only if not already in the recip list
            already = Api.db_forms.find_one({'_id': ObjectId(target_form), 'recipients': user})

            if not already:
                Api.db_forms.find_one_and_update({'_id': ObjectId(target_form)}, {"$push": {'recipients': user} })

            # TODO send email
            

        return make_response('Requests sent ', 200)
    
    # TODO revoke form method - for each user, pull the request from this user and delete all references to this request
    @app.route('/revokeForm', methods = ['POST'])
    def revokeForm():
        users_param = request.form.get('users')

        # If no users provided, set all of them
        if users_param:
            users = json.loads(users_param)['users']
        else:
            users = []
            user_items = Api.db_users.find()

            # Add the id of each user if none were specified
            for u in user_items:
                users.append(str(u['_id']))

        target_form = request.form.get('form')

        # Revoke all requests for this form from each user 
        for user in users:
            Api.revoke_requests(user, target_form)
            
        return make_response('Successfully revoked all occurances of the provided form from the listed user(s).', 200)

            
    # Helper method to revoke requests from a given user
    def revoke_requests(user, target_form):
        # Find and revoke any requests made for this form from the user
        for req in Api.db_requests.find({'user': user, 'form': target_form}):
            Api.db_users.update_one({'_id': ObjectId(user)}, {'$pull': {'requests': str(req['_id'])} })

        # Delete all request objects for this user that are for the given form
        Api.db_requests.delete_many({'user': user, 'form': target_form})



    # delete a form by id
    @app.route('/deleteForm/<id>', methods = ['POST'])
    def deleteForm(id):
        # maybe send an auth token too? api key as below?
        Api.db_forms.delete_one({'_id': ObjectId(id)})
        requests = Api.db_requests.find({'form': id})
        for req in requests:
            # Remove the request from the user
            Api.db_users.update_one({'_id': ObjectId(req['user'])}, {'$pull': {'requests': str(req['_id'])} })

        # Remove the requests for this form from the database
        Api.db_requests.delete_many({'form': id})

        # Delete each response from the db that was made for this form
        Api.db_responses.delete_many({'form': id})

        # Remove the form from the db
        Api.db_forms.delete_one({'_id': ObjectId(id)})


        if os.path.isdir(f'forms/{id}'):
            shutil.rmtree(f'forms/{id}')
            return make_response('Successfully deleted', 200)
        else:
            return make_response('Given id not found!', 404)

    @app.route('/createForm', methods = ['POST'])
    # TODO add api key param to prevent unauthorized access 
    def createForm():
        # Store needed data: title, submission_method, submission_date, 

        # Supplied pdf - null if user wants us to make them a form
        pdf = request.files.get('pdf')
        title = request.form.get('title')
        desc = request.form.get('description')
        num_submissions = request.form.get('num_submissions')
        submission_date = request.form.get('due_date')

        
        
        # create the database entry
        form = {
            'title': title,
            'description': desc,
            'num_submissions': int(num_submissions),
            'due_date': submission_date,
            'responses': [],
            'recipients': [], # used to view status of each request. We can fetch like this: recipients -> user -> requests -> status
        }

        res = Api.db_forms.insert_one(form)
        id = res.inserted_id
        
        # use the id to create a folder structure.
        if not os.path.isdir("forms"):
            os.mkdir("forms")
        os.mkdir(f"forms/{id}")
        os.mkdir(f"forms/{id}/responses")

        # Path to save original pdf to
        original_path = f"forms/{id}/original.pdf"

        # Make the pdf if necessary
        if not pdf:
            # We must have supplied fields json if no pdf
            fields_json = request.form.get('fields_json')
            PdfGenerator.create_pdf(fields_json, title, original_path)
        else:
            # save the pdf to the folder
            pdf.save(original_path)

        # get fields from the given pdf, insert to the db
        fields = PdfGenerator.pdf_to_fields(original_path)
        fields_json = PdfGenerator.fields_to_json(fields)

        # Reformat the field json to include each index as a key so they can be modified
        fields = {}
        numPages = 0
        for field in fields_json['fields']:

            # Keep track of the total number of pages
            if field['pageIndex'] > numPages:
                numPages += 1

            fields.update( 
                { field['index']: 
                    {"name": field['name'], 
                    "index": field['index'], 
                    "type": field['type'],
                    "value": field['value'],
                    "rect": field['rect'],
                    "pageHeight": field['pageHeight'],
                    "pageWidth": field['pageWidth'],
                    "pageIndex": field['pageIndex'],

                    "singleSelectionOnly": field['singleSelectionOnly'],
                    "groupName": field['groupName'],
                    "choiceName": field['choiceName'],
                    } } )
            
        # Add the fields to the entry
        Api.db_forms.find_one_and_update({'_id': ObjectId(id)}, {"$set": {'fields': json.dumps(fields), 'pages': (numPages + 1) }})


        # Using the original pdf, create a printable (no excel yet)
        PdfGenerator.print_form(original_path)

        return str(id)


    # Get all responses for a given form
    # Can optionally send a list of users to only show responses for those users

    @app.route('/getResponses/<id>', methods = ['POST', 'GET'])
    def getResponses(id):
        # return all responses to display
        all_responses = {}
       
        users_param = request.form.get('users')

        # If no users provided, set all of them
        if users_param:
            users = json.loads(users_param)['users']
        else:
            users = []
            user_items = Api.db_users.find()

            # Add the id of each user if none were specified
            for u in user_items:
                users.append(str(u['_id']))


        # Iterate over the user id strings
        for user in users:
            # Find any matching requests
            responses = Api.db_responses.find({'form': id, 'user': user})

            # If this user had any responses, add them all to the json
            if responses.length > 0:
        
                # For each response, add it to this user's array a new json object describing the response.
                user_responses = []
                for res in responses:
                    user_responses.append( {'response_id': str(res['_id']), 'response_date': res['date'], 'response_fields': res['fields']} )
                
                # Add all of this user's responses to the main json response
                all_responses.update({user: user_responses }) # Prepare this user's array

        return all_responses
    
    # Get the image of the given response id 
    # NOTE can get the response id through getResponses/<form_id>/
    # NOTE can also optionally pass users to the above post request
    @app.route('/getResponsePdf/<id>', methods = ['GET'])
    def getResponsePdf(id):
        # We need to get the id of the form by the response id.
        res = Api.db_responses.find_one({'_id': ObjectId(id)})
        form_id = res['form']
        user_id = res['user']

        path = f'forms/{form_id}/responses/{user_id}/{id}.pdf'
        return send_file(path, as_attachment=True)



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

    # Member submits the form.
    # Can call for either PDF or scanned image from mobile.
    @app.route('/submitForm/<user>/<req>', methods = ['GET','POST'])
    def submitForm(user, req):

        # Fetch the request object
        req_obj = Api.db_requests.find_one({'_id': ObjectId(req)})

        # If the request has 0 attempts remaining, fail and exit 
        if not req_obj:
            return make_response('Not authorized to respond! Are you out of attempts?', 403)

        # Fetch the form
        form_id = req_obj['form']
        form = Api.db_forms.find_one({'_id': ObjectId(form_id)})

        # Don't allow if past due. FIXME this should revoke the request when the date occurs
        # NOTE waste of time because it will be all front end based, just show past due and dont allow submit button.

        # If this is our last attempt, revoke the request so it doesn't show on available forms
        # Otherwise, decrease our requests if they are limited.
        if req_obj['submissions_remaining'] == 1:
            Api.revoke_requests(user, form_id)

        # If the form has limited attempts, decrease our remaining attempts by 1
        elif int(form['num_submissions']) > 0:
            Api.db_requests.find_one_and_update({'_id': ObjectId(req)}, {'$inc': {'submissions_remaining': -1}})

     
        # Store the file we submitted, if we uploaded a pdf
        pdf = request.files.get('pdf')

        # store the file to the response path
        response_folder = f'forms/{form_id}/responses/{user}'
        
        # make sure there is a folder for this user
        if not os.path.isdir(response_folder):
            os.mkdir(response_folder)

        # store the pdf in this user's folder for this form.
        # the name of the pdf is the id of the response
        response_id = ObjectId()
        response_path = response_folder + f'/{response_id}.pdf'

        # If we uploaded a pdf, we need to make a field array still (for excel sheet, mostly)
        if pdf:
            pdf.save(response_path)
            fields = PdfGenerator.pdf_to_fields(response_path)

        # If we did not, we already have a field array but we need to make the file
        else:
            fields = json.loads(request.data)['fields']
            source_path = f'forms/{form_id}/original.pdf'
            PdfGenerator.fields_to_pdf(fields, source_path, response_path)

        # Create the new response object, stringifying the fields
        Api.db_responses.insert_one({'_id': response_id, 'user': user, 'form': form_id, 'fields': json.dumps(PdfGenerator.fields_to_json(fields)), 'date': Api.now()}) # Do i need to add request?

        # Associate this response and excel sheet with the form
        Api.db_forms.find_one_and_update({'_id': ObjectId(form_id)}, {"$push": {'responses': response_id} })

        # Generate the new excel sheet
        form = Api.db_forms.find_one({'_id': ObjectId(form_id)})
        responses = []

        for res_id in form['responses']:
            # Iterate over the id of each response
            response = Api.db_responses.find_one({'_id': ObjectId(res_id)})

            # Note response['fields'] from db must be stringified json!
            responses.append(PdfGenerator.json_to_fields(response['fields'])) # add the response (array of fields)
        
        # Make the excel path and sheet
        excel_path = f'forms/{form_id}/excel.xlsx'
        PdfGenerator.generate_excel(responses, excel_path)
            
        return 'submitted form!'


    # This member will retrieve all its form requests
    @app.route('/getAllForms/<user_id>', methods = ['GET'])
    def getAllForms(user_id):
        
        dict = {  }
        user_obj = Api.db_users.find_one({'_id': ObjectId(user_id)})
        requests = user_obj['requests']

        for req in requests:
            # Get the request object 
            req_obj = Api.db_requests.find_one({'_id': ObjectId(req)})
            
            # Get the form object
            form = Api.db_forms.find_one({'_id': ObjectId(req_obj['form'])})
           
           # Note we no longer send printable link because it's not in the cloud.
           # Need a seperate api request that will return the image
            dict.update( {str(form['_id']): 
                          {
                           "name": form['title'],
                           "submissions_remaining": form['num_submissions'],
                           "description": form['description'],
                           "due": form['due_date'],
                           }} )

        return dict
    
    # Get the printable for a given form by the form id
    @app.route('/getPrintable/<id>', methods = ['GET'])
    def getPrintable(id):
        path = f'forms/{id}/print.pdf'
        return send_file(path, as_attachment=True)
    
    # Get the excel sheet for a given form by the form id
    @app.route('/getExcel/<id>', methods = ['GET'])
    def getExcel(id):
        path = f'forms/{id}/excel.xlsx'
        return send_file(path, as_attachment=True)
    
    # View this form that belongs to this member
    # Used when clicking on a form for example.
    # Very similar to get all forms, but we now add on the fields and number of pages as well.
    @app.route('/getForm/<id>/', methods = ['GET'])
    def getForm(id):

        form = Api.db_forms.find_one({'_id': ObjectId(id)})
        if not form:
            return make_response('Specified form was not found!', 404)
        
        # We found the form
        response = {"data": 
                        {
                            "name": form['title'],
                            "submissions_remaining": form['num_submissions'],
                            "description": form['description'],
                            "due": form['due_date'],

                        },
                            "fields": json.loads(form['fields']),
                            'pages': form['pages']
                    }
        return response
    

    def __init__(self):
        
        {

            self.app.run(host="0.0.0.0", debug=True, port= 8000)
            
        }

Api()


