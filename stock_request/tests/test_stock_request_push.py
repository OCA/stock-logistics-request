# Copyright 2026 ForgeFlow S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command

from .test_stock_request import TestStockRequest


class TestStockRequestPush(TestStockRequest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transit_loc = cls._create_location(
            name="Transit",
            location_id=cls.warehouse.view_location_id.id,
            company_id=cls.main_company.id,
        )
        cls.final_loc = cls._create_location(
            name="Final",
            location_id=cls.warehouse.view_location_id.id,
            company_id=cls.main_company.id,
        )
        cls.to_transit_type = cls.warehouse.int_type_id.copy(
            {
                "name": "To Transit",
                "sequence_code": "TOTR",
                "default_location_src_id": cls.ressuply_loc.id,
                "default_location_dest_id": cls.transit_loc.id,
            }
        )
        cls.from_transit_type = cls.warehouse.int_type_id.copy(
            {
                "name": "From Transit",
                "sequence_code": "FRTR",
                "default_location_src_id": cls.transit_loc.id,
                "default_location_dest_id": cls.final_loc.id,
            }
        )
        cls.push_route = cls._create_route(
            name="Transfer in two steps", company_id=cls.main_company.id
        )
        cls.env["stock.rule"].create(
            {
                "name": "Ressuply to Final through Transit",
                "route_id": cls.push_route.id,
                "location_src_id": cls.ressuply_loc.id,
                "location_dest_id": cls.final_loc.id,
                "action": "pull",
                "picking_type_id": cls.to_transit_type.id,
                "procure_method": "make_to_stock",
                "warehouse_id": cls.warehouse.id,
                "company_id": cls.main_company.id,
            }
        )
        cls.push_rule = cls.env["stock.rule"].create(
            {
                "name": "Transit to Final",
                "route_id": cls.push_route.id,
                "location_src_id": cls.transit_loc.id,
                "location_dest_id": cls.final_loc.id,
                "action": "push",
                "picking_type_id": cls.from_transit_type.id,
                "warehouse_id": cls.warehouse.id,
                "company_id": cls.main_company.id,
            }
        )
        cls.product.write({"route_ids": [Command.set(cls.push_route.ids)]})
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.ressuply_loc, 20.0
        )

    def _create_order(self, *quantities):
        return self.request_order.create(
            {
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.final_loc.id,
                "stock_request_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_id": self.product.uom_id.id,
                            "product_uom_qty": qty,
                            "route_id": self.push_route.id,
                            "company_id": self.main_company.id,
                            "warehouse_id": self.warehouse.id,
                            "location_id": self.final_loc.id,
                        }
                    )
                    for qty in quantities
                ],
            }
        )

    def test_push_step_keeps_request_open_until_final_location(self):
        order = self._create_order(10.0)
        order.action_confirm()
        stock_request = order.stock_request_ids
        first_picking = stock_request.picking_ids
        self.assertEqual(first_picking.picking_type_id, self.to_transit_type)
        self.assertEqual(first_picking.location_dest_id, self.transit_loc)
        first_picking.move_line_ids.write({"quantity": 10.0, "picked": True})
        first_picking.button_validate()
        self.assertEqual(stock_request.state, "open")
        self.assertEqual(stock_request.qty_done, 0.0)
        self.assertEqual(stock_request.qty_in_progress, 10.0)
        second_picking = stock_request.picking_ids - first_picking
        self.assertEqual(second_picking.picking_type_id, self.from_transit_type)
        self.assertEqual(second_picking.move_ids.product_uom_qty, 10.0)
        second_picking.move_ids.write({"picked": True})
        second_picking.button_validate()
        self.assertEqual(stock_request.qty_done, 10.0)
        self.assertEqual(stock_request.qty_in_progress, 0.0)
        self.assertEqual(stock_request.state, "done")
        self.assertEqual(order.state, "done")

    def test_push_step_delivers_what_was_picked(self):
        order = self._create_order(10.0)
        order.action_confirm()
        stock_request = order.stock_request_ids
        first_picking = stock_request.picking_ids
        first_picking.move_line_ids.write({"quantity": 8.0, "picked": True})
        action = first_picking.button_validate()
        self.env[action["res_model"]].with_context(**action["context"]).create(
            {"pick_ids": [Command.link(first_picking.id)]}
        ).process_cancel_backorder()
        self.assertFalse(first_picking.backorder_ids)
        self.assertEqual(stock_request.qty_done, 0.0)
        self.assertEqual(stock_request.qty_in_progress, 8.0)
        self.assertEqual(stock_request.qty_cancelled, 2.0)
        second_picking = stock_request.picking_ids - first_picking
        self.assertEqual(second_picking.move_ids.product_uom_qty, 8.0)
        second_picking.move_ids.write({"picked": True})
        second_picking.button_validate()
        self.assertEqual(stock_request.qty_done, 8.0)
        self.assertEqual(stock_request.qty_in_progress, 0.0)
        self.assertEqual(stock_request.qty_cancelled, 2.0)

    def test_push_step_cancels_the_request_left_without_quantity(self):
        order = self._create_order(6.0, 4.0)
        order.action_confirm()
        first_picking = order.picking_ids
        self.assertEqual(len(first_picking.move_ids), 1)
        self.assertEqual(
            first_picking.move_ids.allocation_ids.stock_request_id,
            order.stock_request_ids,
        )
        first_picking.move_line_ids.write({"quantity": 3.0, "picked": True})
        action = first_picking.button_validate()
        self.env[action["res_model"]].with_context(**action["context"]).create(
            {"pick_ids": [Command.link(first_picking.id)]}
        ).process_cancel_backorder()
        second_picking = order.picking_ids - first_picking
        self.assertEqual(second_picking.move_ids.product_uom_qty, 3.0)
        served = second_picking.move_ids.allocation_ids.stock_request_id
        left = order.stock_request_ids - served
        self.assertEqual(len(served), 1)
        self.assertEqual(served.qty_in_progress, 3.0)
        self.assertEqual(left.state, "cancel")
        self.assertEqual(left.qty_in_progress, 0.0)
        self.assertEqual(left.qty_cancelled, left.product_uom_qty)
        self.assertEqual(left.picking_ids, first_picking)

    def test_cancelled_push_step_cancels_the_request(self):
        order = self._create_order(10.0)
        order.action_confirm()
        stock_request = order.stock_request_ids
        first_picking = stock_request.picking_ids
        first_picking.move_ids.write({"quantity": 10.0, "picked": True})
        first_picking.button_validate()
        second_picking = stock_request.picking_ids - first_picking
        self.assertEqual(stock_request.qty_in_progress, 10.0)
        second_picking.action_cancel()
        self.assertEqual(stock_request.qty_done, 0.0)
        self.assertEqual(stock_request.qty_in_progress, 0.0)
        self.assertEqual(stock_request.qty_cancelled, 10.0)
        self.assertEqual(stock_request.state, "cancel")
        self.assertEqual(order.state, "cancel")

    def test_cancelled_push_step_cancels_every_request_of_the_move(self):
        order = self._create_order(6.0, 4.0)
        order.action_confirm()
        first_picking = order.picking_ids
        self.assertEqual(len(first_picking.move_ids), 1)
        first_picking.move_ids.write({"quantity": 10.0, "picked": True})
        first_picking.button_validate()
        second_picking = order.picking_ids - first_picking
        self.assertEqual(len(second_picking.move_ids), 1)
        second_picking.action_cancel()
        for stock_request in order.stock_request_ids:
            self.assertEqual(stock_request.qty_done, 0.0)
            self.assertEqual(stock_request.qty_cancelled, stock_request.product_uom_qty)
            self.assertEqual(stock_request.state, "cancel")
        self.assertEqual(order.state, "cancel")

    def test_cancelled_push_step_keeps_the_backorder_in_progress(self):
        order = self._create_order(10.0)
        order.action_confirm()
        stock_request = order.stock_request_ids
        first_picking = stock_request.picking_ids
        first_picking.move_ids.write({"quantity": 4.0, "picked": True})
        action = first_picking.button_validate()
        self.env[action["res_model"]].with_context(**action["context"]).create(
            {"pick_ids": [Command.link(first_picking.id)]}
        ).process()
        backorder = first_picking.backorder_ids
        second_picking = stock_request.picking_ids - first_picking - backorder
        self.assertEqual(second_picking.move_ids.product_uom_qty, 4.0)
        second_picking.action_cancel()
        self.assertEqual(stock_request.qty_done, 0.0)
        self.assertEqual(stock_request.qty_in_progress, 6.0)
        self.assertEqual(stock_request.qty_cancelled, 4.0)
        self.assertEqual(stock_request.state, "open")
        backorder.move_ids.write({"quantity": 6.0, "picked": True})
        backorder.button_validate()
        last_picking = backorder.move_ids.move_dest_ids.picking_id
        self.assertEqual(last_picking.move_ids.product_uom_qty, 6.0)
        last_picking.move_ids.write({"picked": True})
        last_picking.button_validate()
        self.assertEqual(stock_request.qty_done, 6.0)
        self.assertEqual(stock_request.qty_in_progress, 0.0)
        self.assertEqual(stock_request.qty_cancelled, 4.0)
        self.assertEqual(stock_request.state, "done")

    def test_without_push_rule_request_is_done_on_first_step(self):
        self.push_rule.write({"active": False})
        order = self._create_order(10.0)
        order.action_confirm()
        stock_request = order.stock_request_ids
        picking = stock_request.picking_ids
        picking.move_ids.write({"picked": True})
        picking.button_validate()
        self.assertEqual(picking.location_dest_id, self.transit_loc)
        self.assertEqual(stock_request.qty_done, 10.0)
        self.assertEqual(stock_request.qty_cancelled, 0.0)
        self.assertEqual(stock_request.state, "done")
