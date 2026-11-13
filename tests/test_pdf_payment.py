"""Payment gate checks without contacting Razorpay or charging a card."""

import hashlib
import hmac
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import main
from version_b_service import Activity, DayPlan, TripPlan


class PaidPdfTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plan = TripPlan(
            overview="A short Coorg trip", estimated_total_inr=5000,
            days=[DayPlan(title="Day 1", intro="Explore", activities=[
                Activity(time="Morning", title="Abbey Falls", description="Visit the falls"),
                Activity(time="Evening", title="Town", description="Walk around town"),
            ])],
        )
        self.request = SimpleNamespace(state=SimpleNamespace(user_id="user-1"))
        self.signature = hmac.new(b"secret", b"order_123|pay_123", hashlib.sha256).hexdigest()

    def payload(self, signature=None):
        return main.PaidPdfRequest(
            destination="Coorg", plan=self.plan, razorpay_order_id="order_123",
            razorpay_payment_id="pay_123", razorpay_signature=signature or self.signature,
        )

    async def test_order_binds_account_and_exact_plan(self):
        with patch.object(main, "_payment_keys", return_value=("rzp_test_key", "secret")), \
             patch.object(main, "_razorpay", new_callable=AsyncMock,
                          return_value={"id": "order_123", "amount": 4900}) as provider:
            result = await main.v2_pdf_order(
                main.PdfRequest(destination="Coorg", plan=self.plan), self.request)
        self.assertTrue(result["test_mode"])
        sent = provider.await_args.kwargs["json"]
        self.assertEqual(sent["notes"]["user_id"], "user-1")
        self.assertEqual(sent["notes"]["plan_digest"], main._plan_digest("Coorg", self.plan))
        self.assertEqual(sent["amount"], 4900)

    async def test_rejects_invalid_signature_before_fetching_payment(self):
        with patch.object(main, "_payment_keys", return_value=("rzp_test_key", "secret")), \
             patch.object(main, "_razorpay", new_callable=AsyncMock) as provider:
            with self.assertRaises(HTTPException) as error:
                await main.v2_pdf(self.payload("0" * 64), self.request)
            self.assertEqual(error.exception.status_code, 403)
            provider.assert_not_awaited()

    async def test_rejects_payment_for_another_account(self):
        order = {"id": "order_123", "status": "paid", "amount": 4900,
                 "currency": "INR", "notes": {"user_id": "user-2",
                 "plan_digest": main._plan_digest("Coorg", self.plan)}}
        payment = {"id": "pay_123", "order_id": "order_123", "status": "captured",
                   "amount": 4900, "currency": "INR"}
        with patch.object(main, "_payment_keys", return_value=("rzp_test_key", "secret")), \
             patch.object(main, "_razorpay", new_callable=AsyncMock, side_effect=[order, payment]):
            with self.assertRaises(HTTPException) as error:
                await main.v2_pdf(self.payload(), self.request)
            self.assertEqual(error.exception.status_code, 403)

    async def test_rejects_uncaptured_payment(self):
        order = {"id": "order_123", "status": "attempted", "amount": 4900,
                 "currency": "INR", "notes": {"user_id": "user-1",
                 "plan_digest": main._plan_digest("Coorg", self.plan)}}
        payment = {"id": "pay_123", "order_id": "order_123", "status": "authorized",
                   "amount": 4900, "currency": "INR"}
        with patch.object(main, "_payment_keys", return_value=("rzp_test_key", "secret")), \
             patch.object(main, "_razorpay", new_callable=AsyncMock, side_effect=[order, payment]):
            with self.assertRaises(HTTPException) as error:
                await main.v2_pdf(self.payload(), self.request)
            self.assertEqual(error.exception.status_code, 403)

    async def test_paid_pdf_is_returned_privately(self):
        order = {"id": "order_123", "status": "paid", "amount": 4900,
                 "currency": "INR", "notes": {"user_id": "user-1",
                 "plan_digest": main._plan_digest("Coorg", self.plan)}}
        payment = {"id": "pay_123", "order_id": "order_123", "status": "captured",
                   "amount": 4900, "currency": "INR"}
        def fake_pdf(destination, plan, directory):
            Path(directory, "test.pdf").write_bytes(b"%PDF-test")
            return "test.pdf"
        with patch.object(main, "_payment_keys", return_value=("rzp_test_key", "secret")), \
             patch.object(main, "_razorpay", new_callable=AsyncMock, side_effect=[order, payment]), \
             patch.object(main, "save_v2_pdf", side_effect=fake_pdf):
            result = await main.v2_pdf(self.payload(), self.request)
        self.assertEqual(result.body, b"%PDF-test")
        self.assertEqual(result.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
