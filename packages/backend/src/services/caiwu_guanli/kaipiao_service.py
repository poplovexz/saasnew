"""
开票申请管理服务
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from models.caiwu_guanli import KaipiaoShenqing
from models.hetong_guanli import Hetong
from models.kehu_guanli import Kehu
from models.zhifu_guanli import ZhifuDingdan
from schemas.caiwu_guanli.kaipiao_schemas import (
    KaipiaoShenqingCreate,
    KaipiaoShenqingListParams,
    KaipiaoShenqingListResponse,
    KaipiaoShenqingResponse,
    KaipiaoShenqingUpdate,
    KaipiaoStatistics,
)


class KaipiaoService:
    """开票申请管理服务类"""

    def __init__(self, db: Session):
        self.db = db

    def create_kaipiao_shenqing(
        self, shenqing_data: KaipiaoShenqingCreate, created_by: str
    ) -> KaipiaoShenqingResponse:
        """创建开票申请"""
        # 验证客户是否存在
        kehu = (
            self.db.query(Kehu)
            .filter(Kehu.id == shenqing_data.kehu_id, Kehu.is_deleted == "N")
            .first()
        )

        if not kehu:
            raise HTTPException(status_code=404, detail="客户不存在")

        # 验证合同是否存在（如果提供了合同ID）
        if shenqing_data.hetong_id:
            hetong = (
                self.db.query(Hetong)
                .filter(Hetong.id == shenqing_data.hetong_id, Hetong.is_deleted == "N")
                .first()
            )

            if not hetong:
                raise HTTPException(status_code=404, detail="合同不存在")

        # 验证支付订单是否存在（如果提供了订单ID）
        if shenqing_data.zhifu_dingdan_id:
            zhifu_dingdan = (
                self.db.query(ZhifuDingdan)
                .filter(
                    ZhifuDingdan.id == shenqing_data.zhifu_dingdan_id,
                    ZhifuDingdan.is_deleted == "N",
                )
                .first()
            )

            if not zhifu_dingdan:
                raise HTTPException(status_code=404, detail="支付订单不存在")

        # 生成申请编号
        shenqing_bianhao = self._generate_shenqing_bianhao()

        # 创建开票申请
        kaipiao_shenqing = KaipiaoShenqing(
            shenqing_bianhao=shenqing_bianhao,
            shenqing_shijian=datetime.now(),
            **shenqing_data.model_dump(),
            created_by=created_by,
        )

        self.db.add(kaipiao_shenqing)
        self.db.commit()
        self.db.refresh(kaipiao_shenqing)

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def get_kaipiao_shenqing_list(
        self, params: KaipiaoShenqingListParams
    ) -> KaipiaoShenqingListResponse:
        """获取开票申请列表"""
        query = self.db.query(KaipiaoShenqing).filter(KaipiaoShenqing.is_deleted == "N")

        # 搜索条件
        if params.search:
            search_pattern = f"%{params.search}%"
            query = query.filter(
                or_(
                    KaipiaoShenqing.shenqing_bianhao.like(search_pattern),
                    KaipiaoShenqing.kaipiao_mingcheng.like(search_pattern),
                    KaipiaoShenqing.gouwu_fang_mingcheng.like(search_pattern),
                    KaipiaoShenqing.fapiao_hao.like(search_pattern),
                )
            )

        # 筛选条件
        if params.hetong_id:
            query = query.filter(KaipiaoShenqing.hetong_id == params.hetong_id)

        if params.kehu_id:
            query = query.filter(KaipiaoShenqing.kehu_id == params.kehu_id)

        if params.kaipiao_leixing:
            query = query.filter(
                KaipiaoShenqing.kaipiao_leixing == params.kaipiao_leixing
            )

        if params.shenqing_zhuangtai:
            query = query.filter(
                KaipiaoShenqing.shenqing_zhuangtai == params.shenqing_zhuangtai
            )

        if params.kaipiao_zhuangtai:
            query = query.filter(
                KaipiaoShenqing.kaipiao_zhuangtai == params.kaipiao_zhuangtai
            )

        # 日期范围
        if params.start_date:
            query = query.filter(KaipiaoShenqing.shenqing_shijian >= params.start_date)

        if params.end_date:
            query = query.filter(KaipiaoShenqing.shenqing_shijian <= params.end_date)

        # 总数统计
        total = query.count()

        # 分页查询
        offset = (params.page - 1) * params.size
        items = (
            query.order_by(desc(KaipiaoShenqing.created_at))
            .offset(offset)
            .limit(params.size)
            .all()
        )

        # 计算总页数
        pages = (total + params.size - 1) // params.size

        return KaipiaoShenqingListResponse(
            items=[KaipiaoShenqingResponse.model_validate(item) for item in items],
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )

    def get_kaipiao_shenqing_by_id(self, shenqing_id: str) -> KaipiaoShenqingResponse:
        """根据ID获取开票申请详情"""
        kaipiao_shenqing = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.id == shenqing_id, KaipiaoShenqing.is_deleted == "N"
            )
            .first()
        )

        if not kaipiao_shenqing:
            raise HTTPException(status_code=404, detail="开票申请不存在")

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def update_kaipiao_shenqing(
        self, shenqing_id: str, shenqing_data: KaipiaoShenqingUpdate, updated_by: str
    ) -> KaipiaoShenqingResponse:
        """更新开票申请"""
        kaipiao_shenqing = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.id == shenqing_id, KaipiaoShenqing.is_deleted == "N"
            )
            .first()
        )

        if not kaipiao_shenqing:
            raise HTTPException(status_code=404, detail="开票申请不存在")

        # 检查状态是否允许修改
        if kaipiao_shenqing.shenqing_zhuangtai in ["invoiced", "cancelled"]:
            raise HTTPException(status_code=400, detail="当前状态不允许修改")

        # 更新字段
        update_data = shenqing_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kaipiao_shenqing, field, value)

        kaipiao_shenqing.updated_by = updated_by
        kaipiao_shenqing.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(kaipiao_shenqing)

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def submit_kaipiao_shenqing(
        self, shenqing_id: str, submitted_by: str
    ) -> KaipiaoShenqingResponse:
        """提交开票申请"""
        kaipiao_shenqing = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.id == shenqing_id, KaipiaoShenqing.is_deleted == "N"
            )
            .first()
        )

        if not kaipiao_shenqing:
            raise HTTPException(status_code=404, detail="开票申请不存在")

        if kaipiao_shenqing.shenqing_zhuangtai != "draft":
            raise HTTPException(status_code=400, detail="只有草稿状态的申请才能提交")

        # 更新状态
        kaipiao_shenqing.shenqing_zhuangtai = "submitted"
        kaipiao_shenqing.updated_by = submitted_by
        kaipiao_shenqing.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(kaipiao_shenqing)

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def audit_kaipiao_shenqing(
        self, shenqing_id: str, audit_result: str, audit_comment: str, auditor_id: str
    ) -> KaipiaoShenqingResponse:
        """审核开票申请"""
        kaipiao_shenqing = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.id == shenqing_id, KaipiaoShenqing.is_deleted == "N"
            )
            .first()
        )

        if not kaipiao_shenqing:
            raise HTTPException(status_code=404, detail="开票申请不存在")

        if kaipiao_shenqing.shenqing_zhuangtai != "submitted":
            raise HTTPException(status_code=400, detail="只有已提交的申请才能审核")

        # 更新审核信息
        kaipiao_shenqing.shenqing_zhuangtai = audit_result
        kaipiao_shenqing.shenhe_ren = auditor_id
        kaipiao_shenqing.shenhe_shijian = datetime.now()
        kaipiao_shenqing.shenhe_yijian = audit_comment
        kaipiao_shenqing.updated_by = auditor_id
        kaipiao_shenqing.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(kaipiao_shenqing)

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def process_invoice(
        self,
        shenqing_id: str,
        fapiao_hao: str,
        fapiao_daima: str,
        fapiao_wenjian_lujing: str = None,
        processor_id: str = None,
    ) -> KaipiaoShenqingResponse:
        """处理开票"""
        kaipiao_shenqing = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.id == shenqing_id, KaipiaoShenqing.is_deleted == "N"
            )
            .first()
        )

        if not kaipiao_shenqing:
            raise HTTPException(status_code=404, detail="开票申请不存在")

        if kaipiao_shenqing.shenqing_zhuangtai != "approved":
            raise HTTPException(status_code=400, detail="只有已审批的申请才能开票")

        # 更新开票信息
        kaipiao_shenqing.shenqing_zhuangtai = "invoiced"
        kaipiao_shenqing.kaipiao_zhuangtai = "completed"
        kaipiao_shenqing.fapiao_hao = fapiao_hao
        kaipiao_shenqing.fapiao_daima = fapiao_daima
        kaipiao_shenqing.fapiao_wenjian_lujing = fapiao_wenjian_lujing
        kaipiao_shenqing.kaipiao_shijian = datetime.now()
        kaipiao_shenqing.updated_by = processor_id
        kaipiao_shenqing.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(kaipiao_shenqing)

        return KaipiaoShenqingResponse.model_validate(kaipiao_shenqing)

    def get_kaipiao_statistics(self) -> KaipiaoStatistics:
        """获取开票统计信息"""
        status_counts = (
            self.db.query(
                func.count(KaipiaoShenqing.id).label("total_count"),
                func.sum(
                    case((KaipiaoShenqing.shenqing_zhuangtai == "draft", 1), else_=0)
                ).label("draft_count"),
                func.sum(
                    case(
                        (KaipiaoShenqing.shenqing_zhuangtai == "submitted", 1), else_=0
                    )
                ).label("submitted_count"),
                func.sum(
                    case((KaipiaoShenqing.shenqing_zhuangtai == "approved", 1), else_=0)
                ).label("approved_count"),
                func.sum(
                    case((KaipiaoShenqing.shenqing_zhuangtai == "invoiced", 1), else_=0)
                ).label("invoiced_count"),
                func.sum(
                    case((KaipiaoShenqing.shenqing_zhuangtai == "rejected", 1), else_=0)
                ).label("rejected_count"),
            )
            .filter(KaipiaoShenqing.is_deleted == "N")
            .first()
        )

        total_amount = self.db.query(func.sum(KaipiaoShenqing.jia_shui_jine)).filter(
            KaipiaoShenqing.is_deleted == "N"
        ).scalar() or Decimal("0")

        invoiced_amount = self.db.query(func.sum(KaipiaoShenqing.jia_shui_jine)).filter(
            KaipiaoShenqing.is_deleted == "N",
            KaipiaoShenqing.shenqing_zhuangtai == "invoiced",
        ).scalar() or Decimal("0")

        pending_amount = self.db.query(func.sum(KaipiaoShenqing.jia_shui_jine)).filter(
            KaipiaoShenqing.is_deleted == "N",
            KaipiaoShenqing.shenqing_zhuangtai.in_(["submitted", "approved"]),
        ).scalar() or Decimal("0")

        return KaipiaoStatistics(
            total_count=status_counts.total_count or 0,
            draft_count=status_counts.draft_count or 0,
            submitted_count=status_counts.submitted_count or 0,
            approved_count=status_counts.approved_count or 0,
            invoiced_count=status_counts.invoiced_count or 0,
            rejected_count=status_counts.rejected_count or 0,
            total_amount=total_amount,
            invoiced_amount=invoiced_amount,
            pending_amount=pending_amount,
        )

    def _generate_shenqing_bianhao(self) -> str:
        """生成申请编号"""
        today = datetime.now().strftime("%Y%m%d")

        # 查询今天已有的申请数量
        count = (
            self.db.query(KaipiaoShenqing)
            .filter(
                KaipiaoShenqing.shenqing_bianhao.like(f"KP{today}%"),
                KaipiaoShenqing.is_deleted == "N",
            )
            .count()
        )

        # 生成编号：KP + 日期 + 4位序号
        sequence = str(count + 1).zfill(4)
        return f"KP{today}{sequence}"
