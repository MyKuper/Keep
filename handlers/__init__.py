# handlers/__init__.py — собираем все роутеры маркетплейса в правильном порядке

from handlers.start import router as start_router
from handlers.admin import router as admin_router
from handlers.seller import router as seller_router
from handlers.buyer import router as buyer_router

# Порядок важен: start (роли/регистрация) -> admin -> seller (FSM-шаги раньше общих кнопок)
routers = [start_router, admin_router, seller_router, buyer_router]

__all__ = ["routers"]
