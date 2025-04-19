# run.py
import click
from flask.cli import with_appcontext
from app import create_app, db
from app.models import User, Lesson # 导入 Lesson
from app.tts_utils import generate_and_save_audio_if_not_exists, get_audio_filename
import concurrent.futures # (并行处理保持注释，优先串行)

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


# --- CLI 命令组 ---
@app.cli.group()
def admin():
    """Admin related commands."""
    pass

@app.cli.group()
def audio():
    """Audio generation related commands."""
    pass

@audio.command('generate')
@click.option('--lesson', '-l', type=int, default=None, help='Generate audio for a specific lesson number.')
@click.option('--force', '-f', is_flag=True, default=False, help='Force regeneration even if audio file exists.')
@click.option('--lang', default='en', help='Language code for TTS (e.g., en).')
@with_appcontext
def generate_audio_command(lesson, force, lang):
    """Generates TTS audio for specified or all lessons using configured model."""
    click.echo("Starting TTS audio generation...")
    click.echo(f"Using Model: {app.config.get('TTS_MODEL')}")
    if app.config.get('TTS_VOCODER_MODEL'): # Only show if Vocoder is configured
        click.echo(f"Using Vocoder: {app.config.get('TTS_VOCODER_MODEL')}")
    click.echo(f"Language: {lang}, Force Regeneration: {force}")

    lessons_to_process = []
    if lesson is not None:
        click.echo(f"Targeting specific lesson: {lesson}")
        lesson_obj = Lesson.query.filter_by(lesson_number=lesson).first()
        if lesson_obj: lessons_to_process.append(lesson_obj)
        else: click.echo(f"Error: Lesson {lesson} not found.", err=True); return
    else:
        click.echo("Fetching all lessons...")
        lessons_to_process = Lesson.query.order_by(Lesson.lesson_number).all()
        click.echo(f"Found {len(lessons_to_process)} lessons.")

    if not lessons_to_process: click.echo("No lessons to process."); return

    total_lessons = len(lessons_to_process)
    processed_count = 0; success_count = 0; error_count = 0; skipped_no_text = 0

    click.echo("Processing lessons sequentially...")
    for lesson_obj in lessons_to_process:
        processed_count += 1
        click.echo(f"[{processed_count}/{total_lessons}] Processing Lesson {lesson_obj.lesson_number}...")

        text_to_use = None
        if lang == 'en' and hasattr(lesson_obj, 'text_en'): text_to_use = lesson_obj.text_en
        elif lang == 'zh-cn' and hasattr(lesson_obj, 'text_cn'): text_to_use = lesson_obj.text_cn
        # Add more languages if needed

        if not text_to_use or not text_to_use.strip():
            click.echo(f"  Skipping: No text found for language '{lang}'.")
            skipped_no_text += 1
            continue

        # --- generate_and_save_audio_if_not_exists 现在内部处理 force ---
        result_path = generate_and_save_audio_if_not_exists(
            lesson_number=lesson_obj.lesson_number,
            text=text_to_use,
            language=lang, # 传递 language, 函数内部会判断是否使用
            force=force    # 传递 force 标志
        )

        if result_path:
             # 函数内部会打印是跳过还是生成，这里只记录成功与否
             click.echo(f"  => OK (Path: {result_path})")
             success_count += 1
        else:
            click.echo(f"  => Error: Failed.", err=True)
            error_count += 1

    click.echo("\n--- Generation Summary ---")
    click.echo(f"Total Lessons Targetted: {total_lessons}")
    click.echo(f"Success/Exists: {success_count}")
    click.echo(f"Skipped (No Text): {skipped_no_text}")
    click.echo(f"Errors Encountered: {error_count}")
    click.echo("--------------------------")


if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', True)) # Read debug from config or default to True