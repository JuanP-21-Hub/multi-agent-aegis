import unittest
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from app.transactions import TransferRequest, install_transactions


class MemoryLedger:
    def __init__(self):
        self.accounts = {
            1: {'id': 1, 'customer_id': 11, 'balance': 5000, 'status': 'ACTIVE', 'account_pin_hash': '1234'},
            2: {'id': 2, 'customer_id': 22, 'balance': 0, 'status': 'ACTIVE', 'account_pin_hash': '5678'},
        }
        self.requests = {}
        self.entries = []

    def __enter__(self):
        self.snapshot = deepcopy((self.accounts, self.requests, self.entries))
        return self

    def __exit__(self, error, *_):
        if error:
            self.accounts, self.requests, self.entries = self.snapshot

    def cursor(self, **kwargs):
        return self

    def execute(self, query, values):
        query = ' '.join(query.split())
        if 'FOR NO KEY UPDATE' in query:
            self.rows = [self.accounts[key] for key in values if key in self.accounts]
        elif query.startswith('INSERT INTO transfer_requests'):
            customer, request, source, dest, amount = values
            if (customer, request) in self.requests:
                self.rows = []
            else:
                self.requests[customer, request] = {
                    'source_id': source, 'destination_id': dest, 'amount': amount,
                }
                self.rows = [(request,)]
        elif query.startswith('SELECT source_id'):
            self.rows = [self.requests[values]]
        elif query.startswith('UPDATE accounts'):
            balance, key = values
            self.accounts[key]['balance'] = balance
        elif query.startswith('INSERT INTO transactions'):
            self.entries.append(values)
        else:
            raise AssertionError(query)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.ledger = MemoryLedger()
        core = SimpleNamespace(
            bearer_scheme=lambda: None, get_db=lambda: self.ledger,
            password_hasher=SimpleNamespace(verify=self.verify_pin),
            VerificationError=ValueError, InvalidHashError=TypeError,
        )
        app = FastAPI()
        install_transactions(app, core)
        self.transfer = next(route.endpoint for route in app.routes if route.path == '/api/transfers')

    @staticmethod
    def verify_pin(expected, actual):
        if expected != actual:
            raise ValueError('Invalid PIN')

    def call(self, body, customer=11):
        return self.transfer(body, Request({'type': 'http'}), {'customer_id': customer})

    def request(self, **kwargs):
        return TransferRequest(**({'from_account': 1, 'to_account': 2, 'amount': 1000,
                                   'account_pin': '1234', 'request_id': uuid4()} | kwargs))

    def test_transfer_and_retry_only_debit_once(self):
        body = self.request()
        self.assertEqual(self.call(body), self.call(body))
        self.assertEqual([a['balance'] for a in self.ledger.accounts.values()], [4000, 1000])
        self.assertEqual(len(self.ledger.entries), 2)
        with self.assertRaises(HTTPException) as conflict:
            self.call(body.model_copy(update={'amount': 3000}))
        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(len(self.ledger.entries), 2)

    def test_insufficient_balance_does_not_reserve_request(self):
        body = self.request(amount=6000)
        with self.assertRaises(HTTPException) as failure:
            self.call(body)
        self.assertEqual(failure.exception.status_code, 409)
        self.assertFalse(self.ledger.requests)
        self.assertFalse(self.ledger.entries)

    def test_ownership_and_pin_are_both_required(self):
        for body, customer in ((self.request(), 22), (self.request(account_pin='4321'), 11)):
            with self.assertRaises(HTTPException) as failure:
                self.call(body, customer)
            self.assertEqual(failure.exception.status_code, 403)
        self.assertEqual([a['balance'] for a in self.ledger.accounts.values()], [5000, 0])
        self.assertFalse(self.ledger.entries)
