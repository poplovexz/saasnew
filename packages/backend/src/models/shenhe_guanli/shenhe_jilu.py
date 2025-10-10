"""
审核记录模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from ..base import BaseModel


class ShenheJilu(BaseModel):
    """审核记录表"""
    
    __tablename__ = "shenhe_jilu"
    __table_args__ = {"comment": "审核记录表"}
    
    # 流程关联
    liucheng_id = Column(
        String(36),
        ForeignKey("shenhe_liucheng.id"),
        nullable=False,
        comment="审核流程ID"
    )
    
    # 步骤信息
    buzhou_bianhao = Column(
        Integer,
        nullable=False,
        comment="步骤编号"
    )
    
    buzhou_mingcheng = Column(
        String(200),
        nullable=True,
        comment="步骤名称"
    )
    
    # 审核人信息
    shenhe_ren_id = Column(
        String(36),
        nullable=False,
        comment="审核人ID"
    )
    
    # 审核结果
    shenhe_jieguo = Column(
        String(20),
        nullable=True,
        comment="审核结果：tongguo(通过)、jujue(拒绝)、zhuanfa(转发)、daichuli(待处理)"
    )
    
    shenhe_yijian = Column(
        Text,
        nullable=True,
        comment="审核意见"
    )
    
    shenhe_shijian = Column(
        DateTime,
        nullable=True,
        comment="审核时间"
    )
    
    # 附件信息
    fujian_lujing = Column(
        String(500),
        nullable=True,
        comment="附件文件路径"
    )
    
    fujian_miaoshu = Column(
        String(200),
        nullable=True,
        comment="附件描述"
    )
    
    # 状态信息
    jilu_zhuangtai = Column(
        String(20),
        default="daichuli",
        nullable=False,
        comment="记录状态：daichuli(待处理)、yichuli(已处理)、yitiaoguo(已跳过)"
    )
    
    # 处理时限
    qiwang_chuli_shijian = Column(
        DateTime,
        nullable=True,
        comment="期望处理时间"
    )
    
    # 备注
    beizhu = Column(
        Text,
        nullable=True,
        comment="备注"
    )
    
    biaodan_peizhi = Column(
        Text,
        nullable=True,
        comment="表单字段配置（JSON格式）- 从审核规则继承"
    )
    
    zidingyi_shuju = Column(
        Text,
        nullable=True,
        comment="自定义表单数据（JSON格式）- 审核时提交"
    )
    
    # 关联关系
    shenhe_liucheng = relationship(
        "ShenheLiucheng",
        back_populates="shenhe_jilu_list"
    )
    
    def __repr__(self) -> str:
        return f"<ShenheJilu(liucheng_id='{self.liucheng_id}', buzhou_bianhao={self.buzhou_bianhao})>"
