"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
import os
import click
from flask import url_for
from flask.cli import with_appcontext
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

from app import create_app, db
from app.models.user import User
from app.models.room import Room
from app.models.reservation import RecurringReservation, OneTimeReservation, ReservationHistory

app = create_app()
with app.app_context():
    db.create_all()


# Create CLI commands
@app.cli.command('init-db')
def init_db():
    """Initialize the database with tables"""
    db.create_all()
    click.echo('Database initialized.')


@app.cli.command('create-admin')
@click.argument('username')
@click.argument('password')
def create_admin(username, password):
    """Create an admin user"""
    user = User.query.filter_by(username=username).first()

    if user:
        user.set_password(password)
        user.is_admin = True
        click.echo(f'Updated existing user {username} and granted admin privileges.')
    else:
        user = User(username=username, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        click.echo(f'Created new admin user: {username}')

    db.session.commit()


@app.cli.command('import-rooms')
@click.argument('csv_file')
def import_rooms(csv_file):
    """Import rooms from CSV file"""
    if not os.path.exists(csv_file):
        click.echo(f'File not found: {csv_file}')
        return

    success = Room.import_from_csv(csv_file)

    if success:
        click.echo('Rooms imported successfully!')
    else:
        click.echo('Failed to import rooms. Check the application logs for details.')


@app.cli.command('list-routes')
def list_routes():
    """List all available routes"""
    output = []
    for rule in app.url_map.iter_rules():
        options = {}
        for arg in rule.arguments:
            options[arg] = f"[{arg}]"

        methods = ','.join(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = f"{rule.endpoint:50s} {methods:20s} {url}"
        output.append(line)

    for line in sorted(output):
        click.echo(line)


@app.shell_context_processor
def make_shell_context():
    """Make objects available in the shell context"""
    return {
        'db': db,
        'User': User,
        'Room': Room,
        'RecurringReservation': RecurringReservation,
        'OneTimeReservation': OneTimeReservation,
        'ReservationHistory': ReservationHistory
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)