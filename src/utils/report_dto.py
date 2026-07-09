"""
utils/report_dto.py — 报表数据 DTO (R16 新增)

为什么放 utils 不放 services?
  这 4 个 dataclass 是「纯数据形状」, 没有业务行为, 只用来跨层传值:
    - report_service.py 创建并填充 (services 层)
    - utils/charts.py 读取字段画图 (utils 层)
  之前 charts.py `from src.services.report_service import ...` 形成
  **utils → services 反向依赖**, 违反 4 层架构 (utils 不应依赖业务代码)。

  拆出本模块后, 依赖方向变成:
    - utils/charts.py   → utils/report_dto   ✓ (utils 内部互引 OK)
    - services/report_service.py → utils/report_dto  ✓ (services → utils OK)
  4 层架构方向重新自顶向下。

为什么不放 models/?
  models/ 是 SQLAlchemy ORM 模型 (跟 db/schema.sql 对应, 12 张表)。
  这 4 个 dataclass 不对应任何表, 只是 view model / DTO, 放 models/ 会污染语义。

为什么放 utils/ 不放 services/?
  如果放 services/ 新建 src/services/report_dto.py, charts.py 还是要
  `from src.services.report_dto import ...`, 反向依赖没解。
  放 utils/ 是唯一让两个 layer 都能单向依赖的方案。
"""
from dataclasses import dataclass
from datetime import date


@dataclass
class StudentRate:
    student_id: int
    real_name: str
    rate: float  # 0-1


@dataclass
class TrendPoint:
    date: date
    rate: float


@dataclass
class LabUsagePoint:
    date: date
    hour: int
    count: int


@dataclass
class AbsentWarning:
    student_id: int
    real_name: str
    rate: float
    course_name: str  # "（全部课程）" 或具体课程名