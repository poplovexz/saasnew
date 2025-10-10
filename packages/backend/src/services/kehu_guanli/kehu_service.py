"""
客户管理服务
"""
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException

from models.kehu_guanli import Kehu
from schemas.kehu_guanli.kehu_schemas import (
    KehuCreate, 
    KehuUpdate, 
    KehuResponse,
    KehuListResponse
)

logger = logging.getLogger(__name__)


class KehuService:
    """客户管理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_kehu(self, kehu_data: KehuCreate, created_by: str) -> KehuResponse:
        """创建客户"""
        # 验证统一社会信用代码唯一性
        existing_kehu = self.db.query(Kehu).filter(
            Kehu.tongyi_shehui_xinyong_daima == kehu_data.tongyi_shehui_xinyong_daima,
            Kehu.is_deleted == "N"
        ).first()
        
        if existing_kehu:
            raise HTTPException(status_code=400, detail="统一社会信用代码已存在")
        
        # 创建客户
        kehu = Kehu(
            **kehu_data.model_dump(),
            created_by=created_by
        )
        
        self.db.add(kehu)
        self.db.commit()
        self.db.refresh(kehu)
        
        return KehuResponse.model_validate(kehu)
    
    def get_kehu_by_id(self, kehu_id: str) -> Optional[KehuResponse]:
        """根据ID获取客户"""
        kehu = self.db.query(Kehu).filter(
            Kehu.id == kehu_id,
            Kehu.is_deleted == "N"
        ).first()
        
        if not kehu:
            return None
        
        return KehuResponse.model_validate(kehu)
    
    def get_kehu_list(
        self,
        page: int = 1,
        size: int = 100,
        search: Optional[str] = None,
        kehu_zhuangtai: Optional[str] = None
    ) -> KehuListResponse:
        """获取客户列表"""
        query = self.db.query(Kehu).filter(Kehu.is_deleted == "N")
        
        # 搜索条件
        if search:
            search_filter = or_(
                Kehu.gongsi_mingcheng.contains(search),
                Kehu.tongyi_shehui_xinyong_daima.contains(search),
                Kehu.faren_xingming.contains(search),
                Kehu.lianxi_dianhua.contains(search),
                Kehu.lianxi_youxiang.contains(search)
            )
            query = query.filter(search_filter)
        
        # 状态筛选
        if kehu_zhuangtai:
            query = query.filter(Kehu.kehu_zhuangtai == kehu_zhuangtai)
        
        # 总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * size
        kehu_list = query.offset(offset).limit(size).all()
        
        return KehuListResponse(
            total=total,
            items=[KehuResponse.model_validate(kehu) for kehu in kehu_list],
            page=page,
            size=size
        )
    
    def find_duplicate_kehu(
        self, 
        lianxi_dianhua: Optional[str] = None,
        tongyi_shehui_xinyong_daima: Optional[str] = None
    ) -> Optional[KehuResponse]:
        """查找重复客户（通过手机号或统一社会信用代码）"""
        if not lianxi_dianhua and not tongyi_shehui_xinyong_daima:
            return None
        
        duplicate_filters = []
        
        if lianxi_dianhua:
            duplicate_filters.append(Kehu.lianxi_dianhua == lianxi_dianhua)
        
        if tongyi_shehui_xinyong_daima:
            duplicate_filters.append(
                Kehu.tongyi_shehui_xinyong_daima == tongyi_shehui_xinyong_daima
            )
        
        kehu = self.db.query(Kehu).filter(
            or_(*duplicate_filters),
            Kehu.is_deleted == "N"
        ).first()
        
        if kehu:
            return KehuResponse.model_validate(kehu)
        
        return None
    
    def create_kehu_from_xiansuo(
        self, 
        xiansuo_id: str, 
        created_by: str
    ) -> KehuResponse:
        """从线索自动创建客户（含重复检测）"""
        from models.xiansuo_guanli.xiansuo import Xiansuo
        
        xiansuo = self.db.query(Xiansuo).filter(
            Xiansuo.id == xiansuo_id,
            Xiansuo.is_deleted == "N"
        ).first()
        
        if not xiansuo:
            raise HTTPException(status_code=404, detail="线索不存在")
        
        existing = self.find_duplicate_kehu(
            lianxi_dianhua=xiansuo.lianxi_dianhua,
            tongyi_shehui_xinyong_daima=None
        )
        
        if existing:
            logger.info(f"找到重复客户，复用: kehu_id={existing.id}, phone={xiansuo.lianxi_dianhua}")
            return existing
        
        kehu_data = KehuCreate(
            gongsi_mingcheng=xiansuo.gongsi_mingcheng,
            tongyi_shehui_xinyong_daima=None,
            faren_xingming=xiansuo.lianxi_ren,
            lianxi_dianhua=xiansuo.lianxi_dianhua,
            lianxi_youxiang=xiansuo.lianxi_youxiang,
            hangye_leixing=xiansuo.hangye_leixing,
            gongsi_guimo=xiansuo.gongsi_guimo,
            zhuce_dizhi=xiansuo.zhuce_dizhi,
            kehu_zhuangtai="active",
            kehu_laiyuan="xiansuo_zhuanhua",
            beizhu=f"由线索 {xiansuo.xiansuo_bianma} 自动转化生成"
        )
        
        return self.create_kehu(kehu_data, created_by)
    
    def update_kehu(self, kehu_id: str, kehu_data: KehuUpdate, updated_by: str) -> KehuResponse:
        """更新客户"""
        kehu = self.db.query(Kehu).filter(
            Kehu.id == kehu_id,
            Kehu.is_deleted == "N"
        ).first()
        
        if not kehu:
            raise HTTPException(status_code=404, detail="客户不存在")
        
        # 如果更新统一社会信用代码，验证唯一性
        if kehu_data.tongyi_shehui_xinyong_daima and kehu_data.tongyi_shehui_xinyong_daima != kehu.tongyi_shehui_xinyong_daima:
            existing_kehu = self.db.query(Kehu).filter(
                Kehu.tongyi_shehui_xinyong_daima == kehu_data.tongyi_shehui_xinyong_daima,
                Kehu.id != kehu_id,
                Kehu.is_deleted == "N"
            ).first()
            
            if existing_kehu:
                raise HTTPException(status_code=400, detail="统一社会信用代码已存在")
        
        # 更新字段
        update_data = kehu_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kehu, field, value)
        
        kehu.updated_by = updated_by
        
        self.db.commit()
        self.db.refresh(kehu)
        
        return KehuResponse.model_validate(kehu)
    
    def delete_kehu(self, kehu_id: str, deleted_by: str) -> bool:
        """删除客户（软删除）"""
        kehu = self.db.query(Kehu).filter(
            Kehu.id == kehu_id,
            Kehu.is_deleted == "N"
        ).first()
        
        if not kehu:
            raise HTTPException(status_code=404, detail="客户不存在")
        
        # 软删除
        kehu.is_deleted = "Y"
        kehu.updated_by = deleted_by
        
        self.db.commit()
        
        return True
    
    def update_kehu_status(self, kehu_id: str, new_status: str, updated_by: str) -> KehuResponse:
        """更新客户状态"""
        kehu = self.db.query(Kehu).filter(
            Kehu.id == kehu_id,
            Kehu.is_deleted == "N"
        ).first()
        
        if not kehu:
            raise HTTPException(status_code=404, detail="客户不存在")
        
        # 验证状态值
        allowed_statuses = ["active", "renewing", "terminated"]
        if new_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"无效的客户状态: {new_status}")
        
        kehu.kehu_zhuangtai = new_status
        kehu.updated_by = updated_by
        
        self.db.commit()
        self.db.refresh(kehu)
        
        return KehuResponse.model_validate(kehu)

    def get_kehu_statistics(self) -> dict:
        """获取客户统计信息"""
        from sqlalchemy import func

        # 总客户数
        total_customers = self.db.query(func.count(Kehu.id)).filter(
            Kehu.is_deleted == "N"
        ).scalar() or 0

        # 按状态统计
        status_stats = self.db.query(
            Kehu.kehu_zhuangtai,
            func.count(Kehu.id).label('count')
        ).filter(
            Kehu.is_deleted == "N"
        ).group_by(Kehu.kehu_zhuangtai).all()

        status_dict = {status: count for status, count in status_stats}

        # 本月新增客户
        from datetime import datetime, timedelta
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_new = self.db.query(func.count(Kehu.id)).filter(
            Kehu.is_deleted == "N",
            Kehu.created_at >= current_month_start
        ).scalar() or 0

        return {
            "total_customers": total_customers,
            "active_customers": status_dict.get("active", 0),
            "renewing_customers": status_dict.get("renewing", 0),
            "terminated_customers": status_dict.get("terminated", 0),
            "monthly_new_customers": monthly_new,
            "status_distribution": status_dict
        }

    def batch_update_status(self, kehu_ids: List[str], new_status: str, updated_by: str) -> dict:
        """批量更新客户状态"""
        # 验证状态值
        allowed_statuses = ["active", "renewing", "terminated"]
        if new_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail=f"无效的客户状态: {new_status}")

        # 查询要更新的客户
        kehu_list = self.db.query(Kehu).filter(
            Kehu.id.in_(kehu_ids),
            Kehu.is_deleted == "N"
        ).all()

        if not kehu_list:
            raise HTTPException(status_code=404, detail="未找到要更新的客户")

        # 批量更新
        updated_count = 0
        for kehu in kehu_list:
            kehu.kehu_zhuangtai = new_status
            kehu.updated_by = updated_by
            updated_count += 1

        self.db.commit()

        return {
            "updated_count": updated_count,
            "total_requested": len(kehu_ids),
            "new_status": new_status
        }

    def batch_delete(self, kehu_ids: List[str], deleted_by: str) -> dict:
        """批量删除客户（软删除）"""
        # 查询要删除的客户
        kehu_list = self.db.query(Kehu).filter(
            Kehu.id.in_(kehu_ids),
            Kehu.is_deleted == "N"
        ).all()

        if not kehu_list:
            raise HTTPException(status_code=404, detail="未找到要删除的客户")

        # 批量软删除
        deleted_count = 0
        for kehu in kehu_list:
            kehu.is_deleted = "Y"
            kehu.updated_by = deleted_by
            deleted_count += 1

        self.db.commit()

        return {
            "deleted_count": deleted_count,
            "total_requested": len(kehu_ids)
        }

    def search_customers_advanced(self, search_params: dict) -> KehuListResponse:
        """高级搜索客户"""
        query = self.db.query(Kehu).filter(Kehu.is_deleted == "N")

        # 公司名称搜索
        if search_params.get("gongsi_mingcheng"):
            query = query.filter(Kehu.gongsi_mingcheng.ilike(f"%{search_params['gongsi_mingcheng']}%"))

        # 统一社会信用代码搜索
        if search_params.get("tongyi_shehui_xinyong_daima"):
            query = query.filter(Kehu.tongyi_shehui_xinyong_daima.ilike(f"%{search_params['tongyi_shehui_xinyong_daima']}%"))

        # 法人姓名搜索
        if search_params.get("faren_xingming"):
            query = query.filter(Kehu.faren_xingming.ilike(f"%{search_params['faren_xingming']}%"))

        # 客户状态筛选
        if search_params.get("kehu_zhuangtai"):
            query = query.filter(Kehu.kehu_zhuangtai == search_params["kehu_zhuangtai"])

        # 服务开始日期范围
        if search_params.get("fuwu_kaishi_start"):
            query = query.filter(Kehu.fuwu_kaishi_riqi >= search_params["fuwu_kaishi_start"])

        if search_params.get("fuwu_kaishi_end"):
            query = query.filter(Kehu.fuwu_kaishi_riqi <= search_params["fuwu_kaishi_end"])

        # 创建日期范围
        if search_params.get("created_start"):
            query = query.filter(Kehu.created_at >= search_params["created_start"])

        if search_params.get("created_end"):
            query = query.filter(Kehu.created_at <= search_params["created_end"])

        # 分页
        page = search_params.get("page", 1)
        size = search_params.get("size", 20)

        total = query.count()
        kehu_list = query.offset((page - 1) * size).limit(size).all()

        return KehuListResponse(
            total=total,
            items=[KehuResponse.model_validate(kehu) for kehu in kehu_list],
            page=page,
            size=size
        )
