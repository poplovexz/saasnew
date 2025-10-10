"""
审核记录数据模式
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ShenheJiluBase(BaseModel):
    """审核记录基础模型"""
    liucheng_id: str = Field(..., description="审核流程ID")
    buzhou_bianhao: int = Field(..., ge=1, description="步骤编号")
    buzhou_mingcheng: Optional[str] = Field(None, description="步骤名称")
    shenhe_ren_id: str = Field(..., description="审核人ID")
    shenhe_jieguo: Optional[str] = Field(None, description="审核结果")
    shenhe_yijian: Optional[str] = Field(None, description="审核意见")
    fujian_lujing: Optional[str] = Field(None, description="附件文件路径")
    fujian_miaoshu: Optional[str] = Field(None, description="附件描述")
    qiwang_chuli_shijian: Optional[datetime] = Field(None, description="期望处理时间")
    beizhu: Optional[str] = Field(None, description="备注")


class ShenheJiluCreate(ShenheJiluBase):
    """创建审核记录模型"""
    pass


class ShenheJiluUpdate(BaseModel):
    """更新审核记录模型"""
    shenhe_jieguo: Optional[str] = Field(None, description="审核结果")
    shenhe_yijian: Optional[str] = Field(None, description="审核意见")
    shenhe_shijian: Optional[datetime] = Field(None, description="审核时间")
    fujian_lujing: Optional[str] = Field(None, description="附件文件路径")
    fujian_miaoshu: Optional[str] = Field(None, description="附件描述")
    jilu_zhuangtai: Optional[str] = Field(None, description="记录状态")
    beizhu: Optional[str] = Field(None, description="备注")


class ShenheJiluResponse(BaseModel):
    """审核记录响应模型"""
    id: str
    liucheng_id: str
    buzhou_bianhao: int
    buzhou_mingcheng: Optional[str]
    shenhe_ren_id: str
    shenhe_jieguo: Optional[str]
    shenhe_yijian: Optional[str]
    shenhe_shijian: Optional[datetime]
    fujian_lujing: Optional[str]
    fujian_miaoshu: Optional[str]
    jilu_zhuangtai: str
    qiwang_chuli_shijian: Optional[datetime]
    beizhu: Optional[str]
    biaodan_peizhi: Optional[Dict[str, Any]] = None
    zidingyi_shuju: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class ShenheJiluListParams(BaseModel):
    """审核记录列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")
    liucheng_id: Optional[str] = Field(None, description="流程ID筛选")
    shenhe_ren_id: Optional[str] = Field(None, description="审核人筛选")
    jilu_zhuangtai: Optional[str] = Field(None, description="记录状态筛选")
    sort_by: Optional[str] = Field(default="buzhou_bianhao", description="排序字段")
    sort_order: Optional[str] = Field(default="asc", description="排序方向")


class ShenheActionRequest(BaseModel):
    """审核操作请求模型"""
    shenhe_jieguo: str = Field(..., description="审核结果：approved、rejected")
    shenhe_yijian: Optional[str] = Field(None, description="审核意见")
    fujian_lujing: Optional[str] = Field(None, description="附件文件路径")
    fujian_miaoshu: Optional[str] = Field(None, description="附件描述")
    zidingyi_shuju: Optional[Dict[str, Any]] = Field(None, description="自定义表单数据")
