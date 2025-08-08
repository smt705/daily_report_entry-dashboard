import os
import sqlite3
from datetime import date

DB_FILE = "construction_management.db"


def create_database():
    """
    Creates and initializes the SQLite database with the necessary tables and sample data.
    """
    # Remove the old database file if it exists to start fresh
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old database file: {DB_FILE}")

    # Connect to the SQLite database (this will create the file)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print(f"Successfully connected to and created database: {DB_FILE}")

    # --- SCHEMA DEFINITION ---
    # The schema is designed to be normalized to reduce data redundancy.
    # We use Foreign Keys to link tables together.

    # Table: Projects
    # Stores high-level information about each construction project.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL UNIQUE,
        location TEXT,
        start_date DATE,
        end_date DATE
    );
    ''')
    print("Created 'Projects' table.")

    # Table: DailyReports
    # This is the central table, capturing one report per day per project.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS DailyReports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        report_date DATE NOT NULL,
        weather TEXT,
        site_conditions TEXT,
        general_notes TEXT,
        prepared_by TEXT,
        FOREIGN KEY (project_id) REFERENCES Projects (project_id)
    );
    ''')
    print("Created 'DailyReports' table.")

    # Table: ManpowerLog
    # Logs the different types of labor and their hours for a specific daily report.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ManpowerLog (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        trade TEXT NOT NULL,
        number_of_workers INTEGER NOT NULL,
        hours_worked REAL NOT NULL,
        FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
    );
    ''')
    print("Created 'ManpowerLog' table.")

    # Table: EquipmentLog
    # Logs the equipment used on site for a specific daily report.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS EquipmentLog (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        equipment_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        hours_used REAL NOT NULL,
        FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
    );
    ''')
    print("Created 'EquipmentLog' table.")

    # Table: MaterialDeliveries
    # Logs materials delivered to the site.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS MaterialDeliveries (
        delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        material_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT NOT NULL,
        supplier TEXT,
        ticket_number TEXT,
        FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
    );
    ''')
    print("Created 'MaterialDeliveries' table.")

    # Table: WorkActivities
    # Details the specific work activities performed during the day.
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS WorkActivities (
        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        activity_description TEXT NOT NULL,
        status TEXT CHECK(status IN ('Not Started', 'In Progress', 'Completed', 'Delayed')),
        percent_complete INTEGER,
        notes TEXT,
        FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
    );
    ''')
    print("Created 'WorkActivities' table.")

    # --- SAMPLE DATA INSERTION ---
    try:
        # 1. Create a Project
        cursor.execute(
            "INSERT INTO Projects (project_name, location, start_date) VALUES (?, ?, ?)",
            ('Transmission Line Upgrade - Section 5',
             'Phnom Penh South',
             '2025-08-01'))
        project_id = cursor.lastrowid  # Get the ID of the project we just inserted
        print(f"Inserted sample project with ID: {project_id}")

        # 2. Create a Daily Report for today
        today_str = date.today().isoformat()
        cursor.execute(
            "INSERT INTO DailyReports (project_id, report_date, weather, site_conditions, prepared_by) VALUES (?, ?, ?, ?, ?)",
            (project_id,
             today_str,
             'Sunny, 32°C',
             'Dry, access roads clear.',
             'John Doe (Site Supervisor)'))
        report_id = cursor.lastrowid
        print(f"Inserted sample daily report for today with ID: {report_id}")

        # 3. Add Manpower Logs for this report
        manpower_data = [
            (report_id, 'General Labor', 15, 8.0),
            (report_id, 'Electricians', 4, 8.0),
            (report_id, 'Crane Operator', 1, 6.5)
        ]
        cursor.executemany(
            "INSERT INTO ManpowerLog (report_id, trade, number_of_workers, hours_worked) VALUES (?, ?, ?, ?)",
            manpower_data)
        print(f"Inserted {len(manpower_data)} manpower logs.")

        # 4. Add Equipment Logs
        equipment_data = [
            (report_id, '50-Ton Crane', 1, 6.5),
            (report_id, 'Excavator', 1, 8.0),
            (report_id, 'Pickup Truck', 3, 8.0)
        ]
        cursor.executemany(
            "INSERT INTO EquipmentLog (report_id, equipment_name, quantity, hours_used) VALUES (?, ?, ?, ?)",
            equipment_data)
        print(f"Inserted {len(equipment_data)} equipment logs.")

        # 5. Add a Material Delivery
        cursor.execute(
            "INSERT INTO MaterialDeliveries (report_id, material_name, quantity, unit, supplier, ticket_number) VALUES (?, ?, ?, ?, ?, ?)",
            (report_id,
             'Concrete Mix',
             12,
             'cubic meters',
             'City Concrete Inc.',
             'TICKET-00123'))
        print("Inserted 1 material delivery log.")

        # 6. Add Work Activities
        activity_data = [
            (report_id,
             'Excavate foundation for Tower #23',
             'Completed',
             100,
             'Final depth confirmed.'),
            (report_id,
             'Install rebar cage for Tower #23 foundation',
             'In Progress',
             75,
             'Tying nearly complete.'),
            (report_id,
             'Stringing conductors between Tower #20 and #21',
             'In Progress',
             50,
             'First of three lines pulled.')]
        cursor.executemany(
            "INSERT INTO WorkActivities (report_id, activity_description, status, percent_complete, notes) VALUES (?, ?, ?, ?, ?)",
            activity_data)
        print(f"Inserted {len(activity_data)} work activity logs.")

        # Commit the changes to the database
        conn.commit()
        print("\nSuccessfully inserted all sample data and committed changes.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()  # Roll back changes if an error occurs
    finally:
        # Close the connection
        conn.close()
        print("Database connection closed.")


if __name__ == '__main__':
    create_database()
    print(f"\nScript finished. The database '{DB_FILE}' is ready.")
