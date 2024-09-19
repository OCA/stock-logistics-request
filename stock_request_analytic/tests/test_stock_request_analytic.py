# Copyright 2017-2020 ForgeFlow, S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields
from odoo.tests import Form, new_test_user
from odoo.tests.common import users

from odoo.addons.base.tests.common import BaseCommon


class TestStockRequestAnalytic(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Model
        cls.AccountAnalyticAccount = cls.env["account.analytic.account"]
        cls.ProductProduct = cls.env["product.product"]
        cls.StockRequest = cls.env["stock.request"]
        cls.StockRequestOrder = cls.env["stock.request.order"]
        cls.StockLocation = cls.env["stock.location"]
        cls.StockLocationRoute = cls.env["stock.route"]
        cls.StockRule = cls.env["stock.rule"]

        # Data
        cls.expected_date = fields.Datetime.now()
        cls.main_company = cls.env.ref("base.main_company")
        cls.warehouse = cls.env.ref("stock.warehouse0")
        plan = cls.env["account.analytic.plan"].create({"name": __name__})
        analytic_account = cls.AccountAnalyticAccount.create(
            {"name": "Analytic", "plan_id": plan.id}
        )
        cls.analytic_distribution = {str(analytic_account.id): 100}
        cls.demand_loc = cls.StockLocation.create(
            {
                "name": "demand_loc",
                "location_id": cls.warehouse.lot_stock_id.id,
                "usage": "internal",
            }
        )
        demand_route = cls.StockLocationRoute.create(
            {
                "name": "Transfer",
                "product_categ_selectable": False,
                "product_selectable": True,
                "company_id": cls.main_company.id,
                "sequence": 10,
            }
        )
        cls.StockRule.create(
            {
                "name": "Transfer",
                "route_id": demand_route.id,
                "location_src_id": cls.warehouse.lot_stock_id.id,
                "location_dest_id": cls.demand_loc.id,
                "action": "pull",
                "picking_type_id": cls.warehouse.int_type_id.id,
                "procure_method": "make_to_stock",
                "warehouse_id": cls.warehouse.id,
                "company_id": cls.main_company.id,
            }
        )
        cls.product = cls.ProductProduct.create(
            {
                "name": "Test Product",
                "type": "product",
                "route_ids": [(6, 0, demand_route.ids)],
            }
        )
        cls.user = new_test_user(
            cls.env,
            login="stock_request_user",
            groups=(
                "stock_request.group_stock_request_user,"
                "analytic.group_analytic_accounting,"
                "stock.group_stock_user"
            ),
        )

    def prepare_order_request_analytic(self, analytic_distribution, company):
        vals = {
            "company_id": company.id,
            "warehouse_id": self.warehouse.id,
            "location_id": self.demand_loc.id,
            "expected_date": self.expected_date,
            "stock_request_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_uom_id": self.product.uom_id.id,
                        "product_uom_qty": 5.0,
                        "analytic_distribution": analytic_distribution,
                        "company_id": company.id,
                        "warehouse_id": self.warehouse.id,
                        "location_id": self.demand_loc.id,
                        "expected_date": self.expected_date,
                    },
                )
            ],
        }
        return vals

    def test_stock_analytic(self):
        vals = self.prepare_order_request_analytic(
            self.analytic_distribution,
            self.main_company,
        )
        order = self.StockRequestOrder.create(vals)
        req = order.stock_request_ids
        order.action_confirm()
        self.assertEqual(req.move_ids.analytic_distribution, self.analytic_distribution)

    @users("stock_request_user")
    def test_default_analytic(self):
        """
        Create request order with a default analytic
        """
        vals = self.prepare_order_request_analytic(False, self.main_company)
        vals.update(
            {
                "analytic_distribution": self.analytic_distribution,
            }
        )
        order = self.StockRequestOrder.with_user(self.user).create(vals)
        with Form(order) as order_form:
            with order_form.stock_request_ids.new() as line_form:
                line_form.product_id = self.product
                line_form.product_uom_qty = 5.0
                self.assertEqual(
                    line_form.analytic_distribution,
                    self.analytic_distribution,
                )
