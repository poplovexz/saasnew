"""
客户表模型
"""
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship

from ..base import BaseModel


class Kehu(BaseModel):
    """客户表"""
    
    __tablename__ = "kehu"
    __table_args__ = {"comment": "客户表"}
    
    # 基本信息
    gongsi_mingcheng = Column(
        String(200),
        nullable=False,
        comment="公司名称"
    )
    
    tongyi_shehui_xinyong_daima = Column(
        String(18),
        unique=True,
        nullable=True,
        comment="统一社会信用代码 - 可选，客户后续可完善"
    )
    
    chengli_riqi = Column(
        DateTime,
        nullable=True,
        comment="成立日期"
    )
    
    zhuce_dizhi = Column(
        String(500),
        nullable=True,
        comment="注册地址"
    )
    
    # 法人信息
    faren_xingming = Column(
        String(50),
        nullable=False,
        comment="法人姓名"
    )
    
    faren_shenfenzheng = Column(
        String(18),
        nullable=True,
        comment="法人身份证号码"
    )
    
    faren_lianxi = Column(
        String(20),
        nullable=True,
        comment="法人联系方式"
    )
    
    # 联系信息
    lianxi_dianhua = Column(
        String(20),
        nullable=True,
        comment="联系电话"
    )
    
    lianxi_youxiang = Column(
        String(100),
        nullable=True,
        comment="联系邮箱"
    )
    
    lianxi_dizhi = Column(
        String(500),
        nullable=True,
        comment="联系地址"
    )
    
    # 营业执照信息
    yingye_zhizhao_lujing = Column(
        String(500),
        nullable=True,
        comment="营业执照文件路径"
    )
    
    yingye_zhizhao_youxiao_qi = Column(
        DateTime,
        nullable=True,
        comment="营业执照有效期"
    )
    
    # 状态信息
    kehu_zhuangtai = Column(
        String(20),
        default="active",
        nullable=False,
        comment="客户状态：active-活跃，renewing-续约中，terminated-已终止"
    )
    
    fuwu_kaishi_riqi = Column(
        DateTime,
        nullable=True,
        comment="服务开始日期"
    )
    
    fuwu_jieshu_riqi = Column(
        DateTime,
        nullable=True,
        comment="服务结束日期"
    )
    
    # 关联关系
    fuwu_jilu_list = relationship(
        "FuwuJilu",
        back_populates="kehu",
        cascade="all, delete-orphan"
    )

    fuwu_gongdan_list = relationship(
        "FuwuGongdan",
        back_populates="kehu",
        cascade="all, delete-orphan"
    )

    heguishixiang_peizhi_list = relationship(
        "KehuHeguishixiang",
        back_populates="kehu",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Kehu(gongsi_mingcheng='{self.gongsi_mingcheng}', kehu_zhuangtai='{self.kehu_zhuangtai}')>"
