"""Financial checks used before serialization, writes and migration installation."""


def validate_invoice(invoice):
    if invoice.status not in {"PENDING", "PAID", "CANCELLED"}:
        raise ValueError("Invalid invoice state")
    if type(invoice.amount_cents) is not int or not 0 < invoice.amount_cents <= 9223372036854775807:
        raise ValueError("Invoice amount must be positive integer kopecks")
    if (invoice.status == "PAID") != (invoice.paid_at is not None):
        raise ValueError("Invoice status and paid_at disagree")


def validate_payment(payment, invoice):
    validate_invoice(invoice)
    if payment.status not in {"CREATED", "SUCCEEDED", "FAILED"}:
        raise ValueError("Invalid payment state")
    if type(payment.amount_cents) is not int or payment.amount_cents != invoice.amount_cents:
        raise ValueError("Payment and invoice amounts disagree")
    if payment.user_id != invoice.user_id:
        raise ValueError("Payment and invoice owners disagree")
    if payment.status == "SUCCEEDED" and invoice.status != "PAID":
        raise ValueError("Successful payment requires a paid invoice")
    if payment.status == "CREATED" and invoice.status != "PENDING":
        raise ValueError("Active payment requires a pending invoice")
