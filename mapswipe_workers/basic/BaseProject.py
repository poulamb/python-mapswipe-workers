import os
import logging
import threading
import numpy as np
from queue import Queue
import requests
import time
import json
import csv

from mapswipe_workers.utils import error_handling

class BaseProject(object):
    """
    The basic class for a project

    Attributes
    ----------
    id : int
        The id of a project
    name : str
        The name of a project
    project_details : str
        The detailed description of the project
    look_for : str
        The objects of interest / objects to look for in this project
    image: str
        The URL of the header image of the project
    verification_count : int
        The number of users required for each task to be finished
    is_featured : bool
        Whether a project is displayed as a featured project in the app
    state : int
        Whether a project is displayed in the app
        0 = displayed
        1 = ???
        2 = ???
        3 = not displayed
    group_average : float
        The average number of tasks per group
    progress : int
        The number of finished tasks in percent
    contributors : int
        The number of users contributing to this project
    """

    ####################################################################################################################
    # INIT - Existing projects from id, new projects from import_key and import_dict                                   #
    ####################################################################################################################
    def __init__(self, project_id: int, firebase: object, mysqlDB: object, import_key: str = None, import_dict: dict = None) -> object:

        logging.warning('%s - __init__ - start init' % project_id)

        # set basic project information
        self.id = project_id

        # check if project and groups exist in firebase and get attributes
        project_data = self.project_exists_firebase(firebase)

        # if a project exists in firebase we get the values from there to init the project
        if project_data:
            # we set attributes based on the data from firebase
            self.import_key = project_data['importKey']
            self.name = project_data['name']
            self.image = project_data['image']
            self.look_for = project_data['lookFor']
            self.project_details = project_data['projectDetails']
            self.verification_count = int(project_data['verificationCount'])

            # the following attributes are set regardless the imported information
            self.is_featured = project_data['isFeatured']
            self.state = project_data['state']
            self.group_average = project_data['groupAverage']
            self.progress = project_data['progress']
            self.contributors = project_data['contributors']

            # old projects might not have an info field in firebase
            try:
                self.info = project_data['info']
            except:
                self.info = {}

        else:
            # this is a new project, which has not been imported, we indicate this by setting a temporary attribute
            self.is_new = True

            # first we check, whether there is no project with the same id in the mysql database
            if self.project_exists_mysql(mysqlDB):
                logging.warning("%s - __init__ - project is new, but has been imported to mysql already. Can't init project." % self.id)
                return None
            # then let's check if the import_key and import_dict are provided
            elif not import_key:
                logging.warning("%s - __init__ - no import_key has been provided to create a new project. Can't init project." % self.id)
                return None
            elif not import_dict:
                logging.warning("%s - __init__ - no import_dict information has been provided to create a new project. Cant't init project." % self.id)
                return None
            else:
                try:
                    # let's set the attributes from the parameters provided in the import_dict
                    self.import_key = import_key
                    self.name = import_dict['project']['name']
                    self.image = import_dict['project']['image']
                    self.look_for = import_dict['project']['lookFor']
                    self.project_details = import_dict['project']['projectDetails']
                    self.verification_count = int(import_dict['project']['verificationCount'])

                    # the following attributes are set regardless the imported information
                    self.is_featured = False
                    self.state = 3
                    self.group_average = 0
                    self.progress = 0
                    self.contributors = 0
                except Exception as e:
                    logging.warning("%s - __init__ - could not get all project info from dict. Cant't init project." % self.id)
                    logging.warning("%s - __init__ - %s" % (self.id, e) )
                    return None


    ####################################################################################################################
    # EXISTS - Check if a project exists                                                                               #
    ####################################################################################################################
    def project_exists_firebase(self, firebase):
        """
        The function to check whether a project exists in firebase.

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool or dict
            False if project doesn't exist in firebase projects table, project data dict otherwise.
        """

        fb_db = firebase.database()
        project_data = fb_db.child("projects").child(self.id).get().val()

        if not project_data:
            logging.warning('%s - project_exists_firebase - project not in firebase' % self.id)
            return False
        # a valid project in firebase has at least 12 attributes
        elif len(project_data) < 12:
            logging.warning('%s - project_exists_firebase - project is in firebase, but misses critical information' % self.id)
            return False
        else:
            # we will also check if at least one group exists for this project
            fb_db = firebase.database()
            groups_data = fb_db.child("groups").child(self.id).shallow().get().val()

            if not groups_data:
                logging.warning('%s - project_exists_firebase - groups not in firebase' % self.id)
                return False
            else:
                logging.warning('%s - project_exists_firebase - project and groups exist in firebase' % self.id)
                return project_data

    def project_exists_mysql(self, mysqlDB):
        """
        The function to check whether a project exists in mysql.

        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True is project exists in mysql database. False otherwise.
        """

        m_con = mysqlDB()
        sql_query = '''
            SELECT
              *
            FROM
              projects
            WHERE
              project_id = %s
        '''

        data = [self.id]
        project_data = m_con.retr_query(sql_query, data)
        del m_con

        if not project_data:
            logging.warning('%s - project_exists_firebase - not in mysql database' % self.id)
            return False
        else:
            logging.warning('%s - project_exists_firebase - exists in mysql database' % self.id)
            return True

    ####################################################################################################################
    # IMPORT - We define a bunch of functions related to importing new projects                                        #
    ####################################################################################################################
    def import_project(self, firebase, mysqlDB):
        """
        The function to import a new project

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True if successful. False otherwise.
        """

        try:
            logging.warning('%s - import_project - start importing' % self.id)
            groups = self.create_groups()
            self.set_groups_firebase(firebase, groups)
            self.set_tasks_psql(mysqlDB, groups)
            self.set_groups_psql(mysqlDB, groups)
            self.set_project_psql(mysqlDB)
            self.set_project_firebase(firebase)
            self.set_import_complete(firebase)
            logging.warning('%s - import_project - import finished' % self.id)
            return True
        except Exception as e:
            logging.warning('%s - import_project - could not import project' % self.id)
            logging.warning("%s - import_project - %s" % (self.id, e))
            error_handling.log_error(e, logging)
            self.delete_project(firebase, mysqlDB)
            return False

    def set_groups_firebase(self, firebase, groups):
        """
        The function to upload groups to firebase

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if groups have been uploaded to firebase, False otherwise
        """

        # upload groups in firebase
        fb_db = firebase.database()
        fb_db.child("groups").child(self.id).set(groups)
        logging.warning('%s - set_groups_firebase - uploaded groups in firebase' % self.id)

    def set_project_firebase(self, firebase):
        """
        The function to upload the project information to the firebase projects table

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise

        Notes
        -----
        We don't upload all information to firebase
        We need to be careful with spelling here
        We do this to avoid uploading groups, etc.
        """

        project = {
            "id": self.id,
            "projectType": self.project_type,
            "name": self.name,
            "image": self.image,
            "lookFor": self.look_for,
            "projectDetails": self.project_details,
            "verificationCount": self.verification_count,
            "importKey": self.import_key,
            "isFeatured": self.is_featured,
            "state":  self.state,
            "groupAverage": self.group_average,
            "progress": self.progress,
            "contributors": self.contributors,
            "info": self.info
        }

        fb_db = firebase.database()
        fb_db.child("projects").child(project['id']).set(project)
        logging.warning('%s - set_project_firebase - uploaded project in firebase' % self.id)
        return True

    def set_tasks_psql(self, mysqlDB, groups, tasks_txt_filename='raw_tasks.txt'):
        """
        The function iterates over the groups and extracts tasks and uploads them into postgresql
        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database
        groups : dictionary
            Dictionary containing groups of a project
        tasks_txt_filename : string
            Pointer for storing the tasks temporary in csv format

        Returns
        -------
        bool
            True if successful. False otherwise

        """
        # save tasks in txt file
        tasks_txt_file = open(tasks_txt_filename, 'w', newline='')

        fieldnames = ('task_id', 'project_id', 'group_id', 'info')
        w = csv.DictWriter(tasks_txt_file, fieldnames=fieldnames, delimiter='\t', quotechar="'")

        for group in groups:
            for task in groups[group]['tasks']:

                try:
                    output_dict = {
                        "task_id": groups[group]['tasks'][task]['id'],
                        "project_id": int(groups[group]['tasks'][task]['projectId']),
                        "group_id": int(group),
                        "info": {}
                    }

                    for key in groups[group]['tasks'][task].keys():
                        if not key in ['id', 'projectId']:
                            output_dict['info'][key] = groups[group]['tasks'][task][key]
                    output_dict['info'] = json.dumps(output_dict['info'])

                    w.writerow(output_dict)

                except Exception as e:
                    logging.warning('ALL - set_tasks_psql - tasks missed critical information: %s' % e)

        tasks_txt_file.close()

        # upload data to psql

        m_con = mysqlDB()

        sql_insert = 'DROP TABLE IF EXISTS raw_tasks CASCADE;'
        m_con.query(sql_insert, None)

        # first importer to a table where we store the geom as text
        sql_insert = '''
            DROP TABLE IF EXISTS raw_tasks;
            CREATE TABLE raw_tasks (
                task_id varchar
                ,group_id int
                ,project_id int
                ,info json
            );
            '''

        m_con.query(sql_insert, None)

        f = open(tasks_txt_filename, 'r')
        columns = ['task_id', 'project_id', 'group_id', 'info']
        m_con.copy_from(f, 'raw_tasks', sep='\t', columns=columns)
        logging.warning('ALL - set_tasks_psql - inserted raw tasks into table raw_tasks')
        f.close()

        os.remove(tasks_txt_filename)
        logging.warning('ALL - set_tasks_psql - deleted file: %s' % tasks_txt_filename)

        # TODO discuss if conflict resolution necessary

        sql_insert = '''
                INSERT INTO
                  tasks
                SELECT
                  *
                  -- duplicates is set to zero by default, this will be updated on conflict only
                  --,0
                FROM
                  raw_tasks
                --ON CONFLICT ON CONSTRAINT "tasks_pkey";
                  
            '''
        m_con.query(sql_insert, None)
        logging.warning('ALL - set_tasks_psql - inserted tasks into tasks table')

        del m_con

        return True

    def set_groups_psql(self, mysqlDB, groups, groups_txt_filename='raw_groups.txt'):

        groups_txt_file = open(groups_txt_filename, 'w', newline='')

        fieldnames = ('project_id', 'group_id', 'completedCount', 'count', 'info')
        w = csv.DictWriter(groups_txt_file, fieldnames=fieldnames, delimiter='\t', quotechar="'")

        for group in groups:
            try:
                output_dict = {
                    "project_id": int(groups[group]['projectId']),
                    "group_id": int(groups[group]['id']),
                    "count": int(groups[group]['count']),
                    "completedCount": int(groups[group]['completedCount']),
                    "info": {}

                }

                for key in groups[group].keys():
                    if not key in ['project_id', 'group_id', 'count',
                                   'completedCount', 'tasks']:
                        output_dict['info'][key] = groups[group][key]
                output_dict['info'] = json.dumps(output_dict['info'])

                w.writerow(output_dict)

            except Exception as e:
                logging.warning('ALL - set_groups_psql - groups missed critical information: %s' % e)
                error_handling.log_error(e, logging)

        groups_txt_file.close()

        m_con = mysqlDB()

        sql_insert = 'DROP TABLE IF EXISTS raw_groups CASCADE;'
        m_con.query(sql_insert, None)

        # first importer to a table where we store the geom as text
        sql_insert = '''
            DROP TABLE IF EXISTS raw_groups;
            CREATE TABLE raw_groups (
              project_id int
              ,group_id int
              ,count int
              ,completedCount int
              ,info json
                                );
            '''

        m_con.query(sql_insert, None)

        f = open(groups_txt_filename, 'r')
        columns = ['project_id', 'group_id', 'count', 'completedCount', 'info']
        m_con.copy_from(f, 'raw_groups', sep='\t', columns=columns)
        logging.warning('ALL - set_groups_psql - inserted raw groups into table raw_groups')
        f.close()

        os.remove(groups_txt_filename)
        logging.warning('ALL - set_groups_psql - deleted file: %s' % groups_txt_filename)

        sql_insert = '''
                        INSERT INTO
                          groups
                        SELECT
                          *
                          -- duplicates is set to zero by default, this will be updated on conflict only
                          --,0
                        FROM
                          raw_groups
                        --ON CONFLICT ON CONSTRAINT "tasks_pkey";

                    '''
        m_con.query(sql_insert, None)
        logging.warning('ALL - set_groups_psql - inserted groups into groups table')

        del m_con

        return True



    def set_project_psql(self, mysqlDB):
        """
        The function to create a project in mysql
        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        m_con = mysqlDB()
        sql_insert = "INSERT INTO projects Values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        data = [int(self.contributors), int(self.group_average), int(self.id), self.image, self.import_key,
                self.is_featured, self.look_for, self.name, self.progress, self.project_details, int(self.state),
                int(self.project_type),int(self.verification_count), json.dumps(self.info)]
        # insert in table
        try:
            m_con.query(sql_insert, data)
        except Exception as e:
            del m_con
            raise

        logging.warning('%s - set_project_psql - inserted project info in mysql' % self.id)
        return True

    def set_import_complete(self, firebase):
        """
        The function to set an import as complete by adding a "complete" attribute in firebase

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        fb_db = firebase.database()
        fb_db.child("imports").child(self.import_key).child('complete').set(True)

        logging.warning('%s - set_import_complete - set import complete for import %s' % (self.id, self.import_key))
        return True

    ####################################################################################################################
    # DELETE - We define a bunch of functions related to delete project information                                    #
    ####################################################################################################################
    def delete_project(self, firebase, mysqlDB):
        """
        The function to delete all project related information in firebase and mysql
            This includes information on groups

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        logging.warning('%s - delete_project - start deleting project' % self.id)
        self.delete_groups_firebase(firebase)
        self.delete_project_firebase(firebase)
        self.delete_project_mysql(mysqlDB)
        self.delete_tasks_psql(mysqlDB)
        self.delete_groups_psql(mysqlDB)
        self.delete_results_mysql(mysqlDB)
        logging.warning('%s - delete_project - finished delete project' % self.id)
        return True

    def delete_groups_firebase(self, firebase):
        """
        The function to delete all groups of a project in firebase

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        fb_db = firebase.database()
        fb_db.child("groups").child(self.id).remove()
        logging.warning('%s - delete_groups_firebase - deleted groups in firebase' % self.id)
        return

    def delete_project_firebase(self, firebase):
        """
        The function to delete the project entry in the firebase projects table

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise.
        """

        fb_db = firebase.database()
        fb_db.child("projects").child(self.id).remove()
        logging.warning('%s - delete_project_firebase - deleted project in firebase' % self.id)
        return True

    def delete_import_firebase(self, firebase):
        """
        The function to delete an import in firebase
        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise.
        """

        fb_db = firebase.database()
        fb_db.child("imports").child(self.import_key).remove()

        logging.warning('%s - delete_import_firebase - deleted import in firebase' % self.import_key)
        return True

    def delete_project_mysql(self, mysqlDB):
        """
        The function to delete a project in the mysql projects table.

        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True is successful. False otherwise.

        TODO:
        -----
        Handle exception:
            pymysql.err.InternalError: (1205, 'Lock wait timeout exceeded; try restarting transaction')
        """

        m_con = mysqlDB()
        sql_insert = "DELETE FROM projects WHERE project_id = %s"
        data = [int(self.id)]
        # insert in table
        m_con.query(sql_insert, data)
        del m_con

        logging.warning('%s - delete_project_mysql - deleted project info in mysql' % self.id)
        return True


    def delete_results_mysql(self, mysqlDB):
        """
        The function to delete all results of project in the mysql results table.

        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True is successful. False otherwise.

        TODO:
        -----
        Handle exception:
            pymysql.err.InternalError: (1205, 'Lock wait timeout exceeded; try restarting transaction')
        """

        m_con = mysqlDB()
        sql_insert = "DELETE FROM results WHERE project_id = %s"
        data = [int(self.id)]
        m_con.query(sql_insert, data)
        del m_con

        logging.warning('%s - delete_results_mysql - deleted all results in mysql' % self.id)
        return True

    def delete_tasks_psql(self, mysqlDB):
        m_con = mysqlDB()
        sql_insert = "DELETE FROM tasks WHERE project_id = %s"
        data = [int(self.id)]
        m_con.query(sql_insert, data)
        del m_con

        logging.warning('%s - delete_tasks_psql - deleted all tasks in psql' % self.id)
        return True

    def delete_groups_psql(self, mysqlDB):
        m_con = mysqlDB()
        sql_insert = "DELETE FROM groups WHERE project_id = %s"
        data = [int(self.id)]
        m_con.query(sql_insert, data)
        del m_con

        logging.warning('%s - delete_groups_psql - deleted all groups in psql' % self.id)
        return True
    ####################################################################################################################
    # UPDATE - We define a bunch of functions related to updating existing projects                                    #
    ####################################################################################################################
    def update_project(self, firebase, mysqlDB, output_path='data'):
        self.get_contributors(mysqlDB)
        self.set_contributors(firebase)
        self.log_project_contributors(output_path)
        self.get_progress(firebase)
        self.set_progress(firebase)
        self.log_project_progress(output_path)
        #self.set project_progress_psql()

    def get_group_progress(self, q):
        """
        The function to get the progress for groups in queue

        Parameters
        ----------
        q : queue
            A queue object containing a list with the following items:
            fb_db : firebase connection
            group_progress_list : list
            group_id : int

        Returns
        -------

        """
        while not q.empty():
            # get the values from the q object
            fb_db, group_progress_list, group_id = q.get()

            # this functions downloads only the completed count per group from firebase
            try:
                # establish a new connection to firebase
                completed_count = fb_db.child("groups").child(self.id).child(group_id).child("completedCount").get().val()

                # progress in percent, progress can't be bigger than 100
                progress = 100.0 * float(completed_count) / float(self.verification_count)
                if progress > 100:
                    progress = 100.0
                # all variables are converted to float to avoid errors when computing the mean later
                group_progress_list.append(
                    [float(self.id), float(group_id), float(completed_count), float(self.verification_count),
                     float(progress)])
                q.task_done()

            except Exception as e:
                # add a catch, if something with the connection to firebase goes wrong and log potential errors
                logging.warning("%s - get_groups_progress - %s" % (self.id,e))
                # if we can't get the completed count for a group, we will set it to 0.0
                completed_count = 0.0
                progress = 0.0
                # all variables are converted to float to avoid errors when computing the mean later
                group_progress_list.append(
                    [float(self.id), float(group_id), float(completed_count), float(self.verification_count),
                     float(progress)])
                q.task_done()

    def get_progress(self, firebase, num_threads=24):
        """
        The function to compute the progress of the project

        Parameters
        ----------
         firebase : pyrebase firebase object
            initialized firebase app with admin authentication
        num_threads : int, optional
            The number of threads to use, default: 24

        Notes
        -----
        We use threading in this function.
        There is no easy way to compute the sum of the completed count for all groups.
        """

        fb_db = firebase.database()
        # this tries to set the max pool connections to 100
        adapter = requests.adapters.HTTPAdapter(max_retries=5, pool_connections=100, pool_maxsize=100)
        for scheme in ('http://', 'https://'):
            fb_db.requests.mount(scheme, adapter)

        # it is important to use the shallow option, only keys will be loaded and not the complete json
        all_groups = fb_db.child("groups").child(self.id).shallow().get().val()
        logging.warning('%s - get_progress - downloaded all keys for groups from firebase' % self.id)

        # we will use a queue to limit the number of threads running in parallel
        q = Queue(maxsize=0)
        group_progress_list = []

        for group_id in all_groups:
            q.put([fb_db, group_progress_list, group_id])
        logging.warning('%s - get_progress - added all groups to queue' % self.id)

        logging.warning('%s - get_progress - setup threading with %s workers' % (self.id, num_threads))
        for i in range(num_threads):
            worker = threading.Thread(
                target=self.get_group_progress,
                args=(q,))
            worker.start()

        q.join()
        del fb_db
        logging.warning('%s - get_progress - downloaded progress for all groups from firebase' % self.id)

        # calculate project progress
        self.progress = np.average(group_progress_list, axis=0)[-1]
        logging.warning('%s - get_progress - calculated progress. progress = %s' % (self.id, self.progress))

    def get_contributors(self, mysqlDB):
        """
        The function to query the number of contributor for the project from the mysql database

        Parameters
        ----------
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        contributors : int
            The number of users who contributed to this project
        """

        # establish mysql connection
        m_con = mysqlDB()
        # sql command
        sql_query = '''
                SELECT
                  count(distinct(user_id))
                FROM
                  results
                WHERE
                  project_id = %s
            '''
        data = [self.id]
        # one row with one value will be returned
        self.contributors = m_con.retr_query(sql_query, data)[0][0]
        # delete/close db connection
        del m_con

        logging.warning("%s - get_contributors - got project contributors from mysql. contributors =  %s" % (self.id, self.contributors))

    def set_progress(self, firebase):
        """
        The function to set the progress in percent in firebase.

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        fb_db = firebase.database()
        # progress will be displayed as integer in the app
        fb_db.child("projects").child(self.id).update({"progress": int(self.progress)})

        logging.warning('%s - set_progress - set progress in firebase' % self.id)
        return True

    def set_contributors(self, firebase):
        """
        The function to set the number of contributors in firebase.

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication

        Returns
        -------
        bool
            True if successful. False otherwise.
        """

        fb_db = firebase.database()
        fb_db.child("projects").child(self.id).update({"contributors": self.contributors})

        logging.warning('%s - set_contributors - set contributors in firebase' % self.id)
        return True

    ####################################################################################################################
    # EXPORT - We define a bunch of functions related to exporting exiting projects                                    #
    ####################################################################################################################
    def log_project_progress(self, output_path='data'):
        """
        The function to log the progress to a txt file in the format 'progress_{ID}.txt'

        Parameters
        ----------
        output_path : str, optional
            The path where the txt file will be stored. Default='data'

        Notes
        -----
        The generated txt file will consist of a single line per log.
        We log a unix timestamp and the progress separated by comma
        """

        # check if output path for projects is correct and existing
        if not os.path.exists(output_path + '/progress'):
            os.makedirs(output_path + '/progress')

        filename = "{}/progress/progress_{}.txt".format(output_path, self.id)

        with open(filename, 'a') as output_file:
            timestamp = int(time.time())
            outline = "{},{}\n".format(timestamp, self.progress)
            output_file.write(outline)

        logging.warning('%s - log_project_progress - logged progress to file: %s' % (self.id, filename))
        return True

    def log_project_contributors(self, output_path='data'):
        """
        The function to log the contributors to a txt file in the format 'contributors_{ID}.txt'

        Parameters
        ----------
        output_path : str, optional
            The path where the txt file will be stored. Default='data'

        Notes
        -----
        The generated txt file will consist of a single line per log.
        We log a unix timestamp and the contributors separated by comma
        """

        # check if output path for projects is correct and existing
        if not os.path.exists(output_path + '/contributors'):
            os.makedirs(output_path + '/contributors')

        filename = "{}/contributors/contributors_{}.txt".format(output_path, self.id)

        with open(filename, 'a') as output_file:
            timestamp = int(time.time())
            outline = "{},{}\n".format(timestamp, self.contributors)
            output_file.write(outline)

        logging.warning('%s - log_project_contributors - logged contributors to file: %s' % (self.id, filename))
        return True


    def export_results(self, mysqlDB, output_path='data'):
        """
        The function save the results of the project in a list of jsons'

        Parameters
        ----------
        output_path : str, optional
            The path where the json file will be stored. Default='data'
        """


        # this function is set concerning the project type
        results_list = self.aggregate_results(mysqlDB)

        output_json_file = '{}/projects/{}.json'.format(output_path, self.id)

        with open(output_json_file, 'w') as outfile:
            json.dump(results_list, outfile)

        logging.warning('ALL - export_results - exported results file: %s' % output_json_file)
        return True

    ####################################################################################################################
    # ARCHIVE - We define a bunch of functions related to archiving exiting projects                                   #
    ####################################################################################################################
    def archive_project(self, firebase, mysqlDB):
        """
        The function to archives all project related information in firebase
            This includes information on groups

        Parameters
        ----------
        firebase : pyrebase firebase object
            initialized firebase app with admin authentication
        mysqlDB : database connection class
            The database connection to mysql database

        Returns
        -------
        bool
            True if successful. False otherwise
        """

        logging.warning('%s - archive_project - start archiving project' % self.id)
        self.archive_groups_firebase(firebase)
        self.archive_project_firebase(firebase)
        self.archive_project_mysql(mysqlDB)
        logging.warning('%s - archive_project - finished archive project' % self.id)
        return True