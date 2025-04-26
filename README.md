# CCOM Piano Room Reservation System

A web application for automating piano room reservations at the Central Conservatory of Music (CCOM).

## Features

- **Automated Reservations**: System automatically books rooms at 21:30 every day for the next day
- **Weekly Recurring Reservations**: Set up reservations that repeat every week on specific days
- **One-time Reservations**: Book rooms for specific dates or cancel existing reservations
- **Push Notifications**: Receive alerts when your reservations are confirmed or if there are issues
- **Room Browser**: View all available practice rooms with detailed information
- **Admin Interface**: Manage users, rooms, and system settings

## System Requirements

- Python 3.8+
- Flask and dependencies (see requirements.txt)
- SQLite (default) or other database supported by SQLAlchemy

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ccom-piano-reservation.git
   cd ccom-piano-reservation
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   flask init-db
   ```

5. Create an admin user:
   ```bash
   flask create-admin admin yourpassword
   ```

6. Run the application:
   ```bash
   flask run
   ```

## Configuration

The application is configured through the `config.py` file. Main configuration options:

- `MAX_DAILY_RESERVATIONS`: Maximum number of reservations per user per day (default: 2)
- `MAX_RESERVATION_HOURS`: Maximum duration for a single reservation in hours (default: 3)
- `RESERVATION_OPEN_TIME`: Time when CCOM opens reservations for the next day (default: "2130")
- `NOTIFICATION_ENABLED`: Whether push notifications are enabled (default: True)

## Usage

### User Guide

1. **Login**: Sign in with your CCOM student ID and password
2. **Setup Recurring Reservations**: Create weekly recurring reservations for your regular practice schedule
3. **Make One-time Reservations**: Book rooms for specific dates or cancel existing reservations
4. **Configure Notifications**: Add a push notification key in your profile to receive alerts

### Admin Guide

1. **User Management**: Create, edit, and deactivate user accounts
2. **Room Management**: Import and update room information
3. **System Settings**: Configure system parameters and run maintenance tasks
4. **Reservation History**: View and analyze all reservation activity

## Importing Rooms

To import practice rooms from CCOM:

1. Log in to your CCOM account
2. Run the `update_nameid.py` script to generate `devices_data.csv`
3. Log in to the admin interface and navigate to Room Management > Import Rooms
4. Upload the generated CSV file

## Project Structure

```
ccom-piano-reservation/
├── app/
│   ├── __init__.py                # Flask app initialization
│   ├── models/                    # Database models
│   ├── routes/                    # API endpoints and view functions
│   ├── services/                  # Business logic
│   ├── tasks/                     # Scheduled tasks
│   ├── templates/                 # HTML templates
│   ├── static/                    # CSS, JS, images
│   └── utils/                     # Helper functions
├── config.py                      # Configuration settings
├── run.py                         # Application entry point
├── requirements.txt               # Dependencies
└── README.md                      # Documentation
```

## Development

### Running in Debug Mode

For development, run the application with debug mode enabled:

```bash
flask run --debug
```

### CLI Commands

The application provides several CLI commands:

- `flask init-db`: Initialize the database
- `flask create-admin <username> <password>`: Create an admin user
- `flask import-rooms <csv_file>`: Import rooms from a CSV file
- `flask list-routes`: List all available routes

## Acknowledgements

This project is based on the original CCOM_Piano script by [original author's name].

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.