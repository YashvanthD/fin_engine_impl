"""Aggregate expense-related repositories as a package API.

This module re-exports repository classes implemented in separate files
so callers can import from `fin_server.repository.expenses`.
"""
from .financial_accounts import FinancialAccountsRepository
from .bank_accounts import BankAccountsRepository
from .payment_methods import PaymentMethodsRepository
from .transactions import TransactionsRepository
from .payments import PaymentsRepository
from .bank_statements import BankStatementsRepository, StatementLinesRepository
from .reconciliations import ReconciliationsRepository
from .expense_claims import ExpenseClaimsRepository
from .approvals import ApprovalsRepository
from .settlement_batches import SettlementBatchesRepository
from .audit_logs import AuditLogsRepository
from .expense_categories import (
    ExpenseCategoryRepository,
    load_expense_catalog,
    flatten_categories,
    get_top_level_categories,
    get_subcategories,
    validate_category_path,
    search_categories,
    get_category_suggestions,
    get_expense_category_options,
    normalize_expense_category
)

__all__ = [
    'FinancialAccountsRepository', 'BankAccountsRepository', 'PaymentMethodsRepository',
    'TransactionsRepository', 'PaymentsRepository', 'BankStatementsRepository', 'StatementLinesRepository',
    'ReconciliationsRepository', 'ExpenseClaimsRepository', 'ApprovalsRepository', 'SettlementBatchesRepository',
    'AuditLogsRepository', 'ExpenseCategoryRepository',
    # Category helpers
    'load_expense_catalog', 'flatten_categories', 'get_top_level_categories',
    'get_subcategories', 'validate_category_path', 'search_categories',
    'get_category_suggestions', 'get_expense_category_options', 'normalize_expense_category'
]



