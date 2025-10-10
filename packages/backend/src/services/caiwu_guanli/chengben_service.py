"""
成本记录管理服务
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from models.caiwu_guanli import ChengbenJilu
from models.hetong_guanli import Hetong
from schemas.caiwu_guanli.chengben_schemas import (
    ChengbenAnalysis,
    ChengbenBudgetComparison,
    ChengbenJiluCreate,
    ChengbenJiluListParams,
    ChengbenJiluListResponse,
    ChengbenJiluResponse,
    ChengbenJiluUpdate,
    ChengbenStatistics,
)


class ChengbenService:
    """成本记录管理服务类"""

    def __init__(self, db: Session):
        self.db = db

    def create_chengben_jilu(
        self, jilu_data: ChengbenJiluCreate, created_by: str
    ) -> ChengbenJiluResponse:
        """创建成本记录"""
        # 验证合同是否存在（如果提供了合同ID）
        if jilu_data.hetong_id:
            hetong = (
                self.db.query(Hetong)
                .filter(Hetong.id == jilu_data.hetong_id, Hetong.is_deleted == "N")
                .first()
            )

            if not hetong:
                raise HTTPException(status_code=404, detail="合同不存在")

        # 生成成本编号
        chengben_bianhao = self._generate_chengben_bianhao()

        # 创建成本记录
        chengben_jilu = ChengbenJilu(
            chengben_bianhao=chengben_bianhao,
            **jilu_data.model_dump(),
            created_by=created_by,
        )

        self.db.add(chengben_jilu)
        self.db.commit()
        self.db.refresh(chengben_jilu)

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def get_chengben_jilu_list(
        self, params: ChengbenJiluListParams
    ) -> ChengbenJiluListResponse:
        """获取成本记录列表"""
        query = self.db.query(ChengbenJilu).filter(ChengbenJilu.is_deleted == "N")

        # 搜索条件
        if params.search:
            search_pattern = f"%{params.search}%"
            query = query.filter(
                or_(
                    ChengbenJilu.chengben_bianhao.like(search_pattern),
                    ChengbenJilu.chengben_mingcheng.like(search_pattern),
                    ChengbenJilu.gongyingshang_mingcheng.like(search_pattern),
                    ChengbenJilu.fapiao_hao.like(search_pattern),
                )
            )

        # 筛选条件
        if params.hetong_id:
            query = query.filter(ChengbenJilu.hetong_id == params.hetong_id)

        if params.xiangmu_id:
            query = query.filter(ChengbenJilu.xiangmu_id == params.xiangmu_id)

        if params.bumen_id:
            query = query.filter(ChengbenJilu.bumen_id == params.bumen_id)

        if params.chengben_leixing:
            query = query.filter(
                ChengbenJilu.chengben_leixing == params.chengben_leixing
            )

        if params.chengben_fenlei:
            query = query.filter(ChengbenJilu.chengben_fenlei == params.chengben_fenlei)

        if params.shenhe_zhuangtai:
            query = query.filter(
                ChengbenJilu.shenhe_zhuangtai == params.shenhe_zhuangtai
            )

        if params.fapiao_zhuangtai:
            query = query.filter(
                ChengbenJilu.fapiao_zhuangtai == params.fapiao_zhuangtai
            )

        if params.zhuangtai:
            query = query.filter(ChengbenJilu.zhuangtai == params.zhuangtai)

        # 日期范围
        if params.start_date:
            query = query.filter(ChengbenJilu.fasheng_shijian >= params.start_date)

        if params.end_date:
            query = query.filter(ChengbenJilu.fasheng_shijian <= params.end_date)

        # 总数统计
        total = query.count()

        # 分页查询
        offset = (params.page - 1) * params.size
        items = (
            query.order_by(desc(ChengbenJilu.fasheng_shijian))
            .offset(offset)
            .limit(params.size)
            .all()
        )

        # 计算总页数
        pages = (total + params.size - 1) // params.size

        return ChengbenJiluListResponse(
            items=[ChengbenJiluResponse.model_validate(item) for item in items],
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )

    def get_chengben_jilu_by_id(self, jilu_id: str) -> ChengbenJiluResponse:
        """根据ID获取成本记录详情"""
        chengben_jilu = (
            self.db.query(ChengbenJilu)
            .filter(ChengbenJilu.id == jilu_id, ChengbenJilu.is_deleted == "N")
            .first()
        )

        if not chengben_jilu:
            raise HTTPException(status_code=404, detail="成本记录不存在")

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def update_chengben_jilu(
        self, jilu_id: str, jilu_data: ChengbenJiluUpdate, updated_by: str
    ) -> ChengbenJiluResponse:
        """更新成本记录"""
        chengben_jilu = (
            self.db.query(ChengbenJilu)
            .filter(ChengbenJilu.id == jilu_id, ChengbenJilu.is_deleted == "N")
            .first()
        )

        if not chengben_jilu:
            raise HTTPException(status_code=404, detail="成本记录不存在")

        # 检查状态是否允许修改
        if chengben_jilu.shenhe_zhuangtai in ["recorded"]:
            raise HTTPException(status_code=400, detail="已入账的记录不允许修改")

        # 更新字段
        update_data = jilu_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(chengben_jilu, field, value)

        chengben_jilu.updated_by = updated_by
        chengben_jilu.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(chengben_jilu)

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def submit_chengben_jilu(
        self, jilu_id: str, submitted_by: str
    ) -> ChengbenJiluResponse:
        """提交成本记录"""
        chengben_jilu = (
            self.db.query(ChengbenJilu)
            .filter(ChengbenJilu.id == jilu_id, ChengbenJilu.is_deleted == "N")
            .first()
        )

        if not chengben_jilu:
            raise HTTPException(status_code=404, detail="成本记录不存在")

        if chengben_jilu.shenhe_zhuangtai != "draft":
            raise HTTPException(status_code=400, detail="只有草稿状态的记录才能提交")

        # 更新状态
        chengben_jilu.shenhe_zhuangtai = "submitted"
        chengben_jilu.updated_by = submitted_by
        chengben_jilu.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(chengben_jilu)

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def audit_chengben_jilu(
        self, jilu_id: str, audit_result: str, audit_comment: str, auditor_id: str
    ) -> ChengbenJiluResponse:
        """审核成本记录"""
        chengben_jilu = (
            self.db.query(ChengbenJilu)
            .filter(ChengbenJilu.id == jilu_id, ChengbenJilu.is_deleted == "N")
            .first()
        )

        if not chengben_jilu:
            raise HTTPException(status_code=404, detail="成本记录不存在")

        if chengben_jilu.shenhe_zhuangtai != "submitted":
            raise HTTPException(status_code=400, detail="只有已提交的记录才能审核")

        # 更新审核信息
        chengben_jilu.shenhe_zhuangtai = audit_result
        chengben_jilu.shenhe_ren = auditor_id
        chengben_jilu.shenhe_shijian = datetime.now()
        chengben_jilu.shenhe_yijian = audit_comment
        chengben_jilu.updated_by = auditor_id
        chengben_jilu.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(chengben_jilu)

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def record_chengben(
        self,
        jilu_id: str,
        shiji_jine: Decimal,
        jizhangjian: datetime = None,
        kuaiji_kemu: str = None,
        chengben_zhongxin: str = None,
        recorder_id: str = None,
    ) -> ChengbenJiluResponse:
        """成本入账"""
        chengben_jilu = (
            self.db.query(ChengbenJilu)
            .filter(ChengbenJilu.id == jilu_id, ChengbenJilu.is_deleted == "N")
            .first()
        )

        if not chengben_jilu:
            raise HTTPException(status_code=404, detail="成本记录不存在")

        if chengben_jilu.shenhe_zhuangtai != "approved":
            raise HTTPException(status_code=400, detail="只有已审批的记录才能入账")

        # 更新入账信息
        chengben_jilu.shenhe_zhuangtai = "recorded"
        chengben_jilu.shiji_jine = shiji_jine
        chengben_jilu.jizhangjian = jizhangjian or datetime.now()

        if kuaiji_kemu:
            chengben_jilu.kuaiji_kemu = kuaiji_kemu
        if chengben_zhongxin:
            chengben_jilu.chengben_zhongxin = chengben_zhongxin

        chengben_jilu.updated_by = recorder_id
        chengben_jilu.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(chengben_jilu)

        return ChengbenJiluResponse.model_validate(chengben_jilu)

    def get_chengben_statistics(self) -> ChengbenStatistics:
        """获取成本统计信息"""
        status_counts = (
            self.db.query(
                func.count(ChengbenJilu.id).label("total_count"),
                func.sum(
                    case((ChengbenJilu.shenhe_zhuangtai == "draft", 1), else_=0)
                ).label("draft_count"),
                func.sum(
                    case((ChengbenJilu.shenhe_zhuangtai == "submitted", 1), else_=0)
                ).label("submitted_count"),
                func.sum(
                    case((ChengbenJilu.shenhe_zhuangtai == "approved", 1), else_=0)
                ).label("approved_count"),
                func.sum(
                    case((ChengbenJilu.shenhe_zhuangtai == "recorded", 1), else_=0)
                ).label("recorded_count"),
                func.sum(
                    case((ChengbenJilu.shenhe_zhuangtai == "rejected", 1), else_=0)
                ).label("rejected_count"),
            )
            .filter(ChengbenJilu.is_deleted == "N")
            .first()
        )

        total_amount = self.db.query(func.sum(ChengbenJilu.chengben_jine)).filter(
            ChengbenJilu.is_deleted == "N"
        ).scalar() or Decimal("0")

        budget_amount = self.db.query(func.sum(ChengbenJilu.yusuan_jine)).filter(
            ChengbenJilu.is_deleted == "N", ChengbenJilu.yusuan_jine.isnot(None)
        ).scalar() or Decimal("0")

        actual_amount = self.db.query(func.sum(ChengbenJilu.shiji_jine)).filter(
            ChengbenJilu.is_deleted == "N", ChengbenJilu.shiji_jine.isnot(None)
        ).scalar() or Decimal("0")

        variance_amount = (
            actual_amount - budget_amount if budget_amount > 0 else Decimal("0")
        )
        variance_rate = (
            (variance_amount / budget_amount * 100)
            if budget_amount > 0
            else Decimal("0")
        )

        return ChengbenStatistics(
            total_count=status_counts.total_count or 0,
            draft_count=status_counts.draft_count or 0,
            submitted_count=status_counts.submitted_count or 0,
            approved_count=status_counts.approved_count or 0,
            recorded_count=status_counts.recorded_count or 0,
            rejected_count=status_counts.rejected_count or 0,
            total_amount=total_amount,
            budget_amount=budget_amount,
            actual_amount=actual_amount,
            variance_amount=variance_amount,
            variance_rate=variance_rate,
        )

    def get_chengben_analysis(self) -> ChengbenAnalysis:
        """获取成本分析"""
        # 按类型分析
        by_type = (
            self.db.query(
                ChengbenJilu.chengben_leixing,
                func.sum(ChengbenJilu.chengben_jine).label("total_amount"),
                func.count(ChengbenJilu.id).label("count"),
            )
            .filter(ChengbenJilu.is_deleted == "N")
            .group_by(ChengbenJilu.chengben_leixing)
            .all()
        )

        # 按分类分析
        by_category = (
            self.db.query(
                ChengbenJilu.chengben_fenlei,
                func.sum(ChengbenJilu.chengben_jine).label("total_amount"),
                func.count(ChengbenJilu.id).label("count"),
            )
            .filter(ChengbenJilu.is_deleted == "N")
            .group_by(ChengbenJilu.chengben_fenlei)
            .all()
        )

        # 按部门分析
        by_department = (
            self.db.query(
                ChengbenJilu.bumen_id,
                func.sum(ChengbenJilu.chengben_jine).label("total_amount"),
                func.count(ChengbenJilu.id).label("count"),
            )
            .filter(ChengbenJilu.is_deleted == "N", ChengbenJilu.bumen_id.isnot(None))
            .group_by(ChengbenJilu.bumen_id)
            .all()
        )

        # 按项目分析
        by_project = (
            self.db.query(
                ChengbenJilu.xiangmu_id,
                func.sum(ChengbenJilu.chengben_jine).label("total_amount"),
                func.count(ChengbenJilu.id).label("count"),
            )
            .filter(ChengbenJilu.is_deleted == "N", ChengbenJilu.xiangmu_id.isnot(None))
            .group_by(ChengbenJilu.xiangmu_id)
            .all()
        )

        # 趋势分析（按月）
        trend_analysis = (
            self.db.query(
                func.date_format(ChengbenJilu.fasheng_shijian, "%Y-%m").label("month"),
                func.sum(ChengbenJilu.chengben_jine).label("total_amount"),
                func.count(ChengbenJilu.id).label("count"),
            )
            .filter(
                ChengbenJilu.is_deleted == "N",
                ChengbenJilu.fasheng_shijian >= datetime.now() - timedelta(days=365),
            )
            .group_by(func.date_format(ChengbenJilu.fasheng_shijian, "%Y-%m"))
            .all()
        )

        return ChengbenAnalysis(
            by_type=[
                {"type": item[0], "amount": float(item[1]), "count": item[2]}
                for item in by_type
            ],
            by_category=[
                {"category": item[0], "amount": float(item[1]), "count": item[2]}
                for item in by_category
            ],
            by_department=[
                {"department": item[0], "amount": float(item[1]), "count": item[2]}
                for item in by_department
            ],
            by_project=[
                {"project": item[0], "amount": float(item[1]), "count": item[2]}
                for item in by_project
            ],
            trend_analysis=[
                {"month": item[0], "amount": float(item[1]), "count": item[2]}
                for item in trend_analysis
            ],
        )

    def _generate_chengben_bianhao(self) -> str:
        """生成成本编号"""
        today = datetime.now().strftime("%Y%m%d")

        # 查询今天已有的成本记录数量
        count = (
            self.db.query(ChengbenJilu)
            .filter(
                ChengbenJilu.chengben_bianhao.like(f"CB{today}%"),
                ChengbenJilu.is_deleted == "N",
            )
            .count()
        )

        # 生成编号：CB + 日期 + 4位序号
        sequence = str(count + 1).zfill(4)
        return f"CB{today}{sequence}"
