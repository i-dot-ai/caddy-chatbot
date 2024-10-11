from flask import Flask, render_template, request, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import check_password_hash, generate_password_hash
import boto3
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'placeholder-secret-key'


dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
question_table = dynamodb.Table('Evaluation-Questions')
answer_table = dynamodb.Table('Evaluation-Answers')


class LoginForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    pwd = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class QuestionForm(FlaskForm):
    sub_questions = TextAreaField('What Questions would you ask?')
    useful_info = TextAreaField('Useful Information')
    useful_links = TextAreaField('Useful Links')
    submit = SubmitField('Save')

@app.route('/health')
def health_check():
    return "OK", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Always allow the user to log in
        session['auth'] = form.name.data
        return redirect(url_for('index'))
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.pop('auth', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'auth' not in session:
        return redirect(url_for('login'))
    questions = question_table.scan()['Items']
    #questions = [{'QuestionId': 1, "QuestionString": 'Help I am getting deported'}]
    return render_template('index.html', questions=questions)

@app.route('/questions/<int:id>', methods=['GET', 'POST'])
def question_details(id):
    if 'auth' not in session:
        return redirect(url_for('login'))
    
    question = question_table.get_item(Key={'QuestionId': id})['Item']
    #question = {'QuestionId': 1, "QuestionString": 'Help I am getting deported'}
    form = QuestionForm()
    
    if form.validate_on_submit():
        answer_table.put_item(Item={
            'AnswerId': str(uuid.uuid4()),
            'UserName': session['auth'],
            'QuestionId': str(id),
            'FollowOnQuestions': form.sub_questions.data,
            'UsefulInfo': form.useful_info.data,
            'UsefulLinks': form.useful_links.data,
        })
        return redirect(url_for('index'))
    
    return render_template('question_details.html', question=question, form=form)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)