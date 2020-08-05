# encoding: utf-8
from flask import Flask, render_template, session,redirect,url_for,request,send_file,flash,jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, BooleanField
from wtforms.validators import InputRequired, Length, AnyOf
from flask_sqlalchemy import SQLAlchemy
from flask_restless import APIManager
from flask_moment import Moment
from io import BytesIO
from hashlib import md5
from datetime import datetime
from flask_bootstrap import Bootstrap

ALLOWED_EXTENSIONS = {'zip'}

app = Flask(__name__)
app.jinja_env.globals.update(zip=zip)
app.jinja_env.globals.update(len=len)
app.jinja_env.globals.update(int=int)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/marat/Документы/python25.07/rest/app.db'
app.config['SECRET_KEY'] = 'Mysecret!'
db = SQLAlchemy(app)
moment = Moment(app)
bootstrap = Bootstrap(app)

class Student(db.Model):
    id = db.Column(db.Integer,primary_key = True)
    name = db.Column(db.String(20))
    password = db.Column(db.String(20))
    tasks = db.relationship('Task',backref=db.backref('owner'))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def avatar(self, size):
        digest = md5(self.password.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)   

class Teacher(db.Model):
    id = db.Column(db.Integer,autoincrement=True,primary_key = True)
    name = db.Column(db.String(20))
    password = db.Column(db.String(20))

class Task(db.Model):
    id = db.Column(db.Integer,primary_key = True)
    name = db.Column(db.String(300))
    description = db.Column(db.String(500))
    data = db.Column(db.LargeBinary,nullable = True)
    student_id = db.Column(db.Integer,db.ForeignKey('student.id'))

class Rating(db.Model):
    rating_id = db.Column(db.Integer,autoincrement=True,primary_key = True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))

    score = db.Column(db.Integer,nullable = True)

    student = db.relationship("Student", backref=db.backref("ratings"))

    teacher = db.relationship("Teacher", backref=db.backref("ratings"))

    task = db.relationship("Task",backref=db.backref("ratings"))

class TeachersLoginForm(FlaskForm):
    username = StringField('Логин', validators=[InputRequired('Введите логин')])
    password = PasswordField('Пароль', validators=[InputRequired('Введите пароль!')])

class TeachersRegistrationForm(FlaskForm):
    username = StringField('Логин', validators=[InputRequired('Введите логин')])
    password = PasswordField('Пароль', validators=[InputRequired('Введите пароль!')])

class StudentsLoginForm(FlaskForm):
    username = StringField('Логин', validators=[InputRequired('Введите логин')])
    password = PasswordField('Пароль', validators=[InputRequired('Введите пароль!')])

def get_current_teacher():
    teacher_result = None

    if 'teacher' in session:
        teacher = session['teacher']

        teach = Teacher.query.filter_by(name = teacher).first()
        
        teacher_result = teach

    return teacher_result

def get_current_student():
    student_result = None

    if 'student' in session:
        student = session['student']

        stud = Student.query.filter_by(name = student).first()
        stud.last_seen = datetime.utcnow()
        db.session.commit()
        student_result = stud

    return student_result

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/rating')
def rating():
    students = Student.query.all()
    teachers = Teacher.query.all()
    ratings = Rating.query.all()
    tasks = Task.query.all()
    saving_data = {}
    for student in students:
        saving_data[student.id] = sum([i.score for i in student.ratings])
    return render_template('rating.html',students = students,ratings = ratings,teachers = teachers,tasks = tasks,saving_data=saving_data)

@app.errorhandler(413)
def request_entity_too_large(error):
    return 'File Too Large', 413
    
@app.route('/upload/<id>',methods=['GET','POST'])
def upload(id):
    file = request.files['inputFile']
    if not file.filename:
        flash('А где файл? Файл загрузите пожалуйста!!!','warning')
        return redirect(url_for('profile'))
    if file.filename == '' or not(allowed_file(file.filename)):
        flash('Файл имеет пустое значение или не zip-архив','warning')
        return redirect(url_for('profile'))
    if file and allowed_file(file.filename):
        flash('Файл загружен!','success')
        newFile = Task(name=file.filename,data = file.read(),description = 'Ruby',student_id = id)
        db.session.add(newFile)
        db.session.commit()
        return redirect(url_for('profile'))
    return redirect(url_for('profile'))

@app.route('/delete_upload/<id>',methods=['GET','POST'])
def delete_upload(id):
    student = get_current_student()
    if not student:
        return redirect(url_for('index'))
    newFile = Task.query.filter_by(id = id).first()
    rating = Rating.query.filter_by(student_id = student.id).all()
    r1 = Rating.query.filter_by(task_id = id).all()
    db.session.delete(newFile)
    for i in r1:
        db.session.delete(i)
    db.session.commit()
    flash('Файл удален','danger')
    return redirect(url_for('profile'))

@app.route('/download/<id>')
def download(id):
    file_data = Task.query.filter_by(id=id).first()
    return send_file(BytesIO(file_data.data),attachment_filename=file_data.name,as_attachment=True)


@app.route('/login',methods=['GET','POST'])
def login():
    form = StudentsLoginForm()
    if form.validate_on_submit():
        name = form.username.data
        password = form.password.data
        student = Student.query.filter_by(name=name).first()
        if student:
            if student.password == password:
                session['student'] = student.name
                return redirect(url_for('profile'))
            else:
                flash('Неверный пароль')
                return redirect(url_for('login'))
        else:
            flash('Неверный логин')
            return redirect(url_for('login'))
    return render_template('login.html', form=form)

@app.route('/profile')
def profile():
    task = Task.query.all()
    arr = []
    for j in task:
        arr.append(j.owner.name)
    my_dict = {i:arr.count(i) for i in arr}
    student = get_current_student()
    if not student:
        return redirect(url_for('index'))
    return render_template('profile.html',sid = student.id,sname = student.name, spassword = student.password,simg = student.avatar(128),student=student,task=task,my_dict=my_dict)

@app.route('/teachers_registration', methods=['GET', 'POST'])
def teachers_registration():
    form = TeachersRegistrationForm()
    if form.validate_on_submit():
        teacher = Teacher(name = form.username.data,password = form.password.data)
        db.session.add(teacher)
        db.session.commit()
        return redirect(url_for('teachers_login'))

    return render_template('teachers_registration.html', form=form)

@app.route('/teachers_login',methods=['GET','POST'])
def teachers_login():
    form = TeachersLoginForm()
    if form.validate_on_submit():
        name = form.username.data
        password = form.password.data
        teacher = Teacher.query.filter_by(name=name).first()
        if teacher:
            if teacher.password == password:
                session['teacher'] = teacher.name
                return redirect(url_for('teachers_admin',name = teacher.name))
            else:
                return 'Неверный пароль'
        else:
            return 'Неверный логин'
    return render_template('teachers_login.html', form=form)

@app.route('/teachers_admin/<name>')
def teachers_admin(name):
    teacher = get_current_teacher()
    if not teacher:
        return redirect(url_for('index'))
    students = Student.query.all()
    ratings = Rating.query.all()
    task = Task.query.all()
    return render_template('teachers_admin.html',students = students,ratings=ratings,teacher=teacher,task=task)


@app.route('/teachers_admin_update/<id>',methods=['GET','POST'])
def teachers_admin_update(id):
    teacher = get_current_teacher()
    if not teacher:
        return redirect(url_for('index'))
    if request.method == 'POST':
        rating = Rating(student_id = id,teacher_id = teacher.id,task_id = request.form['task_id'],score=request.form['student_score'])
        db.session.add(rating)        
        db.session.commit()
        return redirect(url_for('teachers_admin',name = teacher.name))
    return redirect(url_for('teachers_admin',name = teacher.name))
    
@app.route('/delete/<rating_id>',methods=['GET','POST'])
def teachers_admin_delete(rating_id):
    teacher = get_current_teacher()
    if not teacher:
        return redirect(url_for('index'))
    rating = Rating.query.filter_by(rating_id = rating_id).first()
    db.session.delete(rating)
    db.session.commit()
    return redirect(url_for('teachers_admin',name = teacher.name)) 

@app.route('/teachers_logout')
def teachers_logout():
    session.pop('teacher', None)
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('student', None)
    return redirect(url_for('index'))

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')
@app.route('/api/students', methods=['GET'])
def get_students():
    students = Student.query.all()

    return_values = []

    for student in students:
        student_dict = {}
        student_dict['id'] = student.id
        student_dict['name'] = student.name
        student_dict['password'] = student.password
        student_dict['ratings'] = [{i.teacher_id:i.score} for i in student.ratings] 
        return_values.append(student_dict)

    return jsonify({'students' : return_values})

@app.route('/api/student/<student_id>', methods=['GET'])
def get_student(student_id):
    student = Student.query.filter_by(id=student_id).first()

    return jsonify({'member' : {'id' : student.id, 'name' : student.name, 'password' : student.password, 'ratings' : [i.score for i in student.ratings] }})

@app.route('/api/students', methods=['POST'])
def add_student():
    new_member_data = request.get_json()
    print(new_member_data)
    name = new_member_data['name']
    password = new_member_data['password']

    s = Student(name = name,password = password)
    db.session.add(s)
    db.session.commit()

    s_cur = Student.query.filter_by(name = name).first()

    return jsonify({'member' : {'id' : s_cur.id, 'name' : s_cur.name, 'email' : s_cur.password}})

if __name__ == '__main__':
     app.run(debug=True)
