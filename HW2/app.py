from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pymysql

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'

# --- 資料庫連線設定 ---
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'Jeremy&930915'
DB_NAME = 'company_db'

def get_db_connection():
    """建立資料庫連線"""
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
                                 database=DB_NAME, cursorclass=pymysql.cursors.DictCursor)
    return connection

# ======================================================
# ================== API Endpoints for JS ===============
# ======================================================

@app.route('/api/jobs/<int:department_id>')
def api_get_jobs_by_department(department_id):
    """根據部門ID，返回該部門下的所有職位 (JSON)"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT job_id, job_title FROM Job_Titles WHERE department_id = %s ORDER BY job_title", (department_id,))
        jobs = cursor.fetchall()
    conn.close()
    return jsonify(jobs)

@app.route('/api/next_employee_code/<int:job_id>')
def api_get_next_employee_code(job_id):
    """根據職位ID，計算並返回下一個建議的員工編號 (JSON)"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""SELECT d.department_code, jt.job_code 
                          FROM Job_Titles jt 
                          JOIN Departments d ON jt.department_id = d.department_id 
                          WHERE jt.job_id = %s""", (job_id,))
        codes = cursor.fetchone()
        if not codes:
            return jsonify({'error': 'Job not found'}), 404
        
        dept_code = codes['department_code']
        job_code = codes['job_code']
        prefix = f"{dept_code}{job_code}"
        prefix_len = len(prefix)
        
        cursor.execute("""SELECT MAX(CAST(SUBSTRING(employee_code, %s) AS UNSIGNED)) as max_serial 
                          FROM Employees 
                          WHERE employee_code LIKE %s""", (prefix_len + 1, f"{prefix}%"))
        result = cursor.fetchone()
        next_serial = (result['max_serial'] or 0) + 1
        employee_code = f"{prefix}{next_serial:03d}"
    conn.close()
    return jsonify({'next_code': employee_code})

@app.route('/api/next_job_code/<int:department_id>')
def api_get_next_job_code(department_id):
    """根據部門ID，計算並返回下一個建議的職位編號 (JSON)"""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT MAX(CAST(job_code AS UNSIGNED)) as max_code 
            FROM Job_Titles 
            WHERE department_id = %s
        """, (department_id,))
        result = cursor.fetchone()
        next_code_num = (result['max_code'] or 0) + 1
        next_job_code = f"{next_code_num:02d}"
    conn.close()
    return jsonify({'next_code': next_job_code})

# ======================================================
# ================== Employee CRUD =====================
# ======================================================

@app.route('/')
def list_employees():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 新增查詢 d.department_code 和 jt.job_code
        sql = """SELECT e.employee_id, e.employee_code, CONCAT(e.first_name, ' ', e.last_name) AS employee_name, 
                        jt.job_code, d.department_code
                FROM Employees e
                JOIN Job_Titles jt ON e.job_id = jt.job_id
                JOIN Departments d ON jt.department_id = d.department_id
                ORDER BY e.employee_code"""
        cursor.execute(sql)
        employees = cursor.fetchall()
    conn.close()
    return render_template('employees.html', employees=employees)

@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        # 現在我們要從表單接收 employee_code
        employee_code = request.form['employee_code']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        job_id = request.form['job_id']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # INSERT 語句現在包含手動指定的 employee_code
                sql_insert = """INSERT INTO Employees (employee_code, first_name, last_name, email, job_id) 
                                VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(sql_insert, (employee_code, first_name, last_name, email, job_id))
            conn.commit()
            flash(f'Employee {employee_code} added successfully!', 'success')
            return redirect(url_for('list_employees'))

        except pymysql.err.IntegrityError as e:
            # 處理唯一鍵衝突 (email 或 employee_code)
            error_message = 'Database error.'
            if e.args[0] == 1062: # 唯一鍵衝突
                if 'employee_code' in str(e):
                    error_message = 'Error: This Employee Code already exists. Please choose another one.'
                elif 'email' in str(e):
                    error_message = 'Error: This email already exists.'
            flash(error_message, 'danger')
            # 如果出錯，需要重新導向到 add 頁面，而不是渲染模板，以避免複雜的狀態管理
            return redirect(url_for('add_employee'))
        finally:
            if conn.open:
                conn.close()

    # GET 請求: 只需傳遞部門列表
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT department_id, department_name FROM Departments ORDER BY department_name")
        departments = cursor.fetchall()
    conn.close()
    return render_template('employee_form.html', departments=departments)

@app.route('/update/<int:employee_id>', methods=['GET', 'POST'])
def update_employee(employee_id):
    conn = get_db_connection()
    if request.method == 'POST':
        # --- POST 邏輯 (處理表單提交) ---
        # Employee Code 在編輯時是唯讀的，所以我們不從表單接收它
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        job_id = request.form['job_id']
        
        try:
            with conn.cursor() as cursor:
                # 更新時不修改 employee_code
                sql = """UPDATE Employees SET first_name=%s, last_name=%s, email=%s, job_id=%s 
                         WHERE employee_id=%s"""
                cursor.execute(sql, (first_name, last_name, email, job_id, employee_id))
            conn.commit()
            flash('Employee updated successfully!', 'success')
        except pymysql.err.IntegrityError as e:
            flash(f'Database error: This email may already be in use. ({e})', 'danger')
        finally:
            conn.close()
        return redirect(url_for('list_employees'))

    # --- GET 邏輯 (載入頁面以顯示現有資料) ---
    with conn.cursor() as cursor:
        # 1. 獲取要編輯的員工的完整資料
        cursor.execute("SELECT * FROM Employees WHERE employee_id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            flash('Employee not found!', 'danger')
            conn.close()
            return redirect(url_for('list_employees'))

        # 2. 為了連動下拉選單，我們需要找出該員工所在的部門ID
        cursor.execute("""
            SELECT d.department_id 
            FROM Departments d 
            JOIN Job_Titles jt ON d.department_id = jt.department_id 
            WHERE jt.job_id = %s
        """, (employee['job_id'],))
        employee_department = cursor.fetchone()
        employee['department_id'] = employee_department['department_id'] if employee_department else None

        # 3. 獲取所有的部門列表 (給第一個下拉選單用)
        cursor.execute("SELECT department_id, department_name FROM Departments ORDER BY department_name")
        departments = cursor.fetchall()
        
        # 4. 獲取該員工所在部門的職位列表 (給第二個下拉選單預先填充)
        if employee['department_id']:
            cursor.execute("SELECT job_id, job_title FROM Job_Titles WHERE department_id = %s ORDER BY job_title", (employee['department_id'],))
            jobs = cursor.fetchall()
        else:
            jobs = [] # 如果員工沒有部門(異常情況)，則職位列表為空
            
    conn.close()
        
    return render_template('employee_form.html', 
                           action='Edit', 
                           employee=employee, 
                           departments=departments, 
                           jobs=jobs)

@app.route('/delete/<int:employee_id>', methods=['POST'])
def delete_employee(employee_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM Employees WHERE employee_id = %s", (employee_id,))
    conn.commit()
    conn.close()
    flash('Employee deleted successfully!', 'danger')
    return redirect(url_for('list_employees'))

# === 部門 CRUD (與之前版本相同，僅貼出不做修改) ===
@app.route('/departments')
def list_departments():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Departments ORDER BY department_code")
        departments = cursor.fetchall()
    conn.close()
    return render_template('departments.html', departments=departments)

@app.route('/departments/add', methods=['GET', 'POST'])
def add_department():
    if request.method == 'POST':
        dept_code = request.form['department_code']
        dept_name = request.form['department_name']
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO Departments (department_code, department_name) VALUES (%s, %s)", 
                               (dept_code, dept_name))
            conn.commit()
            flash('Department added successfully!', 'success')
        except pymysql.err.IntegrityError:
            flash('Error: This department code or name may already exist.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('list_departments'))
    
    # --- 以下是新增的 GET 邏輯 ---
    # 當使用者載入頁面時 (GET request)
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 找出目前最大的 department_code
        cursor.execute("SELECT MAX(CAST(department_code AS UNSIGNED)) as max_code FROM Departments")
        result = cursor.fetchone()
        # 計算下一個 code (如果資料庫是空的, max_code 會是 None)
        next_code_num = (result['max_code'] or 0) + 1
        # 格式化成兩位數的字串，例如 1 -> "01", 10 -> "10"
        next_dept_code = f"{next_code_num:02d}"
    conn.close()

    # 將計算出的下一個 code 傳遞給模板
    return render_template('department_form.html', action='Add', next_dept_code=next_dept_code)

@app.route('/departments/update/<int:department_id>', methods=['GET', 'POST'])
def update_department(department_id):
    conn = get_db_connection()
    if request.method == 'POST':
        dept_code = request.form['department_code']
        dept_name = request.form['department_name']
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE Departments SET department_code = %s, department_name = %s WHERE department_id = %s", 
                               (dept_code, dept_name, department_id))
            conn.commit()
            flash('Department updated successfully!', 'success')
        except pymysql.err.IntegrityError:
            flash('Error: This department code or name may already exist.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('list_departments'))
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Departments WHERE department_id = %s", (department_id,))
        department = cursor.fetchone()
    conn.close()
    return render_template('department_form.html', action='Edit', department=department)

@app.route('/departments/delete/<int:department_id>', methods=['POST'])
def delete_department(department_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM Departments WHERE department_id = %s", (department_id,))
        conn.commit()
        flash('Department deleted successfully!', 'success')
    except pymysql.err.IntegrityError:
        flash('Error: Cannot delete department because it has job titles assigned to it.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('list_departments'))

# === 職位 CRUD ===
@app.route('/jobs')
def list_jobs():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        sql = """SELECT jt.*, d.department_name, d.department_code
                 FROM Job_Titles jt
                 JOIN Departments d ON jt.department_id = d.department_id
                 ORDER BY d.department_code, jt.job_code"""
        cursor.execute(sql)
        jobs = cursor.fetchall()
    conn.close()
    return render_template('jobs.html', jobs=jobs)

@app.route('/jobs/add', methods=['GET', 'POST'])
def add_job():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Departments ORDER BY department_code")
        departments = cursor.fetchall()
    conn.close()

    if request.method == 'POST':
        # 現在我們要從表單接收使用者最終確認的 job_code
        job_code = request.form['job_code']
        job_title = request.form['job_title']
        department_id = request.form['department_id']
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # INSERT 語句現在使用來自表單的 job_code
                sql = "INSERT INTO Job_Titles (job_code, job_title, department_id) VALUES (%s, %s, %s)"
                cursor.execute(sql, (job_code, job_title, department_id))
            conn.commit()
            flash(f'Job Title "{job_title}" added with code {job_code} successfully!', 'success')
        except pymysql.err.IntegrityError as e:
            error_message = f'Database error. ({e})'
            if e.args[0] == 1062: # 唯一鍵衝突
                error_message = 'Error: This job code may already exist in this department.'
            flash(error_message, 'danger')
        finally:
            conn.close()
        return redirect(url_for('list_jobs'))
        
    # GET 請求，只需傳遞部門列表給模板
    return render_template('job_form.html', action='Add', departments=departments)

@app.route('/jobs/update/<int:job_id>', methods=['GET', 'POST'])
def update_job(job_id):
    conn = get_db_connection()
    if request.method == 'POST':
        job_code = request.form['job_code']
        job_title = request.form['job_title']
        department_id = request.form['department_id']
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE Job_Titles SET job_code = %s, job_title = %s, department_id = %s WHERE job_id = %s"
                cursor.execute(sql, (job_code, job_title, department_id, job_id))
            conn.commit()
            flash('Job Title updated successfully!', 'success')
        except pymysql.err.IntegrityError as e:
            flash(f'Error: Database error. ({e})', 'danger')
        finally:
            conn.close()
        return redirect(url_for('list_jobs'))

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Job_Titles WHERE job_id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.execute("SELECT * FROM Departments ORDER BY department_code")
        departments = cursor.fetchall()
    conn.close()
    return render_template('job_form.html', action='Edit', job=job, departments=departments)

@app.route('/jobs/delete/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM Job_Titles WHERE job_id = %s", (job_id,))
        conn.commit()
        flash('Job Title deleted successfully!', 'success')
    except pymysql.err.IntegrityError:
        flash('Error: Cannot delete job title because it has employees assigned to it.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('list_jobs'))

if __name__ == '__main__':
    app.run(debug=True)