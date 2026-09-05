import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import RAZORPAY_KEY_ID
from app.database import get_db
from app.gemini_agent import run_agent_turn
from app.schemas import ChatOrder, ChatRequest, ChatResponse

router = APIRouter(tags=["agent"])


@router.post("/api/agent/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    session_id = req.session_id or str(uuid.uuid4())
    result = run_agent_turn(db, session_id, req.message)

    order = None
    if result["order"]:
        order = ChatOrder(
            order_id=result["order"]["order_id"],
            razorpay_order_id=result["order"]["razorpay_order_id"],
            razorpay_key_id=RAZORPAY_KEY_ID,
            amount_inr=result["order"]["amount_inr"],
            status=result["order"]["status"],
            product_name=result["order"]["product_name"],
        )

    return ChatResponse(session_id=session_id, reply=result["reply"], order=order, upsell=result.get("upsell"))
