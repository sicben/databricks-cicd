import base64
import glob
import os

import requests

HOST = "https://" + os.environ["DB_HOST"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
RUN = os.environ["RUN_ID"]
HEAD = {"Authorization": "Bearer " + TOKEN}

files = glob.glob("hello.notebook")
assert files, "hello.notebook not found in repo"

with open(files[0], "rb") as f:
    src = base64.b64encode(f.read()).decode()

for base in ("/Workspace/prod/v" + RUN, "/Workspace/prod/current"):
    r = requests.post(HOST + "/api/2.0/workspace/mkdirs", headers=HEAD, json={"path": base})
    print("mkdirs", base, r.status_code, r.text)

for path in ("/Workspace/prod/v" + RUN + "/hello", "/Workspace/prod/current/hello"):
    r = requests.post(
        HOST + "/api/2.0/workspace/import",
        headers=HEAD,
        json={
            "path": path,
            "format": "SOURCE",
            "language": "PYTHON",
            "content": src,
            "overwrite": True,
        },
    )
    print("import", path, r.status_code, r.text)
    assert r.status_code == 200, "import failed: " + path

print("deployed: prod/v" + RUN + " + prod/current")
