"""
合同模板管理服务
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, asc, case, desc, func, or_
from sqlalchemy.orm import Session

from models.hetong_guanli import HetongMoban
from schemas.hetong_guanli.hetong_moban_schemas import (
    HetongMobanCreate,
    HetongMobanListResponse,
    HetongMobanResponse,
    HetongMobanUpdate,
)


class HetongMobanService:
    """合同模板管理服务类"""

    def __init__(self, db: Session):
        self.db = db

    def create_hetong_moban(
        self, moban_data: HetongMobanCreate, created_by: str
    ) -> HetongMobanResponse:
        """创建合同模板"""
        # 验证模板编码唯一性
        existing_moban = (
            self.db.query(HetongMoban)
            .filter(
                HetongMoban.moban_bianma == moban_data.moban_bianma,
                HetongMoban.is_deleted == "N",
            )
            .first()
        )

        if existing_moban:
            raise HTTPException(status_code=400, detail="模板编码已存在")

        # 如果设置为当前版本，需要将同类型的其他模板设为非当前版本
        if moban_data.shi_dangqian_banben == "Y":
            self.db.query(HetongMoban).filter(
                HetongMoban.hetong_leixing == moban_data.hetong_leixing,
                HetongMoban.shi_dangqian_banben == "Y",
                HetongMoban.is_deleted == "N",
            ).update({"shi_dangqian_banben": "N"})

        # 创建合同模板
        moban = HetongMoban(**moban_data.model_dump(), created_by=created_by)

        self.db.add(moban)
        self.db.commit()
        self.db.refresh(moban)

        return HetongMobanResponse.model_validate(moban)

    def get_hetong_moban_list(
        self,
        page: int = 1,
        size: int = 20,
        search: Optional[str] = None,
        hetong_leixing: Optional[str] = None,
        moban_zhuangtai: Optional[str] = None,
        moban_fenlei: Optional[str] = None,
        shi_dangqian_banben: Optional[str] = None,
    ) -> HetongMobanListResponse:
        """获取合同模板列表"""
        query = self.db.query(HetongMoban).filter(HetongMoban.is_deleted == "N")

        # 搜索条件
        if search:
            search_filter = or_(
                HetongMoban.moban_mingcheng.contains(search),
                HetongMoban.moban_bianma.contains(search),
                HetongMoban.beizhu.contains(search),
            )
            query = query.filter(search_filter)

        # 筛选条件
        if hetong_leixing:
            query = query.filter(HetongMoban.hetong_leixing == hetong_leixing)

        if moban_zhuangtai:
            query = query.filter(HetongMoban.moban_zhuangtai == moban_zhuangtai)

        if moban_fenlei:
            query = query.filter(HetongMoban.moban_fenlei == moban_fenlei)

        if shi_dangqian_banben:
            query = query.filter(HetongMoban.shi_dangqian_banben == shi_dangqian_banben)

        # 排序
        query = query.order_by(desc(HetongMoban.paixu), desc(HetongMoban.created_at))

        # 分页
        total = query.count()
        offset = (page - 1) * size
        items = query.offset(offset).limit(size).all()

        return HetongMobanListResponse(
            total=total,
            items=[HetongMobanResponse.model_validate(item) for item in items],
            page=page,
            size=size,
        )

    def get_hetong_moban_by_id(self, moban_id: str) -> HetongMobanResponse:
        """根据ID获取合同模板"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        return HetongMobanResponse.model_validate(moban)

    def update_hetong_moban(
        self, moban_id: str, moban_data: HetongMobanUpdate
    ) -> HetongMobanResponse:
        """更新合同模板"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        # 验证模板编码唯一性（如果要更新编码）
        if moban_data.moban_bianma and moban_data.moban_bianma != moban.moban_bianma:
            existing_moban = (
                self.db.query(HetongMoban)
                .filter(
                    HetongMoban.moban_bianma == moban_data.moban_bianma,
                    HetongMoban.id != moban_id,
                    HetongMoban.is_deleted == "N",
                )
                .first()
            )

            if existing_moban:
                raise HTTPException(status_code=400, detail="模板编码已存在")

        # 如果设置为当前版本，需要将同类型的其他模板设为非当前版本
        if moban_data.shi_dangqian_banben == "Y":
            hetong_leixing = moban_data.hetong_leixing or moban.hetong_leixing
            self.db.query(HetongMoban).filter(
                HetongMoban.hetong_leixing == hetong_leixing,
                HetongMoban.shi_dangqian_banben == "Y",
                HetongMoban.id != moban_id,
                HetongMoban.is_deleted == "N",
            ).update({"shi_dangqian_banben": "N"})

        # 更新字段
        update_data = moban_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(moban, field, value)

        self.db.commit()
        self.db.refresh(moban)

        return HetongMobanResponse.model_validate(moban)

    def delete_hetong_moban(self, moban_id: str) -> bool:
        """删除合同模板（软删除）"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        # 检查是否有关联的合同
        # TODO: 添加合同关联检查

        moban.is_deleted = "Y"
        self.db.commit()

        return True

    def preview_hetong_moban(
        self, moban_id: str, bianliang_zhis: Dict[str, Any]
    ) -> str:
        """预览合同模板（替换变量）"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        # 替换模板中的变量
        content = moban.moban_neirong

        # 使用正则表达式查找并替换变量占位符 {{变量名}}
        def replace_variable(match):
            var_name = match.group(1).strip()
            return str(bianliang_zhis.get(var_name, f"{{{{ {var_name} }}}}"))

        # 替换变量
        content = re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace_variable, content)

        return content

    def get_moban_bianliang(self, moban_id: str) -> Dict[str, Any]:
        """获取模板变量配置"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        if moban.bianliang_peizhi:
            try:
                return json.loads(moban.bianliang_peizhi)
            except json.JSONDecodeError:
                return {}

        return {}

    def update_moban_status(
        self, moban_id: str, new_status: str
    ) -> HetongMobanResponse:
        """更新模板状态"""
        moban = (
            self.db.query(HetongMoban)
            .filter(HetongMoban.id == moban_id, HetongMoban.is_deleted == "N")
            .first()
        )

        if not moban:
            raise HTTPException(status_code=404, detail="合同模板不存在")

        allowed_statuses = ["draft", "active", "archived"]
        if new_status not in allowed_statuses:
            raise HTTPException(
                status_code=400, detail=f"状态必须是以下之一: {', '.join(allowed_statuses)}"
            )

        moban.moban_zhuangtai = new_status
        self.db.commit()
        self.db.refresh(moban)

        return HetongMobanResponse.model_validate(moban)

    def get_hetong_moban_statistics(self) -> Dict[str, Any]:
        """获取合同模板统计信息"""
        status_counts = (
            self.db.query(
                func.count(HetongMoban.id).label("total_count"),
                func.sum(
                    case((HetongMoban.moban_zhuangtai == "active", 1), else_=0)
                ).label("active_count"),
                func.sum(
                    case((HetongMoban.moban_zhuangtai == "draft", 1), else_=0)
                ).label("draft_count"),
                func.sum(
                    case((HetongMoban.moban_zhuangtai == "archived", 1), else_=0)
                ).label("archived_count"),
                func.sum(
                    case((HetongMoban.hetong_leixing == "daili_jizhang", 1), else_=0)
                ).label("daili_jizhang_count"),
                func.sum(
                    case((HetongMoban.hetong_leixing == "zengzhi_fuwu", 1), else_=0)
                ).label("zengzhi_fuwu_count"),
                func.sum(
                    case((HetongMoban.hetong_leixing == "zixun_fuwu", 1), else_=0)
                ).label("zixun_fuwu_count"),
            )
            .filter(HetongMoban.is_deleted == "N")
            .first()
        )

        return {
            "total_count": status_counts.total_count or 0,
            "active_count": status_counts.active_count or 0,
            "draft_count": status_counts.draft_count or 0,
            "archived_count": status_counts.archived_count or 0,
            "type_statistics": {
                "daili_jizhang": status_counts.daili_jizhang_count or 0,
                "zengzhi_fuwu": status_counts.zengzhi_fuwu_count or 0,
                "zixun_fuwu": status_counts.zixun_fuwu_count or 0,
            },
        }
