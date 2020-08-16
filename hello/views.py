from django.shortcuts import render
from django.http import HttpResponse

from .models import Greeting
from darksky import forecast
import datetime
from pytz import timezone

import urllib.request
import json
import statistics

# soil moisture sensor data - last 24 hrs
request = urllib.request.urlopen("https://api.thingspeak.com/channels/180968/feeds.json?results=24")
sm_data = json.load(request)['feeds']
sm_list = []
for i in sm_data:
    sm_list.append(int(i['field1']))

sm_avg = round(statistics.mean(sm_list),2)

# darkSky Data
apikey = "4220aeb6ebb11c7abd00a31ae35cab06"

def weather(latitude, longitude):
    LOCATION = latitude, longitude
    with forecast(apikey, *LOCATION) as location:
        return(location['hourly']['data'][0])

kingsland = weather(40.734871, -73.943382) 

# Create your views here.
def index(request):
    # return HttpResponse('Hello from Python!')
    person={'firstname': 'Kingsland', 'lastname': 'Wildflowers'}
    #time = kingsland['time']
    #time = datetime.datetime.utcfromtimestamp(time)
    now_utc = datetime.datetime.now(timezone('UTC'))
    now_eastern = now_utc.astimezone(timezone('US/Eastern'))
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    summary = kingsland['summary']
    precipIntens = kingsland['precipIntensity']
    precipProb = kingsland['precipProbability']
    temp = kingsland['temperature']
    dewPoint = kingsland['dewPoint']
    humidity = kingsland['humidity']
    windSpeed = kingsland['windSpeed']
    windBearing = kingsland['windBearing']
    cloudCover = kingsland['cloudCover']
    visibility = kingsland['visibility']
    ozone = kingsland['ozone']
    plantProfile = {'build_type': 'Green Roof', 'water_type': 'Drought Tolerant'}
    fc = 14
    pwp = 5
    ## irrigation rec
    if sm_avg >= fc and precipProb < 0.80:
        hours = "36 to 48"
    elif sm_avg >= fc and precipProb >= 0.80:
        hours = "48 to 60"
    elif sm_avg < fc and precipProb < 0.80:
        hours = "0 to 12"
    elif sm_avg < fc and precipProb >= 0.80:
        hours = "12 to 24"
    elif sm_avg <= pwp+1:
        hours = "0 to 6"
    else:
        hours = "24"
        
    # pass in context 
    context = {
        'person': person,
        'time': now_eastern.strftime(fmt),
        'summary': summary,
        'precipIntens': precipIntens,
        'precipProb': precipProb,
        'temp': temp,
        'dewPoint': dewPoint,
        'humidity': humidity,
        'windSpeed': windSpeed,
        'fc': fc,
        'pwp': pwp,
        'plantProfile': plantProfile,
        'hours': hours,
        'sm_avg': sm_avg
        
    }
    
    return render(request, "index.html", context)


def db(request):

    greeting = Greeting()
    greeting.save()

    greetings = Greeting.objects.all()

    return render(request, "db.html", {"greetings": greetings})
