# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import new_test_user, users

from odoo.addons.base.tests.common import BaseCommon


class TestStockRequestCatalog(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.location = cls.warehouse.lot_stock_id
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Catalog Product",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
            }
        )
        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "Catalog Product 2",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
            }
        )
        cls.service = cls.env["product.product"].create(
            {"name": "Catalog Service", "type": "service"}
        )
        cls.user = new_test_user(
            cls.env,
            login="stock_request_catalog_user",
            groups="stock_request.group_stock_request_user",
        )
        cls.order = cls.env["stock.request.order"].create(
            {
                "warehouse_id": cls.warehouse.id,
                "location_id": cls.location.id,
                "company_id": cls.company.id,
                "requested_by": cls.user.id,
            }
        )

    @users("stock_request_catalog_user")
    def test_update_creates_line(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 3)
        line = order.stock_request_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.product_uom_qty, 3)
        self.assertEqual(line.product_uom_id, self.product.uom_id)
        self.assertEqual(line.warehouse_id, self.warehouse)
        self.assertEqual(line.location_id, self.location)

    @users("stock_request_catalog_user")
    def test_update_existing_line(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 3)
        order._update_order_line_info(self.product.id, 7)
        self.assertEqual(len(order.stock_request_ids), 1)
        self.assertEqual(order.stock_request_ids.product_uom_qty, 7)

    @users("stock_request_catalog_user")
    def test_update_zero_removes_line(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 3)
        order._update_order_line_info(self.product.id, 0)
        self.assertFalse(order.stock_request_ids)

    @users("stock_request_catalog_user")
    def test_record_lines_grouped_by_product(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 3)
        order._update_order_line_info(self.product_2.id, 1)
        grouped = order._get_product_catalog_record_lines(
            [self.product.id, self.product_2.id]
        )
        self.assertEqual(grouped[self.product].product_uom_qty, 3)
        self.assertEqual(grouped[self.product_2].product_uom_qty, 1)

    @users("stock_request_catalog_user")
    def test_lines_data_single(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 5)
        data = order.stock_request_ids._get_product_catalog_lines_data()
        self.assertEqual(data["quantity"], 5)
        self.assertFalse(data["readOnly"])
        self.assertEqual(data["uomDisplayName"], self.product.uom_id.display_name)

    @users("stock_request_catalog_user")
    def test_lines_data_empty_defaults(self):
        data = self.env["stock.request"]._get_product_catalog_lines_data()
        self.assertEqual(data["quantity"], 0.0)
        self.assertEqual(data["price"], 0.0)

    @users("stock_request_catalog_user")
    def test_default_order_line_values_readonly(self):
        order = self.order.with_user(self.env.user)
        self.assertFalse(order._default_order_line_values()["readOnly"])

    @users("stock_request_catalog_user")
    def test_readonly_follows_state(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 2)
        self.assertFalse(order._is_readonly())
        # cancel reaches a non-draft state without launching procurement
        order.action_cancel()
        self.assertTrue(order._is_readonly())
        self.assertTrue(
            order.stock_request_ids._get_product_catalog_lines_data()["readOnly"]
        )

    @users("stock_request_catalog_user")
    def test_update_zero_no_line_is_noop(self):
        order = self.order.with_user(self.env.user)
        self.assertEqual(order._update_order_line_info(self.product.id, 0), 0.0)
        self.assertFalse(order.stock_request_ids)

    @users("stock_request_catalog_user")
    def test_update_zero_keeps_line_when_not_draft(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 2)
        order.action_cancel()
        # not a draft anymore: the line is left untouched instead of removed
        order._update_order_line_info(self.product.id, 0)
        self.assertEqual(len(order.stock_request_ids), 1)

    @users("stock_request_catalog_user")
    def test_record_lines_skip_products_not_requested(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 3)
        order._update_order_line_info(self.product_2.id, 1)
        grouped = order._get_product_catalog_record_lines([self.product.id])
        self.assertIn(self.product, grouped)
        self.assertNotIn(self.product_2, grouped)

    @users("stock_request_catalog_user")
    def test_order_data_has_zero_price(self):
        order = self.order.with_user(self.env.user)
        data = order._get_product_catalog_order_data(self.product)
        self.assertEqual(data[self.product.id]["price"], 0.0)

    @users("stock_request_catalog_user")
    def test_catalog_domain_excludes_services(self):
        order = self.order.with_user(self.env.user)
        found = self.env["product.product"].search(order._get_product_catalog_domain())
        self.assertIn(self.product, found)
        self.assertNotIn(self.service, found)

    @users("stock_request_catalog_user")
    def test_display_stock_in_catalog(self):
        order = self.order.with_user(self.env.user)
        self.assertTrue(order._is_display_stock_in_catalog())

    @users("stock_request_catalog_user")
    def test_lines_data_aggregates_same_product(self):
        order = self.order.with_user(self.env.user)
        vals = order._prepare_catalog_request_values(self.product, 2)
        lines = self.env["stock.request"].create(vals) | self.env[
            "stock.request"
        ].create({**vals, "product_uom_qty": 3})
        data = lines._get_product_catalog_lines_data()
        self.assertEqual(data["quantity"], 5)
        self.assertTrue(data["readOnly"])

    @users("stock_request_catalog_user")
    def test_line_action_add_from_catalog(self):
        order = self.order.with_user(self.env.user)
        order._update_order_line_info(self.product.id, 1)
        action = order.stock_request_ids.with_context(
            order_id=order.id
        ).action_add_from_catalog()
        self.assertEqual(action["res_model"], "product.product")
        self.assertEqual(
            action["context"]["product_catalog_order_model"], "stock.request.order"
        )
        self.assertEqual(action["context"]["product_catalog_order_id"], order.id)
