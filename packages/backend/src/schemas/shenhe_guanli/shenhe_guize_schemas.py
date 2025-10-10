"""
审核规则配置数据模式
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ShenheGuizeBase(BaseModel):
    """审核规则基础模型"""
    guize_mingcheng: str = Field(..., min_length=1, max_length=200, description="规则名称")
    guize_leixing: str = Field(..., description="规则类型")
    chufa_tiaojian: Dict[str, Any] = Field(..., description="触发条件配置")
    shenhe_liucheng_peizhi: Dict[str, Any] = Field(
        ..., 
        description="""审核流程配置（JSON格式）示例:
{
  "steps": [
    {
      "step": 1,
      "name": "主管审核",
      "auditor_id": "user_uuid_here",
      "form_fields": [
        {
          "field_name": "审批意见",
          "field_type": "textarea",
          "required": true
        }
      ],
      "condition": "amount >= 10000"
    }
  ]
}
"""
    )
    shi_qiyong: str = Field(default="Y", description="是否启用")
    paixu: int = Field(default=0, description="排序号")
    guize_miaoshu: Optional[str] = Field(None, description="规则描述")


class ShenheGuizeCreate(ShenheGuizeBase):
    """创建审核规则模型"""
    pass


class ShenheGuizeUpdate(BaseModel):
    """更新审核规则模型"""
    guize_mingcheng: Optional[str] = Field(None, min_length=1, max_length=200, description="规则名称")
    guize_leixing: Optional[str] = Field(None, description="规则类型")
    chufa_tiaojian: Optional[Dict[str, Any]] = Field(None, description="触发条件配置")
    shenhe_liucheng_peizhi: Optional[Dict[str, Any]] = Field(None, description="审核流程配置")
    shi_qiyong: Optional[str] = Field(None, description="是否启用")
    paixu: Optional[int] = Field(None, description="排序号")
    guize_miaoshu: Optional[str] = Field(None, description="规则描述")


class ShenheGuizeResponse(BaseModel):
    """审核规则响应模型"""
    id: str
    guize_mingcheng: str
    guize_leixing: str
    chufa_tiaojian: Dict[str, Any]
    shenhe_liucheng_peizhi: Dict[str, Any]
    shi_qiyong: str
    paixu: int
    guize_miaoshu: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class ShenheGuizeListParams(BaseModel):
    """审核规则列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=100, description="每页数量")
    search: Optional[str] = Field(None, description="搜索关键词")
    guize_leixing: Optional[str] = Field(None, description="规则类型筛选")
    shi_qiyong: Optional[str] = Field(None, description="启用状态筛选")
    sort_by: Optional[str] = Field(default="paixu", description="排序字段")
    sort_order: Optional[str] = Field(default="asc", description="排序方向")
