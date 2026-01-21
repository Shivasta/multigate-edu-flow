from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app.requests import bp
from app.database import get_db

@bp.route('/request_form')
@login_required
def request_form():
    return render_template('request_form.html')

@bp.route('/status')
@login_required
def status():
    return render_template('status.html')
