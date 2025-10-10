"""
报价相关事件处理器
处理报价确认、拒绝等事件的业务逻辑
"""
import logging
from typing import Dict, Any
from datetime import datetime

from core.events import subscribe, EventNames
from core.database import SessionLocal
from models.xiansuo_guanli.xiansuo import Xiansuo
from models.xiansuo_guanli.xiansuo_baojia import XiansuoBaojia

logger = logging.getLogger(__name__)


def handle_baojia_confirmed(payload: Dict[str, Any]) -> None:
    """处理报价确认事件 - 自动创建客户并触发合同生成
    
    Args:
        payload: 事件数据，包含 baojia_id, xiansuo_id, queren_ren_id 等
    """
    try:
        baojia_id = payload.get("baojia_id")
        xiansuo_id = payload.get("xiansuo_id")
        queren_ren_id = payload.get("queren_ren_id")
        
        if not all([baojia_id, xiansuo_id]):
            logger.error(f"报价确认事件缺少必要参数: {payload}")
            return
        
        logger.info(f"处理报价确认事件: 报价ID={baojia_id}, 线索ID={xiansuo_id}, 确认人={queren_ren_id}")
        
        db = SessionLocal()
        try:
            xiansuo = db.query(Xiansuo).filter(Xiansuo.id == xiansuo_id).first()
            if not xiansuo:
                logger.warning(f"未找到线索: {xiansuo_id}")
                return
            
            if xiansuo.dangqian_zhuangtai not in ["won", "lost"]:
                xiansuo.dangqian_zhuangtai = "quoted"
                logger.info(f"线索状态已更新为'quoted': {xiansuo_id}")
            
            kehu_id = xiansuo.kehu_id
            if not kehu_id:
                from services.kehu_guanli.kehu_service import KehuService
                
                kehu_service = KehuService(db)
                
                try:
                    kehu_response = kehu_service.create_kehu_from_xiansuo(
                        xiansuo_id=xiansuo_id,
                        created_by=queren_ren_id or "system"
                    )
                    kehu_id = kehu_response.id
                    
                    xiansuo.kehu_id = kehu_id
                    xiansuo.shi_zhuanhua = "Y"
                    xiansuo.zhuanhua_shijian = datetime.now()
                    
                    logger.info(f"客户创建成功: kehu_id={kehu_id}, xiansuo_id={xiansuo_id}")
                    
                except Exception as customer_error:
                    logger.error(f"创建客户失败: {customer_error}", exc_info=True)
                    _log_baojia_business_event(
                        db, baojia_id, "customer_creation_failed",
                        f"客户创建失败: {str(customer_error)}",
                        queren_ren_id
                    )
                    db.rollback()
                    return
            else:
                logger.info(f"线索已关联客户: kehu_id={kehu_id}")
            
            from core.events import publish
            hetong_payload = {
                "baojia_id": baojia_id,
                "xiansuo_id": xiansuo_id,
                "kehu_id": kehu_id,
                "queren_ren_id": queren_ren_id,
                "trigger_time": datetime.now().isoformat(),
                "trigger_reason": "baojia_confirmed"
            }
            
            publish(EventNames.HETONG_DRAFT_TRIGGERED, hetong_payload)
            logger.info(f"已触发合同草稿生成事件")
            
            _log_baojia_business_event(
                db, baojia_id, "confirmed",
                f"报价确认成功，客户ID: {kehu_id}",
                queren_ren_id
            )
            
            db.commit()
            logger.info(f"报价确认事件处理完成: baojia_id={baojia_id}, kehu_id={kehu_id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"处理报价确认事件时发生数据库错误: {e}", exc_info=True)
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理报价确认事件失败: {e}", exc_info=True)
        raise


def handle_baojia_rejected(payload: Dict[str, Any]) -> None:
    """处理报价拒绝事件
    
    Args:
        payload: 事件数据，包含 baojia_id, xiansuo_id, queren_ren_id 等
    """
    try:
        baojia_id = payload.get("baojia_id")
        xiansuo_id = payload.get("xiansuo_id")
        queren_ren_id = payload.get("queren_ren_id")
        reject_reason = payload.get("reject_reason", "客户拒绝报价")
        
        if not all([baojia_id, xiansuo_id]):
            logger.error(f"报价拒绝事件缺少必要参数: {payload}")
            return
        
        logger.info(f"处理报价拒绝事件: 报价ID={baojia_id}, 线索ID={xiansuo_id}, 拒绝原因={reject_reason}")
        
        db = SessionLocal()
        try:
            # 1. 线索状态保持不变或根据业务规则调整
            # 注意：报价被拒绝不一定意味着线索失效，可能需要重新报价
            xiansuo = db.query(Xiansuo).filter(Xiansuo.id == xiansuo_id).first()
            if xiansuo:
                # 可以根据业务需求决定是否更新线索状态
                # 这里暂时不更新状态，保持线索继续跟进的可能性
                logger.info(f"报价被拒绝，线索状态保持不变: {xiansuo_id} -> {xiansuo.dangqian_zhuangtai}")
            
            # 2. 记录业务日志
            _log_baojia_business_event(
                db, baojia_id, "rejected", 
                f"报价被拒绝，原因: {reject_reason}", 
                queren_ren_id
            )
            
            db.commit()
            logger.info(f"报价拒绝事件处理完成: {baojia_id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"处理报价拒绝事件时发生数据库错误: {e}")
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理报价拒绝事件失败: {e}")
        raise


def handle_hetong_draft_triggered(payload: Dict[str, Any]) -> None:
    """处理合同草稿触发事件 - 验证客户ID并生成合同
    
    Args:
        payload: 事件数据，包含 baojia_id, xiansuo_id, kehu_id 等
    """
    try:
        baojia_id = payload.get("baojia_id")
        xiansuo_id = payload.get("xiansuo_id")
        kehu_id = payload.get("kehu_id")
        trigger_reason = payload.get("trigger_reason", "unknown")
        
        logger.info(f"处理合同草稿触发事件: 报价ID={baojia_id}, 线索ID={xiansuo_id}, 客户ID={kehu_id}, 触发原因={trigger_reason}")
        
        if not kehu_id:
            logger.error(f"缺少客户ID，无法生成合同: baojia_id={baojia_id}")
            return
        
        db = SessionLocal()
        try:
            baojia = db.query(XiansuoBaojia).filter(XiansuoBaojia.id == baojia_id).first()
            if not baojia:
                logger.error(f"未找到报价信息: {baojia_id}")
                return
            
            try:
                from services.hetong_guanli.hetong_service import HetongService
                hetong_service = HetongService(db)

                hetong_response = hetong_service.create_hetong_from_baojia(
                    baojia_id=baojia_id,
                    created_by=payload.get("queren_ren_id", "system")
                )

                logger.info(f"合同自动生成成功: 合同ID={hetong_response.id}, 合同编号={hetong_response.hetong_bianhao}")

                _log_baojia_business_event(
                    db, baojia_id, "contract_generated",
                    f"合同自动生成成功，合同编号: {hetong_response.hetong_bianhao}",
                    payload.get("queren_ren_id")
                )

            except Exception as contract_error:
                logger.error(f"合同自动生成失败: {contract_error}", exc_info=True)

                _log_baojia_business_event(
                    db, baojia_id, "contract_generation_failed",
                    f"合同自动生成失败: {str(contract_error)}",
                    payload.get("queren_ren_id")
                )
            
            db.commit()
            logger.info(f"合同草稿触发事件处理完成: {baojia_id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"处理合同草稿触发事件时发生数据库错误: {e}", exc_info=True)
            raise
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理合同草稿触发事件失败: {e}", exc_info=True)
        raise


def _log_baojia_business_event(db, baojia_id: str, event_type: str, description: str, operator_id: str = None) -> None:
    """记录报价业务事件日志
    
    Args:
        db: 数据库会话
        baojia_id: 报价ID
        event_type: 事件类型
        description: 事件描述
        operator_id: 操作人ID
    """
    try:
        # 这里可以记录到专门的业务日志表
        # 暂时使用应用日志记录
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "baojia_id": baojia_id,
            "event_type": event_type,
            "description": description,
            "operator_id": operator_id
        }
        
        logger.info(f"业务事件日志: {log_entry}")
        
        # 在未来可以扩展为写入专门的业务日志表
        # business_log = BusinessEventLog(**log_entry)
        # db.add(business_log)
        
    except Exception as e:
        logger.error(f"记录业务事件日志失败: {e}")


# 注册事件处理器
def register_baojia_event_handlers():
    """注册报价相关事件处理器"""
    subscribe(EventNames.BAOJIA_CONFIRMED, handle_baojia_confirmed)
    subscribe(EventNames.BAOJIA_REJECTED, handle_baojia_rejected)
    subscribe(EventNames.HETONG_DRAFT_TRIGGERED, handle_hetong_draft_triggered)
    
    logger.info("报价事件处理器注册完成")


# 自动注册（当模块被导入时）
register_baojia_event_handlers()
