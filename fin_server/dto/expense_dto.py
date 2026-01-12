"""Expense DTO for managing expense records.

This DTO handles the full expense lifecycle including:
- Categorization (using the hierarchical expense catalog)
- Amount and currency
- Payment tracking
- Approval workflow
- Metadata and attachments
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from fin_server.utils.time_utils import get_time_date_dt


# Expense statuses
class ExpenseStatus:
    DRAFT = 'draft'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    PAID = 'paid'
    CANCELLED = 'cancelled'
    INITIATED = 'initiated'
    SUCCESS = 'success'
    FAILED = 'failed'

    @classmethod
    def all(cls) -> List[str]:
        return [cls.DRAFT, cls.PENDING, cls.APPROVED, cls.REJECTED,
                cls.PAID, cls.CANCELLED, cls.INITIATED, cls.SUCCESS, cls.FAILED]


# Expense actions
class ExpenseAction:
    BUY = 'buy'
    SELL = 'sell'
    PAY = 'pay'
    RECEIVE = 'receive'
    TRANSFER = 'transfer'
    REFUND = 'refund'
    ADJUSTMENT = 'adjustment'

    @classmethod
    def all(cls) -> List[str]:
        return [cls.BUY, cls.SELL, cls.PAY, cls.RECEIVE,
                cls.TRANSFER, cls.REFUND, cls.ADJUSTMENT]


class ExpenseDTO:
    """Data Transfer Object for Expenses."""

    def __init__(
        self,
        expense_id: Optional[str] = None,
        account_key: Optional[str] = None,
        # Category fields (hierarchical)
        category: Optional[str] = None,          # Top-level: Infrastructure, Operational, etc.
        subcategory: Optional[str] = None,       # Second-level: Utilities, Maintenance, etc.
        detail: Optional[str] = None,            # Third-level: Electricity, Water, etc.
        category_path: Optional[str] = None,     # Full path: "Operational/Utilities/Electricity"
        # Financial fields
        amount: Optional[float] = None,
        currency: str = 'INR',
        tax_amount: Optional[float] = None,
        tax_rate: Optional[float] = None,
        gst: Optional[float] = None,
        total_amount: Optional[float] = None,    # amount + tax
        # Action and type
        action: str = 'pay',                     # buy, sell, pay, receive, etc.
        expense_type: Optional[str] = None,      # fish, feed, equipment, etc.
        # Payment info
        payment_method: Optional[str] = None,
        payment_status: Optional[str] = None,
        payment_date: Optional[str] = None,
        payment_reference: Optional[str] = None,
        # Vendor/Recipient
        vendor: Optional[str] = None,
        vendor_id: Optional[str] = None,
        recipient: Optional[str] = None,
        # Invoice/Receipt
        invoice_number: Optional[str] = None,
        receipt_number: Optional[str] = None,
        invoice_date: Optional[str] = None,
        due_date: Optional[str] = None,
        # Linkages
        pond_id: Optional[str] = None,
        species: Optional[str] = None,
        event_id: Optional[str] = None,
        sampling_id: Optional[str] = None,
        stock_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        # Workflow
        status: str = ExpenseStatus.DRAFT,
        submitted_by: Optional[str] = None,
        submitted_at: Optional[str] = None,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        rejected_by: Optional[str] = None,
        rejected_at: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        # Audit
        recorded_by: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        # Additional
        notes: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # Recurring
        is_recurring: bool = False,
        recurring_frequency: Optional[str] = None,  # daily, weekly, monthly, yearly
        recurring_end_date: Optional[str] = None,
    ):
        self.expense_id = expense_id
        self.account_key = account_key

        # Category
        self.category = category
        self.subcategory = subcategory
        self.detail = detail
        self.category_path = category_path or self._build_category_path()

        # Financial
        self.amount = float(amount) if amount is not None else None
        self.currency = currency
        self.tax_amount = float(tax_amount) if tax_amount is not None else None
        self.tax_rate = float(tax_rate) if tax_rate is not None else None
        self.gst = float(gst) if gst is not None else None
        self.total_amount = float(total_amount) if total_amount is not None else self._calculate_total()

        # Action/Type
        self.action = action
        self.expense_type = expense_type

        # Payment
        self.payment_method = payment_method
        self.payment_status = payment_status
        self.payment_date = payment_date
        self.payment_reference = payment_reference

        # Vendor
        self.vendor = vendor
        self.vendor_id = vendor_id
        self.recipient = recipient

        # Invoice
        self.invoice_number = invoice_number
        self.receipt_number = receipt_number
        self.invoice_date = invoice_date
        self.due_date = due_date

        # Links
        self.pond_id = pond_id
        self.species = species
        self.event_id = event_id
        self.sampling_id = sampling_id
        self.stock_id = stock_id
        self.transaction_id = transaction_id

        # Workflow
        self.status = status
        self.submitted_by = submitted_by
        self.submitted_at = submitted_at
        self.approved_by = approved_by
        self.approved_at = approved_at
        self.rejected_by = rejected_by
        self.rejected_at = rejected_at
        self.rejection_reason = rejection_reason

        # Audit
        self.recorded_by = recorded_by
        self.created_at = created_at or get_time_date_dt(include_time=True).isoformat()
        self.updated_at = updated_at

        # Additional
        self.notes = notes
        self.description = description
        self.tags = tags or []
        self.attachments = attachments or []
        self.metadata = metadata or {}

        # Recurring
        self.is_recurring = is_recurring
        self.recurring_frequency = recurring_frequency
        self.recurring_end_date = recurring_end_date

    def _build_category_path(self) -> Optional[str]:
        """Build the category path from individual components."""
        parts = [p for p in [self.category, self.subcategory, self.detail] if p]
        return '/'.join(parts) if parts else None

    def _calculate_total(self) -> Optional[float]:
        """Calculate total amount including tax."""
        if self.amount is None:
            return None
        total = self.amount
        if self.tax_amount:
            total += self.tax_amount
        elif self.gst:
            total += self.gst
        return total

    @classmethod
    def from_request(cls, payload: Dict[str, Any]) -> 'ExpenseDTO':
        """Create ExpenseDTO from API request payload."""
        # Handle various field name conventions
        return cls(
            expense_id=payload.get('expense_id') or payload.get('expenseId') or payload.get('id'),
            account_key=payload.get('account_key') or payload.get('accountKey'),
            # Category
            category=payload.get('category'),
            subcategory=payload.get('subcategory') or payload.get('sub_category'),
            detail=payload.get('detail') or payload.get('category_detail'),
            category_path=payload.get('category_path') or payload.get('categoryPath'),
            # Financial
            amount=payload.get('amount'),
            currency=payload.get('currency') or 'INR',
            tax_amount=payload.get('tax_amount') or payload.get('taxAmount'),
            tax_rate=payload.get('tax_rate') or payload.get('taxRate'),
            gst=payload.get('gst'),
            total_amount=payload.get('total_amount') or payload.get('totalAmount'),
            # Action/Type
            action=payload.get('action') or 'pay',
            expense_type=payload.get('type') or payload.get('expense_type') or payload.get('expenseType'),
            # Payment
            payment_method=payload.get('payment_method') or payload.get('paymentMethod'),
            payment_status=payload.get('payment_status') or payload.get('paymentStatus'),
            payment_date=payload.get('payment_date') or payload.get('paymentDate'),
            payment_reference=payload.get('payment_reference') or payload.get('paymentReference'),
            # Vendor
            vendor=payload.get('vendor'),
            vendor_id=payload.get('vendor_id') or payload.get('vendorId'),
            recipient=payload.get('recipient'),
            # Invoice
            invoice_number=payload.get('invoice_number') or payload.get('invoiceNumber') or payload.get('invoice_no'),
            receipt_number=payload.get('receipt_number') or payload.get('receiptNumber'),
            invoice_date=payload.get('invoice_date') or payload.get('invoiceDate'),
            due_date=payload.get('due_date') or payload.get('dueDate'),
            # Links
            pond_id=payload.get('pond_id') or payload.get('pondId'),
            species=payload.get('species'),
            event_id=payload.get('event_id') or payload.get('eventId'),
            sampling_id=payload.get('sampling_id') or payload.get('samplingId'),
            stock_id=payload.get('stock_id') or payload.get('stockId'),
            transaction_id=payload.get('transaction_id') or payload.get('transactionId'),
            # Workflow
            status=payload.get('status') or ExpenseStatus.DRAFT,
            submitted_by=payload.get('submitted_by') or payload.get('submittedBy'),
            approved_by=payload.get('approved_by') or payload.get('approvedBy'),
            rejected_by=payload.get('rejected_by') or payload.get('rejectedBy'),
            rejection_reason=payload.get('rejection_reason') or payload.get('rejectionReason'),
            # Audit
            recorded_by=payload.get('recorded_by') or payload.get('recordedBy') or payload.get('user_key'),
            notes=payload.get('notes'),
            description=payload.get('description'),
            tags=payload.get('tags') or [],
            attachments=payload.get('attachments') or [],
            metadata=payload.get('metadata') or payload.get('extra') or {},
            # Recurring
            is_recurring=payload.get('is_recurring') or payload.get('isRecurring') or False,
            recurring_frequency=payload.get('recurring_frequency') or payload.get('recurringFrequency'),
            recurring_end_date=payload.get('recurring_end_date') or payload.get('recurringEndDate'),
        )

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> 'ExpenseDTO':
        """Create ExpenseDTO from MongoDB document."""
        if doc is None:
            return None

        # Convert _id to string
        expense_id = doc.get('expense_id') or str(doc.get('_id', ''))

        return cls(
            expense_id=expense_id,
            account_key=doc.get('account_key'),
            category=doc.get('category'),
            subcategory=doc.get('subcategory'),
            detail=doc.get('detail'),
            category_path=doc.get('category_path'),
            amount=doc.get('amount'),
            currency=doc.get('currency', 'INR'),
            tax_amount=doc.get('tax_amount'),
            tax_rate=doc.get('tax_rate'),
            gst=doc.get('gst'),
            total_amount=doc.get('total_amount'),
            action=doc.get('action', 'pay'),
            expense_type=doc.get('type') or doc.get('expense_type'),
            payment_method=doc.get('payment_method'),
            payment_status=doc.get('payment_status'),
            payment_date=doc.get('payment_date'),
            payment_reference=doc.get('payment_reference'),
            vendor=doc.get('vendor'),
            vendor_id=doc.get('vendor_id'),
            recipient=doc.get('recipient'),
            invoice_number=doc.get('invoice_number') or doc.get('invoice_no'),
            receipt_number=doc.get('receipt_number'),
            invoice_date=doc.get('invoice_date'),
            due_date=doc.get('due_date'),
            pond_id=doc.get('pond_id'),
            species=doc.get('species'),
            event_id=doc.get('event_id'),
            sampling_id=doc.get('sampling_id'),
            stock_id=doc.get('stock_id'),
            transaction_id=doc.get('transaction_id'),
            status=doc.get('status', ExpenseStatus.DRAFT),
            submitted_by=doc.get('submitted_by'),
            submitted_at=doc.get('submitted_at'),
            approved_by=doc.get('approved_by'),
            approved_at=doc.get('approved_at'),
            rejected_by=doc.get('rejected_by'),
            rejected_at=doc.get('rejected_at'),
            rejection_reason=doc.get('rejection_reason'),
            recorded_by=doc.get('recorded_by'),
            created_at=doc.get('created_at'),
            updated_at=doc.get('updated_at'),
            notes=doc.get('notes'),
            description=doc.get('description'),
            tags=doc.get('tags', []),
            attachments=doc.get('attachments', []),
            metadata=doc.get('metadata', {}),
            is_recurring=doc.get('is_recurring', False),
            recurring_frequency=doc.get('recurring_frequency'),
            recurring_end_date=doc.get('recurring_end_date'),
        )

    def to_db_doc(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        doc = {
            'expense_id': self.expense_id,
            'account_key': self.account_key,
            # Category
            'category': self.category,
            'subcategory': self.subcategory,
            'detail': self.detail,
            'category_path': self.category_path,
            # Financial
            'amount': self.amount,
            'currency': self.currency,
            'tax_amount': self.tax_amount,
            'tax_rate': self.tax_rate,
            'gst': self.gst,
            'total_amount': self.total_amount,
            # Action/Type
            'action': self.action,
            'type': self.expense_type,
            # Payment
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'payment_date': self.payment_date,
            'payment_reference': self.payment_reference,
            # Vendor
            'vendor': self.vendor,
            'vendor_id': self.vendor_id,
            'recipient': self.recipient,
            # Invoice
            'invoice_number': self.invoice_number,
            'receipt_number': self.receipt_number,
            'invoice_date': self.invoice_date,
            'due_date': self.due_date,
            # Links
            'pond_id': self.pond_id,
            'species': self.species,
            'event_id': self.event_id,
            'sampling_id': self.sampling_id,
            'stock_id': self.stock_id,
            'transaction_id': self.transaction_id,
            # Workflow
            'status': self.status,
            'submitted_by': self.submitted_by,
            'submitted_at': self.submitted_at,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at,
            'rejected_by': self.rejected_by,
            'rejected_at': self.rejected_at,
            'rejection_reason': self.rejection_reason,
            # Audit
            'recorded_by': self.recorded_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            # Additional
            'notes': self.notes,
            'description': self.description,
            'tags': self.tags,
            'attachments': self.attachments,
            'metadata': self.metadata,
            # Recurring
            'is_recurring': self.is_recurring,
            'recurring_frequency': self.recurring_frequency,
            'recurring_end_date': self.recurring_end_date,
        }
        # Remove None values
        return {k: v for k, v in doc.items() if v is not None}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            'id': self.expense_id,
            'expenseId': self.expense_id,
            'accountKey': self.account_key,
            # Category
            'category': self.category,
            'subcategory': self.subcategory,
            'detail': self.detail,
            'categoryPath': self.category_path,
            # Financial
            'amount': self.amount,
            'currency': self.currency,
            'taxAmount': self.tax_amount,
            'taxRate': self.tax_rate,
            'gst': self.gst,
            'totalAmount': self.total_amount,
            # Action/Type
            'action': self.action,
            'type': self.expense_type,
            # Payment
            'paymentMethod': self.payment_method,
            'paymentStatus': self.payment_status,
            'paymentDate': self.payment_date,
            'paymentReference': self.payment_reference,
            # Vendor
            'vendor': self.vendor,
            'vendorId': self.vendor_id,
            'recipient': self.recipient,
            # Invoice
            'invoiceNumber': self.invoice_number,
            'receiptNumber': self.receipt_number,
            'invoiceDate': self.invoice_date,
            'dueDate': self.due_date,
            # Links
            'pondId': self.pond_id,
            'species': self.species,
            'eventId': self.event_id,
            'samplingId': self.sampling_id,
            'stockId': self.stock_id,
            'transactionId': self.transaction_id,
            # Workflow
            'status': self.status,
            'submittedBy': self.submitted_by,
            'submittedAt': self.submitted_at,
            'approvedBy': self.approved_by,
            'approvedAt': self.approved_at,
            'rejectedBy': self.rejected_by,
            'rejectedAt': self.rejected_at,
            'rejectionReason': self.rejection_reason,
            # Audit
            'recordedBy': self.recorded_by,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at,
            # Additional
            'notes': self.notes,
            'description': self.description,
            'tags': self.tags,
            'attachments': self.attachments,
            'metadata': self.metadata,
            # Recurring
            'isRecurring': self.is_recurring,
            'recurringFrequency': self.recurring_frequency,
            'recurringEndDate': self.recurring_end_date,
        }

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the expense data.

        Returns (is_valid, list_of_errors)
        """
        errors = []

        if not self.amount and not self.total_amount:
            errors.append("Amount is required")

        if self.amount is not None and self.amount < 0:
            errors.append("Amount cannot be negative")

        if not self.category:
            errors.append("Category is required")

        if self.action and self.action not in ExpenseAction.all():
            errors.append(f"Invalid action: {self.action}")

        if self.status and self.status.lower() not in [s.lower() for s in ExpenseStatus.all()]:
            errors.append(f"Invalid status: {self.status}")

        return len(errors) == 0, errors

    def mark_paid(self, payment_method: str = None, payment_reference: str = None, paid_by: str = None):
        """Mark the expense as paid."""
        self.status = ExpenseStatus.PAID
        self.payment_status = 'completed'
        self.payment_date = get_time_date_dt(include_time=True).isoformat()
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        self.updated_at = get_time_date_dt(include_time=True).isoformat()

    def approve(self, approver_id: str, notes: str = None):
        """Approve the expense."""
        self.status = ExpenseStatus.APPROVED
        self.approved_by = approver_id
        self.approved_at = get_time_date_dt(include_time=True).isoformat()
        if notes:
            self.notes = (self.notes or '') + f"\nApproval note: {notes}"
        self.updated_at = get_time_date_dt(include_time=True).isoformat()

    def reject(self, rejector_id: str, reason: str):
        """Reject the expense."""
        self.status = ExpenseStatus.REJECTED
        self.rejected_by = rejector_id
        self.rejected_at = get_time_date_dt(include_time=True).isoformat()
        self.rejection_reason = reason
        self.updated_at = get_time_date_dt(include_time=True).isoformat()

    def cancel(self, reason: str = None):
        """Cancel the expense."""
        self.status = ExpenseStatus.CANCELLED
        if reason:
            self.notes = (self.notes or '') + f"\nCancellation reason: {reason}"
        self.updated_at = get_time_date_dt(include_time=True).isoformat()

