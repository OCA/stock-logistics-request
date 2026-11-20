# Copyright 2020-24 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging

from odoo import SUPERUSER_ID, Command, api

logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    The objective of this hook is to link existing MOs
    coming from a Stock Request.
    """
    logger.info("Linking existing MOs coming from a Stock Request")
    link_existing_mos_to_stock_request(env)


def link_existing_mos_to_stock_request(env):
    env = api.Environment(env.cr, SUPERUSER_ID, {})
    stock_request_obj = env["stock.request"]
    stock_request_order_obj = env["stock.request.order"]
    mrp_production_obj = env["mrp.production"]
    mos_with_sr = mrp_production_obj.search(
        ["|", ("origin", "ilike", "SR/%"), ("origin", "ilike", "SRO/%")], order="id"
    )
    logger.info(f"Linking {len(mos_with_sr)} MOs records")
    origins = mos_with_sr.mapped("origin")
    stock_requests = stock_request_obj.search(
        ["|", ("name", "in", origins), ("order_id.name", "in", origins)]
    )
    # Quantity of each request still to allocate to a MO, in the product UoM
    pending = {
        request: request.product_qty
        - sum(
            request.allocation_ids.filtered(
                lambda a: (
                    a.stock_move_id.production_id and a.stock_move_id.state != "cancel"
                )
            ).mapped("requested_product_qty")
        )
        for request in stock_requests
    }
    for mo in mos_with_sr:
        # The requests of an order are procured with the name of the order
        candidates = stock_requests.filtered(
            lambda x, mo=mo: (
                x.name == mo.origin
                or (x.order_id.name == mo.origin and x.product_id == mo.product_id)
            )
        )
        if not candidates:
            continue
        linked = candidates.filtered(lambda x, mo=mo: x.name == mo.origin)
        move = mo.move_finished_ids.filtered(
            lambda m, mo=mo: m.product_id == mo.product_id and not m.byproduct_id
        )[:1]
        if move and mo.state != "cancel" and not move.allocation_ids:
            product_uom = move.product_id.uom_id
            to_allocate = move.product_qty
            vals = []
            for request in candidates:
                qty = min(pending[request], to_allocate)
                if product_uom.compare(qty, 0.0) <= 0:
                    continue
                pending[request] -= qty
                to_allocate -= qty
                linked |= request
                vals.append(
                    Command.create(
                        {
                            "stock_request_id": request.id,
                            "requested_product_uom_qty": product_uom._compute_quantity(
                                qty, request.product_uom_id, rounding_method="HALF-UP"
                            ),
                        }
                    )
                )
            if vals:
                logger.info(f"Create allocations for MO {mo.name}")
                move.allocation_ids = vals
        linked |= candidates & move.allocation_ids.stock_request_id
        if not linked:
            continue
        # Link SR to MO
        mo.stock_request_ids = [Command.set(linked.ids)]
        logger.info(f"MO {mo.name} linked to SR {linked.mapped('name')}")
        if move.state == "done":
            # The open quantity of a done move is zero, so allocate the done
            # quantity up to what each allocation requested
            done_qty = sum(
                ml.uom_id._compute_quantity(ml.quantity, ml.product_id.uom_id)
                for ml in move.move_line_ids
            )
            for allocation in move.allocation_ids:
                allocated_qty = max(
                    min(
                        allocation.requested_product_qty
                        - allocation.allocated_product_qty,
                        done_qty,
                    ),
                    0.0,
                )
                allocation.allocated_product_qty += allocated_qty
                done_qty -= allocated_qty
    stock_requests.check_done()
    # Update production_ids from SROs
    stock_request_order_obj.search([])._compute_production_ids()
