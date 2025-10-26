# app.py

from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error

# Initialize the Flask application
app = Flask(__name__)
app.secret_key = 'a_super_secret_key_for_flashing' # Necessary for flash messages

# --- DATABASE CONFIGURATION ---
# IMPORTANT: Replace with your own MySQL credentials
db_config = {
    'host': 'localhost',
    'user': 'root',      # <-- CHANGE THIS
    'password': 'Jeremy&930915',  # <-- CHANGE THIS
    'database': 'database-system'
}

# --- ROUTES ---

@app.route('/')
def show_form():
    """Displays the form to add a new employee."""
    return render_template('add_employee.html')

@app.route('/add', methods=['POST'])
def add_employee():
    """Handles the form submission and inserts data into the database."""
    
    # Get data from the web form
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    birthday = request.form['birthday']
    salary = request.form['salary']
    hire_date = request.form['hire_date']
    department = request.form['department']

    conn = None  # Initialize connection to None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # The SQL query to insert a new employee
        # Using placeholders (%s) is crucial to prevent SQL injection attacks
        query = """
        INSERT INTO employees (first_name, last_name, birthday, salary, hire_date, department) 
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        # The data to be inserted, in a tuple
        data = (first_name, last_name, birthday, salary, hire_date, department)

        # Execute the query
        cursor.execute(query, data)

        # Commit the transaction to make the changes permanent
        conn.commit()

        # Send a success message to the user
        flash('Employee added successfully!', 'success')

    except Error as e:
        # If an error occurs, print it and send an error message
        print(f"Error: {e}")
        flash(f'Failed to add employee. Error: {e}', 'error')
        if conn and conn.is_connected():
            conn.rollback() # Roll back any changes if an error occurred

    finally:
        # Ensure the connection is closed
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    # Redirect the user back to the main form page
    return redirect(url_for('show_form'))

# --- RUN THE APPLICATION ---

if __name__ == '__main__':
    # The debug=True flag allows you to see errors in the browser and automatically reloads the server on code changes
    app.run(debug=True)