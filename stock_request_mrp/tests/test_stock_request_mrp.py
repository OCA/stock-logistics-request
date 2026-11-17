# Copyright 2016-24 ForgeFlow S.L. (https://www.forgeflow.com)
# Copyright 2022-24 Tecnativa - Pedro M. Baeza
# Copyright 2022-24 Tecnativa - Víctor Martínez
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0).

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.modules.module import load_script
from odoo.tests import Form, new_test_user
from odoo.tools import file_path

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
        self.route_manufacture.product_selectable = True
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
                "uom_id": product_id.uom_id.id,
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

        self.assertEqual("views" in action, True)
        self.assertEqual(action["res_id"], stock_request.production_ids[0].id)

        action = stock_request.production_ids[0].action_view_stock_request()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_id"], stock_request.id)

        action = order.action_view_mrp_production()

        self.assertEqual("views" in action, True)
        self.assertEqual(action["res_id"], order.production_ids[0].id)

    def test_read_access_mrp_user(self):
        stock_request = self.stock_request.create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 5.0,
                "requested_by": self.stock_request_manager.id,
            }
        )
        both_user = new_test_user(
            self.env,
            login="stock_request_mrp_user",
            groups="stock_request.group_stock_request_user,mrp.group_mrp_user",
        )
        domain = [("id", "=", stock_request.id)]
        # A requester that is also a manufacturing user only reads their own
        # or followed requests
        self.assertFalse(self.stock_request.with_user(both_user).search(domain))
        stock_request.message_subscribe(partner_ids=both_user.partner_id.ids)
        self.assertEqual(
            self.stock_request.with_user(both_user).search(domain), stock_request
        )

    def test_allocation_in_request_uom(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        stock_request = self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": dozen.id,
                "product_uom_qty": 1.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.action_confirm()
        allocation = stock_request.allocation_ids
        # The allocation is expressed in the UoM of the request
        self.assertEqual(allocation.requested_product_uom_qty, 1.0)
        self.assertEqual(allocation.requested_product_qty, 12.0)
        self.assertEqual(stock_request.qty_in_progress, 1.0)

    def test_byproduct_is_not_allocated(self):
        byproduct = self._create_product("BP", "Byproduct", False)
        self.bom.write(
            {
                "byproduct_ids": [
                    Command.create({"product_id": byproduct.id, "product_qty": 1.0})
                ]
            }
        )
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        stock_request = order.stock_request_ids
        # Only the finished product counts for the request
        self.assertEqual(stock_request.allocation_ids.product_id, self.product)
        self.assertEqual(stock_request.qty_in_progress, 5.0)

    def _create_direct_request(self, qty):
        return self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": qty,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )

    def _produce_with_backorder(self, production, qty, user=None):
        production = production.with_user(user) if user else production
        self._produce(production, qty)
        res = production.button_mark_done()
        self.env[res["res_model"]].with_user(user or self.env.user).with_context(
            **res["context"]
        ).create({}).action_backorder()
        return (
            self.env["mrp.production"].search([("origin", "=", production.origin)])
            - production
        )

    def test_backorder_allocation(self):
        stock_request = self._create_direct_request(5.0)
        stock_request.action_confirm()
        production = stock_request.production_ids
        backorder = self._produce_with_backorder(production, 2.0)
        backorder_allocation = stock_request.allocation_ids.filtered(
            lambda a: a.stock_move_id.production_id == backorder
        )
        self.assertEqual(backorder_allocation.requested_product_uom_qty, 3.0)
        self.assertEqual(stock_request.qty_done, 2.0)
        self.assertEqual(stock_request.qty_in_progress, 3.0)

    def test_partial_production_by_manufacturing_user(self):
        mrp_user = new_test_user(
            self.env, login="stock_request_mrp_only", groups="mrp.group_mrp_user"
        )
        stock_request = self._create_direct_request(5.0)
        stock_request.action_confirm()
        production = stock_request.production_ids
        backorder = self._produce_with_backorder(production, 2.0, user=mrp_user)
        self.assertEqual(backorder.product_qty, 3.0)
        self.assertEqual(stock_request.qty_done, 2.0)
        self.assertEqual(stock_request.qty_in_progress, 3.0)

    def test_batch_size_allocation(self):
        self.bom.write({"enable_batch_size": True, "batch_size": 2.0})
        stock_request = self._create_direct_request(5.0)
        stock_request.action_confirm()
        self.assertEqual(len(stock_request.production_ids), 3)
        self.assertEqual(
            sorted(stock_request.allocation_ids.mapped("requested_product_uom_qty")),
            [1.0, 2.0, 2.0],
        )
        self.assertEqual(stock_request.qty_in_progress, 5.0)

    def test_requests_added_to_the_same_production(self):
        reference = self.env["stock.reference"].create({"name": "Shared reference"})
        requests = self.stock_request
        for qty in (4.0, 3.0):
            stock_request = self._create_direct_request(qty)
            stock_request.reference_ids = reference
            requests |= stock_request
        requests.action_confirm()
        production = requests.production_ids
        self.assertEqual(len(production), 1)
        self.assertEqual(production.product_qty, 7.0)
        for stock_request in requests:
            self.assertEqual(stock_request.production_ids, production)
            self.assertEqual(
                stock_request.qty_in_progress, stock_request.product_uom_qty
            )

    def test_requester_without_manufacturing_group(self):
        requester = new_test_user(
            self.env,
            login="stock_request_no_mrp",
            groups="stock_request.group_stock_request_user",
        )
        self.bom.write({"enable_batch_size": True, "batch_size": 2.0})
        reference = self.env["stock.reference"].create({"name": "Batch reference"})
        stock_request = self.stock_request.with_user(requester).create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 4.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.sudo().reference_ids = reference
        stock_request.action_confirm()
        stock_request = stock_request.sudo()
        productions = stock_request.production_ids
        self.assertEqual(len(productions), 2)
        self.assertEqual(
            stock_request.allocation_ids.mapped("requested_product_uom_qty"), [2.0, 2.0]
        )
        for production in productions:
            self._mark_done(production)
        self.assertEqual(stock_request.state, "done")
        self.assertEqual(stock_request.qty_done, 4.0)

    def test_partial_production_of_a_request_the_user_cannot_read(self):
        user = new_test_user(
            self.env,
            login="stock_request_mrp_both",
            groups="mrp.group_mrp_user,stock_request.group_stock_request_user",
        )
        stock_request = self._create_direct_request(5.0)
        stock_request.action_confirm()
        production = stock_request.production_ids
        self.assertFalse(production.with_user(user).stock_request_ids)
        backorder = self._produce_with_backorder(production, 2.0, user=user)
        backorder_allocation = stock_request.allocation_ids.filtered(
            lambda a: a.stock_move_id.production_id == backorder
        )
        self.assertEqual(backorder_allocation.requested_product_uom_qty, 3.0)
        self.assertEqual(stock_request.qty_in_progress, 3.0)

    def test_manufacturing_user_cannot_create_allocations_through_moves(self):
        mrp_user = new_test_user(
            self.env, login="stock_request_mrp_no_alloc", groups="mrp.group_mrp_user"
        )
        stock_request = self._create_direct_request(5.0)
        stock_request.action_confirm()
        production = stock_request.production_ids
        finished_move = production.move_finished_ids
        with self.assertRaises(AccessError):
            self.env["stock.move"].with_user(mrp_user).create(
                {
                    "product_id": self.product.id,
                    "product_uom_qty": 1.0,
                    "location_id": finished_move.location_id.id,
                    "location_dest_id": finished_move.location_dest_id.id,
                    "production_id": production.id,
                    "allocation_ids": [
                        Command.create(
                            {
                                "stock_request_id": stock_request.id,
                                "requested_product_uom_qty": 50.0,
                            }
                        )
                    ],
                }
            )

    def _leave_as_before_install(self, stock_requests):
        """Unlink the requests from their MOs and leave them open"""
        self.env.flush_all()
        self.env.cr.execute(
            "DELETE FROM stock_request_allocation WHERE stock_request_id IN %s",
            (tuple(stock_requests.ids),),
        )
        self.env.cr.execute(
            "DELETE FROM mrp_production_stock_request_rel WHERE stock_request_id IN %s",
            (tuple(stock_requests.ids),),
        )
        self.env.cr.execute(
            "UPDATE stock_request SET state = 'open' WHERE id IN %s",
            (tuple(stock_requests.ids),),
        )
        self.env.invalidate_all()
        self.assertEqual(set(stock_requests.mapped("state")), {"open"})

    def _mark_done(self, production):
        res = production.button_mark_done()
        if isinstance(res, dict):
            self.env[res["res_model"]].with_context(**res["context"]).create(
                {}
            ).process()

    def test_post_init_hook_done_manufacturing_order(self):
        stock_request = self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 5.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.action_confirm()
        production = stock_request.production_ids
        self._mark_done(production)
        self._leave_as_before_install(stock_request)
        link_existing_mos_to_stock_request(self.env)
        self.assertEqual(stock_request.production_ids, production)
        self.assertEqual(stock_request.state, "done")
        self.assertEqual(stock_request.qty_done, 5.0)

    def test_post_init_hook_manufacturing_order_from_order(self):
        order = self._create_stock_request(self.stock_request_user, [(self.product, 5)])
        order.action_confirm()
        stock_request = order.stock_request_ids
        production = stock_request.production_ids
        self.assertEqual(production.origin, order.name)
        self._mark_done(production)
        self._leave_as_before_install(stock_request)
        link_existing_mos_to_stock_request(self.env)
        self.assertEqual(stock_request.production_ids, production)
        self.assertEqual(order.production_ids, production)
        self.assertEqual(stock_request.state, "done")
        self.assertEqual(stock_request.qty_done, 5.0)

    def test_post_init_hook_manufacturing_order_with_backorder(self):
        stock_request = self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 5.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.action_confirm()
        production = stock_request.production_ids
        self._produce(production, 2.0)
        res = production.button_mark_done()
        self.env[res["res_model"]].with_context(**res["context"]).create(
            {}
        ).action_backorder()
        backorder = (
            self.env["mrp.production"].search([("origin", "=", production.origin)])
            - production
        )
        self.assertEqual(backorder.product_qty, 3.0)
        self._mark_done(backorder)
        self._leave_as_before_install(stock_request)
        link_existing_mos_to_stock_request(self.env)
        self.assertEqual(stock_request.production_ids, production | backorder)
        self.assertEqual(stock_request.state, "done")
        self.assertEqual(stock_request.qty_done, 5.0)

    def test_post_init_hook_order_with_two_requests_of_the_same_product(self):
        order = self._create_stock_request(
            self.stock_request_user, [(self.product, 4), (self.product, 3)]
        )
        order.action_confirm()
        stock_requests = order.stock_request_ids
        productions = self.env["mrp.production"].search([("origin", "=", order.name)])
        for production in productions:
            self._mark_done(production)
        self._leave_as_before_install(stock_requests)
        link_existing_mos_to_stock_request(self.env)
        self.assertEqual(order.production_ids, productions)
        for stock_request in stock_requests:
            self.assertEqual(stock_request.state, "done")
            self.assertEqual(stock_request.qty_done, stock_request.product_uom_qty)

    def _run_migration_scripts(self, modules=("stock_request", "stock_request_mrp")):
        """Run the scripts of stock_request and of this module, in this order"""
        for module in modules:
            script = load_script(
                file_path(f"{module}/migrations/20.0.1.0.0/post-migration.py"),
                f"{module}_post_migration",
            )
            script.migrate(self.env.cr, "19.0.1.0.0")

    def _add_byproduct(self):
        byproduct = self._create_product("BP", "Byproduct", False)
        self.bom.write(
            {
                "byproduct_ids": [
                    Command.create({"product_id": byproduct.id, "product_qty": 1.0})
                ]
            }
        )
        return byproduct

    def test_migration_fix_allocations_stored_in_19(self):
        byproduct = self._add_byproduct()
        dozen = self.env.ref("uom.product_uom_dozen")
        stock_request = self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": dozen.id,
                "product_uom_qty": 1.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.action_confirm()
        # Leave the allocations as they were stored in 19.0: in the UoM of the
        # product, and the byproduct allocated too
        stock_request.allocation_ids.requested_product_uom_qty = 12.0
        byproduct_move = stock_request.production_ids.move_finished_ids.filtered(
            lambda m: m.product_id == byproduct
        )
        self.env["stock.request.allocation"].create(
            {
                "stock_request_id": stock_request.id,
                "stock_move_id": byproduct_move.id,
                "requested_product_uom_qty": 12.0,
            }
        )
        self.assertEqual(stock_request.qty_in_progress, 24.0)
        self._run_migration_scripts()
        allocation = stock_request.allocation_ids
        self.assertEqual(allocation.stock_move_id.product_id, self.product)
        self.assertEqual(allocation.requested_product_uom_qty, 1.0)
        self.assertEqual(allocation.requested_product_qty, 12.0)
        self.assertEqual(stock_request.qty_in_progress, 1.0)

    def _legacy_request_with_byproduct_and_backorder(self, produced_qty):
        """A request of 5 as it was stored in 19.0 after producing part of it:
        the byproducts counted as done, the backorder took the full quantity
        and the request is done"""
        byproduct = self._add_byproduct()
        stock_request = self.stock_request.sudo().create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "product_uom_qty": 5.0,
                "company_id": self.main_company.id,
                "warehouse_id": self.warehouse.id,
                "location_id": self.warehouse.lot_stock_id.id,
            }
        )
        stock_request.action_confirm()
        production = stock_request.production_ids
        self._produce(production, produced_qty)
        res = production.button_mark_done()
        self.env[res["res_model"]].with_context(**res["context"]).create(
            {}
        ).action_backorder()
        backorder = (
            self.env["mrp.production"].search([("origin", "=", production.origin)])
            - production
        )
        allocation_obj = self.env["stock.request.allocation"]
        for mo, allocated_qty in ((production, produced_qty), (backorder, 0.0)):
            allocation_obj.create(
                {
                    "stock_request_id": stock_request.id,
                    "stock_move_id": mo.move_finished_ids.filtered(
                        lambda m: m.product_id == byproduct
                    ).id,
                    "requested_product_uom_qty": 5.0,
                    "allocated_product_qty": allocated_qty,
                }
            )
        backorder_allocation = stock_request.allocation_ids.filtered(
            lambda a: (
                a.stock_move_id.production_id == backorder
                and a.stock_move_id.product_id == self.product
            )
        )
        backorder_allocation.requested_product_uom_qty = 5.0
        stock_request.state = "done"
        return stock_request, backorder_allocation

    def test_migration_reopen_request_closed_by_byproducts(self):
        (
            stock_request,
            backorder_allocation,
        ) = self._legacy_request_with_byproduct_and_backorder(3.0)
        self.assertEqual(stock_request.qty_done, 6.0)
        self._run_migration_scripts()
        self.assertEqual(
            stock_request.allocation_ids.stock_move_id.product_id, self.product
        )
        self.assertEqual(backorder_allocation.requested_product_uom_qty, 2.0)
        self.assertEqual(stock_request.qty_done, 3.0)
        self.assertEqual(stock_request.qty_in_progress, 2.0)
        self.assertEqual(stock_request.state, "open")

    def test_migration_keep_request_closed_by_hand(self):
        (
            stock_request,
            backorder_allocation,
        ) = self._legacy_request_with_byproduct_and_backorder(1.0)
        self.assertEqual(stock_request.qty_done, 2.0)
        self._run_migration_scripts()
        self.assertEqual(backorder_allocation.requested_product_uom_qty, 4.0)
        self.assertEqual(stock_request.qty_done, 1.0)
        self.assertEqual(stock_request.state, "done")

    def test_migration_fix_batch_size_allocations_stored_in_19(self):
        self.bom.write({"enable_batch_size": True, "batch_size": 5.0})
        stock_request = self._create_direct_request(7.0)
        stock_request.action_confirm()
        # As stored in 19.0: each production got the full quantity
        stock_request.allocation_ids.requested_product_uom_qty = 7.0
        self.assertEqual(stock_request.qty_in_progress, 14.0)
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertEqual(
            sorted(stock_request.allocation_ids.mapped("requested_product_uom_qty")),
            [2.0, 5.0],
        )
        self.assertEqual(stock_request.qty_in_progress, 7.0)

    def _legacy_merged_requests(self):
        """Two requests merged into the same production, the second one left
        without production as in previous versions"""
        reference = self.env["stock.reference"].create({"name": "Shared reference"})
        first = self._create_direct_request(4.0)
        second = self._create_direct_request(3.0)
        (first | second).reference_ids = reference
        first.action_confirm()
        second.action_confirm()
        production = first.production_ids
        self.assertEqual(production.product_qty, 7.0)
        self._leave_as_before_install(second)
        second.modified(["allocation_ids"])
        self.assertEqual(second.qty_in_progress, 0.0)
        return first, second, production

    def test_migration_link_request_merged_into_a_production(self):
        first, second, production = self._legacy_merged_requests()
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertEqual(second.production_ids, production)
        self.assertEqual(second.qty_in_progress, 3.0)
        self.assertEqual(first.qty_in_progress, 4.0)

    def test_migration_link_request_merged_without_reference(self):
        # In 18.0 a request without procurement group was merged into any
        # open production of the product
        first = self._create_direct_request(4.0)
        first.action_confirm()
        production = first.production_ids
        second = self._create_direct_request(3.0)
        self._leave_as_before_install(second)
        self.env["change.production.qty"].create(
            {"mo_id": production.id, "product_qty": 7.0}
        ).change_prod_qty()
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertEqual(second.production_ids, production)
        self.assertEqual(second.qty_in_progress, 3.0)
        self.assertEqual(first.qty_in_progress, 4.0)

    def test_migration_link_request_merged_into_a_done_production(self):
        first, second, production = self._legacy_merged_requests()
        self._produce(production, 7.0)
        self._mark_done(production)
        self.assertEqual(first.state, "done")
        self.assertEqual(second.state, "open")
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertEqual(second.production_ids, production)
        self.assertEqual(second.qty_done, 3.0)
        self.assertEqual(second.state, "done")

    def test_migration_do_not_link_merged_request_with_another_candidate(self):
        second = self._legacy_merged_requests()[1]
        other = self._create_direct_request(2.0)
        self._leave_as_before_install(other)
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertFalse(second.production_ids)
        self.assertFalse(other.production_ids)

    def test_migration_do_not_link_merged_request_after_a_quantity_change(self):
        second, production = self._legacy_merged_requests()[1:]
        self.env["change.production.qty"].create(
            {"mo_id": production.id, "product_qty": 8.0}
        ).change_prod_qty()
        self._run_migration_scripts(modules=("stock_request_mrp",))
        self.assertFalse(second.production_ids)
        self.assertEqual(second.qty_in_progress, 0.0)
