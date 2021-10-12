#  Copyright (c) 2020 PLANT Group, LLC
from django.shortcuts import render
from django.http import HttpResponse

from .models import Greeting
from darksky import forecast
import datetime
import time
import math
from math import sqrt
from pytz import timezone

import urllib.request
import json
import statistics

from pysolar.solar import *
from pysolar.radiation import *

# soil moisture sensor data - last 24 hrs
request = urllib.request.urlopen("https://api.thingspeak.com/channels/Your_TS_Channel_ID/feeds.json?results=12")
sm_data = json.load(request)['feeds']
sm_list = []
for i in sm_data:
    sm_list.append(int(i['field1']))

sm_avg = round(statistics.mean(sm_list),2)
# last element in list
sm_current = int(sm_data[-1]['field1'])

# darkSky Data - alive structures photon 
apikey = "Your_DS_apiKey"
# enter US GeoZone - east coast; Kingsland Wildflowers
geoZone = "US_East"
#irrigationType
irrigType = "drip"

def weatherStats(latitude, longitude):
    LOCATION = latitude, longitude
    with forecast(apikey, *LOCATION) as location:
        return(location['hourly']['data'])

# temp F to C conversion 
def convertC(temp):
    return(round((temp - 32) * (5/9), 2))

lat = 40.734871
lon = -73.943382
weatherStats = weatherStats(lat, lon)
# most recent weather data
kingsland = weatherStats[0]
# get temp min, max, avg - used for ETo model
# get dewPoint avg - used for ETo model 
tempStats = []
dewStats = []
windStats = []
for i in weatherStats[0:24]:
    tempStats.append(i['temperature'])
    dewStats.append(i['dewPoint'])
    windStats.append(i['windSpeed'])

try:
    tempLen = len(tempStats)
    tempMin = convertC(min(tempStats))
    tempMax = convertC(max(tempStats))
    tempAvg = convertC(round(statistics.mean(tempStats),2))
    dewAvg = convertC(round(statistics.mean(dewStats),2))
    windAvg = round(statistics.mean(windStats),2)
except:
    tempLen = None
    tempMin = None
    tempMax = None
    tempAvg = None
    dewAvg = None
    windAvg = None

# time
now_utc = datetime.datetime.now(timezone('UTC'))
now_eastern = now_utc.astimezone(timezone('US/Eastern'))
fmt = "%Y-%m-%d %H:%M:%S %Z%z"
# altitude
try:
    alt = round(get_altitude(lat, lon, now_utc),2)
    azimuth = round(get_azimuth(lat, lon, now_utc),2)
    # radiation
    rad = round(radiation.get_radiation_direct(now_utc, alt),2)
except:
    alt = None
    azimuth = None
    rad = None
    
### Evapotranspiration functions   
#: Solar constant [ MJ m-2 min-1]
SOLAR_CONSTANT = 0.0820
# Stefan Boltzmann constant [MJ K-4 m-2 day-1]
STEFAN_BOLTZMANN_CONSTANT = 0.000000004903  #
def deg2rad(degrees):
    return degrees * (math.pi / 180.0)   
# convert lat to radians 
lat = deg2rad(lat)

def avp_from_tdew(tdew):
    return 0.6108 * math.exp((17.27 * tdew) / (tdew + 237.3))
    
def svp_from_t(t):
    return 0.6108 * math.exp((17.27 * t) / (t + 237.3))

def delta_svp(t):
    tmp = 4098 * (0.6108 * math.exp((17.27 * t) / (t + 237.3)))
    return tmp / pow((t + 237.3), 2)

def atm_pressure(altitude):
    tmp = (293.0 - (0.0065 * altitude)) / 293.0
    return pow(tmp, 5.26) * 101.3

def psy_const(atmos_pres):
    return 0.000665 * atmos_pres

def sol_dec(day_of_year):
    return 0.409 * math.sin(((2.0 * math.pi / 365.0) * day_of_year - 1.39))

def sunset_hour_angle(latitude, sol_dec):
    cos_sha = -math.tan(latitude) * math.tan(sol_dec)
    return math.acos(min(max(cos_sha, -1.0), 1.0))

def daylight_hours(sha):
    return (24.0 / math.pi) * sha

def inv_rel_dist_earth_sun(day_of_year):
    return 1 + (0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year))

def et_rad(latitude, sol_dec, sha, ird):
    tmp1 = (24.0 * 60.0) / math.pi
    tmp2 = sha * math.sin(latitude) * math.sin(sol_dec)
    tmp3 = math.cos(latitude) * math.cos(sol_dec) * math.sin(sha)
    return tmp1 * SOLAR_CONSTANT * ird * (tmp2 + tmp3)

def cs_rad(altitude, et_rad):
    return (0.00002 * altitude + 0.75) * et_rad

def sol_rad_from_t(et_rad, cs_rad, tmin, tmax, coastal):
    # Determine value of adjustment coefficient [deg C-0.5] for
    # coastal/interior locations
    if coastal:
        adj = 0.19
    else:
        adj = 0.16

    sol_rad = adj * sqrt(tmax - tmin) * et_rad

    # The solar radiation value is constrained by the clear sky radiation
    return min(sol_rad, cs_rad)

def net_in_sol_rad(sol_rad, albedo=0.23):
    return (1 - albedo) * sol_rad

def net_out_lw_rad(tmin, tmax, sol_rad, cs_rad, avp):
    tmp1 = (STEFAN_BOLTZMANN_CONSTANT *
        ((pow(tmax, 4) + pow(tmin, 4)) / 2))
    tmp2 = (0.34 - (0.14 * sqrt(avp)))
    tmp3 = 1.35 * (sol_rad / cs_rad) - 0.35
    return tmp1 * tmp2 * tmp3

def net_rad(ni_sw_rad, no_lw_rad):
    return ni_sw_rad - no_lw_rad

def fao56_penman_monteith(net_rad, t, ws, svp, avp, delta_svp, psy, shf=0.0):
    a1 = (0.408 * (net_rad - shf) * delta_svp /
          (delta_svp + (psy * (1 + 0.34 * ws))))
    a2 = (900 * ws / t * (svp - avp) * psy /
          (delta_svp + (psy * (1 + 0.34 * ws))))
    return a1 + a2

################################
try:
    # Humidity
    vaporPressure = avp_from_tdew(dewAvg)
    satVapor = svp_from_t(tempAvg)
    satVaporSlope = delta_svp(tempAvg)
    # atmospheric pressure
    atmosphericPressure = atm_pressure(alt)
    # psychometric constant 
    psychoConstant = psy_const(atmosphericPressure)
    # radiation
    day_of_year = time.localtime().tm_yday
    # daily net rad 
    sol_declination = sol_dec(day_of_year)
    # sunset hour angle
    sunsetHourAngle = sunset_hour_angle(lat, sol_declination)
    daylightHours = daylight_hours(sunsetHourAngle)
    # inverse rel distance - sun-earth
    earthSunDist = inv_rel_dist_earth_sun(day_of_year)
    # estimated daily extraterrestrial radiatio 
    extraTerRad = et_rad(lat, sol_declination, sunsetHourAngle, earthSunDist)
    # estimated clear sky radiation 
    clearSkyRad = cs_rad(alt, extraTerRad)
    # gross radiation
    grossRadiation = sol_rad_from_t(extraTerRad, clearSkyRad, tempMin, tempMax, coastal=False)
    # net incoming solar (shortwave rad)
    # grass reference crop albedo
    netIncomingRad = net_in_sol_rad(grossRadiation, albedo=0.23)
    #net outgoing longwave evergy leaving earth's surface
    netOutgoingRad = net_out_lw_rad(tempMin, tempMax, grossRadiation, clearSkyRad, vaporPressure)
    # daily net radiation at crop surface
    dailyNetRadiation = net_rad(netIncomingRad, netOutgoingRad)
    # convert airtemp from C to K
    tempK = tempAvg + 273.15
    # FAO - penman-monteith ETo eq
    penmanMont = round(fao56_penman_monteith(dailyNetRadiation, tempK, windAvg, satVapor, vaporPressure, satVaporSlope, psychoConstant, shf=0.0),2)
    # convert from mm/day to in/day
    pET = round((penmanMont * 0.0393701),4)
    # amount of time to irrigate for (minutes)
    irrigationTime = int(pET/0.01667 + 0.5)
except:
    pET = None
    irrigationTime = None
################################

# irrigation rec - season inputs
currentMonth = datetime.datetime.now().month

if int(currentMonth) >= 8 and int(currentMonth) < 10 and irrigType == "drip":
    currentRec = "15 mins every 24 hrs"
elif int(currentMonth) > 10 and geoZone == "US_East" and irrigType == "drip":
    currentRec = " Time to winterize your system ... "
else:
    currentRec = "20 mins every 48 hrs"

# Create your views here.
def index(request):
    person={'firstname': 'Kingsland', 'lastname': 'Wildflowers'}
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
    
    if sm_avg <= pwp+1:
        sm_status = "Low soil moisture alert, consider irrigating."
    else:
        sm_status = currentRec
    
    ## irrigation rec
    if sm_avg >= fc and precipProb < 0.80:
        hours = "24 to 36"
    elif sm_avg >= fc and precipProb >= 0.80:
        hours = "36 to 48"
    elif sm_avg < fc and precipProb < 0.80:
        hours = "12 to 24"
    elif sm_avg < fc and precipProb >= 0.80:
        hours = "24 to 36"
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
        'sm_avg': sm_avg,
        'sm_current': sm_current,
        'sm_status': sm_status,
        'current_rec': currentRec,
        'pET': pET,
        'irrigationTime': irrigationTime
        
    }
    
    return render(request, "index.html", context)


def db(request):

    greeting = Greeting()
    greeting.save()

    greetings = Greeting.objects.all()

    return render(request, "db.html", {"greetings": greetings})
