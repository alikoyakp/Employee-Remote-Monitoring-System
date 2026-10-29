import json
import os
import subprocess
import sys

import pytest
import requests
from dotenv import load_dotenv

HERE = os.path.dirname(__file__)
load_dotenv(os.path.join(HERE, "..", ".env"))
load_dotenv(os.path.join(HERE, "..", "..", "frontend", ".env"))
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="session")
def tokens():
    out = subprocess.run([sys.executable, os.path.join(HERE, "clerk_test_users.py"), "--tokens"],
                         capture_output=True, text=True, cwd=os.path.join(HERE, ".."), check=True).stdout
    return {j["employee_id"]: j for j in (json.loads(l) for l in out.strip().splitlines())}


def _client(tok):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="session")
def admin(tokens):
    return _client(tokens["TEST_ADM"]["token"])


@pytest.fixture(scope="session")
def manager(tokens):
    return _client(tokens["TEST_MGR"]["token"])


@pytest.fixture(scope="session")
def employee(tokens):
    return _client(tokens["TEST_EMP"]["token"])


@pytest.fixture(scope="session")
def mongo():
    from pymongo import MongoClient
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
