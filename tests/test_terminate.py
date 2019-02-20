import pickle
import os.path
from mapswipe_workers.basic import BaseFunctions



def delete_sample_data_from_firebase(firebase, project_id, import_key):
    fb_db = firebase.database()

    # first delete the project, import and all groups
    fb_db.update(
        {
            "projects/{}".format(project_id): None,
            "groups/{}".format(project_id): None,
            "imports/{}".format(import_key): None
        }
    )
    print('delete the import, project and all groups in firebase')

    # then delete all results for this project in firebase

    # get all results from firebase
    all_results = fb_db.child("results").get()

    data = {}
    for task_id, results in all_results.items():
        for child_id, result in results.items():

            print(result)

            if result['projectId'] == project_id:
                key = 'results/{task_id}/{child_id}'.format(
                    task_id=task_id,
                    child_id=child_id)

                data[key] = None

    fb_db.update(data)





def delete_sample_results_from_postgres(postgres, project_id, import_key):
    p_con = postgres()

    sql_query = '''
        DELETE FROM projects WHERE project_id = %s;
        DELETE FROM results WHERE project_id = %s;
        DELETE FROM tasks WHERE project_id = %s;
        DELETE FROM groups WHERE project_id = %s;
        DELETE FROM imports WHERE import_key = %s;
        '''

    data = [
        project_id,
        project_id,
        project_id,
        project_id,
        import_key
    ]

    p_con.query(sql_query, data)
    print('deleted import, project, groups, tasks, results in postgres')


if __name__ == '__main__':

    firebase, postgres = BaseFunctions.get_environment('development')

    for import_key, project_id, project_type in imported_projects:
        delete_sample_data_from_firebase(firebase, project_id, import_key)
        delete_sample_results_from_postgres(postgres, project_id, import_key)


