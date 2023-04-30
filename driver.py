from digiFormClasses import Server, Member
from pdfStructure import pdfElement, Consts
from pdf_simulator import PdfGenerator

# Sample Driver code to simulate the system.
server = Server()

myOrg = server.createOrg("ABC Construction")
Bob = Member("Bob", "Smith")
Joe = Member("Joe", "Shmo")
Luna = Member("Luna", "Bird")

myOrg.addMember(Bob)
myOrg.addMember(Joe)
myOrg.addMember(Luna)


# Inspectors join the org
Sal = Member("Sal", "Fiore")
Mindy = Member("Mindy", "Smith")
Robin = Member("Robin", "Atwood")
Mike = Member("Mike", "Hamilton")

myOrg.addMember(Sal)
myOrg.addMember(Mindy)
myOrg.addMember(Robin)
myOrg.addMember(Mike)


# Org creates the forms, this dictates form ID's 
newForm = myOrg.generateNewForm("sample.pdf", "My Form", "01/01/01")
inspForm = myOrg.generateNewForm("inspection.pdf", "Inspection", "01/01/01")
multiForm = myOrg.generateNewForm("sample2page.pdf", "Multipage Form", "06/09/04")
cleanForm = myOrg.generateNewForm("sample-clean.pdf", "Clean Form", "06/09/04")
dispForm = myOrg.generateNewForm("disburse.pdf", "Disbursement Form", "01/01/01")

# Demonstrate creation of pdf document through frontend
fields = []
fields.append(pdfElement("First Name", Consts.textFieldDisplay, "", 0, None, True, None, None, 0))
fields.append(pdfElement("Last Name", Consts.textFieldDisplay, "", 1, None, True, None, None, 0))
fields.append(pdfElement("Address", Consts.textFieldDisplay, "", 2, None, True, None, None, 0))
fields.append(pdfElement("$Gender:Male", Consts.mcDisplay, "", 3, None, True, None, None, 0))
fields.append(pdfElement("$Gender:Female", Consts.mcDisplay, "", 4, None, True, None, None, 0))
fields.append(pdfElement("Likes Dogs", Consts.checkBoxDisplay, "", 5, None, True, None, None, 0))
webForm = myOrg.createPdfFromDesktop(fields, "Devin's Form", "02 / 30 / 23")
# cleans up page number, page height, rect objects and what not in pdf manager

PdfGenerator.printForm(newForm)
PdfGenerator.printForm(dispForm)
PdfGenerator.printForm(inspForm)
PdfGenerator.printForm(webForm)
PdfGenerator.printForm(cleanForm)

# Test field outlining in a multi page form
PdfGenerator.printForm(multiForm)



# Org sends these forms to all members
myOrg.sendFormRequest(newForm, myOrg.members)
myOrg.sendFormRequest(multiForm, myOrg.members)
myOrg.sendFormRequest(inspForm, myOrg.members)

# Member clicks on the form our org just created.
# In practice, this will be set when a form is clicked in UI
# This object then will be used to display and prompt member to fill in the fields

# Members select the single page form
Bob.selectForm(myOrg, 0)
Joe.selectForm(myOrg, 0)

#newForm.display() 

Bob.respondToField(0, "Bob Smith")
Joe.respondToField(0, "Joe Shmo")

Joe.respondToField(1, Consts.checkBoxDisplayYes)

Bob.respondToField(2, "Math")
Joe.respondToField(2, "Science")

Bob.respondToField(3, "Summer")
Joe.respondToField(3, "Fall")

# Demonstrate gender, a single response field being updated
Bob.respondToField(6, Consts.checkBoxDisplayYes)
Bob.respondToField(7, Consts.checkBoxDisplayYes)
Joe.respondToField(5, Consts.checkBoxDisplayYes)

# Bob likes cats
Bob.respondToField(4, Consts.checkBoxDisplayYes)

# Demonstrate symptoms, a multi response field being updated
Bob.respondToField(8, Consts.checkBoxDisplayYes)
Bob.respondToField(10, Consts.checkBoxDisplayYes)
Joe.respondToField(9, Consts.checkBoxDisplayYes)
Joe.respondToField(11, Consts.checkBoxDisplayYes)


#Submit the currently active form from the earlier selectForm call
# NOTE: This will occur from frontend when user presses submit button.
# Action: when server recieves it will download the document and store it in the correct directory.

Bob.submitFormResponse() 
Joe.submitFormResponse() 

# TESTING MULTIPLE PAGE FORM WITH BOB
Bob.selectForm(myOrg, 2)

Bob.respondToField(0, "Bob Second")
Bob.respondToField(2, "Multipage Forms")
Bob.respondToField(3, "Ice cold winter")
Bob.respondToField(6, Consts.checkBoxDisplayYes)
Bob.respondToField(10, Consts.checkBoxDisplayYes)
# PAGE 2
Bob.respondToField(13, Consts.checkBoxDisplayYes)
Bob.respondToField(12, "Writing on page 2!")

# Bob submits the multi page form
Bob.submitFormResponse()

# Test inspection form: First we select it
Sal.selectForm(myOrg, 1)
Mindy.selectForm(myOrg, 1)
Robin.selectForm(myOrg, 1)
Mike.selectForm(myOrg, 1)

Sal.respondToField(0, "14 Willow Ct")
Sal.respondToField(1, "2/11/23")
Sal.respondToField(2, "Sal Fiore")
Sal.respondToField(3, "Amanda Fuller")
Sal.respondToField(4, "7 Hamon Ln")
Sal.respondToField(5, "555-308-3726")
Sal.respondToField(6, Consts.checkBoxDisplayYes) # mold 13,15,16,18
Sal.respondToField(8, Consts.checkBoxDisplayYes) # electric
Sal.respondToField(9, Consts.checkBoxDisplayYes) # plumbing
Sal.respondToField(11, Consts.checkBoxDisplayYes) # foundation
Sal.respondToField(13, "Primary bathroom has black mold behind the sink. Requires complete remodel.")
Sal.respondToField(15, "Breakers #6 and #11 are oversized, must be reduced to 15a, or wires upgraded to 12g.")
Sal.respondToField(16, "Primary bathroom leak hidden behind wall causing mold & rot.")
Sal.respondToField(18, "Minor crack on west-side wall.")

Mindy.respondToField(0, "18 Jerry Drive")
Mindy.respondToField(1, "4/1/23")
Mindy.respondToField(2, "Mindy Smith")
Mindy.respondToField(3, "Jeremy Till")
Mindy.respondToField(4, "1 Pond Path")
Mindy.respondToField(5, "555-829-1918")
Mindy.respondToField(8, Consts.checkBoxDisplayYes)
Mindy.respondToField(15, "Wiring is old and ungrounded, should rewire entire home.")

Robin.respondToField(0, "42 Mill Road")
Robin.respondToField(1, "1/4/23")
Robin.respondToField(2, "Robin Atwood")
Robin.respondToField(3, "Amber Roslyn")
Robin.respondToField(4, "16 Cherry St")
Robin.respondToField(5, "555-284-7782")

Mike.respondToField(0, "11 Hay Ln")
Mike.respondToField(1, "12/18/22")
Mike.respondToField(2, "Mike Hamilton")
Mike.respondToField(3, "Carlos Amana")
Mike.respondToField(4, "1087 Express Drive N")
Mike.respondToField(5, "555-294-3398")
Mike.respondToField(7, Consts.checkBoxDisplayYes)
Mike.respondToField(10, Consts.checkBoxDisplayYes)
Mike.respondToField(14, "Improper ledger fasteners on deck")
Mike.respondToField(17, "Deteriorated flashing around chimney causing roof leak")

Robin.submitFormResponse()
Mike.submitFormResponse()
Sal.submitFormResponse()
Mindy.submitFormResponse()





# Demonstrate adding existing responses from organization submission
myOrg.addExisitngResponses()

# Generate excel 
PdfGenerator.generateExcel(newForm)
PdfGenerator.generateExcel(webForm)
PdfGenerator.generateExcel(multiForm)
PdfGenerator.generateExcel(inspForm)
PdfGenerator.generate_csv(inspForm)
# PdfGenerator.cropForm('test.png')