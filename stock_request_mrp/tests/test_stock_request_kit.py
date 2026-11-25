# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command
from odoo.tests import Form, TransactionCase


class TestStockRequestKit(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env.ref("stock.warehouse0")
        cls.source_loc = cls.env["stock.location"].create(
            {
                "name": "Resupply",
                "usage": "internal",
                "location_id": cls.warehouse.view_location_id.id,
            }
        )
        cls.route = cls.env["stock.route"].create(
            {
                "name": "Resupply transfer",
                "product_selectable": True,
                "rule_ids": [
                    Command.create(
                        {
                            "name": "Resupply transfer",
                            "action": "pull",
                            "location_src_id": cls.source_loc.id,
                            "location_dest_id": cls.warehouse.lot_stock_id.id,
                            "picking_type_id": cls.warehouse.int_type_id.id,
                            "procure_method": "make_to_stock",
                            "warehouse_id": cls.warehouse.id,
                        }
                    )
                ],
            }
        )
        product_vals = {"type": "consu", "is_storable": True}
        cls.can = cls.env["product.product"].create(dict(product_vals, name="Can"))
        cls.box = cls.env["product.product"].create(dict(product_vals, name="Box"))
        cls.pack = cls.env["product.product"].create(
            dict(product_vals, name="Pack of 12")
        )
        cls.combo = cls.env["product.product"].create(
            dict(product_vals, name="Two cans in a box")
        )
        for product in cls.can | cls.box:
            cls.env["stock.quant"]._update_available_quantity(
                product, cls.source_loc, 500
            )
        cls._create_kit(cls.pack, [(cls.can, 12)])
        cls._create_kit(cls.combo, [(cls.can, 2), (cls.box, 1)])

    @classmethod
    def _create_kit(cls, product, lines):
        return cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "type": "phantom",
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create({"product_id": component.id, "product_qty": qty})
                    for component, qty in lines
                ],
            }
        )

    def _request(self, product, qty):
        order = self.env["stock.request.order"].create(
            {
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "stock_request_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_id": product.uom_id.id,
                            "product_uom_qty": qty,
                            "warehouse_id": self.warehouse.id,
                            "location_id": self.warehouse.lot_stock_id.id,
                            "route_id": self.route.id,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        return order.stock_request_ids

    def _validate(self, picking, qtys, backorder=True):
        for move in picking.move_ids:
            move.write({"quantity": qtys[move.product_id], "picked": True})
        res = picking.button_validate()
        if (
            isinstance(res, dict)
            and res.get("res_model") == "stock.backorder.confirmation"
        ):
            wizard = Form.from_action(self.env, res).save()
            if backorder:
                wizard.process()
            else:
                wizard.process_cancel_backorder()

    def _assert_qtys(self, request, state, done, in_progress, cancelled):
        self.assertEqual(request.state, state)
        self.assertEqual(request.qty_done, done)
        self.assertEqual(request.qty_in_progress, in_progress)
        self.assertEqual(request.qty_cancelled, cancelled)

    def test_kit_counted_in_kits(self):
        request = self._request(self.pack, 3)
        self.assertEqual(request.move_ids.product_id, self.can)
        self._assert_qtys(request, "open", 0, 3, 0)

        picking = request.picking_ids
        self._validate(picking, {self.can: 12})
        self._assert_qtys(request, "open", 1, 2, 0)

        self._validate(picking.backorder_ids, {self.can: 24})
        self._assert_qtys(request, "done", 3, 0, 0)

    def test_partial_kit_not_counted(self):
        request = self._request(self.pack, 3)
        self._validate(request.picking_ids, {self.can: 18})
        self._assert_qtys(request, "open", 1, 2, 0)

    def test_kit_lowest_component(self):
        request = self._request(self.combo, 4)
        self._validate(request.picking_ids, {self.can: 8, self.box: 1})
        self._assert_qtys(request, "open", 1, 3, 0)

    def test_kit_remaining_cancelled(self):
        request = self._request(self.pack, 3)
        self._validate(request.picking_ids, {self.can: 12}, backorder=False)
        self._assert_qtys(request, "done", 1, 0, 2)
