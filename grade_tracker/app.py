from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import sqlite3
import json
import os
from config import config

app = Flask(__name__)

env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[env])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def get_db():
    conn = sqlite3.connect("grades.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        subject TEXT NOT NULL,
        grades TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        student_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        UNIQUE(teacher_id, student_name, subject, date)
    )''')
    conn.commit()
    conn.close()

class Teacher(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM teachers WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return Teacher(row["id"], row["username"])
    return None

def necta_grade(score):
    if score >= 75: return ("A", "Excellent")
    if score >= 65: return ("B", "Very Good")
    if score >= 45: return ("C", "Good")
    if score >= 30: return ("D", "Satisfactory")
    return ("F", "Fail")

def calculate_average(grades):
    if not grades: return 0
    return round(sum(grades) / len(grades), 1)

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        conn = get_db()
        row = conn.execute("SELECT * FROM teachers WHERE username=?", (username,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password"], password):
            login_user(Teacher(row["id"], row["username"]))
            return jsonify({"success": True})
        return jsonify({"error": "Wrong username or password"}), 401
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not username or not password:
            return jsonify({"error": "All fields required"}), 400
        hashed = generate_password_hash(password)
        try:
            conn = get_db()
            conn.execute("INSERT INTO teachers (username, password) VALUES (?,?)", (username, hashed))
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        except:
            return jsonify({"error": "Username already exists"}), 400
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/api/students", methods=["GET"])
@login_required
def get_students():
    sort_by = request.args.get("sort", "date")
    
    conn = get_db()
    
    if sort_by == "name_asc":
        order_clause = "ORDER BY LOWER(name) ASC"
    elif sort_by == "name_desc":
        order_clause = "ORDER BY LOWER(name) DESC"
    elif sort_by == "subject":
        order_clause = "ORDER BY LOWER(subject) ASC, LOWER(name) ASC"
    else:
        order_clause = "ORDER BY id DESC"
    
    query = f"SELECT * FROM students WHERE teacher_id=? {order_clause}"
    rows = conn.execute(query, (current_user.id,)).fetchall()
    conn.close()
    
    result = []
    for row in rows:
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        grade, remark = necta_grade(avg)
        result.append({
            "id": row["id"],
            "name": row["name"],
            "subject": row["subject"],
            "grades": grades,
            "average": avg,
            "grade": grade,
            "remark": remark
        })
    
    if sort_by == "avg_desc":
        result.sort(key=lambda x: x["average"], reverse=True)
    elif sort_by == "avg_asc":
        result.sort(key=lambda x: x["average"])
    
    return jsonify(result)

@app.route("/api/students", methods=["POST"])
@login_required
def add_student():
    data = request.get_json()
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    grades = data.get("grades", [])
    if not name or not subject:
        return jsonify({"error": "Name and subject required"}), 400
    grades_str = ",".join(str(g) for g in grades)
    conn = get_db()
    conn.execute("INSERT INTO students (teacher_id, name, subject, grades) VALUES (?,?,?,?)",
                 (current_user.id, name, subject, grades_str))
    conn.commit()
    conn.close()
    avg = calculate_average(grades)
    grade, remark = necta_grade(avg)
    return jsonify({
        "name": name, "subject": subject, "grades": grades,
        "average": avg, "grade": grade, "remark": remark
    }), 201

@app.route("/api/students/<int:student_id>", methods=["DELETE"])
@login_required
def delete_student(student_id):
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=? AND teacher_id=?", (student_id, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route("/api/students/<int:student_id>", methods=["PUT"])
@login_required
def edit_student(student_id):
    data = request.get_json()
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    grades = data.get("grades", [])
    
    if not name or not subject:
        return jsonify({"error": "Name and subject required"}), 400
    
    grades_str = ",".join(str(g) for g in grades)
    
    conn = get_db()
    conn.execute("""
        UPDATE students 
        SET name=?, subject=?, grades=? 
        WHERE id=? AND teacher_id=?
    """, (name, subject, grades_str, student_id, current_user.id))
    conn.commit()
    conn.close()
    
    avg = calculate_average(grades)
    grade, remark = necta_grade(avg)
    
    return jsonify({
        "id": student_id,
        "name": name,
        "subject": subject,
        "grades": grades,
        "average": avg,
        "grade": grade,
        "remark": remark
    })
@app.route("/api/attendance", methods=["GET"])
@login_required
def get_attendance():
    subject = request.args.get("subject", "").strip()
    date_filter = request.args.get("date", "").strip()
    
    conn = get_db()
    query = "SELECT * FROM attendance WHERE teacher_id=?"
    params = [current_user.id]
    
    if subject:
        query += " AND subject=?"
        params.append(subject)
    if date_filter:
        query += " AND date=?"
        params.append(date_filter)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "student_name": row["student_name"],
            "subject": row["subject"],
            "date": row["date"],
            "status": row["status"]
        })
    return jsonify(result)

@app.route("/api/attendance", methods=["POST"])
@login_required
def mark_attendance():
    data = request.get_json()
    student_name = data.get("student_name", "").strip()
    subject = data.get("subject", "").strip()
    status = data.get("status", "").strip()
    date_str = data.get("date", date.today().isoformat())
    
    if not student_name or not subject or not status:
        return jsonify({"error": "Student name, subject, and status required"}), 400
    
    if status not in ["Present", "Absent", "Late"]:
        return jsonify({"error": "Invalid status"}), 400
    
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO attendance (teacher_id, student_name, subject, date, status)
            VALUES (?, ?, ?, ?, ?)
        """, (current_user.id, student_name, subject, date_str, status))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Attendance marked for {student_name}"})
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route("/api/attendance/students", methods=["GET"])
@login_required
def get_attendance_students():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT name FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    students = [row["name"] for row in rows]
    return jsonify(students)

@app.route("/api/attendance/subjects", methods=["GET"])
@login_required
def get_attendance_subjects():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT subject FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    subjects = [row["subject"] for row in rows]
    return jsonify(subjects)

@app.route("/api/attendance/summary", methods=["GET"])
@login_required
def get_attendance_summary():
    conn = get_db()
    
    students = conn.execute("SELECT DISTINCT name FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    
    summary = []
    for student in students:
        student_name = student["name"]
        records = conn.execute("""
            SELECT status FROM attendance 
            WHERE teacher_id=? AND student_name=?
        """, (current_user.id, student_name)).fetchall()
        
        total = len(records)
        if total > 0:
            present = sum(1 for r in records if r["status"] == "Present")
            absent = sum(1 for r in records if r["status"] == "Absent")
            late = sum(1 for r in records if r["status"] == "Late")
            percentage = round((present + late * 0.5) / total * 100, 1)
        else:
            present = absent = late = 0
            percentage = 0
        
        summary.append({
            "student_name": student_name,
            "present": present,
            "absent": absent,
            "late": late,
            "total": total,
            "percentage": percentage
        })
    
    conn.close()
    return jsonify(summary)

@app.route("/api/export")
@login_required
def export_data():
    import csv
    from io import StringIO
    
    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Subject', 'Grades', 'Average', 'Grade', 'Remark'])
    
    for row in students:
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        grade, remark = necta_grade(avg)
        writer.writerow([row["name"], row["subject"], row["grades"], avg, grade, remark])
    
    return Response(
        output.getvalue(), 
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=students.csv"}
    )

@app.route("/api/export/attendance")
@login_required
def export_attendance():
    import csv
    from io import StringIO
    
    conn = get_db()
    records = conn.execute("SELECT * FROM attendance WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student', 'Subject', 'Date', 'Status'])
    
    for row in records:
        writer.writerow([row["student_name"], row["subject"], row["date"], row["status"]])
    
    return Response(
        output.getvalue(), 
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=attendance.csv"}
    )

@app.route("/api/export/pdf")
@login_required
def export_pdf():
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from io import BytesIO
    import datetime
    
    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a2744'),
        alignment=1,
        spaceAfter=30
    )
    
    title = Paragraph("Teacher's Companion — Student Report", title_style)
    elements.append(title)
    
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7a99'),
        alignment=2
    )
    date_str = f"Generated: {datetime.datetime.now().strftime('%B %d, %Y %I:%M %p')}"
    elements.append(Paragraph(date_str, date_style))
    elements.append(Spacer(1, 20))
    
    data = [['Name', 'Subject', 'Grades', 'Average', 'Grade', 'Remark']]
    for row in students:
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        grade, remark = necta_grade(avg)
        data.append([row["name"], row["subject"], row["grades"], str(avg), grade, remark])
    
    table = Table(data, colWidths=[1.2*inch, 1.2*inch, 1.5*inch, 0.8*inch, 0.6*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2744')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d8dff0')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f9fc')]),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    if students:
        all_grades = []
        for row in students:
            grades = [float(g) for g in row["grades"].split(",") if g]
            all_grades.extend(grades)
        
        summary_style = ParagraphStyle(
            'SummaryStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a2744'),
            spaceAfter=6
        )
        
        avg_all = sum(all_grades) / len(all_grades) if all_grades else 0
        summary_text = f"""
        <b>Summary:</b><br/>
        Total Students: {len(students)} | 
        Class Average: {avg_all:.1f}% | 
        Highest Score: {max(all_grades) if all_grades else 0} | 
        Lowest Score: {min(all_grades) if all_grades else 0}
        """
        elements.append(Paragraph(summary_text, summary_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={"Content-Disposition": "attachment;filename=student_report.pdf"}
    )

@app.route("/api/charts/performance")
@login_required
def get_performance_data():
    conn = get_db()
    students = conn.execute("SELECT * FROM students WHERE teacher_id=?", (current_user.id,)).fetchall()
    conn.close()
    
    subject_data = {}
    for row in students:
        subject = row["subject"]
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        if subject not in subject_data:
            subject_data[subject] = []
        subject_data[subject].append(avg)
    
    subject_averages = {}
    for subject, avgs in subject_data.items():
        subject_averages[subject] = round(sum(avgs) / len(avgs), 1)
    
    top_students = []
    for row in students:
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        top_students.append({
            "name": row["name"],
            "average": avg,
            "subject": row["subject"]
        })
    top_students.sort(key=lambda x: x["average"], reverse=True)
    
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for row in students:
        grades = [float(g) for g in row["grades"].split(",") if g]
        avg = calculate_average(grades)
        grade, _ = necta_grade(avg)
        grade_counts[grade] += 1
    
    return jsonify({
        "subject_averages": subject_averages,
        "top_students": top_students[:10],
        "grade_distribution": grade_counts
    })

@app.route("/api/backup")
@login_required
def backup_database():
    import shutil
    from datetime import datetime
    
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy('grades.db', backup_name)
    
    return send_file(backup_name, as_attachment=True)
@app.route("/manifest.json")
def manifest():
    return send_file("templates/manifest.json")

@app.route("/service-worker.js")
def service_worker():
    return send_file("templates/service-worker.js")

@app.route("/icon-192.png")
def icon_192():
    return send_file("templates/icon-192.png")

@app.route("/icon-512.png")
def icon_512():
    return send_file("templates/icon-512.png")

@app.route("/favicon.ico")
def favicon_ico():
    return send_file("templates/favicon.ico")

@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_file("templates/apple-touch-icon.png")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)