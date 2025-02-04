# Copyright 2019 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form

from .test_stock_return_request_common import StockReturnRequestCase


class PurchaseReturnRequestCase(StockReturnRequestCase):
    def test_01_return_request_to_customer(self):
        """Find pickings from the customer and make the return"""
        self.return_request_customer.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_1.id,
                            "quantity": 12.0,
                        },
                    )
                ],
            }
        )
        self.return_request_customer.action_confirm()
        pickings = self.return_request_customer.returned_picking_ids
        moves = self.return_request_customer.returned_picking_ids.mapped("move_ids")
        # There are two pickings found with 10 units delivered each.
        # The return moves are filled up to the needed quantity
        self.assertEqual(len(pickings), 2)
        self.assertEqual(len(moves), 2)
        self.assertAlmostEqual(sum(moves.mapped("product_uom_qty")), 12.0)
        # Process the return to validate all the pickings
        self.return_request_customer.action_validate()
        self.assertTrue(
            all([True if x == "done" else False for x in pickings.mapped("state")])
        )
        # Now we've got those 12.0 units back in our stock (there were 80.0)
        prod_1_qty = self.prod_1.with_context(
            location=self.wh1.lot_stock_id.id
        ).qty_available
        self.assertAlmostEqual(prod_1_qty, 92.0)

    def test_01_return_request_to_customer_with_lot(self):
        """
        prod_3 has a lot2: 10 units
        - Delivery lot2: 10 units
        - Create and validate RR1: 6 units of lot2
        - Create (not validate, just confirm) RR2: 2 units of lot2
        - Create (not validate, just confirm) RR3: 3 units of lot2
        - Validate RR2: 2 units of lot2 are returned
        - Try to validate RR3: an exception is raised,
            6+2 returned previously
            8 + 3 = 11 > 10
        """
        picking_customer_lot = self.picking_obj.create(
            {
                "partner_id": self.partner_customer.id,
                "picking_type_id": self.wh1.out_type_id.id,
                "move_ids": [
                    Command.create(
                        {
                            "name": self.prod_3.name,
                            "product_id": self.prod_3.id,
                            "product_uom_qty": 10.0,
                            "quantity": 10.0,
                            "picked": True,
                            "location_id": self.wh1.lot_stock_id.id,
                            "location_dest_id": self.customer_loc.id,
                            "move_line_ids": [
                                Command.create(
                                    {
                                        "product_id": self.prod_3.id,
                                        "lot_id": self.prod_3_lot2.id,
                                        "quantity": 10.0,
                                        "picked": True,
                                        "location_id": self.wh1.lot_stock_id.id,
                                        "location_dest_id": self.customer_loc.id,
                                    },
                                )
                            ],
                        },
                    )
                ],
            }
        )
        picking_customer_lot.action_confirm()
        picking_customer_lot.action_assign()
        picking_customer_lot._action_done()
        self.assertAlmostEqual(
            self.prod_3.with_context(lot_id=self.prod_3_lot2.id).qty_available, 0.0
        )
        # Create RR1 with 6 units of lot2
        self.return_request_customer.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot2.id,
                            "quantity": 6.0,
                        },
                    )
                ],
            }
        )
        self.return_request_customer.action_confirm()
        pickings = self.return_request_customer.returned_picking_ids
        self.return_request_customer.action_validate()
        self.assertEqual(pickings.state, "done")
        self.assertAlmostEqual(
            self.prod_3.with_context(lot_id=self.prod_3_lot2.id).qty_available, 6.0
        )
        # Create RR2 with 2 units of lot2
        return_request_2 = self.return_request_customer.copy(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot2.id,
                            "quantity": 2.0,
                        },
                    )
                ],
            }
        )
        return_request_2.action_confirm()
        # Create RR3 with 3 units of lot2
        return_request_3 = self.return_request_customer.copy(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot2.id,
                            "quantity": 3.0,
                        },
                    )
                ],
            }
        )
        return_request_3.action_confirm()
        # Validate RR2
        return_request_2.action_validate()
        self.assertEqual(return_request_2.returned_picking_ids.state, "done")
        self.assertAlmostEqual(
            self.prod_3.with_context(lot_id=self.prod_3_lot2.id).qty_available, 8.0
        )
        # Try validate RR3, an exception is raised
        with self.assertRaisesRegex(
            UserError, "Not enough moves to return this product"
        ):
            return_request_3.action_validate()

    def test_02_return_request_to_supplier(self):
        """Find pickings from the supplier and make the return"""
        self.return_request_supplier.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_1.id,
                            "quantity": 12.0,
                        },
                    )
                ],
            }
        )
        self.return_request_supplier.action_confirm()
        pickings = self.return_request_supplier.returned_picking_ids
        moves = self.return_request_supplier.returned_picking_ids.mapped("move_ids")
        # There are two pickings found with 10 and 90 units. The older beign
        # the one with 10. So two pickings are get.
        # The return moves are filled up to the needed quantity
        self.assertEqual(len(pickings), 2)
        self.assertEqual(len(moves), 2)
        self.assertAlmostEqual(sum(moves.mapped("product_uom_qty")), 12.0)
        # Process the return to validate all the pickings
        self.return_request_supplier.action_validate()
        self.assertTrue(
            all([True if x == "done" else False for x in pickings.mapped("state")])
        )
        # We've returned 12.0 units from the 80.0 we had
        prod_1_qty = self.prod_1.with_context(
            location=self.wh1.lot_stock_id.id
        ).qty_available
        self.assertAlmostEqual(prod_1_qty, 68.0)

    def test_03_return_request_to_supplier_with_lots(self):
        """Find pickings from the supplier and make the return"""
        self.return_request_supplier.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot1.id,
                            "quantity": 50.0,
                        },
                    ),
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot2.id,
                            "quantity": 5.0,
                        },
                    ),
                ],
            }
        )
        self.return_request_supplier.action_confirm()
        pickings = self.return_request_supplier.returned_picking_ids
        moves = self.return_request_supplier.returned_picking_ids.mapped("move_ids")
        # There are two pickings found with that lot and 90 units.
        # The older has 20 and the newer 70, so only 30 units will be returned
        # from the second.
        self.assertEqual(len(pickings), 2)
        self.assertEqual(len(moves), 2)
        self.assertAlmostEqual(sum(moves.mapped("product_uom_qty")), 55.0)
        # Process the return to validate all the pickings
        self.return_request_supplier.action_validate()
        self.assertTrue(
            all([True if x == "done" else False for x in pickings.mapped("state")])
        )
        # We've returned 50.0 units from the 90.0 we had for that lot
        prod_3_qty_lot_1 = self.prod_3.with_context(
            location=self.wh1.lot_stock_id.id, lot_id=self.prod_3_lot1.id
        ).qty_available
        prod_3_qty_lot_2 = self.prod_3.with_context(
            location=self.wh1.lot_stock_id.id, lot_id=self.prod_3_lot2.id
        ).qty_available
        self.assertAlmostEqual(prod_3_qty_lot_1, 40.0)
        self.assertAlmostEqual(prod_3_qty_lot_2, 5.0)

    def test_return_child_location(self):
        picking = self.picking_supplier_1.copy(
            {
                "location_dest_id": self.location_child_1.id,
            }
        )
        picking.move_ids.unlink()
        picking.move_ids = [
            Command.create(
                {
                    "product_id": self.prod_3.id,
                    "name": self.prod_3.name,
                    "product_uom": self.prod_3.uom_id.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                },
            )
        ]
        picking.action_confirm()
        for move in picking.move_ids:
            vals = {
                "picking_id": picking.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_id.uom_id.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "lot_id": self.prod_3_lot3.id,
                "quantity": 30.0,
                "picked": True,
            }
            move.write({"move_line_ids": [(0, 0, vals)], "quantity": 30.0})
        picking._action_done()
        self.return_request_supplier.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_3.id,
                            "lot_id": self.prod_3_lot3.id,
                            "quantity": 30.0,
                        },
                    ),
                ],
            }
        )
        self.return_request_supplier.action_confirm()
        returned_pickings = self.return_request_supplier.returned_picking_ids
        self.assertEqual(
            returned_pickings.mapped("move_line_ids.location_id"), self.location_child_1
        )

    def test_return_request_putaway_from_customer(self):
        """Test that the putaway strategy has been applied"""
        self.return_request_customer.write(
            {
                "line_ids": [
                    Command.create({"product_id": self.prod_1.id, "quantity": 5.0})
                ]
            }
        )
        self.return_request_customer.action_confirm()
        stock_move_lines = self.return_request_customer.returned_picking_ids.mapped(
            "move_line_ids"
        )
        # No putaway strategy is applied
        self.assertEqual(
            stock_move_lines.mapped("location_dest_id"), self.wh1.lot_stock_id
        )

        # Create a putaway rule to test
        self.env["stock.putaway.rule"].create(
            {
                "product_id": self.prod_1.id,
                "location_in_id": self.wh1.lot_stock_id.id,
                "location_out_id": self.location_child_1.id,
            }
        )
        self.return_request_customer.action_cancel()
        self.return_request_customer.action_cancel_to_draft()
        self.return_request_customer.action_confirm()
        stock_move_lines = self.return_request_customer.returned_picking_ids.mapped(
            "move_line_ids"
        )
        self.assertEqual(
            stock_move_lines.mapped("location_dest_id"), self.location_child_1
        )

    def test_return_request_unlink(self):
        """Prevent unlinking a return request that is done"""
        self.return_request_supplier.write(
            {
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.prod_1.id,
                            "quantity": 12.0,
                        },
                    )
                ],
            }
        )
        self.return_request_supplier.action_confirm()
        # Process the return to validate all the pickings
        self.return_request_supplier.action_validate()
        with self.assertRaisesRegex(UserError, "You cannot delete this record"):
            self.return_request_supplier.unlink()

    def test_return_request_suggest_lot(self):
        """
        Test that the return request suggests the lot,
        the prod_3 has three lots:
        - prod_3_lot1 with 20 + 70 units
        - prod_3_lot2 with 10 units
        - prod_3_lot3 with 0 units
        """
        new_line = self.env["stock.return.request.line"].create(
            {
                "request_id": self.return_request_supplier.id,
                "product_id": self.prod_3.id,
                "quantity": 30,
            }
        )
        action = new_line.action_lot_suggestion()
        wizard_id = action["res_id"]
        # check the lots suggested
        suggest_lots_by_sum = self.env["suggest.return.request.lot.line"].search(
            [("wizard_id", "=", wizard_id), ("lot_suggestion_mode", "=", "sum")]
        )
        suggest_lots_by_detail = self.env["suggest.return.request.lot.line"].search(
            [("wizard_id", "=", wizard_id), ("lot_suggestion_mode", "=", "detail")]
        )
        self.assertEqual(len(suggest_lots_by_sum), 2)
        self.assertEqual(len(suggest_lots_by_detail), 3)
        self.assertFalse(
            suggest_lots_by_sum.filtered(lambda x: x.lot_id == self.prod_3_lot3)
        )
        lot_to_suggest = suggest_lots_by_sum.filtered(
            lambda x: x.lot_id == self.prod_3_lot1
        )
        self.assertEqual(len(lot_to_suggest), 1)
        wizard_form = Form(self.env["suggest.return.request.lot"].browse(wizard_id))
        wizard_form.suggested_lot_id = lot_to_suggest
        wizard = wizard_form.save()
        wizard.action_confirm()
        self.assertEqual(new_line.lot_id, self.prod_3_lot1)
        self.return_request_supplier.action_confirm()
        pickings = self.return_request_supplier.returned_picking_ids
        moves = self.return_request_supplier.returned_picking_ids.mapped("move_ids")
        # There are two pickings found with that lot and 90 units.
        self.assertEqual(len(pickings), 2)
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves.move_line_ids.lot_id, self.prod_3_lot1)
        self.assertAlmostEqual(sum(moves.mapped("product_uom_qty")), 30.0)
        self.return_request_supplier.action_validate()
        # We've returned 30.0 units from the 90.0 we had for that lot
        prod_3_qty_lot_1 = self.prod_3.with_context(
            location=self.wh1.lot_stock_id.id, lot_id=self.prod_3_lot1.id
        ).qty_available
        self.assertAlmostEqual(prod_3_qty_lot_1, 60.0)
        self.assertAlmostEqual(sum(moves.mapped("quantity")), 30.0)

    def test_return_request_max_quantty(self):
        """
        Quantity of return request line
        should not exceed the quantity available in stock.
        The prod_3 has three lots:
        - prod_3_lot1 with 20 + 70 units
        - prod_3_lot2 with 10 units
        - prod_3_lot3 with 0 units
        """
        self.env["stock.return.request.line"].create(
            {
                "request_id": self.return_request_supplier.id,
                "product_id": self.prod_3.id,
                "lot_id": self.prod_3_lot1.id,
                "quantity": 101,
            }
        )
        with self.assertRaisesRegex(
            ValidationError, "Not enough moves to return this product"
        ):
            self.return_request_supplier.action_confirm()
