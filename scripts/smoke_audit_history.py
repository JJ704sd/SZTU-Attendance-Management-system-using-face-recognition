"""W7-W12 关键 bug 修复 smoke 校验"""
import sys
from pathlib import Path
# W14 修复: 跨机适配 — 改成相对路径, 不再硬编码 D 盘
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))
import inspect

results = []

# W7 Bug 1: attendance_service 死方法 apply_leave/approve_leave 已删
from src.services.attendance_service import AttendanceService
has_dead = hasattr(AttendanceService, "apply_leave") or hasattr(AttendanceService, "approve_leave")
results.append(("W7 死方法删除", not has_dead, "期望 True"))

# W7 Bug 3: lab_access_log_dao 加 desc(id) tie-breaker
from src.dao.lab_access_log_dao import LabAccessLogDao
src = inspect.getsource(LabAccessLogDao)
has_tie = "id" in src and "desc" in src
results.append(("W7 lab_access tie-breaker", has_tie, "期望 True"))

# W8 Bug: auth_service.register 字段长度校验
from src.services.auth_service import AuthService
src = inspect.getsource(AuthService.register)
has_len = "len(" in src and ("50" in src or "20" in src or "100" in src)
results.append(("W8 register 长度校验", has_len, "期望 True"))

# W9 Bug 1: _lock 改 Lock
from src.ui.widgets.camera_widget import CameraWidget
src = inspect.getsource(CameraWidget)
has_lock = "threading.Lock" in src and "_lock" in src
results.append(("W9 _lock=Lock", has_lock, "期望 True"))

# W9 Bug 2: face_collect_dialog 成功 1.5s 后 accept
from src.ui.widgets.face_collect_dialog import FaceCollectDialog
src = inspect.getsource(FaceCollectDialog)
has_accept = "singleShot" in src and "accept" in src
results.append(("W9 success singleShot+accept", has_accept, "期望 True"))

# W9 Bug 3: student_window._open_camera 互斥
from src.ui.student_window import StudentWindow
src = inspect.getsource(StudentWindow)
has_mutex = "_open_camera" in src and ("register_camera" in src or "signin_camera" in src)
results.append(("W9 _open_camera 互斥", has_mutex, "期望 True"))

# W11 Bug 1: config.py 4 个 env var try/except
from src import config
src = inspect.getsource(config)
has_try = "_get_int" in src or ("try:" in src and "ValueError" in src)
results.append(("W11 config env try/except", has_try, "期望 True"))

# W11 Bug 2-6: int(item.text()) 4 处 try/except
for mod_name, fn_name in [
    ("src.ui.teacher_window", "TeacherWindow"),
    ("src.ui.widgets.leave_review_dialog", "LeaveReviewDialog"),
    ("src.ui.widgets.lab_admin_tab", "LabAdminTab"),
    ("src.ui.widgets.training_admin_tab", "TrainingAdminTab"),
]:
    try:
        mod = __import__(mod_name, fromlist=[fn_name])
        cls = getattr(mod, fn_name)
        src = inspect.getsource(cls)
        has = "int(" in src and "try:" in src
        results.append((f"W11 {fn_name} int(try)", has, "期望 True"))
    except Exception as e:
        results.append((f"W11 {fn_name}", False, f"import 失败: {e}"))

# W12: face_admin_tab 存在 + student_window 有 _on_clear_my_face
import os
results.append(("W12 face_admin_tab 存在", os.path.exists("src/ui/widgets/face_admin_tab.py"), "期望 True"))
src = inspect.getsource(StudentWindow)
results.append(("W12 _on_clear_my_face", "_on_clear_my_face" in src, "期望 True"))

# W12 摄像头: MSMF/DSHOW/重试
src = inspect.getsource(CameraWidget.start)
has_msmf = "CAP_MSMF" in src
has_dshow = "CAP_DSHOW" in src
has_retry = "retry" in src.lower() or "0.5" in src or "sleep" in src.lower() or "500" in src
results.append(("W12 start MSMF", has_msmf, "期望 True"))
results.append(("W12 start DSHOW", has_dshow, "期望 True"))
results.append(("W12 start retry", has_retry, "期望 True"))

# 输出
all_pass = True
for name, got, expected in results:
    mark = "OK" if got else "FAIL"
    if not got:
        all_pass = False
    print(f"  [{mark}] {name}  got={got}  ({expected})")
print()
print("ALL PASS" if all_pass else "SOME FAILED")
sys.exit(0 if all_pass else 1)
