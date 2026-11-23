# Copyright 2017 Creu Blanca
# Copyright 2017-2024 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo.exceptions import ValidationError

from .base_test import TestBaseKanban


class TestKanban(TestBaseKanban):
    def setUp(self):
        super().setUp()
        self.main_company = self.env.ref("base.main_company")
        self.warehouse = self.env.ref("stock.warehouse0")
        self.uom_unit = self.env.ref("uom.product_uom_unit")

        # common data
        self.company_2 = self.env["res.company"].create({"name": "Comp2"})
        self.wh2 = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_2.id)], limit=1
        )
        self.wh3 = self.env["stock.warehouse"].create(
            {
                "name": "Warehouse TEst",
                "code": "WH-TEST",
                "company_id": self.main_company.id,
            }
        )

        self.ressuply_loc = self.env["stock.location"].create(
            {"name": "Ressuply", "location_id": self.warehouse.view_location_id.id}
        )
        self.route = self.env["stock.route"].create(
            {
                "name": "Transfer",
                "product_categ_selectable": False,
                "product_selectable": True,
                "company_id": self.main_company.id,
                "sequence": 10,
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Product", "route_ids": [(4, self.route.id)], "company_id": False}
        )
        self.uom_dozen = self.env["uom.uom"].create(
            {
                "name": "Test-DozenA",
                "relative_uom_id": self.uom_unit.id,
                "relative_factor": 12,
                "rounding": 0.001,
            }
        )

        self.env["stock.rule"].create(
            {
                "name": "Transfer",
                "route_id": self.route.id,
                "location_src_id": self.ressuply_loc.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "action": "pull_push",
                "picking_type_id": self.warehouse.int_type_id.id,
                "procure_method": "make_to_stock",
                "warehouse_id": self.warehouse.id,
                "company_id": self.main_company.id,
            }
        )
        self.env["ir.config_parameter"].set_param("stock_request_kanban.crc", "1")

    def test_onchanges(self):
        kanban = self.env["stock.request.kanban"].new({})
        kanban.product_id = self.product
        kanban.onchange_product_id()
        kanban.company_id = self.main_company
        kanban.onchange_company_id()
        self.assertTrue(kanban.warehouse_id)
        kanban.warehouse_id = self.wh2
        kanban.onchange_warehouse_id()
        self.assertEqual(kanban.company_id, self.company_2)
        kanban.location_id = self.warehouse.view_location_id
        kanban.onchange_location_id()
        self.assertEqual(kanban.company_id, self.main_company)
        self.assertEqual(kanban.warehouse_id, self.warehouse)

    def test_create(self):
        kanban = self.env["stock.request.kanban"].new({})
        kanban.product_id = self.product
        kanban.onchange_product_id()
        kanban.product_uom_qty = 1
        kanban = kanban.create(kanban._convert_to_write(kanban._cache))
        self.assertTrue(kanban.company_id)
        self.assertIn(self.route, kanban.route_ids)

    def test_order_barcodes(self):
        kanban_1 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        kanban_2 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        kanban_3 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
                "company_id": self.main_company.id,
                "warehouse_id": self.wh3.id,
                "location_id": self.wh3.lot_stock_id.id,
            }
        )
        order = self.env["stock.request.order"].create(
            {
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        wizard = (
            self.env["wizard.stock.request.order.kanban"]
            .with_context(default_order_id=order.id)
            .create({})
        )
        with self.assertRaises(ValidationError):
            wizard.on_barcode_scanned(kanban_1.name)
        self.pass_code(wizard, kanban_1.name)
        self.assertEqual(wizard.status_state, 0)
        self.assertTrue(
            order.stock_request_ids.filtered(lambda r: r.kanban_id == kanban_1)
        )
        self.pass_code(wizard, kanban_2.name)
        self.assertTrue(
            order.stock_request_ids.filtered(lambda r: r.kanban_id == kanban_2)
        )
        self.assertEqual(wizard.status_state, 0)
        self.pass_code(wizard, kanban_1.name)
        self.assertEqual(wizard.status_state, 1)
        self.pass_code(wizard, kanban_2.name + kanban_1.name)
        self.assertEqual(wizard.status_state, 1)
        with self.assertRaises(ValidationError):
            self.pass_code(wizard, kanban_3.name)

    def test_barcodes(self):
        kanban_1 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        kanban_2 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        kanban_3 = self.env["stock.request.kanban"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        wizard = self.env["wizard.stock.request.kanban"].with_context().create({})
        with self.assertRaises(ValidationError):
            wizard.on_barcode_scanned(kanban_1.name)
        self.assertFalse(
            self.env["stock.request"].search([("kanban_id", "=", kanban_1.id)])
        )
        self.pass_code(wizard, kanban_1.name)
        self.assertEqual(wizard.status_state, 0)
        self.assertTrue(
            self.env["stock.request"].search([("kanban_id", "=", kanban_1.id)])
        )
        self.assertFalse(
            self.env["stock.request"].search([("kanban_id", "=", kanban_2.id)])
        )
        self.pass_code(wizard, kanban_2.name)
        self.assertTrue(
            self.env["stock.request"].search([("kanban_id", "=", kanban_2.id)])
        )
        with self.assertRaises(ValidationError):
            wizard.on_barcode_scanned(kanban_3.name)
        self.assertFalse(
            self.env["stock.request"].search([("kanban_id", "=", kanban_3.id)])
        )
        self.env["ir.config_parameter"].set_param("stock_request_kanban.crc", "0")
        wizard.on_barcode_scanned(kanban_3.name)
        self.assertEqual(wizard.status_state, 0)
        self.assertTrue(
            self.env["stock.request"].search([("kanban_id", "=", kanban_3.id)])
        )

    def _create_kanban(self, **vals):
        values = {
            "product_id": self.product.id,
            "product_uom_id": self.product.uom_id.id,
            "product_uom_qty": 1,
        }
        values.update(vals)
        return self.env["stock.request.kanban"].create(values)

    def _create_order_wizard(self, **vals):
        values = {
            "company_id": self.main_company.id,
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
        }
        values.update(vals)
        order = self.env["stock.request.order"].create(values)
        wizard = (
            self.env["wizard.stock.request.order.kanban"]
            .with_context(default_order_id=order.id)
            .create({})
        )
        return order, wizard

    def test_product_kanban_cards(self):
        template = self.product.product_tmpl_id
        self.assertEqual(self.product.kanban_card_count, 0)
        self.assertEqual(template.kanban_card_count, 0)
        self._create_kanban()
        self._create_kanban()
        self.product.invalidate_recordset(["kanban_card_count"])
        template.invalidate_recordset(["kanban_card_count"])
        self.assertEqual(self.product.kanban_card_count, 2)
        self.assertEqual(template.kanban_card_count, 2)
        action = self.product.action_view_kanban_cards()
        self.assertEqual(action["context"]["default_product_id"], self.product.id)
        self.assertIn(("product_id", "=", self.product.id), action["domain"])
        action = template.action_view_kanban_cards()
        self.assertEqual(action["context"]["default_product_id"], self.product.id)
        self.assertIn(("product_template_id", "=", template.id), action["domain"])

    def test_stock_request_scan_kanban_action(self):
        action = self.env["stock.request"].action_scan_kanban()
        self.assertEqual(action["res_model"], "wizard.stock.request.kanban")
        self.assertEqual(action["target"], "new")

    def test_order_barcodes_not_draft(self):
        kanban_1 = self._create_kanban()
        kanban_2 = self._create_kanban()
        order, wizard = self._create_order_wizard()
        self.pass_code(wizard, kanban_1.name)
        self.assertEqual(wizard.status_state, 0)
        order.action_confirm()
        self.assertNotEqual(order.state, "draft")
        with self.assertRaisesRegex(ValidationError, "draft state"):
            self.pass_code(wizard, kanban_2.name)

    def test_order_barcodes_company(self):
        kanban = self._create_kanban(
            company_id=self.company_2.id,
            warehouse_id=self.wh2.id,
            location_id=self.wh2.lot_stock_id.id,
        )
        _order, wizard = self._create_order_wizard()
        with self.assertRaisesRegex(ValidationError, "Company must be the same"):
            self.pass_code(wizard, kanban.name)

    def test_order_barcodes_references(self):
        reference = self.env["stock.reference"].create({"name": "REF-KANBAN"})
        kanban = self._create_kanban(reference_ids=[(6, 0, reference.ids)])
        _order, wizard = self._create_order_wizard()
        with self.assertRaisesRegex(ValidationError, "References must be the same"):
            self.pass_code(wizard, kanban.name)

    def test_order_barcodes_warehouse(self):
        kanban = self._create_kanban(
            company_id=self.main_company.id,
            warehouse_id=self.wh3.id,
            location_id=self.wh3.lot_stock_id.id,
        )
        _order, wizard = self._create_order_wizard(location_id=self.wh3.lot_stock_id.id)
        with self.assertRaisesRegex(ValidationError, "Warehouse must be the same"):
            self.pass_code(wizard, kanban.name)
