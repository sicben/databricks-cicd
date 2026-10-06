import base64
import glob
import os

import requests

HOST = "https://" + os.environ["DB_HOST"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
RUN = os.environ["RUN_ID"]
HEAD = {"Authorization": "Bearer " + TOKEN}

# 递归收集仓库里所有 notebook（排除 .git 和编辑器临时目录）
files = [
    f for f in glob.glob("**/*.ipynb", recursive=True)
    if ".ipynb_checkpoints" not in f and ".git" not in f
]
assert files, "no .ipynb found in repo"
print("found", len(files), "notebooks:", files)

for base in ("/Workspace/prod/v" + RUN, "/Workspace/prod/current"):
    for f in files:
        # 去掉 .ipynb 后缀，按仓库相对路径映射为工作区路径
        # 例：etl/extract.ipynb -> /Workspace/prod/current/etl/extract
        nb = f[:-len(".ipynb")].replace("\\", "/")
        remote = base + "/" + nb
        parent = os.path.dirname(remote)

        r = requests.post(HOST + "/api/2.0/workspace/mkdirs", headers=HEAD, json={"path": parent})
        print("mkdirs", parent, r.status_code, r.text)

        with open(f, "rb") as fh:
            src = base64.b64encode(fh.read()).decode()
        r = requests.post(
            HOST + "/api/2.0/workspace/import",
            headers=HEAD,
            json={
                "path": remote,
                "format": "JUPYTER",
                "content": src,
                "overwrite": True,
            },
        )
        print("import", remote, r.status_code, r.text)
        assert r.status_code == 200, "import failed: " + remote

print("deployed", len(files), "notebooks -> prod/v" + RUN + " + prod/current")
