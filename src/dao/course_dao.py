"""
dao/course_dao.py — 课程 DAO

R16 清理: 删孤儿 find_by_code (返回类型错 + 无任何调用方)。
  原因:
    - 类型签名写 `-> List[Course]` 但实际 `.first()` 返回 Optional[Course]
      是误导, 后人调用必须包 try/except, 易踩坑。
    - 全代码库 (services + scripts + tests) 没有任何调用方, 仅死代码。
  真要用按 code 查单门课, 直接 CourseDao(s).s.query(Course)
  .filter(Course.course_code == code).first() 即可, 一行不需要包装。
"""
from typing import List

from sqlalchemy import or_

from src.dao.base import BaseDao
from src.models.course import Course
from src.models.course_teacher import CourseTeacher


class CourseDao(BaseDao[Course]):
    model = Course

    def find_by_teacher(self, teacher_id: int) -> List[Course]:
        """某老师授/助的所有课程（W14+ 同时查 ``Course.teacher_id`` 和关联表）。

        W14 之前：只查 ``Course.teacher_id == teacher_id``，只命中"主讲"。
        W14 引入了 ``course_teacher`` 多对多关联表后，3 个多老师课程
        （信号与系统 / 数据库原理 / 医用电子技术2）的助教老师
        在 ``Course.teacher_id`` 里查不到自己，会导致
        ``create_task_dialog`` 课程下拉显示"暂无可选课程"。

        修法：``OR`` 起来两个条件，覆盖两种历史数据：
          - 老数据：``Course.teacher_id`` 设了但 ``course_teacher`` 没建条目
          - W14+ 新数据：``import_schedule.py`` 把主讲+助教都入 ``course_teacher``

        注意：要去重 DISTINCT — 同一门课可能同时命中两个条件。
        """
        return (
            self.s.query(Course)
            .outerjoin(CourseTeacher, CourseTeacher.course_id == Course.id)
            .filter(
                or_(
                    Course.teacher_id == teacher_id,
                    CourseTeacher.teacher_id == teacher_id,
                )
            )
            .distinct()
            .all()
        )

    def find_all(self) -> List[Course]:
        return self.s.query(Course).order_by(Course.course_code).all()
