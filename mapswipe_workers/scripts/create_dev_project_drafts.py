import json
import os
from pathlib import Path

from mapswipe_workers import auth


def create_dev_project_draft():
    script_path = os.path.dirname(__file__)
    file_path = os.path.join(script_path, "fixtures",)
    fb_db = auth.firebaseDB()
    ref = fb_db.reference("/v2/projectDrafts/")
    project_drafts = list(Path(file_path).rglob("*.json"))
    for path in project_drafts:
        with open(path) as file:
            project_draft = json.load(file)
        ref.push(project_draft)


if __name__ == "__main__":
    create_dev_project_draft()
