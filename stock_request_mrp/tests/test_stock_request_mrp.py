# Copyright 2016-24 ForgeFlow S.L. (https://www.forgeflow.com)
# Copyright 2022-24 Tecnativa - Pedro M. Baeza
# Copyright 2022-24 Tecnativa - Víctor Martínez
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form

from odoo.addons.stock_request.tests.test_stock_request import TestStockRequest
from odoo.addons.stock_request_mrp.hooks import link_existing_mos_to_stock_request


class TestStockRequestMrp(TestStockRequest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mrp_user_group = cls.env.ref("mrp.group_mrp_user")

    def setUp(self):
        super().setUp()
        self.stock_request_user.write({"group_ids": [(4, self.mrp_user_group.id)]})
        self.stock_request_manager.write({"group_ids": [(4, self.mrp_user_group.id)]})
        self.route_manufacture = self.warehouse.manufacture_pull_id.route_id
        self.product.write({"route_ids": [(6, 0, self.route_manufacture.ids)]})
        self.raw_1 = self._create_product("SL", "Sole", False)
        self._update_qty_in_location(self.warehouse.lot_stock_id, self.raw_1, 10)
        self.raw_2 = self._create_product("LC", "Lace", False)
        self._update_qty_in_location(self.warehouse.lot_stock_id, self.raw_2, 10)

        self.bom = self._create_mrp_bom(self.product, [self.raw_1, self.raw_2])

        self.uom_pair = self.env["uom.uom"].create(
            {
                "name": "Test-Pair",
                "relative_uom_id": self.uom_unit.id,
                "relative_factor": 2,
                "rounding": 0.001,
            }
        )

    @classmethod
    def _update_qty_in_location(self, location, product, quantity):
        self.env["stock.quant"]._update_available_quantity(product, location, quantity)

    @classmethod
    def _create_mrp_bom(self, product_id, raw_materials):
        bom = self.env["mrp.bom"].create(
            {
                "product_id": product_id.id,
                "product_tmpl_id": product_id.product_tmpl_id.id,
                "product_uom_id": product_id.uom_id.id,
                "product_qty": 1.0,
                "type": "normal",
            }
        )
        for raw_mat in raw_materials:
            self.env["mrp.bom.line"].create(
                {"bom_id": bom.id, "product_id": raw_mat.id, "product_qty": 1}
            )

        return bom

    def _produce(self, mo, qty=0.0):
        mo_form = Form(mo)
        mo_form.qty_producing = qty
        mo_form.save()

    def _create_stock_request(self, user, products):
        order_form = Form(
            self.request_order.with_user(user).with_context(
                default_company_id=self.main_company.id,
                default_warehouse_id=self.warehouse.id,
                default_location_id=self.warehouse.lot_stock_id.id,
            )
        )
        order_form.expected_date = fields.Datetime.now()
        for product_data in products:
            with order_form.stock_request_ids.new() as item_form:
                item_form.product_id = product_data[0]
                item_form.product_uom_qty = product_data[1]
        return order_form.save()

    def test_create_request_01(self):
        """Single Stock request with buy rule"""
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        self.assertEqual(order.state, "open")
        self.assertEqual(order.stock_request_ids.state, "open")

        order.invalidate_model()

        self.assertEqual(len(order.production_ids), 1)
        self.assertEqual(len(order.stock_request_ids.production_ids), 1)
        self.assertEqual(order.stock_request_ids.qty_in_progress, 5.0)

        manufacturing_order = order.production_ids[0]
        self.assertEqual(manufacturing_order.state, "confirmed")
        self.assertEqual(
            manufacturing_order.company_id, order.stock_request_ids[0].company_id
        )
        res = manufacturing_order.button_mark_done()
        if isinstance(res, dict):
            wizard_model = (
                self.env[res["res_model"]].with_context(**res["context"]).create({})
            )
            wizard_model.process()
        self.assertEqual(order.stock_request_ids.qty_in_progress, 0.0)
        self.assertEqual(order.stock_request_ids.qty_done, 5.0)
        order2 = order.copy()
        self.assertFalse(order2.production_ids)

    def test_stock_request_order_action_cancel(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        production = order.stock_request_ids.production_ids[:1]
        self.assertEqual(production.state, "confirmed")
        order.with_context(bypass_confirm_wizard=True).action_cancel()
        self.assertEqual(production.state, "cancel")

    def test_stock_request_order_production_action_cancel(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        production = order.stock_request_ids.production_ids[:1]
        self.assertEqual(production.state, "confirmed")
        production.action_cancel()
        self.assertEqual(order.state, "cancel")

    def test_view_actions(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()

        stock_request = order.stock_request_ids

        action = stock_request.action_view_mrp_production()

        self.assertEqual("views" in action.keys(), True)
        self.assertEqual(action["res_id"], stock_request.production_ids[0].id)

        action = stock_request.production_ids[0].action_view_stock_request()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_id"], stock_request.id)

        action = order.action_view_mrp_production()

        self.assertEqual("views" in action.keys(), True)
        self.assertEqual(action["res_id"], order.production_ids[0].id)

    def test_post_init_hook(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        stock_request = order.stock_request_ids
        production = stock_request.production_ids
        self.assertEqual(len(production), 1)
        # Simulate an MO created from a stock request before the module was installed
        production.origin = stock_request.name
        self.env["stock.request.allocation"].search(
            [("stock_request_id", "=", stock_request.id)]
        ).unlink()
        production.stock_request_ids = [(5,)]
        self.assertFalse(stock_request.production_ids)
        production.action_assign()
        self._produce(production, 5.0)
        self.assertTrue(production.finished_move_line_ids)
        self.assertEqual(stock_request.qty_done, 0.0)
        link_existing_mos_to_stock_request(self.env)
        self.assertEqual(production.stock_request_ids, stock_request)
        self.assertEqual(
            stock_request.allocation_ids.stock_move_id, production.move_finished_ids
        )
        self.assertEqual(stock_request.allocation_ids.allocated_product_qty, 5.0)
        self.assertEqual(stock_request.qty_done, 5.0)

    def test_view_actions_multi(self):
        order = self._create_stock_request(
            self.stock_request_user, [(self.product, 5), (self.product, 3)]
        )
        order.action_confirm()
        order.invalidate_model()
        self.assertEqual(len(order.production_ids), 2)
        self.assertEqual(order.production_count, 2)
        action = order.action_view_mrp_production()
        self.assertEqual(action["domain"], [("id", "in", order.production_ids.ids)])
        request_1, request_2 = order.stock_request_ids
        production_2 = request_2.production_ids
        request_1.production_ids = [(4, production_2.id)]
        self.assertEqual(request_1.production_count, 2)
        self.assertEqual(production_2.stock_request_count, 2)
        action = request_1.action_view_mrp_production()
        self.assertEqual(action["domain"], [("id", "in", request_1.production_ids.ids)])
        action = production_2.action_view_stock_request()
        self.assertEqual(
            action["domain"], [("id", "in", production_2.stock_request_ids.ids)]
        )

    def test_production_company_constraint(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        production = self.env["mrp.production"].create(
            {
                "product_id": self.product_company_2.id,
                "product_qty": 1.0,
                "product_uom_id": self.product_company_2.uom_id.id,
                "company_id": self.company_2.id,
                "picking_type_id": self.wh2.manu_type_id.id,
            }
        )
        self.assertFalse(production.stock_request_ids)
        with self.assertRaises(ValidationError):
            order.stock_request_ids.production_ids = [(4, production.id)]
