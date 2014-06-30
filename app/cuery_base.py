import json
import requests
import time
import secret
import copy
import MySQLdb as db
import pandas.io.sql as psql
import pandas as pd
import numpy as np


class CueryConst():
    CurrentYr = 2014
    # http://www.gasbuddy.com/GasPriceReport.aspx?state=CA&site=All
    state_gas_price = {'CA': 4.114}
    state_dsl_price = {'CA': 4.130}
    # lbs of CO2 per gallon https://www.chargepoint.com/files/420f05001.pdf
    CO2_pg_gas = 19.4
    CO2_pg_dsl = 22.2  # lbs of CO2 per gallon
    # from Table A3. Energy prices by sector and source (continued)
    annual_gas_price_incr = 0.021
    # (nominal dollars per million Btu, unless otherwise noted)
    annual_dsl_price_incr = 0.025
    num_years = 5  # no. of years considered
    total_vehicle_miles = float(22371 + 21948 + 25957 + 28395 + 26379 + 28578 +
                                28276 + 29175 + 23749 + 27621 + 28782 + 29063) * 10 ** 6  # for CA in 2011
    total_highway_length = float(1279 + 1174 + 1539 + 6550)  # 2011
    # accidents/mile of highway per day in 2011
    highway_AccidentRate = 144133.0 / (total_highway_length * 365.25)
    # = 0.0374326169135
# http://www.fhwa.dot.gov/policyinformation/statistics/2011/hm20.cfm
# exp CDF, F(x) = 1-e**(-lambda*x)


class Cardidate(object):

    def __init__(self, make, model, trim, model_year, state_code, zip_code):
        self.make = make
        self.model = model
        self.model_prop = model
        self.trim = trim
        self.year = model_year
        self.home_state = state_code
        self.home_zip = zip_code
        self.fuel_cost = 0.0
        self.other_cost = 0.0
        self.total_cost = 0.0
        self.total_CO2 = 0.0
        self.Ed_Id = '200498303'
        self.trany = 'Auto'
        self.fuel_type = 1  # 1= 'Gas', 2='Dsl, 'E'
        self.mpg = {
            'City': 25.0,
            'HiWay': 30.0,
            'Comb': (
                0.6 *
                25 +
                0.4 *
                30),
        }

    def get_total_cost(self):
        self.total_cost = int(self.fuel_cost + self.other_cost)

    def seg_fuel_coster(self, tgt_Seg, Acc_Part, fuel_price):
        '''
        Calculate cost of fuel for a given segment,
        and portion of highway that is affected by accident

        '''
        if (tgt_Seg.seg_type == 'U'):
            seg_fuel_cost = float(
                tgt_Seg.length) / self.mpg['City'] * fuel_price
        elif (tgt_Seg.seg_type == 'H'):
            seg_fuel_cost = float(tgt_Seg.length) * fuel_price * (
                Acc_Part / self.mpg['City'] + (1 - Acc_Part) / self.mpg['HiWay'])
        else:
            seg_fuel_cost = 0.0

        self.fuel_cost += seg_fuel_cost


class Segment(object):

    def __init__(self, index, AccidentRate, xxx_todo_changeme, seg_type):
        (length) = xxx_todo_changeme
        self.index = index
        # no. of accidents per million vehicle miles per year
        self.AccidentRate = float(AccidentRate)
        self.length = float(length)  # length of segment in miles
        self.seg_type = seg_type  # U = urban, H = highway
        # print 'self.length=' , self.length


class Trip(object):

    def __init__(self, index, origin, destination, frequency):
        self.TripIndex = index
        self.TripOrigin = origin
        self.TripDestin = destination
        self.Tripfrequency = frequency
        self.SegmentSet = None

    def router(self):
        '''
        Send O-D pair to Google Directions API, obtain response, write into segments
        References
        1) stackoverflow.com/questions/6386308/http-requests-and-json-parsing-in-python
        2) https://developers.google.com/maps/documentation/directions/
        use http:// in seed_url and remove key= in params to use open, unsecured API call

        '''
        seed_url = 'https://maps.googleapis.com/maps/api/directions/json?'

        # use "Century City, Los Angeles, CA" to "Los Angeles, CA" to test
        # hybrids
        params = dict(
            origin=self.TripOrigin,
            destination=self.TripDestin,
            key=secret.goog_dir_api)

        resp = requests.get(url=seed_url, params=params)
        # print 'in router, response fr. Goog=', resp.content  # print output
        output = json.loads(resp.content)
        time.sleep(0.11)

        # Determine no. of steps, create array for all steps
        # num_legs = len(output['routes']['legs']['steps']['html_instructions'])
        SegmentSet = [
            Segment(
                index=i,
                AccidentRate=0.0,
                length=0.0,
                seg_type=None) for i in range(50)]
        SegmentBinSet = [
            Segment(
                index=i,
                AccidentRate=0.0,
                length=0.0,
                seg_type=None) for i in range(2)]

        # Convert step-by-step directions into segments
        idx_ctr = 0
        for route in output['routes']:
            for leg in route['legs']:
                for step in leg['steps']:
                    desc_temp = step['html_instructions']
                    dist_temp = float(
                        step['distance']['value']) / 1609.344  # convert dist in m to miles
                    # print 'in router- dist_temp=', dist_temp
                    if (desc_temp.find("I-") > -
                            1 or desc_temp.find("CA-") > -
                            1 or desc_temp.find("US-") > -
                            1 or desc_temp.find("Expy") > -
                            1):
                        SegmentSet[idx_ctr] = Segment(
                            index=idx_ctr,
                            AccidentRate=CueryConst.highway_AccidentRate,
                            length=float(dist_temp),
                            seg_type='H')
                    else:
                        SegmentSet[idx_ctr] = Segment(
                            index=idx_ctr,
                            AccidentRate=0.0,
                            length=float(dist_temp),
                            seg_type='U')

                    # print step['html_instructions'], step['distance']['text']
                    # print SegmentSet[idx_ctr].index,
                    # SegmentSet[idx_ctr].length,
                    # SegmentSet[idx_ctr].seg_type#,
                    # SegmentSet[idx_ctr].AccidentRate
                    idx_ctr += 1

        self.SegmentDiscrete = SegmentSet

        SegmentBinSet[0] = Segment(
            index=0,
            AccidentRate=CueryConst.highway_AccidentRate,
            length=0.0,
            seg_type='H')
        SegmentBinSet[1] = Segment(
            index=1,
            AccidentRate=0.0,
            length=0.0,
            seg_type='U')

        for Segmentdum in SegmentSet:
            if Segmentdum.seg_type == 'H':
                SegmentBinSet[0].length += Segmentdum.length
            elif Segmentdum.seg_type == 'U':
                SegmentBinSet[1].length += Segmentdum.length
        self.SegmentSet = SegmentBinSet


class CarYear(object):

    def __init__(self, yr_index, TripSet):
        self.yr_index = yr_index
        self.yr_gas_price = copy.copy(CueryConst.state_gas_price)
        self.yr_dsl_price = copy.copy(CueryConst.state_dsl_price)
        self.TripSet = TripSet
        for key in self.yr_gas_price:
            dummy_gas = copy.copy(CueryConst.state_gas_price[key])
            self.yr_gas_price[key] = dummy_gas * \
                (1 + CueryConst.annual_gas_price_incr) ** yr_index
            dummy_dsl = copy.copy(CueryConst.state_dsl_price[key])
            self.yr_dsl_price[key] = dummy_dsl * \
                (1 + CueryConst.annual_dsl_price_incr) ** yr_index


class Cuery(object):

    def __init__(self, name):
        self.CueryName = name
        self.home_zip = '94703'
        self.home_state = 'CA'
        self.TripSet = [
            Trip(
                index=i,
                origin=None,
                destination=None,
                frequency=0.0) for i in range(2)]
        self.CarYearSet = [
            CarYear(
                yr_index=i,
                TripSet=self.TripSet) for i in range(
                CueryConst.num_years)]
        self.CardidateSet = [
            Cardidate(
                make=None,
                model=None,
                trim=None,
                model_year=CueryConst.CurrentYr,
                state_code=self.home_state,
                zip_code=self.home_zip) for i in range(5)]
        self.Origin_form = None
        self.Destin_form = None
        self.Category_form = None
        self.Autonly_form = False

    def load_cardidates(self, year, Ed_api_key, home_state, home_zip):
        '''
        Populate set of cardidates in self, from db
        '''

        # load car entries from db
        conn = db.connect(
            host='localhost',
            user='root',
            db='cars',
            passwd=secret.mysql_pwd)

        # sql_query='SELECT * FROM testdata' # model_trim' #   #older test
        sql_query = "SELECT * FROM AllCars  WHERE  CarCategory = \'"
        sql_query = sql_query + self.Category_form + "\';"

        CarsDF = psql.read_frame(sql_query, conn)

        ctr = 0
        num_cars = len(CarsDF)

        #  resize CardidateSet
        self.CardidateSet = [
            Cardidate(
                make=None,
                model=None,
                trim=None,
                model_year=CueryConst.CurrentYr,
                state_code=self.home_state,
                zip_code=self.home_zip) for i in range(num_cars)]

        for ii in range(num_cars):
            self.CardidateSet[ii].model = CarsDF.loc[
                ii,
                'model']  # _trim_name']
            self.CardidateSet[ii].model_prop = CarsDF.loc[ii, 'model_prop']
            self.CardidateSet[ii].make = CarsDF.loc[ii, 'make']  # _id']
            self.CardidateSet[ii].year = CarsDF.loc[
                ii,
                'year']  # CarsDF.loc[ctr,'model_year']
            self.CardidateSet[ii].other_cost = CarsDF.loc[ii, 'cost_other_5yr']
            self.CardidateSet[ii].fuel_cost = 0.0
            self.CardidateSet[ii].Ed_Id = CarsDF.loc[
                ii,
                'Ed_Id']  # CarsDF.loc[ctr,'ed_id']
            self.CardidateSet[ii].fuel_type = int(CarsDF.loc[ii, 'fuel_id'])
            self.CardidateSet[ii].trany = CarsDF.loc[ii, 'trany']
            self.CardidateSet[ii].mpg = {
                'City': CarsDF.loc[
                    ii, 'mpg_City'], 'HiWay': CarsDF.loc[
                    ii, 'mpg_HiWay'], }  # 'Comb':CarsDF.loc[ctr,'mpg_Com'], }
            ctr += 1

    def run_analytics(self):
        '''
        Function that runs analytics, using all information stored in self.*
        '''

        for Trip in self.TripSet:
            Trip.router()  # Generate SegmentSet for each Trip

        for CarYr in self.CarYearSet:
            for Trip in self.TripSet:
                # Generate traffic conditions here
                for Cardidatedum in self.CardidateSet:

                    if Cardidatedum.fuel_type == 2:  # 'Dsl':
                        fuel_price = CarYr.yr_dsl_price['CA']
                    else:  # Cardidatedum.fuel_type == 1: #'Gas':
                        # replace 'CA' with state_code variable in future
                        fuel_price = CarYr.yr_gas_price['CA']
                    # print 'fuel_price=', fuel_price

                    for tgt_Segment in Trip.SegmentSet:
                        Cardidatedum.seg_fuel_coster(
                            tgt_Seg=tgt_Segment,
                            Acc_Part=0.0,
                            fuel_price=fuel_price)

        # Derive total cost
        for Cardidatedum in self.CardidateSet:
            # print "car fuel cost=", Cardidatedum.fuel_cost
            # convenient calculation for now. will factor in accident in future
            Cardidatedum.fuel_cost = Cardidatedum.fuel_cost * 250
            Cardidatedum.get_total_cost()

            if Cardidatedum.fuel_type == 2:  # 'Dsl':
                Cardidatedum.total_CO2 = int(
                    CueryConst.CO2_pg_dsl *
                    Cardidatedum.fuel_cost /
                    CarYr.yr_dsl_price['CA'])
            else:  # Cardidatedum.fuel_type == 1: #'Gas':
                Cardidatedum.total_CO2 = int(
                    CueryConst.CO2_pg_gas *
                    Cardidatedum.fuel_cost /
                    CarYr.yr_gas_price['CA'])
