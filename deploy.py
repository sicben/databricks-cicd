import base64
import glob
import os

import requests

HOST = "https://" + os.environ["DB_HOST"]
TOKEN = os.environ["DATABRICKS_TOKEN"]
RUN = os.environ["RUN_ID"]
HEAD = {"Authorization": "Bearer " + TOKEN}
CURRENT = "/Workspace/prod/current"

# 1. 收集仓库里所有 notebook（含子目录）
files = [f.replace("\\", "/") for f in glob.glob("**/*.ipynb", recursive=True)]
files = [f for f in files if not f.startswith(".github/")]
assert files, "no notebook found in repo"
names = {f[: -len(".ipynb")] for f in files}  # 如 hello、etl/extract
print("repo notebooks:", sorted(names))

# 2. 部署到 prod/vN（存档）+ prod/current（生效）
bases = ["/Workspace/prod/v" + RUN, CURRENT]
for base in bases:
    for name in sorted(names):
        parts = name.split("/")
        for i in range(1, len(parts)):  # 逐级建子目录
            d = base + "/" + "/".join(parts[:i])
            requests.post(HOST + "/api/2.0/workspace/mkdirs", headers=HEAD, json={"path": d})
        with open(name + ".ipynb", "rb") as f:
            src = base64.b64encode(f.read()).decode()
        path = base + "/" + name
        r = requests.post(
            HOST + "/api/2.0/workspace/import",
            headers=HEAD,
            json={"path": path, "format": "JUPYTER", "content": src, "overwrite": True},
        )
        print("import", path, r.status_code, r.text)
        assert r.status_code == 200, "import failed: " + path

# 3. 清理幽灵：prod/current 里存在、但仓库里已经没有的 notebook
def list_notebooks(path):
    r = requests.get(HOST + "/api/2.0/workspace/list", headers=HEAD, params={"path": path})
    if r.status_code != 200:
        return []
    out = []
    for obj in r.json().get("objects", []):
        if obj["object_type"] == "NOTEBOOK":
            out.append(obj["path"])
        elif obj["object_type"] == "DIRECTORY":
            out += list_notebooks(obj["path"])
    return out

remote = {p[len(CURRENT) + 1:] for p in list_notebooks(CURRENT)}
ghosts = sorted(remote - names)
for name in ghosts:
    path = CURRENT + "/" + name
    r = requests.post(HOST + "/api/2.0/workspace/delete", headers=HEAD,
                      json={"path": path, "recursive": True})
    print("delete ghost", path, r.status_code, r.text)
    assert r.status_code == 200, "delete failed: " + path

# 4. 清掉删空后遗留的空目录（如 etl/、analytics/）
ghost_dirs = sorted({name.split("/")[0] for name in ghosts if "/" in name})
for d in ghost_dirs:
    if d in names:
        continue
    remaining = [p for p in list_notebooks(CURRENT) if p.startswith(CURRENT + "/" + d)]
    if not remaining:
        path = CURRENT + "/" + d
        r = requests.post(HOST + "/api/2.0/workspace/delete", headers=HEAD,
                          json={"path": path, "recursive": True})
        print("delete empty dir", path, r.status_code, r.text)

print("deployed: prod/v" + RUN + " + prod/current, ghost cleanup done")
