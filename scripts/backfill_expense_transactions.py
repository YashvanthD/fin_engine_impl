"""Backfill script: ensure every expense has a transaction record and expense.transaction_ref set.

Usage: run this script once against your DB (ensure MONGO_URI and MONGO_DB are set to the target DB).
"""
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.repository.transactions_repository import TransactionsRepository
import logging

logging.basicConfig(level=logging.INFO)

def main(limit=1000):
    db = MongoRepositorySingleton.get_db()
    coll = db['expenses']
    tr_repo = TransactionsRepository(db)
    q = {'transaction_ref': {'$exists': False}}
    count = coll.count_documents(q)
    logging.info(f'Found {count} expenses without transaction_ref')
    cursor = coll.find(q).limit(limit)
    processed = 0
    for doc in cursor:
        try:
            expense_id = str(doc.get('_id'))
            tx_payload = {
                'transaction_id': doc.get('transaction_id') or doc.get('transactionId') or None,
                'type': 'expense',
                'subtype': doc.get('category') or doc.get('type'),
                'amount': doc.get('amount'),
                'currency': doc.get('currency') or 'INR',
                'account_key': doc.get('account_key'),
                'pond_id': doc.get('pond_id'),
                'species': doc.get('species'),
                'creditor': doc.get('creditor'),
                'debited': doc.get('debited'),
                'payment_method': doc.get('payment_method'),
                'invoice_no': doc.get('invoice_no'),
                'gst': doc.get('gst'),
                'tax': doc.get('tax'),
                'recorded_by': doc.get('recorded_by')
            }
            res = tr_repo.create_transaction(tx_payload)
            tx_id = getattr(res, 'inserted_id', None)
            if tx_id:
                coll.update_one({'_id': doc['_id']}, {'$set': {'transaction_ref': str(tx_id)}})
                processed += 1
                logging.info(f'Backfilled expense {expense_id} -> tx {tx_id}')
        except Exception:
            logging.exception(f'Failed to backfill expense {doc.get("_id")}')
    logging.info(f'Processed {processed} expenses')

if __name__ == '__main__':
    main()
