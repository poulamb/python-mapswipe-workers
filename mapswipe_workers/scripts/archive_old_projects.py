from mapswipe_workers import auth
from mapswipe_workers.definitions import logger


def get_old_projects():
    """
    Get all projects from Firebase which have been created
    before we switched to v2.
    """
    fb_db = auth.firebaseDB()
    ref = fb_db.reference("projects")
    projects = ref.get()
    logger.info("got old projects from firebase")
    return projects


def move_project_data_to_v2(project_id):
    """
    Copy project information from old path to v2/projects in Firebase.
    Add status=archived attribute.
    Use Firebase transaction function for this.
    """

    # Firebase transaction function
    def transfer(current_data):
        current_data["status"] = "archived"
        current_data["projectType"] = 1
        fb_db.reference("v2/projects/{0}".format(project_id)).set(current_data)
        return dict()

    fb_db = auth.firebaseDB()
    projects_ref = fb_db.reference(f"projects/{project_id}")
    try:
        projects_ref.transaction(transfer)
        logger.info(f"{project_id}: Transfered project to v2 and delete in old path")
        return True
    except fb_db.TransactionAbortedError:
        logger.exception(
            f"{project_id}: Firebase transaction"
            f"for transferring project failed to commit"
        )
        return False


def delete_old_groups(project_id):
    """
    Delete old groups for a project
    """
    fb_db = auth.firebaseDB()
    fb_db.reference("groups/{0}".format(project_id)).set({})
    logger.info(f"deleted groups for: {project_id}")


def delete_other_old_data():
    """
    Delete old imports, results, announcements in Firebase
    """
    fb_db = auth.firebaseDB()
    fb_db.reference("imports").set({})
    fb_db.reference("results").set({})
    fb_db.reference("announcements").set({})
    logger.info(f"deleted old results, imports, announcements")


def archive_old_projects():
    """
    Run workflow to archive old projects.
    First get all old projects.
    Move project data to v2/projects in Firebase and
    set status=archived.
    Then delete all groups for a project.
    Finally, delete old results, imports and announcements.
    We don't touch the old user data in this workflow.
    """

    projects = get_old_projects()
    for project_id in projects.keys():
        if move_project_data_to_v2(project_id):
            delete_old_groups(project_id)
        else:
            logger.info(f"didn't delete project and groups for project: {project_id}")

    delete_other_old_data()


archive_old_projects()