from flask import render_template, request, redirect
from app import app, host, port, user, passwd, db
from app.helpers.database import con_db
from operator import attrgetter
from forms import SubmitForm  # for front-back-end interface
from .cuery_base import *  # for analytics


# ROUTING/VIEW FUNCTIONS
@app.route('/')
@app.route('/index')
def index():
    return render_template('landing.html')
    # Renders index.html.
    return render_template('index.html', output='My Dynamic Content')


@app.route('/query', methods=['GET', 'POST'])
def query():

    form = SubmitForm(csrf_enabled=False)
    ret_form = request.form

    if form.validate_on_submit():
        Cuery1 = None
        Cuery1 = Cuery('Cuery1')
        Cuery1.Origin_form = str(ret_form.getlist('origin_in')[0])
        Cuery1.Destin_form = str(ret_form.getlist('destin_in')[0])
        Cuery1.Category_form = str(ret_form.getlist('category_in')[0])

        # , Cuery1.Autonly_form
        print Cuery1.Origin_form, Cuery1.Destin_form, Cuery1.Category_form

        # Populate CardidateSet
        Cuery1.load_cardidates(
            year=CueryConst.CurrentYr,
            Ed_api_key='b2y9528hx2jy435qxsp9m8dp',
            home_state=Cuery1.home_state,
            home_zip=Cuery1.home_zip)

        # Set Cuery1.TripSet
        Cuery1.TripSet[0] = Trip(
            index=0,
            origin=Cuery1.Origin_form,
            destination=Cuery1.Destin_form,
            frequency=1)
        Cuery1.TripSet[1] = Trip(
            index=0,
            origin=Cuery1.Destin_form,
            destination=Cuery1.Origin_form,
            frequency=1)

        Cuery1.run_analytics()

        AllCardidatesRanked = None
        AllCardidatesRanked = sorted(
            Cuery1.CardidateSet,
            key=attrgetter('total_cost'),
            reverse=False)

        if Cuery1.Category_form == 'Small Cars':
            out_num = 16
        else:
            out_num = 5

        return render_template(
            'results.html',
            output=AllCardidatesRanked[
                :out_num])

    return render_template('submit.html', title='Query', form=form)


@app.route('/notes')
def notes():

    return render_template('notes.html')


@app.route('/slides')
def slides():
    # Renders slides.html.
    return render_template('slides.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
