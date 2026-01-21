from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app.staff import bp
from app.database import get_db

@bp.route('/mentor')
@login_required
def mentor():
    return render_template('mentor.html')

@bp.route('/advisor')
@login_required
def advisor():
    return render_template('advisor.html')

@bp.route('/hod')
@login_required
def hod():
    return render_template('hodd.html')
