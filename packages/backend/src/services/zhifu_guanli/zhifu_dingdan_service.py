"""
支付订单管理服务
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from core.events import EventNames, publish
from models.hetong_guanli import Hetong
from models.kehu_guanli import Kehu
from models.zhifu_guanli import ZhifuDingdan
from schemas.zhifu_guanli.zhifu_dingdan_schemas import (
    ZhifuDingdanCreate,
    ZhifuDingdanListParams,
    ZhifuDingdanListResponse,
    ZhifuDingdanResponse,
    ZhifuDingdanStatistics,
    ZhifuDingdanUpdate,
)


class ZhifuDingdanService:
    """支付订单管理服务类"""

    def __init__(self, db: Session):
        self.db = db

    def create_zhifu_dingdan(
        self, dingdan_data: ZhifuDingdanCreate, created_by: str
    ) -> ZhifuDingdanResponse:
        """创建支付订单"""
        # 验证合同是否存在
        hetong = (
            self.db.query(Hetong)
            .filter(Hetong.id == dingdan_data.hetong_id, Hetong.is_deleted == "N")
            .first()
        )

        if not hetong:
            raise HTTPException(status_code=404, detail="合同不存在")

        # 验证客户是否存在
        kehu = (
            self.db.query(Kehu)
            .filter(Kehu.id == dingdan_data.kehu_id, Kehu.is_deleted == "N")
            .first()
        )

        if not kehu:
            raise HTTPException(status_code=404, detail="客户不存在")

        # 生成订单编号
        dingdan_bianhao = self._generate_dingdan_bianhao()

        # 创建支付订单
        zhifu_dingdan = ZhifuDingdan(
            dingdan_bianhao=dingdan_bianhao,
            chuangjian_shijian=datetime.now(),
            **dingdan_data.model_dump(),
            created_by=created_by,
        )

        self.db.add(zhifu_dingdan)
        self.db.commit()
        self.db.refresh(zhifu_dingdan)

        # 发布支付订单创建事件
        publish(
            EventNames.PAYMENT_ORDER_CREATED,
            {
                "zhifu_dingdan_id": zhifu_dingdan.id,
                "hetong_id": dingdan_data.hetong_id,
                "kehu_id": dingdan_data.kehu_id,
                "dingdan_jine": float(dingdan_data.dingdan_jine),
                "zhifu_leixing": dingdan_data.zhifu_leixing,
                "created_by": created_by,
            },
        )

        return ZhifuDingdanResponse.model_validate(zhifu_dingdan)

    def get_zhifu_dingdan_by_id(self, dingdan_id: str) -> ZhifuDingdanResponse:
        """根据ID获取支付订单"""
        zhifu_dingdan = (
            self.db.query(ZhifuDingdan)
            .filter(ZhifuDingdan.id == dingdan_id, ZhifuDingdan.is_deleted == "N")
            .first()
        )

        if not zhifu_dingdan:
            raise HTTPException(status_code=404, detail="支付订单不存在")

        return ZhifuDingdanResponse.model_validate(zhifu_dingdan)

    def update_zhifu_dingdan(
        self, dingdan_id: str, dingdan_data: ZhifuDingdanUpdate, updated_by: str
    ) -> ZhifuDingdanResponse:
        """更新支付订单"""
        zhifu_dingdan = (
            self.db.query(ZhifuDingdan)
            .filter(ZhifuDingdan.id == dingdan_id, ZhifuDingdan.is_deleted == "N")
            .first()
        )

        if not zhifu_dingdan:
            raise HTTPException(status_code=404, detail="支付订单不存在")

        # 记录原状态
        old_status = zhifu_dingdan.zhifu_zhuangtai

        # 更新字段
        update_data = dingdan_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(zhifu_dingdan, field, value)

        zhifu_dingdan.updated_by = updated_by
        zhifu_dingdan.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(zhifu_dingdan)

        # 如果支付状态发生变化，发布事件
        new_status = zhifu_dingdan.zhifu_zhuangtai
        if old_status != new_status:
            if new_status == "paid":
                publish(
                    EventNames.PAYMENT_SUCCESS,
                    {
                        "zhifu_dingdan_id": zhifu_dingdan.id,
                        "hetong_id": zhifu_dingdan.hetong_id,
                        "kehu_id": zhifu_dingdan.kehu_id,
                        "dingdan_jine": float(zhifu_dingdan.dingdan_jine),
                        "zhifu_shijian": zhifu_dingdan.zhifu_shijian.isoformat()
                        if zhifu_dingdan.zhifu_shijian
                        else None,
                        "updated_by": updated_by,
                    },
                )
            elif new_status == "failed":
                publish(
                    EventNames.PAYMENT_FAILED,
                    {
                        "zhifu_dingdan_id": zhifu_dingdan.id,
                        "hetong_id": zhifu_dingdan.hetong_id,
                        "kehu_id": zhifu_dingdan.kehu_id,
                        "updated_by": updated_by,
                    },
                )

        return ZhifuDingdanResponse.model_validate(zhifu_dingdan)

    def get_zhifu_dingdan_list(
        self, params: ZhifuDingdanListParams
    ) -> ZhifuDingdanListResponse:
        """获取支付订单列表"""
        query = self.db.query(ZhifuDingdan).filter(ZhifuDingdan.is_deleted == "N")

        # 搜索条件
        if params.search:
            search_pattern = f"%{params.search}%"
            query = query.filter(
                or_(
                    ZhifuDingdan.dingdan_bianhao.ilike(search_pattern),
                    ZhifuDingdan.dingdan_mingcheng.ilike(search_pattern),
                )
            )

        # 筛选条件
        if params.hetong_id:
            query = query.filter(ZhifuDingdan.hetong_id == params.hetong_id)

        if params.kehu_id:
            query = query.filter(ZhifuDingdan.kehu_id == params.kehu_id)

        if params.zhifu_leixing:
            query = query.filter(ZhifuDingdan.zhifu_leixing == params.zhifu_leixing)

        if params.zhifu_zhuangtai:
            query = query.filter(ZhifuDingdan.zhifu_zhuangtai == params.zhifu_zhuangtai)

        if params.start_date:
            query = query.filter(ZhifuDingdan.chuangjian_shijian >= params.start_date)

        if params.end_date:
            query = query.filter(ZhifuDingdan.chuangjian_shijian <= params.end_date)

        # 总数
        total = query.count()

        # 分页和排序
        items = (
            query.order_by(desc(ZhifuDingdan.chuangjian_shijian))
            .offset((params.page - 1) * params.size)
            .limit(params.size)
            .all()
        )

        return ZhifuDingdanListResponse(
            total=total,
            items=[ZhifuDingdanResponse.model_validate(item) for item in items],
            page=params.page,
            size=params.size,
        )

    def get_zhifu_dingdan_statistics(self) -> ZhifuDingdanStatistics:
        """获取支付订单统计信息"""
        status_counts = (
            self.db.query(
                func.count(ZhifuDingdan.id).label("total_count"),
                func.sum(
                    case((ZhifuDingdan.zhifu_zhuangtai == "pending", 1), else_=0)
                ).label("pending_count"),
                func.sum(
                    case((ZhifuDingdan.zhifu_zhuangtai == "paid", 1), else_=0)
                ).label("paid_count"),
                func.sum(
                    case((ZhifuDingdan.zhifu_zhuangtai == "failed", 1), else_=0)
                ).label("failed_count"),
            )
            .filter(ZhifuDingdan.is_deleted == "N")
            .first()
        )

        total_amount = self.db.query(func.sum(ZhifuDingdan.dingdan_jine)).filter(
            ZhifuDingdan.is_deleted == "N"
        ).scalar() or Decimal("0")

        paid_amount = self.db.query(func.sum(ZhifuDingdan.shifu_jine)).filter(
            ZhifuDingdan.is_deleted == "N", ZhifuDingdan.zhifu_zhuangtai == "paid"
        ).scalar() or Decimal("0")

        pending_amount = self.db.query(func.sum(ZhifuDingdan.yingfu_jine)).filter(
            ZhifuDingdan.is_deleted == "N", ZhifuDingdan.zhifu_zhuangtai == "pending"
        ).scalar() or Decimal("0")

        return ZhifuDingdanStatistics(
            total_count=status_counts.total_count or 0,
            pending_count=status_counts.pending_count or 0,
            paid_count=status_counts.paid_count or 0,
            failed_count=status_counts.failed_count or 0,
            total_amount=total_amount,
            paid_amount=paid_amount,
            pending_amount=pending_amount,
        )

    def _generate_dingdan_bianhao(self) -> str:
        """生成订单编号"""
        # 格式：ZF + YYYYMMDD + 4位随机数
        today = datetime.now().strftime("%Y%m%d")
        random_suffix = str(uuid.uuid4().int)[:4]
        return f"ZF{today}{random_suffix}"
