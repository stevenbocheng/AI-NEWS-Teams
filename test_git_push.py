"""
測試 git clone + commit + push 是否正常，不呼叫任何 AI API。
執行：python test_git_push.py
"""
import os
import subprocess
import tempfile
import shutil
import stat
from datetime import datetime

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

if not GITHUB_TOKEN or not GITHUB_REPO:
    print("❌ 缺少環境變數 GITHUB_TOKEN 或 GITHUB_REPO")
    exit(1)

print(f"✅ GITHUB_TOKEN: {'*' * 8}{GITHUB_TOKEN[-4:]}")
print(f"✅ GITHUB_REPO: {GITHUB_REPO}")

tmp_dir = tempfile.mkdtemp()
try:
    repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    clean_url = f"https://github.com/{GITHUB_REPO}.git"

    print(f"\n1. Clone {GITHUB_REPO} ...")
    import git as gitpython
    repo = gitpython.Repo.clone_from(repo_url, tmp_dir)
    print("   ✅ Clone 成功")

    print("2. 設定 git user ...")
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "GitHub Actions Bot")
        cw.set_value("user", "email", "actions@github.com")
        cw.set_value("credential", "helper", "")
    subprocess.run(
        ["git", "-C", tmp_dir, "config",
         "http.https://github.com/.extraheader",
         f"AUTHORIZATION: bearer {GITHUB_TOKEN}"],
        check=True, capture_output=True
    )
    print("   ✅ 設定成功")

    print("3. 新增測試檔案並 commit ...")
    test_file = os.path.join(tmp_dir, f"_test_{datetime.now().strftime('%H%M%S')}.txt")
    with open(test_file, "w") as f:
        f.write(f"git push test at {datetime.now()}")
    repo.index.add([test_file])
    repo.index.commit("test: git push authentication check")
    print("   ✅ Commit 成功")

    print("4. Push ...")
    push_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo"}
    result = subprocess.run(
        ["git", "-C", tmp_dir, "push", repo_url, "HEAD:main"],
        env=push_env, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"   ❌ Push 失敗:\n{result.stderr}")
    else:
        print("   ✅ Push 成功！")

    # 清理測試檔案
    print("5. 刪除測試檔案 ...")
    os.remove(test_file)
    repo.index.remove([test_file])
    repo.index.commit("test: cleanup test file")
    result2 = subprocess.run(
        ["git", "-C", tmp_dir, "push", repo_url, "HEAD:main"],
        env=push_env, capture_output=True, text=True
    )
    if result2.returncode == 0:
        print("   ✅ 清理成功")
    else:
        print(f"   ⚠️  清理 push 失敗（不影響測試結果）: {result2.stderr}")

finally:
    def _remove_readonly(func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(tmp_dir, onerror=_remove_readonly)
    print("\n完成。")
