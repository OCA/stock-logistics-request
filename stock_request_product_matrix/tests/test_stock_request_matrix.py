# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import Command
from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestStockRequestMatrix(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.location = cls.warehouse.lot_stock_id

        attribute_color = cls.env["product.attribute"].create(
            {
                "name": "Color",
                "create_variant": "always",
                "value_ids": [
                    Command.create({"name": "Red"}),
                    Command.create({"name": "Blue"}),
                ],
            }
        )
        attribute_size = cls.env["product.attribute"].create(
            {
                "name": "Size",
                "create_variant": "always",
                "value_ids": [
                    Command.create({"name": "S"}),
                    Command.create({"name": "M"}),
                ],
            }
        )
        cls.template = cls.env["product.template"].create(
            {
                "name": "Matrix Shirt",
                "type": "consu",
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute_color.id,
                            "value_ids": [Command.set(attribute_color.value_ids.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": attribute_size.id,
                            "value_ids": [Command.set(attribute_size.value_ids.ids)],
                        }
                    ),
                ],
            }
        )

    def _new_order(self):
        return self.env["stock.request.order"].create(
            {
                "warehouse_id": self.warehouse.id,
                "location_id": self.location.id,
            }
        )

    def _matrix_cells(self, matrix):
        return [
            cell
            for row in matrix["matrix"]
            for cell in row
            if cell.get("ptav_ids") is not None
        ]

    def _variant_for_cell(self, cell):
        return self.template.product_variant_ids.filtered(
            lambda variant, cell=cell: sorted(
                variant.product_template_attribute_value_ids.ids
            )
            == cell["ptav_ids"]
        )

    def _apply_changes(self, order, changes):
        order.grid = json.dumps(
            {"product_template_id": self.template.id, "changes": changes}
        )
        order.grid_update = True
        order._apply_grid()

    def test_get_matrix_reports_existing_quantities(self):
        self.assertEqual(len(self.template.product_variant_ids), 4)
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        self.assertEqual(len(cells), 4)
        self.assertTrue(all(cell["qty"] == 0 for cell in cells))

        self._apply_changes(order, [{"ptav_ids": cells[0]["ptav_ids"], "qty": 7}])
        cells = self._matrix_cells(order._get_matrix(self.template))
        matched = [c for c in cells if c["ptav_ids"] == cells[0]["ptav_ids"]]
        self.assertEqual(matched[0]["qty"], 7)

    def test_apply_grid_creates_one_line_per_cell(self):
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        self._apply_changes(
            order,
            [
                {"ptav_ids": cells[0]["ptav_ids"], "qty": 3},
                {"ptav_ids": cells[1]["ptav_ids"], "qty": 5},
            ],
        )
        lines = order.stock_request_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines.mapped("product_id"),
            self._variant_for_cell(cells[0]) | self._variant_for_cell(cells[1]),
        )
        self.assertEqual(sorted(lines.mapped("product_uom_qty")), [3.0, 5.0])
        for line in lines:
            self.assertEqual(line.warehouse_id, self.warehouse)
            self.assertEqual(line.location_id, self.location)
            self.assertEqual(line.company_id, order.company_id)
            self.assertEqual(line.product_uom_id, line.product_id.uom_id)

    def test_apply_grid_removes_line_when_qty_zeroed(self):
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        self._apply_changes(order, [{"ptav_ids": cells[0]["ptav_ids"], "qty": 4}])
        self.assertEqual(len(order.stock_request_ids), 1)
        self._apply_changes(order, [{"ptav_ids": cells[0]["ptav_ids"], "qty": 0}])
        self.assertFalse(order.stock_request_ids)

    def test_apply_grid_collapses_duplicate_lines(self):
        """Several draft lines for one variant collapse onto a single line."""
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        variant = self._variant_for_cell(cells[0])
        common_vals = {
            "warehouse_id": self.warehouse.id,
            "location_id": self.location.id,
            "product_id": variant.id,
            "product_uom_id": variant.uom_id.id,
        }
        order.stock_request_ids = [
            Command.create({**common_vals, "product_uom_qty": 1}),
            Command.create({**common_vals, "product_uom_qty": 2}),
        ]
        self._apply_changes(order, [{"ptav_ids": cells[0]["ptav_ids"], "qty": 9}])
        self.assertEqual(order.stock_request_ids.product_id, variant)
        self.assertEqual(order.stock_request_ids.product_uom_qty, 9)

    def test_apply_grid_updates_line_added_outside_matrix(self):
        """A line otherwise added to the order is re-quantified, not duplicated."""
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        variant = self._variant_for_cell(cells[0])
        self.env["stock.request"].create(
            {
                "order_id": order.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.location.id,
                "product_id": variant.id,
                "product_uom_id": variant.uom_id.id,
                "product_uom_qty": 4,
            }
        )
        # the grid reports the existing quantity...
        cells = self._matrix_cells(order._get_matrix(self.template))
        matched = next(c for c in cells if c["ptav_ids"] == cells[0]["ptav_ids"])
        self.assertEqual(matched["qty"], 4)
        # ...and editing it updates that same line instead of adding a new one
        self._apply_changes(order, [{"ptav_ids": cells[0]["ptav_ids"], "qty": 6}])
        self.assertEqual(len(order.stock_request_ids), 1)
        self.assertEqual(order.stock_request_ids.product_uom_qty, 6)

    def test_form_select_variant_computes_template(self):
        """Picking a variant directly fills the template and the UoM."""
        variant = self.template.product_variant_ids[0]
        # The order is created directly (its warehouse_id is only visible with
        # the multi-locations group); the Form only drives the line editing.
        order = self._new_order()
        with Form(order) as order_form:
            with order_form.stock_request_ids.new() as line:
                line.product_id = variant
                line.product_uom_qty = 2
                self.assertEqual(line.product_template_id, self.template)
                self.assertEqual(line.product_uom_id, variant.uom_id)
        self.assertEqual(order.stock_request_ids.product_id, variant)

    def test_set_grid_up_and_apply_creates_lines(self):
        """The grid onchanges (as the JS calls them) create the lines.

        The grid fields are invisible, so they cannot be driven through a Form;
        this exercises the same server-side onchange path directly.
        """
        order = self._new_order()
        order.grid_product_tmpl_id = self.template
        order._set_grid_up()
        cells = self._matrix_cells(json.loads(order.grid))
        order.grid = json.dumps(
            {
                "product_template_id": self.template.id,
                "changes": [
                    {"ptav_ids": cells[0]["ptav_ids"], "qty": 3},
                    {"ptav_ids": cells[1]["ptav_ids"], "qty": 5},
                ],
            }
        )
        order.grid_update = True
        order._apply_grid()

        lines = order.stock_request_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines.mapped("product_id"),
            self._variant_for_cell(cells[0]) | self._variant_for_cell(cells[1]),
        )
        self.assertEqual(sorted(lines.mapped("product_uom_qty")), [3.0, 5.0])
        for line in lines:
            self.assertEqual(line.warehouse_id, self.warehouse)
            self.assertEqual(line.location_id, self.location)

    def test_search_product_template_id(self):
        variant = self.template.product_variant_ids[0]
        request = self.env["stock.request"].create(
            {
                "warehouse_id": self.warehouse.id,
                "location_id": self.location.id,
                "product_id": variant.id,
                "product_uom_id": variant.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        found = self.env["stock.request"].search(
            [("product_template_id", "=", self.template.id)]
        )
        self.assertIn(request, found)

    def test_apply_grid_noop_when_order_not_draft(self):
        """The grid may not add/remove lines once the order left draft."""
        order = self._new_order()
        cells = self._matrix_cells(order._get_matrix(self.template))
        variant = self._variant_for_cell(cells[0])
        self.env["stock.request"].create(
            {
                "order_id": order.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.location.id,
                "product_id": variant.id,
                "product_uom_id": variant.uom_id.id,
                "product_uom_qty": 1,
            }
        )
        order.stock_request_ids.state = "open"
        self.assertNotEqual(order.state, "draft")

        self._apply_changes(order, [{"ptav_ids": cells[1]["ptav_ids"], "qty": 5}])
        self.assertEqual(len(order.stock_request_ids), 1)
