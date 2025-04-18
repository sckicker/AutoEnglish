# run.py

import os
import click
from flask.cli import with_appcontext
from app import create_app, db # Import factory and db instance from app package
from app.models import User # Import User model

# Create the Flask app instance using the factory
# It will load configuration based on config.py and environment variables
app = create_app()

# --- Define Custom Flask CLI Commands ---

@app.cli.command('sync-admins')
@with_appcontext # Ensures access to app context (app.config, db.session)
def sync_admins_command():
    """Synchronizes admin status from ADMIN_USERNAMES config to the database.

    Reads the comma-separated list of usernames from the ADMIN_USERNAMES
    configuration variable. For each username found in the database,
    it ensures the 'is_admin' flag is set to True. Warns about users
    listed in the config but not found in the database.
    """
    admin_usernames_str = app.config.get('ADMIN_USERNAMES', '')

    if not admin_usernames_str:
        click.echo("Warning: ADMIN_USERNAMES configuration is empty or not set. No users synchronized.")
        return

    # Parse the comma-separated string into a list of unique, non-empty usernames
    admin_usernames = list(set(name.strip() for name in admin_usernames_str.split(',') if name.strip()))

    if not admin_usernames:
        click.echo("Warning: Parsed ADMIN_USERNAMES list is empty.")
        return

    click.echo(f"Attempting to ensure admin status for: {', '.join(admin_usernames)}")

    updated_count = 0
    not_found_count = 0
    already_admin_count = 0

    for username in admin_usernames:
        user = User.query.filter_by(username=username).first()

        if user:
            if not user.is_admin:
                user.is_admin = True
                db.session.add(user)
                click.echo(f"  [SUCCESS] Marked '{username}' as admin.")
                updated_count += 1
            else:
                click.echo(f"  [INFO] User '{username}' is already an admin.")
                already_admin_count += 1
        else:
            click.echo(f"  [WARNING] User '{username}' not found in database.")
            not_found_count += 1

    if updated_count > 0:
        try:
            db.session.commit()
            click.echo(f"\nSuccessfully updated admin status for {updated_count} user(s).")
        except Exception as e:
            db.session.rollback()
            click.echo(f"\nError: Failed to commit database changes: {e}", err=True)
    else:
        click.echo("\nNo database updates were needed for admin status.")

    if not_found_count > 0:
        click.echo(f"Warning: {not_found_count} configured admin username(s) were not found in the database.")


# --- Standard entry point for running (optional, 'flask run' is preferred) ---
if __name__ == '__main__':
    # Consider using environment variables for host/port/debug in production
    app.run(
        host=os.environ.get('FLASK_RUN_HOST', '127.0.0.1'),
        port=int(os.environ.get('FLASK_RUN_PORT', 5000)),
        debug=app.config.get('DEBUG', False) # Get debug status from config
    )