"""
constants.py — 项目级常量集中地

- 角色枚举：user.role 列只能取以下三个值
- 角色显示标签：UI 把内部枚举值翻成中文
- 业务阈值：和 Config（环境变量）区分，这里是硬编码业务常量
"""
# 角色枚举（与 user.role 列保持一致；DB schema 也按这三个值定义）
ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_LAB_ADMIN = "lab_admin"

VALID_ROLES = (ROLE_STUDENT, ROLE_TEACHER, ROLE_LAB_ADMIN)

# 角色 → 中文显示
ROLE_LABELS = {
    ROLE_STUDENT: "学生",
    ROLE_TEACHER: "教师",
    ROLE_LAB_ADMIN: "实验室管理员",
}
