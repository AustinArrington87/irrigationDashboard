# irrigationDashboard
Open Source Dashboard for Plant Group Irrigation Recommendations

######DEPLOYMENT STEPS######

- Update the Thingspeak sensor Channel ID and Darksky Weather api Key in views.py to match your application 
- Download Heroku CLI and Deploy Python / Django app with Heroku 

   $ heroku login

   $ git clone https://github.com/AustinArrington87/irrigationDashboard.git

   $ cd irrigationDashboard

   // make your edits - update api keys in view.py

   $ heroku create

   $ git commit -a -m "update made" 

   $ git push heroku master
