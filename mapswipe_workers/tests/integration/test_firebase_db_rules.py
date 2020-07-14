import json
import unittest
from requests.exceptions import HTTPError
import requests
import re
from mapswipe_workers.config import FIREBASE_DB, FIREBASE_API_KEY
from mapswipe_workers.auth import firebaseDB
from mapswipe_workers.definitions import logger, CustomError
from mapswipe_workers.utils import user_management


def set_up_team():
    fb_db = firebaseDB()
    team_id = "unittest-team-1234"
    team_name = "unittest-team"
    team_token = "12345678-1234-5678-1234-567812345678"
    data = {"teamName": team_name, "teamToken": team_token}
    ref = fb_db.reference(f"v2/teams/{team_id}")
    ref.set(data)

    return team_id, team_name, team_token


def tear_down_team(team_id):
    fb_db = firebaseDB()
    # check if reference path is valid, e.g. if team_id is None
    ref = fb_db.reference(f"v2/teams/{team_id}")
    if not re.match(r"/v2/\w+/[-a-zA-Z0-9]+", ref.path):
        raise CustomError(
            f"""Given argument resulted in invalid Firebase Realtime Database reference.
                                    {ref.path}"""
        )

    # delete team in firebase
    ref.delete()


def setup_user(project_manager: bool, team_member: bool, team_id=None):
    if project_manager and team_member:
        username = f"unittest-project-manager-and-team-member"
    elif project_manager:
        username = f"unittest-project-manager"
    elif team_member:
        username = f"unittest-team-member"
    else:
        username = f"unittest-normal-user"

    email = f"{username}@mapswipe.org"
    password = f"{username}_pw"

    # username will be user.display_name
    user = user_management.create_user(email, username, password)

    # set project manager credentials

    # set team member attribute
    if team_member:
        user_management.add_user_to_team(email, team_id)

    return user


def sign_in_with_email_and_password(email, password):
    api_key = FIREBASE_API_KEY
    request_ref = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        "?key={0}".format(api_key)
    )
    headers = {"content-type": "application/json; charset=UTF-8"}
    data = json.dumps({"email": email, "password": password, "returnSecureToken": True})
    request_object = requests.post(request_ref, headers=headers, data=data)
    current_user = request_object.json()
    logger.info(f"signed in with user {email}")
    return current_user


def permission_denied(request_object):
    try:
        request_object.raise_for_status()
    except HTTPError as e:
        if "Permission denied" in request_object.text:
            return True
        else:
            raise HTTPError(e, request_object.text)


def test_get_endpoint(user, path, custom_arguments=""):
    database_url = f"https://{FIREBASE_DB}.firebaseio.com"
    request_ref = f"{database_url}{path}.json?{custom_arguments}&auth={user['idToken']}"
    headers = {"content-type": "application/json; charset=UTF-8"}
    request_object = requests.get(request_ref, headers=headers)
    if permission_denied(request_object):
        logger.info(
            f"permission denied for {database_url}{path}.json?{custom_arguments}"
        )
        return False
    else:
        logger.info(
            f"permission granted for {database_url}{path}.json?{custom_arguments}"
        )
        return True


def test_set_endpoint(user, endpoint):
    pass


def test_update_endpoint(user, endpoint):
    pass


class TestFirebaseDBRules(unittest.TestCase):
    def setUp(self):
        # setup team
        self.team_id, self.team_name, self.team_token = set_up_team()
        fb_db = firebaseDB()
        ref = fb_db.reference(f"v2/teams/{self.team_id}")
        ref.set({"teamName": "unittest-team", "teamToken": ""})

        # setup public project
        self.public_project_id = "unittest-public-project"
        fb_db = firebaseDB()
        ref = fb_db.reference(f"v2/projects/{self.public_project_id}")
        ref.update({"status": "active"})

        # setup private project
        self.private_project_id = "unittest-private-project"
        fb_db = firebaseDB()
        ref = fb_db.reference(f"v2/projects/{self.private_project_id}")
        ref.update({"teamId": self.team_id, "status": "private_active"})

        # setup users
        self.normal_user = setup_user(project_manager=False, team_member=False)
        self.team_member = setup_user(
            project_manager=False, team_member=True, team_id=self.team_id
        )
        self.project_manager = setup_user(project_manager=True, team_member=False)
        self.project_manager_and_team_member = setup_user(
            project_manager=True, team_member=True, team_id=self.team_id
        )

        # generate all endpoints to test
        self.endpoints = [  # [path, custom_arguments]
            # projects
            [f"/v2/projects", f'orderBy="status"&equalTo="active"&limitToFirst=20'],
            [f"/v2/projects/{self.public_project_id}/status", ""],
            [
                f"/v2/projects",
                f'orderBy="teamId"&equalTo="{self.team_id}"&limitToFirst=20',
            ],
            [f"/v2/projects/{self.private_project_id}/status", ""],
            # teams
            [f"/v2/teams/{self.team_id}", ""],
            [f"/v2/teams/{self.team_id}/teamName", ""],
            [f"/v2/teams/{self.team_id}/teamToken", ""],
            # groups
            [f"/v2/groups/{self.public_project_id}", ""],
            [f"/v2/groups/{self.private_project_id}", ""],
            # tasks
            [f"/v2/tasks/{self.public_project_id}", ""],
            [f"/v2/tasks/{self.private_project_id}", ""],
            # users
            [f"/v2/users/<user_id>", ""],
            [f"/v2/users/<user_id>/teamId", ""],
            [f"/v2/users/<user_id>/username", ""],
            # results
            [f"/v2/results/{self.public_project_id}/<group_id>/<user_id>", ""],
            [f"/v2/results/{self.private_project_id}/<group_id>/<user_id>", ""],
        ]

    def tearDown(self):
        # tear down team
        tear_down_team(self.team_id)

        # tear down users
        user_management.delete_user(self.normal_user.email)
        user_management.delete_user(self.team_member.email)
        user_management.delete_user(self.project_manager.email)
        user_management.delete_user(self.project_manager_and_team_member.email)

        # tear down public project

        # tear down private project

    def test_access_as_normal_user(self):
        # sign in user with email and password to simulate app user
        user = sign_in_with_email_and_password(
            self.normal_user.email, f"{self.normal_user.display_name}_pw"
        )

        expected_access = [  # [read, write]
            [True, False],  # public project query
            [True, False],  # public project status attribute
            [False, False],  # private project query
            [False, False],  # private project status attribute
            [False, False],  # team
            [False, False],  # teamName
            [False, False],  # teamToken
            [True, False],  # public group
            [False, False],  # private group
            [True, False],  # public task
            [False, False],  # private task
            [True, False],  # user
            [True, False],  # user teamId
            [True, True],  # user username
            [False, True],  # results public project
            [False, False],  # results private project
        ]

        for i, endpoint in enumerate(self.endpoints):
            path = endpoint[0].replace("<user_id>", user["localId"])
            custom_arguments = endpoint[1]
            access = test_get_endpoint(user, path, custom_arguments)
            self.assertEqual(
                access,
                expected_access[i][0],
                f"observed, expected, {endpoint} {user['displayName']}",
            )

    def test_access_as_team_member(self):
        # sign in user with email and password to simulate app user
        user = sign_in_with_email_and_password(
            self.team_member.email, f"{self.team_member.display_name}_pw"
        )

        expected_access = [  # [read, write]
            [True, False],  # public project query
            [True, False],  # public project status attribute
            [True, False],  # private project query
            [True, False],  # private project status
            [False, False],  # team
            [True, False],  # teamName
            [False, False],  # teamToken
            [True, False],  # public group
            [True, False],  # private group
            [True, False],  # public task
            [True, False],  # private task
            [True, False],  # user
            [True, False],  # user teamId
            [True, True],  # user username
            [False, True],  # results public project
            [False, True],  # results private project
        ]

        for i, endpoint in enumerate(self.endpoints):
            path = endpoint[0].replace("<user_id>", user["localId"])
            custom_arguments = endpoint[1]
            access = test_get_endpoint(user, path, custom_arguments)
            self.assertEqual(
                access,
                expected_access[i][0],
                f"observed, expected, {endpoint} {user['displayName']}",
            )

    """
    def test_access_as_team_member(self):
        user = self.team_member
        pass

    def test_access_as_project_manager(self):
        user = self.project_manager
        pass

    def test_access_as_project_manager_and_team_member(self):
        user = self.project_manager_and_team_member
        pass
    """


if __name__ == "__main__":
    unittest.main()