import json
import sys
import time

import click
import schedule as sched

from mapswipe_workers import auth
from mapswipe_workers import generate_stats
from mapswipe_workers.definitions import CustomError
from mapswipe_workers.definitions import DATA_PATH
from mapswipe_workers.definitions import logger
from mapswipe_workers.firebase_to_postgres import transfer_results
from mapswipe_workers.firebase_to_postgres import update_data
from mapswipe_workers.utils import slack

from mapswipe_workers.project_types.build_area.build_area_project \
        import BuildAreaProject
from mapswipe_workers.project_types.footprint.footprint_project \
        import FootprintProject
from mapswipe_workers.project_types.change_detection.change_detection_project \
        import ChangeDetectionProject


@click.group()
@click.option(
        '--verbose',
        '-v',
        is_flag=True,
        )
@click.version_option()
def cli(verbose):
    if not verbose:
        logger.disabled = True


@click.command('create-projects')
@click.option(
        '--schedule',
        '-s',
        default=None,
        help=(
            f'Will create projects every '
            f'10 minutes (m), every hour (h) or every day (d). '
            ),
        type=click.Choice(['m', 'h', 'd'])
        )
def run_create_projects(schedule):
    if schedule:
        if schedule == 'm':
            sched.every(10).minutes.do(_run_create_projects)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'h':
            sched.every().hour.do(_run_create_projects)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'd':
            sched.every().day.do(_run_create_projects)
            while True:
                sched.run_pending()
                time.sleep(1)
        else:
            click.echo(
                    f'{schedule} is not a valid input '
                    f'for the schedule argument. '
                    f'Use m for every 10 minutes, '
                    f'h for every hour and d for every day.'
                    )
    else:
        _run_create_projects()


@click.command('firebase-to-postgres')
@click.option(
        '--schedule',
        '-s',
        default=None,
        help=(
            f'Will update and transfer relevant data (i.a. users and results) '
            f'from Firebase into Postgres '
            f'every 10 minutes (m), every hour (h) or every day (d). '
            ),
        type=click.Choice(['m', 'h', 'd'])
        )
def run_firebase_to_postgres(schedule):
    if schedule:
        if schedule == 'm':
            sched.every(10).minutes.do(_run_firebase_to_postgres)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'h':
            sched.every().hour.do(_run_firebase_to_postgres)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'd':
            sched.every().day.do(_run_firebase_to_postgres)
            while True:
                sched.run_pending()
                time.sleep(1)
        else:
            click.echo(
                    f'{schedule} is not a valid input '
                    f'for the schedule argument. '
                    f'Use m for every 10 minutes, '
                    f'h for every hour and d for every day.'
                    )
    else:
        _run_firebase_to_postgres()


@click.command('generate-stats')
@click.option(
        '--schedule',
        '-s',
        default=None,
        help=(
            f'Will generate stats every '
            f'10 minutes (m), every hour (h) or every day (d). '
            ),
        type=click.Choice(['m', 'h', 'd'])
        )
def run_generate_stats(schedule):
    if schedule:
        if schedule == 'm':
            sched.every(10).minutes.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'h':
            sched.every().hour.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'd':
            sched.every().day.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        else:
            click.echo(
                    f'{schedule} is not a valid input '
                    f'for the schedule argument. '
                    f'Use m for every 10 minutes, '
                    f'h for every hour and d for every day.'
                    )
    else:
        _run_generate_stats()


@click.command('run')
@click.option(
        '--schedule',
        '-s',
        default=None,
        help=(
            f'Will run Mapswipe Workers every '
            f'10 minutes (m), every hour (h) or every day (d). '
            ),
        type=click.Choice(['m', 'h', 'd'])
        )
def run(schedule):
    if schedule:
        if schedule == 'm':
            sched.every(10).minutes.do(_run_create_projects)
            sched.every(10).minutes.do(_run_firebase_to_postgres)
            sched.every(10).minutes.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'h':
            sched.every().hour.do(_run_create_projects)
            sched.every().hour.do(_run_firebase_to_postgres)
            sched.every().hour.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        elif schedule == 'd':
            sched.every().day.do(_run_create_projects)
            sched.every().day.do(_run_firebase_to_postgres)
            sched.every().day.do(_run_generate_stats)
            while True:
                sched.run_pending()
                time.sleep(1)
        else:
            click.echo(
                    f'{schedule} is not a valid input '
                    f'for the schedule argument. '
                    f'Use m for every 10 minutes, '
                    f'h for every hour and d for every day.'
                    )
    else:
        _run_create_projects()
        _run_firebase_to_postgres()
        _run_generate_stats()


def _run_create_projects():
    project_types = {
            # Make sure to import all project types here
            1: BuildAreaProject,
            2: FootprintProject,
            3: ChangeDetectionProject
            }
    project_type_names = {
            1: 'Build Area',
            2: 'Footprint',
            3: 'Change Detection'
            }

    fb_db = auth.firebaseDB()
    ref = fb_db.reference('v2/projectDrafts/')
    project_drafts = ref.get()

    if project_drafts is None:
        del(fb_db)
        return None

    else:
        created_project_ids = list()

        for project_draft_id, project_draft in project_drafts.items():
            project_draft['projectDraftId'] = project_draft_id
            # Early projects have no projectType attribute.
            # If so it defaults to 1
            project_type = project_draft.get('projectType', 1)
            try:
                # TODO: Document properly
                project = project_types[project_type](project_draft)
                project.validate_geometries()
                project.create_groups()
                project.calc_number_of_tasks()
                if project.save_project(fb_db):
                    created_project_ids.append(project.projectId)
                    newline = '\n'
                    message = (
                            f'### PROJECT CREATION SUCCESSFUL ###{newline}'
                            f'Project Name: {project.name}{newline}'
                            f'Project Id: {project.projectId}{newline}'
                            f'Project Type: {project_type_names[project_type]}'
                            f'{newline}'
                            f'Make sure to activate the project in firebase.'
                            f'{newline}'
                            f'Happy Swiping. :)'
                            )
                    slack.send_slack_message(message)
                    logger.info(message)
            except CustomError:
                logger.exception(
                    f'{project_draft_id} '
                    f'- project creation failed'
                    )
                continue
    del(fb_db)
    return created_project_ids


def _run_firebase_to_postgres():
    update_data.copy_new_users()
    transfer_results.transfer_results()


def _run_generate_stats():

    filename = 'aggregated_results.csv'
    generate_stats.get_aggregated_results(filename)

    project_id = '-Lmi5bJWP3T0xXthl1ET'
    filename = f'aggregated_results_by_task_id_{project_id}.csv'
    generate_stats.get_aggregated_results_by_task_id(filename, project_id)

    filename = 'aggregated_results_by_user_id.csv'
    generate_stats.get_aggregated_results_by_user_id(filename)




    logger.info('exported stats')
    '''
    data = generate_stats.get_general_stats()
    filename = f'{DATA_PATH}/stats.json'
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)
    logger.info('exported stats')

    data = generate_stats.get_all_active_projects()
    filename = f'{DATA_PATH}/active_projects.json'
    with open(filename, 'w') as outfile:
        json.dump(data, outfile)
    
    '''

    # TODO:
    # data = generate_stats.get_aggregated_results()
    # filename = f'{DATA_PATH}/aggregated_results.json'
    # with open(filename, 'w') as outfile:
    #     json.dump(data, outfile)
    # logger.info('exported aggregated results')


cli.add_command(run_create_projects)
cli.add_command(run_firebase_to_postgres)
cli.add_command(run_generate_stats)
cli.add_command(run)
