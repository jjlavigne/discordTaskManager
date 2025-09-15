import sqlite3
import json
import datetime
from datetime import date, timedelta

# ---------------------------  
# Helpers
# ---------------------------
def date_to_str(d: date) -> str:
    """Convert date object to YYYY-MM-DD string for SQLite."""
    return d.strftime("%Y-%m-%d")

# ---------------------------
# Database setup
# ---------------------------
conn = sqlite3.connect("task_manager.db")
cur = conn.cursor()

# cur.execute("""
# CREATE TABLE IF NOT EXISTS People (
#     person_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT NOT NULL UNIQUE,
#     active INTEGER DEFAULT 1
# )""")

# cur.execute("""
# CREATE TABLE IF NOT EXISTS Tasks (
#     task_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     task_name TEXT NOT NULL UNIQUE,
#     description TEXT
# )""")

# cur.execute("""
# CREATE TABLE IF NOT EXISTS TaskAssignments (
#     assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     task_id INTEGER NOT NULL,
#     person_id INTEGER NOT NULL,
#     taskDate TEXT NOT NULL,
#     status TEXT DEFAULT 'assigned',
#     FOREIGN KEY (task_id) REFERENCES Tasks(task_id),
#     FOREIGN KEY (person_id) REFERENCES People(person_id),
#     UNIQUE (task_id, taskDate)
# )""")

# class TasksConfig:
#     def __init__(self, cooking_tasks, walking_tasks):
#         self.cooking_tasks = cooking_tasks
#         self.walking_tasks = walking_tasks

# ---------------------------
# Load config JSON
# ---------------------------
def load_config():
    with open("tasks.json", "r") as f:
        return json.load(f)


# ---------------------------
# Populate People & Tasks
# ---------------------------
def populate_people_and_tasks(config):
    for task_name, people in config["tasks"].items():
        print("executed")
        # Insert task
        cur.execute("INSERT OR IGNORE INTO Tasks (task_name) VALUES (?)", (task_name,))
        # Insert each person
        for name in people:
            cur.execute("INSERT OR IGNORE INTO People (name) VALUES (?)", (name,))
    cur.execute("INSERT OR IGNORE INTO People (name) VALUES (?)", ("skipped",))
    conn.commit()
    print("Population complete.")

# ---------------------------
# Generate Assignments
# ---------------------------
def generate_assignments(config, start=None):
    if start is None:
        start = date.today()
    # Get all tasks
    cur.execute("SELECT task_id, task_name FROM Tasks")
    tasks = cur.fetchall()

    # Map task_name -> people list (rotation order)
    task_people_map = config["tasks"]

    current_date = start
    end_date = start + timedelta(config["days"])

    # Track rotation index per task
    rotation_index = {task: 0 for task in task_people_map}

    while current_date < end_date:
        day_int = date_to_str(current_date)

        for task_id, task_name in tasks:
            people = task_people_map[task_name]
            idx = rotation_index[task_name] % len(people)
            person_name = people[idx]

            # Look up person_id
            cur.execute("SELECT person_id FROM People WHERE name=?", (person_name,))
            person_id = cur.fetchone()[0]
            try:
                cur.execute("""
                    INSERT INTO TaskAssignments (task_id, person_id, taskDate)
                    VALUES (?, ?, ?)
                """, (task_id, person_id, day_int))
            except sqlite3.IntegrityError:
                pass  # Already assigned

            # Advance rotation for this task
            rotation_index[task_name] += 1

        current_date += timedelta(days=1)
        conn.commit()

def reset_database(config, start=None)-> bool:
    """
    Drops all tables and recreates them, then repopulates and generates assignments.
    """

    (print("Resetting database..."))
    # Drop tables if they exist
    cur.execute("DROP TABLE IF EXISTS TaskAssignments")
    cur.execute("DROP TABLE IF EXISTS Tasks")
    cur.execute("DROP TABLE IF EXISTS People")
    conn.commit()
    print("Tables dropped.")

    (print("Recreating tables..."))
    # Recreate tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS People (
        person_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        active INTEGER DEFAULT 1
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL UNIQUE,
        description TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS TaskAssignments (
        assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        person_id INTEGER NOT NULL,
        taskDate TEXT NOT NULL,
        status TEXT DEFAULT 'assigned',
        FOREIGN KEY (task_id) REFERENCES Tasks(task_id),
        FOREIGN KEY (person_id) REFERENCES People(person_id),
        UNIQUE (task_id, taskDate)
    )""")
    conn.commit()
    print("Tables recreated.")

    # Repopulate
    print("Populating people and tasks...")

    for task_name, people in config["tasks"].items():
        # Insert task
        cur.execute("INSERT OR IGNORE INTO Tasks (task_name) VALUES (?)", (task_name,))
        # Insert each person
        for name in people:
            cur.execute("INSERT OR IGNORE INTO People (name) VALUES (?)", (name,))

    # myConfig = {
    #     "days": 7,
    #     "tasks": {
    #         "dog_walking": ["Ban", "Nel", "Ju"],
    #         "cooking": ["Nel", "Ju", "Declan", "Brandon"],
    #     }
    # };

    populate_people_and_tasks(config)
    if start is None:
        start = date.today()
        print("Generating assignments...")
    
    generate_assignments(config, start)

    # Verify counts
    cur.execute("SELECT COUNT(*) FROM People")
    people_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM Tasks")
    tasks_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM TaskAssignments")
    assignments_count = cur.fetchone()[0]

    print("People count:", people_count)
    print("Tasks count:", tasks_count)
    print("Assignments count:", assignments_count)

    if people_count == 0 or tasks_count == 0 or assignments_count == 0:
        return False

    print("Database fully reset and repopulated.")
    return True


def update_assignment(config):
    current_date = date.today()
    print("current_date:", current_date)

    # Delete assignments before today
    cur.execute("""
        DELETE FROM TaskAssignments
        WHERE taskDate < ?
    """, (date_to_str(current_date),))
    conn.commit()
    print(f"Deleted assignments before {current_date}")

    # Check how many future days are already populated
    cur.execute("""
        SELECT COUNT(DISTINCT taskDate)
        FROM TaskAssignments
        WHERE taskDate >= ?
    """, (date_to_str(current_date),))
    populated_days = cur.fetchone()[0]
    print("Populated days from today:", populated_days)

    # If we already have 7 days scheduled, do nothing
    if populated_days >= config["days"]:
        print("Already have 7 days scheduled, nothing to update.")
        return

    # Find the last scheduled date (could be today or later)
    cur.execute("SELECT MAX(taskDate) FROM TaskAssignments")
    result = cur.fetchone()
    last_date_str = result[0] if result and result[0] else None

    if last_date_str:
        last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
        newStartDate = last_date + timedelta(days=1)
    else:
        last_date = None
        newStartDate = current_date

    # Get the last assigned person per task 
    lastPersonPerTask = {}
    if last_date:
        cur.execute("""
            SELECT Tasks.task_name, People.name
            FROM TaskAssignments
            JOIN Tasks ON TaskAssignments.task_id = Tasks.task_id
            JOIN People ON TaskAssignments.person_id = People.person_id
            WHERE TaskAssignments.taskDate = ?
        """, (last_date_str,))
        for task_name, person_name in cur.fetchall():
            lastPersonPerTask[task_name] = person_name

    print("Last assigned person per task:", lastPersonPerTask)

    # Build new config starting with the next person in rotation
    myConfig = {"days": config["days"] - populated_days, "tasks": {}}
    for task_name, people in config["tasks"].items():
        last_person = lastPersonPerTask.get(task_name)
        if last_person and last_person in people:
            idx = (people.index(last_person) + 1) % len(people)
            new_rotation = people[idx:] + people[:idx]
        else:
            new_rotation = people
        myConfig["tasks"][task_name] = new_rotation

    print("New config with updated rotations:", myConfig)

    # Generate only the missing days
    generate_assignments(myConfig, newStartDate)
    

def swap_assignments(tasktype: str, date1_str: str, date2_str: str) -> bool:
    print("swap_assignments conn id:", id(conn))
    try:
        date1 = date1_str
        date2 = date2_str
    except ValueError:
        print("Invalid date format")
        return False

    cur.execute("SELECT task_id FROM Tasks WHERE task_name=?", (tasktype,))
    result = cur.fetchone()
    if not result:
        print("Task not found")
        return False
    task_id = result[0]

    cur.execute("""
        SELECT assignment_id, person_id FROM TaskAssignments
        WHERE task_id=? AND (taskDate=? OR taskDate=?)
        ORDER BY taskDate ASC
    """, (task_id, date1, date2))
    rows = cur.fetchall()
    print("Before swap:", rows)

    if len(rows) != 2:
        return False

    (id1, person1), (id2, person2) = rows
    cur.execute("UPDATE TaskAssignments SET person_id=? WHERE assignment_id=?", (person2, id1))
    cur.execute("UPDATE TaskAssignments SET person_id=? WHERE assignment_id=?", (person1, id2))
    conn.commit()

    #added for debugging
    cur.execute("""
        SELECT assignment_id, person_id FROM TaskAssignments
        WHERE task_id=? AND (taskDate=? OR taskDate=?)
        ORDER BY taskDate ASC
    """, (task_id, date1, date2))
    print("After swap:", cur.fetchall())
    #to here

    print("Swap successful")
    return True

def skip_assignment(tasktype: str, date_str: str) -> bool:
    print(f"skip_assignment called with: {tasktype}, {date_str}")
   
    # Look up the task_id
    cur.execute("SELECT task_id FROM Tasks WHERE task_name=?", (tasktype,))
    row = cur.fetchone()
    if not row:
        print("Task not found")
        return False
    task_id = row[0]

    # Get skipped person_id
    cur.execute("SELECT person_id FROM People WHERE name='skipped'")
    skip_row = cur.fetchone()
    if not skip_row:
        print("Skipped person not found")
        return False
    skip_id = skip_row[0]

    # # Push all future assignments down by one calendar day
    # cur.execute("""
    #     UPDATE TaskAssignments
    #     SET taskDate = DATE(taskDate, '+1 day')
    #     WHERE task_id=? AND taskDate>?
    # """, (task_id, date_str))

    # print(f"Assignment skipped: ({task_id}, {date_str})")
    

    # # Mark the assignment as skipped
    # cur.execute("""
    #     UPDATE TaskAssignments
    #     SET person_id=?, status='skipped'
    #     WHERE task_id=? AND taskDate=?
    # """, (skip_id, task_id, date_str))

    # conn.commit()
    # return True

    
    # find the person who was originally assigned that day
    cur.execute("""
        SELECT person_id FROM TaskAssignments
        WHERE task_id=? AND taskDate=?
    """, (task_id, date_str))
    orig_row = cur.fetchone()
    if not orig_row:
        print("No assignment found on that date")
        return False
    orig_person_id = orig_row[0]

    # Optionally, mark the skipped day as "skipped"
    cur.execute("""
        UPDATE TaskAssignments
        SET person_id=?, status='skipped'
        WHERE task_id=? AND taskDate=?
    """, (skip_id, task_id, date_str))

    # Shift all future assignments (after date_str) for this task forward by 1 day
    cur.execute("""
        SELECT assignment_id, taskDate
        FROM TaskAssignments
        WHERE task_id=? AND taskDate>?
        ORDER BY taskDate DESC
    """, (task_id, date_str))
    future_rows = cur.fetchall()

    for assign_id, task_date in future_rows:
        cur.execute("""
            UPDATE TaskAssignments
            SET taskDate = DATE(taskDate, '+1 day')
            WHERE assignment_id=?
        """, (assign_id,))

    #insert the original person into the *next day*
    next_day = (datetime.datetime.strptime(date_str, "%Y-%m-%d").date() 
                + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    cur.execute("""
        INSERT OR REPLACE INTO TaskAssignments (task_id, person_id, taskDate, status)
        VALUES (?, ?, ?, 'assigned')
    """, (task_id, orig_person_id, next_day))

    conn.commit()
    return True


# ---------------------------
# Print schedule
# ---------------------------
def print_schedule():
    print("print_schedule conn id:", id(conn))
    cur.execute("""
        SELECT TaskAssignments.taskDate, Tasks.task_name, People.name
        FROM TaskAssignments
        JOIN Tasks ON TaskAssignments.task_id = Tasks.task_id
        JOIN People ON TaskAssignments.person_id = People.person_id
        WHERE TaskAssignments.taskDate >= date('now', 'localtime')
        AND TaskAssignments.taskDate < date('now', 'localtime', '+7 days')
        ORDER BY TaskAssignments.taskDate ASC, Tasks.task_name ASC
    """)
    rows = cur.fetchall()

    current_date = None
    day_assignments = []
    output = ""
    for day_str, task_name, person_name in rows:
        if current_date != day_str:
            if current_date is not None:
                output += f"{current_date} {day_assignments}\n"
            current_date = day_str
            day_assignments = []
        day_assignments.append((task_name, person_name))

    if current_date is not None:
        output += f"{current_date} {day_assignments}\n"

    return output
