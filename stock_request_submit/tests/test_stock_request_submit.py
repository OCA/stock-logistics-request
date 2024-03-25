# Copyright 2017-2020 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields

from odoo.addons.stock_request.tests.test_stock_request import TestStockRequest

from ..hooks import uninstall_hook


class TestStockRequestSubmit(TestStockRequest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.route_ids = [(6, 0, cls.route.ids)]
        vals = {
            "company_id": cls.main_company.id,
            "warehouse_id": cls.warehouse.id,
            "location_id": cls.warehouse.lot_stock_id.id,
            "expected_date": fields.Datetime.now(),
            "stock_request_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": cls.product.id,
                        "product_uom_id": cls.product.uom_id.id,
                        "product_uom_qty": 5.0,
                        "company_id": cls.main_company.id,
                        "warehouse_id": cls.warehouse.id,
                        "location_id": cls.warehouse.lot_stock_id.id,
                        "expected_date": fields.Datetime.now(),
                    },
                )
            ],
        }
        cls.order = cls.request_order.with_user(cls.stock_request_user).create(vals)
        cls.stock_request = cls.order.stock_request_ids

    def test_stock_request_submit(self):
        self.order.action_submit()
        self.assertEqual(self.order.state, "submitted")
        self.assertEqual(self.stock_request.state, "submitted")
        self.order.with_user(self.stock_request_manager).action_confirm()
        self.assertEqual(self.order.state, "open")
        self.assertEqual(self.stock_request.state, "open")

    def test_uninstall_hook(self):
        # Check state before uninstall
        self.order.action_submit()
        self.assertEqual(self.order.state, "submitted")
        self.assertEqual(self.stock_request.state, "submitted")

        # Uninstall this module
        uninstall_hook(self.cr, self.registry)

        # Check state after uninstall
        self.assertEqual(self.order.state, "draft")
        self.assertEqual(self.stock_request.state, "draft")
