from datetime import datetime, timezone
import json
import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_cashier_or_above, require_staff
from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment, ProcessedWebhookEvent
from app.models.table import RestaurantTable
from app.schemas.payment import (
    PaymentConfigResponse,
    PaymentOrderCreateRequest,
    PaymentOrderCreateResponse,
    PaymentPublicStatusResponse,
    PaymentStaffResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from app.services.razorpay_service import (
    create_provider_order,
    is_placeholder_credentials,
    verify_payment_signature,
    verify_webhook_signature,
)

router = APIRouter(prefix="/api", tags=["Payments"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Public Configuration & Guest Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/public/payments/config", response_model=PaymentConfigResponse)
def get_public_payment_config():
    """Return public checkout configuration required by the frontend Razorpay modal.

    The `razorpay_configured` flag tells the frontend whether real test credentials
    have been supplied. When False, the frontend should show a 'payment not available'
    message instead of attempting to open Razorpay Checkout.
    """
    configured = not is_placeholder_credentials()
    clean_key_id = (settings.RAZORPAY_KEY_ID or "").strip().strip("\"'")
    return PaymentConfigResponse(
        key_id=clean_key_id,
        currency=settings.RAZORPAY_CURRENCY,
        razorpay_configured=configured,
    )


@router.post("/public/payments/create-order", response_model=PaymentOrderCreateResponse)
def create_guest_payment_order(
    payload: PaymentOrderCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Razorpay payment order for a customer dine-in QR or takeaway order.
    Derives authoritative amount and currency strictly from the database record.
    """
    # 0. Validate provider configuration upfront
    if is_placeholder_credentials():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Razorpay payment gateway is not configured with valid test credentials. "
                "Please configure real RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env "
                "or pay cash at the counter."
            ),
        )

    # 1. Fetch order
    order = db.query(Order).filter(Order.order_number == payload.order_number).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{payload.order_number}' not found.",
        )

    # 2. Scope verification: if dine-in, verify active table token
    if order.table_id is not None:
        if not payload.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="QR token is required to access dine-in order payment.",
            )
        table = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if not table or not table.qr_token or table.qr_token != payload.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: The provided QR token does not have access to this order.",
            )

    # 3. Check payment eligibility
    if order.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order '{order.order_number}' has already been paid.",
        )

    if order.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot initiate payment for order in '{order.status}' status.",
        )

    if order.total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order total must be greater than zero to initiate payment.",
        )

    # 4. Derive authoritative amount in paise
    amount_paise = int(order.total * 100)
    currency = settings.RAZORPAY_CURRENCY

    # 5. Check for active existing payment record with status 'created' to avoid duplicates
    existing_payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id, Payment.status == "created")
        .order_by(Payment.created_at.desc())
        .first()
    )

    clean_key_id = (settings.RAZORPAY_KEY_ID or "").strip().strip("\"'")

    if (
        existing_payment
        and existing_payment.provider_order_id
        and not existing_payment.provider_order_id.startswith("order_mock_")
        and existing_payment.amount_paise == amount_paise
    ):
        return PaymentOrderCreateResponse(
            razorpay_order_id=existing_payment.provider_order_id,
            amount_paise=existing_payment.amount_paise,
            amount=existing_payment.amount,
            currency=existing_payment.currency,
            key_id=clean_key_id,
            order_number=order.order_number,
            payment_reference=existing_payment.payment_reference,
        )

    # 6. Create provider order (raises RuntimeError for missing credentials or API failure)
    try:
        provider_res = create_provider_order(
            amount_paise=amount_paise,
            currency=currency,
            receipt=order.order_number,
            notes={
                "order_id": order.id,
                "order_number": order.order_number,
                "table_id": order.table_id,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # 7. Record durable payment record
    ref = f"pay_ref_{secrets.token_hex(12)}"
    new_payment = Payment(
        order_id=order.id,
        payment_reference=ref,
        provider="razorpay",
        provider_order_id=provider_res["id"],
        amount=order.total,
        amount_paise=amount_paise,
        currency=currency,
        status="created",
        idempotency_key=payload.idempotency_key,
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    return PaymentOrderCreateResponse(
        razorpay_order_id=provider_res["id"],
        amount_paise=amount_paise,
        amount=order.total,
        currency=currency,
        key_id=clean_key_id,
        order_number=order.order_number,
        payment_reference=ref,
    )


@router.post("/public/payments/verify", response_model=PaymentVerifyResponse)
def verify_guest_payment(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify payment signature returned by the frontend Razorpay modal.
    Only marks the order as paid upon verified HMAC SHA-256 signature confirmation.
    """
    # 1. Fetch order
    order = db.query(Order).filter(Order.order_number == payload.order_number).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{payload.order_number}' not found.",
        )

    # 2. Scope verification: if dine-in, check table QR token
    if order.table_id is not None:
        if not payload.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="QR token is required to verify dine-in order payment.",
            )
        table = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if not table or not table.qr_token or table.qr_token != payload.qr_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Invalid table token for this order.",
            )

    # 3. Locate matching payment record
    payment = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id,
            Payment.provider_order_id == payload.razorpay_order_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No payment record matching Razorpay order '{payload.razorpay_order_id}'.",
        )

    # Idempotency check: if already captured, return success immediately
    if payment.status == "captured" and order.payment_status == "paid":
        return PaymentVerifyResponse(
            success=True,
            payment_status="paid",
            payment_reference=payment.payment_reference,
            order_number=order.order_number,
            message="Payment has already been confirmed and captured.",
        )

    # 4. Verify signature using official Razorpay HMAC SHA-256
    is_valid = verify_payment_signature(
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )

    if not is_valid:
        payment.status = "failed"
        payment.error_code = "BAD_SIGNATURE"
        payment.error_description = "HMAC SHA-256 signature verification failed."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed. The transaction could not be validated.",
        )

    # 5. Mark payment as captured & order as paid
    now = datetime.now(timezone.utc)
    payment.status = "captured"
    payment.provider_payment_id = payload.razorpay_payment_id
    payment.provider_signature = payload.razorpay_signature
    payment.verified_at = now

    order.payment_status = "paid"
    order.payment_method = "razorpay"

    db.commit()
    db.refresh(payment)
    db.refresh(order)

    return PaymentVerifyResponse(
        success=True,
        payment_status="paid",
        payment_reference=payment.payment_reference,
        order_number=order.order_number,
        message="Payment successfully verified and captured.",
    )


@router.get("/public/orders/{order_number}/payment", response_model=PaymentPublicStatusResponse)
def get_guest_order_payment_status(
    order_number: str,
    qr_token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Check payment status of an order via public table session."""
    order = db.query(Order).filter(Order.order_number == order_number).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.table_id is not None:
        if not qr_token:
            raise HTTPException(status_code=403, detail="QR token required.")
        table = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
        if not table or table.qr_token != qr_token:
            raise HTTPException(status_code=403, detail="Forbidden.")

    latest_payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    return PaymentPublicStatusResponse(
        order_number=order.order_number,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        amount=order.total,
        currency=settings.RAZORPAY_CURRENCY,
        payment_reference=latest_payment.payment_reference if latest_payment else None,
        verified_at=latest_payment.verified_at if latest_payment else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Webhook Ingestion (Signature Verification & Idempotency)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/payments/webhook")
@router.post("/public/payments/webhook")
async def process_razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
):
    """
    Ingest and process official Razorpay webhook events.
    Verifies the HMAC SHA-256 signature against the raw binary request body.
    Guarantees idempotency via durable processed_webhook_events records.
    """
    raw_body = await request.body()

    if not x_razorpay_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Razorpay-Signature header.",
        )

    # 1. Verify webhook signature
    is_valid = verify_webhook_signature(raw_body, x_razorpay_signature)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )

    # 2. Parse JSON payload
    try:
        event_payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event_id = event_payload.get("id")
    event_type = event_payload.get("event")

    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Malformed event data.")

    # 3. Idempotency Check: skip already processed events
    existing_event = (
        db.query(ProcessedWebhookEvent)
        .filter(ProcessedWebhookEvent.event_id == event_id)
        .first()
    )
    if existing_event:
        return {"status": "already_processed", "event_id": event_id}

    # 4. Handle specific event types
    now = datetime.now(timezone.utc)
    entity_id = None

    if event_type in ("payment.captured", "order.paid"):
        payment_entity = (
            event_payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        entity_id = payment_entity.get("id")
        provider_order_id = payment_entity.get("order_id")

        if provider_order_id:
            payment = (
                db.query(Payment)
                .filter(Payment.provider_order_id == provider_order_id)
                .first()
            )
            if payment:
                payment.status = "captured"
                if entity_id:
                    payment.provider_payment_id = entity_id
                payment.verified_at = now
                payment.method = payment_entity.get("method")
                payment.raw_response = json.dumps(payment_entity)

                # Update associated café order
                payment.order.payment_status = "paid"
                payment.order.payment_method = "razorpay"

    elif event_type == "payment.failed":
        payment_entity = (
            event_payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )
        entity_id = payment_entity.get("id")
        provider_order_id = payment_entity.get("order_id")

        if provider_order_id:
            payment = (
                db.query(Payment)
                .filter(Payment.provider_order_id == provider_order_id)
                .first()
            )
            # Safeguard: Never downgrade a verified captured payment to failed!
            if payment and payment.status != "captured":
                payment.status = "failed"
                payment.error_code = payment_entity.get("error_code")
                payment.error_description = payment_entity.get("error_description")
                payment.raw_response = json.dumps(payment_entity)

    # 5. Record processed event to prevent re-execution
    processed = ProcessedWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        entity_id=entity_id,
        processed_at=now,
    )
    db.add(processed)
    db.commit()

    return {"status": "processed", "event_id": event_id}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Staff POS Billing & Audit Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders/{order_id}/payments", response_model=List[PaymentStaffResponse])
def get_order_payments_staff(
    order_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_staff),
):
    """Retrieve full payment audit history for an order (Staff authorized)."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    payments = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    return payments


@router.post("/orders/{order_id}/settle-cash")
def settle_order_cash_staff(
    order_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_cashier_or_above),
):
    """
    Settle an order with cash at the counter/POS terminal.
    Staff-authorized only (Cashier or Manager).
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order '{order.order_number}' is already paid via {order.payment_method or 'unknown'}.",
        )

    order.payment_status = "paid"
    order.payment_method = "cash"

    # Also record internal cash Payment record for accounting consistency
    ref = f"pay_cash_{secrets.token_hex(8)}"
    cash_payment = Payment(
        order_id=order.id,
        payment_reference=ref,
        provider="cash",
        amount=order.total,
        amount_paise=int(order.total * 100),
        currency=settings.RAZORPAY_CURRENCY,
        status="captured",
        method="cash",
        verified_at=datetime.now(timezone.utc),
    )
    db.add(cash_payment)
    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "order_number": order.order_number,
        "payment_status": "paid",
        "payment_method": "cash",
        "payment_reference": ref,
    }
