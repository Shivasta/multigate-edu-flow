from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app.main import bp
from app.database import get_db

@bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@bp.route('/welcome')
def welcome():
    return render_template('welcome.html')
